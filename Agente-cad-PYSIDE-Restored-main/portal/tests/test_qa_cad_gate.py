import copy

import ezdxf
import pytest

from portal.app import qa_cad_gate as gate


@pytest.fixture
def contact(tmp_path):
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0,0), (20,0), (20,66), (0,66)], close=True)
    ms.add_line((20, 52), (100, 52))
    ms.add_line((20, 66), (100, 66))
    ms.add_text('V1', dxfattribs={'insert': (30, 70), 'height': 3})
    ms.add_text('14/55', dxfattribs={'insert': (80, 70), 'height': 3})
    path = tmp_path/'source.dxf'
    doc.saveas(path)
    row = {'points': [[0, 0], [20, 0], [20, 66], [0, 66]],
           'interpretacao_abcd': {'faces': {'B': {'chega': [
               {'nome': 'V1', 'dim': '14/55', 'dist_esq': '52cm', 'dist_dir': '0cm'}]}}}}
    snapshot = {'classe': 'PIL', 'collections': {'pilares': [row]}}
    return path, snapshot


def test_original_measurement_rejects_false_47_and_pillar_section(contact):
    path, snapshot = contact
    link = snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']['B']['chega'][0]
    link.update(dim='20/66', dist_esq='47cm')
    report = gate.measure(path, snapshot)
    assert report['contacts'][0]['distances_cm'] == [0, 52]
    assert set(report['contacts'][0]['errors']) == {'dimensoes', 'distancias_cantos'}
    assert len(gate.errors(report)) == 2
    assert not gate.errors(report, [{'id':'dimensoes', 'status':'fail'},
                                    {'id':'distancias_cantos', 'status':'fail'}])


def test_corrected_contact_passes_without_changing_original(contact):
    path, snapshot = contact
    before = path.read_bytes()
    report = gate.measure(path, snapshot)
    assert not gate.errors(report)
    assert report['contacts'][0]['section'] == '14/55'
    assert path.read_bytes() == before
    assert report['measured_accuracy'] is False


def test_unproved_other_reference_does_not_override_local_section(contact):
    path, snapshot = contact
    snapshot['collections']['pilares'][0]['lajes'] = [{'viga': {'name':'V1', 'dim':'20/66'}}]
    assert 'dimensoes' not in gate.measure(path, snapshot)['contacts'][0]['errors']


def test_rounded_display_zero_does_not_hide_numeric_error(contact):
    path, snapshot = contact
    link = snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']['B']['chega'][0]
    link['dist_dir'] = '0.08cm'
    assert gate.errors(gate.measure(path, snapshot))


def test_unbound_neighbor_dimension_never_proves_section(contact):
    path, snapshot = contact
    doc = ezdxf.readfile(path)
    for text in doc.modelspace().query('TEXT'):
        if text.dxf.text == '14/55':
            text.dxf.insert = (0, 70)
    doc.saveas(path)
    assert gate.measure(path, snapshot)['contacts'][0]['status'] == 'uncertain'


def test_multiple_wall_pairs_are_uncertain(contact):
    path, snapshot = contact
    doc = ezdxf.readfile(path)
    doc.modelspace().add_line((20, 38), (100, 38))
    doc.modelspace().add_text('28/55', dxfattribs={'insert':(70,70), 'height':3})
    doc.saveas(path)
    assert gate.measure(path, snapshot)['contacts'][0]['status'] == 'uncertain'


def test_rotated_or_degenerate_contour_cannot_pass(contact):
    path, snapshot = contact
    snapshot['collections']['pilares'][0]['points'][0] = [3, 5]
    assert gate.errors(gate.measure(path, snapshot))


def test_shifted_pillar_cannot_manufacture_matching_distances(contact):
    path, snapshot = contact
    snapshot['collections']['pilares'][0]['points'] = [[0,-5],[20,-5],[20,66],[0,66]]
    assert 'contorno fechado original' in gate.errors(gate.measure(path, snapshot))[0]


def test_original_explicit_repeated_endpoint_is_closed_geometry(contact):
    path, snapshot = contact
    doc = ezdxf.readfile(path)
    entity = list(doc.modelspace().query('LWPOLYLINE'))[0]
    entity.closed = False
    entity.append_points([(0,0)])
    doc.saveas(path)
    assert not gate.errors(gate.measure(path,snapshot))


def test_placeholder_no_beam_is_not_a_missing_contact(contact):
    path, snapshot = contact
    faces = snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']
    faces['A'] = {'chega':[{'nome':'nenhuma'}]}
    assert len(gate.measure(path, snapshot)['contacts']) == 1


def test_contract_blocks_pass_using_server_measured_evidence(contact):
    from portal.app import qa_review_contract as contract
    from portal.tests.test_qa_review_contract import payload
    path, snapshot = contact
    snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']['B']['chega'][0]['dist_esq'] = '47cm'
    report = gate.measure(path, snapshot)
    # All receipts/proofs could be valid and still contain a false numeric PASS.
    review = payload()
    with pytest.raises(ValueError, match='DXF original'):
        contract.validate(review, 'PIL', {'sa_snapshot':snapshot, 'original_cad_measurements':report})


