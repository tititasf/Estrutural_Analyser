"""Render complete isolated before/after drawings for visual inspection."""
from pathlib import Path
import ezdxf
from ezdxf.addons.drawing import matplotlib

root=Path(__file__).resolve().parents[1]
source=root/'scripts/arete/relatorios/20261001_config_granular/real_134353'
for cls in ('PL','LV_PARA','LV_PASSA','FV','LJ'):
    for kind in ('default','custom'):
        folder=source/f'NOVA_{cls}_{kind}'
        doc=ezdxf.readfile(next(folder.glob('*.dxf')))
        matplotlib.qsave(doc.modelspace(),folder/'full.png',dpi=130)
        print(cls,kind,flush=True)
