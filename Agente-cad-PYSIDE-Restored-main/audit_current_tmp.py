import gzip,json
from pathlib import Path
from src.core.pillar_face_beams import beam_section_dim,beam_runs_from_entity
p=Path('scripts/arete/relatorios/20261009_reprocessamento')
c=json.loads(gzip.decompress((p/'tag_current.json.gz').read_bytes()));(p/'tag_current.json').write_text(json.dumps(c),encoding='utf-8')
for name in ('V501','V507','V513','V514','V522'):
 b=next(b for b in c[4] if b['name']==name);print(name,beam_section_dim(b),beam_runs_from_entity(b))
for name in ('P3','P17'):
 b=next(b for b in c[5] if b['name']==name);print(name,json.dumps(b['face_beams']))
