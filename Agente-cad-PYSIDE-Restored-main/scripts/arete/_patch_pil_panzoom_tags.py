"""Injeta pan/zoom no N1 das fichas PIL e atualiza CSS/JS do chrome."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.pil_qa_notes_chrome import css_pil_qa, js_pil_qa  # noqa: E402


def patch_one(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    name = path.stem
    changed = False

    # refresh CSS block for pil-* (replace from .pil-layer-toggle through notes-status)
    if ".pil-panzoom{" not in html:
        # inject panzoom rules before </style> of first style that has pil-layer
        if ".pil-layer-toggle" in html:
            html = html.replace(
                ".pil-n1-layers{position:relative;width:100%;background:#0d0d0d;border:1px solid #222;border-radius:4px}",
                "",
                1,
            )
            html = html.replace(
                ".pil-layer{width:100%}",
                "",
                1,
            )
            # append full css_pil_qa once
            # strip old pil css roughly by re-injecting full sheet after body fonts
            extra = css_pil_qa()
            if ".pil-panzoom{" not in html:
                html = html.replace("</style>", extra + "\n</style>", 1)
                changed = True
        else:
            html = html.replace("</style>", css_pil_qa() + "\n</style>", 1)
            changed = True

    # refresh JS: replace pil-qa-notes script
    new_js = js_pil_qa()
    if 'id="pil-qa-notes"' in html:
        html2, n = re.subn(
            r'<script id="pil-qa-notes">[\s\S]*?</script>',
            new_js,
            html,
            count=1,
        )
        if n:
            html = html2
            changed = True
    else:
        html = html.replace("</head>", new_js + "\n</head>", 1)
        changed = True

    # wrap near layers in panzoom if missing
    if f'id="pil-n1-near-{name}"' not in html and "data-ctx-layers" in html:
        # insert toggle is outside; wrap pil-n1-layers
        def wrap_layers(m):
            block = m.group(0)
            if "pil-panzoom" in block:
                return block
            return (
                f'<div id="pil-n1-near-{name}" class="pil-panzoom" data-panzoom="1" data-pil-pz="1">'
                f'<button type="button" class="pil-panzoom-reset" data-pz-reset="pil-n1-near-{name}">Reset zoom</button>'
                f'<div class="pil-panzoom-hint">scroll zoom · arrastar · duplo-clique reset</div>'
                f'<div class="pil-panzoom-inner" data-pz-inner="1">{block}</div></div>'
            )

        html2, n = re.subn(
            r'<div class="pil-n1-layers" data-ctx-layers="1">[\s\S]*?</div>\s*</div>\s*</div>',
            wrap_layers,
            html,
            count=1,
        )
        # fallback simpler
        if n == 0:
            html2, n = re.subn(
                r'(<div class="pil-n1-layers" data-ctx-layers="1">[\s\S]*?</div>)\s*(</div>\s*</div>\s*<div class="n1-panel")',
                lambda m: (
                    f'<div id="pil-n1-near-{name}" class="pil-panzoom" data-panzoom="1" data-pil-pz="1">'
                    f'<button type="button" class="pil-panzoom-reset" data-pz-reset="pil-n1-near-{name}">Reset zoom</button>'
                    f'<div class="pil-panzoom-hint">scroll zoom · arrastar · duplo-clique reset</div>'
                    f'<div class="pil-panzoom-inner" data-pz-inner="1">{m.group(1)}</div></div>{m.group(2)}'
                ),
                html,
                count=1,
            )
        if n:
            html = html2
            changed = True

    # far panel panzoom
    if f'id="pil-n1-far-{name}"' not in html:
        html2, n = re.subn(
            r'(data-n1panel="far"[^>]*>\s*<div class="n1-view-note">[^<]*</div>\s*)'
            r'(<div class="n1-svg">[\s\S]*?</div>)\s*(</div>)',
            lambda m: (
                f'{m.group(1)}'
                f'<div id="pil-n1-far-{name}" class="pil-panzoom" data-panzoom="1" data-pil-pz="1">'
                f'<button type="button" class="pil-panzoom-reset" data-pz-reset="pil-n1-far-{name}">Reset zoom</button>'
                f'<div class="pil-panzoom-hint">scroll zoom · arrastar · duplo-clique reset</div>'
                f'<div class="pil-panzoom-inner" data-pz-inner="1">{m.group(2)}</div></div>'
                f'{m.group(3)}'
            ),
            html,
            count=1,
        )
        if n:
            html = html2
            changed = True

    # hint legend
    if "scroll=zoom" not in html and "pil-hl-legend" in html:
        html = html.replace(
            '<b class="ag">QA</b> ciano/verde</span>',
            '<b class="ag">QA</b> ciano/verde · scroll=zoom · arraste=pan</span>',
            1,
        )
        changed = True

    if changed:
        path.write_text(html, encoding="utf-8")
    return changed


def main() -> int:
    pack = Path(
        r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete"
        r"\html_fichas\Obra_TREINO_1\13_PAV_20260730_210556_pilares_abcd\pilares"
    )
    if len(sys.argv) > 1:
        pack = Path(sys.argv[1])
    n = 0
    for f in sorted(pack.glob("P*.html")):
        if patch_one(f):
            print("ok", f.name)
            n += 1
        else:
            print("skip", f.name)
    print(f"[OK] {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
