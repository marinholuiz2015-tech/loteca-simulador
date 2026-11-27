"""
Escada: os sinais fracos somados num modelo so, nos jogos da Loteca, contra as odds (teste no tempo).

Parte dos KPIs ja existentes (motor/kpis.py, jogos da Loteca com odd da Arena) e acrescenta os
sinais que ficaram perto do criterio em outros estudos:
  Empate da Loteca     constante: o empate sai acima da odd na Loteca
  Chuva prevista       4 mm ou mais na previsao de 2 dias antes (lab_chuva) -> empate
  Motivacao            sem nada em jogo / luta contra o rebaixamento (tabela antes do jogo, football-data)
  Dois sem nada        os dois times sem nada em jogo -> empate
  Copa em 4 dias       time que joga Libertadores/Sul-Americana/Copa do Brasil logo depois (pode poupar)

Quatro modelos, todos aprendendo so com concursos anteriores:
  A) todos os KPIs juntos (como hoje)
  B) selecao no tempo: a cada 20 concursos, entram so os KPIs que ja tinham forca > 1 NO PASSADO
  C) so os sinais novos
  D) conjunto pre-escolhido dos "promissores" (cuidado: escolhido olhando estudos que usaram parte
     dos mesmos jogos - serve de teto otimista, nao de prova)
Uso: python motor/lab_escada.py > motor/lab_escada.md
"""
import bisect
import collections
import csv
import datetime as dt
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import fd_base  # noqa: E402
import kpis as K  # noqa: E402
import motivacao as M  # noqa: E402

DADOS = os.path.join(RAIZ, "coleta", "dados")
COPAS = {"Copa do Brasil", "Libertadores", "Sul-Americana"}


def ler(a):
    return list(csv.DictReader(open(a, encoding="utf-8"))) if os.path.exists(a) else []


# ---------------------------------------------------------------- dados auxiliares
def estados_fd():
    """(data, casa, fora) -> (estado mandante, estado visitante) antes do jogo, todas as ligas com tabela."""
    out = collections.defaultdict(list)
    for (liga, temp), js in M.temporadas().items():
        times = sorted({g["casa"] for g in js} | {g["fora"] for g in js})
        n = len(times)
        if n < 10:
            continue
        T = M.Tabela(liga, times, 2 * (n - 1))
        js = sorted((g for g in js if g["gc"] is not None), key=lambda g: g["d"])
        i = 0
        while i < len(js):
            dia = [g for g in js[i:] if g["d"] == js[i]["d"]]
            for g in dia:
                out[g["d"]].append((g["casa"], g["fora"], T.estado(g["casa"]), T.estado(g["fora"])))
            for g in dia:
                T.soma(g["casa"], g["fora"], g["gc"], g["gf"], g["d"])
            i += len(dia)
    return out


def calendario_fotmob():
    cal = collections.defaultdict(list)
    for r in ler(os.path.join(DADOS, "fotmob_jogos.csv")):
        try:
            t = dt.datetime.fromisoformat(r["data_utc"].replace("Z", "+00:00"))
        except Exception:
            continue
        for nome in (r["casa"], r["fora"]):
            cal[nome].append((t, r["liga"]))
    for v in cal.values():
        v.sort()
    return cal


