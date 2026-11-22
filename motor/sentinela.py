"""
Camada Sentinela no motor: ajusta as probabilidades do mercado com os fatos
do jogo (desfalques, descanso, forma, clima) SO quando isso comprovadamente
acerta mais que o mercado.

Modelo (logit multinomial sobre o mercado calibrado):
  z_1 = log p_1 + b . x      z_X = log p_X + c . x_empate      z_2 = log p_2 - b . x
  x = diferencas mandante - visitante (desfalques, valor dos desfalques, dias de
      descanso, jogos em 14 dias, forma); x_empate = chuva forte.
  Pesos por maxima verossimilhanca com penalidade (ridge), so com o passado.

Portao (automatico, refeito toda semana):
  teste no tempo (treina so com concursos anteriores, re-treina a cada 10);
  a camada so liga se melhorar a perda logaritmica E o acerto, com melhora da
  perda maior que 2 erros-padrao (teste pareado jogo a jogo). Senao fica
  desligada, so registrando, e e testada de novo na semana seguinte com mais dados.

Uso:
  python motor/sentinela.py treinar   # teste no tempo + grava motor/sentinela_modelo.json
"""
import csv
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
DADOS = os.path.join(REPO, "coleta", "dados")
MODELO = os.path.join(AQUI, "sentinela_modelo.json")
sys.path.insert(0, AQUI)
from calibracao import aprende, aplica  # noqa: E402

NOMES = ["desfalques", "valor_desfalques", "descanso", "jogos_14d", "forma5", "chuva_empate"]
RIDGE = 2.0


