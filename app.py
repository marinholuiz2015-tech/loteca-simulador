"""
LOTECA ELITE PRO — app.py
Camada 1: Motor de busca dinâmica de jogos
"""

import os
import math
import logging
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

FDATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")
ODDS_KEY  = os.getenv("ODDS_API_KEY", "")

LIGAS = {
    "brasileirao":   {"codigo": "BSA",  "nome": "Brasileirão Série A",  "pais": "Brasil"},
    "copa_brasil":   {"codigo": "CB",   "nome": "Copa do Brasil",        "pais": "Brasil"},
    "libertadores":  {"codigo": "CLI",  "nome": "Copa Libertadores",     "pais": "Sul-América"},
    "serie_b":       {"codigo": "BSB",  "nome": "Brasileirão Série B",   "pais": "Brasil"},
    "premier":       {"codigo": "PL",   "nome": "Premier League",        "pais": "Inglaterra"},
    "la_liga":       {"codigo": "PD",   "nome": "La Liga",               "pais": "Espanha"},
    "serie_a_it":    {"codigo": "SA",   "nome": "Serie A (Itália)",      "pais": "Itália"},
    "bundesliga":    {"codigo": "BL1",  "nome": "Bundesliga",            "pais": "Alemanha"},
    "champions":     {"codigo": "CL",   "nome": "Champions League",      "pais": "Europa"},
    "copa_do_mundo": {"codigo": "WC",   "nome": "Copa do Mundo",         "pais": "Mundial"},
}

def _poisson_prob(lam, k):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def calcular_probabilidades_poisson(media_gols_casa, media_gols_fora,
                                     media_sofridos_casa=None, media_sofridos_fora=None,
                                     max_gols=7):
    ataque_casa = media_gols_casa
    ataque_fora = media_gols_fora
    defesa_casa = media_sofridos_casa if media_sofridos_casa else media_gols_fora * 0.9
    defesa_fora = media_sofridos_fora if media_sofridos_fora else media_gols_casa * 0.9
    lambda_casa = ataque_casa * (defesa_fora / max(0.5, (ataque_fora + defesa_casa) / 2)) * 1.15
    lambda_fora = ataque_fora * (defesa_casa / max(0.5, (ataque_casa + defesa_fora) / 2)) * 0.90
    lambda_casa = max(0.3, min(lambda_casa, 5.0))
    lambda_fora = max(0.3, min(lambda_fora, 5.0))
    p1 = p_x = p2 = 0.0
    for i in range(max_gols + 1):
        for j in range(max_gols + 1):
            p = _poisson_prob(lambda_casa, i) * _poisson_prob(lambda_fora, j)
            if i > j: p1 += p
            elif i == j: p_x += p
            else: p2 += p
    total = p1 + p_x + p2
    if total == 0:
        p1, p_x, p2 = 0.45, 0.25, 0.30
    return {"p1": round(p1/total,4), "px": round(p_x/total,4), "p2": round(p2/total,4)}

def classificar_jogo(probs, limiar_seco=0.60):
    p1, px, p2 = probs["p1"], probs["px"], probs["p2"]
    top1 = max(p1, px, p2)
    vals = sorted([p1, px, p2], reverse=True)
    if top1 >= limiar_seco: return "SECO"
    elif vals[0] + vals[1] >= 0.75: return "DUPLO"
    else: return "TRIPLO"

def resultado_mais_provavel(probs):
    p1, px, p2 = probs["p1"], probs["px"], probs["p2"]
    if p1 >= px and p1 >= p2: return "1"
    elif px >= p1 and px >= p2: return "X"
    else: return "2"

def _headers_fdata():
    return {"X-Auth-Token": FDATA_KEY} if FDATA_KEY else {}

def buscar_jogos_liga(liga_key, dias_frente=14):
    liga = LIGAS.get(liga_key)
    if not liga:
        raise ValueError(f"Liga '{liga_key}' não encontrada.")
    codigo = liga["codigo"]
    hoje = datetime.now(timezone.utc)
    ate  = hoje + timedelta(days=dias_frente)
    url = (f"https://api.football-data.org/v4/competitions/{codigo}/matches"
           f"?status=SCHEDULED&dateFrom={hoje.strftime('%Y-%m-%d')}&dateTo={ate.strftime('%Y-%m-%d')}")
    logger.info(f"Buscando jogos: {url}")
    try:
        resp = requests.get(url, headers=_headers_fdata(), timeout=10)
        if resp.status_code in (401, 403):
            logger.warning("FOOTBALL_DATA_KEY ausente/inválida — usando simulado")
            return _jogos_simulados(liga_key)
        if resp.status_code == 429:
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Erro: {e}")
        return _jogos_simulados(liga_key)
    jogos = []
    for m in data.get("matches", []):
        home = m.get("homeTeam",{}).get("shortName") or m.get("homeTeam",{}).get("name","?")
        away = m.get("awayTeam",{}).get("shortName") or m.get("awayTeam",{}).get("name","?")
        jogos.append({"id": str(m.get("id","")), "mandante": home, "visitante": away,
                      "data_utc": m.get("utcDate",""), "liga": liga["nome"], "liga_key": liga_key})
    return jogos

