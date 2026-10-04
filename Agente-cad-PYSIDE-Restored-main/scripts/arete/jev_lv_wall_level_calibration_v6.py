"""Run the v6 read-only LV wall-level calibration. Dry-run: no Jev API, no N1 writes."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.arete.jev_calibration.adapters_lv_v6 import ComparisonInvalid, run_v6
from scripts.arete.jev_calibration.catalog_v6 import (
    CATALOG_V6_REVISION,
    FACTORY_V6_VERSION,
    MAX_API_CALLS,
    MAX_ROUTED_PACKETS,
    V6_AUDIT_SCHEMA,
    V6_STATUS_SCHEMA,
    catalog_v6_hash,
)
from scripts.arete.jev_calibration.corpus import write_json
from scripts.arete.jev_calibration.filenames import request_filename
from scripts.arete.jev_calibration.hashing import sha256_file, sha256_json
from scripts.arete.jev_sa_second_read import MODEL, validate_request


def _write_relatorio(out: Path, audit: dict) -> None:
    totals = audit.get("totals") or {}
    lines = [
        "# v6 LV wall-level set calibration (Jev optional adviser, dry-run)",
        "",
        f"**Date:** {audit.get('created_at_utc')}. **Model recorded:** `{MODEL}`. "
        f"**Catalog:** `{CATALOG_V6_REVISION}`. **Factory:** `{FACTORY_V6_VERSION}`.",
        "",
        "Jev is an optional adviser. This run does not replace SA/N1, does not "
        "write the production DB/DXF/JSON/VPS, and does not call the Jev API. "
        "N1 stayed out of source selection and out of request payloads. "
        "v3/v4/v5 reports were not modified. CAD BFS was not rewritten. "
        f"**Benefit claimed:** {audit.get('benefit_claimed')}. "
        f"**parity_claimed:** {audit.get('parity_claimed')}. "
        f"**accuracy_claimed:** {audit.get('accuracy_claimed')}.",
        "",
        "The withdrawn v5 endpoint×N1 counters are not reused. A wall locator "
        "that encodes PARA at one end and PASSA at the other is compared as "
        "sets on key (pavimento, unique beam label, source wall handle, face).",
        "",
        "## Provenance (fail-closed SHA)",
        "",
        f"- Catalog SHA-256: `{audit.get('catalog_sha256')}`",
        f"- Audit SHA-256: `{audit.get('audit_sha256')}`",
        "",
        "| pavement | role | DXF | inventory | collision | N1 sidecar | N1 source |",
        "|---|---|---|---|---|---|---|",
    ]
    for pav, row in (audit.get("pavements") or {}).items():
        lines.append(
            f"| {pav} | {row.get('role')} | `{str(row.get('source_dxf_sha256') or '')[:12]}…` | "
            f"`{str(row.get('inventory_sha256') or '')[:12]}…` | "
            f"`{str(row.get('collision_audit_sha256') or '')[:12]}…` | "
            f"`{str(row.get('n1_sidecar_sha256') or '')[:12]}…` | "
            f"{row.get('n1_source')} |"
        )
    lines += [
        "",
        "## Coverage (denominators)",
        "",
        "| measure | 13_PAV | 14_PAV | total |",
        "|---|---:|---:|---:|",
    ]
    cov13 = ((audit.get("pavements") or {}).get("13_PAV") or {}).get("coverage") or {}
    cov14 = ((audit.get("pavements") or {}).get("14_PAV") or {}).get("coverage") or {}
    keys = [
        "source_walls", "source_complete", "source_incomplete", "source_ambiguous",
        "ownership_owned", "ownership_rejected", "ownership_uncertain",
        "n1_exact", "n1_cover_only", "n1_missing", "n1_ambiguous",
        "set_equal", "set_diverge",
        "abstain_ownership", "abstain_source", "abstain_n1_coverage",
    ]
    for key in keys:
        a = int(cov13.get(key) or 0)
        b = int(cov14.get(key) or 0)
        lines.append(f"| {key} | {a} | {b} | {a + b} |")
    lines += [
        "",
        "SET_EQUAL is set identity on a valid wall, not correctness. SET_DIVERGE "
        "is a valid measurement disagreement, not a proven SA error.",
        "",
        "## Valid comparable walls (owned + complete source XOR + exact N1)",
        "",
        "| wall_id | verdict | source set | N1 exact set | ownership |",
        "|---|---|---|---|---|",
    ]
    comparable = []
    for row in (audit.get("pavements") or {}).values():
        comparable.extend(row.get("comparable_rows") or [])
    comparable.sort(key=lambda r: r.get("wall_id") or "")
    if not comparable:
        lines.append("| _(none)_ | | | | |")
    for row in comparable:
        lines.append(
            f"| `{row.get('wall_id')}` | {row.get('verdict')} | {row.get('source_set')} | "
            f"{row.get('n1_set')} | {row.get('ownership_why')} |"
        )
    lines += [
        "",
        "V420 `2F8` face A is SET_EQUAL `{PARA, PASSA}` at wall level. Endpoint-level "
        "comparison of the same locator is invalid and is not used.",
        "",
        "## Actionable routing queue (dry-run, 0 API calls)",
        "",
        f"- Actionable walls: **{totals.get('actionable', 0)}**",
        f"- Packed source-only requests: **{totals.get('packed', 0)} / {MAX_ROUTED_PACKETS}**",
        f"- API calls used: **0 / {MAX_API_CALLS}**",
        "",
        "| wall_id | pavement | route | source set | N1 exact set | packed |",
        "|---|---|---|---|---|---|",
    ]
    for pav, row in (audit.get("pavements") or {}).items():
        for item in row.get("actionable") or []:
            lines.append(
                f"| `{item.get('wall_id')}` | {pav} | {item.get('route')} | "
                f"{item.get('source_set')} | {item.get('n1_set')} | {item.get('packed')} |"
            )
    if totals.get("actionable", 0) == 0:
        lines.append("| _(empty)_ | | | | | |")
    lines += [
        "",
        "Requests reuse `validate_request` / `validate_factory_request`. "
        "N1 values are absent from payloads. A routing queue is not an accuracy claim.",
        "",
        "## Missing evidence / abstain reasons",
        "",
    ]
    for pav, row in (audit.get("pavements") or {}).items():
        miss = row.get("missing_evidence") or {}
        lines.append(f"**{pav}** abstain n={miss.get('abstain_n', 0)}")
        for reason, n in (miss.get("reasons") or {}).items():
            lines.append(f"- `{reason}`: {n}")
        lines.append("")
    lines += [
        "## Limits",
        "",
        "- 14_PAV remains frozen regression (`parity_claimed=false`).",
        "- Cover locators and ambiguous handle mappings are excluded from set equality.",
        "- Shared joints and unknown owners abstain; they are never scored as mismatch.",
        "- v5 `STATUS_CORRIGIDO.json` endpoint metrics remain withdrawn.",
        "- PNG G1 was not packed. Independent visual truth is absent.",
        "",
        f"**Next controlled experiment:** {audit.get('next_controlled_experiment')}",
        "",
        f"Artifacts: `{out.as_posix()}`",
        "",
    ]
    (out / "RELATORIO.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--execute", action="store_true", help="Rejected in v6; dry-run only.")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    if args.execute:
        fail = {
            "schema": V6_STATUS_SCHEMA,
            "status": "FAIL_CLOSED",
            "reason": "v6 execute is disabled until dry-run routing counts are known",
            "api_calls": 0,
            "benefit_claimed": False,
            "parity_claimed": False,
        }
        write_json(out / "STATUS.json", fail)
        (out / "RELATORIO.md").write_text(
            "# v6 FAIL CLOSED\n\nExecute was requested. v6 is dry-run only.\n",
            encoding="utf-8",
        )
        return 2
    created = datetime.now(timezone.utc).isoformat()
    try:
        run = run_v6()
    except ComparisonInvalid as exc:
        fail = {
            "schema": V6_STATUS_SCHEMA,
            "status": "FAIL_CLOSED",
            "reason": str(exc),
            "api_calls": 0,
            "benefit_claimed": False,
            "parity_claimed": False,
            "created_at_utc": created,
        }
        write_json(out / "STATUS.json", fail)
        (out / "RELATORIO.md").write_text(
            "# v6 FAIL CLOSED\n\n"
            "Wall-level comparison could not be validated against frozen artifacts.\n\n"
            f"`{exc}`\n",
            encoding="utf-8",
        )
        return 2

    requests_dir = out / "jev_requests"
    requests_dir.mkdir(parents=True, exist_ok=True)
    packed_index = 0
    for pav, row in run["pavements"].items():
        for item in row.get("packed_requests") or []:
            path = requests_dir / request_filename(packed_index, item["wall_id"])
            payload = item["v1_request"]
            validate_request(payload)
            write_json(path, payload)
            packed_index += 1
        row.pop("packed_requests", None)

    audit = {
        "schema": V6_AUDIT_SCHEMA,
        "created_at_utc": created,
        "model": MODEL,
        **run,
    }
    audit["audit_sha256"] = sha256_json(
        {k: v for k, v in audit.items() if k != "audit_sha256"}
    )
    write_json(out / "audit.json", audit)
    write_json(out / "provenance.json", {
        "catalog_revision": CATALOG_V6_REVISION,
        "factory_version": FACTORY_V6_VERSION,
        "catalog_sha256": catalog_v6_hash(),
        "audit_sha256": audit["audit_sha256"],
        "module_sha256": {
            "catalog_v6.py": sha256_file(Path(__file__).resolve().parents[0] / "jev_calibration" / "catalog_v6.py"),
            "adapters_lv_v6.py": sha256_file(
                Path(__file__).resolve().parents[0] / "jev_calibration" / "adapters_lv_v6.py"
            ),
            "jev_lv_wall_level_calibration_v6.py": sha256_file(Path(__file__).resolve()),
        },
        "pavements": {
            pav: {
                "source_dxf_sha256": row["source_dxf_sha256"],
                "inventory_sha256": row["inventory_sha256"],
                "collision_audit_sha256": row["collision_audit_sha256"],
                "n1_sidecar_sha256": row["n1_sidecar_sha256"],
                "n1_fingerprint_sha256": row.get("n1_fingerprint_sha256"),
                "n1_source": row.get("n1_source"),
                "source_table_sha256": row["source_table_sha256"],
                "parity_claimed": False,
                "role": row["role"],
            }
            for pav, row in run["pavements"].items()
        },
    })
    write_json(out / "routing_queue.json", {
        "schema": "jev_lv_v6_routing_queue/v6",
        "execute": False,
        "calls_used": 0,
        "max_api_calls": MAX_API_CALLS,
        "n_actionable": run["totals"].get("actionable", 0),
        "n_packed": packed_index,
        "items": [
            item
            for row in run["pavements"].values()
            for item in row.get("actionable") or []
        ],
        "note": "Routing queue is not an accuracy claim.",
    })
    status = {
        "schema": V6_STATUS_SCHEMA,
        "status": "DRY_RUN_RECORDED",
        "catalog_revision": CATALOG_V6_REVISION,
        "factory_version": FACTORY_V6_VERSION,
        "created_at_utc": created,
        "api_calls": 0,
        "execute": False,
        "benefit_claimed": False,
        "parity_claimed": False,
        "accuracy_claimed": False,
        "n1_in_jev_prompts": False,
        "totals": run["totals"],
        "audit_sha256": audit["audit_sha256"],
        "v5_endpoint_n1_metrics": "withdrawn_not_reused",
    }
    write_json(out / "STATUS.json", status)
    _write_relatorio(out, audit)
    print(json.dumps({
        "out": str(out),
        "status": status["status"],
        "totals": run["totals"],
        "api_calls": 0,
        "packed_requests": packed_index,
        "audit_sha256": audit["audit_sha256"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
