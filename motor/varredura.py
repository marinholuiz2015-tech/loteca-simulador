"""
Varredura semanal de nuances: onde as odds erram de forma consistente.

Cruza tipos de jogo (equilibrado, favorito forte em casa, favorito fora, Brasil,
Europa, copa, liga, estadual) com sinais do jogo (poupar, desfalques, descanso,
calendario, confronto direto, sequencia, forma, altitude, viagem, classico,
chuva, massa, especialista, noticias). Para cada combinacao compara o que
aconteceu (vitoria do mandante, empate, vitoria do visitante) com o que as odds
previam.

Regra contra sorte:
  1. descobre so nos concursos antigos (ate 2/3 do historico);
  2. exige forca (|z| >= 2,5) e o mesmo sinal nas duas metades da descoberta;
  3. CONFERE no ultimo terco, que a descoberta nunca viu: so fica a nuance que
     repete o sentido e mantem pelo menos 1/3 do tamanho.
O tamanho usado nos alertas e o da conferencia (o efeito real costuma ser
metade do que aparece na descoberta).

Toda segunda refaz tudo com os jogos novos: nuances novas entram, as que
pararam de funcionar saem.

Uso:
  python motor/varredura.py            # refaz -> motor/nuances.json e motor/nuances.md
Funcoes para a previsao: alertas(concurso) -> {jogo: [textos]}
"""
import csv
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
DADOS = os.path.join(REPO, "coleta", "dados")
SAIDA_JSON = os.path.join(AQUI, "nuances.json")
SAIDA_MD = os.path.join(AQUI, "nuances.md")
sys.path.insert(0, AQUI)
from calibracao import ajusta_gama, sem_margem  # noqa: E402

CUP = ("Cup", "Copa", "Libertadores", "Sudamericana", "Champions", "Europa", "Pokal", "Coppa", "Coupe", "Taca")
ESTADUAIS = ("Paulista", "Carioca", "Gaucho", "Mineiro", "Paranaense", "Baiano", "Pernambucano", "Cearense",
             "Catarinense", "Goiano")
ALVOS = ("vitória do mandante", "empate", "vitória do visitante")