def test_general_fail_cannot_hide_false_unit_pass(contact):
    from portal.app import qa_review_contract as contract
    from portal.tests.test_qa_review_contract import payload
    path, snapshot = contact
    snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']['B']['chega'][0]['dist_esq'] = '47cm'
    review = payload()
    units = {c['id']: dict(status='pass', observation='medido', evidence=c['evidence']) for c in review['checks']}
    for check in review['checks']:
        if check['id'] == 'distancias_cantos':
            check['status'] = 'fail'
    review['unit_reviews'] = [{'unit_path':'/collections/pilares/0', 'checks':units}]
    with pytest.raises(ValueError, match='PASS por unidade contradiz DXF original'):
        contract.validate(review, 'PIL', {'sa_snapshot':snapshot, 'original_cad_measurements':gate.measure(path,snapshot)})


def _slab_dxf(tmp_path, texts):
    doc = ezdxf.new()
    for text, at in texts:
        doc.modelspace().add_text(text, dxfattribs={'insert': at, 'height': 3})
    path = tmp_path / 'laj.dxf'
    doc.saveas(path)
    return path


def _slab(**changes):
    slab = dict(name='L1', nivel='852.12', height='12', slab_steps=[],
                points=[[0, 0], [100, 0], [100, 50], [100, 50], [0, 50]])
    slab.update(changes)
    return {'classe': 'LAJ', 'collections': {'lajes': [slab]}}


def test_slab_written_values_must_match(tmp_path):
    path = _slab_dxf(tmp_path, [('L1', (20, 20)), ('h=12', (40, 20)), ('852.19', (60, 20)), ('852.12', (200, 20))])
    report = gate.measure_slabs(path, _slab())
    assert not report['measured_accuracy']
    found = gate.errors(report)
    assert len(found) == 1 and '852,19' in found[0] and 'niveis' not in found[0]
    assert gate.errors(gate.measure_slabs(path, _slab(nivel='852.19'))) == []


def test_slab_without_written_level_blocks_only_level_pass(tmp_path):
    path = _slab_dxf(tmp_path, [('L1', (20, 20)), ('h=12', (40, 20)), ('852.19', (200, 20))])
    report = gate.measure_slabs(path, _slab())
    assert gate.errors(report) == []  # ausência de cota não bloqueia adoção humana
    blocked = gate.errors(report, [{'id': 'niveis', 'status': 'pass'}])
    assert len(blocked) == 1 and 'E1 ausente' in blocked[0]
    assert gate.errors(report, [{'id': 'niveis', 'status': 'uncertain'}, {'id': 'identidade_contorno', 'status': 'pass'}]) == []


def test_slab_foreign_label_and_thickness_are_measured(tmp_path):
    path = _slab_dxf(tmp_path, [('L2', (20, 20)), ('h=10', (40, 20)), ('852.12', (60, 20))])
    found = gate.errors(gate.measure_slabs(path, _slab()))
    assert any('rótulo contido L2' in e for e in found) and any('h=10' in e for e in found)


def test_slab_merged_labels_are_uncertain(tmp_path):
    path = _slab_dxf(tmp_path, [('L1', (20, 20)), ('L2', (70, 20)), ('h=12', (40, 20)), ('852.12', (60, 20))])
    blocked = gate.errors(gate.measure_slabs(path, _slab()), [{'id': 'identidade_contorno', 'status': 'pass'}])
    assert len(blocked) == 1 and 'valores distintos' in blocked[0]


def test_slab_steps_and_degenerate_contour_are_never_certified(tmp_path):
    path = _slab_dxf(tmp_path, [('L1', (20, 20)), ('h=12', (40, 20)), ('852.12', (60, 20))])
    stepped = gate.measure_slabs(path, _slab(slab_steps=[{'delta': -5}]))
    assert gate.errors(stepped, [{'id': 'niveis', 'status': 'pass'}])
    flat = gate.measure_slabs(path, _slab(points=[[0, 0], [100, 0], [0, 0]]))
    assert gate.errors(flat, [{'id': 'identidade_contorno', 'status': 'pass'}])


def test_slab_step_region_is_measured_against_its_own_values(tmp_path):
    step = dict(uid='slab-step:L1:BD1', points=[[60, 0], [100, 0], [100, 50], [60, 50]], height_cm=10.0, level_m=852.16)
    path = _slab_dxf(tmp_path, [('L1', (20, 20)), ('h=12', (30, 20)), ('852.12', (40, 20)),
                                ('h=10', (70, 20)), ('852.16', (80, 20))])
    report = gate.measure_slabs(path, _slab(slab_steps=[step]))
    assert gate.errors(report) == []
    assert all(c['status'] == 'measured' for c in report['contacts'])
    wrong = gate.measure_slabs(path, _slab(slab_steps=[dict(step, level_m=852.12)]))
    assert any('852,16 (degrau BD1)' in e for e in gate.errors(wrong))
