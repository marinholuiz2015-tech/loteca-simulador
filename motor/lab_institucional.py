"""
Camada institucional: arbitro, publico no estadio e classico rendem diferente do que a forca (Elo)
e a odd indicam?

Base: coleta/dados/fotmob_jogos.csv (21 mil jogos 2021-2026, com arbitro, publico e local).

Fatores (tudo calculado so com jogos ANTERIORES ao jogo testado):
  arbitro_casa   historico do arbitro: vitorias do mandante acima/abaixo do esperado nos jogos que apitou
                 antes (encolhido para zero quando ele tem poucos jogos)
  arbitro_empate o mesmo para empates
  casa_cheia     publico do jogo comparado com a media do mandante em casa (log). O publico so e publicado
                 depois do jogo, mas casa cheia se sabe antes (ingressos esgotados nas noticias) - por isso
                 tambem testamos a media do mandante (sem nada do proprio jogo)
  publico_medio  media de publico do mandante nos jogos anteriores (log)
  classico       os dois times mandam jogos a menos de 60 km um do outro (classico local / derby)

Reguas: Elo (todas as ligas), odd de abertura (Europa), odd de fechamento (Brasil e Europa).
forca = ganho medio de log-loss / erro padrao (por mes). Acima de 2 = sinal real.
Uso: python motor/lab_institucional.py > motor/lab_institucional.md
"""
import collections
import math
import os
import statistics
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import lab_desgaste as D  # noqa: E402

K_ARB = 40  # encolhimento: com 40 jogos o historico do arbitro vale metade


def fatores(J):
    """J em ordem de data, com r['elo_p'] (probabilidade pelo Elo, antes do jogo)."""
    arb = collections.defaultdict(lambda: [0.0, 0.0, 0])  # soma resid casa, soma resid empate, n
    pub = collections.defaultdict(list)                     # mandante -> publicos anteriores
    casa_loc = collections.defaultdict(list)                # time -> [(lat, lon)] dos jogos em casa
    for r in J:
        a = arb[r["arbitro"]] if r.get("arbitro") else None
        n = a[2] if a else 0
        w = n / (n + K_ARB)
        r["inst"] = {"arbitro_casa": (a[0] / n * w) if n else 0.0, "arbitro_empate": (a[1] / n * w) if n else 0.0}
        hp = pub[r["casa_id"]][-15:]
        med = statistics.mean(hp) if len(hp) >= 3 else None
        try:
            p = float(r["publico"])
        except Exception:
            p = None
        r["inst"]["casa_cheia"] = math.log(p / med) if (p and med) else 0.0
        r["inst"]["publico_medio"] = math.log1p(med / 1000) if med else 0.0
        lc, lf = casa_loc[r["casa_id"]][-10:], casa_loc[r["fora_id"]][-10:]
        if len(lc) >= 3 and len(lf) >= 3:
            c1 = (statistics.median(x[0] for x in lc), statistics.median(x[1] for x in lc))
            c2 = (statistics.median(x[0] for x in lf), statistics.median(x[1] for x in lf))
            d = D.km(c1, c2)
            r["inst"]["classico"] = int(d is not None and d < 60)
        else:
            r["inst"]["classico"] = 0
        # atualiza depois do jogo
        if a is not None and "elo_p" in r:
            y = D.y_de(r)
            a[0] += (y == 0) - r["elo_p"][0]; a[1] += (y == 1) - r["elo_p"][1]; a[2] += 1
        if p:
            pub[r["casa_id"]].append(p)
        try:
            casa_loc[r["casa_id"]].append((float(r["lat"]), float(r["lon"])))
        except Exception:
            pass


def elo_prob(J):
    """probabilidade pelo Elo antes de cada jogo, com uma curva fixa (so para o residuo do arbitro)."""
    for r in J:
        e = 1 / (1 + 10 ** (-r["elo_d"]))
        pd = 0.27 * (1 - abs(e - 0.5) * 1.2)
        r["elo_p"] = [max(e - pd / 2, 0.02), pd, max(1 - e - pd / 2, 0.02)]


def mat(L, k):
    """arbitro_casa / casa_cheia / publico_medio empurram mandante x visitante; arbitro_empate e classico mexem no empate."""
    out = []
    for r in L:
        x = r["inst"][k]
        if k in ("arbitro_empate", "classico"):
            out.append([[0.0], [x], [0.0]])
        else:
            out.append([[x], [0.0], [-x]])
    return np.array(out, float)


def testar(nome, grupos, k):
    todos = [r for _, te, _, _ in grupos for r in te]
    if not todos or np.allclose(mat(todos, k), 0):
        print(f"| {nome} | - | - | - | - | sem dado |"); return
    g_mes = collections.defaultdict(float); n = 0
    for tr, te, Ptr, Pte in grupos:
        if len(tr) < 300 or not te:
            continue
        b = D.ajusta(mat(tr, k), Ptr, np.array([D.y_de(r) for r in tr]))
        q = D.softmax(np.log(Pte) + mat(te, k) @ b)
        for r, qq, pp in zip(te, q, Pte):
            y = D.y_de(r); g_mes[r["t"].strftime("%Y-%m")] += math.log(qq[y]) - math.log(pp[y]); n += 1
    g = np.array(list(g_mes.values()))
    if len(g) < 3:
        return
    f = g.mean() / (g.std() / math.sqrt(len(g)))
    bt = D.ajusta(mat(todos, k), np.concatenate([x[3] for x in grupos]), np.array([D.y_de(r) for r in todos]))
    print(f"| {nome} | {n} | {bt[0]:+.3f} | {g.sum()/n*1000:+.2f} | {f:+.1f} | "
          f"{'**SINAL REAL**' if f > 2 else ('promissor' if f > 1 else 'nao')} |")


