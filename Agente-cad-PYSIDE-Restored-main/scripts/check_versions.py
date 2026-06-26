#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_versions.py — BUILD-02: Verifica versões e injeta em installer.iss

Lê APP_VERSION de src/config.py (fonte da verdade) e:
  1. Verifica coerência entre src/config.py, pyproject.toml (se existir) e installer.iss
  2. Injeta a versão no installer.iss (define MyAppVersion + OutputBaseFilename)
  3. Exibe relatório de versões

Uso:
  python scripts/check_versions.py            # Apenas verificar
  python scripts/check_versions.py --inject   # Verificar + injetar no installer.iss
  python scripts/check_versions.py --inject --strict  # Falha se versões divergem
"""

import sys
import io
import re
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
CONFIG_PY   = ROOT / "src" / "config.py"
INSTALLER   = ROOT / "scripts" / "installer.iss"
PYPROJECT   = ROOT / "pyproject.toml"


def _read_config_version() -> str | None:
    """Lê APP_VERSION de src/config.py."""
    if not CONFIG_PY.exists():
        return None
    text = CONFIG_PY.read_text(encoding="utf-8-sig")
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def _read_installer_version() -> str | None:
    """Lê a versão definida em installer.iss (#define MyAppVersion)."""
    if not INSTALLER.exists():
        return None
    text = INSTALLER.read_text(encoding="utf-8")
    m = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', text)
    return m.group(1) if m else None


def _read_pyproject_version() -> str | None:
    """Lê version de pyproject.toml [project] ou [tool.poetry.version]."""
    if not PYPROJECT.exists():
        return None
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return m.group(1) if m else None


def _inject_version(version: str) -> bool:
    """Injeta APP_VERSION no installer.iss. Retorna True se alterou o arquivo."""
    if not INSTALLER.exists():
        print(f"  [SKIP] installer.iss não encontrado: {INSTALLER}")
        return False

    text = INSTALLER.read_text(encoding="utf-8")
    original = text

    # Substituir #define MyAppVersion "X.Y.Z"
    text = re.sub(
        r'(#define\s+MyAppVersion\s+)"[^"]+"',
        f'\\1"{version}"',
        text,
    )
    # Substituir OutputBaseFilename "AgenteCAD_Setup_vX.Y.Z"
    text = re.sub(
        r'(#define\s+OutputBaseFilename\s+)"AgenteCAD_Setup_v[^"]+"',
        f'\\1"AgenteCAD_Setup_v{version}"',
        text,
    )

    if text == original:
        return False

    INSTALLER.write_text(text, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description="Verificação e injeção de versão — BUILD-02")
    parser.add_argument("--inject", action="store_true", help="Injeta versão no installer.iss")
    parser.add_argument("--strict", action="store_true", help="Falha se versões divergem entre fontes")
    args = parser.parse_args()

    print(f"\n{'═'*60}")
    print(f"  BUILD-02 — Check Versions & Inject into installer.iss")
    print(f"{'═'*60}\n")

    config_ver    = _read_config_version()
    installer_ver = _read_installer_version()
    pyproject_ver = _read_pyproject_version()

    print(f"  src/config.py    → {config_ver or 'NÃO ENCONTRADO'}")
    print(f"  installer.iss    → {installer_ver or 'NÃO ENCONTRADO'}")
    print(f"  pyproject.toml   → {pyproject_ver or 'não existe / não definida'}")

    if config_ver is None:
        print(f"\n  ❌ FALHA: APP_VERSION não encontrado em {CONFIG_PY}")
        sys.exit(1)

    # Verificar coerência
    mismatches = []
    if installer_ver and installer_ver != config_ver:
        mismatches.append(f"installer.iss={installer_ver} ≠ config.py={config_ver}")
    if pyproject_ver and pyproject_ver != config_ver:
        mismatches.append(f"pyproject.toml={pyproject_ver} ≠ config.py={config_ver}")

    if mismatches:
        for m in mismatches:
            print(f"\n  ⚠️  Divergência: {m}")
        if args.strict and not args.inject:
            print(f"\n  ❌ FALHA (--strict): versões divergem. Use --inject para corrigir.")
            sys.exit(1)
    else:
        print(f"\n  ✅ Versões coerentes: {config_ver}")

    # Injetar
    if args.inject:
        print(f"\n  Injetando v{config_ver} em installer.iss ...")
        changed = _inject_version(config_ver)
        if changed:
            new_ver = _read_installer_version()
            print(f"  ✅ installer.iss atualizado → MyAppVersion={new_ver}")
            print(f"     OutputBaseFilename=AgenteCAD_Setup_v{config_ver}")
        else:
            print(f"  [SKIP] installer.iss já está na versão {config_ver} — sem alterações")

    print(f"\n{'─'*60}")
    print(f"  Versão de produção: {config_ver}")
    print(f"  Fonte da verdade:   src/config.py → APP_VERSION\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
