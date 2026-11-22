"""
Rodizio previsto ANTES do jogo (a escalacao real so sai ~1h antes; a Loteca fecha antes).

Preve a chance de cada time comecar com 5+ titulares diferentes do jogo anterior usando so o que
se sabe na quinta: dias de descanso, jogos nos ultimos 14 dias e o costume do time (quantas vezes
poupou nos ultimos 8 jogos). Ajustado com coleta/dados/sentinela_jogos.csv; grava motor/rodizio.json.
Teste (1.710 jogos nunca vistos): AUC 0,70; previsao >= 50% -> poupou de fato 70% (base 28%).
A nuance "visitante poupa e mandante nao" tem sempre o mesmo sinal (o mercado superestima o
visitante), mas no teste no tempo nao melhora a previsao de forma comprovada (forca +0,4 com o
rodizio previsto; -0,5 com a escalacao real) -> so alerta.
Uso: python motor/rodizio.py   (reajusta; roda na segunda)
"""
import collections
import csv
import json
import os

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(os.path.dirname(AQUI), "coleta", "dados")
MODELO = os.path.join(AQUI, "rodizio.json")


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


def historico_trocas():
    """{time: [trocas por jogo, em ordem]} e as linhas para ajustar o modelo (so passado de cada jogo)."""
    S = list(csv.DictReader(open(os.path.join(DADOS, "sentinela_jogos.csv"), encoding="utf-8")))
    S.sort(key=lambda r: (r.get("inicio_utc") or "", int(r["concurso"]), int(r["jogo"])))
    hist, linhas = collections.defaultdict(list), []
    for r in S:
        for lado in ("casa", "fora"):
            t, tr = r[f"fot_{lado}"], _f(r[f"trocas_{lado}"])
            d, j14 = _f(r[f"dias_{lado}"]), _f(r[f"jogos14_{lado}"])
            if tr is not None and d is not None and j14 is not None:
                linhas.append((x(d, j14, hist[t]), tr >= 5))
        for lado in ("casa", "fora"):
            tr = _f(r[f"trocas_{lado}"])
            if tr is not None:
                hist[r[f"fot_{lado}"]].append(tr)
    return hist, linhas


def x(dias, j14, passado):
    h = passado[-8:]
    hab = float(np.mean([t >= 5 for t in h])) if len(h) >= 3 else None
    return [1.0, min(dias, 10) / 7, j14 / 4, hab if hab is not None else 0.2, 1.0 if hab is None else 0.0]


def ajustar():
    _, linhas = historico_trocas()
    X = np.array([l[0] for l in linhas])
    y = np.array([l[1] for l in linhas], float)
    w = np.zeros(X.shape[1])
    for _ in range(30):
        p = 1 / (1 + np.exp(-X @ w))
        w += np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + np.eye(len(w)), X.T @ (y - p) - w)
    json.dump({"pesos": [round(float(v), 4) for v in w], "jogos": len(y), "base": round(float(y.mean()), 3)},
              open(MODELO, "w"), indent=1)
    print(f"rodizio: modelo ajustado em {len(y)} jogos (poupou 5+ em {y.mean():.0%}); pesos {np.round(w, 2).tolist()}")


def chance(dias, j14, passado, w):
    return float(1 / (1 + np.exp(-np.array(x(dias, j14, passado)) @ np.array(w))))


def alertas(concurso):
    """{jogo: [texto]} para o concurso aberto (sentinela_aberto.csv)."""
    if not os.path.exists(MODELO):
        return {}
    w = json.load(open(MODELO))["pesos"]
    hist, _ = historico_trocas()
    arq = os.path.join(DADOS, "sentinela_aberto.csv")
    if not os.path.exists(arq):
        return {}
    out = {}
    for r in csv.DictReader(open(arq, encoding="utf-8")):
        if int(r["concurso"]) != int(concurso):
            continue
        ch = {}
        for lado in ("casa", "fora"):
            d, j14 = _f(r[f"dias_{lado}"]), _f(r[f"jogos14_{lado}"])
            if d is not None and j14 is not None:
                ch[lado] = chance(d, j14, hist[r[f"fot_{lado}"]], w)
        if "fora" in ch and "casa" in ch and ch["fora"] >= 0.45 and ch["casa"] < 0.30:
            out[int(r["jogo"])] = [f"visitante com {ch['fora']:.0%} de chance de poupar titulares (costume + descanso; "
                                   f"mandante {ch['casa']:.0%}) — quando o visitante poupa e o mandante não, o mercado "
                                   "costuma superestimar o visitante; favorece duplo 1X (efeito pequeno, ainda não comprovado no tempo)"]
        elif "casa" in ch and "fora" in ch and ch["casa"] >= 0.45 and ch["fora"] < 0.30:
            out[int(r["jogo"])] = [f"mandante com {ch['casa']:.0%} de chance de poupar titulares (visitante {ch['fora']:.0%})"]
    return out


if __name__ == "__main__":
    ajustar()
