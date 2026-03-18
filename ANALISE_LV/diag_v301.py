#!/usr/bin/env python3
"""Inspeciona V301 para entender por que sarr22_line ainda contamina o bbox."""
import json, sys
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R
from combinar_vigas_dxf import compute_content_bbox

with open('D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json', encoding='utf-8') as f:
    params = json.load(f)

# Encontrar V301 de Obra_TREINO_1
p = next((x for x in params if x.get('viga') == 'V301' and 'TREINO_1' in x.get('obra','')), None)
if not p:
    print("V301 not found"); sys.exit(1)

fa = p.get('face_a') or {}
print(f"face_a.face_x_min={fa.get('face_x_min')}")
print(f"face_a.face_x_max={fa.get('face_x_max')}")
print(f"face_a.y_min={fa.get('y_min')}")
print(f"face_a.y_max={fa.get('y_max')}")

# Verificar sarr22_lines
sarr22 = p.get('sarr22_lines') or []
print(f"\nsarr22_lines count: {len(sarr22)}")
for sl in sarr22[:10]:
    cx = (sl['x1'] + sl['x2']) / 2
    cy = (sl['y1'] + sl['y2']) / 2
    in_x = R._x_in_face_range(cx, fa)
    in_y = R._y_in_face_range(cy, fa)
    fx_min = fa.get('face_x_min', 0)
    fx_max = fa.get('face_x_max', 0)
    margin = (fx_max - fx_min) * 0.3
    print(f"  x=[{sl['x1']:.0f},{sl['x2']:.0f}] cx={cx:.0f} face_x=[{fx_min},{fx_max}] margin={margin:.0f} in_x={in_x} in_y={in_y}")

# Bbox resultante
bbox = compute_content_bbox(p)
print(f"\nbbox: {bbox}")
