from src.core.pillar_abcd_tables import apply_axial_bilateral_short_faces


def _row(name, corner, role="passa"):
    return {
        "familia": "viga",
        "nome": name,
        "dim": "19/120",
        "nivel": "852.19cm",
        "canto": corner,
        "papel": role,
        "raw": "",
        "dist_esq": "—",
        "dist_dir": "—",
    }


def test_same_beam_on_both_short_faces_becomes_axial_interior():
    tables = {
        face: {"lajes": [], "passa": [], "chega": [], "interior": []}
        for face in "ABCD"
    }
    tables["C"]["passa"] = [_row("VX", "CA")]
    tables["D"]["passa"] = [_row("VX", "DA")]
    tables["A"]["chega"] = [_row("VX", "AC", "chega")]

    notes = apply_axial_bilateral_short_faces(tables)

    assert notes
    assert {(r["nome"], r["canto"]) for r in tables["C"]["interior"]} == {("VX", "CC")}
    assert {(r["nome"], r["canto"]) for r in tables["D"]["interior"]} == {("VX", "DD")}
    assert {(r["nome"], r["canto"]) for r in tables["A"]["passa"]} == {
        ("VX", "AC"), ("VX", "AD")
    }
    assert {(r["nome"], r["canto"]) for r in tables["B"]["passa"]} == {
        ("VX", "BC"), ("VX", "BD")
    }
    assert tables["A"]["chega"] == []


def test_single_short_face_does_not_expand_axial_beam():
    tables = {
        face: {"lajes": [], "passa": [], "chega": [], "interior": []}
        for face in "ABCD"
    }
    tables["D"]["interior"] = [_row("VX", "DD", "interior")]
    assert apply_axial_bilateral_short_faces(tables) == []
    assert tables["A"]["passa"] == []
