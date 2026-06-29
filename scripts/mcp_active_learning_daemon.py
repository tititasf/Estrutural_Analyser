#!/usr/bin/env python3
"""Transforma edições T0 em propostas auditáveis, nunca em regras aprovadas."""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.mcp import db_bridge  # noqa: E402

DB_PATH = ROOT / "project_data.vision"
CANDIDATES_DIR = ROOT / "data" / "active_learning_candidates"


def _json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except (TypeError, json.JSONDecodeError):
        return fallback


def generate_learning_proposal(event: dict[str, Any]) -> dict[str, Any]:
    """Representa uma hipótese explicável derivada de uma edição humana."""
    before = _json_value(event.get("estado_anterior_json"), {})
    after = _json_value(event.get("estado_novo_json"), {})
    changed = _json_value(event.get("campos_alterados"), [])
    reason = str(event.get("user_reason") or "").strip()
    event_kind = str(event.get("event_kind") or "edit")
    phase = str(event.get("fase_editada") or "")

    if "CROP" in phase.upper() or "RECORTE" in phase.upper():
        proposal_type = "crop_adjustment_candidate"
    elif phase.upper().startswith(("N1", "SA")):
        proposal_type = "interpretation_candidate"
    elif "ROBO" in phase.upper() or phase.upper().startswith(("N3", "N4")):
        proposal_type = "robot_adjustment_candidate"
    else:
        proposal_type = "field_adjustment_candidate"

    explanation = (
        f"Edição observada em {event.get('classe')} {event.get('item_id')} "
        f"na fase {phase or '?'}; campos alterados: {', '.join(map(str, changed)) or 'não informados'}."
    )
    if reason:
        explanation += f" Motivo humano: {reason}"

    return {
        "schema_version": 1,
        "proposal_id": str(event["log_id"]),
        "source_event_id": str(event["log_id"]),
        "proposal_type": proposal_type,
        "status": "PROPOSED",
        "tier": "T0",
        "scope": "active_learning_candidate",
        "is_global_truth": False,
        "requires_human_approval": True,
        "obra": event.get("obra_id"),
        "classe": event.get("classe"),
        "item_id": event.get("item_id"),
        "fase": phase,
        "ui_context": event.get("ui_context"),
        "event_kind": event_kind,
        "changed_fields": changed,
        "before": before,
        "after": after,
        "human_reason": reason,
        "source_agent": event.get("source_agent") or "",
        "timestamp": event.get("timestamp"),
        "explanation": explanation,
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def run_once(
    *,
    db_path: str | Path = DB_PATH,
    candidates_dir: str | Path = CANDIDATES_DIR,
    limit: int = 100,
    worker_id: str | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path)
    candidates_dir = Path(candidates_dir)
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    events = db_bridge.claim_events_for_proposal(
        worker_id,
        limit=limit,
        db_path=db_path,
    )
    proposed = 0
    failed = 0
    for event in events:
        try:
            proposal = generate_learning_proposal(event)
            path = candidates_dir / f"proposal_{proposal['proposal_id']}.json"
            _write_json_atomic(path, proposal)
            db_bridge.mark_event_proposed(
                str(event["log_id"]),
                str(path),
                db_path=db_path,
            )
            proposed += 1
        except Exception as exc:
            db_bridge.mark_event_failed(
                str(event["log_id"]),
                str(exc),
                db_path=db_path,
            )
            failed += 1
    return {
        "status": "ok" if not failed else "partial",
        "worker_id": worker_id,
        "claimed": len(events),
        "proposed": proposed,
        "failed": failed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "promotion_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--candidates-dir", default=str(CANDIDATES_DIR))
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    result = run_once(
        db_path=args.db,
        candidates_dir=args.candidates_dir,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
