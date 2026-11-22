"""
Boloes da Vovoteca ("Boloes oficiais Caixa / criacao Vovoteca": A, B, C, D).

Le cada imagem de bolao publicada nos posts: para as 14 linhas, quais colunas
(1, X, 2) estao marcadas. Marcas pretas ou vermelhas. A leitura so e aceita
quando bate com as colunas D/T da propria imagem (linhas com 2 marcas = D,
com 3 = T). Imagens largas com dois boloes lado a lado sao divididas ao meio.
Grava coleta/dados/vovo_boloes.csv: concurso, bolao, jogo, marcas, imagem.
Uso: python coleta/ocr/vovo_boloes.py [historico|semanal]
"""
import csv
import os
import re
import sys
import time

import numpy as np
import requests
from PIL import Image
from scipy import ndimage

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(os.path.dirname(AQUI), "dados", "vovo_boloes.csv")
CACHE = os.path.join(AQUI, "vovo_boloes")
API = "https://vovoteca.com/wp-json/wp/v2/posts?per_page={n}&page={p}&search=bol&_fields=id,date,content"
HEAD = {"User-Agent": "Mozilla/5.0 (pesquisa pessoal; coleta leve)"}
TIPOS = re.compile(r"^(bolao-[a-d]|bolao-vovoteca|boloes-vovo-a-b|bolao-unico|boladao)$")


def ler_painel(a):
    H, W = a.shape[:2]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    marca = ((r < 80) & (g < 80) & (b < 80)) | ((r > 140) & (r - g > 70) & (r - b > 70))
    lab, _ = ndimage.label(marca)
    cand = []
    for sl in ndimage.find_objects(lab):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        mn = max(5, round(0.011 * H))
        if not (mn <= h <= 40 and mn <= w <= 40 and 0.6 <= w / h <= 1.7):
            continue
        my, mx = (sl[0].start + sl[0].stop) // 2, (sl[1].start + sl[1].stop) // 2
        if not marca[my - 2:my + 3, mx - 2:mx + 3].any():
            continue  # caixinha vazia (so contorno) nao e marca; o X cruza no meio
        cy, cx = (sl[0].start + sl[0].stop) / 2 / H, (sl[1].start + sl[1].stop) / 2 / W
        if 0.065 < cx < 0.17 or 0.40 < cx < 0.53 or 0.72 < cx < 0.93:
            cand.append((cy, cx, h))
    if len(cand) < 14:
        return None
    def coluna(a, b, primeiro=False):  # grupo mais cheio da janela (letras dos nomes ficam espalhadas)
        xs = sorted(c[1] for c in cand if a < c[1] < b)
        if not xs:
            return None
        g = [[xs[0]]]
        for x in xs[1:]:
            (g[-1].append(x) if x - g[-1][-1] < 0.012 else g.append([x]))
        if primeiro:  # coluna "1": o grupo cheio mais a esquerda (a 1a letra do mandante vem logo depois)
            g = [v for v in g if len(v) >= 3] or g
            return (np.median(g[0]) - 0.02, np.median(g[0]) + 0.02)
        m = np.median(max(g, key=len))
        return (m - 0.018, m + 0.018)
    col = {"1": coluna(0.065, 0.17, True), "X": coluna(0.40, 0.53), "2": coluna(0.72, 0.795)}
    if not (col["1"] and col["X"] and col["2"]):
        return None
    cand.sort()
    linhas, atual = [], [cand[0]]
    for c in cand[1:]:
        (atual.append(c) if (c[0] - atual[-1][0]) * H < c[2] * 0.8 else (linhas.append(atual), atual := [c]))
    linhas.append(atual)
    linhas = [ln for ln in linhas if any(col["1"][0] < c[1] < col["2"][1] for c in ln)]
    # titulo, cabecalho e rodape tambem viram "linhas": testa cada janela de 14
    # entre as janelas validas, a que tem mais marcas (titulo/cabecalho tem 1 letra solta)
    # e cada linha de verdade tem o numero do jogo (1..14) escrito na coluna JG
    validas = []
    for i in range(len(linhas) - 13):
        o = _ler(linhas[i:i + 14], col, a)
        if o:
            jg = sum(_tinta(a, np.mean([c[0] for c in ln]), 0.005, 0.065) for ln in linhas[i:i + 14])
            validas.append((jg, sum(map(len, o)), i, o))
    return max(validas)[3] if validas else None


