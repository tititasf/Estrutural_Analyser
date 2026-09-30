"""LV v2: source-grounded face A/B × PARA/PASSA. N1 endpoints locate; N1 fields stay out."""
from __future__ import annotations

from typing import Any

from .adapters_lv import (
    MAX_NEARBY,
    _control_shell,
    _nearby_row,
    _unique_label,
)
from .adapters_pil import ConflictCandidate
from .cad_source import CadSource
from .catalog_v2 import (
    CATALOG_V2_REVISION,
    N1_OUTCOMES,
    lv_v2_question,
    outcome_id,
)
from .geometry_util import (
    BEAM_NAME_RE,
    PILLAR_NAME_RE,
    classify_source_curve,
    colinear_continuations,
    compact_entity,
    dist,
    entity_as_segments,
    face_from_transverse,
    is_closed_loop,
    is_strip_encounter_gap,
    midpoint,
    nearby_parallel_segments,
    parallel,
    polygon_area,
    unique_source_wall,
    unique_vertices,
)
from .n1_snapshot import N1Item

MAX_WALL_UNITS = 8
PILLAR_RADIUS = 18.0


def _locator_points(cell: dict) -> list | None:
    pts = cell.get("points") or []
    if len(pts) != 2:
        return None
    return pts


def _partner_walls(nearby: list[dict]) -> list[dict]:
    return [hit for hit in nearby if hit.get("classification") != "closed_polygon_edge"]


def _polygon_hits(nearby: list[dict]) -> list[dict]:
    return [hit for hit in nearby if hit.get("classification") == "closed_polygon_edge"]


def _pillar_markers(source: CadSource, p0, p1) -> list:
    found = []
    seen: set[str] = set()
    for end in (p0, p1):
        for ent in source.entities_near(float(end[0]), float(end[1]), PILLAR_RADIUS,
                                        types=["TEXT", "MTEXT"]):
            text = (ent.text or "").strip()
            if ent.handle in seen or not PILLAR_NAME_RE.fullmatch(text):
                continue
            seen.add(ent.handle)
            found.append(ent)
    return found


def _encounter_gaps(source: CadSource, cell_pts, partner_pts, handle: str) -> list[dict]:
    if not partner_pts or len(partner_pts) != 2:
        return []
    found: list[dict] = []
    seen: set[str] = set()
    for end in cell_pts:
        radius = max(dist(cell_pts[0], cell_pts[1]) / 4.0, 30.0)
        for ent in source.entities_near(float(end[0]), float(end[1]), radius,
                                        types=["LWPOLYLINE", "POLYLINE"]):
            if ent.handle == handle or ent.handle in seen:
                continue
            if not is_strip_encounter_gap(ent, cell_pts, partner_pts, end):
                continue
            seen.add(ent.handle)
            found.append({
                "entity": ent,
                "at": [round(float(end[0]), 3), round(float(end[1]), 3)],
                "closed": True,
                "vertex_count": len(ent.points or []),
                "area": round(polygon_area(ent.points), 3),
                "classification": "encounter_gap",
                "selected_edge": None,
                "bbox": [round(ent.minx, 3), round(ent.miny, 3),
                         round(ent.maxx, 3), round(ent.maxy, 3)],
                "points": ent.points,
                "provenance": {
                    "source": "fase1_dxf",
                    "method": "closed_rectangle_strip_width_touches_endpoint",
                    "n1_fundo_used": False,
                    "classification": "encounter_gap",
                },
            })
    found.sort(key=lambda row: row["entity"].handle)
    return found


def _source_outcomes(*, face: str | None, para: bool, passa: bool) -> list[str]:
    if face not in {"A", "B"}:
        return []
    out = []
    if para:
        out.append(outcome_id(face, "PARA"))
    if passa:
        out.append(outcome_id(face, "PASSA"))
    return out


def endpoint_behavior_flags(cell_pts, gaps: list[dict], pillars: list,
                            continuations: list[dict]) -> list[dict[str, Any]]:
    """Attach PARA/PASSA evidence to each wall endpoint (one encounter each)."""
    rows: list[dict[str, Any]] = []
    for end in cell_pts:
        para = any(dist(gap.get("at") or [], end) <= 1.0 for gap in gaps)
        para = para or any(dist(getattr(p, "xy", (None, None)), end) <= PILLAR_RADIUS
                           for p in pillars)
        passa = any(dist(hit.get("at") or [], end) <= 6.0 for hit in continuations)
        rows.append({
            "at": [round(float(end[0]), 3), round(float(end[1]), 3)],
            "para": bool(para),
            "passa": bool(passa),
        })
    return rows


