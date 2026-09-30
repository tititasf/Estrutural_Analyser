"""G0 manifesto/corpus and G2 PIL/LAJ factory. No Jev API calls."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.arete.jev_calibration.cad_source import DxfParserCadSource
from scripts.arete.jev_calibration.corpus import to_jev_request
from scripts.arete.jev_calibration.factory import emit_case, run_factory, write_dry_run
from scripts.arete.jev_calibration.hashing import sha256_file
from scripts.arete.jev_calibration.import_known import import_known_corpus
from scripts.arete.jev_calibration.leakage import scan_evidence_leakage, validate_factory_request
from scripts.arete.jev_calibration.manifest import build_run_manifest, local_vs_vps
from scripts.arete.jev_calibration.n1_snapshot import N1Item, N1Snapshot
from scripts.arete.jev_calibration.schemas import (
    ADJUDICATION_SCHEMA,
    BASELINE_SCHEMA,
    FORBIDDEN_EVIDENCE_KEYS,
    FROZEN_VPS_14PAV,
    REPO_ROOT,
    SOURCE_PACKET_SCHEMA,
    VPS_PARITY_DIR,
)
from scripts.arete.jev_sa_second_read import validate_request
from scripts.arete.qa_session_index import SessionIndex, build_index

DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DXF_13 = Path(
    "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/"
    "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.dxf"
)
DXF_14_FROZEN = VPS_PARITY_DIR / "torre_1.dxf"
ESTADO_14 = VPS_PARITY_DIR / "estado_14_PAV.json"
PROJECT_13 = "dd238e47-1dc6-4f63-a760-4e7ce19a7386"


def _dxf_pil_laj(tmp_path: Path) -> Path:
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_text("P1", dxfattribs={"insert": (10, 30)})
    msp.add_lwpolyline([(0, 0), (20, 0), (20, 60), (0, 60), (0, 0)], close=True)
    msp.add_lwpolyline([(8, 28), (12, 28)])
    msp.add_text("20/60", dxfattribs={"insert": (8, 28)})
    msp.add_text("19/55", dxfattribs={"insert": (40, 28)})
    msp.add_text("V10", dxfattribs={"insert": (42, 10)})
    msp.add_text("P2", dxfattribs={"insert": (300, 300)})
    msp.add_lwpolyline([(298, 298), (310, 298)])
    msp.add_text("20/60", dxfattribs={"insert": (302, 301)})
    msp.add_text("19/55", dxfattribs={"insert": (320, 301)})
    msp.add_text("L410", dxfattribs={"insert": (100, 100)})
    msp.add_text("h=14", dxfattribs={"insert": (102, 96)})
    msp.add_text("855.25", dxfattribs={"insert": (104, 90)})
    msp.add_text("h=11", dxfattribs={"insert": (70, 140)})
    msp.add_text("855.22", dxfattribs={"insert": (68, 144)})
    msp.add_solid([(50, 120), (90, 120), (90, 160), (50, 160)])
    path = tmp_path / "fase1_pav.dxf"
    doc.saveas(path)
    return path


def _snapshot() -> N1Snapshot:
    p1 = N1Item(
        classe="PIL", name="P1",
        points=[[0, 0], [20, 0], [20, 60], [0, 60], [0, 0]],
        sa_value="19/55", sa_field="dim", snapshot_hash="p1hash",
        extras={"bbox": [0, 0, 20, 60], "center": [10, 30]},
    )
    l410 = N1Item(
        classe="LAJ", name="L410",
        points=[[40, 70], [160, 70], [160, 170], [40, 170], [40, 70]],
        sa_value="855.22", sa_field="laje_nivel", snapshot_hash="l410hash",
        extras={"bbox": [40, 70, 160, 170], "center": [100, 120]},
    )
    return N1Snapshot(
        project_id="proj-test", pavimento="13_PAV", source="fixture",
        fingerprint_sha256="fp-test",
        items={("PIL", "P1"): p1, ("LAJ", "L410"): l410},
    )


def test_leakage_scan_finds_forbidden_keys() -> None:
    problems = scan_evidence_leakage({"baseline_sa": {"value": "x"}, "handle": "A"})
    assert any(p.startswith("forbidden_keys") for p in problems)


def test_factory_packets_keep_sa_out_of_jev_state(tmp_path: Path) -> None:
    source = DxfParserCadSource(_dxf_pil_laj(tmp_path))
    snap = _snapshot()
    audit = run_factory(
        snapshot=snap, source=source, classes=["PIL", "LAJ"], items=["P1", "L410"],
        identity_base={"project_id": "proj-test", "pavimento": "13_PAV"},
    )
    assert audit["packed"] == 2
    for row in audit["cases"]:
        packet, baseline = row["packet"], row["baseline"]
        assert packet["schema"] == SOURCE_PACKET_SCHEMA
        assert baseline["schema"] == BASELINE_SCHEMA
        assert row["adjudication"]["schema"] == ADJUDICATION_SCHEMA
        assert FORBIDDEN_EVIDENCE_KEYS.isdisjoint(packet["evidence"])
        assert "baseline_sa" not in packet
        assert baseline["visible_to_jev"] is False
        request = to_jev_request(packet, baseline)
        validate_request(request)
        validate_factory_request(request, source_dxf=source.dxf_path, known_handles=source.known_handles())
        assert request["baseline_sa"]["value"] in {"19/55", "855.22"}
        evidence_json = json.dumps(packet["evidence"])
        assert "sa_value" not in evidence_json
        assert "baseline_sa" not in evidence_json
        assert packet["case_id"] == row["case_id"]
        assert packet["evidence_bytes"] < 16000
        assert any(c.get("expected_choice") == "INSUFFICIENT" for c in packet["controls"])


def test_l410_adjudication_is_convention_undetermined(tmp_path: Path) -> None:
    source = DxfParserCadSource(_dxf_pil_laj(tmp_path))
    snap = _snapshot()
    audit = run_factory(
        snapshot=snap, source=source, classes=["LAJ"], items=["L410"],
        identity_base={"project_id": "proj-test", "pavimento": "13_PAV"},
    )
    assert audit["cases"][0]["adjudication"]["status"] == "CONVENCAO_INDETERMINADA"
    handles = {row["handle"] for row in audit["cases"][0]["packet"]["evidence"]["direct_elevations"]}
    assert len(handles) >= 2


def test_pil_withdrawal_control_removes_matching_dimension(tmp_path: Path) -> None:
    source = DxfParserCadSource(_dxf_pil_laj(tmp_path))
    snap = _snapshot()
    audit = run_factory(
        snapshot=snap, source=source, classes=["PIL"], items=["P1"],
        identity_base={"project_id": "proj-test", "pavimento": "13_PAV"},
    )
    packet = audit["cases"][0]["packet"]
    full_handles = {row["handle"] for row in packet["evidence"]["dimension_candidates"]}
    control = next(c for c in packet["controls"] if c["id"] == "decisive_dimension_removed")
    ctrl_handles = {row["handle"] for row in control["evidence"]["dimension_candidates"]}
    assert full_handles - ctrl_handles
    assert control["expected_choice"] == "INSUFFICIENT"
    assert control["expected_choice"] not in control["evidence"]


def test_unpackable_when_state_exceeds_limit(tmp_path: Path, monkeypatch) -> None:
    from scripts.arete.jev_calibration import factory as factory_mod

    monkeypatch.setattr(factory_mod, "MAX_STATE_BYTES", 40)
    source = DxfParserCadSource(_dxf_pil_laj(tmp_path))
    snap = _snapshot()
    n1 = snap.get("PIL", "P1")
    from scripts.arete.jev_calibration.adapters_pil import discover_pil
    candidate = discover_pil(n1, source, pavimento="13_PAV")
    emitted = emit_case(candidate, identity_base={"project_id": "p", "pavimento": "13_PAV"},
                        snapshot=snap, source=source, n1_item=n1)
    assert emitted["status"] == "UNPACKABLE"
    assert emitted["reason"] == "STATE_EXCEEDS_16KB"


def test_forbidden_dxf_path_rejected(tmp_path: Path) -> None:
    from scripts.arete.jev_calibration.leakage import assert_source_path_allowed

    bad = tmp_path / "Fase-2_Triagem" / "recortes" / "a.dxf"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"0\nEOF\n")
    with pytest.raises(ValueError):
        assert_source_path_allowed(bad)


def test_manifest_records_mismatch_without_claiming_parity(tmp_path: Path) -> None:
    dxf = _dxf_pil_laj(tmp_path)
    manifest = build_run_manifest(
        project_id="not-the-vps-id", obra="Obra_TREINO_1", pavimento="13_PAV",
        dxf_path=dxf, n1_source="fixture", n1_fingerprint_sha256="abc",
        command=["pytest"], config={"mode": "test"}, cad_insunits=6,
    )
    assert manifest["jev_api_called"] is False
    assert manifest["local_vs_recorded_vps"]["parity_claimed"] is False
    assert manifest["local_vs_recorded_vps"]["this_run"]["dxf_vs_recorded_vps_sha256"] == "MISMATCH"
    assert manifest["local_vs_recorded_vps"]["this_run"]["project_id_vs_recorded_vps"] == "MISMATCH"
    assert manifest["local_vs_recorded_vps"]["comparison_blocked"] is True


def test_frozen_vps_dxf_copy_hash_is_literal() -> None:
    if not DXF_14_FROZEN.is_file():
        pytest.skip("frozen 14_PAV DXF copy absent")
    digest = sha256_file(DXF_14_FROZEN)
    recorded = FROZEN_VPS_14PAV["source_dxf_sha256"]
    comparison = local_vs_vps(dxf_sha256=digest, project_id=FROZEN_VPS_14PAV["project_id"],
                              n1_fingerprint=None, estado_path=ESTADO_14 if ESTADO_14.is_file() else None)
    assert comparison["frozen_vps_dxf_copy"]["matches_recorded_hash"] in {"MATCH", "MISMATCH"}
    if digest == recorded:
        assert comparison["this_run"]["dxf_vs_recorded_vps_sha256"] == "MATCH"
    else:
        assert comparison["this_run"]["dxf_vs_recorded_vps_sha256"] == "MISMATCH"
    assert comparison["parity_claimed"] is False


def test_import_known_marks_l410_convention(tmp_path: Path) -> None:
    summary = import_known_corpus(tmp_path)
    lines = (tmp_path / "adjudication.jsonl").read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(lines[0])
    assert row["status"] == "CONVENCAO_INDETERMINADA"
    packet = json.loads((tmp_path / "source_packet.jsonl").read_text(encoding="utf-8").splitlines()[0])
    validate_request(to_jev_request(packet, json.loads((tmp_path / "baseline.jsonl").read_text().splitlines()[0])))
    assert summary["l410_example"]["case_id"].endswith("imported_example")


def test_session_index_b3_path(tmp_path: Path) -> None:
    import sqlite3

    dxf = _dxf_pil_laj(tmp_path)
    db = tmp_path / "fixture.vision"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, work_name TEXT);
        CREATE TABLE slabs (id INTEGER PRIMARY KEY, project_id TEXT, name TEXT, id_item INTEGER,
            is_validated INTEGER, type TEXT, area REAL, points_json TEXT, links_json TEXT,
            validated_fields_json TEXT, validated_link_classes_json TEXT, na_fields_json TEXT, issues_json TEXT);
        CREATE TABLE pillars (id INTEGER PRIMARY KEY, project_id TEXT, name TEXT, id_item INTEGER,
            is_validated INTEGER, type TEXT, area REAL, points_json TEXT, sides_data_json TEXT, links_json TEXT,
            validated_fields_json TEXT, validated_link_classes_json TEXT, na_fields_json TEXT, issues_json TEXT);
        CREATE TABLE beams (id INTEGER PRIMARY KEY, project_id TEXT, name TEXT, id_item INTEGER,
            is_validated INTEGER, data_json TEXT, sides_data_json TEXT, links_json TEXT,
            validated_fields_json TEXT, validated_link_classes_json TEXT, na_fields_json TEXT, issues_json TEXT);
        """
    )
    con.execute("INSERT INTO projects VALUES ('proj-1','13_TEST','Obra_TEST')")
    con.commit()
    con.close()
    idx_dir = tmp_path / "index"
    build_index("proj-1", idx_dir, db_path=db, pav_dxf=dxf, include_b1=False)
    idx = SessionIndex(idx_dir, skip_stale_check=True)
    from scripts.arete.jev_calibration.cad_source import SessionIndexCadSource
    source = SessionIndexCadSource(idx)
    labels = source.texts_with_value("L410")
    idx.close()
    assert labels and labels[0].text == "L410"


