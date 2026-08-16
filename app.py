"""
Loteca Elite Pro — app.py VERSÃO FINAL
Arquivo único. Sem dependências externas obrigatórias.
APIs opcionais: se falharem o serviço continua no ar.

Variáveis de ambiente no Render:
  RAPIDAPI_KEY  → API-Football (fixtures, lesões, escalação)
  ODDS_API_KEY  → The Odds API (odds de mercado Bet365/Pinnacle)
  DATABASE_URL  → PostgreSQL (se ausente usa SQLite temporário)
"""

import os, math, sqlite3, logging, requests
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("loteca")

app = Flask(__name__)
CORS(app)

# ─── Variáveis de ambiente ────────────────────────────────────
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
ODDS_KEY     = os.getenv("ODDS_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG       = DATABASE_URL.startswith("postgres")

# ─── Banco de dados ───────────────────────────────────────────
def get_conn():
    if USE_PG:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect("/tmp/loteca_elite.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_conn()
        ph   = "%s" if USE_PG else "?"
        sql  = """CREATE TABLE IF NOT EXISTS historico (
            id         SERIAL PRIMARY KEY,
            concurso   INTEGER,
            mandante   TEXT, visitante TEXT,
            prob_1     REAL, prob_x REAL, prob_2 REAL,
            score      REAL, tipo_grade TEXT, coluna TEXT,
            resultado  TEXT, acertou INTEGER,
            odd_1 REAL, odd_x REAL, odd_2 REAL,
            criado_em  TEXT DEFAULT CURRENT_TIMESTAMP
        )""" if USE_PG else """CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concurso INTEGER, mandante TEXT, visitante TEXT,
            prob_1 REAL, prob_x REAL, prob_2 REAL,
            score REAL, tipo_grade TEXT, coluna TEXT,
            resultado TEXT, acertou INTEGER,
            odd_1 REAL, odd_x REAL, odd_2 REAL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
        conn.cursor().execute(sql)
        conn.commit(); conn.close()
        log.info("Banco OK: %s", "PostgreSQL" if USE_PG else "SQLite")
    except Exception as e:
        log.warning("Banco indisponível: %s", e)

init_db()

# ─── ELO dos times ───────────────────────────────────────────
ELO = {
    # Seleções
    "Argentina":2140,"França":2100,"Inglaterra":2080,"Espanha":2070,
    "Alemanha":2060,"Portugal":2040,"Holanda":2030,"Brasil":2050,
    "Bélgica":1990,"Uruguai":1960,"Itália":2010,"México":1880,
    "Estados Unidos":1880,"Marrocos":1900,"Japão":1870,"Coreia do Sul":1850,
    "Equador":1830,"Suíça":1870,"Canadá":1840,"Austrália":1820,
    "Turquia":1840,"Escócia":1820,"Arábia Saudita":1780,"Paraguai":1780,
    "Catar":1650,"Curaçao":1540,"Cabo Verde":1660,"África do Sul":1700,
    "Rep. Tcheca":1820,"Haiti":1490,"Egito":1770,"Costa do Marfim":1820,
    "Senegal":1850,"Congo-Kinshasa":1650,"Argélia":1700,"Noruega":1830,
    "Iraque":1580,"Croácia":1890,
    # Clubes Brasileiros
    "Palmeiras":1820,"Flamengo":1810,"Botafogo":1780,"Fluminense":1750,
    "Atletico MG":1760,"São Paulo":1740,"Corinthians":1720,"Grêmio":1700,
    "Internacional":1710,"Cruzeiro":1690,"Vasco da Gama":1660,"Santos":1650,
    "Fortaleza":1670,"Bahia":1640,"Mirassol":1610,"Juventude":1590,
    "Vitória":1580,"Sport":1560,"Bragantino":1620,"Athletico PR":1660,
    "Chapecoense":1480,"Londrina":1470,"Remo":1460,"CRB":1450,
    # Premier League
    "Manchester City":1810,"Arsenal":1750,"Liverpool":1790,"Chelsea":1730,
    "Manchester United":1700,"Tottenham":1690,"Aston Villa":1720,
    "Crystal Palace":1680,"Everton":1620,"Newcastle":1700,
}

MEDIA_GOLS = {
    "copa":    {"casa":1.35,"fora":1.05},
    "serie_a": {"casa":1.42,"fora":1.05},
    "serie_b": {"casa":1.35,"fora":1.00},
    "serie_c": {"casa":1.28,"fora":0.98},
    "premier": {"casa":1.53,"fora":1.22},
    "la_liga": {"casa":1.47,"fora":1.10},
    "libertadores":{"casa":1.38,"fora":0.95},
}

# ─── Poisson bivariado ────────────────────────────────────────
def _poi(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def poisson_probs(mandante, visitante, liga="_default"):
    ec  = ELO.get(mandante, 1650)
    ef  = ELO.get(visitante, 1650)
    med = MEDIA_GOLS.get(liga, {"casa":1.40,"fora":1.05})
    ajuste = (ec - ef) / 200 * 0.25
    lc = max(0.3, med["casa"] + ajuste + 0.06)
    lf = max(0.3, med["fora"] - ajuste)
    p1 = px = p2 = 0.0
    for i in range(9):
        for j in range(9):
            p = _poi(lc, i) * _poi(lf, j)
            if i > j:    p1 += p
            elif i == j: px += p
            else:        p2 += p
    t = p1 + px + p2
    return {
        "1": round(p1/t, 4), "X": round(px/t, 4), "2": round(p2/t, 4),
        "elo_casa": ec, "elo_fora": ef,
        "lam_casa": round(lc, 3), "lam_fora": round(lf, 3),
    }

# ─── Remoção de margem ────────────────────────────────────────
def sem_margem(o1, ox, o2):
    r1, rx, r2 = 1/o1, 1/ox, 1/o2
    over = r1 + rx + r2
    return {"1":round(r1/over,4),"X":round(rx/over,4),"2":round(r2/over,4),"over":round(over,4)}

# ─── Blending ponderado (Fase 1) ─────────────────────────────
def blending(prob_m, odds=None, w=0.65):
    if not odds:
        return {**prob_m, "fonte":"modelo_puro"}
    pm = sem_margem(odds["1"], odds["X"], odds["2"])
    wm = 1 - w
    out = {}
    for k in ["1","X","2"]:
        out[k] = round(prob_m[k]*w + pm[k]*wm, 4)
    t = sum(out.values())
    out = {k: round(v/t, 4) for k, v in out.items()}
    out["fonte"]     = "blend_65_35"
    out["overround"] = pm["over"]
    return out

# ─── Classificação Loteca (limiar dinâmico) ───────────────────
def classificar(probs, odd_1=None, liga="_default"):
    p1, px, p2 = probs["1"], probs["X"], probs["2"]
    ordem = sorted([("1",p1),("X",px),("2",p2)], key=lambda x: x[1], reverse=True)
    top_c, top_v = ordem[0]
    seg_c, _     = ordem[1]

    # Limiar dinâmico: em Copa com favorito muito curto → força DUPLO
    lim = 0.52
    if liga == "copa" and odd_1:
        if odd_1 < 1.50:   lim = 0.82
        elif odd_1 < 1.80: lim = 0.62

    if top_v >= lim:
        tipo, cols = "SECO",   [top_c]
    elif top_v >= 0.40:
        tipo, cols = "DUPLO",  [top_c, seg_c]
    else:
        tipo, cols = "TRIPLO", ["1","X","2"]

    classe = "A" if top_v>=0.80 else "B" if top_v>=0.65 else \
             "C" if top_v>=0.50 else "D" if top_v>=0.40 else "E"
    return {
        "tipo": tipo,
        "colunas": cols,
        "coluna_display": "/".join(sorted(cols)),
        "confianca": round(top_v*100, 1),
        "classe": classe,
    }

# ─── Kelly Criterion ─────────────────────────────────────────
def kelly(prob, odd, banca=100.0, fracao=0.25):
    b  = odd - 1.0
    kp = (b*prob - (1-prob)) / b if b > 0 else -1.0
    ev = prob*b - (1-prob)
    ok = kp > 0.01 and ev > 0.02
    return {
        "stake":   round(banca*max(0,kp*fracao), 2) if ok else 0.0,
        "ev":      round(ev, 4),
        "apostar": ok,
    }

# ─── Score 0-100 ─────────────────────────────────────────────
def score(classif, mot=0.70):
    return round(min(100.0, classif["confianca"]*(0.85+0.15*mot)), 1)

# ─── Painel de custos ────────────────────────────────────────
def painel(jogos):
    nd = sum(1 for j in jogos if j["classificacao"]["tipo"]=="DUPLO")
    nt = sum(1 for j in jogos if j["classificacao"]["tipo"]=="TRIPLO")
    def c(d,t): return round((2**d)*(3**t)*3.0, 2)
    return {
        "secos":  sum(1 for j in jogos if j["classificacao"]["tipo"]=="SECO"),
        "duplos": nd, "triplos": nt,
        "custo_minimo":      c(nd, 0),
        "custo_recomendado": c(nd, min(nt,1)),
        "custo_completo":    c(nd, nt),
    }

# ─── API-Football: busca jogos ao vivo ───────────────────────
def apif_get(endpoint, params):
    if not RAPIDAPI_KEY:
        return None
    try:
        r = requests.get(
            f"https://api-football-v1.p.rapidapi.com/v3/{endpoint}",
            headers={"X-RapidAPI-Key": RAPIDAPI_KEY,
                     "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"},
            params=params, timeout=8
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.warning("API-Football erro: %s", e)
    return None

def buscar_proximos_jogos(league_id, season=2026):
    data = apif_get("fixtures", {"league": league_id, "season": season,
                                  "status": "NS", "next": 14})
    if not data:
        return []
    jogos = []
    for fix in data.get("response", []):
        f, t = fix["fixture"], fix["teams"]
        jogos.append({
            "id":        f["id"],
            "mandante":  t["home"]["name"],
            "visitante": t["away"]["name"],
            "data":      f["date"][:10],
            "hora":      f["date"][11:16],
            "status":    f["status"]["short"],
        })
    return jogos

# ─── The Odds API ────────────────────────────────────────────
def buscar_odds(sport="soccer_brazil_campeonato"):
    if not ODDS_KEY:
        return {}
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
            params={"apiKey": ODDS_KEY, "regions":"eu",
                    "markets":"h2h", "oddsFormat":"decimal"},
            timeout=8
        )
        if r.status_code != 200:
            return {}
        resultado = {}
        for ev in r.json():
            for book in ev.get("bookmakers", []):
                if book["key"] not in ("pinnacle","bet365","betfair"):
                    continue
                for mkt in book.get("markets", []):
                    if mkt["key"] != "h2h":
                        continue
                    odds = {o["name"]: o["price"] for o in mkt["outcomes"]}
                    key  = f"{ev['home_team']}|{ev['away_team']}"
                    resultado[key] = {
                        "1": odds.get(ev["home_team"], 0),
                        "X": odds.get("Draw", 0),
                        "2": odds.get(ev["away_team"], 0),
                        "casa": book["key"],
                    }
                    break
                break
        return resultado
    except Exception as e:
        log.warning("Odds API erro: %s", e)
        return {}

# ─── Dados dos concursos ─────────────────────────────────────
CONCURSOS = {
    1255: {
        "nome":"Copa Loteca — 1ª Rodada","periodo":"11-15 jun 2026","liga":"copa",
        "jogos":[
            {"id":1, "mandante":"México",         "visitante":"África do Sul","data":"11/06","hora":"16h","odds":{"1":1.85,"X":3.40,"2":4.20}},
            {"id":2, "mandante":"Coreia do Sul",  "visitante":"Rep. Tcheca",  "data":"11/06","hora":"23h","odds":{"1":2.40,"X":3.10,"2":2.80}},
            {"id":3, "mandante":"Canadá",         "visitante":"Itália",       "data":"12/06","hora":"16h","odds":{"1":3.20,"X":3.30,"2":2.10}},
            {"id":4, "mandante":"Estados Unidos", "visitante":"Paraguai",     "data":"12/06","hora":"22h","odds":{"1":1.75,"X":3.50,"2":4.80}},
            {"id":5, "mandante":"Austrália",      "visitante":"Turquia",      "data":"13/06","hora":"01h","odds":{"1":2.20,"X":3.20,"2":3.10}},
            {"id":6, "mandante":"Catar",          "visitante":"Suíça",        "data":"13/06","hora":"16h","odds":{"1":4.50,"X":3.60,"2":1.70}},
            {"id":7, "mandante":"Brasil",         "visitante":"Marrocos",     "data":"13/06","hora":"19h","odds":{"1":1.65,"X":3.60,"2":5.50}},
            {"id":8, "mandante":"Haiti",          "visitante":"Escócia",      "data":"13/06","hora":"22h","odds":{"1":4.80,"X":3.50,"2":1.65}},
            {"id":9, "mandante":"Alemanha",       "visitante":"Curaçao",      "data":"14/06","hora":"14h","odds":{"1":1.18,"X":7.00,"2":14.0}},
            {"id":10,"mandante":"Holanda",        "visitante":"Japão",        "data":"14/06","hora":"17h","odds":{"1":1.90,"X":3.40,"2":3.80}},
            {"id":11,"mandante":"Costa do Marfim","visitante":"Equador",      "data":"14/06","hora":"20h","odds":{"1":2.50,"X":3.10,"2":2.80}},
            {"id":12,"mandante":"Espanha",        "visitante":"Cabo Verde",   "data":"15/06","hora":"13h","odds":{"1":1.25,"X":5.50,"2":10.0}},
            {"id":13,"mandante":"Bélgica",        "visitante":"Egito",        "data":"15/06","hora":"16h","odds":{"1":1.60,"X":3.70,"2":5.80}},
            {"id":14,"mandante":"Arábia Saudita", "visitante":"Uruguai",      "data":"15/06","hora":"19h","odds":{"1":3.80,"X":3.20,"2":1.90}},
        ]
    },
    1256: {"nome":"Copa Loteca — 2ª Rodada","periodo":"jun 2026","liga":"copa","jogos":[]},
    1257: {"nome":"Copa Loteca — 3ª Rodada","periodo":"jun 2026","liga":"copa","jogos":[]},
    1258: {"nome":"Copa Loteca — 4ª Rodada","periodo":"jun 2026","liga":"copa","jogos":[]},
}

# ─── Analisar um jogo ────────────────────────────────────────
def analisar_jogo(mandante, visitante, liga="_default", odds=None, banca=100.0):
    pm  = poisson_probs(mandante, visitante, liga)
    pf  = blending(pm, odds)
    cl  = classificar(pf, odd_1=odds["1"] if odds else None, liga=liga)
    sc  = score(cl)
    # Kelly
    kelly_res, melhor = {}, None
    if odds:
        for res in ["1","X","2"]:
            if odds.get(res, 0) > 1.0:
                kelly_res[res] = kelly(pf[res], odds[res], banca)
        candidatos = [(r,k) for r,k in kelly_res.items() if k["apostar"]]
        if candidatos:
            best = max(candidatos, key=lambda x: x[1]["ev"])
            melhor = {"resultado":best[0],"odd":odds[best[0]],
                      "ev":best[1]["ev"],"stake":best[1]["stake"]}
    return {
        "prob_modelo": {"1":pm["1"],"X":pm["X"],"2":pm["2"]},
        "prob_final":  {"1":pf["1"],"X":pf["X"],"2":pf["2"]},
        "fonte": pf.get("fonte","modelo_puro"),
        "overround": pf.get("overround"),
        "elo_casa":  pm["elo_casa"], "elo_fora": pm["elo_fora"],
        "lam_casa":  pm["lam_casa"], "lam_fora": pm["lam_fora"],
        "classificacao": cl,
        "score": sc,
        "kelly": kelly_res or None,
        "melhor_aposta": melhor,
    }

# ════════════════════════════════════════════════════════════
# ROTAS
# ════════════════════════════════════════════════════════════

@app.route("/health")
@app.route("/api/status")
def health():
    apis = {
        "odds_api":     {"configurada": bool(ODDS_KEY),     "status": "não configurada"},
        "api_football": {"configurada": bool(RAPIDAPI_KEY), "status": "não configurada"},
        "banco":        {"tipo": "postgresql" if USE_PG else "sqlite", "status": "ok"},
    }
    # Testa Odds API
    if ODDS_KEY:
        try:
            r = requests.get("https://api.the-odds-api.com/v4/sports",
                             params={"apiKey":ODDS_KEY}, timeout=6)
            if r.status_code == 200:
                apis["odds_api"]["status"]             = "conectada"
                apis["odds_api"]["requests_remaining"] = r.headers.get("x-requests-remaining","?")
                apis["odds_api"]["requests_used"]      = r.headers.get("x-requests-used","?")
            else:
                apis["odds_api"]["status"] = f"erro {r.status_code}"
        except:
            apis["odds_api"]["status"] = "timeout"
    # Testa API-Football
    if RAPIDAPI_KEY:
        try:
            r = requests.get(
                "https://api-football-v1.p.rapidapi.com/v3/status",
                headers={"X-RapidAPI-Key": RAPIDAPI_KEY,
                         "X-RapidAPI-Host":"api-football-v1.p.rapidapi.com"},
                timeout=6
            )
            if r.status_code == 200:
                d = r.json().get("response", {})
                apis["api_football"]["status"]         = "conectada"
                apis["api_football"]["requests_hoje"]  = d.get("requests",{}).get("current","?")
                apis["api_football"]["limite_dia"]     = d.get("requests",{}).get("limit_day","?")
            else:
                apis["api_football"]["status"] = f"erro {r.status_code}"
        except:
            apis["api_football"]["status"] = "timeout"

    return jsonify({
        "status":  "ok",
        "versao":  "Loteca Elite Pro v9.0",
        "modelo":  "poisson_elo + blending_fase1 + kelly",
        "banco":   "postgresql" if USE_PG else "sqlite",
        "apis":    apis,
        "rotas": {
            "grade":      "/api/grade-automatica",
            "concurso":   "/api/concurso/{num}",
            "analisar":   "/api/analisar?mandante=X&visitante=Y&liga=copa",
            "liga_ao_vivo":"/api/liga/{league_id}",
            "resultado":  "POST /api/resultado",
            "historico":  "/api/historico",
        }
    })

@app.route("/")
@app.route("/api/grade-automatica")
def grade_automatica():
    return concurso(1255)

@app.route("/api/concurso/<int:num>")
def concurso(num):
    dados = CONCURSOS.get(num)
    if not dados:
        return jsonify({"status":"erro","mensagem":f"Concurso {num} não encontrado"}), 404
    if not dados["jogos"]:
        return jsonify({"status":"aviso","mensagem":f"Concurso {num} ainda sem jogos cadastrados","nome":dados["nome"]}), 200

    banca = float(request.args.get("banca", 100))
    liga  = dados["liga"]
    jogos = []
    for j in dados["jogos"]:
        analise = analisar_jogo(j["mandante"], j["visitante"], liga,
                                odds=j.get("odds"), banca=banca)
        jogos.append({**j, **analise})

    return jsonify({
        "status":"sucesso","concurso":num,
        "nome":dados["nome"],"periodo":dados["periodo"],
        "modelo":"poisson_elo_v2+blending+kelly",
        "total_jogos":len(jogos),"jogos":jogos,
        "painel":painel(jogos),
    })

@app.route("/api/analisar")
def analisar():
    m    = request.args.get("mandante","")
    v    = request.args.get("visitante","")
    liga = request.args.get("liga","_default")
    o1   = request.args.get("odd_1", type=float)
    ox   = request.args.get("odd_x", type=float)
    o2   = request.args.get("odd_2", type=float)
    banca= float(request.args.get("banca", 100))

    if not m or not v:
        return jsonify({"status":"erro","mensagem":"mandante e visitante obrigatórios"}), 400

    odds = {"1":o1,"X":ox,"2":o2} if all([o1,ox,o2]) else None
    analise = analisar_jogo(m, v, liga, odds=odds, banca=banca)
    return jsonify({"status":"sucesso","mandante":m,"visitante":v,"liga":liga,**analise})

@app.route("/api/liga/<int:league_id>")
def liga_ao_vivo(league_id):
    """Busca próximos jogos de uma liga via API-Football e analisa."""
    if not RAPIDAPI_KEY:
        return jsonify({"status":"erro","mensagem":"RAPIDAPI_KEY não configurada"}), 400
    jogos_raw = buscar_proximos_jogos(league_id)
    if not jogos_raw:
        return jsonify({"status":"aviso","mensagem":"Nenhum jogo encontrado","league_id":league_id})

    # Mapa league_id → liga
    liga_map = {71:"serie_a",72:"serie_b",75:"serie_c",13:"libertadores",
                39:"premier",140:"la_liga",78:"bundesliga",135:"serie_a_ita"}
    liga = liga_map.get(league_id,"_default")
    jogos = []
    for j in jogos_raw:
        analise = analisar_jogo(j["mandante"], j["visitante"], liga)
        jogos.append({**j, **analise})

    return jsonify({
        "status":"sucesso","league_id":league_id,"liga":liga,
        "total":len(jogos),"jogos":jogos,"painel":painel(jogos),
    })

@app.route("/api/resultado", methods=["POST"])
def resultado():
    d = request.get_json() or {}
    concurso_n = d.get("concurso")
    mandante   = d.get("mandante","")
    visitante  = d.get("visitante","")
    res        = d.get("resultado","")
    gols_c     = d.get("gols_casa", 0)
    gols_f     = d.get("gols_fora", 0)

    if res not in ["H","D","A"]:
        return jsonify({"status":"erro","mensagem":"resultado deve ser H (casa), D (empate) ou A (visitante)"}), 400

    try:
        conn = get_conn()
        ph   = "%s" if USE_PG else "?"
        conn.cursor().execute(
            f"INSERT INTO historico(concurso,mandante,visitante,resultado) VALUES({ph},{ph},{ph},{ph})",
            (concurso_n, mandante, visitante, res)
        )
        conn.commit(); conn.close()
        return jsonify({"status":"sucesso","mensagem":"Resultado registrado","concurso":concurso_n})
    except Exception as e:
        return jsonify({"status":"erro","mensagem":str(e)}), 500

@app.route("/api/historico")
def historico():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT * FROM historico ORDER BY id DESC LIMIT 100")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({"status":"sucesso","total":len(rows),"registros":rows})
    except Exception as e:
        return jsonify({"status":"erro","mensagem":str(e)}), 500

@app.route("/api/db-info")
def db_info():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM historico")
        total = cur.fetchone()[0]
        conn.close()
        return jsonify({
            "status":"sucesso","banco":"postgresql" if USE_PG else "sqlite",
            "total_registros":total,
        })
    except Exception as e:
        return jsonify({"status":"erro","mensagem":str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
