"""
Laboratorio do empate — a chuva.

Achado da etapa 1: chuva forte no dia do jogo (>= 8 mm, medida pela NASA POWER depois do jogo) -> empate
33% x 25% da odd, nas duas metades do historico. Mas na quinta-feira so existe a PREVISAO do tempo.
Este teste usa a previsao como ela estava 2 dias antes de cada jogo (Open-Meteo, "previous runs"),
para os jogos da Loteca desde jan/2024, e compara com a chuva medida nos mesmos jogos.
Previsoes baixadas em coleta/dados/chuva_prevista.csv (gerado por este script a partir do cache).
Saida: motor/lab_chuva.md
"""
import csv
import glob
import json
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(os.path.dirname(AQUI), "coleta", "dados")
CACHE = os.environ.get("CHUVA_CACHE", "/tmp/prev")
sys.path.insert(0, AQUI)
import lab_empate as L0  # noqa: E402


def previsoes():
    prev = {}
    for arq in glob.glob(os.path.join(CACHE, "*.json")):
        la, lo = os.path.basename(arq)[:-5].split("_")
        j = json.load(open(arq))
        h = j.get("hourly") or {}
        for t, v2, v3 in zip(h.get("time", []), h.get("precipitation_previous_day2", []), h.get("precipitation_previous_day3", [])):
            prev[(la, lo, t[:13])] = (v2, v3)
    return prev


def main():
    prev = previsoes()
    sent = {(int(r["concurso"]), int(r["jogo"])): r for r in csv.DictReader(open(os.path.join(DADOS, "sentinela_jogos.csv"), encoding="utf-8"))}
    L = L0.base()
    linhas, saida = [], []
    import datetime
    for d in L:
        s = sent.get((d["c"], d["j"]))
        if not s or not s["lat"] or not s["inicio_utc"]:
            continue
        la, lo = f"{round(float(s['lat']), 2)}", f"{round(float(s['lon']), 2)}"
        ini = datetime.datetime.strptime(s["inicio_utc"][:16], "%Y-%m-%dT%H:%M")
        horas = [(ini + datetime.timedelta(hours=k)).strftime("%Y-%m-%dT%H") for k in range(-2, 3)]  # do aquecimento ao fim
        v = [prev.get((la, lo, h)) for h in horas]
        if any(x is None or x[0] is None for x in v):
            continue
        p2 = sum(x[0] for x in v)
        p3 = sum((x[1] or 0) for x in v) if all(x[1] is not None for x in v) else np.nan
        d = dict(d, prev2=p2, prev3=p3)
        linhas.append(d)
        saida.append({"concurso": d["c"], "jogo": d["j"], "chuva_prevista_2d_mm": round(p2, 1),
                      "chuva_prevista_3d_mm": "" if np.isnan(p3) else round(p3, 1),
                      "chuva_medida_dia_mm": "" if np.isnan(d.get("chuva_mm", np.nan)) else d["chuva_mm"]})
    with open(os.path.join(DADOS, "chuva_prevista.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(saida[0]))
        w.writeheader()
        w.writerows(saida)

    def tab(nome, S):
        if len(S) < 15:
            return f"| {nome} | {len(S)} | — | — | — |"
        y = np.mean([d["y_x"] for d in S])
        p = np.mean([d["p_x"] for d in S])
        se = math.sqrt(sum(d["p_x"] * (1 - d["p_x"]) for d in S)) / len(S)
        return f"| {nome} | {len(S)} | {y:.1%} | {p:.1%} | {(y - p) / se:+.2f} |"

    md = ["# Laboratório do empate — chuva prevista × chuva medida", "",
          f"Jogos da Loteca desde jan/2024 com previsão de 2 dias antes: **{len(linhas)}**. "
          "Chuva somada das 2 horas antes às 2 horas depois do início do jogo.", "",
          "| Grupo | Jogos | Empate real | Empate pela odd | z |", "|---|---|---|---|---|"]
    for corte in (2, 4, 8):
        md.append(tab(f"Previsão 2 dias antes ≥ {corte} mm", [d for d in linhas if d["prev2"] >= corte]))
    md.append(tab("Previsão 2 dias antes < 2 mm", [d for d in linhas if d["prev2"] < 2]))
    for corte in (2, 4, 8):
        md.append(tab(f"Previsão 3 dias antes ≥ {corte} mm", [d for d in linhas if not np.isnan(d["prev3"]) and d["prev3"] >= corte]))
    md.append(tab("Chuva MEDIDA no dia ≥ 8 mm (mesmos jogos)", [d for d in linhas if d.get("chuva_mm", 0) >= 8]))
    md.append(tab("Chuva MEDIDA no dia ≥ 8 mm (histórico todo, 2020+)", [d for d in L if d.get("chuva_mm", 0) >= 8]))
    open(os.path.join(AQUI, "lab_chuva.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
