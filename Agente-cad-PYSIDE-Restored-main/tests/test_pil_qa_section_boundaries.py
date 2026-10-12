from copy import deepcopy
import pytest
from src.core.pil_qa_section_boundaries import own_section_span,proved_section_cells


def label(text, x, y=20, rotation=0):
    return dict(text=text, x=x, y=y, rotation=rotation, margin=4,handle=f'{text}@{x}')


def sample():
    return dict(walls=[dict(axis='y', pos=70, lo=10, hi=29, handle='cap')],
                labels=[label('19/55', 40), label('19/120', 90)],
                axis='x', positions=(10, 29), span=(20, 120), anchor=20,
                closed_handles=set(), tolerance_cm=.05)


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('vertical', [False, True])
def test_original_cap_binds_only_own_adjacent_section(reverse, vertical):
    data = sample()
    if reverse:
        data['anchor'] = 120
    if vertical:
        data['axis'] = 'y'
        data['walls'][0]['axis'] = 'x'
        for t in data['labels']:
            t['x'], t['y'] = t['y'], t['x']
            t['rotation'] = 90
    before = deepcopy(data)
    result = own_section_span(**data)
    assert result['span'] == ((70, 120) if reverse else (20, 70))
    assert result['handles'] == ['cap']
    assert data == before


@pytest.mark.parametrize('failure', ['missing_cap', 'partial', 'extended', 'closed',
                                   'unlabelled', 'same_section', 'conflicting',
                                   'foreign_width', 'wrong_rotation', 'non_boundary_anchor'])
def test_unproved_change_preserves_uncertainty(failure):
    data = sample()
    if failure == 'missing_cap': data['walls'] = []
    if failure == 'partial': data['walls'][0]['lo'] = 15
    if failure == 'extended': data['walls'][0]['hi'] = 50
    if failure == 'closed': data['closed_handles'] = {'cap'}
    if failure == 'unlabelled': data['labels'].pop()
    if failure == 'same_section': data['labels'][1]['text'] = '19/55'
    if failure == 'conflicting': data['labels'].append(label('19/80', 50))
    if failure == 'foreign_width': data['labels'][1]['text'] = '14/120'
    if failure == 'wrong_rotation': data['labels'][1]['rotation'] = 90
    if failure == 'non_boundary_anchor': data['anchor'] = 50
    assert own_section_span(**data) is None


@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('conflict',[False,True])
def test_unlabelled_full_caps_do_not_erase_bilateral_numeric_change(reverse,conflict):
    data=sample()
    data['walls'] += [dict(axis='y',pos=x,lo=10,hi=29,handle=f'other{x}') for x in (25,30)]
    if reverse:data['anchor']=120
    if conflict:data['labels'].append(label('19/80',22))
    before=deepcopy(data)
    result=own_section_span(**data)
    if conflict and not reverse:
        assert result is None
    else:
        assert result['span']==((70,120) if reverse else (20,70))
        assert result['handles']==['cap']
    assert data==before


@pytest.mark.parametrize('conflict',[False,True])
def test_numeric_graph_cells_ignore_only_unproved_extra_caps(conflict):
    data=sample();data.pop('anchor')
    data['walls'] += [dict(axis='y',pos=x,lo=10,hi=29,handle=f'other{x}') for x in (25,30)]
    if conflict:data['labels'].append(label('19/80',22))
    before=deepcopy(data);result=proved_section_cells(**data)
    if conflict:assert result is None
    else:
        assert [c['span'] for c in result['cells']]==[(20,70),(70,120)]
        assert [c['section'] for c in result['cells']]==['19/55','19/120']
        assert result['handles']==['cap']
    assert data==before


def test_original_dxf_reader_respects_explicit_change_without_using_sa_section(tmp_path):
    import ezdxf
    from portal.app.qa_cad_gate import measure
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (20, 0), (20, 80), (0, 80)]
    ms.add_lwpolyline(points, close=True)
    ms.add_lwpolyline([(20, 10), (120, 10)])
    ms.add_lwpolyline([(20, 29), (120, 29)])
    cap = ms.add_lwpolyline([(70, 10), (70, 29)])
    for text, x in [('V304', 30), ('19/55', 40), ('19/120', 90)]:
        ms.add_text(text, dxfattribs={'insert': (x, 20), 'height': 2})
    path = tmp_path/'source.dxf'
    doc.saveas(path)
    row = {'nome': 'V304', 'dim': '19/55', 'dist_esq': 10, 'dist_dir': 51}
    snapshot = {'collections': {'pilares': [{'points': points, 'interpretacao_abcd': {
        'faces': {'B': {'chega': [row]}}}}]}}
    contact = measure(path, snapshot)['contacts'][0]
    assert contact['status'] == 'measured'
    assert contact['section'] == '19/55'
    assert not contact['errors']
    assert contact['section_boundary']['handles'] == [cap.dxf.handle]
    row['dim'] = '19/120'
    wrong = measure(path, snapshot)['contacts'][0]
    assert wrong['section'] == '19/55'
    assert wrong['errors']
    # Remove the actual cap: both numeric calls again remain ambiguous.
    ms.delete_entity(cap)
    unbounded = tmp_path/'unbounded.dxf'
    doc.saveas(unbounded)
    assert measure(unbounded, snapshot)['contacts'][0]['status'] == 'uncertain'
