"""
Base de features por jogo para a pesquisa de acuracia (meta: 14=56%, 10=60%,
8=62%, 6=65%, 4=70%). Junta odds bet365 (Arena), contexto da grade da Caixa,
palpite do Lotequeiros e, quando houver, a enquete da Vovoteca.
Gera coleta/pesquisa/base_features.csv.
"""
import csv
import json
import math
import os

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
DADOS = os.path.join(REPO, "coleta", "dados")


def power(o):
    inv = np.array([1 / x for x in o])
    lo, hi = 0.5, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if (inv ** k).sum() > 1:
            lo = k
        else:
            hi = k
    p = inv ** k
    return p / p.sum()


def ler(nome):
    with open(os.path.join(DADOS, nome), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    cef = json.load(open(os.path.join(REPO, "data", "historico_cef.json"), encoding="utf-8"))["concursos"]
    lq = {(int(r["concurso"]), int(r["jogo"])): r for r in ler("lotequeiros_x_caixa.csv")}
    ms = {(int(r["concurso"]), int(r["jogo"])): r for r in ler("vovoteca_massa.csv")}
    linhas = []
    for r in ler("arena_odds.csv"):
        if not r["resultado"]:
            continue
        c, j = int(r["concurso"]), int(r["jogo"])
        o = [float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])]
        p = power(o)
        g = next((x for x in cef.get(str(c), {}).get("jogos", []) if x["nuSequencial"] == j), {})
        intl = any(g.get(k) and g.get(k) != "BRA" for k in ("siglaPaisUm", "siglaPaisDois"))
        uf_igual = bool(g.get("siglaUFUm")) and g.get("siglaUFUm") == g.get("siglaUFDois")
        l = lq.get((c, j), {})
        m = ms.get((c, j), {})
        fav = int(np.argmax(p))
        linhas.append(dict(
            concurso=c, jogo=j, resultado="1X2".index(r["resultado"]),
            p1=p[0], px=p[1], p2=p[2], margem=sum(1 / x for x in o) - 1,
            pfav=p.max(), fav=fav, equilibrio=abs(p[0] - p[2]),
            intl=int(intl), mesmo_estado=int(uf_igual),
            lq_seco="1X2".index(l["seco"]) if l.get("seco") else -1,
            lq_duplo=l.get("duplo", ""),
            lq_concorda=int(bool(l.get("seco")) and "1X2".index(l["seco"]) == fav) if l.get("seco") else -1,
            massa1=float(m["massa_1"]) / 100 if m else -1, massax=float(m["massa_x"]) / 100 if m else -1,
            massa2=float(m["massa_2"]) / 100 if m else -1,
            mes=int(r["data_jogo"][3:5]) if r["data_jogo"] else 0,
            dow=0,
        ))
    linhas.sort(key=lambda x: (x["concurso"], x["jogo"]))
    with open(os.path.join(AQUI, "base_features.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} jogos | com Lotequeiros: {sum(1 for x in linhas if x['lq_seco'] >= 0)} | "
          f"com massa: {sum(1 for x in linhas if x['massa1'] >= 0)}")


if __name__ == "__main__":
    main()
