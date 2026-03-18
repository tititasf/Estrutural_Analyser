#!/usr/bin/env python3
"""
extract_treino11.py -- Extrai parametros das vigas de Obra_TREINO_11 GWT-1PV.

Este DXF nao tem INSERTs com atributos (usa TEXTs na layer NOMENCLATURA),
entao zones sao fornecidas pelo catalog pre-computado.

Usa extract_viga_v3() do extrator principal com zones do catalog.

Uso:
  python extract_treino11.py
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path

# Import extraction functions
sys.path.insert(0, r'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')
from extrair_parametros_viga_v3 import extract_viga_v3

CATALOG_PATH = Path(r'D:/Agente-cad-PYSIDE/ANALISE_LV/params/catalog_treino11_1pv.json')
DXF_DIR = Path(r'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_11/Fase-1_Ingestao/'
               r'Projetos_Finalizados_para_Engenharia_Reversa')
OUTPUT_PATH = Path(r'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_Obra_TREINO_11.json')


def main():
    catalog = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    print(f'Catalog entries: {len(catalog)}')

    # Group by dxf_source
    by_dxf = {}
    for entry in catalog:
        src = entry.get('dxf_source', '')
        if src not in by_dxf:
            by_dxf[src] = []
        by_dxf[src].append(entry)

    all_params = []
    ok = fail = 0
    fa_ok = fb_ok = sec_ok = sarr_ok = 0

    for dxf_name, entries in by_dxf.items():
        dxf_path = DXF_DIR / dxf_name
        if not dxf_path.exists():
            print(f'SKIP: {dxf_path}')
            fail += len(entries)
            continue

        doc = ezdxf.readfile(str(dxf_path))
        print(f'\n{dxf_name} ({len(entries)} vigas)')

        for entry in entries:
            viga_name = entry['viga']
            zone = entry.get('zone')

            if not zone:
                print(f'  {viga_name:25s} NO ZONE')
                fail += 1
                continue

            # Build zone dict expected by extract_viga_v3
            # The zone needs: y_top, y_bot, x_left, x_right, insert_x, insert_y, secao
            zone_full = {
                'y_top': zone.get('y_top', entry['insert_y'] + 80),
                'y_bot': zone.get('y_bot', entry['insert_y'] - 300),
                'x_left': zone.get('x_left'),
                'x_right': zone.get('x_right'),
                'insert_x': entry['insert_x'],
                'insert_y': entry['insert_y'],
                'secao': entry.get('secao', ''),
                'reaprov': '',
            }

            try:
                params = extract_viga_v3(doc, viga_name, zone_full)
            except Exception as ex:
                print(f'  {viga_name:25s} ERROR: {ex}')
                fail += 1
                continue

            params['obra'] = entry.get('obra', 'Obra_TREINO_11')
            params['dxf_source'] = dxf_name
            params['png'] = ''
            all_params.append(params)

            fa = params['face_a']
            fb = params['face_b']
            sec = params['section']
            sarr = params['sarrafos']

            if fa.get('panel_widths'):
                fa_ok += 1
            if fb.get('panel_widths'):
                fb_ok += 1
            if sec.get('concrete_hatch') or sec.get('section_dims'):
                sec_ok += 1
            if sarr.get('count', 0) > 0 or sarr.get('layers'):
                sarr_ok += 1

            pw_a = ','.join(str(int(w)) for w in (fa.get('panel_widths') or [])[:4])
            pw_b = ','.join(str(int(w)) for w in (fb.get('panel_widths') or [])[:4])
            print(f'  {viga_name:25s} FA[{fa.get("panel_count",0):2d}]={pw_a:20s} '
                  f'FB[{fb.get("panel_count",0):2d}]={pw_b:20s}')
            ok += 1

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_params, f, indent=2, ensure_ascii=False)

    n = len(all_params)
    print(f'\n{"="*60}')
    print(f'RESULTADO: {ok} OK / {fail} FAIL')
    print(f'Salvo: {OUTPUT_PATH}')
    if n > 0:
        print(f'\n=== COBERTURA ===')
        print(f'  Face A panels: {fa_ok:3d}/{n} ({fa_ok/n*100:.0f}%)')
        print(f'  Face B panels: {fb_ok:3d}/{n} ({fb_ok/n*100:.0f}%)')
        print(f'  Secao detail:  {sec_ok:3d}/{n} ({sec_ok/n*100:.0f}%)')
        print(f'  Sarrafos:      {sarr_ok:3d}/{n} ({sarr_ok/n*100:.0f}%)')


if __name__ == '__main__':
    main()
