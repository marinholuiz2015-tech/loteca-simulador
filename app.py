"""
Loteca Elite Pro — app.py v11.13
Mudança desta sessão, depois da v11.12:

- Dois novos endpoints de diagnóstico, só-leitura, pra investigar a
  discrepância encontrada em produção (16.778 jogos / 632 concursos =
  26,5 jogos/concurso, muito acima dos 14 esperados):
  /api/diagnostico-concursos: conta jogos por concurso, mostra quantos
  têm exatamente 14 (válidos), menos de 13 (incompletos, descartados
  pelo backtest) e mais de 14 (possível duplicação, mesmo padrão do
  bug documentado no concurso 1266). Testado com dado sintético
  reproduzindo os três cenários misturados.
  /api/verificar-ambiguidade-residual: checa ATHLETICO/GUARANI (citados
  como pendência de baixo risco na sessão de desambiguação) e qualquer
  nome sem sufixo de UF com muita frequência -- candidato a ambiguidade
  não resolvida. Testado, detecta corretamente nomes genéricos sem
  sufixo e ignora os já desambiguados.
  Motivação: evitar rodar scripts locais que exigem colar a senha do
  banco no terminal/chat -- os dois fazem a mesma investigação direto
  em produção, só acessando uma URL no navegador, com a conexão já
  configurada com segurança via variável de ambiente do Render.

Loteca Elite Pro — app.py v11.12
Mudança desta sessão (12/09/2026), depois da v11.11:

25) CORREÇÃO EM backtest_p1314_seco() -- achado ao rodar /api/backtest-
    p1314?comparar=1 em produção pós-v11.11: "concursos_avaliados": 632,
    exatamente o número que já estava sinalizado como pendência não
    investigada no checklist original ("confirmar por que só 632 de
    ~1268 concursos são avaliados no backtest de produção").
    Causa raiz encontrada: a query decidia UMA VEZ SÓ, pra tabela
    inteira, qual fonte de resultado usar --
        if col_resultado: WHERE resultado IN ('1','X','2')
        elif tem_gols: (calcula via gols)
    Como a coluna "resultado" EXISTE no schema, o primeiro branch sempre
    era escolhido -- e o filtro "WHERE resultado IN (...)" descartava
    SILENCIOSAMENTE toda linha com resultado NULL, mesmo quando
    gols_casa/gols_fora dessa mesma linha estavam preenchidos e dariam
    pra calcular o resultado do mesmo jeito. Ou seja: o fallback pra
    gols só existia pra tabelas SEM a coluna resultado -- nunca era
    usado linha a linha dentro de uma tabela que já tem a coluna, mesmo
    quando ela está parcialmente vazia.
    Corrigido: a decisão agora é POR LINHA, não pela tabela inteira.
    Busca resultado E gols juntos (quando ambas as colunas existem),
    usa "resultado" quando ele já vem válido ('1'/'X'/'2'), cai pro
    cálculo via gols quando "resultado" vier NULL/vazio, e só descarta
    a linha se nenhuma das duas fontes estiver disponível. Loga quantas
    linhas vieram de cada fonte (n_via_resultado / n_via_gols /
    n_descartadas) -- nunca mais silencioso sobre o tamanho do descarte.
    PRÓXIMO PASSO OBRIGATÓRIO: rodar /api/backtest-p1314?comparar=1 de
    novo em produção depois de subir essa versão, conferir se
    "concursos_avaliados" sobe de 632 pra perto do total real de
    concursos (~1270), e tratar o novo freq_13_mais/freq_14 como o
    baseline oficial (o anterior, medido sobre só metade do histórico,
    não deve ser usado pra decisão nenhuma).

Herda tudo da v11.11 e anteriores (changelog completo mantido no
histórico do repositório) -- motor Elo iterativo (K=30, HOME_ADV=75),
bucket empírico com suavização Bayesiana e peso de recência, filtro de
jogos -INDEFINIDO, baseline real 13 secos + 1 duplo, odds de mercado
conectadas via The Odds API (peso do blend ainda não calibrado),
cache de resultados via GitHub Actions para contornar bloqueio 403
da Caixa, placar ao vivo informativo via API-Football.

Variáveis de ambiente no Render:
  RAPIDAPI_KEY  → API-Football (fixtures, lesões, escalação) -- opcional
  ODDS_API_KEY  → The Odds API (odds de mercado Bet365/Pinnacle) -- opcional
  DATABASE_URL  → PostgreSQL (se ausente usa SQLite local) -- recomendado
"""

import os, math, sqlite3, logging, requests, re, time, unicodedata
from datetime import datetime, timezone
from collections import defaultdict
from flask import Flask, jsonify, request
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("loteca")

app = Flask(__name__)
CORS(app)

# ─── Variáveis de ambiente ────────────────────────────────────
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "") or os.getenv("APIFOOTBALL_KEY", "")
ODDS_KEY     = os.getenv("ODDS_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG       = DATABASE_URL.startswith("postgres")

GITHUB_REPO_CACHE   = os.getenv("GITHUB_REPO_CACHE", "marinholuiz2015-tech/loteca-simulador")
GITHUB_BRANCH_CACHE = os.getenv("GITHUB_BRANCH_CACHE", "main")

APIF_HOST = "free-api-live-football-data.p.rapidapi.com"
APIF_BASE = f"https://{APIF_HOST}"
URL_CEF   = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca"

H2H_MIN      = 20
SHRINKAGE_K  = 15

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
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS historico (
            id """ + ("SERIAL" if USE_PG else "INTEGER") + """ PRIMARY KEY""" +
            ("" if USE_PG else " AUTOINCREMENT") + """,
            concurso INTEGER, mandante TEXT, visitante TEXT,
            prob_1 REAL, prob_x REAL, prob_2 REAL,
            score REAL, tipo_grade TEXT, coluna TEXT,
            resultado TEXT, acertou INTEGER,
            odd_1 REAL, odd_x REAL, odd_2 REAL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit(); conn.close()
        log.info("Banco OK: %s", "PostgreSQL" if USE_PG else "SQLite")
    except Exception as e:
        log.warning("Banco indisponível: %s", e)

_SCHEMA_CACHE = {"ts": 0, "info": None}

def detectar_schema_jogos():
    if time.time() - _SCHEMA_CACHE["ts"] < 300 and _SCHEMA_CACHE["info"]:
        return _SCHEMA_CACHE["info"]
    info = {"tabela": None, "col_gm": None, "col_gv": None,
            "col_m": None, "col_v": None,
            "col_liga": None, "col_concurso": "concurso", "existe": False}
    try:
        conn = get_conn(); cur = conn.cursor()
        if USE_PG:
            cur.execute("""SELECT table_name FROM information_schema.tables
                           WHERE table_schema='public'""")
        else:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = [r[0] for r in cur.fetchall()]
        for candidata in ["jogos_loteca", "jogos_historico", "jogos"]:
            if candidata in tabelas:
                info["tabela"] = candidata
                break
        if info["tabela"]:
            if USE_PG:
                cur.execute("""SELECT column_name FROM information_schema.columns
                               WHERE table_name=%s""", (info["tabela"],))
            else:
                cur.execute(f"PRAGMA table_info({info['tabela']})")
                cols_raw = cur.fetchall()
                cur = [(r[1],) for r in cols_raw]
            cols = [r[0] for r in (cur if isinstance(cur, list) else cur.fetchall())]
            info["col_m"] = next((c for c in
                ["time_casa_normalizado", "mandante_normalizado", "time_casa", "mandante"]
                if c in cols), None)
            info["col_v"] = next((c for c in
                ["time_fora_normalizado", "visitante_normalizado", "time_fora", "visitante"]
                if c in cols), None)
            info["col_gm"] = next((c for c in ["gols_casa", "gols_m", "gols_mandante"] if c in cols), None)
            info["col_gv"] = next((c for c in ["gols_fora", "gols_v", "gols_visitante"] if c in cols), None)
            info["col_liga"] = "liga" if "liga" in cols else ("campeonato" if "campeonato" in cols else None)
            info["existe"] = bool(info["col_m"] and info["col_v"])
            if info["tabela"] and not info["existe"]:
                log.warning("Tabela %s existe mas não achei colunas de time reconhecíveis (colunas disponíveis: %s)", info["tabela"], cols)
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

def _parse_num(v):
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).strip())
    except (ValueError, TypeError): return None

def buscar_h2h_real(mandante, visitante):
    schema = detectar_schema_jogos()
    if not schema["existe"]: return None
    m, v = mandante.upper().strip(), visitante.upper().strip()
    try:
        conn = get_conn(); cur = conn.cursor()
        ph = _ph()
        cur.execute(f"""
            SELECT resultado, COUNT(*) FROM {schema['tabela']}
            WHERE UPPER(TRIM({schema['col_m']}))={ph} AND UPPER(TRIM({schema['col_v']}))={ph}
              AND resultado IN ('1','X','2')
            GROUP BY resultado
        """, (m, v))
        contagem = dict(cur.fetchall())
        conn.close()
        total = sum(contagem.values())
        if total < H2H_MIN:
            return None
        return {
            "1": round(contagem.get("1", 0) / total, 4),
            "X": round(contagem.get("X", 0) / total, 4),
            "2": round(contagem.get("2", 0) / total, 4),
            "n": total,
        }
    except Exception as e:
        log.warning("buscar_h2h_real: %s", e)
        return None

