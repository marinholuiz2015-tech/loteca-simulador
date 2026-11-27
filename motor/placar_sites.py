"""
Placar semana a semana: o nosso sistema x Arena do AZ x Vovoteca, nos mesmos concursos e com a mesma
quantidade de secos, duplos e triplos de cada site (so muda ONDE marcar).

Nosso lado: a previsao que o motor gravou na quinta (motor/saida/concurso_N.csv) quando existe;
antes disso, reconstruida com a mesma regra do motor (odds sem margem; sem odds, frequencia historica)
e marcada como "reconstruida".
Arena: coleta/dados/arena_palpites.csv. Vovoteca: matriz de 14 secos (especialistas_palpites.csv,
lida pela IA; se faltar, vovo_matriz.csv).
"""
import collections
import csv
import json
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import camada2 as c2  # noqa: E402

DADOS = os.path.join(RAIZ, "coleta", "dados")
FREQ = np.array([0.472, 0.262, 0.266])


def resultados():
    H = json.load(open(os.path.join(RAIZ, "data", "historico_cef.json")))["concursos"]
    res = {}
    for k, c in H.items():
        js = sorted(c["jogos"], key=lambda j: j["nuSequencial"])
        if len(js) == 14 and all(j["nuGolEquipeUm"] is not None for j in js):
            res[int(k)] = [0 if j["nuGolEquipeUm"] > j["nuGolEquipeDois"] else (1 if j["nuGolEquipeUm"] == j["nuGolEquipeDois"] else 2)
                           for j in js]
    return res


def carregar(arq, col, filtro=None):
    d = collections.defaultdict(dict)
    try:
        for r in csv.DictReader(open(os.path.join(DADOS, arq), encoding="utf-8")):
            if filtro and not filtro(r):
                continue
            if r.get(col):
                d[int(r["concurso"])][int(r["jogo"])] = sorted("1X2".index(x) for x in r[col])
    except FileNotFoundError:
        pass
    return {c: [v[j] for j in range(1, 15)] for c, v in d.items() if len(v) == 14}


def previsao(c, odds):
    arq = os.path.join(AQUI, "saida", f"concurso_{c}.csv")
    if os.path.exists(arq):
        L = sorted(csv.DictReader(open(arq, encoding="utf-8")), key=lambda r: int(r["jogo"]))
        if len(L) == 14:
            return np.array([[float(r["p1"]), float(r["px"]), float(r["p2"])] for r in L]), "gravada"
    if len(odds.get(c, {})) < 10:
        return None, None
    return np.array([c2.prob_mercado(odds[c][j]) if j in odds[c] else FREQ for j in range(1, 15)]), "reconstruida"


def pontos(cart, r):
    return sum(r[i] in cart[i] for i in range(14))


def placar():
    res, odds = resultados(), c2.odds_por_concurso()
    arena = carregar("arena_palpites.csv", "marcas")
    vovo = carregar("especialistas_palpites.csv", "seco", lambda r: r["fonte"] == "vovoteca")
    for c, v in carregar("vovo_matriz.csv", "seco").items():
        vovo.setdefault(c, v)
    out = []
    for c in sorted((set(arena) | set(vovo)) & set(res)):
        P, como = previsao(c, odds)
        if P is None:
            continue
        lin = {"c": c, "previsao": como}
        if c in arena:
            A = arena[c]
            d, t = sum(len(x) == 2 for x in A), sum(len(x) == 3 for x in A)
            N = c2.cartela(P, d, t)
            lin.update({"estrutura": f"{14 - d - t}+{d}+{t}", "arena": pontos(A, res[c]), "nosso_arena": pontos(N, res[c])})
        if c in vovo:
            N = c2.cartela(P, 0, 0)
            lin.update({"vovo": pontos(vovo[c], res[c]), "nosso_vovo": pontos(N, res[c])})
        out.append(lin)
    return out


if __name__ == "__main__":
    L = placar()
    for nome, a, b in (("Arena", "arena", "nosso_arena"), ("Vovoteca", "vovo", "nosso_vovo")):
        X = [x for x in L if a in x]
        d = np.array([x[b] - x[a] for x in X])
        print(f"{nome}: {len(X)} concursos | nosso {np.mean([x[b] for x in X]):.2f} x {np.mean([x[a] for x in X]):.2f} pts | "
              f"nosso melhor {np.mean(d > 0):.0%}, empate {np.mean(d == 0):.0%}, {nome} melhor {np.mean(d < 0):.0%}")
    print(L[-3:])
