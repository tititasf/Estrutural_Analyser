#!/usr/bin/env python3
"""Enfileira uma rodada QA persistente sem depender da interface web."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from portal.app import pipeline_runner
from portal.db import connection
from portal.db import repository as repo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--obra", help="nome exato da obra no portal")
    parser.add_argument("--items", nargs="+")
    parser.add_argument("--listar-obras", action="store_true")
    parser.add_argument("--pavimento", default="13_PAV")
    parser.add_argument("--layer", choices=("L1", "L2", "L3"), default="L1")
    parser.add_argument("--db", type=Path, default=connection.DEFAULT_DB_PATH)
    args = parser.parse_args()

    conn = connection.init_db(args.db)
    if args.listar_obras:
        try:
            rows = conn.execute(
                "SELECT id,nome,membro_id,estado,local_path FROM portal_obras "
                "ORDER BY created_at DESC"
            ).fetchall()
            print(json.dumps([dict(row) for row in rows], ensure_ascii=False))
        finally:
            conn.close()
        return 0
    if not args.obra or not args.items:
        parser.error("--obra e --items sao obrigatorios para enfileirar")
    items = list(dict.fromkeys(item.strip().upper() for item in args.items if item.strip()))
    if not items or any(not item.startswith("P") or not item[1:].isdigit() for item in items):
        parser.error("--items deve conter identificadores PIL como P9 P10")

    try:
        obras = conn.execute(
            "SELECT * FROM portal_obras WHERE nome=? ORDER BY created_at DESC", (args.obra,)
        ).fetchall()
        if not obras:
            parser.error(f"obra nao encontrada no portal: {args.obra}")
        obra = dict(obras[0])
        round_id, job_id = repo.enfileirar_qa_round(
            conn,
            obra_id=obra["id"],
            membro_id=obra["membro_id"],
            classe="PIL",
            pavimento=args.pavimento,
            layer=args.layer,
            items=items,
            engine_version=pipeline_runner.engine_version(REPO_ROOT),
        )
        print(
            json.dumps(
                {
                    "round_id": round_id,
                    "job_id": job_id,
                    "obra_id": obra["id"],
                    "items": items,
                    "layer": args.layer,
                }
            )
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
