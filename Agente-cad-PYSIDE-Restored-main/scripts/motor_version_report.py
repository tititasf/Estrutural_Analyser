#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.artifact_governance import motor_history


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Histórico versionado das execuções dos motores N3/N4."
    )
    parser.add_argument("--motor", help="Ex.: ROBOT_FV_N3_N4")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = motor_history(args.motor)[: max(args.limit, 0)]
    if args.json or args.output:
        text = json.dumps(rows, ensure_ascii=False, indent=2)
    else:
        lines = [
            "MOTOR | VERSÃO | MODO | STATUS | ESCOPO | ITEM | EFEITO | DATA"
        ]
        for row in rows:
            lines.append(
                " | ".join(
                    [
                        row["motor_id"],
                        row["version_id"],
                        row["mode"],
                        row["status"],
                        row["scope"] or "-",
                        row["item_id"] or "-",
                        row["effect"] or "-",
                        row["created_at"],
                    ]
                )
            )
        text = "\n".join(lines)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
