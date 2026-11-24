"""
Chance de Gol (chancedegol.com.br) - probabilidades de cada jogo calculadas pelo modelo do site
(vitoria do mandante / empate / vitoria do visitante), publicadas ANTES do jogo.

E uma fonte independente das odds: modelo estatistico de terceiros, nao deriva da bet365.
Cobertura: Brasileirao A, B, C, D, Copa do Brasil, Libertadores, Sul-Americana (e Copa do Mundo).
Arquivo do site: so as temporadas 2025 e 2026 (anos anteriores dao 404).

Uso:
  python coleta/chancedegol.py            # baixa todas as paginas disponiveis e reescreve os CSVs
Saidas em coleta/dados/:
  chancedegol.csv         jogos ja realizados (com placar) + probabilidades
  chancedegol_aberto.csv  proximos jogos (sem placar) - retrato acumulado, nunca apaga linhas antigas
"""
import csv
import datetime
import os
import re
import sys
import time

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, "dados")
URL = "https://chancedegol.com.br/{}.htm"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CAMPEONATOS = {
    "br": "Brasileirao Serie A", "brb": "Brasileirao Serie B", "brc": "Brasileirao Serie C",
    "brd": "Brasileirao Serie D", "cbr": "Copa do Brasil", "lib": "Libertadores", "sul": "Sul-Americana",
    "ne": "Copa do Nordeste", "copa": "Copa do Mundo",
}
CAMPOS = ["campeonato", "pagina", "data", "mandante", "visitante", "gols_m", "gols_v", "p1", "px", "p2"]


def celulas(tr):
    out = []
    for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I):
        c = re.sub(r"<[^>]+>|&nbsp;", " ", c)
        out.append(re.sub(r"\s+", " ", c).strip())
    return out


def pct(c):
    m = re.fullmatch(r"(\d{1,3}(?:[.,]\d+)?)\s*%", c)
    return float(m.group(1).replace(",", ".")) if m else None


def ler_pagina(html, codigo, campeonato):
    feitos, proximos = [], []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cs = celulas(tr)
        if not cs or not re.fullmatch(r"\d{2}/\d{2}/\d{4}", cs[0]):
            continue
        ps = [pct(c) for c in cs]
        idx = [i for i, p in enumerate(ps) if p is not None]
        if len(idx) != 3 or abs(sum(ps[i] for i in idx) - 100) > 1.5:
            continue  # linha com defeito (falta porcentagem ou nao soma 100)
        p1, px, p2 = (ps[i] for i in idx)
        texto = cs[1:idx[0]]
        placar = next((i for i, c in enumerate(texto) if re.fullmatch(r"\d+\s*x\s*\d+", c)), None)
        lin = {"campeonato": campeonato, "pagina": codigo, "data": cs[0], "p1": p1, "px": px, "p2": p2}
        if placar is not None and placar > 0 and placar + 1 < len(texto):
            gm, gv = re.findall(r"\d+", texto[placar])
            lin.update(mandante=texto[placar - 1], visitante=texto[placar + 1], gols_m=gm, gols_v=gv)
            feitos.append(lin)
        else:
            nomes = [c for c in texto if c and c.lower() != "x"]
            if len(nomes) >= 2:
                lin.update(mandante=nomes[0], visitante=nomes[-1], gols_m="", gols_v="")
                proximos.append(lin)
    return feitos, proximos


def paginas():
    ano = datetime.date.today().year
    anos = sorted({ano % 100, (ano - 1) % 100, 25, 26})
    return [f"{c}{a:02d}" for a in anos for c in CAMPEONATOS]


def main():
    os.makedirs(DADOS, exist_ok=True)
    feitos, proximos, resumo = [], [], []
    for cod in paginas():
        try:
            r = requests.get(URL.format(cod), headers=UA, timeout=30)
        except Exception as e:
            print(cod, "erro", e)
            continue
        if r.status_code != 200 or len(r.content) < 1000:
            continue
        r.encoding = r.encoding or "utf-8"
        f, p = ler_pagina(r.text, cod, CAMPEONATOS[re.sub(r"\d", "", cod)])
        feitos += f
        proximos += p
        resumo.append((cod, len(f), len(p)))
        time.sleep(1)
    vistos, unicos = set(), []
    for lin in feitos:
        k = (lin["data"], lin["mandante"], lin["visitante"])
        if k not in vistos:
            vistos.add(k)
            unicos.append(lin)
    with open(os.path.join(DADOS, "chancedegol.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(unicos)
    # proximos jogos: acumula retratos (a probabilidade de antes do jogo nao pode se perder)
    caminho = os.path.join(DADOS, "chancedegol_aberto.csv")
    antigos = list(csv.DictReader(open(caminho, encoding="utf-8"))) if os.path.exists(caminho) else []
    hoje = datetime.date.today().isoformat()
    ja = {(a["retrato"], a["data"], a["mandante"], a["visitante"]) for a in antigos}
    novos = [dict(lin, retrato=hoje) for lin in proximos if (hoje, lin["data"], lin["mandante"], lin["visitante"]) not in ja]
    with open(caminho, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["retrato"] + CAMPOS)
        w.writeheader()
        w.writerows(antigos + novos)
    for cod, nf, np_ in resumo:
        print(f"{cod}: {nf} realizados, {np_} proximos")
    print(f"Total: {len(unicos)} jogos realizados; {len(novos)} proximos gravados hoje")
    return 0 if unicos else 1


if __name__ == "__main__":
    sys.exit(main())
