"""
Dados do painel oficial (docs/dados/painel.json): jogo da semana, decisao, desdobre, historico de todos
os concursos com acertos e erros jogo a jogo, onde erramos (aprendizado) e confronto com os sites.
Uso: python motor/painel_dados.py
"""
import csv
import glob
import json
import math
import os
import re
import sys
from collections import defaultdict

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import camada2 as c2  # noqa: E402
import camada3 as c3  # noqa: E402
import desdobre as dd  # noqa: E402

SAIDA = os.path.join(AQUI, "saida")
DESTINO = os.path.join(RAIZ, "docs", "dados", "painel.json")
R = "1X2"


def duplo_regra(r):
    """Duplo sempre = favorito + empate (validado: em 2.176 jogos indecisos acertou 74,1% contra 67,9% do 1-2;
    McNemar z=2,33). Recalcula aqui para que previsoes gravadas antes da regra (ex.: 1284) nao mostrem 1-2."""
    p = [float(r["p1"]), float(r["px"]), float(r["p2"])]
    f = max(range(3), key=lambda k: p[k])
    par = [f, 1] if f != 1 else [1, 0 if p[0] >= p[2] else 2]
    return "".join(c for c in "1X2" if "1X2".index(c) in par)


def ler_json(arq):
    try:
        return json.load(open(arq, encoding="utf-8"))
    except Exception:
        return None


def semana():
    feitos = sorted(int(os.path.basename(a)[9:-4]) for a in glob.glob(os.path.join(SAIDA, "concurso_*.csv"))
                    if os.path.basename(a)[9:-4].isdigit())
    if not feitos:
        return None
    c = feitos[-1]
    linhas = sorted(csv.DictReader(open(os.path.join(SAIDA, f"concurso_{c}.csv"), encoding="utf-8")),
                    key=lambda r: int(r["jogo"]))
    alertas = defaultdict(list)
    md = os.path.join(SAIDA, f"concurso_{c}.md")
    if os.path.exists(md):
        for m in re.finditer(r"^- \*\*Jogo (\d+)\*\* \([^)]*\): (.+)$", open(md, encoding="utf-8").read(), re.M):
            alertas[int(m.group(1))].append(m.group(2).strip())
    jogos = [{"jogo": int(r["jogo"]), "mandante": r["mandante"], "visitante": r["visitante"],
              "p": [round(float(r["p1"]), 4), round(float(r["px"]), 4), round(float(r["p2"]), 4)],
              "favorito": r.get("favorito"), "classe": r.get("classe"), "duplo": duplo_regra(r),
              "alertas": alertas.get(int(r["jogo"]), [])} for r in linhas]
    return {"concurso": c, "jogos": jogos,
            "decisao": ler_json(os.path.join(SAIDA, f"concurso_{c}_decisao.json")),
            "desdobre": ler_json(os.path.join(SAIDA, f"concurso_{c}_desdobre_R200.json"))}


def pontos(cart, res):
    return sum(res[j] in cart[j] for j in range(14))


