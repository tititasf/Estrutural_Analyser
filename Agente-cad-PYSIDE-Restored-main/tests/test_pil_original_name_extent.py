import ezdxf
import pytest
from src.core.pil_qa_identity_paths import collect_identity_scene,original_name_in_span

@pytest.mark.parametrize('axis',['x','y'])
@pytest.mark.parametrize('case',['mostly_inside','mostly_outside','section','long_mtext','perpendicular'])
def test_original_printed_name_at_face(axis,case):
    doc=ezdxf.new();ms=doc.modelspace()
    value='19/120' if case=='section' else 'V318'
    rotation=90 if axis=='y' else 0
    if case=='perpendicular':rotation+=90
    insert=(-1,5) if axis=='x' else (5,-1)
    attributes={'insert':insert,'rotation':rotation}
    if case=='long_mtext':ms.add_mtext('V318 NOTE',dxfattribs={**attributes,'char_height':5})
    else:ms.add_text(value,dxfattribs={**attributes,'height':5})
    scene=collect_identity_scene(doc,.05)
    label=next(t for t in scene['labels'] if t['text']==value)
    span=(0,1) if case=='mostly_outside' else (0,100)
    proved=original_name_in_span(label,axis,span,(0,19),.05)
    assert proved==(case=='mostly_inside')

def test_extent_does_not_skip_competing_original_name():
    from src.core.pil_qa_identity_paths import prove_identity_path
    doc=ezdxf.new();ms=doc.modelspace()
    for y in [0,19]:ms.add_line((0,y),(100,y))
    ms.add_text('19/55',dxfattribs={'insert':(20,5),'height':2})
    ms.add_text('V318',dxfattribs={'insert':(-1,5),'height':5})
    ms.add_text('V319',dxfattribs={'insert':(50,5),'height':5})
    scene=collect_identity_scene(doc,.05)
    handles=[h for w in scene['walls'] for h in w['handles']]
    result=prove_identity_path(scene,axis='x',positions=(0,19),wall_handles=handles,anchor=100,
        requested_name='V318',tolerance_cm=.05)
    assert result['status']=='uncertain'
    assert result['names']==['V318','V319']
