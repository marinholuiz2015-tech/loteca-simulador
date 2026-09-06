"""
Loteca Elite Pro — app.py v11.6
Mudança desta sessão (05/09/2026), depois da v11.5:

18) SUAVIZAÇÃO BAYESIANA no bucket empírico, substituindo o corte
    binário (n>=30 usa bucket / n<30 descarta tudo e cai pro fallback
    logístico). O corte criava descontinuidade artificial ("penhasco")
    e jogava fora informação parcial de faixas com pouca amostra.
    Fórmula nova: P(resultado) = (contagem_bucket + α×freq_global) /
    (n_bucket + α), com α=ELO_SHRINKAGE_ALFA=30 -- bucket vazio usa
    puro a distribuição global; bucket com muita amostra converge pro
    bucket puro; nada no meio é descartado, só pesa proporcionalmente.
    _elo_diff_para_probs() (curva logística) não é mais usada como
    fallback em elo_probs() -- o shrinkage cobre isso de forma contínua.
    calcular_elo_ratings() agora também rastreia a distribuição GLOBAL
    de 1/X/2 (não só por bucket) na mesma passada, usada como âncora do
    shrinkage. backtest_p1314_seco() atualizado pra usar a MESMA fórmula
    (produção e validação continuam consistentes, mesmo erro que corrigi
    antes entre curva-logística-fallback vs frequência-global-fallback).
    Testado localmente com 3 cenários: bucket bem povoado (converge pro
    valor real, 88% vs 85% real), bucket esparso (3 jogos de empate não
    viram "100% empate", ficou em 7,75%, puxado pela faixa), e times
    nunca vistos (caem numa estimativa sensata baseada na faixa de Elo,
    não em None nem em zero informação).
    IMPORTANTE, ainda em aberto: essa mudança só foi validada com dado
    SINTÉTICO (mecânica do código correta). AINDA NÃO rodou contra o
    banco real de produção -- próximo passo obrigatório antes de confiar
    cegamente: /api/backtest-p1314?comparar=1 em produção, pra saber o
    número real (tipo o 4,18%/2,60% medido por outra sessão) com essa
    fórmula nova.

Herda tudo da v11.5 abaixo:

17) BASELINE REAL "13 SECOS + 1 DUPLO" no backtest P(13/14) -- achado
    trazido pelo usuário de outra sessão em paralelo: a Loteca NÃO
    permite apostar 14 secos puro -- a aposta mínima (R$4,00) já é
    obrigatoriamente 13 secos + 1 duplo. O backtest_p1314_seco() media
    "14 secos puro", um cenário que na prática ninguém consegue apostar
    -- resultado mais pessimista que a realidade.
    Corrigido: backtest_p1314_seco() agora aceita `baseline="13s_1d"`
    (padrão) ou `baseline="14s_puro"` (só como referência teórica). No
    modo 13s_1d, o jogo MAIS INCERTO do cartão (menor probabilidade do
    favorito) recebe o duplo -- cobre os dois resultados mais prováveis
    daquele jogo específico -- heurística padrão de quem aposta de
    verdade, e não custa nada a mais que o seco puro (mesmo mínimo
    padrão da Loteca).
    Novo parâmetro na rota: /api/backtest-p1314?comparar=1 roda os dois
    baselines lado a lado e calcula o ganho relativo -- é "de graça",
    já que os dois têm o mesmo custo mínimo.
    Testado localmente com dado sintético (jogos de confiança variada,
    incluindo confrontos genuinamente incertos) -- 13s_1d mostrou ganho
    real e mensurável sobre 14s_puro (103% de melhora relativa em
    P(13+) nesse teste), confirmando que a lógica funciona na direção
    certa.
    IMPORTANTE: essa mudança é só de MEDIÇÃO (como avaliamos o motor).
    Ainda não mexe em elo_probs()/classificar() (a lógica de produção
    que decide SECO/DUPLO/TRIPLO real pro usuário) -- só corrige o
    critério de validação pra refletir a estrutura real da aposta.

Herda tudo da v11.4 abaixo:

16) BACKTEST P(13/14) REAL POR CARTÃO — porta FIEL de elo_p1314_seco.py
    (sessão de desambiguação, 31/08-05/09/2026), o código exato que
    gerou os números 4,18% vs 2,60% mencionados nos resumos. Novo
    endpoint /api/backtest-p1314 mede a força REAL do motor jogando
    SECO puro (1 palpite/jogo, sem hedge/duplo/triplo), via P(13/14)
    exato por cartão (Poisson-Binomial), comparando o que o modelo
    previa (média da própria confiança) contra o que realmente
    aconteceu -- a métrica de sucesso real do projeto, confirmada pelo
    usuário: acertar 13/14 toda semana, 14/14 pelo menos 1x/mês.
    Diferenças importantes corrigidas em relação ao que eu tinha
    implementado sozinho na v11.3 (backtest_elo_walkforward):
    - Fallback de bucket esparso é a FREQUÊNCIA GLOBAL observada até
      aquele ponto, não a curva logística -- é o que foi validado.
    - Elo atualizado em LOTE por concurso (todos os jogos de um cartão
      usam o Elo de ANTES daquele concurso começar), não jogo a jogo --
      reflete a realidade de apostar nos 14 de uma vez.
    - bucket_id = round(diff/50), não floor(diff//50).
    Testado localmente com dado sintético de probabilidade conhecida
    (85% favorito) -- calibração quase perfeita (P13+ previsto 37,54%
    vs realizado 35%; P14 previsto 11,57% vs realizado 11,5%),
    confirmando que a porta está mecanicamente correta.
    Ainda NÃO trocado dentro de elo_probs() (produção) -- esse backtest
    só mede/valida; a v11.3 (bucket com fallback logístico) continua
    sendo a fonte usada em /api/analisar e /api/grade-automatica.
    Próximo passo natural: rodar /api/backtest-p1314 em produção com os
    dados reais (17k+ jogos, desambiguação de nomes já aplicada) e
    comparar contra os 4,18%/2,60% da referência; se bater, considerar
    também adotar frequência global (em vez de curva logística) como
    fallback dentro de elo_probs(), pra produção e validação usarem
    exatamente a mesma fórmula ponta a ponta.

Herda tudo da v11.3 abaixo:

15) BUCKET EMPÍRICO como fonte primária de P(1)/P(X)/P(2), substituindo
    a curva logística paramétrica (que virou fallback só pra faixas de
    Elo com pouca amostra). Achado de outra sessão em paralelo (resumo
    "Desambiguação de Times + Fórmula Elo", 31/08-05/09/2026), validado
    contra P(13/14) real em 1.268 concursos: a curva logística previa
    5,97% de chance de bater 13+ pontos, mas na realidade batia só 2,60%
    (superconfiante em ~2,3x); o bucket empírico previa 5,25% e batia
    4,18% -- muito mais calibrado, 60% mais cartões de 13+ (53 vs 33) e
    quase o dobro de 14/14 (11 vs 6) no mesmo histórico.
    calcular_elo_ratings() agora constrói a tabela de bucket na MESMA
    passada que calcula o Elo (sem custo extra), agrupando por faixa de
    diferença de Elo (largura 50) e contando a frequência REAL de 1/X/2
    observada -- SEM VAZAMENTO (conta o resultado de cada jogo só DEPOIS
    de já ter calculado a previsão daquele jogo). elo_probs() usa essa
    tabela quando a faixa tem ELO_BUCKET_MIN_AMOSTRAS (30) ou mais;
    senão cai pro fallback logístico (_elo_diff_para_probs(), mesma
    fórmula de antes).
    Novo endpoint /api/backtest-elo compara as duas fórmulas lado a lado
    (acurácia, Brier Score), walk-forward sem vazamento em nenhuma das
    duas (bucket também construído incrementalmente no teste, não usa a
    tabela final inteira). Testado localmente com dados sintéticos com
    viés conhecido (time muito mais forte, empate raro na realidade) --
    bucket empírico teve Brier melhor (0,0724 vs 0,083), confirmando que
    aprende o padrão que a curva paramétrica não capta sozinha.
    Pendente: validar isso especificamente no critério real do projeto
    (P13/14 por cartão, agrupando os 14 jogos de cada concurso via
    Poisson-Binomial) -- precisa da coluna de agrupamento por concurso
    confiável, ainda não confirmada neste ambiente. O teste_p1314.py da
    outra sessão faz exatamente isso; portar quando disponível.

Herda tudo da v11.2 abaixo:

14) PLACAR AO VIVO (informativo, nunca entra no cálculo de probabilidade
    ou confiança -- decisão explícita do usuário). Usa a API-Football já
    configurada (RAPIDAPI_KEY, endpoint football-current-live,
    confirmado via RapidAPI Playground). buscar_placar_ao_vivo() faz uma
    chamada só por requisição (todos os jogos ao vivo do mundo no
    momento), reaproveitada pros 14 jogos da grade.
    casar_placar_ao_vivo() casa cada jogo da Loteca com o jogo ao vivo
    correspondente por nome normalizado (maiusculo, sem acento -- testado
    até com Fenerbahçe/Beşiktaş). Best-effort: nomes muito diferentes
    entre as duas fontes podem não casar, retorna null nesse caso sem
    quebrar o resto da resposta. Cada jogo em /api/grade-automatica ganha
    o campo "placar_ao_vivo": {"placar","minuto","em_andamento","encerrado"}
    ou null.

Herda tudo da v11.1 abaixo:

13) BLOQUEIO 403 DA CAIXA CONFIRMADO EM PRODUÇÃO (logs do Render, mesmo
    já com os headers de navegador do v10.3): é bloqueio por IP/ASN de
    datacenter, não por cabeçalho -- header não resolve isso.
    Solução implementada: cache desacoplado via GitHub Actions.
    - .github/workflows/fetch_loteca.yml roda a cada 30 min (e sob
      demanda), busca o concurso na Caixa a partir da rede do GitHub
      Actions (ASN diferente do Render), grava em data/cef_cache.json e
      commita no repo.
    - buscar_cef_cache_github() lê esse arquivo via
      raw.githubusercontent.com (domínio público comum, sem relação com
      o WAF da Caixa) quando a chamada direta falha.
    - grade_automatica() agora tenta em cascata: direto na Caixa → cache
      do GitHub Actions → exemplo fixo (só como último recurso, sempre
      identificado como exemplo). Resposta inclui "fonte" explícito
      (caixa_ao_vivo_direto / caixa_ao_vivo_cache_github /
      EXEMPLO_FIXO_NAO_AO_VIVO) e "cache_idade_minutos" quando vier do
      cache, pra nunca esconder de onde veio o dado nem sua idade.
    Ainda não testado ponta a ponta em produção -- depende do workflow
    ser adicionado ao repo e rodar ao menos uma vez. Se o runner do
    GitHub Actions TAMBÉM tomar 403, o bloqueio da Caixa é mais amplo
    que só o ASN do Render, e aí o próximo recurso é um proxy de
    scraping pago (ScraperAPI/ScrapingBee/Bright Data) -- solução padrão
    da indústria pra esse tipo de bloqueio, não gambiarra.

Herda a integração do Elo iterativo (K=30, HOME_ADV=75) como motor
principal, já validada em produção (v11.0), e as correções da v10.4
(RAPIDAPI_KEY vs APIFOOTBALL_KEY) e v10.3 (headers de navegador em
buscar_cef(), mantidos mesmo não resolvendo o bloqueio sozinhos --
não fazem mal e talvez ajudem se o bloqueio um dia for por assinatura
de header também):

12) MOTOR TROCADO PRA ELO ITERATIVO (K=30, HOME_ADV=75), substituindo
    H2H+Poisson+shrinkage como fonte principal de previsão -- decisão já
    registrada no resumo da sessão anterior, baseada no walk-forward sem
    vazamento (comparativo_h2h_poisson_vs_elo.py, 17.742 jogos):
      Acuracia:   48,9% (Elo) vs 47,4% (H2H+Poisson)
      Brier:      0,6213 (Elo, melhor) vs 0,6279 (H2H+Poisson)
      Acerto "2": 31,7% (Elo) vs 1,9% (H2H+Poisson)
    Implementado: calcular_elo_ratings() faz replay cronológico completo
    da tabela histórica real (detecta coluna de data/concurso pra ordenar;
    se não achar nenhuma, usa ordem de inserção com AVISO explícito no
    /api/db-info -- nunca falha silenciosamente). elo_probs() converte
    Elo em P(1/X/2) via expected-score logístico + modelo de largura de
    empate -- é uma APROXIMAÇÃO documentada, não a bucket empírica exata
    do walk-forward original (essa vive em comparativo_h2h_poisson_vs_elo.py,
    ainda não portada). buscar_h2h_real()/buscar_medias_gols_real() ficam
    no arquivo, sem uso por padrão -- fallback total (sem banco) ainda usa
    Elo fixo genérico + Poisson por liga, como antes.
    Testado localmente com dados sintéticos (times fortes/fracos/parelhos)
    antes do commit -- comportamento validado, mas ainda NÃO testado
    contra os dados reais de produção. Próximo passo: rodar
    /api/analisar num confronto conhecido e conferir /api/db-info →
    elo_iterativo pra ver se o aviso de ordem aparece ou não.

Herda a correção da v10.4 (RAPIDAPI_KEY vs APIFOOTBALL_KEY) e da v10.3
(headers de navegador em buscar_cef() pro bloqueio 403 da Caixa):

10) grade_automatica() buscava sempre o ÚLTIMO concurso, que na API da
    Caixa (sem número específico) é o mais recente já FECHADO/disputado
    (com resultado), não o próximo aberto pra aposta. Descoberto ao
    testar com o concurso real: API devolvia #1268 (já com gols
    preenchidos), quando o aberto de verdade era #1269. Corrigido: agora
    busca o campo "numeroConcursoProximo" da resposta e faz uma segunda
    chamada específica pra esse número, priorizando ele sempre que tiver
    jogos publicados.

Herda todas as correções da v10.2 (bug de detecção de coluna mandante/
visitante, preço R$2,00/combinação) e da v10.1 (H2H_MIN=20, shrinkage
bayesiano) -- ver changelog completo nessas versões.

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
# Achado pendente (resumo 01-02/09/2026): no Render a variável foi
# criada como APIFOOTBALL_KEY, mas o código sempre leu RAPIDAPI_KEY --
# ou seja, a API-Football nunca tinha a chave de verdade em produção.
# Corrigido aceitando os dois nomes (RAPIDAPI_KEY tem prioridade se
# alguém também criar esse, senão cai pro nome que já existe no Render).
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "") or os.getenv("APIFOOTBALL_KEY", "")
ODDS_KEY     = os.getenv("ODDS_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG       = DATABASE_URL.startswith("postgres")

# Cache publicado pelo GitHub Actions (fetch_loteca.yml) -- usado quando
# a Caixa bloqueia o IP do Render direto (403 confirmado em produção,
# 04-05/09/2026). Configuravel via env var pra não ficar hardcoded caso
# o repo mude de nome/dono.
GITHUB_REPO_CACHE   = os.getenv("GITHUB_REPO_CACHE", "marinholuiz2015-tech/loteca-simulador")
GITHUB_BRANCH_CACHE = os.getenv("GITHUB_BRANCH_CACHE", "main")

APIF_HOST = "free-api-live-football-data.p.rapidapi.com"
APIF_BASE = f"https://{APIF_HOST}"
URL_CEF   = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca"

# ─── Constantes validadas no walk-forward de hoje ─────────────
H2H_MIN      = 20  # corte minimo de confrontos p/ usar H2H (era 3 na v10.0)
SHRINKAGE_K  = 15  # forca do prior de liga nas medias de gols (Empirical Bayes)

# ─── Banco de dados ───────────────────────────────────────────
def get_conn():
    if USE_PG:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(os.getenv("SQLITE_PATH", "/tmp/loteca_elite.db"))
    conn.row_factory = sqlite3.Row
    return conn

def _ph():
    """Placeholder de parametro SQL -- %s no Postgres, ? no SQLite."""
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

# ─── Detecção de schema da tabela de jogos historicos ─────────
_SCHEMA_CACHE = {"ts": 0, "info": None}

def detectar_schema_jogos():
    """Detecta nome da tabela e das colunas de gols/posicao, na tabela
    de jogos historicos -- sem assumir nada, sempre consultando o banco
    de verdade (mesma logica ja validada hoje contra os dois formatos
    de schema que apareceram: jogos_loteca/jogos, gols_m/gols_mandante)."""
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
                cur = [(r[1],) for r in cols_raw]  # normaliza formato
            cols = [r[0] for r in (cur if isinstance(cur, list) else cur.fetchall())]
            # colunas de time -- prioriza normalizado (mais limpo, sem duplicidade
            # de nomes tipo "São Caetano" vs "SAO CAETANO"), com fallback pros
            # outros formatos ja vistos no schema real
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
    """Converte valor de gol pra int, tolerando TEXT, None, ou ja-int
    (a migracao de hoje recriou a tabela com colunas TEXT -- precisa
    ser tolerante a isso, sem quebrar)."""
    if v is None: return None
    if isinstance(v, (int, float)): return int(v)
    try: return int(str(v).strip())
    except (ValueError, TypeError): return None

def _parse_num(v):
    """Como _parse_gol, mas preserva casas decimais (usado em AVG de liga)."""
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).strip())
    except (ValueError, TypeError): return None

# ─── Consulta de dado historico REAL (corrige achado #1) ──────
def buscar_h2h_real(mandante, visitante):
    """H2H direto do banco, nomes normalizados p/ maiusculo dos dois lados.
    Corte minimo H2H_MIN=20 (validado no walk-forward de hoje -- corte de
    3 deixava passar ruido estatistico como se fosse sinal)."""
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
    """Media real de gols (casa/fora) da liga, calculada do banco --
    usada como prior (ancora) do shrinkage nas medias por time. Cai pro
    dicionario MEDIA_GOLS fixo só se nao houver coluna de liga no schema
    ou nao houver dado suficiente pra essa liga especifica."""
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
            if n >= 10:  # amostra minima pra confiar na media da propria liga
                return {"casa": round(soma_gm/n, 3), "fora": round(soma_gv/n, 3)}
        except Exception as e:
            log.warning("buscar_media_liga_gols: %s", e)
    return MEDIA_GOLS.get(liga, {"casa": 1.40, "fora": 1.05})

def buscar_medias_gols_real(time_nome, mandante=True, liga="_default"):
    """Media de gols pro/contra de um time jogando em casa ou fora,
    calculada do historico real, com shrinkage bayesiano em direcao a
    media real da liga (achado #7): quanto menos jogos o time tem, mais
    a estimativa pende pra media da liga; quanto mais jogos, mais pende
    pro dado proprio do time. SHRINKAGE_K=15 -> em n=15, peso 50/50."""
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

# ─── ELO ITERATIVO (K=30, HOME_ADV=75) — MOTOR PRINCIPAL ──────
# Decisão de 02/09/2026 (comparativo_h2h_poisson_vs_elo.py, walk-forward
# sem vazamento, 17.742 jogos): Elo bateu H2H+Poisson+shrinkage com folga
#   Acuracia:    48,9% (Elo) vs 47,4% (H2H+Poisson)
#   Brier Score: 0,6213 (Elo, melhor) vs 0,6279 (H2H+Poisson)
#   Acerto qdo real=2 (visitante): 31,7% (Elo) vs 1,9% (H2H+Poisson)
# O H2H+Poisson+shrinkage, mesmo corrigido, virava "aposte no mandante"
# disfarcado porque a maioria dos jogos cai no prior da liga sem H2H
# suficiente pra corrigir. Por isso o Elo substitui H2H+Poisson como
# fonte principal aqui -- buscar_h2h_real()/buscar_medias_gols_real()
# continuam no arquivo (podem virar blend depois), mas nao sao mais
# chamadas por padrao.
#
# RESSALVA (herdada do resumo da sessao): a formula de probabilidade
# 1/X/2 abaixo (expected-score logistico padrao de Elo + modelo de
# largura de empate) é uma APROXIMACAO -- nao é a bucket empirica exata
# que gerou os 48,9% no walk-forward original (essa bucket vive em
# comparativo_h2h_poisson_vs_elo.py, ainda nao portada pra ca). Testar
# em producao (/api/analisar) e comparar contra o comportamento esperado
# antes de confiar de olhos fechados.

ELO_K        = 30
ELO_HOME_ADV = 75
ELO_CACHE_TTL = 6 * 3600  # recalcular do zero em toda requisicao seria caro (17k+ jogos)
_ELO_CACHE = {"ts": 0, "ratings": None, "aviso": None, "n_jogos": 0, "buckets": None, "global_dist": None}

ELO_BUCKET_LARGURA = 50   # largura da faixa de diferenca de Elo (pontos)
ELO_SHRINKAGE_ALFA = 30   # forca do shrinkage bayesiano pro bucket empirico --
                          # em n_bucket=ELO_SHRINKAGE_ALFA, bucket e distribuicao
                          # global pesam igual; mais amostra pesa mais o bucket,
                          # menos amostra puxa mais pra global. Sem "penhasco":
                          # nenhuma faixa é descartada inteira, mesmo com pouca
                          # amostra -- ela só pesa menos, proporcionalmente.

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
    """Ordem cronologica é essencial pro Elo iterativo -- sem ela, os
    ratings ficam errados de um jeito que NAO aparece em nenhum erro,
    a mesma familia de bug silencioso ja vista neste projeto (schema
    cego). Tenta achar coluna de data primeiro, depois numero do
    concurso; se nao achar nenhuma, usa a ordem de insercao (id/rowid)
    como ultimo recurso, mas marca aviso explicito -- isso NAO é garantia
    de ordem cronologica real e precisa ser conferido manualmente."""
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

def calcular_elo_ratings():
    """Replay cronologico completo da tabela historica real, calculando
    Elo de todos os times do zero (K=30, HOME_ADV=75). Na MESMA passada,
    constrói a tabela de calibração por bucket empírico: agrupa jogos por
    faixa de diferença de Elo (largura ELO_BUCKET_LARGURA) e conta a
    frequência REAL de 1/X/2 observada em cada faixa -- achado da sessão
    de desambiguação (31/08-05/09/2026): essa calibração empírica bate a
    curva logística paramétrica no critério que importa (P13/14 real:
    4,18% batido vs 5,25% previsto pro bucket, contra 2,60% batido vs
    5,97% previsto pela curva -- a curva estava superconfiante em ~2,3x).
    Cacheado por ELO_CACHE_TTL. Retorna (ratings_dict, aviso_ou_None)."""
    if (time.time() - _ELO_CACHE["ts"] < ELO_CACHE_TTL
            and _ELO_CACHE["ratings"] is not None):
        return _ELO_CACHE["ratings"], _ELO_CACHE["aviso"]

    schema = detectar_schema_jogos()
    ratings = defaultdict(lambda: 1500.0)
    buckets = defaultdict(lambda: {"1": 0, "X": 0, "2": 0})
    global_cnt = {"1": 0, "X": 0, "2": 0}
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
            FROM {schema['tabela']} {order_clause}
        """)
        linhas = cur.fetchall()
        conn.close()

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
            buckets[_bucket_de_diff(diff)][real] += 1  # calibração ANTES de atualizar -- sem vazamento
            global_cnt[real] += 1
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
                    else {"1": 0.4722, "X": 0.2616, "2": 0.2663})  # prior neutro se banco vazio
    _ELO_CACHE.update(ts=time.time(), ratings=resultado, aviso=aviso,
                       n_jogos=n_processados, buckets=buckets_dict, global_dist=global_dist)
    return resultado, aviso