def test_dry_run_writer_separates_files(tmp_path: Path) -> None:
    source = DxfParserCadSource(_dxf_pil_laj(tmp_path))
    snap = _snapshot()
    audit = run_factory(
        snapshot=snap, source=source, classes=["PIL", "LAJ"], items=["P1", "L410"],
        identity_base={"project_id": "proj-test", "pavimento": "13_PAV"},
    )
    manifest = build_run_manifest(
        project_id="proj-test", obra=None, pavimento="13_PAV", dxf_path=source.dxf_path,
        n1_source="fixture", n1_fingerprint_sha256="fp", command=["test"], config={},
    )
    paths = write_dry_run(tmp_path / "out", audit, manifest)
    assert Path(paths["source_packet"]).is_file()
    assert Path(paths["baseline"]).is_file()
    assert Path(paths["adjudication"]).is_file()
    from scripts.arete.jev_calibration.filenames import assert_visible_request_files
    visible = assert_visible_request_files(tmp_path / "out", audit["packed"])
    assert len(visible) == audit["packed"]
    with pytest.raises(FileExistsError):
        write_dry_run(tmp_path / "out", audit, manifest)


def test_discards_are_counted(tmp_path: Path) -> None:
    source = DxfParserCadSource(_dxf_pil_laj(tmp_path))
    snap = _snapshot()
    audit = run_factory(
        snapshot=snap, source=source, classes=["PIL", "XX"], items=["P99"],
        identity_base={"project_id": "proj-test", "pavimento": "13_PAV"},
    )
    assert audit["packed"] == 0
    assert "ITEM_ABSENT_IN_SNAPSHOT" in audit["discard_reasons"] or "CLASS_NOT_IN_PHASE1" in audit["discard_reasons"]


