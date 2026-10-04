"""LV cell×nearby-line discovery. N1 locates discord; source DXF supplies geometry."""
from __future__ import annotations

from typing import Any

from .adapters_pil import ConflictCandidate
from .cad_source import CadSource
from .catalog_v1 import lv_question
from .geometry_util import (
    BEAM_NAME_RE, compact_entity, label_near_strip, match_dxf_line, midpoint,
    nearby_parallel_segments, rounded_points,
)
from .n1_snapshot import N1Item

MAX_UNITS = 3
REMOTE_CM = 30.0
MAX_NEARBY = 4


def _fundo_union(item: N1Item):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    polys = []
    for row in item.extras.get("fundo") or []:
        pts = row.get("points") or []
        if len(pts) >= 4:
            geom = Polygon(pts)
            if geom.is_valid and geom.area > 0:
                polys.append(geom)
    if not polys:
        return None
    return unary_union(polys)


def _cell_remote(points: list, footprint) -> dict[str, Any] | None:
    from shapely.geometry import LineString

    if footprint is None or len(points) != 2:
        return None
    shape = LineString([(float(points[0][0]), float(points[0][1])),
                        (float(points[1][0]), float(points[1][1]))])
    if shape.length <= 0:
        return None
    distance = float(shape.distance(footprint))
    outside = float(shape.difference(footprint.buffer(REMOTE_CM)).length / shape.length)
    return {
        "distance_to_n1_fundo_cm": round(distance, 3),
        "outside_30cm_fraction": round(outside, 3),
        "remote": distance > REMOTE_CM or outside > 0.5,
    }


def _unique_label(source: CadSource, name: str):
    labels = source.texts_with_value(name)
    if len(labels) != 1:
        return None, {"item": name, "classe": "LV", "reason": "NO_UNIQUE_LABEL",
                      "detail": f"label_count={len(labels)}"}
    return labels[0], None


def _line_option_id(handle: str) -> str:
    return f"LINE_{handle}"[:48]


def _edge_points(hit_or_row: dict) -> list:
    if "selected_edge" in hit_or_row and hit_or_row["selected_edge"]:
        return [list(hit_or_row["selected_edge"][0]), list(hit_or_row["selected_edge"][1])]
    if "segment" in hit_or_row:
        a, b = hit_or_row["segment"]
        return [list(a), list(b)]
    pts = hit_or_row.get("points") or []
    return pts[:2]


def _nearby_row(hit: dict) -> dict[str, Any]:
    ent = hit["entity"]
    classification = hit.get("classification") or "wall_line"
    edge = _edge_points(hit)
    full_pts = rounded_points(ent.points)
    extra = {
        "role": "closed_polygon_edge" if classification == "closed_polygon_edge" else "nearby_parallel_line",
        "classification": classification,
        "closed": bool(hit.get("closed")),
        "vertex_count": int(hit.get("vertex_count") or len(ent.points or [])),
        "unique_vertex_count": int(hit.get("unique_vertex_count") or 0),
        "bbox": list(hit.get("bbox") or []),
        "selected_edge": edge,
        "provenance": dict(hit["provenance"]),
    }
    if full_pts:
        extra["points"] = full_pts
    else:
        extra["points"] = edge
        extra["points_truncated"] = True
    if hit.get("duplicate_handles"):
        extra["duplicate_handles"] = list(hit["duplicate_handles"])
        extra["duplicate_layers"] = list(hit.get("duplicate_layers") or [])
    return compact_entity(ent, extra)


