"""Leitura comum dos arquivos do football-data e casamento de nomes de times com a grade da Loteca."""
import csv
import datetime
import difflib
import glob
import os
import re
import unicodedata

FD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "coleta", "dados", "fd")
STOP = {"FC", "EC", "SC", "AC", "CF", "CD", "SE", "CR", "FK", "SK", "AFC", "RJ", "SP", "MG", "PR", "RS", "GO", "BA",
        "PE", "CE", "SAD", "CLUB", "DE", "UD", "RC", "RCD", "US", "SS", "AS", "VFB", "VFL", "TSG", "FSV", "SV", "OSC",
        "STADE", "OLYMPIQUE", "DA", "DO"}
ALIAS = {"ATL": "ATLETICO", "BOTA": "BOTAFOGO", "INTER": "INTERNACIONAL", "M UNITED": "MAN UNITED",
         "MAN UTD": "MAN UNITED", "M CITY": "MAN CITY", "R MADRID": "REAL MADRID", "ATL MADRID": "ATH MADRID",
         "ATLETICO MADRID": "ATH MADRID", "S PAULO": "SAO PAULO", "ATH": "ATHLETICO", "R BETIS": "BETIS",
         "R SOCIEDAD": "SOCIEDAD", "W HAM": "WEST HAM", "INTER ITA": "INTER", "INTER DE MILAO": "INTER",
         "PSG": "PARIS SG", "B DORTMUND": "DORTMUND", "B MUNIQUE": "BAYERN MUNICH", "BAYERN": "BAYERN MUNICH",
         "RB BRAGANTINO": "BRAGANTINO", "VASCO GAMA": "VASCO"}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s.replace("-", " "))
    t = [w for w in s.split() if w not in STOP]
    n = " ".join(t) or s.strip()
    for a, b in ALIAS.items():
        if n == a or n.startswith(a + " "):
            n = b + n[len(a):]
    return n


def sim(a, b):
    a, b = norm(a), norm(b)
    if a == b:
        return 1.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()), set(b.split())
    if ta and tb and (ta <= tb or tb <= ta):
        r = max(r, 0.85)
    if len(a) >= 5 and a[:5] == b[:5]:
        r = max(r, 0.8)
    return r


def data(s):
    for f in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(s.strip(), f).date()
        except Exception:
            pass
    return None


def _f(x):
    try:
        v = float(x)
        return v if v > 1 else None
    except Exception:
        return None


ODDS = {"ps": ("PSCH", "PSCD", "PSCA"), "bf": ("BFECH", "BFECD", "BFECA"), "avg": ("AvgCH", "AvgCD", "AvgCA"),
        "b365c": ("B365CH", "B365CD", "B365CA"), "pso": ("PSH", "PSD", "PSA"), "b365o": ("B365H", "B365D", "B365A"),
        "avgo": ("AvgH", "AvgD", "AvgA")}


def jogos():
    """Todos os jogos: dict liga, temporada, d, casa, fora, gc, gf (ou None se nao jogado), odds por fonte."""
    out = []
    for arq in sorted(glob.glob(os.path.join(FD, "*.csv"))):
        nome = os.path.basename(arq)[:-4]
        liga = nome if nome.startswith("new_") else nome.split("_", 1)[1]
        try:
            rows = list(csv.DictReader(open(arq, encoding="utf-8-sig", errors="ignore")))
        except Exception:
            continue
        for r in rows:
            d = data(r.get("Date") or "")
            h, a = r.get("HomeTeam") or r.get("Home"), r.get("AwayTeam") or r.get("Away")
            if not (d and h and a):
                continue
            try:
                gc, gf = int(float(r.get("FTHG") or r.get("HG"))), int(float(r.get("FTAG") or r.get("AG")))
            except Exception:
                gc = gf = None
            g = {"liga": liga, "temporada": r.get("Season") if liga.startswith("new_") else nome.split("_")[0],
                 "d": d, "casa": h, "fora": a, "gc": gc, "gf": gf}
            for k, cols in ODDS.items():
                v = [_f(r.get(c)) for c in cols]
                if all(v):
                    g[k] = v
            out.append(g)
    return out
