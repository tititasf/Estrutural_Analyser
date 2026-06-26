#!/usr/bin/env python3
"""
regenerar_e_validar.py — Regenera os 4 DXFs de uma obra e valida os elementos.

Uso:
  python scripts/regenerar_e_validar.py --obra DADOS-OBRAS/Obra_TREINO_1
  python scripts/regenerar_e_validar.py --todas               # todas as obras
  python scripts/regenerar_e_validar.py --todas --skip-gen    # só valida (sem regenerar)
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import subprocess
from pathlib import Path

OBRAS_DIR = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
SCRIPTS   = Path(__file__).parent

GERADORES = {
    'PL': 'gerar_pl_dxf_stog.py',
    'LV': 'gerar_lv_dxf_stog.py',
    'FV': 'gerar_fv_dxf_stog.py',
    'LJ': 'gerar_lj_dxf_stog.py',
}

METAS = {'PL': 90.0, 'LV': 90.0, 'FV': 90.0, 'LJ': 90.0}


DXF_NAMES = {
    'PL': 'PL_stog_quality.dxf', 'LV': 'LV_stog_quality.dxf',
    'FV': 'FV_stog_quality.dxf', 'LJ': 'LJ_stog_quality.dxf',
}


def run_gerador(tipo: str, obra_path: Path) -> bool:
    script = SCRIPTS / GERADORES[tipo]
    if not script.exists():
        print(f'  [{tipo}] SKIP — gerador não encontrado: {script.name}')
        return True
    try:
        r = subprocess.run(
            [sys.executable, str(script), '--obra', str(obra_path)],
            capture_output=True, encoding='utf-8', errors='replace', timeout=600
        )
        if r.returncode != 0:
            print(f'  [{tipo}] ERRO gerador:\n{r.stderr[-300:]}')
            return False
        # Verifica se o DXF foi realmente criado (alguns geradores saem 0 sem criar arquivo)
        dxf_path = obra_path / 'Fase-6_Execucao_CAD' / DXF_NAMES[tipo]
        if not dxf_path.exists():
            # Verifica se é por falta de dados (ERRO na saída)
            if '[ERRO]' in r.stdout or 'Nenhum' in r.stdout:
                print(f'  [{tipo}] N/A (sem dados)')
                return None  # None = sem dados (diferente de False = erro)
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f'  [{tipo}] TIMEOUT gerando DXF')
        return False
    except Exception as e:
        print(f'  [{tipo}] EXCECAO: {e}')
        return False


def run_validator(obra_path: Path) -> dict:
    """Retorna dict: tipo -> {score, aprovado, fails, warns}"""
    try:
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / 'validar_elementos_dxf.py'),
             '--obra', str(obra_path), '--pav', '1PAV', '--json'],
            capture_output=True, encoding='utf-8', errors='replace', timeout=120
        )
        data = json.loads(r.stdout)
        result = {}
        for rep in data:
            result[rep['tipo']] = {
                'score': rep['score_pct'],
                'aprovado': rep['aprovado'],
                'fails': [c for c in rep['checks'] if c['status'] == 'FAIL'],
                'warns': [c for c in rep['checks'] if c['status'] == 'WARN'],
            }
        return result
    except Exception as e:
        print(f'  [VALIDATOR] ERRO: {e}')
        return {}


def processar_obra(obra_path: Path, skip_gen: bool = False, tipos: list = None) -> dict:
    tipos = tipos or list(GERADORES.keys())
    print(f'\n{"="*60}')
    print(f'  OBRA: {obra_path.name}')
    print(f'{"="*60}')

    fase6 = obra_path / 'Fase-6_Execucao_CAD'
    if not fase6.exists():
        print(f'  SKIP — Fase-6 não encontrada')
        return {}

    skipped_tipos = set()
    if not skip_gen:
        for tipo in tipos:
            print(f'  [{tipo}] Gerando DXF...', end=' ', flush=True)
            ok = run_gerador(tipo, obra_path)
            if ok is None:
                print('N/A')
                skipped_tipos.add(tipo)
            else:
                print('OK' if ok else 'FALHOU')
    tipos_validos = [t for t in tipos if t not in skipped_tipos]

    print(f'  Validando...')
    resultado = run_validator(obra_path)

    DXF_NAMES = {
        'PL': 'PL_stog_quality.dxf', 'LV': 'LV_stog_quality.dxf',
        'FV': 'FV_stog_quality.dxf', 'LJ': 'LJ_stog_quality.dxf',
    }

    print(f'\n  RESULTADO:')
    for tipo in tipos:
        r = resultado.get(tipo, {})
        if not r:
            print(f'    {tipo}: N/A')
            continue
        # Se o único check é MISSING, marcar como N/A em vez de 0%
        checks = r.get('fails', []) + r.get('warns', [])
        if len(r.get('fails', [])) == 1 and r['fails'][0]['id'].endswith('-MISSING'):
            dxf_path = fase6 / DXF_NAMES[tipo]
            if not dxf_path.exists():
                print(f'    {tipo}: N/A (sem dados para este tipo)')
                resultado[tipo]['score'] = None
                continue
        status = 'APROVADO' if r['aprovado'] else 'REPROVADO'
        n_fail = len(r['fails'])
        n_warn = len(r['warns'])
        print(f'    {tipo}: {r["score"]:.1f}% [{status}] — {n_fail} falhas, {n_warn} avisos')
        for f in r['fails']:
            print(f'      FAIL [{f["id"]}] {f["desc"]} (found={f["found"]}, exp={f["expected"]})')
        for w in r['warns']:
            print(f'      WARN [{w["id"]}] {w["desc"]} (found={w["found"]}, exp={w["expected"]})')

    return resultado


def main():
    parser = argparse.ArgumentParser()
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument('--obra', help='Path de uma obra específica')
    grp.add_argument('--todas', action='store_true', help='Todas as obras treino')
    parser.add_argument('--skip-gen', action='store_true',
                        help='Pular regeneração (só validar)')
    parser.add_argument('--tipos', nargs='+', choices=['PL','LV','FV','LJ'],
                        help='Tipos a processar (default: todos)')
    args = parser.parse_args()

    tipos = args.tipos or list(GERADORES.keys())

    if args.obra:
        processar_obra(Path(args.obra), skip_gen=args.skip_gen, tipos=tipos)
    else:
        obras = sorted([
            d for d in OBRAS_DIR.iterdir()
            if d.is_dir() and d.name.startswith('Obra_TREINO_')
        ])
        print(f'Processando {len(obras)} obras...')

        sumario = {}
        for obra in obras:
            r = processar_obra(obra, skip_gen=args.skip_gen, tipos=tipos)
            sumario[obra.name] = r

        # Sumário global
        print(f'\n{"="*60}')
        print('  SUMÁRIO GLOBAL')
        print(f'{"="*60}')
        header = f'{"Obra":<20}' + ''.join(f'  {t:>8}' for t in tipos)
        print(f'  {header}')
        print(f'  {"-"*60}')

        aprovados_por_tipo = {t: 0 for t in tipos}
        total_obras = len([s for s in sumario.values() if s])

        for obra_name, res in sorted(sumario.items()):
            if not res:
                continue
            row = f'  {obra_name:<20}'
            for tipo in tipos:
                r = res.get(tipo, {})
                if r and r.get('score') is not None:
                    sc = r['score']
                    ok = '✓' if r['aprovado'] else '✗'
                    row += f'  {sc:>5.1f}%{ok}'
                    if r['aprovado']:
                        aprovados_por_tipo[tipo] += 1
                else:
                    row += f'  {"N/A":>7} '
            print(row)

        print(f'\n  Taxa de aprovação por tipo:')
        for tipo in tipos:
            pct = 100 * aprovados_por_tipo[tipo] / max(total_obras, 1)
            print(f'    {tipo}: {aprovados_por_tipo[tipo]}/{total_obras} ({pct:.0f}%)')


if __name__ == '__main__':
    main()
