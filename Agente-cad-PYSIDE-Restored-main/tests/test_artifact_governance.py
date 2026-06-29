import json
import sqlite3
import stat
from pathlib import Path

import pytest

from src.core.artifact_governance import (
    discover_level_artifacts,
    ensure_artifact_integrity,
    guarded_promote,
    guarded_saveas,
    is_artifact_protected,
    motor_history,
    record_motor_test_result,
    register_motor_version,
)
from src.core.item_attention_store import save_human_validation
from src.core.item_attention_store import ensure_table, is_human_validated


class _FakeDoc:
    def __init__(self, payload: bytes):
        self.payload = payload

    def saveas(self, path: str):
        Path(path).write_bytes(self.payload)


def _artifact(
    tmp_path: Path,
    obra: str,
    scope: str,
    filename: str,
    content: bytes = b"validated",
) -> Path:
    root = tmp_path / "DADOS-OBRAS" / obra / "Fase-6_Execucao_CAD"
    if scope == "N4":
        root /= "n4"
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    path.write_bytes(content)
    return path


@pytest.mark.parametrize(
    ("classe", "scope", "filename", "item_id"),
    [
        ("PL", "N3", "PL_ABCD_preview_P1.dxf", "P1"),
        ("LV", "N4", "LV_preview_V301_A.dxf", "V301_A_Para"),
        ("FV", "N4", "FV_preview_V301.dxf", "V301"),
        ("LJ", "N3", "LJ_preview_L101.dxf", "L101"),
    ],
)
def test_human_validation_protects_all_n3_n4_classes(
    tmp_path: Path, classe: str, scope: str, filename: str, item_id: str
):
    db_path = tmp_path / "project_data.vision"
    official = _artifact(tmp_path, "Obra_A", scope, filename)

    save_human_validation(
        "Obra_A",
        "13_PAV",
        classe,
        item_id,
        scope,
        True,
        db_path=db_path,
        validation_origin="human_ui",
    )

    assert is_artifact_protected(official, db_path)
    assert discover_level_artifacts(
        "Obra_A", classe, item_id, scope, tmp_path / "DADOS-OBRAS"
    ) == [official]
    assert not (official.stat().st_mode & stat.S_IWRITE)


def test_protected_output_is_preserved_and_new_motor_goes_to_candidate(
    tmp_path: Path,
):
    db_path = tmp_path / "project_data.vision"
    source = tmp_path / "motor.py"
    source.write_text("version = 1\n", encoding="utf-8")
    official = _artifact(
        tmp_path, "Obra_A", "N4", "FV_preview_V301.dxf", b"human-approved"
    )
    save_human_validation(
        "Obra_A", "13_PAV", "FV", "V301", "N4", True,
        db_path=db_path, validation_origin="human_ui",
    )

    candidate = guarded_saveas(
        _FakeDoc(b"new-engine-result"),
        official,
        motor_id="ROBOT_FV_N3_N4",
        source_paths=[source],
        db_path=db_path,
    )

    assert official.read_bytes() == b"human-approved"
    assert candidate != official
    assert candidate.read_bytes() == b"new-engine-result"
    assert ".motor_versions" in candidate.parts
    run = motor_history("ROBOT_FV_N3_N4", db_path)[0]
    assert run["mode"] == "headless_candidate"
    assert run["status"] == "blocked_protected"
    assert run["effect"] == "changed"
    record_motor_test_result(
        run["run_id"],
        {"geometry_score": 0.97, "regression": False},
        db_path=db_path,
    )
    tested = motor_history("ROBOT_FV_N3_N4", db_path)[0]
    assert tested["status"] == "tested"
    assert json.loads(tested["result_json"])["geometry_score"] == 0.97


def test_integrity_check_restores_a_bypassed_validated_artifact(tmp_path: Path):
    db_path = tmp_path / "project_data.vision"
    official = _artifact(
        tmp_path, "Obra_A", "N3", "LJ_preview_L101.dxf", b"approved"
    )
    save_human_validation(
        "Obra_A", "13_PAV", "LJ", "L101", "N3", True,
        db_path=db_path, validation_origin="human_ui",
    )

    official.chmod(official.stat().st_mode | stat.S_IWRITE)
    official.write_bytes(b"corrupted")

    assert ensure_artifact_integrity(official, db_path) is False
    assert official.read_bytes() == b"approved"
    assert not (official.stat().st_mode & stat.S_IWRITE)


