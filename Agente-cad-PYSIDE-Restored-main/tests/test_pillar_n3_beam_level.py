"""Regressões do nível N1 usado nas vigas passantes do N3 de pilares."""
from __future__ import annotations

import pytest

from src.ui.widgets.pre_validation_dialog import (
    _n3_apply_height_contract,
    _n3_opening_y_rel,
    _n3_variant_web_override,
    _parse_n3_beam_detail,
)


def test_parse_pass_beam_preserves_name_section_and_absolute_level():
    parsed = _parse_n3_beam_detail(
        "Viga: VF301  ·  dim: 19/66  ·  N: 852.19cm  ·  passa CB"
    )

    assert parsed["nome"] == "VF301"
    assert parsed["largura"] == 19.0
    assert parsed["profundidade"] == 66.0
    assert parsed["nivel"] == 852.19


def test_p1_face_c_pass_beam_uses_n1_level_instead_of_top_fallback():
    y_rel = _n3_opening_y_rel(
        level=852.19,
        base_level=848.98,
        opening_height=70.0,
        panel_height=321.0,
        h1=2.0,
        fallback=34.0,
    )

    assert y_rel == pytest.approx(249.0)


def test_n3_beam_level_is_clamped_to_drawable_panel_extent():
    assert _n3_opening_y_rel(
        level=900.0,
        base_level=848.98,
        opening_height=70.0,
        panel_height=321.0,
        h1=2.0,
        fallback=34.0,
    ) == pytest.approx(249.0)


def test_height_contract_is_applied_before_para_opening_clamp():
    base = {"altura": 280.0}
    contract = {
        "altura_pilar": {
            "nivel_saida_abs": 848.98,
            "nivel_chegada_abs": 852.19,
        },
    }

    height = _n3_apply_height_contract(base, contract)
    y_rel = _n3_opening_y_rel(
        level=852.19,
        base_level=848.98,
        opening_height=54.0,
        panel_height=height,
        h1=2.0,
        fallback=224.0,
    )

    assert height == pytest.approx(321.0)
    assert base["altura"] == pytest.approx(321.0)
    assert base["pd_pavimento_cm"] == pytest.approx(321.0)
    assert y_rel == pytest.approx(265.0)


def test_missing_level_keeps_legacy_fallback_for_old_contracts():
    assert _n3_opening_y_rel(
        level=None,
        base_level=848.98,
        opening_height=70.0,
        panel_height=321.0,
        h1=2.0,
        fallback=34.0,
    ) == pytest.approx(34.0)


def test_web_override_is_scoped_to_requested_n3_variant():
    saved = {
        "schema": "pil.n3.web_ficha/v1",
        "faces": {"A": {"legacy": True}},
        "variants": {
            "para": {"schema": "pil.n3.web_ficha/v1", "marker": "PARA"},
            "passa": {"schema": "pil.n3.web_ficha/v1", "marker": "PASSA"},
        },
    }

    assert _n3_variant_web_override(saved, "passa")["marker"] == "PASSA"
    assert _n3_variant_web_override(saved, "para")["marker"] == "PARA"
    assert _n3_variant_web_override(saved, "inexistente") is None


def test_legacy_unscoped_web_ficha_does_not_leak_between_n3_variants():
    saved = {
        "schema": "pil.n3.web_ficha/v1",
        "source": {"human_override": True},
        "faces": {"C": {"openings": {"right": [{"width": 27}]}}},
    }

    assert _n3_variant_web_override(saved, "passa") is None


def test_passa_enrichment_preserves_level_derived_y_instead_of_forcing_top():
    from pl_abcd_visual_nova import enrich_payload_for_abcd_nova

    payload = {
        "nome": "PLEVEL",
        "altura": 321.0,
        "h1_C": 2.0,
        "abertura_C_1": {
            "lado": "meio",
            "largura": 19.0,
            "altura": 70.0,
            "y_rel": 180.0,
            "_origem": "CC",
            "_nivel_origem": 851.50,
        },
        "_sa_mode_variant": "PASSA",
        "_sa_mode_contract": {
            "modo_semantico": "PASSA",
            "faces": {"C": {}},
        },
    }

    out = enrich_payload_for_abcd_nova(payload)

    assert out["abertura_C_1"]["y_rel"] == pytest.approx(180.0)
