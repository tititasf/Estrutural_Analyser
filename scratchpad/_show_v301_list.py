from pathlib import Path
import re

p = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
)
t = p.read_text(encoding="utf-8")
print("fv-seg-table", "class=\"fv-seg-table\"" in t)
print("fv-seg-detail", "fv-seg-detail" in t)
print("fv-seg-item tr", '<tr class="fv-seg-item"' in t)
print("chips leftover", "305.5 × 19" in t)
print("details leftover", "<details class=\"fv-seg-item\"" in t)
m = re.search(r'<div class="fv-seg-table-wrap".*?</tbody>', t, re.S)
if m:
    print("---TABLE HEAD + FIRST ROWS---")
    print(m.group(0)[:2200])
