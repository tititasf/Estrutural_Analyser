import re
from pathlib import Path
p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
    r"\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8")
m = re.search(r'<table class="fv-seg-table">(.*?)</table>', t, re.S)
body = m.group(1)
for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
    cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
    print(cells[:5])
