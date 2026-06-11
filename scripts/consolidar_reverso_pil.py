#!/usr/bin/env python3
"""
consolidar_reverso_pil.py — Consolida fichas reverso PIL de todos os pavimentos.

Regras de merge (mesmo pilar em pavimentos diferentes):
  - comprimento / largura: manter maior valor com confidence >= 0.8 (forma principal)
  - altura_cm: manter conforme pavimento (varia por pé-direito)
  - pavimentos: lista de todos onde aparece

Saida: fichas_reverso_PIL_ALL.json  (dict keyed by pilar id)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json, glob, os, re, argparse


def pav_from_filename(fname):
    stem = os.path.splitext(os.path.basename(fname))[0]
    m = re.search(r'PIL_(.+)$', stem)
    return m.group(1) if m else stem


def load_all(reverso_dir):
    pattern = os.path.join(reverso_dir, 'fichas_reverso_PIL_*.json')
    files = sorted(f for f in glob.glob(pattern) if '_debug' not in f)
    result = []
    for f in files:
        pav = pav_from_filename(f)
        with open(f, encoding='utf-8') as fp:
            data = json.load(fp)
        # Normalize to list
        if isinstance(data, dict):
            data = [v for k, v in data.items() if k != '_meta']
        result.append((pav, data))
        print(f"  Loaded {pav}: {len(data)} pilares")
    return result


def consolidar(all_data):
    consolidated = {}

    for pav, fichas in all_data:
        for ficha in fichas:
            pid = ficha.get('id', '')
            if not pid:
                continue
            comp = float(ficha.get('comprimento', 0) or 0)
            larg = float(ficha.get('largura', 0) or 0)
            alt  = float(ficha.get('altura_cm', 0) or 0)
            conf = float(ficha.get('confidence', 0) or 0)

            if pid not in consolidated:
                consolidated[pid] = {
                    'id':          pid,
                    'comprimento': comp,
                    'largura':     larg,
                    'altura_cm':   alt,
                    'confidence':  conf,
                    'pavimentos':  [pav],
                    '_sources':    {pav: {'comprimento': comp, 'largura': larg,
                                          'altura_cm': alt, 'confidence': conf}},
                }
            else:
                existing = consolidated[pid]
                existing['pavimentos'].append(pav)
                existing['_sources'][pav] = {
                    'comprimento': comp, 'largura': larg,
                    'altura_cm': alt, 'confidence': conf,
                }
                # Keep best comprimento (larger, from confident source)
                if comp > existing['comprimento'] and conf >= existing['confidence']:
                    existing['comprimento'] = comp
                # Keep best largura
                if larg > existing['largura'] and conf >= existing['confidence']:
                    existing['largura'] = larg
                # Keep best confidence
                if conf > existing['confidence']:
                    existing['confidence'] = conf

    return consolidated


def main():
    parser = argparse.ArgumentParser(
        description='Consolida fichas reverso PIL de todos os pavimentos'
    )
    parser.add_argument('--reverso-dir',
                        default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-3_Interpretacao_Extracao/Pilares/reverso',
                        help='Pasta com fichas_reverso_PIL_*.json')
    parser.add_argument('--output',
                        default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-3_Interpretacao_Extracao/Pilares/fichas_reverso_PIL_ALL.json',
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
    print(f"\n{'=' * 75}")
    print(f"{'PILAR':<8} {'COMP':>6} {'LARG':>6} {'ALT':>6} {'CONF':>5}  PAVIMENTOS")
    print(f"{'=' * 75}")

    def sort_key(k):
        m = re.search(r'\d+', k)
        return int(m.group()) if m else 0

    for pid in sorted(consolidated, key=sort_key):
        f = consolidated[pid]
        pavs = ','.join(f['pavimentos'])
        print(f"  {pid:<6} {f['comprimento']:>6.0f} {f['largura']:>6.0f} "
              f"{f['altura_cm']:>6.0f} {f['confidence']:>5.2f}  {pavs}")

    n_ok = sum(1 for f in consolidated.values() if f['comprimento'] > 0)
    print(f"\nTotal: {len(consolidated)} pilares únicos | Com comprimento: {n_ok}")
    print(f"Saida: {args.output}")


if __name__ == '__main__':
    main()
