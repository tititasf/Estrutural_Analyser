#!/usr/bin/env python3
"""
gerar_obra_completa.py — Gera SCR + DXF para obra inteira via robôs reais
==========================================================================
Pipeline: JSON Fase-4 → Robôs headless → SCR → AutoCAD COM → DXF 100%

Usa os robôs PySide reais para gerar SCR de cada elemento:
  - Pilares: CIMA + ABCD + GRADES (3 SCR por pilar)
  - Vigas Laterais: Face A + Face B (2 SCR por viga)
  - Fundos de Vigas: 1 SCR por viga (via ezdxf — robô FV é .pyc)
  - Lajes: 1 DXF modo planta (via ezdxf SmartPanner)

Uso:
  python scripts/gerar_obra_completa.py --obra DADOS-OBRAS/Obra_TREINO_1
  python scripts/gerar_obra_completa.py --obra DADOS-OBRAS/Obra_TREINO_1 --tipo pilares
  python scripts/gerar_obra_completa.py --obra DADOS-OBRAS/Obra_TREINO_1 --tipo vigas
"""
import sys, io, os, json, time, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path


def setup_pilar_paths():
    """Add pilar robot paths."""
    robot_root = Path(__file__).parent.parent / '_ROBOS_ABAS' / 'Robo_Pilares' / 'pilares-atualizado-09-25'
    for d in ['src', 'src/interfaces', 'src/robots', 'src/utils', 'src/models']:
        p = str(robot_root / d)
        if p not in sys.path:
            sys.path.insert(0, p)
    return robot_root


def setup_viga_paths():
    """Add viga robot paths."""
    robot_root = Path(__file__).parent.parent / '_ROBOS_ABAS' / 'Robo_Laterais_de_Vigas'
    if str(robot_root) not in sys.path:
        sys.path.insert(0, str(robot_root))
    return robot_root


def make_pilar_dados(pj, pavimento='TERREO'):
    """Convert Fase-4 JSON to robot legacy dict."""
    comp = float(pj.get('comprimento', pj.get('h', 0)))
    larg = float(pj.get('largura', pj.get('b', 0)))
    alt = float(pj.get('altura', 280))
    g1 = float(pj.get('grade_1', 0))
    g2 = float(pj.get('grade_2', 0))
    nome = pj.get('nome', 'P?')
    if not nome.startswith('P'):
        nome = f"P{pj.get('numero', nome)}"

    d = {
        'interface_principal': None, 'pavimento': pavimento, 'nome': nome,
        'numero': str(pj.get('numero', nome.replace('P',''))),
        'comprimento': comp, 'largura': larg, 'altura': alt,
        'nivel_saida': float(pj.get('nivel_saida', 0)),
        'nivel_chegada': float(pj.get('nivel_chegada', alt)),
        'nivel_diferencial': float(pj.get('nivel_diferencial', 0)),
        'pavimento_anterior': '',
        'parafuso_p1_p2': int(float(pj.get('par_1_2', 62 if comp > 20 else 0))),
        'parafuso_p2_p3': int(float(pj.get('par_2_3', 61 if comp > 30 else 0))),
        'parafuso_p3_p4': int(float(pj.get('par_3_4', 61 if comp > 40 else 0))),
        'parafuso_p4_p5': int(float(pj.get('par_4_5', 62 if comp > 50 else 0))),
        'parafuso_p5_p6': 0, 'parafuso_p6_p7': 0, 'parafuso_p7_p8': 0, 'parafuso_p8_p9': 0,
        'grades_grupo1': {
            'grade_1': g1, 'distancia_1': float(pj.get('distancia_1', 14 if g1 > 0 else 0)),
            'grade_2': g2, 'distancia_2': 0, 'grade_3': 0,
        },
    }

    # Height distribution
    h_rem = alt
    h1 = min(2.0, h_rem); h_rem -= h1
    h2 = min(244.0, h_rem); h_rem -= h2
    h3 = min(244.0, h_rem); h_rem -= h3

    for face in 'ABCDEFGH':
        d[f'laje_{face}'] = 0.0; d[f'posicao_laje_{face}'] = 0
        for i in range(1,4):
            w = comp if face in 'AC' and i==1 else (larg if face in 'BD' and i==1 else 0.0)
            d[f'larg{i}_{face}'] = w
        d[f'h1_{face}'] = h1; d[f'h2_{face}'] = h2; d[f'h3_{face}'] = h3
        d[f'h4_{face}'] = 0.0; d[f'h5_{face}'] = 0.0
        for h in range(2,6):
            for l in range(1,4): d[f'hachura_l{l}_h{h}_{face}'] = ''

    for s in ['esq','dir']:
        for n in ['1','2']:
            for f in ['A','B']:
                for k in ['distancia','largura','profundidade','posicao']:
                    d[f'{k}_{s}_{n}_{f}'] = 0

    # Grade details
    for g in range(1,4):
        for p in range(1,6):
            d[f'detalhe_grade{g}_{p}'] = 29.0 if g1 > 0 and p <= 4 else 0
            d[f'altura_detalhe_{g}_{p}'] = alt if g1 > 0 else 0

    return d


