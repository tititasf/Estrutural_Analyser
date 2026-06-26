#!/usr/bin/env python3
"""
extrair_garfos_evg.py — Extrai dados de garfos/EVG do EVG DXF.

Layer "VIGAS": "V{n} = {count}X" → garfo_count por viga
Layer "NOME DA VIGA": "T{n}-{count}X" → tipo de garfo por secao

O EVG DXF tem dois grupos (por posicao X):
  - TIPO   (PAV 4-11): X <= 22000
  - ADITIVO (12 PAV):  X > 22000

Story: CAD-5.4
Usage: python scripts/extrair_garfos_evg.py --obra PATH --pavimento "12 PAV"
"""
import argparse, json, re, sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERROR: pip install ezdxf")
    sys.exit(1)


ADITIVO_X_THRESHOLD = 22000  # X > threshold = ADITIVO section


def find_evg_dxfs(obra_path):
    """Localiza todos os arquivos EVG DXF disponíveis."""
    fase1 = Path(obra_path) / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'
    dxfs = list(fase1.glob('*.dxf')) + list(fase1.glob('*.DXF'))
    seen, unique = set(), []
    for f in dxfs:
        if 'EVG' in f.name.upper() and f.name not in seen:
            seen.add(f.name)
            unique.append(f)
    return unique


def extract_garfos_from_dxf(dxf_path):
    """
    Extrai dados de garfos do EVG DXF.
    Retorna: {"tipo": {vid: {count, sections}}, "aditivo": {vid: {count, sections}}}
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    tipo_garfos = {}    # PAV 4-11
    aditivo_garfos = {}  # ADITIVO (12 PAV)

    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        if e.dxf.layer not in ('VIGAS',):
            continue
        try:
            txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
            pos_x = e.dxf.insert.x
        except Exception:
            continue

        # Pattern: "V{n} = {count}X"
        m = re.match(r'V(\d+[A-Z]?)\s*=\s*(\d+)X', txt, re.IGNORECASE)
        if not m:
            continue

        vid = 'V' + m.group(1).upper()
        count = int(m.group(2))

        target = aditivo_garfos if pos_x > ADITIVO_X_THRESHOLD else tipo_garfos

        if vid not in target:
            target[vid] = {'garfo_count': 0, 'entries': []}
        # Sum counts for same viga (multiple sections)
        target[vid]['garfo_count'] += count
        target[vid]['entries'].append(f'{count}X @ x={pos_x:.0f}')

    return {'tipo': tipo_garfos, 'aditivo': aditivo_garfos}


def extract_garfo_types(dxf_path):
    """
    Extrai tipos de garfo do EVG DXF.
    Layer "NOME DA VIGA": "T{n}-{count}X" → tipo de garfo
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    tipo_types = {}
    aditivo_types = {}

    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        if e.dxf.layer not in ('NOME DA VIGA',):
            continue
        try:
            txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
            pos_x = e.dxf.insert.x
        except Exception:
            continue

        # Pattern: "T{n}-{count}X" or "T{n}A-{count}X"
        m = re.match(r'(T\d+[A-Z]?)-(\d+)X', txt, re.IGNORECASE)
        if not m:
            continue

        garfo_type = m.group(1).upper()
        count = int(m.group(2))

        target = aditivo_types if pos_x > ADITIVO_X_THRESHOLD else tipo_types

        if garfo_type not in target:
            target[garfo_type] = 0
        target[garfo_type] += count

    return {'tipo': tipo_types, 'aditivo': aditivo_types}


