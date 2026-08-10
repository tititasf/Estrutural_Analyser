import re
from pathlib import Path

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete"
    r"\html_fichas\Obra_TREINO_1\13_PAV_20260730_210556_pilares_abcd\pilares\P2.html"
)
t = p.read_text(encoding="utf-8")
idx = t.find('class="pil-layer pil-layer-sa"')
print("layer idx", idx)
chunk = t[idx : idx + 5000000]
# find first real svg after layer
m = re.search(r"(<svg[^>]*viewBox=\"[^\"]+\"[^>]*>)", chunk)
print("open tag", m.group(1)[:200] if m else None)
if m:
    start = m.start()
    end = chunk.find("</svg>", start)
    svg = chunk[start : end + 6]
    print("svg len", len(svg))
    print("viewBox", re.search(r'viewBox="([^"]+)"', svg).group(1))
    trs = re.findall(r'transform="([^"]+)"', svg)
    print("n transforms", len(trs))
    print("unique", list(dict.fromkeys(trs))[:15])
    print(svg[0:800])
    # red polygon of pillar?
    print("ff1744", "ff1744" in svg or "#ff1744" in svg)
    reds = re.findall(r"#[fF]{2}1744|ff1744", svg)
    print("red hits", len(reds))
