"""
Base de jogos com xG e estatisticas (FotMob) para os pilares sem odds.

Para cada liga/temporada, le a lista de jogos e, para cada jogo encerrado ainda nao salvo, grava em
coleta/dados/fotmob_jogos.csv: data, times, placar, xG, xG de bola rolando, xGOT, finalizacoes, no alvo,
grandes chances, toques na area, posse, vermelhos, gramado, estadio (lat/lon), arbitro, publico.
Retoma de onde parou. Uso: python coleta/fotmob_xg.py [--ligas 268,8814] [--temporadas 2025,2026] [--max N]
"""
import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "coleta", "dados", "fotmob_jogos.csv")
API = "https://www.fotmob.com/api/data"
HEAD = {"User-Agent": "Mozilla/5.0 (estudo pessoal; consulta leve)"}
LIGAS = {268: "Brasileirao A", 8814: "Brasileirao B", 8971: "Brasileirao C", 9067: "Copa do Brasil",
         45: "Libertadores", 299: "Sul-Americana", 10244: "Paulista", 47: "Premier League", 87: "LaLiga",
         55: "Serie A Italia", 53: "Ligue 1", 54: "Bundesliga", 48: "Championship"}
CAMPOS = ["match_id", "liga_id", "liga", "temporada", "rodada", "data_utc", "casa_id", "casa", "fora_id", "fora",
          "gc", "gf", "xg_c", "xg_f", "xgop_c", "xgop_f", "xgot_c", "xgot_f", "fin_c", "fin_f", "alvo_c", "alvo_f",
          "gch_c", "gch_f", "area_c", "area_f", "posse_c", "posse_f", "verm_c", "verm_f", "gramado", "estadio",
          "lat", "lon", "arbitro", "arbitro_id", "publico"]
trava = threading.Lock()


def get(url, params=None, tent=3):
    for t in range(tent):
        try:
            r = requests.get(url, params=params, headers=HEAD, timeout=25)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (403, 429):
                time.sleep(20 * (t + 1))
        except Exception:
            time.sleep(3 * (t + 1))
    return None


def num(v):
    try:
        return float(str(v).split(" ")[0].replace("%", ""))
    except Exception:
        return ""


def detalhe(mid):
    d = get(f"{API}/matchDetails", {"matchId": mid})
    if not d:
        return None
    c = d.get("content", {}) or {}
    st = {}
    try:
        for per in c["stats"]["Periods"]["All"]["stats"]:
            for s in per.get("stats", []):
                k, v = s.get("key"), s.get("stats")
                if k and v and v[0] is not None and k not in st:
                    st[k] = v
    except Exception:
        pass
    info = (c.get("matchFacts") or {}).get("infoBox") or {}
    est = info.get("Stadium") or {}
    arb = info.get("Referee") or {}
    g = lambda k, i: num(st[k][i]) if k in st else ""
    return {"xg_c": g("expected_goals", 0), "xg_f": g("expected_goals", 1),
            "xgop_c": g("expected_goals_open_play", 0), "xgop_f": g("expected_goals_open_play", 1),
            "xgot_c": g("expected_goals_on_target", 0), "xgot_f": g("expected_goals_on_target", 1),
            "fin_c": g("total_shots", 0), "fin_f": g("total_shots", 1), "alvo_c": g("ShotsOnTarget", 0),
            "alvo_f": g("ShotsOnTarget", 1), "gch_c": g("big_chance", 0), "gch_f": g("big_chance", 1),
            "area_c": g("touches_opp_box", 0), "area_f": g("touches_opp_box", 1),
            "posse_c": g("BallPossesion", 0), "posse_f": g("BallPossesion", 1),
            "verm_c": g("red_cards", 0), "verm_f": g("red_cards", 1),
            "gramado": est.get("surface", ""), "estadio": est.get("name", ""), "lat": est.get("lat", ""),
            "lon": est.get("long", ""), "arbitro": arb.get("text", ""), "arbitro_id": arb.get("id", ""),
            "publico": (info.get("Attendance") or "")}


def main():
    a = sys.argv
    ligas = [int(x) for x in a[a.index("--ligas") + 1].split(",")] if "--ligas" in a else list(LIGAS)
    temps = a[a.index("--temporadas") + 1].split(",") if "--temporadas" in a else None
    mx = int(a[a.index("--max") + 1]) if "--max" in a else 10 ** 9
    feitos = set()
    if os.path.exists(SAIDA):
        feitos = {r["match_id"] for r in csv.DictReader(open(SAIDA, encoding="utf-8"))}
    novo = not os.path.exists(SAIDA)
    f = open(SAIDA, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=CAMPOS)
    if novo:
        w.writeheader()
    fila = []
    for lid in ligas:
        base = get(f"{API}/leagues", {"id": lid})
        if not base:
            print("liga sem resposta", lid)
            continue
        disp = base.get("allAvailableSeasons", [])
        alvo = [s for s in disp if (temps is None and (s[:4] >= "2021")) or (temps and any(s.startswith(t) for t in temps))]
        for s in alvo:
            d = base if s == disp[0] else get(f"{API}/leagues", {"id": lid, "season": s})
            if not d:
                continue
            for m in (d.get("fixtures") or {}).get("allMatches", []):
                stt = m.get("status") or {}
                if not stt.get("finished") or stt.get("cancelled") or str(m["id"]) in feitos:
                    continue
                try:
                    gc, gf = [int(x) for x in stt.get("scoreStr", "").replace(" ", "").split("-")[:2]]
                except Exception:
                    continue
                fila.append({"match_id": str(m["id"]), "liga_id": lid, "liga": LIGAS.get(lid, ""), "temporada": s,
                             "rodada": m.get("round", ""), "data_utc": stt.get("utcTime", ""),
                             "casa_id": m["home"]["id"], "casa": m["home"]["name"], "fora_id": m["away"]["id"],
                             "fora": m["away"]["name"], "gc": gc, "gf": gf})
            time.sleep(0.5)
    fila = fila[:mx]
    print(f"jogos a coletar: {len(fila)}", flush=True)
    n = [0]

    def um(base):
        det = detalhe(base["match_id"])
        time.sleep(0.25)
        if det is None:
            return
        base.update(det)
        with trava:
            w.writerow(base)
            n[0] += 1
            if n[0] % 200 == 0:
                f.flush()
                print(f"  {n[0]} de {len(fila)}", flush=True)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(um, fila))
    f.close()
    print(f"coletados {n[0]}")


if __name__ == "__main__":
    main()
