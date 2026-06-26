#!/usr/bin/env python3
"""
ciclo_refinamento.py — Ciclo completo de refinamento ezdxf vs AutoCAD ground truth
====================================================================================
Pipeline:
  1. Carrega cenários JSON (parâmetros dos 50 cenários)
  2. Gera DXF ezdxf para cada cenário
  3. Compara com DXF ground truth (SCR→AutoCAD)
  4. Imprime relatório de gaps por layer/type/block
  5. Sugere correções priorizadas

Uso:
  python scripts/ciclo_refinamento.py --tipo CIMA
  python scripts/ciclo_refinamento.py --tipo ABCD --max 5
  python scripts/ciclo_refinamento.py --tipo ALL --report relatorio_gaps.json
  python scripts/ciclo_refinamento.py --tipo CIMA --cenario P01  # Analisa 1 cenário
"""
import sys, io, json, argparse, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from collections import Counter, defaultdict

try:
    import ezdxf
except ImportError:
    print("pip install ezdxf")
    sys.exit(1)

ROOT = Path(__file__).parent.parent
SCRIPTS_ROBOS = ROOT / '_ROBOS_ABAS' / 'Robo_Pilares' / 'pilares-atualizado-09-25' / 'SCRIPTS_ROBOS'
SCRIPTS_LV = ROOT / '_ROBOS_ABAS' / 'Robo_Laterais_de_Vigas' / 'SCRIPTS'
GROUND_TRUTH_DIR = ROOT / 'GROUND_TRUTH'
EZDXF_OUT_DIR = ROOT / 'EZDXF_OUTPUT'

sys.path.insert(0, str(ROOT / 'scripts'))


# ────────────────────────────────────────────────────────────
# CARREGADORES DE CENÁRIOS
# ────────────────────────────────────────────────────────────

def load_cenarios_pilares():
    """Carrega os 50 cenários de pilares com parâmetros completos."""
    resumo = SCRIPTS_ROBOS / 'cenarios_pilares_resumo.json'
    if not resumo.exists():
        return []
    data = json.loads(resumo.read_text(encoding='utf-8'))
    cenarios = []
    for row in data:
        nome, desc, comp, larg, alt, g1 = row[0], row[1], row[2], row[3], row[4], row[5]
        cenarios.append({
            'nome': nome, 'desc': desc,
            'comp': float(comp), 'larg': float(larg),
            'alt': float(alt), 'g1': float(g1),
            'g2': 0.0,
        })
    return cenarios


def load_cenarios_lv():
    """Carrega os 50 cenários LV."""
    resumo_path = SCRIPTS_LV / 'CENARIOS_LV' / 'cenarios_lv_resumo.json'
    if not resumo_path.exists():
        return []
    data = json.loads(resumo_path.read_text(encoding='utf-8'))
    # Estrutura: [nome, largura, altura_geral, bytes, status]
    cenarios = []
    for row in data:
        nome, larg, alt_str = row[0], row[1], row[2]
        cenarios.append({
            'nome': nome,
            'largura': float(larg),
            'altura_geral': float(alt_str) if str(alt_str).replace('.','').isdigit() else 120.0,
        })
    return cenarios


def load_cenarios_vc():
    """Carrega os 50 cenários VC."""
    resumo_path = SCRIPTS_LV / 'CENARIOS_VC_HEADLESS' / 'cenarios_vc_resumo.json'
    if not resumo_path.exists():
        return []
    data = json.loads(resumo_path.read_text(encoding='utf-8'))
    return data  # [nome_vc, nome_viga, h_A, h_B, b_alma, bytes, status]


def load_cenarios_fv():
    """Carrega os 50 cenários FV."""
    resumo_path = ROOT / 'DADOS-OBRAS' / 'cenarios_fv' / 'cenarios_fv_resumo.json'
    if not resumo_path.exists():
        return []
    return json.loads(resumo_path.read_text(encoding='utf-8'))


