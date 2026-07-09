from src.core.preficha_segments import (
    SEGMENT_TAB_SPECS,
    apply_preficha_segment_decisions,
    collect_preficha_segments,
    fundo_topology_is_locked,
    lock_fundo_topology,
    preficha_geometry_policy,
    preficha_source_status,
    restore_locked_fundo_topology,
)
from scripts.analise_geral_headless import (
    _filter_fv_visual_obstacles,
    process_beam_fv,
)


def _beam():
    return {
        "name": "V301",
        "links": {
            "viga_fundo_seg_1_area_segs": {
                "contour": [{
                    "points": [(0, 0), (100, 0), (100, 20), (0, 20)],
                    "len": 100,
                    "ficha": {"largura_total_fundo": "20"},
                }]
            },
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [{"points": [(0, 20), (100, 20)], "len": 100}]
            },
            "viga_b_seg_1_comprimento_total": {
                "seg_side_b": [{"points": [(0, 0), (100, 0)], "len": 100}]
            },
            "viga_a_seg_1_comp_total_passa": {
                "seg_side_a": [{"points": [(0, 20), (100, 20)], "len": 100}]
            },
            "viga_b_seg_1_comp_total_passa": {
                "seg_side_b": [{"points": [(0, 0), (100, 0)], "len": 100}]
            },
        },
    }


def test_collects_all_five_segment_tabs_from_sa_contract():
    collected = collect_preficha_segments([_beam()])

    assert set(collected) == set(SEGMENT_TAB_SPECS)
    assert {kind: len(rows) for kind, rows in collected.items()} == {
        "fundo": 1,
        "lateral_a_para": 1,
        "lateral_b_para": 1,
        "lateral_a_passa": 1,
        "lateral_b_passa": 1,
    }
    assert collected["fundo"][0]["beam_name"] == "V301"
    assert collected["fundo"][0]["width"] == "20"
    assert collected["lateral_b_passa"][0]["source_slot"] == "seg_side_b"


def test_lateral_link_dimension_does_not_reuse_fv_segment_ficha():
    beam = _beam()
    link = beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"][0]
    link["lv_dimensao"] = "19/55"

    collected = collect_preficha_segments([beam])

    assert collected["fundo"][0]["width"] == "20"
    assert collected["lateral_a_para"][0]["width"] == "19/55"


def test_fundo_preficha_length_and_width_use_bbox_not_stale_len():
    beam = _beam()
    link = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    link["points"] = [(0, 0), (19, 0), (19, 259.5), (0, 259.5), (0, 0)]
    link["len"] = 109.5
    link["ficha"] = {"largura_total_fundo": "999"}

    collected = collect_preficha_segments([beam])["fundo"][0]

    assert collected["length"] == 259.5
    assert collected["width"] == "19"


def test_fundo_preficha_special_diagonal_uses_canonical_measure_length():
    beam = _beam()
    link = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    link["points"] = [
        (0, 0), (19, 0), (19, 35), (255, 35), (255, 16), (30, 16), (0, 0)
    ]
    link["fv_measure_length"] = 255.7
    link["fv_measure_width"] = 19
    link["fv_measure_source"] = "special_diagonal_longest_edge"

    collected = collect_preficha_segments([beam])["fundo"][0]

    assert collected["length"] == 255.7
    assert collected["width"] == "19"
    assert collected["measure_source"] == "special_diagonal_longest_edge"


def test_lateral_dimension_override_propagates_to_sibling_links():
    beam = _beam()
    first = beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"][0]
    first["lv_dimensao"] = "19/55"

    collected = collect_preficha_segments([beam])

    assert collected["lateral_b_passa"][0]["width"] == "19/55"


