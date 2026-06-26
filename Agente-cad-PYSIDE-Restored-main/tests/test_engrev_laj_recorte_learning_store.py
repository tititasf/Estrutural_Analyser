import json
import sqlite3

from src.core.engrev_laj_recorte_learning_store import (
    ensure_engrev_laj_recorte_learning_schema,
    file_sha256,
    record_engrev_laj_recorte_learning_event,
)


def _create_recortes_table(conn):
    conn.execute(
        """CREATE TABLE reverse_eng_recortes (
            id INTEGER PRIMARY KEY,
            obra_name TEXT NOT NULL,
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
    conn.commit()


def test_record_engrev_laj_recorte_learning_events(tmp_path):
    project_db_path = tmp_path / "project_data.vision"
    learning_db_path = tmp_path / "engrev_laj_recorte_learning.vision"
    dxf_path = tmp_path / "Obra_TREINO_1" / "13_PAV" / "LAJ_L301_motor.dxf"
    dxf_path.parent.mkdir(parents=True)
    dxf_path.write_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")

    conn = sqlite3.connect(project_db_path)
    _create_recortes_table(conn)
    conn.execute(
        """INSERT INTO reverse_eng_recortes
           (obra_name, elemento_id, recorte_path, bbox_json, entity_count,
            projeto_id, classe, status, confidence)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            "Obra_TREINO_1",
            "L301",
            str(dxf_path),
            json.dumps({"x0": 1, "y0": 2, "x1": 30, "y1": 40}),
            123,
            "13_PAV",
            "LAJ",
            "motor",
            88.5,
        ),
    )
    conn.commit()
    conn.close()

    ensure_engrev_laj_recorte_learning_schema(learning_db_path)
    motor_event_id = record_engrev_laj_recorte_learning_event(
        project_db_path,
        event_type="motor_generated",
        obra_name="Obra_TREINO_1",
        pavimento="13_PAV",
        classe="LAJ",
        elemento_id="L301",
        source_recorte_path=dxf_path,
        learning_db_path=learning_db_path,
    )
    approved_event_id = record_engrev_laj_recorte_learning_event(
        project_db_path,
        event_type="human_approved",
        obra_name="Obra_TREINO_1",
        pavimento="13_PAV",
        classe="LAJ",
        elemento_id="L301",
        approved_recorte_path=dxf_path,
        learning_db_path=learning_db_path,
    )

    assert motor_event_id != approved_event_id

    conn = sqlite3.connect(learning_db_path)
    events = conn.execute(
        """SELECT event_type, source_hash, approved_hash
           FROM engrev_laj_recorte_learning_events
           ORDER BY id"""
    ).fetchall()
    features = conn.execute(
        """SELECT bbox_motor_json, bbox_aprovado_json, entity_count_motor,
                  entity_count_aprovado, confidence_before, confidence_after,
                  features_json
           FROM engrev_laj_recorte_learning_features ORDER BY id"""
    ).fetchall()
    conn.close()

    project_conn = sqlite3.connect(project_db_path)
    assert project_conn.execute(
        """SELECT name FROM sqlite_master
           WHERE type='table' AND name='engrev_laj_recorte_learning_events'"""
    ).fetchone() is None
    project_conn.close()

    expected_hash = file_sha256(dxf_path)
    assert events == [
        ("motor_generated", expected_hash, None),
        ("human_approved", None, expected_hash),
    ]
    assert json.loads(features[0][0]) == {"x0": 1, "y0": 2, "x1": 30, "y1": 40}
    assert features[0][1] is None
    assert features[0][2] == 123
    assert features[0][3] is None
    assert features[0][4] == 88.5
    assert features[1][0] is None
    assert json.loads(features[1][1]) == {"x0": 1, "y0": 2, "x1": 30, "y1": 40}
    assert features[1][2] is None
    assert features[1][3] == 123
    assert features[1][5] == 88.5
    assert json.loads(features[1][6])["instrumentation_only"] is True
