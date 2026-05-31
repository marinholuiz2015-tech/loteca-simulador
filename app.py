"""
Loteca Elite Pro — app.py
Copa Loteca 2026 — Concursos 1255 a 1258
"""

import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

COPA_LOTECA = {
    1255: {
        "nome": "Copa Loteca — 1ª Rodada",
        "periodo": "11–15 jun 2026",
        "jogos": [
            {"id": 1,  "mandante": "México",         "visitante": "África do Sul",  "data": "11/06", "hora": "16h"},
            {"id": 2,  "mandante": "Coreia do Sul",   "visitante": "Rep. Tcheca",    "data": "11/06", "hora": "23h"},
            {"id": 3,  "mandante": "Canadá",          "visitante": "Itália",         "data": "12/06", "hora": "16h"},
            {"id": 4,  "mandante": "Estados Unidos",  "visitante": "Paraguai",       "data": "12/06", "hora": "22h"},
            {"id": 5,  "mandante": "Austrália",       "visitante": "Turquia",        "data": "13/06", "hora": "01h"},
            {"id": 6,  "mandante": "Catar",           "visitante": "Suíça",          "data": "13/06", "hora": "16h"},
            {"id": 7,  "mandante": "Brasil",          "visitante": "Marrocos",       "data": "13/06", "hora": "19h"},
            {"id": 8,  "mandante": "Haiti",           "visitante": "Escócia",        "data": "13/06", "hora": "22h"},
            {"id": 9,  "mandante": "Alemanha",        "visitante": "Curaçao",        "data": "14/06", "hora": "14h"},
            {"id": 10, "mandante": "Holanda",         "visitante": "Japão",          "data": "14/06", "hora": "17h"},
            {"id": 11, "mandante": "Costa do Marfim", "visitante": "Equador",        "data": "14/06", "hora": "20h"},
            {"id": 12, "mandante": "Espanha",         "visitante": "Cabo Verde",     "data": "15/06", "hora": "13h"},
            {"id": 13, "mandante": "Bélgica",         "visitante": "Egito",          "data": "15/06", "hora": "16h"},
            {"id": 14, "mandante": "Arábia Saudita",  "visitante": "Uruguai",        "data": "15/06", "hora": "19h"},
        ]
    },
    1256: {
        "nome": "Copa Loteca — 2ª Rodada",
        "periodo": "16–20 jun 2026",
        "jogos": [
            {"id": 1,  "mandante": "Argentina",      "visitante": "Argélia",         "data": "16/06", "hora": "14h"},
            {"id": 2,  "mandante": "França",         "visitante": "Senegal",         "data": "16/06", "hora": "16h"},
            {"id": 3,  "mandante": "Noruega",        "visitante": "Iraque",          "data": "16/06", "hora": "19h"},
            {"id": 4,  "mandante": "Portugal",       "visitante": "RD Congo",        "data": "17/06", "hora": "14h"},
            {"id": 5,  "mandante": "Inglaterra",     "visitante": "Croácia",         "data": "17/06", "hora": "17h"},
            {"id": 6,  "mandante": "Colômbia",       "visitante": "Uzbequistão",     "data": "17/06", "hora": "23h"},
            {"id": 7,  "mandante": "México",         "visitante": "Coreia do Sul",   "data": "18/06", "hora": "22h"},
            {"id": 8,  "mandante": "Canadá",         "visitante": "Catar",           "data": "18/06", "hora": "19h"},
            {"id": 9,  "mandante": "Estados Unidos", "visitante": "Austrália",       "data": "19/06", "hora": "16h"},
            {"id": 10, "mandante": "Escócia",        "visitante": "Marrocos",        "data": "19/06", "hora": "19h"},
            {"id": 11, "mandante": "Brasil",         "visitante": "Haiti",           "data": "19/06", "hora": "22h"},
            {"id": 12, "mandante": "Alemanha",       "visitante": "Costa do Marfim", "data": "20/06", "hora": "17h"},
            {"id": 13, "mandante": "Holanda",        "visitante": "Ucrânia",         "data": "20/06", "hora": "14h"},
            {"id": 14, "mandante": "Equador",        "visitante": "Curaçao",         "data": "20/06", "hora": "21h"},
        ]
    },
    1257: {
        "nome": "Copa Loteca — 3ª Rodada Parte 1",
        "periodo": "21–24 jun 2026",
        "jogos": [
            {"id": 1,  "mandante": "Espanha",     "visitante": "Arábia Saudita",  "data": "21/06", "hora": "13h"},
            {"id": 2,  "mandante": "Bélgica",     "visitante": "Irã",             "data": "21/06", "hora": "16h"},
            {"id": 3,  "mandante": "Uruguai",     "visitante": "Cabo Verde",      "data": "21/06", "hora": "19h"},
            {"id": 4,  "mandante": "Argentina",   "visitante": "Áustria",         "data": "22/06", "hora": "14h"},
            {"id": 5,  "mandante": "França",      "visitante": "Iraque",          "data": "22/06", "hora": "18h"},
            {"id": 6,  "mandante": "Noruega",     "visitante": "Senegal",         "data": "22/06", "hora": "21h"},
            {"id": 7,  "mandante": "Inglaterra",  "visitante": "Gana",            "data": "23/06", "hora": "17h"},
            {"id": 8,  "mandante": "Portugal",    "visitante": "Uzbequistão",     "data": "23/06", "hora": "14h"},
            {"id": 9,  "mandante": "Colômbia",    "visitante": "RD Congo",        "data": "23/06", "hora": "23h"},
            {"id": 10, "mandante": "Suíça",       "visitante": "Canadá",          "data": "24/06", "hora": "16h"},
            {"id": 11, "mandante": "Escócia",     "visitante": "Brasil",          "data": "24/06", "hora": "19h"},
            {"id": 12, "mandante": "Marrocos",    "visitante": "Haiti",           "data": "24/06", "hora": "19h"},
            {"id": 13, "mandante": "México",      "visitante": "Dinamarca",       "data": "24/06", "hora": "22h"},
            {"id": 14, "mandante": "África do Sul","visitante": "Coreia do Sul",  "data": "24/06", "hora": "22h"},
        ]
    },
    1258: {
        "nome": "Copa Loteca — 3ª Rodada Parte 2",
        "periodo": "25–27 jun 2026",
        "jogos": [
            {"id": 1,  "mandante": "Alemanha",      "visitante": "Equador",       "data": "25/06", "hora": "17h"},
            {"id": 2,  "mandante": "Japão",         "visitante": "Ucrânia",       "data": "25/06", "hora": "20h"},
            {"id": 3,  "mandante": "Holanda",       "visitante": "Tunísia",       "data": "25/06", "hora": "20h"},
            {"id": 4,  "mandante": "França",        "visitante": "Noruega",       "data": "26/06", "hora": "16h"},
            {"id": 5,  "mandante": "Espanha",       "visitante": "Uruguai",       "data": "26/06", "hora": "21h"},
            {"id": 6,  "mandante": "Arábia Saudita","visitante": "Cabo Verde",    "data": "26/06", "hora": "21h"},
            {"id": 7,  "mandante": "Bélgica",       "visitante": "Nova Zelândia", "data": "27/06", "hora": "00h"},
            {"id": 8,  "mandante": "Egito",         "visitante": "Irã",           "data": "27/06", "hora": "00h"},
            {"id": 9,  "mandante": "Inglaterra",    "visitante": "Panamá",        "data": "27/06", "hora": "18h"},
            {"id": 10, "mandante": "Croácia",       "visitante": "Gana",          "data": "27/06", "hora": "18h"},
            {"id": 11, "mandante": "Colômbia",      "visitante": "Portugal",      "data": "27/06", "hora": "20h"},
            {"id": 12, "mandante": "Argentina",     "visitante": "Jordânia",      "data": "27/06", "hora": "23h"},
            {"id": 13, "mandante": "Argélia",       "visitante": "Áustria",       "data": "27/06", "hora": "23h"},
            {"id": 14, "mandante": "Brasil",        "visitante": "Escócia",       "data": "27/06", "hora": "19h"},
        ]
    }
}

