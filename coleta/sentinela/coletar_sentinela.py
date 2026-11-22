"""
Camada Sentinela: fatos de cada jogo da Loteca, coletados automaticamente.

Para cada jogo (concurso, jogo) acha a partida na FotMob pela data e pelos
nomes dos times e grava, com a hora da coleta:
  - desfalques de cada time (lesao/suspensao), quantidade e valor de mercado;
  - descanso: dias desde o ultimo jogo e jogos nos ultimos 14 dias;
  - forma: pontos nos ultimos 5 jogos (da propria FotMob, antes da partida);
  - clima no estadio no dia do jogo (chuva total do dia e temperatura media;
    historico pela NASA POWER, concurso aberto pela previsao da Open-Meteo);
  - campeonato e rodada.

Modos:
  python coleta/sentinela/coletar_sentinela.py historico   # jogos da base de odds (895+)
  python coleta/sentinela/coletar_sentinela.py aberto      # grade do concurso aberto (semanal)

Saidas:
  coleta/dados/sentinela_jogos.csv     (historico: 1 linha por jogo)
  coleta/dados/sentinela_aberto.csv    (concurso aberto: acrescenta a cada coleta, nunca sobrescreve)
Coleta leve: 1 pedido por vez com pausa, cache local de respostas.
"""
import csv
import datetime as dt
import difflib
import json
import os
import re
import sys
import time
import unicodedata

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
DADOS = os.path.join(REPO, "coleta", "dados")
CACHE = os.path.join(AQUI, "cache")
FOT = "https://www.fotmob.com/api/data"
HEAD = {"User-Agent": "Mozilla/5.0 (pesquisa pessoal; coleta leve)"}
PAUSA = float(os.environ.get("PAUSA", "0.6"))

CAMPOS = ["concurso", "jogo", "mandante", "visitante", "match_id", "fot_casa", "fot_fora", "liga", "liga_id",
          "rodada", "inicio_utc", "similaridade",
          "desf_casa_n", "desf_casa_valor", "desf_casa_lesao", "desf_casa_susp",
          "desf_fora_n", "desf_fora_valor", "desf_fora_lesao", "desf_fora_susp",
          "dias_casa", "dias_fora", "jogos14_casa", "jogos14_fora", "forma5_casa", "forma5_fora",
          "lat", "lon", "chuva_mm", "temp_c", "altitude_m", "trocas_casa", "trocas_fora", "h2h_n", "h2h_saldo", "invicto5_casa", "invicto5_fora", "coletado_em_utc"]

