"""Read-only LV source-wall collision follow-up. No Git, no N1 writes, no VPS."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.arete.jev_calibration.cad_source import DxfParserCadSource
from scripts.arete.jev_calibration.corpus import write_json
from scripts.arete.jev_calibration.hashing import sha256_file, sha256_json
from scripts.arete.jev_calibration.lv_wall_ownership_audit import (
    EXPECTED_V3_INVENTORY_SHA,
    SPECIAL_14PAV_HANDLES,
    apply_cad_validation,
    attach_n1_sidecar,
    audit_inventory_collisions,
    blinded_single_outcome_protocol,
    bounded_cad_probe,
    build_label_choice_request,
    duplicate_name_labels,
    run_api_if_eligible,
    select_representative_handles,
)
from scripts.arete.jev_calibration.schemas import FROZEN_VPS_14PAV, VPS_PARITY_DIR
from scripts.arete.jev_sa_second_read import MODEL

REPO = Path(__file__).resolve().parents[2]
V3_DIR = REPO / "scripts" / "arete" / "relatorios" / "20260929_jev_catalog_v3_lv_source_encounter"
OUT_DIR = REPO / "scripts" / "arete" / "relatorios" / "20260929_jev_lv_source_wall_ownership"
DXF_13 = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-1_Ingestao"
    r"\Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
    r"\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.dxf"
)
DXF_14 = VPS_PARITY_DIR / "torre_1.dxf"
EXPECTED_DXF = {
    "13_PAV": "d23381e30eb358cc07e8c140d92db4c06b7be97859e7f9fb3eea2c0bd33151a4",
    "14_PAV": FROZEN_VPS_14PAV["source_dxf_sha256"],
}
PROJECT = {
    "13_PAV": "dd238e47-1dc6-4f63-a760-4e7ce19a7386",
    "14_PAV": FROZEN_VPS_14PAV["project_id"],
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _probe_cases(audit: dict, source: DxfParserCadSource, extra_handles: list[str]) -> dict:
    handles = list(select_representative_handles(audit))
    for handle in extra_handles:
        if handle not in handles:
            handles.append(handle)
    eligible = [c["wall_handle"] for c in audit["cases"] if c.get("jev_eligible")]
    for handle in eligible:
        if handle not in handles:
            handles.append(handle)
    by_handle = {c["wall_handle"]: c for c in audit["cases"]}
    probes = []
    for handle in handles:
        extra = []
        case = by_handle.get(handle)
        if case:
            extra = [row["label_xy"] for row in case["owners"] if row.get("label_xy")]
        probe = bounded_cad_probe(source, handle, extra_xy=extra)
        if case is not None:
            case["cad_validation"] = apply_cad_validation(case, probe)
            case["jev_eligible"] = bool(case["cad_validation"]["jev_eligible_after_cad"])
        probes.append(probe)
    return {"handles": handles, "probes": probes}


def _requests_for_eligible(audit: dict, source: DxfParserCadSource, probes: list[dict]
                           ) -> list[dict]:
    probe_by = {p["handle"]: p for p in probes}
    requests = []
    eligible = [c for c in audit["cases"] if c.get("jev_eligible")]
    for case in eligible[:4]:
        names = case["in_strip_names"]
        if len(names) != 2:
            continue
        owners = {row["beam"]: row for row in case["owners"]}
        probe = probe_by.get(case["wall_handle"]) or {}
        texts = {row["text"]: row for row in probe.get("beam_texts") or []}
        labels = []
        for name in names:
            owner = owners[name]
            text_row = texts.get(name) or {
                "handle": owner["label_handle"], "text": name, "xy": owner["label_xy"],
            }
            labels.append({
                "handle": text_row["handle"], "text": name,
                "xy": text_row.get("xy") or owner["label_xy"],
            })
        local_walls = []
        for wall in (probe.get("same_layer_open_walls") or [])[:6]:
            local_walls.append({
                "handle": wall["handle"], "etype": wall.get("etype"),
                "xy": wall.get("xy"), "points": wall.get("points"),
            })
        identity = {
            "project_id": PROJECT[audit["pavimento"]],
            "pavimento": audit["pavimento"],
            "classe": "LV",
            "item": case["wall_handle"],
            "campo": "source_label_name",
            "source_dxf_sha256": audit["source_dxf_sha256"],
        }
        requests.append(build_label_choice_request(
            identity=identity,
            wall_handle=case["wall_handle"],
            segment=case["segment"],
            partner_handle=case.get("partner_handle"),
            labels=labels,
            local_walls=local_walls,
            connectivity={
                "in_strip_names": names,
                "partner_handle": case.get("partner_handle"),
                "n_interior": case.get("n_interior"),
            },
        ))
    return requests


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc).isoformat()
    pavements = []
    jev_bundle = []
    sources = {}
    for pav, folder, dxf in (
        ("13_PAV", "dryrun_13pav_lv", DXF_13),
        ("14_PAV", "dryrun_14pav_lv", DXF_14),
    ):
        inv_path = V3_DIR / folder / "source_inventory.json"
        side_path = V3_DIR / folder / "n1_comparison_sidecar.json"
        inventory = _load_json(inv_path)
        expected = EXPECTED_V3_INVENTORY_SHA[pav]
        if inventory.get("inventory_sha256") != expected:
            raise SystemExit(f"{pav} inventory SHA mismatch")
        dxf_sha = sha256_file(dxf)
        if dxf_sha != EXPECTED_DXF[pav]:
            raise SystemExit(f"{pav} DXF SHA mismatch")
        if inventory.get("source_dxf_sha256") != dxf_sha:
            raise SystemExit(f"{pav} inventory DXF SHA mismatch")
        audit = audit_inventory_collisions(inventory)
        source = DxfParserCadSource(dxf)
        sources[pav] = source
        extra = list(SPECIAL_14PAV_HANDLES) if pav == "14_PAV" else ["474", "1007"]
        probed = _probe_cases(audit, source, extra)
        dups = duplicate_name_labels(source)
        n1_src = _load_json(side_path)
        n1_view = attach_n1_sidecar(audit, n1_src)
        audit["duplicate_name_labels"] = {
            "unique_lv_text_names": dups["unique_lv_text_names"],
            "names_with_duplicate_text": dups["names_with_duplicate_text"],
            "duplicate_name_list": [row["name"] for row in dups["duplicate_names"]],
        }
        audit["denominators"]["duplicate_name_texts"] = dups["names_with_duplicate_text"]
        audit["denominators"]["jev_eligible_walls_after_cad"] = sum(
            1 for c in audit["cases"] if c.get("jev_eligible")
        )
        audit["audit_sha256"] = sha256_json(
            {k: v for k, v in audit.items() if k != "audit_sha256"}
        )
        n1_view["collision_audit_sha256"] = audit["audit_sha256"]
        n1_view["sidecar_sha256"] = sha256_json(
            {k: v for k, v in n1_view.items() if k != "sidecar_sha256"}
        )
        write_json(OUT_DIR / f"collision_audit_{pav}.json", audit)
        write_json(OUT_DIR / f"n1_collision_sidecar_{pav}.json", n1_view)
        write_json(OUT_DIR / f"cad_probes_{pav}.json", {
            "pavimento": pav,
            "source_dxf_sha256": dxf_sha,
            "probes": probed["probes"],
        })
        write_json(OUT_DIR / f"duplicate_name_labels_{pav}.json", dups)
        requests = _requests_for_eligible(audit, source, probed["probes"])
        pavements.append({
            "pavimento": pav,
            "inventory_sha256": inventory["inventory_sha256"],
            "dxf_sha256": dxf_sha,
            "audit_sha256": audit["audit_sha256"],
            "n1_view_sha256": n1_view["sidecar_sha256"],
            "denominators": audit["denominators"],
            "special_312_313": audit.get("special_312_313"),
            "n1_sidecar_denominators": n1_view["denominators"],
            "n_jev_requests": len(requests),
            "requests": requests,
            "source": source,
        })
        jev_bundle.extend((pav, req, source) for req in requests)

    protocol = blinded_single_outcome_protocol()
    write_json(OUT_DIR / "blinded_single_outcome_protocol.json", protocol)

    req_dir = OUT_DIR / "jev_requests"
    req_dir.mkdir(exist_ok=True)
    api_report = {
        "called": False,
        "why": "no genuine unresolved source label Choice after CAD validation",
        "model_recorded": MODEL,
        "calls_used": 0,
        "max_calls": 8,
        "outcomes": [],
    }
    if jev_bundle:
        requests = [row[1] for row in jev_bundle]
        for i, req in enumerate(requests):
            write_json(req_dir / f"request_{i:02d}.json", req)
        # Validate then execute only valid source-first cases. Cap 8 calls.
        # If mixed pavements, validate per request.
        outcomes = []
        calls = 0
        execute = True
        for i, (pav, req, source) in enumerate(jev_bundle):
            piece = run_api_if_eligible(
                [req], execute=execute, source_dxf=source.dxf_path,
                known_handles=source.known_handles(),
                output_dir=OUT_DIR / "jev_results", max_calls=8 - calls,
            )
            calls += piece["calls_used"]
            outcomes.extend(piece["outcomes"])
            if calls >= 8:
                execute = False
        api_report = {
            "called": calls > 0,
            "why": "genuine unresolved cases after CAD validation",
            "model_recorded": MODEL,
            "calls_used": calls,
            "max_calls": 8,
            "outcomes": outcomes,
        }
    else:
        (req_dir / "README.txt").write_text(
            "Empty because no genuine unresolved two-label interior collision survived CAD.\n",
            encoding="utf-8",
        )

    write_json(OUT_DIR / "jev_api.json", api_report)

    slim = []
    for row in pavements:
        slim.append({k: v for k, v in row.items() if k not in {"requests", "source"}})
    status = {
        "created_at_utc": created,
        "catalog_v3_preserved": True,
        "jev_api_called": bool(api_report["called"]),
        "model": MODEL,
        "calls_used": api_report["calls_used"],
        "genuine_unresolved_after_cad": sum(p["n_jev_requests"] for p in slim),
        "pavements": slim,
        "protocol": "DESIGN_ONLY_NOT_EXECUTED",
        "parity_claimed": False,
        "v3_zero_packets_scope": (
            "Catalog v3 packed 0 applies only to same-encounter PARA/PASSA Choice."
        ),
    }
    write_json(OUT_DIR / "STATUS.json", status)
    _write_report(created, slim, api_report, protocol)
    print(json.dumps({
        "out": str(OUT_DIR),
        "jev_called": api_report["called"],
        "calls": api_report["calls_used"],
        "eligible": status["genuine_unresolved_after_cad"],
    }, ensure_ascii=False))
    return 0


def _write_report(created: str, pavements: list[dict], api: dict, protocol: dict) -> None:
    p13 = next(p for p in pavements if p["pavimento"] == "13_PAV")
    p14 = next(p for p in pavements if p["pavimento"] == "14_PAV")
    d13 = p13["denominators"]
    d14 = p14["denominators"]
    s14 = p14["special_312_313"]
    n13 = p13["n1_sidecar_denominators"]
    n14 = p14["n1_sidecar_denominators"]
    lines = [
        "# LV source-wall collisions (Jev follow-up)",
        "",
        f"**Date:** {created}. **Jev API:** "
        + ("called" if api["called"] else "not called")
        + f". **Model recorded:** `{api['model_recorded']}`. "
        "**SA / DB / DXF / VPS / JSON Fase-4:** not written. **KB:** not rebuilt. "
        "**Human adjudication:** none. v1/v2/v3 artifacts preserved.",
        "",
        "Continues [`../20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md`]"
        "(../20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md). "
        "v3 packed 0 is a same-encounter PARA/PASSA pack-gate result. "
        "This experiment measures **source-wall name collisions** and designs a "
        "future blinded single-outcome check. It does not treat v3's 0 packets "
        "as evidence that Jev lacks value.",
        "",
        "## Verdict",
        "",
        f"Collision walls: **{d13['collision_walls']}** (13_PAV) and "
        f"**{d14['collision_walls']}** (14_PAV frozen). "
        f"After strip-membership + bounded CAD, genuine unresolved two-label "
        f"interior cases: **{p13['n_jev_requests'] + p14['n_jev_requests']}**. "
        + (
            f"Jev calls used: {api['calls_used']} / 8."
            if api["called"]
            else "Jev was not called: no surviving two-name interior Choice."
        ),
        "",
        "Handles `312`/`313` on 14_PAV are an inventory collision of **V423 and V424**, "
        "classified `LIKELY_OVER_EXPANDED_STRIP` (only V424 sits in the strip). "
        "V419 does not list them. That is a surprising non-attachment relative to "
        "the v2 V419 note, not a V419 collision.",
        "",
        "## Method",
        "",
        "1. Read frozen v3 `source_inventory.json` (SHA checked). N1 not used.",
        "2. Group wall handles by distinct unique beam names.",
        "3. Classify each 2+ name handle with label-vs-strip geometry "
        "(shared wall-direction transverse axis, `MAX_OUTSIDE=40`, interior t in (0.20, 0.80)).",
        "4. Categories: `LIKELY_OVER_EXPANDED_STRIP`, `SHARED_JOINT`, "
        "`UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP`, `SAME_NAME_DUPLICATE_LABEL` (CAD probe).",
        "5. Bounded CAD: `by_handle` + `entities_near` at endpoints/labels only.",
        "6. N1 comparison is a **separate sidecar**.",
        "7. Jev Choice of two source names + INSUFFICIENT only if a genuine "
        "unresolved case survives CAD; withheld-label control; max 8 calls.",
        "",
        "## Observed counts",
        "",
        "| Measure | 13_PAV | 14_PAV frozen |",
        "|---|---:|---:|",
        f"| Unique LV labels (v3) | {d13['unique_lv_labels']} | {d14['unique_lv_labels']} |",
        f"| Unique wall handles | {d13['unique_wall_handles']} | {d14['unique_wall_handles']} |",
        f"| Collision walls (2+ names) | {d13['collision_walls']} | {d14['collision_walls']} |",
        f"| Distinct name-pairs | {d13['collision_pairs']} | {d14['collision_pairs']} |",
        f"| Encounters on collision walls | {d13['collision_encounters']} | {d14['collision_encounters']} |",
        f"| Over-expanded | {d13['category_walls'].get('LIKELY_OVER_EXPANDED_STRIP', 0)} | {d14['category_walls'].get('LIKELY_OVER_EXPANDED_STRIP', 0)} |",
        f"| Shared joint | {d13['category_walls'].get('SHARED_JOINT', 0)} | {d14['category_walls'].get('SHARED_JOINT', 0)} |",
        f"| Unresolved (inventory, before CAD) | {d13['category_walls'].get('UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP', 0)} | {d14['category_walls'].get('UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP', 0)} |",
        f"| Jev-eligible after CAD | {d13.get('jev_eligible_walls_after_cad', 0)} | {d14.get('jev_eligible_walls_after_cad', 0)} |",
        f"| Duplicate-name TEXT (CAD, excluded from unique inventory) | {d13.get('duplicate_name_texts', 0)} | {d14.get('duplicate_name_texts', 0)} |",
        f"| N1 rows on collision encounters (sidecar) | {n13['n1_rows_on_collision_encounters']} | {n14['n1_rows_on_collision_encounters']} |",
        f"| N1 field would change (sidecar) | {n13['n1_field_would_change']} | {n14['n1_field_would_change']} |",
        "",
        "### 13_PAV pair leaders",
        "",
        "| Beams | Walls |",
        "|---|---:|",
    ]
    for row in d13["pair_wall_counts"][:8]:
        lines.append(f"| {' + '.join(row['beams'])} | {row['n_walls']} |")
    lines += [
        "",
        "### 14_PAV pair leaders",
        "",
        "| Beams | Walls |",
        "|---|---:|",
    ]
    for row in d14["pair_wall_counts"][:8]:
        lines.append(f"| {' + '.join(row['beams'])} | {row['n_walls']} |")
    lines += [
        "",
        "## 312 / 313 (14_PAV)",
        "",
        s14["inventory_only_verdict"],
        "",
        "| Handle | Names | V419 | V423 | V424 | Inventory category |",
        "|---|---|---|---|---|---|",
    ]
    for handle in SPECIAL_14PAV_HANDLES:
        row = s14["handles"][handle]
        lines.append(
            f"| `{handle}` | {', '.join(row['attached_beam_names'] or [])} | "
            f"{row['v419_lists_handle']} | {row['v423_lists_handle']} | "
            f"{row['v424_lists_handle']} | {row['category']} |"
        )
    lines += [
        "",
        "CAD (bounded): `312`/`313` are open layer-3 LWPOLYLINE pair "
        "`x=5307.59` / `x=5321.59`, y=2075–2335. Unique `V424` (`D9F`) sits at the "
        "south end; unique `V423` (`D9E`) sits on an orthogonal strip to the northwest. "
        "V419 (`D9A`) is far west. Not a two-label interior Choice.",
        "",
        "## N1 sidecar (isolated)",
        "",
        "N1 was joined only after collision categories were frozen. "
        "It did not classify collisions and is not Jev evidence.",
        "",
        f"13_PAV sidecar `n1_relevance`: `{n13['n1_relevance']}`. "
        f"14_PAV sidecar `n1_relevance`: `{n14['n1_relevance']}`.",
        "",
        "## Jev",
        "",
        api["why"].rstrip(".") + f", so Jev was not called (`{api['calls_used']}` / `{api['max_calls']}` calls). "
        f"Model recorded `{api['model_recorded']}`. Agreement/abstention is reported "
        "only after an API outcome; accuracy without independent truth is not claimed.",
        "",
        "## Blinded corroboration protocol (design only)",
        "",
        "See [`blinded_single_outcome_protocol.json`](blinded_single_outcome_protocol.json). "
        f"Status `{protocol['status']}`. Packets implemented: 0. Benefit claimed: false.",
        "",
        "Question: PARA / PASSA / INSUFFICIENT about listed geometry at one encounter "
        "with exactly one source-supported outcome. N1 compared afterwards. "
        "Removal and perturbation controls. Separate CAD deterministic baseline. "
        "This is independent of the v3 same-encounter conflict pack gate.",
        "",
        "## Artifacts",
        "",
        f"- inventory 13 `{p13['inventory_sha256']}`",
        f"- inventory 14 `{p14['inventory_sha256']}`",
        f"- audit 13 `{p13['audit_sha256']}`",
        f"- audit 14 `{p14['audit_sha256']}`",
        f"- N1 view 13 `{p13['n1_view_sha256']}`",
        f"- N1 view 14 `{p14['n1_view_sha256']}`",
        "- `collision_audit_{13,14}_PAV.json`",
        "- `n1_collision_sidecar_{13,14}_PAV.json`",
        "- `cad_probes_{13,14}_PAV.json`",
        "- `duplicate_name_labels_{13,14}_PAV.json`",
        "- `blinded_single_outcome_protocol.json`",
        "- `jev_api.json`",
        "",
        "## Limitations",
        "",
        "- Unique-label inventory ignores duplicate TEXT of the same V-name "
        "(13_PAV has such names on other layers/positions).",
        "- Strip membership uses inventory partner handles, not a new DXF walk.",
        "- One session is not two G1 reviewers. PNG not packed.",
        "- 14_PAV remains frozen regression (`parity_claimed=false`).",
        "- Over-expansion is a FACT of the v3 walk (`MAX_HOPS` / multi-seed), "
        "not a Jev measurement.",
        "",
        "## Next FAIL",
        "",
        "CAD: cap or split **strip-walk over-expansion** so a wall handle is not "
        "attached to unique labels that sit outside its strip. "
        "Jev: run the blinded single-outcome protocol on a sealed CAD_REDUNDANT "
        "sample (PARA/PASSA/INSUFFICIENT, N1 after, max 8 calls). "
        "Do not reopen v3 same-encounter conflict Choice until a real exclusive pair exists.",
        "",
    ]
    (OUT_DIR / "RELATORIO.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
