import json
import sqlite3

import pytest

from src.core.engrev_laj_n1_interpretacao_learning_store import (
    EVENTS_TABLE,
    FEATURES_TABLE,
    ensure_engrev_laj_n1_interpretacao_learning_schema,
    record_engrev_laj_n1_interpretacao_event,
    record_human_laje_outline_validated,
)


def test_n1_laj_learning_store_is_separate_from_project_db(tmp_path):
    project_db = tmp_path / "project_data.vision"
    learning_db = tmp_path / "engrev_laj_n1_interpretacao_learning.vision"
    source = tmp_path / "estrutural_clean.dxf"
    source.write_text("0\nEOF\n", encoding="utf-8")

    sqlite3.connect(project_db).close()
    ensure_engrev_laj_n1_interpretacao_learning_schema(learning_db)
    event_id = record_engrev_laj_n1_interpretacao_event(
        event_type="engrev_assisted_generated",
        elemento_id="L327",
        analysis_mode="engrev_assisted",
        obra_name="Obra_TREINO_1",
        pavimento="13_PAV",
        source_dxf_path=source,
        features={
            "bbox_n1": [0, 0, 200, 100],
            "laje_outline_segs": [[0, 0], [200, 0], [200, 100], [0, 100]],
            "candidate_line_count": 6,
            "accepted_line_count": 4,
            "rejected_line_count": 2,
        },
        learning_db_path=learning_db,
    )

    assert event_id > 0
    conn = sqlite3.connect(learning_db)
    assert conn.execute(f"SELECT COUNT(*) FROM {EVENTS_TABLE}").fetchone()[0] == 1
    features_json = conn.execute(f"SELECT features_json FROM {FEATURES_TABLE}").fetchone()[0]
    conn.close()
    assert json.loads(features_json)["accepted_line_count"] == 4

    project_conn = sqlite3.connect(project_db)
    assert project_conn.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{EVENTS_TABLE}'"
    ).fetchone() is None
    project_conn.close()


def test_human_laje_outline_validated_event(tmp_path):
    learning_db = tmp_path / "engrev_laj_n1_interpretacao_learning.vision"
    event_id = record_human_laje_outline_validated(
        elemento_id="L308",
        obra_name="Obra_TREINO_1",
        pavimento="13_PAV",
        laje_outline_segs={"contour": [{"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}]},
        learning_db_path=learning_db,
    )
    conn = sqlite3.connect(learning_db)
    event_type, mode = conn.execute(
        f"SELECT event_type, analysis_mode FROM {EVENTS_TABLE} WHERE id=?",
        (event_id,),
    ).fetchone()
    conn.close()
    assert event_type == "human_laje_outline_validated"
    assert mode == "engrev_assisted"


def test_invalid_mode_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        record_engrev_laj_n1_interpretacao_event(
            event_type="baseline_generated",
            elemento_id="L1",
            analysis_mode="invalid",
            learning_db_path=tmp_path / "x.vision",
        )
