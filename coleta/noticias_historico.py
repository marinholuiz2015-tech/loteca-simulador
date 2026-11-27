"""
Historico de noticias dos jogos da Loteca, para medir a camada de noticias contra as odds.

Para cada jogo de cada concurso, busca no Google Noticias as manchetes de cada time
publicadas nos 7 dias ANTERIORES ao jogo, parando na vespera (o dia do jogo fica de fora,
porque ali ja aparecem cronicas com o resultado). Grava as manchetes e os sinais
(desfalque, reservas, crise, tecnico, reforco) de cada lado.

Saidas (coleta/dados):
  noticias_hist_manchetes.csv  concurso, jogo, lado, time, data, titulo
  noticias_hist_sinais.csv     concurso, jogo, lado, time, data_jogo, manchetes, reservas, desfalque, crise, tecnico, reforco

Uso: python coleta/noticias_historico.py 1180 1284
"""
import concurrent.futures as cf
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "sentinela"))
import noticias as N  # noqa: E402

REPO = os.path.dirname(AQUI)
DADOS = os.path.join(AQUI, "dados")
ARQ_M = os.path.join(DADOS, "noticias_hist_manchetes.csv")
ARQ_S = os.path.join(DADOS, "noticias_hist_sinais.csv")
CAMPOS_S = (["concurso", "jogo", "lado", "time", "data_jogo", "manchetes"] + list(N.SINAIS)
            + ["so_dele"] + [f"so_{k}" for k in N.SINAIS])
JANELA = 7


def feitos():
    if not os.path.exists(ARQ_S):
        return set()
    return {(int(r["concurso"]), int(r["jogo"]), r["lado"]) for r in csv.DictReader(open(ARQ_S, encoding="utf-8"))}


def nome_grade(j, lado):
    n = j["nomeEquipeUm" if lado == "1" else "nomeEquipeDois"]
    uf = j["siglaUFUm" if lado == "1" else "siglaUFDois"]
    return f"{n}-{uf}" if uf else n


def manchetes(nome, dia):
    """manchetes do time de (dia-7) ate a vespera de dia."""
    base = N.nome_busca(nome)
    ini = (dia - dt.timedelta(days=JANELA)).isoformat()
    q = urllib.parse.quote(f'"{base}" after:{ini} before:{dia.isoformat()}')
    itens = N.ler_rss(f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419")
    ks = N.chaves(base)
    vistos, out = set(), []
    for t, quando, _ in itens:
        if quando and quando.date() >= dia:  # seguranca extra: nada do dia do jogo
            continue
        st = N.sem_acento(t)
        if not any(k in st for k in ks):
            continue
        k = st[:80]
        if k in vistos:
            continue
        vistos.add(k)
        out.append({"titulo": t, "quando": quando.strftime("%Y-%m-%d") if quando else ""})
    return out


def tarefa(args):
    c, j, lado = args
    nome = nome_grade(j, lado)
    dia = dt.datetime.strptime(j["dtJogo"], "%d/%m/%Y").date()
    ms = manchetes(nome, dia)
    s = N.sinais(ms)
    # manchetes que falam so deste time (sem citar o adversario): as que separam os dois lados
    rival = N.chaves(N.nome_busca(nome_grade(j, "2" if lado == "1" else "1")))
    so = [m for m in ms if not any(k in N.sem_acento(m["titulo"]) for k in rival)]
    s_so = {f"so_{k}": v for k, v in N.sinais(so).items()}
    lin_s = {"concurso": c, "jogo": j["nuSequencial"], "lado": lado, "time": nome, "data_jogo": dia.isoformat(),
             "manchetes": len(ms), **s, "so_dele": len(so), **s_so}
    lin_m = [{"concurso": c, "jogo": j["nuSequencial"], "lado": lado, "time": nome, "data": m["quando"],
              "titulo": m["titulo"]} for m in ms]
    return lin_s, lin_m


def anexar(arq, campos, linhas):
    novo = not os.path.exists(arq)
    with open(arq, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if novo:
            w.writeheader()
        w.writerows(linhas)


def main():
    a, b = int(sys.argv[1]), int(sys.argv[2])
    H = json.load(open(os.path.join(REPO, "data", "historico_cef.json")))["concursos"]
    ja = feitos()
    fila = []
    for c in range(b, a - 1, -1):  # do mais recente para o mais antigo
        js = (H.get(str(c)) or {}).get("jogos") or []
        for j in js:
            if not j.get("dtJogo"):
                continue
            for lado in ("1", "2"):
                if (c, j["nuSequencial"], lado) not in ja:
                    fila.append((c, j, lado))
    print(f"{len(fila)} buscas a fazer")
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        lote_s, lote_m = [], []
        for i, (ls, lm) in enumerate(ex.map(tarefa, fila), 1):
            lote_s.append(ls)
            lote_m += lm
            if i % 50 == 0 or i == len(fila):
                anexar(ARQ_S, CAMPOS_S, lote_s)
                anexar(ARQ_M, ["concurso", "jogo", "lado", "time", "data", "titulo"], lote_m)
                lote_s, lote_m = [], []
                print(f"  {i}/{len(fila)} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
