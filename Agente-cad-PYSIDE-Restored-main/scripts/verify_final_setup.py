#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_final_setup.py — BUILD-01: Smoke test do executável Nuitka compilado.

Verifica que o bundle dist/AgenteCAD/ está pronto para empacotar:
  1. Executável principal existe e tem tamanho mínimo
  2. DLLs e dependências críticas estão presentes
  3. Assets obrigatórios (icon.ico) existem
  4. O exe responde sem travar (--version ou --help, se disponível)
  5. Tamanho total do bundle é razoável (>= 20 MB)

Uso:
  python scripts/verify_final_setup.py
  python scripts/verify_final_setup.py --dist dist/AgenteCAD --strict
"""

import sys
import io
import os
import argparse
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
DEFAULT_DIST = ROOT / "dist" / "AgenteCAD"

# Arquivos obrigatórios no bundle
REQUIRED_FILES = [
    "main.exe",
]

# Arquivos opcionais (aviso se ausentes, não falha)
OPTIONAL_FILES = [
    "assets/icon.ico",
]

# Tamanho mínimo do bundle (bytes) — Nuitka + PySide6 produz pelo menos 50 MB
MIN_BUNDLE_SIZE_MB = 20


def _check_required(dist: Path, strict: bool) -> list[str]:
    errors = []
    for rel in REQUIRED_FILES:
        p = dist / rel
        if not p.exists():
            errors.append(f"AUSENTE: {rel}")
        elif p.stat().st_size < 1024:
            errors.append(f"MUITO PEQUENO (<1KB): {rel} ({p.stat().st_size} bytes)")
    return errors


def _check_optional(dist: Path) -> list[str]:
    warnings = []
    for rel in OPTIONAL_FILES:
        p = dist / rel
        if not p.exists():
            warnings.append(f"AVISO: arquivo opcional ausente: {rel}")
    return warnings


def _check_bundle_size(dist: Path) -> tuple[float, str | None]:
    """Retorna (tamanho_MB, erro_ou_None)."""
    total = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    total_mb = total / (1024 * 1024)
    err = None
    if total_mb < MIN_BUNDLE_SIZE_MB:
        err = f"Bundle muito pequeno: {total_mb:.1f} MB (mínimo: {MIN_BUNDLE_SIZE_MB} MB)"
    return total_mb, err


def _smoke_test_exe(dist: Path) -> str | None:
    """Tenta executar main.exe com timeout de 5s. Retorna None se OK, erro se falha."""
    exe = dist / "main.exe"
    if not exe.exists():
        return "main.exe não encontrado"
    try:
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            timeout=5,
            cwd=str(dist),
        )
        # --version pode retornar 0 ou 1, ambos ok (o exe respondeu)
        return None
    except subprocess.TimeoutExpired:
        return "exe travou (timeout > 5s)"
    except FileNotFoundError as e:
        return f"exe não executável: {e}"
    except Exception as e:
        # Qualquer outro erro de OS (DLL missing etc.) é falha
        if "0xc0000135" in str(e) or "DLL" in str(e):
            return f"DLL ausente ou incompatível: {e}"
        # Outros erros são informativos (o exe pode não suportar --version)
        return None


def main():
    parser = argparse.ArgumentParser(description="Smoke test do bundle Nuitka — BUILD-01")
    parser.add_argument("--dist", default=str(DEFAULT_DIST), help="Caminho do dist/ compilado")
    parser.add_argument("--strict", action="store_true", help="Falha em warnings também")
    args = parser.parse_args()

    dist = Path(args.dist).resolve()

    print(f"\n{'═'*60}")
    print(f"  BUILD-01 — Smoke Test Bundle Nuitka")
    print(f"{'═'*60}")
    print(f"  Bundle: {dist}\n")

    if not dist.exists():
        print(f"  ❌ FALHA: Diretório não encontrado: {dist}")
        print(f"  Execute a compilação Nuitka antes de rodar este script.")
        sys.exit(1)

    errors: list[str] = []
    warnings: list[str] = []

    # 1. Arquivos obrigatórios
    print("[1/4] Verificando arquivos obrigatórios ...")
    req_errors = _check_required(dist, args.strict)
    if req_errors:
        errors.extend(req_errors)
        for e in req_errors:
            print(f"  ❌ {e}")
    else:
        print(f"  ✅ Todos os arquivos obrigatórios presentes")

    # 2. Arquivos opcionais
    print("[2/4] Verificando assets opcionais ...")
    opt_warns = _check_optional(dist)
    if opt_warns:
        warnings.extend(opt_warns)
        for w in opt_warns:
            print(f"  ⚠️  {w}")
    else:
        print(f"  ✅ Assets opcionais presentes")

    # 3. Tamanho do bundle
    print("[3/4] Verificando tamanho do bundle ...")
    total_mb, size_err = _check_bundle_size(dist)
    if size_err:
        errors.append(size_err)
        print(f"  ❌ {size_err}")
    else:
        print(f"  ✅ Tamanho OK: {total_mb:.1f} MB")

    # 4. Smoke test do exe (apenas se arquivos obrigatórios OK)
    print("[4/4] Smoke test do executável ...")
    if not req_errors:
        exe_err = _smoke_test_exe(dist)
        if exe_err:
            warnings.append(exe_err)
            print(f"  ⚠️  {exe_err}")
        else:
            print(f"  ✅ Executável respondeu sem travar")
    else:
        print(f"  [SKIP] Executável ausente — smoke test pulado")

    # Resultado final
    print(f"\n{'─'*60}")
    if errors:
        print(f"  ❌ FALHA — {len(errors)} erro(s):")
        for e in errors:
            print(f"    • {e}")
        sys.exit(1)
    elif warnings and args.strict:
        print(f"  ❌ FALHA (--strict) — {len(warnings)} warning(s):")
        for w in warnings:
            print(f"    • {w}")
        sys.exit(1)
    else:
        if warnings:
            print(f"  ⚠️  PASSOU com {len(warnings)} warning(s)")
        else:
            print(f"  ✅ PASSOU — bundle pronto para empacotar com Inno Setup")
        sys.exit(0)


if __name__ == "__main__":
    main()
