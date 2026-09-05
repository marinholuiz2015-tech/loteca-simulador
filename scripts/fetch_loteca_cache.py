"""
fetch_loteca_cache.py
Roda dentro do GitHub Actions (não no Render), busca o concurso atual/
próximo da Loteca direto na API da Caixa, e grava o resultado em
data/cef_cache.json -- pra ser lido depois via raw.githubusercontent.com
pelo app.py no Render, contornando o bloqueio 403 por IP de datacenter
confirmado em produção (04-05/09/2026, servicebus2.caixa.gov.br).

Achado de 05/09/2026: o endpoint específico por número
(.../api/loteca/{numero}) devolveu erro 500 (exceção interna do backend
da Caixa) ao buscar o concurso ainda ABERTO (1269), mesmo respondendo
200 normalmente pro endpoint geral (sem número). O endpoint geral, o de
número específico de concursos já FECHADOS, e as bibliotecas de
terceiros que existem publicamente usam exatamente o mesmo padrão de
URL -- não é erro de formato nosso, parece ser instabilidade real do
lado da Caixa especificamente pra concursos ainda em período de
apostas. Mitigado aqui com retry + backoff (prática padrão pra
depender de uma API de terceiro instável).

Nunca esconde falha: se a Caixa também bloquear o runner do GitHub
Actions, ou continuar instável após as tentativas, o campo "erro" fica
registrado no próprio cache, e o job termina com exit code != 0 --
fica visível na aba Actions do repo.
"""
import json
import os
import sys
import time
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

MAX_TENTATIVAS = 5
ESPERA_ENTRE_TENTATIVAS_SEG = 8


def buscar(numero="", tentativas=MAX_TENTATIVAS):
    """Retorna (status_code_ou_None, corpo, n_tentativas_usadas). Corpo é
    dict se JSON valido, string (truncada) se deu erro/HTML de bloqueio.
    Faz retry com espera fixa em erros 5xx (instabilidade do servidor da
    Caixa) -- não faz retry em 403 (bloqueio, não adianta insistir) nem
    em erros de rede (timeout já é generoso, insistir não ajuda muito)."""
    url = f"{URL_CEF}/{numero}" if numero else URL_CEF
    ultimo_status, ultimo_corpo = None, None
    for tentativa in range(1, tentativas + 1):
        try:
            r = requests.get(url, headers=HEADERS_NAVEGADOR, timeout=15)
            if r.status_code == 200:
                try:
                    return r.status_code, r.json(), tentativa
                except ValueError:
                    return r.status_code, r.text[:300], tentativa
            ultimo_status = r.status_code
            ultimo_corpo = r.text[:300]
            if r.status_code >= 500 and tentativa < tentativas:
                print(f"  tentativa {tentativa}/{tentativas}: status {r.status_code}, "
                      f"tentando de novo em {ESPERA_ENTRE_TENTATIVAS_SEG}s...")
                time.sleep(ESPERA_ENTRE_TENTATIVAS_SEG)
                continue
            return ultimo_status, ultimo_corpo, tentativa
        except Exception as e:
            ultimo_status, ultimo_corpo = None, str(e)
            if tentativa < tentativas:
                print(f"  tentativa {tentativa}/{tentativas}: excecao {e}, "
                      f"tentando de novo em {ESPERA_ENTRE_TENTATIVAS_SEG}s...")
                time.sleep(ESPERA_ENTRE_TENTATIVAS_SEG)
                continue
            return ultimo_status, ultimo_corpo, tentativa
    return ultimo_status, ultimo_corpo, tentativas


def main():
    out = {
        "fetched_em_utc": datetime.now(timezone.utc).isoformat(),
        "status_ultimo": None,
        "status_aberto": None,
        "dados_ultimo": None,
        "dados_aberto": None,
        "erro": None,
    }

    status_u, body_u, tent_u = buscar("")
    out["status_ultimo"] = status_u
    print(f"busca ultimo concurso: status={status_u} (tentativas={tent_u})")

    if status_u == 200 and isinstance(body_u, dict):
        out["dados_ultimo"] = body_u
        numero_proximo = body_u.get("numeroConcursoProximo")
        if numero_proximo:
            status_a, body_a, tent_a = buscar(str(numero_proximo))
            out["status_aberto"] = status_a
            print(f"busca concurso aberto ({numero_proximo}): status={status_a} (tentativas={tent_a})")
            if status_a == 200 and isinstance(body_a, dict):
                out["dados_aberto"] = body_a
            else:
                out["erro"] = (f"busca do concurso aberto ({numero_proximo}) falhou apos "
                                f"{tent_a} tentativa(s): status {status_a} -- {str(body_a)[:200]}")
    else:
        out["erro"] = f"busca do ultimo concurso falhou apos {tent_u} tentativa(s): status {status_u} -- {str(body_u)[:200]}"

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
