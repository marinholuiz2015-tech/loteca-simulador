"""
Camada 1 — calibracao das probabilidades a partir das odds.

Funcoes puras usadas pelo motor e pela validacao:
  sem_margem(odds)          -> probabilidades sem a margem da casa (metodo de potencia)
  ajusta_empate(p, fator)   -> aumenta o empate nos jogos equilibrados
  ajusta_gama(p, gama)      -> "afina" (gama > 1) ou "achata" (gama < 1) as probabilidades
  aprende(jogos)            -> aprende fator de empate e gama SO com os jogos passados
"""
import math

import numpy as np

FAIXA_EMPATE = (0.27, 0.33)  # jogos equilibrados: probabilidade de empate nessa faixa


def sem_margem(odds):
    inv = np.array([1 / x for x in odds], float)
    lo, hi = 0.5, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if (inv ** k).sum() > 1:
            lo = k
        else:
            hi = k
    p = inv ** k
    return p / p.sum()


def ajusta_empate(p, fator):
    p = np.array(p, float)
    if fator == 1.0 or not (FAIXA_EMPATE[0] <= p[1] <= FAIXA_EMPATE[1]):
        return p
    px = min(p[1] * fator, 0.6)
    resto = 1 - px
    outros = p[[0, 2]] / p[[0, 2]].sum() * resto
    return np.array([outros[0], px, outros[1]])


def ajusta_gama(p, gama):
    p = np.array(p, float) ** gama
    return p / p.sum()


def aplica(odds, params):
    p = sem_margem(odds)
    p = ajusta_gama(p, params.get("gama", 1.0))
    p = ajusta_empate(p, params.get("fator_empate", 1.0))
    return p


def aprende(jogos, usar_empate=True, usar_gama=True):
    """jogos: lista de (odds[3], resultado 0/1/2). Devolve params aprendidos."""
    params = {"gama": 1.0, "fator_empate": 1.0}
    base = [(sem_margem(o), y) for o, y in jogos]
    if usar_gama:
        melhor, ll_melhor = 1.0, -1e18
        for g in np.arange(0.80, 1.31, 0.02):
            ll = sum(math.log(max(ajusta_gama(p, g)[y], 1e-9)) for p, y in base)
            if ll > ll_melhor:
                melhor, ll_melhor = float(g), ll
        params["gama"] = round(melhor, 2)
    if usar_empate:
        ps = [(ajusta_gama(p, params["gama"]), y) for p, y in base]
        faixa = [(p, y) for p, y in ps if FAIXA_EMPATE[0] <= p[1] <= FAIXA_EMPATE[1]]
        if len(faixa) >= 200:
            real = np.mean([y == 1 for _, y in faixa])
            prev = np.mean([p[1] for p, _ in faixa])
            params["fator_empate"] = float(min(max(real / prev, 0.9), 1.2))
    return params
