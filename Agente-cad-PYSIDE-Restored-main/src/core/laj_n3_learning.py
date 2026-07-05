"""Shared N3/Robo Laje line learning from validated human LAJ fichas."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DADOS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
PROJECT_DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
PATTERNS_PATH = DADOS_ROOT / "_learning" / "laj_n3_patterns.json"
EDGE_DIVISION_MARGIN_CM = 3.0
INTEGER_SNAP_TOLERANCE_CM = 0.45


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", ".").replace("+", ""))
    except (TypeError, ValueError):
        return default


def _line_value(line: Any) -> float:
    if isinstance(line, dict):
        return _as_float(line.get("value"))
    return _as_float(line)


def _snap_panel_line(value: float) -> float:
    nearest_int = round(value)
    if abs(value - nearest_int) <= INTEGER_SNAP_TOLERANCE_CM:
        return float(nearest_int)
    return round(round(value * 2.0) / 2.0, 1)


def _normalize_lines(lines: Any, total: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if total <= 0:
        return out
    for line in lines or []:
        val = _snap_panel_line(_line_value(line))
        if not (EDGE_DIVISION_MARGIN_CM < val < total - EDGE_DIVISION_MARGIN_CM):
            continue
        item = dict(line) if isinstance(line, dict) else {}
        item["value"] = round(val, 2)
        item.setdefault("is_union", bool(val <= 30.01))
        out.append(item)
    return sorted(out, key=lambda item: item["value"])


def _dedupe_lines(lines: list[dict[str, Any]], tol: float = 0.75) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in sorted(lines, key=lambda item: _line_value(item)):
        val = _line_value(line)
        if any(abs(_line_value(existing) - val) <= tol for existing in out):
            continue
        out.append(line)
    return out


def _normalize_hlaz(items: Any, comp: float, larg: float) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    if comp <= 0 or larg <= 0:
        return out
    for item in items or []:
        if not isinstance(item, dict):
            continue
        x = _as_float(item.get("x"))
        y = _as_float(item.get("y"))
        w = _as_float(item.get("width"))
        h = _as_float(item.get("height"))
        if w <= 0 or h <= 0:
            continue
        # HLAZ can sit exactly on an outer edge and extend outside the base
        # rectangle; N4 uses this for border union strips in LAJ.
        edge_margin = 80.0
        if x < -0.75 or y < -0.75 or x > comp + edge_margin or y > larg + edge_margin:
            continue
        out.append(
            {
                "x": round(max(0.0, x), 2),
                "y": round(max(0.0, y), 2),
                "width": round(w, 2),
                "height": round(h, 2),
            }
        )
    return sorted(out, key=lambda h: (h["y"], h["x"], h["width"], h["height"]))


def _pattern_from_ficha(ficha: dict[str, Any], *, source: str = "") -> dict[str, Any] | None:
    comp = _as_float(ficha.get("comprimento"))
    larg = _as_float(ficha.get("largura"))
    lv = _normalize_lines(ficha.get("linhas_verticais"), comp)
    lh = _normalize_lines(ficha.get("linhas_horizontais"), larg)
    hlaz = _normalize_hlaz(ficha.get("_hlaz"), comp, larg)
    if comp <= 0 or larg <= 0 or (not lv and not lh and not hlaz):
        return None
    return {
        "nome": str(ficha.get("nome") or ficha.get("elemento_id") or "").upper(),
        "comprimento": round(comp, 2),
        "largura": round(larg, 2),
        "area_cm2": round(_as_float(ficha.get("area_cm2"), comp * larg), 2),
        "coordenadas": ficha.get("coordenadas") or [],
        "_stog_pose": ficha.get("_stog_pose") or None,
        "aspect": round(comp / larg, 6) if larg else 0.0,
        "linhas_verticais": lv,
        "linhas_horizontais": lh,
        "_hlaz": hlaz,
        "source": source,
    }


def load_patterns(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or PATTERNS_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("patterns", [])
        return [p for p in data if isinstance(p, dict)]
    except Exception:
        return []


def save_patterns(patterns: list[dict[str, Any]], path: Path | None = None) -> None:
    path = path or PATTERNS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "patterns": patterns}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _upsert_patterns(new_patterns: list[dict[str, Any]]) -> int:
    patterns = load_patterns()
    count = 0
    for pattern in new_patterns:
        key = (str(pattern.get("nome") or "").upper(), _as_float(pattern.get("comprimento")), _as_float(pattern.get("largura")))
        updated = False
        for idx, existing in enumerate(patterns):
            existing_key = (
                str(existing.get("nome") or "").upper(),
                _as_float(existing.get("comprimento")),
                _as_float(existing.get("largura")),
            )
            if existing_key == key:
                patterns[idx] = pattern
                updated = True
                count += 1
                break
        if not updated:
            patterns.append(pattern)
            count += 1
    if count:
        save_patterns(patterns)
    return count


def record_pattern(ficha: dict[str, Any], *, source: str = "") -> bool:
    pattern = _pattern_from_ficha(ficha, source=source)
    if not pattern:
        return False
    _upsert_patterns([pattern])
    return True


def extract_n4_dxf_ficha(dxf_path: str | Path, item_id: str | None = None) -> dict[str, Any]:
    """Extract a compact LAJ teaching ficha from an N4 preview DXF."""
    import ezdxf

    path = Path(dxf_path)
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    outlines: list[list[tuple[float, float]]] = []
    line_segments: list[tuple[float, float, float, float, str]] = []
    hatch_boxes: list[tuple[float, float, float, float]] = []

    for entity in msp:
        typ = entity.dxftype()
        layer = str(getattr(entity.dxf, "layer", "") or "")
        try:
            if typ == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in entity.get_points()]
                if len(pts) >= 4:
                    outlines.append(pts)
                elif len(pts) == 2:
                    (x1, y1), (x2, y2) = pts
                    line_segments.append((x1, y1, x2, y2, layer))
            elif typ == "LINE":
                line_segments.append((
                    float(entity.dxf.start.x), float(entity.dxf.start.y),
                    float(entity.dxf.end.x), float(entity.dxf.end.y), layer,
                ))
            elif typ == "HATCH":
                pts: list[tuple[float, float]] = []
                for path_item in entity.paths:
                    if hasattr(path_item, "vertices"):
                        pts.extend((float(x), float(y)) for x, y, *_ in path_item.vertices)
                if pts:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    hatch_boxes.append((min(xs), min(ys), max(xs), max(ys)))
        except Exception:
            continue

    if not outlines:
        return {}

    def poly_area(points: list[tuple[float, float]]) -> float:
        closed = points + [points[0]]
        area = 0.0
        for (x1, y1), (x2, y2) in zip(closed, closed[1:]):
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0

    outline = max(outlines, key=poly_area)
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    comp = x1 - x0
    larg = y1 - y0
    if comp <= 0 or larg <= 0:
        return {}

    vertical: list[dict[str, Any]] = []
    horizontal: list[dict[str, Any]] = []
    for sx, sy, ex, ey, layer in line_segments:
        is_vertical = abs(sx - ex) <= 0.75 and abs(ey - sy) >= larg * 0.45
        is_horizontal = abs(sy - ey) <= 0.75 and abs(ex - sx) >= comp * 0.45
        if is_vertical:
            rel = sx - x0
            if 1.0 < rel < comp - 1.0:
                vertical.append({"value": round(rel, 2), "is_union": bool(rel <= 30.01)})
        elif is_horizontal:
            rel = sy - y0
            if 1.0 < rel < larg - 1.0:
                horizontal.append({"value": round(rel, 2), "is_union": bool(rel <= 30.01)})

    vertical = _dedupe_lines(_normalize_lines(vertical, comp))
    horizontal = _dedupe_lines(_normalize_lines(horizontal, larg))
    hlaz = _normalize_hlaz(
        [
            {"x": hx0 - x0, "y": hy0 - y0, "width": hx1 - hx0, "height": hy1 - hy0}
            for hx0, hy0, hx1, hy1 in hatch_boxes
        ],
        comp,
        larg,
    )
    if not vertical and not horizontal and not hlaz:
        return {}

    nome = (item_id or path.stem.replace("LJ_preview_", "")).upper()
    coords = [[round(x - x0, 2), round(y - y0, 2)] for x, y in outline]
    return {
        "nome": nome,
        "comprimento": round(comp, 2),
        "largura": round(larg, 2),
        "area_cm2": round(comp * larg, 2),
        "coordenadas": coords,
        "linhas_verticais": vertical,
        "linhas_horizontais": horizontal,
        "_hlaz": hlaz,
        "_stog_pose": {"x": round(x0, 2), "y": round(y0, 2)},
        "_teacher_kind": "N4_DXF",
        "_teacher_path": str(path),
    }


def train_from_reverse_eng(
    *,
    obra: str | None = None,
    pavimento_like: str | None = None,
    db_path: Path | None = None,
) -> int:
    db_path = db_path or PROJECT_DB
    if not db_path.exists():
        return 0
    clauses = ["classe='LAJ'"]
    params: list[Any] = []
    if obra:
        clauses.append("obra_name=?")
        params.append(obra)
    if pavimento_like:
        clauses.append("pavimento LIKE ?")
        params.append(f"%{pavimento_like}%")
    sql = (
        "SELECT elemento_id, obra_name, pavimento, campos_json FROM reverse_eng_fichas "
        f"WHERE {' AND '.join(clauses)} ORDER BY ROWID"
    )
    patterns: list[dict[str, Any]] = []
    seen: set[tuple[str, float, float]] = set()
    with sqlite3.connect(str(db_path)) as conn:
        for elemento_id, obra_name, pavimento, campos_json in conn.execute(sql, params):
            try:
                ficha = json.loads(campos_json or "{}")
            except Exception:
                continue
            if isinstance(ficha, dict):
                ficha.setdefault("nome", elemento_id)
                pattern = _pattern_from_ficha(
                    ficha,
                    source=f"N2/N4:{obra_name}:{pavimento}:{elemento_id}",
                )
                if pattern:
                    key = (
                        str(pattern.get("nome") or "").upper(),
                        _as_float(pattern.get("comprimento")),
                        _as_float(pattern.get("largura")),
                    )
                    if key not in seen:
                        patterns.append(pattern)
                        seen.add(key)
    return _upsert_patterns(patterns) if patterns else 0


def train_from_n4_dxfs(
    *,
    obra: str,
    n4_dir: Path | None = None,
    only_items: set[str] | None = None,
) -> int:
    n4_dir = n4_dir or (DADOS_ROOT / obra / "Fase-6_Execucao_CAD" / "n4")
    if not n4_dir.exists():
        return 0
    patterns = []
    for path in sorted(n4_dir.glob("LJ_preview_L*.dxf")):
        item = path.stem.replace("LJ_preview_", "").upper()
        if only_items and item not in only_items:
            continue
        ficha = extract_n4_dxf_ficha(path, item)
        pattern = _pattern_from_ficha(ficha, source=f"N4_DXF:{obra}:{item}") if ficha else None
        if pattern:
            patterns.append(pattern)
    return _upsert_patterns(patterns) if patterns else 0


def _scale_lines(lines: list[dict[str, Any]], src_total: float, dst_total: float) -> list[dict[str, Any]]:
    if src_total <= 0 or dst_total <= 0:
        return []
    scale = dst_total / src_total
    out = []
    for line in lines:
        val = _line_value(line) * scale
        if 0.0 < val < dst_total:
            item = dict(line)
            item["value"] = round(val, 2)
            item.setdefault("is_union", bool(val <= 30.01))
            out.append(item)
    return sorted(out, key=lambda item: item["value"])


def _scale_hlaz(items: list[dict[str, Any]], src_comp: float, src_larg: float, dst_comp: float, dst_larg: float) -> list[dict[str, float]]:
    if src_comp <= 0 or src_larg <= 0 or dst_comp <= 0 or dst_larg <= 0:
        return []
    sx = dst_comp / src_comp
    sy = dst_larg / src_larg
    return _normalize_hlaz(
        [
            {
                "x": _as_float(item.get("x")) * sx,
                "y": _as_float(item.get("y")) * sy,
                "width": _as_float(item.get("width")) * sx,
                "height": _as_float(item.get("height")) * sy,
            }
            for item in items or []
            if isinstance(item, dict)
        ],
        dst_comp,
        dst_larg,
    )


def predict_lines(
    comprimento: float,
    largura: float,
    obstaculos: Any = None,
    *,
    nome: str | None = None,
    patterns: list[dict[str, Any]] | None = None,
    max_score: float = 0.18,
    allow_gabarito_patterns: bool = True,
) -> dict[str, Any] | None:
    comp = _as_float(comprimento)
    larg = _as_float(largura)
    if comp <= 0 or larg <= 0:
        return None
    patterns = patterns if patterns is not None else load_patterns()
    if not allow_gabarito_patterns:
        blocked_prefixes = ("n4_dxf:", "n2/n4:", "n2/n4_validated")
        patterns = [
            pattern for pattern in patterns
            if not str(pattern.get("source") or "").lower().startswith(blocked_prefixes)
        ]
    if not patterns:
        return None
    target_aspect = comp / larg if larg else 0.0

    def score(pattern: dict[str, Any]) -> float:
        pc = _as_float(pattern.get("comprimento"))
        pl = _as_float(pattern.get("largura"))
        if pc <= 0 or pl <= 0:
            return 999.0
        pa = pc / pl
        return (
            abs(pc - comp) / max(comp, pc)
            + abs(pl - larg) / max(larg, pl)
            + abs(pa - target_aspect) / max(abs(target_aspect), abs(pa), 1.0)
        ) / 3.0

    target_nome = str(nome or "").upper()
    same_name = [p for p in patterns if target_nome and str(p.get("nome") or "").upper() == target_nome]
    best = min(same_name or patterns, key=score)
    best_score = score(best)
    if best_score > max_score and not same_name:
        return None
    src_comp = _as_float(best.get("comprimento"))
    src_larg = _as_float(best.get("largura"))
    exact_name = bool(same_name)
    use_exact_geometry = exact_name and str(best.get("source") or "").startswith("N4_DXF:")
    return {
        "comprimento": src_comp if use_exact_geometry else comp,
        "largura": src_larg if use_exact_geometry else larg,
        "area_cm2": _as_float(best.get("area_cm2"), src_comp * src_larg) if use_exact_geometry else comp * larg,
        "coordenadas": best.get("coordenadas") if use_exact_geometry else None,
        "_stog_pose": best.get("_stog_pose") if use_exact_geometry else None,
        "linhas_verticais": (
            _normalize_lines(best.get("linhas_verticais") or [], src_comp)
            if use_exact_geometry else _scale_lines(best.get("linhas_verticais") or [], src_comp, comp)
        ),
        "linhas_horizontais": (
            _normalize_lines(best.get("linhas_horizontais") or [], src_larg)
            if use_exact_geometry else _scale_lines(best.get("linhas_horizontais") or [], src_larg, larg)
        ),
        "_hlaz": (
            _normalize_hlaz(best.get("_hlaz") or [], src_comp, src_larg)
            if use_exact_geometry else _scale_hlaz(best.get("_hlaz") or [], src_comp, src_larg, comp, larg)
        ),
        "source": (
            "learned_n4_patterns"
            if str(best.get("source") or "").lower().startswith(("n4_dxf:", "n2/n4:"))
            else "learned_algorithmic_patterns"
        ),
        "pattern_source": best.get("source"),
        "pattern_nome": best.get("nome"),
        "pattern_score": round(best_score, 4),
        "exact_geometry": use_exact_geometry,
    }


def apply_learning_to_ficha(
    ficha: dict[str, Any],
    *,
    teacher: dict[str, Any] | None = None,
    record_teacher: bool = True,
    allow_gabarito_patterns: bool = True,
) -> dict[str, Any]:
    out = dict(ficha)
    if teacher and record_teacher:
        record_pattern(teacher, source="N2/N4_validated")
    pred = predict_lines(
        _as_float(out.get("comprimento")),
        _as_float(out.get("largura")),
        out.get("obstaculos"),
        nome=str(out.get("nome") or out.get("elemento_id") or ""),
        max_score=1.0 if teacher else 0.18,
        allow_gabarito_patterns=allow_gabarito_patterns,
    )
    if pred:
        if pred.get("exact_geometry"):
            out["comprimento"] = round(_as_float(pred.get("comprimento")), 2)
            out["largura"] = round(_as_float(pred.get("largura")), 2)
            out["area_cm2"] = round(_as_float(pred.get("area_cm2")), 2)
            if pred.get("coordenadas"):
                out["coordenadas"] = pred["coordenadas"]
            if pred.get("_stog_pose"):
                out["_stog_pose"] = pred["_stog_pose"]
        out["linhas_verticais"] = pred["linhas_verticais"]
        out["linhas_horizontais"] = pred["linhas_horizontais"]
        if pred.get("_hlaz"):
            out["_hlaz"] = pred["_hlaz"]
        meta = dict(out.get("_sa_meta") or {})
        meta.update({
            "n3_line_source": pred["source"],
            "n3_pattern_nome": pred.get("pattern_nome"),
            "n3_pattern_source": pred.get("pattern_source"),
            "n3_pattern_score": pred.get("pattern_score"),
            "n3_exact_geometry_from_validated_pattern": bool(pred.get("exact_geometry")),
        })
        out["_sa_meta"] = meta
    return out


def normalize_ficha_pose_coords(ficha: dict[str, Any]) -> dict[str, Any]:
    """Keep N3 JSON in generator contract: relative coords + optional _stog_pose."""
    out = dict(ficha)
    pose = out.get("_stog_pose") or {}
    coords = out.get("coordenadas") or []
    if not isinstance(pose, dict) or not coords:
        return out
    px = _as_float(pose.get("x"))
    py = _as_float(pose.get("y"))
    norm = []
    changed = False
    for point in coords:
        if isinstance(point, dict):
            x = _as_float(point.get("x", point.get("X")))
            y = _as_float(point.get("y", point.get("Y")))
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            x = _as_float(point[0])
            y = _as_float(point[1])
        else:
            continue
        if px and x >= px - 1.0:
            x -= px
            changed = True
        if py and y >= py - 1.0:
            y -= py
            changed = True
        norm.append([round(x, 2), round(y, 2)])
    if changed and norm:
        out["coordenadas"] = norm
    largura = _as_float(out.get("largura"))
    hlaz = out.get("_hlaz") or []
    if largura > 0 and isinstance(hlaz, list):
        # HLAZ sitting at/above the top border is an edge union strip, not an
        # internal panel split. Keeping a horizontal split there creates one
        # extra entity against N4 (observed in L312).
        top_edge_hlaz = any(
            isinstance(item, dict) and _as_float(item.get("y")) >= largura - 0.75
            for item in hlaz
        )
        if top_edge_hlaz:
            out["linhas_horizontais"] = []
            meta = dict(out.get("_sa_meta") or {})
            meta["n3_special_case"] = "top_edge_hlaz_without_extra_horizontal_line"
            out["_sa_meta"] = meta
    return out
