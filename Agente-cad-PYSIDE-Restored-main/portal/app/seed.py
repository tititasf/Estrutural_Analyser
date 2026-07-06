"""CLI de admin do dono: cadastra membros no portal_data.db (HANDOFF §4).

O dono nao usa o portal (usa a app PySide6); ele cadastra os 3-5 membros por aqui.
Senha e' hasheada com bcrypt antes de gravar — nunca texto plano.

Uso:
    python -m portal.app.seed --login joao --nome "Joao" --senha segredo \
        --drive-folder-id <folderId>
    python -m portal.app.seed --listar
"""

from __future__ import annotations

import argparse
import sys

from ..db import connection as db_conn
from ..db import repository as repo
from . import auth


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Admin de membros do portal")
    ap.add_argument("--login")
    ap.add_argument("--nome")
    ap.add_argument("--senha")
    ap.add_argument("--email", default=None)
    ap.add_argument("--drive-folder-id", default=None)
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
        membro_id = repo.criar_membro(
            conn, login=args.login, nome=args.nome,
            senha_hash=auth.hash_senha(args.senha), email=args.email,
            drive_folder_id=args.drive_folder_id,
        )
        print(f"membro criado: {args.login} (id={membro_id})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
