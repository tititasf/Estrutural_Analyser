import sys, json
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')

CELL_W, CELL_H, MARGIN, COLS = 2900, 1800, 80, 12

def dedup_correct(params):
    """Exact dedup from build_combined."""
    from collections import defaultdict as _dd
    # Set _obra first
    for p in params:
        p['_obra'] = p.get('obra') or 'desconhecida'
    _groups = _dd(list)
    for p in params:
        ins = p.get('insert') or {}
        key = (p.get('_obra',''), p['viga'],
               round(ins.get('x',0)/5), round(ins.get('y',0)/5))
        _groups[key].append(p)
    deduped = []
    for key, vs in _groups.items():
        best = max(vs, key=lambda v: (
            len(v.get('hatches_data') or []) +
            len(v.get('sarr22_lines') or []) +
            len((v.get('grade_entities') or {}).get('grade_lines', []))
        ))
        deduped.append(best)
    return deduped

for fn in ['params/viga_params_v3.json', 'params/viga_params_v6.json']:
    with open(fn) as f: raw = json.load(f)
    d = dedup_correct(raw)
    print('%s: %d raw -> %d after dedup' % (fn, len(raw), len(d)))
    # Check cell (5,41): index 41*12+5=497
    idx = 41*12+5
    if idx < len(d):
        p = d[idx]
        print('  [%d] viga=%s obra=%s' % (idx, p.get('viga','?'), p.get('_obra','?')))
        fa = p.get('face_a') or {}
        print('  face_a keys: %s' % list(fa.keys())[:6])
        hl = fa.get('face_hlines') or []
        print('  face_hlines count=%d' % len(hl))
    else:
        print('  idx %d >= len=%d' % (idx, len(d)))
