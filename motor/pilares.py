"""
Pilares sem odds: monta, para cada jogo, so com informacao de ANTES do jogo, varias vertentes de analise e testa
cada uma no tempo (walk-forward: ajusta so com o passado e confere no mes seguinte, nunca visto).

Pilares (todos sem odds):
  elo        forca propria (Elo com todos os jogos da base, mando incluso)
  xg         qualidade das chances: xG a favor e contra (ultimos 8 jogos) e saldo de xG
  xg_mando   xG do mandante so em casa e do visitante so fora (ultimos 6)
  eficiencia gols - xG (quem esta marcando acima/abaixo do que cria; tende a voltar ao normal)
  dominio    toques na area adversaria / total (ultimos 8)
  forma      pontos nos ultimos 5 (geral) e em casa/fora (ultimos 5 do mando)
  calendario dias de descanso, jogos em 14 dias, copa (Libertadores/Sul-Americana/Copa do Brasil) ate 4 dias
             antes ou depois
  viagem     distancia (km) do estadio do visitante ate o estadio do jogo
  gramado    jogo em gramado sintetico (e visitante sem costume)
  arbitro    taxa historica de vitoria do mandante e de vermelhos do arbitro (so jogos anteriores dele)

Referencia: odds de fechamento (football-data), so para comparar nos jogos em que existem.
Saida: motor/pilares.md e motor/pilares.json (pesos e resultado do teste).
"""
import collections
import csv
import datetime
import json
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
BASE = os.environ.get('PILARES_BASE') or os.path.join(RAIZ, 'coleta', 'dados', 'fotmob_jogos.csv')
COPAS = {"9067", "45", "299"}
GRUPOS = collections.OrderedDict([
    ("elo", ["elo"]),
    ("xg", ["xg_saldo", "xg_pro", "xg_contra"]),
    ("xg_mando", ["xgm_saldo"]),
    ("eficiencia", ["efic"]),
    ("dominio", ["dom"]),
    ("forma", ["forma5", "forma_mando"]),
    ("calendario", ["descanso", "j14", "copa"]),
    ("viagem", ["viagem"]),
    ("gramado", ["sintetico"]),
    ("arbitro", ["arb_casa", "arb_verm"]),
])
NOMES = {"elo": "Força própria (Elo)", "xg": "Qualidade das chances (xG)", "xg_mando": "xG em casa / fora",
         "eficiencia": "Eficiência (gols − xG)", "dominio": "Domínio (toques na área)", "forma": "Forma (geral e mando)",
         "calendario": "Calendário (descanso, copa)", "viagem": "Distância da viagem", "gramado": "Gramado sintético",
         "arbitro": "Árbitro"}


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def km(a, b, c, d):
    r = math.pi / 180
    h = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(min(1, h)))


def carregar(extra=()):
    J = []
    for r in list(csv.DictReader(open(BASE, encoding="utf-8"))) + list(extra):
        try:
            r["dt"] = datetime.datetime.strptime(r["data_utc"][:16], "%Y-%m-%dT%H:%M")
            if not r.get("futuro"):
                r["gc"], r["gf"] = int(r["gc"]), int(r["gf"])
        except Exception:
            continue
        J.append(r)
    J.sort(key=lambda r: (r["dt"], 0 if r.get("futuro") else 1))
    vistos, out = set(), []
    for r in J:
        if r["match_id"] not in vistos:
            vistos.add(r["match_id"])
            out.append(r)
    return out


