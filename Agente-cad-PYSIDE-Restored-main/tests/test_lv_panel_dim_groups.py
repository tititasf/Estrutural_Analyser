# -*- coding: utf-8 -*-
"""Cotas de painel: agrupar estreitos evita texto colado no SVG."""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from gerar_lv_dxf_stog import group_panel_dims, _fmt_dim_cm  # noqa: E402


def test_v301_a_groups_like_n2():
    # widths canónicos face A
    w = [244.0, 28.7, 21.8, 111.0, 19.0, 21.2]
    g = group_panel_dims(w, min_w=30.0)
    # (x_off, sum, n)
    assert g[0] == (0.0, 244.0, 1)
    assert abs(g[1][1] - 50.5) < 0.05 and g[1][2] == 2  # 28.7+21.8
    assert abs(g[2][1] - 111.0) < 0.05 and g[2][2] == 1
    assert abs(g[3][1] - 40.2) < 0.05 and g[3][2] == 2  # 19+21.2
    assert len(g) == 4


def test_fmt_dim_cm():
    assert _fmt_dim_cm(244.0) == "244"
    assert _fmt_dim_cm(28.7) == "28,7"
    assert _fmt_dim_cm(50.5) == "50,5"
