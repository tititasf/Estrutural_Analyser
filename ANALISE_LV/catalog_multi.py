#!/usr/bin/env python3
"""
catalog_multi.py -- Gera catalog entries para qualquer DXF LV com formato TEXT/NOMENCLATURA.

Funciona com vigas no padrao V###\\P(NxM) na layer NOMENCLATURA.

Uso:
  python catalog_multi.py --dxf PATH --obra NOME --pavimento NOME --output PATH
  python catalog_multi.py --batch TREINO_11   # processa todos os LV DXFs de TREINO_11
  python catalog_multi.py --batch TREINO_5    # processa todos os LV DXFs de TREINO_5
  python catalog_multi.py --batch ALL         # processa TREINO_11 + TREINO_5
"""
import sys, io, json, re, os, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path

OBRAS_BASE = Path(r'D:/Agente-cad-PYSIDE/DADOS-OBRAS')
OUTPUT_DIR = Path(r'D:/Agente-cad-PYSIDE/ANALISE_LV/params')


# --------------- DXF discovery ---------------

TREINO_11_DIR = OBRAS_BASE / 'Obra_TREINO_11' / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'
TREINO_5_DIR  = OBRAS_BASE / 'Obra_TREINO_5'  / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'


def discover_lv_dxfs(obra_key):
    """Return list of (dxf_path, obra, projeto, pavimento) tuples."""
    results = []

    if obra_key in ('TREINO_11', 'ALL'):
        for f in sorted(os.listdir(TREINO_11_DIR)):
            if '-LV-' in f and f.endswith('.dxf') and '_RECOVER' not in f:
                # Parse pavimento from filename: NOVA-SCHWARTZ-GWT-{PAV}-LV-...
                m = re.search(r'GWT-(.+?)-LV', f)
                pav = m.group(1) if m else f.split('-LV')[0].split('-')[-1]
                results.append((
                    TREINO_11_DIR / f,
                    'Obra_TREINO_11',
                    'NOVA-SCHWARTZ-GWT',
                    f'GWT-{pav}',
                ))

    if obra_key in ('TREINO_5', 'ALL'):
        for f in sorted(os.listdir(TREINO_5_DIR)):
            if '-LV-' in f and f.endswith('.dxf') and '_RECOVER' not in f:
                # Parse pavimento: NOVA-D'URSO-EMBRAMACO-{PAV}-LV-...
                m = re.search(r'EMBRAMACO-(.+?)-LV', f)
                pav = m.group(1) if m else f.split('-LV')[0].split('-')[-1]
                results.append((
                    TREINO_5_DIR / f,
                    'Obra_TREINO_5',
                    'NOVA-DURSO-EMBRAMACO',
                    f'EMBRAMACO-{pav}',
                ))

    return results


# --------------- Viga detection ---------------

def find_viga_texts(msp):
    """Encontra TEXTs na layer NOMENCLATURA com pattern V\\d+.
    Formato: 'V401\\P(14x158)' -> titulo='V401', secao='(14x158)'.
    Exclui face labels como V401.A, V402.B e continuacoes.
    """
    vigas = []
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        layer = e.dxf.layer
        if layer != 'NOMENCLATURA':
            continue

        if e.dxftype() == 'TEXT':
            text = e.dxf.text.strip()
            x, y = e.dxf.insert.x, e.dxf.insert.y
        else:
            text = e.text.strip() if hasattr(e, 'text') else ''
            x, y = e.dxf.insert.x, e.dxf.insert.y

        if not re.match(r'^V\d+', text):
            continue

        # Parse: 'V401\P(14x158)'
        parts = text.split('\\P')
        titulo = parts[0].strip()
        secao = parts[1].strip() if len(parts) > 1 else ''

        # Skip face labels like V401.A, V402.B, V101.C, V238.b and CONTINUACAO
        if re.search(r'\.[A-Za-z]', titulo):
            continue
        if 'CONTINUA' in text.upper():
            continue

        vigas.append({
            'nome': titulo,
            'secao': secao,
            'insert_x': round(x, 1),
            'insert_y': round(y, 1),
        })

    # Remove duplicates (keep first occurrence, sorted by Y desc)
    vigas.sort(key=lambda v: (-v['insert_y'], v['insert_x']))
    seen = set()
    unique = []
    for v in vigas:
        if v['nome'] not in seen:
            seen.add(v['nome'])
            unique.append(v)
    return unique


