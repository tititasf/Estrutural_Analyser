"""Contrato de geracao N3 para laterais, derivado dos vinculos canonicos SA.

Esta camada nao interpreta o desenho. Ela impede que a conversao Fase 4 misture
os quatro contratos que o interpretador ja publica: A/B x Para/Passa.
"""

from __future__ import annotations

import math
import re
from typing import Any


_LINK_RE = re.compile(
    r"^viga_([ab])_seg_(\d+)_(comprimento_total|comp_total_passa)$",
    re.IGNORECASE,
)


def _length(points: list) -> float:
    if len(points) < 2:
        return 0.0
    return math.hypot(
        float(points[-1][0]) - float(points[0][0]),
        float(points[-1][1]) - float(points[0][1]),
    )


def _dimension_from_entry(entry: dict[str, Any]) -> tuple[float, float] | None:
    raw = str(entry.get("lv_dimensao") or "").replace(",", ".")
    values = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", raw)]
    if len(values) < 2 or min(values[:2]) <= 0:
        return None
    # Regra LV consolidada: menor = largura da viga; maior = profundidade.
    return min(values[:2]), max(values[:2])


def _dimension_from_beam_lv(beam: dict[str, Any]) -> tuple[float, float] | None:
    """Le somente a cota capturada pelo raio LV do BeamTracer."""
    lv_dimension = (beam.get("geometry") or {}).get("lv_dimension_text") or {}
    return _dimension_from_entry({"lv_dimensao": lv_dimension.get("text")})


def _endpoint_support_labels(
    fields: dict[str, Any], side: str, structural_segments: list[dict[str, Any]]
) -> dict[str, str]:
    """Preserva no contrato N3 os apoios que o próprio SA já capturou.

    São apenas rótulos de contexto (ex.: P34/P35), nunca dados do N2. O
    gerador os usa sob a cota total para tornar visível início/fim da lateral.
    """
    # ``links.apoios`` descreve o limite global do fundo; não é uma prova de
    # contato da face lateral. Os campos LV abaixo já passaram pelo guard de
    # contato local e ausência de rótulo é uma informação válida.
    if not structural_segments:
        return {"start": "", "end": ""}
    first = int(structural_segments[0].get("segment_index") or 1)
    last = int(structural_segments[-1].get("segment_index") or first)
    side_key = str(side or "").lower()
    return {
        "start": str(fields.get(f"viga_{side_key}_seg_{first}_ini_name") or "").strip(),
        "end": str(fields.get(f"viga_{side_key}_seg_{last}_end_name") or "").strip(),
    }


def distribute_lv_panels(length: float) -> list[float]:
    """Distribui um trecho executivo nos modulos STOG 244/122.

    Um resto curto depois de 244 cm nao vira painel residual: troca-se o
    primeiro modulo por 122 cm. Assim 260 -> 122+138 e 256 -> 122+134.
    """
    remaining = round(float(length), 3)
    if remaining <= 0:
        return []
    panels: list[float] = []
    while remaining > 244.0:
        remainder_after_full = remaining - 244.0
        if remainder_after_full < 60.0:
            panels.append(122.0)
            remaining -= 122.0
        else:
            panels.append(244.0)
            remaining = remainder_after_full
    if remaining > 0:
        panels.append(round(remaining, 3))
    return panels


