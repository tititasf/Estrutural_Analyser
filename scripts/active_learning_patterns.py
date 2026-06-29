#!/usr/bin/env python3
"""Agrupa evidências MCP em padrões T0 para investigação humana."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "project_data.vision"
OUTPUT_PATH = ROOT / "data" / "active_learning_patterns" / "patterns.json"


def _json_list(value: Any) -> list[str]:
    try:
        parsed = json.loads(str(value or "[]"))
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def analyze_patterns(
    *,
    db_path: str | Path = DB_PATH,
    output_path: str | Path = OUTPUT_PATH,
) -> dict[str, Any]:
    db_path = Path(db_path)
    output_path = Path(output_path)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    with sqlite3.connect(db_path, timeout=15.0) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT log_id, obra_id, classe, item_id, fase_editada,
                       campos_alterados, user_reason, status, tier
                FROM human_event_logs
                WHERE status IN ('PROPOSED','APPROVED','INDEXED')
                ORDER BY timestamp
                """
            )
        ]
    for row in rows:
        fields = _json_list(row.get("campos_alterados")) or ["<evento>"]
        for field in fields:
            groups[
                (
                    str(row.get("classe") or "?"),
                    str(row.get("fase_editada") or "?"),
                    field,
                )
            ].append(row)

    patterns = []
    for (classe, phase, field), evidence in sorted(groups.items()):
        works = sorted({str(row.get("obra_id") or "?") for row in evidence})
        items = sorted({str(row.get("item_id") or "?") for row in evidence})
        reasons = sorted({
            str(row.get("user_reason") or "").strip()
            for row in evidence
            if str(row.get("user_reason") or "").strip()
        })
        patterns.append(
            {
                "pattern_id": f"{classe}:{phase}:{field}",
                "classe": classe,
                "phase": phase,
                "field": field,
                "occurrences": len(evidence),
                "distinct_works": len(works),
                "works": works,
                "items": items[:50],
                "human_reasons": reasons[:20],
                "source_event_ids": [row["log_id"] for row in evidence],
                "tier": "T0",
                "status": "PATTERN_CANDIDATE",
                "is_global_truth": False,
                "requires_human_review": True,
                "suggested_investigation": (
                    f"Revisar a interpretação/geração de '{field}' em {classe} "
                    f"na fase {phase}; confirmar causa antes de alterar o motor."
                ),
            }
        )

    payload = {
        "schema_version": 1,
        "scope": "active_learning_pattern_candidates",
        "is_global_truth": False,
        "patterns": patterns,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, output_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()
    result = analyze_patterns(db_path=args.db, output_path=args.output)
    print(json.dumps({"status": "ok", "patterns": len(result["patterns"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
