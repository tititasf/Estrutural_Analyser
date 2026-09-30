#!/usr/bin/env python3
"""Converte os DXFs gerados por gen_casos_n4_standalone.py em SVG (pra
embutir na ficha HTML) e PNG (pra eu conferir visualmente), reusando a
mesma receita de src/ui/widgets/pre_validation_dialog.py::_render_ezdxf_b64.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.ui.widgets.svg_embed_utils import strip_fixed_size  # noqa: E402

DXF_DIR = Path(__file__).parent / 'tmp' / 'n4_casos_abcd' / 'dxf'
SVG_DIR = Path(__file__).parent / 'tmp' / 'n4_casos_abcd' / 'svg'
PNG_DIR = Path(__file__).parent / 'tmp' / 'n4_casos_abcd' / 'png'
SVG_DIR.mkdir(parents=True, exist_ok=True)
PNG_DIR.mkdir(parents=True, exist_ok=True)


def render(dxf_path: Path, width=900, height=600, fmt='svg'):
    import io
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    dpi = 150
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    rc = {'svg.fonttype': 'none'} if fmt == 'svg' else {}
    with matplotlib.rc_context(rc):
        fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp)
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=dpi, facecolor='white', bbox_inches='tight')
        plt.close(fig)
    buf.seek(0)
    if fmt == 'svg':
        return strip_fixed_size(buf.read().decode('utf-8'))
    return buf.read()


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', type=int, default=None)
    args = ap.parse_args()
    dxfs = sorted(DXF_DIR.glob(f'caso{args.caso}_*.dxf' if args.caso else 'caso*.dxf'))
    for dxf in dxfs:
        svg_text = render(dxf, fmt='svg')
        (SVG_DIR / (dxf.stem + '.svg')).write_text(svg_text, encoding='utf-8')
        png_bytes = render(dxf, fmt='png')
        (PNG_DIR / (dxf.stem + '.png')).write_bytes(png_bytes)
        print(f'{dxf.stem} -> svg + png ok')


if __name__ == '__main__':
    main()
