"""
Loteca Elite Pro — app.py
Backend com integração real da The Odds API.
Suporta qualquer concurso, não só Copa do Mundo.
"""

import os
import math
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# ─── Concursos da Loteca (editável / expansível) ────────────────────────────
# Cada concurso define quais jogos fazem parte e em quais ligas buscá-los.
# Liga IDs válidos da The Odds API: soccer_brazil_campeonato, soccer_epl,
# soccer_spain_la_liga, soccer_italy_serie_a, soccer_germany_bundesliga,
# soccer_france_ligue_one, soccer_fifa_world_cup, soccer_conmebol_copa_america
# etc.  Consulte GET /sports para lista completa.

CONCURSOS = {
    1255: {
        "nome": "Copa Loteca — 1ª Rodada",
        "periodo": "11–15 jun 2026",
        "ligas": ["soccer_fifa_world_cup"],
        "jogos_fixos": [
            {"id": 1,  "mandante": "México",           "visitante": "África do Sul",   "data": "11/06", "hora": "16h"},
            {"id": 2,  "mandante": "Coreia do Sul",     "visitante": "Rep. Tcheca",     "data": "11/06", "hora": "23h"},
            {"id": 3,  "mandante": "Canadá",            "visitante": "Itália",          "data": "12/06", "hora": "16h"},
            {"id": 4,  "mandante": "Estados Unidos",    "visitante": "Paraguai",        "data": "12/06", "hora": "22h"},
            {"id": 5,  "mandante": "Austrália",         "visitante": "Turquia",         "data": "13/06", "hora": "01h"},
            {"id": 6,  "mandante": "Catar",             "visitante": "Suíça",           "data": "13/06", "hora": "16h"},
            {"id": 7,  "mandante": "Brasil",            "visitante": "Marrocos",        "data": "13/06", "hora": "19h"},
            {"id": 8,  "mandante": "Haiti",             "visitante": "Escócia",         "data": "13/06", "hora": "22h"},
            {"id": 9,  "mandante": "Alemanha",          "visitante": "Curaçao",         "data": "14/06", "hora": "14h"},
            {"id": 10, "mandante": "Holanda",           "visitante": "Japão",           "data": "14/06", "hora": "17h"},
            {"id": 11, "mandante": "Costa do Marfim",  "visitante": "Equador",         "data": "14/06", "hora": "20h"},
            {"id": 12, "mandante": "Espanha",           "visitante": "Cabo Verde",      "data": "15/06", "hora": "13h"},
            {"id": 13, "mandante": "Bélgica",           "visitante": "Egito",           "data": "15/06", "hora": "16h"},
            {"id": 14, "mandante": "Arábia Saudita",   "visitante": "Uruguai",         "data": "15/06", "hora": "19h"},
        ],
    },
    1256: {
        "nome": "Copa Loteca — 2ª Rodada",
        "periodo": "16–20 jun 2026",
        "ligas": ["soccer_fifa_world_cup"],
        "jogos_fixos": [],   # será preenchido quando os jogos forem divulgados
    },
    1257: {
        "nome": "Copa Loteca — 3ª Rodada",
        "periodo": "21–25 jun 2026",
        "ligas": ["soccer_fifa_world_cup"],
        "jogos_fixos": [],
    },
    1258: {
        "nome": "Copa Loteca — Oitavas",
        "periodo": "28 jun–2 jul 2026",
        "ligas": ["soccer_fifa_world_cup"],
        "jogos_fixos": [],
    },
}

# ─── Força de seleções (fallback quando Odds API não retorna o jogo) ─────────
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

# ─── Busca odds reais na The Odds API ────────────────────────────────────────

def _normalizar_nome(nome):
    """Normaliza nomes de times para comparação."""
    return nome.lower().strip()

def _odds_para_prob(o1, ox, o2):
    """Converte odds decimais para probabilidades implícitas (remove margem)."""
    p1 = 1 / o1
    px = 1 / ox
    p2 = 1 / o2
    total = p1 + px + p2
    return round(p1 / total, 4), round(px / total, 4), round(p2 / total, 4)

def buscar_odds_liga(liga_id):
    """Retorna lista de eventos com odds 1X2 da liga especificada."""
    if not ODDS_API_KEY:
        return []
    url = f"{ODDS_API_BASE}/sports/{liga_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        return []
    except Exception:
        return []

def encontrar_odds_jogo(eventos, mandante, visitante):
    """Tenta casar o jogo da Loteca com um evento da Odds API."""
    m = _normalizar_nome(mandante)
    v = _normalizar_nome(visitante)
    for ev in eventos:
        hm = _normalizar_nome(ev.get("home_team", ""))
        aw = _normalizar_nome(ev.get("away_team", ""))
        # match direto ou parcial
        if (m in hm or hm in m) and (v in aw or aw in v):
            # pega bookmaker com h2h
            for bm in ev.get("bookmakers", []):
                for mkt in bm.get("markets", []):
                    if mkt["key"] == "h2h":
                        outs = {o["name"]: o["price"] for o in mkt["outcomes"]}
                        h_name = ev["home_team"]
                        a_name = ev["away_team"]
                        o1 = outs.get(h_name, 0)
                        o2 = outs.get(a_name, 0)
                        # Draw
                        ox = next((outs[k] for k in outs if k not in [h_name, a_name]), 0)
                        if o1 and ox and o2:
                            return _odds_para_prob(o1, ox, o2), True
    return None, False

