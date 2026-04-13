#!/usr/bin/env python3
"""
LOTECA ELITE PRO — Motor v8.0
Sistema COMPLETO e INTEGRADO:
- Grade automática (The Odds API)
- Cartola FC (desfalques + scouts)
- Smart Money 48h (movimento de odds)
- Gerador varandas com filtros
- Backtesting histórico
- API resultado CAIXA
- Gestão de banca automática
"""
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from datetime import datetime, timedelta
import math, os, sqlite3, json, time

try:
    import requests as req_lib
    HAS_REQUESTS = True
except:
    HAS_REQUESTS = False

app = Flask(__name__)
CORS(app)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY","f551053977fdc954910af0b99e0ab8e3")
DB_PATH      = os.environ.get("DB_PATH","loteca_historico_v4.db")

# ── FREQUÊNCIAS HISTÓRICAS REAIS (1241 concursos) ────────
FREQ = {
    1:(43.5,28.6,27.9), 2:(48.5,26.2,25.3), 3:(44.6,26.6,28.8),
    4:(46.4,28.0,25.5), 5:(42.9,27.6,29.6), 6:(44.1,25.0,30.9),
    7:(45.7,29.1,25.2), 8:(46.9,23.9,29.2), 9:(43.8,26.1,30.1),
   10:(42.1,28.8,29.0),11:(44.6,28.4,27.0),12:(42.8,26.8,30.5),
   13:(45.0,22.6,32.3),14:(46.3,26.4,27.3),
}

CLASSICOS = {
    frozenset(["Flamengo","Fluminense"]):25,
    frozenset(["Flamengo","Vasco"]):26,
    frozenset(["Internacional","Gremio"]):45,
    frozenset(["Sao Paulo","Corinthians"]):35,
    frozenset(["Corinthians","Palmeiras"]):27,
    frozenset(["Atletico-MG","Cruzeiro"]):32,
    frozenset(["Bahia","Vitoria"]):34,
    frozenset(["Sport","Nautico"]):30,
}

# Filtros históricos calibrados nos 1.241 concursos
FILTROS = {
    "min_mandantes": 2, "max_mandantes": 11,
    "min_empates": 1,   "max_empates": 8,
    "min_visitantes": 1,"max_visitantes": 9,
}

# ── UTILIDADES ────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def poisson_prob(lam, k):
    return (lam**k * math.exp(-lam)) / math.factorial(k)

def xg_para_prob(xgm=1.55, xgv=1.10):
    p1=px=p2=0
    for gm in range(8):
        for gv in range(8):
            p = poisson_prob(xgm,gm)*poisson_prob(xgv,gv)
            if gm>gv: p1+=p
            elif gm==gv: px+=p
            else: p2+=p
    return p1,px,p2

def odds_para_prob(o1,ox,o2):
    if not all(x and x>1 for x in [o1,ox,o2]):
        return None,None,None
    inv = 1/o1+1/ox+1/o2
    return (1/o1)/inv,(1/ox)/inv,(1/o2)/inv

def is_classico(m,v):
    return frozenset([m,v]) in CLASSICOS

# ── MÓDULO CARTOLA FC ─────────────────────────────────────
CARTOLA_MAP = {
    "Flamengo":"Flamengo","Palmeiras":"Palmeiras",
    "São Paulo":"Sao Paulo","Internacional":"Internacional",
    "Grêmio":"Gremio","Corinthians":"Corinthians",
    "Fluminense":"Fluminense","Botafogo":"Botafogo",
    "Vasco da Gama":"Vasco","Santos":"Santos",
    "Bahia":"Bahia","Athletico Paranaense":"Athletico-PR",
    "Atlético Mineiro":"Atletico-MG","Cruzeiro":"Cruzeiro",
    "Fortaleza":"Fortaleza","Ceará":"Ceara",
    "Sport Recife":"Sport","Coritiba":"Coritiba",
    "Bragantino":"Bragantino","Vitória":"Vitoria",
    "Mirassol":"Mirassol","Juventude":"Juventude",
    "Goiás":"Goias","Cuiabá":"Cuiaba",
}

_cache_cartola = {"data": None, "ts": 0}

