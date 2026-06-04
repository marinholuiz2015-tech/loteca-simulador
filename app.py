"""
LOTECA ELITE PRO — app.py v3.1
Camada 1 + Coletor Histórico CEF integrado
"""

import os, math, logging, sqlite3, threading, glob
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

FDATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")
ODDS_KEY  = os.getenv("ODDS_API_KEY", "")
DB_PATH   = os.getenv("DB_PATH", "loteca_historico.db")
URL_CEF   = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca"

LIGAS = {
    "brasileirao":   {"codigo":"BSA", "nome":"Brasileirão Série A",  "pais":"Brasil"},
    "serie_b":       {"codigo":"BSB", "nome":"Brasileirão Série B",  "pais":"Brasil"},
    "serie_c":       {"codigo":"BSC", "nome":"Brasileirão Série C",  "pais":"Brasil"},
    "serie_d":       {"codigo":"BSD", "nome":"Brasileirão Série D",  "pais":"Brasil"},
    "copa_brasil":   {"codigo":"CB",  "nome":"Copa do Brasil",       "pais":"Brasil"},
    "copa_ne":       {"codigo":"CNE", "nome":"Copa do Nordeste",     "pais":"Brasil"},
    "paulistao":     {"codigo":"CPB", "nome":"Paulistão",            "pais":"Brasil"},
    "carioca":       {"codigo":"CRJ", "nome":"Carioca",              "pais":"Brasil"},
    "gaucho":        {"codigo":"CGS", "nome":"Gaúcho",               "pais":"Brasil"},
    "mineiro":       {"codigo":"CMG", "nome":"Mineiro",              "pais":"Brasil"},
    "libertadores":  {"codigo":"CLI", "nome":"Copa Libertadores",    "pais":"Sul-América"},
    "sul_americana": {"codigo":"CSA", "nome":"Copa Sul-Americana",   "pais":"Sul-América"},
    "champions":     {"codigo":"CL",  "nome":"Champions League",     "pais":"Europa"},
    "premier":       {"codigo":"PL",  "nome":"Premier League",       "pais":"Inglaterra"},
    "la_liga":       {"codigo":"PD",  "nome":"La Liga",              "pais":"Espanha"},
    "serie_a_it":    {"codigo":"SA",  "nome":"Serie A (Itália)",     "pais":"Itália"},
    "bundesliga":    {"codigo":"BL1", "nome":"Bundesliga",           "pais":"Alemanha"},
    "ligue1":        {"codigo":"FL1", "nome":"Ligue 1",              "pais":"França"},
    "primeira_liga": {"codigo":"PPL", "nome":"Primeira Liga",        "pais":"Portugal"},
    "copa_do_mundo": {"codigo":"WC",  "nome":"Copa do Mundo",        "pais":"Mundial"},
}

# ═══════════════════════════════════════════════════════════
# BANCO HISTÓRICO
# ═══════════════════════════════════════════════════════════
def _db_path_real():
    """Encontra o caminho real do banco — testa múltiplos locais."""
    candidatos = [
        DB_PATH,
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "loteca_historico.db"),
        os.path.join(os.getcwd(), "loteca_historico.db"),
        "/opt/render/project/src/loteca_historico.db",
        "/opt/render/project/loteca_historico.db",
    ]
    for p in candidatos:
        if os.path.exists(p):
            return p
    return DB_PATH  # fallback

def criar_banco():
    conn = sqlite3.connect(_db_path_real())
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS concursos (
        id INTEGER PRIMARY KEY, numero INTEGER UNIQUE,
        data_apuracao TEXT, data_proximo TEXT,
        acumulado INTEGER, arrecadacao REAL, coletado_em TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS jogos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concurso INTEGER, numero_jogo INTEGER,
        mandante TEXT, visitante TEXT, resultado TEXT,
        FOREIGN KEY(concurso) REFERENCES concursos(numero))""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jc ON jogos(concurso)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jm ON jogos(mandante)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jv ON jogos(visitante)")
    conn.commit(); conn.close()

def _parse_float(v):
    if isinstance(v,(int,float)): return float(v)
    try: return float(str(v).replace("R$","").replace(".","").replace(",",".").strip())
    except: return 0.0

