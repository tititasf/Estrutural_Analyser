from src.ui.widgets.pre_validation_dialog import build_pillar_n3_base_from_n1


def _contract(*, faces=None, saida=848.98, chegada=852.19):
    return {
        "altura_pilar": {
            "nivel_saida_abs": saida,
            "nivel_chegada_abs": chegada,
        },
        "faces": faces or {fid: {} for fid in "ABCD"},
    }


def test_live_base_derives_rectangular_geometry_and_height():
    payload = build_pillar_n3_base_from_n1(
        "P12",
        [(0, 0), (19, 0), (19, 98), (0, 98), (0, 0)],
        _contract(),
        "13_PAV",
    )

    assert payload["comprimento"] == 98.0
    assert payload["largura"] == 19.0
    assert payload["altura"] == 321.0
    assert payload["larg1_A"] == payload["larg1_B"] == 98.0
    assert payload["larg1_C"] == payload["larg1_D"] == 19.0
    assert payload["larg1_E"] == 0.0
    assert payload["_sa_meta"]["fonte"] == "SA/N1 live contract"
    assert payload["_sa_meta"]["fase4_consultada"] is False


def test_live_base_uses_physical_face_geometry_for_special_faces():
    contract = _contract(faces={fid: {} for fid in "ABCDEF"})
    contract["face_geometry"] = {
        "E": {"p0": [40, 20], "p1": [100, 20]},
        "F": {"p0": [100, 20], "p1": [100, 40]},
    }
    payload = build_pillar_n3_base_from_n1(
        "P26",
        [(0, 0), (100, 0), (100, 40), (40, 40), (40, 20), (0, 20)],
        contract,
        "13_PAV",
    )

    assert payload["subtipo_pil"] == "L"
    assert payload["larg1_E"] == 60.0
    assert payload["larg1_F"] == 20.0


def test_live_base_refuses_missing_geometry_or_height():
    assert build_pillar_n3_base_from_n1("P1", [], _contract(), "13_PAV") == {}
    assert build_pillar_n3_base_from_n1(
        "P1", [(0, 0), (19, 0), (19, 55), (0, 55)],
        {"altura_pilar": {}, "faces": {}}, "13_PAV",
    ) == {}