def load_cenarios_lj():
    """Carrega os 50 cenários LJ."""
    resumo_path = ROOT / 'DADOS-OBRAS' / 'cenarios_lajes' / 'cenarios_lajes_resumo.json'
    if not resumo_path.exists():
        return []
    return json.loads(resumo_path.read_text(encoding='utf-8'))


# ────────────────────────────────────────────────────────────
# GERADORES EZDXF
# ────────────────────────────────────────────────────────────

def gerar_ezdxf_pilar(cenario, output_path):
    """Gera DXF pilar (3 zonas CIMA+ABCD+GRADES) via ezdxf."""
    try:
        import importlib
        mod = importlib.import_module('gerar_pl_dxf_stog')

        doc = mod.setup_doc()
        msp = doc.modelspace()

        # Monta pj no formato esperado por generate_pilar
        pj = {
            'nome': cenario['nome'],
            'comprimento': cenario['comp'],
            'largura': cenario['larg'],
            'altura': cenario['alt'],
            'grade_1': cenario.get('g1', 0),
            'grade_2': cenario.get('g2', 0),
        }
        mod.generate_pilar(msp, pj, row_y_offset=0)

        doc.saveas(str(output_path))
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"    EZDXF PL ERR: {e}")
        return False


def gerar_ezdxf_lv(cenario, output_path):
    """Gera DXF LV via ezdxf usando SmartPanner para painéis."""
    try:
        import importlib
        mod = importlib.import_module('gerar_lv_dxf_stog')

        doc = mod.setup_doc()
        msp = doc.modelspace()

        # Painéis simples baseados na largura total
        larg = float(cenario['largura'])
        alt = float(cenario.get('altura_geral', 120))

        # Distribui painéis por regra 244/122/60
        panels_A = [{'width': min(larg, 244), 'height1': alt, 'height2': alt,
                      'tipo1': 'Sarrafeado', 'tipo2': 'Sarrafeado',
                      'grade_h1': 0, 'grade_h2': 0}]
        if larg > 244:
            panels_A.append({'width': larg - 244, 'height1': alt, 'height2': alt,
                              'tipo1': 'Sarrafeado', 'tipo2': 'Sarrafeado',
                              'grade_h1': 0, 'grade_h2': 0})

        panels_B = [p.copy() for p in panels_A]

        mod.draw_viga_lateral(
            msp, x_origin=0, y_top=alt,
            viga_nome=cenario['nome'],
            h_A=alt, h_B=alt, b=larg,
            panels_A=panels_A, panels_B=panels_B,
        )

        doc.saveas(str(output_path))
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"    EZDXF LV ERR: {e}")
        return False


# ────────────────────────────────────────────────────────────
# ANÁLISE DXF
# ────────────────────────────────────────────────────────────

def analisar_dxf(dxf_path):
    """Extrai contagens por layer, tipo, bloco."""
    path = Path(dxf_path)
    if not path.exists() or path.stat().st_size < 100:
        return None

    try:
        doc = ezdxf.readfile(str(path))
    except Exception as e:
        print(f"    ERR ao ler {path.name}: {e}")
        return None

    msp = doc.modelspace()
    entities = list(msp)

    layers = Counter(e.dxf.layer for e in entities)
    types = Counter(e.dxftype() for e in entities)
    inserts = Counter(e.dxf.name for e in entities if e.dxftype() == 'INSERT')

    return {
        'total': len(entities),
        'layers': dict(layers),
        'types': dict(types),
        'inserts': dict(inserts),
    }


def calcular_ratio(da, db):
    """Calcula ratio geral entre dois dados."""
    if da is None or db is None:
        return 0.0
    ta = da['total']
    tb = db['total']
    if ta == 0:
        return 0.0
    return tb / ta


