# -*- coding: utf-8 -*-
"""Dump COMPACTO da ficha live V301 — so o essencial por face_unit."""
import sys
from pathlib import Path

ARETE = Path(__file__).resolve().parent
SCRIPTS = ARETE.parent
sys.path.insert(0, str(ARETE))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

from gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402

entry = _entry_from_live_recorte("V301")
fus = entry.get("face_units") or []
print(f"total face_units={len(fus)}  h_B={entry.get('h_B_cm')} laje_sup_B={entry.get('laje_sup_B_cm')}")
for i, fu in enumerate(fus):
    side = fu.get("side")
    if side != "B":
        continue
    lab = (fu.get("label") or "").strip() or "(sem)"
    segs = fu.get("segments") or fu.get("panels") or []
    ws = [round(float(s.get("largura_cm", s.get("width", 0)) or 0), 1) for s in segs]
    h1 = [round(float(s.get("height1", 0) or 0), 1) for s in segs]
    print(f"\nFU[{i}] B label={lab} h_body={fu.get('h_body')} widths={ws}")
    print(f"   h1={h1}")
    print(f"   laje_sup={fu.get('laje_sup')} marco={fu.get('marco_laje_sup')}"
          f" sup_local={[s.get('laje_sup_local') for s in segs]}")
    print(f"   sarr_v_e={fu.get('sarrafo_vertical_esquerdo')} sarr_v_d={fu.get('sarrafo_vertical_direito')}")
