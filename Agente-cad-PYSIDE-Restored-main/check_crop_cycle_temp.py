import json,time,hashlib
from pathlib import Path
from scripts.obra_crop_engine import detect_regions,crop_dxf,crop_dxf_complement
from portal.app.crop_islands import ensure_detail_islands
from portal.app.preprocessamento.adapters.level_crossing import _floor_reference
raw=Path('C:/Users/Thierry/Desktop/EST-PE-007-TIPO-R01.DXF')
out=Path('scripts/arete/relatorios/20261009_reprocessamento/fresh_crop_cycle')
out.mkdir(parents=True,exist_ok=True)
start=time.monotonic(); before=hashlib.sha256(raw.read_bytes()).hexdigest()
r=detect_regions(raw,n_torres=1)
assert not r.get('error'),r
ts=[]
for i,t in enumerate(r['torres'],1):
 p=out/f'torre_{i}.dxf'; result=crop_dxf(raw,p,t['bbox'],padding_pct=.01)
 assert not result.get('error'),result
 ts.append(str(p))
c=crop_dxf_complement(raw,out/'detalhes.dxf',ts)
islands=ensure_detail_islands(raw,out,r)
ref=_floor_reference(raw,'TIPO_TESTE','fresh-raw')
report={'raw_sha256':before,'source_unchanged':before==hashlib.sha256(raw.read_bytes()).hexdigest(),
 'elapsed_s':round(time.monotonic()-start,2),'coverage':c,'islands':islands,
 'crop_count':len(list(out.glob('*.dxf'))),'level_reference':ref}
(out/'cycle.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'count':report['crop_count'],'seconds':report['elapsed_s'],'unchanged':report['source_unchanged'],'reference':ref},ensure_ascii=False))
