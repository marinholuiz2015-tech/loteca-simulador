"""
A odd de quinta (bet365, a que o motor usa) perde quanto para a odd de FECHAMENTO?
Casa os jogos da Loteca (arena_odds.csv) com o football-data (data +-1 dia e nomes)
e compara bet365 quinta x fechamento da bet365, Pinnacle, Betfair e media das casas.
Grava motor/fechamento.md. Uso: python coleta/pesquisa/fechamento.py
"""
import csv
import datetime
import math
import os
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "motor"))
import fd_base  # noqa: E402
from calibracao import ajusta_gama, sem_margem  # noqa: E402

R = {"1": 0, "X": 1, "2": 2}
FONTES = [("bet365 fechamento", "b365c"), ("Pinnacle fechamento", "ps"), ("Betfair fechamento", "bf"),
          ("média das casas no fechamento", "avg"), ("Pinnacle abertura", "pso")]


def casar():
    por_dia = {}
    for g in fd_base.jogos():
        por_dia.setdefault(g["d"], []).append(g)
    out = []
    for r in csv.DictReader(open(os.path.join(RAIZ, "coleta", "dados", "arena_odds.csv"), encoding="utf-8")):
        d = fd_base.data(r.get("data_jogo") or "")
        if not d or r.get("resultado") not in R:
            continue
        cands = [g for k in (-1, 0, 1) for g in por_dia.get(d + datetime.timedelta(k), [])]
        sc = sorted(((fd_base.sim(r["mandante"], g["casa"]) + fd_base.sim(r["visitante"], g["fora"]),
                      min(fd_base.sim(r["mandante"], g["casa"]), fd_base.sim(r["visitante"], g["fora"])), i)
                     for i, g in enumerate(cands)), reverse=True)
        if sc and sc[0][0] >= 1.45 and sc[0][1] >= 0.55 and (len(sc) == 1 or sc[0][0] - sc[1][0] > 0.25):
            out.append((r, cands[sc[0][2]]))
    return out


def prob(o):
    return np.array(ajusta_gama(sem_margem(o), 1.04))


def main():
    pares = casar()
    md = ["# Odd de quinta × odd de fechamento", "",
          f"Jogos da Loteca casados com o football-data: {len(pares)}. Mesmo tratamento para todas as odds "
          "(sem margem + gama 1,04).", "",
          "| Odd | Jogos | Log-loss | Acerto do favorito | Duplo fav+X | Ganho sobre a quinta (força) |",
          "|---|---|---|---|---|---|"]

    def met(sub, k):
        ll, ac, du = [], [], []
        for r, g in sub:
            y = R[r["resultado"]]
            p = prob([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])] if k is None else g[k])
            f = int(p.argmax())
            ll.append(-math.log(p[y]))
            ac.append(f == y)
            du.append(y in ({f, 1} if f != 1 else {1, 0 if p[0] >= p[2] else 2}))
        return np.array(ll), np.mean(ac), np.mean(du)

    for nome, k in FONTES:
        sub = [(r, g) for r, g in pares if k in g]
        if len(sub) < 100:
            continue
        b, ab, db = met(sub, None)
        m, am, dm = met(sub, k)
        gan = b - m
        f = gan.mean() / (gan.std() / math.sqrt(len(gan)))
        md.append(f"| bet365 quinta (nosso) | {len(sub)} | {b.mean():.4f} | {ab:.1%} | {db:.1%} | — |")
        md.append(f"| {nome} | {len(sub)} | {m.mean():.4f} | {am:.1%} | {dm:.1%} | {gan.mean():+.4f} ({f:+.1f}) |")
    md += ["", "Leitura: força > 2 = o fechamento é de fato mais preciso; o acerto do favorito mostra se isso muda "
           "o palpite. Se o ganho é pequeno, esperar a odd de sábado rende pouco."]
    open(os.path.join(RAIZ, "motor", "fechamento.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
