import ezdxf
import pytest

from src.core.pil_qa_dimensioned_sections import collect_dimensioned_sections, sections_in_span


def drawing(case='valid', swap=False, mirror=False):
    doc=ezdxf.new(); ms=doc.modelspace()
    def xy(p):
        x,y=p
        if mirror:y=-y
        return (y,x) if swap else (x,y)
    def line(a,b):return ms.add_line(xy(a),xy(b))
    def poly(points):return ms.add_lwpolyline([xy(p) for p in points])
    def text(value,p,vertical=False):
        angle=90 if vertical else 0
        if swap:angle=90-angle
        return ms.add_text(value,dxfattribs={'insert':xy(p),'height':2,'rotation':angle})
    poly([(-30,60),(-30,48),(0,48),(0,27),(19,30),(19,48),(49,48),(49,60),(-30,60)])
    if case!='missing_stem':line((0,0),(0,48))
    line((19,0),(19,48))
    if case!='missing_cap':line((0,0),(19,0))
    line((-42,0),(-42,24));line((-42,36),(-42,60))
    if case!='missing_marker':
        poly([(-42,24),(-42,28),(-48,30),(-36,30),(-42,32),(-42,36)])
    line((-50,0),(-5,0));line((-50,60),(-29,60))
    line((-43,-1),(-41,1))
    if case!='missing_tick':line((-43,59),(-41,61))
    text('120',(-44,20),True)
    if case=='ambiguous_height':text('100',(-44,24),True)
    line((0,95),(19,95));line((-1,94),(1,96));line((18,94),(20,96))
    text('19',(10,97))
    # Original beam walls extend through the profile and the width dimension.
    poly([(0,-60),(0,140)])
    if case=='disconnected_witness':poly([(19,70),(19,140)])
    elif case!='missing_witness':poly([(19,-60),(19,140)])
    return doc


@pytest.mark.parametrize('swap',[False,True])
@pytest.mark.parametrize('mirror',[False,True])
def test_shortened_profile_and_broken_shaft_bind_numeric_height(swap,mirror):
    records=collect_dimensioned_sections(drawing(swap=swap,mirror=mirror))
    assert len(records)==1
    record=records[0]
    assert record['text']=='19/120'
    assert record['geometric_height_cm']==60
    assert record['axis']==('x' if swap else 'y')
    assert not sections_in_span(records,axis=record['axis'],positions=record['positions'],span=(100,200))


@pytest.mark.parametrize('case',['missing_stem','missing_cap','missing_marker','missing_tick',
    'ambiguous_height','missing_witness','disconnected_witness'])
def test_incomplete_original_witnesses_fail_closed(case):
    assert collect_dimensioned_sections(drawing(case))==[]


@pytest.mark.parametrize('case',['valid','missing_tick','missing_cap','ambiguous_height'])
def test_identity_path_uses_only_fully_bound_original_dimensioned_section(case):
    from src.core.pil_qa_identity_paths import collect_identity_scene, prove_identity_path
    doc=drawing(case)
    doc.modelspace().add_text('V700',dxfattribs={'insert':(9,80),'height':2,'rotation':90})
    raw=collect_identity_scene(doc,.05)
    walls=[w for w in raw['walls'] if w['axis']=='y' and
        any(abs(w['pos']-p)<.05 for p in [0,19]) and w['lo']<0 and w['hi']>100]
    proof=prove_identity_path(raw,axis='y',positions=(0,19),
        wall_handles=[h for w in walls for h in w['handles']],anchor=0,
        requested_name='V700',tolerance_cm=.05)
    assert proof['status']==('measured' if case=='valid' else 'uncertain')
    if case=='valid':
        assert proof['spans'][0]['section']=='19/120'
        assert len(proof['spans'][0]['section_handles'])>=15
