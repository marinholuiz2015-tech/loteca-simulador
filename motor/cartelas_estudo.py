"""
Cartela principal e cartela de bolso — qual forma de montar rende mais em cada faixa de valor?

Para cada concurso do historico (modelos ajustados so com o passado, como na camada 3):
  base = a melhor base de 4 duplos + 5 triplos para a chance de 14 (3.888 combinacoes; triplos nos jogos
         mais incertos, duplos favorito + empate)
  formas, no mesmo valor:
    cartela unica  - a melhor cartela de 1 volante que cabe no valor (estrutura da camada 3)
    pela chance    - as combinacoes mais provaveis da base
    pelo valor     - as combinacoes de maior dinheiro esperado (chance x premio do 14 pelo modelo de ganhadores,
                     que usa a massa: combinacao que muita gente joga paga menos)
Dinheiro: rateio real do concurso, regra atual (pote do 14 x1,462 antes do 1162) e liquido de IR.
Saida: motor/cartelas_estudo.md
"""
import itertools
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import camada2 as c2  # noqa: E402
import camada3 as c3  # noqa: E402
import retorno_liquido as rl  # noqa: E402

VALORES = [100, 200, 500, 1000, 2000]
UNICA = {100: (4, 1), 200: (5, 1), 500: (3, 3), 1000: (4, 3), 2000: (5, 3)}  # custo 2*2^d*3^t <= valor


POT = 3 ** np.arange(14)


