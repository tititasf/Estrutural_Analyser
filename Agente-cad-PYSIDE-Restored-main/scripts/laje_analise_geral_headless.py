"""
Analise Geral Headless para LAJ - equivalente ao loop FV, sem GUI/PySide6.

Fluxo:
  1. Le DXF path do projeto no DB
  2. Carrega DXF via DXFLoader em TRUE_GEOMETRY
  3. Constroi SpatialIndex
  4. Roda SlabTracer.detect_slabs_from_texts(valid_layers=None)
  5. Extrai dimensoes, area, linhas/cotas internas e pontaletes
  6. UPSERT deterministico em slab_elements
  7. Render headless limpo + vinculos/poligonos
  8. Chama laje_loop_runner.run()

Uso:
    python -X utf8 scripts/laje_analise_geral_headless.py --obra Obra_TREINO_1 --pav 13
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")

BG = "#0a0a14"
CLEAN_LINE = "#3a3a52"
SLAB_EDGE = "#4dd0ff"
SLAB_FILL = "#4dd0ff"
LABEL_COLOR = "#ffe14d"
CUT_VIEW_COLOR = "#ff4d6d"
HUMAN_CUT_COLOR = "#00ff95"


def get_project(obra_name: str, pav_filter: str | None, db_path: Path) -> tuple[str | None, str | None]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if pav_filter:
            row = conn.execute(
                "SELECT id, dxf_path FROM projects WHERE work_name=? AND pavement_name LIKE ?",
                [obra_name, f"%{pav_filter}%"],
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, dxf_path FROM projects WHERE work_name=? LIMIT 1",
                [obra_name],
            ).fetchone()
        if not row:
            return None, None
        return row["id"], row["dxf_path"]
    finally:
        conn.close()


def ensure_slab_elements_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS slab_elements (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            laje_nome TEXT,
            classe TEXT DEFAULT 'LAJ',
            campos_json TEXT,
            n_linhas INTEGER DEFAULT 0,
            is_validated BOOLEAN DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_slab_elements_project "
        "ON slab_elements(project_id, classe, laje_nome)"
    )


def upsert_slab_element(
    conn: sqlite3.Connection,
    project_id: str,
    laje_nome: str,
    n_linhas: int,
    campos: dict,
) -> None:
    el_id = f"BE-LAJ-{project_id}-{laje_nome}"
    existing = conn.execute(
        "SELECT is_validated FROM slab_elements WHERE id=?",
        (el_id,),
    ).fetchone()
    if existing and int(existing[0] or 0) == 1:
        print(f"  [preservado] {laje_nome}: slab_elements validado por humano")
        return
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO slab_elements
            (id, project_id, laje_nome, classe, campos_json, n_linhas,
             is_validated, created_at, updated_at)
        VALUES (?, ?, ?, 'LAJ', ?, ?, 0, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            campos_json = excluded.campos_json,
            n_linhas = excluded.n_linhas,
            updated_at = excluded.updated_at
        """,
        (
            el_id,
            str(project_id),
            laje_nome,
            json.dumps(campos, ensure_ascii=False),
            int(n_linhas),
            now,
            now,
        ),
    )


def _iter_dxf_segments(dxf_data: dict):
    for line in dxf_data.get("lines", []):
        s, e = line.get("start"), line.get("end")
        if s and e:
            yield [s, e]
    for poly in dxf_data.get("polylines", []):
        pts = poly.get("points", [])
        for i in range(len(pts) - 1):
            yield [pts[i], pts[i + 1]]


def _points_bbox(points: list) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _poly_area(points: list) -> float:
    if len(points) < 3:
        return 0.0
    pts = points[:]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    area = 0.0
    for p1, p2 in zip(pts, pts[1:]):
        area += float(p1[0]) * float(p2[1]) - float(p2[0]) * float(p1[1])
    return abs(area) / 2.0


def _line_parts_from_item(item: dict) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    if "start" in item and "end" in item:
        s, e = item["start"], item["end"]
        return [((float(s[0]), float(s[1])), (float(e[0]), float(e[1])))]
    pts = item.get("points") or []
    parts = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        parts.append(((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))))
    return parts


