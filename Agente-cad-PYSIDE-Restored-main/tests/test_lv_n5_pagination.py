from collections import Counter
import pytest
from ezdxf import bbox
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from src.core.lv_nova_design import draw_ab, panel_spans
from src.core.lv_n5_pagination import paginate_ab


@pytest.mark.parametrize('assembly', ['gradeadas','sarrafeadas'])
def test_native_pagination_preserves_geometry_and_physical_panel_layout(assembly):
    contract = dict(beam='V1',side='B',assembly_variant=assembly,total_cm=75,body_cm=60,
        segments=[dict(segment_index=1,length=2600,
                       beam_openings=[(950,1020,30)],column_openings=[(1930,1980)]),
                  dict(segment_index=2,length=660,beam_openings=[(0,40,30)])])
    doc = draw_ab(contract)
    before = len(doc.modelspace())
    pieces = paginate_ab(doc,contract,1333)
    assert len(pieces)>1 and len(doc.modelspace())==before
    assert pieces[0][1][0]==0 and pieces[-1][1][1]==3260
    assert all(a[1][1]==b[1][0] for a,b in zip(pieces,pieces[1:]))
    boundaries = {b for _,b in panel_spans(2600)} | {2600+b for _,b in panel_spans(660)}
    assert all(window[1] in boundaries for _,window in pieces)
    def lines(document,layer):
        return unary_union([LineString([e.dxf.start.xy,e.dxf.end.xy])
                            for e in document.modelspace().query('LINE') if e.dxf.layer==layer])
    for layer in ('Painéis','SARR_2.2x7','SARR_3.5x7'):
        original=lines(doc,layer)
        actual=unary_union([lines(part,layer) for part,_ in pieces])
        assert original.symmetric_difference(actual).length < 1e-5
    def hatches(document):
        return unary_union([Polygon([(v[0],v[1]) for v in path.vertices])
                            for e in document.modelspace().query('HATCH') for path in e.paths])
    assert hatches(doc).symmetric_difference(unary_union([hatches(p) for p,_ in pieces])).area < 1e-5
    labels=Counter(e.dxf.text for e in doc.modelspace().query('TEXT') if 'pontalete' in e.dxf.text)
    assert labels == Counter(e.dxf.text for p,_ in pieces for e in p.modelspace().query('TEXT') if 'pontalete' in e.dxf.text)
    for part,_ in pieces:
        assert not part.audit().has_errors
        assert bbox.extents(part.modelspace()).size.x <= 1333


def test_small_ab_is_not_rebuilt():
    c=dict(beam='V1',assembly_variant='gradeadas',total_cm=75,body_cm=60,
           segments=[dict(length=640)])
    d=draw_ab(c)
    assert paginate_ab(d,c,1333)==[(d,None)]


def test_remaining_sheet_space_accepts_total_with_unequal_witness_heights():
    c=dict(beam='V301',side='A',assembly_variant='gradeadas',total_cm=59,body_cm=45,
           segments=[dict(length=317.98,total_cm=59,body_cm=45,y_offset_cm=0),
                     dict(length=100.02,total_cm=124,body_cm=110,y_offset_cm=-65)])
    d=draw_ab(c)
    pieces=paginate_ab(d,c,1333,first_width=330)
    assert len(pieces)==2
    assert pieces[0][1]==[0,244]
    assert pieces[-1][1][1]==418
    assert bbox.extents(pieces[0][0].modelspace()).size.x <= 330
    totals=[e for e in pieces[-1][0].modelspace().query('DIMENSION')
            if abs(e.dxf.defpoint.y+135)<1e-5]
    assert len(totals)==1
    assert totals[0].dxf.defpoint2.y==0
    assert totals[0].dxf.defpoint3.y==-65
