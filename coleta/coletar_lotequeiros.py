"""
Coletor de palpites do blog Lotequeiros (lotequeirosbr.blogspot.com).

Etapa 1 - baixar:  python coletar_lotequeiros.py baixar
    Le o feed publico do Blogger em paginas de 150 posts e grava cada post
    em lotequeiros_bruto.jsonl (uma linha por post). Pode ser interrompido e
    rodado de novo: posts ja gravados sao pulados.

Etapa 2 - extrair: python coletar_lotequeiros.py extrair
    Le o bruto e gera lotequeiros_palpites.csv com:
    concurso, jogo, mandante, visitante, seco, duplo, metodo, publicado, url

Etapa 3 - semanal: python coletar_lotequeiros.py semanal
    Baixa so os posts mais recentes (ultimas 2 paginas, ~300 posts) e junta
    os palpites novos ao CSV que ja existe. Nao precisa do arquivo bruto
    completo (24 MB, que fica fora do repositorio).
"""
import csv
import html
import json
import os
import re
import sys
import time
import urllib.request

BLOG = "https://lotequeirosbr.blogspot.com"
FEED = BLOG + "/feeds/posts/default?alt=json&start-index={ini}&max-results={n}"
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
BRUTO = os.path.join(PASTA, "lotequeiros_bruto.jsonl")  # fora do git (.gitignore)
SAIDA = os.path.join(PASTA, "lotequeiros_palpites.csv")
POR_PAGINA = 150
PAUSA = 1.5  # segundos entre pedidos, para nao sobrecarregar o site
UA = {"User-Agent": "Mozilla/5.0 (LotecaElitePro; coleta semanal)"}


# ----------------------------------------------------------------- baixar
def _pedir(url, tentativas=4):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # rede instavel: espera e tenta de novo
            print(f"  erro ({e}); tentando de novo em {5 * (i + 1)}s")
            time.sleep(5 * (i + 1))
    raise RuntimeError("falhou: " + url)


def _ids_gravados():
    ids = set()
    if os.path.exists(BRUTO):
        with open(BRUTO, encoding="utf-8") as f:
            for linha in f:
                ids.add(json.loads(linha)["id"])
    return ids


def baixar(max_paginas=None):
    ja = _ids_gravados()
    primeira = _pedir(FEED.format(ini=1, n=1))
    total = int(primeira["feed"]["openSearch$totalResults"]["$t"])
    print(f"Posts no blog: {total} | ja gravados: {len(ja)}")
    novos = 0
    ini, pagina = 1, 0
    with open(BRUTO, "a", encoding="utf-8") as out:
        while ini <= total:
            pagina += 1
            if max_paginas and pagina > max_paginas:
                break
            dados = _pedir(FEED.format(ini=ini, n=POR_PAGINA))
            entradas = dados["feed"].get("entry", [])
            if not entradas:
                break
            for e in entradas:
                pid = e["id"]["$t"]
                if pid in ja:
                    continue
                link = next((l["href"] for l in e.get("link", [])
                             if l.get("rel") == "alternate"), "")
                out.write(json.dumps({
                    "id": pid,
                    "titulo": e["title"]["$t"],
                    "publicado": e["published"]["$t"],
                    "url": link,
                    "conteudo": e.get("content", {}).get("$t", ""),
                }, ensure_ascii=False) + "\n")
                ja.add(pid)
                novos += 1
            print(f"  pagina {pagina}: posts {ini}-{ini + len(entradas) - 1} (novos ate agora: {novos})")
            ini += len(entradas)
            time.sleep(PAUSA)
    print(f"Concluido. Novos posts gravados: {novos}")


# ---------------------------------------------------------------- extrair
RE_TITULO = re.compile(
    r"LOTEC\w*\s*(?:ESPECIAL\s*)?(\d{3,4})\s*[-:–]?\s*JOGO\s*(\d{1,2})\s*[-:–]?\s*(.+)",
    re.I)
COL = r"(1|X|2|DO MEIO|MEIO|EMPATE)"


def _texto(conteudo):
    t = re.sub(r"<br\s*/?>|</p>|</div>", "\n", conteudo, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"[ \t ]+", " ", t)


def _norm_col(c):
    c = c.upper().strip()
    return "X" if c in ("DO MEIO", "MEIO", "EMPATE", "X") else c


def _norm_duplo(s):
    s = s.upper()
    s = re.sub(r"DO MEIO|MEIO|EMPATE", "X", s)
    cols = sorted(set(re.findall(r"[12X]", s)), key="1X2".index)
    return "".join(cols) if len(cols) == 2 else ""


