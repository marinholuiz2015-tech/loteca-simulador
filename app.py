"""
LOTECA ELITE PRO — app.py v3.0
Camada 2: Poisson com histórico real do loteca_historico_v4.db
- Média dos últimos N jogos por time (configurável, padrão 10)
- Força de ataque e defesa individualizadas por time
- Fallback para médias de liga se time não encontrado no histórico
- Indicador "fonte de dados" por jogo: HISTORICO | LIGA | SIMULADO
- Mantém compatibilidade total com Camada 1
"""

import os
import math
import sqlite3
import logging
import threading
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ── Variáveis de ambiente ──────────────────────────────────────────────────────
FDATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")
ODDS_KEY  = os.getenv("ODDS_API_KEY", "")

_DB_CANDIDATOS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "loteca_historico_v4.db"),
    os.path.join(os.getcwd(), "loteca_historico_v4.db"),
    "/opt/render/project/src/loteca_historico_v4.db",
    "/data/loteca_historico_v4.db",
]

def _encontrar_db():
    for p in _DB_CANDIDATOS:
        if os.path.isfile(p):
            logger.info(f"Banco encontrado: {p}")
            return p
    logger.warning("loteca_historico_v4.db NÃO encontrado — usando médias de liga como fallback")
    return None

DB_PATH = _encontrar_db()

LIGAS = {
    "brasileirao":   {"codigo": "BSA",  "nome": "Brasileirão Série A",   "pais": "Brasil"},
    "copa_brasil":   {"codigo": "CB",   "nome": "Copa do Brasil",         "pais": "Brasil"},
    "libertadores":  {"codigo": "CLI",  "nome": "Copa Libertadores",      "pais": "Sul-América"},
    "serie_b":       {"codigo": "BSB",  "nome": "Brasileirão Série B",    "pais": "Brasil"},
    "premier":       {"codigo": "PL",   "nome": "Premier League",         "pais": "Inglaterra"},
    "la_liga":       {"codigo": "PD",   "nome": "La Liga",                "pais": "Espanha"},
    "serie_a_it":    {"codigo": "SA",   "nome": "Serie A (Itália)",       "pais": "Itália"},
    "bundesliga":    {"codigo": "BL1",  "nome": "Bundesliga",             "pais": "Alemanha"},
    "champions":     {"codigo": "CL",   "nome": "Champions League",       "pais": "Europa"},
    "copa_do_mundo": {"codigo": "WC",   "nome": "Copa do Mundo",          "pais": "Mundial"},
}

MEDIAS_LIGA = {
    "brasileirao":   {"atk_casa": 1.55, "atk_fora": 1.10, "def_casa": 1.10, "def_fora": 1.55},
    "serie_b":       {"atk_casa": 1.40, "atk_fora": 1.00, "def_casa": 1.00, "def_fora": 1.40},
    "copa_brasil":   {"atk_casa": 1.50, "atk_fora": 1.05, "def_casa": 1.05, "def_fora": 1.50},
    "libertadores":  {"atk_casa": 1.45, "atk_fora": 0.95, "def_casa": 0.95, "def_fora": 1.45},
    "champions":     {"atk_casa": 1.80, "atk_fora": 1.20, "def_casa": 1.20, "def_fora": 1.80},
    "premier":       {"atk_casa": 1.75, "atk_fora": 1.30, "def_casa": 1.30, "def_fora": 1.75},
    "la_liga":       {"atk_casa": 1.65, "atk_fora": 1.10, "def_casa": 1.10, "def_fora": 1.65},
    "serie_a_it":    {"atk_casa": 1.50, "atk_fora": 1.00, "def_casa": 1.00, "def_fora": 1.50},
    "bundesliga":    {"atk_casa": 1.90, "atk_fora": 1.35, "def_casa": 1.35, "def_fora": 1.90},
    "copa_do_mundo": {"atk_casa": 1.60, "atk_fora": 1.25, "def_casa": 1.25, "def_fora": 1.60},
}

_cache_medias_db  = {}
_cache_lock       = threading.Lock()
_db_schema_inspec = None

def _inspecionar_schema():
    global _db_schema_inspec
    if _db_schema_inspec is not None:
        return _db_schema_inspec
    if not DB_PATH:
        _db_schema_inspec = {}
        return {}
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = [r[0] for r in cur.fetchall()]
        schema = {}
        for t in tabelas:
            cur.execute(f"PRAGMA table_info({t})")
            colunas = [r[1].lower() for r in cur.fetchall()]
            schema[t] = colunas
        conn.close()
        _db_schema_inspec = schema
        logger.info(f"Schema do banco: {schema}")
        return schema
    except Exception as e:
        logger.error(f"Erro ao inspecionar schema: {e}")
        _db_schema_inspec = {}
        return {}

