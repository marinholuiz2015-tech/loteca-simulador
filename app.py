"""
Loteca Elite Pro — servidor do painel (Render).

So serve o painel oficial (/painel, com senha), os arquivos de dados dele e a banca de apostas.
O motor de previsao roda fora daqui (motor/ e coleta/, pelo GitHub Actions) e grava em docs/dados.
O servidor antigo, com o motor das fases anteriores, esta em legado/app_antigo.py (nao e mais usado).

Variaveis de ambiente no Render: PAINEL_USUARIO, PAINEL_SENHA, PAINEL_GITHUB_TOKEN (leitura),
PAINEL_GITHUB_ESCRITA (banca).
"""
import logging
import os
import time
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, redirect, request

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("loteca")

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({"ok": True, "servico": "painel Loteca Elite Pro"})


@app.route("/")
def raiz():
    return redirect("/painel/", code=302)  # redirect vem do bloco do painel


# ------------------------------------------------------------------ painel oficial (com senha)
# Usuario e senha ficam em variaveis de ambiente do Render: PAINEL_USUARIO e PAINEL_SENHA;
# com o repositorio privado, tambem PAINEL_GITHUB_TOKEN.
# Os dados vem do repositorio (docs/dados), buscados na hora com cache de 60 s: o painel fica
# atualizado sem precisar de novo deploy.
import hmac as _hmac
import json
from flask import Response

_PAINEL_RAW = "https://raw.githubusercontent.com/marinholuiz2015-tech/loteca-simulador/main/docs/"
# repositorio privado: com PAINEL_GITHUB_TOKEN (token so de leitura do conteudo deste repositorio)
# os arquivos vem pela API do GitHub
_PAINEL_API = "https://api.github.com/repos/marinholuiz2015-tech/loteca-simulador/contents/docs/"
_painel_cache = {}


def _painel_autorizado():
    usuario, senha = os.environ.get("PAINEL_USUARIO", "luiz"), os.environ.get("PAINEL_SENHA")
    a = request.authorization
    return bool(senha) and a is not None and _hmac.compare_digest(a.username or "", usuario) \
        and _hmac.compare_digest(a.password or "", senha)


def _painel_pedir_senha():
    if not os.environ.get("PAINEL_SENHA"):
        return Response("Painel sem senha configurada: defina PAINEL_SENHA nas variaveis de ambiente do Render.",
                        503, {"Content-Type": "text/plain; charset=utf-8"})
    return Response("Acesso restrito.", 401, {"WWW-Authenticate": 'Basic realm="Loteca Elite Pro"',
                                             "Content-Type": "text/plain; charset=utf-8"})