def extrair_palpite(texto):
    """Devolve (seco, duplo, metodo). metodo: padrao | livre | nenhum."""
    t = texto.upper()
    # 1) Formato padronizado (2024 em diante)
    m = re.search(r"PALPITE\s*:\s*COLUNA\s*" + COL, t)
    d = re.search(r"PALPITE\s+DUPLO\s*:\s*COLUNAS?\s*([12X][\s\-E/]*[12X])", t)
    if m:
        return _norm_col(m.group(1)), (_norm_duplo(d.group(1)) if d else ""), "padrao"
    # 2) Texto livre (2017-2024)
    seco = ""
    for pad in (
        r"PALPITE\s+SECO\s+(?:\S+\s+){0,4}?COLUNA\s*" + COL,
        r"SECO\s+(?:NA\s+|DE\s+|EM\s+)?COLUNA\s*" + COL,
        r"COLUNA\s*" + COL + r"\s+SECO",
        r"SECO\s*:?\s*COLUNA\s*" + COL,
        r"MEU\s+PALPITE\s+(?:\S+\s+){0,4}?COLUNA\s*" + COL,
    ):
        m = re.search(pad, t)
        if m:
            seco = _norm_col(m.group(1))
            break
    duplo = ""
    for pad in (
        r"DUPLO\s+(?:\S+\s+){0,3}?COLUNAS?\s*([12X](?:\s*(?:E|-|/|,|&)?\s*)(?:[12X]|DO MEIO|MEIO))",
        r"DUPLO\s*:?\s*([12X]\s*[-/]?\s*[12X])\b",
        r"DUPLO\s+(?:\S+\s+){0,6}?['\"‘“]?\s*([12X]\s*[-/]\s*[12X])",
    ):
        m = re.search(pad, t)
        if m:
            duplo = _norm_duplo(m.group(1))
            if duplo:
                break
    if duplo and not seco:
        # ex.: "Aposto no Atletico seco ja que e o favorito COLUNA 1. Nosso duplo..."
        antes = t[:t.find("DUPLO")]
        m = re.findall(r"COLUNA\s*(DO\s+MEIO|MEIO|[12X])\b", antes)
        if m:
            seco = _norm_col(m[-1])
    if seco or duplo:
        return seco, duplo, "livre"
    # 3) Posts antigos (2017-2020): o palpite e a ultima "COLUNA x" do texto,
    #    ou um triplo declarado ("1-X-2"). Leitura de menor confianca.
    sem_enquete = re.sub(r"ENQU\w*\.?\s*PARCIAL[^\n]*", " ", t)
    if re.search(r"\bTRIPLO\b", sem_enquete) and re.search(r"1\s*-\s*X\s*-\s*2", sem_enquete):
        return "", "", "triplo"
    ultimas = re.findall(r"COLUNA\s*(?:DO\s+MEIO|MEIO|[12X])\b", sem_enquete)
    if ultimas:
        c = re.sub(r"COLUNA\s*", "", ultimas[-1])
        return _norm_col(c), "", "ultima_coluna"
    return "", "", "nenhum"


def extrair(juntar=False):
    """juntar=True: parte do CSV existente e so acrescenta/atualiza jogos."""
    linhas, vistos = [], {}
    if juntar and os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r["concurso"], r["jogo"] = int(r["concurso"]), int(r["jogo"])
                vistos[(r["concurso"], r["jogo"])] = r
    antes = len(vistos)
    with open(BRUTO, encoding="utf-8") as f:
        for linha in f:
            p = json.loads(linha)
            tit = html.unescape(p["titulo"]).strip()
            m = RE_TITULO.search(tit)
            if not m:
                continue  # posts que nao sao de jogo (placar ao vivo, youtube...)
            concurso, jogo = int(m.group(1)), int(m.group(2))
            if not 1 <= jogo <= 14:
                continue
            confronto = re.sub(r"\([^)]*\)", " ", m.group(3))
            partes = re.split(r"\s+X\s+", confronto.upper(), maxsplit=1)
            mand = partes[0].strip(" -") if partes else ""
            vis = partes[1].strip(" -") if len(partes) > 1 else ""
            seco, duplo, metodo = extrair_palpite(_texto(p["conteudo"]))
            chave = (concurso, jogo)
            reg = dict(concurso=concurso, jogo=jogo, mandante=mand, visitante=vis,
                       seco=seco, duplo=duplo, metodo=metodo,
                       publicado=p["publicado"][:19], url=p["url"])
            # se houver post repetido para o mesmo jogo, fica o mais antigo
            # (publicado antes do jogo) que tenha palpite
            ant = vistos.get(chave)
            if ant is None or (not ant["seco"] and seco) or (
                    bool(ant["seco"]) == bool(seco) and reg["publicado"] < ant["publicado"]):
                vistos[chave] = reg
    linhas = sorted(vistos.values(), key=lambda r: (r["concurso"], r["jogo"]))
    campos = ["concurso", "jogo", "mandante", "visitante", "seco", "duplo",
              "metodo", "publicado", "url"]
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    com_seco = sum(1 for r in linhas if r["seco"])
    print(f"Jogos encontrados: {len(linhas)} (novos: {len(linhas) - antes}) | "
          f"com palpite seco: {com_seco} | concursos: {len({r['concurso'] for r in linhas})}")
    print(f"Arquivo: {SAIDA}")


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "baixar"
    os.makedirs(PASTA, exist_ok=True)
    if acao == "baixar":
        baixar()
    elif acao == "extrair":
        extrair()
    elif acao == "semanal":
        if os.path.exists(BRUTO):
            os.remove(BRUTO)  # bruto temporario: so os posts recentes
        baixar(max_paginas=2)
        extrair(juntar=True)
    else:
        print(__doc__)
