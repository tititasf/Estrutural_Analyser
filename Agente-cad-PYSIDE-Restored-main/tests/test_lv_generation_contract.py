from src.core.lv_generation_contract import (
    build_lv_generation_contracts,
    distribute_lv_panels,
)


def _entry(length, dim="14/50"):
    entry = {"points": [[0, 0], [length, 0]], "len": length}
    if dim:
        entry["lv_dimensao"] = dim
    return entry


def test_builds_four_isolated_lv_generation_contracts():
    beam = {
        "name": "V327",
        "fields": {"viga_fundo_seg_1_dim": "99/999"},
        "links": {
            "viga_a_seg_1_comprimento_total": {"seg_side_a": [_entry(96.5)]},
            "viga_a_seg_2_comprimento_total": {"seg_side_a": [_entry(100)]},
            "viga_b_seg_1_comprimento_total": {"seg_side_b": [_entry(196.5)]},
            "viga_a_seg_1_comp_total_passa": {"seg_side_a": [_entry(204)]},
            "viga_b_seg_1_comp_total_passa": {"seg_side_b": [_entry(204)]},
        },
    }

    contracts = build_lv_generation_contracts(beam, floor="13_PAV")

    assert [p["width"] for p in contracts["Para"]["A"]["panels"]] == [96.5, 100]
    assert [p["width"] for p in contracts["Passa"]["A"]["panels"]] == [204]
    assert contracts["Para"]["A"]["contract_id"] == "LV_A_PARA"
    assert contracts["Passa"]["B"]["contract_id"] == "LV_B_PASSA"
    assert contracts["Para"]["A"]["total_width"] == 14
    assert contracts["Para"]["A"]["h_section"] == 50
    assert contracts["Para"]["A"]["total_height"] == 54
    assert contracts["Para"]["A"]["behavior_distinct_from_other"] is True


def test_missing_lv_dimension_blocks_generation_and_never_uses_fv_dimension():
    beam = {
        "name": "V327",
        "fields": {"viga_fundo_seg_1_dim": "14/50"},
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_entry(200, dim="")]
            }
        },
    }

    contract = build_lv_generation_contracts(beam)["Para"]["A"]

    assert contract["segment_count"] == 1
    assert contract["dimension_status"] == "missing"
    assert contract["generation_ready"] is False
    assert contract["total_width"] == 0
    assert contract["_sa_meta"]["fv_dimension_fallback"] is False


def test_uses_canonical_lv_segment_field_after_cross_class_autofill():
    beam = {
        "name": "V308",
        "fields": {
            "viga_fundo_seg_1_dim": "19/55",
            "viga_a_seg_1_dim": "100/19",
        },
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_entry(291, dim="")]
            }
        },
    }

    contract = build_lv_generation_contracts(beam)["Para"]["A"]

    assert contract["total_width"] == 19
    assert contract["h_section"] == 100
    assert contract["generation_ready"] is True
    assert contract["_sa_meta"]["dimension_source"] == "sa_lv_segment_field"
    assert contract["_sa_meta"]["fv_dimension_fallback"] is False


def test_uses_beamtracer_lv_dimension_without_fv_fallback():
    beam = {
        "name": "V327",
        "geometry": {"lv_dimension_text": {"text": "14/50"}},
        "fields": {"viga_fundo_seg_1_dim": "24/66"},
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_entry(260, dim="")]
            }
        },
    }

    contract = build_lv_generation_contracts(beam)["Para"]["A"]

    assert contract["total_width"] == 14
    assert contract["h_section"] == 50
    assert contract["total_height"] == 54
    assert contract["generation_ready"] is True


def test_panelizer_avoids_short_residual_after_full_module():
    assert distribute_lv_panels(260) == [122.0, 138.0]
    assert distribute_lv_panels(256) == [122.0, 134.0]
    assert distribute_lv_panels(415) == [244.0, 171.0]


def test_v327_passa_reaches_expected_panels_from_n1_geometry_and_pillar():
    beam = {
        "name": "V327",
        "lv_is_h": False,
        "geometry": {"lv_dimension_text": {"text": "14/50"}},
        "links": {
            "viga_a_seg_1_comp_total_passa": {
                "seg_side_a": [{
                    "points": [[4387.3825, 1982.038], [4387.3825, 2242.038]],
                    "len": 260,
                }]
            },
            "viga_b_seg_1_comp_total_passa": {
                "seg_side_b": [{
                    "points": [[4387.3825, 1982.038], [4387.3825, 2242.038]],
                    "len": 260,
                }]
            },
        },
    }
    pillars = {"P27": (4387.3825, 2242.038, 4552.3825, 2460.038)}

    contracts = build_lv_generation_contracts(
        beam, pillar_bboxes=pillars
    )["Passa"]

    assert [panel["width"] for panel in contracts["A"]["panels"]] == [122.0, 134.0]
    assert [panel["width"] for panel in contracts["B"]["panels"]] == [122.0, 138.0]
    assert contracts["A"]["end_adjustment"] == -4.0
    assert contracts["B"]["end_adjustment"] == 0.0
    assert contracts["A"]["total_length"] == 256.0
    assert contracts["B"]["total_length"] == 260.0


def test_endpoint_labels_use_only_proven_local_lv_fields_not_global_fundo_links():
    beam = {
        "name": "V327",
        "geometry": {"lv_dimension_text": {"text": "14/50"}},
        "fields": {"viga_a_seg_1_end_name": "P27"},
        "links": {
            "apoios": {
                "inicio": [{"name": "V328"}],
                "fim": [{"name": "P27"}],
            },
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_entry(260)]
            },
        },
    }

    contract = build_lv_generation_contracts(beam)["Para"]["A"]

    assert contract["endpoint_labels"] == {"start": "", "end": "P27"}