def buscar_media_liga_gols(liga):
    schema = detectar_schema_jogos()
    if schema["existe"] and schema["col_gm"] and schema["col_gv"] and schema["col_liga"]:
        try:
            conn = get_conn(); cur = conn.cursor()
            ph = _ph()
            cur.execute(f"""
                SELECT {schema['col_gm']}, {schema['col_gv']} FROM {schema['tabela']}
                WHERE {schema['col_liga']}={ph}
            """, (liga,))
            linhas = cur.fetchall()
            conn.close()
            soma_gm, soma_gv, n = 0.0, 0.0, 0
            for gm, gv in linhas:
                gm2, gv2 = _parse_num(gm), _parse_num(gv)
                if gm2 is None or gv2 is None: continue
                soma_gm += gm2; soma_gv += gv2; n += 1
            if n >= 10:
                return {"casa": round(soma_gm/n, 3), "fora": round(soma_gv/n, 3)}
        except Exception as e:
            log.warning("buscar_media_liga_gols: %s", e)
    return MEDIA_GOLS.get(liga, {"casa": 1.40, "fora": 1.05})

def buscar_medias_gols_real(time_nome, mandante=True, liga="_default"):
    schema = detectar_schema_jogos()
    if not schema["existe"] or not schema["col_gm"] or not schema["col_gv"]:
        return None
    t = time_nome.upper().strip()
    campo_nome = schema["col_m"] if mandante else schema["col_v"]
    campo_pro  = schema["col_gm"] if mandante else schema["col_gv"]
    campo_contra = schema["col_gv"] if mandante else schema["col_gm"]
    try:
        conn = get_conn(); cur = conn.cursor()
        ph = _ph()
        cur.execute(f"""
            SELECT {campo_pro}, {campo_contra} FROM {schema['tabela']}
            WHERE UPPER(TRIM({campo_nome}))={ph}
        """, (t,))
        linhas = cur.fetchall()
        conn.close()
        gols_pro, gols_contra, n = 0, 0, 0
        for gp, gc in linhas:
            gp2, gc2 = _parse_gol(gp), _parse_gol(gc)
            if gp2 is None or gc2 is None: continue
            gols_pro += gp2; gols_contra += gc2; n += 1
        if n < 1:
            return None
        media_pro_time    = gols_pro / n
        media_contra_time = gols_contra / n

        liga_ref = buscar_media_liga_gols(liga)
        prior_pro    = liga_ref["casa"] if mandante else liga_ref["fora"]
        prior_contra = liga_ref["fora"] if mandante else liga_ref["casa"]

        peso = n / (n + SHRINKAGE_K)
        gols_pro_shrink    = peso*media_pro_time    + (1-peso)*prior_pro
        gols_contra_shrink = peso*media_contra_time + (1-peso)*prior_contra

        return {
            "gols_pro": round(gols_pro_shrink, 3),
            "gols_contra": round(gols_contra_shrink, 3),
            "n": n, "peso_time": round(peso, 3),
        }
    except Exception as e:
        log.warning("buscar_medias_gols_real: %s", e)
        return None

ELO_K        = 30
ELO_HOME_ADV = 75
ELO_CACHE_TTL = 6 * 3600
_ELO_CACHE = {"ts": 0, "ratings": None, "aviso": None, "n_jogos": 0, "buckets": None, "global_dist": None}

ELO_BUCKET_LARGURA = 50
ELO_SHRINKAGE_ALFA = 30
ELO_BUCKET_MIN_AMOSTRAS = 15

