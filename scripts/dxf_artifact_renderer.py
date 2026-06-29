#!/usr/bin/env python3
"""Render canônico e determinístico para artefatos DXF validados."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

RENDERER_VERSION = "dxf-canonical-v1"
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 768
DEFAULT_DPI = 100
DEFAULT_BG = "#101318"


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def render_canonical_dxf(
    dxf_path: str | Path,
    output_png: str | Path,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    dpi: int = DEFAULT_DPI,
) -> dict[str, Any]:
    """Renderiza um DXF inteiro em dimensões fixas e retorna seu manifesto."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from PIL import Image

    dxf_path = Path(dxf_path).resolve()
    output_png = Path(output_png).resolve()
    if not dxf_path.exists():
        raise FileNotFoundError(dxf_path)
    output_png.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.readfile(str(dxf_path))
    modelspace = doc.modelspace()
    context = RenderContext(doc)

    def show_all_layers(properties):
        for layer in properties:
            layer.is_visible = True

    context.set_layer_properties_override(show_all_layers)
    fig = plt.figure(
        figsize=(width / dpi, height / dpi),
        dpi=dpi,
        facecolor=DEFAULT_BG,
    )
    ax = fig.add_axes([0.015, 0.015, 0.97, 0.97])
    ax.set_facecolor(DEFAULT_BG)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_axis_off()

    backend = MatplotlibBackend(ax)
    frontend = Frontend(context, backend, config=Configuration())
    frontend.draw_layout(modelspace, finalize=True)
    fig.savefig(
        str(output_png),
        dpi=dpi,
        facecolor=DEFAULT_BG,
        edgecolor="none",
        transparent=False,
    )
    plt.close(fig)

    with Image.open(output_png) as image:
        if image.size != (width, height):
            image = image.convert("RGB").resize(
                (width, height),
                Image.Resampling.LANCZOS,
            )
            image.save(output_png, format="PNG", optimize=False)

    layer_names = sorted(
        {
            str(getattr(entity.dxf, "layer", "0") or "0")
            for entity in modelspace
        }
    )
    manifest = {
        "renderer_version": RENDERER_VERSION,
        "source_path": str(dxf_path),
        "source_sha256": _sha256(dxf_path),
        "png_path": str(output_png),
        "png_sha256": _sha256(output_png),
        "width": width,
        "height": height,
        "background": DEFAULT_BG,
        "entity_count": len(modelspace),
        "layers": layer_names,
    }
    manifest_path = output_png.with_suffix(".json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest["manifest_path"] = str(manifest_path)
    return manifest
