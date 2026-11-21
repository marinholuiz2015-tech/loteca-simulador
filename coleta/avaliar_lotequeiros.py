"""
Cruza lotequeiros_palpites.csv com resultados_caixa.csv e mede a
assertividade do Lotequeiros. So entram jogos em que os nomes dos times
do blog batem com os da Caixa (evita casar o jogo errado). Jogos decididos
por sorteio ficam de fora.
Gera lotequeiros_x_caixa.csv (base casada) e imprime o resumo.
"""
import csv
import difflib
import os
import re
import unicodedata
from collections import defaultdict

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")

APELIDOS = {
    "ATH": "ATHLETICO", "ATHLETICOPR": "ATHLETICO", "CAP": "ATHLETICO",
    "ATLMG": "ATLETICOMG", "GALO": "ATLETICOMG", "ATLGO": "ATLETICOGO",
    "MANUNITED": "MANCHESTERUNITED", "MANCITY": "MANCHESTERCITY",
    "MANCHESTERU": "MANCHESTERUNITED", "MANCHESTERC": "MANCHESTERCITY",
    "INTER": "INTERNACIONAL", "RBBRAGANTINO": "BRAGANTINO",
}


def norm(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^A-Z0-9/ ]", "", s)
    s = re.sub(r"/[A-Z]{2}\b", "", s)  # remove /UF
    s = s.replace(" ", "").replace("/", "")
    return APELIDOS.get(s, s)


def parecido(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    if a[:5] == b[:5]:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.6


def main():
    with open(os.path.join(PASTA, "resultados_caixa.csv"), encoding="utf-8") as f:
        res = {(int(r["concurso"]), int(r["jogo"])): r for r in csv.DictReader(f)}
    with open(os.path.join(PASTA, "lotequeiros_palpites.csv"), encoding="utf-8") as f:
        pal = list(csv.DictReader(f))

    casados, sem_res, nomes_dif, sorteio = [], 0, 0, 0
    for p in pal:
        k = (int(p["concurso"]), int(p["jogo"]))
        r = res.get(k)
        if not r:
            sem_res += 1
            continue
        if str(r["sorteio"]) == "1":
            sorteio += 1
            continue
        ok = parecido(p["mandante"], r["mandante"]) or parecido(p["visitante"], r["visitante"])
        if not ok:
            nomes_dif += 1
            continue
        casados.append({**p, "res_mandante": r["mandante"], "res_visitante": r["visitante"],
                        "gols_m": r["gols_m"], "gols_v": r["gols_v"],
                        "resultado": r["resultado"], "data_jogo": r["data_jogo"]})

    with open(os.path.join(PASTA, "lotequeiros_x_caixa.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(casados[0].keys()))
        w.writeheader()
        w.writerows(casados)

    print(f"Palpites: {len(pal)} | casados com a Caixa: {len(casados)} | "
          f"sem resultado: {sem_res} | nomes diferentes (descartados): {nomes_dif} | sorteio: {sorteio}")

    def resumo(rows, rotulo):
        s = [r for r in rows if r["seco"]]
        d = [r for r in rows if r["duplo"]]
        if not s:
            return
        ac_s = sum(r["seco"] == r["resultado"] for r in s) / len(s)
        base1 = sum(r["resultado"] == "1" for r in s) / len(s)
        ac_d = (sum(r["resultado"] in r["duplo"] for r in d) / len(d)) if d else float("nan")
        print(f"{rotulo:<22} secos={len(s):>5}  acerto seco={ac_s:6.1%}  "
              f"(sempre '1'={base1:6.1%}, ganho={ac_s - base1:+6.1%})  "
              f"duplos={len(d):>5}  acerto duplo={ac_d:6.1%}")

    print("\n== Geral ==")
    resumo(casados, "Todos")
    print("\n== Por forma de leitura ==")
    for m in ["padrao", "livre", "ultima_coluna"]:
        resumo([r for r in casados if r["metodo"] == m], m)
    print("\n== Por faixa de concurso ==")
    faixas = defaultdict(list)
    for r in casados:
        faixas[(int(r["concurso"]) // 100) * 100].append(r)
    for b in sorted(faixas):
        resumo(faixas[b], f"{b}-{b + 99}")
    print("\n== Por palpite seco ==")
    for c in "1X2":
        resumo([r for r in casados if r["seco"] == c], f"seco = {c}")

    # quantos secos acerta por concurso (entre os jogos com seco)
    por_conc = defaultdict(lambda: [0, 0])
    for r in casados:
        if r["seco"]:
            por_conc[r["concurso"]][0] += r["seco"] == r["resultado"]
            por_conc[r["concurso"]][1] += 1
    cheios = [v for v in por_conc.values() if v[1] == 14]
    if cheios:
        dist = defaultdict(int)
        for a, _ in cheios:
            dist[a] += 1
        print(f"\n== Concursos com os 14 secos ({len(cheios)}): acertos por concurso ==")
        print("  " + "  ".join(f"{k}:{dist[k]}" for k in sorted(dist)))
        print(f"  media = {sum(a for a, _ in cheios) / len(cheios):.2f} de 14")


if __name__ == "__main__":
    main()
