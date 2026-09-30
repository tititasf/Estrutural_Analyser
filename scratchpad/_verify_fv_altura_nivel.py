from pathlib import Path
from html.parser import HTMLParser
import re

pack = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
    r"\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga"
)

def table_rows(name):
    t = (pack / name).read_text(encoding="utf-8")
    m = re.search(r'<table class="fv-seg-table">(.*?)</table>', t, re.S)
    body = m.group(1) if m else ""
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if cells:
            rows.append(cells)
    return rows

for name in ("V301.html", "V304.html", "V310.html", "V322.html", "V327.html"):
    rows = table_rows(name)
    print("====", name, "====")
    for r in rows[:6]:
        print(" ", r)
    if len(rows) > 6:
        print("  ...", len(rows)-1, "data rows")
    # header check
    print("  header", rows[0] if rows else None)
