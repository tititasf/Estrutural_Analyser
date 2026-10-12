import ezdxf
import pytest

from src.core.pil_qa_dimensioned_sections import collect_dimensioned_sections, sections_in_span


def original(case='valid', rotated=False):
    doc=ezdxf.new(); ms=doc.modelspace()
    xy=lambda x,y:(y,x) if rotated else (x,y)
    # A dimensioned continuous beam stem and one slab wing. Collinear
    # vertices and a repeated end are common in the immutable CAD.
    height=60 if case=='numeric_priority' else 55
    glyph=ms.add_lwpolyline([xy(*p) for p in
        [(0,height),(0,height-12),(0,0),(19,0),(19,height-12),
         (49,height-12),(49,height),(0,height)]])
    if case=='open':glyph.set_points([xy(*p) for p in [(0,55),(0,0),(19,0),(19,43),(49,43),(49,55)]])
    if case=='curve':
        points=list(glyph.get_points('xyb'));points[1]=(points[1][0],points[1][1],1);glyph.set_points(points,format='xyb')
    if case=='nonplanar':glyph.dxf.elevation=2
    def line(a,b):return ms.add_line(xy(*a),xy(*b))
    def text(value,p,rotation):
        return ms.add_text(value,dxfattribs={'insert':xy(*p),'height':2,'rotation':90-rotation if rotated else rotation})
    # Height shaft, witnesses, centred diagonal ticks and aligned text.
    line((-10,0),(-10,height))
    line((-15,0),(-5,0));line((-15,height),(-5,height))
    line((-11,-1),(-9,1))
    if case!='missing_tick':line((-11,height-1),(-9,height+1))
    text('55',(-12,height/2),90)
    if case=='ambiguous_height':text('50',(-11,height/2+3),90)
    line((0,height+10),(19,height+10))
    line((0,height+5),(0,height+15));line((19,height+5),(19,height+15))
    line((-1,height+9),(1,height+11));line((18,height+9),(20,height+11))
    if case=='duplicate_tick':line((18,height+9),(20,height+11))
    text('20' if case=='wrong_width' else '19',(8,height+12),0)
    return doc


@pytest.mark.parametrize('rotated',[False,True])
@pytest.mark.parametrize('case',['valid','duplicate_tick','numeric_priority','missing_tick',
    'ambiguous_height','wrong_width','open','curve','nonplanar'])
def test_only_independently_dimensioned_continuous_original_sections(case,rotated):
    records=collect_dimensioned_sections(original(case,rotated))
    if case not in {'valid','duplicate_tick','numeric_priority'}:
        assert records==[]
        return
    assert len(records)==1
    assert records[0]['text']=='19/55'
    assert records[0]['axis']==('x' if rotated else 'y')
    assert records[0]['geometric_height_cm']==(60 if case=='numeric_priority' else 55)
    assert len(records[0]['evidence_handles'])>=13


@pytest.mark.parametrize('rotated',[False,True])
def test_no_transfer_from_foreign_wall_band_or_past_the_first_support(rotated):
    records=collect_dimensioned_sections(original(rotated=rotated))
    axis='x' if rotated else 'y'
    assert sections_in_span(records,axis=axis,positions=(0,19),span=(-20,100))
    assert not sections_in_span(records,axis=axis,positions=(1,20),span=(-20,100))
    assert not sections_in_span(records,axis=axis,positions=(0,19),span=(-20,40))
    assert not sections_in_span(records,axis=axis,positions=(0,19),span=(56,100))
    assert not sections_in_span(records,axis='y' if rotated else 'x',positions=(0,19),span=(-20,100))
