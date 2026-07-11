from src.core.beam_interpreters import (
    FundoVigaInterpreter,
    InterpreterKind,
    build_interpreter_registry,
)
from src.core.beam_tracer import BeamTracer
from scripts.analise_geral_headless import _find_support_text


class _FakeSpatialIndex:
    def __init__(self, items):
        self.items = items

    def query_bbox(self, _bbox):
        return self.items


def test_registry_contains_exactly_the_seven_structural_interpreters():
    registry = build_interpreter_registry()

    assert set(registry) == set(InterpreterKind)
    assert len(registry) == 7
    assert len({item.contract.kind for item in registry.values()}) == 7


def test_each_interpreter_owns_an_explicit_output_slot():
    registry = build_interpreter_registry()

    assert all(item.contract.owner for item in registry.values())
    assert all(item.contract.output_slot for item in registry.values())
    assert registry[InterpreterKind.LATERAL_VIGA_A_PARA].output_key(3) == (
        "viga_a_seg_3_comprimento_total"
    )
    assert registry[InterpreterKind.LATERAL_VIGA_B_PASSA].output_key(2) == (
        "viga_b_seg_2_comp_total_passa"
    )


def test_fv_exposes_atomic_panels_without_using_them_before_topology_decision():
    interpreter = FundoVigaInterpreter()

    groups = interpreter.atomic_panel_groups(
        [
            {"start": 0.0, "end": 100.0},
            {"start": 0.0, "end": 100.0},
            {"start": 119.0, "end": 219.0},
        ],
        lambda item: item["start"],
        lambda item: item["end"],
    )

    assert groups == [(0.0, 100.0), (119.0, 219.0)]


def test_fv_discards_enclosing_fallback_but_preserves_atomic_panels():
    interpreter = FundoVigaInterpreter()

    groups = interpreter.atomic_occurrences(
        [
            [(0.0, 100.0), (119.0, 219.0), (238.0, 338.0)],
            [(0.0, 338.0)],
        ]
    )

    assert groups == [(0.0, 100.0), (119.0, 219.0), (238.0, 338.0)]


def test_fv_conservative_mode_keeps_short_crossing_gap_merged():
    interpreter = FundoVigaInterpreter()

    groups = interpreter.panel_groups(
        [{"start": 0.0, "end": 100.0}, {"start": 119.0, "end": 219.0}],
        lambda item: item["start"],
        lambda item: item["end"],
    )

    assert groups == [(0.0, 219.0)]


def test_fv_physical_panel_mode_splits_short_support_gap_between_long_panels():
    interpreter = FundoVigaInterpreter()

    groups = interpreter.panel_groups(
        [{"start": 0.0, "end": 254.0}, {"start": 273.0, "end": 691.0}],
        lambda item: item["start"],
        lambda item: item["end"],
        split_support_gaps=True,
    )

    assert groups == [(0.0, 254.0), (273.0, 691.0)]


def test_fv_discards_touching_narrow_cap_before_long_panel():
    interpreter = FundoVigaInterpreter()

    groups = interpreter.discard_attached_narrow_caps([(0.0, 19.0), (19.0, 171.0)])

    assert groups == [(19.0, 171.0)]


def test_fv_merges_short_gap_without_structural_boundary_label():
    interpreter = FundoVigaInterpreter()

    groups = interpreter.merge_unlabeled_short_gaps(
        [(2680.0, 2991.0), (3010.0, 3141.0)],
        is_horizontal=False,
        transverse_center=1600.0,
        texts=[{"text": "P42", "pos": (1638.0, 3049.0)}],
        current_name="V312",
    )

    assert groups == [(2680.0, 3141.0)]


def test_fv_keeps_short_gap_when_boundary_has_structural_label():
    interpreter = FundoVigaInterpreter()

    groups = interpreter.merge_unlabeled_short_gaps(
        [(1349.0, 1603.0), (1622.0, 2040.0)],
        is_horizontal=True,
        transverse_center=2071.0,
        texts=[{"text": "V311", "pos": (1599.6, 2082.0)}],
        current_name="V306",
    )

    assert groups == [(1349.0, 1603.0), (1622.0, 2040.0)]