def test_ignored_segment_removes_the_exact_link_shown_in_preficha():
    beam = _beam()
    collected = collect_preficha_segments([beam])
    target = collected["lateral_a_para"][0]
    untouched = collected["lateral_a_passa"][0]["_link_ref"]

    summary = apply_preficha_segment_decisions(
        [beam],
        {target["uid"]: {"status": "ignore", "attention": "Geometria indevida"}},
    )

    assert summary == {"reviewed": 1, "removed": 1}
    assert beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"] == []
    assert beam["links"]["viga_a_seg_1_comp_total_passa"]["seg_side_a"] == [untouched]
    assert beam["preficha_segmentos"][target["uid"]]["attention"] == "Geometria indevida"
    assert preficha_source_status(beam, target["source_key"]) == "ignore"
    assert preficha_geometry_policy(beam, target["source_key"]) == "ignore"
    assert collect_preficha_segments([beam])["lateral_a_para"] == []


def test_saved_segment_review_is_restored_on_next_collection():
    beam = _beam()
    uid = collect_preficha_segments([beam])["fundo"][0]["uid"]
    beam["preficha_segmentos"] = {
        uid: {"status": "valid", "attention": "Conferir apoio inicial"}
    }

    restored = collect_preficha_segments([beam])["fundo"][0]

    assert restored["status"] == "valid"
    assert restored["attention"] == "Conferir apoio inicial"


def test_preficha_decision_marks_link_but_does_not_freeze_topology():
    beam = _beam()
    target = collect_preficha_segments([beam])["fundo"][0]

    apply_preficha_segment_decisions(
        [beam],
        {target["uid"]: {"status": "valid", "attention": "Aprovado"}},
    )

    link = beam["links"][target["source_key"]][target["source_slot"]][0]
    assert link is target["_link_ref"]
    assert link["preficha_reviewed"] is True
    assert link["preficha_status"] == "valid"
    assert link["preficha_uid"] == target["uid"]
    assert preficha_source_status(beam, target["source_key"]) == "valid"
    assert preficha_geometry_policy(beam, target["source_key"]) == "preserve"
    assert fundo_topology_is_locked(beam) is False
    assert "preficha_fundo_locked_source_keys" not in beam


def test_locked_fundo_restoration_discards_newly_inferred_segments():
    validated = _beam()
    validated["id"] = "project_b_1"
    target = _beam()
    target["id"] = "project_b_1"
    target["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"] = [
        (0, 0), (999, 0), (999, 20), (0, 20)
    ]
    target["links"]["viga_fundo_seg_2_area_segs"] = {
        "contour": [{
            "points": [(100, 0), (200, 0), (200, 20), (100, 20)],
            "len": 100,
        }]
    }
    validated_link = validated["links"][
        "viga_fundo_seg_1_area_segs"
    ]["contour"][0]
    validated_link["validated"] = True

    assert restore_locked_fundo_topology(target, validated) is True
    assert "viga_fundo_seg_2_area_segs" not in target["links"]
    assert target["links"]["viga_fundo_seg_1_area_segs"] == (
        validated["links"]["viga_fundo_seg_1_area_segs"]
    )


def test_lock_excludes_unvalidated_contour_added_after_human_validation():
    beam = _beam()
    beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0][
        "validated"
    ] = True
    beam["links"]["viga_fundo_seg_2_area_segs"] = {
        "contour": [{
            "points": [(100, 0), (200, 0), (200, 20), (100, 20)],
            "len": 100,
        }]
    }

    # Simula registro antigo sem snapshot v2.
    beam.pop("preficha_fundo_locked", None)
    beam.pop("preficha_fundo_locked_version", None)
    beam.pop("preficha_fundo_locked_source_keys", None)
    result = process_beam_fv(beam)

    assert beam["preficha_fundo_locked_source_keys"] == [
        "viga_fundo_seg_1_area_segs"
    ]
    assert result["panels_n1"] == 1


def test_partial_real_validation_prunes_every_unvalidated_contour():
    beam = _beam()
    beam["links"]["viga_fundo_seg_2_area_segs"] = {
        "contour": [{
            "points": [(100, 0), (200, 0), (200, 20), (100, 20)],
            "len": 100,
        }]
    }
    beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0][
        "validated"
    ] = True
    lock_fundo_topology(beam)

    assert beam["preficha_fundo_locked_source_keys"] == [
        "viga_fundo_seg_1_area_segs"
    ]
    assert "viga_fundo_seg_2_area_segs" not in beam["links"]
    assert collect_preficha_segments([beam])["fundo"][0]["segment_index"] == 1
    assert len(collect_preficha_segments([beam])["fundo"]) == 1


