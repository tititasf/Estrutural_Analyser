"""Canonical input contract shared by the FV N3/N4 generator."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

FV_ENGINE_ID = "ROBOT_FV_N3_N4"
FV_CONTRACT_VERSION = 3
PANEL_MODULE = 244.0
PANEL_MINIMUM = 30.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _dim_pair(value: Any) -> tuple[float, float]:
    match = re.search(
        r"\(?\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*\)?",
        str(value or ""),
    )
    if not match:
        return 0.0, 0.0
    values = sorted(_number(part) for part in match.groups())
    return values[0], values[1]


def _segment_length(segment: dict[str, Any]) -> float:
    ficha = segment.get("ficha") if isinstance(segment.get("ficha"), dict) else {}
    # ``length`` pertence ao segmento recém-publicado pelo SA e é a fonte
    # soberana. A subficha pode conservar um valor de uma interpretação
    # anterior; ela só serve como fallback quando o SA atual não mediu.
    value = segment.get("length") or ficha.get("comprimento_total_fundo")
    if _number(value) > 0:
        return _number(value)
    coord = segment.get("coord")
    if isinstance(coord, (list, tuple)) and len(coord) >= 2:
        return abs(_number(coord[1]) - _number(coord[0]))
    points = segment.get("geometry") or []
    if isinstance(points, list) and len(points) >= 2:
        total = 0.0
        for start, end in zip(points, points[1:]):
            if len(start) >= 2 and len(end) >= 2:
                dx = _number(end[0]) - _number(start[0])
                dy = _number(end[1]) - _number(start[1])
                total += (dx * dx + dy * dy) ** 0.5
        return total
    return 0.0


def compute_panel_modules(length: Any) -> list[float]:
    """Same generic panel distribution used by the current FV engine."""
    total = _number(length)
    if total <= 0:
        return []
    if total <= PANEL_MODULE:
        return [total]
    full = int(total // PANEL_MODULE)
    remainder = total - full * PANEL_MODULE
    if remainder == 0:
        return [PANEL_MODULE] * full
    if remainder < PANEL_MINIMUM:
        # This is a distribution preference, never a minimum panel length:
        # retain the entire remainder without exceeding the stock length.
        half = PANEL_MODULE / 2
        return [PANEL_MODULE] * (full - 1) + [half + remainder, half]
    return [PANEL_MODULE] * full + [remainder]


def _blank_apoio(text: Any) -> bool:
    t = str(text or "").strip()
    return t in ("", "—", "-", "N/A", "n/a", "None", "none", "null")


def chain_linear_segment_apoios(
    rows: list[dict[str, Any]],
    *,
    start_key: str = "ponto_inicial",
    end_key: str = "ponto_final",
) -> list[dict[str, Any]]:
    """If every span copied the beam-global end, set fim[i] = ini[i+1]."""
    if len(rows) < 2:
        return rows
    starts = [str(row.get(start_key) or "").strip() for row in rows]
    ends = [str(row.get(end_key) or "").strip() for row in rows]
    valid_ends = [end for end in ends if not _blank_apoio(end)]
    common = ""
    if valid_ends:
        common, count = Counter(valid_ends).most_common(1)[0]
        if count < max(2, (len(valid_ends) + 1) // 2):
            common = ""
    for i in range(len(rows) - 1):
        nxt = starts[i + 1]
        cur = ends[i]
        if _blank_apoio(nxt):
            continue
        copied_global = bool(common) and cur == common and nxt != common
        if _blank_apoio(cur) or copied_global:
            rows[i][end_key] = nxt
            ends[i] = nxt
    return rows


def merge_fv_source_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Consolidate every SA occurrence that belongs to the same canonical beam.

    ``BeamTracer`` can legitimately return more than one occurrence for a beam
    name (for example, interrupted/overlapping runs of V301).  The production
    adapter used to store contracts in a dict by name, so the last occurrence
    silently replaced the others.  This merge happens before the N3 contract is
    built, keeping all segments and ordering them on the structural axis.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for source in results or []:
        if not isinstance(source, dict):
            continue
        raw_name = str(source.get("viga_nome") or source.get("name") or "")
        match = re.search(r"(V[F]?\d+[A-Z]?)", raw_name.upper())
        name = match.group(1) if match else raw_name.upper().replace(".C", "")
        if not name:
            continue
        if name not in grouped:
            grouped[name] = []
            order.append(name)
        grouped[name].append(source)

    merged: list[dict[str, Any]] = []
    for name in order:
        sources = grouped[name]
        base = deepcopy(sources[0])
        segments: list[dict[str, Any]] = []
        for source in sources:
            for segment in source.get("segmentos_fundo") or []:
                if isinstance(segment, dict):
                    segments.append(deepcopy(segment))

        horizontal_votes = [bool(s.get("is_horizontal", True)) for s in sources]
        is_horizontal = Counter(horizontal_votes).most_common(1)[0][0]
        # A ordem publicada pelo SA define S1..Sn. Reordenar novamente pela
        # coordenada invertia vigas verticais e dissociava a ficha do viewer.
        # Ocorrências repetidas continuam consolidadas na ordem em que o SA as
        # forneceu; apenas a numeração final é normalizada.
        for index, segment in enumerate(segments, 1):
            segment["seg_index"] = index
        base["viga_nome"] = name
        base["is_horizontal"] = is_horizontal
        base["segmentos_fundo"] = segments
        base["panels_n1"] = len(segments)
        base["merged_lengths_count"] = len(segments)
        base["comprimento_fundo"] = round(sum(_segment_length(s) for s in segments), 3)
        merged.append(base)
    return merged


def overlay_fv_state_measurements(
    merged_results: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Overlay the exact structured SA measurements onto the N3 adapter input.

    The saved production state is the same source consumed by the web ficha.
    Pairing by canonical beam and SA segment order prevents stale values nested
    in an older per-segment ``ficha`` from replacing current measurements.
    """
    rows_by_beam: dict[str, list[dict[str, Any]]] = {}
    for row in state_rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("beam_name") or row.get("viga_nome") or "").upper()
        match = re.search(r"(V[F]?\d+[A-Z]?)", name)
        if match:
            rows_by_beam.setdefault(match.group(1), []).append(row)

    output = deepcopy(merged_results)
    for source in output:
        raw_name = str(source.get("viga_nome") or source.get("name") or "").upper()
        match = re.search(r"(V[F]?\d+[A-Z]?)", raw_name)
        name = match.group(1) if match else raw_name
        segments = source.get("segmentos_fundo") or []
        rows = rows_by_beam.get(name) or []
        if not rows:
            continue
        # The published SA owns membership as well as measurements. A stale
        # extraction may contain only one span while the current SA contains
        # several (or spans were manually removed). Never silently retain that
        # obsolete list just because its cardinality differs.
        def segment_index(value: dict, fallback: int) -> int:
            return int(_number(value.get("segment_label") or value.get("seg_index"), fallback))

        rows = [row for _, row in sorted(
            enumerate(rows, 1), key=lambda pair: segment_index(pair[1], pair[0])
        )]
        sources_by_index = {
            segment_index(segment, index): segment
            for index, segment in enumerate(segments, 1)
        }
        segments = [
            deepcopy(sources_by_index.get(segment_index(row, index), {}))
            for index, row in enumerate(rows, 1)
        ]
        source["segmentos_fundo"] = segments
        for index, (segment, row) in enumerate(zip(segments, rows), 1):
            measured = _number(row.get("length"))
            if measured > 0:
                segment["length"] = measured
            points = row.get("points")
            if isinstance(points, list) and len(points) >= 2:
                segment["geometry"] = deepcopy(points)
            width = _number(row.get("width"))
            if width > 0:
                segment["dim_width"] = width
            for state_key, source_key in (
                ("beam_height", "dim_height"), ("section_dim", "dim_text"),
                ("support_start", "apoio_inicial"), ("support_end", "apoio_final"),
                ("special_geometry", "special_geometry"),
            ):
                if row.get(state_key) not in (None, ""):
                    segment[source_key] = deepcopy(row[state_key])
            segment["seg_index"] = index
            segment["sa_status"] = row.get("status") or "valid"
            if row.get("level") not in (None, ""):
                segment["nivel"] = row.get("level")
                segment["nivel_origem"] = row.get("level_source") or "sa_state"
                segment["nivel_lajes"] = list(row.get("level_slabs") or [])
                segment["nivel_distancia_cm"] = row.get("level_distance_cm")
        source["comprimento_fundo"] = round(
            sum(_number(segment.get("length")) for segment in segments), 3
        )
        source["panels_n1"] = len(segments)
    return output