def test_fv_does_not_collapse_multi_panel_chain_without_labels():
    interpreter = FundoVigaInterpreter()
    groups = interpreter.merge_unlabeled_short_gaps(
        [(0.0, 100.0), (119.0, 219.0), (238.0, 338.0), (357.0, 457.0)],
        is_horizontal=True,
        transverse_center=0.0,
        texts=[],
        current_name="V301",
    )
    assert groups == [(0.0, 100.0), (119.0, 219.0), (238.0, 338.0), (357.0, 457.0)]


def test_fv_support_text_prefers_structural_v_label_over_nearby_fv_label():
    index = _FakeSpatialIndex([
        {"text": "VF202", "pos": (1393.751216, 2033.233516)},
        {"text": "V307", "pos": (1201.587671, 2216.653715)},
    ])

    link = _find_support_text(
        (1349.278794, 2070.788),
        index,
        current_beam="V306",
    )

    assert link["text"] == "V307"
    assert link["role"] == "Apoio fundo de viga"


def test_fundo_area_rejects_collinear_walls_and_builds_rectangle():
    contour = FundoVigaInterpreter.build_area_contour(
        axial_span=(4101.3825, 4387.3825),
        width=19.0,
        is_horizontal=True,
        transverse_center=2221.991,
        boundary_lines=[
            [(4101.3825, 2242.038), (4343.8825, 2242.038)],
            [(4387.3825, 2242.038), (4343.8825, 2242.038)],
        ],
    )

    assert contour[0] == contour[-1]
    assert max(point[0] for point in contour) - min(point[0] for point in contour) == 286.0
    assert max(point[1] for point in contour) - min(point[1] for point in contour) == 19.0
    assert FundoVigaInterpreter._polygon_area(contour) == 5434.0


def test_fundo_area_preserves_two_real_non_collinear_edges():
    contour = FundoVigaInterpreter.build_area_contour(
        axial_span=(0.0, 100.0),
        width=20.0,
        is_horizontal=True,
        transverse_center=10.0,
        boundary_lines=[[(0, 0), (100, 0)], [(0, 20), (100, 20)]],
    )

    assert contour == [
        (0.0, 0.0), (100.0, 0.0),
        (100.0, 20.0), (0.0, 20.0), (0.0, 0.0),
    ]


def test_fundo_repairs_v305_degenerate_link_using_segment_dimension():
    beam = {
        "is_h": True,
        "pos": (4104.374187, 2221.99086),
        "fields": {"viga_fundo_seg_1_dim": "19/55"},
        "geometry": {"classified": {
            "merged_bottom_groups_coords": [(4101.3825, 4387.3825)],
            "seg_bottom": [
                [(4101.3825, 2242.038), (4343.8825, 2242.038)],
                [(4343.8825, 2242.038), (4387.3825, 2242.038)],
            ],
            "seg_side_a": [
                [
                    (3936.3825, 2242.038), (4101.3825, 2242.038),
                    (4101.3825, 2261.038), (3955.3825, 2261.038),
                ],
                [
                    (4533.3825, 2261.038), (4387.3825, 2261.038),
                    (4387.3825, 2242.038), (4552.3825, 2242.038),
                ],
            ],
        }},
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [{
            "type": "poly",
            "points": [
                (4101.3825, 2242.038), (4343.8825, 2242.038),
                (4387.3825, 2242.038), (4343.8825, 2242.038),
            ],
            "len": 286.0,
        }]}},
    }

    repaired = FundoVigaInterpreter.repair_area_links(beam)
    link = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]

    assert repaired == 1
    assert link["closed"] is True
    assert link["points"][0] == link["points"][-1]
    assert min(p[1] for p in link["points"]) == 2242.038
    assert max(p[1] for p in link["points"]) == 2261.038
    assert max(p[1] for p in link["points"]) - min(p[1] for p in link["points"]) == 19.0
    assert round(FundoVigaInterpreter._polygon_area(link["points"]), 6) == 5434.0


