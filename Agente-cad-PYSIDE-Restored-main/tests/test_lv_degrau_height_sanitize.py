# -*- coding: utf-8 -*-
"""Degrau / height1: micro-faixas de laje não viram painel de degrau."""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from gerar_lv_dxf_stog import (  # noqa: E402
    _is_degrau_panel,
    _panel_draw_height,
    sanitize_face_panels_for_draw,
)


def test_micro_height_is_not_degrau():
    assert _is_degrau_panel({"height1": 6.6}, 124.0) is False
    assert _is_degrau_panel({"height1": 11.9}, 109.0) is False


def test_real_degrau_height_is_degrau():
    assert _is_degrau_panel({"height1": 44.0}, 109.0) is True
    assert _is_degrau_panel({"height1": 58.6}, 124.0) is True


def test_draw_height_promotes_micro_to_full_face():
    assert _panel_draw_height({"height1": 6.6}, 124.0) == 124.0
    assert _panel_draw_height({"height1": 44.0}, 109.0) == 44.0


def test_sanitize_all_micro_becomes_full():
    panels = [
        {"width": 244.0, "height1": 6.6},
        {"width": 22.5, "height1": 6.6},
        {"width": 52.5, "height1": 6.6},
    ]
    out = sanitize_face_panels_for_draw(panels, 124.0)
    assert all(float(p["height1"]) == 124.0 for p in out)
