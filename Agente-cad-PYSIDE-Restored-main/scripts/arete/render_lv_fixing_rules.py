"""Visual proof of LV fixing thresholds; synthetic fixtures are labelled."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.core.lv_n3_cut_contract import build_cut_contract
from scripts.arete.lv_n3_cut_draw import generate
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend,RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
root=Path(__file__).parent/'relatorios/20261001_lv_cut_complete'
root.mkdir(parents=True,exist_ok=True)
for label,height,lower in [('controle_55',55,False),('controle_120',120,False),('controle_laje_inferior',120,True)]:
    cut={'kind':'calculated','id':label,'beam':'CONTROLE','width_cm':19,'beam_height_cm':height,
         'profiles':{s:{'level':852.19,'slabs':[]} for s in ('A','B')},'pairs':[]}
    if lower:cut['profiles']['A']['slabs']=[{'name':'LI','height_cm':10,'level':851.09}]
    doc=generate(build_cut_contract(cut),root/(label+'.dxf'))
    fig=plt.figure(figsize=(14,10));ax=fig.add_axes([0,0,1,1]);ax.set_aspect('equal')
    Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
    fig.savefig(root/(label+'.png'),dpi=120);plt.close(fig)
