"""Aviso canônico: apresentação HTML/checkbox ≠ prova QA Arete."""

from __future__ import annotations

DISCLAIMER_SHORT = (
    "HTML/checkbox e score numérico são apresentação — não prova primária de "
    "interpretação N1 nem selo Arete. A prova vive no dossiê QA (hashes, "
    "adaptador, probe/parity/visual)."
)

DISCLAIMER_HTML_BANNER = """
<aside class="qa-presentation-notice" role="note" data-qa-presentation="true"
 style="border:1px solid #b8860b;background:#2a2110;color:#f0d78c;padding:10px 12px;
 margin:0 0 14px 0;font:12px/1.4 monospace;border-radius:4px">
  <strong style="color:#ffd666">⚠ Apresentação ≠ prova</strong><br>
  HTML, checkbox e score numérico <em>não</em> selam interpretação N1 nem Arete.
  Prova = dossiê QA com grafo de proveniência, SHA-256, adaptador e veredito visual registrado.
  <span class="qa-dossier-hint" data-role="dossier-link-slot"></span>
</aside>
""".strip()


def banner_html(*, dossier_path: str | None = None) -> str:
    """Retorna o banner HTML; opcionalmente inclui caminho clicável do dossiê."""
    if not dossier_path:
        return DISCLAIMER_HTML_BANNER
    link = (
        f'<br>Dossiê QA: <a href="file:///{dossier_path.replace(chr(92), "/")}" '
        f'style="color:#78b7ff">{dossier_path}</a>'
    )
    return DISCLAIMER_HTML_BANNER.replace(
        '<span class="qa-dossier-hint" data-role="dossier-link-slot"></span>',
        link,
    )


def inject_into_html(document: str, *, dossier_path: str | None = None) -> str:
    """Injeta o banner logo após a abertura de <body...> em HTML gerado."""
    if not document or "data-qa-presentation" in document:
        return document
    notice = banner_html(dossier_path=dossier_path)
    lower = document.lower()
    body_idx = lower.find("<body")
    if body_idx < 0:
        return notice + document
    close = document.find(">", body_idx)
    if close < 0:
        return notice + document
    return document[: close + 1] + notice + document[close + 1 :]
