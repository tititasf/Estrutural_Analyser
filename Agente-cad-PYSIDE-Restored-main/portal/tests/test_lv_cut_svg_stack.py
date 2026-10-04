from portal.app.lv_ficha import _stack_cut_svgs
from xml.etree import ElementTree as ET


def test_aggregate_svg_has_html_compatible_root():
    drawing = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 480"><rect id="beam" width="19" height="55"/></svg>'
    stacked = _stack_cut_svgs([drawing, drawing])
    assert stacked.startswith('<svg ')
    assert '<ns0:svg' not in stacked
    root = ET.fromstring(stacked)
    ids = [node.get('id') for node in root.iter() if node.get('id')]
    assert len(ids) == len(set(ids)) == 2
