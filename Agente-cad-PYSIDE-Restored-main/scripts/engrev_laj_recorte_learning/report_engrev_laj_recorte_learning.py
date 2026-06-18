"""Relatorio do dataset de aprendizagem dos recortes LAJ da engenharia reversa."""

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
    infer_pavimento_from_path,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-db", default=str(DEFAULT_PROJECT_DATA_DB_PATH))
    parser.add_argument("--learning-db", default=str(DEFAULT_ENGREV_LAJ_RECORTE_LEARNING_DB_PATH))
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav", default=None)
    args = parser.parse_args()

    project_db_path = Path(args.project_db)
    learning_db_path = Path(args.learning_db)
    ensure_engrev_laj_recorte_learning_schema(learning_db_path)
    project_conn = sqlite3.connect(project_db_path)
    project_conn.row_factory = sqlite3.Row
    learning_conn = sqlite3.connect(learning_db_path)
    learning_conn.row_factory = sqlite3.Row

    recortes = project_conn.execute(
        """SELECT obra_name, elemento_id, recorte_path, status, confidence
           FROM reverse_eng_recortes
           WHERE classe='LAJ' AND obra_name=?
           ORDER BY elemento_id, status""",
        (args.obra,),
    ).fetchall()
    events = learning_conn.execute(
        """SELECT pavimento, event_type, COUNT(*) AS n
           FROM engrev_laj_recorte_learning_events
           WHERE classe='LAJ' AND obra_name=?
           GROUP BY pavimento, event_type
           ORDER BY pavimento, event_type""",
        (args.obra,),
    ).fetchall()

    by_status: dict[str, int] = {}
    by_pav_status: dict[tuple[str, str], int] = {}
    for row in recortes:
        pav = infer_pavimento_from_path(row["recorte_path"]) or ""
        if args.pav and pav != args.pav:
            continue
        status = row["status"] or ""
        by_status[status] = by_status.get(status, 0) + 1
        key = (pav, status)
        by_pav_status[key] = by_pav_status.get(key, 0) + 1

    print("Dataset: engrev_laj_recorte_learning")
    print(f"Obra: {args.obra}")
    if args.pav:
        print(f"Pavimento: {args.pav}")
    print("Recortes LAJ por status:")
    for status, n in sorted(by_status.items()):
        print(f"  {status or '(vazio)'}: {n}")

    print("\nRecortes LAJ por pavimento/status:")
    for (pav, status), n in sorted(by_pav_status.items()):
        print(f"  {pav or '?'} / {status or '(vazio)'}: {n}")

    print("\nEventos de aprendizagem ER LAJ:")
    for row in events:
        if args.pav and row["pavimento"] != args.pav:
            continue
        print(f"  {row['pavimento'] or '?'} / {row['event_type']}: {row['n']}")

    project_conn.close()
    learning_conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
