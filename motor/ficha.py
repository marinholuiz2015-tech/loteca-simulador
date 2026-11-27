"""
Ficha de cada jogo do concurso aberto: as camadas do mapa mental somando num score 0-100 com confianca A-E.

  Estatistica   chance do motor e da odd, empate da Loteca, chuva prevista
  Performance   Cartola (forca da escalacao provavel, desfalques), FotMob (lesionados/suspensos, descanso, rodizio)
  Institucional motivacao/tabela e os alertas do motor (descanso, calendario)
  Humana        fatos que a IA leu nas noticias (com a fonte), canais de Loteca, massa da Vovoteca

Score = chance (%) da marca principal pelo motor. Confianca segue o Sistema de Excelencia:
  A, B -> SECO (A: 60%+ de chance)   C, D -> DUPLO (C: o duplo cobre 78%+)   E -> TRIPLO
Cada fato humano CONTRA o favorito acende um "atencao" e rebaixa a confianca um degrau. Isso nao muda a
probabilidade do motor (esses fatores ainda nao passaram no teste de sinal real; o efeito medido de
cada um vai junto no texto) - serve para voce decidir onde proteger.
"""
import csv
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DADOS = os.path.join(RAIZ, "coleta", "dados")
R = "1X2"
CLASSES = "ABCDE"


def ultimos(arq, concurso, chave):
    """linha mais recente de cada chave (coletas repetidas na semana: vale a ultima)."""
    out = {}
    try:
        for r in csv.DictReader(open(os.path.join(DADOS, arq), encoding="utf-8")):
            if str(r.get("concurso")) != str(concurso):
                continue
            k = chave(r)
            if k not in out or r.get("coletado_em_utc", "") >= out[k].get("coletado_em_utc", ""):
                out[k] = r
    except FileNotFoundError:
        pass
    return out


def todos(arq, concurso):
    try:
        return [r for r in csv.DictReader(open(os.path.join(DADOS, arq), encoding="utf-8"))
                if str(r.get("concurso")) == str(concurso)]
    except FileNotFoundError:
        return []


def f(x, d=None):
    try:
        return float(x)
    except Exception:
        return d


def jl(x):
    try:
        return json.loads(x) if x else []
    except Exception:
        return []


def pc(x):
    return f"{100 * x:.0f}%"


