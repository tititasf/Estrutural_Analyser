from pathlib import Path
import re

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas\Obra_TREINO_1"
    r"\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
print("size", p.stat().st_size)
t = p.read_text(encoding="utf-8", errors="replace")
print("len", len(t))
needles = [
    "fv-layer-sa",
    "fv-sa-ghost",
    "e53935",
    "ec407a",
    "ff1744",
    "b71c1c",
    "fill:",
    "opacity: 0.38",
    "rgb(229",
    "#e5",
    'style="fill',
    "Destaque suave",
    "Reset zoom",
    "fill-opacity",
    "clip-path",
]
for s in needles:
    print(repr(s), t.count(s))

i = t.find("fv-layer fv-layer-sa")
print("idx layer", i)
if i >= 0:
    print("--- layer head ---")
    print(t[i : i + 1200])
    j = t.find("<svg", i)
    print("svg idx", j)
    print(t[j : j + 800] if j >= 0 else "NO SVG")
    # sample some path styles in SA layer until next layer
    k = t.find('class="fv-layer fv-layer-c1', i)
    chunk = t[i : k if k > i else i + 200000]
    print("sa chunk len", len(chunk))
    fills = re.findall(r'style="[^"]{0,180}"', chunk)
    print("style attrs", len(fills))
    for s in fills[:12]:
        print(" ", s[:180])
    # also look for fill= attributes
    fills2 = re.findall(r'\bfill="[^"]+"', chunk)
    print("fill attrs", len(fills2))
    for s in fills2[:12]:
        print(" ", s)
    # rgb
    rgbs = re.findall(r"rgb\([^)]+\)", chunk)
    print("rgbs", len(rgbs), "unique", len(set(rgbs)))
    from collections import Counter
    print(Counter(rgbs).most_common(15))
    hexes = re.findall(r"#[0-9a-fA-F]{3,8}", chunk)
    print("hexes", len(hexes), "unique", len(set(hexes)))
    print(Counter(hexes).most_common(20))