def test_fundo_never_repairs_human_validated_geometry():
    original = [(0, 0), (100, 0)]
    beam = {
        "is_h": True,
        "pos": (0, 0),
        "fields": {"viga_fundo_seg_1_dim": "20/50"},
        "geometry": {"classified": {
            "merged_bottom_groups_coords": [(0, 100)],
            "seg_bottom": [original],
        }},
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [{
            "type": "poly", "points": original, "validated": True,
        }]}},
    }

    assert FundoVigaInterpreter.repair_area_links(beam) == 0
    assert beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"] == original


def test_fundo_preserves_valid_chamfer_and_only_closes_it():
    chamfer = [(0, 0), (80, 0), (100, 20), (0, 20)]
    beam = {
        "is_h": True,
        "pos": (0, 10),
        "fields": {"viga_fundo_seg_1_dim": "20/50"},
        "geometry": {"classified": {
            "merged_bottom_groups_coords": [(0, 100)],
            "seg_bottom": [],
        }},
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [{
            "type": "poly", "points": chamfer,
        }]}},
    }

    assert FundoVigaInterpreter.repair_area_links(beam) == 1
    points = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"]
    assert points == chamfer + [chamfer[0]]
    assert FundoVigaInterpreter._polygon_area(points) == 1800.0


def test_fundo_replaces_short_cap_with_diagonal_body():
    beam = {
        "is_h": False,
        "pos": (1178.8825, 2240.038),
        "fields": {"viga_fundo_seg_1_dim": "19/60"},
        "geometry": {"classified": {
            "merged_bottom_groups_coords": [(2209.329149, 2240.038)],
            "seg_bottom": [
                [(1178.8825, 2240.038), (1178.8825, 2209.329149)],
            ],
            "seg_side_a": [
                [(1197.8825, 2217.506423), (1197.8825, 2240.038)],
            ],
            "seg_side_b": [
                [(1178.8825, 2209.329149), (1349.278794, 2048.038)],
                [(1356.845108, 2067.038), (1197.8825, 2217.506423)],
            ],
        }},
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [{
            "type": "poly",
            "points": [
                (1178.8825, 2209.329149),
                (1178.8825, 2240.038),
                (1198.8825, 2240.038),
                (1198.8825, 2209.329149),
            ],
        }]}}
    }

    assert FundoVigaInterpreter.repair_area_links(beam) == 1
    points = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"]

    link = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]

    assert points[0] == points[-1]
    assert (1349.278794, 2048.038) in points
    assert (1356.845108, 2067.038) in points
    assert link["geometry_source"] == "fundo_viga_interpreter_special_diagonal_l"
    assert link["fv_measure_source"] == "special_diagonal_longest_edge"
    assert link["fv_measure_width"] == 19.0
    assert round(link["fv_measure_length"], 6) == round(234.62679249112776, 6)


def test_fundo_extends_short_diagonal_cap_to_connected_l_shape():
    beam = {
        "is_h": False,
        "pos": (1178.8825, 2240.038),
        "fields": {"viga_fundo_seg_1_dim": "19/60"},
        "geometry": {"classified": {
            "merged_bottom_groups_coords": [(2209.329149, 2240.038)],
            "seg_bottom": [
                [(1178.8825, 2240.038), (1178.8825, 2209.329149)],
            ],
            "seg_side_a": [
                [(1197.8825, 2217.506423), (1197.8825, 2240.038)],
            ],
            "seg_side_b": [
                [(1178.8825, 2209.329149), (1349.278794, 2048.038)],
                [(1356.845108, 2067.038), (1197.8825, 2217.506423)],
            ],
        }},
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [{
            "type": "poly",
            "points": [
                (1178.8825, 2209.329149),
                (1178.8825, 2240.038),
                (1198.8825, 2240.038),
                (1198.8825, 2209.329149),
            ],
        }]}}
    }
    neighbor = {"geometry": {"classified": {
        "seg_bottom": [
            [(1349.278794, 2048.038), (1603.3825, 2048.038)],
            [(1603.3825, 2067.038), (1356.845108, 2067.038)],
        ]
    }}}

    assert FundoVigaInterpreter.repair_area_links(
        beam, context_beams=[beam, neighbor]
    ) == 1
    points = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"]

    link = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]

    assert (1603.3825, 2048.038) in points
    assert (1603.3825, 2067.038) in points
    assert link["geometry_source"] == "fundo_viga_interpreter_special_diagonal_l"
    assert link["fv_measure_source"] == "special_diagonal_longest_edge"
    assert link["fv_measure_width"] == 19.0
    assert round(link["fv_measure_length"], 6) == round(254.10370599999987, 6)


