"""
test_theme_compliance.py — DESIGN-01
Verifica que não existem cores hex hardcoded em src/ui/ sem justificativa.
Usa a mesma lógica do scripts/audit_theme_compliance.py mas como pytest.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC_UI = ROOT / "src" / "ui"

# Padrão: #RGB ou #RRGGBB — exclui seletores CSS (#SomeName) via lookbehind
# Um hex color nunca é precedido por letra/underscore (que seria um seletor ID CSS)
HEX_PATTERN = re.compile(r'(?<![A-Za-z_])#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?(?![0-9A-Fa-f A-Za-z_])')

# Linhas isentas de violation:
IGNORE_PATTERNS = [
    re.compile(r'Colors\.'),            # Já usa token
    re.compile(r'^\s*#'),               # Comentário Python
    re.compile(r'#\s*hardcoded-ok'),    # Exceção explícita declarada
    re.compile(r'^\s*from\s+'),         # Import line
    re.compile(r'^\s*import\s+'),       # Import line
    re.compile(r'=\s*"#[0-9A-Fa-f]'),  # Definição de token em theme.py
    re.compile(r"=\s*'#[0-9A-Fa-f]"),  # Definição de token em theme.py (single quote)
]

def _should_ignore_line(line: str) -> bool:
    for pat in IGNORE_PATTERNS:
        if pat.search(line):
            return True
    return False

def _collect_violations() -> list[tuple[str, int, str]]:
    """Retorna lista de (arquivo_relativo, linha, conteudo) para cada violação."""
    violations = []
    for py_file in SRC_UI.rglob("*.py"):
        # Pular o próprio theme.py (ele define os tokens)
        if py_file.name == "theme.py":
            continue
        try:
            lines = py_file.read_text(encoding="utf-8-sig").splitlines()
        except Exception:
            continue
        for lineno, line in enumerate(lines, start=1):
            if _should_ignore_line(line):
                continue
            if HEX_PATTERN.search(line):
                rel = str(py_file.relative_to(ROOT))
                violations.append((rel, lineno, line.strip()))
    return violations


def test_no_hardcoded_hex_colors():
    """Todos os hex colors em src/ui/ devem usar Colors.TOKEN ou ter # hardcoded-ok."""
    violations = _collect_violations()
    if violations:
        lines = [f"  {f}:{n}  →  {c}" for f, n, c in violations]
        msg = (
            f"\n{len(violations)} hardcoded hex color(s) found in src/ui/.\n"
            "Use Colors.<TOKEN> from src/ui/theme.py, or add '# hardcoded-ok' comment.\n\n"
            + "\n".join(lines)
        )
        assert False, msg


def test_theme_file_parseable():
    """theme.py deve ser importável como módulo (sem erros de sintaxe)."""
    theme_path = ROOT / "src" / "ui" / "theme.py"
    assert theme_path.exists(), "src/ui/theme.py não encontrado"
    source = theme_path.read_text(encoding="utf-8-sig")
    try:
        compile(source, str(theme_path), "exec")
    except SyntaxError as e:
        assert False, f"theme.py tem erro de sintaxe: {e}"


def test_colors_class_has_required_tokens():
    """Colors deve conter os tokens mínimos necessários."""
    required = [
        "BG_PRIMARY", "BG_PANEL", "BG_CARD", "BG_HOVER", "BG_DEEP",
        "ACCENT_PRIMARY", "ACCENT_BLUE", "ACCENT_SUCCESS", "ACCENT_DANGER",
        "TEXT_PRIMARY", "TEXT_BRIGHT", "TEXT_SECONDARY", "TEXT_MUTED",
        "BORDER_DEFAULT", "BORDER_INPUT",
    ]
    theme_path = ROOT / "src" / "ui" / "theme.py"
    source = theme_path.read_text(encoding="utf-8-sig")
    missing = [tok for tok in required if tok not in source]
    assert not missing, f"Tokens ausentes em Colors: {missing}"