def comparar_analises(da, db, label_a='GT', label_b='EZ'):
    """Compara dois resultados de analisar_dxf."""
    if da is None:
        return {'error': f'{label_a} não disponível'}
    if db is None:
        return {'error': f'{label_b} não disponível'}

    all_layers = sorted(set(list(da['layers'].keys()) + list(db['layers'].keys())))
    layer_gaps = {}
    for ly in all_layers:
        ra = da['layers'].get(ly, 0)
        rb = db['layers'].get(ly, 0)
        if ra > 0:
            ratio = rb / ra
            status = 'OK' if ratio >= 0.85 else ('LOW' if ratio > 0 else 'MISS')
        else:
            ratio = float('inf')
            status = 'EXTRA'
        layer_gaps[ly] = {'gt': ra, 'ez': rb, 'ratio': round(ratio, 3), 'status': status}

    all_types = sorted(set(list(da['types'].keys()) + list(db['types'].keys())))
    type_gaps = {}
    for t in all_types:
        ra = da['types'].get(t, 0)
        rb = db['types'].get(t, 0)
        type_gaps[t] = {'gt': ra, 'ez': rb}

    all_inserts = sorted(set(list(da['inserts'].keys()) + list(db['inserts'].keys())))
    insert_gaps = {}
    for ins in all_inserts:
        ra = da['inserts'].get(ins, 0)
        rb = db['inserts'].get(ins, 0)
        insert_gaps[ins] = {'gt': ra, 'ez': rb}

    ratio_total = calcular_ratio(da, db)

    return {
        'ratio_total': round(ratio_total, 3),
        'total': {label_a: da['total'], label_b: db['total']},
        'layers': layer_gaps,
        'types': type_gaps,
        'inserts': insert_gaps,
    }


# ────────────────────────────────────────────────────────────
# CICLO PRINCIPAL
# ────────────────────────────────────────────────────────────

def ciclo_tipo(tipo, cenarios, max_count=999, cenario_filter=None, verbose=False):
    """Executa ciclo de comparação para um tipo."""
    gt_dir = GROUND_TRUTH_DIR / tipo
    ez_dir = EZDXF_OUT_DIR / tipo
    ez_dir.mkdir(parents=True, exist_ok=True)

    if not gt_dir.exists():
        print(f"  Ground truth não disponível: {gt_dir}")
        print(f"  Execute primeiro: python scripts/gerar_ground_truth_batch.py --tipo {tipo}")
        return {}

    gt_dxfs = sorted(gt_dir.glob('*.dxf'))
    if not gt_dxfs:
        print(f"  Nenhum DXF ground truth em {gt_dir}")
        return {}

    resultados = {}
    count = 0

    for gt_dxf in gt_dxfs[:max_count]:
        nome = gt_dxf.stem  # ex: P01_CIMA
        if cenario_filter and cenario_filter.upper() not in nome.upper():
            continue

        # Encontra cenário correspondente
        cenario_match = None
        for c in cenarios:
            c_nome = c.get('nome', c[0] if isinstance(c, list) else '')
            if c_nome.upper() in nome.upper() or nome.upper().startswith(c_nome.upper()):
                cenario_match = c
                break

        print(f"\n  [{count+1}] {nome}", end=' ')

        # Analisa ground truth
        da = analisar_dxf(gt_dxf)
        if da is None:
            print(f"GT inválido")
            count += 1
            continue

        # Gera ezdxf se cenário encontrado
        ez_dxf = ez_dir / gt_dxf.name
        ez_ok = False

        if cenario_match and tipo in ('CIMA', 'ABCD', 'GRADES'):
            if isinstance(cenario_match, dict):
                ez_ok = gerar_ezdxf_pilar(cenario_match, ez_dxf)
        elif cenario_match and tipo == 'LV':
            if isinstance(cenario_match, dict):
                ez_ok = gerar_ezdxf_lv(cenario_match, ez_dxf)

        # Analisa ezdxf
        db = analisar_dxf(ez_dxf) if ez_ok else None

        # Compara
        comp = comparar_analises(da, db, 'GT', 'EZ')

        ratio = comp.get('ratio_total', 0)
        status_char = '✓' if ratio >= 0.85 else ('~' if ratio >= 0.5 else '✗')
        gt_total = da['total']
        ez_total = db['total'] if db else 0
        print(f"GT={gt_total} EZ={ez_total} ratio={ratio:.2f} {status_char}")

        if verbose:
            _print_layer_diff(comp)

        resultados[nome] = comp
        count += 1

    return resultados


