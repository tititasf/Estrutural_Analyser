import ezdxf
import pytest
from portal.app.qa_cad_gate import _beam_texts, _proved_pillar_section_handles
from src.core.pil_qa_identity_paths import collect_identity_scene, prove_identity_path


def scene(case='valid', rotated=False, mirror=False):
    doc=ezdxf.new();ms=doc.modelspace()
    def transform(x,y):
        if mirror:y=-y
        return (y,x) if rotated else (x,y)
    addline=lambda a,b:ms.add_line(transform(*a),transform(*b))
    def text(value,x,y):
        return ms.add_text(value,dxfattribs={'height':1,'rotation':90 if rotated else 0,'insert':transform(x,y)})
    for left,right in [(-30,40),(60,100),(120,180)]:
        if case=='named_t_both_gapped' and left==60:
            addline((left,0),(80,0));addline((90,0),(right,0))
        else:addline((left,0),(right,0))
        if not (case=='missing_wall' and left==60):
            offset=(.025 if case=='offset' else 1) if case in {'offset','width_change'} and left==60 else 0
            if case.startswith('named_t') and left==60:
                addline((left,19),(80,19));addline((90,19),(right,19))
                addline((80,19),(80,50))
                if case!='named_t_missing_wall':addline((90,19),(90,50))
                ms.add_text('V999',dxfattribs={'height':1,'rotation':0 if rotated else 90,'insert':transform(85,30)})
                if case=='named_t_competing':ms.add_text('V888',dxfattribs={'height':1,'rotation':0 if rotated else 90,'insert':transform(85,35)})
                if case=='named_t_closed_piece':
                    ms.add_lwpolyline([transform(80,0),transform(90,0),transform(90,19),transform(80,19)],close=True)
            else:addline((left,19+offset),(right,19+offset))
        if not((case=='missing_section' and left==60) or (case=='missing_local_section' and left==120)):
            text('20/55' if case in {'width_change','wrong_section_width'} and left==60 else '19/55',left+10,9)
        if case=='ambiguous_section' and left==60:text('19/50',left+15,9)
        if case.startswith('numeric_cells') and left==60:
            text('19/120',90,9)
            if case != 'numeric_cells_missing_cap':
                addline((80,0),(80,19 if case != 'numeric_cells_partial_cap' else 10))
    for left,right,name in [(40,60,'P1'),(100,120,'P2')]:
        pts=[(left,0),(right,0),(right,19),(left,19)]
        ms.add_lwpolyline([transform(*p) for p in pts],close=True)
        if not(case=='unnamed_support' and name=='P1'):
            # The numeric ownership callout can sit outside the closed pillar.
            px,py=transform(left-1 if case=='outside_support_name' else left+5,9)
            ms.add_text(name,dxfattribs={'height':1,'rotation':90 if rotated else 0,'insert':(px,py)})
            if not(case=='missing_support_section' and name=='P1'):
                ms.add_text('21/19' if case=='wrong_support_section' else '20/19',dxfattribs={'height':1,'rotation':90 if rotated else 0,'insert':(px,py-2)})
    text('V777',-20,9)
    if case=='competing_name':text('V888',75,9)
    if case=='same_named_span_competition':text('V888',-15,9)
    if case=='foreign_beyond_requested':
        text('V777',75,9)
        for entity in ms.query('TEXT'):
            if entity.dxf.text=='V777' and entity.dxf.insert==ezdxf.math.Vec3(*transform(-20,9)):
                entity.dxf.text='V888'
    if case=='section_change':
        for e in ms.query('TEXT'):
            if e.dxf.text=='19/55' and e.dxf.insert==ezdxf.math.Vec3(*transform(70,9)):
                e.dxf.text='19/50'
    raw=collect_identity_scene(doc,.05)
    axis='y' if rotated else 'x'
    right=[w for w in raw['walls'] if w['axis']==axis and w['lo']==120]
    handles=[h for w in right for h in w['handles']]
    return prove_identity_path(raw,axis=axis,positions=(0,-19 if mirror else 19),wall_handles=handles,anchor=120,
        requested_name='V777',tolerance_cm=.05)


