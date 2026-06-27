import json
import sqlite3

import src.ui.modules.diagnostic_reverse_hub as hub


def _make_db(path, *, status, rag_indexed, campos):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE reverse_eng_fichas (
                id INTEGER PRIMARY KEY,
                projeto_id TEXT,
                obra_name TEXT,
                pavimento TEXT,
                classe TEXT,
                elemento_id TEXT,
                campos_json TEXT,
                recorte_path TEXT,
                confianca REAL,
                status TEXT,
                aprovado_at TEXT,
                rag_indexed INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(obra_name, pavimento, classe, elemento_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO reverse_eng_fichas (
                projeto_id, obra_name, pavimento, classe, elemento_id,
                campos_json, recorte_path, confianca, status, rag_indexed
            ) VALUES ('PAV1','Obra_X','1_PAV','PIL','P1',?,?,?,?,?)
            """,
            (json.dumps(campos), "old.dxf", 0.9, status, rag_indexed),
        )


def _save(worker, db_path, monkeypatch):
    monkeypatch.setattr(hub, "DB_PATH", str(db_path))
    monkeypatch.setattr(hub, "ensure_db_backup", lambda _path: None)
    worker._salvar_ficha(
        obra_name="Obra_X",
        pavimento="1_PAV",
        classe="PIL",
        elemento_id="P1",
        campos_json=json.dumps({"comprimento": 999}),
        recorte_path="new.dxf",
        confianca=0.7,
        projeto_id="PAV1",
    )


def test_approved_f5_is_immutable_until_human_revokes(tmp_path, monkeypatch):
    db_path = tmp_path / "project_data.vision"
    _make_db(
        db_path,
        status="aprovado",
        rag_indexed=1,
        campos={"comprimento": 100},
    )
    worker = hub._FichaMotorWorker.__new__(hub._FichaMotorWorker)

    _save(worker, db_path, monkeypatch)

    with sqlite3.connect(db_path) as conn:
        campos, recorte, status, indexed = conn.execute(
            """
            SELECT campos_json, recorte_path, status, rag_indexed
            FROM reverse_eng_fichas
            """
        ).fetchone()
    assert json.loads(campos)["comprimento"] == 100
    assert recorte == "old.dxf"
    assert status == "aprovado"
    assert indexed == 1


def test_revoked_f5_can_be_reextracted_but_stays_revoked_and_unindexed(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "project_data.vision"
    _make_db(
        db_path,
        status="revoked",
        rag_indexed=1,
        campos={"comprimento": 100},
    )
    worker = hub._FichaMotorWorker.__new__(hub._FichaMotorWorker)

    _save(worker, db_path, monkeypatch)

    with sqlite3.connect(db_path) as conn:
        campos, recorte, status, indexed = conn.execute(
            """
            SELECT campos_json, recorte_path, status, rag_indexed
            FROM reverse_eng_fichas
            """
        ).fetchone()
    assert json.loads(campos)["comprimento"] == 999
    assert recorte == "new.dxf"
    assert status == "revoked"
    assert indexed == 0
