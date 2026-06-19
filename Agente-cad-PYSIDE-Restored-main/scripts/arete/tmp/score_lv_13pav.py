# -*- coding: utf-8 -*-
"""
score_lv_13pav.py — Scoring N2 vs fichas_lv_v2 para 32 LV do 13° PAV.

Métricas por viga/face:
  - h_match    : |h_A_n2 - h_A_n4| <= 2 cm
  - laje_match : |laje_sup_A_n2 - laje_sup_A_n4| <= 2 cm
  - segs_match : panel widths exatos (todos ±5 cm)
  - score      : 0.33*h + 0.33*laje + 0.33*segs

Uso: python scripts/arete/tmp/score_lv_13pav.py
"""
from __future__ import annotations
import sys, json, subprocess, re
from pathlib import Path

REPO     = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'scripts'))

from scripts.motor_reverso_lv import _extract_lv_geom_from_dxf

LV_DIR      = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- LV - R00")
OBRA_DIR    = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
FICHAS_PATH = OBRA_DIR / 'Fase-6_Execucao_CAD' / 'granular' / 'fichas' / 'fichas_lv_v2.json'
GERADOR     = REPO / 'scripts' / 'gerar_lv_dxf_stog.py'
N4_OUT      = OBRA_DIR / 'Fase-6_Execucao_CAD' / 'n4'
N4_OUT.mkdir(parents=True, exist_ok=True)


def _latest_dxf(elem: str) -> Path | None:
    cands = sorted(LV_DIR.glob(f"LV_{elem}_motor_*.dxf"),
                   key=lambda p: int(re.search(r'(\d+)\.dxf$', p.name).group(1)))
    return cands[-1] if cands else None


def _segs_match(n2_ws: list[float], n4_ws: list[float], tol: float = 5.0) -> float:
    """Similaridade de sequências de larguras (não-ordenada, best-matching)."""
    if not n2_ws and not n4_ws:
        return 1.0
    if not n2_ws or not n4_ws:
        return 0.0
    # Conta quantos n2_ws encontram match em n4_ws dentro de tol
    remaining = list(n4_ws)
    matched = 0
    for w in n2_ws:
        for i, r in enumerate(remaining):
            if abs(w - r) <= tol:
                matched += 1
                remaining.pop(i)
                break
    denom = max(len(n2_ws), len(n4_ws))
    return matched / denom


def run_score() -> None:
    # Carregar fichas_lv_v2 como referência N4
    fichas: list[dict] = json.loads(FICHAS_PATH.read_text(encoding='utf-8'))
    fichas_map: dict[str, dict] = {}
    for f in fichas:
        vn = f.get('viga', '')
        face = f.get('face', 'A')
        fichas_map.setdefault(vn, {})[face] = f

    # Descobrir elementos
    elems = sorted(set(
        d.stem.split('_motor_')[0].replace('LV_', '')
        for d in LV_DIR.glob('LV_*_motor_*.dxf')
    ))

    print(f"\n{'ELEM':12s} {'hA_n2':>6} {'hA_v2':>6} {'lsA_n2':>7} {'lsA_v2':>7} "
          f"{'pA_n2':30s} {'pA_v2':30s} {'sco':>5} STATUS")
    print('-' * 120)

    total_score = 0.0
    ok_count = 0

    for elem in elems:
        dxf = _latest_dxf(elem)
        if not dxf:
            print(f'{elem:12s} SEM DXF')
            continue

        # N2: motor extraction
        r = _extract_lv_geom_from_dxf(str(dxf), elem)
        hA_n2  = r['h_A']
        lsA_n2 = r['laje_sup_A']
        pA_n2  = [p['width'] for p in r.get('panels_A', [])]

        # N4 reference: fichas_lv_v2
        fc = fichas_map.get(elem, {})
        fca = fc.get('A', {})
        hA_v2  = float(fca.get('h_cm', 0) or 0)
        lsA_v2 = float(fca.get('laje_sup_cm', 0) or 0)
        pA_v2  = [float(s.get('largura_cm', 0)) for s in fca.get('segmentos', [])]

        # Scores
        h_ok    = abs(hA_n2 - hA_v2) <= 2.0
        ls_ok   = abs(lsA_n2 - lsA_v2) <= 2.0
        seg_sim = _segs_match(pA_n2, pA_v2, tol=5.0)
        score   = (int(h_ok) * 0.33 + int(ls_ok) * 0.33 + seg_sim * 0.34)

        total_score += score
        if score >= 0.9:
            ok_count += 1

        status = 'OK' if score >= 0.9 else ('WARN' if score >= 0.6 else 'FAIL')
        p_n2_str = str([int(w) for w in pA_n2])[:28]
        p_v2_str = str([int(w) for w in pA_v2])[:28]
        print(f'{elem:12s} {hA_n2:6.1f} {hA_v2:6.1f} {lsA_n2:7.1f} {lsA_v2:7.1f} '
              f'{p_n2_str:30s} {p_v2_str:30s} {score:5.2f} {status}')

    n = len(elems)
    avg = total_score / n if n else 0
    print(f'\n{"-"*120}')
    print(f'Total: {n} vigas | OK>=0.9: {ok_count}/{n} | Avg score: {avg:.3f}')


if __name__ == '__main__':
    run_score()
