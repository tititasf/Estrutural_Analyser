import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

source_dir = ROOT / 'scripts/arete/relatorios/20261006_formascia_lv_teste'

for dxf_path in sorted(source_dir.glob('*.dxf')):
    try:
        doc = ezdxf.readfile(dxf_path)
        fig, ax = plt.subplots(figsize=(16, 8), facecolor='#11151c')
        ax.set_facecolor('#11151c')
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
        ax.set_title(f"{dxf_path.stem} (Formascia N3)", color='white', fontsize=12)
        ax.axis('off')
        fig.tight_layout()
        png_path = dxf_path.with_suffix('.png')
        fig.savefig(png_path, dpi=150, facecolor=fig.get_facecolor(), bbox_inches='tight')
        plt.close(fig)
        print(f"[RENDER OK] {png_path.name}")
    except Exception as exc:
        print(f"[RENDER FAIL] {dxf_path.name}: {exc}")
