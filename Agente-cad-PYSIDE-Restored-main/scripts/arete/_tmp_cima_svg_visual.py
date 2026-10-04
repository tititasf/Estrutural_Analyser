"""Render N2 CIMA (recorte) and N3 CIMA L as SVG+PNG for visual/geometric compare."""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import ezdxf

ROOT = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.core.n2_pilar_views import find_n2_pilar_recorte, zone_windows, render_dxf_window_svg
from src.ui.widgets.svg_embed_utils import strip_fixed_size

OUT = ROOT / "scripts" / "arete" / "html_fichas" / "Obra_TREINO_1" / "13_PAV_20260912_161058_141102_pilares_2520" / "cima_l_preview"
OUT.mkdir(parents=True, exist_ok=True)
DARK = "#1b2125"
DB = r"D:/Agente-cad-PYSIDE/project_data.vision"
HTML_DIR = OUT.parent / "pilares_especiais" / "INDETERMINADO"


def dxf_png(path: Path, window, dest: Path, width=1400, height=1100):
    xmin, xmax, ymin, ymax = window
    dpi = 140
    doc = ezdxf.readfile(path)
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi, facecolor=DARK)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(DARK)
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace())
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.savefig(dest, format="png", dpi=dpi, facecolor=DARK, edgecolor="none")
    plt.close(fig)
    print(f"PNG {dest.name}  window=({xmin:.1f},{xmax:.1f},{ymin:.1f},{ymax:.1f})")


def extract_svg_from_html(html_path: Path, aria: str, dest_svg: Path) -> str:
    text = html_path.read_text(encoding="utf-8", errors="replace")
    # Prefer the Foto N2 CIMA block, then N3 CIMA.
    marker = None
    if aria == "n2-cima":
        idx = text.find("CIMA — N2 original")
        if idx < 0:
            idx = text.find("Foto N2")
        chunk = text[idx:] if idx >= 0 else text
        m = re.search(r"<svg[^>]*aria-label=\"CIMA\"[\s\S]*?</svg>", chunk)
    elif aria == "n3-cima":
        idx = text.find("CIMA — parafusos + grades em planta")
        chunk = text[idx:] if idx >= 0 else text
        m = re.search(r"<svg[^>]*aria-label=\"CIMA\"[\s\S]*?</svg>", chunk)
    elif aria == "n4-cima":
        idx = text.find("N4 — Robô via N2")
        chunk = text[idx:] if idx >= 0 else text
        m = re.search(r"<svg[^>]*aria-label=\"CIMA\"[\s\S]*?</svg>", chunk)
    else:
        m = None
    if not m:
        print(f"NO SVG {aria} in {html_path.name}")
        return ""
    svg = m.group(0)
    dest_svg.write_text(svg, encoding="utf-8")
    print(f"SVG {dest_svg.name}  {len(svg)} chars  viewBox={re.search(r'viewBox=\"([^\"]+)\"', svg).group(1) if 'viewBox' in svg else '?'}")
    return svg


def svg_to_png_via_mpl(svg: str, dest: Path, width=1400, height=900):
    """Rasterize matplotlib SVG by re-parsing paths is hard; use cairosvg if present."""
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(dest), output_width=width)
        print(f"PNG via cairo {dest.name}")
        return True
    except Exception as exc:
        print(f"cairo fail {dest.name}: {exc}")
        return False


