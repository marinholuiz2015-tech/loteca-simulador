"""
Mantem o palpite do mercado (favorito) e muda so a ORDEM de confianca.
Modelo (treinado so no passado) estima P(favorito acerta) com sinais extras;
compara o acerto seletivo top-k com a ordem pura das odds.
"""
import math, os, sys, warnings
from collections import defaultdict
import numpy as np
from sklearn.linear_model import LogisticRegression
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from walkforward import carregar, lg, METAS

def feat(r, conj):
    p = sorted([r["p1"], r["px"], r["p2"]], reverse=True)
    fav = int(r["fav"])
    f = [lg(r["pfav"]), lg(p[0]) - lg(p[1]), r["margem"], r["intl"], fav == 0, fav == 2, r["px"]]
    if "lq" in conj:
        f += [r["lq_concorda"] == 1, r["lq_concorda"] == 0, r["lq_concorda"] < 0]
        d = r["lq_duplo"]; favc = "1X2"[fav]
        f += [favc in d if d else 0]
    return f

def topk(rows, score):
    por = defaultdict(list)
    for r, s in zip(rows, score):
        por[r["concurso"]].append((s, int(r["fav"]) == int(r["resultado"])))
    out = {}
    for k in (14, 10, 8, 6, 4):
        h = n = 0
        for v in por.values():
            t = sorted(v, key=lambda x: -x[0])[:k]; h += sum(x[1] for x in t); n += len(t)
        out[k] = h / n
    return out

rows = carregar()
conc = sorted({r["concurso"] for r in rows})
teste = conc[100:]
blocos = [teste[i:i+10] for i in range(0, len(teste), 10)]
tr_rows = [r for r in rows if r["concurso"] in set(teste)]
res = {}
for conj in ("base", "lq"):
    sc = []
    for b in blocos:
        tr = [r for r in rows if r["concurso"] < b[0]]; te = [r for r in rows if r["concurso"] in set(b)]
        m = LogisticRegression(C=0.5, max_iter=2000)
        m.fit(np.array([feat(r, conj) for r in tr], float), [int(r["fav"]) == int(r["resultado"]) for r in tr])
        sc += list(m.predict_proba(np.array([feat(r, conj) for r in te], float))[:, 1])
    res[conj] = sc
print("  " + " " * 30 + " | ".join(f"{k}: {v:.0%}" for k, v in METAS.items()) + "  <- METAS")
for nome, s in (("ordem pelas odds", [r["pfav"] for r in tr_rows]),
                ("ordem modelo (contexto)", res["base"]), ("ordem modelo (+Lotequeiros)", res["lq"])):
    o = topk(tr_rows, s)
    print(f"  {nome:<30} " + " | ".join(f"{k}: {o[k]:.1%}" for k in (14, 10, 8, 6, 4)))
# concordancia: diagnostico
for nome, sel in (("mercado e Lotequeiros concordam", lambda r: r["lq_concorda"] == 1),
                  ("discordam", lambda r: r["lq_concorda"] == 0)):
    g = [r for r in tr_rows if sel(r)]
    print(f"  {nome:<32} {len(g)} jogos | favorito previsto {np.mean([r['pfav'] for r in g]):.1%} | real {np.mean([int(r['fav'])==int(r['resultado']) for r in g]):.1%}")
