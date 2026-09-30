from pathlib import Path
import re

html = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
).read_text(encoding="utf-8")
i = html.find("fv-layer fv-layer-n3")
chunk = html[i : i + 2500]
print(chunk[:600])
print("---clip-path in n3 layer first 50k?---")
n3_start = html.find("<div class=\"fv-layer fv-layer-n3")
print("clip-path count after n3", html[n3_start:n3_start+200000].count("clip-path"))
vb = re.search(r'fv-layer-n3[^>]*>[\s\S]{0,400}viewBox="([^"]+)"', html)
print("html viewBox", vb.group(1) if vb else None)

disk = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/n3/V301_n3.svg"
)
raw = disk.read_text(encoding="utf-8")
print("disk viewBox", re.search(r'viewBox="([^"]+)"', raw).group(1))
print("disk clip-path", raw.count("clip-path"))
print("disk size", disk.stat().st_size)
