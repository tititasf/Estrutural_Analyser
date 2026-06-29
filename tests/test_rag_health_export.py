import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rag_export import export_rag_bundle
from rag_health import collect_health


def _make_db(path: Path, thumbnail: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE semantic_rag_kb (id INTEGER, classe TEXT)")
        conn.execute("INSERT INTO semantic_rag_kb VALUES (1, 'PIL')")
        conn.execute(
            """
            CREATE TABLE rag_artifact_validations (
                status TEXT, render_status TEXT, thumbnail_path TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO rag_artifact_validations VALUES ('validated', 'ready', ?)",
            (str(thumbnail),),
        )
        for table in ("crop_learning_events", "training_events", "item_attention_notes"):
            conn.execute(f"CREATE TABLE {table} (id INTEGER)")
        conn.commit()


def test_health_is_read_only_and_reports_valid_snapshot(tmp_path):
    db_path = tmp_path / "project_data.vision"
    thumbnail = tmp_path / "preview.png"
    thumbnail.write_bytes(b"png")
    _make_db(db_path, thumbnail)
    snapshot_dir = tmp_path / "obras" / "Obra_X" / "obra_rag"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(
            {
                "scope": "obra_local",
                "promotion_policy": "never_auto_global",
            }
        ),
        encoding="utf-8",
    )
    before = db_path.read_bytes()

    report = collect_health(
        db_path=db_path,
        obras_root=tmp_path / "obras",
        faiss_dir=tmp_path / "faiss",
        artifact_root=tmp_path / "artifacts",
    )

    assert report["read_only"] is True
    assert report["status"] == "ok"
    assert report["snapshots"]["valid"] == 1
    assert report["artifacts"]["render_ready"] == 1
    assert db_path.read_bytes() == before


def test_export_has_hash_manifest_and_does_not_mutate_source(tmp_path):
    db_path = tmp_path / "project_data.vision"
    thumbnail = tmp_path / "preview.png"
    thumbnail.write_bytes(b"png")
    _make_db(db_path, thumbnail)
    before = db_path.read_bytes()

    manifest = export_rag_bundle(
        tmp_path / "bundle",
        db_path=db_path,
        obras_root=tmp_path / "obras",
        faiss_dir=tmp_path / "faiss",
        artifact_root=tmp_path / "artifacts",
    )

    assert manifest["read_only_source_export"] is True
    assert manifest["is_global_truth"] is False
    assert any(row["path"] == "tables/semantic_rag_kb.json" for row in manifest["files"])
    disk_manifest = json.loads((tmp_path / "bundle" / "MANIFEST.json").read_text(encoding="utf-8"))
    assert all(len(row["sha256"]) == 64 for row in disk_manifest["files"])
    assert db_path.read_bytes() == before
