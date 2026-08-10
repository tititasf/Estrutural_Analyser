# -*- coding: utf-8 -*-
"""HTML ANIMAL V301 — N4 full + N2 + clips de visão."""
from __future__ import annotations

import html as H
import shutil
import sys
import webbrowser
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from arete.vision_anti_hallucination import render_dxf_png  # noqa: E402

N4 = Path(r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n4")
N2 = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem"
    r"\recortes_reversos\ALIMONTI - PARAISO - 13° PAV.- LV - R00"
    r"\LV_V301_motor_178111332829.dxf"
)
OUT = Path(__file__).resolve().parent / "relatorios" / "g2v" / "v301_geometry_gate" / "html_animal"
VIS = Path(__file__).resolve().parent / "relatorios" / "g2v" / "v301_geometry_gate" / "vision"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    jobs = [
        (N4 / "LV_preview_V301_VIEW_A.dxf", "N4_VIEW_A.png", "N4 VIEW_A"),
        (N4 / "LV_preview_V301_VIEW_B.dxf", "N4_VIEW_B.png", "N4 VIEW_B"),
        (N4 / "LV_preview_V301_A.dxf", "N4_PACK_A.png", "N4 pack A completo"),
        (N4 / "LV_preview_V301_CORTE.dxf", "N4_CORTE.png", "N4 CORTE"),
        (N2, "N2_recorte.png", "N2 recorte original"),
    ]
    for path, name, title in jobs:
        if not path.exists():
            print("missing", path)
            continue
        dest = OUT / name
        ok = render_dxf_png(
            path, dest, clip=None, title=title, width_px=1800, height_px=780, dpi=160
        )
        print(title, "OK" if ok else "FAIL")

    for lab in ("V301.A", "V301.B"):
        for suf in ("N2", "N4", "EXTRA_MAP"):
            src = VIS / f"{lab}_{suf}.png"
            if src.exists():
                shutil.copy2(src, OUT / f"{lab}_{suf}.png")
                print("copied", src.name)

    cards = [
        ("N4_VIEW_A.png", "N4 VIEW_A — multi-segmento face A"),
        ("N4_VIEW_B.png", "N4 VIEW_B — multi-segmento face B"),
        ("N4_PACK_A.png", "N4 pack A completo"),
        ("N4_CORTE.png", "N4 CORTE"),
        ("N2_recorte.png", "N2 recorte original (gabarito)"),
        ("V301.A_N2.png", "V301.A · clip N2"),
        ("V301.A_N4.png", "V301.A · clip N4"),
        ("V301.A_EXTRA_MAP.png", "V301.A · mapa visão (verde=match · vermelho=EXTRA · amarelo=MISS)"),
        ("V301.B_N2.png", "V301.B · clip N2"),
        ("V301.B_N4.png", "V301.B · clip N4"),
        ("V301.B_EXTRA_MAP.png", "V301.B · mapa visão"),
    ]

    parts = [
        """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"/>
<title>V301 N4 HTML ANIMAL</title>
<style>
body{margin:0;font-family:system-ui,sans-serif;background:#070b14;color:#e5e7eb}
header{padding:20px 26px;background:linear-gradient(105deg,#0f172a 0%,#134e4a 55%,#0f172a 100%);
border-bottom:1px solid #1f2937}
h1{margin:0 0 8px;font-size:1.55rem}
.mut{color:#94a3b8;font-size:.92rem}
main{padding:18px 24px 72px;max-width:1760px;margin:0 auto}
.card{background:#0f172a;border:1px solid #1f2937;border-radius:16px;padding:16px;margin:18px 0;
box-shadow:0 12px 48px #0007}
.card h2{margin:0 0 12px;font-size:1.08rem;color:#5eead4}
img{width:100%;border-radius:12px;border:1px solid #334155;background:#0a0a12;display:block}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:1100px){.grid{grid-template-columns:1fr}}
.badge{display:inline-block;background:#064e3b;color:#6ee7b7;padding:4px 12px;border-radius:999px;
font-size:.78rem;font-weight:800;margin-right:6px}
code{color:#fde68a}
.hero{font-size:2rem;font-weight:900;letter-spacing:.04em}
.hero span{color:#34d399}
</style></head><body>
<header>
<div class="hero">V301 · N4 HTML <span>ANIMAL</span></div>
<p class="mut">Render DXF real full-layers · VIEW_A / VIEW_B / pack / CORTE · N2 · clips de face · mapa visão</p>
<p><span class="badge">GEO+VISÃO</span><span class="badge">full layers</span></p>
</header><main>
"""
    ]

    # hero pair
    parts.append('<div class="card"><h2>VIEW_A × VIEW_B (full)</h2><div class="grid">')
    for name, title in (
        ("N4_VIEW_A.png", "N4 VIEW_A"),
        ("N4_VIEW_B.png", "N4 VIEW_B"),
    ):
        if (OUT / name).exists():
            parts.append(
                f'<div><div class="mut">{H.escape(title)}</div>'
                f'<img src="{H.escape(name)}" alt="{H.escape(title)}"/></div>'
            )
    parts.append("</div></div>")

    for name, title in cards:
        if name in ("N4_VIEW_A.png", "N4_VIEW_B.png"):
            continue
        if not (OUT / name).exists():
            continue
        parts.append(
            f'<div class="card"><h2>{H.escape(title)}</h2>'
            f'<img src="{H.escape(name)}" alt="{H.escape(title)}"/>'
            f'<p class="mut"><code>{H.escape(name)}</code></p></div>'
        )

    parts.append(
        """
<div class="card"><h2>Paths DXF</h2>
<ul class="mut">
<li><code>DADOS-OBRAS/.../n4/LV_preview_V301_VIEW_A.dxf</code></li>
<li><code>DADOS-OBRAS/.../n4/LV_preview_V301_VIEW_B.dxf</code></li>
<li><code>DADOS-OBRAS/.../n4/LV_preview_V301_A.dxf</code></li>
<li><code>DADOS-OBRAS/.../n4/LV_preview_V301_CORTE.dxf</code></li>
</ul></div>
</main></body></html>
"""
    )

    html_path = OUT / "V301_N4_HTML_ANIMAL.html"
    html_path.write_text("".join(parts), encoding="utf-8")
    webbrowser.open(html_path.resolve().as_uri())
    print("HTML", html_path.resolve())


if __name__ == "__main__":
    main()