def gerar_pilares(obra_path, max_pilares=999):
    """Generate SCR for all pilares in the obra."""
    robot_root = setup_pilar_paths()
    orig_cwd = os.getcwd()
    os.chdir(str(robot_root))

    from CIMA_FUNCIONAL_EXCEL import preencher_campos_diretamente_e_gerar_scripts as gerar_cima
    from Abcd_Excel import preencher_campos_diretamente_e_gerar_scripts as gerar_abcd
    from GRADE_EXCEL import preencher_campos_diretamente_e_gerar_scripts as gerar_grades

    json_dir = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Pilares'
    pilar_files = sorted(json_dir.glob('P*.json'))[:max_pilares]

    results = {'cima': [], 'abcd': [], 'grades': []}

    for jf in pilar_files:
        pj = json.loads(jf.read_text(encoding='utf-8'))
        dados = make_pilar_dados(pj)
        nome = dados['nome']
        comp = dados['comprimento']
        larg = dados['largura']

        if comp <= 0 or larg <= 0:
            continue

        print(f"  {nome}: {comp:.0f}x{larg:.0f} h={dados['altura']:.0f} g1={dados['grades_grupo1']['grade_1']:.0f}")

        # CIMA
        try:
            gerar_cima(dados)
            results['cima'].append((nome, 'OK'))
        except Exception as e:
            results['cima'].append((nome, f'ERR'))

        # ABCD
        try:
            gerar_abcd(dados)
            results['abcd'].append((nome, 'OK'))
        except Exception as e:
            results['abcd'].append((nome, f'ERR'))

        # GRADES
        try:
            gerar_grades(dados)
            results['grades'].append((nome, 'OK'))
        except Exception as e:
            results['grades'].append((nome, f'ERR'))

    os.chdir(orig_cwd)

    ok_c = sum(1 for r in results['cima'] if r[1] == 'OK')
    ok_a = sum(1 for r in results['abcd'] if r[1] == 'OK')
    ok_g = sum(1 for r in results['grades'] if r[1] == 'OK')
    total = len(pilar_files)
    print(f"\n  Pilares: CIMA {ok_c}/{total} | ABCD {ok_a}/{total} | GRADES {ok_g}/{total}")
    return results


