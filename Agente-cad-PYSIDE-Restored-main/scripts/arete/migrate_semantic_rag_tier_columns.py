#!/usr/bin/env python3
"""Migra semantic_rag_kb para colunas nativas de tier/field/familia/pavimento.

Idempotente e não destrutiva:
- ADD COLUMN se ausente
- backfill a partir do JSON em regra_semantica / obra_contexto
- não apaga regra_semantica

Uso:
  python scripts/arete/migrate_semantic_rag_tier_columns.py --db D:/Agente-cad-PYSIDE/project_data.vision --dry-run
  python scripts/arete/migrate_semantic_rag_tier_columns.py --db D:/Agente-cad-PYSIDE/project_data.vision --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path as _P
_REPO = _P(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import json
import sqlite3
from pathlib import Path

from scripts.arete.qa_rag_evidence import parse_field_from_rule, parse_tier_from_rule

COLUMNS = {
    "tier": "TEXT",
    "field_id": "TEXT",
    "familia": "TEXT",
    "pavimento": "TEXT",
}


def ensure_columns(con: sqlite3.Connection) -> list[str]:
    existing = {row[1] for row in con.execute("PRAGMA table_info(semantic_rag_kb)")}
    added: list[str] = []
    for name, decl in COLUMNS.items():
        if name not in existing:
            con.execute(f"ALTER TABLE semantic_rag_kb ADD COLUMN {name} {decl}")
            added.append(name)
    return added


def _family_from_rule(regra: object) -> str | None:
    if isinstance(regra, dict):
        for key in ("familia", "family", "subclasse"):
            if regra.get(key):
                return str(regra[key])
        return None
    try:
        data = json.loads(str(regra or ""))
    except (TypeError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        for key in ("familia", "family", "subclasse"):
            if data.get(key):
                return str(data[key])
    return None


def backfill(con: sqlite3.Connection, *, dry_run: bool) -> dict:
    rows = con.execute(
        "SELECT id, regra_semantica, obra_contexto, tier, field_id, familia, pavimento "
        "FROM semantic_rag_kb"
    ).fetchall()
    updated = 0
    skipped = 0
    for row in rows:
        rid, regra, obra, tier, field_id, familia, pav = row
        new_tier = (tier or parse_tier_from_rule(regra) or "").upper() or None
        # domain_knowledge sem tier explícito permanece NULL (consultivo T-unknown)
        new_field = field_id or parse_field_from_rule(regra)
        new_fam = familia or _family_from_rule(regra)
        new_pav = pav
        if not new_pav and isinstance(obra, str) and "pav" in obra.lower():
            new_pav = obra
        if (tier, field_id, familia, pav) == (new_tier, new_field, new_fam, new_pav):
            skipped += 1
            continue
        updated += 1
        if not dry_run:
            con.execute(
                "UPDATE semantic_rag_kb SET tier=?, field_id=?, familia=?, pavimento=? WHERE id=?",
                (new_tier, new_field, new_fam, new_pav, rid),
            )
    return {"rows": len(rows), "updated": updated, "unchanged": skipped, "dry_run": dry_run}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dry = not args.apply or args.dry_run
    con = sqlite3.connect(str(args.db))
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "semantic_rag_kb" not in tables:
            raise SystemExit("tabela semantic_rag_kb ausente")
        if dry:
            # dry-run ainda pode ADD COLUMN? não — só reporta o que faria
            existing = {row[1] for row in con.execute("PRAGMA table_info(semantic_rag_kb)")}
            missing = [c for c in COLUMNS if c not in existing]
            # simula backfill em memória se colunas existem
            if not missing:
                stats = backfill(con, dry_run=True)
            else:
                stats = {"rows": con.execute("SELECT COUNT(*) FROM semantic_rag_kb").fetchone()[0],
                         "updated": "n/a until columns added", "missing_columns": missing, "dry_run": True}
            print(json.dumps({"mode": "dry-run", "missing_columns": missing, "backfill": stats}, ensure_ascii=False, indent=2))
            return 0
        added = ensure_columns(con)
        stats = backfill(con, dry_run=False)
        con.commit()
        print(json.dumps({"mode": "apply", "added_columns": added, "backfill": stats}, ensure_ascii=False, indent=2))
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
