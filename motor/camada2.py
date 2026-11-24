"""
Camada 2 — rateio: escolher as combinacoes por VALOR (chance x premio esperado).

Na Loteca o premio de 14 e dividido entre os ganhadores. Uma combinacao muito
jogada pela massa paga pouco quando sai; uma combinacao provavel mas pouco
jogada paga muito. A camada 2:

1. Estima quanto a massa joga cada resultado: enquete da Vovoteca (parcial de
   quinta) quando existe; senao, um modelo da massa a partir das odds (a massa
   exagera no favorito: q = odds^k com vies por resultado, aprendido no historico).
2. Preve quantos ganhadores cada combinacao teria:
      log(ganhadores + 0,5) = a + log(apostas) + b * log(chance pela massa) + c * log(chance pelo mercado)
   ajustado com o rateio oficial (coleta/dados/rateio_caixa.csv).
3. Valor de cada combinacao = chance real x premio em jogo / (ganhadores previstos + 1).
4. Monta o jogo do orcamento com as combinacoes de maior valor e transforma em
   volantes validos (pares que diferem em 1 jogo viram duplo; as demais ganham o
   duplo gratis da aposta minima de R$ 4).

Uso:
  python motor/camada2.py testar          # teste nos concursos com enquete + rateio
  python motor/camada2.py [concurso]      # jogo por valor do concurso aberto -> motor/saida/
"""
import csv
import itertools
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
DADOS = os.path.join(REPO, "coleta", "dados")
SAIDA = os.path.join(AQUI, "saida")
sys.path.insert(0, AQUI)
from calibracao import ajusta_gama, sem_margem  # noqa: E402

ORCAMENTOS = (1296, 2592, 3888)   # R$ (iguais as cartelas 7+3+4, 6+4+4 e 6+3+5)
PRECO = 2


def ler(arq):
    if not os.path.exists(arq):
        return []
    with open(arq, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ dados
def odds_por_concurso():
    out = defaultdict(dict)
    for r in ler(os.path.join(DADOS, "arena_odds.csv")):
        out[int(r["concurso"])][int(r["jogo"])] = r
    return out


def massa_por_concurso():
    out = defaultdict(dict)
    versao = {}
    for nome in ("vovoteca_massa.csv", "vovoteca_massa_aberto.csv"):
        for r in ler(os.path.join(DADOS, nome)):
            if r.get("soma_ok") != "1":
                continue
            c, j = int(r["concurso"]), int(r["jogo"])
            if j in out[c] and versao.get((c, j)) == "parcial":
                continue  # a parcial (antes do fechamento) e a que existe na hora de decidir
            q = np.array([float(r["massa_1"]), float(r["massa_x"]), float(r["massa_2"])])
            if q.sum() > 0:
                out[c][j] = q / q.sum()
                versao[(c, j)] = r.get("versao", "")
    return out


def rateio():
    return {int(r["concurso"]): {k: float(v) for k, v in r.items() if k not in ("concurso", "data")}
            for r in ler(os.path.join(DADOS, "rateio_caixa.csv"))}


def prob_mercado(r):
    return ajusta_gama(sem_margem([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])]), 1.04)


# ------------------------------------------------------------------ modelo da massa (quando nao ha enquete)
def ajusta_massa(pares):
    """pares: [(p_mercado, q_massa)]. Aprende k e vies por resultado: q ~ p^k * exp(vies)."""
    melhor = None
    for k in np.arange(0.8, 2.01, 0.05):
        for b1 in np.arange(-0.3, 0.31, 0.05):
            for b2 in np.arange(-0.5, 0.11, 0.05):
                v = 0.0
                for p, q in pares:
                    z = k * np.log(p) + np.array([b1, 0.0, b2])
                    z = np.exp(z - z.max())
                    z /= z.sum()
                    v += float((q * np.log(z)).sum())
                if melhor is None or v > melhor[0]:
                    melhor = (v, (float(k), float(b1), float(b2)))
    return melhor[1]


def massa_estimada(p, prm):
    k, b1, b2 = prm
    z = k * np.log(p) + np.array([b1, 0.0, b2])
    z = np.exp(z - z.max())
    return z / z.sum()


