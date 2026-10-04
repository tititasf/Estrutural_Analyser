import ezdxf
import pytest

from src.core.number_presentation import apply_dxf_number_presentation, display_number, display_text, display_level


@pytest.mark.parametrize('raw,expected', [(852, '852,00'), (852.195, '852,20'), (-.001, '0,00'), (None, '—')])
def test_levels_two_decimals(raw, expected):
    assert display_level(raw) == expected


def test_level_dxf_and_semantic_text():
    doc = ezdxf.new()
    label = doc.modelspace().add_text('852.195', dxfattribs={'layer': 'NIVEL'})
    apply_dxf_number_presentation(doc)
    assert label.dxf.text == '852,20'
    apply_dxf_number_presentation(doc)
    assert label.dxf.text == '852,20'
    assert display_text('Nível de chegada: 852; altura 18.717 cm') == 'Nível de chegada: 852,00; altura 18,7 cm'


@pytest.mark.parametrize('kind', ['plan', 'section'])
@pytest.mark.parametrize('value,expected', [('852.19', '852,19'), ('+3', '3,00'), ('-0.055', '-0,06')])
def test_generic_layer_altitude_symbols(kind, value, expected):
    doc = ezdxf.new()
    msp = doc.modelspace()
    if kind == 'plan':
        msp.add_circle((0, 0), 12.5)
        msp.add_line((-12.5, 0), (12.5, 0))
        msp.add_line((0, -12.5), (0, 12.5))
        msp.add_line((12.5, 0), (90, 0))
        pos = (20, 2)
    else:
        for a, b in [((-6, 0), (6, 0)), ((-6, 0), (0, -12)),
                     ((6, 0), (0, -12)), ((0, 0), (0, 6)), ((0, 6), (90, 6))]:
            msp.add_line(a, b)
        pos = (20, 9)
    label = msp.add_text(value, dxfattribs={'insert': pos, 'height': 10, 'layer': '3'})
    geometry = [(e.dxftype(), e.dxf.all_existing_dxf_attribs()) for e in msp if e is not label]
    apply_dxf_number_presentation(doc)
    assert label.dxf.text == expected
    apply_dxf_number_presentation(doc)
    assert label.dxf.text == expected
    assert geometry == [(e.dxftype(), e.dxf.all_existing_dxf_attribs()) for e in msp if e is not label]


def test_isolated_circle_and_dimension_arrow_are_not_altitudes():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_circle((0, 0), 12.5)
    for a, b in [((94, 0), (106, 0)), ((94, 0), (100, -12)), ((106, 0), (100, -12))]:
        msp.add_line(a, b)
    labels = [msp.add_text('18.717', dxfattribs={'insert': p, 'height': 10})
              for p in [(20, 2), (120, 2)]]
    apply_dxf_number_presentation(doc)
    assert all(e.dxf.text == '18,7' for e in labels)


@pytest.mark.parametrize('raw,expected', [
    ('Nível da viga: +852.195 m', 'Nível da viga: 852,20 m'),
    ('Nível do trecho: 852.1', 'Nível do trecho: 852,10'),
    ('Nível superior: -0.05 m', 'Nível superior: -0,05 m'),
    ('Nível 18.717 cm', 'Nível 18,7 cm'),
    ('Nível 18.717mm', 'Nível 18,7mm'),
    ('níveis (852.19 m)', 'níveis (852,19 m)'),
])
def test_semantic_level_units_and_idempotence(raw, expected):
    assert display_text(raw) == expected
    assert display_text(expected) == expected


@pytest.mark.parametrize('raw,expected', [(417.98, '418'), (417.88, '417,9'),
    (18.717, '18,7'), (244, '244'), (-.001, '0')])
def test_one_decimal(raw, expected):
    assert display_number(raw) == expected


def test_protected_text():
    assert display_text('V306 S1 2026-10-03 1.2.3 18.717cm') == 'V306 S1 2026-10-03 1.2.3 18,7cm'
    assert display_text(r'{\H2.5x;417.98}') == r'{\H2.5x;418}'


@pytest.mark.parametrize('class_name', ['FV', 'PIL', 'LV', 'LAJ'])
def test_cad_labels_preserve_geometry(class_name):
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    line = msp.add_line((0, 0), (417.98, 18.717))
    dim = msp.add_linear_dim(base=(0, -10), p1=(0, 0), p2=(417.98, 0))
    dim.render()
    label = msp.add_text('173.98', dxfattribs={'layer': class_name})
    title = msp.add_text(class_name + '306 S1')
    points = (tuple(line.dxf.start), tuple(line.dxf.end))
    measurement = dim.dimension.get_measurement()
    apply_dxf_number_presentation(doc)
    assert label.dxf.text == '174'
    assert title.dxf.text == class_name + '306 S1'
    assert (tuple(line.dxf.start), tuple(line.dxf.end)) == points
    assert dim.dimension.get_measurement() == measurement
    block = doc.blocks[dim.dimension.dxf.geometry]
    assert any('418' == e.text for e in block.query('MTEXT'))
    apply_dxf_number_presentation(doc)
    assert label.dxf.text == '174'