def _normalizar_time(nome: str) -> str:
    subs = {
        "atlético": "atletico", "athletico": "atletico",
        "fluminense": "fluminense", "flamengo": "flamengo",
        "são paulo": "sao paulo", "corinthians": "corinthians",
        "palmeiras": "palmeiras", "vasco": "vasco da gama",
        "botafogo": "botafogo", "grêmio": "gremio",
        "internacional": "internacional", "cruzeiro": "cruzeiro",
        "santos": "santos", "fortaleza": "fortaleza",
    }
    nome_low = nome.lower().strip()
    for k, v in subs.items():
        if k in nome_low:
            return v
    return nome_low

def buscar_medias_time(nome_time: str, n_jogos: int = 10):
    global _cache_medias_db
    cache_key = f"{nome_time}:{n_jogos}"
    with _cache_lock:
        if cache_key in _cache_medias_db:
            return _cache_medias_db[cache_key]
    if not DB_PATH:
        return None
    schema = _inspecionar_schema()
    if not schema:
        return None
    tabela_cfg = _detectar_tabela_jogos(schema)
    if not tabela_cfg:
        return None
    tabela       = tabela_cfg["tabela"]
    col_casa     = tabela_cfg["col_casa"]
    col_fora     = tabela_cfg["col_fora"]
    col_gols_casa = tabela_cfg["col_gols_casa"]
    col_gols_fora = tabela_cfg["col_gols_fora"]
    col_data     = tabela_cfg.get("col_data")
    nome_norm    = _normalizar_time(nome_time)
    resultado    = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        order_clause = f"ORDER BY {col_data} DESC" if col_data else ""
        cur.execute(f"""
            SELECT {col_gols_casa} AS gols_marcados, {col_gols_fora} AS gols_sofridos
            FROM {tabela}
            WHERE LOWER({col_casa}) LIKE ?
              AND {col_gols_casa} IS NOT NULL
            {order_clause}
            LIMIT {n_jogos}
        """, (f"%{nome_norm}%",))
        rows_casa = cur.fetchall()
        cur.execute(f"""
            SELECT {col_gols_fora} AS gols_marcados, {col_gols_casa} AS gols_sofridos
            FROM {tabela}
            WHERE LOWER({col_fora}) LIKE ?
              AND {col_gols_fora} IS NOT NULL
            {order_clause}
            LIMIT {n_jogos}
        """, (f"%{nome_norm}%",))
        rows_fora = cur.fetchall()
        conn.close()
        if rows_casa or rows_fora:
            def _media(rows, col):
                vals = [r[col] for r in rows if r[col] is not None]
                return round(sum(vals) / len(vals), 4) if vals else None
            resultado = {
                "atk_casa":          _media(rows_casa, "gols_marcados"),
                "def_sofridos_casa": _media(rows_casa, "gols_sofridos"),
                "atk_fora":          _media(rows_fora, "gols_marcados"),
                "def_sofridos_fora": _media(rows_fora, "gols_sofridos"),
                "n_jogos_casa":      len(rows_casa),
                "n_jogos_fora":      len(rows_fora),
                "fonte":             "historico",
            }
    except Exception as e:
        logger.error(f"Erro na query do time '{nome_time}': {e}")
        resultado = None
    with _cache_lock:
        _cache_medias_db[cache_key] = resultado
    return resultado

def _detectar_tabela_jogos(schema: dict):
    CASA_COLS  = ["mandante", "time_casa", "home", "home_team", "casa", "time_a"]
    FORA_COLS  = ["visitante", "time_fora", "away", "away_team", "fora", "time_b"]
    GCASA_COLS = ["gols_mandante", "gols_casa", "home_score", "placar_casa",
                  "gols_a", "score_a", "gols_home", "resultado_casa", "mandante_gols"]
    GFORA_COLS = ["gols_visitante", "gols_fora", "away_score", "placar_fora",
                  "gols_b", "score_b", "gols_away", "resultado_fora", "visitante_gols"]
    DATA_COLS  = ["data", "date", "data_jogo", "match_date", "dt_jogo", "concurso_data"]

    def _first_match(colunas, candidatos):
        for c in candidatos:
            if c in colunas:
                return c
        return None

    for tabela in schema.keys():
        cols = schema.get(tabela, [])
        col_casa = _first_match(cols, CASA_COLS)
        col_fora = _first_match(cols, FORA_COLS)
        col_gc   = _first_match(cols, GCASA_COLS)
        col_gf   = _first_match(cols, GFORA_COLS)
        col_data = _first_match(cols, DATA_COLS)
        if col_casa and col_fora and col_gc and col_gf:
            return {
                "tabela": tabela, "col_casa": col_casa, "col_fora": col_fora,
                "col_gols_casa": col_gc, "col_gols_fora": col_gf, "col_data": col_data,
            }
    return None

