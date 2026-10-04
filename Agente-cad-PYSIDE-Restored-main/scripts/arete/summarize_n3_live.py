import json
from pathlib import Path
from collections import Counter
p=Path('scripts/arete/relatorios/20261001_lv_n3_cortes/live_validation.json')
data=json.loads(p.read_text(encoding='utf8'))
print(data['counts'])
print('warnings',sum(bool(r.get('warnings')) for r in data['rows']))
print(Counter(w for r in data['rows'] for w in r.get('warnings',[])))
print('V306 VC1',[r for r in data['rows'] if r['beam']=='V306' and r['behavior']=='para' and r['vc']==1])