def _painel_arquivo(caminho, tipo):
    local = os.environ.get("PAINEL_LOCAL_DIR")  # desenvolvimento: le os arquivos de docs/ do disco
    if local:
        try:
            with open(os.path.join(local, caminho), "rb") as f:
                return Response(f.read(), 200, {"Content-Type": tipo, "Cache-Control": "no-store"})
        except OSError:
            return Response("Nao encontrado.", 404)
    agora = time.time()
    c = _painel_cache.get(caminho)
    if c and agora - c[0] < 60:
        return Response(c[1], 200, {"Content-Type": tipo, "Cache-Control": "no-store"})
    try:
        token = os.environ.get("PAINEL_GITHUB_TOKEN")
        if token:
            r = requests.get(_PAINEL_API + caminho, timeout=20, params={"ref": "main"},
                             headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github.raw"})
        else:
            r = requests.get(_PAINEL_RAW + caminho, timeout=20)
        r.raise_for_status()
        _painel_cache[caminho] = (agora, r.content)
        return Response(r.content, 200, {"Content-Type": tipo, "Cache-Control": "no-store"})
    except Exception:
        if c:
            return Response(c[1], 200, {"Content-Type": tipo, "Cache-Control": "no-store"})
        return Response("Dados indisponiveis no momento.", 502, {"Content-Type": "text/plain; charset=utf-8"})


_vivo_cache = {"t": 0, "dados": None}


def _placar_fotmob(match_id):
    d = requests.get("https://www.fotmob.com/api/data/matchDetails", params={"matchId": match_id}, timeout=12,
                     headers={"User-Agent": "Mozilla/5.0 (painel pessoal; consulta leve)"}).json()
    st = d.get("header", {}).get("status", {}); tm = d.get("header", {}).get("teams", [])
    if st.get("cancelled"):
        return {"situacao": "cancelado"}
    if not (st.get("started") and len(tm) == 2):
        return {"situacao": "não começou", "placar": None, "resultado": None}
    gc, gf = tm[0].get("score"), tm[1].get("score")
    curto = str((st.get("liveTime") or {}).get("short") or "")
    curto = "".join(ch for ch in curto if ch.isprintable() and ch not in "\u200e\u200f").strip()
    return {"placar": [gc, gf], "resultado": "1" if gc > gf else ("X" if gc == gf else "2"),
            "situacao": "encerrado" if st.get("finished") else ("ao vivo " + curto).strip()}


def _painel_ao_vivo():
    """Placar ao vivo: usa o arquivo do GitHub e, se ele estiver com mais de 4 min e houver jogo na janela,
    atualiza direto no FotMob (cache de 2 min). Se o FotMob falhar, fica o arquivo do GitHub."""
    import datetime as _dt
    base = _painel_arquivo("dados/ao_vivo.json", "application/json; charset=utf-8")
    if base.status_code != 200:
        return base
    agora = time.time()
    if _vivo_cache["dados"] and agora - _vivo_cache["t"] < 120:
        return Response(_vivo_cache["dados"], 200, {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"})
    try:
        d = json.loads(base.get_data())
        ag = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
        atual = _dt.datetime.strptime(d.get("atualizado_utc", "2000-01-01T00:00Z"), "%Y-%m-%dT%H:%MZ")
        if (ag - atual).total_seconds() < 240:
            return base
        mudou = False
        for g in d.get("jogos", []):
            if g.get("situacao") == "encerrado" or not g.get("match_id"):
                continue
            try:
                ini = _dt.datetime.strptime(g["inicio_utc"], "%Y-%m-%dT%H:%MZ")
            except Exception:
                continue
            if not (ini - _dt.timedelta(minutes=15) <= ag <= ini + _dt.timedelta(hours=3, minutes=30)):
                continue
            try:
                g.update(_placar_fotmob(g["match_id"])); mudou = True
            except Exception:
                pass
        if mudou:
            d["atualizado_utc"] = ag.strftime("%Y-%m-%dT%H:%MZ"); d["fonte"] = "painel (FotMob direto)"
        corpo = json.dumps(d, ensure_ascii=False).encode("utf-8")
        _vivo_cache.update(t=agora, dados=corpo)
        return Response(corpo, 200, {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"})
    except Exception:
        return base


@app.route("/painel")
def painel_raiz():
    return redirect("/painel/", code=302)  # redirect vem do bloco do painel


@app.route("/painel/")
def painel_pagina():
    if not _painel_autorizado():
        return _painel_pedir_senha()
    return _painel_arquivo("index.html", "text/html; charset=utf-8")


@app.route("/painel/dados/<nome>")
def painel_dados(nome):
    if not _painel_autorizado():
        return _painel_pedir_senha()
    if nome not in ("painel.json", "ao_vivo.json", "desdobre.csv", "pilares.json", "placar_pilares.json", "resultados.json"):
        return Response("Nao encontrado.", 404)
    if nome == "ao_vivo.json":
        return _painel_ao_vivo()
    tipo = "text/csv; charset=utf-8" if nome.endswith(".csv") else "application/json; charset=utf-8"
    return _painel_arquivo("dados/" + nome, tipo)


# ------------------------------------------------------------------ banca do painel (apostas registradas)
# As apostas ficam no proprio repositorio, no arquivo apostas/banca.json do ramo "banca" (fora do main,
# para nao disparar deploy a cada aposta). Precisa de PAINEL_GITHUB_ESCRITA no Render: token do GitHub
# (fine-grained) so deste repositorio, com permissao "Contents: Read and write".
# Desenvolvimento: PAINEL_BANCA_LOCAL=/caminho/banca.json grava num arquivo local.
import base64 as _b64
import uuid as _uuid

_BANCA_REPO = "https://api.github.com/repos/marinholuiz2015-tech/loteca-simulador"
_BANCA_RAMO = "banca"
_BANCA_ARQ = "apostas/banca.json"
_BANCA_STATUS = ("carrinho", "pago", "cancelado")


def _banca_hdr():
    return {"Authorization": "Bearer " + os.environ["PAINEL_GITHUB_ESCRITA"], "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _banca_garante_ramo():
    r = requests.get(_BANCA_REPO + "/git/ref/heads/" + _BANCA_RAMO, headers=_banca_hdr(), timeout=20)
    if r.status_code == 200:
        return
    m = requests.get(_BANCA_REPO + "/git/ref/heads/main", headers=_banca_hdr(), timeout=20)
    m.raise_for_status()
    c = requests.post(_BANCA_REPO + "/git/refs", headers=_banca_hdr(), timeout=20,
                      json={"ref": "refs/heads/" + _BANCA_RAMO, "sha": m.json()["object"]["sha"]})
    if c.status_code not in (201, 422):  # 422 = criado por outra chamada ao mesmo tempo
        c.raise_for_status()


def _banca_ler():
    """(dados, sha). sha None = arquivo ainda nao existe."""
    local = os.environ.get("PAINEL_BANCA_LOCAL")
    if local:
        try:
            with open(local, encoding="utf-8") as f:
                return json.load(f), "local"
        except FileNotFoundError:
            return {"apostas": []}, None
    if not os.environ.get("PAINEL_GITHUB_ESCRITA"):
        raise PermissionError("sem_chave")
    r = requests.get(_BANCA_REPO + "/contents/" + _BANCA_ARQ, headers=_banca_hdr(), params={"ref": _BANCA_RAMO}, timeout=20)
    if r.status_code == 404:
        return {"apostas": []}, None
    r.raise_for_status()
    j = r.json()
    return json.loads(_b64.b64decode(j["content"]).decode("utf-8")), j["sha"]


def _banca_gravar(dados, sha, msg):
    corpo = json.dumps(dados, ensure_ascii=False, indent=1)
    local = os.environ.get("PAINEL_BANCA_LOCAL")
    if local:
        with open(local, "w", encoding="utf-8") as f:
            f.write(corpo)
        return True
    _banca_garante_ramo()
    payload = {"message": msg, "branch": _BANCA_RAMO, "content": _b64.b64encode(corpo.encode("utf-8")).decode("ascii")}
    if sha:
        payload["sha"] = sha
    r = requests.put(_BANCA_REPO + "/contents/" + _BANCA_ARQ, headers=_banca_hdr(), json=payload, timeout=30)
    if r.status_code in (409, 422) and sha is not None:
        return False  # outra gravacao no meio: le de novo e refaz
    r.raise_for_status()
    return True


def _banca_vols(v):
    if not isinstance(v, list) or not 1 <= len(v) <= 2000:
        raise ValueError("volantes invalidos")
    out = []
    for vol in v:
        if not isinstance(vol, list) or len(vol) != 14:
            raise ValueError("cada volante precisa de 14 jogos")
        linha = []
        for t in vol:
            t = "".join(k for k in "1X2" if k in str(t).upper())
            if not t:
                raise ValueError("jogo sem marcacao")
            linha.append(t)
        out.append(linha)
    return out


def _banca_custo(vols):
    tot = 0
    for v in vols:
        n = 1
        for t in v:
            n *= len(t)
        tot += n * 2
    return tot


def _banca_aplica(dados, d):
    L = dados.setdefault("apostas", [])
    acao = d.get("acao")
    if acao == "adicionar":
        a = d.get("aposta") or {}
        vols = _banca_vols(a.get("vols"))
        conc = int(a.get("concurso"))
        minhas, total = max(1, int(a.get("minhas") or 1)), max(1, int(a.get("total") or 1))
        st = a.get("status") if a.get("status") in _BANCA_STATUS else "carrinho"
        agora = datetime.now(timezone.utc)
        nova = {"id": agora.strftime("%Y%m%d%H%M%S") + "-" + _uuid.uuid4().hex[:6], "concurso": conc,
                "registrado_utc": agora.strftime("%Y-%m-%dT%H:%MZ"), "origem": str(a.get("origem") or "")[:80],
                "vols": vols, "custo": _banca_custo(vols), "minhas": min(minhas, total), "total": total, "status": st}
        L.append(nova)
        return "Banca: aposta do concurso %d (R$ %d)" % (conc, nova["custo"]), nova
    if acao == "importar":
        chaves = {(x["concurso"], json.dumps(x["vols"])) for x in L}
        n = 0
        for a in (d.get("apostas") or [])[:200]:
            try:
                vols, conc = _banca_vols(a.get("vols")), int(a.get("concurso"))
            except (ValueError, TypeError):
                continue
            if (conc, json.dumps(vols)) in chaves:
                continue
            agora = datetime.now(timezone.utc)
            L.append({"id": agora.strftime("%Y%m%d%H%M%S") + "-" + _uuid.uuid4().hex[:6], "concurso": conc,
                      "registrado_utc": agora.strftime("%Y-%m-%dT%H:%MZ"), "origem": str(a.get("origem") or "importada")[:80],
                      "vols": vols, "custo": _banca_custo(vols), "minhas": max(1, int(a.get("minhas") or 1)),
                      "total": max(1, int(a.get("total") or 1)), "status": "pago"})
            chaves.add((conc, json.dumps(vols)))
            n += 1
        return "Banca: %d aposta(s) importada(s)" % n, n
    alvo = next((x for x in L if x.get("id") == d.get("id")), None)
    if alvo is None:
        raise KeyError("aposta nao encontrada")
    if acao == "status":
        if d.get("status") not in _BANCA_STATUS:
            raise ValueError("status invalido")
        alvo["status"] = d["status"]
        return "Banca: concurso %s marcado como %s" % (alvo["concurso"], d["status"]), alvo
    if acao == "apagar":
        L.remove(alvo)
        return "Banca: aposta do concurso %s apagada" % alvo["concurso"], None
    raise ValueError("acao desconhecida")


@app.route("/painel/api/banca", methods=["GET", "POST"])
def painel_banca():
    if not _painel_autorizado():
        return _painel_pedir_senha()
    try:
        if request.method == "GET":
            dados, _ = _banca_ler()
            return jsonify({"ok": True, "apostas": dados.get("apostas", [])})
        if not request.is_json:
            return jsonify({"ok": False, "erro": "envie JSON"}), 400
        d = request.get_json(silent=True) or {}
        for _ in range(3):
            dados, sha = _banca_ler()
            msg, item = _banca_aplica(dados, d)
            if _banca_gravar(dados, sha, msg):
                return jsonify({"ok": True, "item": item, "apostas": dados.get("apostas", [])})
        return jsonify({"ok": False, "erro": "conflito ao gravar; tente de novo"}), 409
    except PermissionError:
        return jsonify({"ok": False, "erro": "sem_chave"}), 503
    except (ValueError, KeyError, TypeError) as e:
        return jsonify({"ok": False, "erro": str(e)}), 400
    except Exception as e:
        logging.exception("banca")
        return jsonify({"ok": False, "erro": "falha ao falar com o GitHub: " + type(e).__name__}), 502



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
