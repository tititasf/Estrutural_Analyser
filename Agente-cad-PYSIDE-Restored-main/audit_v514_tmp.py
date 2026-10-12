import json
from src.core.dxf_loader import DXFLoader,RenderMode
from src.core.pillar_face_beams import beam_section_dim,beam_runs_from_entity
from src.core.beam_corridor_recovery import recover_pillar_beam_corridors
c=json.load(open('scripts/arete/relatorios/20261009_reprocessamento/tag_context_complete.json',encoding='utf-8'))
b=next(b for b in c[4] if b['name']=='V514')
print('V514', b['pos'],beam_section_dim(b),beam_runs_from_entity(b))
d=DXFLoader.load_dxf('scripts/arete/relatorios/20261009_reprocessamento/review_source_tower.dxf',mode=RenderMode.TRUE_GEOMETRY)
print('near texts',[(t.get('text'),t.get('pos')) for t in d['texts'] if t.get('pos') and sum((t['pos'][i]-b['pos'][i])**2 for i in (0,1))<120**2])
r,m=recover_pillar_beam_corridors('scripts/arete/relatorios/20261009_reprocessamento/review_source_tower.dxf',c[4])
print('recovered',r.get('V514'),m.get('V514'))
