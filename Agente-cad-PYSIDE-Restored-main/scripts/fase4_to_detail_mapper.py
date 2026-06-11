#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fase4_to_detail_mapper.py — CAD-10.1 (AC-5)
Valida mapeamentos Fase-4 → DetailCard contra dados reais de uma obra.

Uso:
    python scripts/fase4_to_detail_mapper.py --obra DADOS-OBRAS/Obra_TREINO_1
    python scripts/fase4_to_detail_mapper.py --obra DADOS-OBRAS/Obra_TREINO_1 --verbose
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

if hasattr(sys.stdout, 'buffer'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from src.core.field_mapping import map_pilar, map_viga_lateral, map_viga_fundo, map_laje


def _analyze_mapping(result: dict, tipo: str, item_id: str, verbose: bool) -> dict:
    total_flat   = len(result['flat'])
    total_links  = len(result['links'])
    # Contar sides_data como campos populados (cada key de cada face)
    sd_count     = sum(len(keys) for keys in result.get('sides_data', {}).values())
    total        = total_flat + total_links  # sem contar sd no denominador (seria muito grande)
    filled_flat  = sum(1 for v in result['flat'].values() if v not in (None, '', 0.0, 0, [], {}))
    filled_links = sum(1 for v in result['links'].values() if v)
    filled_sd    = sum(1 for keys in result.get('sides_data', {}).values()
                       for v in keys.values() if v not in (None, 0.0, 0))
    filled       = filled_flat + filled_links + (1 if filled_sd > 0 else 0)  # sides_data conta como 1 bloco

    unmapped_fase4 = [k for k, v in result['flat'].items()
                      if v in (None, '', 0.0, 0, [], {})]

    pct = round(100 * filled / total, 1) if total else 0

    if verbose:
        print(f"\n  [{tipo}] {item_id}: {filled}/{total} campos ({pct}%)  [sides_data: {filled_sd} campos]")
        if unmapped_fase4:
            print(f"    Campos zerados/ausentes: {unmapped_fase4[:8]}")
        if result['sides_data']:
            faces = list(result['sides_data'].keys())
            print(f"    sides_data faces: {faces}")

    return {'tipo': tipo, 'id': item_id, 'filled': filled, 'total': total, 'pct': pct}


def run(obra_path: str, verbose: bool = False):
    obra = pathlib.Path(obra_path)
    fase4 = obra / 'Fase-4_Sincronizacao'

    if not fase4.exists():
        print(f"[ERRO] Fase-4 não encontrada: {fase4}")
        sys.exit(1)

    stats = {'pilar': [], 'viga_lv': [], 'viga_fv': [], 'laje': []}
    erros = []

    # ── Pilares ──────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"OBRA: {obra.name}")
    print(f"{'─'*50}")
    print(f"\n[PILARES]")
    pil_files = sorted((fase4 / 'JSON_Pilares').glob('*.json'))
    for f in pil_files[:5] if not verbose else pil_files:
        try:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
            r = map_pilar(data)
            stats['pilar'].append(_analyze_mapping(r, 'PILAR', f.stem, verbose))
        except Exception as e:
            erros.append(f'{f.stem}: {e}')

    print(f"  Total arquivos: {len(pil_files)} | Amostrados: {len(stats['pilar'])}")

    # ── Vigas Laterais ────────────────────────────────────────────
    print(f"\n[VIGAS LATERAIS (LV)]")
    lv_files = sorted((fase4 / 'JSON_Vigas_Laterais').glob('*.json'))
    for f in lv_files[:5] if not verbose else lv_files:
        try:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
            side = f.stem.rsplit('_', 1)[-1] if '_' in f.stem else 'A'
            r = map_viga_lateral(data, side)
            stats['viga_lv'].append(_analyze_mapping(r, 'VIGA_LV', f.stem, verbose))
        except Exception as e:
            erros.append(f'{f.stem}: {e}')

    print(f"  Total arquivos: {len(lv_files)} | Amostrados: {len(stats['viga_lv'])}")

    # ── Vigas Fundo ───────────────────────────────────────────────
    print(f"\n[VIGAS FUNDO (FV)]")
    fv_files = sorted((fase4 / 'JSON_Vigas_Fundo').glob('*.json'))
    for f in fv_files[:5] if not verbose else fv_files:
        try:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
            r = map_viga_fundo(data)
            stats['viga_fv'].append(_analyze_mapping(r, 'VIGA_FV', f.stem, verbose))
        except Exception as e:
            erros.append(f'{f.stem}: {e}')

    print(f"  Total arquivos: {len(fv_files)} | Amostrados: {len(stats['viga_fv'])}")

    # ── Lajes ─────────────────────────────────────────────────────
    print(f"\n[LAJES (LJ)]")
    lj_files = sorted((fase4 / 'JSON_Lajes').glob('*.json'))
    for f in lj_files[:5] if not verbose else lj_files:
        try:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
            r = map_laje(data)
            stats['laje'].append(_analyze_mapping(r, 'LAJE', f.stem, verbose))
        except Exception as e:
            erros.append(f'{f.stem}: {e}')

    print(f"  Total arquivos: {len(lj_files)} | Amostrados: {len(stats['laje'])}")

    # ── Sumário ───────────────────────────────────────────────────
    print(f"\n{'═'*50}")
    print("SUMÁRIO DE COBERTURA")
    print(f"{'═'*50}")

    # Pilar: 50% flat (par_3..8 são estruturalmente 0 para pilares simples) + sides_data rico
    thresholds = {'pilar': 50, 'viga_lv': 60, 'viga_fv': 50, 'laje': 50}
    all_pass = True

    for tipo, items in stats.items():
        if not items:
            continue
        avg_pct = sum(i['pct'] for i in items) / len(items)
        avg_filled = sum(i['filled'] for i in items) / len(items)
        avg_total  = sum(i['total'] for i in items) / len(items)
        threshold = thresholds.get(tipo, 50)
        status = '✓ PASS' if avg_pct >= threshold else f'✗ FAIL (meta: {threshold}%)'
        print(f"  {tipo.upper():10s}: {avg_pct:5.1f}%  "
              f"({avg_filled:.0f}/{avg_total:.0f} campos médios)  {status}")
        if avg_pct < threshold:
            all_pass = False

    if erros:
        print(f"\n  Erros: {len(erros)}")
        for e in erros[:5]:
            print(f"    - {e}")

    print(f"\n{'═'*50}")
    print(f"Resultado geral: {'✓ TODOS OS THRESHOLDS OK' if all_pass else '⚠ ALGUNS THRESHOLDS NÃO ATINGIDOS'}")
    print(f"{'═'*50}\n")

    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra',    required=True, help='Path da obra')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    run(args.obra, args.verbose)
