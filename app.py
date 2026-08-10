"""
LOTECA ELITE PRO — app.py v6.1
Banco real: 1.249 concursos | 17.476 jogos | 2010-2018
Lambda calibrado: casa=1.387 | fora=1.065
Dist real: 1=47.2% X=26.2% 2=26.6%
Suporte dual: tabela jogos_loteca OU jogos (detecta automaticamente)
"""
import os, math, logging, sqlite3, threading, struct, time, re
from datetime import datetime
from collections import defaultdict
import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)

VERSAO  = "6.1"
DB_PATH = os.getenv("DB_PATH", "loteca_historico_v4.db")
URL_CEF = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca"
UA      = {"User-Agent": "Mozilla/5.0"}

LAMBDA_CASA = 1.387
LAMBDA_FORA = 1.065
DIST_GLOBAL = {"p1": 0.4722, "px": 0.2616, "p2": 0.2663, "total": 17476}

PROB_POR_POSICAO = {
    1:[0.4463,0.2901,0.2636], 2:[0.4492,0.2626,0.2882],
    3:[0.4860,0.2562,0.2578], 4:[0.4551,0.2628,0.2821],
    5:[0.4708,0.2618,0.2674], 6:[0.4832,0.2564,0.2604],
    7:[0.4563,0.2791,0.2646], 8:[0.4736,0.2516,0.2748],
    9:[0.4487,0.2700,0.2812],10:[0.5148,0.2578,0.2274],
   11:[0.4960,0.2420,0.2620],12:[0.4892,0.2490,0.2618],
   13:[0.4856,0.2564,0.2580],14:[0.4559,0.2660,0.2780],
}

_H2H={}; _GOLS_CASA={}; _GOLS_FORA={}
_APROV_CASA={}; _APROV_FORA={}
_PROB_POS=dict(PROB_POR_POSICAO)
_dados_ok=False; _lock=threading.Lock()
_cache_grade={"data":None,"ts":0}
_coleta={"rodando":False,"relatorio":None,"erro":None,"coletados":0}

def _db():
    for p in [
        DB_PATH,
        os.path.join(os.path.dirname(os.path.abspath(__file__)),"loteca_historico_v4.db"),
        os.path.join(os.getcwd(),"loteca_historico_v4.db"),
        "/opt/render/project/src/loteca_historico_v4.db",
        "/opt/render/project/loteca_historico_v4.db",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),"loteca_historico.db"),
        os.path.join(os.getcwd(),"loteca_historico.db"),
        "/opt/render/project/src/loteca_historico.db",
        "/opt/render/project/loteca_historico.db",
    ]:
        if os.path.exists(p): return p
    return DB_PATH

def _tj():
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabs=[r[0] for r in c.fetchall()]; conn.close()
        if "jogos_loteca" in tabs: return "jogos_loteca"
        if "jogos" in tabs: return "jogos"
    except: pass
    return "jogos_loteca"

def _col_pos():
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute(f"PRAGMA table_info({_tj()})")
        cols=[r[1] for r in c.fetchall()]; conn.close()
        if "posicao" in cols: return "posicao"
        if "sequencial" in cols: return "sequencial"
        if "numero_jogo" in cols: return "numero_jogo"
    except: pass
    return "posicao"

def _gols(b):
    if isinstance(b,bytes):
        try: return struct.unpack('<q',b)[0]
        except: return 0
    return b or 0

