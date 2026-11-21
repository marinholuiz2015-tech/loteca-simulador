"""
Leitura automatica (OCR) das imagens de Cotacoes/Probabilidades da Arena do AZ.

Estrategia (robusta aos varios layouts 2020-2026):
  1. acha as linhas verticais da tabela; as 7 ultimas delimitam as 6 colunas
     numericas (odd 1, odd X, odd 2, prob 1, prob X, prob 2);
  2. le os numeros 1..14 da coluna "Jogo" para achar o centro de cada linha
     (ajuste linear numero -> altura, tolera numeros nao lidos);
  3. recorta cada celula e le so digitos (tesseract, uma linha por celula).

Checagens por jogo: soma das probabilidades 97-103%; margem das odds
(soma de 1/odd) entre 1,00 e 1,25; probabilidade da Arena coerente com a
probabilidade implicita das odds (diferenca <= 4 pp).

Uso: python ocr_arena.py img/1284.png [...]
"""
import re
import sys

import cv2
import numpy as np
import pytesseract


def _picos(proj, limiar, gap=6):
    idx = np.where(proj > limiar)[0]
    grupos = []
    for i in idx:
        if grupos and i - grupos[-1][-1] <= gap:
            grupos[-1].append(i)
        else:
            grupos.append([i])
    return [int(np.mean(g)) for g in grupos]


def colunas(gray):
    h, w = gray.shape
    e = cv2.Canny(gray, 30, 100)
    vl = cv2.morphologyEx(e, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 20)))
    xs = _picos(vl.sum(0) / 255, h * 0.25)
    if len(xs) < 9:
        raise ValueError(f"linhas verticais insuficientes: {xs}")
    return xs[0], xs[1], xs[-7:]  # borda, fim da coluna Jogo, 7 limites numericos


