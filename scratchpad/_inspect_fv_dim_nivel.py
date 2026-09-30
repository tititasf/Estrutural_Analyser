from pathlib import Path
import re
from html import unescape
from collections import Counter

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
    r"\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8")
# first local section
m = re.search(r'N1 / SA — V301 · segmento 1</div>', t)
chunk = t[m.end(): m.end()+25000] if m else t[:25000]
chunk_u = unescape(chunk)

keys = [
    "altura_total",
    "viga_fundo_seg_1_dim",
    "dimensao",
    "nivel",
    "laje_nivel",
    "nivel_viga",
    "visao_corte",
    "corte",
    "largura_total_fundo",
]
for k in keys:
    i = chunk_u.lower().find(k.lower())
    if i >= 0:
        print("---", k, "---")
        print(chunk_u[i:i+220].replace("\n", " ")[:220])
        print()

# count dim values in whole file (unique)
dims = re.findall(r'viga_fundo_seg_\d+_dim(?:</td><td[^>]*>|&quot;:\s*&quot;)([^<&"]+)', t)
print("dims sample", Counter(dims).most_common(10))
print("altura_total occurrences", t.count("altura_total"))
# unique altura_total values
alts = re.findall(r'&quot;altura_total&quot;:\s*([\d.]+)', t)
print("altura_total values", Counter(alts).most_common(10))
