import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_lv_dxf_stog as lv

def panel(w, h):
    return {"width": w, "height1": h, "height2": 0.0,
            "grade_h1": 0.0, "grade_h2": 0.0, "panel_type": "Sarrafeado"}

def verts(msp, layer="Painéis"):
    out = []
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        if str(e.dxf.layer or "") != layer:
            continue
        a, b = e.dxf.start, e.dxf.end
        if abs(a.x - b.x) > 0.3:
            continue
        out.append((round(a.x, 1), round(min(a.y, b.y), 1), round(max(a.y, b.y), 1)))
    return sorted(out)

def run(name, pans, h, **kw):
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(msp, 0.0, 0.0, pans, h, name, **kw)
    print("====", name)
    print("Painéis V", verts(msp, "Painéis"))
    print("COTA V", verts(msp, "COTA")[:20], "...")

run("CONT. V301.B",
    [panel(244, 40), panel(63, 40), panel(111, 104)],
    104.0, laje_sup=14, marco_laje_sup=True,
    painel_sup_alt=7, painel_sup_width=418)
run("UNIT.B#10",
    [panel(21.2, 103), panel(19, 103), panel(117.5, 103),
     panel(21.8, 38), panel(34.7, 38), panel(244, 38)],
    103.0, laje_sup=14, marco_laje_sup=True,
    painel_sup_alt=7, painel_sup_width=418, painel_sup_x_offset=43.2)
run("V301.B",
    [panel(244, 38), panel(22.5, 38), panel(52.5, 102)],
    102.0, laje_sup=15, marco_laje_sup=True,
    painel_sup_alt=7, painel_sup_width=319)
