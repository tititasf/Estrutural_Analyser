import xml.etree.ElementTree as ET

from portal.app.pillar_highlight_tags import project_s1_tags


class Transform:
    def dxf_para_px(self, x, y):
        return x * 2, y * 2


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<g id="axes_1"><g id="cad"><defs><path id="glyph" d="M 0 0 L 1 1"/></defs></g>
<g><path style="fill: #ff1744; opacity: 0.12" d="M 0 0 L 10 0 L 10 20 L 0 20 Z"/></g>
<g id="tag"><use xlink:href="#glyph"/></g>
<g><!-- SA motor --><text>banner</text></g></g></svg>'''


def test_keeps_only_tags_with_calibration_and_shared_glyphs():
    layer = project_s1_tags(SVG, [[0, 0], [10, 0], [10, 20], [0, 20]], Transform())
    root = ET.fromstring(layer)
    assert root.get('class') == 'pillar-interpretive-tags'
    assert 'matrix(2.0 0 0 2.0 0.0 0.0)' in layer
    assert 'banner' not in layer
    ids = {node.get('id') for node in root.iter() if node.get('id')}
    assert not any(value.endswith('-cad') for value in ids)
    use = root.find('.//{http://www.w3.org/2000/svg}use')
    assert use.get('{http://www.w3.org/1999/xlink}href')[1:] in ids


def test_missing_or_inconsistent_calibration_is_not_displayed():
    assert project_s1_tags('<svg/>', [[0, 0]], Transform()) is None
    assert project_s1_tags(SVG, [[0, 0], [20, 20]], Transform()) is None
