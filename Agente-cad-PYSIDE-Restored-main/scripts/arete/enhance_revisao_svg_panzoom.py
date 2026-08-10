#!/usr/bin/env python3
"""Publica uma variante do painel humano com svg-pan-zoom, sem tocar no DB."""
from __future__ import annotations

import re
from pathlib import Path


SOURCE = Path(__file__).parent / "relatorios" / "revisao_pil_n2_n4_20260721_013525" / "index.html"
TARGET = SOURCE.with_name("index_panzoom.html")

LIBRARY = '<script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>'
STYLE = (
    '<style>.canvas{height:560px;overflow:hidden;cursor:grab}.canvas:active{cursor:grabbing}'
    '.canvas svg{width:100%;height:100%}.zoom-controls{display:none}</style>'
)
INITIALIZER = """if (typeof svgPanZoom === 'function') {
  document.querySelectorAll('.zoomable svg').forEach(svg => svgPanZoom(svg, {
    zoomEnabled: true, panEnabled: true, controlIconsEnabled: true,
    mouseWheelZoomEnabled: true, dblClickZoomEnabled: false,
    fit: true, center: true, minZoom: .4, maxZoom: 12,
    preventMouseEventsDefault: true
  }));
} else {
  document.querySelector('.notice').textContent += ' · Controle SVG indisponível.';
}
"""


def main() -> None:
    raw = SOURCE.read_text(encoding="utf-8")
    if "svg-pan-zoom@3.6.1" not in raw:
        raw = raw.replace("</style></head>", f"</style>{STYLE}{LIBRARY}</head>", 1)
    legacy = r"document\.querySelectorAll\('\.zoomable'\)\.forEach\(box=>\{[^\n]*\}\);\n"
    raw, changes = re.subn(legacy, INITIALIZER, raw, count=1)
    if changes != 1:
        raise RuntimeError("Inicializador de zoom anterior não encontrado")
    TARGET.write_text(raw, encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
