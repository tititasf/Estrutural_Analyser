from scripts.arete.qa_class_capability import validate


def test_class_capability_parity_ok():
    result = validate()
    assert result["passed"], result["findings"]
    assert result["parity"]["classes"] == ["FV", "LAJ", "LV", "PIL"]
