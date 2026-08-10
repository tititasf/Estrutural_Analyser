"""Injeta chrome QA PIL (validadores + layers) em pack já exportado com N1 SVG.

Não re-renderiza N1: extrai SVG do painel near e reconstrói com toggle SA/Agêntico.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.pil_qa_notes_chrome import (  # noqa: E402
    css_pil_qa,
    js_pil_qa,
    n1_layer_toggle_and_layers,
    notes_grid_html,
    notes_store_tag,
)


def extract_near_far_svgs(html: str) -> tuple[str, str] | None:
    """Retorna (near_svg_inner, far_svg_inner) dos n1-svg existentes."""
    # after tabs patch: panels near/far
    m_near = re.search(
        r'data-n1panel="near"[\s\S]*?<div class="n1-svg">(.*?)</div>\s*</div>',
        html,
        re.S,
    )
    m_far = re.search(
        r'data-n1panel="far"[\s\S]*?<div class="n1-svg">(.*?)</div>\s*</div>',
        html,
        re.S,
    )
    if m_near and m_far:
        return m_near.group(1), m_far.group(1)
    # deeper: grab first two n1-svg with div depth
    starts = list(re.finditer(r'<div class="n1-svg">', html))
    if len(starts) < 2:
        return None

    def grab(start_end: int) -> str:
        i = start_end
        depth = 1
        j = i
        while j < len(html) and depth:
            if html.startswith("<div", j):
                depth += 1
                j += 4
            elif html.startswith("</div>", j):
                depth -= 1
                if depth == 0:
                    return html[i:j]
                j += 6
            else:
                j += 1
        return html[i:j]

    return grab(starts[0].end()), grab(starts[1].end())


def patch_one(path: Path, obra: str, pav: str) -> bool:
    html = path.read_text(encoding="utf-8")
    name = path.stem
    if 'id="pil-human-box"' in html and "pil-layer-toggle" in html:
        return False

    svgs = extract_near_far_svgs(html)
    if not svgs:
        print("  no n1 svg", name)
        return False
    near, far = svgs

    # remove old atencao-only block
    html = re.sub(
        r'<div class="sec atencao-sec">[\s\S]*?</div>\s*</div>\s*(?=</body>)',
        "",
        html,
        count=1,
    )
    # remove old single-field atencao js
    html = re.sub(
        r"<script>\s*\(function\(\)\{\s*var OBRA=[\s\S]*?</script>",
        "",
        html,
        count=1,
    )

    layers = n1_layer_toggle_and_layers(
        sa_svg=near,
        agent_svg="",
        item=name,
        proposal_src=f"../propostas/{name}_qa_proposta.svg",
    )
    n1_block = f"""
<div class="sec"><div class="sec-title">Foto N1 (SA) + Destaque agêntico</div>
<div class="sec-body">
<div class="n1-hint">N1 em <b>SVG</b>. No <b>próximo</b>: Destaque SA / Agêntico / Ambos.
Proposta: <code>../propostas/{name}_qa_proposta.svg</code></div>
<div class="n1-tabs" role="tablist">
  <button type="button" class="n1-tab active" data-n1tab="near" role="tab" aria-selected="true">N1 próximo</button>
  <button type="button" class="n1-tab" data-n1tab="far" role="tab" aria-selected="false">N1 distante</button>
</div>
<div class="n1-panel active" data-n1panel="near" role="tabpanel">
  <div class="n1-view-note">Contato/local — SA (vermelho) vs proposta agêntica (ciano P#).</div>
  {layers}
</div>
<div class="n1-panel" data-n1panel="far" role="tabpanel" hidden>
  <div class="n1-view-note">Contexto distante.</div>
  <div class="n1-svg">{far}</div>
</div>
</div></div>
"""
    # replace entire Foto N1 section
    html2, n = re.subn(
        r'<div class="sec"><div class="sec-title">Foto N1[\s\S]*?</div>\s*</div>\s*(?=<div class="sec">)',
        n1_block + "\n",
        html,
        count=1,
    )
    if n == 0:
        print("  no Foto N1 block", name)
        return False

    # inject CSS
    if ".pil-layer-toggle" not in html2:
        html2 = html2.replace("</style>", css_pil_qa() + "\n</style>", 1)
    # inject JS
    if 'id="pil-qa-notes"' not in html2:
        html2 = html2.replace("</head>", js_pil_qa() + "\n</head>", 1)
    # notes store
    if 'id="pil-notes-store"' not in html2:
        html2 = html2.replace("<body>", "<body>\n" + notes_store_tag() + "\n", 1)
    # notes grid before </body>
    grid = notes_grid_html(obra, pav, name)
    if 'id="pil-human-box"' not in html2:
        html2 = html2.replace("</body>", grid + "\n</body>")

    path.write_text(html2, encoding="utf-8")
    return True


def main() -> int:
    pack = Path(
        r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete"
        r"\html_fichas\Obra_TREINO_1\13_PAV_20260730_210556_pilares_abcd"
    )
    if len(sys.argv) > 1:
        pack = Path(sys.argv[1])
    (pack / "propostas").mkdir(exist_ok=True)
    obra, pav = "Obra_TREINO_1", "13_PAV"
    n = 0
    for f in sorted((pack / "pilares").glob("P*.html")):
        ok = patch_one(f, obra, pav)
        print(("ok" if ok else "skip"), f.name)
        if ok:
            n += 1
    print(f"[OK] {n} in {pack}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