def _bucket_de_diff(diff):
    return int(diff // ELO_BUCKET_LARGURA) * ELO_BUCKET_LARGURA

def _listar_colunas(cur, tabela):
    if USE_PG:
        cur.execute("""SELECT column_name FROM information_schema.columns
                       WHERE table_name=%s""", (tabela,))
        return [r[0] for r in cur.fetchall()]
    cur.execute(f"PRAGMA table_info({tabela})")
    return [r[1] for r in cur.fetchall()]

def _detectar_coluna_ordem(cols):
    col_data = next((c for c in
        ["data_jogo", "data", "dt_jogo", "data_partida", "dt_partida"]
        if c in cols), None)
    if col_data:
        return col_data, "data"
    col_concurso = next((c for c in ["concurso", "numero_concurso", "rodada"]
                          if c in cols), None)
    if col_concurso:
        return col_concurso, "concurso"
    return None, "SEM_COLUNA_DE_ORDEM"

ELO_RECENCIA_MEIA_VIDA = 3000

def calcular_elo_ratings():
    if (time.time() - _ELO_CACHE["ts"] < ELO_CACHE_TTL
            and _ELO_CACHE["ratings"] is not None):
        return _ELO_CACHE["ratings"], _ELO_CACHE["aviso"]

    schema = detectar_schema_jogos()
    ratings = defaultdict(lambda: 1500.0)
    buckets = defaultdict(lambda: {"1": 0.0, "X": 0.0, "2": 0.0})
    global_cnt = {"1": 0.0, "X": 0.0, "2": 0.0}
    aviso = None
    n_processados = 0
    if not (schema["existe"] and schema["col_gm"] and schema["col_gv"]):
        aviso = "sem_schema_valido_p_elo"
        _ELO_CACHE.update(ts=time.time(), ratings={}, aviso=aviso, n_jogos=0,
                           buckets={}, global_dist=None)
        return {}, aviso

    try:
        conn = get_conn(); cur = conn.cursor()
        cols = _listar_colunas(cur, schema["tabela"])
        col_ordem, tipo_ordem = _detectar_coluna_ordem(cols)
        if tipo_ordem == "SEM_COLUNA_DE_ORDEM":
            aviso = ("Nenhuma coluna de data/concurso encontrada na tabela "
                      f"{schema['tabela']} -- Elo calculado na ordem de "
                      "insercao (id/rowid), que pode NAO refletir a ordem "
                      "cronologica real dos jogos. Ratings finais podem "
                      "estar incorretos ate isso ser confirmado/corrigido.")
            log.warning("calcular_elo_ratings: %s", aviso)

        order_clause = f"ORDER BY {col_ordem} ASC" if col_ordem else ""
        cur.execute(f"""
            SELECT {schema['col_m']}, {schema['col_v']},
                   {schema['col_gm']}, {schema['col_gv']}
            FROM {schema['tabela']}
            WHERE UPPER({schema['col_m']}) NOT LIKE '%INDEFINIDO%'
              AND UPPER({schema['col_v']}) NOT LIKE '%INDEFINIDO%'
            {order_clause}
        """)
        linhas = cur.fetchall()
        conn.close()

        n_total = len(linhas)
        for idx, (m, v, gm, gv) in enumerate(linhas):
            gm2, gv2 = _parse_gol(gm), _parse_gol(gv)
            if not m or not v or gm2 is None or gv2 is None:
                continue
            m, v = str(m).upper().strip(), str(v).upper().strip()
            if gm2 > gv2:   real, resultado_m = "1", 1.0
            elif gm2 < gv2: real, resultado_m = "2", 0.0
            else:           real, resultado_m = "X", 0.5
            elo_m, elo_v = ratings[m], ratings[v]
            diff = (elo_m + ELO_HOME_ADV) - elo_v
            jogos_atras = n_total - 1 - idx
            peso_recencia = 0.5 ** (jogos_atras / ELO_RECENCIA_MEIA_VIDA)
            buckets[_bucket_de_diff(diff)][real] += peso_recencia
            global_cnt[real] += peso_recencia
            esperado_m = 1 / (1 + 10 ** (-diff / 400))
            delta = ELO_K * (resultado_m - esperado_m)
            ratings[m] = elo_m + delta
            ratings[v] = elo_v - delta
            n_processados += 1
        log.info("calcular_elo_ratings: %d jogos processados, %d times, ordem=%s, %d buckets",
                  n_processados, len(ratings), tipo_ordem, len(buckets))
    except Exception as e:
        log.warning("calcular_elo_ratings: %s", e)
        aviso = f"erro_calculo_elo: {e}"

    resultado = dict(ratings)
    buckets_dict = {k: dict(v) for k, v in buckets.items()}
    n_global = sum(global_cnt.values())
    global_dist = ({k: v / n_global for k, v in global_cnt.items()} if n_global > 0
                    else {"1": 0.4722, "X": 0.2616, "2": 0.2663})
    _ELO_CACHE.update(ts=time.time(), ratings=resultado, aviso=aviso,
                       n_jogos=n_processados, buckets=buckets_dict, global_dist=global_dist)
    return resultado, aviso

def elo_time(nome):
    ratings, _ = calcular_elo_ratings()
    return round(ratings.get(nome.upper().strip(), 1500.0), 1)

def _elo_diff_para_probs(diff):
    we = 1 / (1 + 10 ** (-diff / 400))
    largura_empate = max(0.12, 0.24 * math.exp(-abs(diff) / 600))
    p1 = max(0.02, we - largura_empate / 2)
    p2 = max(0.02, (1 - we) - largura_empate / 2)
    px = largura_empate
    t = p1 + px + p2
    return {"1": p1 / t, "X": px / t, "2": p2 / t}, we

def _probs_bucket_empirico(diff):
    buckets = _ELO_CACHE.get("buckets") or {}
    global_dist = _ELO_CACHE.get("global_dist") or {"1": 0.4722, "X": 0.2616, "2": 0.2663}
    contagem = buckets.get(_bucket_de_diff(diff), {"1": 0, "X": 0, "2": 0})
    n_bucket = contagem.get("1", 0) + contagem.get("X", 0) + contagem.get("2", 0)
    alfa = ELO_SHRINKAGE_ALFA
    denom = n_bucket + alfa
    probs = {k: (contagem.get(k, 0) + alfa * global_dist[k]) / denom for k in ("1", "X", "2")}
    t = sum(probs.values())
    probs = {k: v / t for k, v in probs.items()}
    return {**probs, "n_amostras_bucket": n_bucket}

def elo_probs(mandante, visitante):
    ratings, aviso = calcular_elo_ratings()
    ec = ratings.get(mandante.upper().strip(), 1500.0)
    ef = ratings.get(visitante.upper().strip(), 1500.0)
    diff = (ec + ELO_HOME_ADV) - ef

    probs_bucket = _probs_bucket_empirico(diff)
    probs = {k: probs_bucket[k] for k in ("1", "X", "2")}
    fonte = f"elo_bucket_bayesiano_alfa{ELO_SHRINKAGE_ALFA}_n{probs_bucket['n_amostras_bucket']}"

    if aviso:
        fonte += "_AVISO_ORDEM"
    return {
        "1": round(probs["1"], 4), "X": round(probs["X"], 4), "2": round(probs["2"], 4),
        "elo_casa": round(ec, 1), "elo_fora": round(ef, 1),
        "lam_casa": None, "lam_fora": None,
        "fonte_base": fonte, "aviso_elo": aviso,
    }

def backtest_elo_walkforward(limite_jogos=None):
    schema = detectar_schema_jogos()
    if not (schema["existe"] and schema["col_gm"] and schema["col_gv"]):
        return {"erro": "schema_invalido_p_backtest"}

    conn = get_conn(); cur = conn.cursor()
    cols = _listar_colunas(cur, schema["tabela"])
    col_ordem, tipo_ordem = _detectar_coluna_ordem(cols)
    order_clause = f"ORDER BY {col_ordem} ASC" if col_ordem else ""
    limit_clause = f"LIMIT {int(limite_jogos)}" if limite_jogos else ""
    cur.execute(f"""
        SELECT {schema['col_m']}, {schema['col_v']}, {schema['col_gm']}, {schema['col_gv']}
        FROM {schema['tabela']}
        WHERE UPPER({schema['col_m']}) NOT LIKE '%INDEFINIDO%'
          AND UPPER({schema['col_v']}) NOT LIKE '%INDEFINIDO%'
        {order_clause} {limit_clause}
    """)
    linhas = cur.fetchall()
    conn.close()

    ratings = defaultdict(lambda: 1500.0)
    buckets_ate_agora = defaultdict(lambda: {"1": 0, "X": 0, "2": 0})
    n_total = 0
    dist_real = {"1": 0, "X": 0, "2": 0}
    stats = {
        "bucket_empirico": {"acertos": 0, "soma_brier": 0.0, "n_usou_bucket": 0, "n_usou_fallback": 0},
        "curva_logistica": {"acertos": 0, "soma_brier": 0.0},
    }

    for m, v, gm, gv in linhas:
        gm2, gv2 = _parse_gol(gm), _parse_gol(gv)
        if not m or not v or gm2 is None or gv2 is None:
            continue
        m, v = str(m).upper().strip(), str(v).upper().strip()
        if gm2 > gv2:   real, resultado_m = "1", 1.0
        elif gm2 < gv2: real, resultado_m = "2", 0.0
        else:           real, resultado_m = "X", 0.5

        elo_m, elo_v = ratings[m], ratings[v]
        diff = (elo_m + ELO_HOME_ADV) - elo_v

        probs_curva, we = _elo_diff_para_probs(diff)

        b = _bucket_de_diff(diff)
        contagem = buckets_ate_agora.get(b)
        n_bucket = sum(contagem.values()) if contagem else 0
        if contagem and n_bucket >= ELO_BUCKET_MIN_AMOSTRAS:
            probs_bucket = {k: contagem[k] / n_bucket for k in ("1", "X", "2")}
            stats["bucket_empirico"]["n_usou_bucket"] += 1
        else:
            probs_bucket = probs_curva
            stats["bucket_empirico"]["n_usou_fallback"] += 1

        n_total += 1
        dist_real[real] += 1

        for nome, probs in (("bucket_empirico", probs_bucket), ("curva_logistica", probs_curva)):
            previsto = max(probs, key=probs.get)
            if previsto == real:
                stats[nome]["acertos"] += 1
            stats[nome]["soma_brier"] += sum(
                (probs[k] - (1.0 if k == real else 0.0)) ** 2 for k in ("1", "X", "2"))

        buckets_ate_agora[b][real] += 1
        delta = ELO_K * (resultado_m - we)
        ratings[m] = elo_m + delta
        ratings[v] = elo_v - delta

    return {
        "n_jogos_testados": n_total,
        "distribuicao_resultado_real": dist_real,
        "comparacao": {
            nome: {
                "acuracia": round(s["acertos"] / n_total, 4) if n_total else None,
                "brier_score": round(s["soma_brier"] / n_total, 4) if n_total else None,
            }
            for nome, s in stats.items()
        },
        "bucket_empirico_cobertura": {
            "usou_bucket_real": stats["bucket_empirico"]["n_usou_bucket"],
            "usou_fallback_logistico": stats["bucket_empirico"]["n_usou_fallback"],
        },
        "ordem_usada": tipo_ordem,
        "metodologia": ("walk-forward sem vazamento -- bucket empírico também construído "
                         "incrementalmente (só usa jogos ANTERIORES ao ponto de previsão, "
                         "nunca a tabela final inteira)"),
    }

def _detectar_colunas_concurso(cols):
    col_concurso = next((c for c in ["concurso", "numero_concurso"] if c in cols), None)
    col_seq = next((c for c in ["sequencial", "numero_jogo", "jogo", "ordem"] if c in cols), None)
    return col_concurso, col_seq

def _poisson_binomial(probs_acerto):
    pmf = [1.0]
    for p in probs_acerto:
        novo = [0.0] * (len(pmf) + 1)
        for i, prob_i in enumerate(pmf):
            novo[i] += prob_i * (1 - p)
            novo[i + 1] += prob_i * p
        pmf = novo
    return pmf

BACKTEST_P1314_BUCKET = 50

def backtest_p1314_seco(limite_concursos=None, baseline="13s_1d"):
    """CORREÇÃO v11.12 (achado desta sessão): a versão anterior decidia
    UMA VEZ SÓ, pra tabela inteira, se usava a coluna "resultado" ou
    calculava via gols -- se "resultado" existisse no schema, TODA linha
    com resultado NULL era descartada pelo filtro SQL "WHERE resultado
    IN (...)", mesmo quando gols_casa/gols_fora daquela linha estavam
    preenchidos e dariam pra calcular o resultado do mesmo jeito.
    Confirmado em produção: isso derrubava concursos_avaliados de ~1270
    pra 632 -- metade do histórico descartada silenciosamente. Agora a
    decisão é POR LINHA: usa "resultado" quando válido, cai pros gols
    quando "resultado" vier NULL, e só descarta se nenhum dos dois
    estiver disponível."""
    schema = detectar_schema_jogos()
    if not schema["existe"]:
        return {"erro": "schema_invalido"}

    conn = get_conn(); cur = conn.cursor()
    cols = _listar_colunas(cur, schema["tabela"])
    col_concurso, col_seq = _detectar_colunas_concurso(cols)
    col_resultado = "resultado" if "resultado" in cols else None

    if not col_concurso:
        conn.close()
        return {"erro": "sem_coluna_de_concurso",
                "mensagem": (f"Precisa de uma coluna tipo 'concurso' pra agrupar os 14 "
                              f"jogos de cada cartão -- não encontrada em {schema['tabela']}. "
                              f"Sem isso não dá pra calcular P(13/14) por cartão real.")}

    cur.execute(f"SELECT {col_concurso}, COUNT(*) FROM {schema['tabela']} GROUP BY {col_concurso}")
    contagem_original_por_concurso = dict(cur.fetchall())

    aviso_ordem_interna = None if col_seq else (
        "Sem coluna de sequencial/ordem dentro do concurso -- a ordem dos "
        "jogos num mesmo cartão pode não refletir a numeração real (1 a 14), "
        "mas isso não afeta o cálculo em si, só a leitura de qual jogo é qual.")
    order_extra = f", {col_seq}" if col_seq else ""

    # CORREÇÃO v11.12: monta a lista de colunas dinamicamente -- pega
    # "resultado" E gols juntos (quando ambas existirem), pra decidir
    # POR LINHA qual fonte usar, em vez de escolher uma fonte só pra
    # tabela inteira (bug que descartava metade do histórico).
    tem_gols = bool(schema["col_gm"] and schema["col_gv"])
    if not col_resultado and not tem_gols:
        conn.close()
        return {"erro": "sem_coluna_resultado_nem_gols"}

    select_cols = [col_concurso, schema['col_m'], schema['col_v']]
    if col_resultado:
        select_cols.append(col_resultado)
    if tem_gols:
        select_cols.append(schema["col_gm"])
        select_cols.append(schema["col_gv"])
    cols_sql = ", ".join(select_cols)

    n_via_resultado = n_via_gols = n_descartadas = 0
    try:
        cur.execute(f"""
            SELECT {cols_sql}
            FROM {schema['tabela']}
            WHERE UPPER({schema['col_m']}) NOT LIKE '%INDEFINIDO%'
              AND UPPER({schema['col_v']}) NOT LIKE '%INDEFINIDO%'
            ORDER BY {col_concurso} {order_extra}
        """)
        linhas = []
        for row in cur.fetchall():
            i = 0
            conc = row[i]; i += 1
            m = row[i]; i += 1
            v = row[i]; i += 1
            res_raw = None
            if col_resultado:
                res_raw = row[i]; i += 1
            gm_raw = gv_raw = None
            if tem_gols:
                gm_raw = row[i]; i += 1
                gv_raw = row[i]; i += 1

            res = None
            if res_raw in ("1", "X", "2"):
                res = res_raw
                n_via_resultado += 1
            else:
                gm2, gv2 = _parse_gol(gm_raw), _parse_gol(gv_raw)
                if gm2 is not None and gv2 is not None:
                    res = "1" if gm2 > gv2 else ("2" if gm2 < gv2 else "X")
                    n_via_gols += 1
            if res is None:
                n_descartadas += 1
                continue
            linhas.append((conc, m, v, res))
        log.info(
            "backtest_p1314_seco: %d jogos via 'resultado', %d via gols (fallback), "
            "%d descartadas (sem nenhum dos dois)", n_via_resultado, n_via_gols, n_descartadas
        )
    finally:
        conn.close()

    if limite_concursos:
        vistos, filtradas = [], []
        for l in linhas:
            if l[0] not in vistos:
                if len(vistos) >= limite_concursos:
                    break
                vistos.append(l[0])
            filtradas.append(l)
        linhas = filtradas

    elo = defaultdict(lambda: 1500.0)
    bucket_stats = defaultdict(lambda: {"1": 0, "X": 0, "2": 0})
    global_cnt = {"1": 0, "X": 0, "2": 0}

    def aplicar(m, v, diff, resultado):
        bid = round(diff / BACKTEST_P1314_BUCKET)
        bucket_stats[bid][resultado] += 1
        global_cnt[resultado] += 1
        E = 1 / (1 + 10 ** (-diff / 400))
        S = 1.0 if resultado == "1" else (0.5 if resultado == "X" else 0.0)
        ajuste = ELO_K * (S - E)
        elo[m] += ajuste
        elo[v] -= ajuste

    concurso_atual = None
    pendentes = []
    resultado_por_concurso = defaultdict(list)

    for conc, m, v, resultado in linhas:
        if not m or not v:
            continue
        m, v = str(m).upper().strip(), str(v).upper().strip()
        if concurso_atual is not None and conc != concurso_atual:
            for args in pendentes:
                aplicar(*args)
            pendentes = []
        concurso_atual = conc

        diff = (elo[m] + ELO_HOME_ADV) - elo[v]
        bid = round(diff / BACKTEST_P1314_BUCKET)
        stats = bucket_stats[bid]
        n_bucket = sum(stats.values())
        total_dist = sum(global_cnt.values())
        if total_dist > 0:
            global_p = {k: global_cnt[k] / total_dist for k in ("1", "X", "2")}
        else:
            global_p = {"1": 0.4722, "X": 0.2616, "2": 0.2663}
        denom = n_bucket + ELO_SHRINKAGE_ALFA
        p1 = (stats.get("1", 0) + ELO_SHRINKAGE_ALFA * global_p["1"]) / denom
        px = (stats.get("X", 0) + ELO_SHRINKAGE_ALFA * global_p["X"]) / denom
        p2 = (stats.get("2", 0) + ELO_SHRINKAGE_ALFA * global_p["2"]) / denom
        t = p1 + px + p2
        p1, px, p2 = p1 / t, px / t, p2 / t

        resultado_por_concurso[conc].append((p1, px, p2, resultado))
        pendentes.append((m, v, diff, resultado))

    for args in pendentes:
        aplicar(*args)

    def _probs_do_jogo(p1, px, p2, resultado, cobrir_2=False):
        ranking = sorted([("1", p1), ("X", px), ("2", p2)], key=lambda x: x[1], reverse=True)
        if cobrir_2:
            cobertos = {ranking[0][0], ranking[1][0]}
            prob = ranking[0][1] + ranking[1][1]
        else:
            cobertos = {ranking[0][0]}
            prob = ranking[0][1]
        acertou = 1 if resultado in cobertos else 0
        return prob, acertou

    soma_p13mais = soma_p14 = 0.0
    concursos_13mais_real = concursos_14_real = 0
    n_validos = 0
    distribuicao = defaultdict(int)

    for conc, lista in resultado_por_concurso.items():
        n_jogos = len(lista)
        if n_jogos < 13:
            continue

        total_original = contagem_original_por_concurso.get(conc, n_jogos)
        jogos_removidos_indefinido = total_original - n_jogos
        if n_jogos == 13 and jogos_removidos_indefinido > 0:
            continue

        if baseline == "13s_1d" and n_jogos >= 1:
            idx_incerto = min(range(n_jogos), key=lambda i: max(lista[i][0], lista[i][1], lista[i][2]))
        else:
            idx_incerto = None

        probs, acertos_por_jogo = [], []
        for i, (p1, px, p2, resultado) in enumerate(lista):
            cobrir_2 = (i == idx_incerto)
            prob, acertou = _probs_do_jogo(p1, px, p2, resultado, cobrir_2)
            probs.append(prob)
            acertos_por_jogo.append(acertou)

        acertos_reais = sum(acertos_por_jogo)
        pmf = _poisson_binomial(probs)
        p13mais = sum(pmf[13:])
        p14 = pmf[14] if n_jogos >= 14 else (pmf[n_jogos] if n_jogos == 13 else 0.0)
        soma_p13mais += p13mais
        soma_p14 += p14
        distribuicao[acertos_reais] += 1
        if acertos_reais >= 13:
            concursos_13mais_real += 1
        if acertos_reais == n_jogos and n_jogos == 14:
            concursos_14_real += 1
        n_validos += 1

    if n_validos == 0:
        return {"erro": "nenhum_concurso_valido_encontrado"}

    return {
        "baseline_testado": baseline,
        "concursos_avaliados": n_validos,
        "cobertura_fonte_resultado": {
            "n_via_resultado": n_via_resultado,
            "n_via_gols_fallback": n_via_gols,
            "n_descartadas_sem_fonte": n_descartadas,
        },
        "aviso_ordem_interna": aviso_ordem_interna,
        "modelo_media_prevista": {
            "p_13_mais": round(soma_p13mais / n_validos, 4),
            "p_14": round(soma_p14 / n_validos, 5),
        },
        "realidade_historica": {
            "concursos_com_13_mais": concursos_13mais_real,
            "concursos_com_14": concursos_14_real,
            "freq_13_mais": round(concursos_13mais_real / n_validos, 4),
            "freq_14": round(concursos_14_real / n_validos, 5),
        },
        "distribuicao_acertos_por_concurso": dict(sorted(distribuicao.items())),
        "projecao_52_concursos": {
            "concursos_13_mais_esperados": round(concursos_13mais_real / n_validos * 52, 1),
            "concursos_14_esperados": round(concursos_14_real / n_validos * 52, 2),
        },
        "metodologia": (f"baseline={baseline} -- bucket empírico, Elo em lote por concurso, "
                         f"Poisson-Binomial exato. 13s_1d cobre o jogo mais incerto do cartão "
                         f"com duplo (2 resultados), igual à aposta mínima real da Loteca. "
                         f"v11.12: fonte de resultado decidida por linha (resultado com "
                         f"fallback pra gols), não mais pela tabela inteira."),
    }

MEDIA_GOLS = {
    "copa":    {"casa":1.35,"fora":1.05},
    "serie_a": {"casa":1.42,"fora":1.05},
    "serie_b": {"casa":1.35,"fora":1.00},
    "serie_c": {"casa":1.28,"fora":0.98},
    "premier": {"casa":1.53,"fora":1.22},
    "la_liga": {"casa":1.47,"fora":1.10},
    "libertadores":{"casa":1.38,"fora":0.95},
}

ELO_FALLBACK = {
    "ARGENTINA":2140,"FRANÇA":2100,"INGLATERRA":2080,"ESPANHA":2070,
    "ALEMANHA":2060,"PORTUGAL":2040,"HOLANDA":2030,"BRASIL":2050,
    "PALMEIRAS":1820,"FLAMENGO":1810,"BOTAFOGO":1780,"FLUMINENSE":1750,
    "ATLETICO MG":1760,"SÃO PAULO":1740,"CORINTHIANS":1720,"GRÊMIO":1700,
    "INTERNACIONAL":1710,"CRUZEIRO":1690,"VASCO DA GAMA":1660,"SANTOS":1650,
    "FORTALEZA":1670,"BAHIA":1640,"MIRASSOL":1610,"JUVENTUDE":1590,
    "VITÓRIA":1580,"SPORT":1560,"BRAGANTINO":1620,"ATHLETICO PR":1660,
}

def _poi(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

RHO_DIXON_COLES = -0.13

def _tau_dc(i, j, lc, lf, rho):
    if i == 0 and j == 0: return 1.0 - lc * lf * rho
    if i == 0 and j == 1: return 1.0 + lc * rho
    if i == 1 and j == 0: return 1.0 + lf * rho
    if i == 1 and j == 1: return 1.0 - rho
    return 1.0

def poisson_probs(mandante, visitante, liga="_default"):
    schema = detectar_schema_jogos()
    if schema["existe"] and schema["col_gm"] and schema["col_gv"]:
        ep = elo_probs(mandante, visitante)
        if ep and ep.get("fonte_base") not in (None,):
            return ep

    def elo_fallback_fixo(nome):
        return ELO_FALLBACK.get(nome.upper().strip(), 1650)
    ec, ef = elo_fallback_fixo(mandante), elo_fallback_fixo(visitante)
    med = MEDIA_GOLS.get(liga, {"casa":1.40,"fora":1.05})
    ajuste = (ec - ef) / 200 * 0.25
    lc = max(0.3, med["casa"] + ajuste + 0.06)
    lf = max(0.3, med["fora"] - ajuste)
    p1 = px = p2 = 0.0
    for i in range(9):
        for j in range(9):
            p = _poi(lc, i) * _poi(lf, j)
            if i <= 1 and j <= 1:
                p *= _tau_dc(i, j, lc, lf, RHO_DIXON_COLES)
            if i > j:    p1 += p
            elif i == j: px += p
            else:        p2 += p
    t = p1 + px + p2
    return {
        "1": round(p1/t, 4), "X": round(px/t, 4), "2": round(p2/t, 4),
        "elo_casa": ec, "elo_fora": ef,
        "lam_casa": round(lc, 3), "lam_fora": round(lf, 3),
        "fonte_base": "fallback_dixon_coles_SEM_BANCO",
    }

def sem_margem(o1, ox, o2):
    r1, rx, r2 = 1/o1, 1/ox, 1/o2
    over = r1 + rx + r2
    return {"1":round(r1/over,4),"X":round(rx/over,4),"2":round(r2/over,4),"over":round(over,4)}

def blending(prob_m, odds=None, w=0.65):
    if not odds:
        return {**prob_m, "fonte":"modelo_puro"}
    pm = sem_margem(odds["1"], odds["X"], odds["2"])
    wm = 1 - w
    out = {}
    for k in ["1","X","2"]:
        out[k] = round(prob_m[k]*w + pm[k]*wm, 4)
    t = sum(out.values())
    out = {k: round(v/t, 4) for k, v in out.items()}
    out["fonte"]        = "blend_nao_calibrado"
    out["peso_modelo"]  = w
    out["overround"]    = pm["over"]
    return out

def classificar(probs, odd_1=None, liga="_default"):
    p1, px, p2 = probs["1"], probs["X"], probs["2"]
    ordem = sorted([("1",p1),("X",px),("2",p2)], key=lambda x: x[1], reverse=True)
    top_c, top_v = ordem[0]
    seg_c, _     = ordem[1]
    lim = 0.52
    if liga == "copa" and odd_1:
        if odd_1 < 1.50:   lim = 0.82
        elif odd_1 < 1.80: lim = 0.62
    if top_v >= lim:
        tipo, cols = "SECO",   [top_c]
    elif top_v >= 0.40:
        tipo, cols = "DUPLO",  [top_c, seg_c]
    else:
        tipo, cols = "TRIPLO", ["1","X","2"]
    classe = "A" if top_v>=0.80 else "B" if top_v>=0.65 else \
             "C" if top_v>=0.50 else "D" if top_v>=0.40 else "E"
    return {
        "tipo": tipo, "colunas": cols,
        "coluna_display": "/".join(sorted(cols)),
        "confianca": round(top_v*100, 1), "classe": classe,
    }

def kelly(prob, odd, banca=100.0, fracao=0.25):
    b  = odd - 1.0
    kp = (b*prob - (1-prob)) / b if b > 0 else -1.0
    ev = prob*b - (1-prob)
    ok = kp > 0.01 and ev > 0.02
    return {
        "stake":   round(banca*max(0,kp*fracao), 2) if ok else 0.0,
        "ev":      round(ev, 4), "apostar": ok,
    }

def score(classif, mot=0.70):
    return round(min(100.0, classif["confianca"]*(0.85+0.15*mot)), 1)

def painel(jogos):
    nd = sum(1 for j in jogos if j["classificacao"]["tipo"]=="DUPLO")
    nt = sum(1 for j in jogos if j["classificacao"]["tipo"]=="TRIPLO")
    def c(d,t): return max(4.00, round((2**d)*(3**t)*2.0, 2))
    return {
        "secos": sum(1 for j in jogos if j["classificacao"]["tipo"]=="SECO"),
        "duplos": nd, "triplos": nt,
        "custo_minimo":      c(nd, 0),
        "custo_recomendado": c(nd, min(nt,1)),
        "custo_completo":    c(nd, nt),
    }

def apif_get(endpoint, params=None):
    if not RAPIDAPI_KEY:
        return None
    try:
        r = requests.get(
            f"{APIF_BASE}/{endpoint}",
            headers={"X-RapidAPI-Key":  RAPIDAPI_KEY,
                     "X-RapidAPI-Host": APIF_HOST},
            params=params or {}, timeout=8
        )
        if r.status_code == 200:
            return r.json()
        log.warning("API-Football status %s", r.status_code)
    except Exception as e:
        log.warning("API-Football erro: %s", e)
    return None

def buscar_placar_ao_vivo():
    data = apif_get("football-current-live")
    if not data:
        return []
    return (data.get("response", {}) or {}).get("live", []) or []

def _normalizar_nome_time(nome):
    if not nome:
        return ""
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return nome.upper().strip()

def casar_placar_ao_vivo(mandante, visitante, jogos_ao_vivo):
    m_norm = _normalizar_nome_time(mandante)
    v_norm = _normalizar_nome_time(visitante)
    for jogo in jogos_ao_vivo:
        home = jogo.get("home", {}) or {}
        away = jogo.get("away", {}) or {}
        home_nomes = {_normalizar_nome_time(home.get("name")),
                      _normalizar_nome_time(home.get("longName"))}
        away_nomes = {_normalizar_nome_time(away.get("name")),
                      _normalizar_nome_time(away.get("longName"))}
        if m_norm in home_nomes and v_norm in away_nomes:
            status = jogo.get("status", {}) or {}
            live_time = status.get("liveTime", {}) or {}
            return {
                "placar": status.get("scoreStr"),
                "minuto": live_time.get("short"),
                "em_andamento": bool(status.get("ongoing")),
                "encerrado": bool(status.get("finished")),
            }
    return None

def buscar_proximos_jogos(league_id, season=2026):
    data = apif_get("football-get-all-fixtures-by-league-by-season",
                    {"leagueId": league_id, "season": season})
    if not data:
        return []
    jogos = []
    for fix in data.get("response", []):
        f, t = fix["fixture"], fix["teams"]
        jogos.append({
            "id": f["id"], "mandante": t["home"]["name"],
            "visitante": t["away"]["name"],
            "data": f["date"][:10], "hora": f["date"][11:16],
            "status": f["status"]["short"],
        })
    return jogos

def buscar_odds(sport="soccer_brazil_campeonato"):
    if not ODDS_KEY:
        return {}
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
            params={"apiKey": ODDS_KEY, "regions":"eu",
                    "markets":"h2h", "oddsFormat":"decimal"},
            timeout=8
        )
        if r.status_code != 200:
            return {}
        resultado = {}
        for ev in r.json():
            for book in ev.get("bookmakers", []):
                if book["key"] not in ("pinnacle","bet365","betfair"):
                    continue
                for mkt in book.get("markets", []):
                    if mkt["key"] != "h2h":
                        continue
                    odds = {o["name"]: o["price"] for o in mkt["outcomes"]}
                    key  = f"{ev['home_team']}|{ev['away_team']}"
                    resultado[key] = {
                        "1": odds.get(ev["home_team"], 0),
                        "X": odds.get("Draw", 0),
                        "2": odds.get(ev["away_team"], 0),
                        "casa": book["key"],
                    }
                    break
                break
        return resultado
    except Exception as e:
        log.warning("Odds API erro: %s", e)
        return {}

ODDS_SPORT_KEYS = [
    "soccer_brazil_campeonato",
    "soccer_brazil_serie_b",
    "soccer_conmebol_copa_libertadores",
    "soccer_conmebol_sudamericana",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_uefa_champs_league",
]

ODDS_CACHE_TTL = 6 * 3600
_ODDS_CACHE = {"ts": 0, "dados": {}}

def buscar_odds_todas_ligas():
    if time.time() - _ODDS_CACHE["ts"] < ODDS_CACHE_TTL and _ODDS_CACHE["dados"]:
        return _ODDS_CACHE["dados"]
    if not ODDS_KEY:
        return {}
    mesclado = {}
    ligas_ok, ligas_erro = 0, 0
    for sport in ODDS_SPORT_KEYS:
        odds_liga = buscar_odds(sport)
        if odds_liga:
            ligas_ok += 1
            mesclado.update(odds_liga)
        else:
            ligas_erro += 1
    log.info("buscar_odds_todas_ligas: %d ligas com dado, %d sem dado/erro, %d jogos no total",
              ligas_ok, ligas_erro, len(mesclado))
    _ODDS_CACHE.update(ts=time.time(), dados=mesclado)
    return mesclado

def casar_odds(mandante, visitante, odds_todas):
    m_norm = _normalizar_nome_time(mandante)
    v_norm = _normalizar_nome_time(visitante)
    for chave, odds in odds_todas.items():
        partes = chave.split("|")
        if len(partes) != 2:
            continue
        if _normalizar_nome_time(partes[0]) == m_norm and _normalizar_nome_time(partes[1]) == v_norm:
            return odds
    return None

def _parse_float(v):
    if isinstance(v,(int,float)): return float(v)
    try: return float(str(v).replace("R$","").replace(".","").replace(",",".").strip())
    except: return 0.0

HEADERS_NAVEGADOR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://loterias.caixa.gov.br/Paginas/Programacao-Loteca.aspx",
    "Origin": "https://loterias.caixa.gov.br",
}

