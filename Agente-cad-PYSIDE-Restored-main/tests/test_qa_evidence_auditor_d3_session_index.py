"""Testes do D3 (MASTERPLAN-MINIRAG-QA-N1.md): integração B1 no review.

Cobrem load_session_index_b1_context isoladamente — a peça nova. A prova de
regressão fim-a-fim (cmd_review com/sem --session-index, contagem de decisões
idêntica, citações corretamente anexadas) foi feita manualmente contra o DB
real do 13_PAV nesta mesma rodada (ver RELATORIO.md); aqui cobrimos os
caminhos de falha/degradação que não são seguros de reproduzir contra dados
de produção.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "arete"))

from scripts.arete.qa_evidence_auditor import load_session_index_b1_context  # noqa: E402
from qa_session_index import build_index  # noqa: E402


def test_missing_index_dir_degrades_without_raising(tmp_path: Path):
    context, status = load_session_index_b1_context(
        tmp_path / "nao_existe", ["LAJ", "PIL"])
    assert context == {"LAJ": [], "PIL": []}
    assert status["available"] is False
    assert status["error"] is not None


@pytest.fixture()
def fixture_db_with_session_index(tmp_path):
    """DB mínimo compatível com qa_session_index.build_index (schema real)."""
    db = tmp_path / "fixture.vision"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, work_name TEXT,
                               pavement_name TEXT, updated_at TEXT);
        CREATE TABLE slabs (
            id INTEGER PRIMARY KEY, project_id TEXT, name TEXT, area REAL,
            points_json TEXT, type TEXT, links_json TEXT,
            validated_fields_json TEXT, issues_json TEXT, is_validated INTEGER,
            id_item INTEGER, validated_link_classes_json TEXT,
            na_fields_json TEXT, na_link_classes_json TEXT, na_reasons_json TEXT,
            pkl_path TEXT, extra_data_json TEXT
        );
        CREATE TABLE pillars (
            id INTEGER PRIMARY KEY, project_id TEXT, name TEXT, type TEXT,
            area REAL, points_json TEXT, sides_data_json TEXT, links_json TEXT,
            conf_map_json TEXT, validated_fields_json TEXT, issues_json TEXT,
            is_validated INTEGER, id_item INTEGER,
            validated_link_classes_json TEXT, na_fields_json TEXT,
            na_link_classes_json TEXT, na_reasons_json TEXT, pkl_path TEXT,
            extra_data_json TEXT
        );
        CREATE TABLE beams (
            id INTEGER PRIMARY KEY, project_id TEXT, name TEXT, data_json TEXT,
            is_validated INTEGER, id_item INTEGER, sides_data_json TEXT,
            links_json TEXT, validated_fields_json TEXT, issues_json TEXT,
            validated_link_classes_json TEXT, na_fields_json TEXT,
            na_link_classes_json TEXT, na_reasons_json TEXT, pkl_path TEXT,
            seg_a_laje_inf TEXT, seg_b_laje_inf TEXT, laje_inf_enriched_at TEXT,
            laje_inf_algorithm_version TEXT
        );
        CREATE TABLE semantic_rag_kb (
            id INTEGER PRIMARY KEY, classe TEXT, regra_semantica TEXT,
            obra_contexto TEXT, confianca REAL, created_at TEXT, tier TEXT,
            field_id TEXT, familia TEXT, pavimento TEXT
        );
        """
    )
    con.execute("INSERT INTO projects VALUES ('proj-1','13_TEST','Obra_TEST',NULL,NULL)")
    con.execute(
        "INSERT INTO semantic_rag_kb (id, classe, regra_semantica, obra_contexto, "
        "created_at, tier) VALUES (1,'LAJ',?,'Obra_TEST','2026-01-01','T1')",
        (json.dumps({"text": "Regra de teste para D3"}),))
    con.commit()
    con.close()
    return db


def test_available_index_returns_b1_entries_tagged_and_logged(
        tmp_path, fixture_db_with_session_index):
    index_dir = tmp_path / "index"
    build_index("proj-1", index_dir, db_path=fixture_db_with_session_index)

    context, status = load_session_index_b1_context(index_dir, ["LAJ", "PIL"])
    assert status["available"] is True
    assert status["error"] is None
    assert context["LAJ"] and all(
        e["kind"] == "rag_semantic_context_b1" for e in context["LAJ"])
    assert context["PIL"] == []  # sem regra PIL no fixture


def test_stale_index_degrades_without_raising(tmp_path, fixture_db_with_session_index):
    index_dir = tmp_path / "index"
    build_index("proj-1", index_dir, db_path=fixture_db_with_session_index)

    con = sqlite3.connect(fixture_db_with_session_index)
    con.execute(
        "INSERT INTO semantic_rag_kb (id, classe, regra_semantica, created_at) "
        "VALUES (2,'LAJ',?,'2026-01-02')",
        (json.dumps({"text": "regra nova pós-build"}),))
    con.commit()
    con.close()

    context, status = load_session_index_b1_context(index_dir, ["LAJ"])
    assert context == {"LAJ": []}
    assert status["available"] is False
    assert "STALE" in status["error"]


def test_familia_field_tier_filters_are_forwarded(tmp_path, fixture_db_with_session_index):
    index_dir = tmp_path / "index"
    build_index("proj-1", index_dir, db_path=fixture_db_with_session_index)

    context, _ = load_session_index_b1_context(
        index_dir, ["LAJ"], tiers=["T2"])  # a única regra é T1
    assert context["LAJ"] == []

    context, _ = load_session_index_b1_context(index_dir, ["LAJ"], tiers=["T1"])
    assert len(context["LAJ"]) == 1
