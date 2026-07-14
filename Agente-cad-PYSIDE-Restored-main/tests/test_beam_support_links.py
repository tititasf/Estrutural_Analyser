from src.core.beam_support_links import global_beam_boundary_link


def test_global_boundary_is_neutral_outside_fv_and_does_not_mutate_source():
    source = {"name": "P10", "points": [[0, 0], [1, 0]]}

    actual = global_beam_boundary_link(source, is_fv_context=False)

    assert actual == source
    assert actual is not source
    assert "evidence_role" not in source


def test_global_boundary_marks_only_proven_fv_context():
    actual = global_beam_boundary_link("P10", is_fv_context=True)

    assert actual["name"] == "P10"
    assert actual["evidence_role"] == "fv_beam_global_boundary"
    assert actual["scope"] == "beam_global"
