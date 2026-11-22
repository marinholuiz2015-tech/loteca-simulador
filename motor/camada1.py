"""
CAMADA 1 — MOTOR DE PREVISAO (Loteca Elite Pro)

Para cada um dos 14 jogos de um concurso entrega: probabilidades 1/X/2
calibradas, favorito, confianca, posicao na ordem de confianca, classe
(seco/duplo/triplo) e o duplo sugerido. Nao decide aposta nem custo
(isso e das camadas 2 e 3).

Calibracao validada no tempo (motor/validar_camada1.py, 280 concursos):
  odds bet365 sem margem (metodo de potencia) + ajuste gama aprendido no
  historico. Ajuste de empate: reprovado (piorou a calibracao).

Fontes, por ordem:
  grade: API da Caixa -> tabela do Guia da Loteria -> imagem da Arena
  odds : Arena do AZ (coleta/ocr/arena_ocr.jsonl)
  extra: probabilidades da bolsa (Guia) ficam registradas, ainda sem peso
         (precisam de semanas de coleta para serem validadas)
  sem odds: frequencia historica (classe triplo, confianca baixa)

Uso:
  python motor/camada1.py            # concurso aberto mais recente com odds
  python motor/camada1.py 1284       # concurso especifico
Saidas:
  motor/saida/concurso_NNNN.csv e .md
  motor/registro_previsoes.csv (registro prospectivo: so acrescenta)
"""
import csv
import json
import math
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

import numpy as np
import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
from calibracao import aplica, aprende  # noqa: E402

DADOS = os.path.join(REPO, "coleta", "dados")
SAIDA = os.path.join(AQUI, "saida")
REGISTRO = os.path.join(AQUI, "registro_previsoes.csv")
API = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca/{}"
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36",
        "Referer": "https://loterias.caixa.gov.br/Paginas/Programacao-Loteca.aspx"}
FREQ = np.array([0.472, 0.262, 0.266])  # frequencia historica 1/X/2 (17.602 jogos)
SECO_MIN = 0.60     # (referencia antiga; a classe agora vem da cartela padrao)
TRIPLO_MAX = 0.70
# Cartela padrao que define a classe de cada jogo (secos + duplos + triplos = 14).
# Os jogos mais incertos viram triplo; os do meio, duplo; os mais firmes, seco.
CARTELA_PADRAO = (int(os.environ.get("DUPLOS", "4")), int(os.environ.get("TRIPLOS", "4")))  # 6+4+4


def equilibrado(p):
    return 0.30 <= p[0] <= 0.45 and 0.30 <= p[2] <= 0.45


_FATOR_EMPATE = None


def fator_empate():
    """Jogos equilibrados (casa e fora entre 30% e 45%) empatam mais do que o mercado preve
    (1.007 jogos: 33,7% real x 29,3% previsto). Fator = real / previsto, aprendido com todo o historico."""
    global _FATOR_EMPATE
    if _FATOR_EMPATE is None:
        from calibracao import sem_margem, ajusta_gama
        reais, prev = [], []
        try:
            with open(os.path.join(DADOS, "arena_odds.csv"), encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    if not r["resultado"]:
                        continue
                    q = ajusta_gama(sem_margem([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])]), 1.04)
                    if equilibrado(q):
                        reais.append(r["resultado"] == "X")
                        prev.append(q[1])
            _FATOR_EMPATE = float(np.mean(reais) / np.mean(prev)) if len(reais) >= 200 else 1.0
        except (OSError, ValueError):
            _FATOR_EMPATE = 1.0
    return _FATOR_EMPATE


def p_para_duplo(p):
    """Probabilidades usadas para a cobertura do duplo: empate corrigido (o mercado subestima o empate:
    27,7% real x 25,9% previsto em 5.152 jogos; nos equilibrados 33,7% x 29,3%)."""
    q = np.array(p, float)
    q[1] *= fator_empate() if equilibrado(p) else FATOR_EMPATE_GERAL
    return q / q.sum()


FATOR_EMPATE_GERAL = 1.07


def duplo_de(p):
    """Duplo = favorito + empate, em qualquer tipo de jogo (5.152 jogos: melhor par em todas as faixas de
    probabilidade, com mandante ou visitante favorito, nos tres periodos testados; o 1-2 nunca foi o melhor).
    Se o favorito for o proprio empate, cobre o empate + o mais provavel dos outros dois."""
    fav = int(np.argmax(p))
    return [fav, 1] if fav != 1 else [1, 0 if p[0] >= p[2] else 2]


