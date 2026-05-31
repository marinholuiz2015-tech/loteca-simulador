"""
LOTECA ELITE PRO - app.py v3.0
SOLUCAO DEFINITIVA: HTML embutido no proprio Python.
Nao depende de index.html externo. Zero erro 404.
"""

import os
import math
import logging
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)
CORS(app)

FDATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")
ODDS_KEY  = os.getenv("ODDS_API_KEY", "")

LIGAS = {
    "brasileirao":   {"codigo": "BSA",  "nome": "Brasileirao Serie A",  "pais": "Brasil"},
    "copa_brasil":   {"codigo": "CB",   "nome": "Copa do Brasil",        "pais": "Brasil"},
    "libertadores":  {"codigo": "CLI",  "nome": "Copa Libertadores",     "pais": "Sul-America"},
    "serie_b":       {"codigo": "BSB",  "nome": "Brasileirao Serie B",   "pais": "Brasil"},
    "premier":       {"codigo": "PL",   "nome": "Premier League",        "pais": "Inglaterra"},
    "la_liga":       {"codigo": "PD",   "nome": "La Liga",               "pais": "Espanha"},
    "serie_a_it":    {"codigo": "SA",   "nome": "Serie A Italia",        "pais": "Italia"},
    "bundesliga":    {"codigo": "BL1",  "nome": "Bundesliga",            "pais": "Alemanha"},
    "champions":     {"codigo": "CL",   "nome": "Champions League",      "pais": "Europa"},
    "copa_do_mundo": {"codigo": "WC",   "nome": "Copa do Mundo",         "pais": "Mundial"},
}

