"""Regen CIMA L DXF/SVG/PNG and patch HTML N3 CIMA panel."""
from __future__ import annotations

import json
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

from gerar_pl_dxf_stog import generate_pilar_zone, setup_doc
from src.core.cima_l_contract import portal_cima_l_contract, is_cima_l
from src.ui.widgets.svg_embed_utils import strip_fixed_size

PACK = ROOT / "scripts" / "arete" / "html_fichas" / "Obra_TREINO_1" / "13_PAV_20260912_161058_141102_pilares_2520"
PREVIEW = PACK / "cima_l_preview"
HTML_DIR = PACK / "pilares_especiais" / "INDETERMINADO"
DARK = "#1b2125"


def merge_payload(raw: dict) -> dict:
    base = dict(raw)
    nested = raw.get("n1_base")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update({k: v for k, v in raw.items() if k != "n1_base"})
        for key in ("subtipo_pil", "geometry_points", "pilar_especial"):
            if key in nested and key not in merged:
                merged[key] = nested[key]
            if key in nested:
                merged[key] = nested[key]
        return merged
    return base


def window_of(doc):
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
        return (-200, 200, -200, 200)
    return (min(xs) - 40, max(xs) + 40, min(ys) - 40, max(ys) + 40)


def render(doc, dest_png: Path, dest_svg: Path, width=1400, height=1400):
    xmin, xmax, ymin, ymax = window_of(doc)
    dpi = 140
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi, facecolor=DARK)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(DARK)
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace())
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.savefig(dest_png, format="png", dpi=dpi, facecolor=DARK, edgecolor="none")
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", dpi=dpi, facecolor=DARK, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    svg = strip_fixed_size(buf.read().decode("utf-8"))
    dest_svg.write_text(svg, encoding="utf-8")
    print(f"wrote {dest_png.name} {dest_svg.name} window=({xmin:.0f},{xmax:.0f},{ymin:.0f},{ymax:.0f})")
    return svg


def field_table_html(rows):
    parts = ['<table class="field-table">']
    for a, b in rows:
        parts.append(f"<tr><td>{a}</td><td>{b}</td></tr>")
    parts.append("</table>")
    return "".join(parts)


def patch_html(html_path: Path, svg: str, table: str):
    text = html_path.read_text(encoding="utf-8", errors="replace")
    marker = "CIMA — parafusos + grades em planta"
    idx = text.find(marker)
    if idx < 0:
        print("no CIMA card in", html_path.name)
        return
    chunk = text[idx:]
    table_m = re.search(r'<table class="field-table">[\s\S]*?</table>', chunk)
    svg_m = re.search(r"<svg[\s\S]*?</svg>", chunk)
    if table_m:
        start = idx + table_m.start()
        end = idx + table_m.end()
        text = text[:start] + table + text[end:]
        # recompute svg after table replacement
        idx = text.find(marker)
        chunk = text[idx:]
        svg_m = re.search(r"<svg[\s\S]*?</svg>", chunk)
    if svg_m:
        # keep class/aria of original if present
        orig = svg_m.group(0)
        cls = ""
        am = re.search(r'class="[^"]+"', orig)
        if am:
            cls = " " + am.group(0)
        aria = ' role="img" aria-label="CIMA" alt="CIMA"'
        body = svg
        body = re.sub(r"<svg([^>]*)>", lambda m: f"<svg{m.group(1)}{cls}{aria}>" if "aria-label" not in m.group(1) else f"<svg{m.group(1)}>", body, count=1)
        start = idx + svg_m.start()
        end = idx + svg_m.end()
        text = text[:start] + body + text[end:]
    html_path.write_text(text, encoding="utf-8")
    print("patched", html_path.name)


def main():
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for item in ("P26", "P27"):
        raw_path = PACK / "pilares" / "n3_variants" / "para" / f"{item}.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        pj = merge_payload(raw)
        print(item, "is_cima_l", is_cima_l(pj), "subtipo", pj.get("subtipo_pil"))
        card = portal_cima_l_contract(pj)
        print(" rows", len(card.get("rows") or []))
        for row in card.get("rows") or []:
            print("  ", row)
        for variant in ("para", "passa"):
            for zone, prefix in (("cima", "PL_CIMA"), ("abcd", "PL_ABCD"), ("grades", "PL_GRADES")):
                dest = PACK / "pilares" / "n3_variants" / variant / f"{prefix}_preview_{item}.dxf"
                doc = setup_doc()
                n = generate_pilar_zone(doc.modelspace(), dict(pj), zone, visual_mode="NOVA")
                doc.saveas(dest)
                print(f"DXF {variant} {zone} {item} ents={n} -> {dest.name}")
        doc = ezdxf.readfile(PACK / "pilares" / "n3_variants" / "para" / f"PL_CIMA_preview_{item}.dxf")
        svg = render(doc, PREVIEW / f"{item}_cima_l.png", PREVIEW / f"{item}_cima_l.svg")
        table = field_table_html(card.get("rows") or [])
        patch_html(HTML_DIR / f"{item}.html", svg, table)
        for zone, prefix in (("abcd", "PL_ABCD"), ("grades", "PL_GRADES")):
            zdoc = ezdxf.readfile(PACK / "pilares" / "n3_variants" / "para" / f"{prefix}_preview_{item}.dxf")
            render(
                zdoc,
                PREVIEW / f"{item}_{zone}.png",
                PREVIEW / f"{item}_{zone}.svg",
                width=1800,
                height=900,
            )


if __name__ == "__main__":
    main()
