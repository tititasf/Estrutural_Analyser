from pathlib import Path

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas\Obra_TREINO_1"
    r"\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8", errors="replace")
i = t.find("fv-layer fv-layer-sa")
k = t.find('class="fv-layer fv-layer-c1', i)
chunk = t[i:k]
print("sa face", chunk.count('data-fv-hl="face"'))
print("sa edge", chunk.count('data-fv-hl="edge"'))
print("sa tag", chunk.count('data-fv-hl="tag"'))
print("page face", t.count('data-fv-hl="face"'))
print("apply fn", "_applySaGhostVisual" in t)
print("ghost btn", t.count("fv-sa-ghost-btn"))
print("css face", "[data-fv-hl='face']" in t)
