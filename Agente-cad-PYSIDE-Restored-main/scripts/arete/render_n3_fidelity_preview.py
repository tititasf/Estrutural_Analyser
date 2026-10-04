import json,inspect
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.core.lv_n3_cut_contract import build_cut_contract
from scripts.arete.lv_n3_cut_draw import generate,motor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend,RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
root=Path('scripts/arete/relatorios/20261001_lv_n3_cortes')
cut=json.loads((root/'live_cut_sources.json').read_text(encoding='utf8'))['cuts'][0]
doc=generate(build_cut_contract(cut),root/'n3_fidelity_v306.dxf')
print(inspect.getsource(motor().add_text))
fig=plt.figure(figsize=(14,10));ax=fig.add_axes([0,0,1,1]);ax.set_aspect('equal')
Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
fig.savefig(root/'n3_fidelity_v306.png',dpi=150)
