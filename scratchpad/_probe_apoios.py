from pathlib import Path
import re

t = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
).read_text(encoding="utf-8")
print("--- apoios ---")
for m in re.finditer(r"apoios\s+([^·<]{0,40})", t):
    print(repr(m.group(0)))
print("--- table cells around Ponto ---")
# compact summary tds
for m in re.finditer(
    r'id="fv-seg-item-(\d+)"[\s\S]{0,800}?</tr>', t
):
    lab = m.group(1)
    tds = re.findall(r"<td[^>]*>(.*?)</td>", m.group(0))
    plain = [re.sub(r"<[^>]+>", "", x).strip() for x in tds]
    print(lab, plain)
