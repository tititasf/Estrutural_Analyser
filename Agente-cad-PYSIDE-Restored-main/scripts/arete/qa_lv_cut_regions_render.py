"""Render actual candidate drawings and the untouched N4 reference for QA."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import Frontend,RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from src.core.lv_n3_cut_contract import build_cut_contract
from scripts.arete.lv_n3_cut_draw import generate

folder=Path(__file__).parent/'relatorios/20261002_cut_region_fix'
data=json.loads((folder/'staged.json').read_text(encoding='utf8'))
for beam in ('V310','V312'):
    cuts=next(r['cuts'] for r in data['after'] if r['beam']==beam and r['behavior']=='passa')
    fig,axes=plt.subplots(1,len(cuts),figsize=(5*len(cuts),9),dpi=110)
    if len(cuts)==1: axes=[axes]
    for i,(cut,ax) in enumerate(zip(cuts,axes)):
        doc=generate(build_cut_contract(cut),folder/f'{beam}-candidate-{i+1}.dxf')
        Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
    fig.tight_layout();fig.savefig(folder/f'{beam}-candidate.png');plt.close(fig)
    refs=json.loads((folder.parent/'20261001_qa_cut_n3_n4/n4_inventory.json').read_text(encoding='utf8'))
    ref=next(r for r in refs if r['beam']==beam)
    doc=ezdxf.readfile(ref['n4_path'])
    fig=plt.figure(figsize=(10,9),dpi=110);ax=fig.add_axes([0,0,1,1])
    Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
    fig.savefig(folder/f'{beam}-N4-reference.png');plt.close(fig)
print('Rendered V310 and V312 actual candidate DXFs and original N4 references.')