def test_safe_filename_rejects_colon_and_reserved() -> None:
    from scripts.arete.jev_calibration.filenames import request_filename, safe_filename

    name = request_filename(1, "13_PAV|PIL|P20|dim|contour:1C29")
    assert ":" not in name
    assert name.endswith(".json")
    assert name.startswith("01_")
    assert safe_filename("CON") == "case_CON.json"


def test_write_dry_run_windows_visible_json(tmp_path: Path) -> None:
    from scripts.arete.jev_calibration.filenames import assert_visible_request_files, list_visible_json

    source = DxfParserCadSource(_dxf_pil_laj(tmp_path))
    snap = _snapshot()
    audit = run_factory(
        snapshot=snap, source=source, classes=["PIL", "LAJ"], items=["P1", "L410"],
        identity_base={"project_id": "proj-test", "pavimento": "13_PAV"},
    )
    assert audit["packed"] >= 1
    assert any(":" in row["case_id"] for row in audit["cases"])
    out = tmp_path / "windows_out"
    manifest = build_run_manifest(
        project_id="proj-test", obra=None, pavimento="13_PAV", dxf_path=source.dxf_path,
        n1_source="fixture", n1_fingerprint_sha256="fp", command=["test"], config={},
    )
    write_dry_run(out, audit, manifest)
    visible = assert_visible_request_files(out, audit["packed"])
    assert list_visible_json(out / "jev_requests") == visible
    for path in visible:
        assert path.suffix == ".json"
        assert path.stat().st_size > 0
        assert ":" not in path.name
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_request(payload)
        assert payload["case_id"] in {row["case_id"] for row in audit["cases"]}
    leftovers = [p.name for p in (out / "jev_requests").iterdir() if p.is_file() and p.suffix.lower() != ".json"]
    assert leftovers == []


