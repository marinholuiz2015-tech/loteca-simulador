"""
Especialistas de maior expressao: Vovoteca (matriz) e Canal do Puga.

Vovoteca: a "Nossa Matriz" sai em imagem (14 secos, sugestoes de duplo, o jogo que
pede triplo e a zebra da rodada). A IA (Claude, com visao) le a imagem inteira junto
com a grade da Caixa, o que resolve os formatos que o leitor por pixel nao entendia.

Puga: o site palpitesdopuga.com.br traz, por concurso, o palpite principal, o duplo
preferido, as odds que ele consultou e a enquete da comunidade. O proprio site avisa
que a analise e automatica e "parte das cotacoes": por isso guardamos tambem as odds,
para medir se o Puga acrescenta algo alem do favorito do mercado.

Saidas (coleta/dados):
  especialistas_palpites.csv  concurso, fonte, jogo, seco, duplo, triplo, zebra, origem, coletado_em_utc
  puga_odds.csv               concurso, jogo, mandante, visitante, odd_1, odd_x, odd_2, odds_em
  puga_enquete.csv            concurso, jogo, votos_1, votos_x, votos_2, total

Uso:
  python coleta/especialistas.py historico   # tudo que ainda nao esta gravado
  python coleta/especialistas.py semanal     # so os concursos mais recentes
"""
import base64
import csv
import datetime as dt
import json
import os
import re
import sys
import time

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
DADOS = os.path.join(AQUI, "dados")
PALP = os.path.join(DADOS, "especialistas_palpites.csv")
PODDS = os.path.join(DADOS, "puga_odds.csv")
PENQ = os.path.join(DADOS, "puga_enquete.csv")
CAMPOS = ["concurso", "fonte", "jogo", "seco", "duplo", "triplo", "zebra", "origem", "coletado_em_utc"]
HEAD = {"User-Agent": "Mozilla/5.0 (pesquisa pessoal; coleta leve)"}
CAIXA = "https://servicebus3.caixa.gov.br/portaldeloterias/api/loteca/{}"
MEDIA = "https://vovoteca.com/wp-json/wp/v2/media?search=matriz&per_page=100&page={}&_fields=date,source_url"
PUGA = "https://palpitesdopuga.com.br/loteca/{}/palpites"
MODELO = os.environ.get("MODELO_VISAO", os.environ.get("MODELO_NOTICIAS", "claude-haiku-5-5"))



def texto_ia(r):
    """Junta os blocos de texto da resposta da IA (o modelo pode mandar antes um bloco de raciocinio)."""
    d = r.json()
    if r.status_code != 200 or "error" in d:
        raise RuntimeError(f"API {r.status_code}: {str(d.get('error', d))[:300]}")
    t = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    if not t:
        raise RuntimeError(f"resposta sem texto (stop={d.get('stop_reason')}, blocos={[b.get('type') for b in d.get('content', [])]})")
    return t

