"""
Camada humana pelo jogador: time poupado/desfalcado, cansaco de cada titular, jogador fora de forma,
recem-chegado e tecnico novo - rendem diferente do que a forca (Elo) e a odd indicam?

Base: coleta/dados/fotmob_escalacoes.csv (titulares de cada jogo, valor de mercado, nota) +
fotmob_jogos.csv. Brasileirao A, B e C desde 2023.

Fatores de cada time no jogo:
  fora_costume quantos dos 11 que mais jogaram nos 10 jogos anteriores ficaram fora (desfalque/poupado)
  valor_xi     log(valor dos 11 titulares / mediana do valor dos 11 nos 8 jogos anteriores do time)
               -> abaixo de 0 = time poupado ou desfalcado
  desc_jog     dias medios desde o ultimo jogo de cada titular (ate 14) -> cansaco do jogador
  cansados     titulares com 3 dias ou menos desde o ultimo jogo
  forma        nota media dos titulares nos 5 jogos anteriores de cada um, menos a media da temporada dele
  novatos      titulares com ate 3 jogos pelo time (recem-chegados)
  tecnico_novo tecnico com ate 3 jogos no time

Importante: a escalacao confirmada sai cerca de 1 hora antes do jogo, depois que a Loteca fecha.
O teste mede quanto vale SABER antes esses fatos (pelo Cartola, pelas noticias, pela entrevista do
tecnico). Contra o Elo mede o tamanho do efeito; contra a odd de fechamento a comparacao e dura,
porque essa odd ja conhece a escalacao.
Uso: python motor/lab_jogadores.py > motor/lab_jogadores.md
"""
import collections
import csv
import math
import os
import statistics
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import lab_desgaste as D  # noqa: E402

RAIZ = os.path.dirname(AQUI)
ESC = os.path.join(RAIZ, "coleta", "dados", "fotmob_escalacoes.csv")
FAT = ["fora_costume", "valor_xi", "desc_jog", "cansados", "forma", "novatos", "tecnico_novo"]


def fatores_jogador(J):
    por_jogo = collections.defaultdict(lambda: {"1": [], "2": []})
    tec = {}
    for r in csv.DictReader(open(ESC, encoding="utf-8")):
        por_jogo[r["match_id"]][r["lado"]].append(r)
        tec[(r["match_id"], r["lado"])] = r["tecnico"]
    ult_jogo = {}                                   # jogador -> data do ultimo jogo como titular
    notas = collections.defaultdict(list)           # jogador -> [(t, nota)]
    jogos_time = collections.defaultdict(int)       # (jogador, time) -> jogos como titular
    hist_valor = collections.defaultdict(list)      # time -> [valor xi]
    hist_tec = collections.defaultdict(list)        # time -> [tecnico]
    hist_xi = collections.defaultdict(list)         # time -> [set de jogadores titulares]
    for r in J:                                     # J esta em ordem de data
        if r["match_id"] not in por_jogo:
            continue
        for lado, tid, chave in (("1", r["casa_id"], "jh"), ("2", r["fora_id"], "ja")):
            xi = por_jogo[r["match_id"]][lado]
            if len(xi) < 9:
                r[chave] = None
                continue
            v = sum(float(p["valor"] or 0) for p in xi)
            hv = hist_valor[tid][-8:]
            med = statistics.median(hv) if len(hv) >= 4 else None
            dias = []
            for p in xi:
                u = ult_jogo.get(p["jogador_id"])
                dias.append(min((r["t"] - u).total_seconds() / 86400, 14.0) if u else 14.0)
            formas = []
            for p in xi:
                ns = [n for _, n in notas[p["jogador_id"]]]
                if len(ns) >= 6:
                    formas.append(statistics.mean(ns[-5:]) - statistics.mean(ns[-30:]))
            t_atual = tec.get((r["match_id"], lado), "")
            ht = hist_tec[tid]
            seq = 0
            for x in reversed(ht):
                if x == t_atual:
                    seq += 1
                else:
                    break
            hx = hist_xi[tid][-10:]
            if len(hx) >= 5:
                cont = collections.Counter(j for s_ in hx for j in s_)
                costume = {j for j, _ in cont.most_common(11)}
                fora = len(costume - {p["jogador_id"] for p in xi})
            else:
                fora = 0
            r[chave] = {"fora_costume": fora, "valor_xi": math.log(v / med) if (med and v > 0) else 0.0,
                        "desc_jog": statistics.mean(dias),
                        "cansados": sum(d <= 3.2 for d in dias),
                        "forma": statistics.mean(formas) if formas else 0.0,
                        "novatos": sum(jogos_time[(p["jogador_id"], tid)] <= 3 for p in xi),
                        "tecnico_novo": int(len(ht) >= 5 and t_atual and seq < 3)}
        # atualiza o historico DEPOIS do jogo (nada do proprio jogo entra nos fatores)
        for lado, tid in (("1", r["casa_id"]), ("2", r["fora_id"])):
            xi = por_jogo[r["match_id"]][lado]
            if not xi:
                continue
            hist_valor[tid].append(sum(float(p["valor"] or 0) for p in xi))
            hist_tec[tid].append(tec.get((r["match_id"], lado), ""))
            hist_xi[tid].append({p["jogador_id"] for p in xi})
            for p in xi:
                ult_jogo[p["jogador_id"]] = r["t"]
                jogos_time[(p["jogador_id"], tid)] += 1
                if p["nota"]:
                    notas[p["jogador_id"]].append((r["t"], float(p["nota"])))


