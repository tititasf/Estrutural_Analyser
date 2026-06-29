import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from obra_rag_pipeline import build_snapshot, run_pipeline, write_snapshot


def test_pipeline_imports_as_scripts_package():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts.obra_rag_pipeline import run_pipeline; assert callable(run_pipeline)",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _make_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE projects (
                id TEXT, name TEXT, dxf_path TEXT, work_name TEXT,
                pavement_name TEXT, sync_status TEXT, file_version TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE project_documents (
                id TEXT, project_id TEXT, work_name TEXT, name TEXT, file_path TEXT,
                extension TEXT, phase INTEGER, category TEXT, file_version TEXT,
                entity_count INTEGER, dxf_version TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE reverse_eng_fichas (
                id INTEGER, projeto_id TEXT, obra_name TEXT, pavimento TEXT,
                classe TEXT, elemento_id TEXT, campos_json TEXT, recorte_path TEXT,
                confianca REAL, status TEXT, aprovado_at TEXT, rag_indexed INTEGER,
                created_at TEXT, updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE reverse_eng_recortes (
                id INTEGER, ficha_id INTEGER, obra_name TEXT, elemento_id TEXT,
                recorte_path TEXT, entity_count INTEGER, projeto_id TEXT,
                classe TEXT, status TEXT, confidence REAL, created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE obra_recortes (
                id TEXT, obra_name TEXT, pavimento_name TEXT, dxf_bruto_path TEXT,
                recorte_type TEXT, recorte_index INTEGER, output_path TEXT,
                entity_count INTEGER, score REAL, status TEXT, n_torres INTEGER,
                approved_at TEXT, updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE semantic_rag_kb (
                id INTEGER, classe TEXT, regra_semantica TEXT,
                obra_contexto TEXT, confianca REAL, created_at TEXT
            )
            """
        )
        conn.execute("INSERT INTO projects VALUES ('p1','1_PAV','a.dxf','Obra_X','1_PAV','ok','R2018')")
        conn.execute("INSERT INTO project_documents VALUES ('d1','p1','Obra_X','doc','doc.dxf','.dxf',1,'bruto','R2018',10,'R2018')")
        conn.execute(
            "INSERT INTO reverse_eng_fichas VALUES (1,'p1','Obra_X','1_PAV','PIL','P1','{\"altura\":280}','r.dxf',0.9,'draft',NULL,0,NULL,NULL)"
        )
        conn.execute("INSERT INTO reverse_eng_recortes VALUES (1,NULL,'Obra_X','P1','r.dxf',20,'p1','PIL','aprovado',1.0,NULL)")
        conn.execute("INSERT INTO obra_recortes VALUES ('o1','Obra_X','1_PAV','b.dxf','torre',0,'out.dxf',50,0.8,'approved',1,NULL,NULL)")
        conn.execute(
            "INSERT INTO semantic_rag_kb VALUES (1,'PIL','{\"source_doc\":\"doc.md\",\"section\":\"sec\",\"text\":\"regra\"}','domain',1.0,NULL)"
        )
        conn.commit()


def test_build_snapshot_is_local_and_marks_t0(tmp_path):
    db_path = tmp_path / "project_data.vision"
    obras_root = tmp_path / "DADOS-OBRAS"
    (obras_root / "Obra_X").mkdir(parents=True)
    _make_db(db_path)

    snapshot = build_snapshot("Obra_X", db_path=db_path, obras_root=obras_root)

    assert snapshot["scope"] == "obra_local"
    assert snapshot["promotion_policy"] == "never_auto_global"
    assert snapshot["counts"]["reverse_fichas"] == 1
    assert snapshot["tiers"] == {"T0": 1}
    assert snapshot["reverse_fichas"][0]["campos"]["preview"]["altura"] == 280
    assert "contains_local_T0_context_not_global_truth" in snapshot["warnings"]


def test_write_snapshot_outputs_manifest(tmp_path):
    db_path = tmp_path / "project_data.vision"
    obras_root = tmp_path / "DADOS-OBRAS"
    (obras_root / "Obra_X").mkdir(parents=True)
    _make_db(db_path)

    snapshot = build_snapshot("Obra_X", db_path=db_path, obras_root=obras_root)
    out_path = write_snapshot(snapshot, obras_root=obras_root)

    assert out_path.name == "manifest.json"
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["obra_name"] == "Obra_X"


def test_run_pipeline_is_ui_compatible(tmp_path):
    db_path = tmp_path / "project_data.vision"
    obras_root = tmp_path / "DADOS-OBRAS"
    (obras_root / "Obra_X").mkdir(parents=True)
    _make_db(db_path)
    progress = []

    result = run_pipeline(
        "Obra_X",
        db_path=db_path,
        obras_root=obras_root,
        progress_cb=lambda pct, msg: progress.append((pct, msg)),
    )

    assert result["status"] == "ok"
    assert result["scope"] == "obra_local"
    assert result["promotion_policy"] == "never_auto_global"
    assert result["dxf_indexed"] == 1
    assert Path(result["snapshot_path"]).exists()
    assert progress[-1][0] == 100