def agora():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def anexar(arq, campos, linhas):
    if not linhas:
        return
    novo = not os.path.exists(arq)
    with open(arq, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if novo:
            w.writeheader()
        w.writerows(linhas)


def gravados(fonte):
    if not os.path.exists(PALP):
        return set()
    return {int(r["concurso"]) for r in csv.DictReader(open(PALP, encoding="utf-8")) if r["fonte"] == fonte}


_HIST = None


def grade(concurso):
    """{jogo: (mandante, visitante)} pela base historica da Caixa; se faltar, pela API."""
    global _HIST
    if _HIST is None:
        try:
            _HIST = json.load(open(os.path.join(REPO, "data", "historico_cef.json")))["concursos"]
        except Exception:
            _HIST = {}
    c = _HIST.get(str(concurso))
    js = c and c.get("jogos")
    if not js or len(js) != 14:
        try:
            r = requests.get(CAIXA.format(concurso), headers=HEAD, timeout=30)
            js = r.json().get("listaResultadoEquipeEsportiva") or []
        except Exception:
            js = []
    if len(js) != 14:
        return None
    return {j["nuSequencial"]: (j["nomeEquipeUm"], j["nomeEquipeDois"]) for j in js}


# ---------------------------------------------------------------- Vovoteca

def matrizes():
    """{concurso: url} - a imagem 'NNNN-matriz' mais recente de cada concurso (sem a 'MATRIZ PRO')."""
    todas = []
    for p in range(1, 10):
        try:
            r = requests.get(MEDIA.format(p), headers=HEAD, timeout=40)
            if r.status_code != 200:
                break
            L = r.json()
        except Exception:
            break
        if not L:
            break
        todas += L
        if len(L) < 100:
            break
    porc = {}
    for x in todas:
        nome = x["source_url"].rsplit("/", 1)[-1]
        m = re.match(r"(\d{4})-?matriz(?!-?pro)", nome, re.I)
        if not m:
            continue
        c = int(m.group(1))
        if c not in porc or x["date"] > porc[c][0]:
            porc[c] = (x["date"], x["source_url"])
    return {c: u for c, (d, u) in porc.items()}


def ler_matriz(url, g):
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise SystemExit("ANTHROPIC_API_KEY ausente: a leitura da matriz precisa da IA.")
    img = requests.get(url, headers=HEAD, timeout=40)
    tipo = "image/png" if url.lower().endswith(".png") else "image/jpeg"
    jogos = "\n".join(f"{j}. {m} x {v}" for j, (m, v) in sorted(g.items()))
    pedido = (
        "Esta imagem e a 'matriz' de palpites da Vovoteca para a Loteca. Grade oficial do concurso:\n"
        f"{jogos}\n\n"
        "Leia da imagem, sem inventar:\n"
        "- secos: para cada jogo 1 a 14, a coluna marcada (1 = mandante, X = empate, 2 = visitante);\n"
        "- duplos: os jogos com sugestao de duplo e as duas colunas (ex.: 1X, X2, 12). "
        "'aberto' ou '1-2' ou '1~2' = 12; 'mandante e empate' = 1X;\n"
        "- triplo: o numero do jogo sugerido para triplo (se vier so com escudos, use a grade para achar o jogo);\n"
        "- zebra: o time apontado como zebra (pode vir so o escudo) - diga o jogo e o lado (1 ou 2).\n"
        "Se algo nao existir na imagem, use null. Responda so em JSON: "
        "{\"secos\": {\"1\": \"X\", ...}, \"duplos\": {\"4\": \"X2\"}, \"triplo\": 13, "
        "\"zebra\": {\"jogo\": 10, \"lado\": \"2\", \"time\": \"...\"}}")
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=120,
                      headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                      json={"model": MODELO, "max_tokens": 4000, "messages": [{"role": "user", "content": [
                          {"type": "image", "source": {"type": "base64", "media_type": tipo,
                                                       "data": base64.b64encode(img.content).decode()}},
                          {"type": "text", "text": pedido}]}]})
    d = json.loads(re.search(r"\{.*\}", texto_ia(r), re.S).group(0))
    secos = {int(k): str(v).upper().strip() for k, v in (d.get("secos") or {}).items() if str(k).isdigit()}
    if sorted(secos) != list(range(1, 15)) or any(v not in ("1", "X", "2") for v in secos.values()):
        raise ValueError(f"secos incompletos: {secos}")
    duplos = {}
    for k, v in (d.get("duplos") or {}).items():
        v = "".join(sorted(set(str(v).upper()) & {"1", "X", "2"}, key="1X2".index))
        if str(k).isdigit() and len(v) == 2:
            duplos[int(k)] = v
    tri = d.get("triplo")
    tri = int(tri) if str(tri).isdigit() and 1 <= int(tri) <= 14 else None
    z = d.get("zebra") or {}
    zj = int(z["jogo"]) if str(z.get("jogo", "")).isdigit() and 1 <= int(z["jogo"]) <= 14 else None
    zl = str(z.get("lado", "")).strip().upper() if zj else ""
    return secos, duplos, tri, (zj, zl if zl in ("1", "X", "2") else "")


def vovoteca(modo):
    ja = gravados("vovoteca")
    M = matrizes()
    alvo = sorted(c for c in M if c not in ja)
    if modo == "semanal":
        alvo = alvo[-3:]
    print(f"Vovoteca: {len(M)} matrizes publicadas, {len(alvo)} para ler")
    ok = 0
    for c in alvo:
        g = grade(c)
        if not g:
            print(f"  {c}: sem grade da Caixa, fica para depois")
            continue
        try:
            secos, duplos, tri, (zj, zl) = ler_matriz(M[c], g)
        except Exception as e:
            print(f"  {c}: nao consegui ler ({e})")
            continue
        carimbo = agora()
        anexar(PALP, CAMPOS, [{"concurso": c, "fonte": "vovoteca", "jogo": j, "seco": secos[j],
                               "duplo": duplos.get(j, ""), "triplo": int(tri == j),
                               "zebra": zl if zj == j else "", "origem": M[c], "coletado_em_utc": carimbo}
                              for j in range(1, 15)])
        ok += 1
        time.sleep(0.5)
    print(f"Vovoteca: {ok} matrizes gravadas")


