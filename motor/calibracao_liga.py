"""
Frente 2: a bet365 erra de jeito diferente em cada campeonato? Um ajuste (gama + fator de empate) por
campeonato melhora a probabilidade em relacao ao ajuste unico de hoje?

A) 48 mil jogos europeus (bet365 abertura, football-data): aprende com as temporadas anteriores, testa na seguinte.
B) Jogos da Loteca (bet365 de quinta, Arena): grupo = liga do football-data quando o jogo casa
   (Brasileirao A, Italia, Espanha, Inglaterra...), senao "outros" (Serie B/C, copas, estaduais, selecoes).
   Aprende com os concursos anteriores (re-treina a cada 20), testa nos seguintes.
Forca = ganho medio de log-loss (por liga x unico) / erro-padrao. > 2 = ganho real.
Saida: motor/calibracao_liga.md
"""
import csv
import math
import os
import sys
from collections import defaultdict

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(os.path.dirname(AQUI), "coleta", "dados")
sys.path.insert(0, AQUI)
from calibracao import aplica, aprende  # noqa: E402
from fd_base import data, jogos, sim  # noqa: E402

MIN_LIGA = 300  # liga com menos jogos de treino usa o ajuste unico


def ll(odds, y, params):
    return math.log(max(aplica(odds, params)[y], 1e-9))


def forca(g):
    g = np.array(g)
    if len(g) > 2 and g.std() == 0:
        return 0.0  # liga pequena: usou o ajuste unico, nenhuma diferenca
    return float(g.mean() / (g.std(ddof=1) / math.sqrt(len(g)))) if len(g) > 2 else 0.0


def resultado(gc, gf):
    return 0 if gc > gf else (1 if gc == gf else 2)


def europa():
    J = [g for g in jogos() if g["gc"] is not None and "b365o" in g and not g["liga"].startswith("new_")]
    for g in J:
        g["y"] = resultado(g["gc"], g["gf"])
    temps = sorted({g["temporada"] for g in J})
    ganhos, por_liga, params_fim = [], defaultdict(list), {}
    for t in temps[3:]:
        tr = [g for g in J if g["temporada"] < t]
        te = [g for g in J if g["temporada"] == t]
        unico = aprende([(g["b365o"], g["y"]) for g in tr])
        liga = {}
        for lg in {g["liga"] for g in te}:
            sub = [(g["b365o"], g["y"]) for g in tr if g["liga"] == lg]
            liga[lg] = aprende(sub) if len(sub) >= MIN_LIGA else unico
        for g in te:
            d = ll(g["b365o"], g["y"], liga[g["liga"]]) - ll(g["b365o"], g["y"], unico)
            ganhos.append(d)
            por_liga[g["liga"]].append(d)
        params_fim = liga
    return ganhos, por_liga, params_fim


def loteca():
    placar = {(r["concurso"], r["jogo"]): (r["gols_m"], r["gols_v"])
              for r in csv.DictReader(open(os.path.join(DADOS, "resultados_caixa.csv"), encoding="utf-8"))}
    fd = defaultdict(list)
    for g in jogos():
        if g["gc"] is not None:
            fd[(g["gc"], g["gf"])].append(g)
    grupo_nome = {"new_BRA": "Brasileirão A", "I1": "Itália", "SP1": "Espanha", "E0": "Inglaterra"}
    J = []
    for r in csv.DictReader(open(os.path.join(DADOS, "arena_odds.csv"), encoding="utf-8")):
        if r.get("resultado") not in ("1", "X", "2"):
            continue
        grupo = "Outros (Série B/C, copas, estaduais, seleções)"
        d = data(r.get("data_jogo") or "")
        gm, gv = placar.get((r["concurso"], r["jogo"]), ("", ""))
        if d and gm != "":
            melhor, nota = None, 0
            for g in fd[(int(float(gm)), int(float(gv)))]:
                if abs((g["d"] - d).days) <= 2:
                    s = min(sim(r["mandante"], g["casa"]), sim(r["visitante"], g["fora"]))
                    if s > nota:
                        melhor, nota = g, s
            if melhor and nota >= 0.7:
                grupo = grupo_nome.get(melhor["liga"], "Outras ligas europeias")
        J.append({"c": int(r["concurso"]), "odds": [float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])],
                  "y": "1X2".index(r["resultado"]), "grupo": grupo})
    J.sort(key=lambda x: x["c"])
    cs = sorted({x["c"] for x in J})
    inicio = cs[len(cs) // 3]
    ganhos, por_grupo, unico, liga = [], defaultdict(list), None, {}
    for i, c in enumerate(cs):
        if c < inicio:
            continue
        if unico is None or i % 20 == 0:
            tr = [x for x in J if x["c"] < c]
            unico = aprende([(x["odds"], x["y"]) for x in tr])
            liga = {}
            for gname in {x["grupo"] for x in J}:
                sub = [(x["odds"], x["y"]) for x in tr if x["grupo"] == gname]
                liga[gname] = aprende(sub) if len(sub) >= MIN_LIGA else unico
        for x in J:
            if x["c"] == c:
                d = ll(x["odds"], x["y"], liga[x["grupo"]]) - ll(x["odds"], x["y"], unico)
                ganhos.append(d)
                por_grupo[x["grupo"]].append(d)
    cont = defaultdict(int)
    for x in J:
        cont[x["grupo"]] += 1
    return ganhos, por_grupo, liga, unico, cont


def main():
    L = ["# Frente 2 — ajuste da odd por campeonato × ajuste único", "",
         "Gama > 1 = a odd subestima o favorito (deixa ele mais forte); < 1 = superestima. "
         "Fator de empate > 1 = a odd subestima o empate nos jogos equilibrados.", ""]
    g, por, params = europa()
    L += [f"## A) Europa — bet365, {len(g)} jogos testados (temporada seguinte, nunca vista)", "",
          f"Ganho total do ajuste por liga sobre o único: **força {forca(g):+.2f}** "
          f"(ganho médio de log-loss {np.mean(g):+.5f}).", "",
          "| Liga | Jogos testados | Força | Gama aprendida | Fator de empate |", "|---|---|---|---|---|"]
    for lg, v in sorted(por.items(), key=lambda t: -len(t[1])):
        p = params.get(lg, {})
        L.append(f"| {lg} | {len(v)} | {forca(v):+.2f} | {p.get('gama', '-')} | {p.get('fator_empate', 1):.3f} |")
    g, por, liga, unico, cont = loteca()
    L += ["", f"## B) Loteca — bet365 de quinta (Arena), {len(g)} jogos testados", "",
          f"Ganho total do ajuste por campeonato sobre o único: **força {forca(g):+.2f}** "
          f"(ganho médio de log-loss {np.mean(g):+.5f}). Ajuste único aprendido: gama {unico['gama']}, "
          f"empate {unico['fator_empate']:.3f}.", "",
          "| Campeonato | Jogos (total) | Jogos testados | Força | Gama | Fator de empate |", "|---|---|---|---|---|---|"]
    for gname, v in sorted(por.items(), key=lambda t: -len(t[1])):
        p = liga.get(gname, {})
        L.append(f"| {gname} | {cont[gname]} | {len(v)} | {forca(v):+.2f} | {p.get('gama', '-')} | {p.get('fator_empate', 1):.3f} |")
    open(os.path.join(AQUI, "calibracao_liga.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
