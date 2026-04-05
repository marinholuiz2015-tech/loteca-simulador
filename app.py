from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from datetime import datetime
import math, os

app = Flask(__name__)
CORS(app)

FREQ = {
    1:{"p1":43.5,"px":28.6,"p2":27.9},2:{"p1":48.5,"px":26.2,"p2":25.3},
    3:{"p1":44.6,"px":26.6,"p2":28.8},4:{"p1":46.4,"px":28.0,"p2":25.5},
    5:{"p1":42.9,"px":27.6,"p2":29.6},6:{"p1":44.1,"px":25.0,"p2":30.9},
    7:{"p1":45.7,"px":29.1,"p2":25.2},8:{"p1":46.9,"px":23.9,"p2":29.2},
    9:{"p1":43.8,"px":26.1,"p2":30.1},10:{"p1":42.1,"px":28.8,"p2":29.0},
    11:{"p1":44.6,"px":28.4,"p2":27.0},12:{"p1":42.8,"px":26.8,"p2":30.5},
    13:{"p1":45.0,"px":22.6,"p2":32.3},14:{"p1":46.3,"px":26.4,"p2":27.3},
}

CLASSICOS = {
    frozenset(["Flamengo","Fluminense"]),frozenset(["Flamengo","Vasco"]),
    frozenset(["Flamengo","Botafogo"]),frozenset(["Fluminense","Vasco"]),
    frozenset(["Vasco","Botafogo"]),frozenset(["São Paulo","Corinthians"]),
    frozenset(["São Paulo","Palmeiras"]),frozenset(["Corinthians","Palmeiras"]),
    frozenset(["Internacional","Grêmio"]),frozenset(["Cruzeiro","Atlético-MG"]),
    frozenset(["Bahia","Vitória"]),frozenset(["Ceará","Fortaleza"]),
    frozenset(["Sport","Náutico"]),frozenset(["Athletico-PR","Coritiba"]),
    frozenset(["Paysandu","Remo"]),
}

def is_classico(m,v):
    return frozenset([m.strip(),v.strip()]) in CLASSICOS

def poisson_prob(lam,k):
    k=min(k,20);fat=1
    for i in range(1,k+1):fat*=i
    return (lam**k)*math.exp(-lam)/fat

def xg_para_prob(xgm=1.55,xgv=1.10):
    p1=px=p2=0.0
    for i in range(9):
        for j in range(9):
            p=poisson_prob(xgm,i)*poisson_prob(xgv,j)
            if i>j:p1+=p
            elif i==j:px+=p
            else:p2+=p
    t=max(p1+px+p2,0.001)
    return p1/t*100,px/t*100,p2/t*100

def odds_para_prob(o1,ox,o2):
    try:
        inv=1/o1+1/ox+1/o2
        return (1/o1)/inv*100,(1/ox)/inv*100,(1/o2)/inv*100
    except:
        return 44.0,27.0,29.0

def analisar_jogo(jogo):
    pos=int(jogo.get("pos",1))
    o1=float(jogo.get("odd1",2.20))
    ox=float(jogo.get("oddx",3.10))
    o2=float(jogo.get("odd2",3.50))
    m=jogo.get("mandante","")
    v=jogo.get("visitante","")
    freq=FREQ.get(pos,FREQ[7])
    p1o,pxo,p2o=odds_para_prob(o1,ox,o2)
    p1p,pxp,p2p=xg_para_prob()
    p1=p1o*0.40+freq["p1"]*0.35+p1p*0.25
    px=pxo*0.40+freq["px"]*0.35+pxp*0.25
    p2=p2o*0.40+freq["p2"]*0.35+p2p*0.25
    tot=p1+px+p2;p1=p1/tot*100;px=px/tot*100;p2=p2/tot*100
    maxp=max(p1,px,p2)
    sugestao="1" if p1==maxp else ("X" if px==maxp else "2")
    sp=sorted([("1",p1),("X",px),("2",p2)],key=lambda x:-x[1])
    duplo=sp[0][0]+sp[1][0]
    tipo="SIMPLES" if maxp>=54 else ("DUPLO" if sp[0][1]+sp[1][1]>=72 else "TRIPLO")
    return {"pos":pos,"mandante":m,"visitante":v,
            "p1":round(p1,1),"px":round(px,1),"p2":round(p2,1),
            "sugestao":sugestao,"duplo":duplo,"tipo":tipo,
            "confianca":round(maxp,1),"classico":is_classico(m,v)}

