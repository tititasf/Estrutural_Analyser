"""Full DXF PNG evidence of the isolated current-default contracts."""
from pathlib import Path
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'scripts/arete/relatorios/20261001_current_defaults'
SOURCE=OUT/'final_measure_v2'
for cls in ['PL','LV_PARA','LV_PASSA','FV','LJ']:
    path=next(p for p in (SOURCE/('NOVA_'+cls)).glob('*.dxf') if p.name!='cut.dxf')
    doc=ezdxf.readfile(path)
    fig,ax=plt.subplots(figsize=(16,10))
    ax.set_aspect('equal');ax.axis('off')
    Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
    ax.set_facecolor('#080c13');fig.patch.set_facecolor('#080c13')
    fig.savefig(OUT/('full_current_'+cls+'.png'),dpi=160,bbox_inches='tight')
    plt.close(fig)
    print(cls,path.name,flush=True)
