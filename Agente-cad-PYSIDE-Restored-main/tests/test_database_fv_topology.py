from src.core.database import DatabaseManager


def _area(points, *, validated=False):
    link = {"type": "poly", "points": points, "len": 100}
    if validated:
        link["validated"] = True
    return {"contour": [link]}


def test_stale_fv_area_validation_does_not_replace_new_topology(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.vision"))
    project_id = "project"
    beam_id = "project_b_1"
    old = {
        "id": beam_id,
        "name": "V306",
        "id_item": "01",
        "type": "Viga",
        "seg_c": 2,
        "preficha_fundo_locked": True,
        "preficha_fundo_locked_version": 2,
        "preficha_fundo_locked_source_keys": ["viga_fundo_seg_1_area_segs"],
        "validated_fields": [
            "viga_fundo_seg_1_area_segs",
            "viga_fundo_seg_1_dim",
        ],
        "fields": {"viga_fundo_seg_1_dim": "19/55"},
        "links": {
            "viga_fundo_seg_1_area_segs": _area(
                [(900, 0), (1000, 0), (1000, 19), (900, 19)],
                validated=True,
            ),
        },
    }
    db.save_beam(old, project_id, trust_current_validation=True)

    fresh = {
        "id": beam_id,
        "name": "V306",
        "id_item": "01",
        "type": "Viga",
        "seg_c": 2,
        "geometry": {"classified": {
            "merged_bottom_groups_coords": [(0, 100), (120, 220)],
        }},
        "links": {
            "viga_fundo_seg_1_area_segs": _area(
                [(0, 0), (100, 0), (100, 19), (0, 19)],
            ),
            "viga_fundo_seg_2_area_segs": _area(
                [(120, 0), (220, 0), (220, 19), (120, 19)],
            ),
        },
    }
    db.save_beam(fresh, project_id)

    saved = db.load_beams(project_id)[0]
    assert saved["fields"]["viga_fundo_seg_1_dim"] == "19/55"
    assert "viga_fundo_seg_1_area_segs" not in saved["validated_fields"]
    assert saved["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"][0] == [0, 0]
    assert "viga_fundo_seg_2_area_segs" in saved["links"]