HTML_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Loteca Elite Pro</title>
<style>
:root{--verde:#1a7a3c;--verde2:#22a04e;--ouro:#f0c040;--escuro:#0f1c14;--card:#162b1e;--borda:#2a4a34;--texto:#e8f5ec;--cinza:#8aaa94;--seco:#22c55e;--duplo:#f0c040;--triplo:#ef4444}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--escuro);color:var(--texto);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}
header{background:linear-gradient(135deg,#0b1a0f,#1a3a24);border-bottom:2px solid var(--ouro);padding:18px 32px;display:flex;align-items:center;gap:16px}
.logo-icon{width:44px;height:44px;background:var(--ouro);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;color:#0f1c14}
.logo-text h1{font-size:20px;font-weight:800;letter-spacing:1px}
.logo-text p{font-size:11px;color:var(--ouro);letter-spacing:2px;text-transform:uppercase}
.status-badge{margin-left:auto;background:rgba(34,160,78,.2);border:1px solid var(--verde2);border-radius:20px;padding:4px 14px;font-size:12px;color:var(--verde2)}
main{max-width:1200px;margin:0 auto;padding:32px 24px}
.controles{background:var(--card);border:1px solid var(--borda);border-radius:14px;padding:24px;margin-bottom:28px;display:grid;grid-template-columns:1fr 1fr auto auto;gap:16px;align-items:end}
.campo label{display:block;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--cinza);margin-bottom:6px}
select,input[type=number]{width:100%;background:#0f1c14;border:1px solid var(--borda);border-radius:8px;color:var(--texto);padding:10px 14px;font-size:14px;outline:none}
select:focus,input:focus{border-color:var(--verde2)}
.btn{padding:11px 24px;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;border:none;transition:all .2s;white-space:nowrap}
.btn-primary{background:var(--verde2);color:#fff}
.btn-primary:hover{background:#28c060;transform:translateY(-1px)}
.btn-primary:disabled{background:var(--borda);cursor:not-allowed;transform:none}
.btn-secondary{background:transparent;border:1px solid var(--borda);color:var(--cinza)}
.btn-secondary:hover{border-color:var(--verde2);color:var(--verde2)}
.sumario{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:28px}
.card-stat{background:var(--card);border:1px solid var(--borda);border-radius:12px;padding:18px;text-align:center}
.card-stat .valor{font-size:32px;font-weight:800;line-height:1;margin-bottom:4px}
.card-stat .label{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--cinza)}
.card-stat.seco .valor{color:var(--seco)}
.card-stat.duplo .valor{color:var(--duplo)}
.card-stat.triplo .valor{color:var(--triplo)}
.card-stat.total .valor{color:var(--ouro)}
.card-stat.custo .valor{font-size:22px;color:#60a5fa}
.aviso{background:rgba(240,192,64,.1);border:1px solid rgba(240,192,64,.4);border-radius:10px;padding:12px 18px;font-size:13px;color:var(--ouro);margin-bottom:20px;display:none}
.aviso.visivel{display:block}
.grade-header{display:grid;grid-template-columns:32px 1fr 80px 80px 80px 90px 80px;gap:8px;padding:10px 16px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--cinza);border-bottom:1px solid var(--borda);margin-bottom:8px}
.jogo-card{background:var(--card);border:1px solid var(--borda);border-radius:10px;padding:14px 16px;margin-bottom:8px;display:grid;grid-template-columns:32px 1fr 80px 80px 80px 90px 80px;gap:8px;align-items:center;transition:border-color .2s}
.jogo-card:hover{border-color:var(--verde2)}
.jogo-num{font-size:13px;font-weight:700;color:var(--cinza);text-align:center}
.jogo-times .mandante{font-weight:700;font-size:14px}
.jogo-times .vs{font-size:11px;color:var(--cinza);margin:2px 0}
.jogo-times .visitante{font-size:13px;color:#b0c8ba}
.prob{text-align:center;font-size:13px;font-weight:700;padding:5px 8px;border-radius:6px;background:rgba(255,255,255,.04)}
.prob.maior{background:rgba(34,160,78,.25);color:#6ee7a0}
.classificacao{text-align:center;font-size:12px;font-weight:800;letter-spacing:1px;padding:5px 10px;border-radius:20px}
.class-SECO{background:rgba(34,197,94,.2);color:var(--seco);border:1px solid rgba(34,197,94,.4)}
.class-DUPLO{background:rgba(240,192,64,.2);color:var(--duplo);border:1px solid rgba(240,192,64,.4)}
.class-TRIPLO{background:rgba(239,68,68,.2);color:var(--triplo);border:1px solid rgba(239,68,68,.4)}
.conf-bar{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--cinza)}
.conf-bar .barra{flex:1;height:5px;background:var(--borda);border-radius:3px;overflow:hidden}
.conf-bar .fill{height:100%;background:var(--verde2);border-radius:3px}
.loading{text-align:center;padding:60px;color:var(--cinza);display:none}
.loading.visivel{display:block}
.spinner{width:40px;height:40px;border:3px solid var(--borda);border-top-color:var(--verde2);border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 16px}
@keyframes spin{to{transform:rotate(360deg)}}
.erro{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.4);border-radius:10px;padding:16px 20px;color:#fca5a5;display:none;margin-bottom:20px}
.erro.visivel{display:block}
.vazio{text-align:center;padding:60px;color:var(--cinza)}
.vazio .icon{font-size:48px;margin-bottom:16px}
.vazio h3{font-size:18px;margin-bottom:8px;color:var(--texto)}
@media(max-width:900px){.controles{grid-template-columns:1fr 1fr}.sumario{grid-template-columns:repeat(3,1fr)}.grade-header{display:none}.jogo-card{grid-template-columns:24px 1fr}.jogo-card>*:not(.jogo-num):not(.jogo-times):not(.classificacao){display:none}}
</style>
</head>
<body>
<header>
  <div class="logo-icon">L</div>
  <div class="logo-text"><h1>LOTECA ELITE PRO</h1><p>Motor Preditivo v3.0</p></div>
  <span class="status-badge" id="badgeStatus">Carregando...</span>
</header>
<main>
  <div class="controles">
    <div class="campo"><label>Liga</label><select id="selLiga"><option value="">Carregando...</option></select></div>
    <div class="campo"><label>Janela de dias</label><input type="number" id="inputDias" value="14" min="1" max="60"></div>
    <button class="btn btn-primary" id="btnBuscar" onclick="buscarGrade()">Analisar Grade</button>
    <button class="btn btn-secondary" onclick="limparGrade()">Limpar</button>
  </div>
  <div class="aviso" id="avisoSimulado">DADOS SIMULADOS - Configure FOOTBALL_DATA_KEY no Render para jogos reais.</div>
  <div class="erro" id="painelErro"></div>
  <div class="sumario" id="sumario" style="display:none">
    <div class="card-stat total"><div class="valor" id="statTotal">0</div><div class="label">Jogos</div></div>
    <div class="card-stat seco"><div class="valor" id="statSecos">0</div><div class="label">Secos</div></div>
    <div class="card-stat duplo"><div class="valor" id="statDuplos">0</div><div class="label">Duplos</div></div>
    <div class="card-stat triplo"><div class="valor" id="statTriplos">0</div><div class="label">Triplos</div></div>
    <div class="card-stat custo"><div class="valor" id="statCusto">R$0</div><div class="label">Custo estimado</div></div>
  </div>
  <div class="loading" id="loading"><div class="spinner"></div><p>Buscando jogos e calculando probabilidades...</p></div>
  <div id="gradeContainer">
    <div class="vazio"><div class="icon">&#x26BD;</div><h3>Selecione uma liga e clique em Analisar</h3><p>O sistema buscara os proximos jogos automaticamente.</p></div>
  </div>
</main>
<script>
async function init(){
  try{const r=await fetch('/api/status');const d=await r.json();const b=document.getElementById('badgeStatus');b.textContent='Online v'+(d.versao||'3.0');b.style.color='#22c55e';}catch{document.getElementById('badgeStatus').textContent='Offline';}
  try{const r=await fetch('/api/ligas');const d=await r.json();const sel=document.getElementById('selLiga');sel.innerHTML='';d.ligas.forEach(function(l){var o=document.createElement('option');o.value=l.key;o.textContent=l.nome+' ('+l.pais+')';if(l.key==='brasileirao')o.selected=true;sel.appendChild(o);});}catch(e){console.error(e);}
}
async function buscarGrade(){
  var liga=document.getElementById('selLiga').value;
  var dias=document.getElementById('inputDias').value||14;
  if(!liga){mostrarErro('Selecione uma liga.');return;}
  setLoading(true);limparResultados();
  try{
    var r=await fetch('/api/grade-automatica?liga='+liga+'&dias='+dias+'&max=14');
    var d=await r.json();
    if(d.erro){mostrarErro(d.erro);return;}
    if(d.simulado)document.getElementById('avisoSimulado').classList.add('visivel');
    renderSumario(d);renderGrade(d.jogos);
  }catch(e){mostrarErro('Erro ao conectar com o servidor.');}
  finally{setLoading(false);}
}
function renderSumario(d){
  document.getElementById('sumario').style.display='grid';
  document.getElementById('statTotal').textContent=d.total;
  document.getElementById('statSecos').textContent=d.secos;
  document.getElementById('statDuplos').textContent=d.duplos;
  document.getElementById('statTriplos').textContent=d.triplos;
  document.getElementById('statCusto').textContent='R$ '+(d.custo_estimado_reais||0).toFixed(2);
}
function renderGrade(jogos){
  var c=document.getElementById('gradeContainer');
  if(!jogos||jogos.length===0){c.innerHTML='<div class="vazio"><div class="icon">&#x1F4ED;</div><h3>Nenhum jogo encontrado</h3><p>Tente aumentar a janela de dias.</p></div>';return;}
  var header='<div class="grade-header"><div>#</div><div>Confronto</div><div style="text-align:center">P1</div><div style="text-align:center">PX</div><div style="text-align:center">P2</div><div style="text-align:center">Tipo</div><div style="text-align:center">Confianca</div></div>';
  var cards=jogos.map(function(j,i){
    var p=j.probabilidades||{p1:.33,px:.33,p2:.33};
    var mx=Math.max(p.p1,p.px,p.p2);
    var conf=j.confianca||0;
    var cl=j.classificacao||'TRIPLO';
    var dt=j.data_utc?new Date(j.data_utc).toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'}):'';
    return '<div class="jogo-card"><div class="jogo-num">'+(i+1)+'</div>'
      +'<div class="jogo-times"><div class="mandante">'+(j.mandante||'Time 1')+'</div><div class="vs">x '+dt+'</div><div class="visitante">'+(j.visitante||'Time 2')+'</div></div>'
      +'<div class="prob'+(p.p1===mx?' maior':'')+'">'+pct(p.p1)+'</div>'
      +'<div class="prob'+(p.px===mx?' maior':'')+'">'+pct(p.px)+'</div>'
      +'<div class="prob'+(p.p2===mx?' maior':'')+'">'+pct(p.p2)+'</div>'
      +'<div><span class="classificacao class-'+cl+'">'+cl+'</span></div>'
      +'<div class="conf-bar"><div class="barra"><div class="fill" style="width:'+conf+'%"></div></div><span>'+conf.toFixed(0)+'%</span></div>'
      +'</div>';
  }).join('');
  c.innerHTML=header+cards;
}
function pct(v){return Math.round((v||0)*100)+'%';}
function setLoading(on){document.getElementById('loading').classList.toggle('visivel',on);document.getElementById('btnBuscar').disabled=on;}
function mostrarErro(msg){var el=document.getElementById('painelErro');el.textContent='ERRO: '+msg;el.classList.add('visivel');}
function limparResultados(){document.getElementById('painelErro').classList.remove('visivel');document.getElementById('avisoSimulado').classList.remove('visivel');document.getElementById('sumario').style.display='none';document.getElementById('gradeContainer').innerHTML='<div class="vazio"><div class="icon">&#x26BD;</div><h3>Carregando...</h3></div>';}
function limparGrade(){document.getElementById('painelErro').classList.remove('visivel');document.getElementById('avisoSimulado').classList.remove('visivel');document.getElementById('sumario').style.display='none';document.getElementById('gradeContainer').innerHTML='<div class="vazio"><div class="icon">&#x26BD;</div><h3>Selecione uma liga e clique em Analisar</h3><p>O sistema buscara os proximos jogos automaticamente.</p></div>';}
init();
</script>
</body>
</html>"""


# --- Funcoes auxiliares ---

def _poisson_prob(lam, k):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def calcular_probabilidades_poisson(media_gols_casa, media_gols_fora,
                                    media_sofridos_casa=None, media_sofridos_fora=None,
                                    max_gols=7):
    defesa_casa = media_sofridos_casa if media_sofridos_casa else media_gols_fora * 0.9
    defesa_fora = media_sofridos_fora if media_sofridos_fora else media_gols_casa * 0.9
    lc = max(0.3, min(media_gols_casa * (defesa_fora / max(0.5, (media_gols_fora + defesa_casa) / 2)) * 1.15, 5.0))
    lf = max(0.3, min(media_gols_fora * (defesa_casa / max(0.5, (media_gols_casa + defesa_fora) / 2)) * 0.90, 5.0))
    p1 = px = p2 = 0.0
    for i in range(max_gols + 1):
        for j in range(max_gols + 1):
            p = _poisson_prob(lc, i) * _poisson_prob(lf, j)
            if i > j:
                p1 += p
            elif i == j:
                px += p
            else:
                p2 += p
    total = p1 + px + p2 or 1
    return {"p1": round(p1/total, 4), "px": round(px/total, 4), "p2": round(p2/total, 4)}


def classificar_jogo(probs, limiar_seco=0.60):
    vals = sorted([probs["p1"], probs["px"], probs["p2"]], reverse=True)
    if vals[0] >= limiar_seco:
        return "SECO"
    elif vals[0] + vals[1] >= 0.75:
        return "DUPLO"
    return "TRIPLO"


def resultado_mais_provavel(probs):
    p1, px, p2 = probs["p1"], probs["px"], probs["p2"]
    if p1 >= px and p1 >= p2:
        return "1"
    elif px >= p1 and px >= p2:
        return "X"
    return "2"


def buscar_jogos_liga(liga_key, dias_frente=14):
    liga = LIGAS.get(liga_key)
    if not liga:
        raise ValueError(f"Liga '{liga_key}' nao encontrada.")
    if not FDATA_KEY:
        logger.warning("FOOTBALL_DATA_KEY nao configurada - usando simulado")
        return _jogos_simulados(liga_key)
    hoje = datetime.now(timezone.utc)
    ate = hoje + timedelta(days=dias_frente)
    url = (f"https://api.football-data.org/v4/competitions/{liga['codigo']}/matches"
           f"?status=SCHEDULED&dateFrom={hoje.strftime('%Y-%m-%d')}&dateTo={ate.strftime('%Y-%m-%d')}")
    try:
        resp = requests.get(url, headers={"X-Auth-Token": FDATA_KEY}, timeout=10)
        if resp.status_code in (401, 403, 429):
            return _jogos_simulados(liga_key)
        resp.raise_for_status()
        jogos = []
        for m in resp.json().get("matches", []):
            home = m.get("homeTeam", {}).get("shortName") or m.get("homeTeam", {}).get("name", "?")
            away = m.get("awayTeam", {}).get("shortName") or m.get("awayTeam", {}).get("name", "?")
            jogos.append({"id": str(m.get("id", "")), "mandante": home, "visitante": away,
                          "data_utc": m.get("utcDate", ""), "liga": liga["nome"], "liga_key": liga_key})
        return jogos
    except Exception as e:
        logger.error(f"Erro API: {e}")
        return _jogos_simulados(liga_key)


def _jogos_simulados(liga_key):
    base = {
        "brasileirao": [("Flamengo", "Palmeiras"), ("Sao Paulo", "Corinthians"),
                        ("Botafogo", "Fluminense"), ("Cruzeiro", "Atletico MG"),
                        ("Gremio", "Internacional"), ("Santos", "Vasco"),
                        ("Fortaleza", "Ceara"), ("Bahia", "Vitoria"),
                        ("Bragantino", "Mirassol"), ("Cuiaba", "Goias")],
        "libertadores": [("Flamengo", "River Plate"), ("Palmeiras", "Boca Juniors"),
                         ("Botafogo", "Penharol"), ("Atletico MG", "Nacional UY")],
        "champions":    [("Real Madrid", "Man City"), ("Bayern", "PSG"),
                         ("Arsenal", "Barcelona"), ("Liverpool", "Inter")],
    }
    pares = base.get(liga_key, base["brasileirao"])
    hoje = datetime.now(timezone.utc)
    return [{"id": f"sim_{i}", "mandante": h, "visitante": a,
             "data_utc": (hoje + timedelta(days=i % 7)).isoformat(),
             "liga": LIGAS.get(liga_key, {}).get("nome", liga_key),
             "liga_key": liga_key, "_simulado": True}
            for i, (h, a) in enumerate(pares)]


def _medias_padrao_liga(liga_key):
    defaults = {
        "brasileirao":  {"media_gols_casa": 1.55, "media_gols_fora": 1.10, "media_sofridos_casa": 1.10, "media_sofridos_fora": 1.55},
        "libertadores": {"media_gols_casa": 1.45, "media_gols_fora": 0.95, "media_sofridos_casa": 0.95, "media_sofridos_fora": 1.45},
        "champions":    {"media_gols_casa": 1.80, "media_gols_fora": 1.20, "media_sofridos_casa": 1.20, "media_sofridos_fora": 1.80},
        "premier":      {"media_gols_casa": 1.75, "media_gols_fora": 1.30, "media_sofridos_casa": 1.30, "media_sofridos_fora": 1.75},
        "la_liga":      {"media_gols_casa": 1.65, "media_gols_fora": 1.10, "media_sofridos_casa": 1.10, "media_sofridos_fora": 1.65},
        "serie_a_it":   {"media_gols_casa": 1.50, "media_gols_fora": 1.00, "media_sofridos_casa": 1.00, "media_sofridos_fora": 1.50},
        "bundesliga":   {"media_gols_casa": 1.90, "media_gols_fora": 1.35, "media_sofridos_casa": 1.35, "media_sofridos_fora": 1.90},
    }
    return defaults.get(liga_key, defaults["brasileirao"])


def analisar_jogo(jogo, media_gols_casa=1.5, media_gols_fora=1.1,
                  media_sofridos_casa=1.2, media_sofridos_fora=1.4):
    probs = calcular_probabilidades_poisson(media_gols_casa, media_gols_fora,
                                            media_sofridos_casa, media_sofridos_fora)
    classificacao = classificar_jogo(probs)
    vals = sorted([probs["p1"], probs["px"], probs["p2"]], reverse=True)
    return {**jogo, "probabilidades": probs, "classificacao": classificacao,
            "resultado": resultado_mais_provavel(probs),
            "confianca": round((vals[0] - vals[1]) * 100, 1),
            "odds": None, "metodo": "poisson_v1"}


# --- Rotas ---

@app.route("/")
def index():
    return Response(HTML_PAGE, mimetype="text/html; charset=utf-8")


@app.route("/api/ligas")
def listar_ligas():
    return jsonify({"ligas": [{"key": k, "nome": v["nome"], "pais": v["pais"]} for k, v in LIGAS.items()]})


@app.route("/api/jogos")
def listar_jogos():
    liga_key = request.args.get("liga", "brasileirao")
    dias = int(request.args.get("dias", 14))
    try:
        jogos = buscar_jogos_liga(liga_key, dias_frente=dias)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    return jsonify({"liga": LIGAS.get(liga_key, {}).get("nome", liga_key),
                    "total": len(jogos), "jogos": jogos,
                    "simulado": any(j.get("_simulado") for j in jogos)})


@app.route("/api/analisar", methods=["POST"])
def analisar_grade():
    body = request.get_json(silent=True) or {}
    jogos_input = body.get("jogos", [])
    if not jogos_input:
        return jsonify({"erro": "Envie ao menos 1 jogo"}), 400
    resultados = [analisar_jogo(j,
                                float(j.get("media_gols_casa", 1.50)),
                                float(j.get("media_gols_fora", 1.10)),
                                float(j.get("media_sofridos_casa", 1.20)),
                                float(j.get("media_sofridos_fora", 1.40)))
                  for j in jogos_input]
    secos   = sum(1 for r in resultados if r["classificacao"] == "SECO")
    duplos  = sum(1 for r in resultados if r["classificacao"] == "DUPLO")
    triplos = sum(1 for r in resultados if r["classificacao"] == "TRIPLO")
    return jsonify({"total": len(resultados), "secos": secos, "duplos": duplos, "triplos": triplos,
                    "custo_estimado_reais": round(3.0 * (2 ** duplos) * (3 ** triplos) / 100, 2),
                    "jogos": resultados})


@app.route("/api/grade-automatica")
def grade_automatica():
    liga_key  = request.args.get("liga", "brasileirao")
    dias      = int(request.args.get("dias", 14))
    max_jogos = int(request.args.get("max", 14))
    try:
        jogos_raw = buscar_jogos_liga(liga_key, dias_frente=dias)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    jogos_para_analisar = jogos_raw[:max_jogos]
    resultados = [analisar_jogo(j, **_medias_padrao_liga(liga_key)) for j in jogos_para_analisar]
    secos   = sum(1 for r in resultados if r["classificacao"] == "SECO")
    duplos  = sum(1 for r in resultados if r["classificacao"] == "DUPLO")
    triplos = sum(1 for r in resultados if r["classificacao"] == "TRIPLO")
    return jsonify({"liga": LIGAS.get(liga_key, {}).get("nome", liga_key),
                    "total": len(resultados), "secos": secos, "duplos": duplos, "triplos": triplos,
                    "custo_estimado_reais": round(3.0 * (2 ** duplos) * (3 ** triplos) / 100, 2),
                    "jogos": resultados,
                    "simulado": any(j.get("_simulado") for j in jogos_para_analisar)})


@app.route("/api/status")
def status():
    return jsonify({"status": "online", "versao": "3.0-camada1",
                    "ligas_suportadas": len(LIGAS),
                    "integracoes": {
                        "football_data_org": "configurada" if FDATA_KEY else "ausente (simulado)",
                        "the_odds_api": "configurada" if ODDS_KEY else "ausente"},
                    "proximas_camadas": ["Camada 2: Poisson com historico real",
                                         "Camada 3: xG, Cartola, Smart Money"]})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")