def test_pil_unverified_nearby_line_is_needs_source(tmp_path: Path) -> None:
    source = DxfParserCadSource(_dxf_pil_laj(tmp_path))
    p2 = N1Item(
        classe="PIL", name="P2",
        points=[[290, 290], [310, 290], [310, 330], [290, 330], [290, 290]],
        sa_value="20/60", sa_field="dim", snapshot_hash="p2hash",
        extras={"bbox": [290, 290, 310, 330], "center": [300, 310]},
    )
    snap = N1Snapshot(
        project_id="proj-test", pavimento="13_PAV", source="fixture",
        fingerprint_sha256="fp-test", items={("PIL", "P2"): p2},
    )
    audit = run_factory(
        snapshot=snap, source=source, classes=["PIL"], items=["P2"],
        identity_base={"project_id": "proj-test", "pavimento": "13_PAV"},
    )
    assert audit["packed"] == 0
    assert audit["unpackable_reasons"].get("NEEDS_SOURCE") == 1
    assert audit["unpackable_rows"][0]["detail"] == "no_closed_dxf_loop_contains_label"


def test_pil_contour_ref_is_verified_loop_not_nearest_line(tmp_path: Path) -> None:
    source = DxfParserCadSource(_dxf_pil_laj(tmp_path))
    snap = _snapshot()
    audit = run_factory(
        snapshot=snap, source=source, classes=["PIL"], items=["P1"],
        identity_base={"project_id": "proj-test", "pavimento": "13_PAV"},
    )
    contour = audit["cases"][0]["packet"]["evidence"]["contour_ref"]
    assert contour["role"] == "verified_closed_polyline_containing_label"
    assert contour["closed"] is True
    assert contour["role"] != "nearest_dxf_polyline"


