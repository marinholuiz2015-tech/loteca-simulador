"""
LOTECA ELITE PRO — app.py v4.1
Calibrado com banco real: 17.374 jogos, 1.241 concursos (1994-2024)
Suporte universal: clubes + seleções + qualquer campeonato da grade Loteca
"""
import os, math, logging, sqlite3, threading, struct, time
from datetime import datetime
from collections import defaultdict
import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)

DB_PATH = os.getenv("DB_PATH", "loteca_historico_v4.db")
URL_CEF = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca"

# ═══════════════════════════════════════════════════════════
# DADOS CALIBRADOS COM BANCO REAL (17.374 jogos, 1.241 concursos)
# ═══════════════════════════════════════════════════════════

LAMBDA_CASA = 1.3527
LAMBDA_FORA = 1.0768
DIST_GLOBAL = {"p1": 0.4480, "px": 0.2672, "p2": 0.2848, "total": 17374}

PROB_POR_POSICAO = {
    1:  [0.4351, 0.2861, 0.2788],
    2:  [0.4851, 0.2619, 0.2530],
    3:  [0.4456, 0.2659, 0.2885],
    4:  [0.4641, 0.2804, 0.2554],
    5:  [0.4287, 0.2756, 0.2957],
    6:  [0.4408, 0.2498, 0.3094],
    7:  [0.4569, 0.2909, 0.2522],
    8:  [0.4690, 0.2393, 0.2917],
    9:  [0.4376, 0.2611, 0.3014],
    10: [0.4214, 0.2885, 0.2901],
    11: [0.4464, 0.2836, 0.2699],
    12: [0.4279, 0.2675, 0.3046],
    13: [0.4504, 0.2264, 0.3231],
    14: [0.4633, 0.2635, 0.2732],
}

# ═══════════════════════════════════════════════════════════
# DADOS EM MEMÓRIA (carregados do banco)
# ═══════════════════════════════════════════════════════════
_H2H        = {}
_GOLS_CASA  = {}
_GOLS_FORA  = {}
_APROV_CASA = {}
_APROV_FORA = {}
_PROB_POS   = dict(PROB_POR_POSICAO)
_dados_ok   = False
_lock       = threading.Lock()

def _db():
    for p in [DB_PATH,
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "loteca_historico_v4.db"),
              os.path.join(os.getcwd(), "loteca_historico_v4.db"),
              "/opt/render/project/src/loteca_historico_v4.db",
              "/opt/render/project/loteca_historico_v4.db"]:
        if os.path.exists(p): return p
    return DB_PATH

def _gols(b):
    if isinstance(b, bytes): return struct.unpack('<q', b)[0]
    return b or 0

