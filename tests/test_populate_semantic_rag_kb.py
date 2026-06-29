import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from populate_semantic_rag_kb import (  # noqa: E402
    BRIDGE_CONTEXT,
    apply_rows,
    build_rule_payload,
    infer_classes,
    records_to_bridge_rows,
)


def test_infer_classes_from_semantic_records():
    assert infer_classes({"source_doc": "SEMANTICA-PILAR-NOVA.md", "text": "grade_1 pilar"}) == ["PIL"]
    assert infer_classes({"source_doc": "SEMANTICA-LAJE-NOVA.md", "text": "laje contorno"}) == ["LAJ"]
    assert infer_classes({"source_doc": "SEMANTICA-VIGA-NOVA.md", "text": "viga generica"}) == ["LV", "FV"]
    assert infer_classes({"section": "Fundo da viga", "text": "fundo"}) == ["FV"]
    assert infer_classes({"section": "Lateral da viga", "text": "lateral"}) == ["LV"]
    assert infer_classes(
        {
            "source_doc": "SEMANTICA-PILAR-NOVA.md",
            "source_path": "D:/Agente-cad-PYSIDE/docs/SEMANTICA-PILAR-NOVA.md",
            "text": "pilar",
        }
    ) == ["PIL"]


def test_payload_is_json_and_keeps_source_text():
    payload = build_rule_payload(
        {
            "source_doc": "SEMANTICA-PILAR-NOVA.md",
            "doc_type": "field_semantics",
            "section": "grade_1",
            "text": "grade_1 = comprimento + 22",
            "sprint_validated": True,
        }
    )
    data = json.loads(payload)
    assert data["source"] == "domain_knowledge"
    assert data["source_doc"] == "SEMANTICA-PILAR-NOVA.md"
    assert data["section"] == "grade_1"
    assert "comprimento + 22" in data["text"]
    assert data["sprint_validated"] is True


def test_records_to_bridge_rows_only_uses_field_semantics():
    rows = records_to_bridge_rows(
        [
            {
                "source_doc": "SEMANTICA-PILAR-NOVA.md",
                "doc_type": "field_semantics",
                "section": "grade_1",
                "text": "grade_1 = comprimento + 22",
                "sprint_validated": True,
            },
            {
                "source_doc": "ROBOS_GUIDE.md",
                "doc_type": "robot_guide",
                "section": "desenho",
                "text": "nao entra no bridge de regras",
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0].classe == "PIL"
    assert rows[0].obra_contexto == BRIDGE_CONTEXT
    assert rows[0].confianca == 1.0


def test_apply_rows_is_idempotent_with_replace(tmp_path):
    db_path = tmp_path / "project_data.vision"
    rows = records_to_bridge_rows(
        [
            {
                "source_doc": "SEMANTICA-PILAR-NOVA.md",
                "doc_type": "field_semantics",
                "section": "grade_1",
                "text": "grade_1 = comprimento + 22",
                "sprint_validated": True,
            }
        ]
    )

    assert apply_rows(rows, db_path, replace=True) == 1
    assert apply_rows(rows, db_path, replace=True) == 1

    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM semantic_rag_kb WHERE obra_contexto=?",
            (BRIDGE_CONTEXT,),
        ).fetchone()[0]
    assert count == 1
