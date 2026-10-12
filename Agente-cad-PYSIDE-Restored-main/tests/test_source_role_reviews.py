import hashlib
import json
from copy import deepcopy

import ezdxf
import pytest
from shapely.geometry import Polygon, mapping

from portal.app.preprocessamento.adapters.source_role_reviews import inventory_source_role_reviews
from portal.app.preprocessamento.sa_levels import pillar_ownership


def fixture(tmp_path):
    path = tmp_path / 'original.dxf'
    doc = ezdxf.new()
    points = [(1, 1), (4, 1), (4, 3), (1, 3)]
    entity = doc.modelspace().add_lwpolyline(points, close=True)
    doc.saveas(path)
    record = dict(decision_id='human-decision', authority='human_owner', human_answer='belongs to slab',
                  role='slab_region', owner='L1', source_entity_handles=[entity.dxf.handle],
                  original_points=points, level_transfer_authorized=False)
    payload = dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), records=[record])
    slabs = [dict(name='L1', points=[(0, 0), (10, 0), (10, 10), (0, 10)])]
    return path, payload, slabs


def write(path, payload):
    path.with_suffix('.source-role-review.json').write_text(json.dumps(payload), encoding='utf8')


def test_source_role_preserves_owner_and_pillar_geometry(tmp_path):
    path, payload, slabs = fixture(tmp_path)
    write(path, payload)
    proof = inventory_source_role_reviews(path, slabs)
    assert len(proof['records']) == 1 and not proof['rejected']
    record = proof['records'][0]
    item = dict(item_id='false-candidate', item_class='pillar', display_name='P1',
                geometry=mapping(Polygon(record['original_points'])),
                source_entity_handles=record['source_entity_handles'])
    real = dict(item_id='real-pillar', item_class='pillar', display_name='P1',
                geometry=mapping(Polygon([(20, 20), (22, 20), (22, 22), (20, 22)])),
                source_entity_handles=['different'])
    context = dict(state=dict(pilares=[dict(name='P1', points=list(Polygon(real['geometry']['coordinates'][0]).exterior.coords))], slabs=slabs),
                   source_role_reviews=proof)
    snapshot = deepcopy([item, real])
    receivers, roles = pillar_ownership([item, real], context)
    assert receivers == {'P1': 'real-pillar'}
    assert roles['false-candidate'][0]['role'] == 'slab_region'
    assert [item, real] == snapshot and proof['level_transfer_authorized'] is False
    context['state']['pilares'][0]['points'] = record['original_points']
    assert pillar_ownership([item], context)[1] == {}  # Canonical physical pillar wins.


@pytest.mark.parametrize('change', ['sha', 'handle', 'geometry', 'level', 'authority', 'owner', 'conflict'])
def test_invalid_or_ambiguous_proofs_are_rejected(tmp_path, change):
    path, payload, slabs = fixture(tmp_path)
    record = payload['records'][0]
    if change == 'sha': payload['source_sha256'] = 'stale'
    if change == 'handle': record['source_entity_handles'] = ['DEAD']
    if change == 'geometry': record['original_points'][0] = (0, 0)
    if change == 'level': record['level_transfer_authorized'] = True
    if change == 'authority': record['authority'] = 'inferred'
    if change == 'owner': record['owner'] = 'missing'
    if change == 'conflict':
        other = deepcopy(record)
        other.update(decision_id='other', role='nonstructural_wall', owner='outside_pillar_scope')
        payload['records'].append(other)
    write(path, payload)
    result = inventory_source_role_reviews(path, slabs)
    assert result['records'] == [] and result['rejected']


def test_wall_requires_no_slab_and_other_source_has_no_review(tmp_path):
    path, payload, _ = fixture(tmp_path)
    payload['records'][0].update(role='nonstructural_wall', owner='outside_pillar_scope')
    write(path, payload)
    assert len(inventory_source_role_reviews(path)['records']) == 1
    other = tmp_path / 'other.dxf'
    other.write_bytes(path.read_bytes())
    assert inventory_source_role_reviews(other)['records'] == []