def test_fundo_does_not_replace_long_horizontal_panel_with_contextual_diagonal_l():
    points = [
        (1349.278794, 2061.288),
        (1600.8825, 2061.288),
        (1600.8825, 2080.288),
        (1349.278794, 2080.288),
        (1349.278794, 2061.288),
    ]
    beam = {
        "is_h": True,
        "pos": (1475.0, 2061.288),
        "fields": {"viga_fundo_seg_1_dim": "19/55"},
        "geometry": {"classified": {
            "merged_bottom_groups_coords": [(1349.278794, 1600.8825)],
            "seg_bottom": [
                [(1349.278794, 2061.288), (1600.8825, 2061.288)],
            ],
            "seg_side_a": [
                [(1349.278794, 2080.288), (1600.8825, 2080.288)],
            ],
            "seg_side_b": [
                [(1349.278794, 2061.288), (1600.8825, 2061.288)],
            ],
        }},
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [{
            "type": "poly",
            "points": list(points),
        }]}}
    }
    neighbor = {"geometry": {"classified": {
        "seg_side_a": [[(1197.8825, 2217.506423), (1197.8825, 2240.038)]],
        "seg_side_b": [
            [(1178.8825, 2209.329149), (1349.278794, 2048.038)],
            [(1356.845108, 2067.038), (1197.8825, 2217.506423)],
        ],
        "seg_bottom": [
            [(1349.278794, 2048.038), (1603.3825, 2048.038)],
            [(1603.3825, 2067.038), (1356.845108, 2067.038)],
        ],
    }}}

    assert FundoVigaInterpreter.repair_area_links(
        beam, context_beams=[beam, neighbor]
    ) == 0
    link = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]

    assert link["points"] == points
    assert "fv_measure_source" not in link


def test_fundo_repairs_degenerate_vertical_occurrence_from_its_run():
    beam = {
        "is_h": True,
        "fv_is_h": False,
        "pos": (999, 999),
        "fields": {"viga_fundo_seg_1_dim": "20/50"},
        "geometry": {"classified": {
            "merged_bottom_groups_coords": [(0, 999)],
            "seg_bottom": [[(210, 0), (210, 80)]],
            "bottom_runs": [{
                "is_h": False,
                "pos": (200, 0),
                "coords": [(0, 80)],
                "lengths": [80],
            }],
        }},
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [{
            "type": "poly", "points": [(210, 0), (210, 80)],
        }]}},
    }

    assert FundoVigaInterpreter.repair_area_links(beam) == 1
    points = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"]
    assert points[0] == points[-1]
    assert max(p[0] for p in points) - min(p[0] for p in points) == 20.0
    assert max(p[1] for p in points) - min(p[1] for p in points) == 80.0


def test_fundo_repairs_stale_area_when_run_span_is_longer():
    stale_points = [
        (3351.3825, 2881.538),
        (3351.3825, 2991.038),
        (3370.3825, 2991.038),
        (3370.3825, 2881.538),
        (3351.3825, 2881.538),
    ]
    beam = {
        "is_h": True,
        "fv_is_h": False,
        "pos": (3347.6325, 2695.038),
        "fields": {"viga_fundo_seg_1_dim": "19/120"},
        "geometry": {"classified": {
            "bottom_runs": [{
                "is_h": False,
                "pos": (3347.6325, 2695.038),
                "coords": [(2881.538, 3141.038)],
                "lengths": [259.5],
            }],
        }},
        "links": {
            "viga_segs": {"seg_bottom": [{"type": "poly", "points": list(stale_points)}]},
            "viga_fundo_seg_1_area_segs": {"contour": [{
                "type": "poly",
                "points": list(stale_points),
                "len": 259.5,
            }]},
        },
    }

    assert FundoVigaInterpreter.repair_area_links(beam) == 1
    link = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    points = link["points"]

    assert link["geometry_source"] == "fundo_viga_interpreter_run_span_repair"
    assert link["len"] == 259.5
    assert max(p[0] for p in points) - min(p[0] for p in points) == 19.0
    assert max(p[1] for p in points) - min(p[1] for p in points) == 259.5
    assert beam["links"]["viga_segs"]["seg_bottom"][0]["len"] == 259.5
    assert beam["links"]["viga_segs"]["seg_bottom"][0]["points"] == points