def montar(J):
    hist = collections.defaultdict(list)  # time -> lista de (dt, casa?, gp, gs, xgp, xgs, area_p, area_s, liga)
    agenda = collections.defaultdict(list)  # time -> datas de jogos de copa
    for r in J:
        if r["liga_id"] in COPAS:
            agenda[r["casa_id"]].append(r["dt"])
            agenda[r["fora_id"]].append(r["dt"])
    casa_local = collections.defaultdict(collections.Counter)  # time -> estadio (lat,lon) mais comum em casa
    elo = collections.defaultdict(lambda: 1500.0)
    arb = collections.defaultdict(lambda: [0, 0, 0])  # jogos, vitorias mandante, vermelhos
    sint_casa = collections.Counter()
    linhas = []
    for r in J:
        c, v = r["casa_id"], r["fora_id"]
        hc, hv = hist[c], hist[v]
        ok = len(hc) >= 5 and len(hv) >= 5

        def media(h, i, n=8, so=None):
            xs = [t[i] for t in h if (so is None or t[1] == so) and t[i] is not None][-n:]
            return sum(xs) / len(xs) if xs else None

        def pts(h, n=5, so=None):
            xs = [3 if t[2] > t[3] else (1 if t[2] == t[3] else 0) for t in h if so is None or t[1] == so][-n:]
            return sum(xs) / len(xs) if xs else None

        x = {}
        if ok:
            xpc, xsc, xpv, xsv = media(hc, 4), media(hc, 5), media(hv, 4), media(hv, 5)
            if None not in (xpc, xsc, xpv, xsv):
                x["xg_saldo"] = (xpc - xsc) - (xpv - xsv)
                x["xg_pro"] = xpc - xpv
                x["xg_contra"] = xsv - xsc
            a, b, cc, d = media(hc, 4, 6, True), media(hc, 5, 6, True), media(hv, 4, 6, False), media(hv, 5, 6, False)
            if None not in (a, b, cc, d):
                x["xgm_saldo"] = (a - b) - (cc - d)
            ec = [t[2] - t[4] for t in hc if t[4] is not None][-10:]
            ev = [t[2] - t[4] for t in hv if t[4] is not None][-10:]
            if ec and ev:
                x["efic"] = sum(ec) / len(ec) - sum(ev) / len(ev)
            dc = [t[6] / (t[6] + t[7]) for t in hc if t[6] is not None and t[7] is not None and t[6] + t[7] > 0][-8:]
            dv = [t[6] / (t[6] + t[7]) for t in hv if t[6] is not None and t[7] is not None and t[6] + t[7] > 0][-8:]
            if dc and dv:
                x["dom"] = sum(dc) / len(dc) - sum(dv) / len(dv)
            x["forma5"] = pts(hc) - pts(hv)
            pm, pv = pts(hc, 5, True), pts(hv, 5, False)
            if pm is not None and pv is not None:
                x["forma_mando"] = pm - pv
            desc = lambda h: min(15.0, (r["dt"] - h[-1][0]).total_seconds() / 86400)
            x["descanso"] = desc(hc) - desc(hv)
            j14 = lambda h: sum(1 for t in h if (r["dt"] - t[0]).days <= 14)
            x["j14"] = j14(hc) - j14(hv)
            copa = lambda t: any(abs((d - r["dt"]).total_seconds()) <= 4 * 86400 and d != r["dt"] for d in agenda[t])
            x["copa"] = (1 if copa(c) else 0) - (1 if copa(v) else 0)
            la, lo = f(r["lat"]), f(r["lon"])
            if casa_local[v] and la is not None and lo is not None:
                (va, vo), _ = casa_local[v].most_common(1)[0]
                x["viagem"] = km(va, vo, la, lo) / 1000
            sint = r.get("gramado", "").lower() in ("artificial", "artificial turf", "synthetic")
            x["sintetico"] = (1 if sint else 0) * (0 if sint_casa[v] > 0 else 1)
            a3 = arb.get(r["arbitro"]) if r["arbitro"] else None
            if a3 and a3[0] >= 5:
                x["arb_casa"] = (a3[1] + 4.6 * 0.45) / (a3[0] + 4.6) - 0.45
                x["arb_verm"] = (a3[2] + 4.6 * 0.2) / (a3[0] + 4.6) - 0.2
            x["elo"] = (elo[c] - elo[v]) / 100
        if r.get("futuro"):
            linhas.append({"r": r, "x": x, "y": -1, "ok": ok, "hc": len(hc), "hv": len(hv)})
            continue
        y = 0 if r["gc"] > r["gf"] else (1 if r["gc"] == r["gf"] else 2)
        if ok:
            linhas.append({"r": r, "x": x, "y": y})
        # atualiza historico com o jogo (depois de montar as variaveis)
        xc, xv = f(r["xg_c"]), f(r["xg_f"])
        ac, av = f(r["area_c"]), f(r["area_f"])
        hist[c].append((r["dt"], True, r["gc"], r["gf"], xc, xv, ac, av, r["liga_id"]))
        hist[v].append((r["dt"], False, r["gf"], r["gc"], xv, xc, av, ac, r["liga_id"]))
        la, lo = f(r["lat"]), f(r["lon"])
        if la is not None and lo is not None:
            casa_local[c][(round(la, 2), round(lo, 2))] += 1
        if r.get("gramado", "").lower() in ("artificial", "artificial turf", "synthetic"):
            sint_casa[c] += 1
        e = 1 / (1 + 10 ** (-(elo[c] + 65 - elo[v]) / 400))
        s = 1 if y == 0 else (0.5 if y == 1 else 0)
        k = 24 * (1 + 0.5 * min(3, abs(r["gc"] - r["gf"])) / 3)
        elo[c] += k * (s - e)
        elo[v] -= k * (s - e)
        if r["arbitro"]:
            a3 = arb[r["arbitro"]]
            a3[0] += 1
            a3[1] += 1 if y == 0 else 0
            a3[2] += (f(r["verm_c"]) or 0) + (f(r["verm_f"]) or 0)
    return linhas


