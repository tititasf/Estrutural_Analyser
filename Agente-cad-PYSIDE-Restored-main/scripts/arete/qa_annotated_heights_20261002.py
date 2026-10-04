import json
from pathlib import Path
from portal.app.lv_cut_map import section_drawings
rows=json.loads(Path('scripts/arete/relatorios/20261002_cut_region_fix/final_qa.json').read_text(encoding='utf8'))['rows']
result=[]
for row in rows:
 cuts=[c for c in row['cuts'] if c['kind']=='identified']
 if not cuts: continue
 drawings,blocked=section_drawings(cuts, {'B':{'segments':[]}})
 result.append({'beam':row['beam'],'behavior':row['behavior'],'identified':len(cuts),'drawn':len(drawings),'blocked':blocked})
 if row['beam']=='V301' and row['behavior']=='passa':
  for d in drawings:
   print('V301',d['cut_index'],[p['text'] for p in d['primitives'] if p['kind']=='text'])
Path('scripts/arete/relatorios/20261002_sections_on_structure/qa_annotated_heights.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
print('TOTAL',sum(r['identified'] for r in result),sum(r['drawn'] for r in result),'blocked',sum(len(r['blocked']) for r in result))
