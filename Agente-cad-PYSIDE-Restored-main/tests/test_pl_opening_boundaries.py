"""Regressão das fronteiras de aberturas nos painéis ABCD do PIL."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gerar_pl_dxf_stog as generator  # noqa: E402


def test_p1_ad_top_opening_splits_existing_panel_intervals():
    """AD 11x124 começa em 154 e preserva a divisão original em 244."""
    result = generator.panel_intervals_with_opening_boundaries(
        [244.0, 34.0],
        [{"lado": "direito", "largura": 11.0, "y_rel": 154.0, "altura": 124.0}],
    )

    assert result == [154.0, 90.0, 34.0]
    assert sum(result) == 278.0


def test_internal_opening_adds_bottom_and_top_without_losing_original_lines():
    result = generator.panel_intervals_with_opening_boundaries(
        [244.0, 34.0],
        [{"lado": "meio", "largura": 27.0, "y_rel": 100.0, "altura": 50.0}],
    )

    assert result == [100.0, 50.0, 94.0, 34.0]
    assert sum(result) == 278.0


def test_no_opening_keeps_original_intervals():
    assert generator.panel_intervals_with_opening_boundaries(
        [244.0, 34.0], []
    ) == [244.0, 34.0]


def test_duplicate_opening_boundaries_are_idempotent():
    result = generator.panel_intervals_with_opening_boundaries(
        [154.0, 90.0, 34.0],
        [{"y_rel": 154.0, "altura": 124.0}],
    )

    assert result == [154.0, 90.0, 34.0]

