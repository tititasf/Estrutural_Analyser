"""Reautoriza a credencial OAuth do Drive usada pelo portal (rodar 1x, manual, com navegador).

Contexto: o portal reusa a credencial OAuth ja existente do DVC (decisao do dono,
2026-07-06) em vez de criar uma service account — ver `portal/app/drive_poller.py`
(GoogleDriveOAuthClient) e `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` §1-A/§11. O
`refresh_token` copiado do DVC veio EXPIRADO/REVOGADO (Google recusou com
`invalid_grant: Token has been expired or revoked` ao testar de verdade contra a
API) — comum quando o app OAuth no Google Cloud Console ainda esta em modo
"Testing" (refresh token expira em 7 dias). Este script pede consentimento de novo
no navegador e grava um refresh_token novo no MESMO arquivo que o portal ja le
(`portal/.secrets/gdrive-oauth.json`) — nenhum outro arquivo/config muda.

Uso (precisa de navegador — rodar na sua maquina, nao em servidor headless):
    python portal/ops/reautorizar_drive.py

O que o script faz, na ordem:
    1. Le client_id/client_secret do proprio portal/.secrets/gdrive-oauth.json
       (nao inventa credencial nova — reusa o MESMO app OAuth do DVC).
    2. Abre o navegador (InstalledAppFlow.run_local_server) pedindo consentimento
       de escopo 'drive' completo — access_type=offline + prompt=consent GARANTE
       que um refresh_token novo venha na resposta (sem isso o Google as vezes so
       devolve access_token, se ja houve consentimento antes).
    3. Grava o refresh_token novo (+ client_id/secret/token_uri/scopes) de volta em
       portal/.secrets/gdrive-oauth.json, sobrescrevendo o antigo.
    4. Valida de verdade: monta o GoogleDriveOAuthClient com a credencial recem-
       salva e lista arquivos da pasta raiz do DVC no Drive (leitura, nao escreve
       nada) — se funcionar, imprime confirmacao com o nome dos itens encontrados.

Escopo pedido: 'https://www.googleapis.com/auth/drive' (leitura+escrita) — precisa
de escrita porque o portal cria pasta por membro dinamicamente (ver
`portal/app/drive_poller.py::DriveClient.obter_ou_criar_pasta` e
`portal/app/seed.py`), nao so' ler arquivos.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CRED_PATH = REPO_ROOT / "portal" / ".secrets" / "gdrive-oauth.json"
_SCOPES = ["https://www.googleapis.com/auth/drive"]
_PASTA_DVC_TESTE = "16M5RO5VgTlPAAV9ZUFQ12Dg3J-PdubqE"  # mesma usada na validacao anterior


def main() -> int:
    if not CRED_PATH.exists():
        print(f"[ERRO] {CRED_PATH} nao existe — nao ha client_id/client_secret pra reusar.")
        print("Esse arquivo devia ter sido criado a partir da credencial do DVC. Abortando.")
        return 1

    dados_antigos = json.loads(CRED_PATH.read_text(encoding="utf-8"))
    client_id = dados_antigos.get("client_id")
    client_secret = dados_antigos.get("client_secret")
    if not client_id or not client_secret:
        print(f"[ERRO] {CRED_PATH} nao tem client_id/client_secret validos.")
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("[ERRO] google-auth-oauthlib nao instalado. Rode:")
        print("    python -m pip install google-auth-oauthlib")
        return 1

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    print("Abrindo o navegador para voce autorizar o app OAuth do DVC a acessar")
    print("o Drive (escopo 'drive' completo). Faca login com a conta que tem as")
    print("pastas das obras (thierry.tasf@gmail.com) e clique em Permitir.\n")

    flow = InstalledAppFlow.from_client_config(client_config, scopes=_SCOPES)
    # access_type=offline + prompt=consent GARANTEM refresh_token na resposta,
    # mesmo se essa conta ja tiver autorizado esse client_id antes.
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent",
    )

    if not creds.refresh_token:
        print("[ERRO] Google nao devolveu refresh_token. Revogue o acesso do app em")
        print("https://myaccount.google.com/permissions e rode este script de novo.")
        return 1

    novo = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": creds.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": _SCOPES,
    }
    tmp_path = CRED_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(novo, indent=2), encoding="utf-8")
    tmp_path.replace(CRED_PATH)  # escrita atomica — nunca deixa o arquivo pela metade
    print(f"\n[OK] refresh_token novo gravado em {CRED_PATH}")

    print("\nValidando contra o Drive real (lendo a pasta raiz do DVC, so leitura)...")
    sys.path.insert(0, str(REPO_ROOT))
    from portal.app.drive_poller import GoogleDriveOAuthClient  # noqa: E402

    cliente = GoogleDriveOAuthClient(CRED_PATH)
    arquivos = cliente.list_new_files(_PASTA_DVC_TESTE)
    print(f"[OK] CONEXAO REAL CONFIRMADA — {len(arquivos)} item(ns) na pasta:")
    for a in arquivos[:10]:
        print(f"  - {a.name}")
    print("\nPronto. O poller do portal ja pode usar essa credencial (PORTAL_POLL_ENABLED=true).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
