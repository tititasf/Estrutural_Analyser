import json
import sqlite3

from src.core.pillar_db_hydration import hydrate_pillar_lajes_from_db


def test_hydrates_headless_lajes_key(tmp_path):
    db = tmp_path / "test.vision"
    connection = sqlite3.connect(db)
    connection.execute(
        "create table pillars (project_id text, name text, extra_data_json text)"
    )
    connection.execute(
        "insert into pillars values (?, ?, ?)",
        ("prj", "P1", json.dumps({
            "lajes": [{"laje": "L1", "side": "A"}],
            "shape_type": "Em L",
        })),
    )
    connection.commit()
    connection.close()
    pillars = [{"name": "P1", "lajes": []}]

    assert hydrate_pillar_lajes_from_db(db, "prj", pillars) == 1
    assert pillars[0]["lajes"] == [{"laje": "L1", "side": "A"}]
    assert pillars[0]["shape_type"] == "Em L"