def classes_da_cartela(linhas, d, t):
    """Escolhe quais jogos sao seco, duplo e triplo maximizando a chance de 14 da cartela padrao."""
    dp = {(0, 0): (0.0, [])}
    for l in linhas:
        op = [max(l["_p"]), l["cobertura_duplo"], 1.0]
        nd = {}
        for (a, b), (v, esc) in dp.items():
            for k, c in enumerate(op):
                na, nb = a + (k == 1), b + (k == 2)
                if na > d or nb > t:
                    continue
                nv = v + math.log(max(c, 1e-9))
                if (na, nb) not in nd or nd[(na, nb)][0] < nv:
                    nd[(na, nb)] = (nv, esc + [k])
        dp = nd
    melhor = max(dp.values(), key=lambda x: x[0])[1]
    return [("SECO", "DUPLO", "TRIPLO")[k] for k in melhor]
CAMPOS = ["concurso", "jogo", "mandante", "visitante", "p1", "px", "p2", "favorito", "confianca",
          "ordem", "classe", "duplo_sugerido", "cobertura_duplo", "fonte_prob", "odd_1", "odd_x", "odd_2",
          "bolsa_1", "bolsa_x", "bolsa_2", "gama", "pm1", "pmx", "pm2", "kpis", "kpis_valores", "versao", "gerado_em_utc"]


# ----------------------------------------------------------------- utilidades
def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    s = re.sub(r"-[A-Z]{2,3}\b|/[A-Z]{2}\b", "", s)
    return re.sub(r"[^A-Z]", "", s)


def parecido(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b) and (a in b or b in a or a[:4] == b[:4])


def ler_csv(nome):
    caminho = os.path.join(DADOS, nome)
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------- fontes
def arena(concurso=None):
    """Registros de odds da Arena por concurso (o mais recente lido de cada um)."""
    regs = {}
    with open(os.path.join(REPO, "coleta", "ocr", "arena_ocr.jsonl"), encoding="utf-8") as f:
        for l in f:
            r = json.loads(l)
            if "falha" in r:
                continue
            c = r.get("concurso_imagem") or r["concurso_post"]
            regs[c] = r
    return regs if concurso is None else regs.get(concurso)


def grade_caixa(concurso):
    try:
        r = requests.get(API.format(concurso), headers=HEAD, timeout=30)
        if r.status_code == 200:
            l = r.json().get("listaResultadoEquipeEsportiva") or []
            if len(l) == 14:
                return {j["nuSequencial"]: (j["nomeEquipeUm"], j["nomeEquipeDois"]) for j in l}, "Caixa"
    except Exception:
        pass
    return None, None


def grade_guia(concurso):
    linhas = [r for r in ler_csv("guia_loteria.csv") if int(r["concurso"]) == concurso]
    if not linhas:
        return None, None, {}
    ultimo = max(r["coletado_em_utc"] for r in linhas)
    snap = [r for r in linhas if r["coletado_em_utc"] == ultimo]
    if len(snap) != 14:
        return None, None, {}
    g = {int(r["jogo"]): (r["mandante"], r["visitante"]) for r in snap}
    bolsa = {int(r["jogo"]): (float(r["prob_1"]), float(r["prob_x"]), float(r["prob_2"])) for r in snap}
    return g, "Guia da Loteria", bolsa


def grade_arena(reg):
    g = {}
    for j in reg.get("jogos", []):
        partes = re.split(r"\s+[xX×]{1,2}\s+", j.get("texto_times", ""), maxsplit=1)
        g[j["jogo"]] = (partes[0].strip(), partes[1].strip() if len(partes) > 1 else "")
    return (g, "Arena (imagem)") if len(g) == 14 else (None, None)


def params_calibracao():
    jogos = [([float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])], "1X2".index(r["resultado"]))
             for r in ler_csv("arena_odds.csv") if r["resultado"]]
    return aprende(jogos, usar_empate=False, usar_gama=True)


