"""
"Se tivessemos apostado": em cada concurso com odds dos 14 jogos, monta a
cartela que o motor faria SO com as odds (sem ver o resultado), confere com
o resultado oficial e calcula o premio com o rateio real da Caixa.

- Probabilidades: odds bet365 (Arena), margem tirada pelo metodo de potencia.
- Cartela: para cada estrutura (secos+duplos+triplos), a alocacao que
  maximiza a chance de 14 (programacao dinamica).
- Premio de 14: (premio total da faixa) / (ganhadores oficiais + 1).
  Se ninguem fez 14, o premio total e o valor que acumulou.
- Premio de 13: cada combinacao com 13 acertos recebe
  (premio total da faixa 13) / (ganhadores oficiais + nossas combinacoes de 13).
- Custo: R$2 por combinacao (2^duplos x 3^triplos).
"""
import csv
import json
import math
import os
from collections import defaultdict

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
PRECO = 2.0


def power(o):
    inv = np.array([1 / x for x in o])
    lo, hi = 0.5, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if (inv ** k).sum() > 1:
            lo = k
        else:
            hi = k
    p = inv ** k
    return p / p.sum()


def rateio():
    out = {}
    with open("/home/claude/lotequeiros/resultados_caixa_bruto.jsonl", encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            fx = {r["faixa"]: r for r in d.get("listaRateioPremio") or []}
            if 1 not in fx or 2 not in fx:
                continue
            g14, v14 = fx[1]["numeroDeGanhadores"], fx[1]["valorPremio"]
            g13, v13 = fx[2]["numeroDeGanhadores"], fx[2]["valorPremio"]
            pool14 = g14 * v14 if g14 else (d.get("valorAcumuladoProximoConcurso") or 0)
            pool13 = g13 * v13
            out[d["numero"]] = dict(g14=g14, g13=g13, pool14=pool14, pool13=pool13,
                                    arrec=d.get("valorArrecadado") or 0)
    return out


def opcoes(p):
    o = list(np.argsort(-p))
    return [(p[o[0]], {o[0]}), (p[o[0]] + p[o[1]], {o[0], o[1]}), (1.0, {0, 1, 2})]


def cartela(probs, d, t):
    dp = {(0, 0): (0.0, [])}
    for p in probs:
        op = opcoes(p)
        nd = {}
        for (a, b), (v, esc) in dp.items():
            for k, (pc, _) in enumerate(op):
                na, nb = a + (k == 1), b + (k == 2)
                if na > d or nb > t:
                    continue
                nv = v + math.log(max(pc, 1e-9))
                if (na, nb) not in nd or nd[(na, nb)][0] < nv:
                    nd[(na, nb)] = (nv, esc + [k])
        dp = nd
    return dp[(d, t)][1]


def main():
    rat = rateio()
    jogos = defaultdict(dict)
    with open(os.path.join(REPO, "coleta", "dados", "arena_odds.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["resultado"]:
                jogos[int(r["concurso"])][int(r["jogo"])] = r
    concursos = sorted(c for c, g in jogos.items() if len(g) == 14 and c in rat)
    print(f"Concursos simulados: {len(concursos)} ({concursos[0]}-{concursos[-1]}), "
          f"so os que tem odds dos 14 jogos e rateio oficial\n")
    estruturas = [(7, 3, 4), (6, 4, 4), (6, 3, 5), (7, 0, 7), (6, 2, 6), (5, 4, 5), (5, 3, 6)]
    print(f"{'Estrutura':<10}{'Custo/conc.':>12}{'Fez 14':>8}{'Fez 13*':>9}{'Comb. de 13':>12}"
          f"{'Gasto total':>15}{'Premios':>15}{'Retorno':>9}")
    detalhes = {}
    for s, d, t in estruturas:
        custo = (2 ** d) * (3 ** t) * PRECO
        n14 = n13 = comb13 = 0
        premio = 0.0
        lista14 = []
        for c in concursos:
            g = [jogos[c][k] for k in range(1, 15)]
            probs = [power([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])]) for r in g]
            esc = cartela(probs, d, t)
            res = ["1X2".index(r["resultado"]) for r in g]
            cobre = [res[i] in opcoes(probs[i])[esc[i]][1] for i in range(14)]
            tam = [1, 2, 3]
            erros = cobre.count(False)
            R = rat[c]
            if erros == 0:
                n14 += 1
                # 13 acertos: trocar 1 jogo coberto por outra opcao marcada nele
                c13 = sum(tam[e] - 1 for e in esc)
                premio += R["pool14"] / (R["g14"] + 1)
                lista14.append((c, R["pool14"] / (R["g14"] + 1), R["g14"]))
            elif erros == 1:
                n13 += 1
                i = cobre.index(False)
                c13 = tam[esc[i]]  # cada opcao marcada no jogo errado da 13
            else:
                c13 = 0
            if c13:
                comb13 += c13
                premio += c13 * R["pool13"] / (R["g13"] + c13) if (R["g13"] + c13) else 0
        gasto = custo * len(concursos)
        print(f"{s}+{d}+{t:<6}{custo:>12,.0f}{n14:>8}{n13:>9}{comb13:>12}"
              f"{gasto:>15,.0f}{premio:>15,.0f}{premio / gasto:>8.0%}")
        detalhes[(s, d, t)] = lista14
    print("\n* 'Fez 13' = concursos em que a cartela errou so 1 jogo (melhor premio foi 13).")
    print("  Concursos com 14 tambem pagam varias combinacoes de 13 (incluidas em 'Comb. de 13').")
    print("Retorno = premios / gasto (100% = empata; abaixo de 100% = prejuizo).")
    for est in ((6, 4, 4), (6, 3, 5)):
        l = detalhes[est]
        print(f"\nOs 14 do {est[0]}+{est[1]}+{est[2]}: " +
              "; ".join(f"conc {c}: R$ {v:,.0f} ({g} ganhadores oficiais)" for c, v, g in l))


if __name__ == "__main__":
    main()