def num(v, padrao=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return padrao


def vetor(f):
    """Fatos de um jogo -> (x para mandante/visitante, x para empate). None se a partida nao foi achada."""
    if not f or not f.get("match_id"):
        return None
    dias_c = min(num(f.get("dias_casa"), 7), 10)
    dias_f = min(num(f.get("dias_fora"), 7), 10)
    x = np.array([
        (num(f.get("desf_fora_n")) - num(f.get("desf_casa_n"))) / 3,           # + = visitante mais desfalcado
        (math.log1p(num(f.get("desf_fora_valor"))) - math.log1p(num(f.get("desf_casa_valor")))) / 2,
        (dias_c - dias_f) / 3,                                                  # + = mandante mais descansado
        (num(f.get("jogos14_fora"), 2) - num(f.get("jogos14_casa"), 2)) / 2,    # + = visitante mais cansado
        (num(f.get("forma5_casa"), 7) - num(f.get("forma5_fora"), 7)) / 5,
    ])
    chuva = 1.0 if num(f.get("chuva_mm")) >= 3 else 0.0
    return x, np.array([chuva])


def prob(p, x, xe, w):
    b, c = w[:5], w[5:]
    z = np.log(np.clip(p, 1e-9, 1)) + np.array([b @ x, c @ xe, -(b @ x)])
    z -= z.max()
    e = np.exp(z)
    return e / e.sum()


def ajusta(dados, w0=None):
    """MLE com ridge por Newton/gradiente simples (poucos parametros)."""
    w = np.zeros(6) if w0 is None else w0.copy()
    for _ in range(60):
        g = -RIDGE * w
        H = -RIDGE * np.eye(6)
        for p, x, xe, y in dados:
            q = prob(p, x, xe, w)
            # derivadas de log q[y] em relacao a b (efeito +x em 1, -x em 2) e c (efeito xe em X)
            d1 = np.concatenate([x * ((y == 0) - (y == 2) - (q[0] - q[2])), np.zeros(1)])
            d2 = np.concatenate([np.zeros(5), xe * ((y == 1) - q[1])])
            gi = d1 + d2
            g += gi
            # aproximacao de Fisher
            v = np.concatenate([x * (q[0] - q[2]), xe * q[1]])
            ex = np.concatenate([x, np.zeros(1)])
            exe = np.concatenate([np.zeros(5), xe])
            var_b = q[0] + q[2] - (q[0] - q[2]) ** 2
            H -= var_b * np.outer(ex, ex) + q[1] * (1 - q[1]) * np.outer(exe, exe) - 0 * np.outer(v, v)
        passo = np.linalg.solve(H, g)
        w = w - passo
        if np.abs(passo).max() < 1e-6:
            break
    return w


def carregar():
    fat = {}
    caminho = os.path.join(DADOS, "sentinela_jogos.csv")
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fat[(int(r["concurso"]), int(r["jogo"]))] = r
    jogos = []
    with open(os.path.join(DADOS, "arena_odds.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["resultado"]:
                continue
            k = (int(r["concurso"]), int(r["jogo"]))
            v = vetor(fat.get(k))
            if v is None:
                continue
            jogos.append((k[0], [float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])], v[0], v[1],
                          "1X2".index(r["resultado"])))
    jogos.sort(key=lambda j: j[0])
    return jogos


def treinar():
    jogos = carregar()
    if len(jogos) < 500:
        print(f"Poucos jogos com fatos ({len(jogos)}): camada fica desligada.")
        salvar(False, np.zeros(6), {"jogos": len(jogos)})
        return
    concursos = sorted({j[0] for j in jogos})
    inicio = concursos[len(concursos) // 3]
    perdas_m, perdas_s, acerto_m, acerto_s = [], [], 0, 0
    w, calib = None, None
    for i, c in enumerate(concursos):
        if c < inicio:
            continue
        if w is None or i % 10 == 0:
            passado = [j for j in jogos if j[0] < c]
            calib = aprende([(o, y) for _, o, _, _, y in passado], usar_empate=False, usar_gama=True)
            dados = [(aplica(o, calib), x, xe, y) for _, o, x, xe, y in passado]
            w = ajusta(dados, w)
        for _, o, x, xe, y in (j for j in jogos if j[0] == c):
            p = aplica(o, calib)
            q = prob(p, x, xe, w)
            perdas_m.append(-math.log(p[y]))
            perdas_s.append(-math.log(q[y]))
            acerto_m += int(np.argmax(p)) == y
            acerto_s += int(np.argmax(q)) == y
    n = len(perdas_m)
    dif = np.array(perdas_m) - np.array(perdas_s)  # + = sentinela melhor
    ep = dif.std(ddof=1) / math.sqrt(n)
    met = {"jogos_teste": n, "perda_mercado": round(float(np.mean(perdas_m)), 5),
           "perda_sentinela": round(float(np.mean(perdas_s)), 5), "melhora_perda": round(float(dif.mean()), 5),
           "erro_padrao": round(float(ep), 5), "acerto_mercado": round(acerto_m / n, 4),
           "acerto_sentinela": round(acerto_s / n, 4)}
    ativo = bool(dif.mean() > 2 * ep and acerto_s >= acerto_m)
    passado = jogos
    calib = aprende([(o, y) for _, o, _, _, y in passado], usar_empate=False, usar_gama=True)
    w_final = ajusta([(aplica(o, calib), x, xe, y) for _, o, x, xe, y in passado])
    salvar(ativo, w_final, met)
    print(json.dumps(met, indent=1))
    print("Pesos:", dict(zip(NOMES, np.round(w_final, 3))))
    print("CAMADA SENTINELA:", "LIGADA" if ativo else "desligada (nao superou o mercado com folga)")


def salvar(ativo, w, met):
    with open(MODELO, "w", encoding="utf-8") as f:
        json.dump({"ativo": ativo, "pesos": dict(zip(NOMES, [float(v) for v in w])), "metricas": met,
                   "treinado_em_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, f, indent=1)


def modelo():
    if not os.path.exists(MODELO):
        return None
    with open(MODELO, encoding="utf-8") as f:
        return json.load(f)


def aplicar(p, fatos, mod=None):
    """Probabilidade final do jogo. Sem modelo ligado ou sem fatos: devolve p sem mudar."""
    mod = mod or modelo()
    v = vetor(fatos)
    if not mod or not mod.get("ativo") or v is None:
        return np.array(p), False
    w = np.array([mod["pesos"][k] for k in NOMES])
    return prob(np.array(p), v[0], v[1], w), True


def fatos_abertos(concurso):
    """Fatos mais recentes de cada jogo do concurso aberto."""
    caminho = os.path.join(DADOS, "sentinela_aberto.csv")
    out = {}
    if not os.path.exists(caminho):
        return out
    with open(caminho, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if int(r["concurso"]) == concurso and r.get("match_id"):
                j = int(r["jogo"])
                if j not in out or r["coletado_em_utc"] > out[j]["coletado_em_utc"]:
                    out[j] = r
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "treinar":
        treinar()
    else:
        print(__doc__)
