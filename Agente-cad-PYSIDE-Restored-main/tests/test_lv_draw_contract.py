import copy

import pytest

from src.core.lv_draw_contract import LVDrawContractError, validate_n4_ficha


def _ficha():
    return {
        "viga": "V301",
        "h_cm": 109,
        "h_B_cm": 109,
        "b_cm": 19,
        "h_section_cm": 55,
        "face_units": [
            {
                "side": "A",
                "h_body": 109,
                "segments": [
                    {"largura_cm": 244, "height1": 44},
                    {"largura_cm": 161.5, "height1": 109},
                ],
            },
            {
                "side": "B",
                "h_body": 109,
                "segments": [{"largura_cm": 405.5, "height1": 109}],
            },
        ],
    }


def test_strict_contract_rejects_missing_side_instead_of_copying_other_side():
    ficha = _ficha()
    ficha["face_units"] = ficha["face_units"][:1]

    with pytest.raises(LVDrawContractError, match="lado\(s\) ausente\(s\): B"):
        validate_n4_ficha(ficha)


def test_fingerprint_ignores_source_metadata_but_changes_with_geometry():
    first = validate_n4_ficha(_ficha())
    metadata_only = _ficha()
    metadata_only["_confianca"] = 0.77
    metadata_only["face_units"][0]["bbox"] = {"x_left": 999, "y_top": 123}
    second = validate_n4_ficha(metadata_only)
    changed = copy.deepcopy(_ficha())
    changed["face_units"][0]["segments"][0]["largura_cm"] = 243
    third = validate_n4_ficha(changed)

    assert (
        first["_motor_contract"]["drawing_fingerprint"]
        == second["_motor_contract"]["drawing_fingerprint"]
    )
    assert (
        first["_motor_contract"]["drawing_fingerprint"]
        != third["_motor_contract"]["drawing_fingerprint"]
    )


def test_legacy_segments_are_only_mechanically_wrapped_as_a_and_b_units():
    ficha = _ficha()
    ficha.pop("face_units")
    ficha["segmentos"] = [{"largura_cm": 100, "height1": 109}]
    ficha["segmentos_B"] = [{"largura_cm": 120, "height1": 109}]

    normalized = validate_n4_ficha(ficha)

    assert [unit["side"] for unit in normalized["face_units"]] == ["A", "B"]
    assert normalized["face_units"][0]["segments"][0]["width"] == 100
    assert normalized["_motor_contract"]["inference_inside_generator"] is False

