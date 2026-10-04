"""G3 batch runner for valid packets. Reuses jev_sa_second_read; never writes N1/QA."""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.arete.jev_sa_second_read import MODEL, run as jev_run, validate_request, verify_source_dxf

from .catalog_v1 import CATALOG, catalog_hash, lv_diagnostics
from .corpus import write_json
from .filenames import list_visible_json, safe_filename
from .hashing import sha256_file, sha256_json
from .leakage import validate_factory_request
from .schemas import BATCH_SCHEMA, CACHE_SCHEMA, CATALOG_REVISION, JEV_MODEL

WITHDRAWAL_IDS = {
    "nearby_lines_removed",
    "decisive_dimension_removed",
    "target_elevation_removed",
    "local_markers_removed",
    "contour_removed",
    "own_stretch_removed",
}
SECRET_RE = re.compile(r"(api[_-]?key|token|bearer|authorization)\s*[=:]\s*\S+", re.I)


def sanitize_error(exc: BaseException) -> str:
    text = SECRET_RE.sub(r"\1=<redacted>", f"{type(exc).__name__}: {exc}")
    return text[:800]


def api_payload(request: dict) -> dict[str, Any]:
    """Fragment sent as Jev state/questions. Baseline and expected labels stay out."""
    controls = []
    for control in request.get("controls") or []:
        controls.append({
            "id": control["id"],
            "evidence": control["evidence"],
        })
    return {
        "question": request["question"],
        "evidence": request["evidence"],
        "controls": controls,
        "companion_questions": request.get("companion_questions") or {},
    }


def cache_key(*, source_dxf_sha256: str, request: dict, model: str, catalog_sha256: str) -> str:
    return sha256_json({
        "source_dxf_sha256": source_dxf_sha256,
        "api_payload_sha256": sha256_json(api_payload(request)),
        "model": model,
        "catalog_sha256": catalog_sha256,
    })


def load_request(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def attach_choice_diagnostics(request: dict) -> dict:
    """Optional Noul/Score companions. Recorded separately; they do not vote."""
    out = copy.deepcopy(request)
    if out["identity"].get("classe") != "LV":
        return out
    spec = lv_diagnostics()
    companions = dict(out.get("companion_questions") or {})
    if spec.get("noul") and "unique_parallel_pair" not in companions:
        noul = spec["noul"]
        companions["unique_parallel_pair"] = {
            "type": "noul",
            "instructions": noul["instructions"],
            "criteria": noul["criteria"],
        }
    if spec.get("score") and "endpoint_support" not in companions:
        score = spec["score"]
        companions["endpoint_support"] = {
            "type": "score",
            "instructions": score["instructions"],
            "criteria": score["criteria"],
        }
    if companions:
        out["companion_questions"] = companions
    return out


def pilot_request(request: dict) -> dict:
    """Keep Choice + one withdrawal control so a case costs two API calls."""
    out = copy.deepcopy(request)
    withdrawal = [c for c in out.get("controls") or [] if c.get("id") in WITHDRAWAL_IDS]
    if not withdrawal:
        withdrawal = list(out.get("controls") or [])[:1]
    out["controls"] = withdrawal[:1]
    return out


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def read_cache(cache_dir: Path | None, key: str) -> dict | None:
    if cache_dir is None:
        return None
    path = _cache_path(cache_dir, key)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != CACHE_SCHEMA:
        return None
    return payload


def write_cache(cache_dir: Path, key: str, payload: dict) -> Path | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, key)
    if path.exists():
        return path
    write_json(path, payload)
    return path


def _call_count(request: dict) -> int:
    return 1 + len(request.get("controls") or [])


