"""
Desdobre assertivo x cartela cheia, com o MESMO numero de combinacoes (custo).

Cartela cheia: todas as combinacoes de uma estrutura secos+duplos+triplos.
Desdobre: monta uma matriz maior (mais duplos/triplos) e guarda so as K
combinacoes mais provaveis (probabilidade da combinacao = produto das
probabilidades dos 14 resultados). E a forma matematica das "gavetas"
(cortar combinacoes com zebras demais), mas pesada pela probabilidade.

Mede em 238 concursos (so odds, sem ver o resultado): chance media de 14,
quantas vezes fez 14 e 13, combinacoes de 13 e premios pelo rateio oficial.
"""
import itertools
import math
import os
import sys
from collections import defaultdict
import csv

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_premios import cartela, opcoes, power, rateio, REPO, PRECO  # noqa: E402


def opcoes_jogo(p, k):
    """Resultados marcados no jogo (k=0 seco, 1 duplo, 2 triplo), com probabilidades."""
    o = list(np.argsort(-p))[:k + 1]
    return [(int(i), float(p[i])) for i in o]


def matriz(probs, d, t):
    esc = cartela(probs, d, t)
    return [opcoes_jogo(p, k) for p, k in zip(probs, esc)]


def top_k(mat, K):
    """K combinacoes mais provaveis da matriz (enumeracao com poda por produto)."""
    # enumera todas (matrizes de ate ~12 mil combinacoes)
    combos = []
    for c in itertools.product(*mat):
        pr = 1.0
        for _, p in c:
            pr *= p
        combos.append((pr, tuple(i for i, _ in c)))
    combos.sort(key=lambda x: -x[0])
    return combos[:K]


def avalia(combos, res, R):
    """Acertos e premio de um conjunto de combinacoes num concurso."""
    n14 = 0
    n13 = 0
    for _, c in combos:
        ac = sum(a == b for a, b in zip(c, res))
        if ac == 14:
            n14 += 1
        elif ac == 13:
            n13 += 1
    premio = 0.0
    if n14:
        premio += R["pool14"] / (R["g14"] + 1)
    if n13:
        premio += n13 * R["pool13"] / (R["g13"] + n13)
    return n14, n13, premio


def main():
    rat = rateio()
    jogos = defaultdict(dict)
    with open(os.path.join(REPO, "coleta", "dados", "arena_odds.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["resultado"]:
                jogos[int(r["concurso"])][int(r["jogo"])] = r
    concursos = sorted(c for c, g in jogos.items() if len(g) == 14 and c in rat)
    cheias = {648: (7, 3, 4), 1296: (6, 4, 4), 1944: (6, 3, 5), 2916: (6, 2, 6), 3888: (5, 4, 5)}
    matrizes = {"matriz 4+4+6": (4, 6), "matriz 3+5+6": (5, 6)}
    acum = defaultdict(lambda: [0.0, 0, 0, 0, 0.0])  # soma P14, fez14, conc com 13, comb13, premio
    for c in concursos:
        g = [jogos[c][k] for k in range(1, 15)]
        probs = [power([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])]) for r in g]
        res = tuple("1X2".index(r["resultado"]) for r in g)
        R = rat[c]
        for K, (s, d, t) in cheias.items():
            mat = matriz(probs, d, t)
            combos = [(1.0, tuple(i for i, _ in x)) for x in itertools.product(*mat)]
            p14 = math.prod(sum(p for _, p in m) for m in mat)
            n14, n13, pr = avalia(combos, res, R)
            a = acum[("cheia", K)]
            a[0] += p14; a[1] += n14 > 0; a[2] += (n14 == 0 and n13 > 0); a[3] += n13; a[4] += pr
            for nome, (d2, t2) in matrizes.items():
                mat2 = matriz(probs, d2, t2)
                sel = top_k(mat2, K)
                p14s = sum(p for p, _ in sel)
                n14, n13, pr = avalia(sel, res, R)
                a = acum[(nome, K)]
                a[0] += p14s; a[1] += n14 > 0; a[2] += (n14 == 0 and n13 > 0); a[3] += n13; a[4] += pr
    n = len(concursos)
    print(f"{n} concursos (895-1281). Mesmo custo em cada linha do bloco.\n")
    print(f"{'Combinacoes':>11} {'Cartela':<24}{'Chance 14':>10}{'Fez 14':>8}{'Fez 13':>8}{'Comb.13':>9}"
          f"{'Premios':>13}{'Retorno':>9}")
    for K, (s, d, t) in cheias.items():
        gasto = K * PRECO * n
        for nome in ("cheia",) + tuple(matrizes):
            a = acum[(nome, K)]
            rot = f"cheia {s}+{d}+{t}" if nome == "cheia" else f"desdobre ({nome})"
            print(f"{K:>11} {rot:<24}{a[0] / n:>10.2%}{a[1]:>8}{a[2]:>8}{a[3]:>9}"
                  f"{a[4]:>13,.0f}{a[4] / gasto:>8.0%}")
        print()


if __name__ == "__main__":
    main()
