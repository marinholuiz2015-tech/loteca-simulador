"""
Desdobre espalhado: volantes de 1 duplo (aposta minima da Caixa: 2 combinacoes, R$ 4) escolhidos para
cobrir o maximo de resultados a ate 1 erro (13 ou 14 pontos), dentro de uma base forte.

Por que espalhado: na cartela simples as combinacoes ficam grudadas (os vizinhos de uma ja estao na
cartela) e o "desdobre com garantia de 13" so garante se todos os secos baterem. Espalhando, cada volante
cobre resultados novos. 1284 com R$ 200: cartela simples 10+0+4 (R$ 162) 14 = 2,09% / 13+ = 12,2%;
espalhado R$ 160: 2,31% / 13,2%; R$ 200: 2,57% / 14,6%. As combinacoes espalhadas tem mais zebras: quando
acertam, dividem o premio com menos gente. Conta com as probabilidades do motor (calibradas: zebras por
concurso previstas 6,72 x reais 6,71).

Uso: python motor/desdobre.py [N] [orcamento]   -> motor/saida/concurso_N_desdobre_R<orc>.csv e .md
"""
import csv
import glob
import heapq
import itertools
import json
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "saida")


def duplo(p):
    f = int(np.argmax(p))
    return [f, 1] if f != 1 else [1, 0 if p[0] >= p[2] else 2]


def base_otima(P, d, t):
    """melhor cartela com d duplos e t triplos (duplo = favorito + empate)."""
    fav = [int(np.argmax(p)) for p in P]
    best = {(0, 0): (0.0, [])}
    for i, p in enumerate(P):
        nb = {}
        for (a, b), (v, ch) in best.items():
            for tp, s in ((1, [fav[i]]), (2, duplo(p)), (3, [0, 1, 2])):
                a2, b2 = a + (tp == 2), b + (tp == 3)
                if a2 > d or b2 > t:
                    continue
                vv = v + math.log(sum(p[k] for k in s))
                if (a2, b2) not in nb or vv > nb[(a2, b2)][0]:
                    nb[(a2, b2)] = (vv, ch + [s])
        best = nb
    return best[(d, t)][1]


def cartela_simples(P, orc):
    melhor = None
    for d in range(15):
        for t in range(15 - d):
            custo = 2 ** d * 3 ** t * 2
            if 4 <= custo <= orc:
                sel = base_otima(P, d, t)
                cov = [sum(P[i][k] for k in s) for i, s in enumerate(sel)]
                p14 = float(np.prod(cov))
                if not melhor or p14 > melhor["p14"]:
                    p13 = sum((1 - c) * p14 / c for c in cov if c < 1)
                    melhor = {"sel": sel, "custo": custo, "p14": p14, "p13": p14 + p13,
                              "estrutura": f"{14 - d - t}+{d}+{t}"}
    return melhor


def espalhado(P, orc, base=(4, 6), top=3000):
    LP = np.log(np.asarray(P))

    def pr(c):
        return math.exp(sum(LP[i][c[i]] for i in range(14)))

    def viz(c):
        out = [c]
        for i in range(14):
            for k in range(3):
                if k != c[i]:
                    out.append(c[:i] + (k,) + c[i + 1:])
        return out

    bs = base_otima(P, *base)
    cand = sorted((tuple(x) for x in itertools.product(*bs)), key=lambda c: -pr(c))[:top]
    unid = [(c, c[:i] + (k,) + c[i + 1:]) for c in cand for i in range(14) for k in bs[i] if k > c[i]]
    cache = {}

    def cober(n):
        if n not in cache:
            cache[n] = set(viz(unid[n][0])) | set(viz(unid[n][1]))
        return cache[n]

    cob, esc = set(), []
    h = [(-sum(pr(v) for v in cober(n)), n) for n in range(len(unid))]
    heapq.heapify(h)
    while len(esc) < orc // 4 and h:
        _, n = heapq.heappop(h)
        ng = sum(pr(v) for v in cober(n) if v not in cob)
        if h and -h[0][0] > ng + 1e-15:
            heapq.heappush(h, (-ng, n))
            continue
        esc.append(unid[n])
        cob |= cober(n)
    combos = {c for u in esc for c in u}
    return {"volantes": esc, "custo": 4 * len(esc), "p14": sum(pr(c) for c in combos),
            "p13": sum(pr(v) for v in cob), "base": f"{14 - sum(base)}+{base[0]}+{base[1]}"}


def gerar(c=None, orc=200):
    if c is None:
        feitos = sorted(int(os.path.basename(a)[9:-4]) for a in glob.glob(os.path.join(SAIDA, "concurso_*.csv"))
                        if os.path.basename(a)[9:-4].isdigit())
        c = feitos[-1]
    linhas = list(csv.DictReader(open(os.path.join(SAIDA, f"concurso_{c}.csv"), encoding="utf-8")))
    linhas.sort(key=lambda r: int(r["jogo"]))
    P = [[float(r["p1"]), float(r["px"]), float(r["p2"])] for r in linhas]
    s = cartela_simples(P, orc)
    e = espalhado(P, orc)
    arq = os.path.join(SAIDA, f"concurso_{c}_desdobre_R{orc}.csv")
    with open(arq, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["volante"] + [f"jogo_{j}" for j in range(1, 15)] + ["valor"])
        for n, (a, b) in enumerate(e["volantes"], 1):
            w.writerow([n] + ["".join(sorted({"1X2"[a[j]], "1X2"[b[j]]}, key="1X2".index)) for j in range(14)] + [4])
    md = [f"# Concurso {c} — desdobre espalhado para R$ {orc}", "",
          "| Jogo | Custo | Chance de 14 | Chance de 13 ou 14 | Volantes |", "|---|---|---|---|---|",
          f"| Cartela simples (jogo perfeito {s['estrutura']}) | R$ {s['custo']} | {s['p14']:.2%} | {s['p13']:.1%} | divide em volantes |",
          f"| **Desdobre espalhado** (base {e['base']}) | R$ {e['custo']} | **{e['p14']:.2%}** | **{e['p13']:.1%}** | {len(e['volantes'])} de R$ 4 (1 duplo cada) |",
          "", "Cada volante tem um duplo; os volantes estão em "
          f"`concurso_{c}_desdobre_R{orc}.csv`. A garantia de 13 de um desdobre comum só vale se todos os secos "
          "baterem; o espalhado troca essa garantia por mais chance total de 13 e 14."]
    open(os.path.join(SAIDA, f"concurso_{c}_desdobre_R{orc}.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump({"concurso": c, "orcamento": orc,
               "simples": {"estrutura": s["estrutura"], "custo": s["custo"], "p14": s["p14"], "p13": s["p13"],
                           "cartela": ["".join("1X2"[k] for k in sorted(x)) for x in s["sel"]]},
               "espalhado": {"base": e["base"], "custo": e["custo"], "p14": e["p14"], "p13": e["p13"],
                             "volantes": [["".join(sorted({"1X2"[a[j]], "1X2"[b[j]]}, key="1X2".index)) for j in range(14)]
                                          for a, b in e["volantes"]]}},
              open(os.path.join(SAIDA, f"concurso_{c}_desdobre_R{orc}.json"), "w"), ensure_ascii=False)
    print("\n".join(md))
    return s, e


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a.isdigit()]
    gerar(int(args[0]) if args else None, int(args[1]) if len(args) > 1 else 200)
