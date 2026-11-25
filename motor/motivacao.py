"""
Motivacao pela tabela: o que cada time tem em jogo na reta final.

Com os resultados do football-data monta a classificacao ANTES de cada jogo e marca:
  sem nada em jogo = nao alcanca mais a zona de cima (titulo / vaga continental) e ja
                     esta livre do rebaixamento (ou ja garantido / ja rebaixado);
  luta             = brigando contra o rebaixamento, ate 3 pontos da linha, 8 rodadas ou menos.
Testa contra a odd de FECHAMENTO (media das casas) em todas as ligas, no tempo (pesos
aprendidos so com temporadas anteriores). Grava motor/motivacao.md e motor/motivacao.json.
alertas(linhas) avisa, no concurso aberto, os jogos com essas situacoes.
Uso: python motor/motivacao.py
"""
import collections
import datetime
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibracao import sem_margem  # noqa: E402
import fd_base  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA_MD, SAIDA_JSON = os.path.join(AQUI, "motivacao.md"), os.path.join(AQUI, "motivacao.json")
REL = {"new_BRA": 4, "E0": 3, "E1": 3, "SP1": 3, "SP2": 4, "I1": 3, "I2": 3, "D1": 2, "D2": 2, "F1": 3, "F2": 3,
       "P1": 2, "N1": 2, "T1": 3}
TOP = {"new_BRA": 6, "E0": 4, "E1": 2, "SP1": 4, "SP2": 2, "I1": 4, "I2": 2, "D1": 4, "D2": 2, "F1": 3, "F2": 2,
       "P1": 2, "N1": 2, "T1": 2}
NOMES = ["mandante sem nada em jogo (vitoria do mandante)", "visitante sem nada em jogo (vitoria do visitante)",
         "os dois sem nada em jogo (empate)", "mandante na luta contra o rebaixamento (vitoria do mandante)",
         "visitante na luta contra o rebaixamento (vitoria do visitante)"]


class Tabela:
    def __init__(self, liga, times, tot):
        self.liga, self.times, self.tot = liga, times, tot
        self.pts, self.jog, self.vit = collections.Counter(), collections.Counter(), collections.Counter()
        self.ultimo = None

    def soma(self, h, a, gc, gf, d=None):
        self.jog[h] += 1
        self.jog[a] += 1
        if d is not None and (self.ultimo is None or d > self.ultimo):
            self.ultimo = d
        if gc > gf:
            self.pts[h] += 3
            self.vit[h] += 1
        elif gc < gf:
            self.pts[a] += 3
            self.vit[a] += 1
        else:
            self.pts[h] += 1
            self.pts[a] += 1

    def acima_garantido(self, t, q):
        """t termina acima de q com certeza (q nao alcanca os pontos de t; empate decidido por vitorias)."""
        mq = self.pts[q] + 3 * (self.tot - self.jog[q])
        return mq < self.pts[t] or (mq == self.pts[t] and self.vit[q] + (self.tot - self.jog[q]) < self.vit[t])

    def estado(self, t):
        tab = sorted(self.times, key=lambda x: (-self.pts[x], -self.vit[x]))
        pos = tab.index(t)
        P = lambda k: self.pts[tab[k]]
        r, p, n = self.tot - self.jog[t], self.pts[t], len(tab)
        outros = [q for q in tab if q != t]
        kt, nrel = TOP[self.liga], REL[self.liga]
        campeao = all(self.acima_garantido(t, q) for q in outros)
        abaixo_certo = sum(self.acima_garantido(t, q) for q in outros)      # times que terminam atras de t com certeza
        acima_certo = sum(self.acima_garantido(q, t) for q in outros)       # times que terminam a frente de t com certeza
        salvo = abaixo_certo >= nrel
        condenado = acima_certo >= n - nrel
        titulo_vivo = not campeao and acima_certo == 0
        top_vivo = acima_certo < kt and not (abaixo_certo >= n - kt)       # ainda pode entrar e nao esta garantido no top
        reb_vivo = not salvo and not condenado
        return {"restam": r, "posicao": pos + 1, "pontos": p, "campeao": campeao, "salvo": salvo, "rebaixado": condenado,
                "morto": not (top_vivo or titulo_vivo) and not reb_vivo,
                "luta": reb_vivo and r <= 8 and abs(p - P(n - nrel)) <= 3,
                "titulo": titulo_vivo and r <= 8 and pos <= 3}


