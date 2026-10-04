"""Read-only check of every published pair against original segment ranges."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from portal.app.ficha_reader import ler_estado_pavimento, listar_itens_n1
from portal.app.lv_ficha import montar_ficha_lv

obra, output = Path(sys.argv[1]), Path(sys.argv[2])
state = ler_estado_pavimento(obra, '13_PAV')
rows = []
for behavior in ('para', 'passa'):
    beams = sorted({i['beam_name'] for side in ('a', 'b')
                    for i in listar_itens_n1(state, f'lateral_{side}_{behavior}')})
    for beam in beams:
        ficha = montar_ficha_lv(obra, '13_PAV', beam, behavior, state, include_svgs=False)
        sides = {side: {s['id']: s for s in data['segments']}
                 for side, data in ficha['sides'].items()}
        for cut in ficha['cut_views']:
            for pair in cut['pairs']:
                a, b = sides['A'][pair['a_id']], sides['B'][pair['b_id']]
                start, end = pair['start'], pair['end']
                length = math.dist(start, end)
                ux, uy = (end[0]-start[0])/length, (end[1]-start[1])/length
                project = lambda p: p[0]*ux+p[1]*uy
                axis = 'X' if abs(uy) < .0001 else 'Y' if abs(ux) < .0001 else 'inclinado'
                ar = [min(map(project, a['points'])), max(map(project, a['points']))]
                br = [min(map(project, b['points'])), max(map(project, b['points']))]
                low, high = max(ar[0], br[0]), min(ar[1], br[1])
                vals = [project(start), project(end)]
                valid = high-low > .5 and min(vals) >= low-.01 and max(vals) <= high+.01
                rows.append(dict(beam=beam, behavior=behavior, cut=cut['id'],
                                 a=pair['a_id'], b=pair['b_id'], axis=axis,
                                 a_range=ar, b_range=br, shared=[low, high], valid=valid))
result = dict(pairs=len(rows), invalid=sum(not r['valid'] for r in rows), rows=rows)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print({k:v for k,v in result.items() if k != 'rows'})
if result['invalid']: raise SystemExit(1)
