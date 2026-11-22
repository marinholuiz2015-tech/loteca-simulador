"""
Placar ao vivo do concurso aberto (FotMob), para o painel oficial.

Le os jogos do concurso aberto (coleta/dados/sentinela_aberto.csv: match_id de cada jogo) e grava
docs/dados/ao_vivo.json com placar, situacao e o resultado provisorio (1, X ou 2), mais os pontos que
cada jogo nosso faz na hora. So consulta quando ha jogo na janela (15 min antes do inicio ate 3h depois),
para nao pesar. Uso: python coleta/ao_vivo.py [--forcar]
"""
import csv
import datetime
import json
import os
import sys
import time

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ABERTO = os.path.join(RAIZ, "coleta", "dados", "sentinela_aberto.csv")
SAIDA = os.path.join(RAIZ, "docs", "dados", "ao_vivo.json")
FOT = "https://www.fotmob.com/api/data"
HEAD = {"User-Agent": "Mozilla/5.0 (painel pessoal; consulta leve)"}


def jogos_abertos():
    linhas = list(csv.DictReader(open(ABERTO, encoding="utf-8")))
    if not linhas:
        return None, {}
    c = max(int(r["concurso"]) for r in linhas)
    js = {}
    for r in linhas:  # o arquivo acumula coletas; fica a mais recente de cada jogo
        if int(r["concurso"]) == c and r.get("match_id"):
            js[int(r["jogo"])] = r
    return c, js


def na_janela(js, agora):
    for r in js.values():
        try:
            ini = datetime.datetime.strptime(r["inicio_utc"], "%Y-%m-%dT%H:%MZ")
        except Exception:
            continue
        if ini - datetime.timedelta(minutes=15) <= agora <= ini + datetime.timedelta(hours=3):
            return True
    return False


def main():
    forcar = "--forcar" in sys.argv
    c, js = jogos_abertos()
    if not c:
        return
    agora = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    anterior = json.load(open(SAIDA)) if os.path.exists(SAIDA) else {}
    if not forcar and anterior.get("concurso") == c and not na_janela(js, agora):
        print("ao vivo: nenhum jogo na janela agora")
        return
    out = {"concurso": c, "atualizado_utc": agora.strftime("%Y-%m-%dT%H:%MZ"), "jogos": []}
    for j in sorted(js):
        r = js[j]
        g = {"jogo": j, "mandante": r["mandante"], "visitante": r["visitante"], "inicio_utc": r["inicio_utc"],
             "situacao": "não começou", "placar": None, "resultado": None}
        try:
            d = requests.get(f"{FOT}/matchDetails?matchId={r['match_id']}", headers=HEAD, timeout=30).json()
            st = d.get("header", {}).get("status", {})
            tm = d.get("header", {}).get("teams", [])
            if st.get("started") and len(tm) == 2:
                gc, gf = tm[0].get("score"), tm[1].get("score")
                g["placar"] = [gc, gf]
                g["resultado"] = "1" if gc > gf else ("X" if gc == gf else "2")
                g["situacao"] = "encerrado" if st.get("finished") else \
                    ("ao vivo " + "".join(ch for ch in str((st.get("liveTime") or {}).get("short") or "") if ch.isprintable() and ch not in "\u200e\u200f")).strip()
            if st.get("cancelled"):
                g["situacao"] = "cancelado"
        except Exception as e:
            g["situacao"] = "sem dados agora"
        out["jogos"].append(g)
        time.sleep(0.4)
    json.dump(out, open(SAIDA, "w"), ensure_ascii=False, indent=1)
    print(f"ao vivo: concurso {c}, {sum(g['situacao'] == 'encerrado' for g in out['jogos'])} encerrados, "
          f"{sum(g['situacao'].startswith('ao vivo') for g in out['jogos'])} em andamento")


if __name__ == "__main__":
    main()