# ─── Cálculo de probabilidades (fallback) ───────────────────────────────────

def calcular_probs_fallback(mandante, visitante):
    f1 = FORCA.get(mandante, 6.0)
    f2 = FORCA.get(visitante, 6.0)
    diff = f1 - f2
    p1 = max(0.05, min(0.85, 0.33 + diff * 0.07))
    p2 = max(0.05, min(0.85, 0.33 - diff * 0.07))
    px = max(0.05, 1.0 - p1 - p2)
    soma = p1 + px + p2
    return round(p1/soma, 4), round(px/soma, 4), round(p2/soma, 4)

def classificar(p1, px, p2):
    maior = max(p1, px, p2)
    pares = [("1", p1), ("X", px), ("2", p2)]
    pares_ord = sorted(pares, key=lambda x: x[1], reverse=True)

    if maior >= 0.55:
        tipo = "SECO"
        coluna = pares_ord[0][0]
    elif maior >= 0.42:
        tipo = "DUPLO"
        coluna = f"{pares_ord[0][0]}/{pares_ord[1][0]}"
    else:
        tipo = "TRIPLO"
        coluna = "1/X/2"

    return {"tipo": tipo, "coluna": coluna, "confianca": round(maior * 100, 1)}

def gerar_paineis(jogos):
    """Calcula os 3 painéis de grade com custos reais."""
    nd_eco, nt_eco = 5, 0
    nd_rec, nt_rec = 7, 1
    nd_eli, nt_eli = 9, 2

    def custo(nd, nt, ns=0):
        return round((2**nd) * (3**nt) * 3.0, 2)

    def prob_13(nd, nt):
        base = 0.80 - nd * 0.025 - nt * 0.04
        return f"{round(max(base * 100, 0.5), 2)}%"

    def prob_14(nd, nt):
        base = 0.40 - nd * 0.025 - nt * 0.04
        return f"{round(max(base * 100, 0.01), 2)}%"

    return {
        "economica":    {"custo": custo(nd_eco, nt_eco), "prob_13": prob_13(nd_eco, nt_eco), "prob_14": prob_14(nd_eco, nt_eco), "duplos": nd_eco, "triplos": nt_eco},
        "recomendada":  {"custo": custo(nd_rec, nt_rec), "prob_13": prob_13(nd_rec, nt_rec), "prob_14": prob_14(nd_rec, nt_rec), "duplos": nd_rec, "triplos": nt_rec},
        "elite_pro":    {"custo": custo(nd_eli, nt_eli), "prob_13": prob_13(nd_eli, nt_eli), "prob_14": prob_14(nd_eli, nt_eli), "duplos": nd_eli, "triplos": nt_eli},
    }

def montar_concurso(num):
    dados = CONCURSOS.get(num)
    if not dados:
        return None

    # Busca odds de todas as ligas do concurso
    cache_eventos = {}
    for liga in dados.get("ligas", []):
        cache_eventos[liga] = buscar_odds_liga(liga)

    todos_eventos = []
    for evs in cache_eventos.values():
        todos_eventos.extend(evs)

    jogos_out = []
    for j in dados["jogos_fixos"]:
        probs_tuple, usou_api = encontrar_odds_jogo(todos_eventos, j["mandante"], j["visitante"])

        if probs_tuple:
            p1, px, p2 = probs_tuple
            fonte = "odds_api"
        else:
            p1, px, p2 = calcular_probs_fallback(j["mandante"], j["visitante"])
            fonte = "modelo_forca"

        clf = classificar(p1, px, p2)
        jogos_out.append({
            **j,
            "probs": {"1": p1, "X": px, "2": p2},
            "classificacao": clf,
            "fonte_odds": fonte,
        })

    return {
        "status": "sucesso",
        "concurso": num,
        "nome": dados["nome"],
        "periodo": dados["periodo"],
        "total_jogos": len(jogos_out),
        "jogos": jogos_out,
        "paineis": gerar_paineis(jogos_out),
        "odds_api_ativa": bool(ODDS_API_KEY),
    }

# ─── Rotas ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    from flask import send_file
    return send_file("index.html")

@app.route("/api/concursos")
def listar_concursos():
    return jsonify({
        "concursos": [
            {"num": k, "nome": v["nome"], "periodo": v["periodo"], "jogos": len(v["jogos_fixos"])}
            for k, v in sorted(CONCURSOS.items())
        ]
    })

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
    """Lista todas as ligas disponíveis na Odds API."""
    if not ODDS_API_KEY:
        return jsonify({"erro": "ODDS_API_KEY não configurada"}), 500
    url = f"{ODDS_API_BASE}/sports"
    r = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=10)
    return jsonify(r.json())

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "versao": "3.0-odds-api",
        "odds_api_configurada": bool(ODDS_API_KEY),
        "concursos_cadastrados": list(CONCURSOS.keys()),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
