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


def test_equal_depth_beams_do_not_cross_each_other():
    """Dono 2026-09-26 (revisao do Q2): mesma altura -> para na primeira face."""
    inc = {"name": "V9", "start": 300.0, "end": 319.0, "dim": "19/55", "depth": 55.0, "width": 19.0}
    scene = _scene(incidents={"A": [inc]})
    for behavior in ("para", "passa"):
        a = segment_cell(scene, "A", behavior)
        assert [(s.start, s.end) for s in a] == [(0.0, 300.0), (319.0, 1000.0)]
        assert not a[0].beam_openings


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
    inc = {"name": "V312", "start": 415.0, "end": 434.0, "dim": "19/40", "depth": 40.0, "width": 19.0}
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


def test_pillar_that_nasce_on_this_floor_is_not_solid():
    lines = _rect(0, 0, 1000, 19)
    texts = [
        {"text": "V1", "pos": (20.0, 22.0), "rotation": 0.0},
        {"text": "19/55", "pos": (300.0, 22.0), "rotation": 0.0},
    ]
    report = {
        "P42": {"name": "P42", "classification": "NASCE",
                "points": [(400, 0), (450, 0), (450, 19), (400, 19), (400, 0)]},
        "P11": {"name": "P11", "classification": "SEGUE",
                "points": [(700, 0), (780, 0), (780, 19), (700, 19), (700, 0)]},
    }
    v1 = build_scenes([{"name": "V1"}], texts, lines, report)["V1"]
    assert [p["name"] for p in v1.pillars["A"]] == ["P11"]
    para = segment_cell(v1, "A", "para")
    assert [(s.start, s.end) for s in para] == [(0.0, 700.0), (780.0, 1000.0)]


def test_pillar_marked_ignore_in_beams_by_preinterpretation_is_not_solid():
    lines = _rect(0, 0, 1000, 19)
    texts = [{"text": "V1", "pos": (20.0, 22.0), "rotation": 0.0},
             {"text": "19/55", "pos": (300.0, 22.0), "rotation": 0.0}]
    report = {"P9": {"name": "P9", "classification": "SEGUE", "ignore_in_beams": True,
                     "points": [(400, 0), (450, 0), (450, 19), (400, 19), (400, 0)]}}
    v1 = build_scenes([{"name": "V1"}], texts, lines, report)["V1"]
    assert v1.pillars["A"] == [] and len(segment_cell(v1, "A", "para")) == 1


def _tick(x, y):
    return (x - 3.55, y - 3.55, x + 3.55, y + 3.55)


def test_dimension_chain_is_recognized_by_geometry_not_layer():
    from src.core.lv_beam_scene import split_dimension_lines
    chain = [(0.0, -80.0, 305.5, -80.0), (305.5, -80.0, 405.5, -80.0)]
    ticks = [_tick(0.0, -80.0), _tick(305.5, -80.0), _tick(405.5, -80.0)]
    edge = (0.0, 0.0, 405.5, 0.0)
    texts = [{"text": "305.5", "pos": (150.0, -77.0)}]  # o "100" nao tem texto: vem pela cadeia
    structural, dimension = split_dimension_lines(chain + ticks + [edge], texts)
    assert set(dimension) == set(chain)
    assert edge in structural


def test_edge_touched_by_a_tick_is_not_a_dimension():
    """Cota vertical termina NA face: a borda recebe tique e continua borda."""
    from src.core.lv_beam_scene import split_dimension_lines
    edge = (0.0, 19.0, 38.5, 19.0)
    structural, dimension = split_dimension_lines([edge, _tick(10.0, 19.0)], [])
    assert edge in structural and not dimension


def test_segment_over_dimension_line_is_flagged():
    scene = _scene()
    # A: trecho 0-300 so' tem cota por baixo (alucinacao). B: a cota esta'
    # deitada sobre parede real (chamada colinear, V301) — nao e' alucinacao.
    scene.face_coverage = {"A": [[300.0, 1000.0]], "B": [[0.0, 1000.0]]}
    scene.dimension_coverage = {"A": [[0.0, 300.0]], "B": [[0.0, 300.0]]}
    assert "sobre_linha_de_cota" in segment_cell(scene, "A", "passa")[0].flags
    assert "sobre_linha_de_cota" not in segment_cell(scene, "B", "passa")[0].flags