def test_fundo_repairs_simple_rectangle_width_from_dimension():
    points = [(0, 0), (398, 0), (398, 14), (0, 14), (0, 0)]
    beam = {
        "is_h": True,
        "pos": (0, 7),
        "fields": {"viga_fundo_seg_1_dim": "19/100"},
        "geometry": {"classified": {"merged_bottom_groups_coords": [(0, 398)]}},
        "links": {
            "viga_segs": {"seg_bottom": [{"type": "poly", "points": list(points)}]},
            "viga_fundo_seg_1_area_segs": {"contour": [{
                "type": "poly",
                "points": list(points),
            }]},
        },
    }

    assert FundoVigaInterpreter.repair_area_links(beam) == 1
    repaired = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    ys = [point[1] for point in repaired["points"]]
    xs = [point[0] for point in repaired["points"]]

    assert max(xs) - min(xs) == 398
    assert max(ys) - min(ys) == 19
    assert repaired["geometry_source"] == "fundo_viga_interpreter_width_repair"


def test_fundo_width_repair_prefers_link_ficha_over_automatic_dimension():
    points = [(0, 0), (24, 0), (24, 260), (0, 260), (0, 0)]
    beam = {
        "is_h": False,
        "pos": (12, 0),
        "fields": {"viga_fundo_seg_1_dim": "24/66"},
        "geometry": {"classified": {"merged_bottom_groups_coords": [(0, 260)]}},
        "links": {
            "viga_fundo_seg_1_area_segs": {"contour": [{
                "type": "poly",
                "points": list(points),
                "ficha": {
                    "largura_total_fundo": "14",
                    "comprimento_total_fundo": "260",
                },
            }]},
        },
    }

    assert FundoVigaInterpreter.repair_area_links(beam) == 1
    repaired = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    xs = [point[0] for point in repaired["points"]]
    ys = [point[1] for point in repaired["points"]]

    assert max(xs) - min(xs) == 14
    assert max(ys) - min(ys) == 260
    assert repaired["len"] == 260
    assert repaired["geometry_source"] == "fundo_viga_interpreter_width_repair"


def test_lateral_interpreter_writes_only_its_own_side_and_behavior():
    registry = build_interpreter_registry()
    interpreter = registry[InterpreterKind.LATERAL_VIGA_A_PARA]
    beam = {
        "is_h": True,
        "pos": (0.0, 0.0),
        "links": {},
        "lv_dimension_override": "19/55",
    }
    classified = {
        "merged_bottom_lengths": [100.0],
        "merged_bottom_groups_coords": [(0.0, 100.0)],
        "seg_side_a": [[(0.0, 10.0), (100.0, 10.0)]],
        "seg_side_b": [[(0.0, -10.0), (100.0, -10.0)]],
    }

    total = interpreter.interpret(beam, classified)

    assert total == 100.0
    assert set(beam["links"]) == {"viga_a_seg_1_comprimento_total"}
    assert "seg_side_a" in beam["links"]["viga_a_seg_1_comprimento_total"]
    assert (
        beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"][0]
        ["lv_dimensao"]
        == "19/55"
    )
    link = beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"][0]
    assert link["contract_id"] == "LV_A_PARA"
    assert link["behavior"] == "Para"
    assert link["segment_index"] == 1


