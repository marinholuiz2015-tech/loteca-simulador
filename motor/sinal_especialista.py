"""
O palpite de um site traz informacao que a odd nao tem?

Para cada jogo com odd, ajusta q_k proporcional a p_k * exp(b_seco*[k e o seco do site]
+ b_duplo*[k esta no duplo do site]) e mede no tempo: os pesos sao ajustados so com
concursos anteriores (walk-forward) e o ganho de log-loss e medido no concurso seguinte.
forca = ganho medio / erro padrao (por concurso). Acima de 2 = sinal real.
Uso: python motor/sinal_especialista.py > motor/sinal_especialista.md
"""
import collections
import csv
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import camada2 as c2  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(RAIZ, "coleta", "dados")


def resultados():
    H = json.load(open(os.path.join(RAIZ, "data", "historico_cef.json")))["concursos"]
    res = {}
    for k, c in H.items():
        js = sorted(c["jogos"], key=lambda j: j["nuSequencial"])
        if len(js) == 14 and all(j["nuGolEquipeUm"] is not None for j in js):
            res[int(k)] = [0 if j["nuGolEquipeUm"] > j["nuGolEquipeDois"] else
                           (1 if j["nuGolEquipeUm"] == j["nuGolEquipeDois"] else 2) for j in js]
    return res


def fonte(arq, col, chave=lambda r: int(r["concurso"])):
    d = collections.defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(DADOS, arq), encoding="utf-8")):
        d[chave(r)][int(r["jogo"])] = {"1X2".index(x) for x in r[col]}
    return d


def linhas_de(fon, res, odds):
    L = []  # (concurso, p[3], feat[3,2], resultado)
    for k, jogos in fon.items():
        c = k if isinstance(k, int) else k[0]
        if c not in res:
            continue
        for j, V in jogos.items():
            if j not in odds.get(c, {}) or len(V) == 3:
                continue
            f = np.zeros((3, 2))
            for x in V:
                f[x, 0 if len(V) == 1 else 1] = 1
            L.append((c, np.asarray(c2.prob_mercado(odds[c][j]), float), f, res[c][j - 1]))
    return L


def ajustar(L, lam=1.0):
    b = np.zeros(2)
    if not L:
        return b
    P = np.array([l[1] for l in L]); F = np.array([l[2] for l in L]); y = np.array([l[3] for l in L])
    for _ in range(25):
        z = np.log(P) + F @ b
        q = np.exp(z - z.max(1, keepdims=True)); q /= q.sum(1, keepdims=True)
        Fy = F[np.arange(len(y)), y]; Eq = (q[..., None] * F).sum(1)
        g = (Fy - Eq).sum(0) - lam * b
        Hm = np.einsum("ik,ika,ikb->ab", q, F, F) - Eq.T @ Eq
        b += np.linalg.solve(Hm + lam * np.eye(2), g)
    return b


def testar(nome, L, minimo=30):
    cs = sorted({l[0] for l in L})
    ganhos, por_conc = [], []
    for i, c in enumerate(cs):
        treino = [l for l in L if l[0] < c]
        if len({l[0] for l in treino}) < minimo:
            continue
        b = ajustar(treino)
        g = 0.0
        for l in (l for l in L if l[0] == c):
            z = np.log(l[1]) + l[2] @ b; q = np.exp(z - z.max()); q /= q.sum()
            g += math.log(q[l[3]]) - math.log(l[1][l[3]])
        por_conc.append(g)
    bt = ajustar(L)
    seco = [l for l in L if l[2][:, 0].any()]
    acerto_seco = np.mean([l[2][l[3], 0] for l in seco]) if seco else float("nan")
    fav_seco = np.mean([l[1][l[2][:, 0].argmax()] for l in seco]) if seco else float("nan")
    contra = [l for l in seco if l[2][:, 0].argmax() != l[1].argmax()]
    print(f"\n## {nome}")
    print(f"- jogos com odd: {len(L)} em {len(cs)} concursos")
    print(f"- secos do site: acertam {100*acerto_seco:.1f}%; a odd dava a esses mesmos resultados {100*fav_seco:.1f}% em media")
    if contra:
        print(f"- secos CONTRA o favorito do mercado: {len(contra)} jogos, acertam {100*np.mean([l[2][l[3],0] for l in contra]):.1f}%"
              f" (a odd dava {100*np.mean([l[1][l[2][:,0].argmax()] for l in contra]):.1f}%)")
    print(f"- peso ajustado em toda a base: seco {bt[0]:+.3f}, duplo {bt[1]:+.3f} (0 = nao acrescenta nada a odd)")
    if por_conc:
        g = np.array(por_conc); se = g.std() / math.sqrt(len(g))
        print(f"- teste no tempo ({len(g)} concursos): ganho medio {g.mean():+.4f} log-loss por concurso, forca {g.mean()/se:+.1f}"
              f" -> {'SINAL REAL' if g.mean()/se > 2 else 'nao passa no criterio (precisa > 2)'}")
    return bt


def main():
    res = resultados(); odds = c2.odds_por_concurso()
    print("# O palpite dos sites acrescenta informacao a odd?")
    testar("Arena do AZ (palpite com secos/duplos/triplos)", linhas_de(fonte("arena_palpites.csv", "marcas"), res, odds))
    testar("Vovoteca - matriz (secos)", linhas_de(fonte("vovo_matriz.csv", "seco"), res, odds))
    testar("Vovoteca - boloes", linhas_de(fonte("vovo_boloes.csv", "marcas", lambda r: (int(r["concurso"]), r["bolao"])), res, odds), minimo=8)


if __name__ == "__main__":
    main()