def fichas(concurso, jogos):
    """jogos: lista do painel (jogo, mandante, visitante, p, classe, duplo, alertas). Devolve {jogo: ficha}."""
    noticias = ultimos("noticias_aberto.csv", concurso, lambda r: int(r["jogo"]))
    cartola = ultimos("cartola_aberto.csv", concurso, lambda r: (int(r["jogo"]), r["lado"]))
    sent = ultimos("sentinela_aberto.csv", concurso, lambda r: int(r["jogo"]))
    massa = ultimos("vovoteca_massa_aberto.csv", concurso, lambda r: int(r["jogo"]))
    infl = {}
    vistos = set()
    for r in todos("influenciadores_palpites.csv", concurso):
        k = (r["jogo"], r["fonte"], r["trecho"][:60])
        if k in vistos:
            continue
        vistos.add(k)
        infl.setdefault(int(r["jogo"]), []).append(r)
    esp = {}
    for r in todos("especialistas_palpites.csv", concurso):
        esp.setdefault(int(r["jogo"]), {})[r["fonte"]] = r

    out = {}
    for j in jogos:
        n, p = j["jogo"], j["p"]
        fav = max(range(3), key=lambda k: p[k])
        lado_fav = {0: "mandante", 2: "visitante"}.get(fav)
        nome = {"mandante": j["mandante"], "visitante": j["visitante"]}
        cam = {"estatistica": [], "performance": [], "institucional": [], "humana": []}
        atencao = []

        # ---- Estatistica
        cam["estatistica"].append(f"Motor: 1 {pc(p[0])} · X {pc(p[1])} · 2 {pc(p[2])}")
        if p[1] >= 0.29:
            cam["estatistica"].append("Jogo com cara de empate: na Loteca o empate sai ~1,6 ponto acima do que a odd indica.")
        s = sent.get(n, {})
        chuva = f(s.get("chuva_mm"))
        if chuva is not None:
            if chuva >= 4:
                cam["estatistica"].append(f"Chuva prevista {chuva:.0f} mm: com chuva o empate subiu de 25% para 38% no histórico.")
                if fav != 1:
                    atencao.append(f"chuva prevista ({chuva:.0f} mm) puxa para o empate")
            else:
                cam["estatistica"].append(f"Tempo seco ou chuva fraca ({chuva:.0f} mm).")

        # ---- Performance (Cartola + FotMob)
        for lado in ("mandante", "visitante"):
            c = cartola.get((n, lado))
            if c:
                fp = f(c.get("forca_pct"))
                ds = jl(c.get("desfalques"))
                txt = f"{nome[lado]} (Cartola): escalação provável com {fp:.0f}% da força do elenco" if fp is not None else \
                      f"{nome[lado]} (Cartola): sem escalação provável ainda"
                if ds:
                    txt += " · fora: " + ", ".join(f"{d['nome']} ({d['status']})" for d in ds[:4])
                cam["performance"].append(txt)
                if lado == lado_fav and fp is not None and fp < 85:
                    atencao.append(f"favorito deve ir com escalação {100 - fp:.0f}% mais fraca (time reserva rende 2 a 3 pontos abaixo)")
        if s:
            for lado, pre in (("mandante", "casa"), ("visitante", "fora")):
                dn = int(f(s.get(f"desf_{pre}_n"), 0) or 0)
                if dn:
                    cam["performance"].append(f"{nome[lado]} (FotMob): {dn} desfalques "
                                              f"({int(f(s.get(f'desf_{pre}_lesao'), 0) or 0)} lesão, {int(f(s.get(f'desf_{pre}_susp'), 0) or 0)} suspensão)")
            dc, dfo = f(s.get("dias_casa")), f(s.get("dias_fora"))
            if dc is not None and dfo is not None:
                cam["performance"].append(f"Descanso: mandante {dc:.0f} dias, visitante {dfo:.0f} dias")
            dfav = f(s.get("desf_casa_n" if fav == 0 else "desf_fora_n"), 0) if lado_fav else 0
            dout = f(s.get("desf_fora_n" if fav == 0 else "desf_casa_n"), 0) if lado_fav else 0
            if lado_fav and dfav >= 4 and dfav >= dout + 2:
                atencao.append(f"favorito com {dfav:.0f} desfalques (o adversário tem {dout:.0f})")

        # ---- Institucional (motivacao, tabela, alertas do motor)
        for a in j.get("alertas") or []:
            cam["institucional"].append(a)
            al = a.lower()
            if lado_fav and (("nada em jogo" in al or "já é campeão" in al or "livre do rebaixamento" in al
                              or "já está rebaixado" in al) and lado_fav in al):
                atencao.append(f"motivação: {a}")

        # ---- Humana (noticias pela IA, canais, especialistas, massa)
        nt = noticias.get(n)
        if nt:
            for x in jl(nt.get("fatos_ia"))[:5]:
                quem = nome.get(x.get("time"), x.get("time", ""))
                cam["humana"].append(f"{quem}: {x.get('fato', '')} ({x.get('fonte', 'notícia')})")
            nota = f(nt.get("nota_modelo"))
            if nota is not None and nt.get("motivo_modelo"):
                mot = nt["motivo_modelo"]
                mot = mot if len(mot) <= 260 else mot[:mot.rfind(" ", 0, 260)] + "…"
                cam["humana"].append(f"Leitura da IA (nota {nota:+.0f} para o mandante): {mot}")
                if (fav == 0 and nota <= -1) or (fav == 2 and nota >= 1):
                    atencao.append("as notícias da semana pesam contra o favorito")
        for r in infl.get(n, [])[:4]:
            cam["humana"].append(f"{r['fonte']}: {r['trecho']}" + (f" (palpite {r['palpite']})" if r["palpite"] in ("1", "X", "2", "1X", "X2", "12") else ""))
        for fonte, r in esp.get(n, {}).items():
            cam["humana"].append(f"{fonte.capitalize()}: seco {r['seco']}" + (f", duplo {r['duplo']}" if r.get("duplo") else "")
                                 + (" · zebra da rodada" if r.get("zebra") else ""))
        m = massa.get(n)
        if m and m.get("massa_1"):
            mm = [f(m["massa_1"], 0) / 100, f(m["massa_x"], 0) / 100, f(m["massa_2"], 0) / 100]
            cam["humana"].append(f"Massa (Vovoteca): 1 {pc(mm[0])} · X {pc(mm[1])} · 2 {pc(mm[2])}")
            if mm[fav] - p[fav] >= 0.20:
                cam["humana"].append("A massa está bem mais confiante que o motor neste jogo: se a zebra vier, o rateio paga mais.")

        # ---- Score e confianca
        acao = j.get("classe") or "SECO"
        if acao == "SECO":
            score = p[fav]
            cl = 0 if p[fav] >= 0.60 else 1
            marca = R[fav]
        elif acao == "DUPLO":
            marca = j.get("duplo") or ""
            score = sum(p[R.index(c)] for c in marca) if marca else p[fav]
            cl = 2 if score >= 0.78 else 3
        else:
            marca, score, cl = "1X2", 1.0, 4
        cl_motor = cl
        if atencao and cl < 4:
            cl += 1
        out[n] = {"score": round(100 * (p[fav] if acao != "SECO" else score)), "acao": acao, "marca": marca,
                  "cobertura": round(score, 3), "confianca": CLASSES[cl], "confianca_motor": CLASSES[cl_motor],
                  "atencao": atencao, "camadas": cam}
    return out
