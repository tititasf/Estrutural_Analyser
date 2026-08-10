"""Migração de colunas nativas de tier no semantic_rag_kb."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.arete.migrate_semantic_rag_tier_columns import backfill, ensure_columns
from scripts.arete.qa_rag_evidence import load_partitioned_rag


def test_ensure_columns_and_backfill_and_filter(tmp_path: Path):
    db = tmp_path / "rag.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE semantic_rag_kb ("
        "id INTEGER PRIMARY KEY, classe TEXT, regra_semantica TEXT, "
        "obra_contexto TEXT, confianca REAL)"
    )
    con.execute(
        "INSERT INTO semantic_rag_kb (classe, regra_semantica, obra_contexto, confianca) VALUES (?,?,?,?)",
        ("LAJ", json.dumps({"tier": "T1", "field_id": "laje_dim"}), "ctx", 1.0),
    )
    con.execute(
        "INSERT INTO semantic_rag_kb (classe, regra_semantica, obra_contexto, confianca) VALUES (?,?,?,?)",
        ("LAJ", json.dumps({"tier": "T3", "field_id": "hyp"}), "ctx", 0.2),
    )
    con.commit()

    added = ensure_columns(con)
    assert set(added) >= {"tier", "field_id"}
    stats = backfill(con, dry_run=False)
    assert stats["updated"] >= 2
    con.commit()

    row = con.execute("SELECT tier, field_id FROM semantic_rag_kb WHERE field_id='laje_dim'").fetchone()
    assert row[0] == "T1"
    assert row[1] == "laje_dim"

    only_t1 = load_partitioned_rag(con, ["LAJ"], tiers=["T1"])
    assert len(only_t1["LAJ"]) == 1
    assert only_t1["LAJ"][0]["tier"] == "T1"
    con.close()