def test_auxiliary_fundo_field_without_contour_does_not_lock_topology():
    beam = _beam()
    beam["links"].pop("viga_fundo_seg_1_area_segs")
    beam["validated_fields"] = [
        "viga_fundo_seg_1_dim",
        "viga_fundo_seg_1_local_fim",
    ]

    assert fundo_topology_is_locked(beam) is False


def test_stale_locked_fundo_source_without_contour_does_not_lock_topology():
    beam = _beam()
    beam["links"]["viga_fundo_seg_1_area_segs"]["contour"] = []
    beam["preficha_fundo_locked"] = True
    beam["preficha_fundo_locked_version"] = 2
    beam["preficha_fundo_locked_source_keys"] = [
        "viga_fundo_seg_1_area_segs",
    ]

    assert fundo_topology_is_locked(beam) is False


def test_full_validation_after_ignoring_every_fundo_locks_zero_segments():
    beam = _beam()
    decision = collect_preficha_segments([beam])["fundo"][0]
    apply_preficha_segment_decisions(
        [beam],
        {decision["uid"]: {"status": "ignore"}},
    )
    assert fundo_topology_is_locked(beam) is False

    beam["is_validated"] = True
    assert fundo_topology_is_locked(beam) is True
    assert process_beam_fv(beam)["panels_n1"] == 0
    assert beam["preficha_fundo_locked_source_keys"] == []


def test_locked_fundo_processing_uses_only_human_validated_contours():
    beam = _beam()
    beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0][
        "validated"
    ] = True
    beam["geometry"] = {
        "classified": {
            "merged_bottom_lengths": [10.0, 20.0, 30.0],
            "merged_bottom_groups_coords": [(0, 10), (10, 30), (30, 60)],
        }
    }

    result = process_beam_fv(beam)

    assert result["topologia_origem"] == "validacao_humana_bloqueada"
    assert result["panels_n1"] == 1
    assert result["segmentos_fundo"][0]["length"] == 100.0


def test_locked_fundo_processing_uses_bbox_instead_of_stale_len():
    beam = _beam()
    link = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    link["validated"] = True
    link["points"] = [(0, 0), (19, 0), (19, 259.5), (0, 259.5), (0, 0)]
    link["len"] = 999.0

    result = process_beam_fv(beam)

    assert result["segmentos_fundo"][0]["length"] == 259.5
    assert result["comprimento_fundo"] == 259.5
    assert link["len"] == 259.5
    assert link["ficha"]["comprimento_total_fundo"] == "259.5"
    assert link["ficha"]["largura_total_fundo"] == "19"


def test_fv_visual_obstacles_ignore_nasce_pillars():
    filtered = _filter_fv_visual_obstacles([
        {"type": "NASCE", "bbox": (0, 0, 10, 10)},
        {"type": "PILAR_SOLIDO", "bbox": (20, 0, 30, 10)},
        {"type": "VISAO_CORTE", "bbox": (40, 0, 50, 10)},
    ])

    assert [item["type"] for item in filtered] == ["PILAR_SOLIDO", "VISAO_CORTE"]


def test_stale_decision_from_another_beam_id_does_not_block_harmonization():
    beam = _beam()
    beam["id"] = "beam-atual"
    centerline = [(0, 10), (100, 10)]
    beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"][0]["points"] = centerline
    beam["links"]["viga_b_seg_1_comprimento_total"]["seg_side_b"][0]["points"] = centerline
    beam["preficha_segmentos"] = {
        "lateral_a_para|beam-antiga|1|1": {
            "status": "ignore",
            "source_key": "viga_a_seg_1_comprimento_total",
        }
    }

    collected = collect_preficha_segments([beam])

    assert collected["lateral_a_para"][0]["points"] == [(0.0, 20.0), (100.0, 20.0)]
    assert preficha_source_status(beam, "viga_a_seg_1_comprimento_total") == ""
    assert preficha_geometry_policy(
        beam, "viga_a_seg_1_comprimento_total"
    ) == "infer"