def _is_transverse_contaminant(segment: dict[str, Any]) -> bool:
    """Reject a short crossing mistakenly captured as longitudinal FV."""
    left = str(segment.get("apoio_inicial") or "").strip().upper()
    right = str(segment.get("apoio_final") or "").strip().upper()
    if not left or left != right:
        return False
    ficha = segment.get("ficha") if isinstance(segment.get("ficha"), dict) else {}
    depth = _number(segment.get("dim_height") or ficha.get("altura_total"))
    return _segment_length(segment) <= max(100.0, depth * 2.0)


def _local_outline_panel(geometry: Any) -> dict[str, Any] | None:
    """Rigidly unfold an angled SA fold, without changing its vertices.

    The longest structural edge defines the longitudinal axis. Rectangles
    belong to the robot's module distributor. Chamfered strips and an
    angled concave fold are explicit outlines, subsequently modulated
    into stock panels on the straight body. N2/N4 are never consulted.
    """
    try:
        points = [(float(p[0]), float(p[1])) for p in geometry]
    except (TypeError, ValueError, IndexError):
        return None
    if len(points) < 3 or not all(math.isfinite(v) for p in points for v in p):
        return None
    edges = list(zip(points, points[1:] + points[:1]))
    start, end = max(edges, key=lambda e: math.dist(*e))
    dx, dy = end[0] - start[0], end[1] - start[1]
    distance = math.hypot(dx, dy)
    if distance <= 1e-9:
        return None
    # Orient by the contour, not world X/Y: a rotated copy must unfold into
    # the same robot geometry. Reverse winding reverses this boundary edge.
    signed_area = sum(a[0]*b[1]-b[0]*a[1] for a, b in edges)
    if signed_area < 0:
        dx, dy = -dx, -dy
    ux, uy = dx / distance, dy / distance
    projected = [((x-start[0])*ux + (y-start[1])*uy,
                  -(x-start[0])*uy + (y-start[1])*ux) for x, y in points]
    unique = projected[:-1] if math.dist(projected[0], projected[-1]) < 1e-9 else projected
    turns = []
    angled = False
    for i, a in enumerate(unique):
        b, c = unique[(i+1) % len(unique)], unique[(i+2) % len(unique)]
        ex, ey = b[0]-a[0], b[1]-a[1]
        turns.append(ex*(c[1]-b[1])-ey*(c[0]-b[0]))
        angled |= abs(ex) > 1e-7 and abs(ey) > 1e-7
    concave = any(t > 1e-7 for t in turns) and any(t < -1e-7 for t in turns)
    # A convex strip with two parallel walls is a chamfer, not an L.
    # Do not promote arbitrary trapezoids/triangles into folded panels.
    wall_edges = [(a, unique[(i+1) % len(unique)]) for i, a in enumerate(unique)
                  if abs(a[1]-unique[(i+1) % len(unique)][1]) < 1e-7
                  and abs(a[0]-unique[(i+1) % len(unique)][0]) > 1e-7]
    chamfer = (len(unique) == 4 and len(wall_edges) == 2
               and abs(wall_edges[0][0][1]-wall_edges[1][0][1]) > 1e-7)
    if not angled or not (concave or chamfer):
        return None
    x0, y0 = min(x for x, y in projected), min(y for x, y in projected)
    vertices = [{"x": x-x0, "y": y-y0} for x, y in projected]
    length = max(p['x'] for p in vertices)
    height = max(p['y'] for p in vertices)
    area = abs(sum(a[0]*b[1]-b[0]*a[1] for a, b in edges)) / 2
    if area <= 1e-9 or length * height - area <= max(1e-6, area * 1e-8):
        return None
    return {"width": length, "height": height, "vertices": vertices,
            "sa_local_frame": {"origin": [start[0]+x0*ux-y0*uy,
                                            start[1]+x0*uy+y0*ux],
                               "axis": [ux, uy]},
            "source": "sa_chamfer" if chamfer else "sa_outline"}


