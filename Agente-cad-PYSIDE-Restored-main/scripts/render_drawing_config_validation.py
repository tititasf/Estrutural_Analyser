from pathlib import Path
import sys
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
source = Path(sys.argv[1])
for mode in ('INI', 'NOVA'):
    fig, axes = plt.subplots(5, 2, figsize=(18, 20), facecolor='#080d12')
    for row, cls in enumerate(('PL', 'LV_PARA', 'LV_PASSA', 'FV', 'LJ')):
        for col, label in enumerate(('before', 'after')):
            path = source / 'real_output_v2' / f'P1_{mode}_{label}.dxf' if cls == 'PL' else next((source / 'cli_output_v2' / f'{mode}_{cls}_{label}').glob('*.dxf'))
            doc = ezdxf.readfile(path)
            axis = axes[row, col]
            Frontend(RenderContext(doc), MatplotlibBackend(axis)).draw_layout(doc.modelspace(), finalize=True)
            axis.set_title(f'{mode} / {cls} / {label}', color='white', fontsize=14)
    fig.tight_layout()
    fig.savefig(source / f'{mode}_full_comparison.png', dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)
