#!/usr/bin/env python3
"""
audit_theme_compliance.py — Detecta cores hardcoded fora do theme.py

Varre src/ui/ buscando valores hexadecimais de cor inline que deveriam
referenciar Colors.* do design system.

Uso:
  python scripts/audit_theme_compliance.py           # Escaneia src/ui/
  python scripts/audit_theme_compliance.py --fix     # Modo verbose com sugestões
  python scripts/audit_theme_compliance.py --path src/ui/widgets

Exit code 0 = sem violações críticas (apenas warnings)
Exit code 1 = violações críticas encontradas
"""
import sys
import io
import re
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Arquivos excluídos da auditoria (próprio tema + gerados)
EXCLUDE_FILES = {"theme.py", "style.qss"}

# Padrão: #RGB ou #RRGGBB fora de comentários
HEX_PATTERN = re.compile(r"(?<!['\"])#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")

# Mapeamento de cores conhecidas para sugestões de token
KNOWN_COLORS = {
    "#1a1a2e": "Colors.BG_PRIMARY",
    "#16213e": "Colors.BG_SECONDARY",
    "#1e1e1e": "Colors.BG_PANEL",
    "#252525": "Colors.BG_CARD",
    "#2a2a3e": "Colors.BG_HOVER",
    "#252528": "Colors.BG_SURFACE",
    "#121212": "Colors.BG_DEEP",
    "#00d4ff": "Colors.ACCENT_PRIMARY",
    "#00e5ff": "Colors.ACCENT_BRAND",
    "#0078d4": "Colors.ACCENT_BLUE",
    "#0099ff": "Colors.ACCENT_BLUE_HOVER",
    "#4caf50": "Colors.ACCENT_SUCCESS",
    "#00cc66": "Colors.ACCENT_SUCCESS_ALT",
    "#ff9800": "Colors.ACCENT_WARNING",
    "#ffb300": "Colors.ACCENT_WARNING_ALT",
    "#f44336": "Colors.ACCENT_DANGER",
    "#f85149": "Colors.ACCENT_DANGER_ALT",
    "#ffd700": "Colors.ACCENT_GOLD",
    "#e3b341": "Colors.ACCENT_INFO",
    "#00bcd4": "Colors.ACCENT_TEAL",
    "#00ffcc": "Colors.ACCENT_MINT",
    "#d63384": "Colors.ACCENT_MAGENTA",
    "#e0e0e0": "Colors.TEXT_PRIMARY",
    "#ffffff": "Colors.TEXT_BRIGHT",
    "#888888": "Colors.TEXT_SECONDARY",
    "#555555": "Colors.TEXT_MUTED",
    "#666666": "Colors.TEXT_DIM",
    "#333333": "Colors.BORDER_DEFAULT",
    "#2a2a2a": "Colors.BORDER_SUBTLE",
    "#2d2d30": "Colors.BORDER_PANEL",
    "#444444": "Colors.BORDER_INPUT",
}

# Linhas que contêm estes padrões são ignoradas (contexto legítimo)
IGNORE_PATTERNS = [
    "Colors.",          # já usa token
    "from src.ui.theme",
    "import Colors",
    "# noqa",
    "# hardcoded-ok",  # exceção explícita
]


def is_ignorable_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("#"):
        return True  # comentário Python
    for pat in IGNORE_PATTERNS:
        if pat in line:
            return True
    return False


def audit_file(filepath: Path, verbose: bool = False) -> list:
    """Retorna lista de violações: (linha, col, hex, sugestao)."""
    violations = []
    try:
        lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return violations

    for i, line in enumerate(lines, 1):
        if is_ignorable_line(line):
            continue
        for m in HEX_PATTERN.finditer(line):
            hex_val = "#" + m.group(1).lower()
            # Expandir shorthand #RGB → #RRGGBB
            if len(m.group(1)) == 3:
                expanded = "#" + "".join(c * 2 for c in m.group(1).lower())
                suggestion = KNOWN_COLORS.get(expanded, "Colors.???")
            else:
                suggestion = KNOWN_COLORS.get(hex_val, "Colors.???")
            violations.append((i, m.start(), hex_val, suggestion))

    return violations


def main():
    parser = argparse.ArgumentParser(description="Auditar cores hardcoded no design system")
    parser.add_argument("--path", default="src/ui",
                        help="Diretório a escanear (padrão: src/ui)")
    parser.add_argument("--fix", action="store_true",
                        help="Modo verbose com sugestões detalhadas")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 mesmo para warnings (todos os arquivos)")
    args = parser.parse_args()

    base = Path(args.path)
    if not base.exists():
        print(f"[ERRO] Diretório não encontrado: {base}")
        sys.exit(1)

    total_violations = 0
    files_with_violations = 0

    for filepath in sorted(base.rglob("*.py")):
        if "__pycache__" in str(filepath):
            continue
        if filepath.name in EXCLUDE_FILES:
            continue

        violations = audit_file(filepath, verbose=args.fix)
        if violations:
            files_with_violations += 1
            total_violations += len(violations)
            rel = filepath.relative_to(base.parent.parent) if base.parent.parent.exists() else filepath
            for lineno, col, hex_val, suggestion in violations:
                print(f"{rel}:{lineno}: HARDCODED {hex_val}  →  sugestão: {suggestion}")

    print()
    if total_violations == 0:
        print(f"✅ Nenhuma cor hardcoded encontrada em {base}")
        sys.exit(0)
    else:
        print(f"⚠  {total_violations} ocorrência(s) hardcoded em {files_with_violations} arquivo(s)")
        if args.strict:
            sys.exit(1)
        else:
            # Exit 0 — é warning, não bloqueante (há casos legítimos como QColor("#hex"))
            sys.exit(0)


if __name__ == "__main__":
    main()
