"""
fetch_loteca_cache.py
Roda dentro do GitHub Actions (não no Render), busca o concurso atual/
próximo da Loteca direto na API da Caixa, e grava o resultado em
data/cef_cache.json -- pra ser lido depois via raw.githubusercontent.com
pelo app.py no Render, contornando o bloqueio 403 por IP de datacenter
confirmado em produção (04-05/09/2026, servicebus2.caixa.gov.br).

Nunca esconde falha: se a Caixa também bloquear o runner do GitHub
Actions, o campo "erro" fica registrado no próprio cache, e o job
termina com exit code != 0 -- fica visível na aba Actions do repo.
"""
import json
import os
import sys
from datetime import datetime, timezone

import requests

URL_CEF = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca"

HEADERS_NAVEGADOR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://loterias.caixa.gov.br/Paginas/Programacao-Loteca.aspx",
    "Origin": "https://loterias.caixa.gov.br",
}


def buscar(numero=""):
    """Retorna (status_code_ou_None, corpo). Corpo é dict se JSON valido,
    string (truncada) se deu erro/HTML de bloqueio."""
    url = f"{URL_CEF}/{numero}" if numero else URL_CEF
    try:
        r = requests.get(url, headers=HEADERS_NAVEGADOR, timeout=15)
        if r.status_code == 200:
            try:
                return r.status_code, r.json()
            except ValueError:
                return r.status_code, r.text[:300]
        return r.status_code, r.text[:300]
    except Exception as e:
        return None, str(e)


def main():
    out = {
        "fetched_em_utc": datetime.now(timezone.utc).isoformat(),
        "status_ultimo": None,
        "status_aberto": None,
        "dados_ultimo": None,
        "dados_aberto": None,
        "erro": None,
    }

    status_u, body_u = buscar("")
    out["status_ultimo"] = status_u

    if status_u == 200 and isinstance(body_u, dict):
        out["dados_ultimo"] = body_u
        numero_proximo = body_u.get("numeroConcursoProximo")
        if numero_proximo:
            status_a, body_a = buscar(str(numero_proximo))
            out["status_aberto"] = status_a
            if status_a == 200 and isinstance(body_a, dict):
                out["dados_aberto"] = body_a
            else:
                out["erro"] = f"busca do concurso aberto ({numero_proximo}) falhou: status {status_a} -- {str(body_a)[:200]}"
    else:
        out["erro"] = f"busca do ultimo concurso falhou: status {status_u} -- {str(body_u)[:200]}"

    os.makedirs("data", exist_ok=True)
    with open("data/cef_cache.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"status_ultimo={status_u} status_aberto={out['status_aberto']} erro={out['erro']}")

    # sai com erro se a busca principal falhou -- fica visivel na aba
    # Actions do GitHub (job aparece vermelho), mesmo o cache tendo sido
    # gravado com o erro registrado
    if status_u != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
