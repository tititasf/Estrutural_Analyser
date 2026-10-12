"""Source-proved contact metadata survives refresh only under the same authority."""
import copy
import pytest
from src.core.pillar_face_beams import enrich_pillar_report_with_beams
from src.core.pil_original_contact_identity import (
    _restore_original_contact_provenance, serialize_original_contact_slot)


@pytest.mark.parametrize('veto', ['none', 'source', 'geometry', 'section', 'corner',
                                 'role', 'human', 'duplicate', 'incomplete'])
def test_refresh_keeps_exact_contact_proof_without_recreating_a_contact(veto):
    points = [(0, 0), (19, 0), (19, 170), (0, 170)]
    report = {'P900': {'name': 'P900', 'points': points, 'lajes': []}}
    beam = {'name': 'V900', 'dim': '19/48', 'is_h': True,
            '_recovered_corridor': (19, 80, 200, 99)}
    enrich_pillar_report_with_beams(report, [beam])
    pillar = report['P900']
    prior = pillar['face_beams']['B']['para'][0]
    prior.update(source='original_contact_identity', original_identity_evidence={
        'source_sha256': 'a'*64, 'pillar_points': copy.deepcopy(points),
        'positions_preserved': True, 'wall_handles': ['w1', 'w2'],
        'beam_handles': ['n'], 'section_handles': ['s']})
    if veto == 'incomplete':
        prior['original_identity_evidence']['section_handles'] = []
    enrich_pillar_report_with_beams(report, [beam])
    fresh = pillar['face_beams']['B']['para'][0]
    if veto == 'geometry':
        pillar['points'] = [(x+1, y) for x, y in points]
    if veto == 'section': fresh['dim'] = '19/50'
    if veto == 'corner': fresh['corner'] = 'BC' if fresh['corner'] != 'BC' else 'BD'
    if veto == 'human': fresh['human_override'] = True
    if veto == 'duplicate': pillar['face_beams']['B']['para'].append(copy.deepcopy(fresh))
    if veto == 'role':
        pillar['face_beams']['B']['interior'] = pillar['face_beams']['B']['para']
        pillar['face_beams']['B']['para'] = []
    before = copy.deepcopy(pillar['face_beams'])
    _restore_original_contact_provenance(pillar, 'b'*64 if veto == 'source' else 'a'*64)
    assert '_pil_original_provenance_pending' not in pillar
    if veto == 'none':
        assert fresh['source'] == 'original_contact_identity'
        assert fresh['original_identity_evidence'] == prior['original_identity_evidence']
    else:
        assert pillar['face_beams'] == before


@pytest.mark.parametrize('complete', [True, False])
def test_serialized_contact_survives_refresh_only_with_complete_original_authority(complete):
    points = [(0, 0), (19, 0), (19, 170), (0, 170)]
    report = {'P900': {'name': 'P900', 'points': points, 'lajes': []}}
    beams = [{'name': 'V900', 'dim': '19/48', 'is_h': True,
              '_recovered_corridor': (19, 80, 200, 99)}]
    enrich_pillar_report_with_beams(report, beams)
    slot = report['P900']['face_beams']['B']['para'][0]
    slot.update(source='original_contact_identity', original_identity_evidence={
        'source_sha256': 'a'*64, 'pillar_points': points,
        'positions_preserved': True, 'wall_handles': ['w1', 'w2'],
        'beam_handles': ['n'], 'section_handles': ['s'] if complete else [],
        'identity_path': {'heavy': 'excluded'}}, evidence_segments=['excluded'])
    serialized = serialize_original_contact_slot(slot)
    assert 'evidence_segments' not in serialized
    assert 'identity_path' not in serialized.get('original_identity_evidence', {})
    report['P900']['face_beams']['B']['para'] = [serialized]
    enrich_pillar_report_with_beams(report, beams)
    _restore_original_contact_provenance(report['P900'], 'a'*64)
    current = report['P900']['face_beams']['B']['para'][0]
    assert ('original_identity_evidence' in current) is complete