def montar_mapas():
    sent = {(int(r["concurso"]), int(r["jogo"])): r for r in ler(os.path.join(DADOS, "sentinela_jogos.csv"))}
    chuva = {(int(r["concurso"]), int(r["jogo"])): float(r["chuva_prevista_2d_mm"] or 0)
             for r in ler(os.path.join(DADOS, "chuva_prevista.csv")) if r.get("chuva_prevista_2d_mm") not in (None, "")}
    est = estados_fd()
    cal = calendario_fotmob()
    mot, copa = {}, {}
    for k, r in sent.items():
        try:
            t = dt.datetime.fromisoformat(r["inicio_utc"].replace("Z", "+00:00"))
        except Exception:
            continue
        # motivacao: casa o jogo da Loteca com o jogo do football-data (data +-1, nomes parecidos)
        melhor, ms = None, 0
        for dd in (-1, 0, 1):
            for casa, fora, eh, ea in est.get(t.date() + dt.timedelta(days=dd), []):
                s = min(fd_base.sim(r["fot_casa"] or r["mandante"], casa), fd_base.sim(r["fot_fora"] or r["visitante"], fora))
                if s > ms:
                    melhor, ms = (eh, ea), s
        if melhor and ms >= 0.75:
            mot[k] = melhor
        # copa nos 4 dias seguintes (calendario FotMob, mesmos nomes do sentinela)
        def joga_copa(nome):
            L = cal.get(nome)
            if not L:
                return None
            i = bisect.bisect_right([x[0] for x in L], t + dt.timedelta(hours=3))
            return int(any(lg in COPAS and (tt - t).total_seconds() / 86400 <= 4.2 for tt, lg in L[i:i + 3]))
        a, b = joga_copa(r.get("fot_casa")), joga_copa(r.get("fot_fora"))
        if a is not None and b is not None:
            copa[k] = (a, b)
    return chuva, mot, copa


CHUVA, MOT, COPA = {}, {}, {}


def k_empate_loteca(f, k, p, cx):
    return 1.0


def k_chuva_prev(f, k, p, cx):
    v = CHUVA.get(k)
    return None if v is None else (1.0 if v >= 4 else 0.0)


def k_motivacao(f, k, p, cx):
    m = MOT.get(k)
    if not m:
        return None
    eh, ea = m
    v = 0.0
    if eh["morto"] and not ea["morto"]:
        v -= 1
    if ea["morto"] and not eh["morto"]:
        v += 1
    return v


def k_luta(f, k, p, cx):
    m = MOT.get(k)
    if not m:
        return None
    eh, ea = m
    return float(bool(eh["luta"]) and not ea["morto"]) - float(bool(ea["luta"]) and not eh["morto"])


def k_dois_mortos(f, k, p, cx):
    m = MOT.get(k)
    return None if not m else float(m[0]["morto"] and m[1]["morto"])


def k_copa(f, k, p, cx):
    c = COPA.get(k)
    return None if c is None else float(c[1] - c[0])  # + = visitante pode poupar (bom para o mandante)


NOVOS = {
    "Empate da Loteca (constante)": (k_empate_loteca, "empate", "Loteca", "o empate sai acima da odd na Loteca"),
    "Chuva prevista (4 mm+)": (k_chuva_prev, "empate", "Ambiente", "previsao de chuva de 2 dias antes"),
    "Motivacao: sem nada em jogo": (k_motivacao, "lado", "Institucional", "+1 visitante sem nada em jogo, -1 mandante"),
    "Motivacao: luta contra a queda": (k_luta, "lado", "Institucional", "+1 mandante lutando, -1 visitante"),
    "Dois sem nada em jogo": (k_dois_mortos, "empate", "Institucional", "os dois times sem nada em jogo"),
    "Copa em ate 4 dias (poupar)": (k_copa, "lado", "Situacional", "visitante - mandante com copa logo depois"),
}
PROMISSORES = ["Empate da Loteca (constante)", "Chuva prevista (4 mm+)", "Motivacao: sem nada em jogo",
               "Copa em ate 4 dias (poupar)", "Rodizio / time reserva", "Viagem do visitante", "Altitude",
               "Confronto direto (H2H)"]