def test_lateral_contract_specific_topology_keeps_para_and_passa_distinct():
    registry = build_interpreter_registry()
    beam = {"is_h": True, "pos": (0.0, 0.0), "links": {}}
    classified = {
        # Legado propositalmente diferente: nao pode vencer o contrato explicito.
        "lv_merged_bottom_lengths": [999.0],
        "lv_merged_bottom_groups_coords": [(0.0, 999.0)],
        "lv_seg_side_a": [[(0.0, 10.0), (999.0, 10.0)]],
        "lv_a_para_lengths": [96.5, 100.0],
        "lv_a_para_groups_coords": [(0.0, 96.5), (100.0, 200.0)],
        "lv_a_para_lines": [
            [(0.0, 10.0), (96.5, 10.0)],
            [(100.0, 10.0), (200.0, 10.0)],
        ],
        "lv_a_passa_lengths": [204.0],
        "lv_a_passa_groups_coords": [(0.0, 204.0)],
        "lv_a_passa_lines": [[(0.0, 10.0), (204.0, 10.0)]],
    }

    para_total = registry[InterpreterKind.LATERAL_VIGA_A_PARA].interpret(
        beam, classified
    )
    passa_total = registry[InterpreterKind.LATERAL_VIGA_A_PASSA].interpret(
        beam, classified
    )

    assert para_total == 196.5
    assert passa_total == 204.0
    assert beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"][0]["len"] == 96.5
    assert beam["links"]["viga_a_seg_2_comprimento_total"]["seg_side_a"][0]["len"] == 100.0
    assert beam["links"]["viga_a_seg_1_comp_total_passa"]["seg_side_a"][0]["len"] == 204.0
    assert beam["links"]["viga_a_seg_1_comp_total_passa"]["seg_side_a"][0]["contract_id"] == "LV_A_PASSA"


def test_pillar_para_and_passa_are_mutually_exclusive():
    registry = build_interpreter_registry()
    para = registry[InterpreterKind.PILAR_COM_VIGA_PARA]
    passa = registry[InterpreterKind.PILAR_COM_VIGA_PASSA]
    pillar = (90.0, -10.0, 110.0, 10.0)

    stopping_beam = (0.0, -9.0, 100.0, 9.0)
    passing_beam = (0.0, -9.0, 200.0, 9.0)

    assert para.matches(pillar, stopping_beam, True)
    assert not passa.matches(pillar, stopping_beam, True)
    assert passa.matches(pillar, passing_beam, True)
    assert not para.matches(pillar, passing_beam, True)


def test_beam_label_orientation_is_per_occurrence_and_diagonal_is_deferred():
    assert BeamTracer._orientation_from_label(0) is True
    assert BeamTracer._orientation_from_label(180) is True
    assert BeamTracer._orientation_from_label(90) is False
    assert BeamTracer._orientation_from_label(270) is False
    assert BeamTracer._orientation_from_label(136.5) is None


def test_lateral_interpreter_preserves_mixed_orientation_runs():
    registry = build_interpreter_registry()
    interpreter = registry[InterpreterKind.LATERAL_VIGA_B_PASSA]
    beam = {"is_h": True, "pos": (0.0, 0.0), "links": {}}
    classified = {
        "merged_bottom_lengths": [999.0],
        "merged_bottom_groups_coords": [(0.0, 999.0)],
        "seg_side_b": [],
        "bottom_runs": [
            {
                "is_h": True,
                "pos": (0.0, 10.0),
                "coords": [(0.0, 100.0)],
                "lengths": [100.0],
            },
            {
                "is_h": False,
                "pos": (200.0, 0.0),
                "coords": [(0.0, 80.0)],
                "lengths": [80.0],
            },
        ],
    }

    total = interpreter.interpret(beam, classified)

    assert total == 180.0
    assert set(beam["links"]) == {
        "viga_b_seg_1_comp_total_passa",
        "viga_b_seg_2_comp_total_passa",
    }


def test_lv_dimension_rejects_reversed_pillar_dimension():
    class FakeSpatialIndex:
        def query_bbox(self, _bbox):
            return [
                {"text": "120/19", "pos": (1.0, 0.0), "rotation": 0},
                {"text": "19/55", "pos": (5.0, 0.0), "rotation": 0},
            ]

    tracer = BeamTracer(FakeSpatialIndex())

    result = tracer._nearest_beam_dimension(
        (0.0, 0.0),
        [[(0.0, 0.0), (100.0, 0.0)]],
        True,
    )

    assert result["text"] == "19/55"
