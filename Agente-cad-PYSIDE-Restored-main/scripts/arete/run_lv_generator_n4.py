"""Adaptador N4 LV: preserva ocorrencias repetidas com detalhe proprio de ficha."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


GENERATOR = Path(__file__).resolve().parent.parent / "gerar_lv_dxf_stog.py"
sys.path.insert(0, str(GENERATOR.parent))
from lv_n4_face_unit_selection import install_occurrence_aware_key


def _load_generator():
    spec = importlib.util.spec_from_file_location("lv_generator_n4_runtime", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> None:
    motor = _load_generator()
    install_occurrence_aware_key(motor)
    motor.main()


if __name__ == "__main__":
    main()
