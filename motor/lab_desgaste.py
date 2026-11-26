"""
Desgaste e calendario: o time cansado, que viajou muito ou que vai poupar para um jogo maior
rende menos do que a forca dele (ou a odd) indica?

Base: coleta/dados/fotmob_jogos.csv (21 mil jogos 2021-2026, com data e local), calendario de
todas as competicoes que temos (Brasileirao A/B/C, Copa do Brasil, Libertadores, Sul-Americana,
Paulista e ligas europeias - na Europa faltam Champions/Europa League, entao o desgaste europeu
fica subestimado).

Fatores de cada time no jogo (calculados so com o calendario, que e publico antes do jogo):
  descanso   dias desde o ultimo jogo
  jogos_14d  jogos nos 14 dias anteriores
  viagem     km do local do jogo anterior ate este (log)
  poupa      tem jogo de copa (Libertadores, Sul-Americana, Copa do Brasil) nos 4 dias seguintes
  veio_copa  o jogo anterior foi de copa, ate 4 dias antes

Tres reguas, todas com teste no tempo (aprende nas temporadas anteriores, testa na seguinte):
  1) Elo (forca pelos resultados) - vale para todas as ligas, inclusive Serie B e C sem odds
  2) odd de abertura (Europa, football-data) - parecida com a odd de quinta da Loteca
  3) odd de fechamento (Brasil e Europa) - ja inclui a escalacao confirmada
forca = ganho medio de log-loss / erro padrao (por mes). Acima de 2 = sinal real.
Uso: python motor/lab_desgaste.py > motor/lab_desgaste.md
"""
import collections
import csv
import datetime as dt
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import fd_base as F  # noqa: E402

RAIZ = os.path.dirname(AQUI)
ARQ = os.path.join(RAIZ, "coleta", "dados", "fotmob_jogos.csv")
COPAS = {"Copa do Brasil", "Libertadores", "Sul-Americana"}
LIGAS = {"Brasileirao A": "new_BRA", "Brasileirao B": None, "Brasileirao C": None, "Premier League": "E0",
         "Championship": "E1", "LaLiga": "SP1", "Serie A Italia": "I1", "Bundesliga": "D1", "Ligue 1": "F1"}
FATORES = ["descanso", "jogos_14d", "viagem", "poupa", "veio_copa"]


def km(a, b):
    try:
        la1, lo1, la2, lo2 = map(math.radians, map(float, (a[0], a[1], b[0], b[1])))
    except Exception:
        return None
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def carregar():
    J = []
    for r in csv.DictReader(open(ARQ, encoding="utf-8")):
        try:
            r["t"] = dt.datetime.fromisoformat(r["data_utc"].replace("Z", "+00:00"))
            r["gc"], r["gf"] = int(r["gc"]), int(r["gf"])
        except Exception:
            continue
        J.append(r)
    J.sort(key=lambda r: r["t"])
    return J


def fatores(J):
    cal = collections.defaultdict(list)  # time -> [(t, lat, lon, liga)]
    for r in J:
        for tid in (r["casa_id"], r["fora_id"]):
            cal[tid].append((r["t"], r["lat"], r["lon"], r["liga"]))
    idx = {tid: [x[0] for x in v] for tid, v in cal.items()}

    def f(tid, r):
        import bisect
        L, T = cal[tid], idx[tid]
        i = bisect.bisect_left(T, r["t"])
        ant = L[i - 1] if i > 0 else None
        prox = L[i + 1] if i + 1 < len(L) else None
        desc = (r["t"] - ant[0]).total_seconds() / 86400 if ant else 10.0
        j14 = sum(1 for x in L[max(0, i - 10):i] if (r["t"] - x[0]).days < 14)
        k = km((ant[1], ant[2]), (r["lat"], r["lon"])) if ant else None
        poupa = int(bool(prox and prox[3] in COPAS and (prox[0] - r["t"]).total_seconds() / 86400 <= 4.2))
        veio = int(bool(ant and ant[3] in COPAS and desc <= 4.2))
        return {"descanso": min(desc, 10.0), "jogos_14d": j14, "viagem": math.log1p((k or 0) / 100),
                "poupa": poupa, "veio_copa": veio}
    for r in J:
        r["fh"], r["fa"] = f(r["casa_id"], r), f(r["fora_id"], r)


def elo(J):
    R = collections.defaultdict(lambda: 1500.0)
    for r in J:
        h, a = r["casa_id"], r["fora_id"]
        r["elo_d"] = (R[h] + 60 - R[a]) / 400
        e = 1 / (1 + 10 ** (-r["elo_d"]))
        s = 1.0 if r["gc"] > r["gf"] else (0.5 if r["gc"] == r["gf"] else 0.0)
        g = math.log(abs(r["gc"] - r["gf"]) + 1) + 1
        R[h] += 20 * g * (s - e); R[a] -= 20 * g * (s - e)


def y_de(r):
    return 0 if r["gc"] > r["gf"] else (1 if r["gc"] == r["gf"] else 2)