def matriz(L, cols):
    X = np.array([[l["x"].get(c, 0.0) for c in cols] for l in L], float)
    M = np.array([[1.0 if c in l["x"] else 0.0 for c in cols] for l in L], float)
    return X, M


def ajustar(X, y, lam=3.0, it=400):
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    W = np.zeros((d + 1, 3))
    Y = np.eye(3)[y]
    for _ in range(it):
        Z = Xb @ W
        Z -= Z.max(1, keepdims=True)
        P = np.exp(Z)
        P /= P.sum(1, keepdims=True)
        G = Xb.T @ (P - Y) / n
        G[:-1] += lam * W[:-1] / n
        W -= 0.6 * G
    return W


def prever(W, X):
    Xb = np.hstack([X, np.ones((len(X), 1))])
    Z = Xb @ W
    Z -= Z.max(1, keepdims=True)
    P = np.exp(Z)
    return P / P.sum(1, keepdims=True)


def walk(L, cols, ini_frac=0.4):
    """Ajusta com tudo antes de cada mes e preve o mes. Devolve probabilidades e indices testados."""
    X, M = matriz(L, cols)
    mu = np.array([X[M[:, j] > 0, j].mean() if (M[:, j] > 0).any() else 0 for j in range(X.shape[1])])
    sd = np.array([X[M[:, j] > 0, j].std() + 1e-9 if (M[:, j] > 0).any() else 1 for j in range(X.shape[1])])
    Z = np.where(M > 0, (X - mu) / sd, 0.0)
    y = np.array([l["y"] for l in L])
    meses = [(l["r"]["dt"].year, l["r"]["dt"].month) for l in L]
    ordem = sorted(set(meses))
    ini = ordem[int(len(ordem) * ini_frac)]
    P = np.zeros((len(L), 3))
    tst = np.zeros(len(L), bool)
    for m in ordem:
        if m < ini:
            continue
        tr = np.array([mm < m for mm in meses])
        te = np.array([mm == m for mm in meses])
        if tr.sum() < 500 or not te.any():
            continue
        W = ajustar(Z[tr], y[tr])
        P[te] = prever(W, Z[te])
        tst |= te
    Wf = ajustar(Z, y)
    return P, tst, Wf, mu, sd


