"""Vector preview of a single emitted N5 sheet; source DXFs stay immutable."""
from pathlib import Path


def render_sheet(path: Path) -> bytes:
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend, svg, layout
    from ezdxf.addons.drawing.config import Configuration
    doc = ezdxf.readfile(path)
    backend = svg.SVGBackend()
    # Patterns closer than 0.1 CAD cm are below a pixel at sheet scale. This
    # display threshold prevents millions of invisible strokes, without
    # changing the original hatch definitions or exported DXF.
    Frontend(RenderContext(doc), backend, config=Configuration(
        min_hatch_line_distance=.1, hatching_timeout=10,
    )).draw_layout(doc.modelspace(), finalize=True)
    return backend.get_string(layout.Page(1485, 1050)).encode('utf8')
