"""
Jogo pronto da Arena do AZ (tabela "PALPITES AAZ" de cada concurso).

Le as marcacoes (celulas cinza nas colunas 1, X e 2) da imagem publicada no post
"Palpites / Historicos" e grava coleta/dados/arena_palpites.csv:
  concurso, jogo, marcas (ex.: '1', '1X', '1X2'), tipo (seco/duplo/triplo), imagem
Uso: python coleta/ocr/arena_palpites.py [historico|semanal]
"""
import csv
import io
import json
import os
import re
import sys
import time

import numpy as np
import requests
from PIL import Image
from scipy import ndimage

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(os.path.dirname(AQUI), "dados")
SAIDA = os.path.join(DADOS, "arena_palpites.csv")
CACHE = os.path.join(AQUI, "aaz_palpites")
API = "https://arenadoaz.com/wp-json/wp/v2/posts?categories=772985&per_page={n}&page={p}&_fields=id,date,title,content"
HEAD = {"User-Agent": "Mozilla/5.0 (pesquisa pessoal; coleta leve)"}


def ler_marcas(img):
    a = np.asarray(img.convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    cinza = (abs(r - g) < 12) & (abs(g - b) < 12) & (r > 135) & (r < 200)
    lab, n = ndimage.label(cinza)
    W = a.shape[1]
    cel = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        area = int((lab[sl] == i).sum())
        if 15 <= h <= 60 and 20 <= w <= 90 and area > 0.6 * h * w:
            cy, cx = (sl[0].start + sl[0].stop) / 2, (sl[1].start + sl[1].stop) / 2
            fx = cx / W
            perto = min(abs(fx - 0.12), abs(fx - 0.44), abs(fx - 0.76))
            if cy > 0.11 * a.shape[0] and perto < 0.045:  # so a tabela e so as colunas 1, X e 2 (fora o logotipo)
                cel.append((cy, cx, h))
    if not cel:
        return None
    # linhas: agrupa por y
    cel.sort()
    linhas, atual = [], [cel[0]]
    for c in cel[1:]:
        if c[0] - atual[-1][0] < c[2] * 0.6:
            atual.append(c)
        else:
            linhas.append(atual)
            atual = [c]
    linhas.append(atual)
    if len(linhas) != 14:
        return None
    out = []
    for ln in linhas:
        m = set()
        for _, x, _ in ln:
            fx = x / W
            m.add("1" if fx < 0.30 else ("X" if fx < 0.60 else "2"))
        out.append("".join(c for c in "1X2" if c in m))
    return out


def posts():
    todos = []
    for p in range(1, 10):
        r = requests.get(API.format(n=100, p=p), headers=HEAD, timeout=60)
        if r.status_code != 200 or not r.json():
            break
        todos += r.json()
        time.sleep(1)
    return todos


def imagem_do_post(post):
    imgs = re.findall(r'src="([^"]+\.(?:png|jpg|jpeg|webp))', post["content"]["rendered"])
    pal = [i for i in imgs if re.search(r"palpite", i, re.I) and not re.search(r"miniatura|desdobr|custo", i, re.I)]
    return pal[0] if pal else None


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "semanal"
    os.makedirs(CACHE, exist_ok=True)
    feitos = {}
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                feitos.setdefault(int(r["concurso"]), []).append(r)
    lista = posts() if modo == "historico" else requests.get(API.format(n=5, p=1), headers=HEAD, timeout=60).json()
    novos, falhas = 0, []
    for post in lista:
        t = re.sub("<[^>]+>", "", post["title"]["rendered"])
        m = re.search(r"(\d{3,4})", t)
        if not m:
            continue
        c = int(m.group(1))
        if c in feitos and modo == "historico":
            continue
        url = imagem_do_post(post)
        if not url:
            falhas.append((c, "sem imagem"))
            continue
        arq = os.path.join(CACHE, f"{c}.png")
        if not os.path.exists(arq):
            b = requests.get(url, headers=HEAD, timeout=60).content
            with open(arq, "wb") as f:
                f.write(b)
            time.sleep(0.5)
        try:
            marcas = ler_marcas(Image.open(arq))
        except Exception as e:
            marcas = None
        if not marcas:
            falhas.append((c, "nao leu 14 linhas"))
            continue
        feitos[c] = [{"concurso": c, "jogo": j, "marcas": mk,
                      "tipo": {1: "seco", 2: "duplo", 3: "triplo"}[len(mk)], "imagem": url}
                     for j, mk in enumerate(marcas, 1)]
        novos += 1
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["concurso", "jogo", "marcas", "tipo", "imagem"])
        w.writeheader()
        for c in sorted(feitos):
            w.writerows(feitos[c])
    print(f"Arena (jogo pronto): {novos} concursos novos, {len(feitos)} no total; falhas: {len(falhas)} {falhas[:10]}")


if __name__ == "__main__":
    main()
