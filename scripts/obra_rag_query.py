#!/usr/bin/env python3
"""Consulta read-only ao snapshot RAG local de uma obra."""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")


def _tokens(value: Any) -> list[str]:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char)).lower()
    return [token for token in re.findall(r"[a-z0-9_]+", text) if len(token) > 1]


def _record_text(record: dict[str, Any]) -> str:
    values = [
        record.get("kind"),
        record.get("classe"),
        record.get("item_id"),
        record.get("pavimento"),
        record.get("title"),
        record.get("text"),
        record.get("path"),
        " ".join(record.get("field_keys") or []),
        json.dumps(record.get("preview") or {}, ensure_ascii=False, sort_keys=True),
    ]
    return " ".join(str(value or "") for value in values)


def _snapshot_records(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    obra_name = snapshot.get("obra_name")

    for row in snapshot.get("documents") or []:
        records.append(
            {
                "kind": "document",
                "title": row.get("name"),
                "text": f"{row.get('category') or ''} fase {row.get('phase') or ''}",
                "path": row.get("file_path"),
                "tier": "T0",
            }
        )

    for row in snapshot.get("reverse_fichas") or []:
        campos = row.get("campos") or {}
        records.append(
            {
                "kind": "reverse_ficha",
                "classe": row.get("classe"),
                "item_id": row.get("elemento_id"),
                "pavimento": row.get("pavimento"),
                "title": row.get("elemento_id"),
                "text": row.get("status"),
                "path": row.get("recorte_path"),
                "field_keys": campos.get("keys") or [],
                "preview": campos.get("preview") or {},
                "tier": row.get("tier") or "T0",
            }
        )

    for row in snapshot.get("semantic_rules") or []:
        rule = row.get("rule") or {}
        records.append(
            {
                "kind": "semantic_rule",
                "classe": row.get("classe"),
                "title": rule.get("section") or row.get("id"),
                "text": rule.get("text"),
                "path": rule.get("source_doc"),
                "tier": "T1",
            }
        )

    for row in snapshot.get("reverse_recortes") or []:
        records.append(
            {
                "kind": "reverse_recorte",
                "classe": row.get("classe"),
                "item_id": row.get("elemento_id"),
                "title": row.get("elemento_id"),
                "text": row.get("status"),
                "path": row.get("recorte_path"),
                "tier": "T1" if str(row.get("status") or "").lower() in {"aprovado", "approved"} else "T0",
            }
        )

    for record in records:
        record["obra_name"] = obra_name
        record["scope"] = "obra_local"
        record["is_global_truth"] = False
        record["promotion_policy"] = "never_auto_global"
    return records


def query_local_snapshot(
    obra_name: str,
    query: str,
    *,
    limit: int = 8,
    obras_root: str | Path = DEFAULT_OBRAS_ROOT,
) -> list[dict[str, Any]]:
    manifest_path = Path(obras_root) / obra_name / "obra_rag" / "manifest.json"
    if not manifest_path.exists():
        return []
    try:
        snapshot = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if snapshot.get("scope") != "obra_local" or snapshot.get("obra_name") != obra_name:
        return []

    records = _snapshot_records(snapshot)
    query_terms = Counter(_tokens(query))
    if not query_terms:
        return []

    document_frequency: Counter[str] = Counter()
    tokenized: list[Counter[str]] = []
    for record in records:
        terms = Counter(_tokens(_record_text(record)))
        tokenized.append(terms)
        document_frequency.update(terms.keys())

    scored: list[tuple[float, dict[str, Any]]] = []
    total = max(len(records), 1)
    for record, terms in zip(records, tokenized):
        score = 0.0
        for term, query_count in query_terms.items():
            if term not in terms:
                continue
            inverse_frequency = math.log((total + 1) / (document_frequency[term] + 1)) + 1.0
            score += min(terms[term], 3) * query_count * inverse_frequency
        if score <= 0:
            continue
        result = dict(record)
        result["score"] = round(score, 6)
        scored.append((score, result))

    scored.sort(
        key=lambda pair: (
            -pair[0],
            0 if pair[1].get("tier") in {"T1", "T2"} else 1,
            str(pair[1].get("kind") or ""),
            str(pair[1].get("title") or ""),
        )
    )
    return [record for _, record in scored[: max(int(limit), 0)]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("obra")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--obras-root", default=str(DEFAULT_OBRAS_ROOT))
    args = parser.parse_args()
    results = query_local_snapshot(
        args.obra,
        args.query,
        limit=args.limit,
        obras_root=args.obras_root,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
