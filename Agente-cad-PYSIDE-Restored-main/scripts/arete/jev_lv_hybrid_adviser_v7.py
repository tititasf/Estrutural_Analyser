"""Bounded Jev adviser check on two distinct v6 LV wall disagreements.

Read-only with respect to N1/DXF. Frozen v6 selects walls; Jev sees only local
source DXF geometry. Results are advisory and never update SA/QA automatically.
"""
from __future__ import annotations

import argparse
import copy
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.arete.jev_calibration.adapters_lv_v6 import run_v6, scan_v6_leakage
from scripts.arete.jev_calibration.adapters_lv_v5 import PAVEMENT_SPECS, _entity_row
from scripts.arete.jev_calibration.cad_source import DxfParserCadSource
from scripts.arete.jev_calibration.hashing import sha256_json
from scripts.arete.jev_calibration.runner import api_payload, sanitize_error
from scripts.arete.jev_sa_second_read import MODEL, run as jev_run, validate_request, verify_source_dxf


REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "scripts" / "arete" / "relatorios" / "20260930_jev_lv_hybrid_adviser_v7"
WALLS = ("14_PAV|LV|V409|wall|2CC|A", "14_PAV|LV|V420|wall|2F6|A")
MAX_CALLS = 4  # full + withdrawal for each of two different beams


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _enrich(request: dict, source: DxfParserCadSource) -> dict:
    req = copy.deepcopy(request)
    ev = req["evidence"]
    ev["wall"] = _entity_row(source, ev["wall"]["handle"], {"role": "listed_wall"})
    if ev.get("partner"):
        ev["partner"] = _entity_row(source, ev["partner"]["handle"], {"role": "listed_partner"})
    if ev.get("beam_label"):
        ev["beam_label"] = _entity_row(source, ev["beam_label"]["handle"], {"role": "listed_label"})
    for end in ev["endpoints"]:
        for field, role in (("listed_gaps", "listed_gap"),
                            ("listed_colinear_continuations", "listed_continuation")):
            end[field] = [_entity_row(source, row["handle"], {"role": role}) for row in end[field]]
    ctrl = copy.deepcopy(ev)
    for end in ctrl["endpoints"]:
        end["listed_gaps"] = []
        end["listed_pillar_markers"] = []
        end["listed_colinear_continuations"] = []
    req["controls"][0]["evidence"] = ctrl
    req["question"]["instructions"] += (
        " Verify the coordinates and points of the listed source entities at "
        "each endpoint; a handle's presence alone does not prove contact. "
        "If endpoint contact is not established by listed coordinates, choose INSUFFICIENT."
    )
    validate_request(req)
    payload = api_payload(req)
    problems = scan_v6_leakage(payload)
    if problems:
        raise ValueError("Jev payload leakage: " + "; ".join(problems))
    return req


def run(*, execute: bool, out: Path = OUT) -> dict:
    audit = run_v6()
    packed = [p for pav in audit["pavements"].values() for p in pav["packed_requests"]]
    by_id = {p["wall_id"]: p for p in packed}
    if not set(WALLS).issubset(by_id):
        raise ValueError("Frozen v6 selected walls changed; abort")
    source = DxfParserCadSource(PAVEMENT_SPECS["14_PAV"]["dxf"])
    verify_source_dxf(PAVEMENT_SPECS["14_PAV"]["dxf"], PAVEMENT_SPECS["14_PAV"]["expected_dxf_sha256"])
    requests = []
    for wall_id in WALLS:
        req = _enrich(by_id[wall_id]["v1_request"], source)
        requests.append({"wall_id": wall_id, "request": req,
                         "request_sha256": sha256_json(req),
                         "payload_sha256": sha256_json(api_payload(req))})
    freeze = {
        "schema": "jev_lv_hybrid_adviser_freeze/v7",
        "source_dxf_sha256": source.dxf_sha256,
        "source_inventory_sha256": audit["pavements"]["14_PAV"]["inventory_sha256"],
        "v6_run_sha256": sha256_json(audit),
        "model": MODEL,
        "selected_wall_ids": list(WALLS),
        "requests": [{k: v for k, v in p.items() if k != "request"} for p in requests],
        "n1_in_payload": False,
        "max_calls": MAX_CALLS,
    }
    freeze["freeze_sha256"] = sha256_json(freeze)
    _write(out / "freeze.json", freeze)
    for index, case in enumerate(requests, 1):
        _write(out / "requests" / f"{index:02d}.json", case["request"])

    results = []
    calls = 0
    for index, case in enumerate(requests, 1):
        cache = out / "cache" / f"{case['payload_sha256']}.json"
        if cache.exists():
            result = json.loads(cache.read_text(encoding="utf-8"))
            result["cache_hit"] = True
        elif not execute:
            result = {"status": "FROZEN_NOT_EXECUTED", "calls": 0, "cache_hit": False}
        elif calls + 2 > MAX_CALLS:
            result = {"status": "SKIPPED_CAP", "calls": 0, "cache_hit": False}
        else:
            started = time.perf_counter()
            try:
                raw = jev_run(case["request"])
                result = {"status": "RECORDED", "calls": 2, "cache_hit": False,
                          "wall_elapsed_s": round(time.perf_counter() - started, 3),
                          "model": raw.get("model"), "results": raw.get("results"),
                          "error": None}
                calls += 2
            except Exception as exc:
                result = {"status": "TECHNICAL_ERROR", "calls": 0, "cache_hit": False,
                          "wall_elapsed_s": round(time.perf_counter() - started, 3),
                          "results": [], "error": sanitize_error(exc)}
            _write(cache, result)
        results.append({"wall_id": case["wall_id"], "request_sha256": case["request_sha256"], **result})
    status = {"schema": "jev_lv_hybrid_adviser_status/v7",
              "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "execute": execute, "api_calls_new": calls,
              "results": results, "benefit_claimed": False,
              "accuracy_claimed": False, "parity_claimed": False,
              "n1_changed": False, "qa_changed": False}
    _write(out / "STATUS.json", status)
    lines = ["# Jev adviser v7: local geometry on two LV wall disagreements", "",
             "Frozen 14_PAV regression; two distinct beam names. Jev receives source DXF",
             "geometry only, with full and fact-withdrawal control. No N1/QA mutation.", "",
             f"Freeze SHA: `{freeze['freeze_sha256']}`; new API calls: **{calls}/{MAX_CALLS}**.", "",
             "| Wall | Full | Control | Status |", "|---|---|---|---|"]
    for rec in results:
        choices = {r.get("variant"): r.get("choice") for r in rec.get("results") or []}
        lines.append(f"| `{rec['wall_id']}` | {choices.get('full')} | "
                     f"{choices.get('endpoint_facts_removed')} | {rec['status']} |")
    lines += ["", "Choices corroborate or challenge the source hypothesis; they are not",
              "ground truth or proof of SA improvement. Independent adjudication is absent.",
              "See ANALISE.md, when present, for subsequent visual inspection and semantic limits.",
              "The v6 wall-level N1 set comparison remains a separate sidecar.", ""]
    (out / "RELATORIO.md").write_text("\n".join(lines), encoding="utf-8")
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    status = run(execute=args.execute)
    print(json.dumps({"api_calls_new": status["api_calls_new"],
                      "statuses": [r["status"] for r in status["results"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
