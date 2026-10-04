from pathlib import Path
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
root=Path('scripts/arete/relatorios/20261001_lv_n3_cortes')
source=Path('../DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.dxf')
doc=ezdxf.readfile(source)
fig=plt.figure(figsize=(14,12)); ax=fig.add_axes([0,0,1,1]);ax.set_aspect('equal')
Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
ax.set_xlim(2020,2480);ax.set_ylim(1850,2300)
fig.savefig(root/'v306_original_cut_context.png',dpi=160)
plt.close(fig)
print('rendered',root/'v306_original_cut_context.png')
