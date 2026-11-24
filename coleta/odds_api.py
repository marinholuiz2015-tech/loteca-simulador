"""
The Odds API — terceira fonte de odds (reserva da Arena e da bolsa do Guia).

Baixa as odds 1-X-2 (mercado h2h, regiao eu — inclui a Pinnacle) das ligas que aparecem na Loteca,
para os jogos dos proximos 6 dias, e acrescenta um retrato em coleta/dados/odds_api.csv.
O motor (motor/camada1.py) usa a Pinnacle quando houver, senao a media das casas, so para jogos em
que a Arena nao trouxe odd valida e a bolsa do Guia tambem nao.

Chave: segredo ODDS_API_KEY no GitHub (Settings > Secrets and variables > Actions). Sem chave, nao faz nada.
Custo: 1 credito por liga por execucao (plano gratis: 500 por mes).
"""
import csv
import datetime
import os
import sys

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "dados", "odds_api.csv")
API = "https://api.the-odds-api.com/v4"
LIGAS = ("brazil", "epl", "efl_champ", "spain", "italy", "germany", "france", "portugal", "netherlands",
         "argentina", "conmebol", "uefa_champs", "uefa_europa", "fifa_world_cup")
CAMPOS = ["coletado_em_utc", "liga", "inicio_utc", "mandante", "visitante", "casa", "odd_1", "odd_x", "odd_2"]


def main():
    chave = os.environ.get("ODDS_API_KEY", "").strip()
    if not chave:
        print("The Odds API: sem ODDS_API_KEY, nada a fazer")
        return 0
    r = requests.get(f"{API}/sports", params={"apiKey": chave}, timeout=30)
    if r.status_code != 200:
        print("The Odds API: erro ao listar ligas", r.status_code, r.text[:200])
        return 0
    ligas = [s["key"] for s in r.json() if s.get("group") == "Soccer" and s.get("active")
             and any(t in s["key"] for t in LIGAS) and not s.get("has_outrights")]
    agora = datetime.datetime.now(datetime.timezone.utc)
    ate = (agora + datetime.timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    carimbo = agora.strftime("%Y-%m-%dT%H:%M:%SZ")
    linhas, resto = [], None
    for liga in ligas:
        q = requests.get(f"{API}/sports/{liga}/odds", timeout=30,
                         params={"apiKey": chave, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal",
                                 "commenceTimeTo": ate})
        resto = q.headers.get("x-requests-remaining", resto)
        if q.status_code != 200:
            print(liga, "erro", q.status_code)
            continue
        for ev in q.json():
            for bk in ev.get("bookmakers", []):
                mk = next((m for m in bk.get("markets", []) if m["key"] == "h2h"), None)
                if not mk:
                    continue
                pr = {o["name"]: o["price"] for o in mk["outcomes"]}
                if ev["home_team"] in pr and ev["away_team"] in pr and "Draw" in pr:
                    linhas.append({"coletado_em_utc": carimbo, "liga": liga, "inicio_utc": ev["commence_time"],
                                   "mandante": ev["home_team"], "visitante": ev["away_team"], "casa": bk["key"],
                                   "odd_1": pr[ev["home_team"]], "odd_x": pr["Draw"], "odd_2": pr[ev["away_team"]]})
    novo = not os.path.exists(SAIDA)
    with open(SAIDA, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        w.writerows(linhas)
    print(f"The Odds API: {len(ligas)} ligas, {len(linhas)} linhas (jogo x casa); creditos restantes: {resto}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
