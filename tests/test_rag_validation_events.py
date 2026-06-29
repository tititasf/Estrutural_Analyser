import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rag_validation_events import (
    record_comparison_human_validation,
    record_reverse_hub_approval,
    record_reverse_hub_revocation,
)


def _write_valid_dxf(path: Path) -> None:
    import ezdxf

    doc = ezdxf.new("R2010")
    modelspace = doc.modelspace()
    modelspace.add_line((0, 0), (100, 50), dxfattribs={"layer": "FORMA"})
    modelspace.add_text("P1", dxfattribs={"height": 5, "layer": "TEXTO"}).set_placement(
        (10, 10)
    )
    doc.saveas(path)


def _make_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE training_events (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                type TEXT,
                role TEXT,
                context_dna_json TEXT,
                target_value TEXT,
                status TEXT,
                timestamp TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE reverse_eng_fichas (
                id INTEGER PRIMARY KEY,
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
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO reverse_eng_fichas
                (id, obra_name, pavimento, classe, elemento_id, campos_json,
                 recorte_path, confianca, status, rag_indexed)
            VALUES
                (1, 'Obra_X', '1_PAV', 'PIL', 'P1', '{"comprimento": 10}',
                 'recorte.dxf', 0.9, 'draft', 0)
            """
        )
        conn.commit()


def test_reverse_hub_approval_promotes_existing_ficha_without_indexing(tmp_path):
    db_path = tmp_path / "project_data.vision"
    _make_db(db_path)

    result = record_reverse_hub_approval(
        obra_name="Obra_X",
        classe="PIL",
        elemento_id="P1",
        recorte_path="recorte.dxf",
        db_path=db_path,
        auto_index=False,
        validation_origin="human_ui",
    )

    assert result["status"] == "promoted_t1"
    assert result["ficha_id"] == 1
    assert result["indexed"] == 0

    with sqlite3.connect(db_path) as conn:
        status, aprovado_at = conn.execute(
            "SELECT status, aprovado_at FROM reverse_eng_fichas WHERE id=1"
        ).fetchone()
        event_type, event_status = conn.execute(
            "SELECT type, status FROM training_events"
        ).fetchone()

    assert status == "aprovado"
    assert aprovado_at
    assert event_type == "rag_reverse_hub_human_approved"
    assert event_status == "validated"


def test_reverse_hub_approval_without_ficha_records_event_only(tmp_path):
    db_path = tmp_path / "project_data.vision"
    _make_db(db_path)

    result = record_reverse_hub_approval(
        obra_name="Obra_X",
        classe="PIL",
        elemento_id="P404",
        recorte_path="missing.dxf",
        db_path=db_path,
        auto_index=False,
        validation_origin="human_ui",
    )

    assert result["status"] == "event_only"
    assert result["ficha_id"] is None

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM training_events").fetchone()[0] == 1


def test_comparison_human_validation_records_event(tmp_path):
    db_path = tmp_path / "project_data.vision"
    _make_db(db_path)

    result = record_comparison_human_validation(
        obra_name="Obra_X",
        pavimento="1_PAV",
        classe="PIL",
        item_id="P1",
        scope="N3",
        human_validated=True,
        db_path=db_path,
        validation_origin="human_ui",
    )

    assert result["event_id"]
    assert result["revoked"] is False

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT type, role, status, context_dna_json FROM training_events"
        ).fetchone()

    assert row[0] == "rag_comparison_human_validated"
    assert row[1] == "N3"
    assert row[2] == "validated"
    assert json.loads(row[3])["source_id"] == "comparison_engine:Obra_X:1_PAV:PIL:P1:N3"


def test_comparison_validation_materializes_versioned_artifact(tmp_path):
    db_path = tmp_path / "project_data.vision"
    artifact = tmp_path / "P1_N3.dxf"
    _write_valid_dxf(artifact)
    _make_db(db_path)

    result = record_comparison_human_validation(
        obra_name="Obra_X",
        pavimento="1_PAV",
        classe="PIL",
        item_id="P1",
        scope="N3",
        human_validated=True,
        db_path=db_path,
        validation_origin="human_ui",
        artifact_path=artifact,
        artifact_memory_root=tmp_path / "artifact_memory",
    )

    assert result["artifact"]["status"] == "validated"
    assert result["artifact"]["source_id"].startswith(
        "comparison_engine:Obra_X:1_PAV:PIL:P1:N3:"
    )
    assert len(result["artifact"]["artifact_sha256"]) == 64
    assert result["artifact"]["render_status"] == "ready"
    assert Path(result["artifact"]["thumbnail_path"]).exists()
    from PIL import Image

    with Image.open(result["artifact"]["thumbnail_path"]) as image:
        assert image.size == (1024, 768)
    manifest = json.loads(
        Path(result["artifact"]["render_manifest"]["manifest_path"]).read_text(
            encoding="utf-8"
        )
    )
    assert manifest["renderer_version"] == "dxf-canonical-v1"
    assert manifest["source_sha256"] == result["artifact"]["artifact_sha256"]
    assert manifest["entity_count"] == 2
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT scope, status, artifact_path, artifact_sha256
            FROM rag_artifact_validations
            """
        ).fetchone()
    assert row[0:2] == ("N3", "validated")
    assert row[2] == str(artifact)
    assert len(row[3]) == 64


def test_comparison_artifact_revocation_preserves_row_and_tombstones_version(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "project_data.vision"
    artifact = tmp_path / "P1_N4.dxf"
    tombstones_path = tmp_path / "rag_tombstones.json"
    _write_valid_dxf(artifact)
    _make_db(db_path)

    import rag_validation_events as events
    from rag_tier import revoke_item as revoke_at

    monkeypatch.setattr(
        events,
        "revoke_item",
        lambda source_id, **kwargs: revoke_at(
            source_id, path=tombstones_path, **kwargs
        ),
    )

    record_comparison_human_validation(
        obra_name="Obra_X",
        pavimento="1_PAV",
        classe="PIL",
        item_id="P1",
        scope="N4",
        human_validated=True,
        db_path=db_path,
        validation_origin="human_ui",
        artifact_path=artifact,
        artifact_memory_root=tmp_path / "artifact_memory",
    )
    revoked = record_comparison_human_validation(
        obra_name="Obra_X",
        pavimento="1_PAV",
        classe="PIL",
        item_id="P1",
        scope="N4",
        human_validated=False,
        db_path=db_path,
        validation_origin="human_ui",
        artifact_path=artifact,
        artifact_memory_root=tmp_path / "artifact_memory",
    )

    assert revoked["revoked"] is True
    assert revoked["artifact"]["status"] == "revoked"
    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM rag_artifact_validations"
        ).fetchone()[0]
    assert status == "revoked"
    tombstones = json.loads(tombstones_path.read_text(encoding="utf-8"))["items"]
    assert revoked["artifact"]["source_id"] in tombstones


def test_reverse_hub_cli_without_human_origin_does_not_promote(tmp_path):
    db_path = tmp_path / "project_data.vision"
    _make_db(db_path)

    result = record_reverse_hub_approval(
        obra_name="Obra_X",
        classe="PIL",
        elemento_id="P1",
        recorte_path="recorte.dxf",
        db_path=db_path,
        auto_index=False,
    )

    assert result["status"] == "blocked_non_human_origin"
    assert result["ficha_id"] is None
    assert result["indexed"] == 0

    with sqlite3.connect(db_path) as conn:
        status, aprovado_at = conn.execute(
            "SELECT status, aprovado_at FROM reverse_eng_fichas WHERE id=1"
        ).fetchone()
        event_type, event_status, context_json = conn.execute(
            "SELECT type, status, context_dna_json FROM training_events"
        ).fetchone()

    assert status == "draft"
    assert aprovado_at is None
    assert event_type == "rag_reverse_hub_machine_candidate"
    assert event_status == "quarantine"
    assert json.loads(context_json)["validation_origin"] == "missing"


def test_comparison_cli_without_human_origin_records_candidate_only(tmp_path):
    db_path = tmp_path / "project_data.vision"
    _make_db(db_path)

    result = record_comparison_human_validation(
        obra_name="Obra_X",
        pavimento="1_PAV",
        classe="PIL",
        item_id="P1",
        scope="N3",
        human_validated=True,
        db_path=db_path,
    )

    assert result["status"] == "blocked_non_human_origin"
    assert result["revoked"] is False

    with sqlite3.connect(db_path) as conn:
        event_type, event_status = conn.execute(
            "SELECT type, status FROM training_events"
        ).fetchone()

    assert event_type == "rag_comparison_machine_candidate"
    assert event_status == "quarantine"
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='rag_artifact_validations'
            """
        ).fetchone()
    assert exists is None


def test_reverse_hub_revocation_marks_f5_tx_and_revalidation_restores(tmp_path, monkeypatch):
    db_path = tmp_path / "project_data.vision"
    tombstones_path = tmp_path / "rag_tombstones.json"
    _make_db(db_path)

    import rag_validation_events as events

    original_revoke = events.revoke_item
    original_clear = events.clear_revocation
    monkeypatch.setattr(
        events,
        "revoke_item",
        lambda source_id, **kwargs: original_revoke(
            source_id, path=tombstones_path, **kwargs
        ),
    )
    monkeypatch.setattr(
        events,
        "clear_revocation",
        lambda source_id: original_clear(source_id, path=tombstones_path),
    )

    revoked = record_reverse_hub_revocation(
        obra_name="Obra_X",
        classe="PIL",
        elemento_id="P1",
        recorte_path="recorte.dxf",
        reason="campos incorretos",
        db_path=db_path,
        validation_origin="human_ui",
    )
    assert revoked["status"] == "revoked_tx"
    assert revoked["revoked"] is True
    assert tombstones_path.exists()

    restored = record_reverse_hub_approval(
        obra_name="Obra_X",
        classe="PIL",
        elemento_id="P1",
        recorte_path="recorte.dxf",
        db_path=db_path,
        auto_index=False,
        validation_origin="human_ui",
    )
    assert restored["status"] == "promoted_t1"
    assert restored["revocation_cleared"] is True

    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM reverse_eng_fichas WHERE id=1"
        ).fetchone()[0]
    assert status == "aprovado"


def test_reverse_hub_revocation_without_human_origin_is_quarantined(tmp_path):
    db_path = tmp_path / "project_data.vision"
    _make_db(db_path)

    result = record_reverse_hub_revocation(
        obra_name="Obra_X",
        classe="PIL",
        elemento_id="P1",
        recorte_path="recorte.dxf",
        reason="synthetic",
        db_path=db_path,
    )

    assert result["status"] == "blocked_non_human_origin"
    assert result["revoked"] is False
    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM reverse_eng_fichas WHERE id=1"
        ).fetchone()[0]
    assert status == "draft"


def test_reextracted_f5_does_not_reactivate_old_vector_version(tmp_path, monkeypatch):
    db_path = tmp_path / "project_data.vision"
    tombstones_path = tmp_path / "rag_tombstones.json"
    _make_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE reverse_eng_fichas SET status='aprovado', rag_indexed=1 WHERE id=1"
        )
        conn.commit()

    import rag_validation_events as events
    from rag_tier import (
        clear_revocation as clear_at,
        get_reverse_ficha_source_ids,
        load_tombstones,
        revoke_item as revoke_at,
    )

    monkeypatch.setattr(
        events,
        "revoke_item",
        lambda source_id, **kwargs: revoke_at(
            source_id, path=tombstones_path, **kwargs
        ),
    )
    monkeypatch.setattr(
        events,
        "clear_revocation",
        lambda source_id: clear_at(source_id, path=tombstones_path),
    )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        old_row = dict(conn.execute(
            "SELECT * FROM reverse_eng_fichas WHERE id=1"
        ).fetchone())
    old_legacy_id, old_version_id = get_reverse_ficha_source_ids(old_row)

    record_reverse_hub_revocation(
        obra_name="Obra_X",
        classe="PIL",
        elemento_id="P1",
        recorte_path="recorte.dxf",
        reason="corrigir campos",
        db_path=db_path,
        validation_origin="human_ui",
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE reverse_eng_fichas
            SET campos_json='{"comprimento": 20}', rag_indexed=0
            WHERE id=1
            """
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        new_row = dict(conn.execute(
            "SELECT * FROM reverse_eng_fichas WHERE id=1"
        ).fetchone())
    _, new_version_id = get_reverse_ficha_source_ids(new_row)
    assert new_version_id != old_version_id

    record_reverse_hub_approval(
        obra_name="Obra_X",
        classe="PIL",
        elemento_id="P1",
        recorte_path="recorte.dxf",
        db_path=db_path,
        auto_index=False,
        validation_origin="human_ui",
    )

    tombstones = load_tombstones(tombstones_path)
    assert old_legacy_id in tombstones
    assert old_version_id in tombstones
    assert new_version_id not in tombstones