def _materialize_beam_openings(structural_segments, panels, face_height, start_adjustment,
                               *, section_context=None, side=None):
    """Project SA openings onto physical segments, then onto executable panels.

    Projection preserves gaps between Para segments; an opening cannot jump a
    pillar simply because the executive panels are drawn next to one another.
    The generator already accepts panel holes. Splitting a panel at an opening
    edge makes its corner-based hole coordinates exact without changing SA cells.
    """
    intervals = []
    executable_offset = 0.0
    for target_pos, target in enumerate(structural_segments):
        target_panels = [p for p in panels if p.get('physical_segment_index', p['segment_index']) ==
                         target.get('physical_segment_index', target['segment_index'])]
        pts = target['points']
        if len(pts) < 2:
            executable_offset += sum(p['width'] for p in target_panels)
            continue
        dx, dy = float(pts[-1][0])-float(pts[0][0]), float(pts[-1][1])-float(pts[0][1])
        norm = math.hypot(dx, dy)
        if norm <= 0:
            continue
        ux, uy = dx/norm, dy/norm
        trim = -start_adjustment if target_pos == 0 else 0.0
        executable_length = sum(p['width'] for p in target_panels)
        for source in structural_segments:
            sp = source.get('opening_source_points') or source['points']
            if len(sp) < 2:
                continue
            sx, sy = float(sp[-1][0])-float(sp[0][0]), float(sp[-1][1])-float(sp[0][1])
            sn = math.hypot(sx, sy)
            if sn <= 0 or abs(sx/sn*uy-sy/sn*ux) > .001:
                continue
            if abs((float(sp[0][0])-float(pts[0][0]))*uy-(float(sp[0][1])-float(pts[0][1]))*ux) > .1:
                continue
            for opening in source.get('lv_cell', {}).get('beam_openings', []):
                height = opening.get('abertura_altura')
                width = opening.get('abertura_largura')
                structural_width = opening.get('largura')
                if height is None or width is None or structural_width is None:
                    continue
                height, width = float(height), float(width)
                if height <= 0 or width <= 0:
                    continue
                extra = (width-float(structural_width))/2.0
                origin = float(opening.get('pos_inicio', 0))-extra
                ax, ay = float(sp[0][0])+sx/sn*origin, float(sp[0][1])+sy/sn*origin
                bx, by = ax+sx/sn*width, ay+sy/sn*width
                a = (ax-float(pts[0][0]))*ux+(ay-float(pts[0][1]))*uy-trim
                b = (bx-float(pts[0][0]))*ux+(by-float(pts[0][1]))*uy-trim
                lo, hi = max(0.0, min(a,b)), min(executable_length, max(a,b))
                if hi-lo > .001:
                    position = 0.
                    owner = target.get('section_contract') or {}
                    if owner.get('beam_type') == 'inverted':
                        from .beam_vertical_context import incident_vertical_contract, lateral_wall_contact
                        midpoint = float(opening.get('pos_inicio', 0))+float(structural_width)/2
                        point = [float(sp[0][0])+sx/sn*midpoint, float(sp[0][1])+sy/sn*midpoint]
                        incident = incident_vertical_contract(point, opening.get('name'),
                            (section_context or {}).get('physical_entries', []))
                        contact = lateral_wall_contact(owner, incident, side)
                        if contact is None:
                            continue
                        height = contact['height_cm']
                        position = contact['panel_height_cm']-contact['top_cm']
                    intervals.append((executable_offset+lo, executable_offset+hi,
                                      min(height,target.get('face_height', face_height)),
                                      opening.get('name',''), position))
        executable_offset += executable_length
    result, offset = [], 0.0
    for panel in panels:
        end = offset+panel['width']
        hits = list(dict.fromkeys((max(a,offset),min(b,end),h,name,pos)
                    for a,b,h,name,pos in intervals if min(b,end)-max(a,offset) > .001))
        # A corner opening already has exact coordinates at either panel edge.
        # Only an interior opening needs a split, at its leading edge. Splitting
        # both edges creates unnecessary narrow strips around the same opening.
        bounds = sorted({offset, end, *[a for a,b,_,_,_ in hits
                                       if offset+.001 < a and b < end-.001]})
        for a,b in zip(bounds,bounds[1:]):
            if b-a <= .001:
                continue
            piece = dict(panel, width=round(b-a,3))
            holes = []
            for lo,hi,h,name,pos in hits:
                left,right = max(a,lo),min(b,hi)
                if right-left <= .001:
                    continue
                holes.append({'active':True,'width':round(right-left,3),'height':h,'position':round(pos,6),
                              'corner':'TL' if left <= a+.001 else 'TR',
                              'source':'sa_lv_cell_beam_opening','references':[name]})
            if holes:
                piece['holes'] = holes
            result.append(piece)
        offset = end
    return result


def _passa_endpoint_adjustments(
    beam: dict[str, Any],
    side: str,
    structural_segments: list[dict[str, Any]],
    pillar_bboxes: dict[str, tuple[float, float, float, float]],
) -> tuple[float, float, list[dict[str, Any]]]:
    """Detecta recuo de 4 cm no lado oposto ao pilar de extremidade.

    A regra e geométrica e vale apenas para o contrato Passa. O pilar precisa
    tocar o primeiro/ultimo ponto e estar predominantemente em A ou B no eixo
    transversal; o lado oposto e o dono do recuo.
    """
    if not structural_segments or not pillar_bboxes:
        return 0.0, 0.0, []
    is_horizontal = bool(beam.get("lv_is_h", beam.get("is_h", True)))
    endpoints = [
        ("start", structural_segments[0]["points"][0]),
        ("end", structural_segments[-1]["points"][-1]),
    ]
    adjustments = {"start": 0.0, "end": 0.0}
    events = []
    tolerance = 4.5
    for endpoint_name, point in endpoints:
        px, py = float(point[0]), float(point[1])
        for pillar_id, bbox in pillar_bboxes.items():
            minx, miny, maxx, maxy = map(float, bbox)
            if not (
                minx - tolerance <= px <= maxx + tolerance
                and miny - tolerance <= py <= maxy + tolerance
            ):
                continue
            transverse_point = py if is_horizontal else px
            transverse_center = (miny + maxy) / 2.0 if is_horizontal else (minx + maxx) / 2.0
            pillar_side = "B" if transverse_center > transverse_point else "A"
            affected_side = "A" if pillar_side == "B" else "B"
            if side == affected_side:
                adjustments[endpoint_name] = -4.0
            events.append({
                "endpoint": endpoint_name,
                "pillar": pillar_id,
                "pillar_side": pillar_side,
                "affected_side": affected_side,
                "adjustment_cm": -4.0 if side == affected_side else 0.0,
                "reason": "Passa: lado oposto ao volume do pilar recua 4 cm",
            })
            break
    return adjustments["start"], adjustments["end"], events


