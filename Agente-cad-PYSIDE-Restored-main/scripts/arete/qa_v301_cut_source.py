"""Read-only original DXF evidence for the V301 section differences."""
import json
from pathlib import Path
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend,RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

out=Path('scripts/arete/relatorios/20261002_cut_region_fix')
source=Path('../DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA/torre_1.dxf')
doc=ezdxf.readfile(source)
texts=[]
for e in doc.modelspace().query('TEXT'):
    x,y=e.dxf.insert.x,e.dxf.insert.y
    if 1150<x<4590 and 2720<y<3230:
        texts.append(dict(handle=e.dxf.handle,text=e.dxf.text,x=x,y=y,layer=e.dxf.layer))
(out/'V301-original-texts.json').write_text(json.dumps(texts,indent=2,ensure_ascii=False),encoding='utf8')
for i,(lo,hi) in enumerate([(1150,2050),(2000,2900),(2850,3750),(3700,4600)],1):
    fig=plt.figure(figsize=(15,9),dpi=120); ax=fig.add_axes([0,0,1,1])
    Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
    ax.set_xlim(lo,hi);ax.set_ylim(2720,3230)
    fig.savefig(out/f'V301-original-{i}.png',facecolor=ax.get_facecolor());plt.close(fig)
print('Original V301 evidence saved; no CAD source changed.')
