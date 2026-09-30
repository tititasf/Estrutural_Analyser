import json
import sqlite3
import sys
from pathlib import Path

repo = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main")
sys.path.insert(0, str(repo))
from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter
from src.ui.widgets.preficha_fundo_html import relayout_existing_fv_page

beam_id = "dd238e47-1dc6-4f63-a760-4e7ce19a7386_b_1"
db = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
con = sqlite3.connect(str(db))
row = con.execute("SELECT data_json FROM beams WHERE id=?", (beam_id,)).fetchone()
beam = json.loads(row[0])
before = {
    k: beam.get("fields", {}).get(k)
    for k in sorted(beam.get("fields", {}))
    if k.startswith("viga_fundo_seg_") and k.endswith("_dim")
}
n = FundoVigaInterpreter.assign_segment_dimensions_from_texts(beam)
print("assigned", n)
after = {
    k: beam.get("fields", {}).get(k)
    for k in sorted(beam.get("fields", {}))
    if k.startswith("viga_fundo_seg_") and k.endswith("_dim")
}
for i in range(1, 17):
    k = f"viga_fundo_seg_{i}_dim"
    print(f"  {i:2} {before.get(k)!s:8} -> {after.get(k)}")

con.execute(
    "UPDATE beams SET data_json=? WHERE id=?",
    (json.dumps(beam, ensure_ascii=False), beam_id),
)
con.commit()
con.close()
print("db updated")

page = (
    repo
    / "scripts/arete/html_fichas/Obra_TREINO_1"
    / "TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    / "fundos_viga"
    / "V301.html"
)
raw = page.read_text(encoding="utf-8")
updated = relayout_existing_fv_page(raw, n3_dir=str(page.parent / "n3"))
page.write_text(updated, encoding="utf-8")
print("html updated", page.name)
