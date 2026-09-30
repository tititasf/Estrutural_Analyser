"""G1 PNG render + CAD notes. Sealing a visual verdict requires reading the PNG."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .corpus import write_json
from .filenames import safe_filename
from .hashing import sha256_file
from .leakage import assert_source_path_allowed
from .schemas import ADJUDICATION_RUN_SCHEMA


def _points_from_evidence(evidence: dict) -> list[list[float]]:
    pts: list[list[float]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("xy"), list) and len(node["xy"]) >= 2:
                pts.append([float(node["xy"][0]), float(node["xy"][1])])
            for pt in node.get("points") or []:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    pts.append([float(pt[0]), float(pt[1])])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(evidence)
    return pts


def evidence_bbox(evidence: dict, *, margin: float = 80.0) -> tuple[float, float, float, float] | None:
    pts = _points_from_evidence(evidence)
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


def render_pngs(*, dxf: Path, evidence: dict, out_dir: Path, stem: str) -> dict[str, str]:
    from portal.app.dxf_preview import renderizar_dxf_png

    assert_source_path_allowed(dxf)
    out_dir.mkdir(parents=True, exist_ok=True)
    local_bbox = evidence_bbox(evidence)
    paths: dict[str, str] = {}
    full = renderizar_dxf_png(dxf, bbox=None, largura_px=1600, altura_px=1200, margem_pct=0.02)
    full_path = out_dir / safe_filename(f"{stem}_full_dxf", suffix=".png")
    full_path.write_bytes(full)
    paths["full_dxf_png"] = str(full_path)
    if local_bbox is not None:
        local = renderizar_dxf_png(dxf, bbox=local_bbox, largura_px=1200, altura_px=1200, margem_pct=0.05)
        local_path = out_dir / safe_filename(f"{stem}_local", suffix=".png")
        local_path.write_bytes(local)
        paths["local_png"] = str(local_path)
        paths["local_bbox"] = json.dumps(local_bbox)
    return paths


def assert_g1_consensus_allowed(row: dict[str, Any]) -> None:
    """consensus=true needs two distinct agents and their independent judgments.

    Listing agent names is not enough. Blind independence is recorded on each
    review when present; this function does not invent a second reviewer.
    """
    if not row.get("consensus"):
        return
    reviews = row.get("independent_reviews")
    if not isinstance(reviews, list) or len(reviews) < 2:
        raise ValueError(
            "consensus=true requires at least two independent_reviews, each with agent and judgment"
        )
    agents: list[str] = []
    for index, review in enumerate(reviews):
        if not isinstance(review, dict):
            raise ValueError(f"independent_reviews[{index}] must be an object")
        agent = str(review.get("agent") or "").strip()
        judgment = review.get("judgment")
        if judgment is None or str(judgment).strip() == "":
            judgment = review.get("status") or review.get("choice")
        if not agent:
            raise ValueError(f"independent_reviews[{index}] missing agent")
        if judgment is None or str(judgment).strip() == "":
            raise ValueError(f"independent_reviews[{index}] missing judgment")
        agents.append(agent)
    if len(set(agents)) < 2:
        raise ValueError(
            "consensus=true requires two distinct reviewing agents with independent judgments"
        )


def cad_geometry_notes(request: dict) -> dict[str, Any]:
    ev = request.get("evidence") or {}
    target = ev.get("target") or {}
    nearby = ev.get("nearby_lines") or ev.get("dimension_candidates") or ev.get("local_markers") or []
    return {
        "target_handle": target.get("handle"),
        "target_points": target.get("points"),
        "listed_handles": [row.get("handle") for row in nearby if isinstance(row, dict)],
        "relation_provenance": ev.get("relation_provenance"),
        "inventory_exhaustive": (ev.get("inventory") or {}).get("exhaustive"),
    }


def write_g1_scaffold(*, requests: list[tuple[Path, dict]], dxf: Path, out_dir: Path,
                      notes_by_case: dict[str, dict] | None = None) -> dict[str, Any]:
    """Render PNGs and write adjudication rows. Status stays indeterminate until PNG is read."""
    out_dir = Path(out_dir)
    png_dir = out_dir / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for path, request in requests:
        case_id = request.get("case_id") or path.stem
        stem = Path(safe_filename(str(case_id), suffix=".json")).stem
        pngs = render_pngs(dxf=dxf, evidence=request["evidence"], out_dir=png_dir, stem=stem)
        extra = (notes_by_case or {}).get(case_id) or {}
        status = extra.get("status") or "INDETERMINADO_POR_FONTE"
        reviews = list(extra.get("independent_reviews") or [])
        agents = list(extra.get("agents") or [])
        if not agents:
            agents = [str(r.get("agent")) for r in reviews if isinstance(r, dict) and r.get("agent")]
        if not agents:
            agents = ["g1_render"]
        row = {
            "case_id": case_id,
            "identity": request.get("identity"),
            "status": status,
            "png": pngs,
            "cad_notes": cad_geometry_notes(request),
            "visual_review": extra.get("visual_review") or {
                "full_dxf_png_read": False,
                "note": "PNG rendered; verdict stays indeterminate until the full DXF PNG is read.",
            },
            "consensus": bool(extra.get("consensus")),
            "agents": agents,
            "independent_reviews": reviews,
            "review_kind": extra.get("review_kind") or (
                "consensus" if extra.get("consensus") else "single_review"
            ),
            "visible_to_jev": False,
        }
        assert_g1_consensus_allowed(row)
        rows.append(row)
    summary = {
        "schema": ADJUDICATION_RUN_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dxf": str(dxf),
        "source_dxf_sha256": sha256_file(dxf),
        "rows": rows,
        "denominator_note": "Dropped/unpackable cases belong in the parent report, not only packed rows.",
    }
    write_json(out_dir / "g1_adjudication.json", summary)
    return summary