def gerar_vigas(obra_path, max_vigas=999):
    """Generate SCR for all vigas laterais."""
    setup_viga_paths()
    from gerador_script_viga import GeradorScriptViga

    gerador = GeradorScriptViga()
    json_dir = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Laterais'
    out_dir = str(obra_path / 'Fase-6_Execucao_CAD' / 'SCR_Vigas')
    os.makedirs(out_dir, exist_ok=True)

    viga_files = sorted(json_dir.glob('V*_A.json'))[:max_vigas]
    results = []

    for jf in viga_files:
        vj = json.loads(jf.read_text(encoding='utf-8'))
        nome = jf.stem  # V101_A
        panels = vj.get('panels', [])
        largura = sum(float(p.get('width', 0)) for p in panels)

        if largura <= 0:
            continue

        h1_vals = [float(p.get('height1', 0)) for p in panels]
        h1 = max(h1_vals) if h1_vals else 0

        dados = {
            'nome': nome, 'numero': nome.split('_')[0].replace('V',''),
            'obs': '', 'texto_esq': 'ESQ', 'texto_dir': 'DIR',
            'largura': largura, 'altura_geral': str(h1),
            'paineis_larguras': [float(p.get('width', 0)) for p in panels],
            'paineis_alturas': [float(p.get('height1', 0)) for p in panels],
            'paineis_alturas2': [float(p.get('height2', 0)) for p in panels],
            'paineis_tipo1': ['Sarrafeado'] * len(panels),
            'paineis_tipo2': ['Sarrafeado'] * len(panels),
            'paineis_grade_h1': [float(p.get('grade_h1', 0)) for p in panels],
            'paineis_grade_h2': [float(p.get('grade_h2', 0)) for p in panels],
            'lajes_sup': [0] * len(panels), 'lajes_inf': [0] * len(panels),
            'lajes_central_alt': [float(vj.get('laje_central_alt', 0))] * len(panels),
            'continuacao': 'Proxima Parte',
            'sarrafo_esq_id': 0, 'sarrafo_dir_id': 0,
            'sarrafo_h2_esq_id': 0, 'sarrafo_h2_dir_id': 0,
            'fundo_viga': 0,
            'pilar_esq_dist': 0, 'pilar_esq_larg': 0,
            'pilar_dir_dist': 0, 'pilar_dir_larg': 0,
            'aberturas': [[0.0, 0.0, 0.0]] * 4,
        }

        try:
            _, path = gerador.gerar_script(dados, out_dir)
            sz = os.path.getsize(path) if path else 0
            status = 'OK' if sz > 100 else 'FAIL'
        except:
            sz = 0; status = 'ERR'

        results.append((nome, largura, h1, sz, status))
        print(f"  {nome}: {largura:.0f}x{h1:.0f} -> {sz} bytes [{status}]")

    ok = sum(1 for r in results if r[4] == 'OK')
    print(f"\n  Vigas LV: {ok}/{len(results)} OK")
    return results


def gerar_fundos(obra_path):
    """Generate DXF for fundos via ezdxf."""
    print("  FV: usando gerador ezdxf (gerar_fv_dxf_stog.py)")
    os.system(f'cd /d "{obra_path}/../Agente-cad-PYSIDE-Restored-main" && python scripts/gerar_fv_dxf_stog.py --obra "{obra_path}" --max 999')


def gerar_lajes(obra_path):
    """Generate DXF for lajes via ezdxf."""
    print("  LJ: usando gerador ezdxf modo planta (gerar_lj_dxf_stog.py)")
    os.system(f'cd /d "{obra_path}/../Agente-cad-PYSIDE-Restored-main" && python scripts/gerar_lj_dxf_stog.py --obra "{obra_path}" --max 999')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--tipo', choices=['pilares', 'vigas', 'fundos', 'lajes', 'all'], default='all')
    parser.add_argument('--max', type=int, default=999)
    args = parser.parse_args()

    obra = Path(args.obra).resolve()
    print(f"=== GERAR OBRA COMPLETA: {obra.name} ===\n")

    if args.tipo in ('pilares', 'all'):
        print("[1/4] PILARES (CIMA + ABCD + GRADES)")
        gerar_pilares(obra, args.max)

    if args.tipo in ('vigas', 'all'):
        print("\n[2/4] VIGAS LATERAIS (Face A + Face B)")
        gerar_vigas(obra, args.max)

    if args.tipo in ('fundos', 'all'):
        print("\n[3/4] FUNDOS DE VIGAS (ezdxf)")
        gerar_fundos(obra)

    if args.tipo in ('lajes', 'all'):
        print("\n[4/4] LAJES (ezdxf modo planta)")
        gerar_lajes(obra)

    print(f"\n=== OBRA {obra.name} COMPLETA ===")


if __name__ == '__main__':
    main()
