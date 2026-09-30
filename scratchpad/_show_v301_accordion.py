import re
from pathlib import Path
p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
    r"\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8")
print("items", t.count('class="fv-seg-item"'))
print("panels title", "Painéis N3" in t)
print("chanfro esq", "Esq. topo" in t)
m = re.search(r'id="fv-seg-item-1"(.*?)</details>', t, re.S)
chunk = m.group(1) if m else ""
print("seg1 summary", re.sub(r"<[^>]+>", " ", chunk[:500]))
print("244" in chunk, "61.5" in chunk or "61,5" in chunk)
# first panel table rows
rows = re.findall(r"<tr><td>(\d+)</td><td>([^<]+)</td><td>([^<]+)</td></tr>", chunk)
print("panels", rows)
