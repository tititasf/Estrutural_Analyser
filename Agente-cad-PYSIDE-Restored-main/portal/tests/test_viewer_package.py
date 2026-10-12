import hashlib
import struct
from pathlib import Path

import pytest

from portal.app.viewer_package import UnsupportedSVG, build, ensure_cached


def svg(body, style="", group_attributes=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 200" data-cad-thin-strokes="1"><style id="cad-thin-strokes">svg[data-cad-thin-strokes="1"] :is(path,line,polyline,polygon){{vector-effect:non-scaling-stroke!important;stroke-width:0.55px!important;stroke-linecap:butt!important;stroke-linejoin:miter!important;}}</style>{style}'
            f'<g id="axes"><g id="LineCollection_1"{group_attributes}>{body}</g></g></svg>').encode()


def test_duplicates_order_and_precision_preserved():
    path='<path d="M 1.123456789012345 2 L 7 8" style="fill:none;stroke:red"/>'
    source=svg(path+'\n'+path+'\n<path d="M 0 1 L 4 2"/>')
    pack=build(source,'revision',1)
    assert pack.reconstruct()==source
    assert pack.manifest['path_count']==3
    assert pack.manifest['segment_count']==3
    assert struct.unpack('<4d',pack.segments[:32])==(1.123456789012345,2,7,8)
    assert pack.manifest['source_sha256']==hashlib.sha256(source).hexdigest()
    assert pack.fragments[0].strip()==pack.fragments[1].strip()


@pytest.mark.parametrize('attribute',[' transform="translate(10 20)"',' opacity=".5"',' style="filter:url(#blur)"'])
def test_dependent_groups_use_integral_fallback(attribute):
    with pytest.raises(UnsupportedSVG):
        build(svg('<path d="M 1 2 L 3 4"/>',group_attributes=attribute),'r')


def test_unknown_selectors_fail_closed():
    with pytest.raises(UnsupportedSVG):
        build(svg('<path d="M 1 2 L 3 4"/>',style='<style>g > path{stroke:red}</style>'),'r')


def test_curves_kept_whole_with_dependencies():
    source=svg('<path d="M 1 2 L 3 4"/>')
    source=source.replace(b'</svg>',b'<g id="LineCollection_2"><path d="M 1 2 Q 3 8 9 4"/></g></svg>')
    pack=build(source,'r')
    assert b'Q 3 8 9 4' in pack.shell
    assert pack.reconstruct()==source
    assert pack.manifest['shell_paths']==1


def test_atomic_cache_and_revision_race(tmp_path):
    source=svg('<path d="M 1 2 L 3 4"/>')
    folder=ensure_cached('a',tmp_path,lambda:source,lambda:'a')
    assert (folder/'manifest.json').exists()
    assert ensure_cached('a',tmp_path,lambda:pytest.fail('cache recomputed'),lambda:'a')==folder
    with pytest.raises(ValueError,match='source changed'):
        ensure_cached('b',tmp_path,lambda:source,lambda:'changed')
    assert not any(p.name.endswith('.regional') and p!=folder for p in tmp_path.iterdir())


def test_unbounded_stroke_uses_integral_fallback():
    source=svg('<path d="M 1 2 L 3 4"/>').replace(b'stroke-width:0.55px',b'stroke-width:50px')
    with pytest.raises(UnsupportedSVG,match='unbounded stroke'):
        build(source,'r')