def odds_ref(L):
    """Odd de fechamento (sem margem) do football-data para os jogos que casarem por data e nomes."""
    try:
        import fd_base
        from calibracao import sem_margem
    except Exception:
        return [None] * len(L)
    por_dia = collections.defaultdict(list)
    for g in fd_base.jogos():
        o = g.get("ps") or g.get("avg") or g.get("b365c") or g.get("avgo") or g.get("b365o")
        if o and g["gc"] is not None:
            por_dia[g["d"]].append((g, o))
    out = []
    for l in L:
        r = l["r"]
        best, bs = None, 0
        for dd in (0, -1, 1):
            for g, o in por_dia.get((r["dt"] + datetime.timedelta(days=dd)).date(), []):
                s = fd_base.sim(r["casa"], g["casa"]) + fd_base.sim(r["fora"], g["fora"])
                if s > bs and g["gc"] == r["gc"] and g["gf"] == r["gf"]:
                    best, bs = o, s
        out.append(list(sem_margem(best)) if best and bs >= 1.5 else None)
    return out


def met(P, y):
    a = float((P.argmax(1) == y).mean())
    ll = float(-np.log(np.clip(P[np.arange(len(y)), y], 1e-9, 1)).mean())
    return a, ll


def forca(P1, P0, y):
    """Ganho de log-loss de P1 sobre P0 por jogo e sua forca (ganho medio / erro padrao)."""
    g = np.log(np.clip(P1[np.arange(len(y)), y], 1e-9, 1)) - np.log(np.clip(P0[np.arange(len(y)), y], 1e-9, 1))
    return float(g.mean()), float(g.mean() / (g.std(ddof=1) / math.sqrt(len(g))))


