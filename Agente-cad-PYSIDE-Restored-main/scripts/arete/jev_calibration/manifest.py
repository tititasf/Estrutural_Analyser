"""G0 run manifesto and local-versus-recorded-VPS provenance. No live VPS calls."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .hashing import sha256_file, sha256_json
from .schemas import (
    CATALOG_REVISION,
    EXECUTED_MODULE_RELS,
    FACTORY_VERSION,
    FROZEN_VPS_14PAV,
    JEV_MODEL,
    MODULE_COMPARE_PAIRS,
    RECORDED_LOCAL_14PAV_DIVERGENT,
    REPO_ROOT,
    RUN_MANIFEST_SCHEMA,
    VPS_PARITY_DIR,
)


def _rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(Path(path).resolve())


def _hash_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"path": _rel(path), "status": "ABSENT"}
    return {"path": _rel(path), "status": "PRESENT", "sha256": sha256_file(path), "bytes": path.stat().st_size}


def compare_hashes(local: str | None, recorded: str | None) -> str:
    if not local or not recorded:
        return "ABSENT"
    return "MATCH" if local.lower() == recorded.lower() else "MISMATCH"


def local_vs_vps(*, dxf_sha256: str | None, project_id: str | None,
                 n1_fingerprint: str | None, estado_path: Path | None = None) -> dict[str, Any]:
    frozen_dxf = REPO_ROOT / FROZEN_VPS_14PAV["frozen_dxf_relpath"]
    frozen_estado = REPO_ROOT / FROZEN_VPS_14PAV["frozen_estado_relpath"]
    frozen_dxf_now = sha256_file(frozen_dxf) if frozen_dxf.is_file() else None
    frozen_estado_now = sha256_file(frozen_estado) if frozen_estado.is_file() else None
    estado_now = sha256_file(estado_path) if estado_path and estado_path.is_file() else None
    modules = []
    for local_rel, vps_rel in MODULE_COMPARE_PAIRS:
        local = _hash_if_exists(REPO_ROOT / local_rel)
        recorded = _hash_if_exists(REPO_ROOT / vps_rel)
        modules.append({
            "local": local,
            "vps_copy": recorded,
            "comparison": compare_hashes(local.get("sha256"), recorded.get("sha256")),
        })
    dxf_vs_recorded_vps = compare_hashes(dxf_sha256, FROZEN_VPS_14PAV["source_dxf_sha256"])
    dxf_vs_frozen_copy = compare_hashes(dxf_sha256, frozen_dxf_now)
    project_vs_vps = compare_hashes(project_id, FROZEN_VPS_14PAV["project_id"])
    estado_vs_recorded = compare_hashes(estado_now or n1_fingerprint, FROZEN_VPS_14PAV["estado_sha256"])
    module_mismatch = any(row["comparison"] == "MISMATCH" for row in modules)
    any_mismatch = any(status == "MISMATCH" for status in (
        dxf_vs_recorded_vps, project_vs_vps, estado_vs_recorded,
    )) or module_mismatch
    return {
        "recorded_vps_14pav": FROZEN_VPS_14PAV,
        "recorded_local_divergent_14pav": RECORDED_LOCAL_14PAV_DIVERGENT,
        "frozen_vps_dxf_copy": {"path": _rel(frozen_dxf), "sha256": frozen_dxf_now,
                                "matches_recorded_hash": compare_hashes(frozen_dxf_now, FROZEN_VPS_14PAV["source_dxf_sha256"])},
        "frozen_vps_estado_copy": {"path": _rel(frozen_estado), "sha256": frozen_estado_now,
                                   "matches_recorded_hash": compare_hashes(frozen_estado_now, FROZEN_VPS_14PAV["estado_sha256"])},
        "this_run": {
            "dxf_vs_recorded_vps_sha256": dxf_vs_recorded_vps,
            "dxf_vs_frozen_vps_copy": dxf_vs_frozen_copy,
            "project_id_vs_recorded_vps": project_vs_vps,
            "n1_or_estado_vs_recorded_vps": estado_vs_recorded,
            "sa_modules_vs_vps_copies": modules,
        },
        "parity_claimed": False,
        "comparison_blocked": any_mismatch,
        "note": ("Hashes are compared to the frozen 25/09 VPS record and its local copies. "
                 "MISMATCH blocks treating this run as the productive 14_PAV identity. "
                 "This check does not contact the VPS."),
    }


def build_run_manifest(*, project_id: str, obra: str | None, pavimento: str,
                       dxf_path: Path, n1_source: str, n1_fingerprint_sha256: str,
                       command: list[str], config: dict[str, Any],
                       qa_manifest_path: Path | None = None,
                       svg_path: Path | None = None,
                       db_path: Path | None = None,
                       estado_path: Path | None = None,
                       cad_insunits: int | None = None) -> dict[str, Any]:
    dxf_path = Path(dxf_path)
    dxf_info = _hash_if_exists(dxf_path)
    executed = {rel: _hash_if_exists(REPO_ROOT / rel) for rel in EXECUTED_MODULE_RELS}
    qa_info = _hash_if_exists(qa_manifest_path) if qa_manifest_path else {"status": "NOT_PROVIDED"}
    svg_info = _hash_if_exists(svg_path) if svg_path else {"status": "NOT_PROVIDED"}
    comparison = local_vs_vps(
        dxf_sha256=dxf_info.get("sha256"),
        project_id=project_id,
        n1_fingerprint=n1_fingerprint_sha256,
        estado_path=estado_path,
    )
    manifest = {
        "schema": RUN_MANIFEST_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "factory_version": FACTORY_VERSION,
        "catalog_revision": CATALOG_REVISION,
        "jev_model_recorded": JEV_MODEL,
        "jev_api_called": False,
        "command": command,
        "config": config,
        "identity": {
            "project_id": project_id,
            "obra": obra,
            "pavimento": pavimento,
        },
        "source_dxf": dxf_info,
        "derived_svg": svg_info,
        "n1_snapshot": {
            "source": n1_source,
            "fingerprint_sha256": n1_fingerprint_sha256,
            "db_path": str(db_path) if db_path else None,
        },
        "qa_manifest": qa_info,
        "modules_executed_this_phase": executed,
        "cad_units": {
            "insunits": cad_insunits,
            "note": "Numeric lengths follow the drawing practice of the obra; $INSUNITS is recorded, not assumed.",
        },
        "geometric_convention": "source coordinates are raw DXF drawing units; no CSS/SVG scale",
        "local_vs_recorded_vps": comparison,
        "write_policy": "read-only DXF/DB; new sidecars only under scripts/arete/relatorios",
    }
    manifest["manifest_sha256"] = sha256_json({k: v for k, v in manifest.items() if k != "manifest_sha256"})
    return manifest


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))
