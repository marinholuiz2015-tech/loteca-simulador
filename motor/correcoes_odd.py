"""
Correcoes em cima da odd (degraus 5, 6 e 7 da escada). Cada correcao e um ajuste pequeno na probabilidade
da odd, aprendido SO com o passado e conferido nos jogos seguintes. Definicoes fixadas antes do teste:

  C1 Empate nos equilibrados   jogos da Loteca (Arena/bet365) com |p1 - p2| <= 0,10  -> ajuste no empate
  C2 Mandante em luta x visitante favorito   reta final (<= 8 rodadas), mandante a ate 3 pts da zona e
                               visitante favorito pela odd (football-data, Serie A + Europa) -> ajuste na vitoria do mandante
  C3 Massa no empate           enquete Vovoteca da ao empate 15 pontos ou mais acima da odd -> ajuste no empate

Forca = ganho medio de log-loss / erro-padrao, so nos jogos em que a correcao age. Passa com forca > 2
sem piorar o acerto. Saida: motor/correcoes_odd.md
"""
import csv
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(os.path.dirname(AQUI), "coleta", "dados")
sys.path.insert(0, AQUI)
from calibracao import sem_margem  # noqa: E402


def ajustar(P, F, y, lam=2.0):
    """Logit sobre log(p da odd): z = log p + F.b ; F tem forma (n, 3, k)."""
    k = F.shape[2]
    b = np.zeros(k)
    if len(y) == 0:
        return b
    for _ in range(25):
        z = np.log(P) + F @ b
        q = np.exp(z - z.max(1, keepdims=True))
        q /= q.sum(1, keepdims=True)
        Eq = (q[..., None] * F).sum(1)
        g = (F[np.arange(len(y)), y] - Eq).sum(0) - lam * b
        H = np.einsum("ik,ika,ikb->ab", q, F, F) - Eq.T @ Eq
        b += np.linalg.solve(H + lam * np.eye(k), g)
    return b


def no_tempo(chaves, P, F, y, passo):
    """chaves ordenaveis (concurso ou ano). Re-treina a cada `passo` chaves; testa na chave seguinte."""
    unicas = sorted(set(chaves))
    inicio = unicas[len(unicas) // 3]
    ch = np.array(chaves)
    ganhos, acm, acc, pesos, b = [], [], [], [], None
    for i, c in enumerate(unicas):
        if c < inicio:
            continue
        if b is None or i % passo == 0:
            tr = ch < c
            b = ajustar(P[tr], F[tr], y[tr])
            pesos.append(float(b[0]))
        te = np.where((ch == c) & (np.abs(F).sum((1, 2)) > 0))[0]
        for j in te:
            z = np.log(P[j]) + F[j] @ b
            q = np.exp(z - z.max())
            q /= q.sum()
            ganhos.append(math.log(q[y[j]]) - math.log(P[j][y[j]]))
            acm.append(int(np.argmax(P[j]) == y[j]))
            acc.append(int(np.argmax(q) == y[j]))
    g = np.array(ganhos)
    forca = g.mean() / (g.std(ddof=1) / math.sqrt(len(g))) if len(g) > 2 else 0.0
    return {"jogos": len(g), "ganho": float(g.mean()) if len(g) else 0.0, "forca": float(forca),
            "acerto_odd": float(np.mean(acm)) if acm else 0.0, "acerto_corr": float(np.mean(acc)) if acc else 0.0,
            "peso_inicio": pesos[0] if pesos else 0.0, "peso_fim": pesos[-1] if pesos else 0.0}


def arena():
    out = []
    for r in csv.DictReader(open(os.path.join(DADOS, "arena_odds.csv"), encoding="utf-8")):
        if r.get("resultado") not in ("1", "X", "2"):
            continue
        p = sem_margem([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])])
        out.append((int(r["concurso"]), int(r["jogo"]), list(p), "1X2".index(r["resultado"])))
    out.sort(key=lambda a: (a[0], a[1]))
    return out


