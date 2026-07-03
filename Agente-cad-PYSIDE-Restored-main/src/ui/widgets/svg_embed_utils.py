"""Helpers para embutir SVG inline nas fichas granulares N1-N4.

Renderizar como SVG (em vez de PNG base64) mantém texto/cota como <text> real
do DOM: Playwright lê rótulos via accessibility tree/DOM sem gastar visão,
reservando o screenshot para julgamento visual genuíno (hachura, contorno).
Ver `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` §5.1 para o racional completo.

Usado por `pre_validation_dialog.py` (onde o SVG é gerado via matplotlib) e
pelos geradores de ficha por classe (`preficha_laje_html.py`,
`preficha_fundo_html.py`, ...), que só embutem o markup já pronto — por isso
mora num módulo neutro em vez de um dos dois, para não criar import circular.
"""

from __future__ import annotations

import re

_SVG_ROOT_TAG_RE = re.compile(r'<svg\b[^>]*>')


def strip_fixed_size(svg_text: str) -> str:
    """Remove width/height fixos (pt) da tag <svg> raiz, mantendo o viewBox.

    Sem isso o SVG inline força um tamanho físico em pt independente do
    container HTML; sem width/height (só viewBox) o elemento vira um
    "replaced element" com aspect-ratio intrínseco, e o CSS existente das
    classes .img-geo/.img-n2/.img-n3/.img-n4 (width/height/object-fit)
    passa a controlar o tamanho normalmente, do mesmo jeito que já
    controlava a <img> equivalente.
    """
    m = _SVG_ROOT_TAG_RE.search(svg_text)
    if not m:
        return svg_text
    tag = m.group(0)
    tag_clean = re.sub(r'\s(width|height)="[^"]*"', '', tag)
    return svg_text[:m.start()] + tag_clean + svg_text[m.end():]


def embed_visual(payload: str, fmt: str, css_class: str, alt: str) -> str:
    """Constrói o markup de exibição de um artefato N1-N4, em PNG (<img>) ou
    SVG inline — mesma classe CSS nos dois casos, para reusar o CSS existente
    sem duplicar regra por formato.

    `payload` já deve vir sem width/height fixos quando fmt='svg' (ver
    `strip_fixed_size`, aplicado no ponto de geração do SVG).
    """
    if not payload:
        return ''
    if fmt == 'svg':
        m = _SVG_ROOT_TAG_RE.search(payload)
        if not m:
            return payload
        tag = m.group(0)
        # `alt` não é atributo padrão de <svg>, mas mantemos junto com
        # `aria-label` para os seletores `[alt=...]` (scripts de QA, testes)
        # funcionarem igual nos dois formatos (PNG <img> e SVG inline).
        tag_with_class = (
            tag[:-1] + f' class="{css_class}" role="img" '
            f'aria-label="{alt}" alt="{alt}">'
        )
        return payload[:m.start()] + tag_with_class + payload[m.end():]
    return f'<img class="{css_class}" src="data:image/png;base64,{payload}" alt="{alt}">'