def _modulate_outline_panel(panel: dict) -> list[dict]:
    """Clip stock panels only inside the common straight-wall interval.

    Manufacturing joins do not create SA segments or split a fold. A fold
    that cannot fit the stock is an explicit review error, not a guessed cut.
    """
    from shapely.geometry import Polygon, box

    polygon = Polygon([(v['x'], v['y']) for v in panel['vertices']])
    if not polygon.is_valid:
        raise ValueError('FV: contorno angular invalido para modular paineis')
    widths = compute_panel_modules(panel['width'])
    from scripts.fv_l_panel_geometry import derive_quadrilateral_chanfros
    chamfers = derive_quadrilateral_chanfros(panel['vertices'])
    if chamfers:
        panel = deepcopy(panel)
        panel['chanfros'] = chamfers
    if len(widths) == 1:
        return [panel]
    vertices = panel['vertices']
    edges = list(zip(vertices, vertices[1:] + vertices[:1]))
    horizontal = [(min(a['x'], b['x']), max(a['x'], b['x']))
                  for a, b in edges if abs(a['y']-b['y']) < 1e-4
                  and abs(a['x']-b['x']) > 1e-4]
    horizontal.sort(key=lambda edge: edge[1]-edge[0], reverse=True)
    if len(horizontal) < 2:
        raise ValueError('FV: faltam paredes retas para uma emenda segura')
    safe_start = max(e[0] for e in horizontal[:2])
    safe_end = min(e[1] for e in horizontal[:2])
    total = float(panel['width'])
    cuts = [0.0]
    # Nominal stock cuts are preferred; move only when a fold obstructs one.
    preferred = 0.0
    for width in widths[:-1]:
        preferred += width
        # A join at the endpoint of this interval would still be at the fold.
        # This epsilon is numerical clearance, not a minimum piece length.
        low = max(safe_start+1e-7, total - (len(widths)-len(cuts))*PANEL_MODULE)
        high = min(safe_end-1e-7, cuts[-1]+PANEL_MODULE)
        if high < low or high <= cuts[-1] + 1e-8:
            raise ValueError('FV: dobra nao cabe em 244 cm sem emenda no L; revisar')
        target = preferred if safe_start < preferred < safe_end else (low+high)/2
        cuts.append(min(high, max(low, target)))
    cuts.append(total)
    result = []
    for start, end in zip(cuts, cuts[1:]):
        clipped = polygon.intersection(box(start, -1, end, panel['height']+1))
        if clipped.geom_type != 'Polygon' or clipped.area <= 0 or end-start > PANEL_MODULE+1e-8:
            raise ValueError('FV: modulacao angular precisa de revisao geometrica')
        part = deepcopy(panel)
        part['width'] = end-start
        part['vertices'] = [{'x':x-start, 'y':y} for x,y in clipped.exterior.coords]
        # Each cut piece owns only its actual end setback, never the original
        # segment's chamfer repeated on every rectangular stock panel.
        part.pop('chanfros', None)
        chamfers = derive_quadrilateral_chanfros(part['vertices'])
        if chamfers:
            part['chanfros'] = chamfers
        part['height'] = clipped.bounds[3]-clipped.bounds[1]
        part['sa_outline_offset'] = start
        frame = part['sa_local_frame']
        ux, uy = frame['axis']
        frame['origin'][0] += start*ux
        frame['origin'][1] += start*uy
        result.append(part)
    return result


