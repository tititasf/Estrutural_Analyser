#!/usr/bin/env python3
"""
patch_zone_boundaries.py -- Preenche zone boundaries (x_left, x_right, y_bot) nulos
usando dados de face_a como referencia.

Logica:
  x_left null  -> face_a.face_x_min  (fallback: x_right - total_width - 50)
  x_right null -> face_a.face_x_max  (fallback: x_left + total_width + 50)
  y_bot null   -> face_a.y_min - 50

Uso:
  python patch_zone_boundaries.py
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

PARAMS_FILE = Path(r'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json')


def main():
    params = json.loads(PARAMS_FILE.read_text(encoding='utf-8'))

    fixed_xl = 0
    fixed_xr = 0
    fixed_yb = 0

    for v in params:
        zone = v.get('zone')
        if not zone:
            continue
        fa = v.get('face_a') or {}

        # --- x_left ---
        if zone.get('x_left') is None:
            fa_xmin = fa.get('face_x_min')
            if fa_xmin is not None:
                zone['x_left'] = fa_xmin
                fixed_xl += 1
            elif zone.get('x_right') is not None and fa.get('total_width'):
                zone['x_left'] = zone['x_right'] - fa['total_width'] - 50
                fixed_xl += 1

        # --- x_right ---
        if zone.get('x_right') is None:
            fa_xmax = fa.get('face_x_max')
            if fa_xmax is not None:
                zone['x_right'] = fa_xmax
                fixed_xr += 1
            elif zone.get('x_left') is not None and fa.get('total_width'):
                zone['x_right'] = zone['x_left'] + fa['total_width'] + 50
                fixed_xr += 1

        # --- y_bot ---
        if zone.get('y_bot') is None:
            fa_ymin = fa.get('y_min')
            if fa_ymin is not None:
                zone['y_bot'] = fa_ymin - 50
                fixed_yb += 1

    PARAMS_FILE.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding='utf-8')

    # Re-count remaining nulls
    xl_null = sum(1 for p in params if p.get('zone', {}).get('x_left') is None)
    xr_null = sum(1 for p in params if p.get('zone', {}).get('x_right') is None)
    yb_null = sum(1 for p in params if p.get('zone', {}).get('y_bot') is None)

    print(f"PATCH-A: patch_zone_boundaries")
    print(f"  x_left  corrigidos: {fixed_xl}")
    print(f"  x_right corrigidos: {fixed_xr}")
    print(f"  y_bot   corrigidos: {fixed_yb}")
    print(f"  Restantes nulos: x_left={xl_null}, x_right={xr_null}, y_bot={yb_null}")
    print(f"  Salvo: {PARAMS_FILE}")


if __name__ == '__main__':
    main()