def mat(L, quais):
    out = []
    for r in L:
        cols = [r["jh"][k] - r["ja"][k] for k in quais]
        out.append([cols, [0.0] * len(cols), [-c for c in cols]])
    return np.array(out, float)


def testar(nome, grupos, quais):
    g_mes = collections.defaultdict(float); n = 0
    for tr, te, Ptr, Pte in grupos:
        if len(tr) < 300 or not te:
            continue
        b = D.ajusta(mat(tr, quais), Ptr, np.array([D.y_de(r) for r in tr]))
        q = D.softmax(np.log(Pte) + mat(te, quais) @ b)
        for r, qq, pp in zip(te, q, Pte):
            y = D.y_de(r); g_mes[r["t"].strftime("%Y-%m")] += math.log(qq[y]) - math.log(pp[y]); n += 1
    g = np.array(list(g_mes.values()))
    if len(g) < 3:
        return
    f = g.mean() / (g.std() / math.sqrt(len(g)))
    bt = D.ajusta(mat([r for _, te, _, _ in grupos for r in te], quais),
                  np.concatenate([g_[3] for g_ in grupos]), np.array([D.y_de(r) for _, te, _, _ in grupos for r in te]))
    print(f"| {nome} | {n} | {' '.join(f'{x:+.3f}' for x in bt)} | {g.sum()/n*1000:+.2f} | {f:+.1f} | "
          f"{'**SINAL REAL**' if f > 2 else ('promissor' if f > 1 else 'nao')} |")


