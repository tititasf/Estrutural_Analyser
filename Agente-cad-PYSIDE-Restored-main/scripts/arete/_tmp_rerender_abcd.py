"""Re-render ABCD/GRADES with a tight crop so A-F fill the viewer."""
from __future__ import annotations

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
from src.ui.widgets.svg_embed_utils import strip_fixed_size

PACK = ROOT / "scripts" / "arete" / "html_fichas" / "Obra_TREINO_1" / "13_PAV_20260912_161058_141102_pilares_2520"
PREVIEW = PACK / "cima_l_preview"
DARK = "#1b2125"


def extents(doc):
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
                y = float(ins[1])
                if y > 50:
                    continue
                xs.append(float(ins[0]))
                ys.append(y)
        except Exception:
            pass
    if not xs:
        return (-40, 1700, -500, 50)
    return (min(xs) - 40, max(xs) + 60, min(ys) - 50, max(ys) + 40)


def render(dxf_path: Path, png: Path, svg_path: Path, w=1900, h=520):
    doc = ezdxf.readfile(dxf_path)
    xmin, xmax, ymin, ymax = extents(doc)
    dpi = 140
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi, facecolor=DARK)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(DARK)
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace())
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.savefig(png, format="png", dpi=dpi, facecolor=DARK, edgecolor="none")
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", dpi=dpi, facecolor=DARK, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    svg_path.write_text(strip_fixed_size(buf.read().decode("utf-8")), encoding="utf-8")
    print(png.name, "window", tuple(round(v, 1) for v in (xmin, xmax, ymin, ymax)))


def main():
    for item in ("P26", "P27"):
        for zone, prefix in (("abcd", "PL_ABCD"), ("grades", "PL_GRADES")):
            dxf = PACK / "pilares" / "n3_variants" / "para" / f"{prefix}_preview_{item}.dxf"
            render(dxf, PREVIEW / f"{item}_{zone}.png", PREVIEW / f"{item}_{zone}.svg")


if __name__ == "__main__":
    main()
