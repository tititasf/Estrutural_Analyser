import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import rag_context_service as svc


def test_format_rule_text_unwraps_json_payload():
    text = svc.format_rule_text(
        {
            "regra_semantica": json.dumps(
                {
                    "source_doc": "SEMANTICA-PILAR-NOVA.md",
                    "section": "grade_1",
                    "text": "# titulo\n\nRegra validada pelo dono.\nUsada pelo robo.",
                },
                ensure_ascii=False,
            )
        }
    )

    assert text.startswith("SEMANTICA-PILAR-NOVA.md :: grade_1")
    assert "Regra validada pelo dono" in text
    assert '{"source_doc"' not in text


def test_context_loads_semantic_rules_without_examples(tmp_path, monkeypatch):
    db_path = tmp_path / "project_data.vision"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE semantic_rag_kb (
                id INTEGER PRIMARY KEY,
                classe TEXT,
                regra_semantica TEXT,
                obra_contexto TEXT,
                confianca REAL,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO semantic_rag_kb
                (classe, regra_semantica, obra_contexto, confianca)
            VALUES ('PIL', 'grade_1 = comprimento + 22', 'domain', 1.0)
            """
        )
        conn.commit()

    monkeypatch.setattr(svc, "FAISS_DIR", tmp_path / "missing_faiss")
    ctx = svc.get_rag_context_for_item(
        classe="PL",
        item_id="P1",
        obra="Obra_X",
        pavimento="1_PAV",
        db_path=db_path,
        obras_root=tmp_path / "missing_obras",
    )

    assert ctx["classe"] == "PIL"
    assert ctx["rules"][0]["regra_semantica"] == "grade_1 = comprimento + 22"
    assert ctx["validated_examples"] == []
    assert ctx["local_context"] == []
    assert "T0 nao aparece" in svc.format_context_text(ctx)


def test_context_filters_examples_by_tier(tmp_path, monkeypatch):
    db_path = tmp_path / "project_data.vision"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE semantic_rag_kb (
                id INTEGER PRIMARY KEY,
                classe TEXT,
                regra_semantica TEXT,
                obra_contexto TEXT,
                confianca REAL,
                created_at TEXT
            )
            """
        )
        conn.commit()

    faiss_dir = tmp_path / "faiss"
    faiss_dir.mkdir()
    (faiss_dir / "pilares_meta.json").write_text(
        json.dumps(
            [
                {"id": "P1", "tipo": "pilar", "obra": "Obra_X", "tier": "T0", "text": "draft"},
                {"id": "P2", "tipo": "pilar", "obra": "Obra_X", "tier": "T1", "text": "validado"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "FAISS_DIR", faiss_dir)

    ctx = svc.get_rag_context_for_item(
        classe="PIL",
        item_id="P1",
        obra="Obra_X",
        db_path=db_path,
        obras_root=tmp_path / "missing_obras",
    )

    assert [ex["id"] for ex in ctx["validated_examples"]] == ["P2"]