def efeito(L, P):
    print("\n### Efeito direto (vitoria do time menos o esperado pela regua, em pontos percentuais)\n")
    print("| situacao | jogos | vitoria vs esperado |")
    print("|---|---|---|")
    casos = [("mandante com 4+ titulares de costume fora", lambda r: r["jh"]["fora_costume"] >= 4, 0),
             ("visitante com 4+ titulares de costume fora", lambda r: r["ja"]["fora_costume"] >= 4, 2),
             ("mandante com 6+ titulares de costume fora (time reserva)", lambda r: r["jh"]["fora_costume"] >= 6, 0),
             ("visitante com 6+ titulares de costume fora (time reserva)", lambda r: r["ja"]["fora_costume"] >= 6, 2),
             ("mandante poupado/desfalcado (11 valem 30% menos que o costume)", lambda r: r["jh"]["valor_xi"] < math.log(0.7), 0),
             ("visitante poupado/desfalcado (11 valem 30% menos que o costume)", lambda r: r["ja"]["valor_xi"] < math.log(0.7), 2),
             ("mandante com 3+ titulares cansados (<=3 dias)", lambda r: r["jh"]["cansados"] >= 3, 0),
             ("visitante com 3+ titulares cansados (<=3 dias)", lambda r: r["ja"]["cansados"] >= 3, 2),
             ("mandante em boa fase (notas recentes +0,3 acima)", lambda r: r["jh"]["forma"] > 0.3, 0),
             ("mandante em ma fase (notas recentes -0,3 abaixo)", lambda r: r["jh"]["forma"] < -0.3, 0),
             ("visitante em ma fase (notas recentes -0,3 abaixo)", lambda r: r["ja"]["forma"] < -0.3, 2),
             ("mandante com 3+ recem-chegados no time", lambda r: r["jh"]["novatos"] >= 3, 0),
             ("mandante com tecnico novo (ate 3 jogos)", lambda r: r["jh"]["tecnico_novo"] == 1, 0),
             ("visitante com tecnico novo (ate 3 jogos)", lambda r: r["ja"]["tecnico_novo"] == 1, 2)]
    for nome, cond, k in casos:
        sel = [(r, p) for r, p in zip(L, P) if cond(r)]
        if len(sel) < 40:
            print(f"| {nome} | {len(sel)} | poucos jogos |"); continue
        obs = np.mean([D.y_de(r) == k for r, _ in sel]); esp = np.mean([p[k] for _, p in sel])
        se = math.sqrt(esp * (1 - esp) / len(sel))
        print(f"| {nome} | {len(sel)} | {100*(obs-esp):+.1f} (z {(obs-esp)/se:+.1f}) |")


def main():
    J = D.carregar(); D.elo(J); D.casar_odds(J); fatores_jogador(J)
    alvo = [r for r in J if r["liga"].startswith("Brasileirao") and r.get("jh") and r.get("ja")]
    print("# Camada humana pelo jogador x forca (Elo) e odds\n")
    print(f"Jogos do Brasileirao com as duas escalacoes: {len(alvo)} "
          f"({collections.Counter(r['liga'] for r in alvo).most_common()})\n")
    blocos = sorted({(r["t"].year, (r["t"].month - 1) // 3) for r in alvo})
    grupos = []
    for b in blocos[2:]:
        tr = [r for r in alvo if (r["t"].year, (r["t"].month - 1) // 3) < b]
        te = [r for r in alvo if (r["t"].year, (r["t"].month - 1) // 3) == b]
        if len(tr) < 300 or not te:
            continue
        Pte, Ptr = D.base_elo(tr, te)
        grupos.append((tr, te, Ptr, Pte))
    print("## Regua: forca pelo Elo (Serie A, B e C)\n")
    print("| fator (mandante - visitante) | jogos testados | peso | ganho por 1000 jogos | forca | veredito |")
    print("|---|---|---|---|---|---|")
    for k in FAT:
        testar(k, grupos, [k])
    testar("todos juntos", grupos, FAT)
    efeito([r for _, te, _, _ in grupos for r in te], np.concatenate([g[3] for g in grupos]))

    L = [r for r in alvo if r["liga"] == "Brasileirao A" and "o_avg" in r]
    gr = D.por_temporada(L, lambda S: np.array([D.prob(r["o_avg"]) for r in S]))
    print(f"\n## Regua: odd de FECHAMENTO - Brasileirao A ({len(L)} jogos; essa odd ja conhece a escalacao)\n")
    print("| fator (mandante - visitante) | jogos testados | peso | ganho por 1000 jogos | forca | veredito |")
    print("|---|---|---|---|---|---|")
    for k in FAT:
        testar(k, gr, [k])
    testar("todos juntos", gr, FAT)


if __name__ == "__main__":
    main()
