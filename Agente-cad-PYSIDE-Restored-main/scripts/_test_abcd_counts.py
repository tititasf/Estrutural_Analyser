#!/usr/bin/env python3
"""Testa contagem de entities ABCD ezdxf vs SCR."""
import sys, io, json, importlib
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCR_DIR = ROOT / '_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/SCRIPTS_ROBOS'
RESUMO = SCR_DIR / 'cenarios_pilares_resumo.json'

sys.path.insert(0, str(ROOT / 'scripts'))
data = json.loads(RESUMO.read_text(encoding='utf-8'))
cenarios = [{'nome':r[0],'comp':float(r[2]),'larg':float(r[3]),'alt':float(r[4]),'g1':float(r[5])} for r in data]

mod = importlib.import_module('gerar_pl_dxf_stog')

def count_scr(p):
    try: txt = p.read_text(encoding='utf-16-le', errors='replace')
    except: txt = p.read_text(encoding='utf-8', errors='replace')
    lines = txt.splitlines()
    p2 = sum(1 for l in lines if l.strip().upper().startswith('_PLINE'))
    d  = sum(1 for l in lines if '_DIMLINEAR' in l.upper())
    i  = sum(1 for l in lines if l.strip().upper().startswith('-INSERT'))
    t  = sum(1 for l in lines if l.strip().upper().startswith('_TEXT'))
    return p2+d+i+t, p2, d, i, t

ok = 0; fail = 0
for c in cenarios:
    scr_path = SCR_DIR / 'CENARIOS_ABCD' / f"{c['nome']}_ABCD.scr"
    if not scr_path.exists():
        continue
    st, sp2, sd, si, ss = count_scr(scr_path)
    pj = {'nome': c['nome'], 'comprimento': c['comp'], 'largura': c['larg'],
          'altura': c['alt'], 'grade_1': c['g1'], 'grade_2': 0}
    try:
        doc = mod.setup_doc()
        msp = doc.modelspace()
        cnt = mod.draw_abcd(msp, -7000, 0, c['comp'], c['larg'], c['alt'], c['nome'], pj)
    except Exception as e:
        print(f"{c['nome']} ERR: {e}")
        continue
    diff = cnt - st
    if diff == 0:
        ok += 1
    else:
        fail += 1
        print(f"{c['nome']:4s} {int(c['comp']):3d}x{int(c['larg']):3d} alt={int(c['alt']):3d} | "
              f"ez={cnt} scr={st} (P{sp2} D{sd} I{si} T{ss}) [{diff:+d}]")

print(f"\nABCD: {ok} PASS / {ok+fail} total ({fail} fail)")
