"""Run the v5 blinded single-outcome LV experiment. Does not write N1/DXF/DB."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.arete.jev_calibration.adapters_lv_v5 import (
    MAX_API_CALLS,
    PAVEMENT_SPECS,
    build_selection,
    cache_key_v5,
    execute_frozen,
    freeze_case,
    unblind_n1,
)
from scripts.arete.jev_calibration.cad_source import DxfParserCadSource
from scripts.arete.jev_calibration.catalog_v5 import (
    CATALOG_V5_REVISION,
    FACTORY_V5_VERSION,
    V5_AUDIT_SCHEMA,
    catalog_v5_hash,
)
from scripts.arete.jev_calibration.corpus import write_json
from scripts.arete.jev_calibration.filenames import request_filename
from scripts.arete.jev_calibration.hashing import sha256_json
from scripts.arete.jev_sa_second_read import MODEL
from scripts.arete.jev_calibration.runner import api_payload


def _write_relatorio(out: Path, audit: dict) -> None:
    metrics = audit.get("metrics") or {}
    lines = [
        "# v5 blinded single-outcome LV (Jev × source PARA/PASSA)",
        "",
        f"**Date:** {audit.get('created_at_utc')}. **Model:** `{audit.get('model')}`. "
        f"**Catalog:** `{CATALOG_V5_REVISION}`. **Factory:** `{FACTORY_V5_VERSION}`.",
        "",
        "Jev is an optional independent validator. This run does not replace SA/N1, "
        "does not write the production DB/DXF/JSON/VPS, and does not seal G1/G4. "
        "N2/N3/N4 were not used. Visual geometric correctness is "
        f"**{audit.get('visual_truth_status')}**. Agreement with the deterministic "
        "CAD hypothesis is not claimed as accuracy or as incremental improvement.",
        "",
        "## Sample (source-frozen before N1)",
        "",
        "| encounter_id | pavement | beam | handle | endpoint | source XOR | ownership |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in (audit.get("selection") or {}).get("selected") or []:
        lines.append(
            f"| `{row['encounter_id']}` | {row['pavimento']} | {row['beam']} | "
            f"`{row['wall_handle']}` | {row['endpoint']} | {row['source_behavior']} | "
            f"{row['ownership_why']} |"
        )
    lines += [
        "",
        "## Jev vs CAD hypothesis (not accuracy)",
        "",
        f"- Full-packet agreement with CAD hypothesis: "
        f"**{metrics.get('jev_agrees_cad_n')} / {metrics.get('n_full')}**",
        f"- Full-packet INSUFFICIENT: **{metrics.get('jev_abstain_n')} / {metrics.get('n_full')}**",
        f"- Control chose INSUFFICIENT: **{metrics.get('control_insufficient_n')} / {metrics.get('n_control')}**",
        f"- Control kept CAD label after withdrawal: "
        f"**{metrics.get('control_kept_cad_n')} / {metrics.get('n_control')}**",
        f"- API calls used (including cache hits counted as 0 extra): "
        f"**{metrics.get('calls_used')} / {MAX_API_CALLS}**",
        f"- Technical errors: **{metrics.get('technical_errors')}**",
        "",
        "## N1 sidecar (unblinded after freeze)",
        "",
        "| encounter_id | CAD | Jev full | Jev control | N1 outcomes | N1 would change |",
        "|---|---|---|---|---|---|",
    ]
    for row in audit.get("comparison_rows") or []:
        lines.append(
            f"| `{row['encounter_id']}` | {row.get('cad_choice')} | {row.get('jev_full')} | "
            f"{row.get('jev_control')} | {row.get('n1_outcomes')} | {row.get('n1_field_would_change')} |"
        )
    lines += [
        "",
        "N1 endpoint-level agreement: **NOT MEASURABLE** from these locators. "
        "The same wall locator can occur in PARA and PASSA at opposite ends. "
        "The N1 outcomes above describe a wall, not a specific encounter.",
        "",
        "## API / cost",
        "",
        f"- Model: `{audit.get('model')}`",
        f"- Median latency_s (recorded per variant): {metrics.get('latency_s_median')}",
        f"- Request bytes (max full / max control): {metrics.get('max_request_bytes_full')} / "
        f"{metrics.get('max_request_bytes_control')}",
        f"- Input tokens summed when returned: {metrics.get('input_tokens_sum')}",
        f"- Output/cost tokens: {metrics.get('output_or_cost_if_returned')}",
        "",
        "## Limits",
        "",
        "- n≤4; binomial uncertainty is large; no accuracy claim without independent visual truth.",
        "- 14_PAV remains frozen regression (`parity_claimed=false`).",
        "- v3 packed-0 (same-encounter PARA×PASSA Choice) is unchanged.",
        "- One session is not two G1 reviewers. PNG full-layer was not packed.",
        "",
        f"**Benefit claimed:** {audit.get('benefit_claimed')}. **Next FAIL:** {audit.get('next_fail')}",
        "",
    ]
    (out / "RELATORIO.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc).isoformat()

    selection = build_selection()
    # Strip bulky inventory from the human selection table copy but keep freeze input.
    slim = copy_selection_without_records(selection)
    write_json(out / "selection.json", slim)
    (out / "selection.json").write_text(
        json.dumps(slim, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )

    req_dir = out / "jev_requests"
    req_dir.mkdir(parents=True, exist_ok=True)
    v1_dir = out / "jev_requests_v1"
    v1_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out / "jev_cache"
    sources: dict[str, DxfParserCadSource] = {}
    frozen_cases = []
    for i, row in enumerate(selection["selected"], 1):
        pav = row["pavimento"]
        spec = PAVEMENT_SPECS[pav]
        if pav not in sources:
            sources[pav] = DxfParserCadSource(spec["dxf"])
        frozen = freeze_case(
            row=row, source=sources[pav], dxf_path=spec["dxf"],
            project_id=spec["project_id"],
        )
        name = request_filename(i, row["encounter_id"])
        write_json(req_dir / name, frozen["v5_request"])
        write_json(v1_dir / name, frozen["v1_request"])
        write_json(out / "cad_baselines" / name, frozen["cad_baseline"])
        frozen_cases.append({
            "index": i,
            "filename": name,
            "encounter_id": row["encounter_id"],
            "pavimento": pav,
            "beam": row["beam"],
            "wall_handle": row["wall_handle"],
            "endpoint": row["endpoint"],
            "source_behavior": row["source_behavior"],
            "ownership_why": row["ownership_why"],
            "dxf_sha256": frozen["dxf_sha256"],
            "v5_request_sha256": frozen["v5_request_sha256"],
            "v1_request_sha256": frozen["v1_request_sha256"],
            "api_payload_sha256": frozen["api_payload_sha256"],
            "source_handles": frozen["source_handles"],
            "request_bytes": frozen["request_bytes"],
            "cad_baseline": frozen["cad_baseline"],
            "v1_request": frozen["v1_request"],
            "cache_key": cache_key_v5(
                dxf_sha256=frozen["dxf_sha256"],
                api_payload_sha256=frozen["api_payload_sha256"],
            ),
        })

    freeze_manifest = {
        "created_at_utc": created,
        "n1_sidecars_read": False,
        "cases": [
            {k: v for k, v in c.items() if k != "v1_request"}
            for c in frozen_cases
        ],
        "catalog_sha256": catalog_v5_hash(),
        "model": MODEL,
    }
    freeze_manifest["freeze_sha256"] = sha256_json(freeze_manifest)
    write_json(out / "freeze_manifest.json", freeze_manifest)

    calls_used = 0
    results = []
    for case in frozen_cases:
        remaining = MAX_API_CALLS - calls_used
        if remaining < 2 and args.execute:
            rec = {
                "status": "SKIPPED_CAP",
                "error": f"remaining_calls={remaining}",
                "cache_hit": False,
                "calls": 0,
                "results": [],
            }
        else:
            rec = execute_frozen(
                v1_request=case["v1_request"],
                cache_dir=cache_dir,
                cache_key=case["cache_key"],
                execute=args.execute,
            )
        if rec.get("status") == "RECORDED" and not rec.get("cache_hit"):
            calls_used += int(rec.get("calls") or 0)
        results.append({**rec, "encounter_id": case["encounter_id"], "cache_key": case["cache_key"]})

    # N1 only after freeze of requests and responses.
    n1_rows = unblind_n1(selection)
    n1_by_id = {r["encounter_id"]: r for r in n1_rows}

    comparison = []
    latencies = []
    tokens = []
    agree_cad = 0
    abstain = 0
    ctrl_ins = 0
    ctrl_keep = 0
    n_full = 0
    n_ctrl = 0
    tech = 0
    n_n1 = 0
    for case, rec in zip(frozen_cases, results):
        cad = case["cad_baseline"]["choice"]
        variants = {row.get("variant"): row for row in rec.get("results") or []}
        full = variants.get("full") or {}
        ctrl = variants.get(case.get("v1_request", {}).get("controls", [{}])[0].get("id")) or {}
        if not ctrl:
            ctrl = next((v for k, v in variants.items() if k != "full"), {})
        jev_full = full.get("choice")
        jev_ctrl = ctrl.get("choice")
        if rec.get("status") == "TECHNICAL_ERROR":
            tech += 1
        if jev_full is not None:
            n_full += 1
            if jev_full == cad:
                agree_cad += 1
            if jev_full == "INSUFFICIENT":
                abstain += 1
        if jev_ctrl is not None:
            n_ctrl += 1
            if jev_ctrl == "INSUFFICIENT":
                ctrl_ins += 1
            if jev_ctrl == cad:
                ctrl_keep += 1
        for row in rec.get("results") or []:
            if row.get("latency_s") is not None:
                latencies.append(row["latency_s"])
            if row.get("input_tokens") is not None:
                tokens.append(row["input_tokens"])
        n1 = n1_by_id.get(case["encounter_id"]) or {}
        n1_out = list(n1.get("n1_outcomes") or [])
        if n1_out:
            n_n1 += 1
        comparison.append({
            "encounter_id": case["encounter_id"],
            "cad_choice": cad,
            "jev_full": jev_full,
            "jev_full_confidence": full.get("confidence"),
            "jev_full_probabilities": full.get("probabilities"),
            "jev_control": jev_ctrl,
            "jev_control_confidence": ctrl.get("confidence"),
            "control_matches_insufficient": jev_ctrl == "INSUFFICIENT" if jev_ctrl else None,
            "status": rec.get("status"),
            "error": rec.get("error"),
            "latency_s": [row.get("latency_s") for row in rec.get("results") or []],
            "input_tokens": [row.get("input_tokens") for row in rec.get("results") or []],
            "n1_outcomes": n1_out,
            "n1_field_would_change": None,
            "n1_endpoint_alignment": "NOT_MEASURABLE_WALL_LOCATOR_NO_ENDPOINT_ROLE",
            "n1_relevance": n1.get("n1_relevance"),
            "api_payload_sha256": case["api_payload_sha256"],
            "v5_request_sha256": case["v5_request_sha256"],
            "cache_hit": rec.get("cache_hit"),
        })

    latencies_sorted = sorted(latencies)
    median = None
    if latencies_sorted:
        mid = len(latencies_sorted) // 2
        median = latencies_sorted[mid] if len(latencies_sorted) % 2 else (
            latencies_sorted[mid - 1] + latencies_sorted[mid]
        ) / 2.0
    metrics = {
        "n_full": n_full,
        "n_control": n_ctrl,
        "jev_agrees_cad_n": agree_cad,
        "jev_abstain_n": abstain,
        "control_insufficient_n": ctrl_ins,
        "control_kept_cad_n": ctrl_keep,
        "calls_used": calls_used,
        "technical_errors": tech,
        "n_n1_present": n_n1,
        "n1_endpoint_comparable_n": 0,
        "n1_agrees_cad_n": None,
        "jev_agrees_n1_n": None,
        "latency_s_median": median,
        "max_request_bytes_full": max((c["request_bytes"]["full"] for c in frozen_cases), default=0),
        "max_request_bytes_control": max((c["request_bytes"]["control"] for c in frozen_cases), default=0),
        "input_tokens_sum": sum(tokens) if tokens else None,
        "output_or_cost_if_returned": None,
        "accuracy_claimed": False,
        "improvement_claimed": False,
    }
    audit = {
        "schema": V5_AUDIT_SCHEMA,
        "created_at_utc": created,
        "catalog_revision": CATALOG_V5_REVISION,
        "factory_version": FACTORY_V5_VERSION,
        "model": MODEL,
        "parity_claimed": False,
        "benefit_claimed": False,
        "g1_seal": False,
        "g4_seal": False,
        "n1_mutated": False,
        "visual_truth_status": "UNVERIFIED",
        "selection": slim,
        "freeze_sha256": freeze_manifest["freeze_sha256"],
        "metrics": metrics,
        "comparison_rows": comparison,
        "api_results": [
            {k: v for k, v in r.items() if k != "v1_request"}
            for r in results
        ],
        "next_fail": (
            "If control INSUFFICIENT rate is low, tighten listed-fact instructions; "
            "if full-packet agreement is CAD-redundant, do not treat Jev as additive. "
            "Independent PNG G1 still unmeasured."
        ),
    }
    audit["audit_sha256"] = sha256_json({k: v for k, v in audit.items() if k != "audit_sha256"})
    write_json(out / "STATUS.json", {
        "created_at_utc": created,
        "jev_api_called": bool(args.execute),
        "calls_used": calls_used,
        "max_calls": MAX_API_CALLS,
        "n_selected": len(frozen_cases),
        "model": MODEL,
        "benefit_claimed": False,
        "parity_claimed": False,
        "visual_truth_status": "UNVERIFIED",
        "metrics": metrics,
        "freeze_sha256": freeze_manifest["freeze_sha256"],
        "audit_sha256": audit["audit_sha256"],
    })
    write_json(out / "audit.json", audit)
    _write_relatorio(out, audit)
    print(json.dumps({
        "out": str(out),
        "n_selected": len(frozen_cases),
        "calls_used": calls_used,
        "status": [r.get("status") for r in results],
        "execute": bool(args.execute),
    }, ensure_ascii=False))
    return 0


def copy_selection_without_records(selection: dict) -> dict:
    slim = json.loads(json.dumps(selection))
    for row in slim.get("selected") or []:
        row.pop("inventory_record", None)
    return slim


if __name__ == "__main__":
    raise SystemExit(main())