def _print_layer_diff(comp):
    """Imprime diferenças por layer."""
    layers = comp.get('layers', {})
    for ly, v in sorted(layers.items()):
        if v['status'] != 'OK':
            print(f"      {ly:<30} GT={v['gt']:>4} EZ={v['ez']:>4} ratio={v['ratio']:>5.2f} [{v['status']}]")


def gerar_relatorio_gaps(todos_resultados):
    """Agrega gaps de todos os tipos e prioriza correções."""
    # Conta quantas vezes cada layer tem status MISS ou LOW
    layer_miss = defaultdict(lambda: defaultdict(int))  # tipo → layer → count

    for tipo, resultados in todos_resultados.items():
        for nome, comp in resultados.items():
            layers = comp.get('layers', {})
            for ly, v in layers.items():
                if v['status'] in ('MISS', 'LOW'):
                    layer_miss[tipo][ly] += 1

    print(f"\n{'='*60}")
    print("RELATÓRIO DE GAPS — PRIORIDADE DE CORREÇÃO")
    print(f"{'='*60}")

    for tipo, layers in sorted(layer_miss.items()):
        if not layers:
            continue
        print(f"\n[{tipo}] Layers com problemas:")
        for ly, count in sorted(layers.items(), key=lambda x: -x[1]):
            print(f"  {ly:<30} MISS/LOW em {count} cenários")

    return dict(layer_miss)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tipo', choices=['CIMA', 'ABCD', 'GRADES', 'LV', 'VC', 'FV', 'LJ', 'ALL'],
                        default='CIMA')
    parser.add_argument('--max', type=int, default=999)
    parser.add_argument('--cenario', help='Filtrar por nome de cenário (ex: P01)')
    parser.add_argument('--report', help='Salvar relatório de gaps em JSON')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    print(f"=== CICLO DE REFINAMENTO — {args.tipo} ===")
    print(f"Ground truth: {GROUND_TRUTH_DIR}")
    print(f"ezdxf output: {EZDXF_OUT_DIR}")

    tipos = ['CIMA', 'ABCD', 'GRADES', 'LV'] if args.tipo == 'ALL' else [args.tipo]

    todos = {}
    for tipo in tipos:
        print(f"\n{'─'*50}")
        print(f"TIPO: {tipo}")

        if tipo in ('CIMA', 'ABCD', 'GRADES'):
            cenarios = load_cenarios_pilares()
        elif tipo == 'LV':
            cenarios = load_cenarios_lv()
        elif tipo == 'VC':
            cenarios = load_cenarios_vc()
        elif tipo == 'FV':
            cenarios = load_cenarios_fv()
        elif tipo == 'LJ':
            cenarios = load_cenarios_lj()
        else:
            cenarios = []

        print(f"  Cenários disponíveis: {len(cenarios)}")

        resultados = ciclo_tipo(tipo, cenarios, args.max, args.cenario, args.verbose)
        todos[tipo] = resultados

        # Resumo
        if resultados:
            ratios = [v.get('ratio_total', 0) for v in resultados.values()
                      if isinstance(v, dict) and 'ratio_total' in v]
            if ratios:
                avg = sum(ratios) / len(ratios)
                print(f"\n  Média ratio {tipo}: {avg:.3f} ({len(ratios)} cenários comparados)")

    # Relatório de gaps
    gaps = gerar_relatorio_gaps(todos)

    if args.report:
        report_data = {
            'resultados': {t: {n: v for n, v in r.items()}
                          for t, r in todos.items()},
            'gaps': {k: dict(v) for k, v in gaps.items()},
        }
        Path(args.report).write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False), encoding='utf-8'
        )
        print(f"\nRelatório salvo: {args.report}")


if __name__ == '__main__':
    main()
