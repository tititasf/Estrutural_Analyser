"""Backfill idempotente de eventos human_approved para recortes LAJ da ER."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.engrev_laj_recorte_learning_store import (  # noqa: E402
    DEFAULT_ENGREV_LAJ_RECORTE_LEARNING_DB_PATH,
    DEFAULT_PROJECT_DATA_DB_PATH,
    ensure_engrev_laj_recorte_learning_schema,
    file_sha256,
    infer_pavimento_from_path,
    record_engrev_laj_recorte_learning_event,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-db", default=str(DEFAULT_PROJECT_DATA_DB_PATH))
    parser.add_argument("--learning-db", default=str(DEFAULT_ENGREV_LAJ_RECORTE_LEARNING_DB_PATH))
    parser.add_argument("--obra", default=None)
    parser.add_argument("--pav", default=None)
    args = parser.parse_args()

    project_db_path = Path(args.project_db)
    learning_db_path = Path(args.learning_db)
    ensure_engrev_laj_recorte_learning_schema(learning_db_path)

    project_conn = sqlite3.connect(project_db_path)
    project_conn.row_factory = sqlite3.Row
    learning_conn = sqlite3.connect(learning_db_path)
    learning_conn.row_factory = sqlite3.Row
    rows = project_conn.execute(
        """SELECT obra_name, elemento_id, classe, recorte_path, status
           FROM reverse_eng_recortes
           WHERE classe='LAJ' AND status='aprovado'
           ORDER BY obra_name, elemento_id, recorte_path"""
    ).fetchall()

    created = 0
    skipped = 0
    missing = 0
    for row in rows:
        obra_name = row["obra_name"]
        recorte_path = row["recorte_path"]
        pavimento = infer_pavimento_from_path(recorte_path)
        if args.obra and obra_name != args.obra:
            continue
        if args.pav and pavimento != args.pav:
            continue

        digest = file_sha256(recorte_path)
        if not digest:
            missing += 1
            continue

        exists = learning_conn.execute(
            """SELECT id FROM engrev_laj_recorte_learning_events
               WHERE event_type='human_approved'
                 AND approved_recorte_path=?
                 AND approved_hash=?
               LIMIT 1""",
            (recorte_path, digest),
        ).fetchone()
        if exists:
            skipped += 1
            continue

        record_engrev_laj_recorte_learning_event(
            project_db_path,
            event_type="human_approved",
            obra_name=obra_name,
            pavimento=pavimento,
            classe="LAJ",
            elemento_id=row["elemento_id"],
            approved_recorte_path=recorte_path,
            notes="backfill_existing_human_approved",
            learning_db_path=learning_db_path,
            features_extra={
                "source": (
                    "scripts/engrev_laj_recorte_learning/"
                    "backfill_engrev_laj_recorte_approved_events.py"
                )
            },
        )
        created += 1

    project_conn.close()
    learning_conn.close()
    print(f"created={created} skipped={skipped} missing_file={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
