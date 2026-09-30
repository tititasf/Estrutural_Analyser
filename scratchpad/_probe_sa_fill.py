from pathlib import Path
import re

t = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
).read_text(encoding="utf-8")
i = t.find("fv-layer fv-layer-sa")
chunk = t[i : t.find("fv-layer fv-layer-c1", i)]
for pat in ["e53935", "b71c1c", "ff1744"]:
    m = re.search(r"<[^>]{0,300}" + pat + r"[^>]{0,200}>", chunk)
    print("---", pat, "---")
    print(m.group(0)[:400] if m else "none")
    print()
