"""
Laboratorio do empate — etapas 1 e 2.

Pergunta: alem do que a odd ja diz, alguma informacao (massa, especialistas, desfalques, descanso, forma,
clima, posicao na grade, nivel do concurso) ajuda a prever o EMPATE nos jogos da Loteca?
E o acerto do DUPLO favorito + empate?

Etapa 1 - regressao logistica com a odd como ponto de partida (offset): cada coeficiente mede o efeito
          ALEM da odd; erro-padrao agrupado por concurso.
Etapa 2 - LightGBM partindo da odd (init_score) + SHAP: procura combinacoes; so vale o teste no tempo.
Teste no tempo: treina com os concursos anteriores, testa no bloco seguinte (blocos de 20 concursos).
Saida: motor/lab_empate.md
"""
import csv
import math
import os
import sys
from collections import defaultdict

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(os.path.dirname(AQUI), "coleta", "dados")
sys.path.insert(0, AQUI)
import camada2 as c2  # noqa: E402


def ler(nome):
    return list(csv.DictReader(open(os.path.join(DADOS, nome), encoding="utf-8")))


def num(x):
    try:
        return float(x)
    except Exception:
        return np.nan


def logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def base():
    odds = c2.odds_por_concurso()
    res = {(int(r["concurso"]), int(r["jogo"])): r["resultado"] for r in ler("resultados_caixa.csv")}
    # massa: final se houver, senao a parcial mais recente
    massa = {}
    for r in ler("vovoteca_massa.csv"):
        k = (int(r["concurso"]), int(r["jogo"]))
        if r.get("soma_ok") not in ("1", "True", "true"):
            continue
        if k not in massa or r["versao"] == "final":
            massa[k] = [num(r["massa_1"]), num(r["massa_x"]), num(r["massa_2"])]
    lq = {(int(r["concurso"]), int(r["jogo"])): r for r in ler("lotequeiros_palpites.csv")}
    ar = {(int(r["concurso"]), int(r["jogo"])): r["marcas"] for r in ler("arena_palpites.csv")}
    vm = {(int(r["concurso"]), int(r["jogo"])): r["seco"] for r in ler("vovo_matriz.csv")}
    se = {(int(r["concurso"]), int(r["jogo"])): r for r in ler("sentinela_jogos.csv")}
    linhas = []
    for c, J in odds.items():
        nivel = None
        try:
            nivel = sum(1 - max(c2.prob_mercado(J[j])) for j in range(1, 15))
        except Exception:
            pass
        for j, o in J.items():
            y = res.get((c, j))
            if y not in ("1", "X", "2"):
                continue
            p = np.array(c2.prob_mercado(o))
            fav = int(np.argmax([p[0], -1, p[2]]))  # favorito entre os times (0 ou 2)
            d = {"c": c, "j": j, "y_x": int(y == "X"), "y_dup": int("1X2".index(y) in (fav, 1)),
                 "p_x": p[1], "p_dup": p[fav] + p[1], "p_fav": p[fav], "equil": abs(p[0] - p[2]),
                 "posicao": j, "nivel": nivel if nivel is not None else np.nan}
            m = massa.get((c, j))
            if m and not any(np.isnan(m)):
                s = sum(m)
                d["massa_x"] = m[1] / s
                d["massa_x_menos_odd"] = m[1] / s - p[1]
                d["massa_fav_menos_odd"] = m[fav] / s - p[fav]
                d["massa_marca_x"] = float(np.argmax(m) == 1)
            L = lq.get((c, j))
            if L:
                d["lotequeiros_seco_x"] = float(L["seco"] == "X")
                d["lotequeiros_duplo_tem_x"] = float("X" in (L["duplo"] or ""))
            if (c, j) in ar:
                d["arena_marca_x"] = float("X" in ar[(c, j)])
                d["arena_n_marcas"] = float(len(ar[(c, j)]))
            if (c, j) in vm:
                d["vovo_matriz_x"] = float(vm[(c, j)] == "X")
            S = se.get((c, j))
            if S:
                casa_fav = fav == 0
                g = lambda a, b: (num(S[a]) - num(S[b])) * (1 if casa_fav else -1)  # noqa: E731 (favorito - azarao)
                d["desfalques_valor_fav_menos_az"] = g("desf_casa_valor", "desf_fora_valor")
                d["descanso_fav_menos_az"] = g("dias_casa", "dias_fora")
                d["jogos14_fav_menos_az"] = g("jogos14_casa", "jogos14_fora")
                d["forma5_fav_menos_az"] = g("forma5_casa", "forma5_fora")
                d["h2h_n"] = num(S["h2h_n"])
                d["chuva_mm"] = num(S["chuva_mm"])
                d["altitude_m"] = num(S["altitude_m"])
                d["liga_brasil"] = float(S["liga"] in ("Série A", "Serie A") and "/" in S["mandante"]) if S["liga"] else np.nan
                d["serie_b_c"] = float(S["liga"] in ("Série B", "Série C", "Serie B", "Serie C"))
            linhas.append(d)
    linhas.sort(key=lambda d: (d["c"], d["j"]))
    return linhas


