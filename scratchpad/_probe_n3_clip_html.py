from pathlib import Path
import re
from src.ui.widgets.fv_hifi_n1_render import _svg_has_broken_clip, sanitize_inline_svg

html = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
).read_text(encoding="utf-8")
start = html.find('<div class="fv-layer fv-layer-n3')
gt = html.find(">", start)
svg_i = html.find("<svg", gt)
svg_end = html.find("</svg>", svg_i)
inner = html[svg_i : svg_end + 6]
print("inner len", len(inner))
print("clip-path", inner.count("clip-path"))
print("clipPath", inner.count("clipPath"))
cps = re.findall(r"<clipPath[\s\S]{0,300}</clipPath>", inner)
print("n clipPath blocks", len(cps))
for c in cps[:3]:
    print("CP", c[:250])
print("broken?", _svg_has_broken_clip(inner))
out = sanitize_inline_svg(inner)
print("after sanitize clip-path", out.count("clip-path"))
