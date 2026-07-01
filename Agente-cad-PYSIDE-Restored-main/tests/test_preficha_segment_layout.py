from src.ui.widgets.pre_validation_dialog import (
    _segment_details_text,
    _segment_identity_text,
)


def _segment():
    return {
        "beam_name": "V111",
        "segment_label": "2",
        "side": "A",
        "behavior": "Para",
        "length": 30.7,
        "height": "60",
        "width": "19",
        "tag": "Lado A",
        "details": {
            "support_start": {"name": "P25", "dimension": "19x60", "level": "852.19"},
            "support_end": {"name": "V309", "dimension": "19x55", "level": "—"},
            "beam_level": "852.19",
            "slabs": [{"name": "L301", "level": "852.19", "height": "12"}],
            "continuity": "Contínua",
            "adjustment": {"initial": "1", "final": "2", "total": "3"},
            "passing_pillars": ["P30"],
            "beam_openings": ["AV1"],
        },
    }


def test_lateral_identification_is_ordered_in_one_cell():
    text = _segment_identity_text(_segment())

    assert text.splitlines() == [
        "Nome: V111",
        "Segmento: 2",
        "Lado: A",
        "Comportamento: Para",
    ]


def test_lateral_details_include_dimensions_and_visual_sections():
    text = _segment_details_text(_segment())

    assert text.startswith("DIMENSÕES\nComprimento: 30.7\nAltura: 60")
    assert "────────────────────────\nAPOIOS" in text
    assert "────────────────────────\nLAJES" in text
    assert "────────────────────────\nCONTINUIDADE E AJUSTE" in text
    assert "────────────────────────\nINTERFERÊNCIAS" in text


def test_fundo_keeps_simple_identification_and_dimensions():
    segment = _segment()

    assert _segment_identity_text(segment, True).splitlines() == [
        "Nome: V111",
        "Segmento: 2",
    ]
    assert _segment_details_text(segment, True).splitlines() == [
        "DIMENSÕES",
        "Comprimento: 30.7",
        "Largura: 19",
    ]
