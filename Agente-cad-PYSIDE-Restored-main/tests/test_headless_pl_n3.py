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


@pytest.mark.parametrize(
    'section', ('pilares', 'lajes', 'fundos_viga', 'laterais_viga')
)
def test_n3_scope_respects_each_explicit_section_filter(section):
    mod = _load_headless()
    assert mod._n3_sections_for_run({section}) == {section}


def test_n3_scope_preserves_multiple_explicit_sections_and_full_default():
    mod = _load_headless()
    assert mod._n3_sections_for_run({"pilares", "lajes"}) == {
        "pilares", "lajes"
    }
    assert mod._n3_sections_for_run(None) == mod._VALID_SECTIONS


def test_attach_pl_variants_persists_the_same_para_and_passa_payloads():
    mod = _load_headless()
    payload = {'nome': 'P1', 'abertura_A_1': {'largura': 11}}
    cache = {
        ('P1', 'para'): {
            'contract': {'schema': 'pil.n3_mode_contract.v2', 'modo_semantico': 'PARA'},
            'payload': payload,
            'paths': {'json': 'para/P1.json', 'abcd': 'para/P1.dxf'},
        },
        ('P1', 'passa'): {
            'contract': {'schema': 'pil.n3_mode_contract.v2', 'modo_semantico': 'PASSA'},
            'payload': payload,
            'paths': {'json': 'passa/P1.json', 'abcd': 'passa/P1.dxf'},
        },
    }
    pillars = [{'name': 'P1'}, {'name': 'P2'}]

    assert mod._attach_pl_n3_variants_to_pillars(pillars, cache) == 1
    variants = pillars[0]['pl_n3_variants']
    assert set(variants) == {'para', 'passa'}
    assert variants['passa']['payload']['abertura_A_1']['largura'] == 11
    assert pillars[0]['pl_n3_variants_schema'] == 'pil.n3_variants/v1'
    assert 'pl_n3_variants' not in pillars[1]
    # O registro do SA não pode compartilhar o objeto mutável do cache HTML.
    assert variants['para']['payload'] is not payload


def test_pre_validation_has_materialize_pl_n3_api():
    # Import leve da classe (pode puxar Qt — skip se ambiente sem display)
    try:
        from src.ui.widgets.pre_validation_dialog import PreValidationDialog
    except Exception as exc:
        pytest.skip(f"Qt/UI indisponível: {exc}")
    assert hasattr(PreValidationDialog, "materialize_pl_n3_variants")
    assert callable(PreValidationDialog.materialize_pl_n3_variants)


def test_materialize_pl_n3_uses_dxf_only_export_mode():
    try:
        from src.ui.widgets.pre_validation_dialog import PreValidationDialog
    except Exception as exc:
        pytest.skip(f"Qt/UI indisponível: {exc}")

    class FakeDialog:
        def _export_html_snapshot(self, *, sections, materialize_pl_only):
            assert sections == {'pilares'}
            assert materialize_pl_only is True
            self._last_pl_n3_materialize = {
                'generated': ['P1_para', 'P1_passa'],
                'failed': [],
            }

    fake = FakeDialog()
    generated, failed = PreValidationDialog.materialize_pl_n3_variants(fake)
    assert generated == ['P1_para', 'P1_passa']
    assert failed == []