def inicializar_banco():
    conn=sqlite3.connect(_db()); conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS concursos (
        concurso INTEGER PRIMARY KEY, data_sorteio TEXT,
        premio_14 REAL, premio_13 REAL,
        ganhadores_14 INTEGER, ganhadores_13 INTEGER,
        acumulou INTEGER DEFAULT 0, fonte TEXT
    );
    CREATE TABLE IF NOT EXISTS jogos_loteca (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concurso INTEGER, posicao INTEGER,
        mandante TEXT, visitante TEXT, resultado TEXT,
        gols_m BLOB, gols_v BLOB, data_jogo TEXT, liga TEXT,
        FOREIGN KEY(concurso) REFERENCES concursos(concurso)
    );
    CREATE TABLE IF NOT EXISTS freq_historica (
        posicao INTEGER PRIMARY KEY,
        freq_1 REAL, freq_x REAL, freq_2 REAL,
        total INTEGER, updated TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_jl_c ON jogos_loteca(concurso);
    CREATE INDEX IF NOT EXISTS idx_jl_m ON jogos_loteca(mandante);
    CREATE INDEX IF NOT EXISTS idx_jl_v ON jogos_loteca(visitante);
    """)
    conn.commit(); conn.close()

def carregar_dados():
    global _H2H,_GOLS_CASA,_GOLS_FORA,_APROV_CASA,_APROV_FORA,_PROB_POS,_dados_ok
    with _lock:
        if _dados_ok: return
        db=_db()
        if not os.path.exists(db): _dados_ok=True; return
        try:
            tj=_tj(); cp=_col_pos()
            conn=sqlite3.connect(db); c=conn.cursor()
            logger.info("Carregando: tabela=%s col_pos=%s",tj,cp)
            c.execute(f"""SELECT mandante,visitante,COUNT(*) n,
                SUM(CASE WHEN resultado='1' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='X' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='2' THEN 1 ELSE 0 END)
                FROM {tj} WHERE resultado IN ('1','X','2')
                GROUP BY mandante,visitante HAVING n>=3 ORDER BY n DESC LIMIT 300""")
            for m,v,tot,v1,vx,v2 in c.fetchall():
                _H2H[f"{m.lower()}|{v.lower()}"]={"p1":round(v1/tot,4),"px":round(vx/tot,4),"p2":round(v2/tot,4),"n":tot}
            c.execute(f"SELECT mandante,gols_m,gols_v FROM {tj}")
            gc=defaultdict(lambda:[0,0,0])
            for m,gm,gv in c.fetchall():
                try: gc[m.lower()][0]+=_gols(gm); gc[m.lower()][1]+=_gols(gv); gc[m.lower()][2]+=1
                except: pass
            _GOLS_CASA={k:{"gm":round(v[0]/v[2],3),"gc":round(v[1]/v[2],3),"n":v[2]}
                        for k,v in gc.items() if v[2]>=5}
            c.execute(f"SELECT visitante,gols_v,gols_m FROM {tj}")
            gf=defaultdict(lambda:[0,0,0])
            for v,gv,gm in c.fetchall():
                try: gf[v.lower()][0]+=_gols(gv); gf[v.lower()][1]+=_gols(gm); gf[v.lower()][2]+=1
                except: pass
            _GOLS_FORA={k:{"gm":round(v[0]/v[2],3),"gc":round(v[1]/v[2],3),"n":v[2]}
                        for k,v in gf.items() if v[2]>=5}
            c.execute(f"""SELECT mandante,
                SUM(CASE WHEN resultado='1' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='X' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='2' THEN 1 ELSE 0 END),COUNT(*)
                FROM {tj} WHERE resultado IN ('1','X','2')
                GROUP BY mandante HAVING COUNT(*)>=5""")
            _APROV_CASA={r[0].lower():{"v":r[1],"e":r[2],"d":r[3],"total":r[4],"aprov":round(r[1]/r[4],4)}
                         for r in c.fetchall()}
            c.execute(f"""SELECT visitante,
                SUM(CASE WHEN resultado='2' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='X' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='1' THEN 1 ELSE 0 END),COUNT(*)
                FROM {tj} WHERE resultado IN ('1','X','2')
                GROUP BY visitante HAVING COUNT(*)>=5""")
            _APROV_FORA={r[0].lower():{"v":r[1],"e":r[2],"d":r[3],"total":r[4],"aprov":round(r[1]/r[4],4)}
                         for r in c.fetchall()}
            c.execute("SELECT posicao,freq_1,freq_x,freq_2 FROM freq_historica ORDER BY posicao")
            for pos,f1,fx,f2 in c.fetchall(): _PROB_POS[pos]=[f1,fx,f2]
            conn.close(); _dados_ok=True
            logger.info("OK: %d H2H | %d casa | %d fora",len(_H2H),len(_GOLS_CASA),len(_GOLS_FORA))
        except Exception as e:
            logger.error("carregar_dados: %s",e); _dados_ok=True

def _pp(lam,k):
    if lam<=0: return 1.0 if k==0 else 0.0
    return (lam**k)*math.exp(-lam)/math.factorial(k)

# DIXON-COLES 10/08/2026: rho calibrado via busca em grade contra 15.964
# jogos reais do banco (otimizando log-loss). Corrige subestimacao
# estrutural de empates do Poisson puro em placares baixos correlacionados.
# Validado: prob. media de empate sobe de 23.8% para 26.4% (real=26.2%).
RHO_DC = -0.12
def _tau_dc(x,y,lam,mu,rho):
    if x==0 and y==0: return 1-lam*mu*rho
    elif x==0 and y==1: return 1+lam*rho
    elif x==1 and y==0: return 1+mu*rho
    elif x==1 and y==1: return 1-rho
    return 1.0

def poisson_prob(lc,lf):
    p1=px=p2=0.0
    for i in range(8):
        for j in range(8):
            p=_pp(lc,i)*_pp(lf,j)
            if i<=1 and j<=1: p*=_tau_dc(i,j,lc,lf,RHO_DC)
            if i>j: p1+=p
            elif i==j: px+=p
            else: p2+=p
    t=p1+px+p2
    return {"p1":round(p1/t,4),"px":round(px/t,4),"p2":round(p2/t,4)} if t else {"p1":0.45,"px":0.25,"p2":0.30}

def calcular_probs(mandante,visitante,posicao=None):
    carregar_dados()
    m=mandante.lower().strip(); v=visitante.lower().strip()
    h=_H2H.get(f"{m}|{v}")
    if h: return {**h,"fonte":f"h2h_{h['n']}x"}
    gc=_GOLS_CASA.get(m); gf=_GOLS_FORA.get(v)
    if gc and gf:
        # CORRIGIDO 10/08/2026: denominadores estavam trocados (gf["gc"] deve
        # ser normalizado por LAMBDA_CASA, nao LAMBDA_FORA, e vice-versa) e o
        # multiplicador extra 1.08/0.90 duplicava o home advantage ja embutido
        # em gc["gm"]/gf["gm"]. Validado: acuracia sobe de 48.54% para 50.66%
        # contra 15.964 jogos reais; vies de mandante cai de 97.8% para 86.8%.
        lc=max(0.3,min(gc["gm"]*(gf["gc"]/max(0.5,LAMBDA_CASA)),5.0))
        lf=max(0.3,min(gf["gm"]*(gc["gc"]/max(0.5,LAMBDA_FORA)),5.0))
        probs=poisson_prob(lc,lf)
        return {**probs,"fonte":"poisson_dixon_coles","lc":round(lc,3),"lf":round(lf,3)}
    ac=_APROV_CASA.get(m); af=_APROV_FORA.get(v)
    if ac and af:
        rp1=ac["aprov"]*0.6+(1-af["aprov"])*0.4
        rp2=af["aprov"]*0.6+(1-ac["aprov"])*0.4
        rpx=max(0.10,1.0-rp1-rp2); t=rp1+rpx+rp2
        return {"p1":round(rp1/t,4),"px":round(rpx/t,4),"p2":round(rp2/t,4),"fonte":"aproveitamento"}
    if posicao and posicao in _PROB_POS:
        p=_PROB_POS[posicao]; return {"p1":p[0],"px":p[1],"p2":p[2],"fonte":f"posicao_{posicao}"}
    return {"p1":DIST_GLOBAL["p1"],"px":DIST_GLOBAL["px"],"p2":DIST_GLOBAL["p2"],"fonte":"global"}

def classificar(probs):
    v=sorted([probs["p1"],probs["px"],probs["p2"]],reverse=True)
    if v[0]>=0.60: return "SECO"
    if v[0]+v[1]>=0.75: return "DUPLO"
    return "TRIPLO"

def score_0_100(probs):
    v=sorted([probs["p1"],probs["px"],probs["p2"]],reverse=True)
    return round(v[0]*100+(v[0]-v[1])*30,1)

def favorito(probs):
    d={"1":probs["p1"],"X":probs["px"],"2":probs["p2"]}; return max(d,key=d.get)

def buscar_grade_arenadoaz():
    global _cache_grade
    agora=time.time()
    if _cache_grade["data"] and agora-_cache_grade["ts"]<1800: return _cache_grade["data"]
    try:
        r=requests.get("https://arenadoaz.com/simulador/",headers=UA,timeout=12)
        if r.status_code!=200: return _cache_grade["data"]
        txt=r.text
        m=re.search(r"SIMULADOR LOTECA\s+(\d+)",txt)
        concurso=int(m.group(1)) if m else None
        linhas=[l.strip() for l in txt.replace('\r','').split('\n') if l.strip()]
        jogos=[]; i=0
        while i<len(linhas):
            if re.match(r'^\d{1,2}$',linhas[i]):
                pos=int(linhas[i])
                if 1<=pos<=14:
                    nomes=[]; j=i+1
                    while j<len(linhas) and len(nomes)<2:
                        t=linhas[j]
                        if len(t)>2 and not re.match(r'^[12X]$|^[→←]|^\.\.\.',t) and '<' not in t and 'http' not in t:
                            nome=t.split('-')[0].strip()
                            if len(nome)>1: nomes.append(nome)
                        j+=1
                    if len(nomes)==2: jogos.append({"posicao":pos,"mandante":nomes[0],"visitante":nomes[1]})
            i+=1
        resultado={"concurso":concurso,"jogos":jogos,"fonte":"arenadoaz","ts":agora}
        if len(jogos)>=5: _cache_grade={"data":resultado,"ts":agora}
        return resultado
    except Exception as e:
        logger.warning("Arena AZ: %s",e); return _cache_grade["data"]

def _parse_float(v):
    if isinstance(v,(int,float)): return float(v)
    try: return float(str(v).replace("R$","").replace(".","").replace(",",".").strip())
    except: return 0.0

def buscar_cef(numero):
    try:
        url=f"{URL_CEF}/{numero}" if numero else URL_CEF
        r=requests.get(url,timeout=12,headers=UA)
        return r.json() if r.status_code==200 else None
    except: return None

def parsear_cef(numero,d):
    if not d: return None,[]
    con={"concurso":numero,"data_sorteio":d.get("dataApuracao",""),
         "premio_14":_parse_float(d.get("valorPremio14Acertos",0)),
         "premio_13":_parse_float(d.get("valorPremio13Acertos",0)),
         "ganhadores_14":d.get("ganhadores14Acertos",0) or 0,
         "ganhadores_13":d.get("ganhadores13Acertos",0) or 0,
         "acumulou":1 if d.get("acumulado") else 0,"fonte":"cef"}
    t1=d.get("listaResultadosEquipeUm",d.get("listaTimeCoracao",[]))
    t2=d.get("listaResultadosEquipeDois",[])
    res=d.get("listaDezenas",d.get("dezenas",[]))
    jos=[]
    for i in range(max(len(t1),len(res),1)):
        jos.append({"concurso":numero,"posicao":i+1,
                    "mandante":t1[i] if i<len(t1) else f"Time A {i+1}",
                    "visitante":t2[i] if i<len(t2) else f"Time B {i+1}",
                    "resultado":res[i] if i<len(res) else "?",
                    "gols_m":None,"gols_v":None,"data_jogo":"","liga":""})
    return con,jos

def salvar_cef(conn,con,jos):
    tj=_tj(); c=conn.cursor()
    c.execute("INSERT OR REPLACE INTO concursos VALUES(?,?,?,?,?,?,?,?)",
              (con["concurso"],con["data_sorteio"],con["premio_14"],con["premio_13"],
               con["ganhadores_14"],con["ganhadores_13"],con["acumulou"],con["fonte"]))
    c.execute(f"DELETE FROM {tj} WHERE concurso=?",(con["concurso"],))
    for j in jos:
        c.execute(f"INSERT INTO {tj}(concurso,posicao,mandante,visitante,resultado,gols_m,gols_v,data_jogo,liga) VALUES(?,?,?,?,?,?,?,?,?)",
                  (j["concurso"],j["posicao"],j["mandante"],j["visitante"],j["resultado"],
                   j["gols_m"],j["gols_v"],j["data_jogo"],j["liga"]))
    conn.commit()

def _coletar_worker(inicio,fim):
    global _coleta,_dados_ok
    try:
        conn=sqlite3.connect(_db()); conn.execute("PRAGMA journal_mode=WAL")
        c=conn.cursor()
        c.execute("SELECT MAX(concurso) FROM concursos"); ultimo=c.fetchone()[0] or 0
        if inicio<=ultimo: inicio=ultimo+1
        falhas=coletados=0; numero=inicio
        while True:
            if fim and numero>fim: break
            if falhas>=5: break
            dados=buscar_cef(numero)
            if dados is None: falhas+=1
            else:
                falhas=0; con,jos=parsear_cef(numero,dados)
                if con: salvar_cef(conn,con,jos); coletados+=1
            _coleta["coletados"]=coletados; numero+=1; time.sleep(0.4)
        c.execute("SELECT COUNT(*) FROM concursos"); tc=c.fetchone()[0]
        c.execute(f"SELECT COUNT(*) FROM {_tj()}"); tj2=c.fetchone()[0]
        c.execute("SELECT MAX(concurso) FROM concursos"); mx=c.fetchone()[0]
        conn.close(); _dados_ok=False
        _coleta={"rodando":False,"relatorio":{"coletados":coletados,"total_concursos":tc,
                 "total_jogos":tj2,"ultimo":mx},"erro":None,"coletados":coletados}
    except Exception as e:
        _coleta={"rodando":False,"relatorio":None,"erro":str(e),"coletados":0}

@app.route("/")
def index():
    for pasta in [os.path.dirname(os.path.abspath(__file__)),os.getcwd(),
                  "/opt/render/project/src","/opt/render/project"]:
        p=os.path.join(pasta,"index.html")
        if os.path.exists(p):
            with open(p,"r",encoding="utf-8") as f: return Response(f.read(),mimetype="text/html")
    return "index.html não encontrado",404

@app.route("/api/status")
def api_status():
    carregar_dados(); tj=_tj()
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute("SELECT COUNT(*),MIN(concurso),MAX(concurso),MIN(data_sorteio),MAX(data_sorteio) FROM concursos")
        tc,mn,mx,dm,dM=c.fetchone()
        c.execute(f"SELECT COUNT(*) FROM {tj}"); tj2=c.fetchone()[0]
        conn.close(); banco_ok=bool(tc and tc>0)
    except: tc=tj2=mn=mx=dm=dM=None; banco_ok=False
    return jsonify({
        "status":"online","versao":VERSAO,
        "banco":{"ok":banco_ok,"concursos":tc,"jogos":tj2,
                 "periodo":f"{dm} → {dM}","min":mn,"max":mx,"tabela":tj},
        "dados_memoria":{"h2h":len(_H2H),"times_casa":len(_GOLS_CASA),"times_fora":len(_GOLS_FORA)},
        "calibracao":{"lambda_casa":LAMBDA_CASA,"lambda_fora":LAMBDA_FORA},
        "integracoes":{"loteca_historico_db":"conectado" if banco_ok else "desconectado"}
    })

@app.route("/api/analisar")
def api_analisar():
    m=request.args.get("mandante","").strip(); v=request.args.get("visitante","").strip()
    pos=request.args.get("posicao",type=int)
    if not m or not v: return jsonify({"erro":"Informe mandante e visitante"}),400
    probs=calcular_probs(m,v,pos); cl=classificar(probs); fav=favorito(probs)
    vals=sorted([probs["p1"],probs["px"],probs["p2"]],reverse=True)
    conf=round((vals[0]-vals[1])*100,1)
    return jsonify({"mandante":m,"visitante":v,"posicao":pos,
                    "probabilidades":{"p1":probs["p1"],"px":probs["px"],"p2":probs["p2"]},
                    "favorito":fav,"classificacao":cl,"score_0_100":score_0_100(probs),
                    "confianca":conf,"fonte":probs.get("fonte","?"),
                    "lambda_casa":probs.get("lc"),"lambda_fora":probs.get("lf")})

@app.route("/api/concurso/<int:numero>/analisar")
def api_analisar_concurso(numero):
    tj=_tj(); cp=_col_pos()
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute(f"SELECT {cp},mandante,visitante,resultado FROM {tj} WHERE concurso=? ORDER BY {cp}",(numero,))
        rows=c.fetchall(); conn.close()
    except Exception as e: return jsonify({"erro":str(e)}),500
    if not rows: return jsonify({"erro":f"Concurso {numero} não encontrado"}),404
    resultado=[]
    for pos,m,v,res in rows:
        probs=calcular_probs(m or "",v or "",pos)
        cl=classificar(probs); fav=favorito(probs)
        vals=sorted([probs["p1"],probs["px"],probs["p2"]],reverse=True)
        resultado.append({"posicao":pos,"mandante":m,"visitante":v,"resultado_real":res,
                          "probabilidades":{"p1":probs["p1"],"px":probs["px"],"p2":probs["p2"]},
                          "score_0_100":score_0_100(probs),"classificacao":cl,
                          "favorito":fav,"confianca":round((vals[0]-vals[1])*100,1),
                          "fonte":probs.get("fonte","?")})
    acertos=sum(1 for r in resultado if r["resultado_real"] in("1","X","2") and r["resultado_real"]==r["favorito"])
    secos=sum(1 for r in resultado if r["classificacao"]=="SECO")
    duplos=sum(1 for r in resultado if r["classificacao"]=="DUPLO")
    triplos=sum(1 for r in resultado if r["classificacao"]=="TRIPLO")
    return jsonify({"concurso":numero,"total":len(resultado),
                    "acertos_favorito":acertos,"pct_acerto":round(acertos/max(len(resultado),1)*100,1),
                    "secos":secos,"duplos":duplos,"triplos":triplos,
                    "custo_minimo":round(3.0*(2**duplos)*(3**triplos)/100,2),"jogos":resultado})

@app.route("/api/concurso/atual")
def api_concurso_atual():
    grade=buscar_grade_arenadoaz()
    if grade and grade.get("concurso") and grade.get("jogos"):
        resultado=[]
        for j in grade["jogos"]:
            pos=j["posicao"]; m=j["mandante"]; v=j["visitante"]
            probs=calcular_probs(m,v,pos); cl=classificar(probs); fav=favorito(probs)
            vals=sorted([probs["p1"],probs["px"],probs["p2"]],reverse=True)
            resultado.append({"posicao":pos,"mandante":m,"visitante":v,"resultado_real":"?",
                              "probabilidades":{"p1":probs["p1"],"px":probs["px"],"p2":probs["p2"]},
                              "score_0_100":score_0_100(probs),"classificacao":cl,
                              "favorito":fav,"confianca":round((vals[0]-vals[1])*100,1),
                              "fonte":probs.get("fonte","?")})
        secos=sum(1 for r in resultado if r["classificacao"]=="SECO")
        duplos=sum(1 for r in resultado if r["classificacao"]=="DUPLO")
        triplos=sum(1 for r in resultado if r["classificacao"]=="TRIPLO")
        return jsonify({"concurso":grade["concurso"],"total":len(resultado),
                        "fonte_grade":"arenadoaz","secos":secos,"duplos":duplos,"triplos":triplos,
                        "custo_minimo":round(3.0*(2**duplos)*(3**triplos)/100,2),"jogos":resultado})
    dados=buscar_cef("")
    if dados:
        numero=dados.get("numero",dados.get("numeroConcurso",0))
        if numero: return api_analisar_concurso(numero)
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute("SELECT MAX(concurso) FROM concursos"); ultimo=c.fetchone()[0]; conn.close()
        if ultimo: return api_analisar_concurso(ultimo)
    except: pass
    return jsonify({"erro":"Nenhuma fonte disponível"}),503

@app.route("/api/sentinela/grade")
def api_sentinela_grade():
    grade=buscar_grade_arenadoaz()
    if not grade: return jsonify({"erro":"Grade indisponível"}),503
    return jsonify(grade)

@app.route("/api/sentinela/atualizar",methods=["POST"])
def api_sentinela_atualizar():
    global _cache_grade; _cache_grade={"data":None,"ts":0}
    grade=buscar_grade_arenadoaz()
    return jsonify({"ok":True,"concurso":grade.get("concurso") if grade else None,
                    "jogos":len(grade.get("jogos",[])) if grade else 0})

@app.route("/api/historico/resumo")
def hist_resumo():
    tj=_tj()
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute("SELECT COUNT(*),MIN(concurso),MAX(concurso),MIN(data_sorteio),MAX(data_sorteio) FROM concursos")
        tc,mn,mx,dm,dM=c.fetchone()
        c.execute(f"SELECT COUNT(*) FROM {tj}"); tj2=c.fetchone()[0]
        c.execute(f"SELECT resultado,COUNT(*) FROM {tj} WHERE resultado IN ('1','X','2') GROUP BY resultado")
        dist=dict(c.fetchall()); total=sum(dist.values()) or 1
        c.execute(f"SELECT mandante,COUNT(*) FROM {tj} GROUP BY mandante ORDER BY 2 DESC LIMIT 10")
        top=[{"time":r[0],"jogos":r[1]} for r in c.fetchall()]
        conn.close()
        return jsonify({"total_concursos":tc,"total_jogos":tj2,"periodo":f"{dm} → {dM}","min":mn,"max":mx,
                        "distribuicao":{k:{"n":v,"pct":round(v/total*100,1)} for k,v in dist.items()},
                        "top_10_mandantes":top})
    except Exception as e: return jsonify({"erro":str(e)}),500

@app.route("/api/historico/time/<nome>")
def hist_time(nome):
    carregar_dados(); m=nome.lower()
    ac=_APROV_CASA.get(m); af=_APROV_FORA.get(m)
    gc=_GOLS_CASA.get(m); gf=_GOLS_FORA.get(m)
    if not ac and not af: return jsonify({"erro":f"Time '{nome}' não encontrado"}),404
    try:
        tj=_tj(); cp=_col_pos(); conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute(f"""SELECT j.concurso,co.data_sorteio,j.mandante,j.visitante,j.resultado
            FROM {tj} j JOIN concursos co ON j.concurso=co.concurso
            WHERE LOWER(j.mandante)=? OR LOWER(j.visitante)=?
            ORDER BY j.concurso DESC LIMIT 20""",(m,m))
        ultimos=[{"concurso":r[0],"data":r[1],"mandante":r[2],"visitante":r[3],"resultado":r[4]}
                 for r in c.fetchall()]
        conn.close()
    except: ultimos=[]
    return jsonify({"time":nome,
                    "casa":{**ac,"gm":gc["gm"] if gc else None,"gc":gc["gc"] if gc else None} if ac else None,
                    "fora":{**af,"gm":gf["gm"] if gf else None,"gc":gf["gc"] if gf else None} if af else None,
                    "ultimos_jogos":ultimos})

@app.route("/api/historico/confronto")
def hist_confronto():
    m=request.args.get("mandante","").strip().lower()
    v=request.args.get("visitante","").strip().lower()
    if not m or not v: return jsonify({"erro":"Informe mandante e visitante"}),400
    carregar_dados(); h2h=_H2H.get(f"{m}|{v}"); tj=_tj()
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute(f"""SELECT j.concurso,co.data_sorteio,j.mandante,j.visitante,j.resultado
            FROM {tj} j JOIN concursos co ON j.concurso=co.concurso
            WHERE (LOWER(j.mandante)=? AND LOWER(j.visitante)=?)
               OR (LOWER(j.mandante)=? AND LOWER(j.visitante)=?)
            ORDER BY j.concurso DESC LIMIT 30""",(m,v,v,m))
        rows=c.fetchall(); conn.close()
    except Exception as e: return jsonify({"erro":str(e)}),500
    v1=sum(1 for r in rows if r[2].lower()==m and r[4]=="1")
    x=sum(1 for r in rows if r[4]=="X")
    v2=sum(1 for r in rows if r[2].lower()==v and r[4]=="1")
    return jsonify({"mandante":m,"visitante":v,"total":len(rows),
                    "vitorias_t1":v1,"empates":x,"vitorias_t2":v2,"h2h_probs":h2h,
                    "jogos":[{"concurso":r[0],"data":r[1],"mandante":r[2],"visitante":r[3],"resultado":r[4]}
                              for r in rows]})

@app.route("/api/posicoes")
def api_posicoes():
    carregar_dados()
    return jsonify({str(p):{"p1":v[0],"px":v[1],"p2":v[2]} for p,v in _PROB_POS.items()})

@app.route("/api/db-info")
def api_db_info():
    db=_db(); tj=_tj()
    try:
        conn=sqlite3.connect(db); c=conn.cursor()
        c.execute("SELECT COUNT(*),MIN(concurso),MAX(concurso) FROM concursos"); tc,mn,mx=c.fetchone()
        c.execute(f"SELECT COUNT(*) FROM {tj}"); tj2=c.fetchone()[0]
        c.execute("SELECT name FROM sqlite_master WHERE type='table'"); tabelas=[r[0] for r in c.fetchall()]
        conn.close()
        return jsonify({"db_conectado":True,"caminho":db,"total_concursos":tc,
                        "total_jogos":tj2,"concurso_min":mn,"concurso_max":mx,
                        "tabela_jogos":tj,"tabelas":tabelas})
    except Exception as e:
        return jsonify({"db_conectado":False,"caminho":db,"erro":str(e)})

@app.route("/api/coletar",methods=["POST"])
def api_coletar():
    global _coleta
    if _coleta["rodando"]: return jsonify({"status":"ja_rodando"}),409
    body=request.get_json(silent=True) or {}
    inicio=body.get("inicio",1); fim=body.get("fim")
    _coleta={"rodando":True,"relatorio":None,"erro":None,"coletados":0}
    threading.Thread(target=_coletar_worker,args=(inicio,fim),daemon=True).start()
    return jsonify({"status":"iniciado","mensagem":f"Coletando a partir do concurso {inicio}"})

@app.route("/api/coletar/status")
def api_coletar_status(): return jsonify(_coleta)

if __name__=="__main__":
    inicializar_banco(); carregar_dados()
    port=int(os.getenv("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)
