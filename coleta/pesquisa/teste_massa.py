"""
Testes que dependem da base ampliada da massa (enquetes finais + parciais).

1) Ganhadores de 14 e 13: odds sozinhas x odds + massa (validacao cruzada
   deixando um concurso de fora, para nao medir no mesmo dado do ajuste).
2) Desdobre (mesmo custo): corte por chance x corte por retorno esperado, em
   que os ganhadores previstos de cada combinacao usam a massa. Walk-forward:
   o modelo de ganhadores e ajustado so com concursos anteriores.
Jogos sem massa no concurso recebem a massa estimada a partir das odds
(relacao aprendida nos jogos que tem as duas).
"""
import csv
import itertools
import math
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_premios import power, rateio, REPO, PRECO, cartela  # noqa: E402
from backtest_desdobre import matriz, avalia  # noqa: E402

DADOS = os.path.join(REPO, "coleta", "dados")
lg = lambda p: math.log(min(max(p, 1e-3), 0.999) / (1 - min(max(p, 1e-3), 0.999)))


def carregar():
    rat = rateio()
    odds = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(DADOS, "arena_odds.csv"), encoding="utf-8")):
        if r["resultado"]:
            odds[int(r["concurso"])][int(r["jogo"])] = r
    massa = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(DADOS, "vovoteca_massa.csv"), encoding="utf-8")):
        massa[int(r["concurso"])][int(r["jogo"])] = [float(r["massa_1"]) / 100, float(r["massa_x"]) / 100,
                                                    float(r["massa_2"]) / 100]
    return rat, odds, massa


def mapa_mercado_massa(odds, massa):
    X, Y = [], []
    for c, g in massa.items():
        for j, m in g.items():
            if j not in odds.get(c, {}):
                continue
            o = odds[c][j]
            p = power([float(o["odd_1"]), float(o["odd_x"]), float(o["odd_2"])])
            for k in range(3):
                X.append([1, lg(p[k]), k == 0, k == 1]); Y.append(lg(m[k] / sum(m)))
    coef = np.linalg.lstsq(np.array(X, float), np.array(Y), rcond=None)[0]

    def estima(p):
        v = [1 / (1 + math.exp(-(coef[0] + coef[1] * lg(p[k]) + coef[2] * (k == 0) + coef[3] * (k == 1))))
             for k in range(3)]
        s = sum(v)
        return [x / s for x in v]
    return estima


