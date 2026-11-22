"""
Placar da camada 1 AO VIVO: cruza o registro prospectivo
(motor/registro_previsoes.csv, gravado antes do fechamento) com os
resultados oficiais e mede o acerto contra as metas.

Para cada concurso usa a ULTIMA previsao registrada antes do fechamento
(normalmente a de sabado de manha). Gera motor/placar.md.
Uso: python motor/placar.py
"""
import csv
import json
import os
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
METAS = {14: .56, 10: .60, 8: .62, 6: .65, 4: .70}


def main():
    reg = os.path.join(AQUI, "registro_previsoes.csv")
    if not os.path.exists(reg):
        print("Registro vazio: o primeiro concurso registrado sera o 1285 (quinta/sabado).")
        return
    with open(reg, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    ultima = {}
    for l in linhas:
        c = int(l["concurso"])
        if c not in ultima or l["gerado_em_utc"] > ultima[c]:
            ultima[c] = l["gerado_em_utc"]
    prev = defaultdict(dict)
    for l in linhas:
        c = int(l["concurso"])
        if l["gerado_em_utc"] == ultima[c]:
            prev[c][int(l["jogo"])] = l
    with open(os.path.join(REPO, "data", "historico_cef.json"), encoding="utf-8") as f:
        cef = json.load(f)["concursos"]
    res = {}
    for c in prev:
        g = cef.get(str(c))
        if not g:
            continue
        r = {}
        for j in g["jogos"]:
            a, b = j.get("nuGolEquipeUm"), j.get("nuGolEquipeDois")
            if a is not None and b is not None and not j.get("icSorteioResultado"):
                r[j["nuSequencial"]] = "1" if a > b else ("2" if b > a else "X")
        res[c] = r
    acum = {k: [0, 0] for k in METAS}
    md = ["# Placar ao vivo — Camada 1", "", "Previsão registrada antes do fechamento × resultado oficial.", "",
          "| Concurso | 14 | Top 10 | Top 8 | Top 6 | Top 4 |", "|---|---|---|---|---|---|"]
    for c in sorted(res):
        jogos = sorted((l for k, l in prev[c].items() if k in res[c]), key=lambda l: int(l["ordem"]))
        celulas = []
        for k in METAS:
            top = jogos[:k]
            h = sum(l["favorito"] == res[c][int(l["jogo"])] for l in top)
            acum[k][0] += h
            acum[k][1] += len(top)
            celulas.append(f"{h}/{len(top)}")
        md.append(f"| {c} | " + " | ".join(celulas) + " |")
    if not res:
        md.append("| (aguardando resultados) | | | | | |")
    md += ["", "**Acumulado × metas**", "", "| | 14 | Top 10 | Top 8 | Top 6 | Top 4 |", "|---|---|---|---|---|---|",
           "| Acerto | " + " | ".join(f"{acum[k][0] / acum[k][1]:.1%}" if acum[k][1] else "—" for k in METAS) + " |",
           "| Meta | " + " | ".join(f"{v:.0%}" for v in METAS.values()) + " |",
           "| Mercado (histórico 998–1283) | 52,9% | 57,6% | 60,6% | 65,0% | 69,8% |", "",
           f"Concursos avaliados: {len(res)}. Com poucos concursos o acerto oscila muito; "
           "leitura séria a partir de ~10 concursos."]
    texto = "\n".join(md) + "\n"
    with open(os.path.join(AQUI, "placar.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)


if __name__ == "__main__":
    main()
