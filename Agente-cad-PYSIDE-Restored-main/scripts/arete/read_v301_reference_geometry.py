import ezdxf
from pathlib import Path
p=Path('scripts/arete/relatorios/g2v/lv_13pav_rodada_20260911/n4_AQ/LV_preview_V301_CORTE.dxf')
d=ezdxf.readfile(p)
for e in d.modelspace().query('LWPOLYLINE'):
    pts=list(e.get_points('xy'))
    if max(y for x,y in pts)<-260: continue
    if e.dxf.layer!='COTA':print(e.dxf.layer,e.dxf.color,[(round(x,2),round(y,2)) for x,y in pts])
source=Path('scripts/gerar_lv_dxf_stog.py').read_text(encoding='utf8').splitlines()
print('\n'.join(f'{i+1}:{l}' for i,l in enumerate(source) if l.startswith('def ') and any(k in l for k in ['section','corte','dim','setup'])))