def main():
    rat, odds, massa = carregar()
    estima = mapa_mercado_massa(odds, massa)
    concs = sorted(c for c in massa if len(odds.get(c, {})) == 14 and c in rat and rat[c]["arrec"]
                   and len(massa[c]) >= 10)
    linhas = []
    for c in concs:
        P = [power([float(odds[c][j]["odd_1"]), float(odds[c][j]["odd_x"]), float(odds[c][j]["odd_2"])])
             for j in range(1, 15)]
        M = [massa[c][j] if j in massa[c] else estima(P[j - 1]) for j in range(1, 15)]
        M = [[x / sum(m) for x in m] for m in M]
        res = ["1X2".index(odds[c][j]["resultado"]) for j in range(1, 15)]
        lo = sum(math.log10(P[i][res[i]]) for i in range(14))
        lm = sum(math.log10(max(M[i][res[i]], 0.005)) for i in range(14))
        linhas.append(dict(c=c, P=P, M=M, res=res, lo=lo, lm=lm, arr=math.log10(rat[c]["arrec"]),
                           y14=math.log10(rat[c]["g14"] + 1), y13=math.log10(rat[c]["g13"] + 1)))
    n = len(linhas)
    print(f"== 1) Ganhadores: {n} concursos com odds completas e massa (>=10 jogos) ==")
    for alvo in ("y14", "y13"):
        erros = {"odds": [], "odds+massa": [], "massa": []}
        for i in range(n):
            tr = [l for k, l in enumerate(linhas) if k != i]
            te = linhas[i]
            for nome, cols in (("odds", ("lo",)), ("odds+massa", ("lo", "lm")), ("massa", ("lm",))):
                X = np.array([[1, l["arr"]] + [l[k] for k in cols] for l in tr])
                y = np.array([l[alvo] for l in tr])
                b = np.linalg.lstsq(X, y, rcond=None)[0]
                pred = b @ np.array([1, te["arr"]] + [te[k] for k in cols])
                erros[nome].append((pred - te[alvo]) ** 2)
        print(f"  ganhadores de {alvo[1:]}: erro (log10) odds {math.sqrt(np.mean(erros['odds'])):.3f} | "
              f"massa {math.sqrt(np.mean(erros['massa'])):.3f} | odds+massa {math.sqrt(np.mean(erros['odds+massa'])):.3f}")

    print("\n== 2) Desdobre com o mesmo custo: chance x retorno (massa) x cheia ==")
    Ks = {1296: (6, 4, 4), 1944: (6, 3, 5), 3888: (5, 4, 5)}
    acum = defaultdict(lambda: [0.0, 0, 0, 0, 0.0])
    INICIO = 25
    testados = 0
    for idx in range(INICIO, n):
        L = linhas[idx]; ant = linhas[:idx]; c = L["c"]; R = rat[c]
        X = np.array([[1, l["arr"], l["lm"]] for l in ant]); y = np.array([l["y14"] for l in ant])
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        razao = np.mean([rat[l["c"]]["pool14"] / rat[l["c"]]["arrec"] for l in ant])
        pool = razao * R["arrec"]
        mat = matriz(L["P"], 5, 6)
        todas = []
        for comb in itertools.product(*mat):
            idxs = tuple(i for i, _ in comb)
            pr = math.prod(p for _, p in comb)
            lm = sum(math.log10(max(L["M"][g][idxs[g]], 0.005)) for g in range(14))
            W = max(10 ** (b[0] + b[1] * L["arr"] + b[2] * lm) - 1, 0)
            todas.append((pr, pr * pool / (W + 1), idxs))
        por_p = sorted(todas, key=lambda x: -x[0]); por_ev = sorted(todas, key=lambda x: -x[1])
        res = tuple(L["res"])
        for K, (s, d, t) in Ks.items():
            mc = matriz(L["P"], d, t)
            cheia = [(1.0, tuple(i for i, _ in x)) for x in itertools.product(*mc)]
            for nome, sel in (("cheia", cheia), ("desdobre por chance", [(a, z) for a, _, z in por_p[:K]]),
                              ("desdobre por retorno", [(a, z) for a, _, z in por_ev[:K]])):
                n14, n13, pr = avalia(sel, res, R)
                a = acum[(nome, K)]
                a[0] += (math.prod(sum(p for _, p in m) for m in mc) if nome == "cheia" else sum(x[0] for x in sel))
                a[1] += n14 > 0; a[2] += (n14 == 0 and n13 > 0); a[3] += n13; a[4] += pr
        testados += 1
    print(f"  {testados} concursos testados (os {INICIO} primeiros so treinam o modelo de ganhadores)")
    print(f"  {'Comb.':>6} {'Cartela':<22}{'Chance 14':>10}{'Fez 14':>8}{'Fez 13':>8}{'Comb.13':>9}{'Premios':>13}{'Retorno':>9}")
    for K, (s, d, t) in Ks.items():
        for nome in ("cheia", "desdobre por chance", "desdobre por retorno"):
            a = acum[(nome, K)]; g = K * PRECO * testados
            rot = f"cheia {s}+{d}+{t}" if nome == "cheia" else nome
            print(f"  {K:>6} {rot:<22}{a[0] / testados:>10.2%}{a[1]:>8}{a[2]:>8}{a[3]:>9}{a[4]:>13,.0f}{a[4] / g:>8.0%}")
        print()


if __name__ == "__main__":
    main()