def temporadas():
    por = collections.defaultdict(list)
    for g in fd_base.jogos():
        if g["liga"] in REL:
            por[(g["liga"], g["temporada"])].append(g)
    return por


def reta_final():
    """Jogos ja disputados com <=10 rodadas restantes, com estado dos dois times e odd de fechamento."""
    L = []
    for (liga, temp), js in temporadas().items():
        times = sorted({g["casa"] for g in js} | {g["fora"] for g in js})
        n = len(times)
        if n < 10:
            continue
        T = Tabela(liga, times, 2 * (n - 1))
        js = sorted((g for g in js if g["gc"] is not None), key=lambda g: g["d"])
        i = 0
        while i < len(js):
            dia = [g for g in js[i:] if g["d"] == js[i]["d"]]
            for g in dia:
                o = g.get("avg") or g.get("ps") or g.get("avgo") or g.get("b365o")
                eh, ea = T.estado(g["casa"]), T.estado(g["fora"])
                if o and min(eh["restam"], ea["restam"]) <= 10:
                    y = 0 if g["gc"] > g["gf"] else (1 if g["gc"] == g["gf"] else 2)
                    L.append((liga, temp, o, y, eh, ea))
            for g in dia:
                T.soma(g["casa"], g["fora"], g["gc"], g["gf"], g["d"])
            i += len(dia)
    return L


def feats(eh, ea):
    f = np.zeros((3, 5))
    if eh["morto"] and not ea["morto"]:
        f[0, 0] = 1
    if ea["morto"] and not eh["morto"]:
        f[2, 1] = 1
    if eh["morto"] and ea["morto"]:
        f[1, 2] = 1
    if eh["luta"] and not ea["morto"]:
        f[0, 3] = 1
    if ea["luta"] and not eh["morto"]:
        f[2, 4] = 1
    return f


def ajustar(L, cols, lam=2.0):
    b = np.zeros(len(cols))
    if not L:
        return b
    P = np.array([sem_margem(l[2]) for l in L])
    F = np.array([feats(l[4], l[5])[:, cols] for l in L])
    y = np.array([l[3] for l in L])
    for _ in range(20):
        z = np.log(P) + F @ b
        q = np.exp(z - z.max(1, keepdims=True))
        q /= q.sum(1, keepdims=True)
        Eq = (q[..., None] * F).sum(1)
        g = (F[np.arange(len(y)), y] - Eq).sum(0) - lam * b
        H = np.einsum("ik,ika,ikb->ab", q, F, F) - Eq.T @ Eq
        b += np.linalg.solve(H + lam * np.eye(len(cols)), g)
    return b


def ano(t):
    t = str(t)
    if len(t) == 4 and t.isdigit() and int(t[2:]) == int(t[:2]) + 1:
        return 2000 + int(t[:2])
    return int(t[:4])


def no_tempo(L, cols):
    anos = sorted({ano(l[1]) for l in L})
    G, pesos = [], []
    for A in anos:
        tr = [l for l in L if ano(l[1]) < A]
        te = [l for l in L if ano(l[1]) == A and feats(l[4], l[5])[:, cols].any()]
        if len(tr) < 1500 or not te:
            continue
        b = ajustar(tr, cols)
        pesos.append((A, [round(float(x), 3) for x in b]))
        for l in te:
            p = np.array(sem_margem(l[2]))
            z = np.log(p) + feats(l[4], l[5])[:, cols] @ b
            q = np.exp(z - z.max())
            q /= q.sum()
            G.append(math.log(q[l[3]]) - math.log(p[l[3]]))
    G = np.array(G)
    forca = G.mean() / (G.std() / math.sqrt(len(G))) if len(G) > 1 else 0.0
    return len(G), float(G.mean()) if len(G) else 0.0, float(forca), pesos


