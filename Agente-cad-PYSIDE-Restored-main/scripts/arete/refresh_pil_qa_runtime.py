#!/usr/bin/env python
"""Atualiza somente o runtime QA PIL de fichas já geradas.

Não reinterpreta geometria, não redesenha SVG, não altera notas e não acessa o DB.
Serve para propagar correções do viewer (por exemplo namespace de glifos) a um
pack existente, com escopo explícito de itens.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.pil_qa_notes_chrome import js_pil_qa


SCRIPT_RE = re.compile(r'<script id="pil-qa-notes">[\s\S]*?</script>', re.MULTILINE)


def refresh_html(path: Path, *, dry_run: bool = False) -> str:
    html = path.read_text(encoding="utf-8")
    # O helper inclui quebras externas para composição em f-string. Removê-las
    # torna a substituição byte-idempotente em packs já atualizados.
    runtime = js_pil_qa().strip()
    if SCRIPT_RE.search(html):
        updated, count = SCRIPT_RE.subn(lambda _match: runtime, html, count=1)
        action = "updated"
    elif "</head>" in html:
        updated = html.replace("</head>", runtime + "\n</head>", 1)
        count = 1
        action = "inserted"
    else:
        raise ValueError(f"HTML sem </head>: {path}")
    if count != 1:
        raise RuntimeError(f"runtime PIL ambíguo ({count} ocorrências): {path}")
    if updated == html:
        return "unchanged"
    if not dry_run:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(path)
    return action


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--items", nargs="+", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pillars = args.pack / "pilares"
    changed = 0
    for item in args.items:
        if not re.fullmatch(r"P\d+[A-Za-z]?", item):
            raise ValueError(f"item PIL inválido: {item!r}")
        path = pillars / f"{item}.html"
        if not path.is_file():
            raise FileNotFoundError(path)
        action = refresh_html(path, dry_run=args.dry_run)
        changed += action != "unchanged"
        print(f"{item}: {action}")
    print(f"[OK] {changed}/{len(args.items)} ficha(s) alterada(s); dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
