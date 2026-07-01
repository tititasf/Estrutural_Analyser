from src.ui.widgets.pre_validation_dialog import (
    _pillar_abcd_text,
    _pillar_abcdefgh_text,
    _pillar_identity_text,
)


def test_pillar_sides_are_ordered_in_one_cell_with_separators():
    text = _pillar_abcd_text({
        "A": "nulo",
        "B": "Laje: L301\nAltura: 12\nNivel: 852.12",
        "C": "Viga: V309\nLargura: 19\nAltura: 60\nNivel: 852.12",
        "D": "nulo",
    })

    sections = text.split("\n────────────────────────\n")
    assert sections == [
        "LADO A\nnulo",
        "LADO B\nLaje: L301\nAltura: 12\nNivel: 852.12",
        "LADO C\nViga: V309\nLargura: 19\nAltura: 60\nNivel: 852.12",
        "LADO D\nnulo",
    ]


def test_missing_side_value_is_rendered_as_nulo():
    text = _pillar_abcd_text({"A": "Laje: L301"})

    assert "LADO A\nLaje: L301" in text
    assert "LADO B\nnulo" in text
    assert "LADO C\nnulo" in text
    assert text.endswith("LADO D\nnulo")


def test_pillar_identity_groups_name_classification_shape_and_confidence():
    text = _pillar_identity_text("P1", "MORRE  ·  sólido", "Retangular", 95)

    assert text.split("\n────────────────────────\n") == [
        "NOME\nP1",
        "CLASSIFICAÇÃO SA\nMORRE  ·  sólido",
        "FORMATO\nRetangular",
        "CONFIANÇA\n95%",
    ]


def test_special_pillar_groups_sides_a_through_h_in_one_cell():
    text = _pillar_abcdefgh_text({
        "A": "Laje: L325",
        "B": "Laje: L318",
        "C": "nulo",
        "D": "nulo",
        "E": "—",
        "F": "—",
        "G": "—",
        "H": "—",
    })

    sections = text.split("\n────────────────────────\n")
    assert [section.splitlines()[0] for section in sections] == [
        "LADO A", "LADO B", "LADO C", "LADO D",
        "LADO E", "LADO F", "LADO G", "LADO H",
    ]
    assert sections[-1] == "LADO H\n—"
