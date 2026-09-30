import json
import sqlite3
from pathlib import Path

con = sqlite3.connect(r"D:\Agente-cad-PYSIDE\project_data.vision")
con.row_factory = sqlite3.Row

print("=== projects 13 PAV / TREINO ===")
for r in con.execute(
    "SELECT id, name, work_name, pavement_name, level_arrival, level_exit FROM projects"
):
    blob = " ".join(str(x or "") for x in r)
    if "TREINO" in blob.upper() or "13" in blob:
        print(dict(r))

print("\n=== V301 beams ===")
rows = con.execute(
    "SELECT id, project_id, name, substr(data_json,1,80) FROM beams WHERE name LIKE 'V301%'"
).fetchall()
print("count", len(rows))
for r in rows[:8]:
    print(dict(r))

# pick first V301 with data
row = con.execute(
    "SELECT id, project_id, name, data_json FROM beams WHERE name='V301' ORDER BY rowid DESC LIMIT 1"
).fetchone()
if not row:
    print("no V301")
else:
    data = json.loads(row["data_json"] or "{}")
    fields = data.get("fields") or {}
    print("\nV301 id", row["id"], "project", row["project_id"])
    print("field keys sample:")
    keys = sorted(fields.keys())
    for k in keys:
        if any(x in k.lower() for x in ("nivel", "dim", "altura", "laje", "corte", "h1")):
            print(f"  {k} = {fields[k]!r}"[:160])
    print("total fields", len(keys))
    # project levels
    proj = con.execute(
        "SELECT name, work_name, pavement_name, level_arrival, level_exit FROM projects WHERE id=?",
        (row["project_id"],),
    ).fetchone()
    print("project", dict(proj) if proj else None)

    # nearby slabs nivel
    slabs = con.execute(
        "SELECT name, extra_data_json FROM slabs WHERE project_id=? LIMIT 5",
        (row["project_id"],),
    ).fetchall()
    print("\nslabs sample", len(slabs))
    for s in slabs[:3]:
        extra = s["extra_data_json"]
        print(" slab", s["name"], (extra or "")[:120])
    # try links_json on slab
    s2 = con.execute(
        "SELECT name, links_json FROM slabs WHERE project_id=? AND name LIKE 'L3%' LIMIT 3",
        (row["project_id"],),
    ).fetchall()
    for s in s2:
        lj = json.loads(s["links_json"] or "{}") if s["links_json"] else {}
        # if extra_data style - actually nivel is often in a different store
        print(" slab", s["name"], "link keys", list(lj)[:12] if isinstance(lj, dict) else type(lj))
