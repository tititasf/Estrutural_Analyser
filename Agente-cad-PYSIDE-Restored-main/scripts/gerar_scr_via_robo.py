#!/usr/bin/env python3
"""
gerar_scr_via_robo.py — Gera SCR usando os robôs PySide REAIS
==============================================================
Usa os geradores originais (Robo_Pilar_Visao_Cima, Robo_Pilar_ABCD, ROBO_GRADES)
com dados do JSON Fase-4 para gerar SCR 100% corretos.

Uso:
  python scripts/gerar_scr_via_robo.py --obra DADOS-OBRAS/Obra_TREINO_1 --pilar P11
  python scripts/gerar_scr_via_robo.py --obra DADOS-OBRAS/Obra_TREINO_1 --all
"""
import sys, io, os, json, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

# Add robot source to path
ROBOT_ROOT = Path(__file__).parent.parent / '_ROBOS_ABAS' / 'Robo_Pilares' / 'pilares-atualizado-09-25'
ROBOT_SRC = ROBOT_ROOT / 'src'
if str(ROBOT_SRC) not in sys.path:
    sys.path.insert(0, str(ROBOT_SRC))
if str(ROBOT_SRC / 'robots') not in sys.path:
    sys.path.insert(0, str(ROBOT_SRC / 'robots'))
if str(ROBOT_SRC / 'models') not in sys.path:
    sys.path.insert(0, str(ROBOT_SRC / 'models'))

# Templates dir
SCRIPTS_OUTPUT = None  # set per obra


def load_pilar_from_json(json_path, vigas_salvas=None):
    """Load pilar data from Fase-4 JSON and vigas_salvas."""
    d = json.loads(Path(json_path).read_text(encoding='utf-8'))
    nome = Path(json_path).stem

    # Get dimensions from the JSON or vigas_salvas
    comp = float(d.get('comprimento', d.get('h', 0)))
    larg = float(d.get('largura', d.get('b', 0)))
    altura = float(d.get('altura', 280))  # default pe-direito

    # Build legacy dict that the robot expects
    legacy = {
        'interface_principal': None,
        'pavimento': d.get('pavimento', 'TERREO'),
        'nome': nome,
        'numero': d.get('numero', nome.replace('P', '')),
        'comprimento': comp,
        'largura': larg,
        'pavimento_anterior': '',
        'nivel_saida': float(d.get('nivel_saida', 0)),
        'nivel_chegada': float(d.get('nivel_chegada', 0)),
        'nivel_diferencial': float(d.get('nivel_diferencial', 0)),
        'altura': altura,

        # Parafusos
        'parafuso_p1_p2': int(float(d.get('par_1_2', 0))),
        'parafuso_p2_p3': int(float(d.get('par_2_3', 0))),
        'parafuso_p3_p4': int(float(d.get('par_3_4', 0))),
        'parafuso_p4_p5': int(float(d.get('par_4_5', 0))),
        'parafuso_p5_p6': int(float(d.get('par_5_6', 0))),
        'parafuso_p6_p7': int(float(d.get('par_6_7', 0))),
        'parafuso_p7_p8': int(float(d.get('par_7_8', 0))),
        'parafuso_p8_p9': int(float(d.get('par_8_9', 0))),

        # Grades
        'grades_grupo1': {
            'grade_1': float(d.get('grade_1', 0)),
            'distancia_1': float(d.get('distancia_1', 14)),
            'grade_2': float(d.get('grade_2', 0)),
            'distancia_2': float(d.get('distancia_2', 0)),
            'grade_3': float(d.get('grade_3', 0)),
        },
    }

    # Face heights (distribute altura into h1-h5)
    h_remaining = altura
    h1 = min(2.0, h_remaining) if h_remaining > 2 else 0
    h_remaining -= h1
    h2 = min(244.0, h_remaining)
    h_remaining -= h2
    h3 = min(244.0, h_remaining)
    h_remaining -= h3
    h4 = min(244.0, h_remaining)
    h_remaining -= h4
    h5 = max(0, h_remaining)

    # Apply to all faces A-H
    for face in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
        legacy[f'laje_{face}'] = 0.0
        legacy[f'posicao_laje_{face}'] = 0.0

        # Widths: A/C use comprimento, B/D use largura
        if face in ('A', 'C'):
            legacy[f'larg1_{face}'] = comp
        elif face in ('B', 'D'):
            legacy[f'larg1_{face}'] = larg
        else:
            legacy[f'larg1_{face}'] = 0.0
        legacy[f'larg2_{face}'] = 0.0
        legacy[f'larg3_{face}'] = 0.0

        # Heights
        legacy[f'h1_{face}'] = h1
        legacy[f'h2_{face}'] = h2
        legacy[f'h3_{face}'] = h3
        legacy[f'h4_{face}'] = h4
        legacy[f'h5_{face}'] = h5

        # Hatches (empty)
        for h in range(2, 6):
            for l in range(1, 4):
                legacy[f'hachura_l{l}_h{h}_{face}'] = ''

    # Openings (empty)
    for side in ['esq', 'dir']:
        for n in ['1', '2']:
            for face in ['A', 'B']:
                legacy[f'distancia_{side}_{n}_{face}'] = 0
                legacy[f'largura_{side}_{n}_{face}'] = 0
                legacy[f'profundidade_{side}_{n}_{face}'] = 0
                legacy[f'posicao_{side}_{n}_{face}'] = 0

    return legacy


