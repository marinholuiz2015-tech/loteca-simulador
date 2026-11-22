"""
Noticias dos times da grade (setoristas e imprensa), coletadas automaticamente
antes de cada previsao.

Fontes: feed do ge.globo de cada time brasileiro (cobertura dos setoristas) e
Google Noticias (todos os times, inclusive de fora). Guarda as manchetes dos
ultimos 6 dias e marca sinais por palavras-chave:
  reservas  - poupar, time alternativo/misto/reserva, rodizio, foco em outra competicao
  desfalque - lesao, suspenso, vetado, desfalque, fora do jogo, duvida
  crise     - salarios atrasados, crise, protesto, dividas
  tecnico   - tecnico demitido, interino, novo tecnico, cargo ameacado
  reforco   - volta, retorno, liberado, recuperado, reforco

Se existir a variavel ANTHROPIC_API_KEY, um modelo le as manchetes de cada jogo e
da uma nota de -2 a +2 para o mandante (opcional; sem a chave, so palavras-chave).

Saida: coleta/dados/noticias_aberto.csv (acrescenta; nunca sobrescreve).
Sem historico antigo nas fontes: cada semana coletada vira historico, e o
portao do motor so usa estes sinais quando houver semanas suficientes.
Uso: python coleta/sentinela/noticias.py
"""
import csv
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


def brasileiro(nome):
    return bool(re.search(r"/[A-Z]{2}$", (nome or "").strip()))


def nome_busca(nome):
    return re.sub(r"/[A-Z]{2}$", "", nome or "").strip().title()


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
    if brasileiro(nome):
        n = norm(re.sub(r"/[A-Z]{2}$", "", nome))
        uf = nome.strip()[-2:].lower()
        slug = GE_SLUG.get(f"{n} {uf.upper()}", GE_SLUG.get(n, sem_acento(base).replace(" ", "-")))
        itens += [(t, q, l, "ge") for t, q, l in ler_rss(f"https://ge.globo.com/rss/ge/futebol/times/{slug}/")]
    q = urllib.parse.quote(f'"{base}" futebol')
    itens += [(t, q2, l, "google") for t, q2, l in
              ler_rss(f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419")]
    limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DIAS)
    vistos, out = set(), []
    chave_time = sem_acento(base).split()[0]
    for t, q2, l, fonte in itens:
        if q2 and q2 < limite:
            continue
        if fonte == "google" and chave_time not in sem_acento(t):
            continue  # manchete que nao fala do time
        k = sem_acento(t)[:80]
        if k in vistos:
            continue
        vistos.add(k)
        out.append({"titulo": t, "quando": q2.strftime("%Y-%m-%dT%H:%MZ") if q2 else "", "fonte": fonte, "link": l})
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
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave or not (mc or mv):
        return "", ""
    texto = (f"Jogo: {mand} (mandante) x {vis} (visitante).\nManchetes do mandante:\n" +
             "\n".join("- " + m["titulo"] for m in mc[:25]) + "\nManchetes do visitante:\n" +
             "\n".join("- " + m["titulo"] for m in mv[:25]) +
             "\n\nCom base SO nessas manchetes (desfalques, time reserva, crise, foco em outra competicao), "
             "responda em JSON {\"nota\": n, \"motivo\": \"...\"} com n inteiro de -2 (muito pior para o mandante) "
             "a +2 (muito melhor para o mandante) em relacao ao que se esperaria sem essas noticias; 0 se nada relevante.")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=60,
                          headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": os.environ.get("MODELO_NOTICIAS", "claude-haiku-5-5"), "max_tokens": 200,
                                "messages": [{"role": "user", "content": texto}]})
        txt = r.json()["content"][0]["text"]
        d = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        return int(d.get("nota", 0)), str(d.get("motivo", ""))[:300]
    except Exception:
        return "", ""


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
             ["nota_modelo", "motivo_modelo", "manchetes_casa", "manchetes_fora", "coletado_em_utc"]
    arq = os.path.join(DADOS, "noticias_aberto.csv")
    sys.path.insert(0, AQUI)
    from coletar_sentinela import anexar
    linhas = []
    for j in sorted(grade):
        mand, vis = grade[j]
        mc, mv = noticias_do_time(mand), noticias_do_time(vis)
        sc, sv = sinais(mc), sinais(mv)
        nota, motivo = nota_modelo(mand, vis, mc, mv)
        linha = {"concurso": c, "jogo": j, "mandante": mand, "visitante": vis, "nota_modelo": nota,
                 "motivo_modelo": motivo, "coletado_em_utc": agora,
                 "manchetes_casa": json.dumps(mc[:15], ensure_ascii=False),
                 "manchetes_fora": json.dumps(mv[:15], ensure_ascii=False)}
        for lado, s_, m in (("casa", sc, mc), ("fora", sv, mv)):
            for k, v in s_.items():
                linha[f"{lado}_{k}"] = v
            linha[f"{lado}_n"] = len(m)
        linhas.append(linha)
        print(f"Jogo {j}: {mand} ({len(mc)} manchetes, {sc}) x {vis} ({len(mv)}, {sv})"
              + (f" | nota {nota}: {motivo}" if nota != "" else ""))
    anexar(arq, campos, linhas)

if __name__ == "__main__":
    main()
