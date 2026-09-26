"""Regras do guia de laterais aplicadas por celula (A/B x Para/Passa).

Cena sintetica horizontal: faixa y 0..19, extensao x 0..1000.
"""

from __future__ import annotations

from src.core.beam_interpreters.lateral_viga_cells import (
    apply_cells_to_beam,
    segment_cell,
)
from src.core.lv_beam_scene import LvScene, build_scenes


def _scene(**kw) -> LvScene:
    scene = LvScene("V1", True, 0.0, 19.0, 0.0, 1000.0)
    scene.sections = kw.get("sections", [
        {"start": 0.0, "end": 1000.0, "dim": "19/55", "width": 19.0, "depth": 55.0},
    ])
    for side in ("A", "B"):
        scene.pillars[side] = [dict(p) for p in kw.get("pillars", [])]
    for side, incs in kw.get("incidents", {}).items():
        scene.incidents[side] = [dict(i) for i in incs]
    return scene


CENTRAL_PILLAR = {"name": "P12", "start": 400.0, "end": 500.0, "classification": ""}


def test_g6_para_parts_at_pillar_faces_and_passa_goes_through():
    scene = _scene(pillars=[CENTRAL_PILLAR])
    para = segment_cell(scene, "A", "para")
    passa = segment_cell(scene, "A", "passa")
    assert [(s.start, s.end) for s in para] == [(0.0, 400.0), (500.0, 1000.0)]
    assert para[0].adjustment_end == -11.0 and para[1].adjustment_start == -11.0
    assert [(s.start, s.end) for s in passa] == [(0.0, 1000.0)]
    opening = passa[0].pillar_openings[0]
    assert opening["abertura"] == 122.0          # G8: 100 + 22
    assert opening["dist_face_inicio"] == 400.0
    assert opening["dist_abertura_inicio"] == 389.0


def test_g0_side_b_is_read_backwards():
    scene = _scene(pillars=[CENTRAL_PILLAR])
    b = segment_cell(scene, "B", "para")
    assert [(s.start, s.end) for s in b] == [(1000.0, 500.0), (400.0, 0.0)]
    assert scene.point(b[0].start, "B") == (1000.0, 19.0)
    assert scene.point(0.0, "A") == (0.0, 0.0)   # A embaixo na horizontal


def test_g7_shallower_incident_opens_and_closes_segment_at_far_edge():
    inc = {"name": "V9", "start": 300.0, "end": 319.0, "dim": "19/40", "depth": 40.0, "width": 19.0}
    scene = _scene(incidents={"A": [inc]})
    a = segment_cell(scene, "A", "passa")
    assert [(s.start, s.end) for s in a] == [(0.0, 319.0), (319.0, 1000.0)]
    opening = a[0].beam_openings[0]
    assert opening["abertura_largura"] == 27.0 and opening["abertura_altura"] == 44.0
    assert opening["sobra"] == 15.0
    # Caso 9: T so' pela face A nao parte a face B.
    assert len(segment_cell(scene, "B", "passa")) == 1


def test_g7_deeper_incident_terminates_at_first_face():
    inc = {"name": "V9", "start": 300.0, "end": 319.0, "dim": "19/70", "depth": 70.0, "width": 19.0}
    scene = _scene(incidents={"A": [inc]})
    a = segment_cell(scene, "A", "para")
    assert [(s.start, s.end) for s in a] == [(0.0, 300.0), (319.0, 1000.0)]


def test_q2_equal_depth_incident_is_full_height_opening_in_previous_segment():
    inc = {"name": "V9", "start": 300.0, "end": 319.0, "dim": "19/55", "depth": 55.0, "width": 19.0}
    scene = _scene(incidents={"A": [inc]})
    a = segment_cell(scene, "A", "passa")
    assert [(s.start, s.end) for s in a] == [(0.0, 319.0), (319.0, 1000.0)]
    opening = a[0].beam_openings[0]
    assert opening["altura_inteira"] is True and opening["sobra"] == 0.0


def test_q1_section_change_opens_new_segment_touching_previous():
    scene = _scene(sections=[
        {"start": 0.0, "end": 300.0, "dim": "19/55", "width": 19.0, "depth": 55.0},
        {"start": 300.0, "end": 1000.0, "dim": "19/120", "width": 19.0, "depth": 120.0},
    ], pillars=[{"name": "P1", "start": 200.0, "end": 219.0, "classification": ""}])
    para = segment_cell(scene, "A", "para")
    assert [(s.start, s.end, s.dim) for s in para] == [
        (0.0, 200.0, "19/55"), (219.0, 300.0, "19/55"), (300.0, 1000.0, "19/120"),
    ]
    passa = segment_cell(scene, "A", "passa")
    assert [(s.start, s.end) for s in passa] == [(0.0, 300.0), (300.0, 1000.0)]
    assert all(len({z["dim"] for z in s.sections}) == 1 for s in para + passa)