FEATS = ["massa_x_menos_odd", "massa_marca_x", "massa_fav_menos_odd", "lotequeiros_seco_x", "lotequeiros_duplo_tem_x",
         "arena_marca_x", "arena_n_marcas", "vovo_matriz_x", "desfalques_valor_fav_menos_az", "descanso_fav_menos_az",
         "jogos14_fav_menos_az", "forma5_fav_menos_az", "h2h_n", "chuva_mm", "altitude_m", "serie_b_c",
         "equil", "posicao", "nivel"]


def etapa1(L, alvo, prob):
    import statsmodels.api as sm
    out = []
    for f in FEATS:
        S = [d for d in L if f in d and not (isinstance(d[f], float) and np.isnan(d[f]))]
        if len(S) < 300:
            continue
        x = np.array([d[f] for d in S], float)
        if x.std() == 0:
            continue
        z = (x - x.mean()) / x.std()
        y = np.array([d[alvo] for d in S])
        off = np.array([logit(d[prob]) for d in S])
        grupos = np.array([d["c"] for d in S])
        try:
            m = sm.GLM(y, sm.add_constant(z), family=sm.families.Binomial(), offset=off).fit(
                cov_type="cluster", cov_kwds={"groups": grupos})
            b, se = m.params[1], m.bse[1]
            out.append((f, len(S), b, b / se))
        except Exception:
            pass
    return sorted(out, key=lambda t: -abs(t[3]))


def etapa2(L, alvo, prob):
    import lightgbm as lgb
    cs = sorted({d["c"] for d in L})
    X = np.array([[d.get(f, np.nan) for f in FEATS] for d in L], float)
    y = np.array([d[alvo] for d in L])
    off = np.array([logit(d[prob]) for d in L])
    C = np.array([d["c"] for d in L])
    inicio = cs[int(len(cs) * 0.4)]
    blocos = [c for c in cs if c >= inicio][::20]
    ganho, pred = [], np.full(len(L), np.nan)
    params = dict(objective="binary", learning_rate=0.03, num_leaves=7, min_data_in_leaf=60, feature_fraction=0.8,
                  bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1)
    for i, b0 in enumerate(blocos):
        b1 = blocos[i + 1] if i + 1 < len(blocos) else 10 ** 9
        tr, te = C < b0, (C >= b0) & (C < b1)
        if te.sum() == 0:
            continue
        ds = lgb.Dataset(X[tr], y[tr], init_score=off[tr], free_raw_data=False)
        mdl = lgb.train(params, ds, num_boost_round=150)
        z = mdl.predict(X[te], raw_score=True) + off[te]
        pred[te] = 1 / (1 + np.exp(-z))
    ok = ~np.isnan(pred)
    p0 = 1 / (1 + np.exp(-off[ok]))
    ll0 = -(y[ok] * np.log(p0) + (1 - y[ok]) * np.log(1 - p0))
    ll1 = -(y[ok] * np.log(pred[ok]) + (1 - y[ok]) * np.log(1 - pred[ok]))
    g = ll0 - ll1
    forca = g.mean() / (g.std(ddof=1) / math.sqrt(len(g)))
    # SHAP no modelo treinado com tudo (so para explicar, nao para julgar)
    import shap
    mdl = lgb.train(params, lgb.Dataset(X, y, init_score=off), num_boost_round=150)
    sv = shap.TreeExplainer(mdl).shap_values(X)
    sv = sv[1] if isinstance(sv, list) else sv
    imp = sorted(zip(FEATS, np.abs(sv).mean(0)), key=lambda t: -t[1])
    return int(ok.sum()), float(g.mean()), float(forca), imp, pred, y, ok


def main():
    L = base()
    md = ["# Laboratório do empate — etapas 1 e 2", "",
          f"Jogos da Loteca com odds e resultado: **{len(L)}** (concursos {L[0]['c']}–{L[-1]['c']}). "
          "Todas as medidas são **além do que a odd já diz** (a odd entra como ponto de partida).", ""]
    for alvo, prob, titulo in (("y_x", "p_x", "EMPATE"), ("y_dup", "p_dup", "DUPLO favorito + empate")):
        r1 = etapa1(L, alvo, prob)
        md += [f"## {titulo}", "", "### Etapa 1 — regressão logística (uma informação por vez, erro agrupado por concurso)", "",
               "Efeito = mudança no log-odds para 1 desvio-padrão da informação. |z| ≥ 2 = efeito real.", "",
               "| Informação | Jogos | Efeito | z |", "|---|---|---|---|"]
        for f, n, b, z in r1:
            md.append(f"| {f} | {n} | {b:+.3f} | {z:+.2f}{' **' if abs(z) >= 2 else ''} |")
        n, g, fz, imp, pred, y, ok = etapa2(L, alvo, prob)
        md += ["", "### Etapa 2 — LightGBM (todas as informações juntas, procura combinações), teste no tempo", "",
               f"Jogos testados (blocos de 20 concursos, só com o passado): {n}. Ganho de log-loss sobre a odd: "
               f"{g:+.5f} → **força {fz:+.2f}** ({'ganho real' if fz >= 2 else 'sem ganho comprovado'}).", "",
               "Importância SHAP (quanto cada informação mexe na previsão, modelo com todos os dados — só explica, não prova):", ""]
        md += [f"- {f}: {v:.4f}" for f, v in imp[:8]]
        md.append("")
    open(os.path.join(AQUI, "lab_empate.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
