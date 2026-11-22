"""
KPIs do jogo: indicadores medidos um a um e combinados com pesos.

Cada KPI da uma nota por jogo. A nota "lado" e positiva quando favorece o
mandante (ex.: visitante com mais reservas); a nota "empate" e positiva quando
favorece o empate (ex.: chuva forte, classico). Nada e regra fixa:

  - medir:   cada KPI e testado no tempo, sozinho, sobre as odds calibradas
             (aprende so com concursos anteriores). Forca = ganho / erro-padrao.
  - modelo:  todos os KPIs juntos num logit sobre as odds, pesos aprendidos com
             penalidade (ridge) e reaprendidos toda semana. So entra na previsao se
             o teste no tempo mostrar ganho maior que 2 erros-padrao sem perder acerto.
  - pesos do Luiz: motor/kpis_pesos_luiz.json ({"nome do KPI": peso}). Testados
             do mesmo jeito; o relatorio mostra lado a lado aprendido x Luiz x mercado.

KPIs ainda sem historico (noticias, movimento de odd) ficam "coletando" e entram
no teste quando houver concursos suficientes.

Uso:
  python motor/kpis.py medir      # placar de KPIs -> motor/kpis.md e motor/kpis_modelo.json
"""
import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
DADOS = os.path.join(REPO, "coleta", "dados")
MODELO = os.path.join(AQUI, "kpis_modelo.json")
PESOS_LUIZ = os.path.join(AQUI, "kpis_pesos_luiz.json")
RELATORIO = os.path.join(AQUI, "kpis.md")
sys.path.insert(0, AQUI)
from calibracao import aprende, aplica  # noqa: E402

RIDGE = 3.0
MIN_JOGOS_KPI = 300          # minimo de jogos com o KPI para medir
MIN_CONCURSOS_NOVO = 20      # KPIs sem historico: concursos coletados para entrar no teste


def num(v, padrao=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else padrao
    except (TypeError, ValueError):
        return padrao


def km(a, b, c, d):
    a, b, c, d = map(math.radians, (a, b, c, d))
    return 6371 * 2 * math.asin(math.sqrt(math.sin((c - a) / 2) ** 2 +
                                          math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2))


# ------------------------------------------------------------------ contexto (dados auxiliares)
class Contexto:
    def __init__(self):
        self.casa = {}          # time -> (lat, lon, altitude) medianos como mandante
        self.massa = {}         # (c, j) -> [q1, qx, q2]
        self.lot = {}           # (c, j) -> '1' / 'X' / '2'
        self.noticias = {}      # (c, j) -> linha
        self.guia = defaultdict(list)  # (c, j) -> [(coletado, [o1, ox, o2])]

    def carregar(self, abertos=True):
        arqs = [os.path.join(DADOS, "sentinela_jogos.csv")]
        if abertos:
            arqs.append(os.path.join(DADOS, "sentinela_aberto.csv"))
        pts = defaultdict(list)
        for a in arqs:
            for r in ler(a):
                if r.get("lat") and r.get("fot_casa"):
                    pts[r["fot_casa"]].append((float(r["lat"]), float(r["lon"]), num(r.get("altitude_m"), 0.0)))
        self.casa = {t: tuple(np.median(np.array(v), axis=0)) for t, v in pts.items()}
        for nome in ("vovoteca_massa.csv", "vovoteca_massa_aberto.csv"):
            for r in ler(os.path.join(DADOS, nome)):
                if r.get("soma_ok") != "1":
                    continue
                k = (int(r["concurso"]), int(r["jogo"]))
                if k in self.massa and r.get("versao") != "parcial":
                    continue  # prefere a parcial (antes do fechamento)
                q = np.array([float(r["massa_1"]), float(r["massa_x"]), float(r["massa_2"])])
                if q.sum() > 0:
                    self.massa[k] = q / q.sum()
        for nome in ("lotequeiros_x_caixa.csv", "lotequeiros_palpites.csv"):
            for r in ler(os.path.join(DADOS, nome)):
                if r.get("seco") in ("1", "X", "2") and r.get("concurso") and r.get("jogo"):
                    self.lot.setdefault((int(r["concurso"]), int(r["jogo"])), r["seco"])
        for r in ler(os.path.join(DADOS, "noticias_aberto.csv")):
            k = (int(r["concurso"]), int(r["jogo"]))
            if k not in self.noticias or r["coletado_em_utc"] > self.noticias[k]["coletado_em_utc"]:
                self.noticias[k] = r
        for r in ler(os.path.join(DADOS, "guia_loteria.csv")):
            try:
                o = [float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])]
            except (KeyError, ValueError):
                continue
            self.guia[(int(r["concurso"]), int(r["jogo"]))].append((r.get("coletado_em_utc", ""), o))
        return self


