"""
Efeito manada: enquete final da Vovoteca (massa) x odds bet365 (mercado).

Cruza coleta/dados/vovoteca_massa.csv com coleta/dados/arena_odds.csv
(mesmo concurso e jogo) e com o resultado oficial, e mede:
  1. acerto do favorito e Brier: massa x mercado (mesmos jogos)
  2. quando os favoritos divergem, quem acerta
  3. vies da massa: para cada resultado possivel (1, X, 2), compara o quanto a
     massa marcou com a probabilidade do mercado e com a frequencia real.
     Resultado "supervotado" (massa >> mercado) que acontece na frequencia do
     mercado = rateio pior; "subvotado" = rateio melhor quando acontece.
Grava coleta/dados/massa_x_mercado.csv e imprime o resumo.
"""
import csv
import math
import os
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, "dados")


def ler(n):
    with open(os.path.join(DADOS, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    massa = {(int(r["concurso"]), int(r["jogo"])): r for r in ler("vovoteca_massa.csv")}
    odds = {(int(r["concurso"]), int(r["jogo"])): r for r in ler("arena_odds.csv")}
    linhas = []
    for k, m in massa.items():
        o = odds.get(k)
        if not o or not o["resultado"]:
            continue
        pm = {"1": float(m["massa_1"]) / 100, "X": float(m["massa_x"]) / 100, "2": float(m["massa_2"]) / 100}
        s = sum(pm.values())
        pm = {a: v / s for a, v in pm.items()}
        po = {"1": float(o["p_1"]), "X": float(o["p_x"]), "2": float(o["p_2"])}
        linhas.append(dict(concurso=k[0], jogo=k[1], mandante=o["mandante"], visitante=o["visitante"],
                           massa_1=round(pm["1"], 4), massa_x=round(pm["X"], 4), massa_2=round(pm["2"], 4),
                           merc_1=po["1"], merc_x=po["X"], merc_2=po["2"],
                           fav_massa=max(pm, key=pm.get), fav_merc=max(po, key=po.get),
                           resultado=o["resultado"]))
    if not linhas:
        print("sem jogos em comum")
        return
    with open(os.path.join(DADOS, "massa_x_mercado.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    n = len(linhas)
    P = lambda r, p: {"1": r[p + "_1"], "X": r[p + "_x"], "2": r[p + "_2"]}
    brier = lambda p, res: sum((p[a] - (a == res)) ** 2 for a in "1X2")
    ac_ma = sum(r["fav_massa"] == r["resultado"] for r in linhas) / n
    ac_me = sum(r["fav_merc"] == r["resultado"] for r in linhas) / n
    b_ma = sum(brier(P(r, "massa"), r["resultado"]) for r in linhas) / n
    b_me = sum(brier(P(r, "merc"), r["resultado"]) for r in linhas) / n
    print(f"== {n} jogos com enquete final + odds + resultado "
          f"({len({r['concurso'] for r in linhas})} concursos) ==")
    print(f"  acerto do favorito: massa {ac_ma:.1%} | mercado {ac_me:.1%}")
    print(f"  Brier: massa {b_ma:.4f} | mercado {b_me:.4f} (menor = melhor)")

    div = [r for r in linhas if r["fav_massa"] != r["fav_merc"]]
    if div:
        b = sum(r["fav_massa"] == r["resultado"] for r in div)
        c = sum(r["fav_merc"] == r["resultado"] for r in div)
        print(f"\n== Favoritos diferentes: {len(div)} jogos ==")
        print(f"  massa acerta {b} ({b / len(div):.0%}) | mercado acerta {c} ({c / len(div):.0%})")
        z = (c - b) / math.sqrt(b + c) if b + c else 0
        print(f"  McNemar z = {z:.1f} (positivo = mercado melhor)")

    print("\n== Vies da massa por resultado (diferenca massa - mercado, em pontos) ==")
    faixas = [(-1, -.15), (-.15, -.05), (-.05, .05), (.05, .15), (.15, 1)]
    nomes = ["subvotado >15", "subvotado 5-15", "alinhado +-5", "supervotado 5-15", "supervotado >15"]
    for a in "1X2":
        print(f"  resultado {a}:")
        for (lo, hi), nome in zip(faixas, nomes):
            g = [r for r in linhas if lo <= P(r, "massa")[a] - P(r, "merc")[a] < hi]
            if len(g) < 10:
                continue
            real = sum(r["resultado"] == a for r in g) / len(g)
            me = sum(P(r, "merc")[a] for r in g) / len(g)
            ma = sum(P(r, "massa")[a] for r in g) / len(g)
            print(f"    {nome:<17} {len(g):>4} jogos | massa {ma:5.1%} | mercado {me:5.1%} | real {real:5.1%}")

    # resumo agregado: quanto a massa marca cada coluna vs frequencia real
    print("\n== Agregado ==")
    for a in "1X2":
        ma = sum(P(r, "massa")[a] for r in linhas) / n
        me = sum(P(r, "merc")[a] for r in linhas) / n
        real = sum(r["resultado"] == a for r in linhas) / n
        print(f"  coluna {a}: massa {ma:5.1%} | mercado {me:5.1%} | real {real:5.1%}")


if __name__ == "__main__":
    main()