# nomes da Loteca -> nomes usados pela FotMob (so os que o parecido() nao resolve)
TROCAS = {
    "ATLETICO MG": "ATLETICO MINEIRO", "ATHLETICO PR": "ATHLETICO PARANAENSE", "ATLETICO GO": "ATLETICO GOIANIENSE",
    "AMERICA MG": "AMERICA MINEIRO", "AMERICA RN": "AMERICA RN", "SPORT PE": "SPORT RECIFE", "BOTAFOGO SP": "BOTAFOGO SP",
    "BOTAFOGO RJ": "BOTAFOGO", "BOTAFOGO PB": "BOTAFOGO PB", "NAUTICO PE": "NAUTICO", "CEARA CE": "CEARA",
    "VASCO DA GAMA RJ": "VASCO DA GAMA", "VASCO RJ": "VASCO DA GAMA", "SAO PAULO SP": "SAO PAULO", "RED BULL BRAGANTINO": "BRAGANTINO",
    "BRAGANTINO SP": "RED BULL BRAGANTINO", "CRB AL": "CRB", "CSA AL": "CSA", "ABC RN": "ABC", "VILA NOVA GO": "VILA NOVA",
    "GOIAS GO": "GOIAS", "CUIABA MT": "CUIABA", "PAYSANDU PA": "PAYSANDU", "REMO PA": "REMO", "AVAI SC": "AVAI",
    "CHAPECOENSE SC": "CHAPECOENSE", "FIGUEIRENSE SC": "FIGUEIRENSE", "CRICIUMA SC": "CRICIUMA", "JUVENTUDE RS": "JUVENTUDE",
    "INTERNACIONAL RS": "INTERNACIONAL", "GREMIO RS": "GREMIO", "OPERARIO PR": "OPERARIO FERROVIARIO", "LONDRINA PR": "LONDRINA",
    "CORITIBA PR": "CORITIBA", "GUARANI SP": "GUARANI", "PONTE PRETA SP": "PONTE PRETA", "MIRASSOL SP": "MIRASSOL",
    "NOVORIZONTINO SP": "NOVORIZONTINO", "ITUANO SP": "ITUANO", "SANTOS SP": "SANTOS", "PALMEIRAS SP": "PALMEIRAS",
    "CORINTHIANS SP": "CORINTHIANS", "FLAMENGO RJ": "FLAMENGO", "FLUMINENSE RJ": "FLUMINENSE", "CRUZEIRO MG": "CRUZEIRO",
    "BAHIA BA": "BAHIA", "VITORIA BA": "VITORIA", "FORTALEZA CE": "FORTALEZA", "SAMPAIO CORREA MA": "SAMPAIO CORREA",
    "TOMBENSE MG": "TOMBENSE", "ATLETICO MADRID": "ATLETICO MADRID", "INTER DE MILAO": "INTER", "MILAO": "MILAN",
    "ATALANTA BERGAMAS": "ATALANTA", "BAYERN DE MUNIQUE": "BAYERN MUNCHEN", "BAYERN MUNIQUE": "BAYERN MUNCHEN",
    "BORUSSIA DORTMUND": "DORTMUND", "NAPOLES": "NAPOLI", "SEVILHA": "SEVILLA", "MARSELHA": "MARSEILLE",
    "PARIS SAINT GERMAIN": "PARIS SAINT GERMAIN", "PSG": "PARIS SAINT GERMAIN", "TURIM": "TORINO", "GENOVA": "GENOA",
    "SPORTING": "SPORTING CP", "CELTA DE VIGO": "CELTA VIGO", "MANCHESTER UNITED": "MANCHESTER UNITED",
    "WOLVERHAMPTON": "WOLVERHAMPTON WANDERERS", "TOTTENHAM": "TOTTENHAM HOTSPUR", "NEWCASTLE": "NEWCASTLE UNITED",
    "WEST HAM": "WEST HAM UNITED", "BRIGHTON": "BRIGHTON AND HOVE ALBION", "LEEDS": "LEEDS UNITED",
}

