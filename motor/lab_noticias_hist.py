"""
A camada de noticias acrescenta informacao as odds? (historico, sem vazamento)

Usa coleta/dados/noticias_hist_sinais.csv (manchetes dos 7 dias ANTES de cada jogo,
parando na vespera). Para cada sinal, a diferenca mandante - visitante (log de 1 + contagem)
empurra a coluna 1 para um lado e a coluna 2 para o outro; o sinal de "reservas/desfalques
dos dois lados" pode mexer no empate. Modelo: q_k proporcional a p_k * exp(F_k . b), com p = odds.
Teste no tempo (walk-forward): pesos ajustados so com concursos anteriores, ganho de log-loss
medido no concurso seguinte. forca = ganho medio / erro padrao; acima de 2 = sinal real.
Uso: python motor/lab_noticias_hist.py > motor/lab_noticias_hist.md
"""
import collections
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import camada2 as c2  # noqa: E402
from sinal_especialista import resultados  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ = os.path.join(RAIZ, "coleta", "dados", "noticias_hist_sinais.csv")
SINAIS = ["desfalque", "reservas", "crise", "tecnico", "reforco"]


def ajustar(L, lam=2.0):
    m = L[0][2].shape[1]
    b = np.zeros(m)
    P = np.array([l[1] for l in L]); F = np.array([l[2] for l in L]); y = np.array([l[3] for l in L])
    for _ in range(30):
        z = np.log(P) + F @ b
        q = np.exp(z - z.max(1, keepdims=True)); q /= q.sum(1, keepdims=True)
        Fy = F[np.arange(len(y)), y]; Eq = (q[..., None] * F).sum(1)
        g = (Fy - Eq).sum(0) - lam * b
        Hm = np.einsum("ik,ika,ikb->ab", q, F, F) - Eq.T @ Eq
        b += np.linalg.solve(Hm + lam * np.eye(m), g)
    return b


def testar(nome, L, minimo=30):
    cs = sorted({l[0] for l in L})
    por_conc = []
    for c in cs:
        treino = [l for l in L if l[0] < c]
        if len({l[0] for l in treino}) < minimo:
            continue
        b = ajustar(treino)
        g = 0.0
        for l in (l for l in L if l[0] == c):
            z = np.log(l[1]) + l[2] @ b; q = np.exp(z - z.max()); q /= q.sum()
            g += math.log(q[l[3]]) - math.log(l[1][l[3]])
        por_conc.append(g)
    bt = ajustar(L)
    g = np.array(por_conc)
    forca = g.mean() / (g.std() / math.sqrt(len(g))) if len(g) > 1 and g.std() > 0 else 0.0
    print(f"| {nome} | {len(L)} | {len(g)} | {' '.join(f'{x:+.3f}' for x in bt)} | {g.mean():+.4f} | {forca:+.1f} | "
          f"{'**SINAL REAL**' if forca > 2 else ('promissor' if forca > 1 else 'nao')} |")
    return forca


def main():
    res = resultados(); odds = c2.odds_por_concurso()
    d = collections.defaultdict(dict)
    for r in csv.DictReader(open(ARQ, encoding="utf-8")):
        d[(int(r["concurso"]), int(r["jogo"]))][r["lado"]] = r
    base = []
    for (c, j), lados in d.items():
        if len(lados) < 2 or c not in res or j not in odds.get(c, {}):
            continue
        p = np.asarray(c2.prob_mercado(odds[c][j]), float)
        base.append((c, p, lados["1"], lados["2"], res[c][j - 1]))
    print("# Noticias da semana anterior ao jogo x odds (sem vazamento: ate a vespera)\n")
    print(f"Jogos com noticias, odd e resultado: {len(base)} em {len({b[0] for b in base})} concursos\n")
    print("| sinal | jogos | concursos testados | peso | ganho por concurso | forca | veredito |")
    print("|---|---|---|---|---|---|---|")

    def lado(x):  # empurra 1 para um lado e 2 para o outro
        return np.array([[x], [0.0], [-x]])

    for pref, rot in (("so_", "so do time"), ("", "todas")):
        for s in SINAIS:
            L = [(c, p, lado(math.log1p(float(a[pref + s])) - math.log1p(float(b[pref + s]))), y) for c, p, a, b, y in base]
            testar(f"{s} ({rot}) mandante - visitante", L)
        L = [(c, p, lado(math.log1p(float(a[pref + "manchetes" if pref == "" else "so_dele"])) -
                         math.log1p(float(b[pref + "manchetes" if pref == "" else "so_dele"]))), y) for c, p, a, b, y in base]
        testar(f"volume de noticias ({rot}) mandante - visitante", L)
    # empate: muito desfalque/reserva dos dois lados
    L = [(c, p, np.array([[0.0], [math.log1p(float(a["so_desfalque"]) + float(b["so_desfalque"]))], [0.0]]), y) for c, p, a, b, y in base]
    testar("desfalques somados -> empate", L)
    L = [(c, p, np.array([[0.0], [math.log1p(float(a["so_reservas"]) + float(b["so_reservas"]))], [0.0]]), y) for c, p, a, b, y in base]
    testar("reservas somadas -> empate", L)
    # tudo junto
    def tudo(a, b):
        cols = [math.log1p(float(a["so_" + s])) - math.log1p(float(b["so_" + s])) for s in SINAIS]
        return np.array([cols, [0.0] * len(cols), [-x for x in cols]])
    testar("todos os sinais juntos (so do time)", [(c, p, tudo(a, b), y) for c, p, a, b, y in base])


if __name__ == "__main__":
    main()
