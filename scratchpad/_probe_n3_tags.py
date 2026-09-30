from pathlib import Path

t = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
).read_text(encoding="utf-8")
print("composed", 'data-n3-composed="1"' in t)
print("seg count", 'data-n3-seg-count="16"' in t)
print("groups", t.count('class="fv-n3-seg"'))
print("S1", ">S1<" in t, "S16", ">S16<" in t)
print("244x19", "244×19" in t)