# ---------------------------------------------------------------- Puga

def puga_rodada(c, url=PUGA):
    r = requests.get(url.format(c), headers=HEAD, timeout=30)
    if r.status_code != 200:
        return None
    pushes = re.findall(r'\.rsc\.push\((".*?")\)</script>', r.text, re.S)
    full = "".join(json.loads(p) for p in pushes)
    i = full.find('{"round":{')
    while i >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(full, i)
            if obj.get("round", {}).get("number") == c:
                return obj
        except Exception:
            pass
        i = full.find('{"round":{', i + 1)
    return None


def puga(modo):
    ja = gravados("puga")
    ultimo = None
    for n in range(1300, 1279, -1):  # o site comeca no 1280
        if requests.get(PUGA.format(n), headers=HEAD, timeout=30).status_code == 200:
            ultimo = n
            break
    if not ultimo:
        print("Puga: site fora do ar")
        return
    alvo = [c for c in range(1280, ultimo + 1) if c not in ja]
    if modo == "semanal":
        alvo = [c for c in alvo if c >= ultimo - 2]
    print(f"Puga: ultimo concurso {ultimo}, {len(alvo)} para gravar")
    for c in alvo:
        o = puga_rodada(c)
        if not o:
            print(f"  {c}: pagina sem dados")
            continue
        rd = o["round"]
        fecha = dt.datetime.fromisoformat(rd["closesAt"])
        falta = (fecha - dt.datetime.now(dt.timezone.utc)).total_seconds() / 3600
        if falta > 60:
            print(f"  {c}: aberto, fecha em {falta:.0f} h - gravo mais perto do fechamento")
            continue
        # gravado antes do fechamento = palpite limpo; depois = a pagina pode ter sido atualizada
        situacao = "antes_do_fechamento" if falta > 0 else f"depois (pagina atualizada em {rd.get('autoUpdatedAt', '?')[:16]})"
        carimbo = agora()
        palp, odds = [], []
        for m in rd.get("matches", []):
            j = int(m["number"])
            nota = m.get("note") or ""
            s = re.search(r"coluna (1|X|2)\b", nota)  # o primeiro "coluna" e sempre o seco dele
            d = re.search(r"\b(1X|X2|12)\b", nota[s.end():]) if s else None
            if s:
                palp.append({"concurso": c, "fonte": "puga", "jogo": j, "seco": s.group(1),
                             "duplo": d.group(1) if d else "", "triplo": 0, "zebra": "",
                             "origem": f"{PUGA.format(c)} | {situacao}", "coletado_em_utc": carimbo})
            od = m.get("odds") or []
            if len(od) == 3:
                odds.append({"concurso": c, "jogo": j, "mandante": m.get("home"), "visitante": m.get("away"),
                             "odd_1": od[0], "odd_x": od[1], "odd_2": od[2], "odds_em": rd.get("oddsAsOf", "")})
        if len(palp) != 14:
            print(f"  {c}: so {len(palp)} palpites lidos, nao gravei")
            continue
        anexar(PALP, CAMPOS, palp)
        anexar(PODDS, ["concurso", "jogo", "mandante", "visitante", "odd_1", "odd_x", "odd_2", "odds_em"], odds)
        ini = o.get("initial") or {}
        if not ini.get("counts"):
            o2 = puga_rodada(c, "https://palpitesdopuga.com.br/loteca/{}") or {}
            ini = o2.get("initial") or {}
        enq = [{"concurso": c, "jogo": k + 1, "votos_1": v[0], "votos_x": v[1], "votos_2": v[2], "total": ini.get("total")}
               for k, v in enumerate(ini.get("counts") or []) if len(v) == 3]
        anexar(PENQ, ["concurso", "jogo", "votos_1", "votos_x", "votos_2", "total"], enq)
        print(f"  {c}: 14 palpites, {len(odds)} odds, enquete com {ini.get('total')} votos")


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "semanal"
    os.makedirs(DADOS, exist_ok=True)
    try:
        puga(modo)
    except Exception as e:
        print("Puga falhou:", e)
    try:
        vovoteca(modo)
    except SystemExit as e:
        print(e)
    except Exception as e:
        print("Vovoteca falhou:", e)


if __name__ == "__main__":
    main()
