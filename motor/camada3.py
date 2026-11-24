"""
Camada 3 — decisao: quanto investir em cada semana.

Para cada concurso calcula, so com o que se sabia antes (premio estimado pela Caixa,
odds, massa da Vovoteca ou estimada, modelo de ganhadores ajustado so com o passado),
a chance de 14, a chance de 13 e o retorno esperado de cada orcamento (cartela cheia).

  python motor/camada3.py testar   -> o retorno esperado preve as semanas boas? (historico)
  python motor/camada3.py [N]      -> decisao da semana para o concurso N (ou o aberto)
"""
import csv
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import camada2 as c2  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "saida")
FREQ = np.array([0.472, 0.262, 0.266])
# orcamento -> (duplos, triplos) da cartela cheia
ESCADA = {144: (3, 2), 192: (5, 1), 1296: (3, 4), 2592: (4, 4), 3888: (3, 5), 7776: (4, 5), 11664: (3, 6)}


def P_de(odds_c):
    return np.array([c2.prob_mercado(odds_c[j]) if j in odds_c else FREQ for j in range(1, 15)])


def cobertura(P, cart):
    return np.array([P[j, list(cart[j])].sum() for j in range(14)])


def chances(P, cart):
    """chance de 14 e chance de exatamente 13 da cartela cheia."""
    cov = cobertura(P, cart)
    p14 = float(np.prod(cov))
    p13 = float(sum((1 - cov[j]) * np.prod(np.delete(cov, j)) for j in range(14)))
    return p14, p13


def ganhadores_13(rat, ate):
    """razao media ganhadores_13 / ganhadores_14 previstos (13 costuma ter ~20-40x mais ganhadores)."""
    r = [(rat[c]["ganhadores_13"] + 1) / (rat[c]["ganhadores_14"] + 1) for c in rat if c < ate and rat[c]["ganhadores_13"] > 0]
    return float(np.median(r)) if r else 25.0


def valor_esperado(P, Q, coef, cart, pool14, pool13, apostas, razao13):
    """retorno esperado (R$) da cartela cheia: 14 pelo modelo de ganhadores; 13 pela razao 13/14."""
    combs = np.array(np.meshgrid(*[list(s) for s in cart], indexing="ij")).reshape(14, -1).T
    i = np.arange(14)
    lp = np.log(P[i, combs]).sum(1)
    lq = np.log(np.clip(Q[i, combs], 1e-3, 1)).sum(1)
    W14 = np.exp(c2.log_ganhadores(coef, lq, lp, math.log(pool14))) * apostas
    e14 = float((np.exp(lp) * pool14 / (W14 + 1)).sum())
    # 13: cada jogo errado vira |opcoes| combinacoes de 13; ganhadores de 13 ~ razao x ganhadores de 14
    p14, p13 = chances(P, cart)
    w14_tipico = float(np.exp((np.log(W14 + 1) * np.exp(lp)).sum() / np.exp(lp).sum()))
    n13 = np.mean([len(s) for s in cart])
    e13 = p13 * n13 * pool13 / (razao13 * w14_tipico + n13)
    return e14, e13, p14, p13


def ajusta_arrecadacao(rat, ate):
    """log(arrecadacao) ~ a + b*log(premio estimado) + c*log(mediana das 8 semanas anteriores), so com o passado."""
    cs = sorted(k for k in rat if k < ate)
    X, Y = [], []
    for i, c in enumerate(cs):
        ant = rat.get(c - 1) or {}
        est = max(ant.get("estimado_proximo") or 0, ant.get("acumulado_proximo") or 0)
        hist = [rat[k]["arrecadacao"] for k in cs[max(0, i - 8):i]]
        if est > 0 and len(hist) >= 4 and rat[c]["arrecadacao"] > 0:
            X.append([1.0, math.log(est), math.log(np.median(hist))])
            Y.append(math.log(rat[c]["arrecadacao"]))
    return np.linalg.lstsq(np.array(X), np.array(Y), rcond=None)[0] if len(X) > 20 else None


def arrecadacao_prevista(rat, c, pool14, carr):
    hist = [rat[k]["arrecadacao"] for k in sorted(rat) if k < c][-8:]
    med = float(np.median(hist)) if hist else rat.get(c, {}).get("arrecadacao", 1e6)
    if carr is None:
        return med
    return float(math.exp(carr @ [1.0, math.log(pool14), math.log(med)]))


