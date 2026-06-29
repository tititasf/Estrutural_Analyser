"""Validate the only supported CAD-ANALYZER Python runtime."""

from __future__ import annotations

import argparse
import importlib
import sys


SUPPORTED_VERSION = (3, 12)
CORE_IMPORTS = ("numpy", "PySide6", "ezdxf", "chromadb")


def validate_version() -> None:
    current = sys.version_info[:2]
    if current != SUPPORTED_VERSION:
        expected = ".".join(map(str, SUPPORTED_VERSION))
        actual = ".".join(map(str, current))
        raise RuntimeError(
            f"CAD-ANALYZER exige Python {expected}.x; runtime atual: {actual}. "
            "Use iniciar_dashboard.bat ou D:\\Agente-cad-PYSIDE\\.venv\\Scripts\\python.exe."
        )


def validate_imports() -> None:
    failures: list[str] = []
    for module_name in CORE_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - reports environment failures
            failures.append(f"{module_name}: {exc}")
    if failures:
        details = "\n  - ".join(failures)
        raise RuntimeError(f"Dependencias essenciais indisponiveis:\n  - {details}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-imports", action="store_true")
    args = parser.parse_args()

    try:
        validate_version()
        if args.check_imports:
            validate_imports()
    except RuntimeError as exc:
        print(f"ERRO DE RUNTIME: {exc}", file=sys.stderr)
        return 2

    print(f"Runtime OK: Python {sys.version.split()[0]} ({sys.executable})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
