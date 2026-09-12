"""Compositor da ficha web de laterais de viga (Lado A/B, Para/Passa)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import ficha_reader, lv_operations


_BEAM_RE = re.compile(r"(?:V|VF)\d+[A-Z]?", re.IGNORECASE)
_CLASSES = {
    "para": {"A": "lateral_a_para", "B": "lateral_b_para"},
    "passa": {"A": "lateral_a_passa", "B": "lateral_b_passa"},
}


def _natural(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _number(value: Any) -> float | None:
    if value in (None, "", "—", "-"):
        return None
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value))
    return float(match.group(0).replace(",", ".")) if match else None


def _dimensions(value: Any) -> tuple[float | None, float | None]:
    values = re.findall(r"[-+]?\d+(?:[.,]\d+)?", str(value or ""))
    parsed = [float(item.replace(",", ".")) for item in values]
    return (parsed[0] if parsed else None, parsed[1] if len(parsed) > 1 else None)


def _segment(
    obra_dir: Path,
    pavimento: str,
    classe: str,
    item: dict[str, Any],
    *,
    include_svgs: bool,
) -> dict[str, Any]:
    fields = item.get("campos") or {}
    width, height = _dimensions(fields.get("Largura"))
    photos = (
        ficha_reader.resolver_fotos_portal(obra_dir, pavimento, classe, item)
        if include_svgs else {"n1": None, "n3": None}
    )
    return {
        "id": item.get("item_id"),
        "index": int(_number(fields.get("Segmento")) or 0),
        "length_cm": _number(fields.get("Comprimento")),
        "width_cm": width,
        "beam_height_cm": height,
        "level": _number(fields.get("Nível")),
        "status": fields.get("Status"),
        "attention": item.get("atencao") or "",
        "points": item.get("points") or [],
        "pillar_openings": [],
        "layers": {
            "sa": {"available": bool(photos.get("n1")) if include_svgs else True,
                   "lazy": not include_svgs, "svg": photos.get("n1")},
            "c1": {"available": False, "svg": None},
            "c2": {"available": False, "svg": None},
            "c3": {"available": False, "svg": None},
            "n3_panels": {"available": bool(photos.get("n3")) if include_svgs else True,
                          "lazy": not include_svgs, "svg": photos.get("n3")},
        },
    }


def _cut_views(
    obra_dir: Path,
    pavimento: str,
    beam: str,
    estado: dict[str, Any],
    *,
    include_svgs: bool,
) -> list[dict[str, Any]]:
    result = []
    for raw in estado.get("cortes") or []:
        if str(raw.get("beam_name") or "").upper() != beam.upper():
            continue
        item = ficha_reader._normalizar_corte(raw, {  # fonte canônica já usada pelo portal
            slab.get("name"): slab for slab in estado.get("slabs") or [] if slab.get("name")
        })
        photos = (
            ficha_reader.resolver_fotos_portal(obra_dir, pavimento, "cortes", item)
            if include_svgs else {"n1": None, "n3": None}
        )
        result.append({
            "id": item.get("item_id"),
            "beam": beam,
            "own_slab": raw.get("own_laje"),
            "neighbor_slab": raw.get("neigh_laje"),
            "beam_height_cm": _number(raw.get("beam_h")),
            "confidence_percent": raw.get("conf_pct"),
            "status": raw.get("status"),
            "attention": raw.get("atencao") or "",
            "layers": {
                "sa": {"available": bool(photos.get("n1")) if include_svgs else True,
                       "lazy": not include_svgs, "svg": photos.get("n1")},
                "n3_cut": {"available": bool(photos.get("n3")) if include_svgs else True,
                           "lazy": not include_svgs, "svg": photos.get("n3")},
            },
        })
    return result


def montar_ficha_lv(
    obra_dir: Path,
    pavimento: str,
    beam: str,
    behavior: str,
    estado: dict[str, Any],
    *,
    include_svgs: bool = True,
) -> dict[str, Any]:
    behavior = str(behavior or "").lower()
    if behavior not in _CLASSES:
        raise ValueError("comportamento deve ser para ou passa")
    if not _BEAM_RE.fullmatch(str(beam or "")):
        raise ValueError("nome de viga lateral inválido")

    override = lv_operations.load_override(obra_dir, pavimento, behavior, beam)
    by_side: dict[str, dict[str, Any]] = {}
    all_beams: set[str] = set()
    for side, classe in _CLASSES[behavior].items():
        all_items = ficha_reader.listar_itens_n1(estado, classe)
        all_beams.update(str(item.get("beam_name") or "") for item in all_items if item.get("beam_name"))
        selected = [item for item in all_items if str(item.get("beam_name") or "").upper() == beam.upper()]
        segments = sorted(
            (_segment(obra_dir, pavimento, classe, item, include_svgs=include_svgs) for item in selected),
            key=lambda item: item["index"],
        )
        side_overrides = (override.get("sides") or {}).get(side) or {}
        for segment in segments:
            manual = side_overrides.get(str(segment["index"])) or {}
            segment["pillar_openings"] = list(manual.get("pillar_openings") or [])
        by_side[side] = {
            "class": classe,
            "segments": segments,
        }

    beams = sorted(all_beams, key=_natural)
    canonical = next((name for name in beams if name.upper() == beam.upper()), None)
    if canonical is None:
        raise LookupError("viga lateral não encontrada")
    position = beams.index(canonical)
    return {
        "schema": "cad.portal.lv_ficha/v1",
        "beam": {
            "name": canonical,
            "behavior": behavior,
            "behavior_label": (
                "Segmentos param nos pilares" if behavior == "para"
                else "Segmentos passam pelos pilares"
            ),
            "position": position + 1,
            "total_beams": len(beams),
            "previous": beams[position - 1] if position > 0 else None,
            "next": beams[position + 1] if position + 1 < len(beams) else None,
        },
        "sides": by_side,
        "cut_views": _cut_views(
            obra_dir, pavimento, canonical, estado, include_svgs=include_svgs,
        ),
    }


def resolver_camada_lv(
    obra_dir: Path,
    pavimento: str,
    beam: str,
    behavior: str,
    estado: dict[str, Any],
    layer: str,
    *,
    side: str = "A",
    segment_index: int = 1,
    cut_index: int = 0,
) -> dict[str, Any]:
    """Materializa apenas a camada atualmente visível, preservando o SVG canônico."""
    behavior = behavior.lower()
    side = side.upper()
    if behavior not in _CLASSES or side not in {"A", "B"}:
        raise ValueError("lateral inválida")
    if layer == "n3_cut":
        cuts = [
            item for item in ficha_reader.listar_itens_n1(estado, "cortes")
            if str(item.get("beam_name") or "").upper() == beam.upper()
        ]
        if cut_index < 0 or cut_index >= len(cuts):
            raise LookupError("visão de corte não encontrada")
        photo = ficha_reader.resolver_foto_portal(
            obra_dir, pavimento, "cortes", cuts[cut_index], "n3",
        )
        svg = photo.get("svg")
        return {"layer": layer, "available": bool(svg), "svg": svg,
                "origin": photo.get("origem")}
    if layer not in {"sa", "n3_panels"}:
        raise ValueError("camada lateral inválida")
    classe = _CLASSES[behavior][side]
    items = [
        item for item in ficha_reader.listar_itens_n1(estado, classe)
        if str(item.get("beam_name") or "").upper() == beam.upper()
        and int(_number((item.get("campos") or {}).get("Segmento")) or 0) == segment_index
    ]
    if not items:
        raise LookupError("segmento lateral não encontrado")
    key = "n1" if layer == "sa" else "n3"
    photo = ficha_reader.resolver_foto_portal(
        obra_dir, pavimento, classe, items[0], key,
    )
    svg = photo.get("svg")
    return {"layer": layer, "available": bool(svg), "svg": svg,
            "origin": photo.get("origem")}