def softmax(z):
    z = z - z.max(-1, keepdims=True); q = np.exp(z); return q / q.sum(-1, keepdims=True)


def ajusta(X, P, y, lam=3.0):
    """q_k proporcional a P_k * exp(X_k . b); X: (n,3,m)."""
    m = X.shape[2]; b = np.zeros(m)
    for _ in range(30):
        q = softmax(np.log(P) + X @ b)
        Xy = X[np.arange(len(y)), y]; Eq = (q[..., None] * X).sum(1)
        g = (Xy - Eq).sum(0) - lam * b
        H = np.einsum("ik,ika,ikb->ab", q, X, X) - Eq.T @ Eq
        b += np.linalg.solve(H + lam * np.eye(m), g)
    return b


def base_elo(tr, te):
    """probabilidade so pelo Elo: logit multinomial em [1, elo_d] aprendido no treino."""
    def X(L):
        return np.array([[[1.0, r["elo_d"]], [0.0, 0.0], [-1.0, -r["elo_d"]]] for r in L])
    Xtr, ytr = X(tr), np.array([y_de(r) for r in tr])
    # empate: constante propria
    def Xd(L):
        x = X(L); d = np.zeros((len(L), 3, 1)); d[:, 1, 0] = 1.0; return np.concatenate([x, d], 2)
    b = ajusta(Xd(tr), np.full((len(tr), 3), 1 / 3), ytr, lam=0.1)
    return softmax(Xd(te) @ b), softmax(Xd(tr) @ b)


def mat(L, quais):
    out = []
    for r in L:
        cols = []
        for k in quais:
            d = r["fh"][k] - r["fa"][k]
            cols.append(d)
        out.append([cols, [0.0] * len(cols), [-c for c in cols]])
    return np.array(out, float)


def testar(nome, grupos, quais):
    """grupos: lista de (treino, teste, P_treino, P_teste) por temporada/mes."""
    todos = [r for _, te, _, _ in grupos for r in te]
    if todos and all(np.allclose(mat(todos, [k])[:, 0, 0], 0) for k in quais):
        print(f"| {nome} | - | - | - | sem dado (fator sempre zero nesta base) |")
        return
    g_mes = collections.defaultdict(float); n = 0
    for tr, te, Ptr, Pte in grupos:
        if len(tr) < 300 or not te:
            continue
        b = ajusta(mat(tr, quais), Ptr, np.array([y_de(r) for r in tr]))
        q = softmax(np.log(Pte) + mat(te, quais) @ b)
        for r, qq, pp in zip(te, q, Pte):
            y = y_de(r); g_mes[r["t"].strftime("%Y-%m")] += math.log(qq[y]) - math.log(pp[y]); n += 1
    g = np.array(list(g_mes.values()))
    if len(g) < 3:
        return
    f = g.mean() / (g.std() / math.sqrt(len(g)))
    print(f"| {nome} | {n} | {g.sum()/n*1000:+.2f} | {f:+.1f} | {'**SINAL REAL**' if f > 2 else ('promissor' if f > 1 else 'nao')} |")


def efeito_bruto(L, P):
    """quanto o mandante/visitante rende acima do esperado em cada situacao (pontos percentuais)."""
    print("\n### Efeito direto (resultado real menos o esperado pela regua, em pontos percentuais)\n")
    print("| situacao | jogos | vitoria do time vs esperado |")
    print("|---|---|---|")
    casos = [
        ("visitante com <=3 dias de descanso e mandante com 6+", lambda r: r["fa"]["descanso"] <= 3.2 and r["fh"]["descanso"] >= 6, 2),
        ("mandante com <=3 dias de descanso e visitante com 6+", lambda r: r["fh"]["descanso"] <= 3.2 and r["fa"]["descanso"] >= 6, 0),
        ("mandante vai jogar copa em ate 4 dias (pode poupar)", lambda r: r["fh"]["poupa"] == 1, 0),
        ("visitante vai jogar copa em ate 4 dias (pode poupar)", lambda r: r["fa"]["poupa"] == 1, 2),
        ("mandante veio de jogo de copa", lambda r: r["fh"]["veio_copa"] == 1, 0),
        ("visitante veio de jogo de copa", lambda r: r["fa"]["veio_copa"] == 1, 2),
        ("visitante viajou mais de 2.000 km", lambda r: r["fa"]["viagem"] > math.log1p(20), 2),
        ("mandante com 4+ jogos em 14 dias", lambda r: r["fh"]["jogos_14d"] >= 4, 0),
        ("visitante com 4+ jogos em 14 dias", lambda r: r["fa"]["jogos_14d"] >= 4, 2),
    ]
    for nome, cond, k in casos:
        sel = [(r, p) for r, p in zip(L, P) if cond(r)]
        if len(sel) < 40:
            print(f"| {nome} | {len(sel)} | poucos jogos |"); continue
        obs = np.mean([y_de(r) == k for r, _ in sel]); esp = np.mean([p[k] for _, p in sel])
        se = math.sqrt(esp * (1 - esp) / len(sel))
        print(f"| {nome} | {len(sel)} | {100*(obs-esp):+.1f} (z {(obs-esp)/se:+.1f}) |")


