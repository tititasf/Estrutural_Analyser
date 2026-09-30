"""Inject N3 ABCD/GRADES 6-face SVGs into P26/P27 HTML (img-n3 only)."""
from __future__ import annotations

import re
from pathlib import Path

PACK = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas\Obra_TREINO_1\13_PAV_20260912_161058_141102_pilares_2520")
HTML_DIR = PACK / "pilares_especiais" / "INDETERMINADO"
PREVIEW = PACK / "cima_l_preview"


def prepare_svg(raw: str, aria: str) -> str:
    body = raw
    if body.startswith("<?xml"):
        body = re.sub(r"^<\?xml[^>]*>\s*", "", body)
        body = re.sub(r"<!DOCTYPE[^>]*>\s*", "", body, flags=re.I)
    if "aria-label" not in body[:400]:
        body = re.sub(
            r"<svg([^>]*)>",
            rf'<svg\1 class="img-n3" role="img" aria-label="{aria}" alt="{aria}">',
            body,
            count=1,
        )
    else:
        body = re.sub(r'class="[^"]*"', 'class="img-n3"', body, count=1)
    return body.strip()


def replace_n3_svgs(html: str, aria: str, svg: str, count: int = 2) -> tuple[str, int]:
    """Replace the first `count` img-n3 SVGs with this aria-label after N3 section."""
    n3 = html.find("N3 — Robô via N1")
    n4 = html.find("N4 — Robô via N2", n3 if n3 >= 0 else 0)
    if n3 < 0:
        n3 = 0
    if n4 < 0:
        n4 = len(html)
    head, mid, tail = html[:n3], html[n3:n4], html[n4:]
    pattern = re.compile(
        rf'<svg[^>]*aria-label="{aria}"[\s\S]*?</svg>',
        re.I,
    )
    replaced = 0

    def _sub(match):
        nonlocal replaced
        if replaced >= count:
            return match.group(0)
        replaced += 1
        return svg

    mid = pattern.sub(_sub, mid)
    return head + mid + tail, replaced


def patch_grades_table(html: str) -> str:
    extra = (
        "<tr><td>Lado E</td><td>ramo externo 176cm · gera grade · face L</td></tr>"
        "<tr><td>Lado F</td><td>ramo interno 153cm · gera grade · face L</td></tr>"
    )
    # Insert E/F rows before topo local if missing.
    if "Lado E" in html:
        return html
    return html.replace(
        "<tr><td>topo local</td>",
        extra + "<tr><td>topo local</td>",
        2,  # PARA + PASSA
    )


def main():
    for item in ("P26", "P27"):
        html_path = HTML_DIR / f"{item}.html"
        html = html_path.read_text(encoding="utf-8")
        abcd = prepare_svg((PREVIEW / f"{item}_abcd.svg").read_text(encoding="utf-8"), "ABCD")
        grades = prepare_svg((PREVIEW / f"{item}_grades.svg").read_text(encoding="utf-8"), "GRADES")
        html, n_abcd = replace_n3_svgs(html, "ABCD", abcd, 2)
        html, n_gr = replace_n3_svgs(html, "GRADES", grades, 2)
        html = patch_grades_table(html)
        html_path.write_text(html, encoding="utf-8")
        print(f"{item}: ABCD x{n_abcd} GRADES x{n_gr}")


if __name__ == "__main__":
    main()
