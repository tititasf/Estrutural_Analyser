"""Aviso canônico: apresentação HTML/checkbox ≠ prova QA Arete."""

from __future__ import annotations

DISCLAIMER_SHORT = (
    "HTML/checkbox e score numérico são apresentação — não prova primária de "
    "interpretação N1 nem selo Arete. A prova vive no dossiê QA (hashes, "
    "adaptador, probe/parity/visual)."
)

DISCLAIMER_HTML_BANNER = ""


def banner_html(*, dossier_path: str | None = None) -> str:
    """Retorna string vazia (desativado do frontend HTML)."""
    return ""


def inject_into_html(document: str, *, dossier_path: str | None = None) -> str:
    """Retorna o documento intacto sem injetar banners."""
    return document
