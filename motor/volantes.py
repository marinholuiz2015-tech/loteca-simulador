"""
Desmembrador de cartela em volantes validos da Caixa.

Regra oficial (tabela de precos da Loteca, loterias.caixa.gov.br): um volante
aceita qualquer mistura de duplos e triplos com 2 a 864 combinacoes
(ex.: 9 duplos = 512; 1 triplo + 8 duplos = 768; 6 triplos = 729;
3 triplos + 5 duplos = 864). Nao existe volante so de secos (1 combinacao).
Preco: R$ 2 por combinacao.

Qualquer cartela (ate 14 triplos) e quebrada no MENOR numero de volantes:
cada jogo pode ficar inteiro no volante ou ser "aberto" em partes
(triplo -> 3 secos, ou duplo + seco; duplo -> 2 secos). Os volantes sao todas
as combinacoes das partes. Garantias conferidas no fim: soma das combinacoes
dos volantes = combinacoes da cartela, sem repeticao e sem falta; custo total
= custo da cartela.

Uso:
  python motor/volantes.py 1 X 2 1X X2 12 1X2 1 1 2 1X2 1X2 1X2 1X2
  python motor/volantes.py 1X2 x14 --csv volantes.csv
"""
import csv
import itertools
import math
import sys

LIMITE = 864   # combinacoes maximas por volante
MINIMO = 2     # um volante sempre tem pelo menos 1 duplo
PRECO = 2      # R$ por combinacao
ORDEM = "1X2"


def particoes(opcoes):
    """Formas de dividir as opcoes marcadas num jogo (cada parte vai a um conjunto de volantes)."""
    o = [c for c in ORDEM if c in opcoes]
    if len(o) == 1:
        return [[o]]
    if len(o) == 2:
        return [[o], [[o[0]], [o[1]]]]
    return [[o], [o[:2], o[2:]], [[o[0]], [o[1]], [o[2]]]]


def desmembrar(cartela):
    """cartela: lista de 14 strings ('1', 'X2', '1X2'...). Devolve a lista de volantes."""
    cartela = [c.upper().replace("0", "X") for c in cartela]
    if len(cartela) != 14 or any(not c or set(c) - set(ORDEM) for c in cartela):
        raise ValueError("A cartela precisa de 14 jogos, cada um com 1, X e/ou 2.")
    total = math.prod(len(set(c)) for c in cartela)
    if total < MINIMO:
        raise ValueError("Cartela so de secos nao existe na Caixa: marque pelo menos 1 duplo.")
    # programacao dinamica: estado = (maior volante, menor volante limitado a 2) -> (n volantes, escolhas)
    dp = {(1, 1): (1, [])}
    for c in cartela:
        nd = {}
        for (mx, mn), (n, esc) in dp.items():
            for k, part in enumerate(particoes(c)):
                tamanhos = [len(p) for p in part]
                nmx, nmn = mx * max(tamanhos), min(MINIMO, mn * min(tamanhos))
                if nmx > LIMITE:
                    continue
                nn = n * len(part)
                chave = (nmx, nmn)
                if chave not in nd or nd[chave][0] > nn:
                    nd[chave] = (nn, esc + [part])
        dp = nd
    validos = [v for (mx, mn), v in dp.items() if mn >= MINIMO]
    if not validos:
        raise ValueError("Nao foi possivel desmembrar respeitando o minimo de 2 combinacoes por volante.")
    _, escolha = min(validos, key=lambda v: v[0])
    volantes = [list(v) for v in itertools.product(*escolha)]
    conferir(cartela, volantes)
    return volantes


def combinacoes(volante):
    return math.prod(len(p) for p in volante)


def conferir(cartela, volantes):
    """Prova: os volantes cobrem exatamente as combinacoes da cartela, cada uma uma vez."""
    total = math.prod(len(set(c)) for c in cartela)
    soma = sum(combinacoes(v) for v in volantes)
    assert soma == total, f"soma {soma} != cartela {total}"
    for v in volantes:
        assert MINIMO <= combinacoes(v) <= LIMITE
        for j, p in enumerate(v):
            assert set(p) <= set(cartela[j])
    if total <= 200_000:  # checagem combinacao a combinacao (rapida ate esse tamanho)
        vistos = set()
        for v in volantes:
            for comb in itertools.product(*v):
                assert comb not in vistos
                vistos.add(comb)
        assert len(vistos) == total


def br(n):
    return f"{n:,.0f}".replace(",", ".")


def resumo(cartela, volantes):
    d = sum(len(set(c)) == 2 for c in cartela)
    t = sum(len(set(c)) == 3 for c in cartela)
    total = math.prod(len(set(c)) for c in cartela)
    minimo = -(-total // LIMITE)
    return (f"Cartela {14 - d - t} secos + {d} duplos + {t} triplos = {br(total)} combinacoes = "
            f"R$ {br(total * PRECO)}\n{br(len(volantes))} volante(s) (minimo teorico {br(minimo)}), "
            f"custo total R$ {br(sum(combinacoes(v) for v in volantes) * PRECO)}")


def tipo(volante):
    d = sum(len(p) == 2 for p in volante)
    t = sum(len(p) == 3 for p in volante)
    return d, t


def main():
    args = sys.argv[1:]
    arq = None
    if "--csv" in args:
        i = args.index("--csv")
        arq = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) == 2 and args[1].lower().startswith("x"):
        args = [args[0]] * int(args[1][1:])
    vols = desmembrar(args)
    print(resumo(args, vols))
    for i, v in enumerate(vols[:30], 1):
        d, t = tipo(v)
        print(f"Volante {i:>4}: " + " ".join(f"{j + 1}={''.join(p)}" for j, p in enumerate(v)) +
              f"   ({d} duplos, {t} triplos, R$ {br(combinacoes(v) * PRECO)})")
    if len(vols) > 30:
        print(f"... mais {br(len(vols) - 30)} volantes")
    if arq:
        with open(arq, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["volante"] + [f"jogo_{j}" for j in range(1, 15)] + ["duplos", "triplos", "valor"])
            for i, v in enumerate(vols, 1):
                d, t = tipo(v)
                w.writerow([i] + ["".join(p) for p in v] + [d, t, combinacoes(v) * PRECO])
        print(f"Lista completa: {arq}")


if __name__ == "__main__":
    main()