def test_protected_promotion_keeps_official_and_versions_candidate(
    tmp_path: Path,
):
    db_path = tmp_path / "project_data.vision"
    source = tmp_path / "motor.py"
    source.write_text("version = 1\n", encoding="utf-8")
    official = _artifact(
        tmp_path, "Obra_A", "N4", "PL_CIMA_preview_P1.dxf", b"approved"
    )
    generated = tmp_path / "PL_CIMA_preview_P1.generated.dxf"
    generated.write_bytes(b"new-candidate")
    save_human_validation(
        "Obra_A", "13_PAV", "PL", "P1", "N4", True,
        db_path=db_path, validation_origin="human_ui",
    )

    candidate = guarded_promote(
        generated,
        official,
        motor_id="ROBOT_PL_N3_N4",
        source_paths=[source],
        db_path=db_path,
    )

    assert official.read_bytes() == b"approved"
    assert candidate.read_bytes() == b"new-candidate"
    assert not generated.exists()
    assert candidate != official


def test_unchecking_human_validation_allows_publication(tmp_path: Path):
    db_path = tmp_path / "project_data.vision"
    source = tmp_path / "motor.py"
    source.write_text("version = 1\n", encoding="utf-8")
    official = _artifact(
        tmp_path, "Obra_A", "N4", "FV_preview_V301.dxf", b"approved"
    )
    save_human_validation(
        "Obra_A", "13_PAV", "FV", "V301", "N4", True,
        db_path=db_path, validation_origin="human_ui",
    )
    save_human_validation(
        "Obra_A", "13_PAV", "FV", "V301", "N4", False,
        db_path=db_path, validation_origin="human_ui",
    )

    output = guarded_saveas(
        _FakeDoc(b"published-after-uncheck"),
        official,
        motor_id="ROBOT_FV_N3_N4",
        source_paths=[source],
        db_path=db_path,
    )

    assert output == official
    assert official.read_bytes() == b"published-after-uncheck"
    assert not is_artifact_protected(official, db_path)


def test_validation_policy_blocks_future_artifact_until_unchecked(tmp_path: Path):
    db_path = tmp_path / "project_data.vision"
    source = tmp_path / "motor.py"
    source.write_text("version = 1\n", encoding="utf-8")
    target = (
        tmp_path / "DADOS-OBRAS" / "Obra_A" / "Fase-6_Execucao_CAD"
        / "n4" / "LJ_preview_L101.dxf"
    )
    save_human_validation(
        "Obra_A", "13_PAV", "LJ", "L101", "N4", True,
        db_path=db_path, validation_origin="human_ui",
    )

    candidate = guarded_saveas(
        _FakeDoc(b"candidate"),
        target,
        motor_id="ROBOT_LJ_N3_N4",
        source_paths=[source],
        db_path=db_path,
    )

    assert not target.exists()
    assert candidate.exists()
    assert is_artifact_protected(target, db_path)


def test_headless_mode_never_publishes_even_without_validation(
    tmp_path: Path, monkeypatch
):
    db_path = tmp_path / "project_data.vision"
    source = tmp_path / "motor.py"
    source.write_text("version = 1\n", encoding="utf-8")
    official = _artifact(
        tmp_path, "Obra_A", "N3", "LJ_preview_L101.dxf", b"current"
    )
    monkeypatch.setenv("CAD_MOTOR_HEADLESS", "1")

    candidate = guarded_saveas(
        _FakeDoc(b"headless-result"),
        official,
        motor_id="ROBOT_LJ_N3_N4",
        source_paths=[source],
        db_path=db_path,
    )

    assert official.read_bytes() == b"current"
    assert candidate.read_bytes() == b"headless-result"
    assert candidate != official
    run = motor_history("ROBOT_LJ_N3_N4", db_path)[0]
    assert run["status"] == "candidate_pending_test"
    assert json.loads(run["result_json"])["comparison_status"] == "pending"


def test_motor_version_is_content_addressed(tmp_path: Path):
    db_path = tmp_path / "project_data.vision"
    source = tmp_path / "motor.py"
    source.write_text("version = 1\n", encoding="utf-8")
    version_1a = register_motor_version("ROBOT_FV_N3_N4", [source], db_path)
    version_1b = register_motor_version("ROBOT_FV_N3_N4", [source], db_path)
    source.write_text("version = 2\n", encoding="utf-8")
    version_2 = register_motor_version("ROBOT_FV_N3_N4", [source], db_path)

    assert version_1a == version_1b
    assert version_2 != version_1a


def test_legacy_human_validation_is_backfilled_into_protection(tmp_path: Path):
    db_path = tmp_path / "project_data.vision"
    official = _artifact(
        tmp_path, "Obra_A", "N3", "FV_preview_V301.dxf", b"legacy-approved"
    )
    ensure_table(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO item_attention_notes
                (id, obra_name, pavimento, classe, item_id, scope,
                 human_validated, validation_origin, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, 'human_ui', '', '')
            """,
            (
                "Obra_A|13_PAV|FV|V301|N3",
                "Obra_A",
                "13_PAV",
                "FV",
                "V301",
                "N3",
            ),
        )

    assert is_human_validated(
        "Obra_A", "13_PAV", "FV", "V301", "N3", db_path
    )
    assert is_artifact_protected(official, db_path)
    assert not (official.stat().st_mode & stat.S_IWRITE)
