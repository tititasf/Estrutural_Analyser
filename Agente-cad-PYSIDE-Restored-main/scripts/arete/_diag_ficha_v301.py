# -*- coding: utf-8 -*-
"""Dump da ficha live V301 (recorte N2 -> entry N4) — inspeciona face_units."""
import json
import sys
from pathlib import Path

ARETE = Path(__file__).resolve().parent
SCRIPTS = ARETE.parent
sys.path.insert(0, str(ARETE))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

from gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402

entry = _entry_from_live_recorte("V301")
if not entry:
    print("ENTRY NONE")
    sys.exit(1)

print("h_cm=", entry.get("h_cm"), "h_B_cm=", entry.get("h_B_cm"),
      "laje_sup_B=", entry.get("laje_sup_B_cm"), "laje_inf_B=", entry.get("laje_inf_B_cm"))
fus = entry.get("face_units") or []
print("face_units:", len(fus))
for i, fu in enumerate(fus):
    side = fu.get("side")
    lab = fu.get("label")
    bb = fu.get("bbox") or {}
    print(f"\n--- FU[{i}] side={side} label={lab} h_body={fu.get('h_body')} h_total={fu.get('h_total')}")
    print(f"    bbox=({bb.get('x_left')},{bb.get('y_bot')})->({bb.get('x_right')},{bb.get('y_top')})")
    print(f"    laje_sup={fu.get('laje_sup')} laje_inf={fu.get('laje_inf')} marco_laje_sup={fu.get('marco_laje_sup')}")
    print(f"    grade_layer_style={fu.get('grade_layer_style')} sarrafo_v_e={fu.get('sarrafo_vertical_esquerdo')} sarrafo_v_d={fu.get('sarrafo_vertical_direito')}")
    segs = fu.get("segments") or fu.get("panels") or []
    for j, s in enumerate(segs):
        print(f"    seg[{j}] w={s.get('largura_cm', s.get('width'))} h1={s.get('height1')} h2={s.get('height2')}"
              f" gh1={s.get('grade_h1')} gh2={s.get('grade_h2')} laje_c={s.get('laje_central_alt')}"
              f" sup_local={s.get('laje_sup_local', s.get('slab_top'))} inf_local={s.get('laje_inf_local', s.get('slab_bottom'))}"
              f" reuse={s.get('reuse')} type={s.get('panel_type')}")
    sh = fu.get("sarrafos_horizontais") or []
    print(f"    sarrafos_horizontais: {len(sh)}")
    for k, sp in enumerate(sh):
        print(f"      [{k}] {json.dumps(sp, ensure_ascii=False)[:200]}")
    sv = fu.get("sarrafos_verticais") or []
    print(f"    sarrafos_verticais: {len(sv)}")
    for k, sp in enumerate(sv):
        print(f"      [{k}] {json.dumps(sp, ensure_ascii=False)[:200]}")
