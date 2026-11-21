"""
Retrato semanal da pagina de palpites do Guia da Loteria.
https://www.guiadaloteria.com.br/blog/loteca/palpites

A pagina e reescrita a cada concurso e nao guarda historico, por isso o
retrato precisa ser tirado toda semana (quinta e sabado de manha, antes do
fechamento das 15h). Cada retrato vira linhas em
coleta/dados/guia_loteria.csv:

concurso, jogo, mandante, visitante, prob_1, prob_x, prob_2,
odd_1, odd_x, odd_2, palpite, tipo, coletado_em_utc

prob_*: probabilidade de mercado da bolsa esportiva, sem margem (fair odds).
O mesmo concurso pode aparecer em varios retratos (quinta e sabado): isso e
proposital, mostra o movimento das odds ate o fechamento.
"""
import csv
import html
import os
import re
import sys
from datetime import datetime, timezone

import requests

URL = "https://www.guiadaloteria.com.br/blog/loteca/palpites"
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
SAIDA = os.path.join(PASTA, "guia_loteria.csv")
CAMPOS = ["concurso", "jogo", "mandante", "visitante", "prob_1", "prob_x", "prob_2",
          "odd_1", "odd_x", "odd_2", "palpite", "tipo", "coletado_em_utc"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36"}


def _num(s):
    return float(s.replace(",", ".").replace("%", "").strip())


def ler_pagina(texto):
    m = re.search(r"Loteca\s+(\d{3,4})\s*:\s*Palpites", texto)
    if not m:
        raise ValueError("numero do concurso nao encontrado na pagina")
    concurso = int(m.group(1))
    tabela = re.search(r"<table.*?</table>", texto, re.S)
    if not tabela:
        raise ValueError("tabela de palpites nao encontrada")
    linhas = []
    for tr in re.findall(r"<tr.*?</tr>", tabela.group(0), re.S):
        cel = [html.unescape(re.sub(r"<[^>]+>", " ", c)).strip()
               for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        cel = [re.sub(r"\s+", " ", c) for c in cel]
        if not cel or not cel[0].isdigit():
            continue
        jogo = int(cel[0])
        resto = " | ".join(cel[1:])
        conf = re.match(r"(.+?)\s+x\s+(.+?)\s*\|", cel[1] + " |")
        if conf:
            mand, vis = conf.group(1), conf.group(2)
        else:
            mand, vis = cel[1], cel[3] if len(cel) > 3 else ""
            if mand.lower() == "x":
                mand = ""
        probs = re.findall(r"(\d{1,3})%", resto)
        odds = re.findall(r"(\d+,\d+)\s*/\s*(\d+,\d+)\s*/\s*(\d+,\d+)", resto)
        palp = re.search(r"\b(1X|X2|12|1|X|2)\s+(Seco|Duplo|Triplo)\b", resto, re.I)
        if len(probs) < 3 or not odds:
            continue
        linhas.append(dict(
            concurso=concurso, jogo=jogo, mandante=mand, visitante=vis,
            prob_1=_num(probs[0]) / 100, prob_x=_num(probs[1]) / 100, prob_2=_num(probs[2]) / 100,
            odd_1=_num(odds[0][0]), odd_x=_num(odds[0][1]), odd_2=_num(odds[0][2]),
            palpite=palp.group(1).upper() if palp else "",
            tipo=palp.group(2).capitalize() if palp else ""))
    return concurso, linhas


def main():
    r = requests.get(URL, headers=UA, timeout=40)
    r.raise_for_status()
    concurso, linhas = ler_pagina(r.text)
    if len(linhas) != 14:
        print(f"ATENCAO: esperava 14 jogos, li {len(linhas)} (concurso {concurso})")
        if not linhas:
            sys.exit(1)
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for l in linhas:
        l["coletado_em_utc"] = agora
        soma = l["prob_1"] + l["prob_x"] + l["prob_2"]
        if not 0.97 <= soma <= 1.03:
            print(f"ATENCAO: jogo {l['jogo']} com probabilidades somando {soma:.2f}")
    os.makedirs(PASTA, exist_ok=True)
    novo = not os.path.exists(SAIDA)
    with open(SAIDA, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        w.writerows(linhas)
    print(f"Guia da Loteria: concurso {concurso}, {len(linhas)} jogos gravados em {SAIDA}")


if __name__ == "__main__":
    main()