def efeito(L, P):
    print("\n### Efeito direto (resultado real menos o esperado pela regua, em pontos percentuais)\n")
    print("| situacao | jogos | efeito |")
    print("|---|---|---|")
    casos = [("arbitro que historicamente favorece o mandante (+4 pts ou mais)", lambda r: r["inst"]["arbitro_casa"] >= 0.04, 0, "vitoria do mandante"),
             ("arbitro que historicamente prejudica o mandante (-4 pts ou menos)", lambda r: r["inst"]["arbitro_casa"] <= -0.04, 0, "vitoria do mandante"),
             ("arbitro de muitos empates (+3 pts ou mais)", lambda r: r["inst"]["arbitro_empate"] >= 0.03, 1, "empate"),
             ("arbitro de poucos empates (-3 pts ou menos)", lambda r: r["inst"]["arbitro_empate"] <= -0.03, 1, "empate"),
             ("casa cheia (publico 30% acima da media do mandante)", lambda r: r["inst"]["casa_cheia"] >= math.log(1.3), 0, "vitoria do mandante"),
             ("casa vazia (publico 30% abaixo da media do mandante)", lambda r: r["inst"]["casa_cheia"] <= math.log(0.7), 0, "vitoria do mandante"),
             ("classico local (times a menos de 60 km)", lambda r: r["inst"]["classico"] == 1, 1, "empate"),
             ("classico local (times a menos de 60 km)", lambda r: r["inst"]["classico"] == 1, 0, "vitoria do mandante")]
    for nome, cond, k, oque in casos:
        sel = [(r, p) for r, p in zip(L, P) if cond(r)]
        if len(sel) < 40:
            print(f"| {nome} | {len(sel)} | poucos jogos |"); continue
        obs = np.mean([D.y_de(r) == k for r, _ in sel]); esp = np.mean([p[k] for _, p in sel])
        se = math.sqrt(esp * (1 - esp) / len(sel))
        print(f"| {nome} | {len(sel)} | {oque} {100*(obs-esp):+.1f} (z {(obs-esp)/se:+.1f}) |")


FAT = [("arbitro_casa", "arbitro: historico de vitoria do mandante"), ("arbitro_empate", "arbitro: historico de empates"),
       ("casa_cheia", "casa cheia x vazia (publico do jogo)"), ("publico_medio", "publico medio do mandante"),
       ("classico", "classico local -> empate")]


def main():
    J = D.carregar(); D.elo(J); elo_prob(J); D.casar_odds(J); fatores(J)
    alvo = [r for r in J if r["liga"] in D.LIGAS and r["t"].year >= 2021]
    alvo = [r for r in alvo if r["t"] >= alvo[0]["t"] + D.dt.timedelta(days=150)]
    print("# Camada institucional: arbitro, publico e classico x forca e odds\n")
    print(f"Jogos de liga: {len(alvo)}; com arbitro: {sum(1 for r in alvo if r.get('arbitro'))}; "
          f"classicos locais: {sum(r['inst']['classico'] for r in alvo)}\n")
    for titulo, filtro in (("Brasil (Serie A, B e C)", lambda r: r["liga"].startswith("Brasileirao")),
                           ("Europa", lambda r: not r["liga"].startswith("Brasileirao"))):
        L = [r for r in alvo if filtro(r)]
        blocos = sorted({(r["t"].year, (r["t"].month - 1) // 3) for r in L})
        grupos = []
        for b in blocos[4:]:
            tr = [r for r in L if (r["t"].year, (r["t"].month - 1) // 3) < b]
            te = [r for r in L if (r["t"].year, (r["t"].month - 1) // 3) == b]
            if len(tr) < 300 or not te:
                continue
            Pte, Ptr = D.base_elo(tr, te)
            grupos.append((tr, te, Ptr, Pte))
        print(f"\n## Regua: forca pelo Elo - {titulo}\n")
        print("| fator | jogos testados | peso | ganho por 1000 jogos | forca | veredito |")
        print("|---|---|---|---|---|---|")
        for k, nome in FAT:
            testar(nome, grupos, k)
        efeito([r for _, te, _, _ in grupos for r in te], np.concatenate([g[3] for g in grupos]))
    for titulo, chave, filtro in (("odd de ABERTURA - Europa", "o_avgo", lambda r: not r["liga"].startswith("Brasileirao")),
                                  ("odd de FECHAMENTO - Europa", "o_avg", lambda r: not r["liga"].startswith("Brasileirao")),
                                  ("odd de FECHAMENTO - Brasileirao A", "o_avg", lambda r: r["liga"] == "Brasileirao A")):
        L = [r for r in alvo if filtro(r) and chave in r]
        grupos = D.por_temporada(L, lambda S: np.array([D.prob(r[chave]) for r in S]))
        print(f"\n## Regua: {titulo} ({len(L)} jogos)\n")
        print("| fator | jogos testados | peso | ganho por 1000 jogos | forca | veredito |")
        print("|---|---|---|---|---|---|")
        for k, nome in FAT:
            testar(nome, grupos, k)
        efeito([r for _, te, _, _ in grupos for r in te], np.concatenate([g[3] for g in grupos]) if grupos else [])


if __name__ == "__main__":
    main()
