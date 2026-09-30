from pathlib import Path
import re

t = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
).read_text(encoding="utf-8")
i = t.find("fv-layer fv-layer-sa")
j = t.find("fv-layer fv-layer-c1", i)
chunk = t[i:j]
print("b71c1c count", chunk.count("b71c1c"))
# 5 occurrences around first b71c1c
k = chunk.find("b71c1c")
print(chunk[max(0, k - 250) : k + 200])
print("--- next ---")
k2 = chunk.find("b71c1c", k + 1)
print(chunk[max(0, k2 - 200) : k2 + 180])
# arrows
print("marker", chunk.count("marker"), "fancyarrow", chunk.count("fancy"))
print("stroke-width: 0.5", chunk.count("stroke-width: 0.5"))
print("stroke-width: 0.7", chunk.count("stroke-width: 0.7"))
print("stroke-width: 0.65", chunk.count("stroke-width: 0.65"))
