from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

FREQ_HISTORICA = {
    1:  {"p1": 47.2, "px": 27.8, "p2": 25.0},
    2:  {"p1": 46.5, "px": 28.1, "p2": 25.4},
    3:  {"p1": 45.8, "px": 28.6, "p2": 25.6},
    4:  {"p1": 45.1, "px": 29.2, "p2": 25.7},
    5:  {"p1": 44.3, "px": 29.8, "p2": 25.9},
    6:  {"p1": 43.6, "px": 30.4, "p2": 26.0},
    7:  {"p1": 43.9, "px": 29.6, "p2": 26.5},
    8:  {"p1": 42.1, "px": 31.2, "p2": 26.7},
    9:  {"p1": 43.4, "px": 30.1, "p2": 26.5},
    10: {"p1": 44.7, "px": 29.3, "p2": 26.0},
    11: {"p1": 45.3, "px": 28.7, "p2": 26.0},
    12: {"p1": 46.1, "px": 28.2, "p2": 25.7},
    13: {"p1": 46.8, "px": 27.6, "p2": 25.6},
    14: {"p1": 47.5, "px": 27.1, "p2": 25.4},
}

@app.route("/")
def index():
    return jsonify({"status": "online", "sistema": "Loteca Simulador Elite", "versao": "1.0"})

@app.route("/historico")
def historico():
    return jsonify({"status": "ok", "total_concursos": 1241, "frequencias": FREQ_HISTORICA})

@app.route("/analisar", methods=["POST", "GET"])
def analisar():
    jogos = request.json if request.is_json else []
    if not jogos:
        jogos = [{"pos": i, "mandante": f"Time {i*2-1}", "visitante": f"Time {i*2}", "odd1": 2.20, "oddx": 3.10, "odd2": 3.50} for i in range(1, 15)]
    resultado = []
    for jogo in jogos:
        pos = jogo.get("pos", 1)
        hist = FREQ_HISTORICA.get(pos, FREQ_HISTORICA[7])
        try:
            o1, ox, o2 = jogo.get("odd1", 2.20), jogo.get("oddx", 3.10), jogo.get("odd2", 3.50)
            t = (1/o1) + (1/ox) + (1/o2)
            p1 = ((1/o1)/t*100*0.6) + (hist["p1"]*0.4)
            px = ((1/ox)/t*100*0.6) + (hist["px"]*0.4)
            p2 = ((1/o2)/t*100*0.6) + (hist["p2"]*0.4)
        except:
            p1, px, p2 = hist["p1"], hist["px"], hist["p2"]
        sugestao = max({"1": p1, "X": px, "2": p2}, key=lambda k: {"1": p1, "X": px, "2": p2}[k])
        tipo = "SIMPLES" if max(p1,px,p2) >= 55 else "DUPLO" if max(p1,px,p2) >= 45 else "TRIPLO"
        resultado.append({"pos": pos, "mandante": jogo.get("mandante",""), "visitante": jogo.get("visitante",""), "p1": round(p1,1), "px": round(px,1), "p2": round(p2,1), "sugestao": sugestao, "tipo": tipo})
    return jsonify({"status": "ok", "gerado_em": datetime.now().isoformat(), "jogos": resultado})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