@pytest.mark.parametrize('rotated',[False,True])
@pytest.mark.parametrize('case',['valid','section_change','outside_support_name','missing_wall','offset','width_change',
 'missing_section','missing_local_section','wrong_section_width','ambiguous_section',
 'unnamed_support','missing_support_section','wrong_support_section','competing_name',
 'same_named_span_competition','foreign_beyond_requested'])
def test_original_multisupport_path(case,rotated):
    proof=scene(case,rotated)
    if case in {'valid','section_change','outside_support_name','missing_section','foreign_beyond_requested'}:
        assert proof['status']=='measured'
        if case=='foreign_beyond_requested':
            assert len(proof['supports'])==1
            assert len(proof['spans'])==2
            return
        assert len(proof['supports'])==2
        assert len(proof['spans'])==3
        assert len(proof['beam_handles'])==1
        assert all(s['wall_handles'] for s in proof['spans'])
        assert proof['spans'][0]['section_handles']
        if case=='missing_section':
            assert proof['spans'][1]['section'] is None
            assert proof['spans'][1]['section_handles']==[]
        assert all(s['dimension_handles'] for s in proof['supports'])
    else:
        assert proof['status']=='uncertain'


@pytest.mark.parametrize('case',['text','mtext','wrong_dimensions','wrong_rotation','other_name','competing_contour','bulged_contour'])
def test_support_ownership_uses_original_label_footprint(case):
    """A long label has an extent; its insertion point need not touch the piece."""
    doc=ezdxf.new();ms=doc.modelspace()
    points=[(0,0),(50,0),(50,19),(0,19)]
    contour=ms.add_lwpolyline(points,close=True)
    if case=='bulged_contour':contour.set_points([(0,0,1),(50,0,0),(50,19,0),(0,19,0)],format='xyb')
    if case=='competing_contour':ms.add_lwpolyline([(x+10,y) for x,y in points],close=True)
    name='V48' if case=='other_name' else 'P48'
    if case=='mtext':
        ms.add_mtext(name,dxfattribs={'insert':(-56,-31),'char_height':15,'attachment_point':7})
    else:
        ms.add_text(name,dxfattribs={'insert':(-56,-31),'height':15,'rotation':90 if case=='wrong_rotation' else 0})
    section=ms.add_text('51/19' if case=='wrong_dimensions' else '50/19',dxfattribs={'insert':(-56,-46),'height':10})
    bindings=_proved_pillar_section_handles(doc,_beam_texts(doc),return_bindings=True)
    if case in {'text','mtext'}:
        assert len(bindings)==1
        assert bindings[0]['contour_handle']==contour.dxf.handle
        assert bindings[0]['dimension_handles']==[section.dxf.handle]
        assert bindings[0]['label_footprint'][2]>-56
    else:assert bindings==[]


@pytest.mark.parametrize('rotated',[False,True])
@pytest.mark.parametrize('case',['numeric_cells','numeric_cells_missing_cap','numeric_cells_partial_cap'])
def test_numeric_change_in_continuous_original_pair(case,rotated):
    proof=scene(case,rotated)
    if case != 'numeric_cells':
        assert proof['status']=='uncertain'
        return
    assert proof['status']=='measured'
    middle=proof['spans'][1]
    assert middle['section'] is None
    assert [c['section'] for c in middle['section_cells']['cells']]==['19/55','19/120']
    assert all(c['section_handles'] for c in middle['section_cells']['cells'])
    assert middle['section_cells']['handles']


@pytest.mark.parametrize('rotated',[False,True])
@pytest.mark.parametrize('mirror',[False,True])
@pytest.mark.parametrize('case',['named_t','named_t_missing_wall','named_t_competing','named_t_both_gapped','named_t_closed_piece'])
def test_original_t_opening_only_bridges_with_opposite_continuous_wall(case,rotated,mirror):
    proof=scene(case,rotated,mirror)
    assert proof['status']==('measured' if case=='named_t' else 'uncertain')
    if case=='named_t':
        joints=[s for s in proof['supports'] if s.get('kind')=='original_named_t_opening']
        assert len(joints)==1
        assert len(joints[0]['incoming_wall_handles'])==2
        assert joints[0]['continuous_wall_handles']

