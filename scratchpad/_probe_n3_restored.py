from pathlib import Path

html = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
).read_text(encoding="utf-8")
start = html.find('class="fv-layer fv-layer-n3')
gt = html.find(">", start)
svg = html[html.find("<svg", gt) : html.find("</svg>", gt) + 6]
print("composed", "data-n3-composed" in svg)
print("matplotlib", "Matplotlib" in svg)
print("cyan", "#00ffff" in svg or "#00e5ff" in svg or "00ffff" in svg)
print("yellow", "ffbf00" in svg or "ffd54f" in svg)
print("tags", svg.count('class="fv-n3-tag"'), "S1", ">S1<" in svg, "S16", ">S16<" in svg)
print("paths", svg.count("<path"))
print("fv-n3-panel", "fv-n3-panel" in svg)
print("viewBox", svg[svg.find("viewBox") : svg.find("viewBox") + 70])

disk = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/n3/V301_n3.svg"
)
d = disk.read_text(encoding="utf-8")
print("disk composed", "data-n3-composed" in d, "matplotlib", "Matplotlib" in d, "tags", "fv-n3-tag" in d)