def test_fragments_with_same_parent_name_keep_distinct_uids():
    first = _beam()
    second = _beam()
    first.update({"id": "project_b_1", "parent_name": "V301"})
    second.update({"id": "project_b_2", "parent_name": "V301"})

    rows = collect_preficha_segments([first, second])["fundo"]

    assert len(rows) == 2
    assert rows[0]["uid"] != rows[1]["uid"]


def test_repairs_legacy_centerline_as_distinct_lateral_edges():
    beam = _beam()
    centerline = [(0, 10), (100, 10)]
    for side in ("a", "b"):
        for suffix in ("comprimento_total", "comp_total_passa"):
            slot = f"seg_side_{side}"
            beam["links"][f"viga_{side}_seg_1_{suffix}"][slot][0]["points"] = centerline

    collected = collect_preficha_segments([beam])

    for behavior in ("para", "passa"):
        assert collected[f"lateral_a_{behavior}"][0]["points"] == [(0.0, 20.0), (100.0, 20.0)]
        assert collected[f"lateral_b_{behavior}"][0]["points"] == [(0.0, 0.0), (100.0, 0.0)]
    assert beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"][0]["geometry_role"] == "lateral"


def test_lateral_details_include_height_supports_and_only_touching_side_slabs():
    beam = _beam()
    beam["fields"] = {
        "viga_a_seg_1_h1": "55",
        "viga_a_seg_1_ini_name": "P1",
        "viga_a_seg_1_ini_dim": "19x60",
        "viga_a_seg_1_ini_nivel": "+3.00",
        "viga_a_seg_1_end_name": "V302",
        "viga_a_seg_1_nivel_viga": "+2.95",
        "viga_a_seg_1_continuidade": "Viga",
        "viga_a_seg_1_ajuste_inicial": "3",
        "viga_a_seg_1_ajuste_final": "7",
        "viga_a_seg_1_ajuste_comprimento": "10",
    }
    slabs = [
        {
            "name": "L1",
            "points": [(0, 20), (100, 20), (100, 80), (0, 80)],
            "fields": {"laje_dim": "h=12", "laje_nivel": "+3.00"},
        },
        {
            "name": "L2",
            "points": [(0, -80), (100, -80), (100, 0), (0, 0)],
            "fields": {"laje_dim": "h=10", "laje_nivel": "+2.98"},
        },
    ]

    segment = collect_preficha_segments([beam], slabs=slabs)["lateral_a_para"][0]

    assert segment["height"] == "55"
    assert segment["details"]["support_start"] == {
        "name": "P1", "dimension": "19x60", "level": "+3.00"
    }
    assert segment["details"]["support_end"]["name"] == "V302"
    assert segment["details"]["beam_level"] == "+2.95"
    assert segment["details"]["slabs"] == [
        {"name": "L1", "level": "+3.00", "height": "12"}
    ]
    assert segment["details"]["adjustment"] == {
        "initial": "3", "final": "7", "total": "10"
    }


def test_lateral_support_falls_back_to_fundo_segment_and_pillar_metadata():
    beam = _beam()
    beam["fields"] = {
        "viga_fundo_seg_1_local_ini": "P1",
        "viga_fundo_seg_1_local_fim": "V302",
    }
    support_beam = _beam()
    support_beam["name"] = "V302"
    support_beam["fields"] = {"dimensao": "20x60", "nivel_lado_a": "+3.00"}

    segment = collect_preficha_segments(
        [beam, support_beam],
        pillar_report={"P1": {"points": [(0, 0), (19, 0), (19, 50), (0, 50)]}},
        nivel_report={"pilares": {"P1": {"level_str": "+2.95"}}},
    )["lateral_a_para"][0]

    assert segment["details"]["support_start"] == {
        "name": "P1", "dimension": "19x50", "level": "+2.95"
    }
    assert segment["details"]["support_end"] == {
        "name": "V302", "dimension": "20x60", "level": "+3.00"
    }