def ler(arq):
    if not os.path.exists(arq):
        return []
    with open(arq, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ catalogo de KPIs
def k_forma(f, k, p, cx):
    a, b = num(f.get("forma5_casa")), num(f.get("forma5_fora"))
    return None if a is None or b is None else (a - b) / 5


def k_invicto(f, k, p, cx):
    a, b = num(f.get("invicto5_casa")), num(f.get("invicto5_fora"))
    return None if a is None or b is None else (a - b) / 5


def k_descanso(f, k, p, cx):
    a, b = num(f.get("dias_casa")), num(f.get("dias_fora"))
    return None if a is None or b is None else (min(a, 10) - min(b, 10)) / 3


def k_calendario(f, k, p, cx):
    a, b = num(f.get("jogos14_casa")), num(f.get("jogos14_fora"))
    return None if a is None or b is None else (b - a) / 2


def k_rodizio(f, k, p, cx):
    a, b = num(f.get("trocas_casa")), num(f.get("trocas_fora"))
    return None if a is None or b is None else (b - a) / 5


def k_desfalques(f, k, p, cx):
    a, b = num(f.get("desf_casa_n")), num(f.get("desf_fora_n"))
    return None if a is None or b is None else (b - a) / 3


def k_altitude(f, k, p, cx):
    alt = num(f.get("altitude_m"))
    if alt is None:
        return None
    if alt < 1500:
        return 0.0  # abaixo de ~1.500 m nao ha efeito de altitude no futebol
    alt_vis = cx.casa.get(f.get("fot_fora"), (0, 0, 300.0))[2]
    return max(0.0, alt - alt_vis) / 1000


def k_viagem(f, k, p, cx):
    if not f.get("lat") or f.get("fot_fora") not in cx.casa:
        return None
    la, lo, _ = cx.casa[f["fot_fora"]]
    return math.log1p(km(float(f["lat"]), float(f["lon"]), la, lo)) / 7


def k_h2h(f, k, p, cx):
    n, s = num(f.get("h2h_n")), num(f.get("h2h_saldo"))
    return None if not n else s / max(n, 3)


def k_massa(f, k, p, cx):
    q = cx.massa.get(k)
    return None if q is None else float((q[0] - q[2]) - (p[0] - p[2]))


def k_especialista(f, k, p, cx):
    s = cx.lot.get(k)
    return None if s is None else {"1": 1.0, "X": 0.0, "2": -1.0}[s]


def k_classico_empate(f, k, p, cx):
    """Mandante e visitante da mesma regiao (casas a menos de 60 km): rivalidade local."""
    if not f.get("lat") or f.get("fot_fora") not in cx.casa or f.get("fot_casa") not in cx.casa:
        return None
    a, b = cx.casa[f["fot_casa"]], cx.casa[f["fot_fora"]]
    return 1.0 if km(a[0], a[1], b[0], b[1]) < 60 else 0.0


def k_chuva_empate(f, k, p, cx):
    c = num(f.get("chuva_mm"))
    return None if c is None else (1.0 if c >= 10 else 0.0)


def _noticia(k, cx, sinal, inverte=False):
    r = cx.noticias.get(k)
    if not r:
        return None
    a, b = num(r.get(f"casa_{sinal}"), 0.0), num(r.get(f"fora_{sinal}"), 0.0)
    d = b - a  # + = visitante com mais noticias do sinal (bom para o mandante)
    v = math.copysign(math.log1p(abs(d)), d)
    return -v if inverte else v


def k_not_crise(f, k, p, cx):
    return _noticia(k, cx, "crise")


def k_not_tecnico(f, k, p, cx):
    return _noticia(k, cx, "tecnico")


def k_not_reservas(f, k, p, cx):
    return _noticia(k, cx, "reservas")


def k_not_desfalque(f, k, p, cx):
    return _noticia(k, cx, "desfalque")


def k_movimento_odd(f, k, p, cx):
    """Quanto a odd andou a favor do mandante desde a primeira coleta da semana (Guia)."""
    s = sorted(cx.guia.get(k, []))
    if len(s) < 2:
        return None
    from calibracao import sem_margem
    a, b = sem_margem(s[0][1]), sem_margem(s[-1][1])
    return float(((b[0] - b[2]) - (a[0] - a[2])) * 5)


# nome -> (funcao, tipo, grupo, descricao)
KPIS = {
    "Forma (pontos nos ultimos 5)": (k_forma, "lado", "Desempenho", "pontos do mandante - do visitante nos 5 ultimos jogos"),
    "Sequencia sem perder": (k_invicto, "lado", "Desempenho", "jogos seguidos sem perder (ate 5), mandante - visitante"),
    "Confronto direto (H2H)": (k_h2h, "lado", "Desempenho", "saldo de vitorias nos ultimos confrontos"),
    "Descanso": (k_descanso, "lado", "Situacional", "dias desde o ultimo jogo, mandante - visitante"),
    "Calendario apertado": (k_calendario, "lado", "Situacional", "jogos em 14 dias, visitante - mandante"),
    "Rodizio / time reserva": (k_rodizio, "lado", "Situacional", "titulares trocados desde o ultimo jogo, visitante - mandante"),
    "Desfalques": (k_desfalques, "lado", "Situacional", "lesionados e suspensos, visitante - mandante"),
    "Altitude": (k_altitude, "lado", "Ambiente", "estadio a 1.500 m ou mais: diferenca para a casa do visitante (km)"),
    "Viagem do visitante": (k_viagem, "lado", "Ambiente", "distancia da casa do visitante ate o estadio (log)"),
    "Classico / rivalidade local": (k_classico_empate, "empate", "Ambiente", "casas a menos de 60 km (favorece empate)"),
    "Chuva forte": (k_chuva_empate, "empate", "Ambiente", "10 mm ou mais no dia (favorece empate)"),
    "Massa x mercado (manada)": (k_massa, "lado", "Massa", "quanto a enquete puxa para o mandante alem do mercado"),
    "Especialista (Lotequeiros)": (k_especialista, "lado", "Especialistas", "seco do Lotequeiros: 1, X ou 2"),
    "Noticias: crise": (k_not_crise, "lado", "Institucional", "manchetes de crise, visitante - mandante"),
    "Noticias: tecnico": (k_not_tecnico, "lado", "Institucional", "manchetes de tecnico ameacado/trocado, visitante - mandante"),
    "Noticias: reservas": (k_not_reservas, "lado", "Institucional", "manchetes de poupar/reservas, visitante - mandante"),
    "Noticias: desfalques": (k_not_desfalque, "lado", "Institucional", "manchetes de lesao/suspensao, visitante - mandante"),
    "Movimento da odd": (k_movimento_odd, "lado", "Mercado", "odd andando a favor do mandante durante a semana"),
}
NOMES = list(KPIS)
LADO = [n for n in NOMES if KPIS[n][1] == "lado"]
EMP = [n for n in NOMES if KPIS[n][1] == "empate"]


def valores(f, k, p, cx):
    out = {}
    for n, (fn, _, _, _) in KPIS.items():
        try:
            v = fn(f or {}, k, p, cx)
        except Exception:
            v = None
        out[n] = None if v is None or not math.isfinite(v) else float(v)
    return out


# ------------------------------------------------------------------ modelo
def probs(logp, v, w):
    """logp (n,3); v (n,K) com 0 onde falta; w (K,) -> probabilidades (n,3)."""
    il = [NOMES.index(n) for n in LADO]
    ie = [NOMES.index(n) for n in EMP]
    z = logp.copy()
    s = v[:, il] @ w[il]
    z[:, 0] += s
    z[:, 2] -= s
    z[:, 1] += v[:, ie] @ w[ie]
    z -= z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def ajustar(logp, v, y, ativos, w0=None):
    """Ridge-logit por Newton so nos KPIs ativos."""
    K = len(NOMES)
    w = np.zeros(K) if w0 is None else w0.copy()
    m = np.array([n in ativos for n in NOMES], float)
    il = np.array([KPIS[n][1] == "lado" for n in NOMES], float)
    ie = 1 - il
    Y = np.eye(3)[y]
    for _ in range(30):
        q = probs(logp, v, w * m)
        r_lado = (Y[:, 0] - Y[:, 2]) - (q[:, 0] - q[:, 2])
        r_emp = Y[:, 1] - q[:, 1]
        g = (v * (il * r_lado[:, None] + ie * r_emp[:, None])).sum(0) - RIDGE * w
        var_l = q[:, 0] + q[:, 2] - (q[:, 0] - q[:, 2]) ** 2
        var_e = q[:, 1] * (1 - q[:, 1])
        A = v * il
        B = v * ie
        H = -(A.T * var_l) @ A - (B.T * var_e) @ B - RIDGE * np.eye(K)
        g *= m
        H = H * np.outer(m, m) - np.diag(1 - m)
        passo = np.linalg.solve(H, g)
        w = w - passo
        if np.abs(passo).max() < 1e-7:
            break
    return w * m


def base_historica(cx):
    """(concurso, odds, valores, resultado) de cada jogo encerrado com odds."""
    fat = {(int(r["concurso"]), int(r["jogo"])): r for r in ler(os.path.join(DADOS, "sentinela_jogos.csv"))
           if r.get("match_id")}
    from calibracao import sem_margem
    out = []
    for r in ler(os.path.join(DADOS, "arena_odds.csv")):
        if not r.get("resultado"):
            continue
        k = (int(r["concurso"]), int(r["jogo"]))
        o = [float(r["odd_1"]), float(r["odd_x"]), float(r["odd_2"])]
        out.append((k[0], o, valores(fat.get(k), k, sem_margem(o), cx), "1X2".index(r["resultado"])))
    out.sort(key=lambda x: x[0])
    return out


def teste_no_tempo(base, ativos, pesos_fixos=None, a_cada=10):
    """Treina so com o passado (re-treina a cada N concursos). Devolve perdas e acertos por jogo."""
    cs = np.array([b[0] for b in base])
    unicos = np.unique(cs)
    inicio = unicos[len(unicos) // 3]
    V = np.array([[b[2][n] if b[2][n] is not None else 0.0 for n in NOMES] for b in base])
    Y = np.array([b[3] for b in base])
    pm, pk, am, ak = [], [], [], []
    calib = w = None
    for i, c in enumerate(unicos):
        if c < inicio:
            continue
        antes = cs < c
        if calib is None or i % a_cada == 0:
            calib = aprende([(base[j][1], base[j][3]) for j in np.where(antes)[0]], usar_empate=False, usar_gama=True)
            LP = np.log(np.array([aplica(b[1], calib) for b in base]))
            if pesos_fixos is None:
                w = ajustar(LP[antes], V[antes], Y[antes], ativos, w)
            else:
                w = np.array([pesos_fixos.get(n, 0.0) for n in NOMES])
        idx = np.where(cs == c)[0]
        q = probs(LP[idx], V[idx], w)
        p = np.exp(LP[idx])
        for t, j in enumerate(idx):
            pm.append(-math.log(p[t, Y[j]]))
            pk.append(-math.log(q[t, Y[j]]))
            am.append(int(np.argmax(p[t]) == Y[j]))
            ak.append(int(np.argmax(q[t]) == Y[j]))
    return np.array(pm), np.array(pk), np.array(am), np.array(ak)


def resumo(pm, pk, am, ak):
    d = pm - pk
    ep = d.std(ddof=1) / math.sqrt(len(d)) if len(d) > 1 else float("inf")
    return {"jogos": int(len(d)), "ganho": round(float(d.mean()), 6), "erro": round(float(ep), 6),
            "forca": round(float(d.mean() / ep), 2) if ep > 0 else 0.0,
            "acerto_mercado": round(float(am.mean()), 4), "acerto_modelo": round(float(ak.mean()), 4)}


def medir():
    cx = Contexto().carregar(abertos=False)
    base = base_historica(cx)
    tem = {n: sum(b[2][n] is not None for b in base) for n in NOMES}
    concursos_com = {n: len({b[0] for b in base if b[2][n] is not None}) for n in NOMES}
    por_kpi = {}
    for n in NOMES:
        if tem[n] < MIN_JOGOS_KPI or (n.startswith(("Noticias", "Movimento")) and concursos_com[n] < MIN_CONCURSOS_NOVO):
            por_kpi[n] = {"status": "coletando", "jogos": tem[n], "concursos": concursos_com[n]}
            continue
        sub = [b for b in base if b[2][n] is not None]
        r = resumo(*teste_no_tempo(sub, [n], a_cada=20))
        r["status"] = "medido"
        por_kpi[n] = r
    ativos = [n for n in NOMES if por_kpi[n].get("status") == "medido"]
    comb = resumo(*teste_no_tempo(base, ativos))
    ligado = bool(comb["forca"] > 2 and comb["acerto_modelo"] >= comb["acerto_mercado"])
    calib = aprende([(b[1], b[3]) for b in base], usar_empate=False, usar_gama=True)
    LP = np.log(np.array([aplica(b[1], calib) for b in base]))
    V = np.array([[b[2][n] if b[2][n] is not None else 0.0 for n in NOMES] for b in base])
    Y = np.array([b[3] for b in base])
    w = ajustar(LP, V, Y, ativos)
    luiz = carregar_pesos_luiz()
    comb_luiz = resumo(*teste_no_tempo(base, ativos, pesos_fixos=luiz)) if luiz else None
    luiz_ligado = bool(comb_luiz and comb_luiz["forca"] > 2 and comb_luiz["acerto_modelo"] >= comb_luiz["acerto_mercado"]
                       and comb_luiz["ganho"] > comb["ganho"])
    mod = {"ligado": ligado, "usa": "luiz" if luiz_ligado else ("aprendido" if ligado else "mercado"),
           "pesos": {n: round(float(w[NOMES.index(n)]), 4) for n in NOMES},
           "pesos_luiz": luiz, "combinado": comb, "combinado_luiz": comb_luiz, "por_kpi": por_kpi,
           "treinado_em_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    with open(MODELO, "w", encoding="utf-8") as f:
        json.dump(mod, f, indent=1, ensure_ascii=False)
    escrever_relatorio(mod)
    print(open(RELATORIO, encoding="utf-8").read())


def carregar_pesos_luiz():
    if not os.path.exists(PESOS_LUIZ):
        return {}
    with open(PESOS_LUIZ, encoding="utf-8") as f:
        d = json.load(f)
    return {k: float(v) for k, v in d.items() if k in KPIS and isinstance(v, (int, float))}


def leitura(r):
    if r.get("status") != "medido":
        return f"coletando ({r.get('concursos', 0)} concursos)"
    f = r["forca"]
    return "comprovado" if f >= 2 else ("promissor" if f >= 0.5 else ("neutro" if f > -0.5 else "atrapalha"))


def escrever_relatorio(mod):
    L = ["# Placar de KPIs", "",
         f"Atualizado em {mod['treinado_em_utc']} · teste no tempo (aprende só com concursos anteriores).", "",
         "Força = ganho sobre as odds dividido pelo erro: 2 ou mais = comprovado; 0,5 a 2 = promissor; perto de 0 = neutro; negativo = atrapalha.", "",
         "| Grupo | KPI | Jogos | Força | Peso aprendido | Leitura | O que mede |", "|---|---|---|---|---|---|---|"]
    for n, (_, tipo, grupo, desc) in KPIS.items():
        r = mod["por_kpi"][n]
        forca = f"{r['forca']:+.1f}" if r.get("status") == "medido" else "—"
        L.append(f"| {grupo} | {n} | {r.get('jogos', 0)} | {forca} | {mod['pesos'][n]:+.3f} | {leitura(r)} | {desc} |")
    c = mod["combinado"]
    L += ["", "## Todos os KPIs juntos", "",
          f"- Jogos de teste: {c['jogos']} · acerto: mercado {100 * c['acerto_mercado']:.1f}% × KPIs {100 * c['acerto_modelo']:.1f}% · força {c['forca']:+.1f}.",
          f"- Na previsão: **{'LIGADO' if mod['ligado'] else 'desligado'}** (liga sozinho com força acima de 2 sem perder acerto)."]
    if mod.get("combinado_luiz"):
        cl = mod["combinado_luiz"]
        L.append(f"- Pesos do Luiz: acerto {100 * cl['acerto_modelo']:.1f}% · força {cl['forca']:+.1f} "
                 f"({'em uso' if mod['usa'] == 'luiz' else 'não superou'}).")
    else:
        L.append("- Pesos do Luiz: nenhum definido (arquivo `motor/kpis_pesos_luiz.json`).")
    with open(RELATORIO, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


# ------------------------------------------------------------------ uso na previsao
def modelo():
    if not os.path.exists(MODELO):
        return None
    with open(MODELO, encoding="utf-8") as f:
        return json.load(f)


def aplicar(p, vals, mod=None):
    """Probabilidade final e contribuicao de cada KPI (em pontos de probabilidade do mandante)."""
    mod = mod or modelo()
    if not mod or mod.get("usa") == "mercado":
        return np.array(p), {}, False
    pesos = mod["pesos_luiz"] if mod.get("usa") == "luiz" else mod["pesos"]
    w = np.array([pesos.get(n, 0.0) for n in NOMES])
    v = np.array([[vals.get(n) if vals.get(n) is not None else 0.0 for n in NOMES]])
    lp = np.log(np.clip(np.array([p]), 1e-9, 1))
    q = probs(lp, v, w)[0]
    contrib = {}
    for i, n in enumerate(NOMES):
        if w[i] and v[0, i]:
            wi = np.zeros(len(NOMES))
            wi[i] = w[i]
            qi = probs(lp, v, wi)[0]
            contrib[n] = round(float(qi[0] - p[0]) * 100, 1) if KPIS[n][1] == "lado" else round(float(qi[1] - p[1]) * 100, 1)
    return q, contrib, True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "medir":
        medir()
    else:
        print(__doc__)
