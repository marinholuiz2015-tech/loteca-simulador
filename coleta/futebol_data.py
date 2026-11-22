"""
football-data.co.uk: resultados e odds (abertura e FECHAMENTO: Pinnacle, Betfair, bet365,
media das casas) do Brasileirao Serie A e das principais ligas europeias.

Salva os CSVs em coleta/dados/fd/ (fora do git; baixados de novo quando preciso).
  historico: temporadas 2018/19 em diante (base dos testes)
  semanal:   so a temporada atual (tabela ao vivo da reta final)
Uso: python coleta/futebol_data.py [historico|semanal]
"""
import datetime
import os
import sys
import time

import requests

DESTINO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "fd")
BASE = "https://football-data.co.uk"
NOVAS = ["BRA", "ARG", "MEX", "USA"]
LIGAS = ["E0", "E1", "E2", "SC0", "SP1", "SP2", "I1", "I2", "D1", "D2", "F1", "F2", "P1", "N1", "B1", "T1"]
HEAD = {"User-Agent": "Mozilla/5.0 (pesquisa pessoal; coleta leve)"}


def temporada_atual(hoje=None):
    hoje = hoje or datetime.date.today()
    a = hoje.year % 100 if hoje.month >= 7 else hoje.year % 100 - 1
    return f"{a:02d}{a + 1:02d}"


def baixar(url, arq):
    try:
        r = requests.get(url, headers=HEAD, timeout=60)
    except Exception:
        return False
    if r.status_code != 200 or b"," not in r.content[:200]:
        return False
    with open(arq, "wb") as f:
        f.write(r.content)
    return True


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "semanal"
    os.makedirs(DESTINO, exist_ok=True)
    atual = temporada_atual()
    temporadas = [atual] if modo == "semanal" else \
        [f"{a:02d}{a + 1:02d}" for a in range(18, int(atual[:2]) + 1)]
    ok = falhas = 0
    for n in NOVAS:
        ok_ = baixar(f"{BASE}/new/{n}.csv", os.path.join(DESTINO, f"new_{n}.csv"))
        ok, falhas = ok + ok_, falhas + (not ok_)
        time.sleep(0.3)
    for t in temporadas:
        for l in LIGAS:
            arq = os.path.join(DESTINO, f"{t}_{l}.csv")
            if t != atual and os.path.exists(arq):
                continue  # temporada encerrada nao muda
            ok_ = baixar(f"{BASE}/mmz4281/{t}/{l}.csv", arq)
            ok, falhas = ok + ok_, falhas + (not ok_)
            time.sleep(0.2)
    print(f"football-data: {ok} arquivos atualizados, {falhas} indisponiveis (temporada atual {atual})")


if __name__ == "__main__":
    main()
