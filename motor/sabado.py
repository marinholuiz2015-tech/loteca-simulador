"""
Atualizacao de sabado: recalcula a chance de cada jogo com a odd mais recente (The Odds API; Pinnacle quando
houver) e compara com a previsao de quinta.

Por que: no historico, a odd de FECHAMENTO acerta mais que a bet365 de quinta (Pinnacle +2,8 de forca,
motor/hora_da_odd.md); a de sexta nao ajudava. A de sabado de manha ainda nao foi medida - por isso este
script grava as duas lado a lado (coleta/dados/odds_quinta_sabado.csv) e motor/lab_sabado.py mede com os
resultados. O painel mostra o que mudou e deixa montar as cartelas com a odd de sabado.

Saida: motor/saida/concurso_N_sabado.json. So grava se houver coleta de odds DEPOIS da previsao de quinta.
Uso: python motor/sabado.py
"""
import csv
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import camada1 as c1  # noqa: E402
from calibracao import ajusta_gama, sem_margem  # noqa: E402

SAIDA = os.path.join(AQUI, "saida")
REGISTRO = os.path.join(RAIZ, "coleta", "dados", "odds_quinta_sabado.csv")
CAMPOS = ["concurso", "jogo", "mandante", "visitante", "p1_quinta", "px_quinta", "p2_quinta",
          "p1_sabado", "px_sabado", "p2_sabado", "casa", "odds_em_utc", "previsao_quinta_utc"]


def ultimo_concurso():
    cs = [int(os.path.basename(a)[9:-4]) for a in glob.glob(os.path.join(SAIDA, "concurso_*.csv"))
          if os.path.basename(a)[9:-4].isdigit()]
    return max(cs) if cs else None


def odds_recentes(grade, depois_de):
    """{jogo: (odds, casa, coletado)} da coleta mais recente de cada jogo feita depois de 'depois_de'."""
    linhas = [r for r in c1.ler_csv("odds_api.csv") if r.get("coletado_em_utc", "") > depois_de]
    out = {}
    for k, (m, v) in grade.items():
        casas = [r for r in linhas if c1.parecido(m, r["mandante"]) and c1.parecido(v, r["visitante"])]
        if not casas:
            continue
        ult = max(r["coletado_em_utc"] for r in casas)
        casas = [r for r in casas if r["coletado_em_utc"] == ult and c1.odds_validas([r["odd_1"], r["odd_x"], r["odd_2"]])]
        pin = [r for r in casas if r["casa"] == "pinnacle"]
        usar = pin or casas
        if usar:
            o = [float(np.mean([float(r[c]) for r in usar])) for c in ("odd_1", "odd_x", "odd_2")]
            out[k] = (o, "Pinnacle" if pin else f"média de {len(usar)} casas", ult)
    return out


def main():
    c = ultimo_concurso()
    if not c:
        print("sabado: sem previsao de quinta")
        return
    # referencia = a previsao OFICIAL de quinta/sexta no registro (o motor reescreve concurso_N.csv em toda rodada,
    # inclusive no sabado); sem registro oficial, usa a previsao gravada
    reg_arq = os.path.join(AQUI, "registro_previsoes.csv")
    ofi = [r for r in (list(csv.DictReader(open(reg_arq, encoding="utf-8"))) if os.path.exists(reg_arq) else [])
           if r.get("concurso") == str(c) and r.get("versao") == "oficial"]
    if ofi:
        ult = max(r["gerado_em_utc"] for r in ofi)
        L = sorted([r for r in ofi if r["gerado_em_utc"] == ult], key=lambda r: int(r["jogo"]))
    if not ofi or len(L) != 14:
        L = sorted(csv.DictReader(open(os.path.join(SAIDA, f"concurso_{c}.csv"), encoding="utf-8")), key=lambda r: int(r["jogo"]))
    gerado = max(r.get("gerado_em_utc", "") for r in L)
    # so vale odd coletada pelo menos 3 h depois da ultima previsao oficial
    try:
        corte = (datetime.strptime(gerado, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        corte = gerado
    grade = {int(r["jogo"]): (r["mandante"], r["visitante"]) for r in L}
    novas = odds_recentes(grade, corte)
    if not novas:
        print(f"sabado: concurso {c} sem odds novas depois de {corte}")
        return
    jogos, reg = [], []
    for r in L:
        j = int(r["jogo"])
        pq = np.array([float(r["p1"]), float(r["px"]), float(r["p2"])])
        if j in novas:
            o, casa, quando = novas[j]
            ps = ajusta_gama(sem_margem(o), float(r.get("gama") or 1.04))
        else:
            ps, casa, quando = pq, "sem odd nova (mantida a de quinta)", ""
        fq, fs = int(pq.argmax()), int(ps.argmax())
        jogos.append({"jogo": j, "mandante": r["mandante"], "visitante": r["visitante"],
                      "p_quinta": [round(float(x), 4) for x in pq], "p_sabado": [round(float(x), 4) for x in ps],
                      "fonte": casa, "odds_em": quando, "mudou_favorito": fq != fs,
                      "variacao": round(float(np.abs(ps - pq).max()), 4)})
        if j in novas:
            reg.append({"concurso": c, "jogo": j, "mandante": r["mandante"], "visitante": r["visitante"],
                        **{f"p{k}_quinta": round(float(pq[i]), 4) for i, k in enumerate(("1", "x", "2"))},
                        **{f"p{k}_sabado": round(float(ps[i]), 4) for i, k in enumerate(("1", "x", "2"))},
                        "casa": casa, "odds_em_utc": quando, "previsao_quinta_utc": gerado})
    out = {"concurso": c, "gerado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "previsao_quinta_utc": gerado,
           "com_odd_nova": len(reg), "jogos": jogos}
    json.dump(out, open(os.path.join(SAIDA, f"concurso_{c}_sabado.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # registro para medir: substitui as linhas deste concurso pela coleta mais recente
    antigas = [x for x in (list(csv.DictReader(open(REGISTRO, encoding="utf-8"))) if os.path.exists(REGISTRO) else [])
               if int(x["concurso"]) != c]
    with open(REGISTRO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(antigas + reg)
    mud = [x for x in jogos if x["mudou_favorito"] or x["variacao"] >= 0.05]
    print(f"sabado: concurso {c}, {len(reg)} jogos com odd nova, {len(mud)} mudaram 5 pontos ou mais / trocaram o favorito")


if __name__ == "__main__":
    main()