def montar(c, odds, massa, rat, prm, coef, razao13, carr=None):
    if len(odds.get(c, {})) < 10:
        return None
    P = P_de(odds[c])
    Q = np.array([massa[c][j] for j in range(1, 15)]) if len(massa.get(c, {})) == 14 else \
        np.array([c2.massa_estimada(p, prm) for p in P])
    ant = rat.get(c - 1) or {}
    pool14 = max(ant.get("estimado_proximo") or 0, ant.get("acumulado_proximo") or 0)
    if pool14 <= 0:
        return None
    hist = [rat[k] for k in sorted(rat) if k < c][-8:]
    arrec = arrecadacao_prevista(rat, c, pool14, carr)
    pool13 = float(np.median([h["pool_13"] for h in hist if h["pool_13"] > 0])) if hist else 0.0
    out = {"concurso": c, "pool14": pool14, "pool13": pool13, "apostas": arrec / c2.PRECO, "orc": {}}
    for orc, (d, t) in ESCADA.items():
        cart = c2.cartela(P, d, t)
        e14, e13, p14, p13 = valor_esperado(P, Q, coef, cart, pool14, pool13, arrec / c2.PRECO, razao13)
        out["orc"][orc] = {"cartela": cart, "e14": e14, "e13": e13, "p14": p14, "p13": p13,
                           "retorno": (e14 + e13) / orc}
    return out, P, Q


def resultado(odds_c, rat_c):
    try:
        return [("1", "X", "2").index(odds_c[j]["resultado"]) for j in range(1, 15)]
    except Exception:
        return None


def resultados_cef():
    H = json.load(open(os.path.join(os.path.dirname(AQUI), "data", "historico_cef.json")))["concursos"]
    res = {}
    for k, c in H.items():
        js = sorted(c["jogos"], key=lambda j: j["nuSequencial"])
        if len(js) == 14 and all(j["nuGolEquipeUm"] is not None for j in js):
            res[int(k)] = [0 if j["nuGolEquipeUm"] > j["nuGolEquipeDois"] else
                           (1 if j["nuGolEquipeUm"] == j["nuGolEquipeDois"] else 2) for j in js]
    return res


def pago(cart, res, R):
    ok = [res[j] in cart[j] for j in range(14)]
    er = ok.count(False)
    pr = 0.0
    if er == 0:
        pr += R["pool_14"] / (R["ganhadores_14"] + 1)
        n13 = sum(len(s) - 1 for s in cart)
    elif er == 1:
        n13 = len(cart[ok.index(False)])
    else:
        n13 = 0
    if n13 and R["pool_13"] > 0:
        pr += n13 * R["pool_13"] / (R["ganhadores_13"] + n13)
    return 14 - er, pr


def historico():
    """lista por concurso com previsoes (so passado) e o que pagou de fato."""
    odds, massa, rat, res = c2.odds_por_concurso(), c2.massa_por_concurso(), c2.rateio(), resultados_cef()
    X, Y, cs_g = c2.dados_ganhadores(odds, massa, rat)
    pares_por_c = {cc: [(c2.prob_mercado(odds[cc][j]), massa[cc][j]) for j in range(1, 15)] for cc in cs_g}
    linhas, cache = [], {}
    for c in sorted(set(odds) & set(rat) & set(res)):
        passado = [i for i, cc in enumerate(cs_g) if cc < c]
        if len(passado) < 30:
            continue
        chave = len(passado) // 10  # reajusta os modelos a cada 10 concursos novos (so com o passado)
        if chave not in cache:
            coef = c2.ajusta_ganhadores(X[passado], Y[passado])
            prm = c2.ajusta_massa([p for cc in cs_g[:len(passado)][-100:] for p in pares_por_c[cc]])
            cache[chave] = (coef, prm, ganhadores_13(rat, c), ajusta_arrecadacao(rat, c))
        coef, prm, razao13, carr = cache[chave]
        m = montar(c, odds, massa, rat, prm, coef, razao13, carr)
        if not m:
            continue
        info = m[0]
        for orc, o in info["orc"].items():
            o["pontos"], o["pago"] = pago(o["cartela"], res[c], rat[c])
        linhas.append(info)
    return linhas


# ------------------------------------------------------------------ decisao da semana
CONFIG = os.path.join(AQUI, "camada3_config.json")
PADRAO = {"modo": "cofrinho", "deposito_semana": 200, "retorno_minimo": 1.0, "inicio_concurso": 1285,
          "orcamento_mensal": 800, "minimo_semana": 0, "teto_semana": 200,
          "obs": "modo cofrinho: guarda deposito_semana toda semana e so aposta quando o retorno esperado passa de "
                 "retorno_minimo (o jogo se paga em media). modo semanal: aposta toda semana dentro do orcamento_mensal."}
