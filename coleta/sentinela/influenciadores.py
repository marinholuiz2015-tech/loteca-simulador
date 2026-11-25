"""
Especialistas e influenciadores — o que cada um disse sobre os jogos da grade.

Fontes em coleta/fontes_influenciadores.json (facil de aumentar): canais de YouTube (titulo e descricao
dos videos), canais publicos do Telegram (texto das mensagens) e feeds de sites.
Guarda tudo dos ultimos 7 dias em coleta/dados/influenciadores_aberto.csv. Com o segredo ANTHROPIC_API_KEY,
a IA le o material e extrai, por jogo da grade, o palpite e o que cada fonte disse
(coleta/dados/influenciadores_palpites.csv), para o placar de assertividade por fonte.
Conteudo pago (grupos e areas de membros) nao e coletado: o palpite pode ser colado no painel.
Uso: python coleta/sentinela/influenciadores.py
"""
import csv
import datetime as dt
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
DADOS = os.path.join(REPO, "coleta", "dados")
CONFIG = os.path.join(REPO, "coleta", "fontes_influenciadores.json")
HEAD = {"User-Agent": "Mozilla/5.0 (pesquisa pessoal; coleta leve)"}
DIAS = 7
CAMPOS_MAT = ["concurso", "fonte", "tipo", "quando", "titulo", "texto", "link", "coletado_em_utc"]
CAMPOS_PAL = ["concurso", "jogo", "mandante", "visitante", "fonte", "palpite", "trecho", "link", "coletado_em_utc"]



def texto_ia(r):
    """Junta os blocos de texto da resposta da IA (o modelo pode mandar antes um bloco de raciocinio)."""
    d = r.json()
    if r.status_code != 200 or "error" in d:
        raise RuntimeError(f"API {r.status_code}: {str(d.get('error', d))[:300]}")
    t = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    if not t:
        raise RuntimeError(f"resposta sem texto (stop={d.get('stop_reason')}, blocos={[b.get('type') for b in d.get('content', [])]})")
    return t

def youtube(cid):
    r = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", headers=HEAD, timeout=30)
    if r.status_code != 200:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/"}
    out = []
    for e in ET.fromstring(r.content).findall("a:entry", ns):
        out.append({"quando": e.findtext("a:published", "", ns), "titulo": e.findtext("a:title", "", ns),
                    "texto": (e.find("m:group", ns).findtext("m:description", "", ns) if e.find("m:group", ns) is not None else ""),
                    "link": (e.find("a:link", ns).get("href") if e.find("a:link", ns) is not None else "")})
    return out


def telegram(canal):
    r = requests.get(f"https://t.me/s/{canal}", headers=HEAD, timeout=30)
    if r.status_code != 200:
        return []
    out = []
    for b in r.text.split("tgme_widget_message_wrap")[1:]:
        m = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)(?:<div class="tgme_widget_message_footer|$)', b, re.S)
        d = re.search(r'<time datetime="([^"]+)"', b)
        p = re.search(r'data-post="([^"]+)"', b)
        txt = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>", "\n", m.group(1)))) if m else ""
        txt = re.sub(r"[ \t]+", " ", txt).strip()
        if txt:
            out.append({"quando": d.group(1) if d else "", "titulo": txt[:120], "texto": txt,
                        "link": f"https://t.me/{p.group(1)}" if p else ""})
    return out


def rss(url):
    r = requests.get(url, headers=HEAD, timeout=30)
    if r.status_code != 200:
        return []
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        desc = html.unescape(re.sub(r"<[^>]+>", " ", it.findtext("description") or ""))
        out.append({"quando": it.findtext("pubDate") or "", "titulo": it.findtext("title") or "", "texto": desc.strip(),
                    "link": it.findtext("link") or ""})
    return out


def quando_dt(s):
    import email.utils
    for f in (lambda x: dt.datetime.fromisoformat(x.replace("Z", "+00:00")), email.utils.parsedate_to_datetime):
        try:
            d = f(s)
            return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
        except Exception:
            pass
    return None


def ia_palpites(grade, material):
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave or not material:
        return []
    jogos = "\n".join(f"{j}. {m} x {v}" for j, (m, v) in sorted(grade.items()))
    mat = "\n\n".join(f"[{x['fonte']} | {x['quando'][:10]} | {x['link']}]\n{x['titulo']}\n{x['texto'][:1500]}" for x in material[:60])
    texto = (f"Grade da Loteca:\n{jogos}\n\nMaterial de especialistas e influenciadores (ultimos dias):\n{mat}\n\n"
             "Para cada jogo da grade em que alguma fonte deu opiniao, diga o palpite dessa fonte (1 = mandante, X = empate, "
             "2 = visitante, ou duplo 1X/X2/12, ou triplo) e um trecho curto que mostre isso. So use o que estiver escrito; "
             "nao invente; se a fonte so falou do time sem palpite, use palpite \"comentario\". Responda so em JSON: "
             "{\"palpites\": [{\"jogo\": n, \"fonte\": \"...\", \"palpite\": \"...\", \"trecho\": \"...\", \"link\": \"...\"}]}")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=120,
                          headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": os.environ.get("MODELO_NOTICIAS", "claude-haiku-5-5"), "max_tokens": 8000,
                                "messages": [{"role": "user", "content": texto}]})
        d = json.loads(re.search(r"\{.*\}", texto_ia(r), re.S).group(0))
        return [p for p in d.get("palpites", []) if isinstance(p, dict) and str(p.get("jogo", "")).isdigit()]
    except Exception as e:
        print("IA dos influenciadores falhou:", e)
        return []