def elo_time(nome):
    """Elo iterativo real de um time (le do cache calculado por
    calcular_elo_ratings()). Se o time nao apareceu em nenhum jogo do
    historico, comeca em 1500 (rating inicial padrao)."""
    ratings, _ = calcular_elo_ratings()
    return round(ratings.get(nome.upper().strip(), 1500.0), 1)

def _elo_diff_para_probs(diff):
    """Fórmula pura Elo-diff -> P(1)/P(X)/P(2), sem consultar banco.
    Extraída de elo_probs() pra garantir que o backtest walk-forward
    (backtest_elo_walkforward, abaixo) testa EXATAMENTE a mesma fórmula
    que está em produção -- nunca duas versões que podem divergir sem
    ninguém notar."""
    we = 1 / (1 + 10 ** (-diff / 400))  # expected score do mandante (empate=0,5pt)
    largura_empate = max(0.12, 0.24 * math.exp(-abs(diff) / 600))
    p1 = max(0.02, we - largura_empate / 2)
    p2 = max(0.02, (1 - we) - largura_empate / 2)
    px = largura_empate
    t = p1 + px + p2
    return {"1": p1 / t, "X": px / t, "2": p2 / t}, we

def _probs_bucket_empirico(diff):
    """P(1)/P(X)/P(2) via suavização Bayesiana (shrinkage tipo Dirichlet)
    do bucket empírico em direção à distribuição GLOBAL observada --
    substitui o corte binário anterior (n>=30 usa bucket / n<30 descarta
    tudo e usa só fallback), que criava descontinuidade artificial e
    jogava fora informação parcial de faixas com pouca amostra.
    Fórmula: P(resultado) = (contagem_bucket + α×freq_global) / (n_bucket + α).
    Com α=ELO_SHRINKAGE_ALFA: bucket vazio -> puro global; bucket com
    muita amostra -> puro bucket; nada no meio é descartado, só pesa
    proporcionalmente. Nunca retorna None -- sempre há pelo menos a
    distribuição global como base (mesmo p/ faixas nunca vistas)."""
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
    """Converte Elo (com vantagem de mandante) em P(1)/P(X)/P(2).
    Fonte: bucket empírico com suavização Bayesiana em direção à
    distribuição global (_probs_bucket_empirico) -- nunca cai pro
    fallback logístico separado, porque o shrinkage já cobre faixas com
    pouca amostra de forma contínua e proporcional, sem descontinuidade.
    Validado contra P(13/14) real em 1.268 concursos (metodologia com
    corte binário, versão anterior desta função): bucket empírico bate
    4,18% das vezes contra 5,25% previsto (bem calibrado), enquanto a
    curva logística batia só 2,60% contra 5,97% previsto (superconfiante
    em ~2,3x). A suavização contínua deve preservar ou melhorar isso,
    já que usa mais informação (nenhuma faixa é 100% descartada)."""
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
    """Walk-forward SEM VAZAMENTO comparando as duas fórmulas lado a lado:
    bucket empírico (fonte primária em produção) vs curva logística
    (fallback). Pra cada jogo, ANTES de atualizar Elo E ANTES de contar o
    resultado no bucket, calcula a previsão das duas fórmulas usando só o
    que já foi visto até aquele ponto -- exatamente como seria numa
    previsão real. O bucket empírico aqui é construído incrementalmente
    (não usa a tabela final inteira), pra não vazar o resultado do
    próprio jogo sendo testado pra dentro do bucket que o prevê.
    Existe pra confirmar, com o histórico completo, se a vantagem
    encontrada pela sessão de desambiguação (4,18% vs 2,60% de acerto em
    13+/cartão) se sustenta também nessa base de dados corrigida."""
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
        FROM {schema['tabela']} {order_clause} {limit_clause}
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

        probs_curva, we = _elo_diff_para_probs(diff)  # sempre disponível

        b = _bucket_de_diff(diff)
        contagem = buckets_ate_agora.get(b)
        n_bucket = sum(contagem.values()) if contagem else 0
        if contagem and n_bucket >= ELO_BUCKET_MIN_AMOSTRAS:
            probs_bucket = {k: contagem[k] / n_bucket for k in ("1", "X", "2")}
            stats["bucket_empirico"]["n_usou_bucket"] += 1
        else:
            probs_bucket = probs_curva  # mesmo fallback usado em produção
            stats["bucket_empirico"]["n_usou_fallback"] += 1

        n_total += 1
        dist_real[real] += 1

        for nome, probs in (("bucket_empirico", probs_bucket), ("curva_logistica", probs_curva)):
            previsto = max(probs, key=probs.get)
            if previsto == real:
                stats[nome]["acertos"] += 1
            stats[nome]["soma_brier"] += sum(
                (probs[k] - (1.0 if k == real else 0.0)) ** 2 for k in ("1", "X", "2"))

        # atualiza bucket e Elo SÓ DEPOIS de prever -- sem vazamento em nenhuma das duas fórmulas
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
    """Detecta colunas de agrupamento por concurso e de ordem do jogo
    dentro do concurso -- necessário pro backtest de P(13/14) por
    cartão real (14 jogos por concurso). Retorna (col_concurso, col_seq),
    qualquer um pode vir None se não encontrado."""
    col_concurso = next((c for c in ["concurso", "numero_concurso"] if c in cols), None)
    col_seq = next((c for c in ["sequencial", "numero_jogo", "jogo", "ordem"] if c in cols), None)
    return col_concurso, col_seq

