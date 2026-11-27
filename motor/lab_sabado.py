"""
A odd de sabado de manha acerta mais que a previsao de quinta? Mede com os resultados oficiais, nos
mesmos jogos (coleta/dados/odds_quinta_sabado.csv, gravado por motor/sabado.py).
forca = ganho medio de log-loss por concurso / erro padrao; acima de 2 = vale passar a apostar no sabado.
Uso: python motor/lab_sabado.py > motor/lab_sabado.md
"""
import collections
import csv
import json
import math
import os

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(RAIZ, "coleta", "dados", "odds_quinta_sabado.csv")


def resultados():
    H = json.load(open(os.path.join(RAIZ, "data", "historico_cef.json")))["concursos"]
    out = {}
    for k, c in H.items():
        for j in c["jogos"]:
            a, b = j.get("nuGolEquipeUm"), j.get("nuGolEquipeDois")
            if a is not None and b is not None:
                out[(int(k), j["nuSequencial"])] = 0 if a > b else (1 if a == b else 2)
    return out


def main():
    print("# Odd de sábado de manhã x previsão de quinta (mesmos jogos)\n")
    if not os.path.exists(REG):
        print("Ainda sem registros: o primeiro sábado com odds novas cria o arquivo.")
        return
    res = resultados()
    g = collections.defaultdict(float); n = aq = asb = 0
    for r in csv.DictReader(open(REG, encoding="utf-8")):
        k = (int(r["concurso"]), int(r["jogo"]))
        if k not in res:
            continue
        y = res[k]
        pq = np.array([float(r["p1_quinta"]), float(r["px_quinta"]), float(r["p2_quinta"])])
        ps = np.array([float(r["p1_sabado"]), float(r["px_sabado"]), float(r["p2_sabado"])])
        g[k[0]] += math.log(ps[y]) - math.log(pq[y]); n += 1
        aq += int(pq.argmax() == y); asb += int(ps.argmax() == y)
    if not n:
        print("Ainda sem resultados para os jogos registrados.")
        return
    d = np.array(list(g.values()))
    f = d.mean() / (d.std(ddof=1) / math.sqrt(len(d))) if len(d) > 2 and d.std() > 0 else 0.0
    print(f"- concursos medidos: {len(d)} · jogos: {n}")
    print(f"- acerto do favorito: quinta {100*aq/n:.1f}% → sábado {100*asb/n:.1f}%")
    print(f"- força (log-loss): {f:+.1f} → " + ("**vale apostar no sábado com a odd nova**" if f > 2 and len(d) >= 10
                                              else "ainda sem conclusão (precisa de força > 2 com 10+ concursos)"))


if __name__ == "__main__":
    main()
