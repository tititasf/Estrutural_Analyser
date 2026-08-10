# -*- coding: utf-8 -*-
from pathlib import Path

from scripts.arete.g2v_gate0_geometry import compare_segments


def test_compare_segments_pass_when_equal():
    segs = {
        ("Painéis", 0.0, 0.0, 0.0, 100.0),
        ("SARR", 10.0, 20.0, 90.0, 20.0),
    }
    r = compare_segments(segs, segs)
    assert r["status"] == "PASS"
    assert r["pass_allowed"] is True


def test_compare_segments_fail_on_n4_extra():
    n2 = {("Painéis", 0.0, 0.0, 0.0, 100.0)}
    n4 = n2 | {("Painéis", 50.0, 0.0, 50.0, 100.0)}
    r = compare_segments(n2, n4)
    assert r["status"] == "FAIL"
    assert r["counts"]["only_n4_struct"] == 1


def test_compare_segments_ignores_n2_junk_below_floor():
    n2 = {
        ("Painéis", 0.0, 0.0, 0.0, 100.0),
        ("Painéis", 0.0, -60.0, 0.0, -10.0),  # junk sob o vão
    }
    n4 = {("Painéis", 0.0, 0.0, 0.0, 100.0)}
    r = compare_segments(n2, n4)
    assert r["status"] == "PASS"
    assert r["counts"]["only_n2_junk"] >= 1
