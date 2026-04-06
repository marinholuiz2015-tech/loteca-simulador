#!/usr/bin/env python3
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from datetime import datetime
import math, os

try:
    import requests as req_lib
    HAS_REQUESTS = True
except:
    HAS_REQUESTS = False

app = Flask(__name__)
CORS(app)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "f551053977fdc954910af0b99e0ab8e3")
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/soccer_brazil_campeonato/odds/"

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
    frozenset(["Vasco","Botafogo"]),frozenset(["Sao Paulo","Corinthians"]),
    frozenset(["Sao Paulo","Palmeiras"]),frozenset(["Corinthians","Palmeiras"]),
    frozenset(["Internacional","Gremio"]),frozenset(["Cruzeiro","Atletico-MG"]),
    frozenset(["Bahia","Vitoria"]),frozenset(["Ceara","Fortaleza"]),
    frozenset(["Sport","Nautico"]),frozenset(["Athletico-PR","Coritiba"]),
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

def buscar_odds_reais():
    if not HAS_REQUESTS:
        return {}
    try:
        resp=req_lib.get(ODDS_API_URL,params={
            "apiKey":ODDS_API_KEY,"regions":"eu",
            "markets":"h2h","oddsFormat":"decimal"},timeout=10)
        if resp.status_code!=200:
            return {}
        odds_map={}
        for jogo in resp.json():
            home=jogo.get("home_team","")
            away=jogo.get("away_team","")
            o1_list=[];ox_list=[];o2_list=[]
            for bk in jogo.get("bookmakers",[]):
                for mkt in bk.get("markets",[]):
                    if mkt["key"]=="h2h":
                        out={o["name"]:o["price"] for o in mkt["outcomes"]}
                        if home in out and away in out:
                            o1_list.append(out[home])
                            o2_list.append(out[away])
                            if "Draw" in out:ox_list.append(out["Draw"])
            if o1_list and ox_list and o2_list:
                odds_map[f"{home}|{away}"]={
                    "odd1":round(sum(o1_list)/len(o1_list),2),
                    "oddx":round(sum(ox_list)/len(ox_list),2),
                    "odd2":round(sum(o2_list)/len(o2_list),2)}
        return odds_map
    except:
        return {}

def encontrar_odds(m,v,odds_map):
    mn=m.lower().strip();vn=v.lower().strip()
    for key,odds in odds_map.items():
        km,kv=key.split("|")
        if mn[:6] in km.lower() and vn[:6] in kv.lower():
            return odds
    return None

def analisar_jogo(jogo,odds_reais=None):
    pos=int(jogo.get("pos",1))
    m=jogo.get("mandante","")
    v=jogo.get("visitante","")
    freq=FREQ.get(pos,FREQ[7])
    o1=float(jogo.get("odd1",0))
    ox=float(jogo.get("oddx",0))
    o2=float(jogo.get("odd2",0))
    fonte="historico"
    if odds_reais and o1==0:
        od=encontrar_odds(m,v,odds_reais)
        if od:
            o1=od["odd1"];ox=od["oddx"];o2=od["odd2"];fonte="the-odds-api"
    if o1==0:o1=2.20
    if ox==0:ox=3.10
    if o2==0:o2=3.50
    p1o,pxo,p2o=odds_para_prob(o1,ox,o2)
    p1p,pxp,p2p=xg_para_prob()
    p1=p1o*0.40+freq["p1"]*0.35+p1p*0.25
    px=pxo*0.40+freq["px"]*0.35+pxp*0.25
    p2=p2o*0.40+freq["p2"]*0.35+p2p*0.25
    tot=p1+px+p2;p1=p1/tot*100;px=px/tot*100;p2=p2/tot*100
    maxp=max(p1,px,p2)
    sugestao="1" if p1==maxp else("X" if px==maxp else"2")
    sp=sorted([("1",p1),("X",px),("2",p2)],key=lambda x:-x[1])
    duplo=sp[0][0]+sp[1][0]
    tipo="SIMPLES" if maxp>=54 else("DUPLO" if sp[0][1]+sp[1][1]>=72 else"TRIPLO")
    return{"pos":pos,"mandante":m,"visitante":v,
           "p1":round(p1,1),"px":round(px,1),"p2":round(p2,1),
           "sugestao":sugestao,"duplo":duplo,"tipo":tipo,
           "confianca":round(maxp,1),"classico":is_classico(m,v),
           "odd1":o1,"oddx":ox,"odd2":o2,"fonte_odds":fonte}

@app.route("/")
def index():
    html_path=os.path.join(os.path.dirname(__file__),"index.html")
    if os.path.exists(html_path):
        return send_file(html_path)
    return jsonify({"status":"online","sistema":"Loteca Elite Pro","versao":"5.0"})

@app.route("/health")
def health():
    return jsonify({"status":"ok","ts":datetime.now().isoformat()})

@app.route("/historico")
def historico():
    return jsonify({"status":"ok","total_concursos":1241,"frequencias":FREQ})

@app.route("/odds-reais")
def odds_reais_endpoint():
    odds=buscar_odds_reais()
    return jsonify({"status":"ok","jogos":len(odds),"odds":odds,
                    "fonte":"the-odds-api","ts":datetime.now().isoformat()})

@app.route("/analisar",methods=["POST","GET"])
def analisar():
    jogos_in=request.json if request.is_json else[]
    odds_reais=buscar_odds_reais()
    if not jogos_in:
        jogos_in=[
            {"pos":1,"mandante":"Flamengo","visitante":"Palmeiras"},
            {"pos":2,"mandante":"Sao Paulo","visitante":"Internacional"},
            {"pos":3,"mandante":"Corinthians","visitante":"Gremio"},
            {"pos":4,"mandante":"Cruzeiro","visitante":"Fortaleza"},
            {"pos":5,"mandante":"Fluminense","visitante":"Santos"},
            {"pos":6,"mandante":"Athletico-PR","visitante":"Botafogo"},
            {"pos":7,"mandante":"Bahia","visitante":"Bragantino"},
            {"pos":8,"mandante":"Vasco","visitante":"Ceara"},
            {"pos":9,"mandante":"Sport","visitante":"Nautico"},
            {"pos":10,"mandante":"Coritiba","visitante":"Chapecoense"},
            {"pos":11,"mandante":"Paysandu","visitante":"Remo"},
            {"pos":12,"mandante":"Internacional","visitante":"Bahia"},
            {"pos":13,"mandante":"Palmeiras","visitante":"Mirassol"},
            {"pos":14,"mandante":"Flamengo","visitante":"Fluminense"},
        ]
    resultado=[analisar_jogo(j,odds_reais) for j in jogos_in[:14]]
    nd=sum(1 for r in resultado if r["tipo"]=="DUPLO")
    nt=sum(1 for r in resultado if r["tipo"]=="TRIPLO")
    odds_usadas=sum(1 for r in resultado if r["fonte_odds"]=="the-odds-api")
    return jsonify({"status":"ok","gerado_em":datetime.now().isoformat(),
                    "odds_reais_usadas":odds_usadas,"jogos":resultado,
                    "resumo":{"duplos":nd,"triplos":nt,
                    "custo_base":f"R$ {3*(2**nd)*(3**nt)}"}})

@app.route("/demo")
def demo():
    return analisar()

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