# -------------------------------------------------------------------- motor
def prever(concurso):
    reg = arena(concurso)
    if not reg:
        raise SystemExit(f"Sem odds da Arena para o concurso {concurso}.")
    grade, fonte_grade = grade_caixa(concurso)
    g_guia, f_guia, bolsa = grade_guia(concurso)
    if not grade:
        grade, fonte_grade = (g_guia, f_guia) if g_guia else grade_arena(reg)
    if not grade:
        raise SystemExit("Grade do concurso nao encontrada (Caixa, Guia e Arena).")
    prm = params_calibracao()
    import sentinela
    import kpis
    mod_kpi = kpis.modelo()
    ctx_kpi = kpis.Contexto().carregar(abertos=True)
    fatos = sentinela.fatos_abertos(concurso)
    noticias = noticias_abertas(concurso)
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # casa cada linha da Arena com o jogo da grade (posicao; se nao bater, pelos nomes)
    odds_por_jogo = {}
    for j in reg["jogos"]:
        if not j.get("odd_1") or j.get("erros"):
            continue
        partes = re.split(r"\s+[xX×]{1,2}\s+", j.get("texto_times", ""), maxsplit=1)
        m = partes[0] if partes else ""
        v = partes[1] if len(partes) > 1 else ""
        alvo = None
        k = j["jogo"]
        if k in grade and (parecido(m, grade[k][0]) or parecido(v, grade[k][1]) or fonte_grade.startswith("Arena")):
            alvo = k
        else:
            alvo = next((q for q, (gm, gv) in grade.items() if parecido(m, gm) and parecido(v, gv)), None)
        if alvo and alvo not in odds_por_jogo:
            odds_por_jogo[alvo] = [j["odd_1"], j["odd_x"], j["odd_2"]]

    linhas = []
    for k in range(1, 15):
        mand, vis = grade.get(k, ("", ""))
        if k in odds_por_jogo:
            pm = aplica(odds_por_jogo[k], prm)
            vals = kpis.valores(fatos.get(k), (int(concurso), k), pm, ctx_kpi)
            p, contrib, usou = kpis.aplicar(pm, vals, mod_kpi)
            fonte = "odds bet365 (Arena)" + (" + KPIs" if usou else "")
            sent = ("ligados (" + ("pesos do Luiz" if mod_kpi.get("usa") == "luiz" else "pesos aprendidos") + ")"
                    if usou else "desligados (não superaram o mercado)") if mod_kpi else "sem modelo"
        else:
            pm = p = FREQ.copy()
            vals, contrib = {}, {}
            fonte = "sem odds: frequencia historica"
            sent = "sem odds"
        ordem_res = list(np.argsort(-p))
        fav = "1X2"[ordem_res[0]]
        pd_ = p_para_duplo(p)
        od = duplo_de(p)
        duplo = "".join(c for c in "1X2" if "1X2".index(c) in od)
        cobertura = float(p[od[0]] + p[od[1]])
        cobertura_real = float(pd_[od[0]] + pd_[od[1]])  # cobertura com o empate corrigido
        classe = "TRIPLO" if fonte.startswith("sem odds") else ""
        b = bolsa.get(k)
        o = odds_por_jogo.get(k, ["", "", ""])
        linhas.append(dict(concurso=concurso, jogo=k, mandante=mand, visitante=vis,
                           p1=round(float(p[0]), 4), px=round(float(p[1]), 4), p2=round(float(p[2]), 4),
                           favorito=fav, confianca=round(float(p.max()), 4), ordem=0, classe=classe,
                           duplo_sugerido=duplo, cobertura_duplo=round(cobertura_real, 4), fonte_prob=fonte,
                           _p=p,
                           odd_1=o[0], odd_x=o[1], odd_2=o[2],
                           bolsa_1=b[0] if b else "", bolsa_x=b[1] if b else "", bolsa_2=b[2] if b else "",
                           gama=prm.get("gama", 1.0), pm1=round(float(pm[0]), 4), pmx=round(float(pm[1]), 4),
                           pm2=round(float(pm[2]), 4), kpis=sent,
                           kpis_valores=json.dumps({n: round(v, 3) for n, v in vals.items() if v is not None},
                                                   ensure_ascii=False),
                           gerado_em_utc=agora))
    for pos, l in enumerate(sorted(linhas, key=lambda x: -x["confianca"]), 1):
        l["ordem"] = pos
    cls = classes_da_cartela(linhas, *CARTELA_PADRAO)
    for l, c in zip(linhas, cls):
        l["classe"] = l["classe"] or c
        l.pop("_p", None)
    return linhas, fonte_grade


