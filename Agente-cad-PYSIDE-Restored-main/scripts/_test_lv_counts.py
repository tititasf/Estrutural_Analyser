#!/usr/bin/env python3
"""Testa contagem de entities LV draw_lv_face vs SCR (face 1).

Anatomia V01-1.scr confirmada:
  - SCR SEMPRE usa 3 paineis iguais (b/3 cada)
  - Sarrafos como PLINE (1 linha por posição)
  - PLINEs = 13 (estrutura paineis) + 2*(n_pos*3) + 2 (bordas) por face
  - D=8 (4 horiz + 4 verit fixos), T=3 (ESQ, DIR, nome)
"""
import sys, json, importlib
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCR_LV = ROOT / '_ROBOS_ABAS/Robo_Laterais_de_Vigas/SCRIPTS/CENARIOS_LV'
sys.path.insert(0, str(ROOT / 'scripts'))

data = json.loads((SCR_LV / 'cenarios_lv_resumo.json').read_text(encoding='utf-8'))
mod = importlib.import_module('gerar_lv_dxf_stog')


def count_scr(p):
    try:
        txt = p.read_text(encoding='utf-16-le', errors='replace')
    except Exception:
        txt = p.read_text(encoding='utf-8', errors='replace')
    lines = txt.splitlines()
    p2 = sum(1 for l in lines if l.strip().upper().startswith('_PLINE'))
    d  = sum(1 for l in lines if '_DIMLINEAR' in l.upper())
    i  = sum(1 for l in lines if l.strip().upper().startswith('-INSERT'))
    t  = sum(1 for l in lines if l.strip().upper().startswith('_TEXT'))
    li = sum(1 for l in lines if l.strip().upper().startswith('_LINE'))
    return p2 + d + i + t + li, p2, d, i, t, li


def count_ezdxf_by_type(msp):
    """Count entities by type from modelspace."""
    from collections import defaultdict
    counts = defaultdict(int)
    for e in msp:
        counts[e.dxftype()] += 1
    return dict(counts)


def n_sarr_positions(h):
    """Number of sarrafo positions per panel for given height h (matches SCR)."""
    if h < 15:
        return 2   # 2 positions
    elif h < 30:
        return 2   # SARR_2.2x5
    elif h < 80:
        return 4   # center ± 3.5 + edges
    else:
        return 8   # quarter + center + 3/4 + edges


def expected_scr_counts(b, h):
    """Expected SCR command counts for face-1 with 3 panels.
    Returns (total, plines, dims, texts)
    """
    np = n_sarr_positions(h)
    # PLINEs:
    #   Panel structure (Paineis layer): 2 borders + 2 dividers + 6 top/bot + 3 rects = 13
    #   SARR edge: 2
    #   SARR per-panel (np pos × 3 panels): np*3
    #   SARR combined spans (np rows × 3 spans): np*3
    plines = 13 + 2 + np * 3 + np * 3
    dims   = 8   # 4 horiz panel widths + 4 vert height (constant)
    texts  = 3   # ESQ + DIR + nome
    return plines + dims + texts, plines, dims, texts


ok = 0
fail = 0
results = []

for row in data:
    nome = row[0]
    larg = float(row[1])
    alt  = float(row[2]) if str(row[2]).replace('.', '').isdigit() else 120.0

    scr_path = SCR_LV / f'{nome}-1.scr'
    if not scr_path.exists():
        continue

    st, sp2, sd, si, ss, sl = count_scr(scr_path)

    # Expected theoretical counts
    exp_total, exp_p, exp_d, exp_t = expected_scr_counts(larg, alt)

    # Build 3 equal panels (SCR anatomy: always 3 equal panels)
    pw = larg / 3.0
    panels = [
        {'width': pw, 'height1': alt, 'height2': 0.0,
         'grade_h1': 0, 'grade_h2': 0,
         'panel_type': 'Sarrafeado', 'reuse': False}
        for _ in range(3)
    ]

    try:
        doc = mod.setup_doc()
        msp = doc.modelspace()
        mod.draw_lv_face(
            msp, x0=0, y0=0,
            panels=panels, h=alt,
            nome_face=nome,
            laje_sup=0.0, laje_inf=0.0,
        )
        ez = len(list(msp))
        by_type = count_ezdxf_by_type(msp)
    except Exception as e:
        print(f'{nome} ERR: {e}')
        continue

    diff = ez - st
    scr_matches_expected = (st == exp_total)
    results.append((nome, larg, alt, ez, st, diff, by_type, sp2, sd, ss,
                    exp_total, exp_p, exp_d, exp_t, scr_matches_expected))

    if diff == 0:
        ok += 1
    else:
        fail += 1

print('LV draw_lv_face vs SCR Face-1')
print('=' * 90)
print(f'{"Viga":6s} {"b":>4s} {"h":>4s} | {"ez":>5s} {"scr":>5s} {"diff":>6s} | '
      f'{"LINE":>5s} {"DIM":>5s} {"TEXT":>5s} {"MTEXT":>5s} | {"P_scr":>6s} {"D_scr":>5s} {"T_scr":>5s}')
print('-' * 90)

for r in results[:20]:  # Show first 20
    nome, b, h, ez, st, diff, by_type, sp2, sd, ss, exp, ep, ed, et, match = r
    print(f'{nome:6s} {int(b):4d} {int(h):4d} | {ez:5d} {st:5d} {diff:+6d} | '
          f'{by_type.get("LINE",0):5d} {by_type.get("DIMENSION",0):5d} {by_type.get("TEXT",0):5d} '
          f'{by_type.get("MTEXT",0):5d} | {sp2:6d} {sd:5d} {ss:5d}')

print()
print(f'draw_lv_face: {ok} PASS / {ok+fail} total ({fail} fail)')

# Summary of deltas by entity type (first failing case)
if fail > 0:
    failing = [r for r in results if r[5] != 0][:3]
    print('\n--- Per-type breakdown (first 3 failing cases) ---')
    for r in failing:
        nome, b, h, ez, st, diff, by_type, sp2, sd, ss, exp, ep, ed, et, match = r
        print(f'\n{nome} (b={int(b)}, h={int(h)}): ezdxf={ez} scr={st} diff={diff:+d}')
        print(f'  SCR: P={sp2} D={sd} T={ss}')
        print(f'  ezdxf types: {dict(sorted(by_type.items(), key=lambda x:-x[1]))}')
        print(f'  Expected: total={exp} P={ep} D={ed} T={et}  scr_matches_expected={match}')
