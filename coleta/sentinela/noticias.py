"""
Noticias dos times da grade (setoristas e imprensa), coletadas automaticamente
antes de cada previsao.

Fontes: feed do ge.globo de cada time brasileiro (cobertura dos setoristas), Google Noticias
(todos os times, e filtrado pelos sites que bloqueiam acesso direto: Lance!, Terra, CNN Brasil,
Itatiaia, O Tempo, L'Equipe, The Guardian, Goal) e os feeds de jornais e sites esportivos:
UOL Esporte, ESPN Brasil, Gazeta Esportiva, Trivela, Placar, BBC Sport, Sky Sports, Marca, AS,
Mundo Deportivo, Gazzetta dello Sport, Football Italia, Kicker, Ole e Record. Guarda as manchetes dos
ultimos 6 dias e marca sinais por palavras-chave:
  reservas  - poupar, time alternativo/misto/reserva, rodizio, foco em outra competicao
  desfalque - lesao, suspenso, vetado, desfalque, fora do jogo, duvida
  crise     - salarios atrasados, crise, protesto, dividas
  tecnico   - tecnico demitido, interino, novo tecnico, cargo ameacado
  reforco   - volta, retorno, liberado, recuperado, reforco

Se existir a variavel ANTHROPIC_API_KEY, um modelo le as manchetes de cada jogo e extrai os FATOS
(ja campeao/rebaixado/classificado, desfalques, poupar titulares, foco em outra competicao, tecnico,
crise), cada um com a fonte, e da uma nota de -2 a +2 para o mandante. Sem a chave, so palavras-chave.

Saida: coleta/dados/noticias_aberto.csv (acrescenta; nunca sobrescreve).
Sem historico antigo nas fontes: cada semana coletada vira historico, e o
portao do motor so usa estes sinais quando houver semanas suficientes.
Uso: python coleta/sentinela/noticias.py
"""
import datetime as dt
import email.utils
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
DADOS = os.path.join(REPO, "coleta", "dados")
HEAD = {"User-Agent": "Mozilla/5.0 (pesquisa pessoal; coleta leve)"}
DIAS = 6
FEEDS = {
    "UOL Esporte": "https://rss.uol.com.br/feed/esporte.xml",
    "ESPN Brasil": "https://www.espn.com.br/espn/rss/news",
    "Gazeta Esportiva": "https://www.gazetaesportiva.com/feed/",
    "Trivela": "https://trivela.com.br/feed/",
    "Placar": "https://placar.com.br/feed/",
    "BBC Sport": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "Sky Sports": "https://www.skysports.com/rss/12040",
    "Marca": "https://e00-marca.uecdn.es/rss/futbol/primera-division.xml",
    "AS": "https://as.com/rss/futbol/primera.xml",
    "Mundo Deportivo": "https://www.mundodeportivo.com/rss/futbol",
    "Gazzetta": "https://www.gazzetta.it/rss/calcio.xml",
    "Football Italia": "https://football-italia.net/feed/",
    "Kicker": "https://newsfeed.kicker.de/news/fussball",
    "Ole": "https://www.ole.com.ar/rss/ultimas-noticias/",
    "Record": "https://www.record.pt/rss",
}
SITES_BR = "site:lance.com.br OR site:terra.com.br OR site:cnnbrasil.com.br OR site:itatiaia.com.br OR site:otempo.com.br"
SITES_FORA = "site:lequipe.fr OR site:theguardian.com OR site:goal.com OR site:espn.com"
GENERICAS = {"real", "atletico", "athletico", "sport", "dep", "deportivo", "inter", "club", "clube", "esporte", "fc",
             "sporting", "united", "city", "america", "nacional", "santa", "sao", "racing", "manc", "athletic"}
EXPANDE = {"MANC.": "MANCHESTER", "REALSOCIEDAD": "REAL SOCIEDAD", "DEP.": "", "~~": "",
           "ATL.": "ATLETICO", "B.": "", "BORUSSIA M.": "BORUSSIA MONCHENGLADBACH"}
_FEEDS_CACHE = None

SINAIS = {
    "reservas": r"poupa|poupad|time alternativo|time misto|equipe alternativa|reservas|rodizio|preservar|foco na (libertadores|copa|final|sul-americana)|priorizar",
    "desfalque": r"lesao|lesionad|suspens|vetad|desfalque|fora do jogo|fora da partida|duvida|cirurgia|entorse|contusao|dores",
    "crise": r"salarios? atrasad|atraso salarial|crise|protesto|pressao da torcida|organizada|dividas?|penhora|transfer ban",
    "tecnico": r"demitid|demissao|deixa o cargo|treinador interino|tecnico interino|novo tecnico|novo treinador|balanca no cargo|cargo ameacado|ultimato|anuncia tecnico|fica no cargo",
    "reforco": r"volta ao time|retorno|retorna|liberad|recuperad|reforco|estreia|de volta",
}