def gerar_cima(legacy_data, output_dir):
    """Gera SCR CIMA usando o robô real."""
    try:
        from Robo_Pilar_Visao_Cima import GeradorPilar

        nome = legacy_data['nome']
        gen = GeradorPilar()

        # Configure output
        scr_path = os.path.join(output_dir, f'{nome}_CIMA.scr')
        gen.pasta_destino = output_dir
        gen.nome_arquivo = f'{nome}_CIMA'

        # Generate
        gen.preencher_campos(legacy_data)
        gen.gerar_script()

        if os.path.exists(scr_path):
            return scr_path
        # Try alternative names
        for f in Path(output_dir).glob(f'*{nome}*CIMA*'):
            return str(f)
        return None
    except Exception as e:
        print(f"  CIMA erro: {e}")
        return None


def gerar_abcd(legacy_data, output_dir):
    """Gera SCR ABCD usando o robô real."""
    try:
        from Robo_Pilar_ABCD import GeradorPilares

        nome = legacy_data['nome']
        gen = GeradorPilares()

        scr_path = os.path.join(output_dir, f'{nome}_ABCD.scr')
        gen.pasta_destino = output_dir
        gen.nome_arquivo = f'{nome}_ABCD'

        gen.preencher_campos(legacy_data)
        gen.gerar_script()

        if os.path.exists(scr_path):
            return scr_path
        for f in Path(output_dir).glob(f'*{nome}*ABCD*'):
            return str(f)
        return None
    except Exception as e:
        print(f"  ABCD erro: {e}")
        return None


def gerar_grades(legacy_data, output_dir):
    """Gera SCR GRADES usando o robô real."""
    try:
        from ROBO_GRADES import gerar_script_grade

        nome = legacy_data['nome']
        scr_path = os.path.join(output_dir, f'{nome}_GRADES.scr')

        # Extract grade data
        grades_g1 = legacy_data.get('grades_grupo1', {})
        grade_1 = float(grades_g1.get('grade_1', 0))

        if grade_1 <= 0:
            print(f"  GRADES skip (grade_1=0)")
            return None

        gerar_script_grade(
            pavimento=legacy_data['pavimento'],
            nome=nome,
            grades_ativas=[grades_g1],
            altura_base=legacy_data['altura'],
            x_inicial_custom=0,
            y_inicial_custom=0,
            distancias=[float(grades_g1.get('distancia_1', 14))],
        )

        for f in Path(output_dir).glob(f'*{nome}*GRADE*'):
            return str(f)
        return None
    except Exception as e:
        print(f"  GRADES erro: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--pilar', help='Nome do pilar (ex: P11)')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--tipo', choices=['CIMA', 'ABCD', 'GRADES', 'ALL'], default='ALL')
    args = parser.parse_args()

    obra = Path(args.obra)
    json_dir = obra / 'Fase-4_Sincronizacao' / 'JSON_Pilares'
    output_dir = str(obra / 'Fase-6_Execucao_CAD' / 'SCR_Robot')
    os.makedirs(output_dir, exist_ok=True)

    if args.pilar:
        files = [json_dir / f'{args.pilar}.json']
    elif args.all:
        files = sorted(json_dir.glob('P*.json'))
    else:
        files = sorted(json_dir.glob('P*.json'))[:3]

    print(f"Gerando SCR via robôs reais para {len(files)} pilares...")

    for jf in files:
        if not jf.exists():
            print(f"  SKIP: {jf.name}")
            continue

        legacy = load_pilar_from_json(jf)
        nome = legacy['nome']
        comp = legacy['comprimento']
        larg = legacy['largura']
        print(f"\n  {nome}: {comp:.0f}x{larg:.0f}cm altura={legacy['altura']:.0f}")

        if args.tipo in ('CIMA', 'ALL'):
            r = gerar_cima(legacy, output_dir)
            print(f"    CIMA: {'OK' if r else 'FAIL'} {r or ''}")

        if args.tipo in ('ABCD', 'ALL'):
            r = gerar_abcd(legacy, output_dir)
            print(f"    ABCD: {'OK' if r else 'FAIL'} {r or ''}")

        if args.tipo in ('GRADES', 'ALL'):
            r = gerar_grades(legacy, output_dir)
            print(f"    GRADES: {'OK' if r else 'FAIL'} {r or ''}")

    print(f"\nSCR salvos em: {output_dir}")


if __name__ == '__main__':
    main()