def buscar_concurso_cef(numero):
    try:
        r = requests.get(f"{URL_CEF}/{numero}", timeout=10,
                         headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 404: return None
        if r.status_code != 200: return None
        return r.json()
    except: return None

def parsear(numero, dados):
    if not dados: return None, []
    concurso = {
        "numero": numero,
        "data_apuracao": dados.get("dataApuracao",""),
        "data_proximo":  dados.get("dataProximoConcurso",""),
        "acumulado": 1 if dados.get("acumulado") else 0,
        "arrecadacao": _parse_float(dados.get("valorArrecadado",0)),
        "coletado_em": datetime.now().isoformat()
    }
    times_1   = dados.get("listaResultadosEquipeUm", dados.get("listaTimeCoracao",[]))
    times_2   = dados.get("listaResultadosEquipeDois",[])
    resultados= dados.get("listaDezenas", dados.get("dezenas",[]))
    jogos = []
    for i in range(max(len(times_1),len(resultados),1)):
        jogos.append({
            "concurso": numero, "numero_jogo": i+1,
            "mandante":  times_1[i]   if i<len(times_1)   else f"Time A {i+1}",
            "visitante": times_2[i]   if i<len(times_2)   else f"Time B {i+1}",
            "resultado": resultados[i] if i<len(resultados) else "?"
        })
    return concurso, jogos

def salvar(conn, concurso, jogos):
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO concursos VALUES(NULL,?,?,?,?,?,?)",
        (concurso["numero"],concurso["data_apuracao"],concurso["data_proximo"],
         concurso["acumulado"],concurso["arrecadacao"],concurso["coletado_em"]))
    c.execute("DELETE FROM jogos WHERE concurso=?",(concurso["numero"],))
    for j in jogos:
        c.execute("INSERT INTO jogos(concurso,numero_jogo,mandante,visitante,resultado) VALUES(?,?,?,?,?)",
            (j["concurso"],j["numero_jogo"],j["mandante"],j["visitante"],j["resultado"]))
    conn.commit()

def coletar(inicio=1, fim=None):
    criar_banco()
    db = _db_path_real()
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute("SELECT MAX(numero) FROM concursos")
    ultimo = c.fetchone()[0] or 0
    if inicio <= ultimo: inicio = ultimo + 1
    logger.info(f"Coleta iniciando do concurso {inicio}")
    falhas = 0; coletados = 0; numero = inicio
    while True:
        if fim and numero > fim: break
        if falhas >= 5: break
        c.execute("SELECT 1 FROM concursos WHERE numero=?",(numero,))
        if c.fetchone(): numero+=1; continue
        dados = buscar_concurso_cef(numero)
        if dados is None:
            falhas+=1
        else:
            falhas = 0
            con, jos = parsear(numero, dados)
            if con: salvar(conn, con, jos); coletados+=1
        numero+=1
        import time; time.sleep(0.4)
    c.execute("SELECT COUNT(*) FROM concursos"); tc = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM jogos"); tj = c.fetchone()[0]
    c.execute("SELECT MIN(numero),MAX(numero) FROM concursos"); mn,mx = c.fetchone()
    conn.close()
    return {"coletados":coletados,"total_concursos":tc,"total_jogos":tj,"min":mn,"max":mx}

# ═══════════════════════════════════════════════════════════
# POISSON
# ═══════════════════════════════════════════════════════════
def _pp(lam,k):
    if lam<=0: return 1.0 if k==0 else 0.0
    return (lam**k)*math.exp(-lam)/math.factorial(k)

def poisson(mc,mf,msc=None,msf=None,mg=7):
    msc = msc or mf*0.9; msf = msf or mc*0.9
    lc = max(0.3,min(mc*(msf/max(0.5,(mf+msc)/2))*1.15,5.0))
    lf = max(0.3,min(mf*(msc/max(0.5,(mc+msf)/2))*0.90,5.0))
    p1=px=p2=0.0
    for i in range(mg+1):
        for j in range(mg+1):
            p=_pp(lc,i)*_pp(lf,j)
            if i>j: p1+=p
            elif i==j: px+=p
            else: p2+=p
    t=p1+px+p2
    if t==0: p1,px,p2=0.45,0.25,0.30
    return {"p1":round(p1/t,4),"px":round(px/t,4),"p2":round(p2/t,4)}

def classificar(probs,limiar=0.60):
    v=sorted([probs["p1"],probs["px"],probs["p2"]],reverse=True)
    if v[0]>=limiar: return "SECO"
    elif v[0]+v[1]>=0.75: return "DUPLO"
    return "TRIPLO"

