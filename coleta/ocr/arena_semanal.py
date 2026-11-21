"""
Coleta semanal das odds bet365 publicadas pela Arena do AZ (imagem).

Busca os posts de cotacoes mais recentes, le as imagens dos concursos novos
(e rele o concurso mais recente, porque a Arena atualiza a imagem durante a
semana) e grava em coleta/ocr/arena_ocr.jsonl. Depois roda avaliar_arena.py,
que casa com a grade oficial e atualiza coleta/dados/arena_odds.csv
(concursos ainda abertos entram quando a Caixa publicar a grade/resultado).

Uso: python coleta/ocr/arena_semanal.py
"""
import json
import os
import re
import sys
import time

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import rodar_arena  # noqa: E402

JSONL = os.path.join(AQUI, "arena_ocr.jsonl")
TMP = os.path.join(AQUI, "_tmp_arena")
POSTS = "https://arenadoaz.com/wp-json/wp/v2/posts?search=cotacoes&per_page=10&_fields=date,slug,content"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36"}


def imagem_do_post(html):
    imgs = re.findall(r'src="(https?://[^"]+/uploads/[^"?]+\.(?:png|jpg))', html)
    imgs = [i for i in imgs if re.search(r"cotac", i, re.I) and "MINIATURA" not in i.upper()]
    return imgs[0] if imgs else None


def main():
    registros = {}
    if os.path.exists(JSONL):
        with open(JSONL, encoding="utf-8") as f:
            for l in f:
                r = json.loads(l)
                registros[r["concurso_post"]] = r
    r = requests.get(POSTS, headers=UA, timeout=60)
    r.raise_for_status()
    posts = []
    for p in r.json():
        m = re.search(r"loteca-(\d{3,4})-cotacoes", p["slug"])
        if m:
            posts.append((int(m.group(1)), imagem_do_post(p["content"]["rendered"])))
    if not posts:
        print("nenhum post de cotacoes encontrado")
        sys.exit(1)
    mais_recente = max(c for c, _ in posts)
    alvo = [(c, u) for c, u in posts if u and (c not in registros or c == mais_recente)]
    print(f"posts recentes: {sorted(c for c, _ in posts)} | a ler: {[c for c, _ in alvo]}")
    os.makedirs(TMP, exist_ok=True)
    for c, url in alvo:
        arq = os.path.join(TMP, f"{c}.png")
        img = requests.get(url, headers=UA, timeout=60)
        img.raise_for_status()
        with open(arq, "wb") as f:
            f.write(img.content)
        res = rodar_arena.processa(arq)
        os.remove(arq)
        lidos = sum(1 for j in res.get("jogos", []) if j["odd_1"] and not j["erros"])
        print(f"  concurso {c} (titulo da imagem: {res.get('concurso_imagem')}): "
              f"{lidos}/14 jogos com odds aceitas" + (f" | FALHA {res['falha']}" if "falha" in res else ""))
        registros[c] = res
        time.sleep(1)
    with open(JSONL, "w", encoding="utf-8") as f:
        for c in sorted(registros):
            f.write(json.dumps(registros[c], ensure_ascii=False) + "\n")
    import avaliar_arena
    avaliar_arena.main()


if __name__ == "__main__":
    main()
