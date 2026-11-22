"""
Validacao da camada 1 no tempo (walk-forward): para cada bloco de 10
concursos, aprende os ajustes so com os concursos anteriores e preve o bloco.
Compara: odds puras (potencia) x + ajuste de empate x + gama x os dois.
Um ajuste so e aceito se nao piorar o acerto (14 e top-k) e melhorar Brier
ou calibracao.
Uso: python motor/validar_camada1.py
"""
import csv
import math
import os
import sys
from collections import defaultdict

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from calibracao import aplica, aprende  # noqa: E402

REPO = os.path.dirname(AQUI)
METAS = {14: .56, 10: .60, 8: .62, 6: .65, 4: .70}


def carregar():
    jogos = []
    with open(os.path.join(REPO, "coleta", "dados", "arena_odds.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["resultado"]:
                jogos.append(dict(c=int(r["concurso"]), odds=[float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])],
                                  y="1X2".index(r["resultado"])))
    return jogos


def metricas(itens):
    """itens: lista de (concurso, p[3], y)."""
    por = defaultdict(list)
    for c, p, y in itens:
        por[c].append((max(p), int(np.argmax(p)) == y))
    acc = {}
    for k in METAS:
        h = n = 0
        for v in por.values():
            t = sorted(v, key=lambda x: -x[0])[:k]
            h += sum(x[1] for x in t)
            n += len(t)
        acc[k] = h / n
    brier = np.mean([sum((p[i] - (i == y)) ** 2 for i in range(3)) for _, p, y in itens])
    ll = np.mean([-math.log(max(p[y], 1e-9)) for _, p, y in itens])
    # erro de calibracao (todas as probabilidades, 10 faixas)
    pares = sorted((p[i], i == y) for _, p, y in itens for i in range(3))
    n = len(pares)
    ece = sum(abs(np.mean([a for a, _ in pares[k * n // 10:(k + 1) * n // 10]]) -
                  np.mean([b for _, b in pares[k * n // 10:(k + 1) * n // 10]])) / 10 for k in range(10))
    return acc, brier, ll, ece


def main():
    jogos = carregar()
    concursos = sorted({j["c"] for j in jogos})
    teste = concursos[100:]
    blocos = [teste[i:i + 10] for i in range(0, len(teste), 10)]
    variantes = {"odds puras (potencia)": (False, False), "+ ajuste de empate": (True, False),
                 "+ gama (favoritos)": (False, True), "+ empate + gama": (True, True)}
    saida = {v: [] for v in variantes}
    params_hist = defaultdict(list)
    for b in blocos:
        treino = [(j["odds"], j["y"]) for j in jogos if j["c"] < b[0]]
        te = [j for j in jogos if j["c"] in set(b)]
        for nome, (emp, gam) in variantes.items():
            prm = aprende(treino, usar_empate=emp, usar_gama=gam) if (emp or gam) else {}
            params_hist[nome].append(prm)
            saida[nome] += [(j["c"], aplica(j["odds"], prm), j["y"]) for j in te]
    n_jogos = len(saida["odds puras (potencia)"])
    print(f"Teste no tempo: {len(teste)} concursos ({teste[0]}-{teste[-1]}), {n_jogos} jogos; "
          f"ajustes aprendidos so com concursos anteriores\n")
    print(f"  {'':<24}" + " | ".join(f"{k}: {v:.0%}" for k, v in METAS.items()) + "  <- METAS")
    for nome in variantes:
        acc, brier, ll, ece = metricas(saida[nome])
        print(f"  {nome:<24}" + " | ".join(f"{k}: {acc[k]:.1%}" for k in METAS) +
              f" | Brier {brier:.4f} | log-loss {ll:.4f} | calibracao {ece:.2%}")
    for nome in ("+ empate + gama",):
        g = [p.get("gama", 1) for p in params_hist[nome]]
        f = [p.get("fator_empate", 1) for p in params_hist[nome]]
        print(f"\n  parametros aprendidos ({nome}): gama {min(g):.2f}-{max(g):.2f} (ultimo {g[-1]:.2f}); "
              f"fator de empate {min(f):.3f}-{max(f):.3f} (ultimo {f[-1]:.3f})")


if __name__ == "__main__":
    main()
