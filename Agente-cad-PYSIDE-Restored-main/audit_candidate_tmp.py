import json
from src.core.pillar_face_beams import beam_runs_from_entity,beam_axis_is_horizontal
c=json.load(open('scripts/arete/relatorios/20261009_reprocessamento/tag_candidate_audit/context.json',encoding='utf-8'))
for name in ('V514','V513','V522','V507'):
 b=next(b for b in c[4] if b['name']==name);print(name,b.get('_recovered_corridor'),b.get('_measured_corridor'),beam_runs_from_entity(b),beam_axis_is_horizontal(b))
p=next(p for p in c[5] if p['name']=='P17');print(p['points'],p['face_beams'])