def historico():
    odds, rat, res = c2.odds_por_concurso(), c2.rateio(), c3.resultados_cef()
    esp = {}
    arq = os.path.join(AQUI, "historico_desdobre.csv")
    if os.path.exists(arq):
        esp = {int(r["concurso"]): int(r["pontos_espalhado"]) for r in csv.DictReader(open(arq))}
    liga = {}
    sj = os.path.join(RAIZ, "coleta", "dados", "sentinela_jogos.csv")
    if os.path.exists(sj):
        for r in csv.DictReader(open(sj, encoding="utf-8")):
            liga[(int(r["concurso"]), int(r["jogo"]))] = r.get("liga") or ""
    out = []
    for c in sorted(set(odds) & set(res), reverse=True):
        if len(odds[c]) < 14:
            continue
        P = c3.P_de(odds[c])
        r = res[c]
        simples = dd.cartela_simples(P.tolist(), 200)["sel"]
        padrao = c2.cartela(P, 4, 4)
        jogos = []
        for j in range(14):
            o = odds[c].get(j + 1, {})
            f = int(np.argmax(P[j]))
            jogos.append({"j": j + 1, "m": o.get("mandante", ""), "v": o.get("visitante", ""),
                          "p": [round(float(x), 3) for x in P[j]], "fav": R[f], "res": R[r[j]],
                          "s": "".join(R[k] for k in sorted(simples[j])), "q": "".join(R[k] for k in sorted(padrao[j])),
                          "liga": liga.get((c, j + 1), "")})
        Rt = rat.get(c, {})
        out.append({"c": c, "data": next((o.get("data_jogo") for o in odds[c].values() if o.get("data_jogo")), ""),
                    "pts_simples": pontos(simples, r), "pts_644": pontos(padrao, r), "pts_espalhado": esp.get(c),
                    "zebras": sum(r[j] != int(np.argmax(P[j])) for j in range(14)),
                    "esperado_zebras": round(float(sum(1 - P[j].max() for j in range(14))), 2),
                    "ganhadores14": Rt.get("ganhadores_14"), "premio14": Rt.get("premio_14"), "premio13": Rt.get("premio_13"),
                    "jogos": jogos})
    return out


def aprendizado(H):
    secos = [(c["c"], g) for c in H for g in c["jogos"] if len(g["s"]) == 1]
    def bloco(itens):
        n = len(itens)
        if not n:
            return None
        real = sum(g["res"] == g["s"] for _, g in itens) / n
        prev = sum(g["p"][R.index(g["s"])] for _, g in itens) / n
        se = math.sqrt(max(prev * (1 - prev), 1e-9) / n)
        return {"n": n, "real": round(real, 4), "previsto": round(prev, 4), "z": round((real - prev) / se, 1)}
    faixas = []
    for a, b, nome in ((0, .45, "abaixo de 45%"), (.45, .55, "45 a 55%"), (.55, .65, "55 a 65%"), (.65, .75, "65 a 75%"), (.75, 1.01, "acima de 75%")):
        x = bloco([(c, g) for c, g in secos if a <= g["p"][R.index(g["s"])] < b])
        if x:
            faixas.append(dict(x, faixa=nome))
    por_liga = []
    grupos = defaultdict(list)
    for c, g in secos:
        if g["liga"]:
            grupos[g["liga"]].append((c, g))
    for lg, it in grupos.items():
        x = bloco(it)
        if x and x["n"] >= 40:
            por_liga.append(dict(x, liga=lg))
    por_liga.sort(key=lambda x: x["z"])
    lado = [dict(bloco([(c, g) for c, g in secos if g["s"] == k]) or {}, lado=n)
            for k, n in (("1", "seco no mandante"), ("X", "seco no empate"), ("2", "seco no visitante"))]
    erros = [g for _, g in secos if g["res"] != g["s"]]
    tipo = {"empate": sum(g["res"] == "X" for g in erros), "virada": sum(g["res"] != "X" for g in erros), "total": len(erros)}
    recentes = H[:20]
    tend = {"concursos": len(recentes), "zebras_reais": round(float(np.mean([c["zebras"] for c in recentes])), 2),
            "zebras_previstas": round(float(np.mean([c["esperado_zebras"] for c in recentes])), 2),
            "secos_real": bloco([(c["c"], g) for c in recentes for g in c["jogos"] if len(g["s"]) == 1])}
    licoes = []
    for x in por_liga:
        if abs(x["z"]) >= 2:
            licoes.append(f"{x['liga']}: os secos acertam {x['real']:.0%} contra {x['previsto']:.0%} previstos "
                          f"({x['n']} jogos) — {'o mercado erra para mais nessa liga; pensar em duplo' if x['z'] < 0 else 'os favoritos rendem mais que o previsto'}.")
    for x in faixas:
        if abs(x["z"]) >= 2:
            licoes.append(f"Favoritos com {x['faixa']}: acertam {x['real']:.0%} contra {x['previsto']:.0%} previstos.")
    if tipo["total"]:
        licoes.append(f"Dos {tipo['total']} secos errados, {tipo['empate'] / tipo['total']:.0%} foram empate — "
                      "o empate é o erro mais comum; o duplo sempre usa favorito + empate por isso.")
    if not licoes:
        licoes.append("Nenhum grupo de jogos foge do previsto de forma consistente: os erros estão dentro do normal do futebol.")
    return {"faixas": faixas, "ligas": por_liga, "lado": lado, "tipo_erro": tipo, "tendencia": tend, "licoes": licoes}


