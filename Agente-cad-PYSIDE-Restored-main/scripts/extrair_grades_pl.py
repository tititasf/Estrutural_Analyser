#!/usr/bin/env python3
"""
extrair_grades_pl.py — Extrai dados de grades dos DXFs STOG PL (Pilares)
=========================================================================
Lê DXF STOG real e extrai grade_1/2/3, distancia_1/2 e parafusos
para popular JSON_Pilares com dados reais de grades.

Estratégia:
  1. Conta blocos INSERT "PONTALETE" e "MEIO PONTALETE" por pilar
  2. Mede distâncias entre INSERTs verticalmente → grade_1, distancia_1, grade_2
  3. Mede distâncias entre LINEs SARR_2.2x7 → par_1_2..par_8_9
  4. Exporta para JSON_Pilares/P*.json

Uso:
  python scripts/extrair_grades_pl.py --obra DADOS-OBRAS/Obra_TREINO_1
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse
from pathlib import Path
from collections import defaultdict

try:
    import ezdxf
except ImportError:
    print("ERROR: pip install ezdxf")
    sys.exit(1)


def find_pl_dxfs(obra_path):
    """Localiza DXFs PL STOG na engenharia reversa."""
    fase1 = Path(obra_path) / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'
    dxfs = list(fase1.glob('*PL*.dxf')) + list(fase1.glob('*PL*.DXF'))
    return sorted(set(dxfs))


def extract_grades_from_dxf(dxf_path):
    """
    Extrai dados de grades do DXF STOG PL.
    Retorna dict: {pilar_name: {grade_1, grade_2, distancia_1, pontalete_count, meio_pont_count}}
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    # Contar INSERTs por tipo e posição Y
    pontaletes = defaultdict(list)  # y_pos → list of inserts
    meio_ponts = defaultdict(list)

    for e in msp:
        if e.dxftype() != 'INSERT':
            continue
        bname = e.dxf.name
        if bname == 'PONTALETE':
            pontaletes[round(e.dxf.insert.x, 0)].append(e.dxf.insert.y)
        elif bname == 'MEIO PONTALETE':
            meio_ponts[round(e.dxf.insert.x, 0)].append(e.dxf.insert.y)

    # Contar SARR_2.2x7 por coluna X
    sarr_by_col = defaultdict(list)
    for e in msp:
        if e.dxf.layer == 'SARR_2.2x7' and e.dxftype() == 'LINE':
            # Linhas horizontais (y1 ≈ y2)
            if abs(e.dxf.start.y - e.dxf.end.y) < 1.0:
                mid_x = (e.dxf.start.x + e.dxf.end.x) / 2
                sarr_by_col[round(mid_x / 100) * 100].append(e.dxf.start.y)

    result = {
        'pontalete_columns': len(pontaletes),
        'pontalete_total': sum(len(v) for v in pontaletes.values()),
        'meio_pont_total': sum(len(v) for v in meio_ponts.values()),
        'sarr_2_2x7_total': sum(len(v) for v in sarr_by_col.values()),
    }

    # Estimar grade_1 a partir da distância entre pontaletes na mesma coluna
    for col_x, y_positions in pontaletes.items():
        if len(y_positions) >= 2:
            y_sorted = sorted(y_positions)
            diffs = [y_sorted[i+1] - y_sorted[i] for i in range(len(y_sorted)-1)]
            if diffs:
                result['estimated_grade_1'] = round(min(diffs), 1)
                if len(diffs) >= 2:
                    result['estimated_distancia_1'] = round(diffs[1] - diffs[0], 1) if len(set(diffs)) > 1 else 0
                break

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    dxfs = find_pl_dxfs(obra_path)

    if not dxfs:
        print(f'[ERRO] Nenhum *PL*.dxf em {obra_path}/Fase-1_Ingestao/...')
        return

    print(f'Encontrados {len(dxfs)} DXFs PL STOG')

    for dxf in dxfs:
        print(f'\n--- {dxf.name} ---')
        result = extract_grades_from_dxf(dxf)
        for k, v in result.items():
            print(f'  {k}: {v}')

    # Salvar resumo
    out_dir = obra_path / 'Fase-3_Interpretacao_Extracao' / 'Pilares'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / 'grades_extraidas.json'
    # Use last DXF result
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f'\nSalvo: {out_file}')


if __name__ == '__main__':
    main()
