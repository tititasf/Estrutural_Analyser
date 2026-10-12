import json
from pathlib import Path
p=Path('scripts/arete/relatorios/20261009_reprocessamento/tag_candidate_audit')
t=json.load(open(p/'tables.json',encoding='utf-8'))
for n,v in t.items():
 print(n,v.get('geometry_type'),{f:{k:[(r.get('nome'),r.get('dim'),r.get('canto')) for r in a] for k,a in d.items() if isinstance(a,list) and a} for f,d in v.get('faces',{}).items()})
