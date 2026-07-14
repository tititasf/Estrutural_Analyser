from src.core.lv_support_contact import support_contacts_lv_segment


def test_parallel_global_beam_is_not_a_local_lv_endpoint():
    segment = [[4387.3825, 1982.038], [4387.3825, 2242.038]]
    parallel = {
        "name": "V328",
        "geometry": {
            "classified": {
                "seg_bottom": [[[4533.3825, 1982.038], [4533.3825, 2242.038]]]
            }
        },
    }

    assert not support_contacts_lv_segment(segment, "V328", beams=[parallel])


def test_pillar_touching_segment_is_a_valid_local_endpoint():
    segment = [[4387.3825, 1982.038], [4387.3825, 2242.038]]
    pillar = {
        "name": "P27",
        "points": [[4377.0, 2242.038], [4397.0, 2242.038], [4397.0, 2262.0]],
    }

    assert support_contacts_lv_segment(segment, "P27", pillars=[pillar])
