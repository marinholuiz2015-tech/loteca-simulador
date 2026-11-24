"""
Estrutura da aposta por concurso (item 4 da auditoria) — quantos duplos e triplos usar.

Para o orcamento de ~R$ 200 por semana, compara no historico (cartelas montadas so com o passado; o motor
coloca os triplos nos jogos mais incertos e os duplos favorito+empate de forma otima para a chance de 14):
  estruturas fixas: 6 duplos (R$ 128), 3 duplos + 2 triplos (R$ 144), 4 triplos (R$ 162),
                    5 duplos + 1 triplo (R$ 192, a de hoje), 2 duplos + 3 triplos (R$ 216)
  adaptativa: em cada concurso, a estrutura de maior retorno esperado pelo modelo (por real apostado)
  por incerteza: mais triplos quando a grade tem muitos jogos incertos (favorito abaixo de 45%)
Dinheiro com a regra atual da Caixa e liquido de IR (motor/retorno_liquido.py).
Saida: motor/estrutura_concurso.md
"""
import os
import pickle
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import camada3 as c3  # noqa: E402
import camada2 as c2  # noqa: E402
import retorno_liquido as rl  # noqa: E402

ESTR = {128: (6, 0), 144: (3, 2), 162: (0, 4), 192: (5, 1), 216: (2, 3)}
NOME = {128: "6 duplos", 144: "3 duplos + 2 triplos", 162: "4 triplos", 192: "5 duplos + 1 triplo (hoje)",
        216: "2 duplos + 3 triplos"}


def main():
    cache = "/tmp/estrutura_hist.pkl"
    if os.path.exists(cache):
        L = pickle.load(open(cache, "rb"))
    else:
        c3.ESCADA = ESTR
        L = c3.historico()
        pickle.dump(L, open(cache, "wb"))
    rat, res, odds = c2.rateio(), c3.resultados_cef(), c2.odds_por_concurso()

    def liq(l, orc):
        R = dict(rat[l["concurso"]], _c=l["concurso"])
        return rl.pago(l["orc"][orc]["cartela"], res[l["concurso"]], R, True, True)

    def incertos(c):
        return sum(max(c2.prob_mercado(odds[c][j])) < 0.45 for j in range(1, 15) if j in odds[c])

    linhas = []
    for nome, escolhe in [(NOME[o], (lambda l, o=o: o)) for o in ESTR] + [
            ("**Adaptativa** (maior retorno esperado no concurso)", lambda l: max(ESTR, key=lambda o: l["orc"][o]["retorno"])),
            ("**Por incerteza** (≥ 6 jogos incertos → 2 duplos + 3 triplos; ≤ 3 → 6 duplos; senão hoje)",
             lambda l: 216 if incertos(l["concurso"]) >= 6 else (128 if incertos(l["concurso"]) <= 3 else 192))]:
        gasto = receb = n14 = n13 = 0.0
        esc = {}
        for l in L:
            o = escolhe(l)
            esc[o] = esc.get(o, 0) + 1
            gasto += o
            receb += liq(l, o)
            n14 += l["orc"][o]["pontos"] == 14
            n13 += l["orc"][o]["pontos"] == 13
        ev = np.mean([l["orc"][escolhe(l)]["retorno"] for l in L])
        linhas.append((nome, gasto, receb, int(n14), int(n13), ev, esc))
    inc = np.array([incertos(l["concurso"]) for l in L])
    md = ["# Estrutura da aposta por concurso — orçamento de ~R$ 200", "",
          f"{len(L)} concursos ({L[0]['concurso']}–{L[-1]['concurso']}), cartelas montadas só com informação anterior. "
          "Os triplos vão para os jogos mais incertos e os duplos para favorito + empate (posição ótima para a chance de 14). "
          "Dinheiro com a regra atual da Caixa, líquido de IR.", "",
          f"Jogos incertos (favorito < 45%) por concurso: mediana {np.median(inc):.0f}, de {inc.min()} a {inc.max()}.", "",
          "| Estrutura | Gasto | Recebido líquido | Retorno líquido | 14 | 13 | Retorno esperado pelo modelo (bruto, regra da época) | Escolhas |",
          "|---|---|---|---|---|---|---|---|"]
    for nome, g, r, a, b, ev, esc in linhas:
        md.append(f"| {nome} | R$ {g:,.0f} | R$ {r:,.0f} | {r / g:.0%} | {a} | {b} | {ev:.0%} | ".replace(",", ".") +
                  ", ".join(f"R$ {o}: {n}" for o, n in sorted(esc.items())) + " |")
    open(os.path.join(AQUI, "estrutura_concurso.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
