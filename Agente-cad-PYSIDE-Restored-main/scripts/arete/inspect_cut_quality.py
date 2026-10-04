import json
from pathlib import Path
p=Path('scripts/arete/relatorios/20260930_lv_visao_corte/validated_cut_inventory.json')
data=json.loads(p.read_text(encoding='utf8'))
for beam in ('V306','V301'):
 r=next(r for r in data['rows'] if r['beam']==beam and r['behavior']=='para')
 print(beam,json.dumps(r['cuts'][:3],ensure_ascii=False,indent=2)[:12000])
for file,start,end in [('portal/app/lv_ficha.py',245,320),('portal/app/lv_ficha.py',540,601),('scripts/gerar_lv_dxf_stog.py',4400,4438),('scripts/gerar_lv_dxf_stog.py',5290,5370)]:
 print(file,start,'\n'.join(Path(file).read_text(encoding='utf8').splitlines()[start-1:end]))
