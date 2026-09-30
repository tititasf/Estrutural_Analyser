from pathlib import Path
import re
from collections import Counter

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas\Obra_TREINO_1"
    r"\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8", errors="replace")
i = t.find("fv-layer fv-layer-sa")
k = t.find('class="fv-layer fv-layer-c1', i)
chunk = t[i:k]

styles = re.findall(r'style="[^"]+"', chunk)
hl = [s for s in styles if any(c in s for c in (
    "e53935", "ec407a", "ff1744", "f8bbd0", "b71c1c", "ad1457", "ff8a80", "f48fb1"
))]
print("hl styles", len(hl))
print(Counter(hl).most_common(30))

print("\n--- opacity 0.38 ---")
print(chunk.count("opacity: 0.38"))
print("\n--- stroke-width near highlight ---")
sw = re.findall(r'stroke: #(?:ff1744|f8bbd0); stroke-width: [^;"]+', chunk)
print(Counter(sw).most_common(20))
