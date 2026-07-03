#!/usr/bin/env python3
"""Injeta o bloco 'Geracao N4 dos diagramas' (carousel com SVGs ABCD/CIMA/
GRADES gerados por gen_casos_n4_standalone.py + dxf_to_svg_casos.py) dentro
do bloco <div class="caso"> de um caso especifico na ficha
interpretacao_abcd.html, logo apos o </div> que fecha .caso-body (antes do
</div> que fecha .caso).

Ancora na string exata `id="c{N}-counter"` (contador do carousel de
diagramas de referencia) e localiza, a partir dali, a sequencia fixa de 5
</div> que fecha nav -> carousel -> caso-diag -> caso-body -> caso.
"""
import sys
import argparse
from pathlib import Path

HTML_PATH = Path(
    "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/arete/"
    "html_fichas/Obra_TREINO_1/13_PAV_20260630_203509/pilares/interpretacao_abcd.html"
)
SVG_DIR = Path(__file__).parent / 'tmp' / 'n4_casos_abcd' / 'svg'

ZONE_LABELS = [
    ('abcd', 'N4 — Painéis ABCD (motor gerar_pl_dxf_stog.py, standalone)'),
    ('cima', 'N4 — Cima (seção transversal)'),
    ('grades', 'N4 — Grades (sarrafos / pontaletes)'),
]

CLOSE_SEQUENCE = (
    "          </div>\n"   # closes carousel-nav
    "        </div>\n"     # closes carousel
    "      </div>\n"       # closes caso-diag
    "    </div>\n"         # closes caso-body
    "  </div>\n"           # closes caso
)


def build_block(caso_num: int) -> str:
    slides = []
    for i, (zone, label) in enumerate(ZONE_LABELS):
        svg_path = SVG_DIR / f'caso{caso_num}_{zone}.svg'
        svg_text = svg_path.read_text(encoding='utf-8')
        active = ' active' if i == 0 else ''
        slides.append(
            f'            <div class="carousel-slide{active}">\n'
            f'              <div class="n4-svg-box">\n{svg_text}\n              </div>\n'
            f'              <div class="slide-label">{label}</div>\n'
            f'            </div>'
        )
    slides_html = '\n'.join(slides)
    cid = f'n4-c{caso_num}'
    return (
        f'      <div class="caso-n4">\n'
        f'        <div class="caso-n4-title">Geração N4 dos diagramas — resultado real do motor (standalone, sem obra)</div>\n'
        f'        <div class="carousel" id="{cid}">\n'
        f'          <div class="carousel-slides">\n{slides_html}\n          </div>\n'
        f'          <div class="carousel-nav">\n'
        f'            <button class="carousel-btn" onclick="prevSlide(\'{cid}\')">&#8249;</button>\n'
        f'            <span class="carousel-counter" id="{cid}-counter">1 / {len(ZONE_LABELS)}</span>\n'
        f'            <button class="carousel-btn" onclick="nextSlide(\'{cid}\')">&#8250;</button>\n'
        f'          </div>\n'
        f'        </div>\n'
        f'      </div>\n'
    )


def inject(caso_num: int):
    html = HTML_PATH.read_text(encoding='utf-8')
    marker = f'<!-- caso-n4-marker-{caso_num} -->'
    if marker in html:
        print(f'Caso {caso_num}: ja injetado, pulando (remova o marcador pra re-gerar).')
        return

    anchor = f'id="c{caso_num}-counter"'
    a_idx = html.find(anchor)
    if a_idx == -1:
        print(f'Caso {caso_num}: ancora {anchor!r} nao encontrada.', file=sys.stderr)
        sys.exit(1)

    seq_idx = html.find(CLOSE_SEQUENCE, a_idx)
    if seq_idx == -1:
        print(f'Caso {caso_num}: sequencia de fechamento nao encontrada apos a ancora.', file=sys.stderr)
        sys.exit(1)

    # Posicao logo apos o 4o </div> (fecha caso-body), antes do 5o (fecha caso)
    lines = CLOSE_SEQUENCE.split('\n')
    prefix_4 = '\n'.join(lines[:4]) + '\n'
    insert_at = seq_idx + len(prefix_4)

    block = build_block(caso_num) + marker + '\n'
    html = html[:insert_at] + block + html[insert_at:]
    HTML_PATH.write_text(html, encoding='utf-8')
    print(f'Caso {caso_num}: injetado ok (em offset {insert_at}).')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', type=int, required=True)
    args = ap.parse_args()
    inject(args.caso)