def medias_liga(liga_key):
    d={
        "brasileirao":  (1.55,1.10,1.10,1.55),
        "serie_b":      (1.45,1.05,1.05,1.45),
        "serie_c":      (1.35,1.00,1.00,1.35),
        "serie_d":      (1.25,0.95,0.95,1.25),
        "copa_brasil":  (1.40,1.00,1.00,1.40),
        "copa_ne":      (1.40,1.05,1.05,1.40),
        "paulistao":    (1.50,1.05,1.05,1.50),
        "carioca":      (1.55,1.10,1.10,1.55),
        "gaucho":       (1.45,1.05,1.05,1.45),
        "mineiro":      (1.45,1.05,1.05,1.45),
        "libertadores": (1.45,0.95,0.95,1.45),
        "sul_americana":(1.40,1.00,1.00,1.40),
        "champions":    (1.80,1.20,1.20,1.80),
        "premier":      (1.75,1.30,1.30,1.75),
        "la_liga":      (1.65,1.10,1.10,1.65),
        "serie_a_it":   (1.50,1.00,1.00,1.50),
        "bundesliga":   (1.90,1.35,1.35,1.90),
        "ligue1":       (1.60,1.10,1.10,1.60),
        "primeira_liga":(1.45,1.00,1.00,1.45),
    }
    return d.get(liga_key,d["brasileirao"])

def analisar(jogo,mc=1.5,mf=1.1,msc=1.2,msf=1.4):
    probs=poisson(mc,mf,msc,msf)
    cl=classificar(probs)
    vs=sorted([probs["p1"],probs["px"],probs["p2"]],reverse=True)
    conf=round((vs[0]-vs[1])*100,1)
    return {**jogo,"probabilidades":probs,"classificacao":cl,
            "confianca":conf,"metodo":"poisson_v1"}

# ═══════════════════════════════════════════════════════════
# BUSCA DE JOGOS
# ═══════════════════════════════════════════════════════════
def jogos_simulados(liga_key):
    base={"brasileirao":[("Flamengo","Palmeiras"),("São Paulo","Corinthians"),
                         ("Botafogo","Fluminense"),("Cruzeiro","Atlético MG"),
                         ("Grêmio","Internacional"),("Santos","Vasco"),
                         ("Fortaleza","Ceará"),("Bahia","Vitória"),
                         ("Bragantino","Mirassol"),("Cuiabá","Goiás")],
          "libertadores":[("Flamengo","River Plate"),("Palmeiras","Boca Juniors"),
                          ("Botafogo","Peñarol"),("Atlético MG","Nacional UY")],
          "champions":   [("Real Madrid","Manchester City"),("Bayern","PSG"),
                          ("Arsenal","Barcelona"),("Liverpool","Inter Milão")]}
    pares=base.get(liga_key,base["brasileirao"])
    hoje=datetime.now(timezone.utc)
    return [{"id":f"sim_{i}","mandante":h,"visitante":a,
             "data_utc":(hoje+timedelta(days=i%7)).isoformat(),
             "liga":LIGAS.get(liga_key,{}).get("nome",liga_key),
             "liga_key":liga_key,"_simulado":True}
            for i,(h,a) in enumerate(pares)]

def buscar_jogos(liga_key,dias=14):
    liga=LIGAS.get(liga_key)
    if not liga: raise ValueError(f"Liga '{liga_key}' inválida")
    if not FDATA_KEY: return jogos_simulados(liga_key)
    hoje=datetime.now(timezone.utc)
    ate=hoje+timedelta(days=dias)
    url=(f"https://api.football-data.org/v4/competitions/{liga['codigo']}/matches"
         f"?status=SCHEDULED&dateFrom={hoje.strftime('%Y-%m-%d')}&dateTo={ate.strftime('%Y-%m-%d')}")
    try:
        r=requests.get(url,headers={"X-Auth-Token":FDATA_KEY},timeout=10)
        if r.status_code in(401,403): return jogos_simulados(liga_key)
        r.raise_for_status(); data=r.json()
    except: return jogos_simulados(liga_key)
    jogos=[]
    for m in data.get("matches",[]):
        h=m.get("homeTeam",{}).get("shortName") or m.get("homeTeam",{}).get("name","?")
        a=m.get("awayTeam",{}).get("shortName") or m.get("awayTeam",{}).get("name","?")
        jogos.append({"id":str(m.get("id","")),"mandante":h,"visitante":a,
                      "data_utc":m.get("utcDate",""),"liga":liga["nome"],"liga_key":liga_key})
    return jogos

# ═══════════════════════════════════════════════════════════
# ESTADO DA COLETA
# ═══════════════════════════════════════════════════════════
_coleta = {"rodando":False,"relatorio":None,"erro":None}