def gravar(linhas, fonte_grade, registrar=True):
    os.makedirs(SAIDA, exist_ok=True)
    c = linhas[0]["concurso"]
    with open(os.path.join(SAIDA, f"concurso_{c}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(linhas)
    md = [f"# Loteca {c} — Camada 1 (motor de previsão)", "",
          f"Gerado em {linhas[0]['gerado_em_utc']} (UTC). Grade: {fonte_grade}. "
          f"Probabilidades: odds bet365 sem margem + calibração gama {linhas[0]['gama']}.", "",
          "| Jogo | Confronto | 1 | X | 2 | Favorito | Confiança | Ordem | Classe | Duplo |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for l in linhas:
        md.append(f"| {l['jogo']} | {l['mandante']} x {l['visitante']} | {l['p1']:.0%} | {l['px']:.0%} | "
                  f"{l['p2']:.0%} | {l['favorito']} | {l['confianca']:.0%} | {l['ordem']}º | {l['classe']} | "
                  f"{l['duplo_sugerido']} ({l['cobertura_duplo']:.0%}) |")
    top = sorted(linhas, key=lambda x: x["ordem"])
    md += ["", "Top 4: " + ", ".join(f"jogo {l['jogo']} ({l['favorito']})" for l in top[:4]),
           "Top 8: " + ", ".join(f"jogo {l['jogo']} ({l['favorito']})" for l in top[:8])]
    if any(l.get("kpis_valores") not in (None, "", "{}") for l in linhas):
        destaques = {"Rodizio / time reserva": "reservas", "Altitude": "altitude", "Viagem do visitante": "viagem",
                     "Confronto direto (H2H)": "H2H", "Sequencia sem perder": "invicto", "Desfalques": "desfalques",
                     "Descanso": "descanso", "Classico / rivalidade local": "clássico", "Massa x mercado (manada)": "massa"}
        md += ["", f"## KPIs do jogo ({linhas[0].get('kpis', '')})", "",
               "Notas positivas favorecem o mandante (no clássico, o empate). Placar completo dos KPIs: `motor/kpis.md`.", "",
               "| Jogo | " + " | ".join(destaques.values()) + " |", "|---|" + "---|" * len(destaques)]
        for l in linhas:
            try:
                v = json.loads(l.get("kpis_valores") or "{}")
            except ValueError:
                v = {}
            md.append(f"| {l['jogo']} | " + " | ".join(f"{v[n]:+.2f}" if n in v else "—" for n in destaques) + " |")
    noticias = noticias_abertas(c)
    if noticias:
        md += ["", "## Notícias da semana (setoristas e imprensa)", "",
               "| Jogo | Mandante: desfalque / reservas / crise / retorno | Visitante: desfalque / reservas / crise / retorno | Nota do leitor |",
               "|---|---|---|---|"]
        for l in linhas:
            n = noticias.get(l["jogo"])
            if not n:
                continue
            f = lambda lado: " / ".join(n.get(f"{lado}_{k}", "0") for k in ("desfalque", "reservas", "crise", "reforco"))
            md.append(f"| {l['jogo']} | {f('casa')} ({n.get('casa_n', 0)} manchetes) | {f('fora')} ({n.get('fora_n', 0)}) | "
                      f"{n.get('nota_modelo') or '—'} {n.get('motivo_modelo') or ''} |")
    sem = [l["jogo"] for l in linhas if l["fonte_prob"].startswith("sem odds")]
    if sem:
        md.append(f"Jogos sem odds (frequência histórica, triplo): {sem}")
    with open(os.path.join(SAIDA, f"concurso_{c}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    if registrar:
        novo = not os.path.exists(REGISTRO)
        with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            if novo:
                w.writeheader()
            w.writerows(linhas)
    return "\n".join(md)


def noticias_abertas(c):
    caminho = os.path.join(DADOS, "noticias_aberto.csv")
    out = {}
    if not os.path.exists(caminho):
        return out
    with open(caminho, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if int(r["concurso"]) == int(c):
                j = int(r["jogo"])
                if j not in out or r["coletado_em_utc"] > out[j]["coletado_em_utc"]:
                    out[j] = r
    return out


def concurso_encerrado(c):
    try:
        with open(os.path.join(REPO, "data", "historico_cef.json"), encoding="utf-8") as f:
            return str(c) in json.load(f)["concursos"]
    except Exception:
        return False


def versao_do_dia(agora_br):
    """Calendario (Brasilia): terca/quarta = provisoria; quinta/sexta = OFICIAL
    (depois da atualizacao das 7h da Arena, a tempo dos especialistas e bolões);
    sabado ate 15h = atualizacao (medida a parte). Fora disso: nao registra."""
    d = agora_br.weekday()
    if d in (1, 2):
        return "provisoria"
    if d in (3, 4):
        return "oficial"
    if d == 5 and agora_br.hour < 15:
        return "atualizacao"
    return None


def main():
    """Sem argumento: modo automatico (coleta semanal) para o concurso aberto.
    Registra conforme o calendario (versao_do_dia). Com numero: gera a tabela
    e so registra se o concurso estiver aberto e dentro do calendario."""
    from datetime import timedelta
    agora_br = datetime.now(timezone.utc) - timedelta(hours=3)
    versao = versao_do_dia(agora_br)
    janela = versao is not None
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    c = int(nums[0]) if nums else max(arena().keys())
    if concurso_encerrado(c):
        print(f"Concurso {c} ja encerrado: nada a prever.")
        return
    linhas, fonte = prever(c)
    for l in linhas:
        l["versao"] = versao or "fora do calendario"
    registrar = janela and "--sem-registro" not in sys.argv
    print(gravar(linhas, fonte, registrar))
    print("\nRegistro prospectivo: " + (f"GRAVADO como previsao {versao}" if registrar else
                                       "nao gravado (fora do calendario terca-sabado 15h)"))


if __name__ == "__main__":
    main()