def buscar_cef(numero=""):
    try:
        url = f"{URL_CEF}/{numero}" if numero else URL_CEF
        r = requests.get(url, timeout=12, headers=HEADERS_NAVEGADOR)
        if r.status_code == 200:
            return r.json()
        log.warning("buscar_cef: status HTTP %s pra url %s -- corpo (primeiros 300 chars): %s",
                    r.status_code, url, r.text[:300])
        return None
    except Exception as e:
        log.warning("buscar_cef: excecao ao buscar %s -- %s", numero or "(ultimo)", e)
        return None

def buscar_cef_cache_github():
    url = (f"https://raw.githubusercontent.com/{GITHUB_REPO_CACHE}/"
           f"{GITHUB_BRANCH_CACHE}/data/cef_cache.json")
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            log.warning("buscar_cef_cache_github: status %s pra %s", r.status_code, url)
            return None
        cache = r.json()
        if cache.get("status_ultimo") != 200:
            log.warning("buscar_cef_cache_github: cache existe mas a ultima busca do "
                        "Action tambem falhou (%s) -- se isso persistir, o bloqueio da "
                        "Caixa pode nao ser só por IP do Render, e sim mais amplo",
                        cache.get("erro"))
        return cache
    except Exception as e:
        log.warning("buscar_cef_cache_github: %s", e)
        return None

