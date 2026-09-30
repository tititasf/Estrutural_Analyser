import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arete.gerar_lv_n4_fichas import _entry_from_live_recorte
from lv_n4_face_unit_selection import select_n4_face_units
import gerar_lv_dxf_stog as lv

e = _entry_from_live_recorte("V301")
fus = select_n4_face_units(lv, e.get("face_units") or [], "V301")
for u in fus:
    lab = str(u.get("label") or "?")
    side = u.get("side")
    if str(side).upper() != "B":
        continue
    hs = u.get("sarrafos_horizontais") or []
    ys = sorted({round(float(s.get("y_offset", 0) or 0), 1) for s in hs})
    h = float(u.get("h_body") or 0)
    print(
        lab, "h", h, "laje", u.get("laje_sup"),
        "sup", u.get("painel_sup_alt"),
        "n_h", len(hs), "y_off", ys,
        "above_h", [y for y in ys if y > h + 1],
    )
