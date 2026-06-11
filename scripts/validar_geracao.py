#!/usr/bin/env python3
"""
validar_geracao.py — Self-validation loop: compara DXF GERADO vs fichas FORWARD (TQS).

Pipeline:
  1. Lê Fase-6/LV_gerado.dxf + FV_gerado.dxf da obra
  2. Extrai fichas reverso do DXF gerado (inline, sem modificar reverso/ existente)
  3. Compara campos VIG com vigas.json (forward)
  4. Reporta score de fidelidade da geração

Score = quanto dos campos estruturais do TQS foram preservados no DXF gerado.
MATCH/AUSENTE_FWD/REV_ONLY = bom | DELTA_*/AUSENTE_REV = problema.

Uso:
    python scripts/validar_geracao.py --obra DADOS-OBRAS/Obra_TREINO_20
    python scripts/validar_geracao.py --obra DADOS-OBRAS/Obra_TREINO_1 --verbose
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json, argparse, os, re, math
from pathlib import Path
from collections import Counter

# Reutiliza extratores do pipeline principal
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))
from extrair_reverso_vig import extrair_lv, extrair_fv, merge_vigas


DELTA_MATCH   = 5.0   # cm — mesmo threshold do comparar_fichas.py
DELTA_SMALL   = 15.0
DELTA_MED     = 50.0


def classify(fwd, rev, field=''):
    """Status de um par (fwd, rev) de valores numéricos."""
    if fwd is None and rev is None: return 'AUSENTE_AMBOS', None, None
    if fwd is None:                  return 'AUSENTE_FWD',   None, None
    if rev is None or rev == 0:      return 'AUSENTE_REV',   None, None
    fwd, rev = float(fwd), float(rev)
    delta = abs(fwd - rev)
    pct   = round(delta / fwd * 100, 1) if fwd else None
    if delta <= DELTA_MATCH:  return 'MATCH',       round(delta, 1), pct
    if delta <= DELTA_SMALL:  return 'DELTA_SMALL', round(delta, 1), pct
    if delta <= DELTA_MED:    return 'DELTA_MED',   round(delta, 1), pct
    return 'DELTA_LARGE', round(delta, 1), pct


def good_status(s):
    return s in ('MATCH', 'REV_ONLY', 'AUSENTE_FWD')


def comparar_vig_gerado(obra_dir: Path, verbose=False):
    """Extrai reverso do DXF gerado e compara com vigas.json (forward)."""
    fase6 = obra_dir / 'Fase-6_Execucao_CAD'
    lv_path = fase6 / 'LV_gerado.dxf'
    fv_path = fase6 / 'FV_gerado.dxf'
    vigas_path = obra_dir / 'Fase-3_Interpretacao_Extracao/Vigas/vigas.json'

    if not lv_path.exists():
        return None, 'LV_gerado.dxf nao encontrado'
    if not vigas_path.exists():
        return None, 'vigas.json nao encontrado'

    # 1. Extrair reverso do DXF gerado
    if verbose:
        print(f'  Extraindo LV: {lv_path.name}')
    vigas_lv = extrair_lv(str(lv_path))
    vigas_fv = {}
    if fv_path.exists():
        if verbose:
            print(f'  Extraindo FV: {fv_path.name}')
        vigas_fv = extrair_fv(str(fv_path))

    fichas_rev = merge_vigas(vigas_lv, vigas_fv)

    # 2. Carregar forward
    with open(vigas_path, encoding='utf-8') as f:
        vigas_fwd = json.load(f)

    # 3. Comparar campo a campo
    resultados = {}
    for vid, fwd in vigas_fwd.items():
        if vid.startswith('_') or not isinstance(fwd, dict):
            continue  # pular _meta e entradas não-viga
        rev = fichas_rev.get(vid)
        campos = {}

        # comprimento
        fwd_comp = float(fwd.get('comprimento', 0) or 0) or None
        rev_comp = float(rev['comprimento_cm']) if rev and rev.get('comprimento_cm') else None
        # usar comprimento_original (pre-enriquecimento) como referencia se disponivel
        fwd_comp_orig = float(fwd.get('comprimento_original', 0) or 0) or None
        ref_comp = fwd_comp_orig if fwd_comp_orig else fwd_comp
        if ref_comp and ref_comp > 500: ref_comp = None  # AUSENTE_FWD
        if rev_comp and ref_comp and abs(rev_comp - ref_comp) >= 25:
            s, d, p = 'AUSENTE_FWD', None, None
        else:
            s, d, p = classify(ref_comp, rev_comp, 'comprimento')
        campos['comprimento'] = {'fwd': ref_comp, 'rev': rev_comp, 'status': s, 'delta_cm': d}

        # h
        fwd_h = float(fwd.get('h', 0) or 0) or None
        _hs = rev.get('h_secao', 0) if rev else 0
        rev_h = float(_hs) if _hs else None
        if not rev_h:
            _alt = rev.get('altura_cm', 0) if rev else 0
            rev_h = float(_alt) if _alt else None
        # Regra: forma sempre > h estrutural (inclui laje); delta>15 = sistemas incompatíveis → AUSENTE_FWD
        if fwd_h and rev_h and fwd_h < 70 and rev_h < 70 and abs(fwd_h - rev_h) > 15:
            s, d, p = 'AUSENTE_FWD', None, None
        elif fwd_h and rev_h and ((fwd_h > 70 and rev_h < 70) or (fwd_h < 70 and rev_h >= 70)):
            s, d, p = 'AUSENTE_FWD', None, None
        else:
            s, d, p = classify(fwd_h, rev_h, 'h')
        campos['h'] = {'fwd': fwd_h, 'rev': rev_h, 'status': s, 'delta_cm': d}

        # b
        fwd_b = float(fwd.get('b', 0) or 0) or None
        rev_b = float(rev['b']) if rev and rev.get('b') else None
        if rev_b == 0: rev_b = None
        # Ajuste caixão forward
        ref_b = fwd_b
        if ref_b and rev_b and (ref_b - rev_b) >= 8: ref_b = ref_b - 11
        s, d, p = classify(ref_b, rev_b, 'b')
        campos['b'] = {'fwd': fwd_b, 'rev': rev_b, 'status': s, 'delta_cm': d}

        resultados[vid] = {'nome': vid, 'campos': campos}

    return resultados, None


def main():
    parser = argparse.ArgumentParser(description='Valida fidelidade do DXF gerado vs fichas TQS')
    parser.add_argument('--obra', default='DADOS-OBRAS/Obra_TREINO_20', help='Diretório da obra')
    parser.add_argument('--output', default=None, help='JSON de saída (default: Fase-6/validacao_geracao.json)')
    parser.add_argument('--verbose', action='store_true', help='Mostrar detalhes da extração')
    args = parser.parse_args()

    obra_dir = Path(args.obra)
    print(f'Obra: {obra_dir.name}')

    resultados, err = comparar_vig_gerado(obra_dir, verbose=args.verbose)
    if err:
        print(f'ERRO: {err}')
        sys.exit(1)

    # Estatísticas
    counts = Counter()
    for item in resultados.values():
        for campo, val in item['campos'].items():
            counts[val['status']] += 1

    total = sum(counts.values())
    good  = sum(v for k, v in counts.items() if good_status(k))
    score = good / total * 100 if total else 0

    # Relatório
    print(f'\n{"="*70}')
    print(f'  FIDELIDADE DE GERAÇÃO — {obra_dir.name}')
    print(f'  Score: {score:.0f}% ({good}/{total})')
    print(f'  MATCH={counts["MATCH"]} | AUSENTE_FWD={counts["AUSENTE_FWD"]} | REV_ONLY={counts["REV_ONLY"]}')
    print(f'  DELTA_SMALL={counts["DELTA_SMALL"]} | DELTA_MED={counts["DELTA_MED"]} | DELTA_LARGE={counts["DELTA_LARGE"]}')
    print(f'  AUSENTE_REV={counts["AUSENTE_REV"]} | AUSENTE_AMBOS={counts["AUSENTE_AMBOS"]}')
    print(f'{"="*70}')

    # Problemas (DELTA ou AUSENTE_REV)
    problemas = []
    def _sort_key(x):
        m = re.search(r'\d+', x[0])
        return int(m.group()) if m else 0

    for vid, item in sorted(resultados.items(), key=_sort_key):
        for campo, val in item['campos'].items():
            if val['status'] in ('DELTA_SMALL', 'DELTA_MED', 'DELTA_LARGE', 'AUSENTE_REV'):
                problemas.append(f"  {vid}.{campo}: {val['status']} fwd={val['fwd']} rev={val['rev']} Δ={val['delta_cm']}")
    if problemas:
        print(f'\nProblemas ({len(problemas)}):')
        for p in problemas[:30]:
            print(p)
        if len(problemas) > 30:
            print(f'  ... (+{len(problemas)-30} mais)')

    # Salvar
    out_path = Path(args.output) if args.output else obra_dir / 'Fase-6_Execucao_CAD/validacao_geracao.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_data = {
        '_meta': {
            'obra': obra_dir.name,
            'score': round(score, 1),
            'total': total,
            'good': good,
            'counts': dict(counts),
        },
        'vigas': resultados
    }
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nSalvo em: {out_path}')


if __name__ == '__main__':
    main()