def classify_relevance(*, wall: dict | None, face: str | None,
                       para: bool, passa: bool, label_ok: bool,
                       endpoint_flags: list[dict[str, Any]] | None = None
                       ) -> tuple[str, str]:
    if wall is None:
        return "SOURCE_INSUFFICIENT", "no_dxf_line_matches_n1_cell"
    if not label_ok:
        return "SOURCE_INSUFFICIENT", "unique_label_not_connected_to_strip"
    outcomes = _source_outcomes(face=face, para=para, passa=passa)
    if face not in {"A", "B"}:
        return "CONVENTION_INDETERMINATE", "face_not_unique_from_source_strip"
    if para and passa:
        flags = list(endpoint_flags or [])
        competing = [row for row in flags if row.get("para") and row.get("passa")]
        split = (
            any(row.get("para") and not row.get("passa") for row in flags)
            and any(row.get("passa") and not row.get("para") for row in flags)
            and not competing
        )
        if split:
            return "SOURCE_INSUFFICIENT", "para_and_passa_on_distinct_encounters"
        if competing:
            return "SOURCE_INSUFFICIENT", "para_and_passa_not_exclusive_at_one_encounter"
        return "SOURCE_INSUFFICIENT", "para_and_passa_not_exclusive_for_one_wall_handle"
    if len(outcomes) >= 2:
        return "SOURCE_INSUFFICIENT", "para_and_passa_not_exclusive_for_one_wall_handle"
    if len(outcomes) == 1:
        return "CAD_REDUNDANT", "single_source_supported_n1_outcome:" + outcomes[0]
    return "SOURCE_INSUFFICIENT", "no_source_supported_para_or_passa"


def _label_in_bbox(label_xy, minx, miny, maxx, maxy, *, margin: float = 40.0) -> bool:
    x, y = float(label_xy[0]), float(label_xy[1])
    return (minx - margin) <= x <= (maxx + margin) and (miny - margin) <= y <= (maxy + margin)


def _walls_touching(source: CadSource, xy, parallel_pts, exclude: set[str], *, gap: float = 8.0):
    hits = []
    for ent in source.entities_near(float(xy[0]), float(xy[1]), gap + 12.0,
                                    types=["LINE", "LWPOLYLINE"]):
        if ent.handle in exclude or classify_source_curve(ent) != "wall_line":
            continue
        for a, b in entity_as_segments(ent):
            if min(dist(a, xy), dist(b, xy)) > gap:
                continue
            if not parallel(parallel_pts[0], parallel_pts[1], a, b):
                continue
            hits.append((ent, [list(a), list(b)]))
            break
    return hits


def _connected_to_label(source: CadSource, wall_ent, cell_pts, partner_pts,
                        label_xy, handle: str) -> bool:
    if not partner_pts:
        return False
    from .geometry_util import label_near_strip

    ok, _where = label_near_strip(label_xy, cell_pts, partner_pts)
    if ok:
        return True
    visited = {handle}
    queue = [cell_pts]
    minx = min(float(p[0]) for p in cell_pts + partner_pts)
    maxx = max(float(p[0]) for p in cell_pts + partner_pts)
    miny = min(float(p[1]) for p in cell_pts + partner_pts)
    maxy = max(float(p[1]) for p in cell_pts + partner_pts)
    hops = 0
    while queue and hops < 16:
        pts = queue.pop(0)
        hops += 1
        for p in pts:
            minx, maxx = min(minx, float(p[0])), max(maxx, float(p[0]))
            miny, maxy = min(miny, float(p[1])), max(maxy, float(p[1]))
        if _label_in_bbox(label_xy, minx, miny, maxx, maxy):
            return True
        for hit in colinear_continuations(source, pts[0], pts[1], handle, gap=12.0):
            ent = hit["entity"]
            if ent.handle in visited:
                continue
            visited.add(ent.handle)
            queue.append([list(hit["segment"][0]), list(hit["segment"][1])])
        for gap in _encounter_gaps(source, pts, partner_pts, handle):
            gent = gap["entity"]
            if gent.handle in visited:
                continue
            visited.add(gent.handle)
            for vx, vy in unique_vertices(gent.points):
                minx, maxx = min(minx, vx), max(maxx, vx)
                miny, maxy = min(miny, vy), max(maxy, vy)
                for ent, seg in _walls_touching(source, [vx, vy], pts, visited):
                    visited.add(ent.handle)
                    queue.append(seg)
        if _label_in_bbox(label_xy, minx, miny, maxx, maxy):
            return True
    return _label_in_bbox(label_xy, minx, miny, maxx, maxy)