def casar_odds(J):
    fd = collections.defaultdict(list)
    for g in F.jogos():
        if g["gc"] is not None:
            fd[(g["liga"], g["d"])].append(g)
    for r in J:
        lg = LIGAS.get(r["liga"])
        if not lg:
            continue
        d0 = r["t"].date()
        melhor, ms = None, 0
        for dd in (-1, 0, 1):
            for g in fd.get((lg, d0 + dt.timedelta(days=dd)), []):
                s = min(F.sim(r["casa"], g["casa"]), F.sim(r["fora"], g["fora"]))
                if s > ms and g["gc"] == r["gc"] and g["gf"] == r["gf"]:
                    melhor, ms = g, s
        if melhor and ms >= 0.6:
            for k in ("avgo", "b365o", "avg", "ps", "b365c"):
                if k in melhor:
                    r["o_" + k] = melhor[k]


def prob(o):
    p = np.array([1 / x for x in o]); return p / p.sum()


def por_temporada(L, P_fn):
    """treina em tudo antes do ano/mes de teste (blocos de 3 meses)."""
    blocos = sorted({(r["t"].year, (r["t"].month - 1) // 3) for r in L})
    out = []
    for b in blocos[4:]:
        tr = [r for r in L if (r["t"].year, (r["t"].month - 1) // 3) < b]
        te = [r for r in L if (r["t"].year, (r["t"].month - 1) // 3) == b]
        out.append((tr, te, P_fn(tr), P_fn(te)))
    return out


def main():
    J = carregar(); fatores(J); elo(J); casar_odds(J)
    alvo = [r for r in J if r["liga"] in LIGAS and r["t"].year >= 2021]
    alvo = [r for r in alvo if r["t"] >= alvo[0]["t"] + dt.timedelta(days=150)]  # Elo aquecido
    print("# Desgaste e calendario x forca e odds\n")
    print(f"Jogos de liga analisados: {len(alvo)} ({collections.Counter(r['liga'] for r in alvo).most_common()})\n")

    # 1) regua Elo, por grupo de ligas
    for titulo, filtro in (("Brasil (Serie A, B e C)", lambda r: r["liga"].startswith("Brasileirao")),
                           ("Serie B e C (sem odds no mercado de dados)", lambda r: r["liga"] in ("Brasileirao B", "Brasileirao C")),
                           ("Europa", lambda r: not r["liga"].startswith("Brasileirao"))):
        L = [r for r in alvo if filtro(r)]
        blocos = sorted({(r["t"].year, (r["t"].month - 1) // 3) for r in L})
        grupos = []
        for b in blocos[4:]:
            tr = [r for r in L if (r["t"].year, (r["t"].month - 1) // 3) < b]
            te = [r for r in L if (r["t"].year, (r["t"].month - 1) // 3) == b]
            if len(tr) < 300 or not te:
                continue
            Pte, Ptr = base_elo(tr, te)
            grupos.append((tr, te, Ptr, Pte))
        print(f"\n## Regua: forca pelo Elo - {titulo}\n")
        print("| fator (mandante - visitante) | jogos testados | ganho por 1000 jogos | forca | veredito |")
        print("|---|---|---|---|---|")
        for k in FATORES:
            testar(k, grupos, [k])
        testar("todos juntos", grupos, FATORES)
        if titulo.startswith("Brasil"):
            ultimo = grupos[-1] if grupos else None
            Ltest = [r for _, te, _, _ in grupos for r in te]; Ptest = np.concatenate([g[3] for g in grupos])
            efeito_bruto(Ltest, Ptest)

    # 2) e 3) reguas de odds
    for titulo, chave, filtro in (("odd de ABERTURA - Europa", "o_avgo", lambda r: not r["liga"].startswith("Brasileirao")),
                                  ("odd de FECHAMENTO - Europa", "o_avg", lambda r: not r["liga"].startswith("Brasileirao")),
                                  ("odd de FECHAMENTO - Brasileirao A", "o_avg", lambda r: r["liga"] == "Brasileirao A")):
        L = [r for r in alvo if filtro(r) and chave in r]
        grupos = por_temporada(L, lambda S: np.array([prob(r[chave]) for r in S]))
        print(f"\n## Regua: {titulo} ({len(L)} jogos casados)\n")
        print("| fator (mandante - visitante) | jogos testados | ganho por 1000 jogos | forca | veredito |")
        print("|---|---|---|---|---|")
        for k in FATORES:
            testar(k, grupos, [k])
        testar("todos juntos", grupos, FATORES)
        if titulo.endswith("Brasileirao A"):
            efeito_bruto(L, [prob(r[chave]) for r in L])


if __name__ == "__main__":
    main()