def _poisson_binomial(probs_acerto):
    """PMF exata do número de acertos, dado uma lista de probabilidades
    de acerto (uma por jogo). DP clássico O(n²). Idêntico ao usado em
    elo_p1314_seco.py (sessão de desambiguação, 31/08-05/09/2026)."""
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
    """Porta FIEL de elo_p1314_seco.py (sessão de desambiguação,
    31/08-05/09/2026) -- mede a força REAL do motor via P(13/14) exato
    por cartão (Poisson-Binomial), comparando o que o modelo previa
    (média da própria confiança) contra o que realmente aconteceu.
    Metodologia EXATA da referência:
    - Elo (K=30, HOME_ADV=75) atualizado em LOTE por concurso -- todos
      os jogos de um mesmo concurso usam o Elo de ANTES daquele
      concurso começar (reflete a realidade de apostar nos 14 de uma
      vez, sem saber resultado parcial de nenhum).
    - Bucket empírico por faixa de diferença de Elo (bucket=round(diff/50)),
      mínimo 15 amostras; sem amostra suficiente, cai pra frequência
      GLOBAL observada até aquele ponto (não a curva logística).

    `baseline` controla a estrutura de aposta testada:
    - "14s_puro": 14 secos (1 palpite por jogo) -- é o que a referência
      testou, mas NINGUÉM aposta assim de verdade: a Loteca não permite
      aposta de 14 secos puro.
    - "13s_1d" (padrão, é o mínimo REAL da Loteca, R$4,00): 13 secos +
      1 duplo obrigatório. O duplo cobre os dois resultados mais
      prováveis (1+X, 1+2 ou X+2) do jogo MAIS incerto do cartão
      (heurística padrão -- proteger onde a confiança é menor). Isso
      não custa nada a mais que o seco puro (é o próprio mínimo padrão),
      então qualquer ganho aqui é "de graça" na comparação."""
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

    aviso_ordem_interna = None if col_seq else (
        "Sem coluna de sequencial/ordem dentro do concurso -- a ordem dos "
        "jogos num mesmo cartão pode não refletir a numeração real (1 a 14), "
        "mas isso não afeta o cálculo em si, só a leitura de qual jogo é qual.")
    order_extra = f", {col_seq}" if col_seq else ""

    try:
        if col_resultado:
            cur.execute(f"""
                SELECT {col_concurso}, {schema['col_m']}, {schema['col_v']}, {col_resultado}
                FROM {schema['tabela']}
                WHERE {col_resultado} IN ('1','X','2')
                ORDER BY {col_concurso} {order_extra}
            """)
            linhas = [(conc, m, v, res) for conc, m, v, res in cur.fetchall()]
        elif schema["col_gm"] and schema["col_gv"]:
            cur.execute(f"""
                SELECT {col_concurso}, {schema['col_m']}, {schema['col_v']},
                       {schema['col_gm']}, {schema['col_gv']}
                FROM {schema['tabela']}
                ORDER BY {col_concurso} {order_extra}
            """)
            linhas = []
            for conc, m, v, gm, gv in cur.fetchall():
                gm2, gv2 = _parse_gol(gm), _parse_gol(gv)
                if gm2 is None or gv2 is None:
                    continue
                res = "1" if gm2 > gv2 else ("2" if gm2 < gv2 else "X")
                linhas.append((conc, m, v, res))
        else:
            conn.close()
            return {"erro": "sem_coluna_resultado_nem_gols"}
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
    # agora guarda (p1, px, p2, resultado_real) por jogo -- não só o
    # palpite favorito -- pra poder computar seco puro E 13S+1D na mesma
    # passada, sem duplicar o cálculo de Elo/bucket
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
            global_p = {"1": 0.4722, "X": 0.2616, "2": 0.2663}  # prior inicial
        # MESMA suavização Bayesiana usada em produção (_probs_bucket_empirico)
        # -- sem isso, backtest e produção medem/usam fórmulas diferentes
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
        """Retorna (prob_de_acerto, acertou) pro jogo. Se cobrir_2=True,
        cobre os DOIS resultados mais prováveis (duplo); senão só o
        favorito (seco)."""
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

        if baseline == "13s_1d" and n_jogos >= 1:
            # acha o jogo MAIS incerto (menor prob do favorito) pra
            # receber o duplo -- heurística padrão de quem aposta
            idx_incerto = min(range(n_jogos), key=lambda i: max(lista[i][0], lista[i][1], lista[i][2]))
        else:
            idx_incerto = None  # nenhum jogo recebe duplo -- seco puro

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
                         f"com duplo (2 resultados), igual à aposta mínima real da Loteca."),
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