def _outline_pillar_supports(geometry: Any, panel: dict, pillars: Any) -> dict:
    """Resolve angular-panel caps only when a solid SA face is fully shared.

    A nearby label, point contact or ambiguous pair is not support evidence.
    The 0.0001 cm tolerance compensates serialization rounding, not a gap.
    """
    from shapely.geometry import LineString, Polygon

    tolerance = 1e-4
    vertices = panel['vertices']
    points = [(float(p[0]), float(p[1])) for p in geometry]
    if math.dist(points[0], points[-1]) < 1e-9:
        points = points[:-1]
        vertices = vertices[:-1]
    beam = Polygon(points)
    if not beam.is_valid:
        return {}
    candidates = {'left': set(), 'right': set()}
    solids = []
    for pillar in pillars or []:
        if not isinstance(pillar, dict):
            continue
        classification = str(pillar.get('classification') or '').upper().replace('_', ' ')
        if classification not in ('SEGUE', 'MORRE', 'MORRE AQUI'):
            continue
        try:
            polygon = Polygon(pillar.get('points') or [])
        except (TypeError, ValueError):
            continue
        label = str(pillar.get('name') or pillar.get('key') or '').strip()
        if not polygon.is_valid or polygon.is_empty or not label:
            continue
        # Caps are exterior contacts, never a reason to accept an invading FV.
        if beam.intersection(polygon).area > tolerance * beam.length:
            continue
        solids.append((label, polygon.boundary.buffer(tolerance)))
    for i, a in enumerate(vertices):
        b = vertices[(i+1) % len(vertices)]
        if abs(a['y']-b['y']) <= tolerance:
            continue  # Longitudinal wall, not a cap.
        edge = LineString([points[i], points[(i+1) % len(points)]])
        if edge.length <= tolerance:
            continue
        side = None
        if min(a['x'], b['x']) <= tolerance:
            side = 'left'
        elif max(a['x'], b['x']) >= panel['width']-tolerance:
            side = 'right'
        if side:
            for label, face in solids:
                if edge.difference(face).length <= tolerance:
                    candidates[side].add(label)
    return {side: next(iter(names)) for side, names in candidates.items() if len(names) == 1}


