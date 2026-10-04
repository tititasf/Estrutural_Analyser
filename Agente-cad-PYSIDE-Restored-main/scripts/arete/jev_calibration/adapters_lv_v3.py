"""LV v3: source-first encounters from Fase-1 DXF. N1 is a later sidecar only."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .adapters_lv import MAX_NEARBY, _control_shell, _nearby_row
from .adapters_lv_v2 import (
    PILLAR_RADIUS,
    _connected_to_label,
    _encounter_gaps,
    _partner_walls,
    _pillar_markers,
    _polygon_hits,
    _source_outcomes,
    _walls_touching,
)
from .adapters_pil import ConflictCandidate
from .cad_source import CadEntity, CadSource
from .catalog_v2 import N1_OUTCOMES, outcome_id
from .catalog_v3 import (
    CATALOG_V3,
    CATALOG_V3_REVISION,
    FACTORY_V3_VERSION,
    catalog_v3_hash,
    lv_v3_question,
)
from .geometry_util import (
    BEAM_NAME_RE,
    classify_source_curve,
    colinear_continuations,
    compact_entity,
    dist,
    entity_as_segments,
    face_from_transverse,
    is_closed_loop,
    midpoint,
    nearby_parallel_segments,
    unique_source_wall,
    unique_vertices,
)
from .hashing import sha256_json
from .n1_snapshot import N1Snapshot

INVENTORY_SCHEMA = "jev_lv_source_inventory/v3"
SIDECAR_SCHEMA = "jev_lv_n1_comparison_sidecar/v3"

MAX_WALLS_PER_BEAM = 24
MAX_HOPS = 24
LABEL_RADIUS = 90.0
STRIP_GAP_MIN = 8.0
STRIP_GAP_MAX = 40.0
END_TOL = 6.0
COORD_NDIGITS = 3


def _round_xy(pt) -> list[float]:
    return [round(float(pt[0]), COORD_NDIGITS), round(float(pt[1]), COORD_NDIGITS)]


def _primary_segment(ent: CadEntity) -> list[list[float]] | None:
    segs = [seg for seg in entity_as_segments(ent) if dist(seg[0], seg[1]) >= 1.0]
    if not segs:
        return None
    a, b = max(segs, key=lambda seg: dist(seg[0], seg[1]))
    return [_round_xy(a), _round_xy(b)]


def _is_lv_beam_name(text: str) -> bool:
    raw = (text or "").strip()
    if not BEAM_NAME_RE.fullmatch(raw):
        return False
    return not raw.upper().startswith("VF")


def iter_unique_lv_labels(source: CadSource) -> list[CadEntity]:
    buckets: dict[str, list[CadEntity]] = {}
    for etype in ("TEXT", "MTEXT"):
        for ent in source.entities_of_type(etype):
            text = (ent.text or "").strip()
            if not _is_lv_beam_name(text):
                continue
            buckets.setdefault(text, []).append(ent)
    unique = [ents[0] for name, ents in sorted(buckets.items()) if len(ents) == 1]
    return unique


def _partner_for_wall(source: CadSource, pts: list, handle: str) -> dict[str, Any] | None:
    nearby = nearby_parallel_segments(source, pts, handle, gap_max=STRIP_GAP_MAX)
    partners = []
    for hit in _partner_walls(nearby):
        gap = float(hit.get("gap") or 0.0)
        if gap < STRIP_GAP_MIN or gap > STRIP_GAP_MAX:
            continue
        partners.append(hit)
    if not partners:
        return None
    partners.sort(key=lambda hit: (hit.get("gap") or 0.0, hit["entity"].handle))
    return partners[0]


def _label_in_strip(label_xy, wall_pts, partner_pts) -> bool:
    from .geometry_util import label_near_strip

    if not partner_pts:
        return False
    ok, _where = label_near_strip(label_xy, wall_pts, partner_pts)
    return bool(ok)


def seed_strip_walls(source: CadSource, label: CadEntity) -> list[tuple[CadEntity, list]]:
    """Open walls near the unique beam label that form a strip containing the label."""
    found: list[tuple[CadEntity, list]] = []
    seen: set[str] = set()
    xy = label.xy
    for ent in source.entities_near(float(xy[0]), float(xy[1]), LABEL_RADIUS,
                                    types=["LINE", "LWPOLYLINE"]):
        if ent.handle in seen or classify_source_curve(ent) != "wall_line":
            continue
        pts = _primary_segment(ent)
        if pts is None:
            continue
        partner = _partner_for_wall(source, pts, ent.handle)
        if partner is None:
            continue
        partner_pts = [list(partner["segment"][0]), list(partner["segment"][1])]
        if not _label_in_strip(xy, pts, partner_pts):
            continue
        seen.add(ent.handle)
        found.append((ent, pts))
    found.sort(key=lambda row: row[0].handle)
    return found


def collect_connected_walls(source: CadSource, seed_ent: CadEntity, seed_pts: list,
                            partner_pts: list, label_xy) -> list[tuple[CadEntity, list]]:
    visited = {seed_ent.handle}
    walls = [(seed_ent, seed_pts)]
    queue = [(seed_ent.handle, seed_pts)]
    hops = 0
    while queue and hops < MAX_HOPS and len(walls) < MAX_WALLS_PER_BEAM:
        handle, pts = queue.pop(0)
        hops += 1
        for hit in colinear_continuations(source, pts[0], pts[1], handle, gap=12.0):
            ent = hit["entity"]
            if ent.handle in visited:
                continue
            seg = [_round_xy(hit["segment"][0]), _round_xy(hit["segment"][1])]
            visited.add(ent.handle)
            walls.append((ent, seg))
            queue.append((ent.handle, seg))
        if partner_pts:
            for gap in _encounter_gaps(source, pts, partner_pts, handle):
                gent = gap["entity"]
                if gent.handle in visited:
                    continue
                visited.add(gent.handle)
                for vx, vy in unique_vertices(gent.points):
                    for ent, seg in _walls_touching(source, [vx, vy], pts, visited):
                        if classify_source_curve(ent) != "wall_line":
                            continue
                        visited.add(ent.handle)
                        nseg = [_round_xy(seg[0]), _round_xy(seg[1])]
                        walls.append((ent, nseg))
                        queue.append((ent.handle, nseg))
                        if len(walls) >= MAX_WALLS_PER_BEAM:
                            break
    walls.sort(key=lambda row: row[0].handle)
    return walls


def _pillars_at(source: CadSource, end) -> list[CadEntity]:
    found = []
    seen: set[str] = set()
    for ent in source.entities_near(float(end[0]), float(end[1]), PILLAR_RADIUS,
                                    types=["TEXT", "MTEXT"]):
        text = (ent.text or "").strip()
        if ent.handle in seen:
            continue
        from .geometry_util import PILLAR_NAME_RE
        if not PILLAR_NAME_RE.fullmatch(text):
            continue
        seen.add(ent.handle)
        found.append(ent)
    return found


def _crossing_beams(source: CadSource, end, self_name: str, self_label_handle: str) -> list[CadEntity]:
    found = []
    seen: set[str] = set()
    for ent in source.entities_near(float(end[0]), float(end[1]), 24.0,
                                    types=["TEXT", "MTEXT"]):
        text = (ent.text or "").strip()
        if ent.handle in seen or ent.handle == self_label_handle:
            continue
        if not BEAM_NAME_RE.fullmatch(text):
            continue
        if text.strip() == self_name:
            continue
        seen.add(ent.handle)
        found.append(ent)
    return found


def encounter_id(*, pavimento: str, beam: str, handle: str, face: str | None,
                 at: list[float], source_handles: list[str]) -> str:
    face_s = face or "U"
    handles = ",".join(sorted({h for h in source_handles if h}))
    return (
        f"{pavimento}|LV|{beam}|enc|{handle}|{face_s}|"
        f"{at[0]:.3f},{at[1]:.3f}|{handles}"
    )


def classify_encounter(*, face: str | None, para: bool, passa: bool, label_ok: bool
                       ) -> tuple[str, str]:
    """Fail-closed: PARA and PASSA at one encounter are never a Choice."""
    if not label_ok:
        return "SOURCE_INSUFFICIENT", "unique_label_not_connected_to_strip"
    if face not in {"A", "B"}:
        return "CONVENTION_INDETERMINATE", "face_not_unique_from_source_strip"
    if para and passa:
        return "SOURCE_INSUFFICIENT", "para_and_passa_not_exclusive_at_one_encounter"
    outcomes = _source_outcomes(face=face, para=para, passa=passa)
    if len(outcomes) >= 2:
        return "SOURCE_INSUFFICIENT", "para_and_passa_not_exclusive_at_one_encounter"
    if len(outcomes) == 1:
        return "CAD_REDUNDANT", "single_source_supported_n1_outcome:" + outcomes[0]
    return "SOURCE_INSUFFICIENT", "no_source_supported_para_or_passa"


def pack_gate(*, relevance: str, why: str, para: bool, passa: bool,
              para_handles: list[str], passa_handles: list[str],
              n1_field_would_change: bool) -> tuple[str, str]:
    """Jev Choice only for same-encounter mutually exclusive source-supported N1 outcomes."""
    both_source = bool(para and passa and para_handles and passa_handles)
    if both_source:
        return "SOURCE_INSUFFICIENT", "para_and_passa_not_exclusive_at_one_encounter"
    if relevance == "N1_DECISION_RELEVANT":
        return "SOURCE_INSUFFICIENT", "n1_decision_upgraded_without_exclusive_source_choice"
    if n1_field_would_change and not both_source:
        return relevance, why
    return relevance, why


def _build_encounter(*, pavimento: str, beam: str, label: CadEntity, ent: CadEntity,
                     pts: list, partner: dict | None, source: CadSource, end,
                     face: str | None, label_ok: bool) -> dict[str, Any]:
    partner_pts = None
    partner_handle = None
    if partner is not None:
        partner_pts = [list(partner["segment"][0]), list(partner["segment"][1])]
        partner_handle = partner["entity"].handle
    gaps = _encounter_gaps(source, pts, partner_pts, ent.handle) if partner_pts else []
    gaps_here = [g for g in gaps if dist(g.get("at") or [], end) <= 1.0]
    raw_conts = colinear_continuations(source, pts[0], pts[1], ent.handle)
    gap_touch = {
        tuple(g["at"]) for g in gaps if isinstance(g.get("at"), list) and len(g["at"]) == 2
    }
    continuations = []
    for hit in raw_conts:
        at = hit.get("at")
        if at is not None and any(dist(at, gxy) <= END_TOL for gxy in gap_touch):
            continue
        if dist(hit.get("at") or [], end) > END_TOL:
            continue
        continuations.append(hit)
    pillars = _pillars_at(source, end)
    crossings = _crossing_beams(source, end, beam, label.handle)
    para = bool(gaps_here or pillars)
    passa = bool(continuations)
    para_handles = [g["entity"].handle for g in gaps_here] + [p.handle for p in pillars]
    passa_handles = [h["entity"].handle for h in continuations]
    relevance, why = classify_encounter(face=face, para=para, passa=passa, label_ok=label_ok)
    relevance, why = pack_gate(
        relevance=relevance, why=why, para=para, passa=passa,
        para_handles=para_handles, passa_handles=passa_handles,
        n1_field_would_change=False,
    )
    outcomes = _source_outcomes(face=face, para=para, passa=passa)
    at = _round_xy(end)
    handles = [ent.handle, label.handle]
    if partner_handle:
        handles.append(partner_handle)
    handles.extend(para_handles)
    handles.extend(passa_handles)
    handles.extend(c.handle for c in crossings)
    eid = encounter_id(
        pavimento=pavimento, beam=beam, handle=ent.handle, face=face,
        at=at, source_handles=handles,
    )
    polygons = _polygon_hits(nearby_parallel_segments(source, pts, ent.handle)) if pts else []
    return {
        "layer": "FACT",
        "encounter_id": eid,
        "beam": beam,
        "face": face,
        "face_rule": "transverse_min_is_face_a",
        "wall_handle": ent.handle,
        "at": at,
        "wall_segment": pts,
        "partner_handle": partner_handle,
        "source_handles": sorted({h for h in handles if h}),
        "facts": {
            "wall_etype": ent.etype,
            "closed": bool(is_closed_loop(ent)),
            "vertex_count": len(ent.points or []),
            "gap_handles": [g["entity"].handle for g in gaps_here],
            "pillar_markers": [
                {"handle": p.handle, "text": (p.text or "").strip(), "xy": list(p.xy)}
                for p in pillars[:4]
            ],
            "continuation_handles": passa_handles,
            "crossing_beam_labels": [
                {"handle": c.handle, "text": (c.text or "").strip(), "xy": list(c.xy)}
                for c in crossings[:4]
            ],
            "nearby_polygon_handles": [h["entity"].handle for h in polygons[:MAX_NEARBY]],
            "label_handle": label.handle,
            "label_xy": list(label.xy),
        },
        "hypotheses": {
            "layer": "HYPOTHESIS",
            "para": para,
            "passa": passa,
            "para_why": (
                "encounter_gap_or_pillar_marker_at_this_endpoint" if para else None
            ),
            "passa_why": (
                "colinear_open_wall_at_this_endpoint_without_strip_gap" if passa else None
            ),
            "source_outcomes": outcomes,
            "n1_locator_cover_unused": True,
        },
        "n1_relevance": relevance,
        "why": why,
        "label_ok": label_ok,
        "item": beam,
        "classe": "LV",
        "handle": ent.handle,
        "source_outcomes": outcomes,
        "reason": "NEEDS_SOURCE" if relevance == "SOURCE_INSUFFICIENT" else relevance,
        "catalog_id": "lv_source_encounter_face_behavior",
    }


def extract_source_inventory(source: CadSource, *, pavimento: str,
                             beam_names: list[str] | None = None,
                             limit_beams: int | None = None) -> dict[str, Any]:
    """Enumerate LV encounters from DXF labels/topology. Does not read N1."""
    labels = iter_unique_lv_labels(source)
    if beam_names:
        wanted = set(beam_names)
        labels = [lab for lab in labels if (lab.text or "").strip() in wanted]
        missing = sorted(wanted - {(lab.text or "").strip() for lab in labels})
    else:
        missing = []
    beams: list[dict[str, Any]] = []
    encounters: list[dict[str, Any]] = []
    scanned = 0
    for label in labels:
        if limit_beams is not None and scanned >= limit_beams:
            break
        scanned += 1
        name = (label.text or "").strip()
        seeds = seed_strip_walls(source, label)
        if not seeds:
            beams.append({
                "beam": name, "label_handle": label.handle, "label_xy": list(label.xy),
                "walls": [], "reason": "no_source_strip_connected_to_unique_label",
            })
            continue
        wall_map: dict[str, tuple[CadEntity, list]] = {}
        partner_by_handle: dict[str, dict | None] = {}
        for seed_ent, seed_pts in seeds:
            partner = _partner_for_wall(source, seed_pts, seed_ent.handle)
            partner_pts = (
                [list(partner["segment"][0]), list(partner["segment"][1])]
                if partner else None
            )
            for ent, pts in collect_connected_walls(
                    source, seed_ent, seed_pts, partner_pts or seed_pts, label.xy):
                wall_map[ent.handle] = (ent, pts)
                partner_by_handle[ent.handle] = _partner_for_wall(source, pts, ent.handle)
        wall_rows = []
        for handle, (ent, pts) in sorted(wall_map.items()):
            partner = partner_by_handle.get(handle)
            partner_pts = (
                [list(partner["segment"][0]), list(partner["segment"][1])]
                if partner else None
            )
            face = face_from_transverse(pts, partner_pts) if partner_pts else None
            label_ok = _connected_to_label(
                source, ent, pts, partner_pts, label.xy, ent.handle,
            ) if partner_pts else False
            wall_rows.append({
                "handle": handle, "segment": pts, "face": face,
                "partner_handle": partner["entity"].handle if partner else None,
                "label_ok": label_ok,
            })
            for end in pts:
                enc = _build_encounter(
                    pavimento=pavimento, beam=name, label=label, ent=ent, pts=pts,
                    partner=partner, source=source, end=end, face=face, label_ok=label_ok,
                )
                encounters.append(enc)
        beams.append({
            "beam": name, "label_handle": label.handle, "label_xy": list(label.xy),
            "walls": wall_rows,
        })
    denominators = {
        "unique_lv_labels": len(labels) if not beam_names else len(iter_unique_lv_labels(source)),
        "labels_scanned": scanned,
        "labels_missing_unique_text": missing,
        "beams_with_strip": sum(1 for b in beams if b.get("walls")),
        "source_walls": sum(len(b.get("walls") or []) for b in beams),
        "encounters": len(encounters),
        "encounters_para_only": sum(
            1 for e in encounters if e["hypotheses"]["para"] and not e["hypotheses"]["passa"]
        ),
        "encounters_passa_only": sum(
            1 for e in encounters if e["hypotheses"]["passa"] and not e["hypotheses"]["para"]
        ),
        "encounters_para_and_passa": sum(
            1 for e in encounters if e["hypotheses"]["para"] and e["hypotheses"]["passa"]
        ),
        "encounters_neither": sum(
            1 for e in encounters if not e["hypotheses"]["para"] and not e["hypotheses"]["passa"]
        ),
    }
    inventory = {
        "schema": INVENTORY_SCHEMA,
        "catalog_revision": CATALOG_V3_REVISION,
        "factory_version": FACTORY_V3_VERSION,
        "pavimento": pavimento,
        "source_dxf_sha256": source.dxf_sha256,
        "n1_used": False,
        "note": (
            "Geometry FACT and PARA/PASSA HYPOTHESIS only. N1 locators/values "
            "are absent. Locator-cover length is never PASSA."
        ),
        "denominators": denominators,
        "beams": beams,
        "encounters": encounters,
    }
    inventory["inventory_sha256"] = sha256_json(
        {k: v for k, v in inventory.items() if k != "inventory_sha256"}
    )
    return inventory


def compare_n1_sidecar(inventory: dict[str, Any], snapshot: N1Snapshot | None,
                       source: CadSource) -> dict[str, Any]:
    """Isolated N1 comparison. Must not be copied into Jev evidence."""
    rows: list[dict[str, Any]] = []
    n1_names = set(snapshot.names("LV")) if snapshot else set()
    source_names = {b["beam"] for b in inventory.get("beams") or []}
    for enc in inventory.get("encounters") or []:
        beam = enc["beam"]
        n1_item = snapshot.get("LV", beam) if snapshot else None
        cells = list((n1_item.extras.get("cells") or []) if n1_item else [])
        matches = []
        locator_cover = False
        locator_miss_cells = 0
        for cell in cells:
            pts = cell.get("points") or []
            if len(pts) != 2:
                continue
            wall = unique_source_wall(source, pts[0], pts[1])
            handle = wall["entity"].handle if wall else None
            cover = bool(wall and wall.get("match") == "cover")
            if cover:
                locator_cover = True
            end_near = any(dist(pts[i], enc["at"]) <= END_TOL for i in (0, 1))
            handle_match = handle == enc["wall_handle"]
            if wall is None:
                locator_miss_cells += 1
            if handle_match or end_near:
                matches.append({
                    "kind": cell.get("kind"),
                    "side": cell.get("side"),
                    "behavior": cell.get("behavior"),
                    "index": cell.get("index"),
                    "locator_points": [_round_xy(pts[0]), _round_xy(pts[1])],
                    "matched_source_handle": handle,
                    "locator_match": (wall or {}).get("match"),
                    "locator_cover": cover,
                    "endpoint_near_encounter": end_near,
                })
        n1_kinds = [m.get("kind") for m in matches if m.get("kind")]
        source_outcomes = list(enc.get("source_outcomes") or [])
        n1_outcomes = []
        for m in matches:
            side = str(m.get("side") or "")
            beh = str(m.get("behavior") or "")
            if side.upper() in {"A", "B"} and beh.upper() in {"PARA", "PASSA"}:
                n1_outcomes.append(outcome_id(side.upper(), beh.upper()))
        would_change = bool(source_outcomes) and bool(n1_outcomes) and (
            set(source_outcomes) != set(n1_outcomes)
        )
        relevance, why = pack_gate(
            relevance=enc["n1_relevance"], why=enc["why"],
            para=bool(enc["hypotheses"]["para"]),
            passa=bool(enc["hypotheses"]["passa"]),
            para_handles=list(enc["facts"].get("gap_handles") or []) + [
                p["handle"] for p in enc["facts"].get("pillar_markers") or [] if p.get("handle")
            ],
            passa_handles=list(enc["facts"].get("continuation_handles") or []),
            n1_field_would_change=would_change,
        )
        if would_change and relevance != "N1_DECISION_RELEVANT":
            tag = "NOT_N1_DECISION"
            detail = "n1_differs_but_no_same_encounter_exclusive_source_choice"
        else:
            tag = relevance
            detail = why
        rows.append({
            "layer": "N1_COMPARISON",
            "encounter_id": enc["encounter_id"],
            "beam": beam,
            "wall_handle": enc["wall_handle"],
            "at": enc["at"],
            "face": enc.get("face"),
            "source_outcomes": source_outcomes,
            "n1_present": n1_item is not None,
            "n1_cell_matches": matches,
            "n1_kinds": n1_kinds,
            "n1_outcomes": n1_outcomes,
            "locator_cover_seen": locator_cover,
            "locator_cover_not_used_as_passa": True,
            "n1_locator_miss_cells_on_beam": locator_miss_cells,
            "n1_field_would_change": would_change,
            "n1_relevance": tag,
            "why": detail,
        })
    sidecar = {
        "schema": SIDECAR_SCHEMA,
        "catalog_revision": CATALOG_V3_REVISION,
        "source_inventory_sha256": inventory.get("inventory_sha256"),
        "n1_source": snapshot.source if snapshot else None,
        "n1_fingerprint_sha256": snapshot.fingerprint_sha256 if snapshot else None,
        "note": (
            "Isolated sidecar. Do not copy into Jev evidence. "
            "N2/N3/N4 are unused. Locator cover is not PASSA."
        ),
        "denominators": {
            "source_beams": len(source_names),
            "n1_lv_items": len(n1_names),
            "source_not_in_n1": sorted(source_names - n1_names),
            "n1_not_in_source_unique_labels": sorted(n1_names - source_names),
            "encounters_compared": len(rows),
            "locator_cover_rows": sum(1 for r in rows if r["locator_cover_seen"]),
            "n1_field_would_change": sum(1 for r in rows if r["n1_field_would_change"]),
            "n1_decision_relevant": sum(
                1 for r in rows if r["n1_relevance"] == "N1_DECISION_RELEVANT"
            ),
        },
        "rows": rows,
    }
    sidecar["sidecar_sha256"] = sha256_json(
        {k: v for k, v in sidecar.items() if k != "sidecar_sha256"}
    )
    return sidecar


def _packet_from_encounter(enc: dict[str, Any], source: CadSource, pavimento: str
                           ) -> ConflictCandidate | None:
    """Only for true same-encounter exclusive Choice. Stage 1 expects none."""
    if enc.get("n1_relevance") != "N1_DECISION_RELEVANT":
        return None
    outcomes = list(enc.get("source_outcomes") or [])
    if len(outcomes) < 2:
        return None
    if enc["hypotheses"]["para"] and enc["hypotheses"]["passa"]:
        return None
    option_rows = {}
    for oid in N1_OUTCOMES:
        if oid not in outcomes:
            continue
        face_ch, behavior = oid.split("_", 1)
        option_rows[oid] = (
            f"N1 cell assignment FACE_{face_ch} {behavior} for source wall "
            f"handle {enc['wall_handle']} at encounter {enc['at']}."
        )
    question = lv_v3_question(option_rows)
    if len(question["criteria"]) < 3:
        return None
    ent = source.by_handle(enc["wall_handle"])
    if ent is None:
        return None
    pts = enc["wall_segment"]
    nearby = nearby_parallel_segments(source, pts, ent.handle)
    partners = _partner_walls(nearby)
    polygons = _polygon_hits(nearby)
    line_rows = [_nearby_row(hit) for hit in partners[:MAX_NEARBY]]
    polygon_rows = [_nearby_row(hit) for hit in polygons[:MAX_NEARBY]]
    label = source.by_handle(enc["facts"]["label_handle"])
    target = compact_entity(ent, {
        "role": "cell_line",
        "closed": False,
        "vertex_count": len(ent.points or []),
        "points": pts,
        "selected_edge": pts,
        "bbox": [
            min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts),
        ],
    })
    evidence = {
        "target": target,
        "beam_label": compact_entity(label, {"role": "beam_label", "include_points": False})
        if label else {"role": "beam_label", "handle": enc["facts"]["label_handle"]},
        "nearby_lines": line_rows,
        "nearby_polygon_edges": polygon_rows,
        "encounter_gaps": [
            {"handle": h, "role": "encounter_gap"} for h in enc["facts"]["gap_handles"]
        ],
        "colinear_continuations": [
            {"handle": h, "role": "colinear_continuation"}
            for h in enc["facts"]["continuation_handles"]
        ],
        "pillar_markers": enc["facts"]["pillar_markers"],
        "search": {"center": enc["at"], "units": "dxf_drawing"},
        "relation_provenance": {
            "n1_field_unused": True,
            "n1_fundo_used_for_relation": False,
            "n1_locator_unused": True,
            "face_rule": "transverse_min_is_face_a",
            "para_support": "encounter_gap_or_pillar_marker_at_this_endpoint",
            "passa_support": "colinear_continuation_at_same_encounter",
            "encounter_id": enc["encounter_id"],
        },
    }
    return ConflictCandidate(
        case_id=enc["encounter_id"], classe="LV", item=enc["beam"], campo="lv_cell",
        unit_kind="source_encounter", unit_id=enc["encounter_id"],
        trigger="source_face_behavior_conflict",
        severity="high",
        alternatives=[{"id": oid, "role": "n1_cell_assignment"} for oid in outcomes],
        evidence=evidence,
        included=[evidence["target"], evidence["beam_label"], *line_rows, *polygon_rows],
        excluded=[],
        decisive_handles=list(enc["source_handles"]),
        question=question,
        physical_unit={"kind": "source_encounter", "encounter_id": enc["encounter_id"]},
        cad_rules=[
            "Encounter is one source wall handle plus one endpoint.",
            "FACE_A is the strip wall with the smaller transverse coordinate.",
            "PARA requires a strip-width gap or pillar marker at this same endpoint.",
            "PASSA requires a colinear open continuation at this same endpoint.",
            "PARA at one endpoint and PASSA at the other are separate encounters.",
            "N1 locator cover is never PASSA.",
        ],
        catalog_id="lv_source_encounter_face_behavior",
        baseline_value=None,
        n1_relevance=enc["n1_relevance"],
        n1_relevance_why=enc["why"],
        catalog_revision=CATALOG_V3_REVISION,
    )


def withdrawal_control_v3(candidate: ConflictCandidate) -> dict[str, Any]:
    evidence = _control_shell(
        candidate.evidence,
        nearby_lines=[],
        nearby_polygon_edges=[],
        encounter_gaps=[],
        colinear_continuations=[],
        pillar_markers=[],
        control_note="listed partner walls, encounter gaps, continuations withdrawn",
    )
    return {"id": "topology_removed", "expected_choice": "INSUFFICIENT", "evidence": evidence}


def reversed_control_v3(candidate: ConflictCandidate) -> dict[str, Any] | None:
    lines = list(reversed(candidate.evidence.get("nearby_lines") or []))
    polys = list(reversed(candidate.evidence.get("nearby_polygon_edges") or []))
    if len(lines) + len(polys) < 2:
        return None
    return {
        "id": "candidate_order_reversed",
        "evidence": _control_shell(
            candidate.evidence, nearby_lines=lines, nearby_polygon_edges=polys,
        ),
    }


def run_lv_v3(*, snapshot: N1Snapshot | None, source: CadSource, identity_base: dict,
              items: list[str] | None = None, limit: int | None = None) -> dict[str, Any]:
    from .factory import emit_case, _record_audits

    inventory = extract_source_inventory(
        source, pavimento=identity_base["pavimento"],
        beam_names=items, limit_beams=limit,
    )
    sidecar = compare_n1_sidecar(inventory, snapshot, source)
    sidecar_by_id = {row["encounter_id"]: row for row in sidecar.get("rows") or []}
    packed: list[dict[str, Any]] = []
    unpackable: list[dict[str, Any]] = []
    discards: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    dummy_item = None
    if snapshot is not None:
        names = snapshot.names("LV")
        dummy_item = snapshot.get("LV", names[0]) if names else None
    for enc in inventory.get("encounters") or []:
        side = sidecar_by_id.get(enc["encounter_id"]) or {}
        relevance = side.get("n1_relevance") or enc["n1_relevance"]
        why = side.get("why") or enc["why"]
        audit = {
            "item": enc["beam"],
            "classe": "LV",
            "catalog_id": "lv_source_encounter_face_behavior",
            "n1_relevance": relevance,
            "why": why,
            "handle": enc["wall_handle"],
            "encounter_id": enc["encounter_id"],
            "at": enc["at"],
            "face": enc.get("face"),
            "source_outcomes": enc.get("source_outcomes") or [],
            "reason": "NEEDS_SOURCE" if relevance == "SOURCE_INSUFFICIENT" else relevance,
        }
        audits.append(audit)
        if relevance != "N1_DECISION_RELEVANT":
            continue
        cand = _packet_from_encounter(enc, source, identity_base["pavimento"])
        if cand is None:
            unpackable.append({
                "status": "UNPACKABLE", "reason": "NEEDS_SOURCE",
                "item": enc["beam"], "classe": "LV",
                "detail": "n1_decision_without_packable_exclusive_choice",
                "n1_relevance": "SOURCE_INSUFFICIENT",
                "handle": enc["wall_handle"],
            })
            continue
        if dummy_item is None:
            unpackable.append({
                "status": "UNPACKABLE", "reason": "NEEDS_SOURCE",
                "item": enc["beam"], "classe": "LV",
                "detail": "n1_snapshot_required_to_emit_packet",
                "n1_relevance": relevance, "handle": enc["wall_handle"],
            })
            continue
        emitted = emit_case(
            cand, identity_base=identity_base, snapshot=snapshot,
            source=source, n1_item=dummy_item,
        )
        if emitted["status"] == "UNPACKABLE":
            unpackable.append(emitted)
        else:
            packed.append(emitted)
    _record_audits(audits, discards=discards, unpackable=unpackable)
    labels_without_n1 = [
        name for name in (inventory["denominators"].get("labels_missing_unique_text") or [])
    ]
    for name in labels_without_n1:
        discards.append({
            "item": name, "classe": "LV", "reason": "NO_UNIQUE_LABEL",
            "n1_relevance": "SOURCE_INSUFFICIENT",
        })
    relevance_counts = Counter(row.get("n1_relevance") or "UNSET" for row in audits)
    return {
        "schema": "jev_calibration_dry_run_audit/1",
        "factory_version": FACTORY_V3_VERSION,
        "scanned": inventory["denominators"]["labels_scanned"],
        "packed": len(packed),
        "unpackable": len(unpackable),
        "discarded": len(discards),
        "discard_reasons": dict(Counter(row.get("reason") or "unknown" for row in discards)),
        "unpackable_reasons": dict(Counter(row.get("reason") or "unknown" for row in unpackable)),
        "cases": packed,
        "unpackable_rows": unpackable,
        "discards": discards,
        "cell_audits": audits,
        "n1_relevance_counts": dict(relevance_counts),
        "catalog_revision": CATALOG_V3_REVISION,
        "catalog_sha256": catalog_v3_hash(),
        "catalog": "v3",
        "audit_sha256": None,
        "source_inventory": inventory,
        "n1_sidecar": sidecar,
        "denominators": {
            **inventory["denominators"],
            **{f"sidecar_{k}": v for k, v in (sidecar.get("denominators") or {}).items()},
        },
        "catalog_doc": CATALOG_V3,
        "jev_api_called": False,
        "g4": "NOT_RUN",
    }