def parsear_cef(numero, d):
    if not d: return None, []
    partidas = d.get("listaResultadoEquipeEsportiva") or []
    jos = []
    for p in partidas:
        gm, gv = p.get("nuGolEquipeUm"), p.get("nuGolEquipeDois")
        if gm is None or gv is None: resultado = "?"
        elif gm > gv: resultado = "1"
        elif gm < gv: resultado = "2"
        else: resultado = "X"
        jos.append({
            "id": p.get("nuSequencial", len(jos)+1),
            "mandante": p.get("nomeEquipeUm", f"Time A {len(jos)+1}"),
            "visitante": p.get("nomeEquipeDois", f"Time B {len(jos)+1}"),
            "resultado_real": resultado,
            "data": p.get("dtJogo",""), "liga": p.get("nomeCampeonato",""),
        })
    return d.get("numero", numero), jos

CONCURSO_FALLBACK_EXEMPLO = {
    1255: {
        "nome":"Copa Loteca — 1ª Rodada (DADO DE EXEMPLO, NAO AO VIVO)",
        "periodo":"11-15 jun 2026","liga":"copa",
        "jogos":[
            {"id":1, "mandante":"México",         "visitante":"África do Sul","odds":{"1":1.85,"X":3.40,"2":4.20}},
            {"id":7, "mandante":"Brasil",         "visitante":"Marrocos",     "odds":{"1":1.65,"X":3.60,"2":5.50}},
        ]
    },
}