def _poisson_prob(lam: float, k: int) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def calcular_lambdas(atk_casa, atk_fora, def_casa, def_fora,
                     media_liga_atk=1.5, media_liga_def=1.2):
    lambda_casa = (atk_casa * def_fora / media_liga_atk) * 1.15
    lambda_fora = (atk_fora * def_casa / media_liga_def) * 0.90
    return round(max(0.20, min(lambda_casa, 6.0)), 4), round(max(0.20, min(lambda_fora, 6.0)), 4)

def calcular_probabilidades_poisson(lambda_casa, lambda_fora, max_gols=8):
    p1 = p_x = p2 = 0.0
    for i in range(max_gols + 1):
        for j in range(max_gols + 1):
            p = _poisson_prob(lambda_casa, i) * _poisson_prob(lambda_fora, j)
            if i > j:    p1  += p
            elif i == j: p_x += p
            else:        p2  += p
    total = p1 + p_x + p2
    if total == 0:
        return {"p1": 0.45, "px": 0.25, "p2": 0.30}
    return {"p1": round(p1/total, 4), "px": round(p_x/total, 4), "p2": round(p2/total, 4)}

def classificar_jogo(probs, limiar_seco=0.60):
    vals = sorted([probs["p1"], probs["px"], probs["p2"]], reverse=True)
    if vals[0] >= limiar_seco:          return "SECO"
    elif vals[0] + vals[1] >= 0.75:     return "DUPLO"
    else:                               return "TRIPLO"

def resultado_mais_provavel(probs):
    p1, px, p2 = probs["p1"], probs["px"], probs["p2"]
    if p1 >= px and p1 >= p2: return "1"
    elif px >= p1 and px >= p2: return "X"
    else: return "2"

def analisar_jogo_v2(jogo, liga_key, n_jogos_historico=10):
    medias_liga = MEDIAS_LIGA.get(liga_key, MEDIAS_LIGA["brasileirao"])
    ml_atk = (medias_liga["atk_casa"] + medias_liga["atk_fora"]) / 2
    ml_def = (medias_liga["def_casa"] + medias_liga["def_fora"]) / 2
    mandante  = jogo.get("mandante", "")
    visitante = jogo.get("visitante", "")
    hist_m = buscar_medias_time(mandante,  n_jogos_historico) if mandante else None
    hist_v = buscar_medias_time(visitante, n_jogos_historico) if visitante else None

    if hist_m and hist_m.get("atk_casa") is not None:
        atk_casa = hist_m["atk_casa"]
        def_casa = hist_m.get("def_sofridos_casa") or medias_liga["def_casa"]
        fonte_m  = "historico"; n_j_casa = hist_m.get("n_jogos_casa", 0)
    else:
        atk_casa = medias_liga["atk_casa"]; def_casa = medias_liga["def_casa"]
        fonte_m  = "liga"; n_j_casa = 0

    if hist_v and hist_v.get("atk_fora") is not None:
        atk_fora = hist_v["atk_fora"]
        def_fora = hist_v.get("def_sofridos_fora") or medias_liga["def_fora"]
        fonte_v  = "historico"; n_j_fora = hist_v.get("n_jogos_fora", 0)
    else:
        atk_fora = medias_liga["atk_fora"]; def_fora = medias_liga["def_fora"]
        fonte_v  = "liga"; n_j_fora = 0

    if fonte_m == "historico" and fonte_v == "historico": fonte_dados = "HISTORICO"
    elif fonte_m == "historico" or fonte_v == "historico": fonte_dados = "MISTO"
    else: fonte_dados = "LIGA"
    if jogo.get("_simulado"): fonte_dados = "SIMULADO"

    lam_c, lam_f = calcular_lambdas(atk_casa, atk_fora, def_casa, def_fora, ml_atk, ml_def)
    probs = calcular_probabilidades_poisson(lam_c, lam_f)
    classificacao = classificar_jogo(probs)
    vals = sorted([probs["p1"], probs["px"], probs["p2"]], reverse=True)
    confianca = round((vals[0] - vals[1]) * 100, 1)
    return {
        **jogo,
        "probabilidades": probs,
        "classificacao": classificacao,
        "resultado": resultado_mais_provavel(probs),
        "confianca": confianca,
        "lambda_casa": lam_c, "lambda_fora": lam_f,
        "fonte_dados": fonte_dados,
        "detalhe_fontes": {
            "mandante":  {"time": mandante,  "fonte": fonte_m, "n_jogos": n_j_casa},
            "visitante": {"time": visitante, "fonte": fonte_v, "n_jogos": n_j_fora},
        },
        "parametros_poisson": {
            "atk_casa": round(atk_casa, 3), "def_casa": round(def_casa, 3),
            "atk_fora": round(atk_fora, 3), "def_fora": round(def_fora, 3),
        },
        "metodo": "poisson_v2_camada2", "odds": None,
    }