def test_witness_line_of_dimension_is_not_beam_wall():
    """Linha de chamada (V322/V309A): perpendicular a' cota, passa o tique ~10 cm."""
    from src.core.lv_beam_scene import split_dimension_lines
    chain = [(0.0, 313.1, 418.0, 313.1)]
    ticks = [_tick(0.0, 313.1), _tick(418.0, 313.1)]
    witness = (418.0, 212.0, 418.0, 323.1)
    wall = (418.0, 0.0, 418.0, 141.0)
    texts = [{"text": "418", "pos": (200.0, 316.0)}]
    structural, dimension = split_dimension_lines(chain + ticks + [witness, wall], texts)
    assert witness in dimension and wall in structural


def test_beam_extent_needs_both_walls():
    """V310: linha colinear a UMA face nao estica a viga alem da V303."""
    lines = [{"points": [(0.0, 0.0), (0.0, 400.0)]}, {"points": [(14.0, 150.0), (14.0, 400.0)]}]
    texts = [{"text": "V1", "pos": (-3.0, 300.0), "rotation": 90.0},
             {"text": "14/50", "pos": (-3.0, 250.0), "rotation": 90.0}]
    v1 = build_scenes([{"name": "V1"}], texts, lines, {})["V1"]
    assert (v1.start, v1.end) == (150.0, 400.0)


def test_passa_wraps_end_pillar_and_para_stops_at_its_face():
    """Dono 2026-09-26: Passa engloba a parede do pilar tambem na ponta."""
    scene = _scene()
    scene.end_supports["end"] = [{"type": "pilar", "name": "P1", "start": 1000.0, "end": 1066.0}]
    passa = segment_cell(scene, "A", "passa")
    para = segment_cell(scene, "A", "para")
    assert passa[-1].end == 1066.0 and passa[-1].pillar_openings[-1]["name"] == "P1"
    assert para[-1].end == 1000.0


def test_passa_absorbs_beam_arriving_inside_pillar():
    """V302 chega no P10 da V309A: o pilar fica inteiro, a viga vira abertura."""
    pillar = {"name": "P10", "start": 400.0, "end": 460.0, "classification": "SEGUE"}
    inc = {"name": "V302", "start": 441.0, "end": 460.0, "dim": "19/55", "depth": 55.0, "width": 19.0}
    scene = _scene(pillars=[pillar], incidents={"A": [inc]})
    passa = segment_cell(scene, "A", "passa")
    assert [(s.start, s.end) for s in passa] == [(0.0, 460.0), (460.0, 1000.0)]
    assert passa[0].beam_openings[0]["altura_inteira"] is True


def test_passa_does_not_wrap_pillar_the_beam_does_not_reach():
    """V311 termina na V306 (mesma altura); o P28 depois dela nao e' da V311."""
    inc = {"name": "V306", "start": 5.0, "end": 24.0, "dim": "19/55", "depth": 55.0, "width": 19.0}
    scene = _scene(incidents={"A": [inc]})
    scene.end_supports["start"] = [{"type": "pilar", "name": "P28", "start": -80.0, "end": 0.0}]
    passa = segment_cell(scene, "A", "passa")
    assert [(s.start, s.end) for s in passa] == [(24.0, 1000.0)]


def test_passa_runs_along_pillar_wall_but_never_through_its_core():
    """VF301: face em cima da parede do pilar passa; face dentro do pilar para.

    Faixa y 0..14 dentro da fileira de pilares (y -52..14): a face B (y=14) e'
    a parede de cima do pilar (C/D e' parede, nao miolo); a face A (y=0) cruza
    o corpo do pilar.
    """
    lines = _rect(0, 0, 1000, 14) + [{"points": [(400, -52), (419, -52)]}]
    texts = [{"text": "V1", "pos": (20.0, 17.0), "rotation": 0.0},
             {"text": "14/55", "pos": (300.0, 17.0), "rotation": 0.0}]
    report = {"P2": {"name": "P2", "classification": "SEGUE",
                     "points": [(400, -52), (419, -52), (419, 14), (400, 14), (400, -52)]}}
    v1 = build_scenes([{"name": "V1"}], texts, lines, report)["V1"]
    a = segment_cell(v1, "A", "passa")
    b = segment_cell(v1, "B", "passa")
    assert [(s.start, s.end) for s in a] == [(0.0, 400.0), (419.0, 1000.0)]
    assert len(b) == 1 and b[0].pillar_openings[0]["name"] == "P2"
