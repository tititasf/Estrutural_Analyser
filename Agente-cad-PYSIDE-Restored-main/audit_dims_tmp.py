import json
c=json.load(open('scripts/arete/relatorios/20261009_reprocessamento/tag_current.json',encoding='utf-8'))
b=next(b for b in c[4] if b['name']=='V514');print(json.dumps(b['dimension_texts'],ensure_ascii=False));print(json.dumps(b['texts'],ensure_ascii=False)[:1000])
