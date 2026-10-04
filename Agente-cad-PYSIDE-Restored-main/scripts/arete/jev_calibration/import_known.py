"""Read-only import of already published Jev/SA reports into the G0 corpus."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.arete.jev_sa_second_read import validate_request

from .corpus import adjudication_record, append_jsonl, baseline_record, source_packet_record
from .hashing import sha256_file
from .schemas import CATALOG_REVISION, REPO_ROOT, VPS_PARITY_DIR


def import_l410_example(out_dir: Path) -> dict:
    example = REPO_ROOT / "scripts" / "arete" / "examples" / "jev_sa_second_read_l410.json"
    request = json.loads(example.read_text(encoding="utf-8-sig"))
    validate_request(request)
    identity = request["identity"]
    case_id = f"{identity['pavimento']}|{identity['classe']}|{identity['item']}|{identity['campo']}|imported_example"
    packet = source_packet_record(
        case_id, identity,
        {"kind": "region", "source": "imported_example"},
        request["question"], request["evidence"], request["controls"],
        included=list(request["evidence"].get("direct_elevations") or []),
        excluded=[], catalog_revision=CATALOG_REVISION,
    )
    baseline = baseline_record(
        case_id, identity, sa_value=request["baseline_sa"].get("value"),
        sa_field=identity["campo"], router_trigger="imported_l410_example",
        cad_rules=["imported helper example; SA stays in baseline"],
    )
    adj = adjudication_record(
        case_id, identity, status="CONVENCAO_INDETERMINADA",
        handles=["DAD", "CB5", "DC7", "E5C", "128"],
        png_relpath="scripts/arete/relatorios/20260924_jev_14pav/vps_parity/visual/L410_source_full.png",
        convention="desnivel_laje",
        notes="Graphic regions are distinct; the desnivel convention is not proven. Accuracy metric excludes this case.",
        agents=["imported_report"],
        consensus=False,
    )
    append_jsonl(out_dir / "source_packet.jsonl", [packet])
    append_jsonl(out_dir / "baseline.jsonl", [baseline])
    append_jsonl(out_dir / "adjudication.jsonl", [adj])
    return {"case_id": case_id, "example": str(example), "example_sha256": sha256_file(example)}


def import_vps_physical_audit(out_dir: Path) -> dict | None:
    audit_path = VPS_PARITY_DIR / "l410_physical_audit.json"
    if not audit_path.is_file():
        return None
    payload = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    record = {
        "schema": "jev_calibration_imported_report/1",
        "kind": "physical_audit",
        "path": str(audit_path.as_posix()),
        "sha256": sha256_file(audit_path),
        "caution": payload.get("caution"),
        "handles": [row.get("handle") for row in payload.get("raw_texts") or []],
        "adjudication_status": "CONVENCAO_INDETERMINADA",
    }
    append_jsonl(out_dir / "imported_reports.jsonl", [record])
    return record


def import_known_corpus(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    l410 = import_l410_example(out_dir)
    audit = import_vps_physical_audit(out_dir)
    return {"l410_example": l410, "l410_physical_audit": audit}