def testar():
    J = carregar()
    L = montar(J)
    y = np.array([l["y"] for l in L])
    todas = [c for g in GRUPOS.values() for c in g]
    print(f"base: {len(J)} jogos; com historico suficiente: {len(L)}")
    res = {"jogos_base": len(J), "jogos_modelo": len(L)}
    Pt, tst, Wf, mu, sd = walk(L, todas)
    yt = y[tst]
    fr = np.bincount(y[~tst], minlength=3) / max(1, (~tst).sum())
    Pfr = np.tile(fr, (tst.sum(), 1))
    linhas_md = []
    a0, l0 = met(Pfr, yt)
    a1, l1 = met(Pt[tst], yt)
    g1, f1 = forca(Pt[tst], Pfr, yt)
    linhas_md.append(("Só a frequência (chute)", a0, l0, "", ""))
    linhas_md.append(("**Todos os pilares sem odds**", a1, l1, g1, f1))
    res["todos"] = {"acerto": a1, "logloss": l1, "forca_vs_chute": f1}
    # cada pilar sozinho e o ganho de juntar ao Elo
    Pe, _, _, _, _ = walk(L, GRUPOS["elo"])
    ae, le = met(Pe[tst], yt)
    linhas_md.append(("Só Elo (força própria)", ae, le, *forca(Pe[tst], Pfr, yt)))
    por = {}
    for nome, cols in GRUPOS.items():
        if nome == "elo":
            continue
        Ps, _, _, _, _ = walk(L, cols)
        Pse, _, _, _, _ = walk(L, GRUPOS["elo"] + cols)
        a, l = met(Ps[tst], yt)
        g, fz = forca(Pse[tst], Pe[tst], yt)
        por[nome] = {"acerto_sozinho": a, "ganho_sobre_elo": g, "forca_sobre_elo": fz}
        print(f"  {nome:11s} sozinho {a:.3f} | somado ao Elo: forca {fz:+.2f}")
    res["por_pilar"] = por
    # comparacao com odds onde existem
    O = odds_ref(L)
    tem = np.array([o is not None for o in O]) & tst
    if tem.sum() > 200:
        Oa = np.array([o if o else [1 / 3] * 3 for o in O])
        yo = y[tem]
        ao, lo = met(Oa[tem], yo)
        ap, lp = met(Pt[tem], yo)
        mix = {}
        for w in (0.15, 0.3, 0.5):
            B = (1 - w) * Oa[tem] + w * Pt[tem]
            mix[w] = (*met(B, yo), *forca(B, Oa[tem], yo))
        res["odds"] = {"jogos": int(tem.sum()), "acerto_odds": ao, "ll_odds": lo, "acerto_pilares": ap, "ll_pilares": lp,
                       "mistura": {str(k): v for k, v in mix.items()}}
        # onde os pilares discordam do mercado
        dif = []
        for i in np.where(tem)[0]:
            fo = int(np.argmax(Oa[i]))
            if fo != 1 and Oa[i][fo] > 0.55 and Pt[i][fo] < 0.42:
                dif.append((Oa[i][fo], y[i] == fo, Oa[i][1], y[i] == 1))
        if dif:
            n = len(dif)
            res["divergencia"] = {"jogos": n, "fav_odd": sum(d[0] for d in dif) / n, "fav_real": sum(d[1] for d in dif) / n,
                                  "emp_odd": sum(d[2] for d in dif) / n, "emp_real": sum(d[3] for d in dif) / n}
    res["pesos"] = {c: float(Wf[i, 0] - Wf[i, 2]) for i, c in enumerate(todas)}
    res["pesos_empate"] = {c: float(Wf[i, 1] - (Wf[i, 0] + Wf[i, 2]) / 2) for i, c in enumerate(todas)}
    res["atualizado"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    json.dump({**res, "colunas": todas, "W": Wf.tolist(), "mu": mu.tolist(), "sd": sd.tolist()},
              open(os.path.join(AQUI, "pilares.json"), "w"), indent=1)
    # relatorio
    pc = lambda v: f"{100 * v:.1f}%"
    md = ["# Pilares sem odds — teste no tempo", "",
          f"Base FotMob: {len(J)} jogos (Brasileirão A/B/C, Copa do Brasil, Libertadores, Sul-Americana, Paulista, "
          f"5 ligas grandes da Europa e Championship). Jogos com histórico suficiente: {len(L)}; testados mês a mês, "
          f"sempre ajustando só com o passado: {int(tst.sum())}.", "",
          "| Método | Acerto do favorito | Log-loss (menor = melhor) | Ganho | Força |", "|---|---|---|---|---|"]
    for n, a, l, g, fz in linhas_md:
        md.append(f"| {n} | {pc(a)} | {l:.4f} | {'' if g == '' else f'{g:+.4f}'} | {'' if fz == '' else f'{fz:+.1f}'} |")
    md += ["", "## Cada pilar", "", "| Pilar | Acerto sozinho | Somado ao Elo: força (precisa > 2) |", "|---|---|---|"]
    for nome, v in por.items():
        md.append(f"| {NOMES[nome]} | {pc(v['acerto_sozinho'])} | {v['forca_sobre_elo']:+.1f} |")
    if "odds" in res:
        o = res["odds"]
        md += ["", f"## Contra as odds de fechamento ({o['jogos']} jogos que casaram com o football-data)", "",
               "| Método | Acerto | Log-loss |", "|---|---|---|",
               f"| Odds | {pc(o['acerto_odds'])} | {o['ll_odds']:.4f} |",
               f"| Pilares sem odds | {pc(o['acerto_pilares'])} | {o['ll_pilares']:.4f} |"]
        for w, (a, l, g, fz) in o["mistura"].items():
            md.append(f"| Odds + {int(float(w) * 100)}% pilares | {pc(a)} | {l:.4f} (força {fz:+.1f} sobre as odds) |")
    if "divergencia" in res:
        d = res["divergencia"]
        md += ["", f"Quando o mercado tem favorito forte (>55%) e os pilares discordam (<42%): {d['jogos']} jogos; "
               f"favorito venceu {pc(d['fav_real'])} (odd dava {pc(d['fav_odd'])}); empate {pc(d['emp_real'])} "
               f"(odd dava {pc(d['emp_odd'])})."]
    md += ["", "## Peso de cada variável (vitória do mandante − vitória do visitante, escala padronizada)", ""]
    for c, w in sorted(res["pesos"].items(), key=lambda t: -abs(t[1])):
        md.append(f"- {c}: {w:+.3f}")
    open(os.path.join(AQUI, "pilares.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


def concurso_aberto():
    """Pilares dos 14 jogos do concurso aberto (para o painel): valores de cada vertente e a probabilidade
    dos pilares juntos (sem odds). Grava docs/dados/pilares.json."""
    import requests
    ab = os.path.join(RAIZ, "coleta", "dados", "sentinela_aberto.csv")
    linhas = list(csv.DictReader(open(ab, encoding="utf-8")))
    conc = max(int(r["concurso"]) for r in linhas)
    jogos = {}
    for r in linhas:
        if int(r["concurso"]) == conc:
            jogos[int(r["jogo"])] = r
    extra = []
    for j, r in sorted(jogos.items()):
        if not r.get("match_id"):
            continue
        try:
            d = requests.get("https://www.fotmob.com/api/data/matchDetails", params={"matchId": r["match_id"]},
                             headers={"User-Agent": "Mozilla/5.0 (estudo pessoal)"}, timeout=25).json()
            tm = d["header"]["teams"]
            info = d["content"]["matchFacts"]["infoBox"]
            est, arb = info.get("Stadium") or {}, info.get("Referee") or {}
            extra.append({"match_id": "aberto-" + r["match_id"], "liga_id": "", "data_utc": info["Match Date"]["utcTime"][:16],
                          "casa_id": str(tm[0]["id"]), "fora_id": str(tm[1]["id"]), "casa": tm[0]["name"], "fora": tm[1]["name"],
                          "gc": "", "gf": "", "lat": est.get("lat", ""), "lon": est.get("long", ""),
                          "gramado": est.get("surface", ""), "arbitro": arb.get("text", ""), "futuro": True, "jogo": j,
                          "xg_c": "", "xg_f": "", "area_c": "", "area_f": "", "verm_c": "", "verm_f": ""})
        except Exception as e:
            print("sem detalhes", j, e)
    J = carregar(extra)
    L = sorted([l for l in montar(J) if l["r"].get("futuro")], key=lambda l: l["r"]["jogo"])
    cfg = json.load(open(os.path.join(AQUI, "pilares.json")))
    cols, W, mu, sd = cfg["colunas"], np.array(cfg["W"]), np.array(cfg["mu"]), np.array(cfg["sd"])
    out = []
    for l in L:
        x = l["x"]
        z = np.array([[(x[c] - mu[i]) / sd[i] if c in x else 0.0 for i, c in enumerate(cols)]])
        p = prever(W, z)[0] if l["ok"] else None
        out.append({"jogo": l["r"]["jogo"], "casa": l["r"]["casa"], "fora": l["r"]["fora"], "dados": l["ok"],
                    "jogos_base": [l["hc"], l["hv"]], "p": [round(float(v), 4) for v in p] if p is not None else None,
                    "x": {k: round(float(v), 3) for k, v in x.items()}})
    res = {"concurso": conc, "gerado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "jogos": out,
           "teste": {k: cfg.get(k) for k in ("todos", "por_pilar", "odds", "jogos_modelo")}}
    json.dump(res, open(os.path.join(RAIZ, "docs", "dados", "pilares.json"), "w"), ensure_ascii=False, indent=1)
    registrar(conc, out)
    print(f"pilares do concurso {conc}: {sum(1 for o in out if o['dados'])} de {len(out)} jogos com dados")
    placar()


REG = os.path.join(AQUI, "pilares_registro.csv")
VOTOS = [("elo", "Força própria (Elo)"), ("xg_saldo", "Saldo de xG"), ("xgm_saldo", "xG em casa/fora"), ("dom", "Domínio"),
         ("forma5", "Forma (5 jogos)"), ("descanso", "Descanso")]


def registrar(conc, out):
    """Grava a previsao dos pilares do concurso antes dos jogos (substitui a do mesmo concurso enquanto nao comecou)."""
    campos = ["concurso", "jogo", "gerado", "p1", "px", "p2"] + [k for k, _ in VOTOS]
    linhas = list(csv.DictReader(open(REG, encoding="utf-8"))) if os.path.exists(REG) else []
    linhas = [r for r in linhas if int(r["concurso"]) != conc]
    agora = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    for o in out:
        if not o["p"]:
            continue
        r = {"concurso": conc, "jogo": o["jogo"], "gerado": agora, "p1": o["p"][0], "px": o["p"][1], "p2": o["p"][2]}
        r.update({k: o["x"].get(k, "") for k, _ in VOTOS})
        linhas.append(r)
    w = csv.DictWriter(open(REG, "w", newline="", encoding="utf-8"), fieldnames=campos)
    w.writeheader()
    w.writerows(linhas)


def placar():
    """Acerto de cada vertente nos concursos registrados que ja tem resultado: mercado (camada 1), pilares juntos
    e o 'voto' de cada pilar (lado que ele favorece). Grava docs/dados/placar_pilares.json."""
    if not os.path.exists(REG):
        return
    res = {}
    rc = os.path.join(RAIZ, "coleta", "dados", "resultados_caixa.csv")
    if os.path.exists(rc):
        for r in csv.DictReader(open(rc, encoding="utf-8")):
            if r["resultado"] in ("1", "X", "2"):
                res[(int(r["concurso"]), int(r["jogo"]))] = r["resultado"]
    av = os.path.join(RAIZ, "docs", "dados", "ao_vivo.json")
    if os.path.exists(av):
        d = json.load(open(av))
        for g in d.get("jogos", []):
            if g.get("situacao") == "encerrado" and g.get("resultado"):
                res.setdefault((int(d["concurso"]), int(g["jogo"])), g["resultado"])
    merc = {}
    for c in {int(r["concurso"]) for r in csv.DictReader(open(REG, encoding="utf-8"))}:
        arq = os.path.join(AQUI, "saida", f"concurso_{c}.csv")
        if os.path.exists(arq):
            for r in csv.DictReader(open(arq, encoding="utf-8")):
                merc[(c, int(r["jogo"]))] = [float(r["p1"]), float(r["px"]), float(r["p2"])]
    tab = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for r in csv.DictReader(open(REG, encoding="utf-8")):
        k = (int(r["concurso"]), int(r["jogo"]))
        if k not in res:
            continue
        y = "1X2".index(res[k])
        c = k[0]
        pp = [float(r["p1"]), float(r["px"]), float(r["p2"])]
        for nome, p in (("Pilares juntos (sem odds)", pp), ("Mercado (odds)", merc.get(k))):
            if p:
                t = tab[nome][c]
                t[0] += 1
                t[1] += int(max(range(3), key=lambda i: p[i]) == y)
        for kk, nome in VOTOS:
            v = f(r.get(kk))
            if v is None or abs(v) < 1e-9:
                continue
            t = tab[nome][c]
            t[0] += 1
            t[1] += int((v > 0 and y == 0) or (v < 0 and y == 2))
    out = {"atualizado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "vertentes": []}
    for nome, por in tab.items():
        n = sum(t[0] for t in por.values())
        a = sum(t[1] for t in por.values())
        out["vertentes"].append({"nome": nome, "jogos": n, "acertos": a, "acerto": a / n if n else None,
                                 "por_concurso": {str(c): t for c, t in sorted(por.items())}})
    out["vertentes"].sort(key=lambda v: -(v["acerto"] or 0))
    json.dump(out, open(os.path.join(RAIZ, "docs", "dados", "placar_pilares.json"), "w"), ensure_ascii=False, indent=1)
    print("placar por pilar:", ", ".join(f"{v['nome']} {v['acertos']}/{v['jogos']}" for v in out["vertentes"]))


if __name__ == "__main__":
    concurso_aberto() if "--aberto" in sys.argv else (placar() if "--placar" in sys.argv else testar())
