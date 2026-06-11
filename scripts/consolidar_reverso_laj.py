#!/usr/bin/env python3
"""
consolidar_reverso_laj.py — Consolida fichas reverso LAJ de todos os pavimentos.

Regras de merge: cada laje tem ID único por pavimento (L1-L30 no TIPO, L101+ em outros).
Conflitos (mesmo ID em pavimentos diferentes) são improváveis; se ocorrerem,
prefere comprimento maior de fonte com has_comp=True.

Saida: fichas_reverso_LAJ_ALL.json (dict keyed by laje nome)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json, glob, os, re, argparse


def pav_from_filename(fname):
    stem = os.path.splitext(os.path.basename(fname))[0]
    m = re.search(r'LAJ_(.+)$', stem)
    return m.group(1) if m else stem


def load_all(reverso_dir):
    pattern = os.path.join(reverso_dir, 'fichas_reverso_LAJ_*.json')
    files = sorted(glob.glob(pattern))
    result = []
    for f in files:
        pav = pav_from_filename(f)
        with open(f, encoding='utf-8') as fp:
            data = json.load(fp)
        # Normalize to dict
        if isinstance(data, list):
            data = {item.get('nome', item.get('id', '')): item for item in data}
        result.append((pav, data))
        n_comp = sum(1 for v in data.values() if v.get('comprimento_total', 0) > 0)
        print(f"  Loaded {pav}: {len(data)} lajes ({n_comp} com comp)")
    return result


def consolidar(all_data):
    consolidated = {}

    for pav, fichas in all_data:
        for nome, ficha in fichas.items():
            comp = float(ficha.get('comprimento_total', 0) or 0)
            larg = float(ficha.get('largura_total', 0) or 0)
            nivel = ficha.get('nivel_delta', 0)

            n_paineis = ficha.get('n_paineis', 0) or 0

            if nome not in consolidated:
                consolidated[nome] = {
                    'nome':              nome,
                    'comprimento_total': comp,
                    'largura_total':     larg,
                    'nivel_delta':       nivel,
                    'n_paineis':         n_paineis,
                    'pavimentos':        [pav],
                    '_sources':          {pav: {'comprimento_total': comp,
                                                'largura_total': larg,
                                                'nivel_delta': nivel}},
                }
            else:
                existing = consolidated[nome]
                existing['pavimentos'].append(pav)
                existing['_sources'][pav] = {
                    'comprimento_total': comp,
                    'largura_total':     larg,
                    'nivel_delta':       nivel,
                }
                # Prefer larger comprimento
                if comp > existing['comprimento_total']:
                    existing['comprimento_total'] = comp
                # Prefer non-zero largura
                if larg > existing['largura_total']:
                    existing['largura_total'] = larg
                # Keep nivel_delta from best source
                if nivel > 0 and existing['nivel_delta'] == 0:
                    existing['nivel_delta'] = nivel
                # n_paineis: take max (best coverage)
                if n_paineis > existing.get('n_paineis', 0):
                    existing['n_paineis'] = n_paineis

    return consolidated


def main():
    parser = argparse.ArgumentParser(
        description='Consolida fichas reverso LAJ de todos os pavimentos'
    )
    parser.add_argument('--reverso-dir',
                        default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-3_Interpretacao_Extracao/Lajes/reverso',
                        help='Pasta com fichas_reverso_LAJ_*.json')
    parser.add_argument('--output',
                        default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-3_Interpretacao_Extracao/Lajes/fichas_reverso_LAJ_ALL.json',
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
    print(f"\n{'=' * 72}")
    print(f"{'LAJE':<8} {'COMP':>6} {'LARG':>6} {'h=':>4}  PAVIMENTOS")
    print(f"{'=' * 72}")

    def sort_key(k):
        m = re.search(r'\d+', k)
        return int(m.group()) if m else 0

    for nome in sorted(consolidated, key=sort_key):
        f = consolidated[nome]
        pavs = ','.join(f['pavimentos'])
        print(f"  {nome:<6} {f['comprimento_total']:>6.0f} {f['largura_total']:>6.0f} "
              f"{f['nivel_delta']:>4}  {pavs}")

    n_comp = sum(1 for f in consolidated.values() if f['comprimento_total'] > 0)
    n_larg = sum(1 for f in consolidated.values() if f['largura_total'] > 0)
    print(f"\nTotal: {len(consolidated)} lajes únicas | Comp>0: {n_comp} | Larg>0: {n_larg}")
    print(f"Saida: {args.output}")


if __name__ == '__main__':
    main()
