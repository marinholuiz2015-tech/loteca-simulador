"""
Loteca Elite Pro — app.py v10.1
Corrige o bug encontrado no teste da v10.0: buscar_h2h_real,
buscar_medias_gols_real e elo_time ainda usavam nomes de coluna fixos
("mandante"/"visitante"), em vez de usar o schema que
detectar_schema_jogos() já descobre corretamente (no banco real,
jogos_historico, as colunas se chamam time_casa/time_fora).

Variáveis de ambiente no Render:
  RAPIDAPI_KEY  → API-Football (fixtures, lesões, escalação) -- opcional
  ODDS_API_KEY  → The Odds API (odds de mercado Bet365/Pinnacle) -- opcional
  DATABASE_URL  → PostgreSQL (se ausente usa SQLite local) -- recomendado
"""

import os, math, sqlite3, logging, requests, time
from flask import Flask, jsonify, request
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("loteca")

app = Flask(__name__)
CORS(app)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
ODDS_KEY     = os.getenv("ODDS_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG       = DATABASE_URL.startswith("postgres")

APIF_HOST = "free-api-live-football-data.p.rapidapi.com"
APIF_BASE = f"https://{APIF_HOST}"
URL_CEF   = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca"

# ─── Banco de dados ───────────────────────────────────────────
def get_conn():
    if USE_PG:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(os.getenv("SQLITE_PATH", "/tmp/loteca_elite.db"))
    conn.row_factory = sqlite3.Row
    return conn

def _ph():
    return "%s" if USE_PG else "?"

def init_db():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS historico (
            id """ + ("SERIAL" if USE_PG else "INTEGER") + """ PRIMARY KEY""" +
            ("" if USE_PG else " AUTOINCREMENT") + """,
            concurso INTEGER, mandante TEXT, visitante TEXT,
            resultado TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit(); conn.close()
        log.info("Banco OK: %s", "PostgreSQL" if USE_PG else "SQLite")
    except Exception as e:
        log.warning("Banco indisponível: %s", e)

# ─── Detecção dinâmica de schema ──────────────────────────────
_SCHEMA_CACHE = {"ts": 0, "info": None}

def detectar_schema_jogos():
    if time.time() - _SCHEMA_CACHE["ts"] < 300 and _SCHEMA_CACHE["info"]:
        return _SCHEMA_CACHE["info"]
    info = {"tabela": None, "col_mandante": None, "col_visitante": None,
            "col_gm": None, "col_gv": None, "col_pos": None,
            "col_liga": None, "existe": False}
    try:
        conn = get_conn(); cur = conn.cursor()
        if USE_PG:
            cur.execute("""SELECT table_name FROM information_schema.tables
                           WHERE table_schema='public'""")
        else:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = [r[0] for r in cur.fetchall()]
        for candidata in ["jogos_historico", "jogos_loteca", "jogos"]:
            if candidata in tabelas:
                info["tabela"] = candidata
                break
        if info["tabela"]:
            if USE_PG:
                cur.execute("""SELECT column_name FROM information_schema.columns
                               WHERE table_name=%s""", (info["tabela"],))
                cols = [r[0] for r in cur.fetchall()]
            else:
                cur.execute(f"PRAGMA table_info({info['tabela']})")
                cols = [r[1] for r in cur.fetchall()]

            if "time_casa" in cols and "time_fora" in cols:
                info["col_mandante"], info["col_visitante"] = "time_casa", "time_fora"
            elif "mandante" in cols and "visitante" in cols:
                info["col_mandante"], info["col_visitante"] = "mandante", "visitante"

            if "gols_casa" in cols and "gols_fora" in cols:
                info["col_gm"], info["col_gv"] = "gols_casa", "gols_fora"
            elif "gols_m" in cols and "gols_v" in cols:
                info["col_gm"], info["col_gv"] = "gols_m", "gols_v"
            elif "gols_mandante" in cols and "gols_visitante" in cols:
                info["col_gm"], info["col_gv"] = "gols_mandante", "gols_visitante"

            info["col_pos"] = "sequencial" if "sequencial" in cols else ("posicao" if "posicao" in cols else None)
            info["col_liga"] = "liga" if "liga" in cols else ("campeonato" if "campeonato" in cols else None)
            info["existe"] = bool(info["col_mandante"] and info["col_gm"])
        conn.close()
    except Exception as e:
        log.warning("detectar_schema_jogos: %s", e)
    _SCHEMA_CACHE["ts"] = time.time()
    _SCHEMA_CACHE["info"] = info
    return info

def _parse_gol(v):
    if v is None: return None
    if isinstance(v, (int, float)): return int(v)
    try: return int(str(v).strip())
    except (ValueError, TypeError): return None

def buscar_h2h_real(mandante, visitante):
    schema = detectar_schema_jogos()
    if not schema["existe"]: return None
    cm, cv = schema["col_mandante"], schema["col_visitante"]
    m, v = mandante.upper().strip(), visitante.upper().strip()
    try:
        conn = get_conn(); cur = conn.cursor()
        ph = _ph()
        cur.execute(f"""
            SELECT resultado, COUNT(*) FROM {schema['tabela']}
            WHERE UPPER(TRIM({cm}))={ph} AND UPPER(TRIM({cv}))={ph}
              AND resultado IN ('1','X','2')
            GROUP BY resultado
        """, (m, v))
        contagem = dict(cur.fetchall())
        conn.close()
        total = sum(contagem.values())
        if total < 3: return None
        return {"1": round(contagem.get("1",0)/total,4),
                "X": round(contagem.get("X",0)/total,4),
                "2": round(contagem.get("2",0)/total,4), "n": total}
    except Exception as e:
        log.warning("buscar_h2h_real: %s", e); return None

def buscar_medias_gols_real(time_nome, mandante=True):
    schema = detectar_schema_jogos()
    if not schema["existe"] or not schema["col_gm"] or not schema["col_gv"]: return None
    t = time_nome.upper().strip()
    campo_nome   = schema["col_mandante"] if mandante else schema["col_visitante"]
    campo_pro    = schema["col_gm"] if mandante else schema["col_gv"]
    campo_contra = schema["col_gv"] if mandante else schema["col_gm"]
    try:
        conn = get_conn(); cur = conn.cursor()
        ph = _ph()
        cur.execute(f"""
            SELECT {campo_pro}, {campo_contra} FROM {schema['tabela']}
            WHERE UPPER(TRIM({campo_nome}))={ph}
        """, (t,))
        linhas = cur.fetchall(); conn.close()
        gols_pro, gols_contra, n = 0, 0, 0
        for gp, gc in linhas:
            gp2, gc2 = _parse_gol(gp), _parse_gol(gc)
            if gp2 is None or gc2 is None: continue
            gols_pro += gp2; gols_contra += gc2; n += 1
        if n < 5: return None
        return {"gols_pro": round(gols_pro/n,3), "gols_contra": round(gols_contra/n,3), "n": n}
    except Exception as e:
        log.warning("buscar_medias_gols_real: %s", e); return None

ELO_FALLBACK = {
    "ARGENTINA":2140,"FRANÇA":2100,"INGLATERRA":2080,"ESPANHA":2070,
    "ALEMANHA":2060,"PORTUGAL":2040,"HOLANDA":2030,"BRASIL":2050,
    "PALMEIRAS":1820,"FLAMENGO":1810,"BOTAFOGO":1780,"FLUMINENSE":1750,
    "ATLETICO MG":1760,"SÃO PAULO":1740,"CORINTHIANS":1720,"GRÊMIO":1700,
    "INTERNACIONAL":1710,"CRUZEIRO":1690,"VASCO DA GAMA":1660,"SANTOS":1650,
    "FORTALEZA":1670,"BAHIA":1640,"MIRASSOL":1610,"JUVENTUDE":1590,
    "VITÓRIA":1580,"SPORT":1560,"BRAGANTINO":1620,"ATHLETICO PR":1660,
}

def elo_time(nome):
    schema = detectar_schema_jogos()
    if schema["existe"]:
        cm, cv = schema["col_mandante"], schema["col_visitante"]
        t = nome.upper().strip()
        try:
            conn = get_conn(); cur = conn.cursor()
            ph = _ph()
            cur.execute(f"""
                SELECT resultado, COUNT(*) FROM {schema['tabela']}
                WHERE UPPER(TRIM({cm}))={ph} OR UPPER(TRIM({cv}))={ph}
                GROUP BY resultado
            """, (t, t))
            linhas = dict(cur.fetchall()); conn.close()
            total = sum(linhas.values())
            if total >= 5:
                taxa_vitoria = linhas.get("1", 0) / total
                return round(1500 + taxa_vitoria * 400, 0)
        except Exception as e:
            log.warning("elo_time: %s", e)
    return ELO_FALLBACK.get(nome.upper().strip(), 1650)

MEDIA_GOLS = {
    "copa":{"casa":1.35,"fora":1.05}, "serie_a":{"casa":1.42,"fora":1.05},
    "serie_b":{"casa":1.35,"fora":1.00}, "serie_c":{"casa":1.28,"fora":0.98},
    "premier":{"casa":1.53,"fora":1.22}, "la_liga":{"casa":1.47,"fora":1.10},
    "libertadores":{"casa":1.38,"fora":0.95},
}

def _poi(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def poisson_probs(mandante, visitante, liga="_default"):
    h2h = buscar_h2h_real(mandante, visitante)
    if h2h:
        return {"1":h2h["1"],"X":h2h["X"],"2":h2h["2"],
                "elo_casa":elo_time(mandante),"elo_fora":elo_time(visitante),
                "lam_casa":None,"lam_fora":None,"fonte_base":f"h2h_real_{h2h['n']}x"}
    mg_casa = buscar_medias_gols_real(mandante, mandante=True)
    mg_fora = buscar_medias_gols_real(visitante, mandante=False)
    if mg_casa and mg_fora:
        lc = max(0.3, (mg_casa["gols_pro"] + mg_fora["gols_contra"]) / 2)
        lf = max(0.3, (mg_fora["gols_pro"] + mg_casa["gols_contra"]) / 2)
        fonte_base = "medias_reais"
    else:
        ec, ef = elo_time(mandante), elo_time(visitante)
        med = MEDIA_GOLS.get(liga, {"casa":1.40,"fora":1.05})
        ajuste = (ec - ef) / 200 * 0.25
        lc = max(0.3, med["casa"] + ajuste + 0.06)
        lf = max(0.3, med["fora"] - ajuste)
        fonte_base = "fallback_elo_generico"
    ec, ef = elo_time(mandante), elo_time(visitante)
    p1 = px = p2 = 0.0
    for i in range(9):
        for j in range(9):
            p = _poi(lc,i) * _poi(lf,j)
            if i > j: p1 += p
            elif i == j: px += p
            else: p2 += p
    t = p1 + px + p2
    return {"1":round(p1/t,4),"X":round(px/t,4),"2":round(p2/t,4),
            "elo_casa":ec,"elo_fora":ef,"lam_casa":round(lc,3),"lam_fora":round(lf,3),"fonte_base":fonte_base}

def sem_margem(o1, ox, o2):
    r1,rx,r2 = 1/o1,1/ox,1/o2; over = r1+rx+r2
    return {"1":round(r1/over,4),"X":round(rx/over,4),"2":round(r2/over,4),"over":round(over,4)}

def blending(prob_m, odds=None, w=0.65):
    if not odds: return {**prob_m,"fonte":"modelo_puro"}
    pm = sem_margem(odds["1"],odds["X"],odds["2"]); wm = 1-w
    out = {k:round(prob_m[k]*w+pm[k]*wm,4) for k in ["1","X","2"]}
    t = sum(out.values()); out = {k:round(v/t,4) for k,v in out.items()}
    out["fonte"]="blend_nao_calibrado"; out["peso_modelo"]=w; out["overround"]=pm["over"]
    return out

def classificar(probs, odd_1=None, liga="_default"):
    p1,px,p2 = probs["1"],probs["X"],probs["2"]
    ordem = sorted([("1",p1),("X",px),("2",p2)],key=lambda x:x[1],reverse=True)
    top_c,top_v = ordem[0]; seg_c,_ = ordem[1]
    lim = 0.52
    if liga=="copa" and odd_1:
        if odd_1<1.50: lim=0.82
        elif odd_1<1.80: lim=0.62
    if top_v>=lim: tipo,cols="SECO",[top_c]
    elif top_v>=0.40: tipo,cols="DUPLO",[top_c,seg_c]
    else: tipo,cols="TRIPLO",["1","X","2"]
    classe = "A" if top_v>=0.80 else "B" if top_v>=0.65 else "C" if top_v>=0.50 else "D" if top_v>=0.40 else "E"
    return {"tipo":tipo,"colunas":cols,"coluna_display":"/".join(sorted(cols)),
            "confianca":round(top_v*100,1),"classe":classe}

def kelly(prob, odd, banca=100.0, fracao=0.25):
    b=odd-1.0; kp=(b*prob-(1-prob))/b if b>0 else -1.0; ev=prob*b-(1-prob)
    ok=kp>0.01 and ev>0.02
    return {"stake":round(banca*max(0,kp*fracao),2) if ok else 0.0,"ev":round(ev,4),"apostar":ok}

def score(classif, mot=0.70):
    return round(min(100.0,classif["confianca"]*(0.85+0.15*mot)),1)

def analisar_jogo(mandante, visitante, liga="_default", odds=None, banca=100.0):
    pm = poisson_probs(mandante,visitante,liga)
    pf = blending(pm,odds)
    cl = classificar(pf,odd_1=odds["1"] if odds else None,liga=liga)
    sc = score(cl)
    kelly_res,melhor = {},None
    if odds:
        for res in ["1","X","2"]:
            if odds.get(res,0)>1.0: kelly_res[res]=kelly(pf[res],odds[res],banca)
        candidatos=[(r,k) for r,k in kelly_res.items() if k["apostar"]]
        if candidatos:
            best=max(candidatos,key=lambda x:x[1]["ev"])
            melhor={"resultado":best[0],"odd":odds[best[0]],"ev":best[1]["ev"],"stake":best[1]["stake"]}
    return {"prob_modelo":{"1":pm["1"],"X":pm["X"],"2":pm["2"]},
            "prob_final":{"1":pf["1"],"X":pf["X"],"2":pf["2"]},
            "fonte":pf.get("fonte","modelo_puro"),"fonte_base_modelo":pm.get("fonte_base"),
            "overround":pf.get("overround"),"elo_casa":pm["elo_casa"],"elo_fora":pm["elo_fora"],
            "lam_casa":pm.get("lam_casa"),"lam_fora":pm.get("lam_fora"),
            "classificacao":cl,"score":sc,"kelly":kelly_res or None,"melhor_aposta":melhor}

@app.route("/health")
@app.route("/api/status")
def health():
    schema = detectar_schema_jogos()
    return jsonify({"status":"ok","versao":"Loteca Elite Pro v10.1",
                    "modelo":"h2h_real > medias_gols_real > elo_dinamico > fallback_fixo",
                    "banco":"postgresql" if USE_PG else "sqlite",
                    "tabela_jogos_historicos":schema["tabela"] or "NENHUMA",
                    "schema_ok":schema["existe"]})

@app.route("/api/analisar")
def analisar():
    m=request.args.get("mandante",""); v=request.args.get("visitante","")
    liga=request.args.get("liga","_default")
    o1=request.args.get("odd_1",type=float); ox=request.args.get("odd_x",type=float); o2=request.args.get("odd_2",type=float)
    banca=float(request.args.get("banca",100))
    if not m or not v:
        return jsonify({"status":"erro","mensagem":"mandante e visitante obrigatórios"}),400
    odds={"1":o1,"X":ox,"2":o2} if all([o1,ox,o2]) else None
    analise=analisar_jogo(m,v,liga,odds=odds,banca=banca)
    return jsonify({"status":"sucesso","mandante":m,"visitante":v,"liga":liga,**analise})

@app.route("/api/db-info")
def db_info():
    try:
        schema=detectar_schema_jogos(); conn=get_conn(); cur=conn.cursor()
        info={"tabela_jogos_historicos":schema["tabela"],"schema_detectado":schema}
        if schema["existe"]:
            cur.execute(f"SELECT COUNT(*) FROM {schema['tabela']}")
            info["total_jogos"]=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(DISTINCT UPPER(TRIM({schema['col_mandante']}))) FROM {schema['tabela']}")
            info["times_distintos"]=cur.fetchone()[0]
            cur.execute(f"SELECT MIN(concurso), MAX(concurso) FROM {schema['tabela']}")
            mn,mx=cur.fetchone(); info["concurso_min"],info["concurso_max"]=mn,mx
        conn.close()
        return jsonify({"status":"sucesso","banco":"postgresql" if USE_PG else "sqlite",**info})
    except Exception as e:
        return jsonify({"status":"erro","mensagem":str(e)}),500

init_db()

if __name__ == "__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)
