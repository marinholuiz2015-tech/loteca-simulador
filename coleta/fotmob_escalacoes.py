"""
Escalacoes titulares (FotMob) dos jogos de fotmob_jogos.csv: para medir desfalque/time poupado,
cansaco de cada jogador e jogador fora de forma.

Saida: coleta/dados/fotmob_escalacoes.csv - uma linha por jogador titular:
  match_id, data_utc, lado, time_id, tecnico, formacao, jogador_id, jogador, posicao, valor, nota, idade
Retoma de onde parou. Uso: python coleta/fotmob_escalacoes.py --ligas 268,8814,8971 --desde 2023
"""
import argparse
import csv
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOGOS = os.path.join(RAIZ, "coleta", "dados", "fotmob_jogos.csv")
SAIDA = os.path.join(RAIZ, "coleta", "dados", "fotmob_escalacoes.csv")
API = "https://www.fotmob.com/api/data/matchDetails"
HEAD = {"User-Agent": "Mozilla/5.0 (estudo pessoal; consulta leve)"}
CAMPOS = ["match_id", "data_utc", "lado", "time_id", "tecnico", "formacao", "jogador_id", "jogador", "posicao",
          "valor", "nota", "idade"]
trava = threading.Lock()


def um(r):
    try:
        d = requests.get(API, params={"matchId": r["match_id"]}, headers=HEAD, timeout=30).json()
        lu = d["content"]["lineup"] or {}
    except Exception:
        return []
    out = []
    for lado, k in (("1", "homeTeam"), ("2", "awayTeam")):
        t = lu.get(k) or {}
        tec = (t.get("coach") or {}).get("name", "") if isinstance(t.get("coach"), dict) else ""
        for p in t.get("starters") or []:
            out.append({"match_id": r["match_id"], "data_utc": r["data_utc"], "lado": lado, "time_id": t.get("id"),
                        "tecnico": tec, "formacao": t.get("formation", ""), "jogador_id": p.get("id"),
                        "jogador": p.get("name"), "posicao": p.get("usualPlayingPositionId", p.get("positionId")),
                        "valor": p.get("marketValue") or "", "nota": (p.get("performance") or {}).get("rating") or "",
                        "idade": p.get("age") or ""})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ligas", default="268,8814,8971")
    ap.add_argument("--desde", type=int, default=2023)
    a = ap.parse_args()
    ligas = set(a.ligas.split(","))
    feitos = set()
    if os.path.exists(SAIDA):
        feitos = {r["match_id"] for r in csv.DictReader(open(SAIDA, encoding="utf-8"))}
    fila = [r for r in csv.DictReader(open(JOGOS, encoding="utf-8"))
            if r["liga_id"] in ligas and int(r["data_utc"][:4]) >= a.desde and r["match_id"] not in feitos]
    print(f"{len(fila)} jogos para buscar", flush=True)
    novo = not os.path.exists(SAIDA)
    with open(SAIDA, "a", newline="", encoding="utf-8") as f, ThreadPoolExecutor(4) as ex:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        for i, linhas in enumerate(ex.map(um, fila), 1):
            with trava:
                w.writerows(linhas)
            if i % 200 == 0:
                f.flush(); print(f"  {i}/{len(fila)}", flush=True)


if __name__ == "__main__":
    main()