def carregar_dados():
    global _H2H, _GOLS_CASA, _GOLS_FORA, _APROV_CASA, _APROV_FORA, _PROB_POS, _dados_ok
    with _lock:
        if _dados_ok: return
        db = _db()
        if not os.path.exists(db):
            logger.warning("Banco não encontrado: %s", db)
            _dados_ok = True
            return
        try:
            conn = sqlite3.connect(db)
            c = conn.cursor()

            # H2H
            c.execute("""SELECT mandante, visitante, COUNT(*) n,
                SUM(CASE WHEN resultado='1' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='X' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='2' THEN 1 ELSE 0 END)
                FROM jogos_loteca WHERE resultado IN ('1','X','2')
                GROUP BY mandante, visitante HAVING n >= 3
                ORDER BY n DESC LIMIT 300""")
            for m,v,tot,v1,vx,v2 in c.fetchall():
                _H2H[f"{m}|{v}"] = {"p1":round(v1/tot,4),"px":round(vx/tot,4),"p2":round(v2/tot,4),"n":tot}

            # Gols por time
            c.execute('SELECT mandante, gols_m, gols_v FROM jogos_loteca')
            gc = defaultdict(lambda:[0,0,0])
            for m,gm,gv in c.fetchall():
                try: gc[m][0]+=_gols(gm); gc[m][1]+=_gols(gv); gc[m][2]+=1
                except: pass
            _GOLS_CASA = {k:{"gm":round(v[0]/v[2],3),"gc":round(v[1]/v[2],3),"n":v[2]}
                          for k,v in gc.items() if v[2]>=5}

            c.execute('SELECT visitante, gols_v, gols_m FROM jogos_loteca')
            gf = defaultdict(lambda:[0,0,0])
            for v,gv,gm in c.fetchall():
                try: gf[v][0]+=_gols(gv); gf[v][1]+=_gols(gm); gf[v][2]+=1
                except: pass
            _GOLS_FORA = {k:{"gm":round(v[0]/v[2],3),"gc":round(v[1]/v[2],3),"n":v[2]}
                          for k,v in gf.items() if v[2]>=5}

            # Aproveitamento
            c.execute("""SELECT mandante,
                SUM(CASE WHEN resultado='1' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='X' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='2' THEN 1 ELSE 0 END), COUNT(*)
                FROM jogos_loteca WHERE resultado IN ('1','X','2')
                GROUP BY mandante HAVING COUNT(*)>=5""")
            _APROV_CASA = {r[0]:{"v":r[1],"e":r[2],"d":r[3],"total":r[4],"aprov":round(r[1]/r[4],4)}
                           for r in c.fetchall()}

            c.execute("""SELECT visitante,
                SUM(CASE WHEN resultado='2' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='X' THEN 1 ELSE 0 END),
                SUM(CASE WHEN resultado='1' THEN 1 ELSE 0 END), COUNT(*)
                FROM jogos_loteca WHERE resultado IN ('1','X','2')
                GROUP BY visitante HAVING COUNT(*)>=5""")
            _APROV_FORA = {r[0]:{"v":r[1],"e":r[2],"d":r[3],"total":r[4],"aprov":round(r[1]/r[4],4)}
                           for r in c.fetchall()}

            # Prob por posição do banco
            c.execute('SELECT posicao, freq_1, freq_x, freq_2 FROM freq_historica ORDER BY posicao')
            for pos,f1,fx,f2 in c.fetchall():
                _PROB_POS[pos] = [f1, fx, f2]

            conn.close()
            _dados_ok = True
            logger.info("Dados carregados: %d H2H, %d times casa, %d times fora",
                        len(_H2H), len(_GOLS_CASA), len(_GOLS_FORA))
        except Exception as e:
            logger.error("Erro ao carregar dados: %s", e)
            _dados_ok = True

# ═══════════════════════════════════════════════════════════
# MOTOR POISSON
# ═══════════════════════════════════════════════════════════

def _pp(lam, k):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam**k) * math.exp(-lam) / math.factorial(k)

def poisson_prob(lc, lf, mg=7):
    p1 = px = p2 = 0.0
    for i in range(mg+1):
        for j in range(mg+1):
            p = _pp(lc,i) * _pp(lf,j)
            if i>j: p1+=p
            elif i==j: px+=p
            else: p2+=p
    t = p1+px+p2
    if t == 0: return {"p1":0.45,"px":0.25,"p2":0.30}
    return {"p1":round(p1/t,4),"px":round(px/t,4),"p2":round(p2/t,4)}

def calcular_probs(mandante, visitante, posicao=None):
    """
    Hierarquia: H2H → Poisson gols reais → Aproveitamento → Posição → Global
    Funciona para clubes E seleções.
    """
    carregar_dados()
    m = mandante.lower().strip()
    v = visitante.lower().strip()

    # 1. H2H direto
    h = _H2H.get(f"{m}|{v}")
    if h: return {**h, "fonte": f"h2h_{h['n']}x"}

    # 2. Poisson com gols reais
    gc = _GOLS_CASA.get(m)
    gf = _GOLS_FORA.get(v)
    if gc and gf:
        lc = max(0.3, min(gc["gm"] * (gf["gc"] / max(0.5, LAMBDA_FORA)) * 1.08, 5.0))
        lf = max(0.3, min(gf["gm"] * (gc["gc"] / max(0.5, LAMBDA_CASA)) * 0.90, 5.0))
        probs = poisson_prob(lc, lf)
        return {**probs, "fonte": "poisson_real", "lc": round(lc,3), "lf": round(lf,3)}

    # 3. Aproveitamento histórico
    ac = _APROV_CASA.get(m)
    af = _APROV_FORA.get(v)
    if ac and af:
        rp1 = ac["aprov"] * 0.6 + (1-af["aprov"]) * 0.4
        rp2 = af["aprov"] * 0.6 + (1-ac["aprov"]) * 0.4
        rpx = max(0.10, 1.0 - rp1 - rp2)
        t   = rp1+rpx+rp2
        return {"p1":round(rp1/t,4),"px":round(rpx/t,4),"p2":round(rp2/t,4),"fonte":"aproveitamento"}

    # 4. Posição
    if posicao and posicao in _PROB_POS:
        p = _PROB_POS[posicao]
        return {"p1":p[0],"px":p[1],"p2":p[2],"fonte":f"posicao_{posicao}"}

    # 5. Global
    return {"p1":DIST_GLOBAL["p1"],"px":DIST_GLOBAL["px"],"p2":DIST_GLOBAL["p2"],"fonte":"global"}

