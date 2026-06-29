import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from obra_rag_query import query_local_snapshot


def _write_snapshot(root: Path) -> None:
    out_dir = root / "Obra_X" / "obra_rag"
    out_dir.mkdir(parents=True)
    snapshot = {
        "schema_version": 1,
        "obra_name": "Obra_X",
        "scope": "obra_local",
        "promotion_policy": "never_auto_global",
        "documents": [
            {"name": "planta limpa", "category": "estrutural", "phase": 2, "file_path": "limpo.dxf"}
        ],
        "reverse_fichas": [
            {
                "classe": "PIL",
                "elemento_id": "P101",
                "pavimento": "1_PAV",
                "status": "draft",
                "tier": "T0",
                "recorte_path": "p101.dxf",
                "campos": {"keys": ["altura", "grade_1"], "preview": {"altura": 280}},
            }
        ],
        "semantic_rules": [
            {
                "id": 1,
                "classe": "PIL",
                "rule": {
                    "source_doc": "SEMANTICA-PIL.md",
                    "section": "grade_1",
                    "text": "grade_1 depende do comprimento",
                },
            }
        ],
        "reverse_recortes": [],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(snapshot, ensure_ascii=False),
        encoding="utf-8",
    )


def test_local_query_labels_t0_as_non_global_truth(tmp_path):
    _write_snapshot(tmp_path)

    results = query_local_snapshot(
        "Obra_X",
        "PIL P101 altura 1_PAV",
        obras_root=tmp_path,
    )

    ficha = next(row for row in results if row["kind"] == "reverse_ficha")
    assert ficha["tier"] == "T0"
    assert ficha["scope"] == "obra_local"
    assert ficha["is_global_truth"] is False
    assert ficha["promotion_policy"] == "never_auto_global"


def test_local_query_is_read_only_and_rejects_wrong_scope(tmp_path):
    _write_snapshot(tmp_path)
    manifest = tmp_path / "Obra_X" / "obra_rag" / "manifest.json"
    before = manifest.read_bytes()

    assert query_local_snapshot("Obra_X", "grade_1", obras_root=tmp_path)
    assert manifest.read_bytes() == before

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["scope"] = "global"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert query_local_snapshot("Obra_X", "grade_1", obras_root=tmp_path) == []
