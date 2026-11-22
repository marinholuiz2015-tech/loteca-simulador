"""
Noticias de semanas passadas, para medir os KPIs de noticias nos jogos que ja temos.

Para cada jogo da base de odds (com data), busca no Google Noticias as manchetes
de cada time nos 7 dias ANTERIORES ao jogo (ate a vespera: nada do dia do jogo,
para nao pegar o resultado). Marca os mesmos sinais da coleta semanal
(desfalque, reservas, crise, tecnico, retorno).

Uso: PARTES=4 PARTE=0 python coleta/sentinela/noticias_historico.py [concurso_inicial]
Saida: coleta/dados/noticias_historico.csv (ou _pN.csv por parte; acrescenta, retoma de onde parou).
"""
import csv
import datetime as dt
import os
import sys
import time
import urllib.parse

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from noticias import SINAIS, ler_rss, nome_busca, sem_acento, sinais  # noqa: E402

REPO = os.path.dirname(os.path.dirname(AQUI))
DADOS = os.path.join(REPO, "coleta", "dados")
TERMOS = ("lesao OR lesionado OR desfalque OR suspenso OR vetado OR poupar OR reservas OR \"time alternativo\" OR "
          "crise OR \"salarios atrasados\" OR protesto OR demitido OR interino OR \"novo tecnico\" OR retorno OR volta")


def manchetes(time_nome, data_jogo):
    base = nome_busca(time_nome).replace(" Bergamas", "")
    ini = (data_jogo - dt.timedelta(days=7)).isoformat()
    fim = data_jogo.isoformat()  # before: exclui o dia do jogo
    q = urllib.parse.quote(f'"{base}" ({TERMOS}) after:{ini} before:{fim}')
    itens = ler_rss(f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419")
    chave = sem_acento(base).split()[0] if base else ""
    out, vistos = [], set()
    for t, quando, _ in itens:
        if chave and chave not in sem_acento(t):
            continue
        if quando and quando.date() >= data_jogo:
            continue
        k = sem_acento(t)[:80]
        if k not in vistos:
            vistos.add(k)
            out.append({"titulo": t})
    return out


def main():
    partes, parte = int(os.environ.get("PARTES", "1")), int(os.environ.get("PARTE", "0"))
    inicio = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    arq = os.path.join(DADOS, "noticias_historico.csv" if partes == 1 else f"noticias_historico_p{parte}.csv")
    campos = ["concurso", "jogo", "mandante", "visitante"] + \
             [f"{lado}_{k}" for lado in ("casa", "fora") for k in list(SINAIS) + ["n"]] + ["data_jogo"]
    feitos = set()
    if os.path.exists(arq):
        with open(arq, encoding="utf-8") as f:
            feitos = {(r["concurso"], r["jogo"]) for r in csv.DictReader(f)}
    jogos = []
    with open(os.path.join(DADOS, "arena_odds.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["data_jogo"] and r["resultado"] and int(r["concurso"]) >= inicio
                    and (r["concurso"], r["jogo"]) not in feitos and int(r["concurso"]) % partes == parte):
                jogos.append(r)
    novo = not os.path.exists(arq)
    with open(arq, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if novo:
            w.writeheader()
        for i, r in enumerate(jogos, 1):
            d = dt.datetime.strptime(r["data_jogo"], "%d/%m/%Y").date()
            mc, mv = manchetes(r["mandante"], d), manchetes(r["visitante"], d)
            sc, sv = sinais(mc), sinais(mv)
            linha = {"concurso": r["concurso"], "jogo": r["jogo"], "mandante": r["mandante"],
                     "visitante": r["visitante"], "data_jogo": r["data_jogo"]}
            for lado, s_, m in (("casa", sc, mc), ("fora", sv, mv)):
                for k, v in s_.items():
                    linha[f"{lado}_{k}"] = v
                linha[f"{lado}_n"] = len(m)
            w.writerow(linha)
            f.flush()
            if i % 50 == 0:
                print(f"{i}/{len(jogos)}", flush=True)
            time.sleep(float(os.environ.get("PAUSA", "0.5")))
    print("Fim", len(jogos))


if __name__ == "__main__":
    main()
