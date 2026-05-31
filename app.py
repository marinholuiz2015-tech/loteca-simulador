"""
Loteca Elite Pro — app.py
Backend com integração real da The Odds API.
Suporta qualquer concurso, não só Copa do Mundo.
"""

import os
import math
import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

CONCURSOS = {
    1255: {
        "nome": "Copa Loteca — 1ª Rodada",
        "periodo": "11–15 jun 2026",
        "ligas": ["soccer_fifa_world_cup"],
        "jogos_fixos": [
            {"id": 1,  "mandante": "México",          "visitante": "África do Sul",  "data": "11/06", "hora": "16h"},
            {"id": 2,  "mandante": "Coreia do Sul",    "visitante": "Rep. Tcheca",    "data": "11/06", "hora": "23h"},
            {"id": 3,  "mandante": "Canadá",           "visitante": "Itália",         "data": "12/06", "hora": "16h"},
            {"id": 4,  "mandante": "Estados Unidos",   "visitante": "Paraguai",       "data": "12/06", "hora": "22h"},
            {"id": 5,  "mandante": "Austrália",        "visitante": "Turquia",        "data": "13/06", "hora": "01h"},
            {"id": 6,  "mandante": "Catar",            "visitante": "Suíça",          "data": "13/06", "hora": "16h"},
            {"id": 7,  "mandante": "Brasil",           "visitante": "Marrocos",       "data": "13/06", "hora": "19h"},
            {"id": 8,  "mandante": "Haiti",            "visitante": "Escócia",        "data": "13/06", "hora": "22h"},
            {"id": 9,  "mandante": "Alemanha",         "visitante": "Curaçao",        "data": "14/06", "hora": "14h"},
            {"id": 10, "mandante": "Holanda",          "visitante": "Japão",          "data": "14/06", "hora": "17h"},
            {"id": 11, "mandante": "Costa do Marfim", "visitante": "Equador",        "data": "14/06", "hora": "20h"},
            {"id": 12, "mandante": "Espanha",          "visitante": "Cabo Verde",     "data": "15/06", "hora": "13h"},
            {"id": 13, "mandante": "Bélgica",          "visitante": "Egito",          "data": "15/06", "hora": "16h"},
            {"id": 14, "mandante": "Arábia Saudita",  "visitante": "Uruguai",        "data": "15/06", "hora": "19h"},
        ],
    },
    1256: {"nome": "Copa Loteca — 2ª Rodada", "periodo": "16–20 jun 2026", "ligas": ["soccer_fifa_world_cup"], "jogos_fixos": []},
    1257: {"nome": "Copa Loteca — 3ª Rodada", "periodo": "21–25 jun 2026", "ligas": ["soccer_fifa_world_cup"], "jogos_fixos": []},
    1258: {"nome": "Copa Loteca — Oitavas",   "periodo": "28 jun–2 jul 2026", "ligas": ["soccer_fifa_world_cup"], "jogos_fixos": []},
}

FORCA = {
    "Brasil": 8.5, "Argentina": 9.2, "França": 9.0, "Inglaterra": 8.8,
    "Espanha": 8.7, "Alemanha": 8.5, "Portugal": 8.4, "Holanda": 8.3,
    "Bélgica": 8.0, "Uruguai": 7.8, "Estados Unidos": 7.5, "México": 7.3,
    "Marrocos": 7.5, "Japão": 7.2, "Coreia do Sul": 7.0, "Equador": 6.8,
    "Suíça": 7.0, "Canadá": 6.8, "Austrália": 6.5, "Turquia": 6.8,
    "Escócia": 6.5, "Arábia Saudita": 6.2, "Paraguai": 6.2,
    "Catar": 5.0, "Curaçao": 4.0, "Cabo Verde": 5.0, "África do Sul": 5.5,
    "Rep. Tcheca": 6.5, "Haiti": 3.5, "Itália": 8.2, "Egito": 6.0,
    "Costa do Marfim": 6.5,
}

def _normalizar(nome):
    return nome.lower().strip()

def _odds_para_prob(o1, ox, o2):
    p1, px, p2 = 1/o1, 1/ox, 1/o2
    t = p1 + px + p2
    return round(p1/t, 4), round(px/t, 4), round(p2/t, 4)

def buscar_odds_liga(liga_id):
    if not ODDS_API_KEY:
        return []
    try:
        r = requests.get(f"{ODDS_API_BASE}/sports/{liga_id}/odds",
            params={"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"},
            timeout=10)
        return r.json() if r.status_code == 200 else []
    except:
        return []

