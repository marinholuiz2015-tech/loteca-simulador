"""
Montagem POR VALOR (triplos e duplos onde a massa exagera) x montagem POR CHANCE (a de hoje), pelo mesmo dinheiro,
com o que cada cartela teria pago de verdade no rateio oficial da Caixa.

Por chance: escolhe secos/duplos/triplos para maximizar a chance de 14 (peso de cada resultado = p do mercado).
Por valor (alfa): peso = p / massa^alfa  -> premia cobrir o resultado que a massa despreza (prêmio maior se vier).
  alfa 0 = por chance; 0,5 = meio a meio; 1 = valor puro.
O valor esperado do 14 se separa jogo a jogo: soma sobre as combinacoes de p(c)/massa(c) = produto, em cada jogo,
de (soma dos p/massa dos resultados marcados). Por isso a mesma otimizacao serve para os dois.
Premio real: 14 -> pool_14/(ganhadores+1) (ou o pool inteiro se ninguem acertou); 13 -> pool_13/(ganhadores_13+k).
Saida: motor/valor_massa.md
"""
import csv, json, math, os, collections
AQUI = os.path.dirname(os.path.abspath(__file__)); RAIZ = os.path.dirname(AQUI)
R = "1X2"

def opcoes(p):
    """Seco = favorito; duplo = favorito + empate (regra validada); triplo = tudo."""
    f = max(range(3), key=lambda k: p[k])
    du = [f, 1] if f != 1 else [1, 0 if p[0] >= p[2] else 2]
    return [[f], du, [0, 1, 2]]


def otimo(W, d, t, PP=None):
    """Escolhe ONDE vao os d duplos e t triplos (opcoes fixas pela regra de chance), maximizando o produto das
    somas dos pesos de cada jogo (DP). Peso = p / massa^alfa: o valor so muda em quais jogos se cobre mais."""
    best = {(0, 0): (0.0, [])}
    for i, w in enumerate(W):
        ops = opcoes(PP[i])
        op = [(math.log(sum(w[k] for k in ops[0])), R[ops[0][0]], 0, 0),
              (math.log(sum(w[k] for k in ops[1])), "".join(sorted((R[k] for k in ops[1]), key=R.index)), 1, 0),
              (math.log(sum(w)), "1X2", 0, 1)]
        nb = {}
        for (a, b), (v, ch) in best.items():
            for lv, s, da, tb in op:
                k = (a + da, b + tb)
                if k[0] > d or k[1] > t: continue
                if k not in nb or v + lv > nb[k][0]: nb[k] = (v + lv, ch + [s])
        best = nb
    r = best.get((d, t)); return r[1] if r else None

def main():
    massa = collections.defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(RAIZ, "coleta/dados/vovoteca_massa.csv"), encoding="utf-8")):
        try:
            m = [float(r["massa_1"]), float(r["massa_x"]), float(r["massa_2"])]
        except Exception: continue
        if r.get("soma_ok") != "1": continue
        c, j = int(r["concurso"]), int(r["jogo"])
        if j not in massa[c] or r["versao"] == "final": massa[c][j] = [x / sum(m) for x in m]
    rat = {int(r["concurso"]): r for r in csv.DictReader(open(os.path.join(RAIZ, "coleta/dados/rateio_caixa.csv"), encoding="utf-8"))}
    P = json.load(open(os.path.join(RAIZ, "docs/dados/painel.json")))
    estruturas = {"R$ 144 (9+3+2)": (3, 2), "R$ 576 (7+5+2)": (5, 2), "R$ 2.592 (6+4+4)": (4, 4), "R$ 7.776 (5+5+4)": (5, 4), "R$ 23.328 (4+4+6)": (4, 6)}
    alfas = [0, 0.25, 0.5, 0.75, 1.0]
    tot = {(e, a): [0, 0.0, 0, 0, 0] for e in estruturas for a in alfas}  # concursos, premio, 14s, 13s, cobriu zebra forte
    n = 0
    for h in P["historico"]:
        c = h["c"]
        if c not in rat or len(massa.get(c, {})) < 14: continue
        rr = rat[c]; g14, g13 = int(rr["ganhadores_14"]), int(rr["ganhadores_13"])
        p14, p13 = float(rr["pool_14"] or 0), float(rr["pool_13"] or 0)
        if p13 == 0: p13 = 0.18 * float(rr["arrecadacao"] or 0) * 0.4
        jogos = sorted(h["jogos"], key=lambda g: g["j"]); res = [g["res"] for g in jogos]
        if any(r not in R for r in res): continue
        n += 1
        for a in alfas:
            W = [[g["p"][k] / max(0.05, massa[c][g["j"]][k]) ** a for k in range(3)] for g in jogos]
            for e, (d, t) in estruturas.items():
                s = otimo(W, d, t, [g['p'] for g in jogos])
                if not s: continue
                err = [i for i in range(14) if res[i] not in s[i]]
                pr = 0.0
                if not err:
                    k13 = sum(len(x) - 1 for x in s)
                    pr = p14 / (g14 + 1) + k13 * p13 / (g13 + k13)
                    tot[(e, a)][2] += 1
                elif len(err) == 1:
                    k13 = len(s[err[0]]); pr = k13 * p13 / (g13 + k13); tot[(e, a)][3] += 1
                tot[(e, a)][0] += 1; tot[(e, a)][1] += pr
    md = ["# Montagem por valor (massa) x por chance — pago de verdade", "",
          f"{n} concursos com enquete da massa (Vovoteca) completa, odds e rateio oficial. Mesma estrutura e mesmo custo em cada comparação; prêmio real do rateio (nosso bilhete somado aos ganhadores).", "",
          "alfa 0 = por chance (como é hoje); 1 = valor puro (triplo/duplo onde a massa mais despreza o resultado).", ""]
    for e, (d, t) in estruturas.items():
        custo = 2 * 2 ** d * 3 ** t
        md += [f"## {e}", "", "| Montagem | 14 | 13 | Prêmio total | Gasto | Retorno |", "|---|---|---|---|---|---|"]
        for a in alfas:
            k, pr, q14, q13, _ = tot[(e, a)]
            nome = "por chance (hoje)" if a == 0 else f"valor alfa {a}"
            md.append(f"| {nome} | {q14} | {q13} | R$ {pr:,.0f} | R$ {custo * k:,.0f} | {100 * pr / max(1, custo * k):.0f}% |".replace(",", "."))
        md.append("")
    open(os.path.join(AQUI, "valor_massa.md"), "w").write("\n".join(md))
    print("\n".join(md))

if __name__ == "__main__":
    main()