def teste_selecao(base, a_cada=20, limiar=1.0):
    """Modelo B: a cada bloco, escolhe os KPIs pela forca medida SO no passado e preve o bloco seguinte."""
    cs = np.array([b[0] for b in base]); unicos = np.unique(cs)
    inicio = unicos[len(unicos) // 3]
    V = np.array([[b[2][n] if b[2][n] is not None else 0.0 for n in K.NOMES] for b in base])
    Y = np.array([b[3] for b in base])
    pm, pk, am, ak = [], [], [], []
    escolhas = []
    blocos = [c for c in unicos if c >= inicio]
    for bi in range(0, len(blocos), a_cada):
        bloco = blocos[bi:bi + a_cada]
        c0 = bloco[0]
        passado = [b for b in base if b[0] < c0]
        ativos = []
        for n in K.NOMES:
            sub = [b for b in passado if b[2][n] is not None]
            if len(sub) < 300:
                continue
            r = K.resumo(*K.teste_no_tempo(sub, [n], a_cada=30))
            if r["forca"] > limiar:
                ativos.append(n)
        escolhas.append((c0, ativos))
        antes = cs < c0
        calib = K.aprende([(base[j][1], base[j][3]) for j in np.where(antes)[0]], usar_empate=False, usar_gama=True)
        LP = np.log(np.array([K.aplica(b[1], calib) for b in base]))
        w = K.ajustar(LP[antes], V[antes], Y[antes], ativos) if ativos else np.zeros(len(K.NOMES))
        idx = np.where(np.isin(cs, bloco))[0]
        q = K.probs(LP[idx], V[idx], w); p = np.exp(LP[idx])
        for t, j in enumerate(idx):
            pm.append(-math.log(p[t, Y[j]])); pk.append(-math.log(q[t, Y[j]]))
            am.append(int(np.argmax(p[t]) == Y[j])); ak.append(int(np.argmax(q[t]) == Y[j]))
    return (np.array(pm), np.array(pk), np.array(am), np.array(ak)), escolhas


def linha(nome, r):
    v = "**SINAL REAL**" if r["forca"] > 2 else ("promissor" if r["forca"] > 1 else "nao")
    print(f"| {nome} | {r['jogos']} | {r['forca']:+.1f} | {100*r['acerto_mercado']:.1f}% | {100*r['acerto_modelo']:.1f}% | {v} |")


def main():
    global CHUVA, MOT, COPA
    CHUVA, MOT, COPA = montar_mapas()
    K.KPIS.update(NOVOS)
    K.NOMES[:] = list(K.KPIS)
    K.LADO[:] = [n for n in K.NOMES if K.KPIS[n][1] == "lado"]
    K.EMP[:] = [n for n in K.NOMES if K.KPIS[n][1] == "empate"]
    cx = K.Contexto().carregar(abertos=False)
    base = K.base_historica(cx)
    print("# Escada: sinais fracos somados x odds (jogos da Loteca, teste no tempo)\n")
    print(f"Jogos da Loteca com odd e resultado: {len(base)} em {len({b[0] for b in base})} concursos. "
          f"Cobertura dos novos: chuva {sum(b[2]['Chuva prevista (4 mm+)'] is not None for b in base)}, "
          f"motivacao {sum(b[2]['Motivacao: sem nada em jogo'] is not None for b in base)}, "
          f"copa {sum(b[2]['Copa em ate 4 dias (poupar)'] is not None for b in base)}.\n")
    print("## Cada sinal novo sozinho\n")
    print("| sinal | jogos | forca | acerto odd | acerto modelo | veredito |\n|---|---|---|---|---|---|")
    for n in NOVOS:
        sub = [b for b in base if b[2][n] is not None]
        if len(sub) >= 300:
            linha(n, K.resumo(*K.teste_no_tempo(sub, [n], a_cada=20)))
        else:
            print(f"| {n} | {len(sub)} | - | - | - | poucos jogos |")
    medidos = [n for n in K.NOMES if sum(b[2][n] is not None for b in base) >= K.MIN_JOGOS_KPI
               and not n.startswith("Movimento")]
    print("\n## Modelos combinados\n")
    print("| modelo | jogos | forca | acerto odd | acerto modelo | veredito |\n|---|---|---|---|---|---|")
    linha("A) todos os KPIs juntos", K.resumo(*K.teste_no_tempo(base, medidos)))
    rB, escolhas = teste_selecao(base)
    linha("B) selecao no tempo (so KPIs com forca > 1 no passado)", K.resumo(*rB))
    linha("C) so os sinais novos", K.resumo(*K.teste_no_tempo(base, list(NOVOS))))
    linha("D) promissores pre-escolhidos (teto otimista)", K.resumo(*K.teste_no_tempo(base, PROMISSORES)))
    print("\n### O que a selecao no tempo escolheu em cada bloco\n")
    for c0, at in escolhas:
        print(f"- a partir do concurso {c0}: {', '.join(at) if at else 'nenhum (fica so a odd)'}")


if __name__ == "__main__":
    main()
