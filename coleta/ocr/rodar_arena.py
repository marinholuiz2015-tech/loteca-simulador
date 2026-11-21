"""
Le todas as imagens de cotacoes da Arena (todas/NNNN.png) e grava
arena_ocr.jsonl (uma linha por imagem, retomavel):
  concurso_post, concurso_imagem (lido no titulo), jogos[ {jogo, odd_1, odd_x,
  odd_2, prob_1, prob_x, prob_2, texto_times, erros} ]
"""
import glob
import json
import os
import re
import sys
from multiprocessing import Pool

import cv2
import pytesseract

import ocr_arena as o

SAIDA = "arena_ocr.jsonl"


def numero_no_titulo(gray):
    h, w = gray.shape
    topo = gray[: int(h * 0.2), :]
    topo = cv2.resize(topo, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    t = pytesseract.image_to_string(topo, config="--psm 6")
    m = re.search(r"LOTECA\s*(\d{3,4})", t.upper().replace("O", "O"))
    return int(m.group(1)) if m else None


def texto_times(gray, x1, xnum, yc, alt):
    cel = gray[max(0, int(yc - alt * 0.42)):int(yc + alt * 0.42), x1 + 2:xnum - 2]
    cel = cv2.resize(cel, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return re.sub(r"\s+", " ", pytesseract.image_to_string(cel, config="--psm 7")).strip()


def processa(caminho):
    conc = int(os.path.basename(caminho).split(".")[0])
    try:
        gray = cv2.cvtColor(cv2.imread(caminho), cv2.COLOR_BGR2GRAY)
        x0, x1, lim = o.colunas(gray)
        grade = o.linhas_pela_grade(gray)
        centros, alt = grade if grade else o.centros_linhas(gray, x0, x1)[:2]
        jogos = o.ler_imagem(caminho)
        for j, yc in zip(jogos, centros):
            j["texto_times"] = texto_times(gray, x1, lim[0], yc, alt)
            j["erros"] = o.checar(j)
        return dict(concurso_post=conc, concurso_imagem=numero_no_titulo(gray), jogos=jogos)
    except Exception as e:
        return dict(concurso_post=conc, falha=str(e))


if __name__ == "__main__":
    feitos = set()
    if os.path.exists(SAIDA):
        with open(SAIDA) as f:
            feitos = {json.loads(l)["concurso_post"] for l in f}
    arquivos = sorted(glob.glob("todas/*"), key=lambda p: int(os.path.basename(p).split(".")[0]))
    falta = [a for a in arquivos if int(os.path.basename(a).split(".")[0]) not in feitos]
    print(f"a processar: {len(falta)}", flush=True)
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as p, open(SAIDA, "a") as out:
        for i, r in enumerate(p.imap_unordered(processa, falta), 1):
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush()
            if i % 10 == 0:
                print(f"{i}/{len(falta)}", flush=True)
    print("fim", flush=True)
