import gzip
import xml.etree.ElementTree as ET
from portal.app.svg_compact import compact_svg, SVG
from portal.app.drawing_frame import compact_preview
from portal.app.svg_compact import compact_svg_structure
from portal.app.svg_compact import compact_svg_serialization, _PATH_TOKEN

def test_lexical_compaction_keeps_numeric_lexemes_groups_and_text():
    source = f'''<svg xmlns="{SVG}"><g id="tag" transform="translate(1 2)">
      <!--face C--><path d="M 1.000000 -2e-3\n L 4.50,6 z" style="fill: none; stroke: #ff0000; opacity: .5"/>
      <text> face C <tspan>  537,86  </tspan> end </text>
    </g></svg>'''.replace('<!--face C-->', ' ' * 100 + '<!--face C-->').encode()
    result = compact_svg_serialization(source)
    a, b = ET.fromstring(source), ET.fromstring(result)
    assert _PATH_TOKEN.findall(a.find(f'.//{{{SVG}}}path').get('d')) == _PATH_TOKEN.findall(b.find(f'.//{{{SVG}}}path').get('d'))
    text_a, text_b = a.find(f'.//{{{SVG}}}text'), b.find(f'.//{{{SVG}}}text')
    text_a.tail = text_b.tail = None
    assert ET.tostring(text_a) == ET.tostring(text_b)
    assert b.find(f'.//{{{SVG}}}g').attrib == a.find(f'.//{{{SVG}}}g').attrib
    assert b'<!--face C-->' in result
    assert b'opacity:.5' in result

def test_lexical_compaction_preserves_unknown_css():
    source = f'<svg xmlns="{SVG}"><style>path[style] {{stroke:red}}</style><path d="M 0 0" style="fill: none"/></svg>'.encode()
    assert compact_svg_serialization(source) == source

def test_lexical_compaction_keeps_complex_style_and_invalid_path():
    source = f'<svg xmlns="{SVG}"><path d="M 0 0 INVALID" style="fill: url(#gradient); stroke: rgb(1, 2, 3)"/></svg>'.encode()
    result = ET.fromstring(compact_svg_serialization(source))[0]
    assert result.get('d') == 'M 0 0 INVALID'
    assert result.get('style') == 'fill: url(#gradient); stroke: rgb(1, 2, 3)'

def test_structure_keeps_paint_operations_comments_and_referenced_groups():
    source = f'''<svg xmlns="{SVG}"><defs><g id="symbol"><path d="M0 0 L1 1"/></g></defs>
    <g id="unused"><!--face C--><path d="M0 0 L1 1" style="stroke:red;opacity:.5"/>
    <path d="M0 0 L1 1" style="stroke:red;opacity:.5"/></g>
    <g id="linked"><path d="M2 2 L3 3"/></g><use href="#linked"/>
    <g transform="translate(1 2)"><path d="M4 4 L5 5"/></g></svg>'''.encode()
    result = compact_svg_structure(source)
    before, after = ET.fromstring(source), ET.fromstring(result)
    paths = lambda root: [dict(n.attrib) for n in root.iter(f'{{{SVG}}}path')]
    assert paths(before) == paths(after)
    assert b'<!--face C-->' in result
    assert after.find(f'.//{{{SVG}}}g[@id="unused"]') is None
    assert after.find(f'.//{{{SVG}}}g[@id="linked"]') is not None
    assert after.find(f'.//{{{SVG}}}g[@id="symbol"]') is not None
    assert after.find(f'.//{{{SVG}}}g[@transform="translate(1 2)"]') is not None

def test_structure_leaves_group_dependent_css_untouched():
    source = f'<svg xmlns="{SVG}"><style>g &gt; path {{stroke:red}}</style><g id="x"><path d="M0 0 L1 1"/></g></svg>'.encode()
    assert compact_svg_structure(source) == source

def test_line_batches_preserve_every_subpath_and_clip():
    lines=''.join(f'<path d="M {i} 0 L {i} 10" clip-path="url(#clip)" style="fill: none; stroke: red"/>' for i in range(300))
    root=ET.fromstring(compact_svg(f'<svg xmlns="{SVG}"><g id="lines">{lines}</g></svg>'.encode()))
    paths=list(root.iter(f'{{{SVG}}}path'))
    assert len(paths)==3
    assert sum(p.get('d').count('M ') for p in paths)==300
    assert all(p.get('clip-path')=='url(#clip)' for p in paths)

def test_markers_keep_curves_positions_and_styles():
    source=f'<svg xmlns="{SVG}" xmlns:xlink="http://www.w3.org/1999/xlink"><defs><path id="dot" d="M 0 1 C 1 1 1 0 0 0 z" style="stroke: red"/></defs><g><use xlink:href="#dot" x="10" y="20" style="fill: red"/><use xlink:href="#dot" x="30" y="40" style="fill: red"/></g></svg>'.encode()
    root=ET.fromstring(compact_svg(source))
    assert not list(root.iter(f'{{{SVG}}}use'))
    shape=list(root.iter(f'{{{SVG}}}path'))[-1]
    assert 'M10.000000000 21.000000000 c1 0 1 -1 0 -1 z' in shape.get('d')
    assert 'M30.000000000 41.000000000' in shape.get('d')
    assert shape.get('style')=='stroke: red;fill: red'

def test_unknown_transforms_and_alpha_are_preserved():
    source=f'<svg xmlns="{SVG}"><g transform="scale(2)"><path d="M0 0 L1 1" style="fill: none; stroke: red; opacity: .5"/><path d="M0 0 L1 1" style="fill: none; stroke: red; opacity: .5"/><use href="#missing" transform="rotate(4)"/></g></svg>'.encode()
    root=ET.fromstring(compact_svg(source))
    assert root[0].get('transform')=='scale(2)'
    assert len(root[0])==3

def test_cache_preserves_original_and_rebuilds_when_source_changes(tmp_path):
    p=tmp_path/'test.svg';source=f'<svg xmlns="{SVG}"><path d="M0 0 L1 1" style="fill: none"/></svg>'.encode();p.write_bytes(source)
    cache=compact_preview(p);gz=compact_preview(p,True)
    assert p.read_bytes()==source
    assert gzip.decompress(gz.read_bytes())==cache.read_bytes()
    before=cache.stat().st_mtime_ns
    assert compact_preview(p).stat().st_mtime_ns==before
    p.write_bytes(source.replace(b'L1 1',b'L2 2'))
    assert b'L2 2' in compact_preview(p).read_bytes()