def analisar_jogo(mandante, visitante, liga="_default", odds=None, banca=100.0):
    pm  = poisson_probs(mandante, visitante, liga)
    pf  = blending(pm, odds)
    cl  = classificar(pf, odd_1=odds["1"] if odds else None, liga=liga)
    sc  = score(cl)
    kelly_res, melhor = {}, None
    if odds:
        for res in ["1","X","2"]:
            if odds.get(res, 0) > 1.0:
                kelly_res[res] = kelly(pf[res], odds[res], banca)
        candidatos = [(r,k) for r,k in kelly_res.items() if k["apostar"]]
        if candidatos:
            best = max(candidatos, key=lambda x: x[1]["ev"])
            melhor = {"resultado":best[0],"odd":odds[best[0]],
                      "ev":best[1]["ev"],"stake":best[1]["stake"]}
    return {
        "prob_modelo": {"1":pm["1"],"X":pm["X"],"2":pm["2"]},
        "prob_final":  {"1":pf["1"],"X":pf["X"],"2":pf["2"]},
        "fonte": pf.get("fonte","modelo_puro"),
        "fonte_base_modelo": pm.get("fonte_base"),
        "overround": pf.get("overround"),
        "elo_casa":  pm["elo_casa"], "elo_fora": pm["elo_fora"],
        "lam_casa":  pm.get("lam_casa"), "lam_fora": pm.get("lam_fora"),
        "classificacao": cl, "score": sc,
        "kelly": kelly_res or None, "melhor_aposta": melhor,
    }

# ════════════════════════════════════════════════════════════
# ROTAS
# ════════════════════════════════════════════════════════════

@app.route("/health")
@app.route("/api/status")
def health():
    schema = detectar_schema_jogos()
    apis = {
        "odds_api":     {"configurada": bool(ODDS_KEY), "status": "não configurada",
                          "usada_em_producao": True,
                          "ligas_configuradas": ODDS_SPORT_KEYS,
                          "cache_atual": {
                              "jogos_em_cache": len(_ODDS_CACHE["dados"]),
                              "idade_segundos": round(time.time() - _ODDS_CACHE["ts"], 1) if _ODDS_CACHE["ts"] else None,
                          }},
        "api_football": {"configurada": bool(RAPIDAPI_KEY), "status": "não configurada",
                          "env_var_usada": ("RAPIDAPI_KEY" if os.getenv("RAPIDAPI_KEY")
                                             else "APIFOOTBALL_KEY" if os.getenv("APIFOOTBALL_KEY")
                                             else None)},
        "banco":        {"tipo": "postgresql" if USE_PG else "sqlite",
                          "tabela_jogos_historicos": schema["tabela"] or "NENHUMA (previsao cai no fallback ELO fixo)"},
        "caixa_loteca":  {"direto": "desconhecido (só testado no /api/grade-automatica)",
                           "cache_github": {"repo": GITHUB_REPO_CACHE, "branch": GITHUB_BRANCH_CACHE}},
    }
    if ODDS_KEY:
        try:
            r = requests.get("https://api.the-odds-api.com/v4/sports",
                             params={"apiKey":ODDS_KEY}, timeout=6)
            apis["odds_api"]["status"] = "conectada" if r.status_code==200 else f"erro {r.status_code}"
        except: apis["odds_api"]["status"] = "timeout"
    if RAPIDAPI_KEY:
        try:
            r = requests.get(f"https://{APIF_HOST}/football-get-all-leagues",
                headers={"X-RapidAPI-Key":RAPIDAPI_KEY,"X-RapidAPI-Host":APIF_HOST}, timeout=6)
            apis["api_football"]["status"] = "conectada" if r.status_code==200 else f"erro {r.status_code}"
        except: apis["api_football"]["status"] = "timeout"
    return jsonify({
        "status": "ok", "versao": "Loteca Elite Pro v11.13",
        "modelo": "elo_iterativo(K30,HA75) > fallback_elo_fixo+poisson_liga",
        "banco": "postgresql" if USE_PG else "sqlite",
        "apis": apis,
    })

