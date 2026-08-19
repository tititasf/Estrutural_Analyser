#!/usr/bin/env python3
"""Exporta o corpus QA; por padrão somente amostras promovidas por curadoria."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from portal.db import connection
from portal.db import repository as repo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=connection.DEFAULT_DB_PATH)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--include-candidates", action="store_true")
    args = parser.parse_args()

    conn = connection.init_db(args.db)
    try:
        rows = conn.execute(
            "SELECT id FROM portal_qa_rounds ORDER BY criado_em,id"
        ).fetchall()
        records = []
        for row in rows:
            detail = repo.detalhe_qa_round(conn, row["id"])
            for item in detail["items"]:
                if not args.include_candidates and not item["training_eligible"]:
                    continue
                records.append({
                    "schema": "cad.qa_training_export/v1",
                    "round": {k: v for k, v in detail.items() if k != "items"},
                    "item": item,
                })
    finally:
        conn.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"records": len(records), "output": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
