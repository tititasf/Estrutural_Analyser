import json
import sqlite3
from collections import Counter

con = sqlite3.connect(r"D:\Agente-cad-PYSIDE\project_data.vision")
pid = "dd238e47-1dc6-4f63-a760-4e7ce19a7386"
rows = con.execute(
    "SELECT name, data_json FROM beams WHERE project_id=? ORDER BY name",
    (pid,),
).fetchall()
print("beams", len(rows))
for name, raw in rows:
    data = json.loads(raw or "{}")
    fields = data.get("fields") or {}
    fundo_dims = {
        k: v for k, v in fields.items()
        if k.startswith("viga_fundo_seg_") and k.endswith("_dim")
    }
    niveis = {
        k: v for k, v in fields.items()
        if "nivel_viga" in k and v not in (None, "", 0, "0")
    }
    uniq_n = sorted({str(v) for v in niveis.values()})
    uniq_d = sorted({str(v) for v in fundo_dims.values()})
    h1 = fields.get("altura_h1")
    dim = fields.get("dimensao")
    print(
        f"{name:7} fundo_dims={uniq_d or '-'}  "
        f"n_seg={len(fundo_dims)}  altura_h1={h1}  dimensao={dim}  "
        f"nivel_lv={uniq_n or '-'}"
    )
