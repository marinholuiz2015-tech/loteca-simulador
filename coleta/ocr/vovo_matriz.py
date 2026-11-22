"""
Jogo pronto da Vovoteca: "matriz" do Vovo (um palpite seco por jogo).

Le o X marcado em cada uma das 14 linhas (colunas 1, X, 2) da imagem "matriz"
publicada nos posts de programacao. Entende os dois formatos usados:
  - ate 2024: tabela alta, X vermelho dentro de caixinhas;
  - depois: tabela larga a esquerda, X preto.
Grava coleta/dados/vovo_matriz.csv: concurso, jogo, seco, imagem.
Uso: python coleta/ocr/vovo_matriz.py [historico|semanal]
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
SAIDA = os.path.join(DADOS, "vovo_matriz.csv")
CACHE = os.path.join(AQUI, "vovo_matriz")
API = "https://vovoteca.com/wp-json/wp/v2/posts?categories=82602977,576512100,556868214&per_page={n}&page={p}&_fields=id,date,title,content"
HEAD = {"User-Agent": "Mozilla/5.0 (pesquisa pessoal; coleta leve)"}


def ler_secos(img):
    a = np.asarray(img.convert("RGB")).astype(int)
    H, W = a.shape[:2]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    largo = W / H > 1.3
    if largo:   # formato novo: X preto, tabela a esquerda
        cols = (0.088, 0.276, 0.465)
        marca = (r < 70) & (g < 70) & (b < 70)
        y0, y1 = 0.20, 0.99
    else:       # formato antigo: X vermelho
        cols = (0.122, 0.488, 0.81)
        marca = (r > 170) & (g < 90) & (b < 90)
        y0, y1 = 0.15, 0.76
    lab, n = ndimage.label(marca)
    cand = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        cy, cx = (sl[0].start + sl[0].stop) / 2 / H, (sl[1].start + sl[1].stop) / 2 / W
        if not (y0 < cy < y1) or not (6 <= h <= 45 and 6 <= w <= 45) or abs(h - w) > 0.6 * max(h, w):
            continue
        if largo and (h < 13 or w < 13 or not 0.75 <= w / h <= 1.5):
            continue  # letras dos nomes sao menores/estreitas; o X e quase quadrado
        d = [abs(cx - c) for c in cols]
        k = int(np.argmin(d))
        if d[k] < (0.022 if largo else 0.04):
            cand.append((cy, k, h))
    if len(cand) < 14:
        return None
    cand.sort()
    linhas, atual = [], [cand[0]]
    for c in cand[1:]:
        if (c[0] - atual[-1][0]) * H < c[2] * 0.8:
            atual.append(c)
        else:
            linhas.append(atual)
            atual = [c]
    linhas.append(atual)
    if len(linhas) != 14:
        return None
    out = []
    for ln in linhas:
        ks = {c[1] for c in ln}
        if len(ks) != 1:
            return None
        out.append("1X2"[ks.pop()])
    return out


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "semanal"
    os.makedirs(CACHE, exist_ok=True)
    feitos = {}
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                feitos.setdefault(int(r["concurso"]), []).append(r)
    paginas = range(1, 15) if modo == "historico" else range(1, 2)
    falhas, novos = [], 0
    for p in paginas:
        try:
            lista = requests.get(API.format(n=100 if modo == "historico" else 10, p=p), headers=HEAD, timeout=60).json()
        except Exception:
            break
        if not isinstance(lista, list) or not lista:
            break
        for post in lista:
            imgs = [u for u in re.findall(r'src="([^"]+\.(?:png|jpg|jpeg))', post["content"]["rendered"]) if "matriz" in u.lower()]
            if not imgs:
                continue
            m = re.search(r"/(\d{3,4})[-_]", imgs[0]) or re.search(r"(\d{3,4})", re.sub("<[^>]+>", "", post["title"]["rendered"]))
            if not m:
                continue
            c = int(m.group(1))
            if c in feitos:
                continue
            arq = os.path.join(CACHE, f"{c}.png")
            if not os.path.exists(arq):
                try:
                    with open(arq, "wb") as f:
                        f.write(requests.get(imgs[0], headers=HEAD, timeout=60).content)
                except Exception:
                    continue
                time.sleep(0.5)
            try:
                s = ler_secos(Image.open(arq))
            except Exception:
                s = None
            if not s:
                falhas.append(c)
                continue
            feitos[c] = [{"concurso": c, "jogo": j, "seco": x, "imagem": imgs[0]} for j, x in enumerate(s, 1)]
            novos += 1
        time.sleep(1)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["concurso", "jogo", "seco", "imagem"])
        w.writeheader()
        for c in sorted(feitos):
            w.writerows(feitos[c])
    print(f"Vovoteca (matriz): {novos} concursos novos, {len(feitos)} no total; falhas: {len(falhas)} {falhas[:12]}")


if __name__ == "__main__":
    main()