def _audit_row(item: str, *, cell_index: Any, relevance: str, why: str,
               handle: str | None = None, outcomes: list[str] | None = None,
               match: str | None = None) -> dict[str, Any]:
    return {
        "item": item,
        "classe": "LV",
        "catalog_id": "lv_cell_face_behavior_choice",
        "n1_relevance": relevance,
        "why": why,
        "handle": handle,
        "locator_index": cell_index,
        "source_outcomes": outcomes or [],
        "match": match,
        "reason": "NEEDS_SOURCE" if relevance == "SOURCE_INSUFFICIENT" else relevance,
    }


def discover_lv_v2(item: N1Item, source: CadSource, *, pavimento: str
                   ) -> dict[str, Any]:
    if item.name.startswith("VF"):
        return {"item": item.name, "classe": "LV", "reason": "NOT_LV_OCCURRENCE",
                "n1_relevance": "SOURCE_INSUFFICIENT", "packets": [], "audits": []}
    label, err = _unique_label(source, item.name)
    if err:
        err["n1_relevance"] = "SOURCE_INSUFFICIENT"
        err["packets"] = []
        err["audits"] = []
        return err
    packets: list[ConflictCandidate] = []
    audits: list[dict[str, Any]] = []
    seen: set[str] = set()
    needs_wall = 0
    cells = list(item.extras.get("cells") or [])
    for cell in cells:
        pts = _locator_points(cell)
        if pts is None:
            audits.append(_audit_row(item.name, cell_index=cell.get("index"),
                                     relevance="SOURCE_INSUFFICIENT",
                                     why="locator_not_two_endpoints"))
            continue
        wall = unique_source_wall(source, pts[0], pts[1])
        if wall is None:
            needs_wall += 1
            audits.append(_audit_row(
                item.name, cell_index=cell.get("index"),
                relevance="SOURCE_INSUFFICIENT", why="no_dxf_line_matches_n1_cell",
            ))
            continue
        handle = wall["entity"].handle
        if handle in seen:
            audits.append(_audit_row(
                item.name, cell_index=cell.get("index"),
                relevance="CAD_REDUNDANT", why="duplicate_source_wall_handle",
                handle=handle, match=wall["match"],
            ))
            continue
        seen.add(handle)
        cand, audit = _packet_v2(
            item, pavimento, label, pts, wall, source,
            leftover=[{"handle": h, "reason": "other_wall_of_item"} for h in seen if h != handle],
        )
        audits.append(audit)
        if cand is not None:
            packets.append(cand)
        if len(packets) >= MAX_WALL_UNITS:
            break
    if not packets:
        detail = "no_dxf_line_matches_n1_cell" if needs_wall and not seen else "no_n1_decision_relevant_wall"
        return {
            "item": item.name,
            "classe": "LV",
            "reason": "NEEDS_SOURCE" if detail == "no_dxf_line_matches_n1_cell" else "NO_N1_DECISION",
            "detail": detail,
            "n1_relevance": "SOURCE_INSUFFICIENT" if detail == "no_dxf_line_matches_n1_cell"
            else (audits[0]["n1_relevance"] if audits else "SOURCE_INSUFFICIENT"),
            "packets": [],
            "audits": audits,
        }
    return {"packets": packets, "audits": audits, "item": item.name, "classe": "LV"}