def testar():
    L = reta_final()
    md = ["# Motivação pela tabela (reta final: 10 rodadas ou menos)", "",
          f"Jogos testados: {len(L)} (Brasileirão Série A e ligas europeias, odd de fechamento — média das casas).", "",
          "| Situação | Jogos | Aconteceu | A odd dava | Peso (0 = a odd já sabe) |", "|---|---|---|---|---|"]
    bt = ajustar(L, list(range(5)))
    for k in range(5):
        S = [l for l in L if feats(l[4], l[5])[:, k].any()]
        if not S:
            continue
        o = [int(feats(l[4], l[5])[:, k].argmax()) for l in S]
        real = np.mean([l[3] == x for l, x in zip(S, o)])
        odd = np.mean([sem_margem(l[2])[x] for l, x in zip(S, o)])
        md.append(f"| {NOMES[k]} | {len(S)} | {real:.1%} | {odd:.1%} | {bt[k]:+.3f} |")
    res = {}
    for nome, cols in (("todas as situacoes juntas", list(range(5))), ("so visitante sem nada em jogo", [1])):
        n, g, f, pesos = no_tempo(L, cols)
        res[nome] = {"jogos": n, "ganho": g, "forca": f, "pesos_por_ano": pesos}
        md += ["", f"**Teste no tempo — {nome}:** {n} jogos, ganho médio {g:+.4f} log-loss por jogo, força {f:+.1f} → "
               + ("**SINAL REAL**" if f > 2 else "não passa no critério (precisa > 2)"),
               "Pesos aprendidos só com o passado, por ano: " + ", ".join(f"{a}: {p}" for a, p in pesos)]
    vis = res["so visitante sem nada em jogo"]
    modelo = {"peso_visitante_morto": float(ajustar(L, [1])[0]), "forca": vis["forca"], "ligado": vis["forca"] > 2,
              "atualizado": str(datetime.date.today())}
    md += ["", "Uso no motor: alerta no concurso aberto sempre; entra na probabilidade só com força > 2 "
           f"(hoje: {'ligado' if modelo['ligado'] else 'desligado'})."]
    open(SAIDA_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(modelo, open(SAIDA_JSON, "w"), indent=1)
    print("\n".join(md))


FOTMOB_LIGA = {"268": "new_BRA", "47": "E0", "48": "E1", "87": "SP1", "55": "I1", "54": "D1", "53": "F1"}


def tabelas_fotmob():
    """Tabelas da temporada atual montadas com os resultados da FotMob (coleta/dados/fotmob_jogos.csv),
    que chegam toda semana; o football-data costuma atrasar alguns dias."""
    arq = os.path.join(os.path.dirname(AQUI), "coleta", "dados", "fotmob_jogos.csv")
    if not os.path.exists(arq):
        return {}
    import csv
    por = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in csv.DictReader(open(arq, encoding="utf-8")):
        liga = FOTMOB_LIGA.get(r["liga_id"])
        if liga and r["gc"] not in ("", None) and r["gf"] not in ("", None):
            por[liga][r["temporada"]].append(r)
    out = {}
    for liga, ts in por.items():
        js = ts[max(ts, key=lambda t: max(x["data_utc"] for x in ts[t]))]
        times = sorted({x["casa"] for x in js} | {x["fora"] for x in js})
        if len(times) < 10:
            continue
        T = Tabela(liga, times, 2 * (len(times) - 1))
        for x in js:
            d = datetime.datetime.strptime(x["data_utc"][:10], "%Y-%m-%d").date()
            T.soma(x["casa"], x["fora"], int(float(x["gc"])), int(float(x["gf"])), d)
        if max(T.jog.values() or [0]) >= 2:
            out[liga] = T
    return out


def tabelas_atuais():
    """Tabela da temporada mais recente de cada liga, com os jogos ja disputados.
    Usa a fonte com o resultado mais recente (FotMob ou football-data)."""
    por = collections.defaultdict(dict)
    for (liga, temp), js in temporadas().items():
        por[liga][temp] = js
    out = {}
    for liga, ts in por.items():
        temp = max(ts, key=ano)
        js = ts[temp]
        times = sorted({g["casa"] for g in js} | {g["fora"] for g in js})
        if len(times) < 10:
            continue
        T = Tabela(liga, times, 2 * (len(times) - 1))
        for g in js:
            if g["gc"] is not None:
                T.soma(g["casa"], g["fora"], g["gc"], g["gf"], g["d"])
        if max(T.jog.values() or [0]) >= 2:
            out[liga] = T
    for liga, T in tabelas_fotmob().items():
        atual = out.get(liga)
        if atual is None or (T.ultimo and (atual.ultimo is None or T.ultimo > atual.ultimo)):
            out[liga] = T
    return out


def alertas(linhas):
    """linhas: [(jogo, mandante, visitante)] do concurso aberto -> {jogo: [textos]}."""
    T = tabelas_atuais()
    if not T:
        return {}
    modelo = json.load(open(SAIDA_JSON)) if os.path.exists(SAIDA_JSON) else {}
    hoje = datetime.date.today()
    T = {k: t for k, t in T.items() if t.ultimo and (hoje - t.ultimo).days <= 6}  # tabela com mais de 6 dias: nao afirma nada
    out = {}
    for j, m, v in linhas:
        melhor = None
        for liga, tab in T.items():
            sm = max(tab.times, key=lambda t: fd_base.sim(m, t))
            sv = max(tab.times, key=lambda t: fd_base.sim(v, t))
            s = fd_base.sim(m, sm) + fd_base.sim(v, sv)
            if fd_base.sim(m, sm) >= 0.8 and fd_base.sim(v, sv) >= 0.8 and sm != sv and (not melhor or s > melhor[0]):
                melhor = (s, tab, sm, sv)
        if not melhor:
            continue
        _, tab, sm, sv = melhor
        eh, ea = tab.estado(sm), tab.estado(sv)
        if min(eh["restam"], ea["restam"]) > 10:
            continue
        txt = []
        f = modelo.get("forca")
        for lado, e in (("mandante", eh), ("visitante", ea)):
            if e["campeao"]:
                txt.append(f"{lado} já é campeão ({e['posicao']}º, {e['pontos']} pts)")
            elif e["salvo"] and e["restam"] <= 8 and e["posicao"] > 8:
                txt.append(f"{lado} já está livre do rebaixamento ({e['posicao']}º, {e['pontos']} pts)")
            if e["rebaixado"]:
                txt.append(f"{lado} já está rebaixado ({e['posicao']}º, {e['pontos']} pts)")
        if ea["morto"] and not eh["morto"]:
            txt.append(f"visitante sem nada em jogo ({ea['posicao']}º, {ea['restam']} jogos restantes): no histórico "
                       "o visitante nessa situação vence menos do que a odd indica (Brasileirão 14% × 20%, Europa "
                       f"22% × 25%) — favorece duplo 1X{'' if f is None else f'; teste no tempo: força {f:+.1f}'}")
        if eh["morto"] and not ea["morto"]:
            txt.append(f"mandante sem nada em jogo ({eh['posicao']}º, {eh['restam']} restantes): a odd costuma já "
                       "precificar (37,4% × 37,9%)")
        if eh["morto"] and ea["morto"]:
            txt.append("os dois sem nada em jogo")
        if eh["titulo"] and ea["titulo"]:
            txt.append(f"confronto direto pelo título ({eh['posicao']}º {eh['pontos']} pts × {ea['posicao']}º "
                       f"{ea['pontos']} pts, {eh['restam']} restantes) — os dois com tudo em jogo")
        for lado, e in (("mandante", eh), ("visitante", ea)):
            if e["titulo"] and not (eh["titulo"] and ea["titulo"]):
                txt.append(f"{lado} brigando pelo título ({e['posicao']}º, {e['pontos']} pts, {e['restam']} restantes)")
            if e["luta"]:
                txt.append(f"{lado} na luta contra o rebaixamento ({e['posicao']}º, {e['pontos']} pts, "
                           f"{e['restam']} restantes)")
        if txt:
            out[j] = txt
    return out


if __name__ == "__main__":
    testar()