def normalize_fv_generation_contract(
    viga_nome: str,
    ficha: dict[str, Any],
    *,
    floor: str = "Pavimento",
) -> dict[str, Any]:
    """Return the common FV schema consumed by the single N3/N4 engine.

    Rich N4 fields are never recomputed: this function only copies the ficha
    and fills fields absent from either lineage.
    """
    result = deepcopy(ficha) if isinstance(ficha, dict) else {}
    name_match = re.search(r"(V[F]?\d+[A-Z]?)", str(viga_nome).upper())
    name = name_match.group(1) if name_match else str(viga_nome).upper().replace(".C", "")
    segments = result.get("segments_rich")
    if not isinstance(segments, list):
        panels = result.get("panels")
        segments = panels if isinstance(panels, list) else []
    number_match = re.search(r"\d+", name)

    result.setdefault("contract_version", FV_CONTRACT_VERSION)
    result.setdefault("motor_id", FV_ENGINE_ID)
    result.setdefault("number", number_match.group(0) if number_match else name)
    result.setdefault("name", name)
    result.setdefault("floor", floor or "Pavimento")
    result.setdefault("side", "C")
    result.setdefault("total_width", 0.0)
    result.setdefault("total_height", 0.0)
    result["segments_rich"] = segments
    result["panels"] = segments
    result.setdefault("holes", [])
    result.setdefault("label_left", "")
    result.setdefault("label_right", "")
    result.setdefault(
        "pillar_left",
        {"active": False, "label": "", "width": 0.0, "length": 0.0},
    )
    result.setdefault(
        "pillar_right",
        {"active": False, "label": "", "width": 0.0, "length": 0.0},
    )
    result.setdefault("sarrafo_left_id", 0)
    result.setdefault("sarrafo_right_id", 0)
    return result