def _headers_fdata():
    return {"X-Auth-Token": FDATA_KEY} if FDATA_KEY else {}

def buscar_jogos_liga(liga_key, dias_frente=14):
    liga = LIGAS.get(liga_key)
    if not liga:
        raise ValueError(f"Liga '{liga_key}' não encontrada.")
    hoje = datetime.now(timezone.utc)
    ate  = hoje + timedelta(days=dias_frente)
    url  = (f"https://api.football-data.org/v4/competitions/{liga['codigo']}/matches"
            f"?status=SCHEDULED&dateFrom={hoje.strftime('%Y-%m-%d')}&dateTo={ate.strftime('%Y-%m-%d')}")
    try:
        resp = requests.get(url, headers=_headers_fdata(), timeout=10)
        if resp.status_code in (401, 403):
            return _jogos_simulados(liga_key)
        if resp.status_code == 429:
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Erro ao buscar jogos: {e}")
        return _jogos_simulados(liga_key)
    jogos = []
    for m in data.get("matches", []):
        home = m.get("homeTeam", {}).get("shortName") or m.get("homeTeam", {}).get("name", "?")
        away = m.get("awayTeam", {}).get("shortName") or m.get("awayTeam", {}).get("name", "?")
        jogos.append({"id": str(m.get("id", "")), "mandante": home, "visitante": away,
                      "data_utc": m.get("utcDate", ""), "liga": liga["nome"], "liga_key": liga_key})
    return jogos

def _jogos_simulados(liga_key):
    base = {
        "brasileirao":  [("Flamengo","Palmeiras"),("São Paulo","Corinthians"),
                         ("Botafogo","Fluminense"),("Cruzeiro","Atlético MG"),
                         ("Grêmio","Internacional"),("Santos","Vasco"),
                         ("Fortaleza","Ceará"),("Bahia","Vitória"),
                         ("Bragantino","Mirassol"),("Cuiabá","Goiás")],
        "libertadores": [("Flamengo","River Plate"),("Palmeiras","Boca Juniors"),
                         ("Botafogo","Peñarol"),("Atlético MG","Nacional UY")],
        "champions":    [("Real Madrid","Manchester City"),("Bayern","PSG"),
                         ("Arsenal","Barcelona"),("Liverpool","Inter Milão")],
    }
    pares = base.get(liga_key, base["brasileirao"])
    hoje  = datetime.now(timezone.utc)
    return [{"id": f"sim_{i}", "mandante": h, "visitante": a,
             "data_utc": (hoje + timedelta(days=i % 7)).isoformat(),
             "liga": LIGAS.get(liga_key, {}).get("nome", liga_key),
             "liga_key": liga_key, "_simulado": True}
            for i, (h, a) in enumerate(pares)]

# ── Rotas ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/ligas")
def listar_ligas():
    return jsonify({"ligas": [{"key": k, "nome": v["nome"], "pais": v["pais"]} for k, v in LIGAS.items()]})

@app.route("/api/jogos")
def listar_jogos():
    liga_key = request.args.get("liga", "brasileirao")
    dias     = int(request.args.get("dias", 14))
    try:
        jogos = buscar_jogos_liga(liga_key, dias_frente=dias)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    return jsonify({"liga": LIGAS.get(liga_key, {}).get("nome", liga_key),
                    "total": len(jogos), "jogos": jogos,
                    "simulado": any(j.get("_simulado") for j in jogos)})