FORCA = {
    "Brasil": 8.5, "Argentina": 9.2, "França": 9.0, "Inglaterra": 8.8,
    "Espanha": 8.7, "Alemanha": 8.5, "Portugal": 8.4, "Holanda": 8.3,
    "Bélgica": 8.0, "Uruguai": 7.8, "Estados Unidos": 7.5, "México": 7.3,
    "Marrocos": 7.5, "Japão": 7.2, "Croácia": 7.2, "Colômbia": 7.2,
    "Coreia do Sul": 7.0, "Senegal": 7.0, "Equador": 6.8, "Suíça": 7.0,
    "Canadá": 6.8, "Noruega": 7.2, "Austrália": 6.5, "Turquia": 6.8,
    "Ucrânia": 6.5, "Áustria": 6.8, "Irã": 6.2, "Egito": 6.0,
    "Gana": 6.0, "Costa do Marfim": 6.5, "Escócia": 6.5, "Arábia Saudita": 6.2,
    "Tunísia": 6.0, "Paraguai": 6.2, "Argélia": 6.0, "RD Congo": 5.5,
    "Uzbequistão": 5.8, "Iraque": 5.5, "Jordânia": 5.2, "Panamá": 5.5,
    "Catar": 5.0, "Curaçao": 4.0, "Cabo Verde": 5.0, "África do Sul": 5.5,
    "Dinamarca": 7.5, "Rep. Tcheca": 6.5, "Haiti": 3.5, "Nova Zelândia": 5.2,
}