# ═══════════════════════════════════════════════════════════
# ROTAS
# ═══════════════════════════════════════════════════════════
@app.route("/")
def index():
    for pasta in [
        os.path.dirname(os.path.abspath(__file__)),
        os.getcwd(),
        "/opt/render/project/src",
        "/opt/render/project",
    ]:
        caminho = os.path.join(pasta, "index.html")
        if os.path.exists(caminho):
            with open(caminho, "r", encoding="utf-8") as f:
                return Response(f.read(), mimetype="text/html")
    return f"index.html nao encontrado. CWD:{os.getcwd()}", 404

@app.route("/api/ligas")
def listar_ligas():
    return jsonify({"ligas":[{"key":k,"nome":v["nome"],"pais":v["pais"]} for k,v in LIGAS.items()]})

@app.route("/api/jogos")
def listar_jogos():
    liga_key=request.args.get("liga","brasileirao")
    dias=int(request.args.get("dias",14))
    try: jogos=buscar_jogos(liga_key,dias)
    except ValueError as e: return jsonify({"erro":str(e)}),400
    return jsonify({"liga":LIGAS.get(liga_key,{}).get("nome",liga_key),
                    "total":len(jogos),"jogos":jogos,
                    "simulado":any(j.get("_simulado") for j in jogos)})

@app.route("/api/grade-automatica")
def grade_automatica():
    liga_key=request.args.get("liga","brasileirao")
    dias=int(request.args.get("dias",14))
    max_j=int(request.args.get("max",14))
    try: raw=buscar_jogos(liga_key,dias)
    except ValueError as e: return jsonify({"erro":str(e)}),400
    raw=raw[:max_j]
    mc,mf,msc,msf=medias_liga(liga_key)
    res=[analisar(j,mc,mf,msc,msf) for j in raw]
    secos=sum(1 for r in res if r["classificacao"]=="SECO")
    duplos=sum(1 for r in res if r["classificacao"]=="DUPLO")
    triplos=sum(1 for r in res if r["classificacao"]=="TRIPLO")
    return jsonify({"liga":LIGAS.get(liga_key,{}).get("nome",liga_key),
                    "total":len(res),"secos":secos,"duplos":duplos,"triplos":triplos,
                    "custo":round(3.0*(2**duplos)*(3**triplos)/100,2),
                    "jogos":res,"simulado":any(j.get("_simulado") for j in raw)})

@app.route("/api/analisar",methods=["POST"])
def analisar_grade():
    body=request.get_json(silent=True) or {}
    jos=body.get("jogos",[])
    if not jos: return jsonify({"erro":"Envie ao menos 1 jogo"}),400
    res=[analisar(j,float(j.get("mc",1.5)),float(j.get("mf",1.1)),
                    float(j.get("msc",1.2)),float(j.get("msf",1.4))) for j in jos]
    secos=sum(1 for r in res if r["classificacao"]=="SECO")
    duplos=sum(1 for r in res if r["classificacao"]=="DUPLO")
    triplos=sum(1 for r in res if r["classificacao"]=="TRIPLO")
    return jsonify({"total":len(res),"secos":secos,"duplos":duplos,"triplos":triplos,
                    "custo":round(3.0*(2**duplos)*(3**triplos)/100,2),"jogos":res})

@app.route("/api/coletar",methods=["POST"])
def iniciar_coleta():
    global _coleta
    if _coleta["rodando"]:
        return jsonify({"status":"ja_rodando"}),409
    body=request.get_json(silent=True) or {}
    inicio=int(body.get("inicio",1))
    fim=body.get("fim",None)
    if fim: fim=int(fim)
    def _run():
        global _coleta
        _coleta={"rodando":True,"relatorio":None,"erro":None}
        try:
            rel=coletar(inicio=inicio,fim=fim)
            _coleta={"rodando":False,"relatorio":rel,"erro":None}
        except Exception as e:
            _coleta={"rodando":False,"relatorio":None,"erro":str(e)}
    threading.Thread(target=_run,daemon=True).start()
    return jsonify({"status":"iniciado","msg":f"Coletando a partir do concurso {inicio}"})

@app.route("/api/coletar/status")
def status_coleta():
    return jsonify(_coleta)

