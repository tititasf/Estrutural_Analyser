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
) -> dict[str, dict[str, dict[str, Any]]]:
    """Retorna ``{Para|Passa: {A|B: ficha}}`` sem cruzar contratos.

    Dimensao lateral nunca cai para a ficha FV. Quando o proprio vinculo LV nao
    informa B/H, a ficha sai com ``dimension_status=missing`` para bloquear uma
    geracao silenciosamente contaminada.
    """
    name = str(beam_name or beam.get("name") or "").strip()
    links = beam.get("links") or {}
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
            for index, entry in rows:
                points = entry.get("points") or []
                length = float(entry.get("len") or _length(points))
                if length <= 0:
                    continue
                dimension = dimension or _dimension_from_entry(entry)
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
                })
            dimension = dimension or _dimension_from_beam_lv(beam)
            b, depth = dimension if dimension else (0.0, 0.0)
            # A lateral executiva inclui os 4 cm consolidados no guia LV.
            # Mantemos a profundidade estrutural separada para a visao de corte.
            face_height = depth + 4.0 if depth else 0.0
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
                        "height1": face_height,
                        "height2": face_height,
                        "grade_h1": 0.0,
                        "grade_h2": 0.0,
                        "panel_type": "Sarrafeado",
                        "structural_segment_index": structural["segment_index"],
                        "segment_index": structural["segment_index"],
                        "panel_index_in_segment": panel_index,
                        "points": structural["points"],
                        "contract_id": structural["contract_id"],
                        "source_key": structural["source_key"],
                    })
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
                "h_face_rule": "section_depth + 4 cm" if depth else "missing",
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
                "total_length": sum(panel["width"] for panel in panels),
                "dimension_status": "sa_lv" if dimension else "missing",
                "generation_ready": bool(panels and dimension),
                "_sa_meta": {
                    "source": "Structural Analyzer / N1 / beams.data_json.links",
                    "schema": "lv_generation_contract/v1",
                    "behavior_isolated": True,
                    "fv_dimension_fallback": False,
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
