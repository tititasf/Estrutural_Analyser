import copy

from scripts.arete.jev_contact_advisor_v9 import assess, translated_equivalent
from scripts.arete.jev_calibration.hashing import sha256_json
from scripts.arete.jev_sa_second_read import MODEL


def packet():
    evidence = {'target_endpoint': [100, 200], 'candidate':
                {'handle': 'X', 'etype': 'LINE', 'closed': False, 'points': [[100, 205], [100, 210]]}}
    removed = copy.deepcopy(evidence)
    removed['candidate']['points'] = []
    return {'identity': {'source_dxf_sha256': 'a' * 64}, 'question': {'id': 'contact'},
            'evidence': evidence, 'controls': [{'id': 'withdrawal', 'evidence': removed, 'expected_choice': 'INSUFFICIENT'}]}


def response(req, choice='SEPARATE', control='INSUFFICIENT'):
    return {'schema': 'jev_sa_second_read_result/1', 'model': MODEL,
            'request_sha256': sha256_json(req), 'identity': req['identity'],
            'results': [{'variant': 'full', 'choice': choice, 'confidence': 1,
                         'evidence_sha256': sha256_json(req['evidence'])},
                        {'variant': 'withdrawal', 'choice': control,
                         'evidence_sha256': sha256_json(req['controls'][0]['evidence'])}]}


def relative(req):
    rel = copy.deepcopy(req)
    rel['evidence']['target_endpoint'] = [0, 0]
    rel['evidence']['candidate']['points'] = [[0, 5], [0, 10]]
    rel['controls'][0]['evidence']['target_endpoint'] = [0, 0]
    return rel


def test_consistent_bound_advice_never_approves_or_writes():
    req = packet()
    rel = relative(req)
    result = assess(req, response(req), (rel, response(rel)))
    assert result['decision'] == 'ADVISORY_ONLY'
    assert result['can_write_n1'] is False
    assert result['can_approve_qa'] is False
    assert result['semantic_verdict'] is None


def test_high_confidence_wrong_translation_is_withheld():
    req = packet()
    rel = relative(req)
    result = assess(req, response(req), (rel, response(rel, 'TOUCH')))
    assert result['decision'] == 'WITHHOLD_ADVICE'
    assert 'REPRESENTATION_INSTABILITY' in result['reasons']
    assert 'EQUIVALENT_DETERMINISTIC_CONTRADICTION' in result['reasons']


def test_stale_response_binding_is_withheld():
    req = packet()
    stale = response(req)
    req['evidence']['candidate']['points'][0][1] += 1
    assert 'INVALID_OR_UNBOUND_EVIDENCE' in assess(req, stale)['reasons']


def test_control_boolean_does_not_override_wrong_answer():
    req = packet()
    answer = response(req, control='TOUCH')
    answer['results'][1]['control_matches_expectation'] = True
    assert 'INVALID_OR_UNBOUND_EVIDENCE' in assess(req, answer)['reasons']


def test_missing_equivalence_is_withheld():
    req = packet()
    assert assess(req, response(req))['reasons'] == ['EQUIVALENCE_NOT_TESTED']


def test_translation_cannot_change_geometry():
    req = packet()
    rel = relative(req)
    rel['evidence']['candidate']['points'][0][1] = 0
    assert translated_equivalent(req, rel) is False
    assert 'INVALID_OR_UNBOUND_EVIDENCE' in assess(req, response(req), (rel, response(rel)))['reasons']


def test_model_abstention_is_not_promoted():
    req = packet()
    assert 'MODEL_ABSTAINED' in assess(req, response(req, 'INSUFFICIENT'))['reasons']


def test_wrong_source_identity_is_withheld():
    req = packet()
    answer = response(req)
    answer['identity'] = {'source_dxf_sha256': 'b' * 64}
    assert 'INVALID_OR_UNBOUND_EVIDENCE' in assess(req, answer)['reasons']
