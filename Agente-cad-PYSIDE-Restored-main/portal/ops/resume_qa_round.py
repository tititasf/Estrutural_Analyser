"""Retoma com seguranca uma rodada QA interrompida.

Uso operacional:
  python portal/ops/resume_qa_round.py --db portal_data.db \
      --round-id UUID --reset-item V310
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--round-id", required=True)
    parser.add_argument("--reset-item", action="append", default=[])
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Mantem a rodada retomavel, mas impede o worker de seleciona-la.",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        round_row = conn.execute(
            "SELECT id, job_id, status FROM portal_qa_rounds WHERE id=?",
            (args.round_id,),
        ).fetchone()
        if round_row is None:
            raise SystemExit(f"rodada inexistente: {args.round_id}")

        known = {
            row["item_id"]
            for row in conn.execute(
                "SELECT item_id FROM portal_qa_items WHERE round_id=?",
                (args.round_id,),
            )
        }
        missing = sorted(set(args.reset_item) - known)
        if missing:
            raise SystemExit(f"itens ausentes na rodada: {', '.join(missing)}")

        if args.pause:
            with conn:
                conn.execute(
                    """UPDATE portal_qa_rounds
                       SET status='queued', iniciado_em=NULL, finalizado_em=NULL,
                           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                       WHERE id=?""",
                    (args.round_id,),
                )
                conn.execute(
                    """UPDATE portal_jobs
                       SET status='cancelado', finalizado_em=strftime('%Y-%m-%dT%H:%M:%SZ','now'),
                           erro_msg='pausado pelo operador',
                           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                       WHERE id=?""",
                    (round_row["job_id"],),
                )
            print(
                f"rodada={args.round_id} job={round_row['job_id']} status=paused"
            )
            return 0

        with conn:
            for item_id in args.reset_item:
                conn.execute(
                    """UPDATE portal_qa_items
                       SET status='queued', provider=NULL, model=NULL, verdict=NULL,
                           note=NULL, suggestion_json=NULL, prompt_text=NULL,
                           prompt_sha256=NULL, evidence_json=NULL,
                           adapter_version=NULL, decision_authority='PENDENTE',
                           training_eligible=0,
                           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                       WHERE round_id=? AND item_id=?""",
                    (args.round_id, item_id),
                )
            conn.execute(
                """UPDATE portal_qa_rounds
                   SET status='queued', iniciado_em=NULL, finalizado_em=NULL,
                       updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                   WHERE id=?""",
                (args.round_id,),
            )
            conn.execute(
                """UPDATE portal_jobs
                   SET status='na_fila', iniciado_em=NULL, finalizado_em=NULL,
                       erro_msg=NULL,
                       updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                   WHERE id=?""",
                (round_row["job_id"],),
            )

        counts = dict(
            conn.execute(
                """SELECT status, COUNT(*) AS total FROM portal_qa_items
                   WHERE round_id=? GROUP BY status""",
                (args.round_id,),
            ).fetchall()
        )
        print(
            f"rodada={args.round_id} job={round_row['job_id']} "
            f"status=queued itens={counts}"
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
