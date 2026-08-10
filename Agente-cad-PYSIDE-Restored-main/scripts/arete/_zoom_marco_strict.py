# -*- coding: utf-8 -*-
"""Zoom estrito marco N2×N4 — sem aspect expandir o crop."""
from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import ezdxf  # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

from arete._diag_right_wall_v301 import N4_DIR, resolve_n2  # noqa: E402
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402
from arete.geometry_lv_units import pair_units, split_n4_view, unit_label  # noqa: E402
from gerar_lv_dxf_stog import (  # noqa: E402
    _marco_extension_cm,
    _small_panel_start_x,
    select_canonical_face_units,
)

OUT = Path(__file__).resolve().parent / "relatorios" / "g2v" / "v301_geometry_gate" / "html_animal"
OUT.mkdir(parents=True, exist_ok=True)


def render_strict(dxf: Path, png: Path, clip, title: str) -> None:
    doc = ezdxf.readfile(str(dxf))
    msp = doc.modelspace()
    fig = plt.figure(figsize=(10, 7), dpi=150)
    ax = fig.add_axes([0.05, 0.05, 0.9, 0.88])
    ax.set_facecolor("#0a0a12")
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
    xmin, ymin, xmax, ymax = clip
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    # re-force limits after aspect (evita expandir para vizinho)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_title(title, color="#e2e8f0", fontsize=11)
    fig.savefig(png, dpi=150, facecolor="#0a0a12")
    plt.close(fig)
    print("wrote", png, png.stat().st_size)


def main():
    item = "V301"
    n2 = resolve_n2(item)
    entry = _entry_from_live_recorte(item)
    fus = select_canonical_face_units(entry.get("face_units") or [], item)
    n4a = N4_DIR / "LV_preview_V301_VIEW_A.dxf"
    n4 = {"A": split_n4_view(n4a, "A"), "B": []}
    n2s = {"A": [], "B": []}
    for i, u in enumerate(fus):
        s = str(u.get("side") or "?").upper()
        if s in n2s:
            u = dict(u)
            u["_idx"] = i
            n2s[s].append(u)

    for pr in pair_units(n2s["A"], n4["A"]):
        if pr["status"] != "paired":
            continue
        u2, u4 = pr["n2"], pr["n4"]
        lab = unit_label(u2, u2.get("_idx", 0))
        if lab != "V301.A":
            continue
        panels = u2.get("panels") or []
        h = float(u2.get("h_body") or 0)
        full = sum(float(p.get("width", 0) or 0) for p in panels)
        be = float(_small_panel_start_x(0.0, h, panels) or full)
        mh = _marco_extension_cm(bool(u2.get("marco_laje_sup")), float(u2.get("laje_sup") or 0))
        ox4, oy4 = u4["origin"]
        bb = u2.get("bbox") or {}
        ox2, oy2 = float(bb["x_left"]), float(bb["y_bot"])
        # crop: um pouco de corpo + marco + cotas (sem vizinho)
        rel = (be - 80.0, -40.0, full + 70.0, h + mh + 25.0)
        c4 = (ox4 + rel[0], oy4 + rel[1], ox4 + rel[2], oy4 + rel[3])
        c2 = (ox2 + rel[0], oy2 + rel[1], ox2 + rel[2], oy2 + rel[3])
        p4 = OUT / "V301.A_MARCO_STRICT_N4.png"
        p2 = OUT / "V301.A_MARCO_STRICT_N2.png"
        render_strict(n4a, p4, c4, f"N4 STRICT marco be={be:.0f} full={full:.0f}")
        render_strict(n2, p2, c2, f"N2 STRICT marco be={be:.0f} full={full:.0f}")
        html = OUT / "V301_MARCO_STRICT.html"
        html.write_text(
            f"""<!DOCTYPE html><html><head><meta charset=utf-8>
<title>V301.A marco STRICT</title>
<style>
body{{margin:0;background:#070b14;color:#e5e7eb;font-family:system-ui}}
header{{padding:16px 22px;background:#134e4a}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px}}
img{{width:100%;background:#000;border:1px solid #334155;border-radius:10px}}
.mut{{color:#94a3b8}}
</style></head><body>
<header><h1>V301.A — marco STRICT (mesmo crop relativo)</h1>
<p class=mut>body_end={be:.1f} full_end={full:.1f} marco_h={mh:.1f}. Se N2 também tiver caixa vazia no marco, a geometria é real; se N2 for parede única, o N4 está overdrawing.</p>
</header>
<div class=grid>
<div><h2>N2 gabarito</h2><img src="{p2.name}"></div>
<div><h2>N4 motor</h2><img src="{p4.name}"></div>
</div></body></html>""",
            encoding="utf-8",
        )
        webbrowser.open(html.resolve().as_uri())
        os.startfile(str(p2))
        os.startfile(str(p4))
        print("HTML", html)


if __name__ == "__main__":
    main()
