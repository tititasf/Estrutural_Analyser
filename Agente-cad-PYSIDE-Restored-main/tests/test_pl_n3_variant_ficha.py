"""Fichas N3 PIL devem expor o payload real de cada variante."""
from __future__ import annotations

from types import SimpleNamespace


def test_variant_ficha_shows_payload_that_feeds_dxf():
    from src.ui.widgets.pre_validation_dialog import PreValidationDialog

    ficha = PreValidationDialog._n3_ficha_html_pilar(
        SimpleNamespace(),
        'P1',
        {
            'vazio_laje_A': 14.0,
            'abertura_A_1': {'largura': 11.0, 'altura': 59.0},
            '_sa_mode_contract': {'nao_deve': 'aparecer'},
        },
    )

    assert 'vazio_laje_A' in ficha
    assert 'abertura_A_1' in ficha
    assert 'nao_deve' not in ficha
