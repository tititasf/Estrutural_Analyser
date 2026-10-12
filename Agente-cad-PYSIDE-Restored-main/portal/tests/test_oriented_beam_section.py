import math
import pytest
from portal.app.preprocessamento.oriented_beam_section import measured_section


def drawing(angle=43):
    r=math.radians(angle)
    def p(x,y):return (x*math.cos(r)-y*math.sin(r),x*math.sin(r)+y*math.cos(r))
    polygon=[p(0,0),p(200,0),p(200,19),p(0,19),p(0,0)]
    texts=[dict(text='V1',position=p(10,25),rotation=angle,handle='name'),
           dict(text='19/55',position=p(100,25),rotation=angle,handle='section')]
    walls=[dict(a=p(0,0),b=p(200,0),handle='wall1'),dict(a=p(0,19),b=p(200,19),handle='wall2')]
    return polygon,texts,walls,p


@pytest.mark.parametrize('angle',[0,43,90,136.572])
def test_original_local_wall_pair_and_aligned_own_numeric_section(angle):
    poly,texts,walls,_=drawing(angle)
    proof=measured_section(poly,'V1',texts,walls)
    assert proof['height_cm']==55
    assert proof['width_cm']==pytest.approx(19)
    assert proof['source_entity_handles']==['name','section','wall1','wall2']


@pytest.mark.parametrize('failure',['name','rotation','outside','width','missing_wall','displaced_polygon','conflict'])
def test_unrelated_or_ambiguous_numeric_section_cannot_supply_depth(failure):
    poly,texts,walls,p=drawing()
    if failure=='name':texts[0]['text']='V2'
    if failure=='rotation':texts[1]['rotation']+=90
    if failure=='outside':texts[1]['position']=p(100,80)
    if failure=='width':texts[1]['text']='14/55'
    if failure=='missing_wall':walls.pop()
    if failure=='displaced_polygon':poly=[(x+10,y+10) for x,y in poly]
    if failure=='conflict':texts.append(dict(text='19/60',position=p(110,25),rotation=43,handle='other'))
    assert measured_section(poly,'V1',texts,walls) is None


def test_fund_depth_fallback_uses_original_dxf_and_preserves_segment(tmp_path):
    import ezdxf
    from copy import deepcopy
    from portal.app.preprocessamento.beam_cut_continuity import fund_section
    poly,texts,walls,_=drawing()
    doc=ezdxf.new();msp=doc.modelspace()
    for t in texts:msp.add_text(t['text'],dxfattribs={'insert':t['position'],'rotation':t['rotation']})
    for w in walls:msp.add_line(w['a'],w['b'])
    source=tmp_path/'original.dxf';doc.saveas(source)
    segment={'points':poly,'beam_name':'V1','segment_label':'1'};before=deepcopy(segment)
    assert fund_section(segment,{},[]) is None
    proof=fund_section(segment,{},[],source)
    assert proof['height_cm']==55
    assert len(proof['source_entity_handles'])==4
    assert segment==before
