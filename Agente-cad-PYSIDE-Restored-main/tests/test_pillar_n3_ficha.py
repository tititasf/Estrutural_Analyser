from __future__ import annotations

from src.core import pillar_n3_ficha as ficha


def _rect_pillar():
    return {"name": "P1", "points": [[0, 0], [66, 0], [66, 19], [0, 19], [0, 0]]}


def test_build_uses_robot_and_keeps_a1_two_centimeters():
    robot = {
        "nome": "P1", "comprimento": 66, "largura": 19, "altura": 280,
        "h1_A": 2, "h2_A": 244, "h3_A": 34, "larg1_A": 66,
    }
    result = ficha.build_ficha(_rect_pillar(), robot, pavimento="TERREO")
    assert list(result["faces"]) == list("ABCD")
    a1 = next(p for p in result["faces"]["A"]["panels"] if p["row"] == 1)
    assert a1["height"] == 2
    assert result["dimensions"]["height"] == 280


def test_special_pillar_exposes_up_to_eight_faces():
    pillar = {
        "name": "P26",
        "points": [[0, 0], [60, 0], [60, 20], [20, 20], [20, 60], [0, 60], [0, 0]],
    }
    result = ficha.build_ficha(pillar, {"altura": 300}, pavimento="TIPO")
    assert result["special"] is True
    assert set(result["faces"]) == set("ABCDEFGH")


def test_special_pillar_uses_geometry_when_fase4_extra_face_width_is_zero():
    pillar = {
        "name": "P26",
        "points": [[0, 0], [50, 0], [50, 19], [19, 19], [19, 50], [0, 50], [0, 0]],
    }
    robot = {
        "comprimento": 50, "largura": 19, "altura": 280,
        "larg1_A": 50, "larg1_B": 50, "larg1_C": 19, "larg1_D": 19,
        "larg1_E": 0.0, "larg1_F": 0.0, "larg1_G": 0.0, "larg1_H": 0.0,
    }

    result = ficha.build_ficha(pillar, robot, pavimento="TERREO")

    assert result["special"] is True
    assert all(
        panel["width"] > 0 and panel["height"] > 0
        for face in result["faces"].values()
        for panel in face["panels"]
    )


def test_right_opening_zero_distance_is_anchored_inside_right_panel_edge():
    result = ficha.build_ficha(_rect_pillar(), {
        "comprimento": 100, "largura": 20, "altura": 280,
        "h1_A": 2, "h2_A": 244, "h3_A": 34, "larg1_A": 100,
    })
    result["faces"]["A"]["openings"]["right"] = [{
        "distance": 0, "width": 12, "depth": 25, "level": 120, "top_distance": 0,
    }]
    patch = ficha.robot_patch(result)
    opening = patch["abertura_A_1"]
    assert opening["lado"] == "direito"
    assert opening["x_offset"] == 88
    assert opening["y_rel"] == 120


def test_human_ficha_roundtrip_and_robot_patch(tmp_path):
    result = ficha.build_ficha(_rect_pillar(), {
        "comprimento": 66, "largura": 19, "altura": 280, "grade_1": 88,
    }, pavimento="13_PAV")
    result["faces"]["A"]["panels"][0]["kind"] = "slab_void"
    result["faces"]["A"]["panels"][0]["hatch"] = "striped"
    result["grades"]["horizontal_slats"] = [{
        "left_distance": 10, "right_distance": 12, "width": 5, "height": 7,
    }]
    saved = ficha.save_ficha(tmp_path, "13_PAV", "P1", result)
    loaded = ficha.load_ficha(tmp_path, "13_PAV", "P1")
    assert loaded == saved
    assert saved["revision"] == 1
    patch = ficha.robot_patch(loaded)
    assert patch["grade_1"] == 88
    assert patch["portal_cells_A"][0]["kind"] == "slab_void"
    assert patch["portal_cells_A"][0]["hatch"] == "striped"
    assert patch["sarrafos_horizontais"][0]["right_distance"] == 12


def test_invalid_zero_sized_panel_is_rejected():
    result = ficha.build_ficha(_rect_pillar(), {"altura": 280})
    result["faces"]["A"]["panels"][0]["width"] = 0
    try:
        ficha.validate_ficha(result)
    except ValueError as exc:
        assert "largura/altura invalida" in str(exc)
    else:
        raise AssertionError("painel zero deveria ser rejeitado")


def test_motor_fase4_reapplies_saved_web_ficha(tmp_path):
    import json

    from scripts.motor_fase4 import MotorFase4

    obra = tmp_path / "ObraIsolada"
    pilares_dir = obra / "Fase-3_Interpretacao_Extracao" / "Pilares"
    pilares_dir.mkdir(parents=True)
    (pilares_dir / "pilares_bh.json").write_text(json.dumps({
        "P1": {"b": 19, "h": 66, "altura": 280},
    }), encoding="utf-8")
    web = ficha.build_ficha(_rect_pillar(), {
        "nome": "P1", "comprimento": 66, "largura": 19, "altura": 280,
        "h1_A": 2, "h2_A": 244, "h3_A": 34, "larg1_A": 66,
    }, pavimento="TERREO")
    web["grades"]["grade_1"] = 91
    web["faces"]["A"]["panels"][1]["height"] = 200
    ficha.save_ficha(obra, "TERREO", "P1", web)

    generated = MotorFase4(str(obra), pavimento="TERREO").process_pilares()
    assert generated["P1"]["grade_1"] == 91
    assert generated["P1"]["h2_A"] == 200
    assert generated["P1"]["_portal_n3_ficha"]["revision"] == 1


def test_sa_materializes_all_fichas_and_preserves_human_revision(tmp_path):
    import json

    state_path = tmp_path / "estado_TERREO.json"
    state_path.write_text(json.dumps({"pilares": [_rect_pillar()]}), encoding="utf-8")
    stats = ficha.materialize_pavimento(tmp_path, "TERREO")
    assert stats == {"pavimento": "TERREO", "total": 1, "created": 1,
                     "refreshed": 0, "preserved": 0, "errors": []}
    automatic = ficha.load_ficha(tmp_path, "TERREO", "P1")
    assert automatic["revision"] == 0
    assert automatic["source"]["human_override"] is False

    automatic["grades"]["grade_1"] = 99
    human = ficha.save_ficha(tmp_path, "TERREO", "P1", automatic)
    state_path.write_text(json.dumps({"pilares": [{
        **_rect_pillar(), "points": [[0, 0], [100, 0], [100, 20], [0, 20], [0, 0]],
    }]}), encoding="utf-8")
    stats2 = ficha.materialize_pavimento(tmp_path, "TERREO")
    assert stats2["preserved"] == 1
    assert ficha.load_ficha(tmp_path, "TERREO", "P1")["grades"]["grade_1"] == 99
    assert human["revision"] == 1


def test_n3_enrich_preserves_explicit_web_panel_mesh():
    from scripts.pl_abcd_visual_nova import enrich_payload_for_abcd_nova

    payload = {
        "altura": 280, "h1_A": 2, "paineis_intervals_A": [100, 80, 98],
        "_portal_n3_ficha": {"schema": ficha.SCHEMA, "revision": 2},
        "_sa_mode_contract": {"faces": {"A": {}}, "modo": "para"},
    }
    enriched = enrich_payload_for_abcd_nova(payload)
    assert enriched["paineis_intervals_A"] == [100.0, 80.0, 98.0]
