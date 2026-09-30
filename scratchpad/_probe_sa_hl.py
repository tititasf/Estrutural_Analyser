from pathlib import Path
import re

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas\Obra_TREINO_1"
    r"\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8", errors="replace")
i = t.find("fv-layer fv-layer-sa")
k = t.find('class="fv-layer fv-layer-c1', i)
chunk = t[i : k if k > i else i + 800000]

# every style that mentions highlight colors
for color in ["e53935", "ec407a", "ff1744", "f8bbd0", "b71c1c", "ad1457"]:
    print("====", color, "====")
    n = 0
    for m in re.finditer(r"<[^>]{0,80}" + color + r"[^>]{0,220}>", chunk):
        n += 1
        if n <= 3:
            print(m.group(0)[:350])
            print()
    print("count tags", n)

print("==== nearby parent ids for first e53935 ====")
idx = chunk.find("e53935")
print(chunk[max(0, idx - 400) : idx + 250])