def _cluster_values(values: list[float], tol: float = 3.0) -> list[float]:
    if not values:
        return []
    ordered = sorted(values)
    groups = [[ordered[0]]]
    for value in ordered[1:]:
        if value - groups[-1][-1] <= tol:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(g) / len(g) for g in groups]


def _count_internal_axes(dxf_data: dict, bbox: tuple[float, float, float, float]) -> tuple[int, int]:
    x0, y0, x1, y1 = bbox
    w = max(1.0, x1 - x0)
    h = max(1.0, y1 - y0)
    margin_x = max(4.0, w * 0.025)
    margin_y = max(4.0, h * 0.025)
    tol = max(0.5, min(w, h) * 0.01)
    min_v_len = h * 0.35
    min_h_len = w * 0.35

    verticals: list[float] = []
    horizontals: list[float] = []
    for item in list(dxf_data.get("lines", [])) + list(dxf_data.get("polylines", [])):
        layer = str(item.get("layer") or "").upper()
        if any(tok in layer for tok in ("COTA", "DIM", "TEXT", "TEXTO", "EIXO", "HATCH")):
            continue
        for a, b in _line_parts_from_item(item):
            sx0, sy0 = min(a[0], b[0]), min(a[1], b[1])
            sx1, sy1 = max(a[0], b[0]), max(a[1], b[1])
            if sx1 < x0 or sx0 > x1 or sy1 < y0 or sy0 > y1:
                continue
            dx = abs(a[0] - b[0])
            dy = abs(a[1] - b[1])
            if dx <= tol and dy >= min_v_len:
                x = (a[0] + b[0]) / 2.0
                if x0 + margin_x < x < x1 - margin_x:
                    verticals.append(x)
            elif dy <= tol and dx >= min_h_len:
                y = (a[1] + b[1]) / 2.0
                if y0 + margin_y < y < y1 - margin_y:
                    horizontals.append(y)

    return len(_cluster_values(verticals, tol=tol * 2.0)), len(_cluster_values(horizontals, tol=tol * 2.0))


def _estimate_panel_line_count(comprimento: float, largura: float) -> int:
    """Estimate LAJ panel/cota line count from slab module dimensions.

    This is a fallback for DXFs where internal support/cota lines are not encoded
    as reliable geometry inside the detected boundary.
    """
    short = min(float(comprimento or 0.0), float(largura or 0.0))
    if short <= 0:
        return 0
    if short <= 90.0:
        return 2
    if short <= 150.0:
        return 1
    if short <= 220.0:
        return 3
    if short <= 360.0:
        return 4
    return 5


def _normalize_laje_name(name: str) -> str:
    m = re.search(r"L\s*[-_\.]?\s*(\d+[A-Z0-9_]*)", str(name or "").upper())
    return f"L{m.group(1)}" if m else str(name or "").upper().strip()


