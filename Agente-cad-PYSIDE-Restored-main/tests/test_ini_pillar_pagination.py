import ezdxf

from src.core.ini_pillar_pagination import identity


def grade(height=300, number='1'):
    doc = ezdxf.new('R2018')
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (30, 0), (30, height), (0, height)], close=True)
    m.add_text(number, dxfattribs={'insert': (15, 100), 'height': 5})
    return doc


def test_group_identity_ignores_position_but_preserves_fabrication_and_number():
    original = grade()
    translated = grade()
    for entity in translated.modelspace():
        entity.translate(900, -420, 0)
    assert identity(original) == identity(translated)
    assert identity(original) != identity(grade(height=299))
    assert identity(original) != identity(grade(number='2'))


def test_group_identity_preserves_mline_thickness_and_fill():
    a = grade()
    a.modelspace().add_mline([(0, 0), (0, 300)], dxfattribs={'scale_factor': 7})
    b = grade()
    b.modelspace().add_mline([(0, 0), (0, 300)], dxfattribs={'scale_factor': 3.5})
    assert identity(a) != identity(b)