# ------------------------------------------------------------------ modelo de ganhadores
def dados_ganhadores(odds, massa, rat):
    X, Y, cs = [], [], []
    for c in sorted(rat):
        if len(odds.get(c, {})) != 14 or len(massa.get(c, {})) != 14 or rat[c]["arrecadacao"] <= 0:
            continue
        res = [odds[c][j]["resultado"] for j in range(1, 15)]
        if any(x not in ("1", "X", "2") for x in res):
            continue
        ant = rat.get(c - 1) or {}
        pool = max(ant.get("estimado_proximo") or 0, ant.get("acumulado_proximo") or 0)
        if pool <= 0:
            continue
        lpool = math.log(pool)
        idx = ["1X2".index(x) for x in res]
        lq = sum(math.log(max(massa[c][j][i], 1e-3)) for j, i in zip(range(1, 15), idx))
        lp = sum(math.log(prob_mercado(odds[c][j])[i]) for j, i in zip(range(1, 15), idx))
        X.append([1.0, lq, lp, lq * lq, lpool, lpool * lq])
        Y.append(math.log(rat[c]["ganhadores_14"] + 0.5) - math.log(rat[c]["arrecadacao"] / PRECO))
        cs.append(c)
    return np.array(X), np.array(Y), cs


def ajusta_ganhadores(X, Y):
    return np.linalg.lstsq(X, Y, rcond=None)[0]


def log_ganhadores(coef, lq, lp, lpool=None):
    """log(ganhadores por aposta) do resultado. O termo lq^2 capta a concentracao nos resultados
    populares (todos os favoritos): sem ele o modelo previa 13 ganhadores no 992 (foram 1.339).
    Os termos do premio (log do premio estimado e premio x massa, 23/11/2026) captam que premio alto
    muda quem aposta e como: erro do modelo caiu de 1,01 para 0,93 (log) no teste no tempo e sumiu o
    vies nas semanas de premio >= R$ 2 mi."""
    z = coef[0] + coef[1] * lq + coef[2] * lp
    if len(coef) > 3:
        z = z + coef[3] * lq * lq
    if len(coef) > 5 and lpool is not None:
        z = z + coef[4] * lpool + coef[5] * lpool * lq
    return z


# ------------------------------------------------------------------ universo e selecao
def opcoes(p):
    o = list(np.argsort(-p))
    fav = o[0]
    du = [fav, 1] if fav != 1 else [1, 0 if p[0] >= p[2] else 2]
    return [(p[fav], [fav]), (p[du[0]] + p[du[1]], sorted(du)), (1.0, [0, 1, 2])]


def cartela(P, d, t):
    dp = {(0, 0): (0.0, [])}
    for p in P:
        op = opcoes(p)
        nd = {}
        for (a, b), (v, esc) in dp.items():
            for k, (c, _) in enumerate(op):
                na, nb = a + (k == 1), b + (k == 2)
                if na > d or nb > t:
                    continue
                nv = v + math.log(max(c, 1e-9))
                if (na, nb) not in nd or nd[(na, nb)][0] < nv:
                    nd[(na, nb)] = (nv, esc + [k])
        dp = nd
    esc = max(dp.values(), key=lambda x: x[0])[1]
    return [opcoes(P[i])[esc[i]][1] for i in range(len(P))]


def universo(P, d=4, t=7):
    return np.array(list(itertools.product(*cartela(P, d, t))), dtype=np.int8)


def volantes_de(sel, P):
    """Combinacoes -> volantes de R$ 4 (2 combinacoes cada): pares que diferem em 1 jogo viram duplo;
    as sobras ganham 1 duplo gratis onde ele soma mais chance."""
    resto = {tuple(c): True for c in sel}
    vols = []
    for c in map(tuple, sel):
        if c not in resto:
            continue
        del resto[c]
        par, jp = None, -1
        for j in range(14):
            for o in range(3):
                if o == c[j]:
                    continue
                f = c[:j] + (o,) + c[j + 1:]
                if f in resto:
                    par, jp = f, j
                    break
            if par:
                break
        v = [[x] for x in c]
        if par:
            del resto[par]
            v[jp] = sorted([c[jp], par[jp]])
        else:
            bj, bo, bp = 0, 0, -1
            for j in range(14):
                for o in range(3):
                    if o != c[j] and P[j][o] / P[j][c[j]] > bp:
                        bp, bj, bo = P[j][o] / P[j][c[j]], j, o
            v[bj] = sorted([c[bj], bo])
        vols.append(v)
    return vols


def combinacoes_de(vols):
    s = set()
    for v in vols:
        for c in itertools.product(*v):
            s.add(c)
    return s