@app.route("/")
@app.route("/api/grade-automatica")
def grade_automatica():
    fonte_dado = None
    cache_idade_min = None

    dados_ultimo = buscar_cef("")
    dados_aberto = None
    if dados_ultimo:
        fonte_dado = "caixa_ao_vivo_direto"
        numero_proximo = dados_ultimo.get("numeroConcursoProximo")
        if numero_proximo:
            dados_aberto = buscar_cef(str(numero_proximo))

    if not dados_ultimo:
        cache = buscar_cef_cache_github()
        if cache and cache.get("dados_ultimo"):
            dados_ultimo = cache["dados_ultimo"]
            dados_aberto = cache.get("dados_aberto")
            fonte_dado = "caixa_ao_vivo_cache_github"
            try:
                fetched = datetime.fromisoformat(
                    cache["fetched_em_utc"].replace("Z", "+00:00"))
                cache_idade_min = round(
                    (datetime.now(timezone.utc) - fetched).total_seconds() / 60, 1)
            except Exception:
                cache_idade_min = None

    dados = dados_aberto if (dados_aberto and dados_aberto.get("listaResultadoEquipeEsportiva")) else dados_ultimo

    if dados:
        numero, jogos_cef = parsear_cef(dados.get("numero"), dados)
        if jogos_cef:
            banca = float(request.args.get("banca", 100))
            jogos_ao_vivo = buscar_placar_ao_vivo()
            odds_todas = buscar_odds_todas_ligas()
            jogos = []
            n_com_odds = 0
            for j in jogos_cef:
                odds_jogo = casar_odds(j["mandante"], j["visitante"], odds_todas)
                if odds_jogo:
                    n_com_odds += 1
                analise = analisar_jogo(j["mandante"], j["visitante"], "_default",
                                         odds=odds_jogo, banca=banca)
                placar = casar_placar_ao_vivo(j["mandante"], j["visitante"], jogos_ao_vivo)
                jogos.append({**j, **analise, "placar_ao_vivo": placar,
                              "odds_aplicadas": odds_jogo is not None})
            return jsonify({
                "status":"sucesso","concurso":numero,"fonte":fonte_dado,
                "concurso_ainda_aberto": dados is dados_aberto,
                "cache_idade_minutos": cache_idade_min,
                "cobertura_odds": {"jogos_com_odds": n_com_odds, "total_jogos": len(jogos),
                                    "peso_modelo_no_blend": 0.65,
                                    "aviso": "peso_ainda_NAO_calibrado_via_walkforward"},
                "total_jogos":len(jogos),"jogos":jogos,"painel":painel(jogos),
            })
    exemplo = CONCURSO_FALLBACK_EXEMPLO[1255]
    banca = float(request.args.get("banca", 100))
    jogos = []
    for j in exemplo["jogos"]:
        analise = analisar_jogo(j["mandante"], j["visitante"], exemplo["liga"], odds=j.get("odds"), banca=banca)
        jogos.append({**j, **analise})
    return jsonify({
        "status":"aviso","fonte":"EXEMPLO_FIXO_NAO_AO_VIVO",
        "mensagem":"API da Caixa indisponivel no momento (direto e via cache do GitHub Actions) -- mostrando dado de exemplo, nao concurso real",
        "nome":exemplo["nome"],"total_jogos":len(jogos),"jogos":jogos,"painel":painel(jogos),
    })

@app.route("/api/analisar")
def analisar():
    m = request.args.get("mandante","")
    v = request.args.get("visitante","")
    liga = request.args.get("liga","_default")
    o1 = request.args.get("odd_1", type=float)
    ox = request.args.get("odd_x", type=float)
    o2 = request.args.get("odd_2", type=float)
    banca = float(request.args.get("banca", 100))
    if not m or not v:
        return jsonify({"status":"erro","mensagem":"mandante e visitante obrigatórios"}), 400
    odds = {"1":o1,"X":ox,"2":o2} if all([o1,ox,o2]) else None
    analise = analisar_jogo(m, v, liga, odds=odds, banca=banca)
    return jsonify({"status":"sucesso","mandante":m,"visitante":v,"liga":liga,**analise})

@app.route("/api/backtest-p1314")
def backtest_p1314_route():
    try:
        limite = request.args.get("limite_concursos")
        limite = int(limite) if limite else None
        if request.args.get("comparar"):
            r_seco = backtest_p1314_seco(limite, baseline="14s_puro")
            r_real = backtest_p1314_seco(limite, baseline="13s_1d")
            if "erro" in r_seco or "erro" in r_real:
                return jsonify({"status": "erro", "14s_puro": r_seco, "13s_1d": r_real}), 500
            f13_seco = r_seco["realidade_historica"]["freq_13_mais"]
            f13_real = r_real["realidade_historica"]["freq_13_mais"]
            f14_seco = r_seco["realidade_historica"]["freq_14"]
            f14_real = r_real["realidade_historica"]["freq_14"]
            ganho_13 = round((f13_real / f13_seco - 1) * 100, 1) if f13_seco else None
            ganho_14 = round((f14_real / f14_seco - 1) * 100, 1) if f14_seco else None
            return jsonify({
                "status": "sucesso",
                "14s_puro": r_seco, "13s_1d": r_real,
                "ganho_relativo_13s_1d_vs_14s_puro": {
                    "p_13_mais_pct": ganho_13, "p_14_pct": ganho_14,
                    "nota": ("13s_1d é o mínimo REAL da Loteca (mesmo custo do seco puro, "
                              "que a Caixa nem permite apostar) -- esse ganho é 'de graça'."),
                },
            })
        baseline = request.args.get("baseline", "13s_1d")
        resultado = backtest_p1314_seco(limite, baseline=baseline)
        return jsonify({"status": "sucesso", **resultado})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/backtest-elo")
def backtest_elo_route():
    try:
        limite = request.args.get("limite")
        limite = int(limite) if limite else None
        resultado = backtest_elo_walkforward(limite)
        return jsonify({"status": "sucesso", **resultado})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/verificar-ambiguidade-residual")