def buscar_cartola():
    """Busca dados do Cartola FC com cache de 2h."""
    global _cache_cartola
    if time.time() - _cache_cartola["ts"] < 7200 and _cache_cartola["data"]:
        return _cache_cartola["data"]

    if not HAS_REQUESTS:
        return {}

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 Chrome/120.0.0.0",
            "Accept": "application/json",
            "Origin": "https://cartola.globo.com",
            "Referer": "https://cartola.globo.com/"
        }
        r = req_lib.get(
            "https://api.cartola.globo.com/atletas/mercado",
            headers=headers, timeout=12
        )
        if r.status_code != 200:
            return {}

        data = r.json()
        atletas = data.get("atletas", [])
        clubes  = data.get("clubes", {})

        times = {}
        for a in atletas:
            cid   = str(a.get("clube_id",""))
            cnome = clubes.get(cid,{}).get("nome","")
            tlot  = CARTOLA_MAP.get(cnome, cnome)
            sid   = a.get("status_id",7)

            if tlot not in times:
                times[tlot] = {
                    "titulares":[], "duvidosos":[], "suspensos":[], "lesionados":[],
                    "md3":0, "n_atletas":0
                }

            jogador = {
                "nome":  a.get("apelido",""),
                "media": a.get("media_num",0),
                "preco": a.get("preco_num",0),
            }

            if sid == 7:   times[tlot]["titulares"].append(jogador)
            elif sid == 2: times[tlot]["duvidosos"].append(jogador)
            elif sid == 3: times[tlot]["suspensos"].append(jogador)
            elif sid == 5: times[tlot]["lesionados"].append(jogador)

        # Calcular MD3 (média 3 rodadas dos titulares)
        for t, info in times.items():
            tits = info["titulares"]
            if tits:
                medias = sorted([j["media"] for j in tits], reverse=True)[:11]
                info["md3"]      = round(sum(medias)/len(medias),1) if medias else 0
                info["n_atletas"] = len(tits)

        _cache_cartola = {"data": times, "ts": time.time()}
        return times

    except Exception as e:
        return {}

def ajuste_cartola(time_nome, dados_cartola):
    """Calcula ajuste de score baseado no Cartola."""
    if not dados_cartola or time_nome not in dados_cartola:
        return 0, []

    info    = dados_cartola[time_nome]
    ajuste  = 0
    alertas = []

    # Suspensos e lesionados
    n_fora = len(info["suspensos"]) + len(info["lesionados"])
    if n_fora >= 3:
        ajuste -= 12
        alertas.append(f"{n_fora} titulares fora (suspensão/lesão)")
    elif n_fora == 2:
        ajuste -= 8
        alertas.append(f"{n_fora} titulares fora")
    elif n_fora == 1:
        ajuste -= 5
        alertas.append(f"1 titular fora")

    # Duvidosos
    n_duv = len(info["duvidosos"])
    if n_duv >= 3:
        ajuste -= 6
        alertas.append(f"{n_duv} em dúvida")
    elif n_duv > 0:
        ajuste -= 3
        alertas.append(f"{n_duv} em dúvida")

    # MD3 baixo (time desfalcado)
    if info["md3"] > 0 and info["md3"] < 5.0:
        ajuste -= 4
        alertas.append(f"MD3 baixo: {info['md3']}")

    return ajuste, alertas

# ── MÓDULO SMART MONEY ────────────────────────────────────
_cache_odds_hist = {}

def setup_odds_table():
    try:
        conn = get_db()
        conn.execute('''CREATE TABLE IF NOT EXISTS historico_odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogo_key TEXT, mandante TEXT, visitante TEXT,
            odd1 REAL, oddx REAL, odd2 REAL,
            coletado_em TEXT DEFAULT (datetime('now'))
        )''')
        conn.commit()
        conn.close()
    except:
        pass

def salvar_snapshot_odds(jogos):
    """Salva snapshot atual das odds no banco."""
    try:
        conn = get_db()
        for j in jogos:
            if j.get("odd_1") and j.get("odd_x") and j.get("odd_2"):
                key = f"{j['mandante']}_{j['visitante']}"
                conn.execute('''INSERT INTO historico_odds
                    (jogo_key,mandante,visitante,odd1,oddx,odd2)
                    VALUES (?,?,?,?,?,?)''',
                    (key,j["mandante"],j["visitante"],
                     j["odd_1"],j["odd_x"],j["odd_2"]))
        conn.commit()
        conn.close()
    except:
        pass