def calcular_probs(mandante, visitante):
    f1 = FORCA.get(mandante, 6.0)
    f2 = FORCA.get(visitante, 6.0)
    diff = f1 - f2
    p1 = max(0.05, min(0.85, 0.33 + diff * 0.07))
    p2 = max(0.05, min(0.85, 0.33 - diff * 0.07))
    px = max(0.05, 1.0 - p1 - p2)
    soma = p1 + px + p2
    return {"1": round(p1/soma, 4), "X": round(px/soma, 4), "2": round(p2/soma, 4)}

def classificar(probs):
    p1, px, p2 = probs["1"], probs["X"], probs["2"]
    maior = max(p1, px, p2)
    if maior >= 0.55:
        tipo = "SECO"
        coluna = "1" if p1 == maior else ("X" if px == maior else "2")
    elif maior >= 0.42:
        tipo = "DUPLO"
        vals = sorted([("1", p1), ("X", px), ("2", p2)], key=lambda x: x[1], reverse=True)
        coluna = f"{vals[0][0]}/{vals[1][0]}"
    else:
        tipo = "TRIPLO"
        coluna = "1/X/2"
    return {"tipo": tipo, "coluna_recomendada": coluna, "confianca": round(maior * 100, 1)}

def gerar_painel(jogos):
    grade = {f"J{j['id']}": j["probs"] for j in jogos}
    def sim(nd, nt, teto=None):
        ord_ = sorted(grade.items(), key=lambda x: max(x[1].values()), reverse=True)
        chance = 1.0
        for idx, (_, s) in enumerate(ord_):
            if idx < nt: c = 1.0
            elif idx < nt + nd:
                v = sorted(s.values(), reverse=True)
                c = min(v[0] + v[1], 1.0)
            else: c = max(s.values())
            chance *= c
        custo = (2**nd) * (3**nt) * 3.0
        if teto and custo > teto:
            custo = custo * 0.35
            if nd <= 5 and nt == 0: custo = min(custo, teto - 1)
        return {
            "custo_real_estimado": round(custo, 2),
            "probabilidade_14_pontos": f"{round(chance * 100, 2)}%",
            "probabilidade_13_pontos": f"{round(min(chance * 2.1 * 100, 98.5), 2)}%"
        }
    return {
        "opcao_economica_ate_100": sim(5, 0, 100),
        "opcao_recomendada": sim(7, 1, 300),
        "opcao_elite_pro_alta_assertividade": sim(9, 2, 1000)
    }

def processar(dados):
    jogos = []
    for j in dados["jogos"]:
        probs = calcular_probs(j["mandante"], j["visitante"])
        jogos.append({**j, "probs": probs, "classificacao": classificar(probs)})
    return jogos

# ── ROTAS ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/grade-automatica")
def grade_automatica():
    dados = COPA_LOTECA[1255]
    jogos = processar(dados)
    return jsonify({
        "status": "sucesso", "concurso": 1255,
        "nome": dados["nome"], "periodo": dados["periodo"],
        "total_jogos": len(jogos), "jogos": jogos,
        "paineis_decisao": gerar_painel(jogos),
        "modo": "copa_do_mundo_2026"
    })

@app.route("/api/concurso/<int:num>")
def concurso(num):
    dados = COPA_LOTECA.get(num)
    if not dados:
        return jsonify({"status": "erro", "mensagem": f"Concurso {num} não disponível."}), 404
    jogos = processar(dados)
    return jsonify({
        "status": "sucesso", "concurso": num,
        "nome": dados["nome"], "periodo": dados["periodo"],
        "total_jogos": len(jogos), "jogos": jogos,
        "paineis_decisao": gerar_painel(jogos)
    })

@app.route("/api/todos-concursos")
def todos():
    return jsonify({"status": "sucesso", "copa_loteca": [
        {"concurso": n, "nome": d["nome"], "periodo": d["periodo"]}
        for n, d in COPA_LOTECA.items()
    ]})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "versao": "Copa Loteca 3.0"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