def centros_linhas(gray, x0, x1):
    h, w = gray.shape
    col = gray[:, x0 + 2:x1 - 2]
    col = cv2.resize(col, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, b = cv2.threshold(col, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if b.mean() < 127:
        b = 255 - b
    d = pytesseract.image_to_data(b, config="--psm 6 -c tessedit_char_whitelist=0123456789",
                                  output_type=pytesseract.Output.DICT)
    pontos = []
    for t, top, hh in zip(d["text"], d["top"], d["height"]):
        if t.strip().isdigit() and 1 <= int(t) <= 14:
            pontos.append((int(t), (top + hh / 2) / 3))
    # mantem o primeiro de cada numero e descarta pontos fora da reta
    vis = {}
    for n, y in pontos:
        vis.setdefault(n, y)
    if len(vis) < 4:
        raise ValueError(f"coluna Jogo ilegivel ({len(vis)} numeros)")
    ns = np.array(sorted(vis)); ys = np.array([vis[n] for n in ns])
    for _ in range(3):
        a, b0 = np.polyfit(ns, ys, 1)
        res = np.abs(ys - (a * ns + b0))
        ok = res < max(4, a * 0.25)
        if ok.all():
            break
        ns, ys = ns[ok], ys[ok]
    a, b0 = np.polyfit(ns, ys, 1)
    return [a * n + b0 for n in range(1, 15)], a, len(vis)


def linhas_pela_grade(gray):
    """Centros e altura das 14 linhas a partir das linhas horizontais da
    grade (layouts 2020-2025). Devolve None se a grade nao for nitida."""
    h, w = gray.shape
    e = cv2.Canny(gray, 30, 100)
    hl = cv2.morphologyEx(e, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (w // 8, 1)))
    ys = _picos(hl.sum(1) / 255, w * 0.15)
    candidatos = []
    for i in range(len(ys) - 14):
        seq = ys[i:i + 15]
        d = np.diff(seq)
        med = np.median(d)
        if med >= 18 and (np.abs(d - med) <= med * 0.12).all():
            candidatos.append(seq)
    if not candidatos:
        return None
    if len(candidatos) == 1:
        seq = candidatos[0]
    else:
        # desempate: o numero lido na coluna "Jogo" tem de bater com a linha
        x0, x1, _ = colunas(gray)
        def acertos(seq):
            n = 0
            for k in (0, 6, 13):
                cel = gray[seq[k] + 3:seq[k + 1] - 2, x0 + 3:x1 - 3]
                t = pytesseract.image_to_string(_binariza(cel, 3),
                                                config="--psm 8 -c tessedit_char_whitelist=0123456789").strip()
                n += t == str(k + 1)
            return n
        seq = max(candidatos, key=acertos)
    return [(seq[k] + seq[k + 1]) / 2 for k in range(14)], float(np.median(np.diff(seq)))


def _binariza(cel, escala):
    c = cv2.resize(cel, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    _, b = cv2.threshold(c, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if b.mean() < 127:
        b = 255 - b
    return cv2.copyMakeBorder(b, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)


def _odd(t):
    t = t.replace(".", ",")
    m = re.search(r"(\d{1,2}),?(\d{2})", t)
    return float(f"{m.group(1)}.{m.group(2)}") if m else None


def _pct(t):
    m = re.search(r"(\d{1,3})", t)
    if not m:
        return None
    v = int(m.group(1))
    if v > 100:  # o "%" lido como digito extra
        v = int(str(v)[:-1])
    return v


def ler_celula(gray, x0, x1, yc, alt, pct):
    """Le com duas combinacoes de tratamento; devolve (valor_a, valor_b)."""
    y0, y1 = int(yc - alt * 0.40), int(yc + alt * 0.40)
    cel = gray[max(0, y0):y1, x0 + 4:x1 - 4]
    wl = "0123456789" if pct else "0123456789,"
    ta = pytesseract.image_to_string(_binariza(cel, 4),
                                     config=f"--psm 8 -c tessedit_char_whitelist={wl}").strip()
    tb = pytesseract.image_to_string(_binariza(cel, 2),
                                     config=f"--psm 7 -c tessedit_char_whitelist={wl}").strip()
    f = _pct if pct else _odd
    return f(ta), f(tb)


def _escolhe(a, b, prob_ref):
    """Junta as duas leituras de uma odd. Concordando, aceita. Divergindo,
    fica com a que bate com a probabilidade da Arena (se lida)."""
    if a == b:
        return a
    cand = [v for v in (a, b) if v]
    if not cand:
        return None
    if len(cand) == 1:
        return cand[0]
    return cand


def ler_imagem(caminho):
    img = cv2.imread(caminho)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    x0, x1, lim = colunas(gray)
    grade = linhas_pela_grade(gray)
    if grade:
        centros, alt = grade
    else:
        centros, alt, _ = centros_linhas(gray, x0, x1)
    jogos = []
    for j, yc in enumerate(centros, 1):
        odds = [ler_celula(gray, lim[k], lim[k + 1], yc, alt, pct=False) for k in range(3)]
        probs = [ler_celula(gray, lim[k], lim[k + 1], yc, alt, pct=True) for k in range(3, 6)]
        # probabilidade so conta como conferencia quando as duas leituras concordam
        prob = [p[0] if p[0] == p[1] else None for p in probs]
        escolha = [_escolhe(a, b, None) for a, b in odds]
        # divergencias: testa as combinacoes e fica com a mais coerente com as probabilidades
        opcoes = [[e] if not isinstance(e, list) else e for e in escolha]
        melhor, erro_min = None, 1e9
        for o1 in opcoes[0]:
            for ox in opcoes[1]:
                for o2 in opcoes[2]:
                    if None in (o1, ox, o2) or 0 in (o1, ox, o2):
                        continue
                    inv = [1 / o1, 1 / ox, 1 / o2]
                    s = sum(inv)
                    err = sum(abs(100 * p / s - q) for p, q in zip(inv, prob) if q is not None)
                    if not 1.0 <= s <= 1.25:
                        err += 100
                    if err < erro_min:
                        melhor, erro_min = (o1, ox, o2), err
        o1, ox, o2 = melhor if melhor else (None, None, None)
        jogos.append(dict(jogo=j, odd_1=o1, odd_x=ox, odd_2=o2,
                          prob_1=prob[0], prob_x=prob[1], prob_2=prob[2],
                          divergiu=any(isinstance(e, list) for e in escolha)))
    return jogos


def checar(j):
    """Erros de um jogo. As odds sao o dado principal; as probabilidades da
    Arena (calculadas a partir das odds) servem de conferencia."""
    if None in (j["odd_1"], j["odd_x"], j["odd_2"]):
        return ["odd nao lida"]
    erros = []
    probs = [j["prob_1"], j["prob_x"], j["prob_2"]]
    if None not in probs:
        soma = sum(probs)
        if not 97 <= soma <= 103:
            erros.append(f"soma={soma}")
    inv = [1 / j["odd_1"], 1 / j["odd_x"], 1 / j["odd_2"]]
    s = sum(inv)
    if not 1.0 <= s <= 1.25:
        erros.append(f"margem={s:.2f}")
    for k, p in zip(("1", "x", "2"), inv):
        q = j["prob_" + k]
        if q is not None and abs(100 * p / s - q) > 4:
            erros.append(f"p{k}")
    return erros


if __name__ == "__main__":
    for c in sys.argv[1:]:
        try:
            jogos = ler_imagem(c)
        except Exception as e:
            print(f"{c}: FALHOU ({e})")
            continue
        ruins = [(j["jogo"], checar(j)) for j in jogos if checar(j)]
        print(f"{c}: {14 - len(ruins)}/14 jogos passam nas checagens")
        for n, e in ruins:
            print(f"   jogo {n}: {jogos[n - 1]} -> {e}")
