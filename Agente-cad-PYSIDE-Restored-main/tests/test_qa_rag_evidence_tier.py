"""Filtro de tier via JSON embutido (schema legado sem coluna tier)."""
from __future__ import annotations

import json
import sqlite3

from scripts.arete.qa_rag_evidence import load_partitioned_rag, parse_tier_from_rule


def test_parse_tier_from_rule_json():
    assert parse_tier_from_rule(json.dumps({"tier": "T1", "field_id": "x"})) == "T1"
    assert parse_tier_from_rule("not-json") is None


def test_load_partitioned_rag_filters_tier_from_json(tmp_path):
    db = tmp_path / "rag.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE semantic_rag_kb "
        "(id INTEGER PRIMARY KEY, classe TEXT, regra_semantica TEXT, obra_contexto TEXT, confianca REAL)"
    )
    con.execute(
        "INSERT INTO semantic_rag_kb (classe, regra_semantica, obra_contexto, confianca) VALUES (?,?,?,?)",
        ("LAJ", json.dumps({"tier": "T1", "field_id": "laje_dim"}), "qa_groundtruth_t1:p1", 1.0),
    )
    con.execute(
        "INSERT INTO semantic_rag_kb (classe, regra_semantica, obra_contexto, confianca) VALUES (?,?,?,?)",
        ("LAJ", json.dumps({"tier": "T3", "field_id": "hypothesis"}), "ctx", 0.2),
    )
    con.commit()

    only_t1 = load_partitioned_rag(con, ["LAJ"], tiers=["T1"])
    assert len(only_t1["LAJ"]) == 1
    assert only_t1["LAJ"][0]["tier"] == "T1"

    try:
        load_partitioned_rag(con, ["LAJ"], tiers=["T2"], require_tier=True)
        raised = False
    except RuntimeError:
        raised = True
    assert raised
    con.close()