def sites():
    md = os.path.join(AQUI, "confronto_sites.md")
    if not os.path.exists(md):
        return []
    out, nome = [], None
    for ln in open(md, encoding="utf-8"):
        m = re.match(r"=== (.+?) x nosso sistema: (\d+)", ln)
        if m:
            nome = m.group(1)
            continue
        m = re.match(r"(\S.{0,40}?)\s{2,}([\d.]+)\s+(\d+)\s+(\d+)\s+([\d.]+)%", ln)
        if m and nome:
            out.append({"comparacao": nome, "quem": m.group(1).strip(), "pontos": float(m.group(2)),
                        "treze": int(m.group(3)), "catorze": int(m.group(4)), "secos": float(m.group(5))})
    return out


def financeiro():
    rat, res = c2.rateio(), c3.resultados_cef()
    out = []
    for nome, arq in (("recomendada", c3.RECOMENDADAS), ("jogada", c3.JOGADAS)):
        if not os.path.exists(arq):
            continue
        for x in csv.DictReader(open(arq, encoding="utf-8")):
            c = int(x["concurso"])
            item = {"tipo": nome, "concurso": c, "valor": float(x["orcamento"]), "estrutura": x["estrutura"]}
            if c in res and c in rat:
                cart = [set(R.index(k) for k in x[f"jogo_{j}"]) for j in range(1, 15)]
                ok = [res[c][j] in cart[j] for j in range(14)]
                er = ok.count(False)
                pr = (rat[c]["premio_14"] + sum(len(s) - 1 for s in cart) * rat[c]["premio_13"]) if er == 0 else \
                    (len(cart[ok.index(False)]) * rat[c]["premio_13"] if er == 1 else 0.0)
                item.update(pontos=14 - er, premio=round(pr, 2))
            out.append(item)
    return out


def financeiro_historico(H):
    """se tivesse jogado: gasto e premio por concurso de cada estrategia (rateio oficial da Caixa).
    - jogo perfeito (ate R$ 200), toda semana: premio exato (14 + combinacoes de 13).
    - desdobre espalhado R$ 200, toda semana: 14 = premio do 14; 13 = ao menos 1 combinacao (minimo).
    - cofrinho: R$ 200 guardados por semana; aposta a cartela 6+4+4 so quando o retorno esperado passou de 100%."""
    rat, odds, res = c2.rateio(), c2.odds_por_concurso(), c3.resultados_cef()
    ret = {}
    arq = os.path.join(AQUI, "camada3_historico.csv")
    if os.path.exists(arq):
        ret = {int(r["concurso"]): float(r["retorno_2592"]) for r in csv.DictReader(open(arq))}
    out = []
    for c in sorted(x["c"] for x in H):
        if c not in rat:
            continue
        Rt = rat[c]
        h = next(x for x in H if x["c"] == c)
        sel = [set(R.index(k) for k in g["s"]) for g in h["jogos"]]
        r = res[c]
        er = [j for j in range(14) if r[j] not in sel[j]]
        custo_s = int(np.prod([len(s) for s in sel])) * 2
        pr_s = (Rt["premio_14"] + sum(len(s) - 1 for s in sel) * Rt["premio_13"]) if not er else \
            (len(sel[er[0]]) * Rt["premio_13"] if len(er) == 1 else 0.0)
        pe = h.get("pts_espalhado")
        pr_e = Rt["premio_14"] if pe == 14 else (Rt["premio_13"] if pe == 13 else 0.0)
        cof = None
        if ret.get(c, 0) >= 1.0 and len(odds.get(c, {})) >= 10:
            P = c3.P_de(odds[c])
            cart = c2.cartela(P, 4, 4)
            er2 = [j for j in range(14) if r[j] not in cart[j]]
            cof = (Rt["premio_14"] + sum(len(s) - 1 for s in cart) * Rt["premio_13"]) if not er2 else \
                (len(cart[er2[0]]) * Rt["premio_13"] if len(er2) == 1 else 0.0)
        out.append({"c": c, "custo_s": custo_s, "premio_s": round(pr_s, 2), "custo_e": 200 if pe is not None else 0,
                    "premio_e": round(pr_e, 2), "cofrinho_aposta": 2592 if cof is not None else 0,
                    "cofrinho_premio": round(cof or 0.0, 2)})
    return out


