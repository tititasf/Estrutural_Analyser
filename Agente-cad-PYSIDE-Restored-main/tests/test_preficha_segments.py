from src.core.preficha_segments import (
    SEGMENT_TAB_SPECS,
    apply_preficha_segment_decisions,
    collect_preficha_segments,
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


def test_ignored_segment_removes_the_exact_link_shown_in_preficha():
    beam = _beam()
    collected = collect_preficha_segments([beam])
    target = collected["lateral_a_para"][0]
    untouched = collected["lateral_a_passa"][0]["_link_ref"]

    summary = apply_preficha_segment_decisions(
        [beam],
        {target["uid"]: {"status": "ignore", "attention": "Geometria indevida"}},
    )

    assert summary == {"reviewed": 5, "removed": 1}
    assert beam["links"]["viga_a_seg_1_comprimento_total"]["seg_side_a"] == []
    assert beam["links"]["viga_a_seg_1_comp_total_passa"]["seg_side_a"] == [untouched]
    assert beam["preficha_segmentos"][target["uid"]]["attention"] == "Geometria indevida"


def test_saved_segment_review_is_restored_on_next_collection():
    beam = _beam()
    uid = collect_preficha_segments([beam])["fundo"][0]["uid"]
    beam["preficha_segmentos"] = {
        uid: {"status": "valid", "attention": "Conferir apoio inicial"}
    }

    restored = collect_preficha_segments([beam])["fundo"][0]

    assert restored["status"] == "valid"
    assert restored["attention"] == "Conferir apoio inicial"


def test_fragments_with_same_parent_name_keep_distinct_uids():
    first = _beam()
    second = _beam()
    first.update({"id": "project_b_1", "parent_name": "V301"})
    second.update({"id": "project_b_2", "parent_name": "V301"})

    rows = collect_preficha_segments([first, second])["fundo"]

    assert len(rows) == 2
    assert rows[0]["uid"] != rows[1]["uid"]