def p13mais(S, P):
    """chance de 13 ou 14: resultado igual a uma combinacao escolhida ou a 1 jogo de distancia."""
    cod = set((S.astype(np.int64) * POT).sum(1).tolist())
    cov = set(cod)
    for x in cod:
        for i in range(14):
            d = (x // POT[i]) % 3
            for k in range(3):
                if k != d:
                    cov.add(x + (k - d) * int(POT[i]))
    a = np.array(list(cov), dtype=np.int64)
    dig = (a[:, None] // POT) % 3
    return float(np.exp(np.log(P[np.arange(14), dig]).sum(1)).sum())


def main():
    odds, massa, rat, res = c2.odds_por_concurso(), c2.massa_por_concurso(), c2.rateio(), c3.resultados_cef()
    X, Y, cs_g = c2.dados_ganhadores(odds, massa, rat)
    pares = {cc: [(c2.prob_mercado(odds[cc][j]), massa[cc][j]) for j in range(1, 15)] for cc in cs_g}
    cache, linhas = {}, []
    for c in sorted(set(odds) & set(rat) & set(res)):
        passado = [i for i, cc in enumerate(cs_g) if cc < c]
        if len(passado) < 30 or len(odds[c]) < 14:
            continue
        ch = len(passado) // 10
        if ch not in cache:
            cache[ch] = (c2.ajusta_ganhadores(X[passado], Y[passado]),
                         c2.ajusta_massa([p for cc in cs_g[:len(passado)][-100:] for p in pares[cc]]),
                         c3.ajusta_arrecadacao(rat, c))
        coef, prm, carr = cache[ch]
        P = c3.P_de(odds[c])
        Q = np.array([massa[c][j] for j in range(1, 15)]) if len(massa.get(c, {})) == 14 else np.array([c2.massa_estimada(p, prm) for p in P])
        ant = rat.get(c - 1) or {}
        pool14p = max(ant.get("estimado_proximo") or 0, ant.get("acumulado_proximo") or 0)
        if pool14p <= 0:
            continue
        apostas = c3.arrecadacao_prevista(rat, c, pool14p, carr) / c2.PRECO
        base = c2.cartela(P, 4, 5)
        opts = [[int(k) for k in s] for s in base]
        combos = np.array(list(itertools.product(*opts)), dtype=np.int8)
        i = np.arange(14)
        lp = np.log(P[i, combos]).sum(1)
        lq = np.log(np.clip(Q[i, combos], 1e-3, 1)).sum(1)
        W = np.exp(c2.log_ganhadores(coef, lq, lp, math.log(pool14p))) * apostas
        valor = np.exp(lp) * pool14p / (W + 1)
        r = np.array([int(x) for x in res[c]])
        R = dict(rat[c])
        pool14 = R["pool_14"] * (rl.FATOR_14 if c < rl.NOVA_REGRA else 1)
        dist = (combos != r).sum(1)
        linha = {"c": c}
        for V in VALORES:
            k = V // 2
            equil = lp + 0.5 * np.log(np.maximum(valor / np.exp(lp), 1.0))  # chance x raiz do premio por ganhador
            for nome, ordem in (("chance", np.argsort(-lp)), ("equilibrado", np.argsort(-equil)), ("valor", np.argsort(-valor))):
                S = ordem[:k]
                acerta14 = bool((dist[S] == 0).any())
                n13 = int((dist[S] == 1).sum())
                pago = 0.0
                if acerta14:
                    pago += rl.liquido(pool14 / (R["ganhadores_14"] + 1))
                if n13 and R["pool_13"] > 0:
                    pago += n13 * rl.liquido(R["pool_13"] / (R["ganhadores_13"] + n13))
                linha[(nome, V)] = (pago, float(np.exp(lp[S]).sum()), float(valor[S].sum()) / V, acerta14, n13 > 0 and not acerta14, V,
                                    p13mais(combos[S], P))
            d, t = UNICA[V]
            cart = c2.cartela(P, d, t)
            custo = 2 * 2 ** d * 3 ** t
            Rr = dict(R, _c=c)
            pago = rl.pago(cart, res[c], Rr, True, True)
            okc = [res[c][j] in cart[j] for j in range(14)]
            p14 = float(np.prod([P[j, [int(x) for x in cart[j]]].sum() for j in range(14)]))
            cc = np.array(list(itertools.product(*[[int(x) for x in s_] for s_ in cart])), dtype=np.int8)
            lpu = np.log(P[np.arange(14), cc]).sum(1); lqu = np.log(np.clip(Q[np.arange(14), cc], 1e-3, 1)).sum(1)
            Wu = np.exp(c2.log_ganhadores(coef, lqu, lpu, math.log(pool14p))) * apostas
            linha[("unica", V)] = (pago, p14, float((np.exp(lpu) * pool14p / (Wu + 1)).sum()) / custo, all(okc), okc.count(False) == 1, custo,
                                   p13mais(cc, P))
        linhas.append(linha)
    md = ["# Cartela principal e cartela de bolso — qual forma rende mais", "",
          f"{len(linhas)} concursos ({linhas[0]['c']}–{linhas[-1]['c']}), modelos ajustados só com o passado. "
          "Base de 4 duplos + 5 triplos (3.888 combinações). Dinheiro com o rateio real, regra atual, líquido de IR.", "",
          "| Valor | Forma | Custo médio | Chance de 14 | Chance de 13 ou 14 | Retorno esperado do 14 (modelo) | 14 esperados × feitos | 13 feitos | Retorno líquido realizado |",
          "|---|---|---|---|---|---|---|---|---|"]
    for V in VALORES:
        for nome, rot in (("unica", "Cartela única"), ("chance", "Desdobre pela chance"), ("equilibrado", "Desdobre equilibrado"), ("valor", "Desdobre pelo valor")):
            vs = [l[(nome, V)] for l in linhas]
            custo = np.mean([v[5] for v in vs])
            gasto = sum(v[5] for v in vs)
            md.append(f"| R$ {V:,} | {rot} | R$ {custo:,.0f} | {np.mean([v[1] for v in vs]):.2%} | {np.mean([v[6] for v in vs]):.1%} | "
                      f"{np.mean([v[2] for v in vs]):.0%} | {sum(v[1] for v in vs):.1f} × {sum(v[3] for v in vs)} | "
                      f"{sum(v[4] for v in vs)} | {sum(v[0] for v in vs) / gasto:.0%} |".replace(",", "."))
    open(os.path.join(AQUI, "cartelas_estudo.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
