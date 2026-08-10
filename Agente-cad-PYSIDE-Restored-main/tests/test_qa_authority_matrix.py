"""CI anti-drift: authority_matrix ↔ CLASS_REGISTRY ↔ skill/squad."""
from __future__ import annotations

from scripts.arete.qa_authority_matrix import (
    class_validation_mode,
    load_matrix,
    parse_registry_modes,
    validate_alignment,
)


def test_matrix_matches_registry_and_docs():
    result = validate_alignment()
    assert result["registry"]["LAJ"] == "validation_ready"
    assert result["registry"]["PIL"] == "validation_ready"
    assert result["registry"]["FV"] == "validation_ready"
    assert result["registry"]["LV"] == "validation_ready"
    assert result["passed"], result["findings"]


def test_class_validation_mode_helpers():
    matrix = load_matrix()
    assert class_validation_mode("pil", matrix) == "validation_ready"
    assert class_validation_mode("fv", matrix) == "validation_ready"
    assert class_validation_mode("lv", matrix) == "validation_ready"
    assert parse_registry_modes()["PIL"] == "validation_ready"
