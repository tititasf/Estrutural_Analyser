"""N3 LAJ generation bridge using the same STOG DXF generator as N4."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "gerar_lj_dxf_stog.py"


def assert_laj_n3_matches_n4_contract(n3_ficha: dict, n4_ficha: dict) -> None:
    """Fail if N3 diverges from the N4 robot contract in geometry-critical fields."""
    critical_fields = ("coordenadas", "linhas_verticais", "linhas_horizontais")
    for field in critical_fields:
        if n3_ficha.get(field) != n4_ficha.get(field):
            raise ValueError(f"N3 LAJ diverge do contrato N4 no campo {field}")


def build_laj_n3_args(
    obra_path: str | Path,
    *,
    n1_json_dir: str | Path,
    out_dir: str | Path | None = None,
    item: str | None = None,
    mode: str = "planta",
) -> tuple[Path, list[str]]:
    args = [
        "--obra",
        str(obra_path),
        "--json-dir",
        str(n1_json_dir),
        "--mode",
        mode,
    ]
    if out_dir:
        args += ["--out-dir", str(out_dir)]
    if item:
        args += ["--item", str(item)]
    return SCRIPT_PATH, args


def gerar_laj_n3_from_n1(
    obra_path: str | Path,
    *,
    n1_json_dir: str | Path,
    out_dir: str | Path | None = None,
    item: str | None = None,
    timeout: int = 180,
) -> tuple[bool, Path | None]:
    script, args = build_laj_n3_args(
        obra_path, n1_json_dir=n1_json_dir, out_dir=out_dir, item=item
    )
    target_dir = Path(out_dir) if out_dir else Path(obra_path) / "Fase-3_N3_LAJ"
    expected = target_dir / (f"LJ_preview_{item}.dxf" if item else "LJ_stog_quality.dxf")
    try:
        result = subprocess.run(
            [sys.executable, str(script)] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, None
    return result.returncode == 0 and expected.exists(), expected if expected.exists() else None