def c1():
    A = arena()
    P = np.array([a[2] for a in A])
    F = np.zeros((len(A), 3, 1))
    for i, a in enumerate(A):
        if abs(a[2][0] - a[2][2]) <= 0.10:
            F[i, 1, 0] = 1
    S = F[:, 1, 0] == 1
    y = np.array([a[3] for a in A])
    real, odd = float(np.mean(y[S] == 1)), float(P[S, 1].mean())
    return no_tempo([a[0] for a in A], P, F, y, 10), int(S.sum()), real, odd


def c3():
    massa = {}
    for arq in ("vovoteca_massa.csv",):
        for r in csv.DictReader(open(os.path.join(DADOS, arq), encoding="utf-8")):
            try:
                massa[(int(r["concurso"]), int(r["jogo"]))] = float(r["massa_x"])
            except Exception:
                pass
    A = [a for a in arena() if (a[0], a[1]) in massa]
    P = np.array([a[2] for a in A])
    F = np.zeros((len(A), 3, 1))
    for i, a in enumerate(A):
        if massa[(a[0], a[1])] - 100 * a[2][1] >= 15:
            F[i, 1, 0] = 1
    S = F[:, 1, 0] == 1
    y = np.array([a[3] for a in A])
    real, odd = float(np.mean(y[S] == 1)), float(P[S, 1].mean())
    return no_tempo([a[0] for a in A], P, F, y, 10), int(S.sum()), real, odd, len(A)


def c2():
    import motivacao as M
    L = M.reta_final()
    P = np.array([M.sem_margem(l[2]) for l in L])
    F = np.zeros((len(L), 3, 1))
    for i, l in enumerate(L):
        if l[4]["luta"] and P[i][2] > P[i][0]:
            F[i, 0, 0] = 1
    S = F[:, 0, 0] == 1
    y = np.array([l[3] for l in L])
    real, odd = float(np.mean(y[S] == 0)), float(P[S, 0].mean())
    return no_tempo([M.ano(l[1]) for l in L], P, F, y, 1), int(S.sum()), real, odd


def linha(nome, r, n, real, odd, evento):
    ok = r["forca"] > 2 and r["acerto_corr"] >= r["acerto_odd"]
    return (f"| {nome} | {n} | {evento}: {real:.1%} × odd {odd:.1%} | {r['jogos']} | {r['forca']:+.2f} | "
            f"{r['acerto_odd']:.1%} → {r['acerto_corr']:.1%} | {r['peso_inicio']:+.3f} → {r['peso_fim']:+.3f} | "
            f"{'**APROVADA**' if ok else ('promissora' if r['forca'] > 0.5 else 'reprovada')} |")


def main():
    r1, n1, re1, o1 = c1()
    r2, n2, re2, o2 = c2()
    r3, n3, re3, o3, tot3 = c3()
    md = ["# Correções em cima da odd — teste no tempo", "",
          "Cada correção aprende só com o passado (Loteca: re-treina a cada 10 concursos; reta final: ano a ano) "
          "e é conferida nos jogos seguintes. Força > 2 sem perder acerto = aprovada.", "",
          "| Correção | Jogos com a situação | Histórico inteiro | Jogos testados | Força | Acerto odd → corrigido | Peso (início → fim) | Resultado |",
          "|---|---|---|---|---|---|---|---|",
          linha("C1 Empate nos equilibrados (diferença p1−p2 até 0,10, Loteca 895+)", r1, n1, re1, o1, "empate"),
          linha("C2 Mandante em luta × visitante favorito (reta final, Série A + Europa)", r2, n2, re2, o2, "mandante vence"),
          linha(f"C3 Massa ≥ 15 pts acima da odd no empate (Loteca, {tot3} jogos com enquete)", r3, n3, re3, o3, "empate")]
    open(os.path.join(AQUI, "correcoes_odd.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
