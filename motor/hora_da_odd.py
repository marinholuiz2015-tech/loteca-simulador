"""
A hora da odd: quanto se perde decidindo com a bet365 de quinta (Arena do AZ) em vez da odd mais recente?

Casa os jogos da Loteca (coleta/dados/arena_odds.csv) com o football-data (data +-2 dias, nomes parecidos,
placar igual) e compara, nos MESMOS jogos:
  Arena bet365 (quinta)  |  bet365 abertura football-data (sexta)  |  bet365 fechamento  |
  Pinnacle fechamento    |  media do mercado no fechamento
Forca = ganho medio de log-loss sobre a Arena / erro-padrao (pareado, jogo a jogo). > 2 = diferenca real.
Saida: motor/hora_da_odd.md
"""
import csv
import math
import os
import sys
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(os.path.dirname(AQUI), "coleta", "dados")
sys.path.insert(0, AQUI)
from calibracao import sem_margem  # noqa: E402
from fd_base import data, jogos, sim  # noqa: E402

FONTES = [("arena", "Arena bet365 (quinta)"), ("b365o", "bet365 abertura (sexta)"), ("pso", "Pinnacle abertura (sexta)"), ("avgo", "Média do mercado na abertura (sexta)"), ("b365c", "bet365 fechamento"),
          ("ps", "Pinnacle fechamento"), ("avg", "Média do mercado no fechamento")]


def main():
    fd = defaultdict(list)
    for g in jogos():
        if g["gc"] is not None:
            fd[(g["gc"], g["gf"])].append(g)
    placar = {}
    for r in csv.DictReader(open(os.path.join(DADOS, "resultados_caixa.csv"), encoding="utf-8")):
        placar[(r["concurso"], r["jogo"])] = (r["gols_m"], r["gols_v"])
    casados = []
    for r in csv.DictReader(open(os.path.join(DADOS, "arena_odds.csv"), encoding="utf-8")):
        r["gols_m"], r["gols_v"] = placar.get((r["concurso"], r["jogo"]), ("", ""))
        d = data(r.get("data_jogo") or "")
        if not d or r.get("resultado") not in ("1", "X", "2") or not r.get("gols_m"):
            continue
        try:
            gm, gv = int(float(r["gols_m"])), int(float(r["gols_v"]))
        except Exception:
            continue
        melhor, nota = None, 0
        for g in fd[(gm, gv)]:
            if abs((g["d"] - d).days) > 2:
                continue
            s = min(sim(r["mandante"], g["casa"]), sim(r["visitante"], g["fora"]))
            if s > nota:
                melhor, nota = g, s
        if melhor and nota >= 0.7:
            row = {"concurso": int(r["concurso"]), "y": "1X2".index(r["resultado"]), "liga": melhor["liga"],
                   "arena": list(sem_margem([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])]))}
            for k, _ in FONTES[1:]:
                if k in melhor:
                    row[k] = list(sem_margem(melhor[k]))
            casados.append(row)

    def comparar(rows, k):
        rs = [x for x in rows if k in x]
        if len(rs) < 30:
            return None
        g, ac_a, ac_k, br_a, br_k, troca, troca_ok_k, troca_ok_a = [], 0, 0, 0, 0, 0, 0, 0
        for x in rs:
            pa, pk, y = x["arena"], x[k], x["y"]
            g.append(math.log(max(pk[y], 1e-6)) - math.log(max(pa[y], 1e-6)))
            fa, fk = max(range(3), key=lambda i: pa[i]), max(range(3), key=lambda i: pk[i])
            ac_a += fa == y
            ac_k += fk == y
            br_a += sum((pa[i] - (i == y)) ** 2 for i in range(3))
            br_k += sum((pk[i] - (i == y)) ** 2 for i in range(3))
            if fa != fk:
                troca += 1
                troca_ok_k += fk == y
                troca_ok_a += fa == y
        n = len(rs)
        m = sum(g) / n
        sd = math.sqrt(sum((v - m) ** 2 for v in g) / (n - 1))
        return {"n": n, "forca": m / (sd / math.sqrt(n)), "ac_a": ac_a / n, "ac_k": ac_k / n,
                "br_a": br_a / n, "br_k": br_k / n, "troca": troca, "ok_k": troca_ok_k, "ok_a": troca_ok_a}

    ligas = defaultdict(int)
    for x in casados:
        ligas[x["liga"]] += 1
    L = ["# A hora da odd — bet365 de quinta × odds mais recentes", "",
         f"Jogos da Loteca casados com o football-data: **{len(casados)}** "
         f"(concursos {min(x['concurso'] for x in casados)}–{max(x['concurso'] for x in casados)}). "
         "Cada linha compara a fonte com a Arena **nos mesmos jogos**.", "",
         "| Fonte | Jogos | Acerto Arena → fonte | Brier Arena → fonte | Força (log-loss) | Favorito trocado: fonte acertou × Arena acertou |",
         "|---|---|---|---|---|---|"]
    res = {}
    for k, nome in FONTES[1:]:
        c = comparar(casados, k)
        if not c:
            continue
        res[k] = c
        L.append(f"| {nome} | {c['n']} | {c['ac_a']:.1%} → {c['ac_k']:.1%} | {c['br_a']:.4f} → {c['br_k']:.4f} | "
                 f"{c['forca']:+.2f} | {c['troca']} jogos: {c['ok_k']} × {c['ok_a']} |")
    L += ["", "Jogos por liga: " + ", ".join(f"{k} {v}" for k, v in sorted(ligas.items(), key=lambda t: -t[1]))]
    open(os.path.join(AQUI, "hora_da_odd.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
