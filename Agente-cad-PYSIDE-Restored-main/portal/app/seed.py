"""CLI de admin do dono: cadastra membros no portal_data.db (HANDOFF §4).

O dono nao usa o portal (usa a app PySide6); ele cadastra os 3-5 membros por aqui.
Senha e' hasheada com bcrypt antes de gravar — nunca texto plano.

[2026-07-06] Criacao dinamica de pasta no Drive: se `--drive-folder-id` NAO for
passado, o script cria (ou acha, se ja existir — idempotente) uma subpasta com o
login do membro dentro da pasta-mae `Settings.drive_pasta_raiz_nome`
("Portal-Obras" por padrao) na raiz do PROPRIO Drive do dono — decisao do dono de
reusar a credencial OAuth existente (nao service account; ver drive_poller.py).
Se nenhuma credencial de Drive real existir ainda, cai no FakeDriveClient (pasta
local) sem quebrar — mesmo comportamento do poller.

Uso:
    python -m portal.app.seed --login joao --nome "Joao" --senha segredo
        # cria/acha Drive:/Portal-Obras/joao automaticamente
    python -m portal.app.seed --login joao --nome "Joao" --senha segredo \
        --drive-folder-id <folderId>   # usa um folder ID ja existente, sem criar
    python -m portal.app.seed --login joao --nome "Joao" --senha segredo --sem-drive
        # nao mexe no Drive (drive_folder_id fica NULL)
    python -m portal.app.seed --listar
"""

from __future__ import annotations

import argparse
import sys

from ..db import connection as db_conn
from ..db import repository as repo
from . import auth, drive_poller
from .config import load_settings


def _criar_pasta_drive(login: str) -> str | None:
    """Cria/acha Drive:/<raiz>/<login> — None se o Drive nao estiver disponivel."""
    settings = load_settings()
    cliente = drive_poller.montar_drive_client(settings)
    if isinstance(cliente, drive_poller.FakeDriveClient):
        print(
            "[aviso] nenhuma credencial de Drive real encontrada — pasta criada "
            "localmente (FakeDriveClient), nao no Google Drive de verdade.",
            file=sys.stderr,
        )
    try:
        raiz_id = cliente.obter_ou_criar_pasta(settings.drive_pasta_raiz_nome)
        return cliente.obter_ou_criar_pasta(login, pasta_pai_id=raiz_id)
    except Exception as exc:  # noqa: BLE001 - qualquer falha de rede/credencial vira mensagem clara
        # [2026-07-06] achado real: a credencial em portal/.secrets/gdrive-oauth.json
        # existe (nao cai no FakeDriveClient) mas pode estar com refresh_token
        # expirado/revogado — a excecao so' aparece na PRIMEIRA chamada de API real
        # (construir o client nao valida o token). Sem este catch, o comando quebra
        # com uma stack trace de 20 linhas do google-auth em vez de dizer o que fazer.
        print(
            f"[ERRO] nao foi possivel criar/achar a pasta no Drive real ({exc!r}).\n"
            "Se a credencial existe mas parece expirada/revogada, rode:\n"
            "    python portal/ops/reautorizar_drive.py\n"
            "e tente cadastrar o membro de novo.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Admin de membros do portal")
    ap.add_argument("--login")
    ap.add_argument("--nome")
    ap.add_argument("--senha")
    ap.add_argument("--email", default=None)
    ap.add_argument(
        "--drive-folder-id", default=None,
        help="usa um folder ID ja existente em vez de criar um novo",
    )
    ap.add_argument(
        "--sem-drive", action="store_true",
        help="nao cria/associa pasta no Drive (drive_folder_id fica NULL)",
    )
    ap.add_argument("--db", default=None, help="path do portal_data.db (default: raiz do repo)")
    ap.add_argument("--listar", action="store_true", help="lista membros e sai")
    args = ap.parse_args(argv)

    conn = db_conn.init_db(args.db)
    try:
        if args.listar:
            for m in repo.listar_membros(conn):
                print(f"{m['login']:<16} {m['papel']:<8} folder={m['drive_folder_id']}")
            return 0
        if not (args.login and args.nome and args.senha):
            ap.error("--login, --nome e --senha sao obrigatorios (ou use --listar)")
        if repo.obter_membro_por_login(conn, args.login):
            print(f"membro '{args.login}' ja existe", file=sys.stderr)
            return 1

        drive_folder_id = args.drive_folder_id
        if drive_folder_id is None and not args.sem_drive:
            drive_folder_id = _criar_pasta_drive(args.login)
            print(f"pasta do Drive pronta: {drive_folder_id}")

        membro_id = repo.criar_membro(
            conn, login=args.login, nome=args.nome,
            senha_hash=auth.hash_senha(args.senha), email=args.email,
            drive_folder_id=drive_folder_id,
        )
        print(f"membro criado: {args.login} (id={membro_id})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
