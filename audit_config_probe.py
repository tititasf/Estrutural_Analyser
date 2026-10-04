import hashlib,json
from pathlib import Path
r=Path('/opt/cad-analyzer')
for name in ['config/drawing_mode_current_catalog.json','portal/app/static/drawing_mode_config.js','portal_runtime/drawing_mode_settings.json']:
 p=r/name;print(name,hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None)
from scripts.drawing_mode_config import current_catalog
c=current_catalog();print('catalog_verified',c['verified'])
for name,sha in c['sources'].items():
 actual=hashlib.sha256((r/name).read_text().encode()).hexdigest()
 if actual!=sha:print('CHANGED',name)
for p in (r/'DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n5').glob('N5_PL_13_PAV_NOVA*.json'):
 m=json.loads(p.read_text());print('N5',p.name,len(m.get('items',[])),m.get('frame_layout',{}).get('kind'),p.stat().st_mtime)
