#!/usr/bin/env python3
"""Memória de erro tipada por família (cross-sessão, sem hardcode de item).

Append-only JSONL em scripts/arete/relatorios/qa_error_memory/errors.jsonl.
Campos: classe, familia, field_pattern, code, kind, message, project_id (contexto),
item (contexto, nunca chave de generalização), run_id, at.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = REPO / "scripts" / "arete" / "relatorios" / "qa_error_memory" / "errors.jsonl"
SCHEMA = "arete.qa_error_memory/v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def field_pattern(field_id: str) -> str:
    """Generaliza campo (remove índices de segmento/face numéricos)."""
    text = str(field_id or "")
    text = re.sub(r"seg_\d+", "seg_N", text)
    text = re.sub(r"p_s[A-H]_", "p_sF_", text)
    text = re.sub(r"_\d+_", "_N_", text)
    return text


def append_errors(
    findings: list[dict],
    *,
    ledger: Path = DEFAULT_LEDGER,
    run_id: str | None = None,
    project_id: str | None = None,
    classe: str | None = None,
) -> int:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with ledger.open("a", encoding="utf-8") as handle:
        for row in findings:
            entry = {
                "schema": SCHEMA,
                "at": utc_now(),
                "run_id": run_id or row.get("run_id"),
                "project_id": project_id or row.get("project_id"),
                "classe": (classe or row.get("classe") or "").upper(),
                "item": row.get("item"),  # contexto apenas
                "field_id": row.get("field_id"),
                "field_pattern": field_pattern(str(row.get("field_id") or "")),
                "code": row.get("code") or row.get("kind") or "unknown",
                "kind": row.get("kind") or "finding",
                "message": row.get("message") or row.get("reason") or "",
                "familia": row.get("familia") or _guess_family(str(row.get("field_id") or "")),
            }
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            written += 1
    return written


def _guess_family(field_id: str) -> str:
    f = field_id.lower()
    if "fundo" in f or f.startswith("viga_fundo"):
        return "fv_segments"
    if "abert" in f:
        return "openings"
    if f.startswith("viga_a_") or f.startswith("viga_b_") or f.startswith("lv_"):
        return "lv_side"
    if f.startswith("p_s") or "pilar" in f:
        return "pil_face"
    if "laje" in f:
        return "laj"
    return "other"


def load_entries(ledger: Path = DEFAULT_LEDGER) -> list[dict]:
    if not ledger.is_file():
        return []
    rows = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def recurrence_report(
    ledger: Path = DEFAULT_LEDGER,
    *,
    min_count: int = 2,
    classe: str | None = None,
) -> dict:
    rows = load_entries(ledger)
    if classe:
        rows = [r for r in rows if str(r.get("classe") or "").upper() == classe.upper()]
    key_counts: Counter = Counter()
    examples: dict[str, list] = defaultdict(list)
    for row in rows:
        key = f"{row.get('classe')}|{row.get('familia')}|{row.get('field_pattern')}|{row.get('code')}"
        key_counts[key] += 1
        if len(examples[key]) < 5:
            examples[key].append({
                "item": row.get("item"),
                "project_id": row.get("project_id"),
                "run_id": row.get("run_id"),
                "message": row.get("message"),
            })
    recurring = []
    for key, count in key_counts.most_common():
        if count < min_count:
            continue
        classe_k, familia, pattern, code = key.split("|", 3)
        recurring.append({
            "classe": classe_k,
            "familia": familia,
            "field_pattern": pattern,
            "code": code,
            "count": count,
            "examples": examples[key],
        })
    return {
        "schema": "arete.qa_error_recurrence/v1",
        "ledger": str(ledger),
        "total_entries": len(rows),
        "min_count": min_count,
        "recurring": recurring,
    }


def ingest_findings_file(path: Path, **kwargs) -> int:
    rows = []
    if path.suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("findings") or []
    return append_errors(rows, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="ingere achados de um dossiê/jsonl")
    ing.add_argument("--findings", type=Path, required=True)
    ing.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ing.add_argument("--run-id")
    ing.add_argument("--project-id")
    ing.add_argument("--classe")
    rec = sub.add_parser("recurrence", help="relatório de recorrência por família")
    rec.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    rec.add_argument("--min-count", type=int, default=2)
    rec.add_argument("--classe")
    rec.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.cmd == "ingest":
        n = ingest_findings_file(
            args.findings, ledger=args.ledger, run_id=args.run_id,
            project_id=args.project_id, classe=args.classe,
        )
        print(json.dumps({"written": n, "ledger": str(args.ledger)}, ensure_ascii=False))
        return 0
    report = recurrence_report(args.ledger, min_count=args.min_count, classe=args.classe)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
