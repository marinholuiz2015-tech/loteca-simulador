"""
Desdobre pelo RETORNO ESPERADO de cada combinacao (nao so pela chance).
Ganhadores previstos de uma combinacao: log10(g14+1) ~ a + b*soma(log10 p) + c*log10(arrecadacao),
ajustado nos concursos ANTERIORES (walk-forward). Retorno esperado da combinacao
= P(combinacao) x premio14 / (ganhadores previstos + 1).
Premio14 usado na decisao: media historica da razao premio14/arrecadacao (dos concursos anteriores)
x arrecadacao do concurso (aproximacao do que se sabe antes do sorteio).
"""
import itertools, math, os, sys, csv
from collections import defaultdict
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_premios import power, rateio, REPO, PRECO
from backtest_desdobre import matriz, avalia, top_k

rat = rateio()
jogos = defaultdict(dict)
for r in csv.DictReader(open(os.path.join(REPO, "coleta", "dados", "arena_odds.csv"), encoding="utf-8")):
    if r["resultado"]: jogos[int(r["concurso"])][int(r["jogo"])] = r
conc = sorted(c for c, g in jogos.items() if len(g) == 14 and c in rat and rat[c]["arrec"])
P = {c: [power([float(jogos[c][k]["odd_1"]), float(jogos[c][k]["odd_x"]), float(jogos[c][k]["odd_2"])]) for k in range(1, 15)] for c in conc}
RES = {c: tuple("1X2".index(jogos[c][k]["resultado"]) for k in range(1, 15)) for c in conc}
def lp_res(c): return sum(math.log10(P[c][i][RES[c][i]]) for i in range(14))
INICIO = 40  # primeiros 40 concursos so para treinar o modelo de ganhadores
Ks = {648: (7, 3, 4), 1296: (6, 4, 4), 1944: (6, 3, 5), 2916: (6, 2, 6), 3888: (5, 4, 5)}
acum = defaultdict(lambda: [0.0, 0, 0, 0, 0.0])
for idx in range(INICIO, len(conc)):
    c = conc[idx]; ant = conc[:idx]
    X = np.array([[1, lp_res(a), math.log10(rat[a]["arrec"])] for a in ant]); y = np.log10([rat[a]["g14"] + 1 for a in ant])
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    razao = np.mean([rat[a]["pool14"] / rat[a]["arrec"] for a in ant])
    pool_est = razao * rat[c]["arrec"]
    R = rat[c]; res = RES[c]; probs = P[c]
    mat = matriz(probs, 5, 6)
    todas = []
    for comb in itertools.product(*mat):
        pr = math.prod(p for _, p in comb); lp = sum(math.log10(p) for _, p in comb)
        W = max(10 ** (coef[0] + coef[1] * lp + coef[2] * math.log10(R["arrec"])) - 1, 0)
        todas.append((pr, pr * pool_est / (W + 1), tuple(i for i, _ in comb)))
    por_prob = sorted(todas, key=lambda x: -x[0]); por_ev = sorted(todas, key=lambda x: -x[1])
    for K, (s, d, t) in Ks.items():
        # cartela cheia
        mc = matriz(probs, d, t); cheia = [(1.0, tuple(i for i, _ in x)) for x in itertools.product(*mc)]
        for nome, sel in (("cheia", cheia), ("desdobre por chance", [(a, b) for a, _, b in por_prob[:K]]),
                          ("desdobre por retorno", [(a, b) for a, _, b in por_ev[:K]])):
            n14, n13, pr = avalia(sel, res, R)
            a = acum[(nome, K)]
            a[0] += (math.prod(sum(p for _, p in m) for m in mc) if nome == "cheia" else sum(x[0] for x in sel))
            a[1] += n14 > 0; a[2] += (n14 == 0 and n13 > 0); a[3] += n13; a[4] += pr
n = len(conc) - INICIO
print(f"{n} concursos testados (os {INICIO} primeiros so treinam o modelo de ganhadores). Matriz-base do desdobre: 3+5+6.\n")
print(f"{'Comb.':>6} {'Cartela':<24}{'Chance 14':>10}{'Fez 14':>8}{'Fez 13':>8}{'Comb.13':>9}{'Premios':>13}{'Retorno':>9}")
for K, (s, d, t) in Ks.items():
    for nome in ("cheia", "desdobre por chance", "desdobre por retorno"):
        a = acum[(nome, K)]; g = K * PRECO * n
        rot = f"cheia {s}+{d}+{t}" if nome == "cheia" else nome
        print(f"{K:>6} {rot:<24}{a[0] / n:>10.2%}{a[1]:>8}{a[2]:>8}{a[3]:>9}{a[4]:>13,.0f}{a[4] / g:>8.0%}")
    print()
