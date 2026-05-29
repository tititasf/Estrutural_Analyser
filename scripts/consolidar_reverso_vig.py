#!/usr/bin/env python3
"""
consolidar_reverso_vig.py — Consolida fichas reverso VIG de todos os pavimentos.

Lê todos os fichas_reverso_VIG_*.json da pasta reverso/ e gera
fichas_reverso_VIG_ALL.json com pavimento anotado e sem duplicatas.

Regras de merge (mesmo nome de viga em diferentes pavimentos):
  - comprimento_cm: priorizar maior valor com has_lv=True (forma real)
  - altura_cm: média ou valor com has_lv=True
  - b: max (melhor estimativa)
  - pavimentos: lista de todos os pavimentos onde aparece

Saida: fichas_reverso_VIG_ALL.json
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json, glob, os, re, argparse


PAVIMENTO_ORDER = ['TIPO', 'TERREO', '1PAV', '2PAV', '13PAV', '14PAV', 'COBERTURA']


def pav_from_filename(fname):
    """Extrai label do pavimento do nome do arquivo."""
    stem = os.path.splitext(os.path.basename(fname))[0]
    m = re.search(r'VIG_(.+)$', stem)
    return m.group(1) if m else stem


def load_all(reverso_dir):
    """Carrega todos os JSONs de reverso/ em lista de (pavimento, fichas_dict)."""
    pattern = os.path.join(reverso_dir, 'fichas_reverso_VIG_*.json')
    files = sorted(glob.glob(pattern))
    result = []
    for f in files:
        pav = pav_from_filename(f)
        with open(f, encoding='utf-8') as fp:
            data = json.load(fp)
        result.append((pav, data))
        print(f"  Loaded {pav}: {len(data)} vigas")
    return result


def consolidar(all_data):
    """Consolida todos os dados em dict keyed by viga name."""
    consolidated = {}

    for pav, fichas in all_data:
        for viga, ficha in fichas.items():
            if viga not in consolidated:
                entry = {
                    'nome':           viga,
                    'comprimento_cm': ficha.get('comprimento_cm', 0),
                    'altura_cm':      ficha.get('altura_cm', 0),
                    'b':              ficha.get('b', 0),
                    'h_secao':        ficha.get('h_secao', 0),
                    'has_lv':         ficha.get('has_lv', False),
                    'has_fv':         ficha.get('has_fv', False),
                    'pavimentos':     [pav],
                    '_sources':       {pav: {
                        'comprimento_cm': ficha.get('comprimento_cm', 0),
                        'altura_cm':      ficha.get('altura_cm', 0),
                        'b':              ficha.get('b', 0),
                        'h_secao':        ficha.get('h_secao', 0),
                        'has_lv':         ficha.get('has_lv', False),
                        'has_fv':         ficha.get('has_fv', False),
                    }},
                }
                # Propagar lado_A e lado_B (contêm pillar_left/right, n_paineis, paineis)
                for side in ('lado_A', 'lado_B'):
                    if side in ficha:
                        entry[side] = ficha[side]
                consolidated[viga] = entry
            else:
                existing = consolidated[viga]
                existing['pavimentos'].append(pav)
                existing['_sources'][pav] = {
                    'comprimento_cm': ficha.get('comprimento_cm', 0),
                    'altura_cm':      ficha.get('altura_cm', 0),
                    'b':              ficha.get('b', 0),
                    'has_lv':         ficha.get('has_lv', False),
                    'has_fv':         ficha.get('has_fv', False),
                }
                # Merge: prefer best comprimento from has_lv source
                new_comp = ficha.get('comprimento_cm', 0)
                if new_comp > existing['comprimento_cm'] and ficha.get('has_lv', False):
                    existing['comprimento_cm'] = new_comp
                # b: max
                new_b = ficha.get('b', 0)
                if new_b > existing['b']:
                    existing['b'] = new_b
                # h_secao: prefer value from has_lv source (more reliable)
                new_hs = ficha.get('h_secao', 0)
                if new_hs > 0 and existing.get('h_secao', 0) == 0:
                    existing['h_secao'] = new_hs
                # altura_cm: prefer has_lv with has_fv (better estimate)
                new_h = ficha.get('altura_cm', 0)
                if new_h > 0 and ficha.get('has_fv', False) and not existing.get('has_fv', False):
                    existing['altura_cm'] = new_h
                elif new_h > existing['altura_cm'] and existing['altura_cm'] == 0:
                    existing['altura_cm'] = new_h
                # Update flags
                if ficha.get('has_lv', False):
                    existing['has_lv'] = True
                if ficha.get('has_fv', False):
                    existing['has_fv'] = True

    return consolidated


def main():
    parser = argparse.ArgumentParser(
        description='Consolida fichas reverso VIG de todos os pavimentos'
    )
    parser.add_argument('--reverso-dir',
                        default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-3_Interpretacao_Extracao/Vigas/reverso',
                        help='Pasta com fichas_reverso_VIG_*.json')
    parser.add_argument('--output',
                        default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-3_Interpretacao_Extracao/Vigas/fichas_reverso_VIG_ALL.json',
                        help='Saida JSON consolidada')
    args = parser.parse_args()

    print(f"Lendo reverso dir: {args.reverso_dir}")
    all_data = load_all(args.reverso_dir)
    print(f"  Total arquivos: {len(all_data)}")

    consolidated = consolidar(all_data)

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as fp:
        json.dump(consolidated, fp, ensure_ascii=False, indent=2)

    # ── Relatório ────────────────────────────────────────────────────────────
    print(f"\n{'=' * 78}")
    print(f"{'VIGA':<8} {'COMP':>6} {'ALT':>5} {'B':>4}  LV  FV  PAVIMENTOS")
    print(f"{'=' * 78}")

    def sort_key(k):
        m = re.search(r'\d+', k)
        return int(m.group()) if m else 0

    for viga in sorted(consolidated, key=sort_key):
        f = consolidated[viga]
        pavs = ','.join(f['pavimentos'])
        print(f"  {viga:<6} {f['comprimento_cm']:>6.0f} {f['altura_cm']:>5.1f} {f['b']:>4.0f}  "
              f"{'Y' if f['has_lv'] else '-':>2}  {'Y' if f['has_fv'] else '-':>2}  {pavs}")

    n_lv  = sum(1 for f in consolidated.values() if f['has_lv'])
    n_fv  = sum(1 for f in consolidated.values() if f['has_fv'])
    n_ok  = sum(1 for f in consolidated.values() if f['comprimento_cm'] > 0)
    n_b   = sum(1 for f in consolidated.values() if f['b'] > 0)
    print(f"\nTotal: {len(consolidated)} vigas | LV: {n_lv} | FV: {n_fv} | "
          f"Comp>0: {n_ok} | B>0: {n_b}")
    print(f"Saida: {args.output}")


if __name__ == '__main__':
    main()