def escolher(P, Q, coef, pool, apostas, orcamento, criterio="valor"):
    G = universo(P)
    i = np.arange(14)
    lp = np.log(P[i, G]).sum(1)
    lq = np.log(np.clip(Q[i, G], 1e-3, 1)).sum(1)
    W = np.exp(log_ganhadores(coef, lq, lp, math.log(max(pool, 1.0)))) * apostas
    ev = np.exp(lp) * pool / (W + 1)
    ordem = np.argsort(-(ev if criterio == "valor" else lp))
    # cresce o conjunto ate o custo em volantes (R$ 4 cada) atingir o orcamento
    alvo = orcamento // 4
    k = 2 * alvo
    while True:
        vols = volantes_de(G[ordem[:k]], P)
        if len(vols) <= alvo or k <= 2:
            break
        k = int(k * 0.9)
    return vols, G, ev, W


def chance_e_valor(vols, P, Q, coef, pool, apostas):
    combs = np.array(sorted(combinacoes_de(vols)), dtype=np.int8)
    i = np.arange(14)
    lp = np.log(P[i, combs]).sum(1)
    lq = np.log(np.clip(Q[i, combs], 1e-3, 1)).sum(1)
    W = np.exp(log_ganhadores(coef, lq, lp, math.log(max(pool, 1.0)))) * apostas
    return float(np.exp(lp).sum()), float((np.exp(lp) * pool / (W + 1)).sum())


def premio_real(vols, res, R):
    combs = combinacoes_de(vols)
    res = tuple(res)
    n14 = 1 if res in combs else 0
    n13 = sum(1 for j in range(14) for o in range(3) if o != res[j] and res[:j] + (o,) + res[j + 1:] in combs)
    pr = 0.0
    if n14:
        pr += R["pool_14"] / (R["ganhadores_14"] + 1)
    if n13:
        pr += n13 * R["pool_13"] / (R["ganhadores_13"] + n13)
    return n14, n13, pr


# ------------------------------------------------------------------ teste
def testar():
    odds, massa, rat = odds_por_concurso(), massa_por_concurso(), rateio()
    X, Y, cs = dados_ganhadores(odds, massa, rat)
    print(f"Concursos com odds + enquete completa + rateio: {len(cs)}")
    pred = []
    for i in range(len(cs)):
        m = np.ones(len(cs), bool)
        m[i] = False
        pred.append(X[i] @ ajusta_ganhadores(X[m], Y[m]))
    print(f"Modelo de ganhadores (deixando o concurso de fora): correlacao {np.corrcoef(pred, Y)[0, 1]:.2f}")
    tot = defaultdict(lambda: [0, 0, 0.0, 0.0, 0.0, 0.0])
    estrut = {1296: (3, 4), 2592: (4, 4), 3888: (3, 5)}
    for i, c in enumerate(cs):
        m = np.ones(len(cs), bool)
        m[i] = False
        coef = ajusta_ganhadores(X[m], Y[m])
        P = np.array([prob_mercado(odds[c][j]) for j in range(1, 15)])
        Q = np.array([massa[c][j] for j in range(1, 15)])
        res = ["1X2".index(odds[c][j]["resultado"]) for j in range(1, 15)]
        R = rat[c]
        apostas = R["arrecadacao"] / PRECO
        for orc in ORCAMENTOS:
            d, t = estrut[orc]
            cheia = [[list(x) for x in [s]][0] for s in cartela(P, d, t)]
            vols_cheia = [cheia]  # uma cartela (pode passar de 864 comb.; so para conta)
            for nome, vols in (("cartela cheia", vols_cheia),
                               ("por chance", escolher(P, Q, coef, R["pool_14"], apostas, orc, "chance")[0]),
                               ("por valor (camada 2)", escolher(P, Q, coef, R["pool_14"], apostas, orc, "valor")[0])):
                ch, ev = chance_e_valor(vols, P, Q, coef, R["pool_14"], apostas)
                n14, n13, pr = premio_real(vols, res, R)
                custo = orc if nome == "cartela cheia" else len(vols) * 4
                t_ = tot[(orc, nome)]
                t_[0] += n14
                t_[1] += n13 > 0 and not n14
                t_[2] += pr
                t_[3] += custo
                t_[4] += ch
                t_[5] += ev
    print(f"\n{'orcamento':>10s} | {'escolha':22s} | {'chance 14':>9s} | {'retorno esperado 14':>19s} | {'fez 14':>6s} | {'fez 13':>6s} | {'retorno real':>12s}")
    for (orc, nome), t_ in sorted(tot.items()):
        n = len(cs)
        print(f"R$ {orc:>7,} | {nome:22s} | {100 * t_[4] / n:8.2f}% | {100 * t_[5] / t_[3]:18.1f}% | {t_[0]:6d} | {t_[1]:6d} | {100 * t_[2] / t_[3]:11.1f}%")