@pytest.mark.skipif(not (DB.is_file() and DXF_13.is_file()), reason="13_PAV Fase-1 DXF or DB absent")
def test_smoke_13pav_few_items_readonly(tmp_path: Path) -> None:
    from scripts.arete.jev_calibration.n1_snapshot import load_snapshot_from_db

    source = DxfParserCadSource(DXF_13)
    snap = load_snapshot_from_db(DB, PROJECT_13, "13_PAV")
    names = [name for name in ("P20", "P1") if snap.get("PIL", name)]
    assert "P20" in names
    audit = run_factory(
        snapshot=snap, source=source, classes=["PIL"], items=names,
        identity_base={"project_id": PROJECT_13, "pavimento": "13_PAV", "obra": "Obra_TREINO_1"},
    )
    assert audit["scanned"] == len(names)
    assert audit["packed"] + audit["discarded"] + audit["unpackable"] == audit["scanned"]
    for row in audit["cases"]:
        validate_request(row["jev_request"])
        assert row["packet"]["evidence"]["contour_ref"]["role"] == "verified_closed_polyline_containing_label"
    manifest = build_run_manifest(
        project_id=PROJECT_13, obra="Obra_TREINO_1", pavimento="13_PAV", dxf_path=DXF_13,
        n1_source=snap.source, n1_fingerprint_sha256=snap.fingerprint_sha256,
        command=["pytest"], config={"mode": "smoke-13"},
    )
    write_dry_run(tmp_path / "smoke13", audit, manifest)
    from scripts.arete.jev_calibration.filenames import assert_visible_request_files
    assert_visible_request_files(tmp_path / "smoke13", audit["packed"])


@pytest.mark.skipif(not (DXF_14_FROZEN.is_file() and ESTADO_14.is_file()), reason="frozen 14_PAV source absent")
def test_smoke_14pav_l410_frozen_source(tmp_path: Path) -> None:
    from scripts.arete.jev_calibration.n1_snapshot import load_snapshot_from_estado

    digest = sha256_file(DXF_14_FROZEN)
    source = DxfParserCadSource(DXF_14_FROZEN)
    snap = load_snapshot_from_estado(ESTADO_14, FROZEN_VPS_14PAV["project_id"], "14_PAV")
    audit = run_factory(
        snapshot=snap, source=source, classes=["LAJ"], items=["L410"],
        identity_base={"project_id": FROZEN_VPS_14PAV["project_id"], "pavimento": "14_PAV"},
    )
    assert audit["scanned"] == 1
    if digest != FROZEN_VPS_14PAV["source_dxf_sha256"]:
        pytest.skip("frozen DXF copy hash differs from recorded VPS hash; factory still ran locally")
    assert audit["packed"] == 1
    row = audit["cases"][0]
    assert row["adjudication"]["status"] == "CONVENCAO_INDETERMINADA"
    validate_factory_request(row["jev_request"], source_dxf=DXF_14_FROZEN, known_handles=source.known_handles())
    manifest = build_run_manifest(
        project_id=FROZEN_VPS_14PAV["project_id"], obra=None, pavimento="14_PAV",
        dxf_path=DXF_14_FROZEN, n1_source=snap.source,
        n1_fingerprint_sha256=snap.fingerprint_sha256, command=["pytest"], config={"mode": "smoke-14"},
        estado_path=ESTADO_14,
    )
    write_dry_run(tmp_path / "smoke14", audit, manifest)
    from scripts.arete.jev_calibration.filenames import assert_visible_request_files
    files = assert_visible_request_files(tmp_path / "smoke14", 1)
    assert files[0].stat().st_size > 0
    assert ":" not in files[0].name