def build_lv_generation_contracts(
    beam: dict[str, Any],
    *,
    beam_name: str | None = None,
    floor: str = "",
    pillar_bboxes: dict[str, tuple[float, float, float, float]] | None = None,
    section_context: dict | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Retorna ``{Para|Passa: {A|B: ficha}}`` sem cruzar contratos.

    Dimensao lateral nunca cai para a ficha FV. Quando o proprio vinculo LV nao
    informa B/H, a ficha sai com ``dimension_status=missing`` para bloquear uma
    geracao silenciosamente contaminada.
    """
    name = str(beam_name or beam.get("name") or "").strip()
    links = beam.get("links") or {}
    fields = beam.get("fields") or {}
    vertical_entries = [e for e in (section_context or {}).get('physical_entries', [])
                        if str(e.get('beam') or '').upper() == name.upper()]
    inverted = any((e.get('section_contract') or {}).get('beam_type') == 'inverted'
                   for e in vertical_entries)
    grouped: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    for key, slots in links.items():
        match = _LINK_RE.match(str(key))
        if not match:
            continue
        side, index_raw, suffix = match.groups()
        behavior = "Para" if suffix.lower() == "comprimento_total" else "Passa"
        slot = f"seg_side_{side.lower()}"
        entries = slots.get(slot, []) if isinstance(slots, dict) else []
        for entry in entries:
            if isinstance(entry, dict):
                grouped.setdefault((behavior, side.upper()), []).append(
                    (int(index_raw), entry)
                )

    result: dict[str, dict[str, dict[str, Any]]] = {"Para": {}, "Passa": {}}
    for behavior in ("Para", "Passa"):
        for side in ("A", "B"):
            rows = sorted(grouped.get((behavior, side), []), key=lambda row: row[0])
            structural_segments = []
            dimension = None
            dimension_source = ""
            for index, entry in rows:
                points = entry.get("points") or []
                length = float(entry.get("len") or _length(points))
                if length <= 0:
                    continue
                entry_dimension = _dimension_from_entry(entry)
                if not dimension and entry_dimension:
                    dimension = entry_dimension
                    dimension_source = str(
                        entry.get("_lv_dimension_source") or "lv_length_link"
                    )
                if not dimension:
                    # Campo N1 canônico do card LV. Pode ter sido enriquecido
                    # cross-class pelo SA, mas a conversão não consulta FV/N2:
                    # consome apenas o resultado já materializado neste contrato.
                    field_key = f"viga_{side.lower()}_seg_{index}_dim"
                    field_dimension = _dimension_from_entry({
                        "lv_dimensao": fields.get(field_key) or beam.get(field_key)
                    })
                    if field_dimension:
                        dimension = field_dimension
                        dimension_source = "sa_lv_segment_field"
                structural_segments.append({
                    "width": length,
                    "segment_index": index,
                    "points": points,
                    "source_key": (
                        f"viga_{side.lower()}_seg_{index}_"
                        f"{'comprimento_total' if behavior == 'Para' else 'comp_total_passa'}"
                    ),
                    "source_slot": f"seg_side_{side.lower()}",
                    "contract_id": f"LV_{side}_{behavior.upper()}",
                    "lv_cell": entry.get("lv_cell") or {},
                })
            if not dimension:
                dimension = _dimension_from_beam_lv(beam)
                if dimension:
                    dimension_source = "beamtracer_lv_dimension_text"
            b, depth = dimension if dimension else (0.0, 0.0)
            # A lateral executiva inclui os 4 cm consolidados no guia LV.
            # Mantemos a profundidade estrutural separada para a visao de corte.
            face_height = depth + 4.0 if depth else 0.0
            vertical_pending = ''
            vertical_pending_segments = []
            if inverted:
                from .beam_vertical_context import partition_inverted_lateral
                partitioned = []
                for structural in structural_segments:
                    try:
                        for piece in partition_inverted_lateral(structural['points'], vertical_entries, side):
                            if piece.get('pending'):
                                vertical_pending_segments.append({
                                    'segment_index': structural['segment_index'],
                                    'source_key': structural['source_key'],
                                    'points': [list(p) for p in piece['points']],
                                    'length_cm': piece['width'],
                                    'vertical_partition': piece['vertical_partition'],
                                    'reason': piece['pending'],
                                })
                            else:
                                partitioned.append({**structural, **piece,
                                                    'opening_source_points': structural['points']})
                    except ValueError as exc:
                        vertical_pending_segments.append({
                            'segment_index': structural['segment_index'],
                            'source_key': structural['source_key'],
                            'points': [list(p) for p in structural['points']],
                            'length_cm': structural['width'],
                            'reason': str(exc),
                        })
                if not vertical_pending_segments:
                    structural_segments = partitioned
                    face_height = max((p['face_height'] for p in partitioned), default=0.)
                else:
                    vertical_pending = '; '.join(dict.fromkeys(
                        p['reason'] for p in vertical_pending_segments))
            start_adjustment = end_adjustment = 0.0
            endpoint_events: list[dict[str, Any]] = []
            if behavior == "Passa":
                start_adjustment, end_adjustment, endpoint_events = (
                    _passa_endpoint_adjustments(
                        beam, side, structural_segments, pillar_bboxes or {}
                    )
                )
            panels = []
            for position, structural in enumerate(structural_segments):
                structural['physical_segment_index'] = position+1
                if vertical_pending:
                    break
                panel_height = structural.get('face_height', face_height)
                executable_length = float(structural["width"])
                if position == 0:
                    executable_length += start_adjustment
                if position == len(structural_segments) - 1:
                    executable_length += end_adjustment
                for panel_index, panel_width in enumerate(
                    distribute_lv_panels(executable_length), start=1
                ):
                    panels.append({
                        "width": panel_width,
                        "height1": panel_height,
                        "height2": panel_height,
                        "grade_h1": 0.0,
                        "grade_h2": 0.0,
                        "panel_type": "Sarrafeado",
                        "structural_segment_index": structural["segment_index"],
                        "segment_index": structural["segment_index"],
                        "physical_segment_index": position+1,
                        "panel_index_in_segment": panel_index,
                        "points": structural["points"],
                        "contract_id": structural["contract_id"],
                        "source_key": structural["source_key"],
                        **({'section_contract': structural['section_contract'],
                            'vertical_partition': structural['vertical_partition']}
                           if 'section_contract' in structural else {}),
                    })
            try:
                panels = _materialize_beam_openings(structural_segments, panels, face_height, start_adjustment,
                    section_context=section_context, side=side)
            except ValueError as exc:
                if not inverted:
                    raise
                vertical_pending = str(exc)
                panels = []
            result[behavior][side] = {
                "number": re.sub(r"\D", "", name),
                "name": f"{name}_{side}_{behavior}",
                "beam_name": name,
                "floor": floor,
                "side": side,
                "behavior": behavior,
                "contract_id": f"LV_{side}_{behavior.upper()}",
                "total_width": b,
                "total_height": face_height,
                "h_section": depth,
                "h_face_rule": "confirmed local inverted mounting" if inverted else "section_depth + 4 cm" if depth else "missing",
                "vertical_pending": vertical_pending,
                "vertical_pending_segments": vertical_pending_segments,
                "panels": panels,
                "structural_segments": structural_segments,
                "structural_segment_count": len(structural_segments),
                "segment_count": len(panels),
                "geometry_length": sum(
                    segment["width"] for segment in structural_segments
                ),
                "start_adjustment": start_adjustment,
                "end_adjustment": end_adjustment,
                "endpoint_events": endpoint_events,
                "endpoint_labels": _endpoint_support_labels(
                    fields, side, structural_segments
                ),
                "total_length": sum(panel["width"] for panel in panels),
                "dimension_status": "sa_lv" if dimension else "missing",
                "generation_ready": bool(panels and dimension and not vertical_pending),
                "_sa_meta": {
                    "source": "Structural Analyzer / N1 / beams.data_json.links",
                    "schema": "lv_generation_contract/v1",
                    "behavior_isolated": True,
                    "fv_dimension_fallback": False,
                    "dimension_source": dimension_source or "missing",
                },
            }
    for side in ("A", "B"):
        para = result["Para"][side]
        passa = result["Passa"][side]
        para_signature = [
            (panel["segment_index"], panel["width"], panel["points"])
            for panel in para["panels"]
        ]
        passa_signature = [
            (panel["segment_index"], panel["width"], panel["points"])
            for panel in passa["panels"]
        ]
        distinct = para_signature != passa_signature
        para["behavior_distinct_from_other"] = distinct
        passa["behavior_distinct_from_other"] = distinct
    return result