PAISES = {"INGLATERRA": "ENGLAND", "ESTADOS UNIDOS": "USA", "EUA": "USA", "ALEMANHA": "GERMANY", "FRANCA": "FRANCE",
    "ESPANHA": "SPAIN", "ITALIA": "ITALY", "HOLANDA": "NETHERLANDS", "PAISES BAIXOS": "NETHERLANDS", "BELGICA": "BELGIUM",
    "CROACIA": "CROATIA", "SUICA": "SWITZERLAND", "SUECIA": "SWEDEN", "DINAMARCA": "DENMARK", "NORUEGA": "NORWAY",
    "POLONIA": "POLAND", "ESCOCIA": "SCOTLAND", "PAIS DE GALES": "WALES", "IRLANDA": "IRELAND", "GRECIA": "GREECE",
    "TURQUIA": "TURKIYE", "RUSSIA": "RUSSIA", "UCRANIA": "UKRAINE", "AUSTRIA": "AUSTRIA", "HUNGRIA": "HUNGARY",
    "REPUBLICA TCHECA": "CZECHIA", "TCHEQUIA": "CZECHIA", "SERVIA": "SERBIA", "ROMENIA": "ROMANIA", "ESLOVAQUIA": "SLOVAKIA",
    "ESLOVENIA": "SLOVENIA", "ALBANIA": "ALBANIA", "ISLANDIA": "ICELAND", "FINLANDIA": "FINLAND", "BRASIL": "BRAZIL",
    "ARGENTINA": "ARGENTINA", "URUGUAI": "URUGUAY", "PARAGUAI": "PARAGUAY", "CHILE": "CHILE", "PERU": "PERU",
    "COLOMBIA": "COLOMBIA", "EQUADOR": "ECUADOR", "BOLIVIA": "BOLIVIA", "VENEZUELA": "VENEZUELA", "MEXICO": "MEXICO",
    "CANADA": "CANADA", "COSTA RICA": "COSTA RICA", "PANAMA": "PANAMA", "HONDURAS": "HONDURAS", "JAMAICA": "JAMAICA",
    "JAPAO": "JAPAN", "COREIA DO SUL": "SOUTH KOREA", "COREIA": "SOUTH KOREA", "AUSTRALIA": "AUSTRALIA", "IRA": "IRAN",
    "ARABIA SAUDITA": "SAUDI ARABIA", "CATAR": "QATAR", "MARROCOS": "MOROCCO", "SENEGAL": "SENEGAL", "TUNISIA": "TUNISIA",
    "EGITO": "EGYPT", "NIGERIA": "NIGERIA", "GANA": "GHANA", "CAMAROES": "CAMEROON", "ARGELIA": "ALGERIA",
    "COSTA DO MARFIM": "IVORY COAST", "AFRICA DO SUL": "SOUTH AFRICA", "NOVA ZELANDIA": "NEW ZEALAND", "PORTUGAL": "PORTUGAL",
    "LDU": "LDU QUITO", "GUADALUPE": "GUADELOUPE"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    s = s.replace("/", " ").replace("-", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = TROCAS.get(s, s)
    s = PAISES.get(s, s)
    s = re.sub(r"\b(FC|EC|SC|AC|CF|CLUB|FUTEBOL|ESPORTE|SAF)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parecido(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    sa = re.sub(r"\s[A-Z]{2}$", "", a)  # tira UF solta no fim
    if sa == b or (len(sa) >= 4 and (sa in b or b in sa)):
        return 0.92
    return difflib.SequenceMatcher(None, sa, b).ratio()


def anexar(arq, campos, linhas):
    """Acrescenta linhas a um CSV. Se o arquivo antigo tiver outras colunas, reescreve com o cabecalho
    novo (colunas que faltam ficam vazias), para nenhuma linha ficar desalinhada."""
    antigas = []
    if os.path.exists(arq):
        with open(arq, encoding="utf-8") as f:
            r = csv.DictReader(f)
            if r.fieldnames != campos:
                antigas = list(r)
                modo = "w"
            else:
                modo = "a"
    else:
        modo = "w"
    with open(arq, modo, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        if modo == "w":
            w.writeheader()
            w.writerows(antigas)
        w.writerows(linhas)


def pegar(url, nome_cache):
    os.makedirs(CACHE, exist_ok=True)
    arq = os.path.join(CACHE, nome_cache)
    if os.path.exists(arq):
        with open(arq, encoding="utf-8") as f:
            return json.load(f)
    for tent in range(4):
        try:
            r = requests.get(url, headers=HEAD, timeout=30)
            time.sleep(PAUSA)
            if r.status_code == 200:
                d = r.json()
                with open(arq, "w", encoding="utf-8") as f:
                    json.dump(d, f)
                return d
            if r.status_code in (403, 404):
                return None
            if r.status_code == 429:  # limite de pedidos: espera e tenta de novo
                time.sleep(int(r.headers.get("Retry-After", "30") or 30))
        except Exception:
            time.sleep(3 * (tent + 1))
    return None


def partidas_do_dia(data):
    d = pegar(f"{FOT}/matches?date={data:%Y%m%d}", f"dia_{data:%Y%m%d}.json") or {}
    out = []
    for lg in d.get("leagues", []):
        for m in lg.get("matches", []):
            out.append((m, lg))
    return out


def achar(mandante, visitante, data):
    melhor = (0.0, None, None)
    for delta in (0, 1, -1):
        for m, lg in partidas_do_dia(data + dt.timedelta(days=delta)):
            s = min(parecido(mandante, m["home"]["name"]), parecido(visitante, m["away"]["name"]))
            if s > melhor[0]:
                melhor = (s, m, lg)
    return melhor


def resultado_fot(m):
    try:
        a, b = int(m["home"]["score"]), int(m["away"]["score"])
    except Exception:
        return ""
    return "1" if a > b else ("2" if b > a else "X")


def desfalques(team):
    un = team.get("unavailable") or []
    les = sum((u.get("unavailability") or {}).get("type") == "injury" for u in un)
    sus = sum((u.get("unavailability") or {}).get("type") in ("suspension", "red_card", "yellow_card") for u in un)
    valor = sum(u.get("marketValue") or 0 for u in un)
    return len(un), round(valor / 1e6, 2), les, sus


def descanso(forma, inicio):
    """forma: lista dos ultimos jogos (FotMob teamForm) -> dias desde o ultimo, jogos em 14 dias, pontos."""
    datas, pts = [], 0
    for g in forma or []:
        try:
            t = dt.datetime.fromisoformat(g["date"]["utcTime"].replace("Z", "+00:00"))
        except Exception:
            continue
        if t < inicio:
            datas.append(t)
            pts += {1: 3, 0: 1, -1: 0}.get(g.get("result"), 0)
    if not datas:
        return "", "", ""
    dias = (inicio - max(datas)).total_seconds() / 86400
    j14 = sum((inicio - t).days < 14 for t in datas)
    return round(dias, 1), j14, pts


def clima_nasa(lat, lon):
    """Chuva diaria (mm) e temperatura media de todo o periodo num pedido so (NASA POWER, sem chave)."""
    fim = (dt.date.today() - dt.timedelta(days=3)).strftime("%Y%m%d")
    url = (f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR,T2M&community=AG"
           f"&longitude={lon:.2f}&latitude={lat:.2f}&start=20180101&end={fim}&format=JSON")
    d = pegar(url, f"nasa_{lat:.2f}_{lon:.2f}_{fim[:6]}.json")
    try:
        return d["properties"]["parameter"]
    except Exception:
        return None


def clima(lat, lon, inicio, historico):
    """Chuva do dia do jogo (mm, total do dia) e temperatura media no estadio.
    Historico: NASA POWER (um pedido por estadio). Concurso aberto: previsao diaria da Open-Meteo."""
    if os.environ.get("CLIMA", "1") == "0" or lat in ("", None) or lon in ("", None):
        return "", ""
    dia = inicio.strftime("%Y-%m-%d")
    if historico:
        par = clima_nasa(float(lat), float(lon))
        try:
            k = inicio.strftime("%Y%m%d")
            chuva, temp = par["PRECTOTCORR"][k], par["T2M"][k]
            return ("" if chuva < -900 else round(chuva, 1)), ("" if temp < -900 else round(temp, 1))
        except Exception:
            return "", ""
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={float(lat):.3f}&longitude={float(lon):.3f}"
           f"&start_date={dia}&end_date={dia}&daily=precipitation_sum,temperature_2m_mean&timezone=GMT")
    d = pegar(url, f"prev_{float(lat):.2f}_{float(lon):.2f}_{dia}_{dt.date.today():%Y%m%d}.json")
    try:
        return round(d["daily"]["precipitation_sum"][0] or 0, 1), d["daily"]["temperature_2m_mean"][0]
    except Exception:
        return "", ""

def altitude(lat, lon):
    if lat in ("", None) or lon in ("", None):
        return ""
    d = pegar(f"https://api.open-meteo.com/v1/elevation?latitude={lat:.3f}&longitude={lon:.3f}",
              f"elev_{lat:.3f}_{lon:.3f}.json")
    try:
        return round(d["elevation"][0])
    except Exception:
        return ""


def trocas(d, lado, forma):
    """Titulares deste jogo que nao foram titulares no jogo anterior do time (rodizio / time reserva).
    Antes do jogo usa a escalacao provavel da FotMob, quando existe."""
    lu = d["content"].get("lineup") or {}
    t = lu.get(lado) or {}
    atual = {p.get("id") for p in t.get("starters") or [] if p.get("id")}
    if len(atual) < 11:
        return ""
    ant = None
    for g in reversed(forma or []):
        m = re.search(r"#(\d+)", g.get("linkToMatch", ""))
        if m:
            ant = m.group(1)
            break
    if not ant:
        return ""
    pd = pegar(f"{FOT}/matchDetails?matchId={ant}", f"md_{ant}.json")
    if not pd:
        return ""
    for s2 in ("homeTeam", "awayTeam"):
        t2 = (pd["content"].get("lineup") or {}).get(s2) or {}
        if t2.get("id") == t.get("id"):
            prev = {p.get("id") for p in t2.get("starters") or [] if p.get("id")}
            return len(atual - prev) if len(prev) >= 11 else ""
    return ""


def confronto(d, inicio, id_casa):
    """Confrontos diretos ANTES do jogo: quantidade e saldo (vitorias do mandante - do visitante)."""
    n = saldo = 0
    for m in ((d["content"].get("h2h") or {}).get("matches") or []):
        try:
            t = dt.datetime.fromisoformat(m["time"]["utcTime"].replace("Z", "+00:00"))
            if t >= inicio or not m["status"].get("finished"):
                continue
            a, b = (int(x) for x in m["status"]["scoreStr"].replace(" ", "").split("-"))
        except Exception:
            continue
        casa_e_mandante = str(m["home"]["id"]) == str(id_casa)
        gm, gv = (a, b) if casa_e_mandante else (b, a)
        n += 1
        saldo += (gm > gv) - (gv > gm)
        if n >= 8:
            break
    return (n, saldo) if n else ("", "")


def invicto(forma, inicio):
    """Jogos seguidos sem perder (ate 5) antes do jogo."""
    seq = 0
    datas = []
    for g in forma or []:
        try:
            t = dt.datetime.fromisoformat(g["date"]["utcTime"].replace("Z", "+00:00"))
        except Exception:
            continue
        if t < inicio:
            datas.append((t, g.get("result")))
    for _, r in sorted(datas, reverse=True):
        if r == -1:
            break
        seq += 1
    return seq if datas else ""


def fatos(c, j, mandante, visitante, data, resultado=None, historico=True):
    s, m, lg = achar(mandante, visitante, data)
    linha = {k: "" for k in CAMPOS}
    linha.update(concurso=c, jogo=j, mandante=mandante, visitante=visitante, similaridade=round(s, 2),
                 coletado_em_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    if not m or s < 0.6:
        return linha, "nao achado"
    if resultado and resultado_fot(m) and resultado_fot(m) != resultado:
        return linha, "resultado diferente"  # partida errada: nao usa
    mid = m["id"]
    d = pegar(f"{FOT}/matchDetails?matchId={mid}", f"md_{mid}.json")
    if not d:
        return linha, "sem detalhes"
    inicio = dt.datetime.fromisoformat(m["status"]["utcTime"].replace("Z", "+00:00"))
    info = d["content"]["matchFacts"].get("infoBox") or {}
    est = info.get("Stadium") or {}
    lu = d["content"].get("lineup") or {}
    dc = desfalques(lu.get("homeTeam") or {})
    df = desfalques(lu.get("awayTeam") or {})
    tf = d["content"]["matchFacts"].get("teamForm") or [[], []]
    rc = descanso(tf[0] if len(tf) > 0 else [], inicio)
    rf = descanso(tf[1] if len(tf) > 1 else [], inicio)
    chuva, temp = clima(est.get("lat"), est.get("long"), inicio, historico)
    alt = altitude(est.get("lat"), est.get("long"))
    tc = trocas(d, "homeTeam", tf[0] if len(tf) > 0 else [])
    tfo = trocas(d, "awayTeam", tf[1] if len(tf) > 1 else [])
    hn, hs = confronto(d, inicio, m["home"]["id"])
    ic = invicto(tf[0] if len(tf) > 0 else [], inicio)
    ifo = invicto(tf[1] if len(tf) > 1 else [], inicio)
    linha.update(match_id=mid, fot_casa=m["home"]["name"], fot_fora=m["away"]["name"], liga=lg.get("name", ""),
                 liga_id=lg.get("primaryId") or lg.get("id"), rodada=(info.get("Tournament") or {}).get("round", ""),
                 inicio_utc=inicio.strftime("%Y-%m-%dT%H:%MZ"),
                 desf_casa_n=dc[0], desf_casa_valor=dc[1], desf_casa_lesao=dc[2], desf_casa_susp=dc[3],
                 desf_fora_n=df[0], desf_fora_valor=df[1], desf_fora_lesao=df[2], desf_fora_susp=df[3],
                 dias_casa=rc[0], dias_fora=rf[0], jogos14_casa=rc[1], jogos14_fora=rf[1],
                 forma5_casa=rc[2], forma5_fora=rf[2], lat=est.get("lat", ""), lon=est.get("long", ""),
                 chuva_mm=chuva, temp_c=temp, altitude_m=alt, trocas_casa=tc, trocas_fora=tfo,
                 h2h_n=hn, h2h_saldo=hs, invicto5_casa=ic, invicto5_fora=ifo)
    return linha, "ok"


def historico():
    partes, parte = int(os.environ.get("PARTES", "1")), int(os.environ.get("PARTE", "0"))
    arq = os.path.join(DADOS, "sentinela_jogos.csv" if partes == 1 else f"sentinela_jogos_p{parte}.csv")
    feitos = set()
    if os.path.exists(arq):
        with open(arq, encoding="utf-8") as f:
            feitos = {(r["concurso"], r["jogo"]) for r in csv.DictReader(f)}
    jogos = []
    with open(os.path.join(DADOS, "arena_odds.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["data_jogo"] and (r["concurso"], r["jogo"]) not in feitos and int(r["concurso"]) % partes == parte:
                jogos.append(r)
    novo = not os.path.exists(arq)
    cont = {}
    with open(arq, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        for i, r in enumerate(jogos, 1):
            data = dt.datetime.strptime(r["data_jogo"], "%d/%m/%Y").date()
            linha, st = fatos(r["concurso"], r["jogo"], r["mandante"], r["visitante"], data, r["resultado"] or None)
            cont[st] = cont.get(st, 0) + 1
            w.writerow(linha)
            f.flush()  # linha inteira gravada: se o tempo acabar, nada fica pela metade
            if i % 100 == 0:
                print(f"{i}/{len(jogos)} {cont}", flush=True)
    print("Fim:", cont)


def completar_clima():
    """Preenche chuva/temperatura (do dia) das linhas do historico que ainda nao tem. NASA POWER: 1 pedido por estadio."""
    arq = os.path.join(DADOS, "sentinela_jogos.csv")
    with open(arq, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    feitos = 0
    prazo = time.time() + float(os.environ.get("CLIMA_PRAZO", "1e9"))
    for l in linhas:
        if time.time() > prazo:
            break
        if l["match_id"] and l["lat"] and l["inicio_utc"] and (l["chuva_mm"] == "" or os.environ.get("REFAZER_CLIMA")):
            inicio = dt.datetime.strptime(l["inicio_utc"], "%Y-%m-%dT%H:%MZ")
            l["chuva_mm"], l["temp_c"] = clima(float(l["lat"]), float(l["lon"]), inicio, True)
            feitos += 1
            if feitos >= int(os.environ.get("MAX_CLIMA", "4500")):
                break
    with open(arq, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(linhas)
    print(f"Clima preenchido em {feitos} jogos.")


def aberto():
    """Grade do concurso aberto (arquivo do motor) -> fatos de hoje. Acrescenta, nunca sobrescreve."""
    sys.path.insert(0, os.path.join(REPO, "motor"))
    import camada1
    c = max(camada1.arena().keys())
    if camada1.concurso_encerrado(c):
        print(f"Concurso {c} encerrado.")
        return
    reg = camada1.arena(c)
    grade, _ = camada1.grade_caixa(c)
    if not grade:
        grade, _, _ = camada1.grade_guia(c)
    if not grade:
        grade, _ = camada1.grade_arena(reg)
    datas = {j["jogo"]: j.get("data") for j in reg.get("jogos", [])}
    hoje = dt.date.today()
    arq = os.path.join(DADOS, "sentinela_aberto.csv")
    ok = 0
    linhas = []
    for j in sorted(grade):
        mand, vis = grade[j]
        linha, st = None, "nao achado"
        # jogo da Loteca: entre hoje e os proximos 6 dias
        for k in range(0, 7):
            linha, st = fatos(c, j, mand, vis, hoje + dt.timedelta(days=k), None, historico=False)
            if st == "ok":
                break
        ok += st == "ok"
        linhas.append(linha)
    anexar(arq, CAMPOS, linhas)
    print(f"Concurso {c}: fatos de {ok}/14 jogos -> {arq}")


if __name__ == "__main__":
    {"historico": historico, "aberto": aberto, "clima": completar_clima}[sys.argv[1] if len(sys.argv) > 1 else "aberto"]()
