import json
from pathlib import Path
r=next(r for r in json.loads(Path('scripts/arete/relatorios/20261002_cut_region_fix/final_qa.json').read_text())['rows'] if r['beam']=='V301' and r['behavior']=='passa')
for c in r['cuts']:
 if c['kind']=='identified': print(c['id'],json.dumps(c['source_cut']['ficha'],ensure_ascii=False))
