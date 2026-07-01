from src.ui.canvas import CADCanvas
from src.ui.widgets.detail_card import DetailCard


def _beam_links():
    return {
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [{"type": "poly", "points": [(0, 20), (100, 20)]}]
            },
            "viga_a_seg_1_comp_total_passa": {
                "seg_side_a": [{"type": "poly", "points": [(0, 21), (100, 21)]}]
            },
            "viga_b_seg_1_comprimento_total": {
                "seg_side_b": [{"type": "poly", "points": [(0, 0), (100, 0)]}]
            },
            "viga_b_seg_1_comp_total_passa": {
                "seg_side_b": [{"type": "poly", "points": [(0, -1), (100, -1)]}]
            },
            "viga_fundo_seg_1_area_segs": {
                "contour": [{
                    "type": "poly",
                    "points": [(0, 0), (100, 0), (100, 20), (0, 20)],
                }]
            },
        },
        "viga_a_seg_1_exists": True,
        "viga_b_seg_1_exists": True,
        "viga_fundo_seg_1_exists": True,
    }


def test_canvas_filters_face_and_para_passa_as_independent_contexts():
    para_a = {"type": "viga_lateral_a", "_tipo_comp": "para"}
    passa_a = {"type": "viga_lateral_a", "_tipo_comp": "passa"}

    assert CADCanvas._beam_subtype_link_allowed(
        para_a, "viga_a_seg_1_comprimento_total"
    )
    assert not CADCanvas._beam_subtype_link_allowed(
        para_a, "viga_a_seg_1_comp_total_passa"
    )
    assert not CADCanvas._beam_subtype_link_allowed(
        para_a, "viga_b_seg_1_comprimento_total"
    )
    assert CADCanvas._beam_subtype_link_allowed(
        passa_a, "viga_a_seg_1_comp_total_passa"
    )


def test_canvas_segment_labels_come_from_selected_lateral_motor():
    beam = _beam_links()
    para = {"type": "viga_lateral_a", "_tipo_comp": "para"}
    passa = {"type": "viga_lateral_a", "_tipo_comp": "passa"}

    para_links = CADCanvas._collect_lateral_segs(None, beam, para)
    passa_links = CADCanvas._collect_lateral_segs(None, beam, passa)

    assert [link["points"] for link in para_links] == [[(0, 20), (100, 20)]]
    assert [link["points"] for link in passa_links] == [[(0, 21), (100, 21)]]
    assert para_links[0]["_field_id"].endswith("comprimento_total")
    assert passa_links[0]["_field_id"].endswith("comp_total_passa")


class _DetailCardContract:
    def __init__(self, item_data):
        self.item_data = item_data


def test_detail_card_hides_ignored_lateral_behavior_but_keeps_other_motor():
    beam = _beam_links()
    beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"] = []

    para_card = _DetailCardContract({**beam, "_tipo_comp": "para"})
    passa_card = _DetailCardContract({**beam, "_tipo_comp": "passa"})

    assert DetailCard._existing_beam_segment_indices(
        para_card, "viga_a", is_fundo=False
    ) == set()
    assert DetailCard._existing_beam_segment_indices(
        passa_card, "viga_a", is_fundo=False
    ) == {1}


def test_detail_card_hides_ignored_fundo_with_empty_contour():
    beam = _beam_links()
    beam["links"]["viga_fundo_seg_1_area_segs"]["contour"] = []
    beam["viga_fundo_seg_1_exists"] = False
    card = _DetailCardContract(beam)

    assert DetailCard._existing_beam_segment_indices(
        card, "viga_fundo", is_fundo=True
    ) == set()
