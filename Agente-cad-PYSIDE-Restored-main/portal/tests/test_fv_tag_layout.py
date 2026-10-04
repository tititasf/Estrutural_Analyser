import re
import xml.etree.ElementTree as ET
import pytest
from portal.app.fv_tag_layout import separate_chips

NS='{http://www.w3.org/2000/svg}'


def drawing(centres=(30,40,50), width=100):
    groups=[]
    for n,x in enumerate(centres,1):
        groups.append(f'<g><path d="M {x} 20 Q {x} 25 {x} 30"/>'
            f'<path d="M {x-1} 28 L {x} 30 L {x+1} 28 z"/></g>'
            f'<g><g><path data-fv-hl="tag" d="M {x-8} 5 L {x+8} 5 L {x+8} 15 L {x-8} 15 z"/></g>'
            f'<text x="{x}" y="12">S{n}</text></g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 100"><path id="CAD" d="M 1 1 L 99 99"/>'+''.join(groups)+'</svg>'


def test_separates_chips_preserving_cad_labels_and_arrow_targets():
    before=drawing(); after=separate_chips(before)
    root=ET.fromstring(after)
    assert root.find(NS+'path').get('d') == 'M 1 1 L 99 99'
    assert [t.text for t in root.iter(NS+'text')] == ['S1','S2','S3']
    centres=[]
    for group in list(root)[2::2]:
        text=group.find(NS+'text')
        dx=float(re.search(r'translate\(([^ ]+)',group.get('transform','translate(0 0)')).group(1))
        centres.append(float(text.get('x'))+dx)
    assert all(b-a >= 18 for a,b in zip(centres,centres[1:]))
    for x,group in zip((30,40,50),list(root)[1::2]):
        coords=re.findall(r'\d+(?:\.\d+)?',group[0].get('d'))
        assert [float(v) for v in coords[-2:]] == [x,30]
        assert group[1].get('d') == f'M {x-1} 28 L {x} 30 L {x+1} 28 z'
    assert separate_chips(after) == after


def test_no_collision_preserves_original_bytes():
    svg=drawing((20,45,70))
    assert separate_chips(svg) == svg


def test_insufficient_frame_cannot_claim_readable_layout():
    with pytest.raises(ValueError,match='insuficiente'):
        separate_chips(drawing(width=45))