def main():
    parser = argparse.ArgumentParser(description='Extrair dados de garfos do EVG DXF')
    parser.add_argument('--obra', required=True, help='Path da obra')
    parser.add_argument('--pavimento', default='12 PAV', help='Pavimento (ex: 12 PAV)')
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    evg_files = find_evg_dxfs(obra_path)

    if not evg_files:
        print(f"ERRO: Nenhum EVG DXF encontrado em {obra_path}")
        sys.exit(1)

    print(f"EVG DXFs encontrados: {[f.name for f in evg_files]}")

    # Consolidar todos os EVG DXFs
    all_tipo = {}
    all_aditivo = {}

    for evg_path in evg_files:
        print(f"\nProcessando: {evg_path.name}")
        garfos = extract_garfos_from_dxf(evg_path)
        types = extract_garfo_types(evg_path)

        for vid, data in garfos['tipo'].items():
            if vid not in all_tipo:
                all_tipo[vid] = {'garfo_count': data['garfo_count'], 'entries': data['entries'], 'source': evg_path.name}
            else:
                # Manter o maior count (evita dupla contagem de mesmo DXF em dois arquivos)
                if data['garfo_count'] > all_tipo[vid]['garfo_count']:
                    all_tipo[vid] = {'garfo_count': data['garfo_count'], 'entries': data['entries'], 'source': evg_path.name}

        for vid, data in garfos['aditivo'].items():
            if vid not in all_aditivo:
                all_aditivo[vid] = {'garfo_count': data['garfo_count'], 'entries': data['entries'], 'source': evg_path.name}
            else:
                if data['garfo_count'] > all_aditivo[vid]['garfo_count']:
                    all_aditivo[vid] = {'garfo_count': data['garfo_count'], 'entries': data['entries'], 'source': evg_path.name}

    # Para 12 PAV, usar ADITIVO se disponível, senão TIPO
    pav_num = re.search(r'\d+', args.pavimento)
    pav_num = int(pav_num.group()) if pav_num else 12
    use_aditivo = pav_num >= 12  # Assumir ADITIVO para PAV >= 12

    primary = all_aditivo if (use_aditivo and all_aditivo) else all_tipo
    secondary = all_tipo if primary is all_aditivo else all_aditivo

    # Merge: primary overrides secondary
    merged = {}
    for vid in set(list(secondary.keys()) + list(primary.keys())):
        if vid in primary:
            merged[vid] = primary[vid]
            merged[vid]['section'] = 'aditivo' if primary is all_aditivo else 'tipo'
        else:
            merged[vid] = secondary[vid]
            merged[vid]['section'] = 'tipo' if secondary is all_tipo else 'aditivo'

    # Build output
    result = {}
    for vid in sorted(merged.keys(), key=lambda x: (len(x), x)):
        data = merged[vid]
        result[vid] = {
            'id': vid,
            'garfo_count': data['garfo_count'],
            'section': data.get('section', 'tipo'),
            'source_dxf': data.get('source', ''),
            'confidence': 0.90 if data['garfo_count'] > 0 else 0.0,
        }

    # Save
    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = obra_path / 'Fase-3_Interpretacao_Extracao' / 'Garfos'
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / 'garfos_evg.json'

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Resumo
    total = len(result)
    com_garfos = sum(1 for v in result.values() if v['garfo_count'] > 0)
    total_garfos = sum(v['garfo_count'] for v in result.values())

    print(f"\n=== RESULTADO ===")
    print(f"  Vigas com garfo: {com_garfos}/{total}")
    print(f"  Total garfos: {total_garfos}")
    print(f"  Output: {out_path}")
    print()
    print(f"{'Viga':<8} {'Garfos':<10} {'Section':<10}")
    print("-" * 30)
    for vid, v in sorted(result.items(), key=lambda x: (len(x[0]), x[0])):
        print(f"{vid:<8} {v['garfo_count']:<10} {v['section']:<10}")

    # Também mostrar ADITIVO separado para diagnóstico
    print(f"\n=== ADITIVO vigas (X > {ADITIVO_X_THRESHOLD}) ===")
    for vid, data in sorted(all_aditivo.items(), key=lambda x: (len(x[0]), x[0])):
        print(f"  {vid}: {data['garfo_count']}X")

    print(f"\n=== TIPO vigas (X <= {ADITIVO_X_THRESHOLD}) ===")
    for vid, data in sorted(all_tipo.items(), key=lambda x: (len(x[0]), x[0])):
        print(f"  {vid}: {data['garfo_count']}X")


if __name__ == '__main__':
    main()