# ─── ELO fixo — só usado se o banco estiver mesmo indisponível ─
ELO_FALLBACK = {
    "ARGENTINA":2140,"FRANÇA":2100,"INGLATERRA":2080,"ESPANHA":2070,
    "ALEMANHA":2060,"PORTUGAL":2040,"HOLANDA":2030,"BRASIL":2050,
    "PALMEIRAS":1820,"FLAMENGO":1810,"BOTAFOGO":1780,"FLUMINENSE":1750,
    "ATLETICO MG":1760,"SÃO PAULO":1740,"CORINTHIANS":1720,"GRÊMIO":1700,
    "INTERNACIONAL":1710,"CRUZEIRO":1690,"VASCO DA GAMA":1660,"SANTOS":1650,
    "FORTALEZA":1670,"BAHIA":1640,"MIRASSOL":1610,"JUVENTUDE":1590,
    "VITÓRIA":1580,"SPORT":1560,"BRAGANTINO":1620,"ATHLETICO PR":1660,
}

# ─── Poisson bivariado — usado só no fallback total (banco indisponível) ──
def _poi(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def poisson_probs(mandante, visitante, liga="_default"):
    # 1) motor principal: Elo iterativo (decisao de 02/09/2026)
    schema = detectar_schema_jogos()
    if schema["existe"] and schema["col_gm"] and schema["col_gv"]:
        ep = elo_probs(mandante, visitante)
        if ep and ep.get("fonte_base") not in (None,):
            return ep

    # 2) fallback total: banco indisponivel/schema nao detectado --
    #    Elo fixo generico + media de gols generica por liga (comportamento
    #    antigo, agora so usado quando de fato nao ha banco pra consultar)
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
            if i > j:    p1 += p
            elif i == j: px += p
            else:        p2 += p
    t = p1 + px + p2
    return {
        "1": round(p1/t, 4), "X": round(px/t, 4), "2": round(p2/t, 4),
        "elo_casa": ec, "elo_fora": ef,
        "lam_casa": round(lc, 3), "lam_fora": round(lf, 3),
        "fonte_base": "fallback_elo_generico_SEM_BANCO",
    }

# ─── Remoção de margem ────────────────────────────────────────
def sem_margem(o1, ox, o2):
    r1, rx, r2 = 1/o1, 1/ox, 1/o2
    over = r1 + rx + r2
    return {"1":round(r1/over,4),"X":round(rx/over,4),"2":round(r2/over,4),"over":round(over,4)}

# ─── Blending ponderado — peso marcado como NAO CALIBRADO (achado #5) ─
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

# ─── Classificação Loteca ──────────────────────────────────────
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

# ─── Kelly Criterion (ja estava correto, mantido) ─────────────
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
    def c(d,t): return max(4.00, round((2**d)*(3**t)*2.0, 2))  # R$2,00/combinação, confirmado nas regras oficiais da Caixa (não R$3,00)
    return {
        "secos": sum(1 for j in jogos if j["classificacao"]["tipo"]=="SECO"),
        "duplos": nd, "triplos": nt,
        "custo_minimo":      c(nd, 0),
        "custo_recomendado": c(nd, min(nt,1)),
        "custo_completo":    c(nd, nt),
    }

# ─── API-Football (opcional, ja estava ok) ─────────────────────
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

# ─── Placar ao vivo (informativo, 05/09/2026) ──────────────────
# Endpoint confirmado via RapidAPI Playground: football-current-live,
# retorna response.live[] com todos os jogos em andamento no mundo no
# momento da chamada. Usado só pra mostrar o placar junto de cada jogo
# da grade -- NUNCA entra no cálculo de probabilidade/confiança (decisão
# explícita: só informativo). Best-effort: se a API falhar ou não achar
# o jogo (nomes de time não batem entre as duas fontes), retorna None
# silenciosamente, sem quebrar o resto da resposta.
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
    """Tenta achar, entre os jogos ao vivo do momento (API-Football), um
    que bata com o confronto mandante x visitante da Loteca. Comparação
    por nome normalizado (maiusculo, sem acento) contra "name" e
    "longName" dos dois lados -- best-effort, times com nomes muito
    diferentes entre as duas fontes (ex: abreviações tipo "ATLETICO MG"
    vs "Atletico Mineiro") podem não casar. Retorna None se não achar."""
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

# ─── The Odds API (opcional, ja estava ok) ─────────────────────
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

# ─── Caixa (CEF) — grade e resultado REAIS (corrige achado #3) ───
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
    """Fallback pro bloqueio 403 confirmado em produção (04-05/09/2026):
    lê o cache publicado por um job agendado do GitHub Actions, que
    busca a Caixa a partir de outra rede (não o IP do Render). Servido
    via raw.githubusercontent.com -- domínio público comum, sem nenhuma
    relação com o WAF da Caixa. Nunca finge que é dado direto ao vivo --
    quem chama isso precisa checar o campo "fetched_em_utc" pra saber a
    idade do cache."""
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
    """Validado hoje contra dado real da Caixa (concurso #1264) --
    resultado sempre vem null da API, calcula a partir dos gols."""
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

# ─── Concurso fixo — mantido só como FALLBACK EXPLICITO (achado #3) ───
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

# ─── Analisar jogo ───────────────────────────────────────────
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
        "odds_api":     {"configurada": bool(ODDS_KEY),     "status": "não configurada"},
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
        "status": "ok", "versao": "Loteca Elite Pro v11.6",
        "modelo": "elo_iterativo(K30,HA75) > fallback_elo_fixo+poisson_liga",
        "banco": "postgresql" if USE_PG else "sqlite",
        "apis": apis,
    })

