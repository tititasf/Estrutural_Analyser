"""Real DXF evidence for the owner's opening-section presentation decision."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.arete.gerar_duvida_html import Duvida, Destaque, Leitura, gerar
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

root=Path(__file__).resolve().parents[2]
out=root/'scripts/arete/relatorios/20261002_cut_region_fix'
dxf=root.parent/'DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA/torre_1.dxf'
window=(1320,2590,1455,2735)
gerar(Duvida(titulo='V302 × V310 — faixa de abertura e Visão Corte',
    pergunta='A faixa da abertura deve gerar um corte específico ou ficar somente nas laterais?',
    dxf=dxf,janela=window,saida=out/'DUVIDA-ABERTURA.html',
    contexto='Par A/B de 13,85 cm coincide com abertura V310 de 14 cm no lado A da V302. O corte atual trata esse trecho como concreto integral sem laje.',
    destaques=[Destaque('Faixa de abertura V310',1380.4,2660,1394.4,2681,'#ea580c')],
    leituras=[Leitura('Somente laterais','Conservar abertura na ficha lateral.','Não acrescenta seção comum à lista de cortes.'),
              Leitura('Corte específico','Representar a abertura e a parte restante.','Acrescenta corte de interferência, sem fingir uma seção comum.')]))
doc=ezdxf.readfile(dxf)
fig=plt.figure(figsize=(8,8),dpi=140); ax=fig.add_axes([0,0,1,1])
Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
ax.set_xlim(window[0],window[2]);ax.set_ylim(window[1],window[3])
from matplotlib.patches import Rectangle
ax.add_patch(Rectangle((1380.4,2660),14,21,fill=False,color='#ff8800',linewidth=2))
fig.savefig(out/'abertura-V302.png',facecolor=ax.get_facecolor())
print(out/'DUVIDA-ABERTURA.html')
