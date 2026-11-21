"""
Cruza as odds lidas da Arena (arena_ocr.jsonl) com a grade/resultados
oficiais (data/historico_cef.json do repositorio) e com os palpites do
Lotequeiros, e mede:
  - cobertura (jogos com odds)
  - acerto do favorito do mercado (menor odd) vs. "sempre coluna 1"
  - Brier (probabilidade normalizada das odds) vs. frequencia historica
  - acerto por faixa de probabilidade do favorito (base para seco/duplo/triplo)
  - comparacao pareada com o seco do Lotequeiros (McNemar)
Grava arena_odds.csv (base final casada).
"""
import csv
import json
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from avaliar_lotequeiros import parecido  # noqa: E402

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
cef = json.load(open(os.path.join(REPO, "data/historico_cef.json")))["concursos"]
lq = {}
with open(os.path.join(REPO, "coleta/dados/lotequeiros_x_caixa.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        lq[(int(r["concurso"]), int(r["jogo"]))] = r


def grade(conc):
    c = cef.get(str(conc))
    if not c:
        return {}
    out = {}
    for j in c.get("jogos", []):
        gm, gv = j.get("nuGolEquipeUm"), j.get("nuGolEquipeDois")
        res = None
        if gm is not None and gv is not None and not j.get("icSorteioResultado"):
            res = "1" if gm > gv else ("2" if gv > gm else "X")
        out[j["nuSequencial"]] = dict(mandante=j["nomeEquipeUm"], visitante=j["nomeEquipeDois"],
                                      uf_m=j.get("siglaUFUm", ""), uf_v=j.get("siglaUFDois", ""),
                                      resultado=res, data=j.get("dtJogo", ""))
    return out


def _lados(texto):
    partes = re.split(r"\s+[xX×]{1,2}\s+", texto, maxsplit=1)
    esq = partes[0] if partes else ""
    dir_ = partes[1] if len(partes) > 1 else ""
    limpa = lambda s: re.sub(r"-[A-Z]{2,3}\b|[_|]", "", s.upper()).strip()
    return limpa(esq), limpa(dir_)


def times_batem(texto, g):
    esq, dir_ = _lados(texto)
    return parecido(esq, g["mandante"]) or parecido(dir_, g["visitante"])


def achar_jogo(texto, g, pos):
    """Jogo da grade da Caixa que corresponde a linha da Arena: primeiro a
    mesma posicao; se os times nao baterem, procura nas outras posicoes
    (a Arena as vezes lista os jogos em outra ordem). Exige os dois times
    batendo quando a posicao e diferente."""
    if pos in g and times_batem(texto, g[pos]):
        return pos
    esq, dir_ = _lados(texto)
    for k, gj in g.items():
        if k != pos and parecido(esq, gj["mandante"]) and parecido(dir_, gj["visitante"]):
            return k
    return None


def main():
    linhas, stats = [], defaultdict(int)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "arena_ocr.jsonl"), encoding="utf-8") as f:
        imagens = [json.loads(l) for l in f]
    for im in sorted(imagens, key=lambda x: x["concurso_post"]):
        stats["imagens"] += 1
        if "falha" in im:
            stats["imagem_falhou"] += 1
            continue
        ci, cp = im.get("concurso_imagem"), im["concurso_post"]
        if ci and ci != cp:
            stats["titulo_diferente_do_post"] += 1
        conc = ci or cp
        g = grade(conc)
        if not g:
            stats["sem_grade_caixa"] += 1
            continue
        usados = set()
        for j in im["jogos"]:
            stats["jogos"] += 1
            if j["odd_1"] is None:
                stats["sem_odd"] += 1
                continue
            if j["erros"]:
                stats["odd_reprovada_checagem"] += 1
                continue
            k = achar_jogo(j.get("texto_times", ""), g, j["jogo"])
            if k is None or k in usados:
                stats["times_nao_batem"] += 1
                continue
            if k != j["jogo"]:
                stats["casado_em_outra_posicao"] += 1
            usados.add(k)
            gj = g[k]
            j = {**j, "jogo": k}
            inv = [1 / j["odd_1"], 1 / j["odd_x"], 1 / j["odd_2"]]
            s = sum(inv)
            p = [v / s for v in inv]
            fav = "1X2"[p.index(max(p))]
            linhas.append(dict(concurso=conc, jogo=j["jogo"], mandante=gj["mandante"],
                               visitante=gj["visitante"], data_jogo=gj["data"],
                               odd_1=j["odd_1"], odd_x=j["odd_x"], odd_2=j["odd_2"],
                               p_1=round(p[0], 4), p_x=round(p[1], 4), p_2=round(p[2], 4),
                               margem=round(s - 1, 4), favorito=fav, p_fav=round(max(p), 4),
                               resultado=gj["resultado"] or "",
                               titulo_confere=int(ci == cp) if ci else ""))
    with open(os.path.join(REPO, "coleta/dados/arena_odds.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    print("== Leitura ==")
    for k in ["imagens", "imagem_falhou", "titulo_diferente_do_post", "sem_grade_caixa", "jogos",
              "sem_odd", "odd_reprovada_checagem", "times_nao_batem", "casado_em_outra_posicao"]:
        print(f"  {k:<26}{stats[k]}")
    print(f"  {'jogos aceitos':<26}{len(linhas)}")

    av = [r for r in linhas if r["resultado"]]
    n = len(av)
    ac_fav = sum(r["favorito"] == r["resultado"] for r in av) / n
    ac_1 = sum(r["resultado"] == "1" for r in av) / n
    freq = {k: sum(r["resultado"] == k for r in av) / n for k in "1X2"}
    def brier(p, res):
        return sum((p[k] - (1 if res == k else 0)) ** 2 for k in "1X2")
    b_mer = sum(brier({"1": r["p_1"], "X": r["p_x"], "2": r["p_2"]}, r["resultado"]) for r in av) / n
    b_base = sum(brier(freq, r["resultado"]) for r in av) / n
    print(f"\n== Mercado (odds bet365) em {n} jogos com resultado ==")
    print(f"  acerto do favorito: {ac_fav:.1%}  | sempre '1': {ac_1:.1%}  | lift {ac_fav / ac_1:.3f}x")
    print(f"  Brier mercado: {b_mer:.4f}  | frequencia fixa: {b_base:.4f}  | melhora {1 - b_mer / b_base:.1%}")
    print(f"  favorito do mercado = X em {sum(r['favorito'] == 'X' for r in av)} jogos")

    print("\n== Acerto por forca do favorito (base p/ seco/duplo/triplo) ==")
    faixas = [(0, .40), (.40, .50), (.50, .60), (.60, .70), (.70, .80), (.80, 1.01)]
    for a, b in faixas:
        g_ = [r for r in av if a <= r["p_fav"] < b]
        if not g_:
            continue
        acf = sum(r["favorito"] == r["resultado"] for r in g_) / len(g_)
        # duplo: favorito + segundo mais provavel
        def duplo_ok(r):
            p = {"1": r["p_1"], "X": r["p_x"], "2": r["p_2"]}
            top2 = sorted(p, key=p.get, reverse=True)[:2]
            return r["resultado"] in top2
        acd = sum(duplo_ok(r) for r in g_) / len(g_)
        print(f"  p_fav {a:.0%}-{min(b, 1):.0%}: {len(g_):>5} jogos | seco no favorito {acf:6.1%} "
              f"(esperado {sum(r['p_fav'] for r in g_) / len(g_):6.1%}) | duplo {acd:6.1%}")

    print("\n== Comparacao pareada com o Lotequeiros (mesmos jogos) ==")
    par = [(r, lq[(r["concurso"], r["jogo"])]) for r in av
           if (r["concurso"], r["jogo"]) in lq and lq[(r["concurso"], r["jogo"])]["seco"]]
    if par:
        m = len(par)
        a_m = sum(r["favorito"] == r["resultado"] for r, _ in par)
        a_l = sum(l["seco"] == r["resultado"] for r, l in par)
        b_ = sum(1 for r, l in par if r["favorito"] == r["resultado"] and l["seco"] != r["resultado"])
        c_ = sum(1 for r, l in par if r["favorito"] != r["resultado"] and l["seco"] == r["resultado"])
        z = (b_ - c_) / math.sqrt(b_ + c_) if b_ + c_ else 0
        print(f"  {m} jogos | mercado {a_m / m:.1%} | Lotequeiros {a_l / m:.1%} | "
              f"so mercado acerta {b_} | so Lotequeiros acerta {c_} | McNemar z={z:.1f}")
        disc = [(r, l) for r, l in par if l["seco"] != r["favorito"]]
        if disc:
            a_ld = sum(l["seco"] == r["resultado"] for r, l in disc) / len(disc)
            a_md = sum(r["favorito"] == r["resultado"] for r, l in disc) / len(disc)
            print(f"  quando discordam ({len(disc)} jogos): mercado {a_md:.1%} | Lotequeiros {a_ld:.1%}")


if __name__ == "__main__":
    main()