def num(v, d=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else d
    except (TypeError, ValueError):
        return d


def ler(arq):
    if not os.path.exists(arq):
        return []
    with open(arq, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def km(a, b, c, d):
    a, b, c, d = map(math.radians, (a, b, c, d))
    return 6371 * 2 * math.asin(math.sqrt(math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2))


class Dados:
    def __init__(self):
        self.fat = {}
        for nome in ("sentinela_jogos.csv", "sentinela_aberto.csv"):
            for x in ler(os.path.join(DADOS, nome)):
                if x.get("match_id"):
                    k = (int(x["concurso"]), int(x["jogo"]))
                    if k not in self.fat or x.get("coletado_em_utc", "") >= self.fat[k].get("coletado_em_utc", ""):
                        self.fat[k] = x
        self.noticias = {}
        for nome in ("noticias_historico.csv", "noticias_aberto.csv"):
            for r in ler(os.path.join(DADOS, nome)):
                k = (int(r["concurso"]), int(r["jogo"]))
                if k not in self.noticias or r.get("coletado_em_utc", "") >= self.noticias[k].get("coletado_em_utc", ""):
                    self.noticias[k] = r
        self.massa = {}
        for nome in ("vovoteca_massa.csv", "vovoteca_massa_aberto.csv"):
            for r in ler(os.path.join(DADOS, nome)):
                if r.get("soma_ok") != "1":
                    continue
                k = (int(r["concurso"]), int(r["jogo"]))
                if k in self.massa and r.get("versao") != "parcial":
                    continue
                q = np.array([float(r["massa_1"]), float(r["massa_x"]), float(r["massa_2"])])
                if q.sum() > 0:
                    self.massa[k] = q / q.sum()
        self.lot = {}
        for nome in ("lotequeiros_x_caixa.csv", "lotequeiros_palpites.csv"):
            for r in ler(os.path.join(DADOS, nome)):
                if r.get("seco") in ("1", "X", "2") and r.get("concurso") and r.get("jogo"):
                    self.lot.setdefault((int(r["concurso"]), int(r["jogo"])), r["seco"])
        pts = defaultdict(list)
        for x in self.fat.values():
            if x.get("lat"):
                pts[x["fot_casa"]].append((float(x["lat"]), float(x["lon"])))
        self.casa = {t: tuple(np.median(np.array(v), axis=0)) for t, v in pts.items()}


def segmentos(p, mandante, liga):
    br = bool(re.search(r"/[A-Z]{2}$", (mandante or "").strip()))
    copa = any(w in (liga or "") for w in CUP)
    return {
        "todos": True,
        "equilibrado": 0.30 <= p[0] <= 0.45 and 0.30 <= p[2] <= 0.45,
        "favorito casa forte (>=60%)": p[0] >= 0.60,
        "favorito fora (>=45%)": p[2] >= 0.45,
        "favorito moderado (45-60%)": 0.45 <= p.max() < 0.60,
        "Brasil": br, "exterior": not br,
        "copa/continental": copa, "liga": bool(liga) and not copa,
        "estadual": any(w in (liga or "") for w in ESTADUAIS),
    }


def sinais(k, p, D):
    f = D.fat.get(k) or {}
    S = {}
    tem = lambda a, b: num(f.get(a)) is not None and num(f.get(b)) is not None
    fav = int(np.argmax(p))
    if f:
        if tem("trocas_casa", "trocas_fora"):
            S["mandante poupa (5+ trocas) e visitante não"] = num(f["trocas_casa"]) >= 5 and num(f["trocas_fora"]) <= 2
            S["visitante poupa (5+ trocas) e mandante não"] = num(f["trocas_fora"]) >= 5 and num(f["trocas_casa"]) <= 2
        if tem("desf_casa_n", "desf_fora_n"):
            S["mandante com 3+ desfalques a mais"] = num(f["desf_casa_n"]) - num(f["desf_fora_n"]) >= 3
            S["visitante com 3+ desfalques a mais"] = num(f["desf_fora_n"]) - num(f["desf_casa_n"]) >= 3
        if tem("dias_casa", "dias_fora"):
            dc, dv = min(num(f["dias_casa"]), 10), min(num(f["dias_fora"]), 10)
            S["mandante com 3+ dias a mais de descanso"] = dc - dv >= 3
            S["visitante com 3+ dias a mais de descanso"] = dv - dc >= 3
        if tem("jogos14_casa", "jogos14_fora"):
            S["mandante com 4+ jogos em 14 dias"] = num(f["jogos14_casa"]) >= 4
            S["visitante com 4+ jogos em 14 dias"] = num(f["jogos14_fora"]) >= 4
        if tem("h2h_n", "h2h_saldo") and num(f["h2h_n"]) >= 3:
            S["confronto direto dominado pelo mandante"] = num(f["h2h_saldo"]) >= 3
            S["confronto direto dominado pelo visitante"] = num(f["h2h_saldo"]) <= -3
        if tem("invicto5_casa", "invicto5_fora"):
            S["mandante 5 jogos sem perder"] = num(f["invicto5_casa"]) >= 5
            S["visitante 5 jogos sem perder"] = num(f["invicto5_fora"]) >= 5
            S["mandante perdeu o último jogo"] = num(f["invicto5_casa"]) == 0
            S["visitante perdeu o último jogo"] = num(f["invicto5_fora"]) == 0
        if tem("forma5_casa", "forma5_fora"):
            S["mandante em forma muito melhor (+6 pts)"] = num(f["forma5_casa"]) - num(f["forma5_fora"]) >= 6
            S["visitante em forma muito melhor (+6 pts)"] = num(f["forma5_fora"]) - num(f["forma5_casa"]) >= 6
        if f.get("altitude_m") not in ("", None):
            S["estádio acima de 1.500 m"] = num(f["altitude_m"], 0) >= 1500
        if f.get("lat") and f.get("fot_fora") in D.casa:
            S["viagem do visitante acima de 1.500 km"] = km(float(f["lat"]), float(f["lon"]), *D.casa[f["fot_fora"]]) > 1500
            if f.get("fot_casa") in D.casa:
                S["clássico local (casas a menos de 60 km)"] = km(*D.casa[f["fot_casa"]], *D.casa[f["fot_fora"]]) < 60
        if f.get("chuva_mm") not in ("", None):
            S["chuva forte (10 mm ou mais)"] = num(f["chuva_mm"]) >= 10
    if k in D.massa:
        q = D.massa[k]
        S["massa exagera no favorito (+10 pts)"] = q[fav] - p[fav] >= 0.10
        S["massa contra o favorito (-5 pts)"] = q[fav] - p[fav] <= -0.05
    if k in D.lot:
        S["especialista contra o favorito"] = D.lot[k] != "1X2"[fav]
    n = D.noticias.get(k)
    if n:
        g = lambda s: int(num(n.get(s), 0))
        S["notícias de técnico no mandante"] = g("casa_tecnico") >= 4 and g("fora_tecnico") == 0
        S["notícias de técnico no visitante"] = g("fora_tecnico") >= 4 and g("casa_tecnico") == 0
        S["notícias de crise no mandante"] = g("casa_crise") >= 6 and g("fora_crise") <= 1
        S["notícias de crise no visitante"] = g("fora_crise") >= 6 and g("casa_crise") <= 1
        S["notícias de reservas no mandante"] = g("casa_reservas") >= 3
        S["notícias de reservas no visitante"] = g("fora_reservas") >= 3
    return S


def jogos_historicos(D):
    G = []
    for o in ler(os.path.join(DADOS, "arena_odds.csv")):
        if not o.get("resultado"):
            continue
        k = (int(o["concurso"]), int(o["jogo"]))
        p = ajusta_gama(sem_margem([float(o["odd_1"]), float(o["odd_x"]), float(o["odd_2"])]), 1.04)
        G.append((k[0], p, "1X2".index(o["resultado"]), segmentos(p, o["mandante"], (D.fat.get(k) or {}).get("liga", "")),
                  sinais(k, p, D)))
    G.sort(key=lambda g: g[0])
    return G


def diferenca(R, alvo):
    real = np.mean([g[2] == alvo for g in R])
    prev = np.mean([g[1][alvo] for g in R])
    se = math.sqrt(np.mean([g[1][alvo] * (1 - g[1][alvo]) for g in R]) / len(R))
    return real - prev, (real - prev) / se if se > 0 else 0.0, real, prev


def varrer():
    D = Dados()
    G = jogos_historicos(D)
    cs = sorted({g[0] for g in G})
    t1, t2 = cs[len(cs) // 3], cs[2 * len(cs) // 3]
    desc = [g for g in G if g[0] < t2]
    conf = [g for g in G if g[0] >= t2]
    nomes_sinais = sorted({s for g in G for s in g[4]})
    candidatos, testes = [], 0
    for sg in G[0][3]:
        for sn in nomes_sinais:
            R = [g for g in desc if g[3][sg] and g[4].get(sn)]
            if len(R) < 50:
                continue
            for alvo in range(3):
                testes += 1
                d, z, real, prev = diferenca(R, alvo)
                a = [g for g in R if g[0] < t1]
                b = [g for g in R if g[0] >= t1]
                if abs(z) < 2.5 or len(a) < 15 or len(b) < 15:
                    continue
                da, db = diferenca(a, alvo)[0], diferenca(b, alvo)[0]
                if np.sign(da) == np.sign(db) == np.sign(d):
                    candidatos.append(dict(segmento=sg, sinal=sn, alvo=alvo, descoberta=round(float(d), 4),
                                           z=round(float(z), 2), jogos_descoberta=len(R)))
    confirmadas, recusadas, vistos = [], [], set()
    for c in sorted(candidatos, key=lambda c: -abs(c["z"])):
        R = [g for g in conf if g[3][c["segmento"]] and g[4].get(c["sinal"])]
        if len(R) < 20:
            c["motivo"] = f"poucos jogos na conferência ({len(R)})"
            recusadas.append(c)
            continue
        d2, z2, real, prev = diferenca(R, c["alvo"])
        c.update(conferencia=round(float(d2), 4), jogos_conferencia=len(R), real=round(float(real), 4), previsto=round(float(prev), 4))
        chave = (c["sinal"], c["alvo"], round(d2, 4))
        if np.sign(d2) == np.sign(c["descoberta"]) and abs(d2) >= abs(c["descoberta"]) / 3:
            if chave not in vistos:
                vistos.add(chave)
                confirmadas.append(c)
        else:
            c["motivo"] = "não se repetiu no período nunca visto"
            recusadas.append(c)
    out = {"atualizado_em_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "descoberta": f"{cs[0]}-{t2 - 1}", "conferencia": f"{t2}-{cs[-1]}", "combinacoes_testadas": testes,
           "confirmadas": confirmadas, "recusadas": recusadas}
    with open(SAIDA_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    escrever_md(out)
    print(open(SAIDA_MD, encoding="utf-8").read())


def texto(c):
    lado = "subestima" if c["conferencia"] > 0 else "superestima"
    return (f"{c['segmento']} + {c['sinal']}: o mercado {lado} a {ALVOS[c['alvo']]} "
            f"em {abs(100 * c['conferencia']):.1f} pts (real {100 * c['real']:.1f}% x previsto {100 * c['previsto']:.1f}%)")


def escrever_md(out):
    L = ["# Nuances confirmadas (onde as odds erram)", "",
         f"Atualizado em {out['atualizado_em_utc'][:10]} · descoberta nos concursos {out['descoberta']}, "
         f"conferência nos concursos {out['conferencia']} (nunca vistos pela descoberta) · "
         f"{out['combinacoes_testadas']} combinações testadas.", "",
         "| Tipo de jogo | Sinal | O mercado... | Descoberta | Conferência (vale este) | Jogos |", "|---|---|---|---|---|---|"]
    for c in out["confirmadas"]:
        lado = "subestima" if c["conferencia"] > 0 else "superestima"
        L.append(f"| {c['segmento']} | {c['sinal']} | {lado} a {ALVOS[c['alvo']]} | {100 * c['descoberta']:+.1f} pts | "
                 f"**{100 * c['conferencia']:+.1f} pts** | {c['jogos_descoberta']} → {c['jogos_conferencia']} |")
    if not out["confirmadas"]:
        L.append("| — | nenhuma nuance confirmada nesta semana | | | | |")
    L += ["", f"Recusadas nesta semana (pareciam nuance e não se confirmaram): {len(out['recusadas'])}."]
    with open(SAIDA_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def alertas(concurso, odds_por_jogo):
    """{jogo: [textos]} das nuances confirmadas que valem para os jogos do concurso aberto."""
    if not os.path.exists(SAIDA_JSON):
        return {}
    with open(SAIDA_JSON, encoding="utf-8") as f:
        conf = json.load(f).get("confirmadas", [])
    if not conf:
        return {}
    D = Dados()
    grade = {}
    for r in ler(os.path.join(DADOS, "arena_odds.csv")):
        if int(r["concurso"]) == int(concurso):
            grade[int(r["jogo"])] = r["mandante"]
    out = {}
    for j, o in odds_por_jogo.items():
        k = (int(concurso), int(j))
        p = ajusta_gama(sem_margem([float(x) for x in o]), 1.04)
        sg = segmentos(p, grade.get(j, ""), (D.fat.get(k) or {}).get("liga", ""))
        S = sinais(k, p, D)
        for c in conf:
            if sg.get(c["segmento"]) and S.get(c["sinal"]):
                out.setdefault(j, []).append(texto(c))
    return out


if __name__ == "__main__":
    varrer()
