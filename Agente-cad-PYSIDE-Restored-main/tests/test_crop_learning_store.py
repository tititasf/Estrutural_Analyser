import json
import sqlite3

from src.core.crop_learning_store import (
    ensure_crop_learning_schema,
    get_active_crop_examples,
    record_crop_learning_event,
    revoke_crop_learning_event,
    revoke_crop_learning_events_for_recorte,
)


def _create_reverse_tables(conn):
    conn.execute(
        """CREATE TABLE reverse_eng_recortes (
            id INTEGER PRIMARY KEY,
            obra_name TEXT NOT NULL,
            pavimento TEXT,
            elemento_id TEXT NOT NULL,
            recorte_path TEXT NOT NULL,
            bbox_json TEXT,
            entity_count INTEGER,
            projeto_id TEXT,
            classe TEXT,
            status TEXT,
            confidence REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE reverse_eng_fichas (
            id INTEGER PRIMARY KEY,
            obra_name TEXT NOT NULL,
            pavimento TEXT NOT NULL,
            classe TEXT NOT NULL,
            elemento_id TEXT NOT NULL,
            campos_json TEXT NOT NULL DEFAULT '{}',
            recorte_path TEXT,
            confianca REAL DEFAULT 0.0,
            status TEXT DEFAULT 'draft',
            aprovado_at DATETIME,
            rag_indexed INTEGER DEFAULT 0
        )"""
    )
    conn.commit()


def test_crop_learning_event_does_not_promote_f5(tmp_path):
    db_path = tmp_path / "project_data.vision"
    dxf_path = tmp_path / "crop_P101.dxf"
    dxf_path.write_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")

    conn = sqlite3.connect(db_path)
    _create_reverse_tables(conn)
    bbox = {"x0": 10, "y0": 20, "x1": 110, "y1": 220}
    conn.execute(
        """INSERT INTO reverse_eng_recortes
           (obra_name, pavimento, elemento_id, recorte_path, bbox_json,
            entity_count, projeto_id, classe, status, confidence)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            "Obra_TREINO_3",
            "13_PAV",
            "P101",
            str(dxf_path),
            json.dumps(bbox),
            42,
            "13_PAV",
            "PIL",
            "manual",
            91.0,
        ),
    )
    conn.execute(
        """INSERT INTO reverse_eng_fichas
           (obra_name, pavimento, classe, elemento_id, campos_json,
            recorte_path, confianca, status, rag_indexed)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            "Obra_TREINO_3",
            "13_PAV",
            "PIL",
            "P101",
            "{}",
            str(dxf_path),
            0.5,
            "draft",
            0,
        ),
    )
    conn.commit()
    conn.close()

    ensure_crop_learning_schema(db_path)
    event_id = record_crop_learning_event(
        obra_name="Obra_TREINO_3",
        pavimento="13_PAV",
        classe="PIL",
        elemento_id="P101",
        recorte_path=dxf_path,
        notes="human_reviewed_crop_approval",
        db_path=db_path,
    )

    conn = sqlite3.connect(db_path)
    crop = conn.execute(
        """SELECT status, classe, elemento_id, bbox_json, metadata_json
           FROM crop_learning_events WHERE id=?""",
        (event_id,),
    ).fetchone()
    ficha = conn.execute(
        """SELECT status, aprovado_at, rag_indexed
           FROM reverse_eng_fichas WHERE recorte_path=?""",
        (str(dxf_path),),
    ).fetchone()
    conn.close()

    assert crop[0] == "validated"
    assert crop[1] == "PIL"
    assert crop[2] == "P101"
    assert json.loads(crop[3]) == bbox
    assert json.loads(crop[4])["instrumentation_only"] is True
    assert ficha == ("draft", None, 0)


def test_crop_learning_revoke_excludes_active_examples(tmp_path):
    db_path = tmp_path / "project_data.vision"
    dxf_path = tmp_path / "crop_LV.dxf"
    dxf_path.write_text("0\nEOF\n", encoding="utf-8")

    event_id = record_crop_learning_event(
        obra_name="Obra_TREINO_3",
        pavimento="13_PAV",
        classe="LV",
        elemento_id="V301",
        recorte_path=dxf_path,
        db_path=db_path,
    )
    assert len(get_active_crop_examples("LV", db_path=db_path)) == 1

    assert revoke_crop_learning_event(
        event_id,
        reason="crop boundary was wrong",
        revoked_by="tester",
        db_path=db_path,
    )
    assert get_active_crop_examples("LV", db_path=db_path) == []


def test_crop_learning_revoke_by_recorte_preserves_audit_history(tmp_path):
    db_path = tmp_path / "project_data.vision"
    dxf_path = tmp_path / "crop_FV.dxf"
    dxf_path.write_text("0\nEOF\n", encoding="utf-8")

    event_id = record_crop_learning_event(
        obra_name="Obra_TREINO_3",
        pavimento="13_PAV",
        classe="FV",
        elemento_id="V301",
        recorte_path=dxf_path,
        db_path=db_path,
    )

    revoked = revoke_crop_learning_events_for_recorte(
        dxf_path,
        reason="human_deleted_or_invalidated_crop",
        revoked_by="human_ui",
        db_path=db_path,
    )

    assert revoked == 1
    assert get_active_crop_examples("FV", db_path=db_path) == []
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """SELECT status, revoked_by, revoked_reason
               FROM crop_learning_events WHERE id=?""",
            (event_id,),
        ).fetchone()
    assert row == (
        "revoked",
        "human_ui",
        "human_deleted_or_invalidated_crop",
    )
