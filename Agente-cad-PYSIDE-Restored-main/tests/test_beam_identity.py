from src.core.beam_identity import canonical_beam_name, consolidate_beam_identities


def _text(text, x, y):
    return {"text": text, "pos": [x, y]}


def test_legacy_name_uses_nearest_drawing_label_instead_of_contaminated_suffix():
    beam = {
        "name": "FV-V331.C",
        "pos": [10.0, 20.0],
        "texts": [_text("V331", 90, 20), _text("V329", 10, 20)],
    }

    assert canonical_beam_name(beam) == "V329"


def test_consolidation_removes_legacy_duplicates_and_preserves_coherent_validation():
    beams = [
        {
            "id": "b1",
            "name": "FV-V329.C",
            "pos": [10.0, 20.0],
            "texts": [_text("V329", 10, 20), _text("V331", 90, 20)],
            "validated_fields": ["name", "fim"],
            "fields": {"fim": "P18"},
            "links": {"name": {"label": [_text("V329", 10, 20)]}},
        },
        {
            "id": "b2",
            "name": "FV-V331.C",
            "pos": [10.0, 20.0],
            "texts": [_text("V329", 10, 20), _text("V331", 90, 20)],
            "validated_fields": ["inicio"],
            "fields": {"inicio": "V331"},
            "links": {"inicio": {"label": [_text("V331", 90, 20)]}},
        },
        {
            "id": "b3",
            "name": "FV-V331.C",
            "pos": [10.0, 20.0],
            "texts": [_text("V329", 10, 20), _text("V331", 90, 20)],
            "validated_fields": ["inicio"],
            "fields": {"inicio": "V329"},
            "links": {"inicio": {"label": [_text("V329", 10, 20)]}},
        },
        {
            "id": "b4",
            "name": "V331",
            "pos": [90.0, 20.0],
            "texts": [_text("V331", 90, 20)],
            "fields": {},
            "links": {},
        },
    ]

    result, removed, changed = consolidate_beam_identities(beams)

    assert [beam["name"] for beam in result] == ["V329", "V331"]
    assert set(removed) == {"b2", "b3"}
    assert changed == 3
    assert result[0]["fields"] == {"fim": "P18", "inicio": "V329"}
    assert set(result[0]["validated_fields"]) == {"name", "fim", "inicio"}


def test_plain_structural_names_are_preserved():
    result, removed, changed = consolidate_beam_identities(
        [{"id": "b1", "name": "VF202", "pos": [1, 2], "links": {}, "fields": {}}]
    )

    assert result[0]["name"] == "VF202"
    assert removed == []
    assert changed == 0


def test_plain_but_renamed_record_uses_coherent_structural_field():
    beam = {
        "id": "project_b_1",
        "name": "V329",
        "pos": [10, 20],
        "texts": [_text("V301", 10, 20), _text("V329", 500, 20)],
        "fields": {"nome": "V301", "numero": "01"},
    }

    assert canonical_beam_name(beam) == "V301"
