"""
Rateio oficial de cada concurso da Loteca (API publica da Caixa).

Grava coleta/dados/rateio_caixa.csv, uma linha por concurso:
  ganhadores e premio de 14 e de 13, premio total em jogo (pool) de cada faixa,
  arrecadacao, acumulado e estimativa para o proximo concurso.
Incremental: acrescenta os concursos encerrados que ainda nao estao no arquivo.
Semente opcional: python coleta/rateio_caixa.py --semente arquivo.jsonl (respostas brutas da API).
"""
import csv
import json
import os
import sys
import time

import requests

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
SAIDA = os.path.join(PASTA, "rateio_caixa.csv")
API = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca/{}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36",
           "Accept": "application/json, text/plain, */*",
           "Referer": "https://loterias.caixa.gov.br/Paginas/Programacao-Loteca.aspx",
           "Origin": "https://loterias.caixa.gov.br"}
CAMPOS = ["concurso", "data", "ganhadores_14", "premio_14", "ganhadores_13", "premio_13", "pool_14", "pool_13",
          "arrecadacao", "acumulado_proximo", "estimado_proximo"]


def linha(d):
    fx = {r["faixa"]: r for r in d.get("listaRateioPremio") or []}
    if 1 not in fx or 2 not in fx:
        return None
    g14, v14 = fx[1]["numeroDeGanhadores"], fx[1]["valorPremio"]
    g13, v13 = fx[2]["numeroDeGanhadores"], fx[2]["valorPremio"]
    pool14 = g14 * v14 if g14 else (d.get("valorAcumuladoProximoConcurso") or 0)
    return {"concurso": d["numero"], "data": d.get("dataApuracao", ""), "ganhadores_14": g14, "premio_14": v14,
            "ganhadores_13": g13, "premio_13": v13, "pool_14": round(pool14, 2), "pool_13": round(g13 * v13, 2),
            "arrecadacao": d.get("valorArrecadado") or 0, "acumulado_proximo": d.get("valorAcumuladoProximoConcurso") or 0,
            "estimado_proximo": d.get("valorEstimadoProximoConcurso") or 0}


def ler():
    if not os.path.exists(SAIDA):
        return {}
    with open(SAIDA, encoding="utf-8") as f:
        return {int(r["concurso"]): r for r in csv.DictReader(f)}


def gravar(dados):
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for c in sorted(dados):
            w.writerow(dados[c])


def pedir(n):
    for t in range(3):
        try:
            r = requests.get(API.format(n if n else ""), headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (404, 500):
                return None
        except Exception:
            time.sleep(3 * (t + 1))
    return None


def main():
    dados = ler()
    if len(sys.argv) > 2 and sys.argv[1] == "--semente":
        with open(sys.argv[2], encoding="utf-8") as f:
            for l in f:
                try:
                    li = linha(json.loads(l))
                except (ValueError, KeyError):
                    li = None
                if li:
                    dados[li["concurso"]] = li
        gravar(dados)
        print(f"Semente: {len(dados)} concursos")
        return
    ultimo = pedir(None)
    fim = (ultimo or {}).get("numero") or (max(dados) + 1 if dados else 0)
    ini = max(dados) + 1 if dados else max(fim - 30, 1)
    # tambem preenche buracos no meio da serie (antes so pegava concursos depois do ultimo salvo)
    buracos = [n for n in range(min(dados), ini) if n not in dados] if dados else []
    novos = 0
    for n in buracos + list(range(ini, fim + 1)):
        d = ultimo if ultimo and ultimo.get("numero") == n else pedir(n)
        li = linha(d) if d else None
        if li:
            dados[n] = li
            novos += 1
        time.sleep(0.5)
    gravar(dados)
    print(f"Rateio: {novos} concursos novos, {len(dados)} no total")


if __name__ == "__main__":
    main()