def compute_zone(all_vigas, target_name):
    """Calcula zone (y_top, y_bot, x_left, x_right) baseado na vizinhanca."""
    if not all_vigas:
        return None

    # Group vigas into rows by Y proximity
    sorted_vigas = sorted(all_vigas, key=lambda v: -v['insert_y'])
    zones = []
    current = [sorted_vigas[0]]
    for i in range(1, len(sorted_vigas)):
        if current[-1]['insert_y'] - sorted_vigas[i]['insert_y'] < 150:
            current.append(sorted_vigas[i])
        else:
            zones.append(current)
            current = [sorted_vigas[i]]
    zones.append(current)

    for zi, zone in enumerate(zones):
        for v in zone:
            if v['nome'] == target_name:
                y_top = max(z['insert_y'] for z in zone) + 80
                if zi < len(zones) - 1:
                    y_bot = max(z['insert_y'] for z in zones[zi + 1])
                else:
                    y_bot = min(z['insert_y'] for z in zone) - 1000

                zone_by_x = sorted(zone, key=lambda z: z['insert_x'])
                idx = next(i for i, z in enumerate(zone_by_x) if z['nome'] == target_name)
                x_left = (zone_by_x[idx]['insert_x'] + zone_by_x[idx - 1]['insert_x']) / 2 if idx > 0 else None
                x_right = (zone_by_x[idx]['insert_x'] + zone_by_x[idx + 1]['insert_x']) / 2 if idx < len(zone_by_x) - 1 else None

                return {
                    'y_top': round(y_top, 1),
                    'y_bot': round(y_bot, 1),
                    'x_left': round(x_left, 1) if x_left is not None else None,
                    'x_right': round(x_right, 1) if x_right is not None else None,
                }
    return None


def catalog_single_dxf(dxf_path, obra, projeto, pavimento):
    """Generate catalog entries for a single DXF file."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    vigas = find_viga_texts(msp)

    catalog = []
    for v in vigas:
        zone = compute_zone(vigas, v['nome'])
        entry = {
            'obra': obra,
            'projeto': projeto,
            'pavimento': pavimento,
            'viga': v['nome'],
            'secao': v['secao'],
            'insert_x': v['insert_x'],
            'insert_y': v['insert_y'],
            'dxf_source': dxf_path.name,
            'zone': zone,
        }
        catalog.append(entry)

    return catalog, vigas


def main():
    parser = argparse.ArgumentParser(description='Multi-DXF LV catalog generator')
    parser.add_argument('--dxf', help='Single DXF file path')
    parser.add_argument('--obra', default='', help='Obra name')
    parser.add_argument('--projeto', default='', help='Projeto name')
    parser.add_argument('--pavimento', default='', help='Pavimento name')
    parser.add_argument('--output', help='Output JSON path')
    parser.add_argument('--batch', choices=['TREINO_11', 'TREINO_5', 'ALL'],
                        help='Batch process all LV DXFs from obra')
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.batch:
        dxf_list = discover_lv_dxfs(args.batch)
        print(f'=== BATCH CATALOG: {args.batch} ({len(dxf_list)} DXFs) ===\n')

        grand_catalog = []
        summary = []

        for dxf_path, obra, projeto, pavimento in dxf_list:
            print(f'--- {pavimento} ---')
            print(f'  DXF: {dxf_path.name}')

            try:
                cat, vigas = catalog_single_dxf(dxf_path, obra, projeto, pavimento)
            except Exception as ex:
                print(f'  ERROR: {ex}')
                summary.append((pavimento, 0, str(ex)))
                continue

            print(f'  Vigas: {len(cat)}')
            for v in cat:
                z = v.get('zone', {}) or {}
                print(f'    {v["viga"]:25s} {v["secao"]:15s} ({v["insert_x"]:8.0f},{v["insert_y"]:8.0f})')

            # Save individual catalog
            safe_pav = re.sub(r'[^\w\-]', '_', pavimento)
            safe_obra = re.sub(r'[^\w\-]', '_', obra)
            out_path = OUTPUT_DIR / f'catalog_{safe_obra}_{safe_pav}.json'
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(cat, f, indent=2, ensure_ascii=False)
            print(f'  Saved: {out_path.name}')

            grand_catalog.extend(cat)
            summary.append((pavimento, len(cat), 'OK'))

        # Save combined catalog
        combined_path = OUTPUT_DIR / f'catalog_{args.batch}_all.json'
        with open(combined_path, 'w', encoding='utf-8') as f:
            json.dump(grand_catalog, f, indent=2, ensure_ascii=False)

        print(f'\n{"="*60}')
        print(f'SUMMARY: {args.batch}')
        print(f'{"="*60}')
        total = 0
        for pav, cnt, status in summary:
            print(f'  {pav:30s} {cnt:4d} vigas  {status}')
            total += cnt
        print(f'  {"TOTAL":30s} {total:4d} vigas')
        print(f'\nCombined catalog: {combined_path}')

    elif args.dxf:
        dxf_path = Path(args.dxf)
        print(f'=== CATALOG: {dxf_path.name} ===')
        cat, vigas = catalog_single_dxf(
            dxf_path,
            args.obra or 'unknown',
            args.projeto or 'unknown',
            args.pavimento or 'unknown',
        )
        print(f'Vigas: {len(cat)}')
        for v in cat:
            print(f'  {v["viga"]:25s} {v["secao"]:15s} ({v["insert_x"]:8.0f},{v["insert_y"]:8.0f})')

        out_path = Path(args.output) if args.output else OUTPUT_DIR / f'catalog_single.json'
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(cat, f, indent=2, ensure_ascii=False)
        print(f'Saved: {out_path}')

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
