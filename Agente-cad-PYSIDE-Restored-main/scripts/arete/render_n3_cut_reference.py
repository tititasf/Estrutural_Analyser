"""Renderiza referência N4 existente para leitura visual; não alimenta o N3."""
from pathlib import Path
import json
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
root=Path('scripts/arete/relatorios/20261001_lv_n3_cortes')
source=Path('scripts/arete/relatorios/g2v/lv_13pav_rodada_20260911/n4_Z/LV_preview_V306_CORTE.dxf')
doc=ezdxf.readfile(source)
fig=plt.figure(figsize=(14,10));ax=fig.add_axes([0,0,1,1]);ax.set_aspect('equal')
Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
fig.savefig(root/'n4_v306_reference.png',dpi=140);plt.close(fig)
data=json.loads((root/'live_validation.json').read_text(encoding='utf8'))
from collections import Counter
print('generated',data['counts'])
print('warning cuts',sum(bool(r.get('warnings')) for r in data['rows']))
print('warnings',Counter(w for r in data['rows'] for w in r.get('warnings',[])))