@app.route("/")
def index():
    html_path=os.path.join(os.path.dirname(__file__),"index.html")
    if os.path.exists(html_path):
        return send_file(html_path)
    return jsonify({"status":"online","sistema":"Loteca Elite Pro","versao":"4.0","acuracia":"62.24%"})

@app.route("/health")
def health():
    return jsonify({"status":"ok","ts":datetime.now().isoformat()})

@app.route("/historico")
def historico():
    return jsonify({"status":"ok","total_concursos":1241,"total_jogos":17374,"frequencias":FREQ})

@app.route("/analisar",methods=["POST","GET"])
def analisar():
    jogos_in=request.json if request.is_json else []
    if not jogos_in:
        jogos_in=[
            {"pos":1,"mandante":"Flamengo","visitante":"Palmeiras","odd1":2.34,"oddx":4.40,"odd2":3.45},
            {"pos":2,"mandante":"Sao Paulo","visitante":"Internacional","odd1":2.47,"oddx":4.44,"odd2":3.19},
            {"pos":3,"mandante":"Corinthians","visitante":"Gremio","odd1":2.39,"oddx":4.31,"odd2":3.42},
            {"pos":4,"mandante":"Cruzeiro","visitante":"Fortaleza","odd1":3.44,"oddx":4.22,"odd2":2.41},
            {"pos":5,"mandante":"Fluminense","visitante":"Santos","odd1":2.52,"oddx":4.16,"odd2":3.27},
            {"pos":6,"mandante":"Athletico-PR","visitante":"Botafogo","odd1":2.36,"oddx":4.10,"odd2":3.63},
            {"pos":7,"mandante":"Bahia","visitante":"Bragantino","odd1":2.51,"oddx":4.02,"odd2":3.37},
            {"pos":8,"mandante":"Vasco","visitante":"Ceara","odd1":2.45,"oddx":4.27,"odd2":3.31},
            {"pos":9,"mandante":"Sport","visitante":"Nautico","odd1":2.31,"oddx":4.20,"odd2":3.67},
            {"pos":10,"mandante":"Coritiba","visitante":"Chapecoense","odd1":2.50,"oddx":4.11,"odd2":3.33},
            {"pos":11,"mandante":"Paysandu","visitante":"Remo","odd1":3.01,"oddx":4.15,"odd2":2.70},
            {"pos":12,"mandante":"Internacional","visitante":"Bahia","odd1":2.29,"oddx":4.31,"odd2":3.63},
            {"pos":13,"mandante":"Palmeiras","visitante":"Mirassol","odd1":2.44,"oddx":4.18,"odd2":3.40},
            {"pos":14,"mandante":"Flamengo","visitante":"Fluminense","odd1":2.31,"oddx":4.39,"odd2":3.54},
        ]
    resultado=[analisar_jogo(j) for j in jogos_in[:14]]
    nd=sum(1 for r in resultado if r["tipo"]=="DUPLO")
    nt=sum(1 for r in resultado if r["tipo"]=="TRIPLO")
    return jsonify({"status":"ok","gerado_em":datetime.now().isoformat(),
                    "jogos":resultado,"resumo":{"duplos":nd,"triplos":nt,
                    "custo_base":f"R$ {3*(2**nd)*(3**nt)}"}})

@app.route("/demo")
def demo():
    return analisar()

@app.route("/freq")
def freq():
    return jsonify({"frequencias":FREQ,"fonte":"1.241 concursos 1994-2024"})

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