def kpis():
    md = os.path.join(AQUI, "kpis.md")
    linhas = []
    if os.path.exists(md):
        for ln in open(md, encoding="utf-8"):
            p = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(p) >= 6 and re.match(r"^[+-]?\d", p[3] or ""):
                linhas.append({"grupo": p[0], "kpi": p[1], "jogos": p[2], "forca": p[3], "leitura": p[5] if len(p) > 5 else ""})
    return linhas


def completar_desdobre(limite=15):
    """calcula os pontos do desdobre espalhado nos concursos encerrados que faltam (so passado de cada um)."""
    arq = os.path.join(AQUI, "historico_desdobre.csv")
    feitos = {int(r["concurso"]) for r in csv.DictReader(open(arq))} if os.path.exists(arq) else set()
    odds, res = c2.odds_por_concurso(), c3.resultados_cef()
    faltam = sorted(c for c in set(odds) & set(res) if len(odds[c]) >= 14 and c not in feitos)[-limite:]
    novos = []
    for c in faltam:
        P = c3.P_de(odds[c]).tolist()
        r = res[c]
        s = dd.cartela_simples(P, 200)
        e = dd.espalhado(P, 200, top=1500)
        ps = 14 - sum(r[j] not in s["sel"][j] for j in range(14))
        pe = 14 - min(sum(a[j] != r[j] for j in range(14)) for u in e["volantes"] for a in u)
        novos.append([c, pe, ps, e["custo"], s["custo"], round(e["p14"], 5), round(e["p13"], 4)])
    if novos:
        novo_arq = not os.path.exists(arq)
        with open(arq, "a", newline="") as f:
            w = csv.writer(f)
            if novo_arq:
                w.writerow(["concurso", "pontos_espalhado", "pontos_simples", "custo_espalhado", "custo_simples",
                            "p14_espalhado", "p13_espalhado"])
            w.writerows(novos)
    return len(novos)


def main():
    n = completar_desdobre()
    if n:
        print(f"desdobre espalhado calculado em mais {n} concursos do historico")
    H = historico()
    dados = {"gerado": __import__("datetime").datetime.now().strftime("%d/%m/%Y %H:%M"), "semana": semana(),
             "historico": H, "aprendizado": aprendizado(H), "sites": sites(), "financeiro": financeiro(), "kpis": kpis(),
             "financeiro_historico": financeiro_historico(H)}
    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    sem = dados["semana"]
    if sem and sem.get("desdobre"):
        with open(os.path.join(os.path.dirname(DESTINO), "desdobre.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["volante"] + [f"jogo_{j}" for j in range(1, 15)] + ["valor"])
            for n, v in enumerate(sem["desdobre"]["espalhado"]["volantes"], 1):
                w.writerow([n] + v + [4])
    json.dump(dados, open(DESTINO, "w"), ensure_ascii=False, separators=(",", ":"))
    print(f"painel: {len(H)} concursos no historico, semana {dados['semana']['concurso'] if dados['semana'] else '-'}, "
          f"{os.path.getsize(DESTINO) // 1024} KB")


if __name__ == "__main__":
    main()
