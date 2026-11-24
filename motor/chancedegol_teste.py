"""
Teste: o modelo do Chance de Gol acrescenta algo as odds da bet365 (Arena do AZ) nos jogos da Loteca?

Casa coleta/dados/chancedegol.csv com coleta/dados/arena_odds.csv (data +-1 dia, nomes parecidos e
placar coerente com o resultado). Compara, nos MESMOS jogos:
  odds sozinhas | Chance de Gol sozinho | mistura das duas
O peso da mistura e escolhido so na 1a metade (ordem do tempo) e conferido na 2a metade, nunca vista.
Saida: motor/chancedegol_teste.md
"""
import csv
import datetime
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
from fd_base import data, sim  # noqa: E402

DADOS = os.path.join(RAIZ, "coleta", "dados")


def metricas(probs, ys):
    n = len(ys)
    ac = sum(max(range(3), key=lambda i: p[i]) == y for p, y in zip(probs, ys)) / n
    br = sum(sum((p[i] - (i == y)) ** 2 for i in range(3)) for p, y in zip(probs, ys)) / n
    ll = -sum(math.log(max(p[y], 1e-6)) for p, y in zip(probs, ys)) / n
    return ac, br, ll


def mistura(a, b, w):
    # media geometrica ponderada (log-linear), renormalizada
    q = [math.exp((1 - w) * math.log(max(x, 1e-6)) + w * math.log(max(z, 1e-6))) for x, z in zip(a, b)]
    s = sum(q)
    return [x / s for x in q]


def main():
    cdg = list(csv.DictReader(open(os.path.join(DADOS, "chancedegol.csv"), encoding="utf-8")))
    for c in cdg:
        c["d"] = data(c["data"])
    arena = list(csv.DictReader(open(os.path.join(DADOS, "arena_odds.csv"), encoding="utf-8")))
    casados = []
    for a in arena:
        d = data(a.get("data_jogo") or "")
        if not d or a["resultado"] not in ("1", "X", "2"):
            continue
        y = {"1": 0, "X": 1, "2": 2}[a["resultado"]]
        melhor, nota = None, 0
        for c in cdg:
            if not c["d"] or abs((c["d"] - d).days) > 1:
                continue
            gm, gv = int(c["gols_m"]), int(c["gols_v"])
            if (0 if gm > gv else (1 if gm == gv else 2)) != y:
                continue
            s = min(sim(a["mandante"], c["mandante"]), sim(a["visitante"], c["visitante"]))
            if s > nota:
                melhor, nota = c, s
        if melhor and nota >= 0.8:
            odd = [float(a["p_1"]), float(a["p_x"]), float(a["p_2"])]
            ch = [float(melhor["p1"]) / 100, float(melhor["px"]) / 100, float(melhor["p2"]) / 100]
            casados.append((d, int(a["concurso"]), odd, ch, y, melhor["campeonato"]))
    casados.sort(key=lambda t: (t[0], t[1]))
    n = len(casados)
    L = ["# Chance de Gol × odds bet365 nos jogos da Loteca", "",
         f"Gerado em {datetime.date.today().isoformat()}. Jogos da Loteca casados: **{n}** "
         f"(concursos {min(t[1] for t in casados) if n else '-'}–{max(t[1] for t in casados) if n else '-'})."]
    if n < 40:
        L.append("\nPoucos jogos casados — teste inconclusivo.")
        open(os.path.join(AQUI, "chancedegol_teste.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
        print("\n".join(L))
        return
    ys = [t[4] for t in casados]
    odd = [t[2] for t in casados]
    ch = [t[3] for t in casados]
    meio = n // 2
    pesos = [i / 10 for i in range(11)]
    melhor_w = min(pesos, key=lambda w: metricas([mistura(o, c, w) for o, c in zip(odd[:meio], ch[:meio])], ys[:meio])[2])
    L += ["", "## Todos os jogos casados", "", "| Fonte | Acerto | Brier (menor = melhor) | Log-loss |", "|---|---|---|---|"]
    for nome, P in [("Odds bet365", odd), ("Chance de Gol", ch)] + \
                   [(f"Mistura {int(w * 100)}% Chance de Gol", [mistura(o, c, w) for o, c in zip(odd, ch)]) for w in (0.2, 0.4, 0.5)]:
        ac, br, ll = metricas(P, ys)
        L.append(f"| {nome} | {ac:.1%} | {br:.4f} | {ll:.4f} |")
    L += ["", f"## Teste no tempo (peso escolhido na 1ª metade = {int(melhor_w * 100)}% Chance de Gol; conferido na 2ª metade, {n - meio} jogos)", "",
          "| Fonte | Acerto | Brier | Log-loss |", "|---|---|---|---|"]
    res = {}
    for nome, P in [("Odds bet365", odd[meio:]), ("Chance de Gol", ch[meio:]),
                    ("Mistura", [mistura(o, c, melhor_w) for o, c in zip(odd[meio:], ch[meio:])])]:
        res[nome] = metricas(P, ys[meio:])
        ac, br, ll = res[nome]
        L.append(f"| {nome} | {ac:.1%} | {br:.4f} | {ll:.4f} |")
    ganho = (res["Odds bet365"][1] - res["Mistura"][1]) / res["Odds bet365"][1]
    L += ["", f"Ganho de Brier da mistura sobre as odds na metade nunca vista: **{ganho:+.2%}**."]
    disc = [(o, c, y) for o, c, y in zip(odd, ch, ys) if max(range(3), key=lambda i: o[i]) != max(range(3), key=lambda i: c[i])]
    if disc:
        ao = sum(max(range(3), key=lambda i: o[i]) == y for o, c, y in disc) / len(disc)
        ac_ = sum(max(range(3), key=lambda i: c[i]) == y for o, c, y in disc) / len(disc)
        L += [f"Quando os dois apontam favoritos diferentes ({len(disc)} jogos): odds acertam {ao:.1%}, Chance de Gol {ac_:.1%}."]
    camp = {}
    for t in casados:
        camp[t[5]] = camp.get(t[5], 0) + 1
    L += ["", "Jogos por campeonato: " + ", ".join(f"{k} {v}" for k, v in sorted(camp.items(), key=lambda x: -x[1]))]
    open(os.path.join(AQUI, "chancedegol_teste.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
