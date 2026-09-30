from main import MainWindow


class _Host:
    pillars_found = []
    slabs_found = []
    _lv_cross_class_context = MainWindow._lv_cross_class_context
    _populate_lv_segment_ui_fields = MainWindow._populate_lv_segment_ui_fields
    _beam_base_name = staticmethod(MainWindow._beam_base_name)
    _beam_list_display_name = MainWindow._beam_list_display_name


def _length(points):
    return {"points": points, "len": 200.0}


def test_v308_fundo_dimension_replaces_unvalidated_neighbor_and_reaches_all_contracts():
    beam = {
        "name": "V308",
        "dim": "60/19",
        "fields": {
            "dimensao": "60/19",
            "viga_fundo_seg_1_dim": "100/19",
            "viga_fundo_seg_1_local_ini": "V330",
            "viga_fundo_seg_1_local_fim": "P23",
            "viga_fundo_seg_2_dim": "100/19",
            "viga_fundo_seg_2_local_ini": "P23",
            "viga_fundo_seg_2_local_fim": "V309",
        },
        "validated_fields": [],
        "geometry": {"classified": {}},
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_length([[0, 0], [200, 0]])]
            },
            "viga_a_seg_1_comp_total_passa": {
                "seg_side_a": [_length([[0, 0], [200, 0]])]
            },
            "viga_a_seg_2_comprimento_total": {
                "seg_side_a": [_length([[200, 0], [400, 0]])]
            },
            "viga_a_seg_2_comp_total_passa": {
                "seg_side_a": [_length([[200, 0], [400, 0]])]
            },
            "viga_b_seg_1_comprimento_total": {
                "seg_side_b": [_length([[0, 19], [200, 19]])]
            },
            "viga_b_seg_1_comp_total_passa": {
                "seg_side_b": [_length([[0, 19], [200, 19]])]
            },
            "viga_b_seg_2_comprimento_total": {
                "seg_side_b": [_length([[200, 19], [400, 19]])]
            },
            "viga_b_seg_2_comp_total_passa": {
                "seg_side_b": [_length([[200, 19], [400, 19]])]
            },
        },
    }

    _Host()._populate_lv_segment_ui_fields(beam)

    assert beam["dim"] == "100/19"
    assert beam["fields"]["dimensao"] == "100/19"
    assert beam["_lv_dimension_source"] == "fundo_same_beam"
    for side in ("a", "b"):
        for index in (1, 2):
            assert beam["fields"][f"viga_{side}_seg_{index}_dim"] == "100/19"
            assert beam["fields"][f"viga_{side}_seg_{index}_ini_name"]
            assert beam["fields"][f"viga_{side}_seg_{index}_end_name"]
            for suffix in ("comprimento_total", "comp_total_passa"):
                entry = beam["links"][f"viga_{side}_seg_{index}_{suffix}"][f"seg_side_{side}"][0]
                assert entry["lv_dimensao"] == "100/19"
                assert entry["_lv_dimension_source"] == "fundo_same_beam"


def test_human_validated_global_dimension_is_not_overwritten():
    beam = {
        "name": "V308",
        "dim": "60/19",
        "fields": {
            "dimensao": "60/19",
            "viga_fundo_seg_1_dim": "100/19",
        },
        "validated_fields": ["dimensao"],
        "geometry": {"classified": {}},
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_length([[0, 0], [200, 0]])]
            }
        },
    }

    _Host()._populate_lv_segment_ui_fields(beam)

    assert beam["fields"]["dimensao"] == "60/19"
    assert beam["dim"] == "60/19"


def test_side_b_list_label_heals_stale_side_a_display_name():
    label = _Host()._beam_list_display_name(
        {"name": "LV-V327.A Para"},
        subtype="viga_lateral_b",
        tipo_comp="para",
    )

    assert label == "LV-V327.B Para"
