exec(open('audit_candidate_tmp.py',encoding='utf-8-sig').read().split("for name")[0])
from src.core.pillar_face_beams import beam_bbox_from_entity
for n in ('V514','V501','V507'):
 b=next(b for b in c[4] if b['name']==n);print(n,beam_bbox_from_entity(b), list(b))
