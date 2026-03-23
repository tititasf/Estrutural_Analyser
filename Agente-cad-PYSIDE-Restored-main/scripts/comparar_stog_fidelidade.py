#!/usr/bin/env python3
"""
comparar_stog_fidelidade.py — Compara DXF STOG real vs DXF gerado por layer
============================================================================
Quality gate permanente: mede fidelidade dos geradores contra engenharia reversa.

Uso:
  python scripts/comparar_stog_fidelidade.py --obra DADOS-OBRAS/Obra_TREINO_1
  python scripts/comparar_stog_fidelidade.py --obra DADOS-OBRAS/Obra_TREINO_1 --tipo PL
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse
from pathlib import Path
from collections import Counter

try:
    import ezdxf
except ImportError:
    print("pip install ezdxf")
    sys.exit(1)


def count_layers(dxf_path):
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    layers = Counter(e.dxf.layer for e in msp)
    types = Counter(e.dxftype() for e in msp)
    inserts = Counter(e.dxf.name for e in msp if e.dxftype() == 'INSERT')
    return {
        'layers': dict(layers),
        'types': dict(types),
        'inserts': dict(inserts),
        'total': sum(layers.values()),
    }


def find_stog_real(obra_path, tipo):
    """Encontra DXF STOG real na engenharia reversa."""
    eng_rev = obra_path / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'
    pattern = f'*TIPO*{tipo}*R00.dxf'
    files = sorted(eng_rev.glob(pattern))
    if not files:
        files = sorted(eng_rev.glob(f'*{tipo}*.dxf'))
    return files[0] if files else None


def find_gerado(obra_path, tipo):
    """Encontra DXF gerado mais recente."""
    fase6 = obra_path / 'Fase-6_Execucao_CAD'
    if tipo == 'PL':
        return fase6 / 'PL_stog_quality.dxf'
    elif tipo == 'LJ':
        return fase6 / 'LJ_stog_quality.dxf'
    elif tipo == 'LV':
        files = sorted(fase6.glob('LV_stog_*.dxf'), key=lambda x: x.stat().st_size, reverse=True)
        return files[0] if files else None
    elif tipo == 'FV':
        return fase6 / 'FV_stog_quality.dxf'
    return None


def compare(real_data, gen_data, label):
    """Compara e retorna relatório."""
    real_layers = real_data['layers']
    gen_layers = gen_data['layers']
    all_layers = sorted(set(list(real_layers.keys()) + list(gen_layers.keys())))

    rows = []
    for ly in all_layers:
        r = real_layers.get(ly, 0)
        g = gen_layers.get(ly, 0)
        if r > 0:
            ratio = g / r
            status = 'OK' if ratio > 0.2 else 'MISS'
        elif g > 0:
            ratio = 0
            status = 'NEW'
        else:
            continue
        rows.append({'layer': ly, 'real': r, 'gen': g, 'ratio': round(ratio, 2), 'status': status})

    total_ratio = gen_data['total'] / real_data['total'] if real_data['total'] > 0 else 0

    return {
        'label': label,
        'real_total': real_data['total'],
        'gen_total': gen_data['total'],
        'ratio': round(total_ratio, 2),
        'layers': rows,
        'real_inserts': real_data['inserts'],
        'gen_inserts': gen_data['inserts'],
        'verdict': 'PASS' if total_ratio >= 0.50 else 'NEEDS_WORK',
    }


def print_report(report):
    print(f"\n=== {report['label']} ===")
    print(f"{'Layer':30s} {'Real':>8s} {'Gen':>8s} {'Ratio':>8s} {'Status':>8s}")
    print("-" * 66)
    for row in report['layers']:
        print(f"{row['layer']:30s} {row['real']:8d} {row['gen']:8d} {row['ratio']:8.2f} {row['status']:>8s}")
    print("-" * 66)
    print(f"{'TOTAL':30s} {report['real_total']:8d} {report['gen_total']:8d} {report['ratio']:8.2f} {report['verdict']:>8s}")

    if report['gen_inserts']:
        print(f"  INSERTs: {report['gen_inserts']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--tipo', choices=['PL', 'LJ', 'LV', 'FV', 'ALL'], default='ALL')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    tipos = ['PL', 'LJ', 'LV', 'FV'] if args.tipo == 'ALL' else [args.tipo]

    all_reports = []
    for tipo in tipos:
        real_path = find_stog_real(obra_path, tipo)
        gen_path = find_gerado(obra_path, tipo)

        if not real_path or not real_path.exists():
            print(f"\n[{tipo}] STOG real nao encontrado")
            continue
        if not gen_path or not gen_path.exists():
            print(f"\n[{tipo}] DXF gerado nao encontrado")
            continue

        real_data = count_layers(real_path)
        gen_data = count_layers(gen_path)
        report = compare(real_data, gen_data, f"{tipo} ({real_path.name} vs {gen_path.name})")
        print_report(report)
        all_reports.append(report)

    # Salvar JSON
    if all_reports:
        out = obra_path / 'Fase-6_Execucao_CAD' / 'fidelidade_stog.json'
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(all_reports, f, indent=2, ensure_ascii=False)
        print(f"\nRelatorio salvo: {out}")

    # Resumo
    if all_reports:
        print(f"\n=== RESUMO ===")
        for r in all_reports:
            print(f"  {r['label'][:20]:20s} ratio={r['ratio']:.2f}  {r['verdict']}")


if __name__ == '__main__':
    main()