def discover_lv(item: N1Item, source: CadSource, *, pavimento: str
                ) -> list[ConflictCandidate] | dict[str, str]:
    if item.name.startswith("VF"):
        return {"item": item.name, "classe": "LV", "reason": "NOT_LV_OCCURRENCE"}
    label, err = _unique_label(source, item.name)
    if err:
        return err
    cells = list(item.extras.get("cells") or [])
    if item.extras.get("lv_audit_cells"):
        audit_by_key = {}
        for row in item.extras["lv_audit_cells"]:
            audit_by_key[(row.get("kind"), str(row.get("segment_label")))] = row
        for cell in cells:
            key = (cell.get("kind"), str(cell.get("index")))
            if key in audit_by_key:
                cell["audit"] = audit_by_key[key]
    footprint = _fundo_union(item)
    units = []
    needs = 0
    for cell in cells:
        pts = cell.get("points") or []
        if len(pts) != 2:
            continue
        dxf_line = match_dxf_line(source, pts[0], pts[1])
        if dxf_line is None:
            needs += 1
            continue
        geom = cell.get("audit") or _cell_remote(pts, footprint) or {}
        remote = bool(geom.get("remote") or geom.get("suspicious_remote"))
        units.append((cell, dxf_line, geom, remote))
    if not units and needs:
        return {"item": item.name, "classe": "LV", "reason": "NEEDS_SOURCE",
                "detail": "no_dxf_line_matches_n1_cell"}
    if not units:
        return {"item": item.name, "classe": "LV", "reason": "NO_CANDIDATES"}
    remotes = [u for u in units if u[3]]
    chosen = remotes[:MAX_UNITS] if remotes else units[:1]
    leftover_units = units[len(chosen):] if remotes else units[1:]
    leftover = [{"handle": u[1].handle, "reason": "unit_cap"}
                for u in leftover_units[:20]]
    packets = []
    continuity = [u[1].handle for u in units]
    for cell, dxf_line, geom, remote in chosen:
        packet = _packet(
            item, pavimento, label, cell, dxf_line, geom, remote, source, continuity, leftover,
        )
        if packet is None:
            leftover.append({"handle": dxf_line.handle,
                             "reason": "independent_strip_unproven_from_source_dxf"})
            continue
        packets.append(packet)
    if not packets:
        return {"item": item.name, "classe": "LV", "reason": "NEEDS_SOURCE",
                "detail": "independent_strip_unproven_from_source_dxf"}
    return packets