def _packet_v2(item, pavimento, label, locator_pts, wall, source, leftover
               ) -> tuple[ConflictCandidate | None, dict[str, Any]]:
    ent = wall["entity"]
    cell_pts = [list(wall["segment"][0]), list(wall["segment"][1])]
    nearby = nearby_parallel_segments(source, cell_pts, ent.handle)
    partners = _partner_walls(nearby)
    polygons = _polygon_hits(nearby)
    partner_pts = None
    face = None
    if len(partners) == 1:
        partner_pts = [list(partners[0]["segment"][0]), list(partners[0]["segment"][1])]
        face = face_from_transverse(cell_pts, partner_pts)
    gaps = _encounter_gaps(source, cell_pts, partner_pts, ent.handle) if partner_pts else []
    raw_conts = colinear_continuations(source, cell_pts[0], cell_pts[1], ent.handle)
    gap_touch = {
        tuple(gap["at"]) for gap in gaps if isinstance(gap.get("at"), list) and len(gap["at"]) == 2
    }
    continuations = []
    for hit in raw_conts:
        at = hit.get("at")
        if at is not None and any(dist(at, gxy) <= 6.0 for gxy in gap_touch):
            continue
        continuations.append(hit)
    pillars = _pillar_markers(source, cell_pts[0], cell_pts[1])
    cover_passa = bool(wall.get("extends_beyond_locator") and wall["match"] == "cover")
    para = bool(gaps or pillars)
    passa = bool(continuations) or cover_passa
    endpoint_flags = endpoint_behavior_flags(cell_pts, gaps, pillars, continuations)
    label_ok = _connected_to_label(source, ent, cell_pts, partner_pts, label.xy, ent.handle)
    outcomes = _source_outcomes(face=face, para=para, passa=passa)
    relevance, why = classify_relevance(
        wall=wall, face=face, para=para, passa=passa, label_ok=label_ok,
        endpoint_flags=endpoint_flags,
    )
    audit = _audit_row(
        item.name, cell_index=ent.handle, relevance=relevance, why=why,
        handle=ent.handle, outcomes=outcomes, match=wall["match"],
    )
    if relevance != "N1_DECISION_RELEVANT":
        return None, audit
    option_rows = {}
    for oid in N1_OUTCOMES:
        if oid not in outcomes:
            continue
        face_ch, behavior = oid.split("_", 1)
        option_rows[oid] = (
            f"N1 cell assignment FACE_{face_ch} {behavior} for source {ent.etype} "
            f"handle {ent.handle} from {cell_pts[0]} to {cell_pts[1]} "
            f"(closed={bool(is_closed_loop(ent))}; vertex_count={len(ent.points or [])})."
        )
    question = lv_v2_question(option_rows)
    if len(question["criteria"]) < 3:
        audit["n1_relevance"] = "SOURCE_INSUFFICIENT"
        audit["why"] = "fewer_than_two_n1_outcomes_plus_insufficient"
        audit["reason"] = "NEEDS_SOURCE"
        return None, audit
    mid = midpoint(cell_pts)
    neighbors = [e for e in source.entities_near(mid[0], mid[1], 80, types=["TEXT", "MTEXT"])
                 if BEAM_NAME_RE.fullmatch((e.text or "").strip()) and e.handle != label.handle]
    line_rows = [_nearby_row(hit) for hit in partners[:MAX_NEARBY]]
    polygon_rows = [_nearby_row(hit) for hit in polygons[:MAX_NEARBY]]
    gap_rows = []
    for hit in gaps[:MAX_NEARBY]:
        gap_rows.append(compact_entity(hit["entity"], {
            "role": "encounter_gap",
            "closed": True,
            "vertex_count": hit["vertex_count"],
            "bbox": hit["bbox"],
            "points": [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in (hit["entity"].points or [])[:24]],
            "provenance": dict(hit["provenance"]),
        }))
    cont_rows = []
    for hit in continuations[:MAX_NEARBY]:
        cont_rows.append(compact_entity(hit["entity"], {
            "role": "colinear_continuation",
            "closed": False,
            "vertex_count": len(hit["entity"].points or []),
            "points": [list(hit["segment"][0]), list(hit["segment"][1])],
            "selected_edge": [list(hit["segment"][0]), list(hit["segment"][1])],
            "provenance": {
                "source": "fase1_dxf",
                "method": "colinear_open_wall_at_endpoint",
                "gap": hit["gap"],
                "n1_fundo_used": False,
            },
        }))
    pillar_rows = [compact_entity(e, {"role": "pillar_marker", "include_points": False})
                   for e in pillars[:4]]
    target = compact_entity(ent, {
        "role": "cell_line",
        "closed": False,
        "vertex_count": len(ent.points or []),
        "points": [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in (ent.points or cell_pts)[:24]],
        "selected_edge": cell_pts,
        "match": wall["match"],
        "bbox": [
            round(min(float(p[0]) for p in cell_pts), 3),
            round(min(float(p[1]) for p in cell_pts), 3),
            round(max(float(p[0]) for p in cell_pts), 3),
            round(max(float(p[1]) for p in cell_pts), 3),
        ],
    })
    evidence = {
        "target": target,
        "beam_label": compact_entity(label, {"role": "beam_label", "include_points": False}),
        "nearby_lines": line_rows,
        "nearby_polygon_edges": polygon_rows,
        "encounter_gaps": gap_rows,
        "colinear_continuations": cont_rows,
        "pillar_markers": pillar_rows,
        "neighbor_beam_labels": [compact_entity(e, {"role": "neighbor_beam", "include_points": False})
                                 for e in neighbors[:3]],
        "search": {"center": mid, "units": "dxf_drawing"},
        "relation_provenance": {
            "cell_match": (
                "unique_source_wall_same_endpoints" if wall["match"] == "exact"
                else "unique_source_wall_covers_locator_endpoints"
            ),
            "n1_field_unused": True,
            "n1_fundo_used_for_relation": False,
            "face_rule": "transverse_min_is_face_a",
            "para_support": "encounter_gap_or_pillar_marker_at_endpoint",
            "passa_support": "colinear_continuation_at_same_encounter",
            "endpoint_flags": endpoint_flags,
            "label": "unique_text_value_on_source_dxf",
        },
    }
    extras = []
    if neighbors:
        extras.append(_neighbor_control_v2(evidence, neighbors[0]))
    alternatives = [{"id": oid, "role": "n1_cell_assignment"} for oid in outcomes]
    case_id = f"{pavimento}|LV|{item.name}|lv_cell|wall:{ent.handle}"
    cand = ConflictCandidate(
        case_id=case_id, classe="LV", item=item.name, campo="lv_cell",
        unit_kind="cell", unit_id=f"wall:{ent.handle}",
        trigger="source_face_behavior_conflict",
        severity="high",
        alternatives=alternatives, evidence=evidence,
        included=[evidence["target"], evidence["beam_label"], *line_rows, *polygon_rows,
                  *gap_rows, *cont_rows],
        excluded=list(leftover[:20]),
        decisive_handles=[ent.handle, *[row["handle"] for row in line_rows],
                          *[row["handle"] for row in gap_rows],
                          *[row["handle"] for row in cont_rows]],
        question=question,
        physical_unit={"kind": "cell", "source_handle": ent.handle, "match": wall["match"],
                       "n1_relevance": relevance},
        cad_rules=[
            "Locator endpoints come from the N1 cell geometry only; the N1 field value is unused.",
            "Target is the unique source-DXF open wall that carries those endpoints.",
            "FACE_A is the strip wall with the smaller transverse coordinate; FACE_B is the other.",
            "PARA requires a strip-width encounter gap or a pillar-name marker at an endpoint.",
            "PASSA requires a colinear open continuation at the same encounter.",
            "PARA at one endpoint and PASSA at the other are separate encounters, not a Choice.",
            "Closed slab contours stay in nearby_polygon_edges and are not wall options.",
        ],
        extra_controls=extras,
        catalog_id="lv_cell_face_behavior_choice",
        baseline_value=None,
        n1_relevance=relevance,
        n1_relevance_why=why,
        catalog_revision=CATALOG_V2_REVISION,
    )
    return cand, audit


