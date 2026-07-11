"""Headless N3 PL: sempre PARA + PASSA (sem escolha manual)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_headless():
    path = ROOT / "scripts" / "arete" / "headless_sa_analise.py"
    spec = importlib.util.spec_from_file_location("headless_sa_analise", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Evita QT_QPA side effects pesados se já importado
    if "headless_sa_analise" in sys.modules:
        return sys.modules["headless_sa_analise"]
    spec.loader.exec_module(mod)
    return mod


def test_generate_pl_n3_function_exists_and_calls_dialog():
    mod = _load_headless()
    assert hasattr(mod, "_generate_pl_n3_nova_previews")

    calls = []

    class FakeDialog:
        def materialize_pl_n3_variants(self):
            calls.append("materialize")
            return ["P1_para", "P1_passa", "P2_para", "P2_passa"], []

    window = SimpleNamespace(
        _build_pre_validation_dialog=lambda: FakeDialog(),
    )
    generated, failed = mod._generate_pl_n3_nova_previews("Obra_X", window)
    assert calls == ["materialize"]
    assert failed == []
    assert "P1_para" in generated and "P1_passa" in generated
    assert "P2_para" in generated and "P2_passa" in generated


def test_generate_pl_n3_dialog_missing():
    mod = _load_headless()
    window = SimpleNamespace(_build_pre_validation_dialog=lambda: None)
    generated, failed = mod._generate_pl_n3_nova_previews("Obra_X", window)
    assert generated == []
    assert failed == ["dialog-ausente"]


def test_pre_validation_has_materialize_pl_n3_api():
    # Import leve da classe (pode puxar Qt — skip se ambiente sem display)
    try:
        from src.ui.widgets.pre_validation_dialog import PreValidationDialog
    except Exception as exc:
        pytest.skip(f"Qt/UI indisponível: {exc}")
    assert hasattr(PreValidationDialog, "materialize_pl_n3_variants")
    assert callable(PreValidationDialog.materialize_pl_n3_variants)