def _packet(item, pavimento, label, cell, dxf_line, geom, remote,
            source, continuity, leftover) -> ConflictCandidate | None:
    cell_pts = list(dxf_line.points[:2] if dxf_line.points and len(dxf_line.points) >= 2
                    else (cell.get("points") or []))
    if len(cell_pts) != 2:
        return None
    nearby = nearby_parallel_segments(source, cell_pts, dxf_line.handle)
    walls, polygons = [], []
    for hit in nearby:
        if hit.get("classification") == "closed_polygon_edge":
            polygons.append(hit)
        else:
            walls.append(hit)
    gated = []
    for hit in walls:
        ok, where = label_near_strip(label.xy, cell_pts, hit["segment"])
        if ok:
            gated.append((hit, where))
    if not gated:
        return None
    mid = midpoint(cell_pts)
    neighbors = [e for e in source.entities_near(mid[0], mid[1], 80, types=["TEXT", "MTEXT"])
                 if BEAM_NAME_RE.fullmatch((e.text or "").strip()) and e.handle != label.handle]
    line_rows = [_nearby_row(hit) for hit, _where in gated[:MAX_NEARBY]]
    polygon_rows = [_nearby_row(hit) for hit in polygons[:MAX_NEARBY]]
    option_rows = {}
    for row in line_rows:
        edge = _edge_points(row)
        option_rows[_line_option_id(row["handle"])] = (
            f"Source DXF {row['etype']} handle {row['handle']} "
            f"from {edge[0]} to {edge[1]}; closed={row.get('closed')}; "
            f"vertex_count={row.get('vertex_count')}"
        )
    question = lv_question(option_rows)
    if len(question["criteria"]) < 2:
        return None
    unit_id = f"cell:{cell.get('kind')}:{cell.get('index')}"
    case_id = f"{pavimento}|LV|{item.name}|lv_cell|{unit_id}"
    alternatives = [
        {"id": _line_option_id(row["handle"]), "handle": row["handle"], "xy": row["xy"],
         "role": "nearby_parallel_line", "etype": row["etype"],
         "points": _edge_points(row), "closed": row.get("closed"),
         "vertex_count": row.get("vertex_count")}
        for row in line_rows
    ]
    target = compact_entity(dxf_line, {
        "role": "cell_line",
        "closed": False,
        "vertex_count": len(cell_pts),
        "points": [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in cell_pts],
        "selected_edge": [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in cell_pts],
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
        "neighbor_beam_labels": [compact_entity(e, {"role": "neighbor_beam", "include_points": False})
                                 for e in neighbors[:3]],
        "search": {"center": mid, "units": "dxf_drawing"},
        "continuity_index": continuity,
        "relation_provenance": {
            "cell_match": "dxf_line_same_segment_as_n1_cell_endpoints",
            "nearby_lines": "source_dxf_open_wall_parallel_within_gap",
            "nearby_polygon_edges": "source_dxf_closed_contour_parallel_edge",
            "label": "unique_text_value_on_source_dxf",
            "label_strip": gated[0][1],
            "n1_fundo_used_for_relation": False,
        },
    }
    extra = []
    if neighbors:
        extra.append(neighbor_control(evidence, neighbors[0]))
    return ConflictCandidate(
        case_id=case_id, classe="LV", item=item.name, campo="lv_cell",
        unit_kind="cell", unit_id=unit_id,
        trigger="remote_cell" if remote else "coherent_control",
        severity="high" if remote else "low",
        alternatives=alternatives, evidence=evidence,
        included=[evidence["target"], evidence["beam_label"], *line_rows, *polygon_rows],
        excluded=list(leftover[:20]),
        decisive_handles=[row["handle"] for row in line_rows],
        question=question,
        physical_unit={"kind": "cell", "index": cell.get("index"),
                       "continuity_index": continuity},
        cad_rules=[
            "Target is a source-DXF line whose endpoints match the N1 cell locator.",
            "nearby_lines are open source-DXF wall segments from a parallel-and-gap search.",
            "Closed contours that share a parallel edge are nearby_polygon_edges with full contour, vertex_count, closed flag, selected_edge and bbox; they are not equivalent wall lines.",
            "Duplicate closed contours across layers are collapsed to one row with duplicate_handles/layers provenance.",
            "N1 fundo is not used to decide the geometric relation or ownership.",
            "A unique source-DXF text equal to the item name lies in or within 40 drawing units of the wall strip.",
        ],
        extra_controls=extra,
        catalog_id="lv_cell_nearby_parallel_line",
        baseline_value=cell.get("kind"),
    )


def _control_shell(evidence: dict, **overrides) -> dict[str, Any]:
    shell = {
        "target": evidence["target"],
        "beam_label": evidence["beam_label"],
        "nearby_lines": evidence.get("nearby_lines") or [],
        "nearby_polygon_edges": evidence.get("nearby_polygon_edges") or [],
        "neighbor_beam_labels": evidence.get("neighbor_beam_labels") or [],
        "search": evidence["search"],
        "continuity_index": evidence.get("continuity_index") or [],
        "relation_provenance": evidence.get("relation_provenance") or {},
    }
    for key in ("encounter_gaps", "colinear_continuations", "pillar_markers"):
        if key in evidence:
            shell[key] = evidence.get(key) or []
    shell.update(overrides)
    return shell


def withdrawal_control(candidate: ConflictCandidate) -> dict[str, Any]:
    evidence = _control_shell(
        candidate.evidence,
        nearby_lines=[],
        nearby_polygon_edges=[],
        control_note="listed nearby parallel walls and closed polygon edges withdrawn",
    )
    return {"id": "nearby_lines_removed", "expected_choice": "INSUFFICIENT", "evidence": evidence}


def reversed_control(candidate: ConflictCandidate) -> dict[str, Any] | None:
    lines = list(reversed(candidate.evidence.get("nearby_lines") or []))
    polys = list(reversed(candidate.evidence.get("nearby_polygon_edges") or []))
    neigh = list(reversed(candidate.evidence.get("neighbor_beam_labels") or []))
    if len(lines) + len(neigh) < 2:
        return None
    return {
        "id": "candidate_order_reversed",
        "evidence": _control_shell(
            candidate.evidence,
            nearby_lines=lines,
            nearby_polygon_edges=polys,
            neighbor_beam_labels=neigh,
        ),
    }


def neighbor_control(evidence: dict, neighbor) -> dict[str, Any]:
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
            control_note="nearby parallel walls, closed polygon edges and the unique item label withdrawn; neighbor label remains",
        ),
    }
