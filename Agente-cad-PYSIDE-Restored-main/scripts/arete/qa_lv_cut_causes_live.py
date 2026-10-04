"""Read-only provenance for short cut ranges and their beam openings."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from portal.app.ficha_reader import ler_estado_pavimento
from portal.app.lv_ficha import montar_ficha_lv

obra = Path(sys.argv[1])
state = ler_estado_pavimento(obra, '13_PAV')
rows = []
for beam in ('V302', 'V303', 'V311', 'V312', 'V315', 'V330', 'VF301'):
    ficha = montar_ficha_lv(obra, '13_PAV', beam, 'passa', state, include_svgs=False)
    segments = {s['id']: s for d in ficha['sides'].values() for s in d['segments']}
    for cut in ficha['cut_views']:
        for pair in cut['pairs']:
            if pair['length_cm'] >= 20:
                continue
            rows.append(dict(beam=beam, cut=cut['id'], profiles=cut.get('profiles'),
                             pair=pair, a=segments[pair['a_id']], b=segments[pair['b_id']]))
Path(sys.argv[2]).write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding='utf8')
for row in rows:
    print(row['beam'], row['pair']['length_cm'], 'openings A', row['a']['beam_openings'],
          'openings B', row['b']['beam_openings'])
