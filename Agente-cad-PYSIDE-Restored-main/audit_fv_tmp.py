import json
c=json.load(open('scripts/arete/relatorios/20261009_reprocessamento/tag_current.json',encoding='utf-8'))
for n in ('V507','V513','V514','V522','V526'):
 b=next(b for b in c[4] if b['name']==n)
 print(n)
 for k,v in b.get('links',{}).items():
  if 'fundo' in k and 'area_segs' in k:print(k,json.dumps(v)[:1800])