def _jogos_simulados(liga_key):
    base = {
        "brasileirao": [("Flamengo","Palmeiras"),("São Paulo","Corinthians"),
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
    hoje = datetime.now(timezone.utc)
    return [{"id": f"sim_{i}", "mandante": h, "visitante": a,
             "data_utc": (hoje + timedelta(days=i%7)).isoformat(),
             "liga": LIGAS.get(liga_key,{}).get("nome", liga_key),
             "liga_key": liga_key, "_simulado": True}
            for i, (h,a) in enumerate(pares)]

def _medias_padrao_liga(liga_key):
    defaults = {
        "brasileirao":  {"media_gols_casa":1.55,"media_gols_fora":1.10,"media_sofridos_casa":1.10,"media_sofridos_fora":1.55},
        "libertadores": {"media_gols_casa":1.45,"media_gols_fora":0.95,"media_sofridos_casa":0.95,"media_sofridos_fora":1.45},
        "champions":    {"media_gols_casa":1.80,"media_gols_fora":1.20,"media_sofridos_casa":1.20,"media_sofridos_fora":1.80},
        "premier":      {"media_gols_casa":1.75,"media_gols_fora":1.30,"media_sofridos_casa":1.30,"media_sofridos_fora":1.75},
        "la_liga":      {"media_gols_casa":1.65,"media_gols_fora":1.10,"media_sofridos_casa":1.10,"media_sofridos_fora":1.65},
        "serie_a_it":   {"media_gols_casa":1.50,"media_gols_fora":1.00,"media_sofridos_casa":1.00,"media_sofridos_fora":1.50},
        "bundesliga":   {"media_gols_casa":1.90,"media_gols_fora":1.35,"media_sofridos_casa":1.35,"media_sofridos_fora":1.90},
    }
    return defaults.get(liga_key, defaults["brasileirao"])

def analisar_jogo(jogo, media_gols_casa=1.5, media_gols_fora=1.1,
                  media_sofridos_casa=1.2, media_sofridos_fora=1.4):
    probs = calcular_probabilidades_poisson(media_gols_casa, media_gols_fora,
                                             media_sofridos_casa, media_sofridos_fora)
    classificacao = classificar_jogo(probs)
    resultado = resultado_mais_provavel(probs)
    vals = sorted([probs["p1"], probs["px"], probs["p2"]], reverse=True)
    confianca = round((vals[0] - vals[1]) * 100, 1)
    return {**jogo, "probabilidades": probs, "classificacao": classificacao,
            "resultado": resultado, "confianca": confianca, "odds": None, "metodo": "poisson_v1"}

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/ligas", methods=["GET"])
def listar_ligas():
    return jsonify({"ligas": [{"key":k,"nome":v["nome"],"pais":v["pais"]} for k,v in LIGAS.items()]})

@app.route("/api/jogos", methods=["GET"])
def listar_jogos():
    liga_key = request.args.get("liga", "brasileirao")
    dias = int(request.args.get("dias", 14))
    try:
        jogos = buscar_jogos_liga(liga_key, dias_frente=dias)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    return jsonify({"liga": LIGAS.get(liga_key,{}).get("nome",liga_key),
                    "total": len(jogos), "jogos": jogos,
                    "simulado": any(j.get("_simulado") for j in jogos)})

@app.route("/api/analisar", methods=["POST"])
def analisar_grade():
    body = request.get_json(silent=True) or {}
    jogos_input = body.get("jogos", [])
    if not jogos_input:
        return jsonify({"erro": "Envie ao menos 1 jogo"}), 400
    resultados = []
    for j in jogos_input:
        analise = analisar_jogo(j,
            float(j.get("media_gols_casa",1.50)), float(j.get("media_gols_fora",1.10)),
            float(j.get("media_sofridos_casa",1.20)), float(j.get("media_sofridos_fora",1.40)))
        resultados.append(analise)
    secos   = sum(1 for r in resultados if r["classificacao"]=="SECO")
    duplos  = sum(1 for r in resultados if r["classificacao"]=="DUPLO")
    triplos = sum(1 for r in resultados if r["classificacao"]=="TRIPLO")
    return jsonify({"total":len(resultados),"secos":secos,"duplos":duplos,"triplos":triplos,
                    "custo_estimado_reais": round(3.0*(2**duplos)*(3**triplos)/100,2),
                    "jogos":resultados})

@app.route("/api/grade-automatica", methods=["GET"])
def grade_automatica():
    liga_key  = request.args.get("liga", "brasileirao")
    dias      = int(request.args.get("dias", 14))
    max_jogos = int(request.args.get("max", 14))
    try:
        jogos_raw = buscar_jogos_liga(liga_key, dias_frente=dias)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    jogos_para_analisar = jogos_raw[:max_jogos]
    resultados = []
    for j in jogos_para_analisar:
        medias = _medias_padrao_liga(liga_key)
        resultados.append(analisar_jogo(j, **medias))
    secos   = sum(1 for r in resultados if r["classificacao"]=="SECO")
    duplos  = sum(1 for r in resultados if r["classificacao"]=="DUPLO")
    triplos = sum(1 for r in resultados if r["classificacao"]=="TRIPLO")
    return jsonify({"liga": LIGAS.get(liga_key,{}).get("nome",liga_key),
                    "total":len(resultados),"secos":secos,"duplos":duplos,"triplos":triplos,
                    "custo_estimado_reais": round(3.0*(2**duplos)*(3**triplos)/100,2),
                    "jogos":resultados,
                    "simulado": any(j.get("_simulado") for j in jogos_para_analisar)})

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"status":"online","versao":"2.0-camada1","ligas_suportadas":len(LIGAS),
                    "integracoes":{"football_data_org":"configurada" if FDATA_KEY else "ausente (simulado)",
                                   "the_odds_api":"configurada" if ODDS_KEY else "ausente"},
                    "proximas_camadas":["Camada 2: Poisson com histórico real","Camada 3: xG, Cartola, Smart Money"]})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV")=="development")