def classificar(probs):
    v = sorted([probs["p1"],probs["px"],probs["p2"]],reverse=True)
    if v[0] >= 0.60: return "SECO"
    if v[0]+v[1] >= 0.75: return "DUPLO"
    return "TRIPLO"

def score_0_100(probs):
    return round(probs["p1"]*100 + probs["px"]*50, 1)

def favorito(probs):
    return max({"1":probs["p1"],"X":probs["px"],"2":probs["p2"]}, key=lambda k: {"1":probs["p1"],"X":probs["px"],"2":probs["p2"]}[k])

# ═══════════════════════════════════════════════════════════
# BANCO — SCHEMA
# ═══════════════════════════════════════════════════════════

def inicializar_banco():
    db = _db()
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
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
        odd_1 REAL, odd_x REAL, odd_2 REAL,
        xg_m REAL, xg_v REAL,
        forma_m TEXT, forma_v TEXT,
        h2h_1 REAL, h2h_x REAL, h2h_2 REAL,
        posicao_m INTEGER, posicao_v INTEGER,
        classico INTEGER DEFAULT 0, enriquecido INTEGER DEFAULT 0,
        FOREIGN KEY(concurso) REFERENCES concursos(concurso)
    );
    CREATE TABLE IF NOT EXISTS freq_historica (
        posicao INTEGER PRIMARY KEY, freq_1 REAL, freq_x REAL, freq_2 REAL,
        total INTEGER, updated TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_jl_c ON jogos_loteca(concurso);
    CREATE INDEX IF NOT EXISTS idx_jl_m ON jogos_loteca(mandante);
    CREATE INDEX IF NOT EXISTS idx_jl_v ON jogos_loteca(visitante);
    """)
    conn.commit(); conn.close()

# ═══════════════════════════════════════════════════════════
# COLETA CEF
# ═══════════════════════════════════════════════════════════

def _parse_float(v):
    if isinstance(v,(int,float)): return float(v)
    try: return float(str(v).replace("R$","").replace(".","").replace(",",".").strip())
    except: return 0.0

def buscar_cef(numero):
    try:
        url = f"{URL_CEF}/{numero}" if numero else URL_CEF
        r = requests.get(url, timeout=12, headers={"User-Agent":"Mozilla/5.0"})
        return r.json() if r.status_code==200 else None
    except: return None

def parsear_cef(numero, d):
    if not d: return None, []
    concurso = {"concurso":numero, "data_sorteio":d.get("dataApuracao",""),
                "premio_14":_parse_float(d.get("valorPremio14Acertos",0)),
                "premio_13":_parse_float(d.get("valorPremio13Acertos",0)),
                "ganhadores_14":d.get("ganhadores14Acertos",0) or 0,
                "ganhadores_13":d.get("ganhadores13Acertos",0) or 0,
                "acumulou":1 if d.get("acumulado") else 0, "fonte":"cef"}
    t1  = d.get("listaResultadosEquipeUm", d.get("listaTimeCoracao",[]))
    t2  = d.get("listaResultadosEquipeDois",[])
    res = d.get("listaDezenas", d.get("dezenas",[]))
    jogos = []
    for i in range(max(len(t1),len(res),1)):
        jogos.append({"concurso":numero,"posicao":i+1,
                      "mandante":t1[i] if i<len(t1) else f"Time A {i+1}",
                      "visitante":t2[i] if i<len(t2) else f"Time B {i+1}",
                      "resultado":res[i] if i<len(res) else "?",
                      "gols_m":None,"gols_v":None,"data_jogo":"","liga":""})
    return concurso, jogos

def salvar_cef(conn, concurso, jogos):
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO concursos
        (concurso,data_sorteio,premio_14,premio_13,ganhadores_14,ganhadores_13,acumulou,fonte)
        VALUES(?,?,?,?,?,?,?,?)""",
        (concurso["concurso"],concurso["data_sorteio"],concurso["premio_14"],
         concurso["premio_13"],concurso["ganhadores_14"],concurso["ganhadores_13"],
         concurso["acumulou"],concurso["fonte"]))
    c.execute("DELETE FROM jogos_loteca WHERE concurso=?", (concurso["concurso"],))
    for j in jogos:
        c.execute("""INSERT INTO jogos_loteca
            (concurso,posicao,mandante,visitante,resultado,gols_m,gols_v,data_jogo,liga)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (j["concurso"],j["posicao"],j["mandante"],j["visitante"],j["resultado"],
             j["gols_m"],j["gols_v"],j["data_jogo"],j["liga"]))
    conn.commit()

_coleta = {"rodando":False,"relatorio":None,"erro":None,"coletados":0}

def _coletar_worker(inicio, fim):
    global _coleta
    try:
        conn = sqlite3.connect(_db())
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()
        c.execute("SELECT MAX(concurso) FROM concursos"); ultimo = c.fetchone()[0] or 0
        if inicio <= ultimo: inicio = ultimo+1
        falhas = coletados = 0; numero = inicio
        while True:
            if fim and numero>fim: break
            if falhas>=5: break
            dados = buscar_cef(numero)
            if dados is None: falhas+=1
            else:
                falhas=0; con,jos = parsear_cef(numero,dados)
                if con: salvar_cef(conn,con,jos); coletados+=1
                _coleta["coletados"] = coletados
            numero+=1; time.sleep(0.4)
        c.execute("SELECT COUNT(*) FROM concursos"); tc=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM jogos_loteca"); tj=c.fetchone()[0]
        c.execute("SELECT MAX(concurso) FROM concursos"); mx=c.fetchone()[0]
        conn.close()
        _coleta = {"rodando":False,"relatorio":{"coletados":coletados,"total_concursos":tc,
                   "total_jogos":tj,"ultimo":mx},"erro":None,"coletados":coletados}
    except Exception as e:
        _coleta = {"rodando":False,"relatorio":None,"erro":str(e),"coletados":0}

# ═══════════════════════════════════════════════════════════
# ROTAS
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    for pasta in [os.path.dirname(os.path.abspath(__file__)), os.getcwd(),
                  "/opt/render/project/src", "/opt/render/project"]:
        p = os.path.join(pasta, "index.html")
        if os.path.exists(p):
            with open(p,"r",encoding="utf-8") as f:
                return Response(f.read(), mimetype="text/html")
    return "index.html não encontrado", 404

@app.route("/api/status")
def api_status():
    carregar_dados()
    db = _db()
    try:
        conn = sqlite3.connect(db); c = conn.cursor()
        c.execute("SELECT COUNT(*), MIN(concurso), MAX(concurso), MIN(data_sorteio), MAX(data_sorteio) FROM concursos")
        tc,mn,mx,dm,dM = c.fetchone()
        c.execute("SELECT COUNT(*) FROM jogos_loteca"); tj=c.fetchone()[0]
        conn.close(); banco_ok=True
    except: tc=tj=mn=mx=dm=dM=None; banco_ok=False
    return jsonify({
        "status":"online","versao":"4.1",
        "banco":{"ok":banco_ok,"concursos":tc,"jogos":tj,"periodo":f"{dm} → {dM}","min":mn,"max":mx},
        "dados_memoria":{"h2h":len(_H2H),"times_casa":len(_GOLS_CASA),"times_fora":len(_GOLS_FORA)},
        "calibracao":{"lambda_casa":LAMBDA_CASA,"lambda_fora":LAMBDA_FORA,"dist_global":DIST_GLOBAL}
    })

@app.route("/api/analisar")
def api_analisar():
    m = request.args.get("mandante","").strip()
    v = request.args.get("visitante","").strip()
    pos = request.args.get("posicao", type=int)
    if not m or not v: return jsonify({"erro":"Informe mandante e visitante"}),400
    probs = calcular_probs(m, v, pos)
    cl = classificar(probs); sc = score_0_100(probs)
    fav = favorito(probs)
    vals = sorted([probs["p1"],probs["px"],probs["p2"]],reverse=True)
    conf = round((vals[0]-vals[1])*100,1)
    return jsonify({"mandante":m,"visitante":v,"posicao":pos,
                    "probabilidades":probs,"favorito":fav,
                    "classificacao":cl,"score_0_100":sc,"confianca":conf,
                    "fonte":probs.get("fonte","?")})

@app.route("/api/concurso/<int:numero>/analisar")
def api_analisar_concurso(numero):
    db = _db()
    try:
        conn = sqlite3.connect(db); c = conn.cursor()
        c.execute("""SELECT posicao,mandante,visitante,resultado
            FROM jogos_loteca WHERE concurso=? ORDER BY posicao""", (numero,))
        rows = c.fetchall(); conn.close()
    except Exception as e: return jsonify({"erro":str(e)}),500
    if not rows: return jsonify({"erro":f"Concurso {numero} não encontrado"}),404
    resultado = []
    for pos,m,v,res in rows:
        probs = calcular_probs(m or "",v or "",pos)
        cl=classificar(probs); sc=score_0_100(probs); fav=favorito(probs)
        resultado.append({"posicao":pos,"mandante":m,"visitante":v,"resultado_real":res,
                          "probabilidades":{"p1":probs["p1"],"px":probs["px"],"p2":probs["p2"]},
                          "score_0_100":sc,"classificacao":cl,"favorito":fav,"fonte":probs.get("fonte","?")})
    acertos = sum(1 for r in resultado if r["resultado_real"] in ("1","X","2") and r["resultado_real"]==r["favorito"])
    secos   = sum(1 for r in resultado if r["classificacao"]=="SECO")
    duplos  = sum(1 for r in resultado if r["classificacao"]=="DUPLO")
    triplos = sum(1 for r in resultado if r["classificacao"]=="TRIPLO")
    custo   = round(3.0*(2**duplos)*(3**triplos)/100,2)
    return jsonify({"concurso":numero,"total":len(resultado),
                    "acertos_favorito":acertos,"pct_acerto":round(acertos/max(len(resultado),1)*100,1),
                    "secos":secos,"duplos":duplos,"triplos":triplos,"custo_minimo":custo,
                    "jogos":resultado})

@app.route("/api/concurso/atual")
def api_concurso_atual():
    dados = buscar_cef("")
    if not dados:
        try:
            conn=sqlite3.connect(_db()); c=conn.cursor()
            c.execute("SELECT MAX(concurso) FROM concursos"); ultimo=c.fetchone()[0]; conn.close()
            if ultimo: return api_analisar_concurso(ultimo)
        except: pass
        return jsonify({"erro":"API CEF indisponível"}),503
    numero = dados.get("numero", dados.get("numeroConcurso",0))
    return api_analisar_concurso(numero)

@app.route("/api/historico/resumo")
def hist_resumo():
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute("SELECT COUNT(*),MIN(concurso),MAX(concurso),MIN(data_sorteio),MAX(data_sorteio) FROM concursos")
        tc,mn,mx,dm,dM=c.fetchone()
        c.execute("SELECT COUNT(*) FROM jogos_loteca"); tj=c.fetchone()[0]
        c.execute("SELECT resultado,COUNT(*) FROM jogos_loteca WHERE resultado IN ('1','X','2') GROUP BY resultado")
        dist=dict(c.fetchall()); total=sum(dist.values())
        c.execute("SELECT mandante,COUNT(*) FROM jogos_loteca GROUP BY mandante ORDER BY 2 DESC LIMIT 10")
        top=[{"time":r[0],"jogos":r[1]} for r in c.fetchall()]
        conn.close()
        return jsonify({"total_concursos":tc,"total_jogos":tj,
                        "periodo":f"{dm} → {dM}","min":mn,"max":mx,
                        "distribuicao":{k:{"n":v,"pct":round(v/total*100,1)} for k,v in dist.items()},
                        "top_10_mandantes":top})
    except Exception as e: return jsonify({"erro":str(e)}),500

@app.route("/api/historico/time/<nome>")
def hist_time(nome):
    carregar_dados()
    m = nome.lower()
    ac = _APROV_CASA.get(m); af = _APROV_FORA.get(m)
    gc = _GOLS_CASA.get(m);  gf = _GOLS_FORA.get(m)
    if not ac and not af: return jsonify({"erro":f"Time '{nome}' não encontrado"}),404
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute("""SELECT j.concurso,co.data_sorteio,j.mandante,j.visitante,j.resultado
            FROM jogos_loteca j JOIN concursos co ON j.concurso=co.concurso
            WHERE LOWER(j.mandante)=? OR LOWER(j.visitante)=?
            ORDER BY j.concurso DESC LIMIT 20""", (m,m))
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
    carregar_dados()
    h2h=_H2H.get(f"{m}|{v}")
    try:
        conn=sqlite3.connect(_db()); c=conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jogos_loteca'")
        if not c.fetchone(): conn.close(); return jsonify({"mandante":m,"visitante":v,"total":0,"h2h_probs":h2h,"jogos":[]})
        c.execute("""SELECT j.concurso,co.data_sorteio,j.mandante,j.visitante,j.resultado
            FROM jogos_loteca j JOIN concursos co ON j.concurso=co.concurso
            WHERE (LOWER(j.mandante)=? AND LOWER(j.visitante)=?)
               OR (LOWER(j.mandante)=? AND LOWER(j.visitante)=?)
            ORDER BY j.concurso DESC LIMIT 30""", (m,v,v,m))
        rows=c.fetchall(); conn.close()
    except Exception as e: return jsonify({"erro":str(e)}),500
    return jsonify({"mandante":m,"visitante":v,"total":len(rows),"h2h_probs":h2h,
                    "jogos":[{"concurso":r[0],"data":r[1],"mandante":r[2],"visitante":r[3],"resultado":r[4]}
                              for r in rows]})

@app.route("/api/coletar", methods=["POST"])
def api_coletar():
    global _coleta
    if _coleta["rodando"]: return jsonify({"status":"ja_rodando"}),409
    body=request.get_json(silent=True) or {}
    inicio=body.get("inicio",1); fim=body.get("fim")
    _coleta={"rodando":True,"relatorio":None,"erro":None,"coletados":0}
    threading.Thread(target=_coletar_worker,args=(inicio,fim),daemon=True).start()
    return jsonify({"status":"iniciado","mensagem":f"Coletando a partir do concurso {inicio}"})

@app.route("/api/coletar/status")
def api_coletar_status():
    return jsonify(_coleta)

@app.route("/api/posicoes")
def api_posicoes():
    carregar_dados()
    return jsonify({str(p):{"p1":v[0],"px":v[1],"p2":v[2]} for p,v in _PROB_POS.items()})

@app.route("/api/db-info")
def api_db_info():
    db=_db()
    try:
        conn=sqlite3.connect(db); c=conn.cursor()
        c.execute("SELECT COUNT(*),MAX(concurso) FROM concursos"); tc,mx=c.fetchone()
        c.execute("SELECT COUNT(*) FROM jogos_loteca"); tj=c.fetchone()[0]
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas=[r[0] for r in c.fetchall()]
        conn.close()
        return jsonify({"db_conectado":True,"caminho":db,"total_concursos":tc,
                        "total_jogos":tj,"ultimo_concurso":mx,"tabelas":tabelas})
    except Exception as e:
        return jsonify({"db_conectado":False,"caminho":db,"erro":str(e)})

if __name__=="__main__":
    inicializar_banco()
    carregar_dados()
    port=int(os.getenv("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)