def encontrar_odds_jogo(eventos, mandante, visitante):
    m, v = _normalizar(mandante), _normalizar(visitante)
    for ev in eventos:
        hm = _normalizar(ev.get("home_team", ""))
        aw = _normalizar(ev.get("away_team", ""))
        if (m in hm or hm in m) and (v in aw or aw in v):
            for bm in ev.get("bookmakers", []):
                for mkt in bm.get("markets", []):
                    if mkt["key"] == "h2h":
                        outs = {o["name"]: o["price"] for o in mkt["outcomes"]}
                        o1 = outs.get(ev["home_team"], 0)
                        o2 = outs.get(ev["away_team"], 0)
                        ox = next((outs[k] for k in outs if k not in [ev["home_team"], ev["away_team"]]), 0)
                        if o1 and ox and o2:
                            return _odds_para_prob(o1, ox, o2), True
    return None, False

def calcular_probs_fallback(mandante, visitante):
    f1 = FORCA.get(mandante, 6.0)
    f2 = FORCA.get(visitante, 6.0)
    diff = f1 - f2
    p1 = max(0.05, min(0.85, 0.33 + diff * 0.07))
    p2 = max(0.05, min(0.85, 0.33 - diff * 0.07))
    px = max(0.05, 1.0 - p1 - p2)
    s = p1 + px + p2
    return round(p1/s, 4), round(px/s, 4), round(p2/s, 4)

def classificar(p1, px, p2):
    maior = max(p1, px, p2)
    pares = sorted([("1",p1),("X",px),("2",p2)], key=lambda x: x[1], reverse=True)
    if maior >= 0.55:
        return {"tipo": "SECO",   "coluna": pares[0][0], "confianca": round(maior*100,1)}
    elif maior >= 0.42:
        return {"tipo": "DUPLO",  "coluna": f"{pares[0][0]}/{pares[1][0]}", "confianca": round(maior*100,1)}
    else:
        return {"tipo": "TRIPLO", "coluna": "1/X/2", "confianca": round(maior*100,1)}

def gerar_paineis(jogos):
    def painel(nd, nt):
        return {
            "custo": round((2**nd) * (3**nt) * 3.0, 2),
            "prob_13": f"{round(max((0.80 - nd*0.025 - nt*0.04)*100, 0.5), 2)}%",
            "prob_14": f"{round(max((0.40 - nd*0.025 - nt*0.04)*100, 0.01), 2)}%",
            "duplos": nd, "triplos": nt
        }
    return {"economica": painel(5,0), "recomendada": painel(7,1), "elite_pro": painel(9,2)}

def montar_concurso(num):
    dados = CONCURSOS.get(num)
    if not dados:
        return None
    todos_eventos = []
    for liga in dados.get("ligas", []):
        todos_eventos.extend(buscar_odds_liga(liga))
    jogos_out = []
    for j in dados["jogos_fixos"]:
        probs_tuple, usou_api = encontrar_odds_jogo(todos_eventos, j["mandante"], j["visitante"])
        if probs_tuple:
            p1, px, p2 = probs_tuple
            fonte = "odds_api"
        else:
            p1, px, p2 = calcular_probs_fallback(j["mandante"], j["visitante"])
            fonte = "modelo_forca"
        jogos_out.append({**j, "probs": {"1": p1, "X": px, "2": p2},
            "classificacao": classificar(p1, px, p2), "fonte_odds": fonte})
    return {"status": "sucesso", "concurso": num, "nome": dados["nome"],
        "periodo": dados["periodo"], "total_jogos": len(jogos_out),
        "jogos": jogos_out, "paineis": gerar_paineis(jogos_out),
        "odds_api_ativa": bool(ODDS_API_KEY)}

@app.route("/")
def index():
    html = open("index.html", encoding="utf-8").read()
    return Response(html, mimetype="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.route("/api/concursos")
def listar_concursos():
    return jsonify({"concursos": [
        {"num": k, "nome": v["nome"], "periodo": v["periodo"], "jogos": len(v["jogos_fixos"])}
        for k, v in sorted(CONCURSOS.items())
    ]})

@app.route("/api/concurso/<int:num>")
def concurso(num):
    dados = montar_concurso(num)
    if not dados:
        return jsonify({"status": "erro", "mensagem": f"Concurso {num} não cadastrado"}), 404
    return jsonify(dados)

@app.route("/api/grade-automatica")
def grade_automatica():
    num = int(request.args.get("concurso", 1255))
    dados = montar_concurso(num)
    if not dados:
        return jsonify({"status": "erro", "mensagem": f"Concurso {num} não encontrado"}), 404
    return jsonify(dados)

@app.route("/api/sports")
def listar_sports():
    if not ODDS_API_KEY:
        return jsonify({"erro": "ODDS_API_KEY não configurada"}), 500
    r = requests.get(f"{ODDS_API_BASE}/sports", params={"apiKey": ODDS_API_KEY}, timeout=10)
    return jsonify(r.json())

@app.route("/health")
def health():
    return jsonify({"status": "ok", "versao": "3.0",
        "odds_api_configurada": bool(ODDS_API_KEY),
        "concursos_cadastrados": list(CONCURSOS.keys())})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
