"""
Resultados oficiais da Loteca (API publica da Caixa) para os concursos que
aparecem nos palpites coletados (coleta/dados/lotequeiros_palpites.csv).

Grava coleta/dados/resultados_caixa.csv:
concurso, jogo, mandante, visitante, gols_m, gols_v, resultado (1/X/2),
data_jogo, sorteio (1 = resultado definido por sorteio).

Incremental: so baixa concursos que ainda nao estao no CSV. Concurso ainda
sem resultado (jogos nao terminados) e ignorado e tentado de novo na
proxima rodada.
"""
import csv
import os
import time

import requests

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
SAIDA = os.path.join(PASTA, "resultados_caixa.csv")
PALPITES = os.path.join(PASTA, "lotequeiros_palpites.csv")
API = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca/{}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://loterias.caixa.gov.br/Paginas/Programacao-Loteca.aspx",
    "Origin": "https://loterias.caixa.gov.br",
}
CAMPOS = ["concurso", "jogo", "mandante", "visitante", "gols_m", "gols_v",
          "resultado", "data_jogo", "sorteio"]


def pedir(n):
    for i in range(3):
        try:
            r = requests.get(API.format(n), headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            print(f"  concurso {n}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  concurso {n}: erro {e}")
        time.sleep(3 * (i + 1))
    return None


def linhas_do_concurso(d):
    out = []
    for j in d.get("listaResultadoEquipeEsportiva") or []:
        gm, gv = j.get("nuGolEquipeUm"), j.get("nuGolEquipeDois")
        if gm is None or gv is None:
            return []  # concurso ainda em andamento
        res = "1" if gm > gv else ("2" if gv > gm else "X")
        out.append(dict(concurso=d["numero"], jogo=j["nuSequencial"],
                        mandante=j["nomeEquipeUm"], visitante=j["nomeEquipeDois"],
                        gols_m=gm, gols_v=gv, resultado=res,
                        data_jogo=j.get("dtJogo", ""),
                        sorteio=j.get("icSorteioResultado", 0) or 0))
    return out


def main():
    with open(PALPITES, encoding="utf-8") as f:
        alvo = {int(r["concurso"]) for r in csv.DictReader(f) if int(r["concurso"]) >= 700}
    linhas = []
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
    ja = {int(r["concurso"]) for r in linhas}
    falta = sorted(alvo - ja)
    print(f"Concursos com palpite: {len(alvo)} | com resultado: {len(ja & alvo)} | a buscar: {len(falta)}")
    novos = 0
    for n in falta:
        d = pedir(n)
        if d:
            l = linhas_do_concurso(d)
            if l:
                linhas.extend(l)
                novos += 1
        time.sleep(0.4)
    linhas.sort(key=lambda r: (int(r["concurso"]), int(r["jogo"])))
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(linhas)
    print(f"Concursos novos com resultado: {novos} -> {SAIDA}")


if __name__ == "__main__":
    main()