def _tinta(a, y, x0, x1):
    H, W = a.shape[:2]
    faixa = a[max(0, int((y - 0.012) * H)):int((y + 0.012) * H) + 1, int(x0 * W):int(x1 * W)]
    n = (faixa.max(axis=2) < 110).sum(axis=0)
    return int(((n >= 2) & (n < 0.8 * faixa.shape[0])).sum() >= 3)


def _dt(a, y, x2):
    """Tinta escura nas celulas D/T da linha (o x fino de D/T as vezes some no filtro de marca)."""
    H, W = a.shape[:2]
    faixa = a[max(0, int((y - 0.012) * H)):int((y + 0.012) * H) + 1, int((x2 + 0.03) * W):int(0.93 * W)]
    n = (faixa.max(axis=2) < 110).sum(axis=0)
    escuro = np.where((n >= 2) & (n < 0.8 * faixa.shape[0]))[0]  # linhas de grade ocupam a faixa toda
    if len(escuro) < 3:
        return ""
    x = x2 + 0.03 + np.median(escuro) / W
    return "D" if x < x2 + 0.085 else "T"


def _ler(linhas, col, a):
    x2 = col["2"][0] + 0.018
    out, nd, nt = [], 0, 0
    for ln in linhas:
        s = "".join(k for k in "1X2" if any(col[k][0] < c[1] < col[k][1] for c in ln))
        if not s:
            return None
        out.append(s)
        dt = _dt(a, np.mean([c[0] for c in ln]), x2)
        tem_d, tem_t = dt == "D", dt == "T"
        if tem_d != (len(s) == 2) or tem_t != (len(s) == 3):
            return None  # linha a linha: D marcado <=> duplo, T marcado <=> triplo
        nd += tem_d
        nt += tem_t
    if nd + nt == 0:
        return None
    return out


def ler_boloes(img):
    a = np.asarray(img.convert("RGB")).astype(int)
    H, W = a.shape[:2]
    paineis = [a[:, : W // 2], a[:, W // 2:]] if W / H > 1.3 else [a]
    return [ler_painel(p) for p in paineis]


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "semanal"
    os.makedirs(CACHE, exist_ok=True)
    linhas = []
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
    feitos = {r["imagem"] for r in linhas}
    falhas, novos = [], 0
    for p in (range(1, 15) if modo == "historico" else range(1, 2)):
        try:
            lista = requests.get(API.format(n=100 if modo == "historico" else 20, p=p), headers=HEAD, timeout=60).json()
        except Exception:
            break
        if not isinstance(lista, list) or not lista:
            break
        for post in lista:
            for u in re.findall(r'src="([^"]+\.(?:png|jpg|jpeg))', post["content"]["rendered"]):
                m = re.match(r"(\d{3,4})[-_]?(.*)\.(png|jpe?g)$", u.rsplit("/", 1)[1].lower())
                if not m or not TIPOS.match(m.group(2)) or u in feitos:
                    continue
                c, tipo = int(m.group(1)), m.group(2)
                arq = os.path.join(CACHE, f"{c}-{tipo}.png")
                if not os.path.exists(arq):
                    try:  # direto da origem (o CDN i0.wp.com as vezes devolve texto de erro)
                        conteudo = requests.get(re.sub(r"https://i\d\.wp\.com/", "https://", u).split("?")[0],
                                                headers=HEAD, timeout=60).content
                    except Exception:
                        continue
                    if conteudo[:4] not in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\xff\xd8\xff\xdb"):
                        falhas.append(f"{c}-download")
                        continue
                    with open(arq, "wb") as f:
                        f.write(conteudo)
                    time.sleep(0.5)
                feitos.add(u)
                try:
                    lidos = ler_boloes(Image.open(arq))
                except Exception:
                    lidos = [None]
                nome = tipo.replace("bolao-", "").replace("boloes-vovo-", "").upper()
                for i, s in enumerate(lidos):
                    rot = (nome.split("-")[i] if "-" in nome and len(lidos) > 1 else nome)
                    if not s:
                        falhas.append(f"{c}-{rot}")
                        continue
                    novos += 1
                    linhas += [{"concurso": c, "bolao": rot, "jogo": j, "marcas": x, "imagem": u} for j, x in enumerate(s, 1)]
        time.sleep(1)
    linhas.sort(key=lambda r: (int(r["concurso"]), r["bolao"], int(r["jogo"])))
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["concurso", "bolao", "jogo", "marcas", "imagem"])
        w.writeheader()
        w.writerows(linhas)
    print(f"Boloes Vovoteca: {novos} boloes novos lidos; falhas: {len(falhas)} {falhas[:15]}")


if __name__ == "__main__":
    main()
