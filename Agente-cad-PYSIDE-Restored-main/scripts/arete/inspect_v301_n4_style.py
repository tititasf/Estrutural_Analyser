from pathlib import Path
from collections import Counter
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend,RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
p=Path('scripts/arete/relatorios/g2v/lv_13pav_rodada_20260911/n4_AQ/LV_preview_V301_CORTE.dxf')
doc=ezdxf.readfile(p)
print('source',p)
print('layers',[(l.dxf.name,l.dxf.color) for l in doc.layers])
print('entities',Counter((e.dxftype(),e.dxf.layer,e.dxf.color) for e in doc.modelspace()))
print('texts',[(e.dxf.text,round(e.dxf.height,2),tuple(e.dxf.insert)[:2],e.dxf.layer,e.dxf.color) for e in doc.modelspace().query('TEXT')][:100])
fig=plt.figure(figsize=(13,14));ax=fig.add_axes([0,0,1,1]);ax.set_aspect('equal')
Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
fig.savefig('scripts/arete/relatorios/20261001_lv_n3_cortes/v301_n4_AQ_reference.png',dpi=140)
