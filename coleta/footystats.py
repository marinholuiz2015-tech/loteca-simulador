"""
FootyStats (API gratuita) - Premier League, todas as temporadas liberadas no plano gratis (2018/19 em diante).
Usa a chave publica de teste "example" (sem cadastro). Se houver o segredo FOOTYSTATS_KEY no GitHub,
usa a chave dele (plano pago libera mais ligas, inclusive as brasileiras).

Por jogo grava: odds 1-X-2 de abertura, xG real, xG PREVISTO antes do jogo (modelo do FootyStats),
pontos por jogo antes da partida.
Saida: coleta/dados/footystats.csv
"""
import csv
import datetime
import os
import sys
import time

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "dados", "footystats.csv")
API = "https://api.football-data-api.com/{}"
CHAVE = os.environ.get("FOOTYSTATS_KEY") or "example"
CAMPOS = ["liga", "temporada", "data", "mandante", "visitante", "gols_m", "gols_v", "odd_1", "odd_x", "odd_2",
          "xg_m", "xg_v", "xg_prev_m", "xg_prev_v", "ppg_prev_m", "ppg_prev_v", "ppg_prev_geral_m", "ppg_prev_geral_v"]


def get(rota, **p):
    for _ in range(3):
        try:
            r = requests.get(API.format(rota), params=dict(p, key=CHAVE), timeout=60)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(5)
    return {}


def main():
    ligas = get("league-list", chosen_leagues_only="true").get("data") or []
    linhas = []
    for liga in ligas:
        for temp in liga.get("season", []):
            pag, maxp = 1, 1
            while pag <= maxp:
                d = get("league-matches", season_id=temp["id"], page=pag)
                maxp = (d.get("pager") or {}).get("max_page", 1)
                for m in d.get("data") or []:
                    if m.get("status") != "complete":
                        continue
                    linhas.append({
                        "liga": liga["name"], "temporada": temp["year"],
                        "data": datetime.datetime.utcfromtimestamp(m["date_unix"]).strftime("%d/%m/%Y"),
                        "mandante": m["home_name"], "visitante": m["away_name"],
                        "gols_m": m["homeGoalCount"], "gols_v": m["awayGoalCount"],
                        "odd_1": m.get("odds_ft_1"), "odd_x": m.get("odds_ft_x"), "odd_2": m.get("odds_ft_2"),
                        "xg_m": m.get("team_a_xg"), "xg_v": m.get("team_b_xg"),
                        "xg_prev_m": m.get("team_a_xg_prematch"), "xg_prev_v": m.get("team_b_xg_prematch"),
                        "ppg_prev_m": m.get("pre_match_home_ppg"), "ppg_prev_v": m.get("pre_match_away_ppg"),
                        "ppg_prev_geral_m": m.get("pre_match_teamA_overall_ppg"),
                        "ppg_prev_geral_v": m.get("pre_match_teamB_overall_ppg"),
                    })
                pag += 1
                time.sleep(1)
            print(liga["name"], temp["year"], "ok")
    if not linhas:
        print("FootyStats: nada baixado")
        return 1
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(linhas)
    print(f"FootyStats: {len(linhas)} jogos gravados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
