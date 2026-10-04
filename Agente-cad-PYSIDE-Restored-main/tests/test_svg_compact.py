import gzip
import xml.etree.ElementTree as ET
from portal.app.svg_compact import compact_svg, SVG
from portal.app.drawing_frame import compact_preview

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