def _bbox_from_points(points: list) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    try:
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def _bbox_center(bb: tuple[float, float, float, float]) -> tuple[float, float]:
    return (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0


def _same_cut_bbox(a: tuple[float, float, float, float], b: tuple[float, float, float, float], tol: float = 28.0) -> bool:
    ac = _bbox_center(a)
    bc = _bbox_center(b)
    if math.hypot(ac[0] - bc[0], ac[1] - bc[1]) > tol:
        return False
    return abs((a[2] - a[0]) - (b[2] - b[0])) <= tol and abs((a[3] - a[1]) - (b[3] - b[1])) <= tol


def _looks_like_support_pillar(points: list, geom: Any, bb: tuple[float, float, float, float]) -> bool:
    if not points or not bb:
        return False
    w = bb[2] - bb[0]
    h = bb[3] - bb[1]
    if w <= 0 or h <= 0:
        return False
    closed = len(points) >= 4 and points[0] == points[-1]
    aspect = max(w / max(h, 1.0), h / max(w, 1.0))
    try:
        fill_ratio = abs(float(getattr(geom, "area", 0.0) or 0.0)) / max(w * h, 1.0)
    except Exception:
        fill_ratio = 0.0
    if closed and aspect <= 4.0 and len(points) <= 6 and fill_ratio >= 0.70:
        return True
    if closed and aspect <= 2.5 and len(points) >= 10 and fill_ratio >= 0.65:
        return True
    return False


def load_human_cut_refs(conn: sqlite3.Connection, project_id: str) -> dict[str, dict]:
    refs: dict[str, dict] = {}
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name, links_json, validated_link_classes_json FROM slabs WHERE project_id=?",
        (project_id,),
    ).fetchall()
    for row in rows:
        name = _normalize_laje_name(row["name"])
        try:
            links = json.loads(row["links_json"] or "{}")
            validated = json.loads(row["validated_link_classes_json"] or "{}")
        except Exception:
            continue
        cut_slots = set(validated.get("laje_visao_corte") or []) if isinstance(validated, dict) else set()
        old_level_slots = set(validated.get("laje_nivel") or []) if isinstance(validated, dict) else set()
        cut_links = links.get("laje_visao_corte", {}) if isinstance(links, dict) else {}
        old_level_links = links.get("laje_nivel", {}) if isinstance(links, dict) else {}
        if not isinstance(cut_links, dict):
            cut_links = {}
        if not isinstance(old_level_links, dict):
            old_level_links = {}
        cuts = []
        slot_sources = [
            ("cut_view_geom", cut_links.get("cut_view_geom", []) or [], cut_slots),
            ("neighbor_level_text", cut_links.get("neighbor_level_text", []) or [], cut_slots),
            ("cut_view_geom", old_level_links.get("cut_view_geom", []) or [], old_level_slots),
            ("cut_view_text", old_level_links.get("cut_view_text", []) or [], old_level_slots),
        ]
        for slot, slot_links, slot_validated in slot_sources:
            for link in slot_links:
                if not isinstance(link, dict):
                    continue
                if slot not in slot_validated and not link.get("validated"):
                    continue
                pts = link.get("points") or []
                bb = _bbox_from_points(pts)
                cuts.append(
                    {
                        "slot": slot,
                        "bbox": bb,
                        "points": pts,
                        "text": link.get("text"),
                    }
                )
        if cuts:
            refs[name] = {"cut_views": cuts}
    return refs


def _slab_polygons(slabs_found: list[dict]) -> dict[str, Any]:
    from shapely.geometry import Polygon

    polys: dict[str, Any] = {}
    for slab in slabs_found:
        pts = slab.get("points") or []
        if len(pts) < 3:
            continue
        try:
            poly = Polygon(pts)
            if poly.is_valid and not poly.is_empty and poly.area > 100:
                polys[_normalize_laje_name(slab.get("name"))] = poly
        except Exception:
            continue
    return polys


def detect_cut_view_candidates(dxf_data: dict, slabs_found: list[dict]) -> dict[str, list[dict]]:
    """Detecta geometrias pequenas de visao de corte tocando/contornando lajes.

    A regra e propositalmente geometrica e sem layer fixo: polilinhas pequenas,
    com formato de detalhe/corte, perto da borda da laje.
    """
    from shapely.geometry import LineString, Polygon

    slab_polys = _slab_polygons(slabs_found)
    candidates = []
    for item in dxf_data.get("polylines", []) or []:
        pts = item.get("points") or []
        if len(pts) < 7 or len(pts) > 28:
            continue
        bb = _bbox_from_points(pts)
        if not bb:
            continue
        w = bb[2] - bb[0]
        h = bb[3] - bb[1]
        if w < 18 or h < 18 or w > 170 or h > 170:
            continue
        if w / max(h, 1.0) > 5.5 or h / max(w, 1.0) > 5.5:
            continue
        try:
            geom = Polygon(pts) if pts[0] == pts[-1] else LineString(pts)
            if geom.is_empty:
                continue
            if _looks_like_support_pillar(pts, geom, bb):
                continue
            candidates.append((item, geom, bb))
        except Exception:
            continue

    out: dict[str, list[dict]] = {name: [] for name in slab_polys}
    used_by_laje: dict[str, list[tuple[float, float, float, float]]] = {name: [] for name in slab_polys}
    for name, poly in slab_polys.items():
        minx, miny, maxx, maxy = poly.bounds
        min_dim = max(1.0, min(maxx - minx, maxy - miny))
        max_dist = max(28.0, min(115.0, min_dim * 0.20))
        ranked = []
        for item, geom, bb in candidates:
            try:
                dist_boundary = float(geom.distance(poly.boundary))
                dist_poly = float(geom.distance(poly))
            except Exception:
                continue
            if dist_boundary <= max_dist and dist_poly <= max_dist:
                ranked.append((dist_boundary, item, bb))
        for dist, item, bb in sorted(ranked, key=lambda x: x[0])[:6]:
            if any(_same_cut_bbox(bb, old) for old in used_by_laje[name]):
                continue
            used_by_laje[name].append(bb)
            out[name].append(
                {
                    "type": "poly",
                    "points": item.get("points") or [],
                    "bbox": tuple(round(float(v), 3) for v in bb),
                    "layer": item.get("layer"),
                    "distance_to_slab": round(dist, 3),
                    "source": "headless_cut_view_detector",
                }
            )
    return out


