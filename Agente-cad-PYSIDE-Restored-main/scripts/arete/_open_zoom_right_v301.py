# -*- coding: utf-8 -*-
"""Gera zoom N2×N4 da parede extrema direita + cotas e abre no browser."""
from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

from arete._diag_right_wall_v301 import N4_DIR, resolve_n2  # noqa: E402
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402
from arete.geometry_lv_units import pair_units, split_n4_view, unit_label  # noqa: E402
from arete.vision_anti_hallucination import abs_clip, render_dxf_png  # noqa: E402
from gerar_lv_dxf_stog import (  # noqa: E402
    _marco_extension_cm,
    _small_panel_start_x,
    select_canonical_face_units,
)

OUT = Path(__file__).resolve().parent / "relatorios" / "g2v" / "v301_geometry_gate" / "html_animal"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    item = "V301"
    n2 = resolve_n2(item)
    entry = _entry_from_live_recorte(item)
    fus = select_canonical_face_units(entry.get("face_units") or [], item)
    n4a = N4_DIR / "LV_preview_V301_VIEW_A.dxf"
    n4b = N4_DIR / "LV_preview_V301_VIEW_B.dxf"
    n4 = {"A": split_n4_view(n4a, "A"), "B": split_n4_view(n4b, "B")}
    n2s: dict[str, list] = {"A": [], "B": []}
    for i, u in enumerate(fus):
        s = str(u.get("side") or "?").upper()
        if s in n2s:
            u = dict(u)
            u["_idx"] = i
            n2s[s].append(u)

    jobs = []
    for side, n4p in (("A", n4a), ("B", n4b)):
        for pr in pair_units(n2s[side], n4[side]):
            if pr["status"] != "paired":
                continue
            u2, u4 = pr["n2"], pr["n4"]
            lab = unit_label(u2, u2.get("_idx", 0))
            if lab not in ("V301.A", "V301.B"):
                continue
            panels = u2.get("panels") or []
            h = float(u2.get("h_body") or 0)
            full = sum(float(p.get("width", 0) or 0) for p in panels)
            be = float(_small_panel_start_x(0.0, h, panels) or full)
            mh = _marco_extension_cm(
                bool(u2.get("marco_laje_sup")), float(u2.get("laje_sup") or 0)
            )
            ox4, oy4 = u4["origin"]
            bb = u2.get("bbox") or {}
            ox2, oy2 = float(bb["x_left"]), float(bb["y_bot"])
            # clip relativo: corpo|marco + faixa de cotas à direita
            clip_rel = (be - 55.0, -80.0, full + 90.0, h + mh + 40.0)
            c4 = abs_clip((ox4, oy4), clip_rel)
            c2 = abs_clip((ox2, oy2), clip_rel)
            p4 = OUT / f"{lab}_ZOOM_RIGHT_N4.png"
            p2 = OUT / f"{lab}_ZOOM_RIGHT_N2.png"
            ok4 = render_dxf_png(
                n4p, p4, clip=c4, title=f"{lab} N4 RIGHT+COTAS",
                width_px=1500, height_px=920, dpi=160,
            )
            ok2 = render_dxf_png(
                n2, p2, clip=c2, title=f"{lab} N2 RIGHT+COTAS",
                width_px=1500, height_px=920, dpi=160,
            )
            print(lab, "N4", ok4, p4.stat().st_size if p4.exists() else 0)
            print(lab, "N2", ok2, p2.stat().st_size if p2.exists() else 0)
            jobs.append((lab, p2.name, p4.name, be, full, mh))

    # também full view
    for path, name, title in (
        (n4a, "N4_VIEW_A.png", "N4 VIEW_A"),
        (n4b, "N4_VIEW_B.png", "N4 VIEW_B"),
        (n2, "N2_recorte.png", "N2 recorte"),
    ):
        dest = OUT / name
        ok = render_dxf_png(path, dest, clip=None, title=title, width_px=1800, height_px=780, dpi=140)
        print(title, ok)

    cards = []
    for lab, n2n, n4n, be, full, mh in jobs:
        cards.append(
            f"""<div class="card"><h2>{lab} — zoom parede extrema + cotas</h2>
<p class="mut">body_end={be:.1f} · full_end={full:.1f} · marco={mh:.1f}<br/>
Cotas altura devem estar em <code>full+25={full+25:.1f}</code> e
<code>full+50={full+50:.1f}</code> — FORA da parede, não dentro do marco.</p>
<div class="grid">
<div><h3>N2 gabarito</h3><img src="{n2n}" alt="n2"/></div>
<div><h3>N4 motor (agora)</h3><img src="{n4n}" alt="n4"/></div>
</div></div>"""
        )

    html = OUT / "V301_ZOOM_RIGHT_COTAS.html"
    html.write_text(
        f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"/>
<title>V301 ZOOM parede direita + cotas</title>
<style>
body{{margin:0;background:#070b14;color:#e5e7eb;font-family:system-ui,sans-serif}}
header{{padding:18px 24px;background:linear-gradient(105deg,#0f172a,#134e4a,#0f172a);border-bottom:1px solid #1f2937}}
h1{{margin:0 0 8px;font-size:1.4rem}}.mut{{color:#94a3b8}}
main{{padding:16px 22px 56px;max-width:1680px;margin:0 auto}}
.card{{background:#0f172a;border:1px solid #1f2937;border-radius:14px;padding:14px;margin:18px 0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
img{{width:100%;border-radius:10px;border:1px solid #334155;background:#000;display:block}}
code{{color:#fde68a}} h3{{margin:0 0 8px;color:#5eead4;font-size:.95rem}}
</style></head><body>
<header>
<h1>V301 — ver agora: parede extrema direita + cotas</h1>
<p class="mut">Compare lado a lado N2 × N4. Se a vertical de cota ainda invadir o marco ou colar na parede, marque o print.</p>
</header>
<main>
{''.join(cards)}
<div class="card"><h2>Vista completa</h2>
<div class="grid">
<div><h3>N4 VIEW_A</h3><img src="N4_VIEW_A.png"/></div>
<div><h3>N4 VIEW_B</h3><img src="N4_VIEW_B.png"/></div>
</div>
<p class="mut" style="margin-top:12px">N2 recorte:</p>
<img src="N2_recorte.png"/>
</div>
</main></body></html>
""",
        encoding="utf-8",
    )
    print("HTML", html)
    webbrowser.open(html.resolve().as_uri())
    # PNG zooms direto
    for lab, _, _, _, _, _ in jobs:
        for suf in ("N2", "N4"):
            p = OUT / f"{lab}_ZOOM_RIGHT_{suf}.png"
            if p.exists():
                os.startfile(str(p))
    for p in (n4a, n4b):
        if p.exists():
            os.startfile(str(p))
    print("opened")


if __name__ == "__main__":
    main()
