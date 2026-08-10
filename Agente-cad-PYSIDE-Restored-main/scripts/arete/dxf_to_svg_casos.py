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


def render(dxf_path: Path, width=900, height=600, fmt='svg', highlight_polys=None):
    """Renderiza DXF -> SVG/PNG. `highlight_polys` (opcional): lista de
    polígonos [(x,y), ...] em coordenadas MUNDO do próprio DXF (mesmo espaço
    que ezdxf/matplotlib já usam para desenhar) — desenhados por cima como
    marco laranja translúcido (mesma cor/estilo do Comparison Engine,
    Semantic.WARNING #ff9800, ver src/ui/modules/comparison_engine.py e
    src/core/n2_marco_highlight.py)."""
    import io
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as _MplPolygon
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
        for poly in (highlight_polys or []):
            pts = [(float(p[0]), float(p[1])) for p in poly if len(p) >= 2]
            if len(pts) >= 3:
                # alpha 0.18 sobre fundo escuro do DXF lia como "amarelo" pro
                # dono (achado 27/07) em vez de laranja -- subiu pra 0.5 +
                # borda mais grossa pra ficar inconfundivel com a cor real
                # (#ff9800, mesma do Comparison Engine).
                ax.add_patch(_MplPolygon(
                    pts, closed=True, facecolor='#ff9800', edgecolor='none',
                    alpha=0.5, zorder=50,
                ))
                ax.add_patch(_MplPolygon(
                    pts, closed=True, fill=False, edgecolor='#ff9800',
                    linewidth=2.2, zorder=51,
                ))
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
