"""
Escada da cartela: parte da aposta minima (13 secos + 1 duplo = R$4) e vai
acrescentando, um a um, o duplo ou triplo que compra mais chance de 14 por
real gasto. Mede, em cada degrau, a chance esperada (pelas probabilidades da
camada 1) e quantas vezes a cartela teria feito 14 e 13 de verdade.
Uso: python motor/escada.py
"""
import csv, math, os, sys
from collections import defaultdict
import numpy as np
AQUI = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
from calibracao import aplica, aprende

def escada(probs, custo_max=8192):
    """Lista de degraus (custo_R$, cartela) a partir de 13 secos + 1 duplo."""
    ordens = [list(np.argsort(-p)) for p in probs]
    cob = lambda i, k: sum(probs[i][o] for o in ordens[i][:k + 1])
    nivel = [0] * 14
    g = max(range(14), key=lambda i: cob(i, 1) / cob(i, 0))   # 1o duplo: maior ganho
    nivel[g] = 1
    degraus = [(4, list(nivel))]
    while True:
        melhor, ganho_m = None, 0
        for i in range(14):
            if nivel[i] < 2:
                ganho = math.log(cob(i, nivel[i] + 1) / cob(i, nivel[i])) / math.log((nivel[i] + 2) / (nivel[i] + 1))
                if ganho > ganho_m: melhor, ganho_m = i, ganho
        if melhor is None: break
        nivel[melhor] += 1
        custo = 2 * math.prod([1, 2, 3][n] for n in nivel)
        if custo > custo_max: break
        degraus.append((custo, list(nivel)))
    return degraus, ordens

def main():
    rows = [r for r in csv.DictReader(open(os.path.join(REPO, "coleta/dados/arena_odds.csv"), encoding="utf-8")) if r["resultado"]]
    prm = aprende([([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])], "1X2".index(r["resultado"])) for r in rows], usar_empate=False)
    jog = defaultdict(dict)
    for r in rows: jog[int(r["concurso"])][int(r["jogo"])] = r
    concs = sorted(c for c, g in jog.items() if len(g) == 14)
    alvos = [4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192]
    acum = {a: [0.0, 0, 0, None] for a in alvos}
    for c in concs:
        g = [jog[c][k] for k in range(1, 15)]
        probs = [aplica([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])], prm) for r in g]
        res = ["1X2".index(r["resultado"]) for r in g]
        degs, ordens = escada(probs)
        for a in alvos:
            custo, niv = max((d for d in degs if d[0] <= a), key=lambda d: d[0])
            cob = [set(ordens[i][:niv[i] + 1]) for i in range(14)]
            p14 = math.prod(sum(probs[i][o] for o in cob[i]) for i in range(14))
            erros = sum(res[i] not in cob[i] for i in range(14))
            x = acum[a]; x[0] += p14; x[1] += erros == 0; x[2] += erros == 1
            x[3] = (sum(n == 0 for n in niv), sum(n == 1 for n in niv), sum(n == 2 for n in niv))
    n = len(concs)
    print(f"{n} concursos com odds dos 14 jogos (895-1283). Probabilidades da camada 1.\n")
    print(f"{'Orcamento':>10} {'Estrutura tipica':>17} {'Chance de 14':>13} {'1 em cada':>10} {'Fez 14':>7} {'Fez 13 (errou 1)':>17}")
    for a in alvos:
        x = acum[a]; p = x[0] / n
        print(f"{'R$ ' + format(a, ','):>10} {f'{x[3][0]}+{x[3][1]}+{x[3][2]}':>17} {p:>12.3%} {1/p:>10,.0f} {x[1]:>7} {x[2]:>17}")

if __name__ == "__main__":
    main()