def anexar(arq, campos, linhas):
    novo = not os.path.exists(arq)
    with open(arq, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if novo:
            w.writeheader()
        w.writerows(linhas)


def main():
    sys.path.insert(0, AQUI)
    sys.path.insert(0, os.path.join(REPO, "motor"))
    import camada1
    import noticias as N
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    c = max(camada1.arena().keys())
    grade, _ = camada1.grade_caixa(c)
    if not grade:
        grade, _, _ = camada1.grade_guia(c)
    if not grade:
        grade, _ = camada1.grade_arena(camada1.arena(c))
    agora = dt.datetime.now(dt.timezone.utc)
    carimbo = agora.strftime("%Y-%m-%dT%H:%M:%SZ")
    limite = agora - dt.timedelta(days=DIAS)
    material = []
    for f in cfg["fontes"]:
        try:
            itens = {"youtube": youtube, "telegram": telegram, "rss": rss}[f["tipo"]](f["id"])
        except Exception as e:
            print(f"{f['nome']}: falhou ({e})")
            continue
        novos = [dict(x, fonte=f["nome"], tipo=f["tipo"]) for x in itens if (quando_dt(x["quando"]) or agora) >= limite]
        print(f"{f['nome']} ({f['tipo']}): {len(novos)} itens nos ultimos {DIAS} dias")
        material += novos
    # so o material que fala de algum time da grade (ou da Loteca)
    chaves = set()
    for m, v in grade.values():
        chaves |= N.chaves(N.nome_busca(m)) | N.chaves(N.nome_busca(v))
    rel = [x for x in material if "loteca" in N.sem_acento(x["titulo"] + " " + x["texto"]) or
           any(k in N.sem_acento(x["titulo"] + " " + x["texto"]) for k in chaves)]
    print(f"Material que cita times da grade ou a Loteca: {len(rel)} de {len(material)}")
    anexar(os.path.join(DADOS, "influenciadores_aberto.csv"), CAMPOS_MAT,
           [{"concurso": c, "fonte": x["fonte"], "tipo": x["tipo"], "quando": x["quando"], "titulo": x["titulo"],
             "texto": x["texto"][:3000], "link": x["link"], "coletado_em_utc": carimbo} for x in rel])
    pal = ia_palpites(grade, rel)
    if pal:
        anexar(os.path.join(DADOS, "influenciadores_palpites.csv"), CAMPOS_PAL,
               [{"concurso": c, "jogo": int(p["jogo"]), "mandante": grade.get(int(p["jogo"]), ("", ""))[0],
                 "visitante": grade.get(int(p["jogo"]), ("", ""))[1], "fonte": p.get("fonte", ""), "palpite": p.get("palpite", ""),
                 "trecho": str(p.get("trecho", ""))[:300], "link": p.get("link", ""), "coletado_em_utc": carimbo} for p in pal])
        print(f"IA: {len(pal)} palpites/opinioes extraidos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
