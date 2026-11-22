"""
Teste no tempo (walk-forward) dos modelos que corrigem as odds.
Para cada bloco de 10 concursos, treina so com os concursos anteriores e
preve o bloco. Mede acerto nos 14 e acerto seletivo (top 10/8/6/4 por
concurso, ordenados pela confianca de cada modelo) contra o mercado.
Metas: 14=56%, 10=60%, 8=62%, 6=65%, 4=70%.
"""
import csv
import math
import os
import sys
import warnings
from collections import defaultdict

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
AQUI = os.path.dirname(os.path.abspath(__file__))
METAS = {14: .56, 10: .60, 8: .62, 6: .65, 4: .70}


def carregar():
    with open(os.path.join(AQUI, "base_features.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if k not in ("lq_duplo",):
                r[k] = float(v)
    return rows


def lg(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def features(r, conjunto):
    f = [lg(r["p1"]), lg(r["px"]), lg(r["p2"]), r["pfav"], r["equilibrio"], r["margem"],
         r["intl"], r["mesmo_estado"], r["equilibrio"] * r["px"]]
    if "lq" in conjunto:
        s = int(r["lq_seco"])
        f += [s == 0, s == 1, s == 2, s < 0, r["lq_concorda"] == 1]
        d = r["lq_duplo"]
        f += ["1" in d, "X" in d, "2" in d]
    return f


def avaliar(rows, probs, nome, linha_base=None):
    por_conc = defaultdict(list)
    for r, p in zip(rows, probs):
        por_conc[r["concurso"]].append((max(p), int(np.argmax(p)) == int(r["resultado"]), p, int(r["resultado"])))
    res = {}
    for k in (14, 10, 8, 6, 4):
        h = n = 0
        for v in por_conc.values():
            top = sorted(v, key=lambda x: -x[0])[:k]
            h += sum(t[1] for t in top)
            n += len(top)
        res[k] = h / n
    brier = np.mean([sum((p[i] - (i == y)) ** 2 for i in range(3)) for v in por_conc.values() for _, _, p, y in v])
    txt = " | ".join(f"{k}: {res[k]:.1%}" for k in (14, 10, 8, 6, 4))
    print(f"  {nome:<34} {txt} | Brier {brier:.4f}")
    return res


def main():
    rows = carregar()
    concursos = sorted({r["concurso"] for r in rows})
    inicio = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    teste = [c for c in concursos[inicio:]]
    blocos = [teste[i:i + 10] for i in range(0, len(teste), 10)]
    modelos = {
        "logistica (odds+contexto)": ("base", lambda: LogisticRegression(C=0.5, max_iter=2000)),
        "logistica (+Lotequeiros)": ("lq", lambda: LogisticRegression(C=0.5, max_iter=2000)),
        "boosting (+Lotequeiros)": ("lq", lambda: HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=150, l2_regularization=1.0, min_samples_leaf=60)),
    }
    test_rows = [r for r in rows if r["concurso"] in set(teste)]
    pred = {m: [] for m in modelos}
    for bloco in blocos:
        tr = [r for r in rows if r["concurso"] < bloco[0]]
        te = [r for r in rows if r["concurso"] in set(bloco)]
        y = [int(r["resultado"]) for r in tr]
        for nome, (conj, fab) in modelos.items():
            m = fab()
            m.fit(np.array([features(r, conj) for r in tr], float), y)
            pred[nome] += list(m.predict_proba(np.array([features(r, conj) for r in te], float)))
    print(f"Teste no tempo: {len(teste)} concursos ({int(teste[0])}-{int(teste[-1])}), "
          f"{len(test_rows)} jogos; treino sempre so com concursos anteriores")
    print("  " + " " * 34 + " | ".join(f"{k}: {v:.0%}" for k, v in METAS.items()) + "  <- METAS")
    merc = [np.array([r["p1"], r["px"], r["p2"]]) for r in test_rows]
    avaliar(test_rows, merc, "MERCADO (odds bet365)")
    for nome in modelos:
        avaliar(test_rows, pred[nome], nome)
        mix = [(a + b) / 2 for a, b in zip(merc, pred[nome])]
        avaliar(test_rows, mix, "  media mercado + " + nome.split(" ")[0])


if __name__ == "__main__":
    main()