@app.route("/api/historico/resumo")
def hist_resumo():
    try:
        conn=sqlite3.connect(_db_path_real()); c=conn.cursor()
        c.execute("SELECT COUNT(*) FROM concursos"); tc=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM jogos"); tj=c.fetchone()[0]
        c.execute("SELECT MIN(numero),MAX(numero),MIN(data_apuracao),MAX(data_apuracao) FROM concursos")
        mn,mx,dm,dM=c.fetchone()
        c.execute("SELECT mandante,COUNT(*) FROM jogos GROUP BY mandante ORDER BY 2 DESC LIMIT 10")
        top=[{"time":r[0],"jogos":r[1]} for r in c.fetchall()]
        c.execute("SELECT resultado,COUNT(*) FROM jogos GROUP BY resultado")
        dist=dict(c.fetchall())
        conn.close()
        return jsonify({"total_concursos":tc,"total_jogos":tj,
                        "concurso_mais_antigo":mn,"concurso_mais_recente":mx,
                        "data_mais_antiga":dm,"data_mais_recente":dM,
                        "distribuicao_resultados":dist,"top_10_times":top})
    except Exception as e:
        return jsonify({"erro":str(e),"msg":"Banco vazio ou não encontrado."}),500

@app.route("/api/historico/time/<nome>")
def hist_time(nome):
    try:
        conn=sqlite3.connect(_db_path_real()); c=conn.cursor()
        c.execute("SELECT resultado,COUNT(*) FROM jogos WHERE mandante=? GROUP BY resultado",(nome,))
        casa=dict(c.fetchall())
        c.execute("SELECT resultado,COUNT(*) FROM jogos WHERE visitante=? GROUP BY resultado",(nome,))
        fora=dict(c.fetchall())
        conn.close()
        vc=casa.get("1",0); ec=casa.get("X",0); dc=casa.get("2",0)
        vf=fora.get("2",0); ef=fora.get("X",0); df=fora.get("1",0)
        total=vc+ec+dc+vf+ef+df
        return jsonify({"time":nome,"total_jogos":total,
                        "casa":{"jogos":vc+ec+dc,"V":vc,"E":ec,"D":dc},
                        "fora":{"jogos":vf+ef+df,"V":vf,"E":ef,"D":df},
                        "aproveitamento_pct":round((vc+vf)/max(total,1)*100,1)})
    except Exception as e:
        return jsonify({"erro":str(e)}),500

@app.route("/api/historico/confronto")
def hist_confronto():
    m=request.args.get("mandante",""); v=request.args.get("visitante","")
    if not m or not v: return jsonify({"erro":"Informe mandante e visitante"}),400
    try:
        conn=sqlite3.connect(_db_path_real()); c=conn.cursor()
        c.execute("""SELECT j.concurso,co.data_apuracao,j.resultado
                     FROM jogos j JOIN concursos co ON j.concurso=co.numero
                     WHERE j.mandante=? AND j.visitante=?
                     ORDER BY j.concurso DESC LIMIT 20""",(m,v))
        rows=c.fetchall(); conn.close()
        v1=sum(1 for r in rows if r[2]=="1")
        x=sum(1 for r in rows if r[2]=="X")
        v2=sum(1 for r in rows if r[2]=="2")
        return jsonify({"mandante":m,"visitante":v,"total":len(rows),
                        "vitorias_mandante":v1,"empates":x,"vitorias_visitante":v2,
                        "jogos":[{"concurso":r[0],"data":r[1],"resultado":r[2]} for r in rows]})
    except Exception as e:
        return jsonify({"erro":str(e)}),500

@app.route("/api/status")
def api_status():
    db = _db_path_real()
    dbs_encontrados = glob.glob("/opt/render/project/**/*.db", recursive=True)
    try:
        conn=sqlite3.connect(db); c=conn.cursor()
        c.execute("SELECT COUNT(*) FROM concursos"); tc=c.fetchone()[0]
        conn.close()
        banco="populado" if tc>0 else "vazio"
        banco_info=f"{tc} concursos"
    except Exception as e:
        banco="não encontrado"
        banco_info=f"erro: {str(e)}"
    return jsonify({
        "status":"online",
        "versao":"3.1",
        "banco_historico":banco,
        "banco_info":banco_info,
        "db_path_usado":db,
        "db_existe":os.path.exists(db),
        "cwd":os.getcwd(),
        "dbs_no_servidor":dbs_encontrados,
        "football_data":"configurada" if FDATA_KEY else "ausente (simulado)",
        "odds_api":"configurada" if ODDS_KEY else "ausente"
    })

if __name__=="__main__":
    criar_banco()
    port=int(os.getenv("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=os.getenv("FLASK_ENV")=="development")
