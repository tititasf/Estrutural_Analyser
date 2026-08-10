"""Contrato rigido entre fichas LV e o motor de desenho N3/N4.

O interpretador pode inferir dados a partir do N1 ou do recorte N2. O motor de
desenho nao pode fazer essa inferencia novamente: ele valida e normaliza a
ficha recebida, e depois desenha somente os campos publicados nela.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


SCHEMA = "lv_draw_contract/v2"
_PANEL_TYPES = {"Sarrafeado", "Grade", "Misto"}


class LVDrawContractError(ValueError):
    """Ficha LV insuficiente ou contraditoria para geracao rigida."""


def _positive(value: Any, path: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise LVDrawContractError(f"{path}: numero obrigatorio") from exc
    if number <= 0:
        raise LVDrawContractError(f"{path}: deve ser maior que zero")
    return number


def _segments(unit: dict[str, Any]) -> list[dict[str, Any]]:
    raw = unit.get("segments") or unit.get("panels") or []
    return raw if isinstance(raw, list) else []


def _normalize_segment(
    raw: dict[str, Any], *, path: str, default_height: float
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise LVDrawContractError(f"{path}: segmento deve ser objeto")
    segment = copy.deepcopy(raw)
    width = _positive(
        segment.get("largura_cm", segment.get("width")), f"{path}.largura_cm"
    )
    panel_type = str(segment.get("panel_type") or "Sarrafeado").strip().title()
    if panel_type not in _PANEL_TYPES:
        raise LVDrawContractError(
            f"{path}.panel_type: {panel_type!r}; esperado {sorted(_PANEL_TYPES)}"
        )
    height = segment.get("height1", default_height)
    height = _positive(height, f"{path}.height1")
    segment["largura_cm"] = width
    segment["width"] = width
    segment["height1"] = height
    segment["panel_type"] = panel_type
    segment.setdefault("height2", 0.0)
    segment.setdefault("grade_h1", 0.0)
    segment.setdefault("grade_h2", 0.0)
    segment.setdefault("holes", [])
    segment.setdefault("reuse", False)
    segment.setdefault("reuse_regions", [])
    return segment


def _normalize_face_unit(
    raw: dict[str, Any], *, index: int, default_heights: dict[str, float]
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise LVDrawContractError(f"face_units[{index}]: unidade deve ser objeto")
    unit = copy.deepcopy(raw)
    side = str(unit.get("side") or "").strip().upper()
    if side not in {"A", "B"}:
        raise LVDrawContractError(f"face_units[{index}].side: use A ou B")
    height = _positive(
        unit.get("h_body", unit.get("h_total", default_heights[side])),
        f"face_units[{index}].h_body",
    )
    raw_segments = _segments(unit)
    if not raw_segments:
        raise LVDrawContractError(f"face_units[{index}].segments: vazio")
    unit["side"] = side
    unit["h_body"] = height
    unit["segments"] = [
        _normalize_segment(
            segment,
            path=f"face_units[{index}].segments[{seg_index}]",
            default_height=height,
        )
        for seg_index, segment in enumerate(raw_segments)
    ]
    unit.pop("panels", None)
    return unit


def _drawing_projection(ficha: dict[str, Any]) -> dict[str, Any]:
    """Remove somente metadados de origem; geometria e regras ficam no hash."""
    ignored = {
        "_confianca",
        "_confianca_extracao",
        "_motor_contract",
        "bbox",
        "source_bbox",
        "source_path",
        "visual_primitives",
    }

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: clean(item)
                for key, item in sorted(value.items())
                if key not in ignored and not key.startswith("_source")
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(ficha)


def validate_n4_ficha(
    ficha: dict[str, Any], *, item: str | None = None
) -> dict[str, Any]:
    """Valida e normaliza uma ficha N2 para o motor N4 sem inventar dados.

    Os dois lados sao obrigatorios. ``face_units`` e o contrato preferencial;
    fichas legadas podem fornecer ``segmentos`` e ``segmentos_B``, que sao
    convertidos mecanicamente em uma unidade A e uma unidade B.
    """
    if not isinstance(ficha, dict):
        raise LVDrawContractError("ficha N4 deve ser objeto")
    result = copy.deepcopy(ficha)
    name = str(result.get("viga") or result.get("name") or item or "").strip()
    if not name:
        raise LVDrawContractError("viga: identificador obrigatorio")
    result["viga"] = name

    h_a = _positive(result.get("h_cm", result.get("h_A")), "h_cm")
    h_b = _positive(result.get("h_B_cm", result.get("h_B")), "h_B_cm")
    b = _positive(result.get("b_cm", result.get("b_geom")), "b_cm")
    result["h_cm"] = h_a
    result["h_B_cm"] = h_b
    result["b_cm"] = b

    raw_units = result.get("face_units") or []
    if not raw_units:
        seg_a = result.get("segmentos") or result.get("panels_A") or []
        seg_b = result.get("segmentos_B") or result.get("panels_B") or []
        raw_units = [
            {"side": "A", "label": f"{name}.A", "h_body": h_a, "segments": seg_a},
            {"side": "B", "label": f"{name}.B", "h_body": h_b, "segments": seg_b},
        ]
    if not isinstance(raw_units, list):
        raise LVDrawContractError("face_units: deve ser lista")

    units = [
        _normalize_face_unit(
            unit, index=index, default_heights={"A": h_a, "B": h_b}
        )
        for index, unit in enumerate(raw_units)
    ]
    sides = {unit["side"] for unit in units}
    missing = {"A", "B"} - sides
    if missing:
        raise LVDrawContractError(
            "face_units: lado(s) ausente(s): " + ", ".join(sorted(missing))
        )
    result["face_units"] = units

    sections = result.get("section_views") or []
    if not sections:
        sections = [{
            "h_A": h_a,
            "h_B": h_b,
            "h_section": _positive(
                result.get("h_section_cm", result.get("h_section")),
                "h_section_cm",
            ),
            "b": b,
        }]
    if not isinstance(sections, list):
        raise LVDrawContractError("section_views: deve ser lista")
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise LVDrawContractError(f"section_views[{index}]: deve ser objeto")
        _positive(
            section.get("h_section", section.get("h_section_cm")),
            f"section_views[{index}].h_section",
        )
    result["section_views"] = copy.deepcopy(sections)

    projection = _drawing_projection(result)
    fingerprint = hashlib.sha256(
        json.dumps(
            projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    result["_motor_contract"] = {
        "schema": SCHEMA,
        "mode": "strict",
        "source": "N2_FICHA",
        "drawing_fingerprint": fingerprint,
        "inference_inside_generator": False,
    }
    return result

