import pytest
from src.core.lv_beam_scene import _EdgeIndex, _find_band

@pytest.mark.parametrize('horizontal',[True,False])
@pytest.mark.parametrize('offset',[0,12345])
def test_label_selects_its_span_instead_of_nearer_distant_crossing(horizontal,offset):
    # Label outside its two faces; a crossing has a closer transverse face
    # but its two walls exist only 300 cm farther along the axis.
    segs=[(0,0,250,0),(0,14,250,14),(300,14,400,14),(300,28,400,28)]
    label=(10,31)
    if not horizontal:
        segs=[(y,x,b,a) for x,y,a,b in segs];label=label[::-1]
    segs=[tuple(v+offset for v in s) for s in segs]
    assert _find_band({'pos':[v+offset for v in label]},horizontal,_EdgeIndex(segs),14)==(offset,offset+14)