def verificar_ambiguidade_residual():
    """Procura por nomes de time que ainda podem estar ambíguos além dos
    já tratados (ATLETICO/AMERICA) -- especificamente ATHLETICO (tem
    Athletico Paranaense, mas também pode aparecer como forma alternativa
    de escrita de Atlético) e GUARANI (tem Guarani-SP e Guarani-CE),
    citados como pendência na sessão de desambiguação (baixo risco, mas
    não zero). Também lista, de forma genérica, qualquer nome que
    apareça em MUITOS jogos mas sem sufixo de UF -- candidato a ser um
    nome genérico não resolvido, sem assumir que sabemos quais são."""
    try:
        schema = detectar_schema_jogos()
        if not schema["existe"]:
            return jsonify({"status": "erro", "mensagem": "schema_invalido"}), 500
        conn = get_conn(); cur = conn.cursor()
        ph = _ph()

        candidatos = ["ATHLETICO", "GUARANI", "ATLETICO", "AMERICA",
                      "SANTA CRUZ", "SAO RAIMUNDO", "BRASIL DE PELOTAS",
                      "OPERARIO", "FLUMINENSE", "RIO BRANCO"]
        resultado = {}
        for nome in candidatos:
            cur.execute(f"""
                SELECT COUNT(*) FROM {schema['tabela']}
                WHERE UPPER(TRIM({schema['col_m']}))={ph}
                   OR UPPER(TRIM({schema['col_v']}))={ph}
            """, (nome, nome))
            n = cur.fetchone()[0]
            if n > 0:
                resultado[nome] = n

        # nomes SEM sufixo de UF/desambiguação (sem hífen) que aparecem
        # em muitos jogos -- candidatos a precisar de atenção, sem viés
        # de lista fixa
        cur.execute(f"""
            SELECT UPPER(TRIM({schema['col_m']})) AS t, COUNT(*) AS n
            FROM {schema['tabela']}
            WHERE {schema['col_m']} NOT LIKE '%-%'
              AND UPPER({schema['col_m']}) NOT LIKE '%INDEFINIDO%'
            GROUP BY t
            HAVING COUNT(*) > 100
            ORDER BY n DESC
            LIMIT 20
        """)
        nomes_sem_sufixo = [{"nome": r[0], "n_jogos": r[1]} for r in cur.fetchall()]
        conn.close()

        return jsonify({
            "status": "sucesso",
            "contagem_nomes_candidatos_conhecidos": resultado,
            "nomes_sem_sufixo_uf_mais_frequentes": nomes_sem_sufixo,
            "interpretacao": (
                "Nomes na primeira lista com contagem > 0 SEM o correspondente "
                "com sufixo (ex: ATHLETICO sem ATHLETICO-PR/ATHLETICO-*) podem "
                "estar misturando times diferentes sob um nome genérico. A "
                "segunda lista mostra os nomes mais frequentes sem hífen -- "
                "vale checar manualmente se algum desses é time único de "
                "verdade (não precisa desambiguar) ou nome genérico escondido."
            ),
        })
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/verificar-desambiguacao")
def verificar_desambiguacao():
    try:
        schema = detectar_schema_jogos()
        if not schema["existe"]:
            return jsonify({"status": "erro", "mensagem": "schema_invalido"}), 500
        conn = get_conn(); cur = conn.cursor()
        ph = _ph()
        variantes_esperadas = ["ATLETICO-MG", "ATLETICO-GO", "AMERICA-MG",
                                "AMERICA-RN", "ATLETICO", "AMERICA"]
        encontrados = {}
        for nome in variantes_esperadas:
            cur.execute(f"""
                SELECT COUNT(*) FROM {schema['tabela']}
                WHERE UPPER(TRIM({schema['col_m']}))={ph}
                   OR UPPER(TRIM({schema['col_v']}))={ph}
            """, (nome, nome))
            encontrados[nome] = cur.fetchone()[0]

        cur.execute(f"""
            SELECT COUNT(*) FROM {schema['tabela']}
            WHERE UPPER(TRIM({schema['col_m']})) LIKE '%INDEFINIDO%'
               OR UPPER(TRIM({schema['col_v']})) LIKE '%INDEFINIDO%'
        """)
        n_indefinido = cur.fetchone()[0]

        cur.execute(f"""
            SELECT COUNT(DISTINCT UPPER(TRIM({schema['col_m']})))
            FROM {schema['tabela']}
        """)
        n_times_distintos = cur.fetchone()[0]
        conn.close()

        desambiguado = (encontrados["ATLETICO-MG"] > 0 or encontrados["ATLETICO-GO"] > 0
                         or encontrados["AMERICA-MG"] > 0 or encontrados["AMERICA-RN"] > 0)

        return jsonify({
            "status": "sucesso",
            "coluna_usada_pelo_app": {"mandante": schema["col_m"], "visitante": schema["col_v"]},
            "contagem_por_variante": encontrados,
            "jogos_marcados_indefinido": n_indefinido,
            "times_distintos_no_banco": n_times_distintos,
            "desambiguacao_aplicada": desambiguado,
            "interpretacao": (
                "Se ATLETICO-MG/ATLETICO-GO/AMERICA-MG/AMERICA-RN aparecerem com "
                "contagem > 0 E o genérico ATLETICO/AMERICA tiver contagem 0 (ou "
                "bem menor), a desambiguação foi aplicada nas colunas que o app usa. "
                "Se ATLETICO/AMERICA genérico ainda tiver contagem alta e as versões "
                "desambiguadas forem 0, a desambiguação NÃO chegou nessa coluna/banco."
            ),
        })
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/diagnostico-concursos")
def diagnostico_concursos():
    """Investiga a distribuição real de jogos por concurso -- motivado
    pela discrepância encontrada em produção: 16.778 jogos / 632
    concursos = 26,5 jogos/concurso em média, muito acima dos 14
    esperados. Mostra quantos concursos têm exatamente 14 (válidos),
    quantos têm menos de 13 (incompletos, descartados pelo backtest),
    e quantos têm mais de 14 (possível duplicação de jogos -- já houve
    um caso documentado de 28 jogos duplicados no concurso 1266)."""
    try:
        schema = detectar_schema_jogos()
        if not schema["existe"]:
            return jsonify({"status": "erro", "mensagem": "schema_invalido"}), 500
        conn = get_conn(); cur = conn.cursor()
        cols = _listar_colunas(cur, schema["tabela"])
        col_concurso, col_seq = _detectar_colunas_concurso(cols)
        if not col_concurso:
            conn.close()
            return jsonify({"status": "erro", "mensagem": "sem_coluna_de_concurso"}), 500

        cur.execute(f"""
            SELECT {col_concurso}, COUNT(*)
            FROM {schema['tabela']}
            GROUP BY {col_concurso}
        """)
        contagens = cur.fetchall()
        conn.close()

        total_concursos = len(contagens)
        total_jogos = sum(n for _, n in contagens)
        distribuicao = defaultdict(int)
        concursos_14 = concursos_menos_13 = concursos_mais_14 = concursos_13 = 0
        exemplos_duplicados, exemplos_incompletos = [], []

        for conc, n in contagens:
            distribuicao[n] += 1
            if n == 14:
                concursos_14 += 1
            elif n == 13:
                concursos_13 += 1
            elif n < 13:
                concursos_menos_13 += 1
                if len(exemplos_incompletos) < 15:
                    exemplos_incompletos.append({"concurso": conc, "n_jogos": n})
            else:  # n > 14
                concursos_mais_14 += 1
                if len(exemplos_duplicados) < 15:
                    exemplos_duplicados.append({"concurso": conc, "n_jogos": n})

        return jsonify({
            "status": "sucesso",
            "total_concursos_distintos": total_concursos,
            "total_jogos": total_jogos,
            "media_jogos_por_concurso": round(total_jogos / total_concursos, 2) if total_concursos else None,
            "concursos_com_exatamente_14": concursos_14,
            "concursos_com_13_exatos": concursos_13,
            "concursos_com_menos_de_13_incompletos": concursos_menos_13,
            "concursos_com_mais_de_14_possivel_duplicacao": concursos_mais_14,
            "distribuicao_n_jogos_por_concurso": dict(sorted(distribuicao.items())),
            "exemplos_concursos_com_duplicacao": sorted(
                exemplos_duplicados, key=lambda x: -x["n_jogos"]),
            "exemplos_concursos_incompletos": exemplos_incompletos,
            "nota": ("backtest_p1314_seco só considera concursos com >=13 jogos "
                      "válidos -- concursos_com_menos_de_13 explica boa parte da "
                      "diferença entre total_concursos_distintos e "
                      "concursos_avaliados no backtest."),
        })
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/db-info")
def db_info():
    try:
        schema = detectar_schema_jogos()
        conn = get_conn(); cur = conn.cursor()
        info = {"tabela_jogos_historicos": schema["tabela"], "schema_detectado": schema}
        if schema["existe"]:
            cur.execute(f"SELECT COUNT(*) FROM {schema['tabela']}")
            info["total_jogos"] = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(DISTINCT UPPER(TRIM({schema['col_m']}))) FROM {schema['tabela']}")
            info["times_distintos"] = cur.fetchone()[0]
        conn.close()
        ratings, aviso_elo = calcular_elo_ratings()
        info["elo_iterativo"] = {
            "times_com_rating": len(ratings),
            "aviso": aviso_elo,
            "cache_idade_segundos": round(time.time() - _ELO_CACHE["ts"], 1),
            "cache_ttl_segundos": ELO_CACHE_TTL,
            "n_jogos_processados_no_ultimo_calculo": _ELO_CACHE["n_jogos"],
            "parametros": {"K": ELO_K, "HOME_ADV": ELO_HOME_ADV},
        }
        return jsonify({"status":"sucesso","banco":"postgresql" if USE_PG else "sqlite", **info})
    except Exception as e:
        return jsonify({"status":"erro","mensagem":str(e)}), 500

@app.route("/api/resultado", methods=["POST"])
def resultado():
    d = request.get_json() or {}
    res = d.get("resultado","")
    if res not in ["1","X","2"]:
        return jsonify({"status":"erro","mensagem":"resultado deve ser 1, X ou 2"}), 400
    try:
        conn = get_conn(); ph = _ph()
        conn.cursor().execute(
            f"INSERT INTO historico(concurso,mandante,visitante,resultado) VALUES({ph},{ph},{ph},{ph})",
            (d.get("concurso"), d.get("mandante",""), d.get("visitante",""), res))
        conn.commit(); conn.close()
        return jsonify({"status":"sucesso"})
    except Exception as e:
        return jsonify({"status":"erro","mensagem":str(e)}), 500

@app.route("/api/historico")
def historico():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM historico ORDER BY id DESC LIMIT 100")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        return jsonify({"status":"sucesso","total":len(rows),"registros":rows})
    except Exception as e:
        return jsonify({"status":"erro","mensagem":str(e)}), 500

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