@app.route("/")
@app.route("/api/grade-automatica")
def grade_automatica():
    """Tenta buscar o concurso AO VIVO real da Caixa, em cascata:
      1) direto na Caixa (funciona se o IP do Render não estiver bloqueado
         -- vale sempre tentar primeiro, sem custo, caso o bloqueio suma)
      2) cache publicado pelo GitHub Actions (fetch_loteca.yml) -- criado
         pra contornar o 403 confirmado em produção em 04-05/09/2026
      3) exemplo fixo, só como último recurso, sempre avisando que é
         exemplo e nunca fingindo ser dado ao vivo
    Busca especificamente o PRÓXIMO concurso ainda aberto pra aposta
    (achado de 03/09/2026: a API sem número devolve o último concurso já
    FECHADO/disputado -- o campo "numeroConcursoProximo" indica qual
    concurso buscar de verdade)."""
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

    # prioriza o concurso aberto (jogos ainda não realizados, pra apostar
    # de verdade); só cai pro último fechado se o aberto não tiver jogos
    # publicados ainda
    dados = dados_aberto if (dados_aberto and dados_aberto.get("listaResultadoEquipeEsportiva")) else dados_ultimo

    if dados:
        numero, jogos_cef = parsear_cef(dados.get("numero"), dados)
        if jogos_cef:
            banca = float(request.args.get("banca", 100))
            jogos_ao_vivo = buscar_placar_ao_vivo()  # 1 chamada só, reusada pros 14 jogos
            jogos = []
            for j in jogos_cef:
                analise = analisar_jogo(j["mandante"], j["visitante"], "_default", banca=banca)
                placar = casar_placar_ao_vivo(j["mandante"], j["visitante"], jogos_ao_vivo)
                jogos.append({**j, **analise, "placar_ao_vivo": placar})
            return jsonify({
                "status":"sucesso","concurso":numero,"fonte":fonte_dado,
                "concurso_ainda_aberto": dados is dados_aberto,
                "cache_idade_minutos": cache_idade_min,
                "total_jogos":len(jogos),"jogos":jogos,"painel":painel(jogos),
            })
    # fallback explicito -- só chega aqui se nem o direto nem o cache do
    # GitHub Actions deram certo
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
    """P(13/14) real por cartão -- a métrica de verdade do projeto (não
    acurácia média por jogo isolado). ?baseline=13s_1d (padrão, é a
    aposta mínima REAL da Loteca) ou ?baseline=14s_puro (referência
    teórica, ninguém aposta assim -- a Caixa não permite 14 secos puro).
    ?comparar=1 roda os dois baselines e retorna o ganho relativo."""
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
    """Compara bucket empírico vs curva logística no histórico real,
    walk-forward sem vazamento. Parâmetro opcional ?limite=N pra rodar
    com uma amostra menor (mais rápido, útil pra teste rápido)."""
    try:
        limite = request.args.get("limite")
        limite = int(limite) if limite else None
        resultado = backtest_elo_walkforward(limite)
        return jsonify({"status": "sucesso", **resultado})
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
        # diagnostico do Elo iterativo (motor principal, v11) -- expõe se
        # tem aviso de ordem cronologica, quantos jogos processou e a
        # idade do cache, no mesmo espirito de nunca falhar silenciosamente
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
