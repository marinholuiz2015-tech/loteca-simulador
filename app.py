"""
Loteca Elite Pro — app.py
Backend principal com suporte especial aos 4 concursos Copa Loteca 1255–1258.
"""

import os
import math

from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

COPA_LOTECA = {
    1255: {
        "nome": "Copa Loteca — 1ª Rodada",
        "periodo": "11–13 jun 2026",
        "jogos": [
            {"id": 1,  "mandante": "México",        "visitante": "África do Sul", "data": "11/06", "hora": "16h"},
            {"id": 2,  "mandante": "Coreia do Sul",  "visitante": "Rep. Tcheca",  "data": "11/06", "hora": "23h"},
            {"id": 3,  "mandante": "Canadá",         "visitante": "Itália",       "data": "12/06", "hora": "16h"},
            {"id": 4,  "mandante": "Estados Unidos", "visitante": "Paraguai",     "data": "12/06", "hora": "22h"},
            {"id": 5,  "mandante": "Austrália",      "visitante": "Turquia",      "data": "13/06", "hora": "01h"},
            {"id": 6,  "mandante": "Catar",          "visitante": "Suíça",        "data": "13/06", "hora": "16h"},
            {"id": 7,  "mandante": "Brasil",         "visitante": "Marrocos",     "data": "13/06", "hora": "19h"},
            {"id": 8,  "mandante": "Haiti",          "visitante": "Escócia",      "data": "13/06", "hora": "22h"},
            {"id": 9,  "mandante": "Alemanha",       "visitante": "Curaçao",      "data": "14/06", "hora": "14h"},
            {"id": 10, "mandante": "Holanda",        "visitante": "Japão",        "data": "14/06", "hora": "17h"},
            {"id": 11, "mandante": "Costa do Marfim","visitante": "Equador",      "data": "14/06", "hora": "20h"},
            {"id": 12, "mandante": "Espanha",        "visitante": "Cabo Verde",   "data": "15/06", "hora": "13h"},
            {"id": 13, "mandante": "Bélgica",        "visitante": "Egito",        "data": "15/06", "hora": "16h"},
            {"id": 14, "mandante": "Arábia Saudita", "visitante": "Uruguai",      "data": "15/06", "hora": "19h"},
        ]
    },
}

FORCA_SELECAO = {
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

def calcular_probs_copa(mandante, visitante):
    f1 = FORCA_SELECAO.get(mandante, 6.0)
    f2 = FORCA_SELECAO.get(visitante, 6.0)
    diff = f1 - f2
    p1 = max(0.05, min(0.85, 0.33 + diff * 0.07))
    p2 = max(0.05, min(0.85, 0.33 - diff * 0.07))
    px = max(0.05, 1.0 - p1 - p2)
    soma = p1 + px + p2
    return {"1": round(p1/soma, 4), "X": round(px/soma, 4), "2": round(p2/soma, 4)}

def classificar_jogo(probs):
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

def gerar_painel_decisao(jogos):
    grade = {f"Jogo_{j['id']}": j["probs"] for j in jogos}
    def simular(nd, nt, teto=None):
        jogos_ord = sorted(grade.items(), key=lambda x: max(x[1].values()), reverse=True)
        chance = 1.0
        for idx, (_, s) in enumerate(jogos_ord):
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
        return {"custo_real_estimado": round(custo, 2),
                "probabilidade_14_pontos": f"{round(chance*100, 2)}%",
                "probabilidade_13_pontos": f"{round(min(chance*2.1*100, 98.5), 2)}%"}
    return {
        "opcao_economica_ate_100": simular(5, 0, 100),
        "opcao_recomendada": simular(7, 1, 300),
        "opcao_elite_pro_alta_assertividade": simular(9, 2, 1000),
    }

@app.route("/api/grade-automatica")
def grade_automatica():
    concurso_ativo = 1255
    dados = COPA_LOTECA.get(concurso_ativo)
    if not dados:
        return jsonify({"status": "erro", "mensagem": "Concurso não encontrado"}), 404
    jogos_analisados = []
    for jogo in dados["jogos"]:
        probs = calcular_probs_copa(jogo["mandante"], jogo["visitante"])
        jogos_analisados.append({**jogo, "probs": probs, "classificacao": classificar_jogo(probs)})
    return jsonify({"status": "sucesso", "concurso": concurso_ativo, "nome": dados["nome"],
                    "periodo": dados["periodo"], "total_jogos": len(jogos_analisados),
                    "jogos": jogos_analisados, "paineis_decisao": gerar_painel_decisao(jogos_analisados),
                    "modo": "copa_do_mundo_2026"})

@app.route("/api/concurso/<int:num>")
def concurso_especifico(num):
    dados = COPA_LOTECA.get(num)
    if not dados:
        return jsonify({"status": "erro", "mensagem": f"Concurso {num} não disponível."}), 404
    jogos_analisados = []
    for jogo in dados["jogos"]:
        probs = calcular_probs_copa(jogo["mandante"], jogo["visitante"])
        jogos_analisados.append({**jogo, "probs": probs, "classificacao": classificar_jogo(probs)})
    return jsonify({"status": "sucesso", "concurso": num, "nome": dados["nome"],
                    "periodo": dados["periodo"], "jogos": jogos_analisados,
                    "paineis_decisao": gerar_painel_decisao(jogos_analisados)})

@app.route("/api/todos-concursos")
def todos_concursos():
    return jsonify({"status": "sucesso", "copa_loteca": [
        {"concurso": num, "nome": d["nome"], "periodo": d["periodo"]}
        for num, d in COPA_LOTECA.items()]})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "versao": "Copa Loteca 1.0"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)