def tight_cima_window(dxf_path: Path, item: str):
    """Tighten the CIMA cluster around GRADE/PAINEL texts, not the whole x-cluster."""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    xs, ys, texts = [], [], []
    for e in msp:
        dt = e.dxftype()
        if dt in {"TEXT", "MTEXT"}:
            raw = e.plain_text() if dt == "MTEXT" else (e.dxf.text or "")
            raw = raw.replace("\\P", " ").strip()
            ins = e.dxf.insert
            texts.append((float(ins[0]), float(ins[1]), raw))
        pts = []
        try:
            if dt == "LINE":
                pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
            elif dt == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points("xy")]
            elif dt == "CIRCLE":
                c = e.dxf.center
                r = float(e.dxf.radius)
                pts = [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
        except Exception:
            pts = []
        for x, y in pts:
            xs.append(x)
            ys.append(y)
    # CIMA cluster: texts with PAINEL / GRADE / Gxxx near planta letters
    cima_pts = []
    for x, y, raw in texts:
        u = raw.upper()
        if "PAINEL" in u or "GRADE" in u or re.fullmatch(r"G\d+", u) or re.fullmatch(r"[A-H]", raw):
            cima_pts.append((x, y, raw))
    print(f"{item} recorte texts CIMA-like: {len(cima_pts)}")
    for t in cima_pts[:40]:
        print(f"  {t[0]:.1f},{t[1]:.1f}  {t[2]!r}")
    if not cima_pts:
        return None
    cx = [p[0] for p in cima_pts]
    cy = [p[1] for p in cima_pts]
    # pad around the text cluster, then include nearby geometry
    xmin, xmax = min(cx) - 80, max(cx) + 80
    ymin, ymax = min(cy) - 80, max(cy) + 80
    # expand to nearby geometry in that box
    gx = [x for x in xs if xmin - 200 <= x <= xmax + 200]
    gy = [y for y, x in zip(ys, xs) if xmin - 200 <= x <= xmax + 200]
    if gx:
        xmin, xmax = min(gx) - 40, max(gx) + 40
        ymin, ymax = min(gy) - 40, max(gy) + 40
    return (xmin, xmax, ymin, ymax)


def n3_window(dxf_path: Path):
    doc = ezdxf.readfile(dxf_path)
    xs, ys = [], []
    for e in doc.modelspace():
        dt = e.dxftype()
        try:
            if dt == "LINE":
                xs += [e.dxf.start.x, e.dxf.end.x]
                ys += [e.dxf.start.y, e.dxf.end.y]
            elif dt == "LWPOLYLINE":
                pts = list(e.get_points("xy"))
                xs += [p[0] for p in pts]
                ys += [p[1] for p in pts]
            elif dt in {"TEXT", "MTEXT"}:
                ins = e.dxf.insert
                xs.append(float(ins[0]))
                ys.append(float(ins[1]))
            elif dt == "DIMENSION":
                ins = e.dxf.insert
                xs.append(float(ins[0]))
                ys.append(float(ins[1]))
        except Exception:
            pass
    if not xs:
        return None
    return (min(xs) - 30, max(xs) + 30, min(ys) - 30, max(ys) + 30)


def main():
    for item in ("P26", "P27"):
        recorte = find_n2_pilar_recorte("Obra_TREINO_1", "13_PAV", item, db_path=DB)
        print(f"\n=== {item} recorte={recorte}")
        if recorte and recorte.is_file():
            wins = zone_windows(recorte, item)
            print("windows", {k: tuple(round(v, 1) for v in w) for k, w in wins.items()})
            tight = tight_cima_window(recorte, item)
            print("tight", None if not tight else tuple(round(v, 1) for v in tight))
            if "cima" in wins:
                dxf_png(recorte, wins["cima"], OUT / f"{item}_n2_cima_window.png", 1600, 700)
                svg = render_dxf_window_svg(recorte, wins["cima"], width=1600, height=700)
                (OUT / f"{item}_n2_cima_window.svg").write_text(svg, encoding="utf-8")
            if tight:
                dxf_png(recorte, tight, OUT / f"{item}_n2_cima_tight.png", 1400, 1200)
                svg = render_dxf_window_svg(recorte, tight, width=1400, height=1200)
                (OUT / f"{item}_n2_cima_tight.svg").write_text(svg, encoding="utf-8")
        n3 = OUT.parent / "pilares" / "n3_variants" / "para" / f"PL_CIMA_preview_{item}.dxf"
        if n3.is_file():
            w = n3_window(n3)
            print("n3 window", None if not w else tuple(round(v, 1) for v in w))
            if w:
                dxf_png(n3, w, OUT / f"{item}_n3_cima_full.png", 1400, 1400)
        html = HTML_DIR / f"{item}.html"
        if html.is_file():
            for kind in ("n2-cima", "n3-cima", "n4-cima"):
                svg = extract_svg_from_html(html, kind, OUT / f"{item}_{kind}.svg")
                if svg:
                    svg_to_png_via_mpl(svg, OUT / f"{item}_{kind}.png")


if __name__ == "__main__":
    main()