# slug do time no ge.globo (so os de nome diferente do padrao)
GE_SLUG = {"ATLETICO MG": "atletico-mg", "ATHLETICO PR": "athletico-pr", "ATLETICO GO": "atletico-go",
           "AMERICA MG": "america-mg", "SAO PAULO": "sao-paulo", "VASCO DA GAMA": "vasco", "BOTAFOGO RJ": "botafogo",
           "BRAGANTINO": "bragantino", "SPORT": "sport", "CEARA": "ceara", "GREMIO": "gremio", "VITORIA": "vitoria",
           "GOIAS": "goias", "CRICIUMA": "criciuma", "CUIABA": "cuiaba", "AVAI": "avai", "PONTE PRETA": "ponte-preta",
           "NAUTICO": "nautico", "PAYSANDU": "paysandu", "CHAPECOENSE": "chapecoense", "FIGUEIRENSE": "figueirense"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    s = re.sub(r"[/\-.]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sem_acento(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def limpa(nome):
    """tira sobras do OCR da grade (~~, _, espacos) e corrige UF lida errado."""
    n = re.sub(r"[~_]+", " ", nome or "").strip()
    n = re.sub(r"\s+", " ", n)
    return re.sub(r"-RI$", "-RJ", n)


def brasileiro(nome):
    return bool(re.search(r"[/-][A-Z]{2}$", limpa(nome)))


def nome_busca(nome):
    n = re.sub(r"[/-][A-Z]{2,3}$", "", limpa(nome))
    for a, b in EXPANDE.items():
        n = n.replace(a, b)
    return re.sub(r"\s+", " ", n).strip().title()


def chaves(base):
    """termos que identificam o time numa manchete: o nome inteiro e a palavra mais distintiva."""
    b = sem_acento(base)
    ks = {b}
    pal = [w for w in re.findall(r"[a-z]+", b) if w not in GENERICAS and len(w) >= 4]
    if pal:
        ks.add(max(pal, key=len))
    return ks


def feeds_gerais():
    global _FEEDS_CACHE
    if _FEEDS_CACHE is None:
        _FEEDS_CACHE = []
        for nome, url in FEEDS.items():
            _FEEDS_CACHE += [(t, q, l, nome) for t, q, l in ler_rss(url)]
    return _FEEDS_CACHE


def ler_rss(url):
    for t in range(3):
        try:
            r = requests.get(url, headers=HEAD, timeout=30)
            time.sleep(0.8)
            if r.status_code != 200:
                return []
            raiz = ET.fromstring(r.content)
            itens = []
            for it in raiz.iter("item"):
                tit = (it.findtext("title") or "").strip()
                data = it.findtext("pubDate")
                try:
                    quando = email.utils.parsedate_to_datetime(data)
                    if quando.tzinfo is None:
                        quando = quando.replace(tzinfo=dt.timezone.utc)
                except Exception:
                    quando = None
                itens.append((tit, quando, (it.findtext("link") or "").strip()))
            return itens
        except Exception:
            time.sleep(3 * (t + 1))
    return []


def noticias_do_time(nome):
    base = nome_busca(nome).replace(" Bergamas", "").replace(" Bergamo", "")
    itens = []
    br = brasileiro(nome)
    if br:
        n = norm(re.sub(r"[/-][A-Z]{2}$", "", limpa(nome)))
        uf = limpa(nome)[-2:].lower()
        slug = GE_SLUG.get(f"{n} {uf.upper()}", GE_SLUG.get(n, sem_acento(base).replace(" ", "-")))
        itens += [(t, q, l, "ge") for t, q, l in ler_rss(f"https://ge.globo.com/rss/ge/futebol/times/{slug}/")]
    for consulta, fonte in ((f'"{base}" futebol', "google"), (f'"{base}" ({SITES_BR if br else SITES_FORA})', "google sites")):
        q = urllib.parse.quote(consulta)
        itens += [(t, q2, l, fonte) for t, q2, l in
                  ler_rss(f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419")]
    if not br:  # times de fora: tambem a imprensa local (ingles e espanhol)
        for hl, gl, ceid in (("en-GB", "GB", "GB:en"), ("es", "ES", "ES:es")):
            q = urllib.parse.quote(f'"{base}"')
            itens += [(t, q2, l, "google " + gl) for t, q2, l in
                      ler_rss(f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}")]
    itens += feeds_gerais()
    limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DIAS)
    vistos, out = set(), []
    ks = chaves(base)
    for t, q2, l, fonte in itens:
        if q2 and q2 < limite:
            continue
        if fonte != "ge" and not any(k in sem_acento(t) for k in ks):
            continue  # manchete que nao fala do time
        k = sem_acento(t)[:80]
        if k in vistos:
            continue
        vistos.add(k)
        out.append({"titulo": t, "quando": q2.strftime("%Y-%m-%dT%H:%MZ") if q2 else "", "fonte": fonte, "link": l})
    out.sort(key=lambda m: m["quando"], reverse=True)
    return out


def sinais(manchetes):
    cont = {k: 0 for k in SINAIS}
    for m in manchetes:
        t = sem_acento(m["titulo"])
        for k, rx in SINAIS.items():
            if re.search(rx, t):
                cont[k] += 1
    return cont


def nota_modelo(mand, vis, mc, mv):
    """IA le as manchetes e devolve (nota, motivo, fatos). fatos = [{"time","fato","fonte"}]."""
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave or not (mc or mv):
        return "", "", []
    lista = lambda ms: "\n".join(f"- [{m['fonte']}, {m['quando'][:10]}] {m['titulo']}" for m in ms[:40])  # noqa: E731
    texto = (f"Jogo da Loteca: {mand} (mandante) x {vis} (visitante).\nManchetes recentes do mandante:\n{lista(mc)}\n"
             f"Manchetes recentes do visitante:\n{lista(mv)}\n\n"
             "Use SO o que estas manchetes dizem. Extraia os fatos que mudam o jogo: ja campeao, ja rebaixado, ja "
             "classificado ou eliminado, desfalques importantes (quem), poupar titulares, foco em outra competicao/final, "
             "tecnico demitido/novo/interino, crise (salarios, protestos). Nao invente; se a manchete for vaga, ignore. "
             "Responda so em JSON: {\"fatos\": [{\"time\": \"mandante|visitante\", \"fato\": \"...\", "
             "\"fonte\": \"nome da fonte\"}], \"nota\": n, \"motivo\": \"...\"} com n inteiro de -2 (muito pior "
             "para o mandante) a +2 (muito melhor para o mandante) em relacao ao esperado sem essas noticias; 0 se nada relevante.")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=90,
                          headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": os.environ.get("MODELO_NOTICIAS", "claude-haiku-5-5"), "max_tokens": 700,
                                "messages": [{"role": "user", "content": texto}]})
        txt = r.json()["content"][0]["text"]
        d = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        fatos = [f for f in d.get("fatos", []) if isinstance(f, dict) and f.get("fato")][:12]
        return int(d.get("nota", 0)), str(d.get("motivo", ""))[:300], fatos
    except Exception:
        return "", "", []


def main():
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
    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    campos = ["concurso", "jogo", "mandante", "visitante"] + \
             [f"{lado}_{k}" for lado in ("casa", "fora") for k in list(SINAIS) + ["n"]] + \
             ["nota_modelo", "motivo_modelo", "fatos_ia", "fontes", "manchetes_casa", "manchetes_fora", "coletado_em_utc"]
    arq = os.path.join(DADOS, "noticias_aberto.csv")
    sys.path.insert(0, AQUI)
    from coletar_sentinela import anexar
    linhas = []
    for j in sorted(grade):
        mand, vis = grade[j]
        mc, mv = noticias_do_time(mand), noticias_do_time(vis)
        sc, sv = sinais(mc), sinais(mv)
        nota, motivo, fatos = nota_modelo(mand, vis, mc, mv)
        fontes = sorted({m["fonte"] for m in mc + mv})
        linha = {"concurso": c, "jogo": j, "mandante": mand, "visitante": vis, "nota_modelo": nota,
                 "motivo_modelo": motivo, "coletado_em_utc": agora,
                 "fatos_ia": json.dumps(fatos, ensure_ascii=False), "fontes": "; ".join(fontes),
                 "manchetes_casa": json.dumps(mc[:25], ensure_ascii=False),
                 "manchetes_fora": json.dumps(mv[:25], ensure_ascii=False)}
        for lado, s_, m in (("casa", sc, mc), ("fora", sv, mv)):
            for k, v in s_.items():
                linha[f"{lado}_{k}"] = v
            linha[f"{lado}_n"] = len(m)
        linhas.append(linha)
        print(f"Jogo {j}: {mand} ({len(mc)} manchetes, {sc}) x {vis} ({len(mv)}, {sv}) | fontes: {', '.join(fontes)}"
              + (f" | nota {nota}: {motivo}" if nota != "" else ""))
    anexar(arq, campos, linhas)

if __name__ == "__main__":
    main()
