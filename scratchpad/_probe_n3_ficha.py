from pathlib import Path

html = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
).read_text(encoding="utf-8")
start = html.find('class="fv-layer fv-layer-n3')
gt = html.find(">", start)
svg = html[html.find("<svg", gt) : html.find("</svg>", gt) + 6]
print("tags", svg.count('class="fv-n3-tag"'))
print("S1", ">S1<" in svg, "S16", ">S16<" in svg)
print("composed", "data-n3-composed" in svg)
print("244", "244" in svg)
print("305", "305" in svg)
print("61.5", "61.5" in svg, "61,5", "61,5" in svg)
print("100", svg.count("100"))
print("paths", svg.count("<path"))
print("viewBox", svg[svg.find("viewBox") : svg.find("viewBox") + 80])
