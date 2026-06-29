import importlib.util
import json
import sqlite3
import sys
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESTORED = ROOT / "Agente-cad-PYSIDE-Restored-main"
if str(RESTORED) not in sys.path:
    sys.path.insert(0, str(RESTORED))

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="Support for class-based `config` is deprecated.*",
        category=DeprecationWarning,
    )
    module_path = RESTORED / "src" / "ui" / "widgets" / "project_manager.py"
    spec = importlib.util.spec_from_file_location("rag_curadoria_project_manager", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    ProjectManager = module.ProjectManager


def _create_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE reverse_eng_fichas (
                id INTEGER, classe TEXT, status TEXT, rag_indexed INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE fase3_fichas (
                id INTEGER, tipo TEXT, revisado INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE semantic_rag_kb (
                id INTEGER, classe TEXT, regra_semantica TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE training_events (
                id INTEGER, type TEXT, role TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE transformation_rules (
                id INTEGER, entity_type TEXT, accuracy_pct REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE rag_artifact_validations (
                source_id TEXT, scope TEXT, status TEXT, classe TEXT,
                render_status TEXT
            )
            """
        )
        conn.execute("INSERT INTO reverse_eng_fichas VALUES (1, 'PIL', 'draft', 0)")
        conn.execute("INSERT INTO fase3_fichas VALUES (1, 'pilar', 0)")
        conn.execute("INSERT INTO semantic_rag_kb VALUES (1, 'PIL', 'regra confirmada')")
        conn.execute("INSERT INTO training_events VALUES (1, 'user_validation', 'Pilar_name')")
        conn.execute("INSERT INTO transformation_rules VALUES (1, 'PIL', 82.5)")
        conn.execute(
            """
            INSERT INTO rag_artifact_validations
            VALUES ('comparison:P1:N3:abc', 'N3', 'validated', 'PIL', 'ready')
            """
        )


def test_curadoria_metrics_are_read_only_and_expose_pending_work(tmp_path):
    db_path = tmp_path / "project_data.vision"
    _create_db(db_path)
    registry = json.loads((ROOT / "data" / "classe_registry.json").read_text(encoding="utf-8"))
    registry["classes"].append({
        "id": "FUND",
        "name": "Fundacao",
        "aliases": [],
        "enabled": True,
    })
    registry_dir = tmp_path / "data"
    registry_dir.mkdir()
    (registry_dir / "classe_registry.json").write_text(
        json.dumps(registry),
        encoding="utf-8",
    )
    before = db_path.read_bytes()

    class DummyDB:
        pass

    class Dummy:
        pass

    dummy = Dummy()
    dummy.db = DummyDB()
    dummy.db.db_path = str(db_path)

    metrics = ProjectManager._collect_curadoria_rag_metrics(dummy)

    assert db_path.read_bytes() == before
    assert metrics["learning_counts"]["user_validation"] == 1
    assert metrics["learning_accuracy"] == "82.5%"
    assert metrics["table_counts"]["rag_artifact_validations"] == 1
    assert metrics["artifact_counts"]["validated"] == 1
    assert metrics["artifact_counts"]["render_ready"] == 1
    assert metrics["artifact_history_rows"][0][0] == "N3"
    assert metrics["artifact_history_rows"][0][5] == "VALIDATED"
    assert metrics["pending_counts"]["ALTA"] >= 1
    assert any(row[0] == "PIL" and row[9] == "5/8" for row in metrics["encyclopedia_rows"])
    assert any(row[0] == "FUND" and row[1:9] == [0, 0, 0, 0, 0, 0, 0, "-"] for row in metrics["encyclopedia_rows"])
    assert any(
        row[0] == "ALTA" and row[1] == "Classe PIL" and "T1/T2" in row[2]
        for row in metrics["pending_rows"]
    )