def test_q3_passa_keeps_pillar_whole_when_beam_crosses_inside_it():
    pillar = {"name": "P42", "start": 400.0, "end": 450.0, "classification": ""}
    inc = {"name": "V312", "start": 415.0, "end": 434.0, "dim": "19/55", "depth": 55.0, "width": 19.0}
    scene = _scene(pillars=[pillar], incidents={"A": [inc]})
    passa = segment_cell(scene, "A", "passa")
    assert [(s.start, s.end) for s in passa] == [(0.0, 450.0), (450.0, 1000.0)]
    opening = passa[0].pillar_openings[0]
    assert (opening["pos_inicio"], opening["pos_fim"], opening["abertura"]) == (400.0, 450.0, 72.0)
    assert "G8_abertura_excede_segmento:P42" in passa[0].flags


def test_opening_at_extremity_belongs_to_the_segment():
    inc = {"name": "V0", "start": 0.0, "end": 14.0, "dim": "14/50", "depth": 50.0, "width": 14.0}
    scene = _scene(incidents={"A": [inc]})
    a = segment_cell(scene, "A", "passa")
    assert len(a) == 1 and a[0].beam_openings[0]["name"] == "V0"


def test_cells_are_isolated_and_frozen_cell_is_preserved():
    scene = _scene(pillars=[CENTRAL_PILLAR])
    human = {"seg_side_a": [{"points": [(0, 0), (1000, 0)], "len": 1000}]}
    beam = {
        "name": "V1",
        "links": {"viga_a_seg_1_comprimento_total": human},
        "preficha_segmentos": {"lateral_a_para|V1|1|1": {"status": "valid"}},
    }
    counts = apply_cells_to_beam(beam, scene)
    assert counts == {"A_PARA": 1, "A_PASSA": 1, "B_PARA": 2, "B_PASSA": 1}
    assert beam["links"]["viga_a_seg_1_comprimento_total"] is human
    passa = beam["links"]["viga_a_seg_1_comp_total_passa"]["seg_side_a"][0]
    assert passa["contract_id"] == "LV_A_PASSA" and passa["lv_cell"]["pillar_openings"]
    assert "viga_a_seg_2_comprimento_total" not in beam["links"]
    assert beam["_lv_cells_meta"]["frozen_cells"] == ["A_PARA"]


def _rect(x0, y0, x1, y1):
    return [{"points": [(x0, y0), (x1, y0)]}, {"points": [(x0, y1), (x1, y1)]}]


def test_scene_uses_real_pillar_polygon_not_bbox_and_label_band():
    lines = _rect(0, 0, 1000, 19) + _rect(0, 60, 1000, 79)  # outra faixa paralela
    texts = [
        {"text": "V1", "pos": (20.0, 22.0), "rotation": 0.0},
        {"text": "19/55", "pos": (300.0, 22.0), "rotation": 0.0},
        {"text": "V2", "pos": (20.0, 82.0), "rotation": 0.0},
    ]
    # pilar em "L": bbox cobre 400..565, mas so' a parede 400..419 toca a faixa
    pillar = {"name": "P26", "points": [(400, -200), (565, -200), (565, -181), (419, -181),
                                       (419, 19), (400, 19), (400, -200)]}
    scenes = build_scenes([{"name": "V1"}, {"name": "V2"}], texts, lines, {"P26": pillar})
    v1 = scenes["V1"]
    assert (v1.t_lo, v1.t_hi) == (0.0, 19.0)
    assert [(p["start"], p["end"]) for p in v1.pillars["A"]] == [(400.0, 419.0)]
    assert v1.sections[0]["dim"] == "19/55"
    assert (scenes["V2"].t_lo, scenes["V2"].t_hi) == (60.0, 79.0)


def test_segment_off_structural_line_is_flagged():
    """Invariante do dono: destaque que nao esta' sobre linha do estrutural e' erro."""
    scene = _scene()
    scene.face_coverage = {"A": [[0.0, 1000.0]], "B": [[0.0, 200.0]]}
    a = segment_cell(scene, "A", "passa")
    b = segment_cell(scene, "B", "passa")
    assert a[0].line_coverage == 1.0 and "fora_da_linha_estrutural" not in a[0].flags
    assert b[0].line_coverage == 0.2 and "fora_da_linha_estrutural" in b[0].flags