def summarize_cut_view_detection(auto_cuts: dict[str, list[dict]], human_refs: dict[str, dict]) -> dict:
    expected = {name for name, ref in human_refs.items() if ref.get("cut_views")}
    detected = {name for name, cuts in auto_cuts.items() if cuts}
    tp = expected & detected
    fp = detected - expected
    fn = expected - detected
    return {
        "expected": sorted(expected, key=_normalize_laje_name),
        "detected": sorted(detected, key=_normalize_laje_name),
        "tp": sorted(tp, key=_normalize_laje_name),
        "fp": sorted(fp, key=_normalize_laje_name),
        "fn": sorted(fn, key=_normalize_laje_name),
        "precision": (len(tp) / len(detected) * 100.0) if detected else 0.0,
        "recall": (len(tp) / len(expected) * 100.0) if expected else 0.0,
    }


def process_laje(slab: dict, dxf_data: dict, cut_views: list[dict] | None = None, human_cut_ref: dict | None = None) -> dict:
    points = slab.get("points") or []
    if len(points) >= 2 and points[0] != points[-1]:
        points = points + [points[0]]

    if points:
        bbox = _points_bbox(points)
        comprimento = bbox[2] - bbox[0]
        largura = bbox[3] - bbox[1]
        area = float(slab.get("area") or 0.0) or _poly_area(points)
    else:
        bbox = (0.0, 0.0, 0.0, 0.0)
        comprimento = largura = area = 0.0

    linhas_v, linhas_h = _count_internal_axes(dxf_data, bbox) if points else (0, 0)
    raw_linhas_total = linhas_v + linhas_h
    estimated_linhas_total = _estimate_panel_line_count(comprimento, largura)
    linhas_total = raw_linhas_total
    if estimated_linhas_total and raw_linhas_total == estimated_linhas_total + 1 and estimated_linhas_total >= 5:
        linhas_total = raw_linhas_total
    elif estimated_linhas_total and (raw_linhas_total == 0 or abs(raw_linhas_total - estimated_linhas_total) >= 1):
        linhas_total = estimated_linhas_total
    diag = slab.get("trace_diagnostics") or {}
    cut_views = cut_views or []
    human_cuts = (human_cut_ref or {}).get("cut_views") or []

    return {
        "nome": slab.get("name", "").upper(),
        "pos": slab.get("pos"),
        "coordenadas": points,
        "bbox": bbox,
        "comprimento": round(comprimento, 2),
        "largura": round(largura, 2),
        "area_cm2": round(area, 2),
        "linhas_verticais_count": linhas_v,
        "linhas_horizontais_count": linhas_h,
        "linhas_total_count": linhas_total,
        "linhas_total_raw_count": raw_linhas_total,
        "linhas_total_estimated_count": estimated_linhas_total,
        "pontaletes": {},
        "cut_view_count": len(cut_views),
        "cut_views": cut_views,
        "human_cut_view_count": len(human_cuts),
        "human_cut_views": human_cuts,
        "has_cut_view": bool(cut_views),
        "is_detected": bool(slab.get("is_detected")),
        "method": slab.get("method"),
        "confidence_score": slab.get("confidence_score"),
        "confidence_level": slab.get("confidence_level"),
        "candidate_line_count": diag.get("candidate_line_count"),
        "accepted_line_count": diag.get("accepted_line_count"),
        "rejected_line_count": diag.get("rejected_line_count"),
        "trace_diagnostics": diag,
    }