@app.route("/api/grade-automatica")
def grade_automatica():
    liga_key  = request.args.get("liga", "brasileirao")
    dias      = int(request.args.get("dias", 14))
    max_jogos = int(request.args.get("max", 14))
    n_hist    = int(request.args.get("n_historico", 10))
    try:
        jogos_raw = buscar_jogos_liga(liga_key, dias_frente=dias)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    jogos_para_analisar = jogos_raw[:max_jogos]
    resultados = [analisar_jogo_v2(j, liga_key, n_hist) for j in jogos_para_analisar]
    secos   = sum(1 for r in resultados if r["classificacao"] == "SECO")
    duplos  = sum(1 for r in resultados if r["classificacao"] == "DUPLO")
    triplos = sum(1 for r in resultados if r["classificacao"] == "TRIPLO")
    n_hist_total = sum(1 for r in resultados if r["fonte_dados"] in ("HISTORICO", "MISTO"))
    n_liga       = sum(1 for r in resultados if r["fonte_dados"] == "LIGA")
    n_simulado   = sum(1 for r in resultados if r["fonte_dados"] == "SIMULADO")
    return jsonify({
        "liga": LIGAS.get(liga_key, {}).get("nome", liga_key),
        "versao_motor": "3.0-camada2", "total": len(resultados),
        "secos": secos, "duplos": duplos, "triplos": triplos,
        "custo_estimado_reais": round(3.0 * (2 ** duplos) * (3 ** triplos) / 100, 2),
        "cobertura_historico": {"com_historico": n_hist_total, "apenas_liga": n_liga, "simulado": n_simulado},
        "jogos": resultados,
        "simulado": any(j.get("_simulado") for j in jogos_para_analisar),
        "db_conectado": DB_PATH is not None,
    })

@app.route("/api/analisar", methods=["POST"])
def analisar_grade():
    body        = request.get_json(silent=True) or {}
    jogos_input = body.get("jogos", [])
    liga_key    = body.get("liga", "brasileirao")
    n_hist      = int(body.get("n_historico", 10))
    if not jogos_input:
        return jsonify({"erro": "Envie ao menos 1 jogo"}), 400
    resultados = [analisar_jogo_v2(j, liga_key, n_hist) for j in jogos_input]
    secos   = sum(1 for r in resultados if r["classificacao"] == "SECO")
    duplos  = sum(1 for r in resultados if r["classificacao"] == "DUPLO")
    triplos = sum(1 for r in resultados if r["classificacao"] == "TRIPLO")
    return jsonify({"total": len(resultados), "secos": secos, "duplos": duplos, "triplos": triplos,
                    "custo_estimado_reais": round(3.0 * (2 ** duplos) * (3 ** triplos) / 100, 2),
                    "jogos": resultados})

@app.route("/api/time/<nome>")
def consultar_time(nome):
    n_jogos = int(request.args.get("n", 10))
    medias  = buscar_medias_time(nome, n_jogos)
    if not medias:
        return jsonify({"time": nome, "encontrado": False}), 404
    return jsonify({"time": nome, "encontrado": True, "medias": medias})

@app.route("/api/db-info")
def db_info():
    if not DB_PATH:
        return jsonify({"db_conectado": False})
    schema = _inspecionar_schema()
    tabela_cfg = _detectar_tabela_jogos(schema)
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        cur  = conn.cursor()
        info = {}
        for t in schema:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            info[t] = {"colunas": schema[t], "registros": cur.fetchone()[0]}
        conn.close()
        return jsonify({"db_conectado": True, "db_path": DB_PATH,
                        "tabelas": info, "tabela_jogos_detectada": tabela_cfg})
    except Exception as e:
        return jsonify({"db_conectado": True, "erro": str(e)}), 500

@app.route("/api/status")
def status():
    schema = _inspecionar_schema() if DB_PATH else {}
    tabela_cfg = _detectar_tabela_jogos(schema) if schema else None
    return jsonify({
        "status": "online", "versao": "3.0-camada2",
        "ligas_suportadas": len(LIGAS),
        "integracoes": {
            "football_data_org":    "configurada" if FDATA_KEY else "ausente (simulado)",
            "the_odds_api":         "configurada" if ODDS_KEY  else "ausente",
            "loteca_historico_db":  "conectado"   if DB_PATH   else "ausente (usando médias de liga)",
        },
        "camadas": {
            "camada_1": "✅ busca dinâmica + Poisson com médias globais",
            "camada_2": "✅ Poisson com histórico real do banco loteca_historico_v4.db",
            "camada_3": "🔲 xG, Cartola FC, Smart Money 48h",
            "camada_4": "🔲 lesões, árbitro, clima, altitude",
        },
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")
