from src.core.pillar_face_beams import _propagate_collinear_short_face_bands


def _pillar(x, *, donor=False, occupied=False):
    faces = {
        fid: {
            "passa_esq": None, "passa_dir": None,
            "para": [], "interior": [],
        }
        for fid in "ABCD"
    }
    if donor:
        faces["C"]["passa_dir"] = {"name": "VX", "dim": "19/55", "corner": "CB"}
    if occupied:
        faces["C"]["interior"] = [{"name": "VY", "dim": "19/50"}]
    return {
        "points": [[x, 0], [x + 19, 0], [x + 19, 66], [x, 66], [x, 0]],
        "face_beams": faces,
    }


def test_single_end_label_propagates_ac_bc_and_ca_cb_without_overwrite():
    report = {
        "P1": _pillar(0, donor=True),
        "P2": _pillar(100),
        "P3": _pillar(200, occupied=True),
        "P4": _pillar(300),
    }

    assert _propagate_collinear_short_face_bands(report) == 1
    p2 = report["P2"]["face_beams"]
    assert p2["C"]["passa_esq"]["corner"] == "CA"
    assert p2["C"]["passa_dir"]["corner"] == "CB"
    assert [(row["name"], row["corner"]) for row in p2["A"]["para"]] == [("VX", "AC")]
    assert [(row["name"], row["corner"]) for row in p2["B"]["para"]] == [("VX", "BC")]
    assert report["P3"]["face_beams"]["C"]["interior"][0]["name"] == "VY"
    assert report["P4"]["face_beams"]["C"]["passa_esq"] is None


def test_ambiguous_or_middle_donor_does_not_propagate():
    middle = {"P1": _pillar(0), "P2": _pillar(100, donor=True), "P3": _pillar(200)}
    assert _propagate_collinear_short_face_bands(middle) == 0
    ambiguous = {"P1": _pillar(0, donor=True), "P2": _pillar(100), "P3": _pillar(200, donor=True)}
    assert _propagate_collinear_short_face_bands(ambiguous) == 0


def test_open_row_endpoint_receives_only_inward_contact():
    report = {
        "P1": _pillar(0, donor=True),
        "P2": _pillar(100),
        "P3": _pillar(200),
    }

    assert _propagate_collinear_short_face_bands(report) == 2
    middle = report["P2"]["face_beams"]
    assert middle["C"]["passa_esq"] and middle["C"]["passa_dir"]
    endpoint = report["P3"]["face_beams"]
    assert endpoint["C"]["passa_esq"]["corner"] == "CA"
    assert endpoint["C"]["passa_dir"] is None
    assert [row["corner"] for row in endpoint["A"]["para"]] == ["AC"]
    assert endpoint["B"]["para"] == []


def test_reverse_open_row_endpoint_receives_only_inward_contact():
    report = {
        "P1": _pillar(0),
        "P2": _pillar(100),
        "P3": _pillar(200, donor=True),
    }

    assert _propagate_collinear_short_face_bands(report) == 2
    endpoint = report["P1"]["face_beams"]
    assert endpoint["C"]["passa_esq"] is None
    assert endpoint["C"]["passa_dir"]["corner"] == "CB"
    assert endpoint["A"]["para"] == []
    assert [row["corner"] for row in endpoint["B"]["para"]] == ["BC"]


def test_local_section_change_is_carried_to_following_pillars():
    report = {
        "P1": _pillar(0, donor=True),
        "P2": _pillar(100),
        "P3": _pillar(200),
    }
    # P2 recebe 19/55 pelo lado CA e sai 19/70 pelo lado CB.
    beams = [{
        "name": "VX",
        "geometry": {"dimension_texts": [
            {"text": "19/55", "pos": [90, 66]},
            {"text": "19/70", "pos": [125, 66]},
        ]},
    }]

    assert _propagate_collinear_short_face_bands(report, beams=beams) == 2
    p2 = report["P2"]["face_beams"]
    assert p2["C"]["passa_esq"]["dim"] == "19/55"
    assert p2["C"]["passa_dir"]["dim"] == "19/70"
    assert p2["A"]["para"][0]["dim"] == "19/55"
    assert p2["B"]["para"][0]["dim"] == "19/70"
    p3 = report["P3"]["face_beams"]
    assert p3["C"]["passa_esq"]["dim"] == "19/70"


def test_pillar_section_dimension_is_not_reused_as_beam_section():
    report = {
        "P1": _pillar(0, donor=True),
        "P2": _pillar(100),
        "P3": _pillar(200),
    }
    beams = [{
        "name": "VX",
        "geometry": {"dimension_texts": [
            {"text": "19/55", "pos": [90, 66]},
            {"text": "19/66", "pos": [125, 66]},
        ]},
    }]

    _propagate_collinear_short_face_bands(report, beams=beams)

    assert report["P2"]["face_beams"]["C"]["passa_dir"]["dim"] == "19/55"
    assert report["P3"]["face_beams"]["C"]["passa_esq"]["dim"] == "19/55"


def test_single_stray_dimension_does_not_reset_carried_section():
    report = {
        "P1": _pillar(0, donor=True),
        "P2": _pillar(100),
        "P3": _pillar(200),
        "P4": _pillar(300),
    }
    beams = [{
        "name": "VX",
        "geometry": {"dimension_texts": [
            {"text": "19/55", "pos": [90, 66]},
            {"text": "19/70", "pos": [125, 66]},
            # Em P3 existe somente uma cota solta: não prova nova transição.
            {"text": "14/40", "pos": [195, 66]},
        ]},
    }]

    _propagate_collinear_short_face_bands(report, beams=beams)

    assert report["P3"]["face_beams"]["C"]["passa_esq"]["dim"] == "19/70"
    assert report["P4"]["face_beams"]["C"]["passa_esq"]["dim"] == "19/70"