def build_fv_generation_contract(
    viga_nome: str,
    source_data: dict[str, Any],
    *,
    floor: str = "Pavimento",
    pillars: list[dict[str, Any]] | None = None,
    section_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert the current SA/N1 FV result to the rich N3/N4 input schema."""
    name_match = re.search(r"(V[F]?\d+[A-Z]?)", str(viga_nome).upper())
    name = name_match.group(1) if name_match else str(viga_nome).upper().replace(".C", "")
    dim_width, dim_height = _dim_pair(
        source_data.get("dim") or source_data.get("dim_text")
    )
    all_source_segments = [
        segment for segment in source_data.get("segmentos_fundo", [])
        if isinstance(segment, dict)
    ]
    # O SA é a autoridade geométrica desta etapa. Um segmento curto ou com o
    # mesmo apoio nas duas pontas pode representar um vão real medido; o
    # adaptador N3 não pode reinterpretá-lo nem descartá-lo por heurística.
    # Eventuais contaminantes devem ser resolvidos no próprio motor SA, antes
    # da publicação do snapshot estruturado.
    source_segments = all_source_segments
    segments: list[dict[str, Any]] = []
    segment_widths: list[float] = []
    segment_heights: list[float] = []
    first_support = ""
    last_support = ""
    is_horizontal = bool(source_data.get("is_horizontal", True))
    context = section_context or {}
    context_entries = [e for e in context.get('physical_entries', context.get('entries', []))
                       if str(e.get('beam') or '').upper() == name.upper()]
    inverted_evidence = any(((e.get('section_contract') or {}).get('beam_type') == 'inverted'
                            or (e.get('section_semantics') or {}).get('beam_type') == 'inverted')
                            for e in context_entries)
    beam_section_runs = []

    if inverted_evidence:
        from .beam_vertical_context import exclude_inverted_cap_junctions, split_inverted_soffit
        from shapely.geometry import Polygon
        cap_parts = []
        for source in source_segments:
            # Structural section continuity is measured BEFORE assembly gaps.
            # Two cap pieces at either side of an incident beam do not create
            # two structural sections of the same depth.
            runs = split_inverted_soffit(source, context_entries)
            descriptors = []
            for run in runs:
                descriptor = dict(index=len(beam_section_runs), geometry=run['geometry'],
                                  length_cm=run['length'], section_contract=run['_vertical_contract'])
                beam_section_runs.append(descriptor)
                descriptors.append(descriptor)
            for span in exclude_inverted_cap_junctions(source, context_entries, pillars=pillars):
                for part in split_inverted_soffit(span, context_entries):
                    polygon = Polygon(part['geometry'])
                    owners = [run for run in descriptors
                              if polygon.difference(Polygon(run['geometry']).buffer(1e-5)).area <= 1e-5]
                    if len(owners) != 1:
                        raise ValueError('tampa sem trecho estrutural único confirmado')
                    part['_beam_section_run'] = owners[0]['index']
                    cap_parts.append(part)
        source_segments = cap_parts

    for index, source in enumerate(source_segments):
        ficha = source.get("ficha") if isinstance(source.get("ficha"), dict) else {}
        length = _segment_length(source)
        if length <= 0:
            continue
        vertical = None
        if inverted_evidence:
            from .beam_vertical_context import covering_vertical_contract
            vertical = source.get('_vertical_contract') or covering_vertical_contract(source.get('geometry') or [],context_entries)
        width = _number(
            source.get("dim_width")
            or ficha.get("largura_total_fundo")
            or dim_width
        )
        if source.get("special_geometry") == "orthogonal_l":
            # O snapshot estruturado mede a bbox do L (29/49 no V303), nao a
            # largura do corpo principal (19). Para modular o painel, a secao
            # declarada do segmento continua sendo a largura transversal real.
            declared_width, _declared_height = _dim_pair(
                source.get("dim_text") or source_data.get("dim_text")
            )
            if declared_width > 0:
                width = declared_width
        height = _number(
            source.get("dim_height") or ficha.get("altura_total") or dim_height
        )
        dim_width = dim_width or width
        dim_height = dim_height or height
        if width > 0:
            segment_widths.append(round(width, 3))
        if height > 0:
            segment_heights.append(round(height, 3))
        left = str(source.get("apoio_inicial") or "").strip()
        right = str(source.get("apoio_final") or "").strip()
        segment: dict[str, Any] = {
            "total_width": round(length, 3),
            "width": round(length, 3),
            "dim_text": source.get("dim_text") or source_data.get("dim_text") or "",
            "largura_total_fundo": round(width, 3),
            "comprimento_total_fundo": round(length, 3),
            "altura_total": round(height, 3),
            "texto_esq": left,
            "texto_dir": right,
            "row_break": index > 0,
        }
        if source.get('cap_assembly_rule'):
            segment['cap_assembly_rule'] = source['cap_assembly_rule']
            segment['cap_junction_exclusions'] = source['cap_junction_exclusions']
            segment['cap_assembly_span'] = source['cap_assembly_span']
        if source.get('_beam_section_run') is not None:
            segment['beam_section_run_index'] = source['_beam_section_run']
        if source.get("nivel") not in (None, ""):
            segment["nivel"] = source.get("nivel")
            segment["nivel_origem"] = source.get("nivel_origem") or source.get("level_source") or "sa"
            segment["nivel_lajes"] = list(source.get("nivel_lajes") or source.get("level_slabs") or [])
            segment["nivel_distancia_cm"] = source.get("nivel_distancia_cm", source.get("level_distance_cm"))
        explicit_panels = source.get("panels") or ficha.get("panels")
        outline_panel = _local_outline_panel(source.get("geometry"))
        if isinstance(explicit_panels, list) and explicit_panels:
            segment["panels"] = explicit_panels
        elif source.get("special_geometry") == "orthogonal_l":
            points = source.get("geometry") or []
            try:
                axis_values = [float(point[0 if is_horizontal else 1]) for point in points]
                transverse_values = [float(point[1 if is_horizontal else 0]) for point in points]
                axis_min = min(axis_values)
                axis_max = max(axis_values)
                transverse_span = max(transverse_values) - min(transverse_values)
                internal_axes = sorted({
                    value - axis_min for value in axis_values
                    if value > axis_min + 1e-3 and value < axis_max - 1e-3
                })
            except (IndexError, TypeError, ValueError):
                internal_axes = []
                transverse_span = 0.0
            if internal_axes and transverse_span > width:
                main_width = internal_axes[-1]
                leaf_width = max(0.0, length - main_width)
                modules = compute_panel_modules(main_width)
                segment["panels"] = [
                    {"width": round(module, 3), "height": round(width, 3)}
                    for module in modules
                ]
                segment["panels"].append({
                    "width": round(leaf_width, 3),
                    "height": round(transverse_span, 3),
                    "is_L_drop": True,
                    "l_side": "right",
                    "l_drop_depth": round(transverse_span - width, 3),
                    "special_geometry": "orthogonal_l",
                    "fv_l_incident": source.get("fv_l_incident") or "",
                })
                segment["special_geometry"] = "orthogonal_l"
        elif outline_panel:
            segment["panels"] = _modulate_outline_panel(outline_panel)
            segment["total_width"] = outline_panel["width"]
            segment["width"] = outline_panel["width"]
            segment["source_geometry"] = outline_panel["source"]
            supports = _outline_pillar_supports(source['geometry'], outline_panel, pillars)
            left = supports.get('left', left)
            right = supports.get('right', right)
            segment['texto_esq'], segment['texto_dir'] = left, right
            if supports:
                segment['support_source'] = 'sa_shared_solid_pillar_cap'
        # Sem topologia explicita no N1, nao congele aqui uma regra de paineis.
        # O motor comum N3/N4 deve aplicar sua regra mais recente em draw_viga().
        # Isso evita que o adaptador N1 continue reproduzindo uma distribuicao
        # antiga depois que o gerador FV for refinado.
        for key in (
            "abertura_especial", "chanfro_esq_top", "chanfro_esq_fun",
            "chanfro_dir_top", "chanfro_dir_fun", "abertura_topo_esq",
            "abertura_topo_dir", "abertura_fundo_esq", "abertura_fundo_dir",
            "holes", "_multiplier",
        ):
            value = source.get(key, ficha.get(key))
            if value not in (None, "", "N/A"):
                segment[key] = value
        if outline_panel and outline_panel['source'] == 'sa_chamfer':
            from scripts.fv_l_panel_geometry import derive_quadrilateral_chanfros
            setbacks = derive_quadrilateral_chanfros(outline_panel['vertices'])
            for position, field in (
                ('te', 'chanfro_esq_top'), ('fe', 'chanfro_esq_fun'),
                ('td', 'chanfro_dir_top'), ('fd', 'chanfro_dir_fun'),
            ):
                if setbacks.get(position, 0) > 0:
                    segment[field] = setbacks[position]
        first_support = first_support or left
        last_support = right or last_support
        if vertical:
            if abs(height-vertical['height_cm']) > .5 or abs(width-vertical['width_cm']) > .5:
                raise ValueError('seção FV incompatível com o contexto vertical confirmado')
            # Feed the certified generator's existing LISO support. Every
            # leaf of this interval is a cap, including repeated stock modules.
            leaves = deepcopy(segment.get('panels') or [
                dict(width=round(module,3),height=round(width,3))
                for module in compute_panel_modules(length)])
            for leaf in leaves:
                leaf['is_liso'] = True
            segment.update(panels=leaves,form_role='top_cap',beam_type='inverted',
                           nivel=vertical['top_level_m'],nivel_origem='confirmed_vertical_section',
                           section_contract=vertical)
            segment['vertical_partition'] = source.get('vertical_partition')
        segments.append(segment)

    # A ficha do segmento e mais recente/especifica que o dim_text agregado da
    # viga. Em obras reais o cabecalho pode conservar 14/55 enquanto o fundo
    # validado do segmento e 19/55; o motor N4 usa a largura do segmento.
    if segment_widths:
        dim_width = Counter(segment_widths).most_common(1)[0][0]
    if segment_heights:
        dim_height = Counter(segment_heights).most_common(1)[0][0]

    contract = {
        "contract_version": FV_CONTRACT_VERSION,
        "motor_id": FV_ENGINE_ID,
        "name": name,
        "floor": floor or "Pavimento",
        "side": "C",
        "total_width": round(dim_width, 3),
        "total_height": round(dim_height, 3),
        "panels": segments,
        "segments_rich": segments,
        "holes": list(source_data.get("holes") or []),
        "label_left": first_support,
        "label_right": last_support,
        "pillar_left": {"active": bool(first_support), "label": first_support, "width": 0.0, "length": 0.0},
        "pillar_right": {"active": bool(last_support), "label": last_support, "width": 0.0, "length": 0.0},
        "apoio_inicial": first_support,
        "apoio_final": last_support,
        "observations": "Fonte: Structural Analyzer N1; contrato canonico FV N3/N4",
    }
    if beam_section_runs:
        contract['beam_section_runs'] = beam_section_runs
    return normalize_fv_generation_contract(name, contract, floor=floor)


def materialize_fv_contract_from_db(
    *,
    db_path: str | Path,
    project_id: str,
    item_id: str,
    output_dir: str | Path,
    floor: str = "Pavimento",
) -> Path | None:
    """Materialize one current SA beam_element without touching DXF artifacts."""
    match = re.search(r"(V[F]?\d+[A-Z]?)", str(item_id).upper())
    wanted = match.group(1) if match else str(item_id).upper()
    with sqlite3.connect(str(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT viga_nome, campos_json FROM beam_elements "
            "WHERE project_id=? AND classe='FV' ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
    for row in rows:
        found = re.search(r"(V[F]?\d+[A-Z]?)", str(row["viga_nome"]).upper())
        if not found or found.group(1) != wanted:
            continue
        try:
            source = json.loads(row["campos_json"] or "{}")
        except json.JSONDecodeError:
            return None
        contract = build_fv_generation_contract(wanted, source, floor=floor)
        if not contract["segments_rich"]:
            return None
        target = Path(output_dir) / f"{wanted}_fundo.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
    return None
