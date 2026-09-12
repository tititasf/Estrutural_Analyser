"""N2 original views for PIL: pick the human recorte and crop CIMA / ABCDEF."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from src.core.ficha_utils import canonical_pavimento


_FACE_LABEL_RE = re.compile(r"^P(\d+)\.([A-H])$", re.I)
_PAD = 80.0
_DADOS_OBRAS = Path(r"D:/Agente-cad-PYSIDE/DADOS-OBRAS")


def _obra_name(obra: str | Path) -> str:
    return Path(str(obra or "")).name


def _entity_xy(entity) -> list[tuple[float, float]]:
    dt = entity.dxftype()
    try:
        if dt == "LINE":
            return [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
        if dt == "LWPOLYLINE":
            return [(p[0], p[1]) for p in entity.get_points("xy")]
        if dt == "POLYLINE":
            return [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        if dt in {"TEXT", "MTEXT", "INSERT"}:
            ins = entity.dxf.insert
            return [(float(ins[0]), float(ins[1]))]
        if dt in {"CIRCLE", "ARC"}:
            c = entity.dxf.center
            return [(float(c[0]), float(c[1]))]
        if dt == "HATCH":
            box = entity.bbox()
            if box:
                return [(box.extmin.x, box.extmin.y), (box.extmax.x, box.extmax.y)]
    except Exception:
        return []
    return []


def _texts(msp) -> list[tuple[float, float, str]]:
    out = []
    for entity in msp:
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        raw = entity.plain_text() if entity.dxftype() == "MTEXT" else (entity.dxf.text or "")
        raw = raw.replace("\\P", " ").strip()
        if not raw:
            continue
        ins = entity.dxf.insert
        out.append((float(ins[0]), float(ins[1]), raw))
    return out


def _bounds_in_x(msp, xmin: float, xmax: float) -> tuple[float, float, float, float] | None:
    xs, ys = [], []
    for entity in msp:
        for x, y in _entity_xy(entity):
            if xmin <= x <= xmax:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (
        min(xs) - _PAD, max(xs) + _PAD,
        min(ys) - _PAD, max(ys) + _PAD,
    )


def _item_num(item: str) -> str:
    m = re.search(r"(\d+)", str(item or ""))
    return m.group(1) if m else str(item or "").lstrip("P")


def _x_clusters(xs: list[float], gap: float = 450.0) -> list[tuple[float, float]]:
    if not xs:
        return []
    ordered = sorted(xs)
    start = prev = ordered[0]
    out: list[tuple[float, float]] = []
    for x in ordered[1:]:
        if x - prev > gap:
            out.append((start, prev))
            start = x
        prev = x
    out.append((start, prev))
    return out


def zone_windows(dxf_path: str | Path, item: str) -> dict[str, tuple[float, float, float, float]]:
    """Crop windows for CIMA (planta) and ABCDEF elevations in a human N2 recorte."""
    import ezdxf

    path = Path(dxf_path)
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    texts = _texts(msp)
    num = _item_num(item)
    all_xs: list[float] = []
    for entity in msp:
        all_xs.extend(x for x, _y in _entity_xy(entity))
    clusters = _x_clusters(all_xs)

    def labels_in(xmin: float, xmax: float) -> list[str]:
        return [raw.strip() for x, _y, raw in texts if xmin - 20 <= x <= xmax + 20]

    windows: dict[str, tuple[float, float, float, float]] = {}
    for xmin, xmax in clusters:
        labels = labels_in(xmin, xmax)
        faces = []
        has_grade = False
        has_planta_letter = False
        for raw in labels:
            face = _FACE_LABEL_RE.match(raw.replace(" ", ""))
            if face and face.group(1) == num:
                faces.append(face.group(2).upper())
            upper = raw.upper()
            if "GRADE" in upper:
                has_grade = True
            if re.fullmatch(r"[A-H]", raw):
                has_planta_letter = True
        win = _bounds_in_x(msp, xmin, xmax)
        if not win:
            continue
        if any(f in "EFGH" for f in faces) and not any(f in "ABCD" for f in faces):
            windows["ef"] = win
        elif any(f in "ABCD" for f in faces):
            windows["abcd"] = win
        elif has_grade or has_planta_letter:
            windows["cima"] = win
    if "abcd" in windows and "ef" in windows:
        a, e = windows["abcd"], windows["ef"]
        gap = min(abs(a[0] - e[1]), abs(e[0] - a[1]))
        if gap < 500:
            windows["abcdef"] = (
                min(a[0], e[0]), max(a[1], e[1]),
                min(a[2], e[2]), max(a[3], e[3]),
            )
    return windows


def find_n2_pilar_recorte(
    obra: str | Path,
    pavimento: str,
    item: str,
    db_path: str | Path | None = None,
) -> Path | None:
    """Prefer the ficha N2 of this pavement, then the largest sel/motor recorte."""
    obra_name = _obra_name(obra)
    pav = canonical_pavimento(pavimento)
    item = str(item or "").strip().upper()
    if db_path:
        try:
            con = sqlite3.connect(str(db_path))
            row = con.execute(
                "SELECT recorte_path FROM reverse_eng_fichas "
                "WHERE classe='PIL' AND obra_name=? AND elemento_id=? "
                "ORDER BY id DESC",
                (obra_name, item),
            ).fetchall()
            con.close()
        except sqlite3.Error:
            row = []
        for (raw,) in row:
            path = Path(str(raw or ""))
            if not path.is_file():
                continue
            if canonical_pavimento(path.parent.name) == pav or canonical_pavimento(str(raw)) == pav:
                return path
    recortes = _DADOS_OBRAS / obra_name / "Fase-2_Triagem" / "recortes_reversos"
    if not recortes.is_dir():
        return None
    candidates: list[Path] = []
    for path in recortes.rglob(f"PIL_{item}_*.dxf"):
        if canonical_pavimento(path.parent.name) != pav:
            continue
        candidates.append(path)
    if not candidates:
        return None

    def score(path: Path) -> tuple[int, int, int]:
        name = path.name.lower()
        sel = 2 if "_sel_" in name else 1 if "_motor_" in name else 0
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        return (sel, size, 0)

    ranked = sorted(candidates, key=score, reverse=True)
    return ranked[0]


def render_dxf_window_svg(
    dxf_path: str | Path,
    window: tuple[float, float, float, float],
    *,
    width: int = 1400,
    height: int = 900,
) -> str:
    """SVG crop of one N2 zone. ViewBox-only, dark background of the ficha."""
    import io
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from src.ui.widgets.svg_embed_utils import strip_fixed_size as _strip_svg_size

    path = Path(dxf_path)
    if not path.is_file() or not window:
        return ""
    xmin, xmax, ymin, ymax = window
    if xmax - xmin < 1 or ymax - ymin < 1:
        return ""
    dpi = 150
    dark = "#1b2125"
    doc = ezdxf.readfile(path)
    with matplotlib.rc_context({"svg.fonttype": "none"}):
        fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi, facecolor=dark)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor(dark)
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace())
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal", adjustable="box")
        ax.axis("off")
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", dpi=dpi, facecolor=dark, edgecolor="none")
        plt.close(fig)
    buf.seek(0)
    return _strip_svg_size(buf.read().decode("utf-8"))


def n2_view_svgs(
    obra: str | Path,
    pavimento: str,
    item: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """CIMA + ABCDEF SVGs from the original N2 recorte."""
    recorte = find_n2_pilar_recorte(obra, pavimento, item, db_path=db_path)
    if recorte is None:
        return {"recorte": None, "windows": {}, "svgs": {}}
    windows = zone_windows(recorte, item)
    svgs: dict[str, str] = {}
    if "cima" in windows:
        svgs["cima"] = render_dxf_window_svg(recorte, windows["cima"], width=1100, height=900)
    if "abcdef" in windows:
        svgs["abcdef"] = render_dxf_window_svg(recorte, windows["abcdef"], width=1600, height=900)
    else:
        if "abcd" in windows:
            svgs["abcd"] = render_dxf_window_svg(recorte, windows["abcd"], width=1500, height=900)
        if "ef" in windows:
            svgs["ef"] = render_dxf_window_svg(recorte, windows["ef"], width=1200, height=900)
    return {"recorte": recorte, "windows": windows, "svgs": svgs}
