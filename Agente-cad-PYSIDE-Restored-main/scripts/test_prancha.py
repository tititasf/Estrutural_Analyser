#!/usr/bin/env python3
"""Test prancha detection on TREINO_18 LV and TREINO_3 FV."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
import json
import validar_visual_dxf as v

disc = json.loads(Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS/dxf_discovery.json').read_text(encoding='utf-8'))

tests = [
    ('Obra_TREINO_18', '1PV', 'LV', 'test_t18_lv_strip.png'),
    ('Obra_TREINO_3', 'TORRE A - TIPO 2 AO 13PAV', 'FV', 'test_t3_fv_strip.png'),
]

for obra, pav, tipo, out_name in tests:
    stog_path_str = disc.get(obra, {}).get(pav, {}).get(tipo)
    if not stog_path_str:
        print(f'{obra}/{pav}/{tipo}: NOT IN DISCOVERY')
        continue
    stog_path = Path(stog_path_str)
    print(f'\nTesting {obra}/{tipo}: {stog_path.name}')
    frames = v.detectar_prancha(stog_path)
    if frames:
        print(f'  Detected {len(frames)} frames')
        f0 = frames[0]
        print(f'  Frame[0]: ({f0["x0"]:.0f},{f0["y0"]:.0f}) inner: ({f0["inner_x0"]:.0f},{f0["inner_y0"]:.0f}) to ({f0["inner_x1"]:.0f},{f0["inner_y1"]:.0f})')
        print(f'  Rendering strip...')
        png = v.render_dxf_prancha_strip(stog_path, frames, dpi=72)
        out = Path(f'D:/Agente-cad-PYSIDE/validacao_visual/{out_name}')
        out.write_bytes(png)
        print(f'  Saved: {out} ({len(png)//1024}KB)')
    else:
        print(f'  No prancha detected')

print('\nDone.')
sys.stdout.flush()