def _neighbor_control_v2(evidence: dict, neighbor) -> dict[str, Any]:
    label = compact_entity(neighbor, {"role": "neighbor_as_only_label", "include_points": False}) \
        if not isinstance(neighbor, dict) else neighbor
    return {
        "id": "neighbor_label_only",
        "expected_choice": "INSUFFICIENT",
        "evidence": _control_shell(
            evidence,
            beam_label=label,
            nearby_lines=[],
            nearby_polygon_edges=[],
            encounter_gaps=[],
            colinear_continuations=[],
            pillar_markers=[],
            control_note="partner walls, encounter gaps, continuations and the unique item label withdrawn; neighbor label remains",
        ),
    }


def withdrawal_control_v2(candidate: ConflictCandidate) -> dict[str, Any]:
    evidence = _control_shell(
        candidate.evidence,
        nearby_lines=[],
        nearby_polygon_edges=[],
        encounter_gaps=[],
        colinear_continuations=[],
        pillar_markers=[],
        control_note="listed partner walls, encounter gaps, continuations and closed contours withdrawn",
    )
    return {"id": "topology_removed", "expected_choice": "INSUFFICIENT", "evidence": evidence}


def reversed_control_v2(candidate: ConflictCandidate) -> dict[str, Any] | None:
    lines = list(reversed(candidate.evidence.get("nearby_lines") or []))
    polys = list(reversed(candidate.evidence.get("nearby_polygon_edges") or []))
    gaps = list(reversed(candidate.evidence.get("encounter_gaps") or []))
    cont = list(reversed(candidate.evidence.get("colinear_continuations") or []))
    neigh = list(reversed(candidate.evidence.get("neighbor_beam_labels") or []))
    if len(lines) + len(gaps) + len(cont) + len(neigh) < 2:
        return None
    return {
        "id": "candidate_order_reversed",
        "evidence": _control_shell(
            candidate.evidence,
            nearby_lines=lines,
            nearby_polygon_edges=polys,
            encounter_gaps=gaps,
            colinear_continuations=cont,
            neighbor_beam_labels=neigh,
        ),
    }
