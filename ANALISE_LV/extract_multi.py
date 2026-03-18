#!/usr/bin/env python3
"""
extract_multi.py -- Extrai parametros de vigas a partir de catalogs gerados por catalog_multi.py.

Uso:
  python extract_multi.py --catalog params/catalog_TREINO_11_all.json --output params/viga_params_new_TREINO_11.json
  python extract_multi.py --catalog params/catalog_TREINO_5_all.json --output params/viga_params_new_TREINO_5.json
  python extract_multi.py --catalog params/catalog_TREINO_11_all.json params/catalog_TREINO_5_all.json --output params/viga_params_new_all.json
"""
import sys, io, json, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path
from collections import defaultdict

# Import extraction functions
sys.path.insert(0, r'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')
from extrair_parametros_viga_v3 import extract_viga_v3

OBRAS_BASE = Path(r'D:/Agente-cad-PYSIDE/DADOS-OBRAS')


def find_dxf(obra, dxf_name):
    """Locate DXF file in known subdirectories."""
    for sub in [
        'Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
        'Fase-1_Ingestao',
    ]:
        p = OBRAS_BASE / obra / sub / dxf_name
        if p.exists():
            return p
    return None


def extract_from_catalog(catalog_entries):
    """Extract viga parameters from catalog entries, grouped by DXF for efficiency."""
    # Group by (obra, dxf_source)
    by_dxf = defaultdict(list)
    for entry in catalog_entries:
        key = (entry.get('obra', ''), entry.get('dxf_source', ''))
        by_dxf[key].append(entry)

    all_params = []
    ok = fail = 0
    stats = {'fa_ok': 0, 'fb_ok': 0, 'sec_ok': 0, 'sarr_ok': 0}

    for (obra, dxf_name), entries in sorted(by_dxf.items()):
        dxf_path = find_dxf(obra, dxf_name)
        if not dxf_path:
            print(f'  [SKIP] DXF not found: {obra}/{dxf_name}')
            fail += len(entries)
            continue

        print(f'\n  {obra}/{dxf_name} ({len(entries)} vigas)')
        doc = ezdxf.readfile(str(dxf_path))

        for entry in entries:
            viga_name = entry['viga']
            zone = entry.get('zone')

            if not zone:
                print(f'    {viga_name:25s} NO ZONE')
                fail += 1
                continue

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
                print(f'    {viga_name:25s} ERROR: {ex}')
                fail += 1
                continue

            params['obra'] = obra
            params['dxf_source'] = dxf_name
            params['pavimento'] = entry.get('pavimento', '')
            params['png'] = ''
            all_params.append(params)

            fa = params.get('face_a', {})
            fb = params.get('face_b', {})
            sec = params.get('section', {})
            sarr = params.get('sarrafos', {})

            if fa.get('panel_widths'):
                stats['fa_ok'] += 1
            if fb.get('panel_widths'):
                stats['fb_ok'] += 1
            if sec.get('concrete_hatch') or sec.get('section_dims'):
                stats['sec_ok'] += 1
            if sarr.get('count', 0) > 0 or sarr.get('layers'):
                stats['sarr_ok'] += 1

            pw_a = ','.join(str(int(w)) for w in (fa.get('panel_widths') or [])[:4])
            pw_b = ','.join(str(int(w)) for w in (fb.get('panel_widths') or [])[:4])
            print(f'    {viga_name:25s} FA[{fa.get("panel_count",0):2d}]={pw_a:20s} '
                  f'FB[{fb.get("panel_count",0):2d}]={pw_b:20s}')
            ok += 1

    return all_params, ok, fail, stats


def main():
    parser = argparse.ArgumentParser(description='Multi-catalog viga parameter extraction')
    parser.add_argument('--catalog', nargs='+', required=True, help='Catalog JSON file(s)')
    parser.add_argument('--output', required=True, help='Output params JSON')
    parser.add_argument('--skip-existing', help='Path to existing params JSON to skip already-extracted vigas')
    args = parser.parse_args()

    # Load catalogs
    all_catalog = []
    for cat_path in args.catalog:
        cat = json.loads(Path(cat_path).read_text(encoding='utf-8'))
        print(f'Loaded catalog: {cat_path} ({len(cat)} entries)')
        all_catalog.extend(cat)

    # Optional: skip already-extracted vigas
    skip_keys = set()
    if args.skip_existing:
        existing = json.loads(Path(args.skip_existing).read_text(encoding='utf-8'))
        for v in existing:
            key = (v.get('obra', ''), v.get('dxf_source', ''), v.get('viga', ''))
            skip_keys.add(key)
        before = len(all_catalog)
        all_catalog = [
            e for e in all_catalog
            if (e.get('obra', ''), e.get('dxf_source', ''), e.get('viga', '')) not in skip_keys
        ]
        print(f'Skipped {before - len(all_catalog)} already-extracted vigas')

    print(f'\nTotal catalog entries to process: {len(all_catalog)}')

    # Extract
    all_params, ok, fail, stats = extract_from_catalog(all_catalog)

    # Save
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_params, f, indent=2, ensure_ascii=False)

    n = len(all_params)
    print(f'\n{"="*60}')
    print(f'RESULTADO: {ok} OK / {fail} FAIL')
    print(f'Saved: {out_path}')
    if n > 0:
        print(f'\n=== COBERTURA ===')
        print(f'  Face A panels: {stats["fa_ok"]:3d}/{n} ({stats["fa_ok"]/n*100:.0f}%)')
        print(f'  Face B panels: {stats["fb_ok"]:3d}/{n} ({stats["fb_ok"]/n*100:.0f}%)')
        print(f'  Secao detail:  {stats["sec_ok"]:3d}/{n} ({stats["sec_ok"]/n*100:.0f}%)')
        print(f'  Sarrafos:      {stats["sarr_ok"]:3d}/{n} ({stats["sarr_ok"]/n*100:.0f}%)')


if __name__ == '__main__':
    main()
