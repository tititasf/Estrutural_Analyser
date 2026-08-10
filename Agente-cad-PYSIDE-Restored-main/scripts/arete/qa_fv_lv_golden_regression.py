#!/usr/bin/env python3
"""Compat: redireciona para o golden unificado das 4 classes (só FV/LV por default).

Preferir: scripts/arete/qa_class_golden_regression.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.arete.qa_class_golden_regression import DEFAULT_BASELINE as UNIFIED_BASELINE
from scripts.arete.qa_class_golden_regression import main as unified_main

# baseline legado FV/LV ainda honrado se o caller passar --baseline default antigo
LEGACY_BASELINE = (
    REPO / "scripts" / "arete" / "qa_requests" / "golden" / "fv_lv_13pav_baseline.json"
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # força só FV+LV se o caller não passou --classe
    if not any(a == "--classe" or a.startswith("--classe=") for a in args):
        args = ["--classe", "FV", "--classe", "LV", *args]
    # se não passou baseline, usa legado para não quebrar scripts antigos
    if "--baseline" not in args and not any(a.startswith("--baseline=") for a in args):
        baseline = LEGACY_BASELINE if LEGACY_BASELINE.is_file() else UNIFIED_BASELINE
        args = ["--baseline", str(baseline), *args]
    return unified_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