def render_pavimento(
    dxf_data: dict,
    slabs_found: list[dict],
    cut_views_by_laje: dict[str, list[dict]] | None,
    human_cut_refs: dict[str, dict] | None,
    out_dir: str | Path,
    prefix: str,
    focus_laje: str | None = None,
) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Polygon as MplPolygon

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_segs = list(_iter_dxf_segments(dxf_data))
    if not clean_segs:
        return {}

    xs = [p[0] for seg in clean_segs for p in seg]
    ys = [p[1] for seg in clean_segs for p in seg]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    mx = (xmax - xmin) * 0.03 or 10
    my = (ymax - ymin) * 0.03 or 10

    def new_ax(title: str):
        fig, ax = plt.subplots(1, 1, figsize=(20, 14), facecolor=BG)
        ax.set_facecolor(BG)
        ax.add_collection(LineCollection(clean_segs, colors=CLEAN_LINE, linewidths=0.5))
        ax.set_xlim(xmin - mx, xmax + mx)
        ax.set_ylim(ymin - my, ymax + my)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(title, color="#ffffff", fontsize=13, pad=8)
        ax.axis("off")
        return fig, ax

    fig, ax = new_ax("PAVIMENTO LIMPO")
    p_limpo = out_dir / f"{prefix}_limpo.png"
    fig.savefig(str(p_limpo), dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)

    cut_views_by_laje = cut_views_by_laje or {}
    human_cut_refs = human_cut_refs or {}

    def draw_cut_views(ax, slab_name: str, only_human: bool = False):
        auto_items = [] if only_human else cut_views_by_laje.get(_normalize_laje_name(slab_name), [])
        for cut in auto_items:
            pts = cut.get("points") or []
            if len(pts) >= 2:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                ax.plot(xs, ys, color=CUT_VIEW_COLOR, linewidth=1.8, alpha=0.95)
        for cut in (human_cut_refs.get(_normalize_laje_name(slab_name), {}).get("cut_views") or []):
            pts = cut.get("points") or []
            if len(pts) >= 2:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                ax.plot(xs, ys, color=HUMAN_CUT_COLOR, linewidth=2.1, alpha=0.95, linestyle="--")

    fig, ax = new_ax("PAVIMENTO + POLIGONOS DE LAJE DETECTADOS")
    drawn = 0
    for slab in slabs_found:
        points = slab.get("points") or []
        if len(points) >= 3:
            patch = MplPolygon(points, closed=True, facecolor=SLAB_FILL, edgecolor=SLAB_EDGE, alpha=0.18, linewidth=1.6)
            ax.add_patch(patch)
            drawn += 1
        pos = slab.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            ax.plot(pos[0], pos[1], "o", color=LABEL_COLOR, markersize=4)
            ax.annotate(
                slab.get("name", ""),
                (pos[0], pos[1]),
                color=LABEL_COLOR,
                fontsize=6,
                xytext=(3, 3),
                textcoords="offset points",
            )
    p_vinc = out_dir / f"{prefix}_vinculos.png"
    fig.savefig(str(p_vinc), dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)

    fig, ax = new_ax("PAVIMENTO + VISAO DE CORTE LAJ")
    cut_count = 0
    human_count = 0
    for slab in slabs_found:
        points = slab.get("points") or []
        if len(points) >= 3:
            patch = MplPolygon(points, closed=True, facecolor=SLAB_FILL, edgecolor=SLAB_EDGE, alpha=0.08, linewidth=1.0)
            ax.add_patch(patch)
        name = slab.get("name", "")
        draw_cut_views(ax, name)
        cut_count += len(cut_views_by_laje.get(_normalize_laje_name(name), []) or [])
        human_count += len(human_cut_refs.get(_normalize_laje_name(name), {}).get("cut_views") or [])
        pos = slab.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) >= 2 and (
            cut_views_by_laje.get(_normalize_laje_name(name)) or human_cut_refs.get(_normalize_laje_name(name))
        ):
            ax.annotate(name, (pos[0], pos[1]), color=LABEL_COLOR, fontsize=7, xytext=(3, 3), textcoords="offset points")
    p_cortes = out_dir / f"{prefix}_cortes_laj.png"
    fig.savefig(str(p_cortes), dpi=140, bbox_inches="tight", facecolor=BG)
    plt.close(fig)

    result = {
        "limpo": str(p_limpo),
        "vinculos": str(p_vinc),
        "cortes": str(p_cortes),
        "slabs_desenhadas": drawn,
        "cut_views_desenhadas": cut_count,
        "human_cut_views_desenhadas": human_count,
    }

    if focus_laje:
        focus = focus_laje.upper()
        fig, ax = new_ax(f"PAVIMENTO + VINCULOS DA LAJE {focus}")
        focus_drawn = 0
        for slab in slabs_found:
            if (slab.get("name") or "").upper() != focus:
                continue
            points = slab.get("points") or []
            if len(points) >= 3:
                patch = MplPolygon(points, closed=True, facecolor=SLAB_FILL, edgecolor="#ff4d6d", alpha=0.28, linewidth=2.4)
                ax.add_patch(patch)
                focus_drawn += 1
            draw_cut_views(ax, slab.get("name", ""))
            pos = slab.get("pos")
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                ax.plot(pos[0], pos[1], "o", color=LABEL_COLOR, markersize=5)
                ax.annotate(
                    slab.get("name", ""),
                    (pos[0], pos[1]),
                    color=LABEL_COLOR,
                    fontsize=8,
                    xytext=(4, 4),
                    textcoords="offset points",
                )
        p_focus = out_dir / f"{prefix}_{focus}_vinculos.png"
        fig.savefig(str(p_focus), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(fig)
        result["item_vinculos"] = str(p_focus)
        result["item_desenhado"] = focus_drawn

    return result


def run(
    obra_name: str,
    pav_filter: str | None = None,
    db_path: Path = DB_PATH,
    debug_laje: str | None = None,
) -> list[dict] | None:
    print(f"\n[Analise Geral Headless LAJ] obra={obra_name} pav={pav_filter or 'TODOS'}")

    project_id, dxf_path = get_project(obra_name, pav_filter, db_path)
    if not project_id:
        print("  [ERRO] Projeto nao encontrado no DB.")
        return None
    if not dxf_path or not Path(dxf_path).exists():
        print(f"  [ERRO] DXF nao encontrado: {dxf_path}")
        return None

    print(f"  project_id: {project_id}")
    print(f"  dxf_path:   {dxf_path}")

    print("  Carregando DXF...")
    from src.core.dxf_loader import DXFLoader, RenderMode

    dxf_data = DXFLoader.load_dxf(dxf_path, mode=RenderMode.TRUE_GEOMETRY)
    if not dxf_data:
        print("  [ERRO] DXFLoader retornou None.")
        return None
    lines = dxf_data.get("lines", [])
    polys = dxf_data.get("polylines", [])
    texts = dxf_data.get("texts", [])
    print(f"  DXF: {len(lines)} linhas, {len(polys)} polys, {len(texts)} textos")

    print("  Construindo SpatialIndex...")
    from src.core.spatial_index import SpatialIndex

    spatial_index = SpatialIndex()
    for poly in polys:
        pts = poly.get("points", [])
        if pts:
            spatial_index.insert(
                poly,
                (
                    min(p[0] for p in pts),
                    min(p[1] for p in pts),
                    max(p[0] for p in pts),
                    max(p[1] for p in pts),
                ),
            )
    for line in lines:
        s, e = line["start"], line["end"]
        spatial_index.insert(line, (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1])))
    for txt in texts:
        p = txt["pos"]
        spatial_index.insert(txt, (p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5))
    print(f"  SpatialIndex: {spatial_index.counter} objetos indexados")

    print("  Executando SlabTracer sem filtro por layer...")
    from src.core.slab_tracer import SlabTracer

    tracer = SlabTracer(spatial_index)
    slabs_found = tracer.detect_slabs_from_texts(texts, search_radius=2000.0, valid_layers=None, teacher_dims=None)
    print(f"  Lajes detectadas: {len(slabs_found)}")

    conn_refs = sqlite3.connect(str(db_path))
    try:
        human_cut_refs = load_human_cut_refs(conn_refs, project_id)
    finally:
        conn_refs.close()
    cut_views_by_laje = detect_cut_view_candidates(dxf_data, slabs_found)
    cut_summary = summarize_cut_view_detection(cut_views_by_laje, human_cut_refs)
    print("\n  [Visao de corte LAJ]")
    print(f"    seeds humanos: {len(cut_summary['expected'])} lajes -> {', '.join(cut_summary['expected']) or '-'}")
    print(f"    detectadas N1: {len(cut_summary['detected'])} lajes -> {', '.join(cut_summary['detected']) or '-'}")
    print(f"    precisao vs seeds: {cut_summary['precision']:.1f}% | recall vs seeds: {cut_summary['recall']:.1f}%")
    if cut_summary["fn"]:
        print(f"    faltando seeds: {', '.join(cut_summary['fn'])}")

    if debug_laje:
        target = debug_laje.upper()
        for slab in slabs_found:
            if slab.get("name") == target:
                print(f"\n  --- DEBUG {target} ---")
                print(json.dumps(slab.get("trace_diagnostics", {}), indent=2, ensure_ascii=False))
                break
        else:
            print(f"\n  [WARN] Laje '{target}' nao encontrada.")

    print("  Salvando resultados em slab_elements...")
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_slab_elements_schema(conn)
        n_saved = 0
        for slab in slabs_found:
            name = (slab.get("name") or "").upper()
            if not re.match(r"^L\d+", name):
                continue
            norm_name = _normalize_laje_name(name)
            laj = process_laje(
                slab,
                dxf_data,
                cut_views=cut_views_by_laje.get(norm_name, []),
                human_cut_ref=human_cut_refs.get(norm_name, {}),
            )
            n_linhas = int(laj["linhas_total_count"])
            upsert_slab_element(conn, project_id, name, n_linhas, laj)
            n_saved += 1
        conn.commit()
        print(f"  slab_elements LAJ atualizados: {n_saved}")
    finally:
        conn.close()

    try:
        render_dir = ROOT / "sandbox_laje_loop"
        prefix = f"laj_{obra_name}_{pav_filter or 'all'}".replace(" ", "_")
        pngs = render_pavimento(
            dxf_data,
            slabs_found,
            cut_views_by_laje,
            human_cut_refs,
            render_dir,
            prefix=prefix,
            focus_laje=debug_laje,
        )
        if pngs:
            print("\n  [Render visual]")
            print(f"    limpo:    {pngs.get('limpo')}")
            print(f"    vinculos: {pngs.get('vinculos')}  ({pngs.get('slabs_desenhadas')} lajes)")
            print(
                f"    cortes:   {pngs.get('cortes')}  "
                f"({pngs.get('cut_views_desenhadas')} N1, {pngs.get('human_cut_views_desenhadas')} humanos)"
            )
            if pngs.get("item_vinculos"):
                print(f"    item:     {pngs.get('item_vinculos')}  ({pngs.get('item_desenhado')} laje)")
    except Exception as e:
        print(f"  [WARN] Render visual falhou: {e}")

    print("\n" + "=" * 60)
    print("  Rodando comparacao LAJ (laje_loop_runner)...")
    print("=" * 60)
    import scripts.laje_loop_runner as ljr

    return ljr.run(obra_name, pav_filter, db_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analise Geral Headless LAJ sem GUI")
    parser.add_argument("--obra", required=True)
    parser.add_argument("--pav", default=None)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--debug-laje", default=None)
    args = parser.parse_args()

    run(
        obra_name=args.obra,
        pav_filter=args.pav,
        db_path=Path(args.db),
        debug_laje=args.debug_laje,
    )


if __name__ == "__main__":
    main()
