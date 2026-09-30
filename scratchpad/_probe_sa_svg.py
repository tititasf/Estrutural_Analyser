from pathlib import Path

t = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
).read_text(encoding="utf-8")
for s in [
    "e53935", "ec407a", "229, 57", "fill-opacity", "b71c1c",
    "ff1744", "f8bbd0", "fv-layer-sa",
]:
    print(s, t.count(s))
i = t.find("fv-layer fv-layer-sa")
print("idx", i)
print(t[i : i + 600])
# first svg after that
j = t.find("<svg", i)
print("svg", t[j : j + 400])
