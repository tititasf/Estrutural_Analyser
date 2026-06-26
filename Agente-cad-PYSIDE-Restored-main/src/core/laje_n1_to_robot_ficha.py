"""Convert N1 LAJ interpretation data into the robot LJ ficha contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", ".").replace("+", ""))
    except (TypeError, ValueError):
        return default


def _extract_numero(nome: str) -> int | None:
    m = re.search(r"\d+", nome or "")
    return int(m.group()) if m else None


def _normalize_point(point: Any) -> list[float] | None:
    if isinstance(point, dict):
        x = point.get("x", point.get("X"))
        y = point.get("y", point.get("Y"))
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        x, y = point[0], point[1]
    else:
        return None
    return [_as_float(x), _as_float(y)]


def _normalize_points(points: Any) -> list[list[float]]:
    out: list[list[float]] = []
    for p in points or []:
        np = _normalize_point(p)
        if np is not None:
            out.append(np)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _points_from_outline_links(n1_laje: dict[str, Any]) -> list[list[float]]:
    links = n1_laje.get("links", {}).get("laje_outline_segs", {})
    if isinstance(links, list):
        link_lists = [links]
    elif isinstance(links, dict):
        link_lists = list(links.values())
    else:
        link_lists = []

    pts: list[list[float]] = []
    for link_list in link_lists:
        for link in link_list or []:
            for key in ("points", "coords", "coordenadas"):
                if key in link:
                    pts.extend(_normalize_points(link.get(key)))
            if "start" in link and "end" in link:
                start = _normalize_point(link.get("start"))
                end = _normalize_point(link.get("end"))
                if start:
                    pts.append(start)
                if end:
                    pts.append(end)
    return pts


def _shoelace_area(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    closed = points + [points[0]]
    for (x1, y1), (x2, y2) in zip(closed, closed[1:]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _bbox_dims(points: list[list[float]]) -> tuple[float, float]:
    if not points:
        return 0.0, 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return max(xs) - min(xs), max(ys) - min(ys)


def _line_count_to_positions(count: Any, total: float) -> list[dict[str, Any]]:
    n = int(_as_float(count, 0.0))
    if n <= 0 or total <= 0:
        return []
    step = total / (n + 1)
    return [{"value": round(step * i, 1), "is_union": False} for i in range(1, n + 1)]


def _normalize_lines(value: Any, total: float) -> list[dict[str, Any]]:
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                val = _as_float(item.get("value"))
                if 0.0 < val < total:
                    normalized = dict(item)
                    normalized["value"] = round(val, 1)
                    normalized.setdefault("is_union", False)
                    out.append(normalized)
            else:
                val = _as_float(item)
                if 0.0 < val < total:
                    out.append({"value": round(val, 1), "is_union": False})
        return sorted(out, key=lambda x: x["value"])
    return _line_count_to_positions(value, total)


def _field(n1_laje: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in n1_laje:
        return n1_laje[key]
    fields = n1_laje.get("fields") or {}
    if key in fields:
        return fields[key]
    return default


def n1_laje_to_robot_ficha(
    n1_laje: dict[str, Any],
    *,
    modo_selecionado: int | str | None = None,
) -> dict[str, Any]:
    nome = str(_field(n1_laje, "nome", _field(n1_laje, "name", _field(n1_laje, "id_item", "L?"))))
    if not nome or nome == "None":
        nome = "L?"

    coords = _normalize_points(_field(n1_laje, "coordenadas", None))
    if not coords:
        coords = _normalize_points(_field(n1_laje, "points", None))
    if not coords:
        coords = _points_from_outline_links(n1_laje)

    comprimento = _as_float(_field(n1_laje, "comprimento", 0.0))
    largura = _as_float(_field(n1_laje, "largura", 0.0))
    if (comprimento <= 0 or largura <= 0) and coords:
        comprimento, largura = _bbox_dims(coords)

    area_cm2 = _as_float(_field(n1_laje, "area_cm2", 0.0))
    if area_cm2 <= 0:
        area = _as_float(_field(n1_laje, "area", 0.0))
        area_cm2 = area * 10000.0 if 0 < area < 10000 else area
    if area_cm2 <= 0 and coords:
        area_cm2 = _shoelace_area(coords)
    if area_cm2 <= 0 and comprimento > 0 and largura > 0:
        area_cm2 = comprimento * largura

    mode = modo_selecionado
    if mode is None:
        mode = _field(n1_laje, "modo_selecionado", 0)

    linhas_v = _normalize_lines(
        _field(n1_laje, "linhas_verticais", _field(n1_laje, "laje_linhas_v_count", [])),
        comprimento,
    )
    linhas_h = _normalize_lines(
        _field(n1_laje, "linhas_horizontais", _field(n1_laje, "laje_linhas_h_count", [])),
        largura,
    )

    return {
        "nome": nome.upper(),
        "numero": _extract_numero(nome),
        "coordenadas": coords,
        "comprimento": round(comprimento, 2),
        "largura": round(largura, 2),
        "area_cm2": round(area_cm2, 2),
        "modo_selecionado": int(_as_float(mode, 0.0)),
        "linhas_verticais": linhas_v,
        "linhas_horizontais": linhas_h,
        "obstaculos": _field(n1_laje, "obstaculos", []) or [],
        "unioes_nos_bordes": _field(n1_laje, "unioes_nos_bordes", []) or [],
        "observacoes": _field(n1_laje, "observacoes", "") or "",
    }


def write_n1_laje_robot_ficha(n1_laje: dict[str, Any], output_dir: str | Path) -> Path:
    import json

    ficha = n1_laje_to_robot_ficha(n1_laje)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{ficha['nome']}.json"
    path.write_text(json.dumps(ficha, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