# ------------------------------------------------------------------ semana
def concurso_aberto(c=None):
    odds, massa, rat = odds_por_concurso(), massa_por_concurso(), rateio()
    import glob
    feitos = sorted(int(os.path.basename(a)[9:-4]) for a in glob.glob(os.path.join(SAIDA, "concurso_*.csv"))
                    if os.path.basename(a)[9:-4].isdigit())
    c = c or (feitos[-1] if feitos else max(odds))
    if len(odds.get(c, {})) != 14:
        # concurso aberto: odds da previsao da camada 1 (motor/saida/concurso_N.csv)
        prev = ler(os.path.join(SAIDA, f"concurso_{c}.csv"))
        if len(prev) == 14 and all(r.get("odd_1") for r in prev):
            odds[c] = {int(r["jogo"]): r for r in prev}
    if len(odds.get(c, {})) != 14:
        print(f"Concurso {c}: sem as 14 odds.")
        return
    X, Y, cs = dados_ganhadores(odds, massa, rat)
    coef = ajusta_ganhadores(X, Y)
    pares = [(prob_mercado(odds[cc][j]), massa[cc][j]) for cc in cs for j in range(1, 15)]
    prm = ajusta_massa(pares[-1400:])
    P = np.array([prob_mercado(odds[c][j]) for j in range(1, 15)])
    tem_massa = len(massa.get(c, {})) == 14
    Q = np.array([massa[c][j] for j in range(1, 15)]) if tem_massa else np.array([massa_estimada(p, prm) for p in P])
    ant = rat.get(c - 1) or {}
    pool = ant.get("estimado_proximo") or np.median([r["pool_14"] for r in rat.values()])
    acum = ant.get("acumulado_proximo") or 0
    pool = max(pool, acum)
    arrec = np.median([rat[k]["arrecadacao"] for k in sorted(rat)[-8:]])
    apostas = arrec / PRECO
    os.makedirs(SAIDA, exist_ok=True)
    estrut = {1296: (3, 4), 2592: (4, 4), 3888: (3, 5)}
    md = [f"# Concurso {c} — camada 2 (jogo por valor)", "",
          f"Prêmio de 14 em jogo (estimativa da Caixa): R$ {pool:,.0f} · apostas estimadas: {apostas:,.0f} combinações · "
          f"massa: {'enquete parcial da Vovoteca' if tem_massa else 'estimada pelas odds (sem enquete ainda)'}.".replace(",", "."), "",
          "| Orçamento | Escolha | Chance de 14 | Retorno esperado do 14 | Volantes |", "|---|---|---|---|---|"]
    for orc in ORCAMENTOS:
        d, t = estrut[orc]
        cheia = [cartela(P, d, t)]
        ch_c, ev_c = chance_e_valor(cheia, P, Q, coef, pool, apostas)
        vols, _, _, _ = escolher(P, Q, coef, pool, apostas, orc, "valor")
        ch_v, ev_v = chance_e_valor(vols, P, Q, coef, pool, apostas)
        md.append(f"| R$ {orc:,} | cartela cheia {14 - d - t}+{d}+{t} | {100 * ch_c:.2f}% | {100 * ev_c / orc:.0f}% | divide em volantes |".replace(",", "."))
        md.append(f"| R$ {orc:,} | **por valor** | {100 * ch_v:.2f}% | **{100 * ev_v / (len(vols) * 4):.0f}%** | {len(vols)} de R$ 4 |".replace(",", "."))
        arq = os.path.join(SAIDA, f"concurso_{c}_valor_R{orc}.csv")
        with open(arq, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["volante"] + [f"jogo_{j}" for j in range(1, 15)] + ["valor"])
            for n, v in enumerate(vols, 1):
                w.writerow([n] + ["".join("1X2"[o] for o in op) for op in v] + [4])
    md += ["", "Retorno esperado = chance × prêmio dividido pelos ganhadores previstos (modelo do rateio), sobre o custo. "
               "Volantes do jogo por valor em `concurso_{c}_valor_R<orçamento>.csv`.".replace("{c}", str(c))]
    with open(os.path.join(SAIDA, f"concurso_{c}_camada2.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "testar":
        testar()
    else:
        concurso_aberto(int(sys.argv[1]) if len(sys.argv) > 1 else None)