def calcular_smart_money(mandante, visitante, o1_atual, ox_atual, o2_atual):
    """Detecta movimento de odds nas últimas 48h."""
    try:
        key  = f"{mandante}_{visitante}"
        dt48 = (datetime.now()-timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        row  = conn.execute('''
            SELECT odd1,oddx,odd2 FROM historico_odds
            WHERE jogo_key=? AND coletado_em < ?
            ORDER BY coletado_em DESC LIMIT 1
        ''', (key, dt48)).fetchone()
        conn.close()

        if not row or not o1_atual:
            return 0, "sem histórico"

        o1_ant, ox_ant, o2_ant = row["odd1"], row["oddx"], row["odd2"]
        ajuste = 0
        sinal  = "estável"

        var1 = (o1_ant - o1_atual) / o1_ant if o1_ant else 0
        var2 = (o2_ant - o2_atual) / o2_ant if o2_ant else 0

        if var1 > 0.12:
            ajuste = 8
            sinal  = f"smart money mandante (odd caiu {var1*100:.0f}%)"
        elif var2 > 0.12:
            ajuste = -8
            sinal  = f"smart money visitante (odd caiu {var2*100:.0f}%)"
        elif abs(var1-var2) > 0.15:
            ajuste = -4
            sinal  = "divergência mercado — incerteza"

        return ajuste, sinal
    except:
        return 0, "erro"

# ── SCORE 0-100 ───────────────────────────────────────────
def calcular_score(p1,px,p2,o1,ox,o2,m,v,
                   aj_cartola=0, aj_smart=0):
    maxp = max(p1,px,p2)
    top2 = sorted([p1,px,p2],reverse=True)
    diff = top2[0]-top2[1]

    score = 50

    # Odds
    if o1 and o1 < 1.50: score += 20
    elif o1 and o1 < 1.80: score += 12
    elif o1 and o1 > 3.0:  score -= 10

    # Probabilidade
    if maxp > 0.60: score += 15
    elif maxp > 0.55: score += 8
    elif maxp < 0.40: score -= 10

    # Divergência (clareza)
    if diff > 0.20: score += 10
    elif diff < 0.08: score -= 10

    # Clássico (aumenta incerteza)
    if is_classico(m,v): score -= 8

    # Ajustes externos
    score += aj_cartola
    score += aj_smart

    return max(0, min(100, score))

def decidir_tipo(score, p1, px, p2):
    fav  = '1' if p1>=px and p1>=p2 else ('X' if px>=p2 else '2')
    top2 = sorted(['1','X','2'],key=lambda x:{'1':p1,'X':px,'2':p2}[x],reverse=True)[:2]

    if score >= 65:
        return 'SIMPLES', fav, score
    elif score >= 45:
        return 'DUPLO', ''.join(sorted(top2)), score
    else:
        return 'TRIPLO', '1X2', score

# ── ANÁLISE COMPLETA DO JOGO ──────────────────────────────
def analisar_jogo(pos, mandante, visitante,
                  o1=0, ox=0, o2=0, dados_cartola=None):
    # Frequência histórica
    f = FREQ.get(pos,(44,27,29))
    p1h,pxh,p2h = f[0]/100, f[1]/100, f[2]/100

    # Poisson
    p1p,pxp,p2p = xg_para_prob()

    # Odds
    p1o,pxo,p2o = odds_para_prob(o1,ox,o2)
    tem_odds = p1o is not None

    # Blend
    if tem_odds:
        p1 = 0.50*p1o+0.25*p1h+0.25*p1p
        px = 0.50*pxo+0.25*pxh+0.25*pxp
        p2 = 0.50*p2o+0.25*p2h+0.25*p2p
    else:
        p1 = 0.60*p1h+0.40*p1p
        px = 0.60*pxh+0.40*pxp
        p2 = 0.60*p2h+0.40*p2p

    # Clássico
    if is_classico(mandante, visitante):
        taxa = CLASSICOS.get(frozenset([mandante,visitante]),30)/100
        diff = taxa - px
        px += diff*0.5; p1 -= diff*0.3; p2 -= diff*0.2

    # Normalizar
    tot = p1+px+p2
    p1/=tot; px/=tot; p2/=tot

    # Ajustes
    aj_cart_m, alertas_m = ajuste_cartola(mandante, dados_cartola)
    aj_cart_v, alertas_v = ajuste_cartola(visitante, dados_cartola)
    aj_cartola = aj_cart_m - (aj_cart_v * 0.5)  # desfalque visitante vale menos

    aj_smart, sinal_smart = calcular_smart_money(mandante,visitante,o1,ox,o2)

    score = calcular_score(p1,px,p2,o1,ox,o2,mandante,visitante,
                           aj_cartola, aj_smart)
    tipo, palpite, _ = decidir_tipo(score, p1, px, p2)

    alertas = []
    if alertas_m: alertas.append(f"Mandante: {'; '.join(alertas_m)}")
    if alertas_v: alertas.append(f"Visitante: {'; '.join(alertas_v)}")
    if sinal_smart != "estável" and sinal_smart != "sem histórico":
        alertas.append(f"Smart Money: {sinal_smart}")

    return {
        "pos": pos,
        "mandante": mandante, "visitante": visitante,
        "p1": round(p1*100,1), "px": round(px*100,1), "p2": round(p2*100,1),
        "odd_1": o1, "odd_x": ox, "odd_2": o2,
        "tipo": tipo, "palpite": palpite, "score": score,
        "classico": is_classico(mandante, visitante),
        "alertas": alertas,
        "cartola_m": {"ajuste": aj_cart_m, "alertas": alertas_m},
        "cartola_v": {"ajuste": aj_cart_v, "alertas": alertas_v},
        "smart_money": {"ajuste": aj_smart, "sinal": sinal_smart},
    }

# ── GERADOR DE VARANDAS COM FILTROS ──────────────────────
def varanda_valida(cartao):
    """Verifica se a varanda passa nos filtros históricos."""
    vals  = list(cartao.values())
    n1    = vals.count('1')
    nx    = vals.count('X')
    n2    = vals.count('2')
    if n1 < FILTROS["min_mandantes"] or n1 > FILTROS["max_mandantes"]: return False
    if nx < FILTROS["min_empates"]   or nx > FILTROS["max_empates"]:   return False
    if n2 < FILTROS["min_visitantes"] or n2 > FILTROS["max_visitantes"]: return False
    return True

def gerar_varandas(jogos, n=33):
    import random
    random.seed(int(time.time()) % 10000)

    fixos   = {j["pos"]: j["palpite"] for j in jogos if j["score"] >= 65}
    incertos= [j for j in jogos if j["score"] < 65]

    varandas = []
    vistos   = set()
    tent     = 0

    while len(varandas) < n and tent < n * 30:
        tent += 1
        cartao = dict(fixos)

        for j in incertos:
            p1,px,p2 = j["p1"]/100, j["px"]/100, j["p2"]/100
            if j["tipo"] == "DUPLO":
                opc = sorted([("1",p1),("X",px),("2",p2)],key=lambda x:-x[1])[:2]
                tot = sum(o[1] for o in opc)
                r   = random.random()*tot
                acum = 0
                esc  = opc[0][0]
                for res,prob in opc:
                    acum += prob
                    if r <= acum: esc=res; break
                cartao[j["pos"]] = esc
            else:
                r = random.random()
                if r < p1: cartao[j["pos"]] = '1'
                elif r < p1+px: cartao[j["pos"]] = 'X'
                else: cartao[j["pos"]] = '2'

        if not varanda_valida(cartao):
            continue

        chave = tuple(cartao.get(i,'?') for i in range(1,15))
        if chave not in vistos:
            vistos.add(chave)
            varandas.append({
                "id": len(varandas)+1,
                "palpites": cartao,
                "string": ''.join(cartao.get(i,'?') for i in range(1,15)),
                "valida": True
            })

    return varandas

# ── GESTÃO DE BANCA ───────────────────────────────────────
def calcular_banca(jogos):
    scores = [j["score"] for j in jogos]
    media  = sum(scores)/len(scores) if scores else 50
    n_s    = sum(1 for j in jogos if j["tipo"]=="SIMPLES")
    n_d    = sum(1 for j in jogos if j["tipo"]=="DUPLO")
    n_t    = sum(1 for j in jogos if j["tipo"]=="TRIPLO")

    if n_s >= 7:
        tipo,inv,nv,obs = "FÁCIL",30,10,"Grade fácil — investimento mínimo"
    elif media >= 58:
        tipo,inv,nv,obs = "MÉDIO",99,33,"Grade equilibrada — padrão"
    else:
        tipo,inv,nv,obs = "DIFÍCIL",198,66,"Grade difícil — prêmio maior"

    return {
        "tipo_concurso":tipo, "investimento_recomendado":inv,
        "n_varandas":nv, "n_secos":n_s, "n_duplos":n_d, "n_triplos":n_t,
        "media_score":round(media,1), "observacao":obs
    }

# ── BUSCAR GRADE (The Odds API) ───────────────────────────
def buscar_grade():
    if not HAS_REQUESTS:
        return []
    try:
        r = req_lib.get(
            "https://api.the-odds-api.com/v4/sports/soccer_brazil_campeonato/odds/",
            params={"apiKey":ODDS_API_KEY,"regions":"eu",
                    "markets":"h2h","oddsFormat":"decimal",
                    "bookmakers":"betano,bet365,pinnacle"},
            timeout=12
        )
        if r.status_code != 200:
            return []

        jogos = []
        for j in r.json():
            home = j.get("home_team","?")
            away = j.get("away_team","?")
            o1=ox=o2=0
            for bk in j.get("bookmakers",[]):
                for mkt in bk.get("markets",[]):
                    if mkt["key"]=="h2h":
                        out = {o["name"]:o["price"] for o in mkt["outcomes"]}
                        if out.get(home) and out.get("Draw") and out.get(away):
                            o1=out[home]; ox=out["Draw"]; o2=out[away]
                            break
                if o1: break
            jogos.append({"mandante":home,"visitante":away,
                          "data":j.get("commence_time",""),
                          "odd_1":o1,"odd_x":ox,"odd_2":o2})
        return jogos[:14]
    except:
        return []

# ── RESULTADO CAIXA ───────────────────────────────────────
def buscar_resultado_caixa(concurso="ultimo"):
    if not HAS_REQUESTS:
        return None
    try:
        r = req_lib.get(
            f"https://api.guidi.dev.br/loteria/loteca/{concurso}",
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        return None
    except:
        return None

# ── BACKTESTING ───────────────────────────────────────────
def backtesting(n=100):
    try:
        conn = get_db()
        rows = conn.execute(f'''
            SELECT posicao,mandante,visitante,resultado,odd_1,odd_x,odd_2
            FROM jogos_loteca WHERE resultado IS NOT NULL
            ORDER BY concurso DESC, posicao
            LIMIT {n*14}
        ''').fetchall()
        conn.close()

        ac_d=tot_d=ac_s=tot_s=ac_t=tot_t=0
        for r in rows:
            a = analisar_jogo(r["posicao"],r["mandante"],r["visitante"],
                              r["odd_1"] or 0,r["odd_x"] or 0,r["odd_2"] or 0)
            res = r["resultado"]
            if a["tipo"]=="SIMPLES":
                tot_s+=1
                if res==a["palpite"]: ac_s+=1
            elif a["tipo"]=="DUPLO":
                tot_d+=1
                if res in a["palpite"]: ac_d+=1
            else:
                tot_t+=1; ac_t+=1

        return {
            "total_jogos": tot_s+tot_d+tot_t,
            "taxa_seco":   round(ac_s/tot_s*100,1) if tot_s else 0,
            "taxa_duplo":  round(ac_d/tot_d*100,1) if tot_d else 0,
            "taxa_triplo": 100.0,
            "acertos_seco":ac_s, "total_seco":tot_s,
            "acertos_duplo":ac_d,"total_duplo":tot_d,
            "acertos_triplo":ac_t,"total_triplo":tot_t,
        }
    except Exception as e:
        return {"erro": str(e)}

# ── ROTAS ─────────────────────────────────────────────────
@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/grade-automatica')
def grade_automatica():
    setup_odds_table()
    jogos_api = buscar_grade()
    dados_cartola = buscar_cartola()

    if not jogos_api:
        return jsonify({"fonte":"manual","status":"sem_grade",
                        "mensagem":"Grade não encontrada. Use /api/analisar-grade.",
                        "cartola_ativo": bool(dados_cartola)})

    salvar_snapshot_odds(jogos_api)

    jogos_analisados = []
    for i,j in enumerate(jogos_api[:14]):
        a = analisar_jogo(i+1, j["mandante"], j["visitante"],
                          j.get("odd_1",0), j.get("odd_x",0), j.get("odd_2",0),
                          dados_cartola)
        a["data"] = j.get("data","")
        jogos_analisados.append(a)

    banca    = calcular_banca(jogos_analisados)
    varandas = gerar_varandas(jogos_analisados, banca["n_varandas"])

    # Resumo Cartola
    cartola_resumo = {}
    if dados_cartola:
        for j in jogos_analisados:
            for time in [j["mandante"], j["visitante"]]:
                if time in dados_cartola:
                    d = dados_cartola[time]
                    cartola_resumo[time] = {
                        "md3": d.get("md3",0),
                        "duvidosos": len(d.get("duvidosos",[])),
                        "suspensos": len(d.get("suspensos",[])),
                        "lesionados": len(d.get("lesionados",[])),
                    }

    return jsonify({
        "fonte": "automatica",
        "timestamp": datetime.now().isoformat(),
        "jogos": jogos_analisados,
        "banca": banca,
        "varandas": varandas[:10],
        "total_varandas": len(varandas),
        "cartola_ativo": bool(dados_cartola),
        "cartola_resumo": cartola_resumo,
        "smart_money_ativo": True,
        "status": "ok"
    })

@app.route('/api/analisar-grade', methods=['POST'])
def analisar_grade():
    data  = request.json or {}
    jogos_input = data.get('jogos',[])
    dados_cartola = buscar_cartola()

    jogos_analisados = []
    for i,j in enumerate(jogos_input[:14]):
        a = analisar_jogo(i+1,
            j.get("mandante","Time A"), j.get("visitante","Time B"),
            j.get("odd_1",0), j.get("odd_x",0), j.get("odd_2",0),
            dados_cartola)
        jogos_analisados.append(a)

    banca    = calcular_banca(jogos_analisados)
    varandas = gerar_varandas(jogos_analisados, banca["n_varandas"])

    return jsonify({"jogos":jogos_analisados,"banca":banca,
                    "varandas":varandas,"total_varandas":len(varandas)})

@app.route('/api/backtesting')
def api_backtesting():
    n = int(request.args.get('n',100))
    return jsonify(backtesting(n))

@app.route('/api/resultado-caixa')
def api_resultado_caixa():
    conc = request.args.get('concurso','ultimo')
    res  = buscar_resultado_caixa(conc)
    return jsonify(res or {"erro":"não encontrado"})

@app.route('/api/historico-concursos')
def historico_concursos():
    try:
        conn = get_db()
        rows = conn.execute('''
            SELECT concurso,ganhadores_13,ganhadores_14,premio_13,premio_14
            FROM concursos ORDER BY concurso DESC LIMIT 50
        ''').fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"erro":str(e)})

@app.route('/api/cartola-status')
def cartola_status():
    dados = buscar_cartola()
    return jsonify({
        "ativo": bool(dados),
        "times": len(dados),
        "atualizado": datetime.fromtimestamp(_cache_cartola["ts"]).isoformat()
                      if _cache_cartola["ts"] else None
    })

@app.route('/api/health')
def health():
    try:
        conn = get_db()
        n = conn.execute('SELECT COUNT(*) n FROM concursos').fetchone()['n']
        conn.close()
        cartola = buscar_cartola()
        return jsonify({
            "status":"ok", "versao":"8.0",
            "concursos": n,
            "cartola": bool(cartola),
            "smart_money": True,
            "filtros_ativos": True,
        })
    except Exception as e:
        return jsonify({"status":"erro","msg":str(e)})

if __name__ == '__main__':
    setup_odds_table()
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port, debug=False)