APOSTAS = os.path.join(AQUI, "apostas")
RECOMENDADAS = os.path.join(APOSTAS, "recomendadas.csv")
HIST = os.path.join(AQUI, "camada3_historico.csv")  # retorno esperado de cada semana, calculado antes do concurso
JOGADAS = os.path.join(APOSTAS, "jogadas.csv")
CAMPOS_AP = ["concurso", "origem", "orcamento", "estrutura"] + [f"jogo_{j}" for j in range(1, 15)]


def config():
    if not os.path.exists(CONFIG):
        json.dump(PADRAO, open(CONFIG, "w"), indent=1, ensure_ascii=False)
    return {**PADRAO, **json.load(open(CONFIG))}


def gasto_no_mes(c, rat):
    """soma das apostas registradas (jogadas; se nao houver, as recomendadas) nos 3 concursos anteriores."""
    arq = JOGADAS if os.path.exists(JOGADAS) else RECOMENDADAS
    if not os.path.exists(arq):
        return 0.0
    tot = 0.0
    for r in csv.DictReader(open(arq, encoding="utf-8")):
        if c - 3 <= int(r["concurso"]) < c:
            tot += float(r["orcamento"])
    return tot


def decidir(c=None):
    odds, massa, rat = c2.odds_por_concurso(), c2.massa_por_concurso(), c2.rateio()
    if c is None:
        import glob
        feitos = sorted(int(os.path.basename(a)[9:-4]) for a in glob.glob(os.path.join(SAIDA, "concurso_*.csv"))
                        if os.path.basename(a)[9:-4].isdigit())
        c = feitos[-1] if feitos else max(odds) + 1
    if len(odds.get(c, {})) < 14:
        prev = c2.ler(os.path.join(SAIDA, f"concurso_{c}.csv"))
        if len(prev) == 14 and all(r.get("odd_1") for r in prev):
            odds[c] = {int(r["jogo"]): r for r in prev}
    if len(odds.get(c, {})) < 10:
        print(f"Concurso {c}: sem odds suficientes para decidir.")
        return
    X, Y, cs = c2.dados_ganhadores(odds, massa, rat)
    coef = c2.ajusta_ganhadores(X, Y)
    prm = c2.ajusta_massa([(c2.prob_mercado(odds[cc][j]), massa[cc][j]) for cc in cs[-100:] for j in range(1, 15)])
    m = montar(c, odds, massa, rat, prm, coef, ganhadores_13(rat, c), ajusta_arrecadacao(rat, c))
    if not m:
        print(f"Concurso {c}: sem premio estimado da Caixa ainda.")
        return
    info = m[0]
    cfg = config()
    # posicao da semana entre as ultimas 52 (retorno esperado do R$ 2.592)
    r = info["orc"][2592]["retorno"]
    hist = {}
    if os.path.exists(HIST):
        hist = {int(x["concurso"]): x for x in csv.DictReader(open(HIST, encoding="utf-8"))}
    hist_r = [float(hist[k]["retorno_2592"]) for k in sorted(hist) if k < c][-52:]
    hist[c] = {"concurso": c, "premio_estimado": round(info["pool14"]), "retorno_2592": round(r, 4)}
    with open(HIST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["concurso", "premio_estimado", "retorno_2592"])
        w.writeheader()
        w.writerows(hist[k] for k in sorted(hist))
    pct = float(np.mean([x <= r for x in hist_r])) if hist_r else None
    if cfg.get("modo") == "cofrinho":
        return decidir_cofrinho(c, info, cfg, r, pct, hist_r)
    base = max([o for o in ESCADA if o <= cfg["orcamento_mensal"] / 4] or [min(ESCADA)])
    if r >= 1.0:
        nivel, alvo = "excepcional (retorno esperado acima de 100%)", cfg["teto_semana"]
    elif pct is not None and pct >= 0.9:
        nivel, alvo = "forte (entre as 10% melhores do último ano)", min(cfg["teto_semana"], max(o for o in ESCADA if o <= base * 3))
    elif pct is not None and pct >= 2 / 3:
        nivel, alvo = "boa (terço de cima)", min(cfg["teto_semana"], min(o for o in ESCADA if o > base) if base < max(ESCADA) else base)
    elif pct is not None and pct < 1 / 3:
        nivel, alvo = "fraca (terço de baixo)", cfg["minimo_semana"]
    else:
        nivel, alvo = "média", base
    sobra = cfg["orcamento_mensal"] - gasto_no_mes(c, rat)  # o orcamento do mes vale sempre, ate na semana excepcional
    alvo = max([o for o in ESCADA if o <= min(alvo, max(sobra, 0))] or [0]) if alvo else 0
    md = [f"# Concurso {c} — camada 3 (decisão da semana)", "",
          f"Prêmio de 14 estimado pela Caixa: **R$ {info['pool14']:,.0f}** · apostas previstas: {info['apostas']:,.0f} combinações "
          "(a arrecadação sobe com o prêmio).".replace(",", "."), "",
          f"**Semana {nivel}**" + (f" — melhor que {pct:.0%} das últimas {len(hist_r)} semanas." if pct is not None else "."), "",
          "| Orçamento | Cartela | Chance de 14 | Chance de 13 | Retorno esperado (14 + 13) |", "|---|---|---|---|---|"]
    for orc, o in info["orc"].items():
        d, t = ESCADA[orc]
        md.append(f"| R$ {orc:,} | {14 - d - t}+{d}+{t} | {o['p14']:.2%} | {o['p13']:.1%} | {o['retorno']:.0%} |".replace(",", "."))
    if alvo:
        d, t = ESCADA[alvo]
        md += ["", f"## Recomendação: **R$ {alvo:,}** — cartela {14 - d - t}+{d}+{t}".replace(",", "."), "",
               (f"Seu orçamento: R$ {cfg['orcamento_mensal']:,.0f} por mês · mínimo R$ {cfg['minimo_semana']:,.0f} · "
                f"teto R$ {cfg['teto_semana']:,.0f} por semana").replace(",", ".") + " (mude em `motor/camada3_config.json`)."]
        cart = info["orc"][alvo]["cartela"]
        os.makedirs(APOSTAS, exist_ok=True)
        linhas = list(csv.DictReader(open(RECOMENDADAS, encoding="utf-8"))) if os.path.exists(RECOMENDADAS) else []
        linhas = [x for x in linhas if int(x["concurso"]) != c] + [dict(
            concurso=c, origem="recomendada", orcamento=alvo, estrutura=f"{14 - d - t}+{d}+{t}",
            **{f"jogo_{j + 1}": "".join("1X2"[k] for k in sorted(cart[j])) for j in range(14)})]
        with open(RECOMENDADAS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_AP)
            w.writeheader()
            w.writerows(sorted(linhas, key=lambda x: int(x["concurso"])))
    else:
        md += ["", "## Recomendação: **não apostar nesta semana** (orçamento do mês já usado ou semana fraca com mínimo zero)."]
    md += ["", "Como ler: retorno esperado = quanto volta em média para cada R$ 1 apostado, contando a divisão do prêmio "
               "com os outros ganhadores. No histórico (176 concursos) ele fica perto de 27% numa semana normal; só 4 "
               "semanas passaram de 100%, todas com prêmio acumulado muito alto. O sistema faz mais pontos que os sites, "
               "mas a Loteca devolve menos do que arrecada: aposte só o orçamento definido.", "",
           "Para o jogo por valor (menos chance, prêmio mais inteiro) veja a camada 2."]
    open(os.path.join(SAIDA, f"concurso_{c}_decisao.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


def cofre(c, cfg):
    """saldo guardado antes do concurso c: depositos desde inicio_concurso menos o que foi apostado."""
    ini = int(cfg["inicio_concurso"])
    dep = cfg["deposito_semana"] * max(0, c - ini + 1)
    gasto = 0.0
    arq = JOGADAS if os.path.exists(JOGADAS) else RECOMENDADAS
    if os.path.exists(arq):
        gasto = sum(float(x["orcamento"]) for x in csv.DictReader(open(arq, encoding="utf-8"))
                    if ini <= int(x["concurso"]) < c)
    return dep - gasto


def decidir_cofrinho(c, info, cfg, r, pct, hist_r):
    saldo = cofre(c, cfg)
    minimo = cfg["retorno_minimo"]
    boas = [(o, v) for o, v in info["orc"].items() if v["retorno"] >= minimo and o <= saldo]
    alvo = max(boas, key=lambda t: t[1]["e14"] + t[1]["e13"] - t[0])[0] if boas else 0
    melhor = max(info["orc"].items(), key=lambda t: t[1]["retorno"])
    md = [f"# Concurso {c} — camada 3 (decisão da semana · modo cofrinho)", "",
          f"Prêmio de 14 estimado pela Caixa: **R$ {info['pool14']:,.0f}** · apostas previstas: {info['apostas']:,.0f}.".replace(",", "."), "",
          (f"Cofrinho: R$ {cfg['deposito_semana']:,.0f} por semana desde o concurso {cfg['inicio_concurso']} · "
           f"saldo guardado: **R$ {saldo:,.0f}** · só aposta quando o retorno esperado passa de {minimo:.0%}.").replace(",", "."), "",
          "| Orçamento | Cartela | Chance de 14 | Chance de 13 | Retorno esperado (14 + 13) |", "|---|---|---|---|---|"]
    for orc, o in info["orc"].items():
        d, t = ESCADA[orc]
        md.append(f"| R$ {orc:,} | {14 - d - t}+{d}+{t} | {o['p14']:.2%} | {o['p13']:.1%} | {o['retorno']:.0%} |".replace(",", "."))
    if alvo:
        d, t = ESCADA[alvo]
        md += ["", f"## Recomendação: **apostar R$ {alvo:,}** do cofrinho — cartela {14 - d - t}+{d}+{t}".replace(",", "."), "",
               f"Semana em que o jogo se paga em média: retorno esperado de {info['orc'][alvo]['retorno']:.0%}."]
        cart = info["orc"][alvo]["cartela"]
        os.makedirs(APOSTAS, exist_ok=True)
        linhas = list(csv.DictReader(open(RECOMENDADAS, encoding="utf-8"))) if os.path.exists(RECOMENDADAS) else []
        linhas = [x for x in linhas if int(x["concurso"]) != c] + [dict(
            concurso=c, origem="recomendada", orcamento=alvo, estrutura=f"{14 - d - t}+{d}+{t}",
            **{f"jogo_{j + 1}": "".join("1X2"[k] for k in sorted(cart[j])) for j in range(14)})]
        with open(RECOMENDADAS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_AP)
            w.writeheader()
            w.writerows(sorted(linhas, key=lambda x: int(x["concurso"])))
    else:
        motivo = (f"o melhor retorno esperado desta semana é {melhor[1]['retorno']:.0%} (R$ {melhor[0]:,}) — abaixo de {minimo:.0%}"
                  if melhor[1]["retorno"] < minimo else f"o saldo (R$ {saldo:,.0f}) ainda não cobre a cartela que se paga").replace(",", ".")
        md += ["", f"## Recomendação: **não apostar — guardar R$ {cfg['deposito_semana']:,.0f}**".replace(",", "."), "",
               f"Motivo: {motivo}."]
    md += ["", "Por que assim: com R$ 200 por semana toda semana, nenhuma cartela se paga (retorno esperado 18–27%; "
               "R$ 144 9+3+2 faz 13 ou 14 cerca de 2 vezes por ano). Guardando e apostando só quando o retorno esperado "
               "passa de 100% (prêmio acumulado alto), o histórico de 176 concursos teve 4 apostas de R$ 2.592: gasto "
               "R$ 10.368, prêmios R$ 15.176 (um 14 no 1210). Amostra pequena: é o único caminho que se paga em média, "
               "não uma garantia."]
    open(os.path.join(SAIDA, f"concurso_{c}_decisao.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump({"concurso": c, "modo": "cofrinho", "premio": info["pool14"], "saldo": saldo, "deposito": cfg["deposito_semana"],
               "retorno_minimo": minimo, "apostar": alvo, "percentil": pct,
               "orcamentos": [{"valor": o, "estrutura": f"{14 - sum(ESCADA[o])}+{ESCADA[o][0]}+{ESCADA[o][1]}",
                               "p14": v["p14"], "p13": v["p13"], "retorno": v["retorno"]} for o, v in info["orc"].items()],
               "motivo": None if alvo else motivo},
              open(os.path.join(SAIDA, f"concurso_{c}_decisao.json"), "w"), ensure_ascii=False)
    print("\n".join(md))


# ------------------------------------------------------------------ conferencia e placar financeiro
def conferir():
    """Confere recomendadas (o que o sistema mandou jogar) e jogadas (o que foi registrado de fato)
    com o resultado e o rateio oficiais. Grava motor/placar_financeiro.md."""
    rat, res = c2.rateio(), resultados_cef()
    md = ["# Placar financeiro", "",
          "Conferido com o resultado e o rateio oficiais da Caixa. 'Recomendada' = o jogo que a camada 3 indicou "
          "(conta como se tivesse sido jogado); 'Jogada' = o que você registrou em `motor/apostas/jogadas.csv`.", ""]
    for nome, arq in (("Recomendada", RECOMENDADAS), ("Jogada", JOGADAS)):
        if not os.path.exists(arq):
            continue
        linhas = list(csv.DictReader(open(arq, encoding="utf-8")))
        if not linhas:
            continue
        md += [f"## {nome}", "", "| Concurso | Aposta | Pontos | Prêmio | Saldo do concurso | Saldo acumulado |",
               "|---|---|---|---|---|---|"]
        acum = gasto = ganho = 0.0
        for x in sorted(linhas, key=lambda y: int(y["concurso"])):
            c = int(x["concurso"])
            cart = [set("1X2".index(k) for k in x[f"jogo_{j}"]) for j in range(1, 15)]
            if c not in res or c not in rat:
                md.append(f"| {c} | R$ {float(x['orcamento']):,.0f} | aguardando | — | — | — |".replace(",", "."))
                continue
            R = rat[c]
            ok = [res[c][j] in cart[j] for j in range(14)]
            er = ok.count(False)
            pr = 0.0
            if er == 0:  # o premio oficial por ganhador ja inclui a nossa aposta
                pr += R["premio_14"] + sum(len(s) - 1 for s in cart) * R["premio_13"]
            elif er == 1:
                pr += len(cart[ok.index(False)]) * R["premio_13"]
            v = float(x["orcamento"])
            gasto += v
            ganho += pr
            acum += pr - v
            md.append(f"| {c} | R$ {v:,.0f} | {14 - er} | R$ {pr:,.0f} | R$ {pr - v:,.0f} | R$ {acum:,.0f} |".replace(",", "."))
        if gasto:
            md += ["", f"Total: gasto R$ {gasto:,.0f} · prêmios R$ {ganho:,.0f} · retorno {ganho / gasto:.0%}.".replace(",", "."), ""]
    open(os.path.join(AQUI, "placar_financeiro.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


def testar():
    L = historico()
    with open(HIST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["concurso", "premio_estimado", "retorno_2592"])
        w.writeheader()
        for l in L:
            w.writerow({"concurso": l["concurso"], "premio_estimado": round(l["pool14"]),
                        "retorno_2592": round(l["orc"][2592]["retorno"], 4)})
    md = ["# Camada 3 — teste no histórico (só informação anterior a cada concurso)", "",
          f"Concursos: {len(L)}. Modelo de ganhadores com o termo de concentração (lq²), arrecadação prevista pelo prêmio estimado.", "",
          "| Orçamento | 14 previstos | 14 feitos | 13 previstos | 13 feitos | Retorno esperado | Retorno real |", "|---|---|---|---|---|---|---|"]
    for orc in ESCADA:
        cu = orc * len(L)
        md.append(f"| R$ {orc:,} | {sum(l['orc'][orc]['p14'] for l in L):.1f} | {sum(l['orc'][orc]['pontos'] == 14 for l in L)} | "
                  f"{sum(l['orc'][orc]['p13'] for l in L):.1f} | {sum(l['orc'][orc]['pontos'] == 13 for l in L)} | "
                  f"{sum(l['orc'][orc]['e14'] + l['orc'][orc]['e13'] for l in L) / cu:.0%} | {sum(l['orc'][orc]['pago'] for l in L) / cu:.0%} |".replace(",", "."))
    rs = np.array([l["orc"][2592]["retorno"] for l in L])
    md += ["", f"Semanas com retorno esperado ≥ 100%: {int((rs >= 1).sum())} de {len(L)}: " +
           ", ".join(f"{l['concurso']} (prêmio R$ {l['pool14'] / 1e6:.1f} mi)" for l in L if l["orc"][2592]["retorno"] >= 1),
           "", "O retorno real depende de poucos 14 (1152 e 1267 pagaram R$ 535 mil, em semanas de retorno esperado baixo) — "
           "não serve para julgar a regra; a chance de 14/13 e os ganhadores previstos são conferidos à parte."]
    open(os.path.join(AQUI, "camada3.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "testar":
        testar()
    elif len(sys.argv) > 1 and sys.argv[1] == "conferir":
        conferir()
    else:
        decidir(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None)
