import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from src.mcp import db_bridge  # noqa: E402
from src.mcp import cad_analyzer_mcp as mcp_server  # noqa: E402
from active_learning_query import query_active_learning  # noqa: E402
from active_learning_patterns import analyze_patterns  # noqa: E402
from mcp_active_learning_daemon import run_once  # noqa: E402
from rag_active_trainer import build_store  # noqa: E402


APP_ROOT = ROOT / "Agente-cad-PYSIDE-Restored-main"


class FakeModel:
    def encode(self, texts, **_kwargs):
        rows = []
        for text in texts:
            seed = sum(text.encode("utf-8")) % 384
            vector = np.zeros(384, dtype=np.float32)
            vector[seed] = 1.0
            rows.append(vector)
        return np.asarray(rows)


def test_desktop_runtime_can_import_canonical_mcp():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from src.mcp.db_bridge import save_human_edit_event; "
                "import src.mcp.db_bridge as bridge; "
                "print(bridge.__file__)"
            ),
        ],
        cwd=APP_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(ROOT / "src" / "mcp" / "db_bridge.py") in result.stdout.strip()


def _event(db_path: Path) -> str:
    return db_bridge.save_human_edit_event(
        obra_id="Obra_X",
        classe="PIL",
        item_id="P1",
        fase_editada="N1_ATENCAO",
        ui_context="ComparisonEngine",
        estado_anterior={"comprimento": 40},
        estado_novo={"comprimento": 20},
        nota_usuario="cota interpretada incorretamente",
        source_agent="test",
        db_path=db_path,
    )


def _row(db_path: Path, log_id: str):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return dict(conn.execute(
            "SELECT * FROM human_event_logs WHERE log_id=?", (log_id,)
        ).fetchone())


def test_edit_is_t0_and_cannot_self_approve(tmp_path):
    db_path = tmp_path / "test.vision"
    log_id = _event(db_path)
    row = _row(db_path, log_id)
    assert row["status"] == "CAPTURED"
    assert row["tier"] == "T0"
    assert row["processado_por_rag"] == 0
    assert db_bridge.mark_event_as_processed(
        log_id, "forbidden", db_path=db_path
    ) is False
    assert _row(db_path, log_id)["processado_por_rag"] == 0

    with pytest.raises(ValueError, match="origem humana"):
        db_bridge.approve_event_candidate(
            log_id,
            approved_by="agent",
            reason="synthetic",
            validation_origin="cli",
            db_path=db_path,
        )


def test_daemon_proposes_and_candidate_store_does_not_touch_structural(tmp_path):
    db_path = tmp_path / "test.vision"
    log_id = _event(db_path)
    candidates = tmp_path / "candidates"
    faiss_root = tmp_path / "vectors"
    structural = tmp_path / "estruturais.index"
    structural.write_bytes(b"production-index")
    before = hashlib.sha256(structural.read_bytes()).hexdigest()

    result = run_once(db_path=db_path, candidates_dir=candidates)
    assert result["proposed"] == 1
    assert _row(db_path, log_id)["status"] == "PROPOSED"
    proposal = json.loads((candidates / f"proposal_{log_id}.json").read_text(encoding="utf-8"))
    assert proposal["tier"] == "T0"
    assert proposal["is_global_truth"] is False
    assert proposal["requires_human_approval"] is True

    store = build_store(
        db_path=db_path,
        vector_root=faiss_root,
        model=FakeModel(),
    )
    assert store["store"] == "candidates"
    assert store["count"] == 1
    assert store["modified_structural_index"] is False
    assert hashlib.sha256(structural.read_bytes()).hexdigest() == before
    results = query_active_learning(
        "comprimento incorreto",
        include_candidates=True,
        vector_root=faiss_root,
        model=FakeModel(),
    )
    assert results[0]["meta"]["tier"] == "T0"


def test_only_human_approved_proposal_enters_approved_store(tmp_path):
    db_path = tmp_path / "test.vision"
    log_id = _event(db_path)
    run_once(db_path=db_path, candidates_dir=tmp_path / "candidates")

    assert db_bridge.approve_event_candidate(
        log_id,
        approved_by="thierry",
        reason="confirmado visualmente",
        validation_origin="human_ui",
        db_path=db_path,
    )
    result = build_store(
        approved=True,
        db_path=db_path,
        vector_root=tmp_path / "vectors",
        model=FakeModel(),
    )
    assert result["count"] == 1
    row = _row(db_path, log_id)
    assert row["status"] == "INDEXED"
    assert row["tier"] == "T1"
    assert row["rag_vector_id"].startswith("active_learning:approved:")


def test_known_production_smoke_event_is_quarantined(tmp_path):
    db_path = tmp_path / "test.vision"
    db_bridge.ensure_event_sourcing_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO human_event_logs (
                log_id,timestamp,obra_id,classe,item_id,fase_editada,ui_context,
                estado_anterior_json,estado_novo_json,status,tier
            ) VALUES (?,?,?,?,?,?,?,?,?,'CAPTURED','T0')
            """,
            (
                "52fd248f-c0c4-4893-ade0-47393a2512fb",
                "2026-06-29", "Obra_TREINO_1", "PIL", "P15", "N1", "DiagnosticPreHub",
                "{}", "{}",
            ),
        )
        conn.commit()
    db_bridge.ensure_event_sourcing_tables(db_path)
    row = _row(db_path, "52fd248f-c0c4-4893-ade0-47393a2512fb")
    assert row["status"] == "TEST_QUARANTINED"
    assert row["tier"] == "T0"


def test_mcp_writes_require_configured_token(tmp_path, monkeypatch):
    db_path = tmp_path / "test.vision"
    db_bridge.ensure_event_sourcing_tables(db_path)
    monkeypatch.setattr(mcp_server, "DB_PATH", db_path)
    monkeypatch.setattr(mcp_server, "WRITE_TOKEN", "secret")

    with pytest.raises(PermissionError):
        mcp_server.save_human_edit_event(
            "Obra_X", "PIL", "P1", "N1", "Test",
            "{}", '{"a": 1}', write_token="wrong",
        )

    result = json.loads(
        mcp_server.save_human_edit_event(
            "Obra_X", "PIL", "P1", "N1", "Test",
            "{}", '{"a": 1}', motivo_humano="teste isolado",
            write_token="secret",
        )
    )
    assert _row(db_path, result["log_id"])["status"] == "CAPTURED"


def test_pattern_analysis_remains_t0_and_explains_recurrence(tmp_path):
    db_path = tmp_path / "test.vision"
    first = _event(db_path)
    run_once(db_path=db_path, candidates_dir=tmp_path / "candidates")
    second = db_bridge.save_human_edit_event(
        obra_id="Obra_Y",
        classe="PIL",
        item_id="P2",
        fase_editada="N1_ATENCAO",
        ui_context="ComparisonEngine",
        estado_anterior={"comprimento": 50},
        estado_novo={"comprimento": 25},
        nota_usuario="mesma leitura de cota",
        source_agent="test",
        db_path=db_path,
    )
    run_once(db_path=db_path, candidates_dir=tmp_path / "candidates")

    result = analyze_patterns(
        db_path=db_path,
        output_path=tmp_path / "patterns.json",
    )
    pattern = next(row for row in result["patterns"] if row["field"] == "comprimento")
    assert pattern["tier"] == "T0"
    assert pattern["is_global_truth"] is False
    assert pattern["occurrences"] == 2
    assert pattern["distinct_works"] == 2
    assert {first, second} <= set(pattern["source_event_ids"])
