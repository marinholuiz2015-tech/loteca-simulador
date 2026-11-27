"""
Cada jogo e um caso: o fator que nao pesa na media pode pesar num contexto especifico?

Para cada KPI (os de motor/kpis.py + os sinais novos da escada) e cada contexto, mede a forca
sobre as odds no teste no tempo, so dentro daquele contexto:
  Brasil x Europa (pelo local do estadio)
  Reta final (8 rodadas ou menos) x resto do campeonato
  Jogo equilibrado (diferenca entre mandante e visitante < 15 pts) x favorito claro (> 30 pts)
  Favorito em casa x favorito fora
  Brasil na reta final / Brasil equilibrado (cruzamentos mais citados)

Fatiar muito gera achado falso por acaso (com ~200 testes, alguns passam de 2 sozinhos). Por isso
so conta como achado o que passa de 2 no total E e positivo nas DUAS metades do periodo de teste
(o comeco e o fim do historico) - um padrao de verdade aparece nas duas.
Uso: python motor/lab_contexto.py > motor/lab_contexto.md
"""
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import kpis as K  # noqa: E402
import lab_escada as E  # noqa: E402


def brasil(b, f):
    try:
        lat, lon = float(f.get("lat")), float(f.get("lon"))
        return lon < -30 and lat < 6
    except Exception:
        return None


def contexto(b, f, k):
    p = K.aplica(b[1], None) if False else None  # noqa: F841
    from calibracao import sem_margem
    p = sem_margem(b[1])
    br = brasil(b, f)
    m = E.MOT.get(k)
    reta = None if not m else (min(m[0]["restam"], m[1]["restam"]) <= 8)
    dif = abs(p[0] - p[2])
    return {"br": br, "reta": reta, "equil": dif < 0.15, "claro": dif > 0.30, "fav_casa": p[0] >= p[2]}


CTX = [("Brasil", lambda c: c["br"] is True), ("Europa", lambda c: c["br"] is False),
       ("Reta final (8 rodadas ou menos)", lambda c: c["reta"] is True), ("Antes da reta final", lambda c: c["reta"] is False),
       ("Jogo equilibrado", lambda c: c["equil"]), ("Favorito claro", lambda c: c["claro"]),
       ("Favorito em casa", lambda c: c["fav_casa"]), ("Favorito fora", lambda c: not c["fav_casa"]),
       ("Brasil + reta final", lambda c: c["br"] is True and c["reta"] is True),
       ("Brasil + jogo equilibrado", lambda c: c["br"] is True and c["equil"])]


def forca(d):
    return d.mean() / (d.std(ddof=1) / math.sqrt(len(d))) if len(d) > 2 and d.std() > 0 else 0.0


def main():
    E.CHUVA, E.MOT, E.COPA = E.montar_mapas()
    K.KPIS.update(E.NOVOS)
    K.NOMES[:] = list(K.KPIS)
    K.LADO[:] = [n for n in K.NOMES if K.KPIS[n][1] == "lado"]
    K.EMP[:] = [n for n in K.NOMES if K.KPIS[n][1] == "empate"]
    cx = K.Contexto().carregar(abertos=False)
    fat = {(int(r["concurso"]), int(r["jogo"])): r for r in K.ler(os.path.join(K.DADOS, "sentinela_jogos.csv"))}
    base = K.base_historica(cx)
    # base_historica nao guarda o jogo: refaz a ordem com arena_odds para achar (c, j)
    chaves = []
    for r in K.ler(os.path.join(K.DADOS, "arena_odds.csv")):
        if r.get("resultado"):
            chaves.append((int(r["concurso"]), int(r["jogo"])))
    chaves.sort(key=lambda x: x[0])
    ctx = [contexto(b, fat.get(k, {}), k) for b, k in zip(base, chaves)]
    kpis = [n for n in K.NOMES if not n.startswith(("Movimento", "Noticias"))]
    print("# Cada jogo e um caso: fatores dentro de cada contexto x odds (teste no tempo)\n")
    print(f"Jogos da Loteca com odd: {len(base)}. Testes feitos: {len(kpis)} fatores x {len(CTX)} contextos.\n")
    achados, quase, n_testes = [], [], 0
    for nome_c, filt in CTX:
        idx = [i for i, c in enumerate(ctx) if filt(c)]
        for n in kpis:
            sub = [base[i] for i in idx if base[i][2][n] is not None]
            if len(sub) < 300 or len({b[0] for b in sub}) < 40:
                continue
            pm, pk, am, ak = K.teste_no_tempo(sub, [n], a_cada=25)
            n_testes += 1
            d = pm - pk
            if len(d) < 100:
                continue
            f_tot, h = forca(d), len(d) // 2
            f1, f2 = forca(d[:h]), forca(d[h:])
            lin = (nome_c, n, len(d), f_tot, f1, f2, 100 * am.mean(), 100 * ak.mean())
            if f_tot > 2 and f1 > 0 and f2 > 0:
                achados.append(lin)
            elif f_tot > 1.5:
                quase.append(lin)
    print(f"Testes com jogos suficientes: {n_testes}. Por acaso, esperam-se cerca de {max(1, round(n_testes * 0.023))} "
          f"passando de 2.\n")
    cab = "| contexto | fator | jogos testados | forca | 1a metade | 2a metade | acerto odd | acerto modelo |\n|---|---|---|---|---|---|---|---|"
    print("## Achados (forca > 2 no total e positivo nas duas metades do tempo)\n")
    print(cab if achados else "Nenhum.")
    for l in sorted(achados, key=lambda x: -x[3]):
        print(f"| {l[0]} | {l[1]} | {l[2]} | {l[3]:+.1f} | {l[4]:+.1f} | {l[5]:+.1f} | {l[6]:.1f}% | {l[7]:.1f}% |")
    print("\n## Perto (forca entre 1,5 e 2, ou acima de 2 so numa metade)\n")
    print(cab if quase else "Nenhum.")
    for l in sorted(quase, key=lambda x: -x[3]):
        print(f"| {l[0]} | {l[1]} | {l[2]} | {l[3]:+.1f} | {l[4]:+.1f} | {l[5]:+.1f} | {l[6]:.1f}% | {l[7]:.1f}% |")


if __name__ == "__main__":
    main()
