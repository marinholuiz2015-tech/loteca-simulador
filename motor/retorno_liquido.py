"""
Bloco 1 — retorno em reais com a regra ATUAL do rateio e o valor LIQUIDO (depois do IR).

Usa o mesmo teste no tempo da camada 3 (c3.historico: cartelas montadas so com informacao anterior),
e recalcula o que cada cartela teria recebido de tres jeitos:
  bruto, regra da epoca   (como os estudos anteriores)
  bruto, regra atual      concursos antes do 1162: pote do 14 x 1,462 (18,43% -> 26,95% da arrecadacao)
  liquido, regra atual    + IR de 30% sobre o que passa da isencao (R$ 2.428,80) em cada premio
Tambem separa por nivel do concurso (derrotas esperadas do favorito, pela odd).
Saida: motor/retorno_liquido.md
"""
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import camada2 as c2  # noqa: E402
import camada3 as c3  # noqa: E402

ISENCAO = 2428.80
NOVA_REGRA = 1162
FATOR_14 = 26.95 / 18.43


def liquido(v):
    return v if v <= ISENCAO else ISENCAO + (v - ISENCAO) * 0.7


def pago(cart, res, R, atual, ir):
    ok = [res[j] in cart[j] for j in range(14)]
    er = ok.count(False)
    pool14 = R["pool_14"] * (FATOR_14 if atual and R.get("_c", 9999) < NOVA_REGRA else 1)
    total = 0.0
    if er == 0:
        p = pool14 / (R["ganhadores_14"] + 1)
        total += liquido(p) if ir else p
        n13 = sum(len(s) - 1 for s in cart)
    elif er == 1:
        n13 = len(cart[ok.index(False)])
    else:
        n13 = 0
    if n13 and R["pool_13"] > 0:
        p = R["pool_13"] / (R["ganhadores_13"] + n13)
        total += n13 * (liquido(p) if ir else p)
    return total


def main():
    import pickle
    cache = '/tmp/c3_historico.pkl'
    if os.path.exists(cache):
        L = pickle.load(open(cache, 'rb'))
    else:
        L = c3.historico()
        pickle.dump(L, open(cache, 'wb'))
    rat, res, odds = c2.rateio(), c3.resultados_cef(), c2.odds_por_concurso()
    nivel = {}
    for c in odds:
        try:
            nivel[c] = sum(1 - max(c2.prob_mercado(odds[c][j])) for j in range(1, 15))
        except Exception:
            pass
    niveis = np.array([nivel[l["concurso"]] for l in L if l["concurso"] in nivel])
    corte1, corte2 = np.percentile(niveis, 33), np.percentile(niveis, 67)
    jeitos = [("Bruto, regra da época", False, False), ("Bruto, regra atual", True, False), ("**Líquido, regra atual**", True, True)]
    md = ["# Bloco 1 — retorno em reais com a regra atual e o valor líquido", "",
          f"Concursos testados: {len(L)} ({min(l['concurso'] for l in L)}–{max(l['concurso'] for l in L)}). "
          "Cartelas montadas só com informação anterior a cada concurso (mesmo teste da camada 3). "
          "Regra atual: pote do 14 ×1,462 nos concursos antes do 1162. Líquido: IR de 30% acima de R$ 2.428,80 por prêmio.", "",
          "## Retorno por orçamento (recebido ÷ apostado)", "", "| Orçamento | " + " | ".join(j[0] for j in jeitos) + " | 14 feitos | 13 feitos |",
          "|---|" + "---|" * (len(jeitos) + 2)]
    for orc in c3.ESCADA:
        cu = orc * len(L)
        vals = []
        for _, atual, ir in jeitos:
            tot = 0.0
            for l in L:
                R = dict(rat[l["concurso"]], _c=l["concurso"])
                tot += pago(l["orc"][orc]["cartela"], res[l["concurso"]], R, atual, ir)
            vals.append(f"{tot / cu:.0%}")
        md.append(f"| R$ {orc:,} | ".replace(",", ".") + " | ".join(vals) +
                  f" | {sum(l['orc'][orc]['pontos'] == 14 for l in L)} | {sum(l['orc'][orc]['pontos'] == 13 for l in L)} |")
    md += ["", f"## Por nível do concurso (líquido, regra atual) — fácil < {corte1:.1f} derrotas esperadas do favorito ≤ médio ≤ {corte2:.1f} < difícil", "",
           "| Orçamento | Nível | Concursos | Retorno líquido | 14 feitos | 13 feitos | Prêmio médio do 14 (bruto, regra atual) |", "|---|---|---|---|---|---|---|"]
    for orc in (192, 2592, 11664):
        for nome, f in (("fácil", lambda x: x < corte1), ("médio", lambda x: corte1 <= x <= corte2), ("difícil", lambda x: x > corte2)):
            S = [l for l in L if l["concurso"] in nivel and f(nivel[l["concurso"]])]
            if not S:
                continue
            tot = sum(pago(l["orc"][orc]["cartela"], res[l["concurso"]], dict(rat[l["concurso"]], _c=l["concurso"]), True, True) for l in S)
            pr = [rat[l["concurso"]]["pool_14"] * (FATOR_14 if l["concurso"] < NOVA_REGRA else 1) / rat[l["concurso"]]["ganhadores_14"]
                  for l in S if rat[l["concurso"]]["ganhadores_14"] > 0]
            md.append(f"| R$ {orc:,} | {nome} | {len(S)} | {tot / (orc * len(S)):.0%} | ".replace(",", ".") +
                      f"{sum(l['orc'][orc]['pontos'] == 14 for l in S)} | {sum(l['orc'][orc]['pontos'] == 13 for l in S)} | "
                      f"R$ {np.median(pr):,.0f} (mediana) |".replace(",", "."))
    open(os.path.join(AQUI, "retorno_liquido.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
