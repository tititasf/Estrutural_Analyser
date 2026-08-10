from __future__ import annotations

from scripts.arete.qa_class_golden_regression import compare


def test_compare_detects_confirmar_regression():
    baseline = {
        "classes": {
            "PIL": {
                "decision_totals": {"CONFIRMAR": 10, "PENDENTE": 1},
                "items_seen": ["P1"],
                "fields": {"P1": {"name": "CONFIRMAR"}},
            }
        }
    }
    current = {
        "classes": {
            "PIL": {
                "decision_totals": {"CONFIRMAR": 8, "PENDENTE": 3},
                "items_seen": ["P1"],
                "fields": {"P1": {"name": "PENDENTE"}},
            }
        }
    }
    issues = compare(baseline, current, ["PIL"])
    assert any("CONFIRMAR regrediu" in i for i in issues)
    assert any("despromovidos" in i for i in issues)


def test_compare_ok_when_stable():
    row = {
        "decision_totals": {"CONFIRMAR": 5},
        "items_seen": ["L301"],
        "fields": {"L301": {"name": "CONFIRMAR"}},
    }
    issues = compare({"classes": {"LAJ": row}}, {"classes": {"LAJ": row}}, ["LAJ"])
    assert issues == []
