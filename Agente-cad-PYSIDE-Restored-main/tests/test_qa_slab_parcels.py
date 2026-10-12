import copy
import ezdxf
import pytest
from portal.app.qa_cad_gate import measure_slabs
from portal.app.qa_cad_gate_run import resumo


@pytest.mark.parametrize('fault',['absent','wrong'])
def test_all_homonymous_parcels_measured_without_last_wins(tmp_path, fault):
    doc = ezdxf.new()
    ms = doc.modelspace()
    rows = []
    for i,x in enumerate((0,100)):
        label = ms.add_text('L9',dxfattribs={'insert':(x+5,5),'height':1})
        ms.add_text('h=12',dxfattribs={'insert':(x+10,5),'height':1})
        if i or fault == 'wrong':
            ms.add_text('855.25',dxfattribs={'insert':(x+15,5),'height':1})
        rows.append(dict(name='L9',height='12',nivel='855.22' if not i and fault=='wrong' else '855.25',
            source_label_handle=label.dxf.handle,
            points=[(x,0),(x+30,0),(x+30,20),(x,20),(x,0)]))
    source = tmp_path / 'original.dxf'
    doc.saveas(source)
    snapshot = {'collections':{'lajes':rows}}
    unchanged = copy.deepcopy(snapshot)
    report = measure_slabs(source,snapshot)
    reverse = measure_slabs(source,{'collections':{'lajes':rows[::-1]}})
    assert snapshot == unchanged
    assert len(report['parcels']) == 2
    assert report['items']['L9'] == reverse['items']['L9']
    assert report['items']['L9']['status'] == ('incerto' if fault=='absent' else 'diverge')
    assert resumo(report)['status'] != 'confere'
    assert len({r['source_label_handle'] for r in report['parcels']}) == 2
    assert all(r['source_handles'] for r in report['parcels'])
