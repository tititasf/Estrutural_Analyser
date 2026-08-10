#!/usr/bin/env python3
"""Remove elementos indesejados das fichas HTML de fundos de viga já geradas.

Remove:
  1. Banner <aside class="qa-presentation-notice">...</aside>
  2. Sidebar <aside class="sidebar">...</aside> (incluindo script de flags)
  3. Bloco <!-- ARETE_FV_DIAGNOSTIC_START -->...<!-- ARETE_FV_DIAGNOSTIC_END -->

Pode ser rodado em uma pasta ou arquivo específico.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# ── Padrões de remoção ────────────────────────────────────────────────────────

_PATTERNS: list[tuple[str, str]] = [
    # 1. Banner "Apresentação ≠ prova"
    (
        r'<aside\s[^>]*class="qa-presentation-notice"[^>]*>.*?</aside>',
        'qa-presentation-notice aside',
    ),
    # 2. Sidebar (inclui o <script> de erro-flag logo após)
    (
        r'<aside\s[^>]*class="sidebar"[^>]*>.*?</aside>\s*(?:<script>[^<]*?\.sidebar[^<]*?</script>)?',
        'sidebar aside',
    ),
    # 3. Diagnóstico automático N1×N2
    (
        r'<!-- ARETE_FV_DIAGNOSTIC_START -->.*?<!-- ARETE_FV_DIAGNOSTIC_END -->',
        'ARETE_FV_DIAGNOSTIC block',
    ),
]

_FLAGS = re.DOTALL | re.IGNORECASE


def clean_html(text: str) -> tuple[str, list[str]]:
    """Remove os blocos indesejados do documento HTML. Retorna (texto_limpo, changes)."""
    changes: list[str] = []
    for pattern, label in _PATTERNS:
        new_text, count = re.subn(pattern, '', text, flags=_FLAGS)
        if count:
            changes.append(f'  removido: {label} ({count}x)')
            text = new_text
    return text, changes


def process_file(path: Path, dry_run: bool = False) -> bool:
    """Processa um arquivo HTML. Retorna True se houve modificação."""
    try:
        original = path.read_text(encoding='utf-8')
    except Exception as exc:
        print(f'[ERRO] {path}: {exc}')
        return False

    cleaned, changes = clean_html(original)
    if not changes:
        print(f'[OK] {path.name} — sem blocos a remover')
        return False

    print(f'[MOD] {path.name}')
    for c in changes:
        print(c)

    if not dry_run:
        path.write_text(cleaned, encoding='utf-8')
        print(f'  → gravado ({len(cleaned):,} bytes, redução {len(original)-len(cleaned):,} bytes)')
    else:
        print('  → dry-run: arquivo não alterado')

    return True


def main() -> None:
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    paths_raw = [a for a in args if not a.startswith('--')]

    if not paths_raw:
        # Default: todas as fichas da última run de fundos_viga
        script_dir = Path(__file__).resolve().parent
        html_fichas = script_dir / 'html_fichas'
        targets: list[Path] = []
        for html_file in html_fichas.rglob('fundos_viga/*.html'):
            if html_file.name != 'index.html' and not html_file.name.startswith('interpretacao_'):
                targets.append(html_file)
        if not targets:
            print('[AVISO] Nenhum arquivo fundos_viga/*.html encontrado em html_fichas/')
            return
    else:
        targets = []
        for raw in paths_raw:
            p = Path(raw)
            if p.is_dir():
                targets.extend(p.rglob('fundos_viga/*.html'))
            elif p.is_file():
                targets.append(p)
            else:
                print(f'[AVISO] Caminho não encontrado: {raw}')

    modified = 0
    for target in sorted(set(targets)):
        if process_file(target, dry_run=dry_run):
            modified += 1

    print(f'\n[TOTAL] {modified}/{len(targets)} arquivo(s) modificado(s)')


if __name__ == '__main__':
    main()
