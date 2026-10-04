from pathlib import Path
import ezdxf
from ezdxf import bbox
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[2]
original=ezdxf.readfile(root/'scripts/arete/relatorios/20261001_lv_cut_fittings/mold_copy.dxf')
for name in ('COTAX2','Cota Seção (2x)'):
    if name in original.dimstyles:
        print('DIMSTYLE',name,'dimlfac',original.dimstyles.get(name).dxf.dimlfac)
doc=ezdxf.readfile(root/'scripts/arete/assets/lv_cut_fittings.dxf')
names=['PAR_ESQ','PAR_FUNDO_ESQ','PAR_FUNDO_DIR','par_int_esq','par_int_dir']
space=doc.modelspace()
for i,name in enumerate(names):
    insert=space.add_blockref(name,(i*60,0))
    bounds=bbox.extents([insert])
    print(name, 'base',doc.blocks.get(name).block.dxf.base_point,'bounds',bounds)
    space.add_text(name,dxfattribs={'height':2.5,'insert':(i*60,-20),'color':7})
fig=plt.figure(figsize=(16,5));ax=fig.add_axes([0,0,1,1])
Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(space,finalize=True)
fig.savefig(root/'scripts/arete/relatorios/20261001_lv_cut_fittings/original_blocks.png',dpi=160)