def run_batch(*, requests_dir: Path, source_dxf: Path, out_dir: Path,
              execute: bool = False, max_cases: int = 2, max_calls: int = 4,
              cache_dir: Path | None = None, diagnostics: bool = False,
              jev_run_fn: Callable[[dict], dict] | None = None) -> dict[str, Any]:
    if max_cases < 1 or max_calls < 1:
        raise ValueError("max_cases and max_calls must be positive")
    source_dxf = Path(source_dxf)
    source_sha = sha256_file(source_dxf)
    cat_sha = catalog_hash()
    files = list_visible_json(Path(requests_dir))
    prepared: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for path in files:
        try:
            request = load_request(path)
            if diagnostics:
                request = attach_choice_diagnostics(request)
            request = pilot_request(request)
            validate_factory_request(request, source_dxf=source_dxf)
            verify_source_dxf(source_dxf, request["identity"]["source_dxf_sha256"])
            if request["identity"]["source_dxf_sha256"].lower() != source_sha.lower():
                raise ValueError("request identity source_dxf_sha256 differs from --source-dxf")
            payload = api_payload(request)
            if "baseline_sa" in payload or any("expected_choice" in c for c in payload["controls"]):
                raise ValueError("API payload leaked baseline or expected_choice")
            key = cache_key(source_dxf_sha256=source_sha, request=request,
                            model=JEV_MODEL, catalog_sha256=cat_sha)
            prepared.append({
                "path": str(path),
                "case_id": request.get("case_id"),
                "identity": request["identity"],
                "request": request,
                "cache_key": key,
                "calls_if_executed": _call_count(request),
                "cached": read_cache(cache_dir, key) is not None,
            })
        except Exception as exc:
            rejected.append({"path": str(path), "status": "REJECTED",
                             "reason": sanitize_error(exc)})

    selected: list[dict[str, Any]] = []
    skipped_cap: list[dict[str, Any]] = []
    for row in prepared:
        if len(selected) >= max_cases:
            skipped_cap.append({
                "path": row["path"], "case_id": row["case_id"],
                "reason": "cap_max_cases_or_calls",
            })
            continue
        selected.append(row)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sidecar_dir = out_dir / "jev_results"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    calls_reserved = 0
    calls_completed = 0
    calls_actual_unknown = 0
    cache_hits = 0
    technical = 0
    runner = jev_run_fn or jev_run

    for index, row in enumerate(selected, 1):
        cost = int(row["calls_if_executed"])
        record = {
            "case_id": row["case_id"],
            "path": row["path"],
            "cache_key": row["cache_key"],
            "calls_planned": cost,
            "identity": row["identity"],
        }
        if not execute:
            record["status"] = "DRY_RUN_ELIGIBLE"
            record["jev_api_called"] = False
            results.append(record)
            continue
        cached = read_cache(cache_dir, row["cache_key"])
        if cached:
            cache_hits += 1
            dest = sidecar_dir / safe_filename(f"{index:02d}_{row['case_id']}_cached", suffix=".json")
            if not dest.exists():
                write_json(dest, cached["result"])
            record.update({
                "status": "CACHE_HIT",
                "jev_api_called": False,
                "sidecar": str(dest),
                "choice": (cached.get("result") or {}).get("results", [{}])[0].get("choice"),
                "calls_reserved": 0,
                "calls_completed": 0,
            })
            results.append(record)
            continue
        if calls_reserved + cost > max_calls:
            record["status"] = "SKIPPED_CAP"
            record["jev_api_called"] = False
            record["reason"] = "cap_max_cases_or_calls"
            results.append(record)
            skipped_cap.append({
                "path": row["path"], "case_id": row["case_id"],
                "reason": "cap_max_cases_or_calls",
            })
            continue
        sidecar = sidecar_dir / safe_filename(f"{index:02d}_{row['case_id']}_result", suffix=".json")
        if sidecar.exists():
            record.update({"status": "SIDECAR_EXISTS", "jev_api_called": False,
                           "sidecar": str(sidecar)})
            results.append(record)
            continue
        calls_reserved += cost
        record["calls_reserved"] = cost
        try:
            result = runner(row["request"])
            completed = len(result.get("results") or [])
            calls_completed += completed
            write_json(sidecar, result)
            if cache_dir is not None:
                write_cache(cache_dir, row["cache_key"], {
                    "schema": CACHE_SCHEMA,
                    "cache_key": row["cache_key"],
                    "model": MODEL,
                    "catalog_revision": CATALOG_REVISION,
                    "catalog_sha256": cat_sha,
                    "source_dxf_sha256": source_sha,
                    "api_payload_sha256": sha256_json(api_payload(row["request"])),
                    "result": result,
                })
            record.update({
                "status": "RECORDED",
                "jev_api_called": True,
                "sidecar": str(sidecar),
                "choice": (result.get("results") or [{}])[0].get("choice"),
                "decision": result.get("decision"),
                "calls_completed": completed,
                "calls_actual_unknown": False,
            })
        except Exception as exc:
            technical += 1
            calls_actual_unknown += cost
            fail_path = sidecar_dir / safe_filename(
                f"{index:02d}_{row['case_id']}_technical_error", suffix=".json")
            payload = {
                "schema": "jev_calibration_technical_error/1",
                "status": "TECHNICAL_ERROR",
                "case_id": row["case_id"],
                "identity": row["identity"],
                "error": sanitize_error(exc),
                "affects_qa_or_n1": False,
                "calls_reserved": cost,
                "calls_completed": None,
                "calls_actual_unknown": True,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            if not fail_path.exists():
                write_json(fail_path, payload)
            record.update({
                "status": "TECHNICAL_ERROR",
                "jev_api_called": True,
                "jev_api_attempted": True,
                "sidecar": str(fail_path),
                "error": payload["error"],
                "affects_qa_or_n1": False,
                "calls_completed": None,
                "calls_actual_unknown": True,
            })
        results.append(record)

    summary = {
        "schema": BATCH_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_revision": CATALOG_REVISION,
        "catalog_sha256": cat_sha,
        "model": JEV_MODEL,
        "source_dxf": str(source_dxf),
        "source_dxf_sha256": source_sha,
        "execute": execute,
        "max_cases": max_cases,
        "max_calls": max_calls,
        "diagnostics": diagnostics,
        "found_requests": len(files),
        "eligible": len(prepared),
        "rejected": rejected,
        "selected": len(selected),
        "skipped_cap": skipped_cap,
        "results": results,
        "calls_reserved": calls_reserved,
        "calls_completed": calls_completed,
        "calls_made": calls_completed,
        "calls_actual_unknown": calls_actual_unknown,
        "cache_hits": cache_hits,
        "technical_errors": technical,
        "jev_api_attempted": bool(execute and calls_reserved > 0),
        "jev_api_called": bool(execute and calls_completed > 0),
        "affects_qa_or_n1": False,
        "catalog_classes": sorted(CATALOG["classes"]),
    }
    write_json(out_dir / "batch_run.json", summary)
    return summary
