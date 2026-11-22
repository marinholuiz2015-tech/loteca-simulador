"""
Placar da camada 1 AO VIVO: cruza o registro prospectivo
(motor/registro_previsoes.csv) com os resultados oficiais e mede o acerto
contra as metas.

Calendario das previsoes (Brasilia):
  terca/quarta = provisoria | quinta/sexta = OFICIAL | sabado ate 15h = atualizacao
O placar principal usa a ultima previsao OFICIAL de cada concurso (a que vale
para decidir, a tempo dos especialistas e bolões). A atualizacao de sabado e
medida a parte, para saber se esperar mais informacao melhora o acerto.
Gera motor/placar.md. Uso: python motor/placar.py
"""
import csv
import json
import math
import os
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
METAS = {14: .56, 10: .60, 8: .62, 6: .65, 4: .70}
MERCADO_ACERTO = {14: .529, 10: .576, 8: .606, 6: .650, 4: .698}
N_HIST = 280  # concursos do teste no tempo (998-1283)


def faixa(acertos, n, z=1.96):
    """Intervalo de Wilson (95%): onde o acerto verdadeiro provavelmente esta."""
    if not n:
        return None
    p = acertos / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centro - meia, centro + meia


def fmt_faixa(f):
    return "—" if f is None else f"{f[0]:.1%} a {f[1]:.1%}"


MERCADO = ("| Mercado (histórico 998–1283) | " +
           " | ".join(f"{MERCADO_ACERTO[k]:.1%}" for k in METAS) + " | — |")
MERCADO_FAIXA = ("| Faixa provável do mercado | " +
                 " | ".join(fmt_faixa(faixa(round(MERCADO_ACERTO[k] * k * N_HIST), k * N_HIST)) for k in METAS) +
                 " | — |")


def resultados(concursos):
    with open(os.path.join(REPO, "data", "historico_cef.json"), encoding="utf-8") as f:
        cef = json.load(f)["concursos"]
    res = {}
    for c in concursos:
        g = cef.get(str(c))
        if not g:
            continue
        r = {}
        for j in g["jogos"]:
            a, b = j.get("nuGolEquipeUm"), j.get("nuGolEquipeDois")
            if a is not None and b is not None and not j.get("icSorteioResultado"):
                r[j["nuSequencial"]] = "1" if a > b else ("2" if b > a else "X")
        if r:
            res[c] = r
    return res


def escolhe(linhas, versoes):
    """Ultima previsao de cada concurso dentre as versoes aceitas."""
    ultima, prev = {}, defaultdict(dict)
    for l in linhas:
        if l.get("versao", "oficial") not in versoes:
            continue
        c = int(l["concurso"])
        if c not in ultima or l["gerado_em_utc"] > ultima[c]:
            ultima[c] = l["gerado_em_utc"]
    for l in linhas:
        c = int(l["concurso"])
        if c in ultima and l["gerado_em_utc"] == ultima[c] and l.get("versao", "oficial") in versoes:
            prev[c][int(l["jogo"])] = l
    return prev


def bloco(titulo, prev, res):
    acum = {k: [0, 0] for k in METAS}
    p14_soma, n_c = 0.0, 0
    md = [f"## {titulo}", "", "| Concurso | 14 | Top 10 | Top 8 | Top 6 | Top 4 | Chance de 14 (R$4) |",
          "|---|---|---|---|---|---|---|"]
    for c in sorted(set(prev) & set(res)):
        jogos = sorted((l for k, l in prev[c].items() if k in res[c]), key=lambda l: int(l["ordem"]))
        cel = []
        for k in METAS:
            top = jogos[:k]
            h = sum(l["favorito"] == res[c][int(l["jogo"])] for l in top)
            acum[k][0] += h
            acum[k][1] += len(top)
            cel.append(f"{h}/{len(top)}")
        # chance de 14 da aposta minima (13 secos + 1 duplo no jogo de maior ganho)
        conf = [float(l["confianca"]) for l in jogos]
        cob = [float(l["cobertura_duplo"]) for l in jogos]
        if len(conf) == 14:
            i = max(range(14), key=lambda q: cob[q] / conf[q])
            p14 = math.prod(conf[q] if q != i else cob[q] for q in range(14))
            p14_soma += p14
            n_c += 1
            cel.append(f"{p14:.3%}")
        else:
            cel.append("—")
        md.append(f"| {c} | " + " | ".join(cel) + " |")
    if not (set(prev) & set(res)):
        md.append("| (aguardando resultados) | | | | | | |")
    md += ["", "| | 14 | Top 10 | Top 8 | Top 6 | Top 4 | Chance de 14 (R$4) |", "|---|---|---|---|---|---|---|",
           "| Acerto | " + " | ".join(f"{acum[k][0] / acum[k][1]:.1%}" if acum[k][1] else "—" for k in METAS) +
           (f" | {p14_soma / n_c:.3%} |" if n_c else " | — |"),
           "| Faixa provável (95%) | " + " | ".join(fmt_faixa(faixa(*acum[k])) for k in METAS) + " | — |",
           "| Meta | " + " | ".join(f"{v:.0%}" for v in METAS.values()) + " | — |", MERCADO, MERCADO_FAIXA, "",
           "Faixa provável: com 95% de confiança o acerto verdadeiro está nesse intervalo. "
           "Uma melhora só é real quando sai da faixa do mercado; dentro dela pode ser sorte.", ""]
    return md, len(set(prev) & set(res))


def main():
    reg = os.path.join(AQUI, "registro_previsoes.csv")
    if not os.path.exists(reg):
        print("Registro vazio: o primeiro concurso registrado sera o 1285.")
        return
    with open(reg, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    oficial = escolhe(linhas, {"oficial"})
    atual = escolhe(linhas, {"atualizacao"})
    res = resultados(set(oficial) | set(atual))
    md = ["# Placar ao vivo — Camada 1", "",
          "Previsões registradas antes do fechamento × resultado oficial. "
          "Calendário: terça = provisória, **quinta = oficial**, sábado = atualização.", ""]
    b1, n1 = bloco("Previsão OFICIAL (quinta) — vale para decidir", oficial, res)
    b2, n2 = bloco("Atualização de sábado — mede se esperar melhora", atual, res)
    md += b1 + b2 + [f"Concursos avaliados: {n1} (oficial) / {n2} (atualização). "
                     "Com 10 concursos a faixa do top 4 ainda vai de ~55% a ~82%; leitura séria a partir de ~50 concursos (cerca de 1 ano)."]
    texto = "\n".join(md) + "\n"
    with open(os.path.join(AQUI, "placar.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)


if __name__ == "__main__":
    main()
