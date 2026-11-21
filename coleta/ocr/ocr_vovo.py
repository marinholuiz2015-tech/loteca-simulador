"""
Leitura automatica (OCR) das imagens da enquete da Vovoteca (efeito manada).

Dois formatos convivem (2022-2026):
  A) tabela gerada pelo site da enquete: percentuais com 2 decimais;
  B) arte em planilha: percentuais inteiros com "%".
Nos dois a ordem das colunas e: JG | Mandante | 1 | X | 2 | Visitante.

Passos: colunas pelas linhas verticais (ou, se faltarem, pelo fundo colorido
das 3 colunas de percentual); centro das linhas pelos numeros da coluna JG;
leitura celula a celula com duas combinacoes de tratamento.
Checagem por jogo: soma dos tres percentuais entre 98 e 102.

Uso: python ocr_vovo.py img/1284.png [...]
"""
import os
import re
import sys

import cv2
import numpy as np
import pytesseract

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocr_arena import _binariza, _picos, centros_linhas  # noqa: E402


def colunas(img, gray):
    h, w = gray.shape
    e = cv2.Canny(gray, 30, 100)
    vl = cv2.morphologyEx(e, cv2.MORPH_OPEN,
                          cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, h // 40))))
    # procura as 3 colunas estreitas e parecidas (1, X, 2) entre duas largas
    # (mandante e visitante); resiste a faixas/logos extras nas bordas.
    # Tenta primeiro o limiar normal e depois um mais sensivel (linha fraca).
    for limiar in (0.25, 0.15, 0.08):
        xs = _picos(vl.sum(0) / 255, h * limiar)
        for i in range(2, len(xs) - 3):
            lar = [xs[i + k + 1] - xs[i + k] for k in range(3)]
            med = float(np.median(lar))
            mand = xs[i] - xs[i - 1]
            vis = xs[i + 4] - xs[i + 3] if i + 4 < len(xs) else w - xs[i + 3]
            if med > 15 and all(abs(l - med) <= med * 0.3 for l in lar) and mand > 1.8 * med and vis > 1.8 * med:
                return xs[i - 2], xs[i - 1], xs[i:i + 4]
    xs = _picos(vl.sum(0) / 255, h * 0.25)
    if len(xs) >= 7:
        return xs[0], xs[1], xs[2:6]
    # plano B: faixa de maior saturacao (fundos coloridos das 3 colunas)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    faixa = hsv[int(h * 0.2):int(h * 0.75), :, 1].mean(0)
    alto = np.where(faixa > np.percentile(faixa, 70))[0]
    grupos = []
    for i in alto:
        if grupos and i - grupos[-1][-1] <= 4:
            grupos[-1].append(i)
        else:
            grupos.append([i])
    g = max(grupos, key=len)
    a, b = g[0], g[-1]
    passo = (b - a) / 3
    return xs[0], xs[1], [int(a), int(a + passo), int(a + 2 * passo), int(b)]


def _valor(t):
    t = t.replace(",", ".")
    m = re.search(r"(\d{1,3})(?:\.(\d{1,2}))?", t)
    if not m:
        return None
    v = float(m.group(1) + ("." + m.group(2) if m.group(2) else ""))
    if v > 100 and not m.group(2):  # "%" lido como digito
        v = float(m.group(1)[:-1])
    return v if 0 <= v <= 100 else None


def ler_celula(gray, x0, x1, yc, alt):
    cel = gray[max(0, int(yc - alt * 0.40)):int(yc + alt * 0.40), x0 + 3:x1 - 3]
    wl = "0123456789.,"
    a = _valor(pytesseract.image_to_string(_binariza(cel, 4),
               config=f"--psm 8 -c tessedit_char_whitelist={wl}"))
    b = _valor(pytesseract.image_to_string(_binariza(cel, 2),
               config=f"--psm 7 -c tessedit_char_whitelist={wl}"))
    # terceira leitura sem a borda direita (setas/icones ao lado do numero)
    w = cel.shape[1]
    c = _valor(pytesseract.image_to_string(_binariza(cel[:, : int(w * 0.74)], 3),
               config=f"--psm 7 -c tessedit_char_whitelist={wl}")) if w > 20 else None
    return a, b, c


FAIXAS = {  # faixa de valor indicada pela cor de fundo da celula
    "zebra": (0, 12.99), "surpresa": (13, 25.99), "normal": (26, 50.99),
    "favorito": (51, 80.99), "super": (79, 100),
}


def faixa_por_cor(img, x0, x1, yc, alt):
    """Classifica a cor de fundo da celula (mediana da celula inteira).
    Devolve a faixa de valores possivel ou None se a cor nao for reconhecida."""
    if img is None:
        return None
    cel = img[max(0, int(yc - alt * 0.35)):int(yc + alt * 0.35), x0 + 3:x1 - 3]
    if cel.size == 0:
        return None
    hsv = cv2.cvtColor(cel, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    h, s, v = np.median(hsv, axis=0)
    if s < 90:
        return None  # branco/cinza: formato sem cor de faixa
    if h < 10 or h > 165:
        return FAIXAS["zebra"]
    if 18 <= h <= 40:
        return FAIXAS["surpresa"]
    if 80 <= h <= 105:
        return FAIXAS["normal"]
    if 40 < h < 80:
        return FAIXAS["favorito"] if v > 200 else FAIXAS["super"]
    return None


def _candidatos(par, faixa=None):
    """Leituras a/b de uma celula + variantes sem um digito (icone ou '%' lido
    como digito: '4%' -> 14). Se a cor da celula indicar a faixa, so ficam os
    candidatos dentro dela (um 14 em celula de zebra e impossivel)."""
    out = set()
    for v in par:
        if v is None:
            continue
        out.add(v)
        if v == int(v) and v >= 10:
            out.add(float(int(v) // 10))   # sem o ultimo digito
            out.add(float(int(v) % 10))    # sem o primeiro digito
            if v >= 100:
                out.add(float(int(v) % 100))
    if faixa:
        dentro = {v for v in out if faixa[0] <= v <= faixa[1]}
        if dentro:
            return dentro
    return out or {None}


def _ler_linhas(gray, lim, centros, alt, img=None):
    jogos = []
    for j, yc in enumerate(centros, 1):
        leituras = [_candidatos(ler_celula(gray, lim[k], lim[k + 1], yc, alt),
                                faixa_por_cor(img, lim[k], lim[k + 1], yc, alt)) for k in range(3)]
        melhor, dif = None, 1e9
        for va in leituras[0]:
            for vx in leituras[1]:
                for v2 in leituras[2]:
                    if None in (va, vx, v2):
                        continue
                    d = abs(va + vx + v2 - 100)
                    if d < dif:
                        melhor, dif = (va, vx, v2), d
        p1, px, p2 = melhor if melhor else (None, None, None)
        jogos.append(dict(jogo=j, massa_1=p1, massa_x=px, massa_2=p2))
    return jogos


def _sequencias_grade(gray, tol=0.22):
    h, w = gray.shape
    e = cv2.Canny(gray, 30, 100)
    hl = cv2.morphologyEx(e, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (w // 8, 1)))
    ys = _picos(hl.sum(1) / 255, w * 0.15)
    seqs = []
    for i in range(len(ys) - 14):
        s = ys[i:i + 15]
        d = np.diff(s)
        med = np.median(d)
        if med >= 12 and (np.abs(d - med) <= med * tol).all():
            seqs.append(([(s[k] + s[k + 1]) / 2 for k in range(14)], float(med)))
    return seqs


def _norm_nome(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z]", "", s)


def confere_nome(texto, nome):
    a, b = _norm_nome(texto), _norm_nome(nome)
    return bool(a and b) and (a[:3] == b[:3] or a in b or b in a)


def ler_imagem(caminho, mandantes=None):
    """mandantes: lista opcional com os 14 mandantes da grade da Caixa; se
    vier, a posicao das linhas e escolhida tambem pelos nomes que batem."""
    img = cv2.imread(caminho)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    x0, x1, lim = colunas(img, gray)
    opcoes = _sequencias_grade(gray)
    try:
        c, a, _ = centros_linhas(gray, x0, x1)
        opcoes.append((c, a))
    except Exception:
        pass
    if not opcoes:
        raise ValueError("linhas da tabela nao encontradas")
    # fica com a posicao de linhas que deixa mais jogos com soma ~100
    h, w = gray.shape
    # 1o: le os percentuais em cada posicao de linha possivel
    candidatos = []
    for c, a in opcoes:
        js = _ler_linhas(gray, lim, c, a, img)
        candidatos.append((sum(1 for j in js if not checar(j)), js, c, a))
    candidatos.sort(key=lambda r: -r[0])
    # 2o: le os nomes dos times so nas 2 melhores posicoes (economiza tempo)
    resultados = []
    for pontos, js, c, a in candidatos[:2]:
        for j, yc in zip(js, c):
            j["texto_mandante"] = _texto(gray, x1, lim[0], yc, a)
            j["texto_visitante"] = _texto(gray, lim[3], w - 2, yc, a)
        if mandantes:
            pontos += 2 * sum(1 for j, m in zip(js, mandantes) if confere_nome(j["texto_mandante"], m))
        resultados.append((pontos, js))
    return max(resultados, key=lambda r: r[0])[1]


def _texto(gray, xa, xb, yc, alt):
    cel = gray[max(0, int(yc - alt * 0.42)):int(yc + alt * 0.42), xa + 2:xb - 2]
    if cel.size == 0:
        return ""
    cel = cv2.resize(cel, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    t = pytesseract.image_to_string(cel, config="--psm 7")
    return re.sub(r"\s+", " ", t).strip()


def checar(j):
    v = [j["massa_1"], j["massa_x"], j["massa_2"]]
    if None in v:
        return ["nao lido"]
    s = sum(v)
    decimal = any(x != int(x) for x in v)
    lim = 0.6 if decimal else 1  # formato A soma 100,00; formato B arredonda (99 a 101)
    return [] if abs(s - 100) <= lim else [f"soma={s:.1f}"]


if __name__ == "__main__":
    for c in sys.argv[1:]:
        try:
            jogos = ler_imagem(c)
        except Exception as e:
            print(f"{c}: FALHOU ({e})")
            continue
        ruins = [j for j in jogos if checar(j)]
        print(f"{c}: {14 - len(ruins)}/14 passam | " +
              " ".join(f"{j['jogo']}:{j['massa_1']}/{j['massa_x']}/{j['massa_2']}" for j in jogos))
        for j in ruins:
            print(f"   jogo {j['jogo']}: {checar(j)}")
