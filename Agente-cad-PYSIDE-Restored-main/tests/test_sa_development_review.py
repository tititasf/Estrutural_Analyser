"""Synthetic review attestations only; no mission approvals are generated."""
import copy
import json

import ezdxf
import pytest

from scripts.arete.sa_development_review import (
    EVIDENCE_SCHEMA, RECEIPT_SCHEMA, file_sha256, fingerprint, review_regressions,
)


@pytest.fixture
def case(tmp_path):
    source = tmp_path / 'original.dxf'
    doc = ezdxf.new()
    line = doc.modelspace().add_line((0, 0), (20, 0))
    doc.saveas(source)
    baseline = tmp_path / 'baseline.json'
    current = tmp_path / 'current.json'
    baseline.write_text('{"value":19}', encoding='utf-8')
    current.write_text('{"value":20}', encoding='utf-8')
    regression = {'kind': 'numeric_changes', 'item': 'TEST_ONLY',
                  'field': 'length', 'before': 19, 'after': 20}
    hashes = dict(source_sha256=file_sha256(source),
                  baseline_state_sha256=file_sha256(baseline),
                  current_state_sha256=file_sha256(current))
    evidence = dict(schema=EVIDENCE_SCHEMA, **hashes,
                    diff_fingerprint=fingerprint(regression),
                    reviewer_id='synthetic-test', verdict='approved',
                    source_proof={'basis': 'original_cad', 'rule': 'original measured length',
                                  'facts': {'measured_length': 20},
                                  'source_handles': [line.dxf.handle]},
                    counterproof={'checked': True, 'baseline_fails': True,
                                  'current_satisfies': True, 'reason': '19 differs from original 20',
                                  'source_handles': [line.dxf.handle]})
    evidence_path = tmp_path / 'evidence.json'
    evidence_path.write_text(json.dumps(evidence), encoding='utf-8')
    approval = {'diff_fingerprint': fingerprint(regression), 'verdict': 'approved',
                'evidence': {'id': 'test-proof', 'sha256': file_sha256(evidence_path)}}
    receipt = dict(schema=RECEIPT_SCHEMA, **hashes,
                   reviewer={'id': 'synthetic-test', 'authority': 'agent'}, approvals=[approval])
    return dict(source=source, baseline=baseline, current=current, regression=regression,
                evidence=evidence, evidence_path=evidence_path, receipt=receipt)


def run(case, regressions=None, receipt='default', **overrides):
    args = dict(source_path=case['source'], baseline_state_path=case['baseline'],
                current_state_path=case['current'],
                evidence_paths={'test-proof': case['evidence_path']},
                accepted_reviewers={'synthetic-test'})
    args.update(overrides)
    return review_regressions([case['regression']] if regressions is None else regressions,
                             case['receipt'] if receipt == 'default' else receipt, **args)


def rewrite_evidence(case):
    case['evidence_path'].write_text(json.dumps(case['evidence']), encoding='utf-8')
    case['receipt']['approvals'][0]['evidence']['sha256'] = file_sha256(case['evidence_path'])


def assert_closed(result):
    assert result['validation_errors']
    assert result['approved_exact'] == []
    assert result['unreviewed'] == result['all_regressions']


def test_exact_evidence_bound_approval_preserves_inputs_and_files(case):
    original = copy.deepcopy(case['receipt'])
    original_diff = copy.deepcopy(case['regression'])
    bytes_before = {k: case[k].read_bytes() for k in ['source', 'baseline', 'current', 'evidence_path']}
    result = run(case)
    assert result['validation_errors'] == []
    assert result['approved_exact'] == [case['regression']]
    assert result['unreviewed'] == []
    assert result['all_regressions'] == [original_diff]
    assert case['receipt'] == original
    assert case['regression'] == original_diff
    assert bytes_before == {k: case[k].read_bytes() for k in bytes_before}


def test_absent_receipt_preserves_all_pending(case):
    result = run(case, receipt=None)
    assert result['approved_exact'] == []
    assert result['unreviewed'] == [case['regression']]
    assert result['validation_errors'] == []


def test_contact_inventory_change_needs_its_own_exact_original_proof(case):
    contact={'kind':'contact_changes','family':'PIL','item':'TEST_ONLY',
        'removed_contacts':[['C','passa','V1']],'added_contacts':[],
        'original_source_review_required':True}
    # A valid geometry/numeric receipt does not approve a new contact diff.
    result=run(case,[case['regression'],contact])
    assert result['approved_exact']==[case['regression']]
    assert result['unreviewed']==[contact]
    case['regression']=contact
    case['evidence']['diff_fingerprint']=fingerprint(contact)
    case['evidence']['source_proof']['rule']='original wall excludes contact'
    case['evidence']['source_proof']['facts']={'contact_exists':False}
    case['evidence']['counterproof']['reason']='baseline contact lacks original wall; current excludes it'
    case['receipt']['approvals'][0]['diff_fingerprint']=fingerprint(contact)
    rewrite_evidence(case)
    assert run(case)['approved_exact']==[contact]
    case['evidence']['counterproof']['checked']=False
    rewrite_evidence(case)
    assert_closed(run(case))


def test_new_difference_remains_unreviewed_even_same_item(case):
    new = {**case['regression'], 'field': 'depth', 'after': 55}
    result = run(case, [case['regression'], new])
    assert result['validation_errors'] == []
    assert result['approved_exact'] == [case['regression']]
    assert result['unreviewed'] == [new]
    assert result['all_regressions'] == [case['regression'], new]


@pytest.mark.parametrize('file', ['source', 'baseline', 'current'])
def test_actual_file_bytes_changed_invalidates_receipt(case, file):
    with case[file].open('ab') as stream:
        stream.write(b'\n')
    assert_closed(run(case))


@pytest.mark.parametrize('key', ['source_sha256', 'baseline_state_sha256', 'current_state_sha256'])
def test_receipt_hash_mismatch(case, key):
    case['receipt'][key] = '0'*64
    assert_closed(run(case))


def test_mutated_diff_cannot_approve_by_item(case):
    case['regression']['after'] = 20.000000001
    assert_closed(run(case))


def test_extra_approval_invalidates_even_other_good_approval(case):
    case['receipt']['approvals'].append({**case['receipt']['approvals'][0],
                                        'diff_fingerprint': '0'*64})
    assert_closed(run(case))


def test_duplicate_approval_invalidates(case):
    case['receipt']['approvals'].append(copy.deepcopy(case['receipt']['approvals'][0]))
    assert_closed(run(case))


def test_duplicate_differences_are_ambiguous(case):
    assert_closed(run(case, [case['regression'], copy.deepcopy(case['regression'])]))


def test_missing_file_evidence(case):
    case['evidence_path'].unlink()
    assert_closed(run(case))


def test_unregistered_evidence_cannot_follow_receipt_path(case):
    case['receipt']['approvals'][0]['evidence']['path'] = str(case['evidence_path'])
    assert_closed(run(case, evidence_paths={}))


def test_changed_evidence_bytes(case):
    with case['evidence_path'].open('ab') as stream:
        stream.write(b' ')
    assert_closed(run(case))


@pytest.mark.parametrize('key', ['source_sha256', 'baseline_state_sha256',
                                 'current_state_sha256', 'diff_fingerprint'])
def test_rehashed_evidence_still_requires_all_bindings(case, key):
    case['evidence'][key] = '0'*64
    rewrite_evidence(case)
    assert_closed(run(case))


@pytest.mark.parametrize('field,value', [('checked', False), ('baseline_fails', False),
                                       ('current_satisfies', False), ('reason', ''),
                                       ('source_handles', [])])
def test_counterproof_required(case, field, value):
    case['evidence']['counterproof'][field] = value
    rewrite_evidence(case)
    assert_closed(run(case))


@pytest.mark.parametrize('field,value', [('basis', 'sa_result'), ('facts', {}),
                                       ('facts', True), ('rule', ''), ('rule', True),
                                       ('source_handles', [])])
def test_original_proof_required(case, field, value):
    case['evidence']['source_proof'][field] = value
    rewrite_evidence(case)
    assert_closed(run(case))


@pytest.mark.parametrize('group', ['source_proof', 'counterproof'])
def test_cited_handle_must_exist_in_hashed_original(case, group):
    case['evidence'][group]['source_handles'] = ['FFFFABC']
    rewrite_evidence(case)
    assert_closed(run(case))


@pytest.mark.parametrize('kind', ['qa_regression', 'geometry_errors', 'pillar_detail_context'])
def test_qa_or_invalid_geometry_cannot_be_waived(case, kind):
    case['regression']['kind'] = kind
    fp = fingerprint(case['regression'])
    case['receipt']['approvals'][0]['diff_fingerprint'] = fp
    case['evidence']['diff_fingerprint'] = fp
    rewrite_evidence(case)
    assert_closed(run(case))


def test_evidence_reviewer_must_match_explicit_reviewer(case):
    case['evidence']['reviewer_id'] = 'another'
    rewrite_evidence(case)
    assert_closed(run(case))


def test_caller_can_constrain_reviewers(case):
    assert_closed(run(case, accepted_reviewers={'someone-else'}))


def test_verdict_is_not_inferred_from_qa_status(case):
    case['receipt']['approvals'][0].pop('verdict')
    case['receipt']['approvals'][0]['qa_status'] = 'confirmed'
    assert_closed(run(case))


@pytest.mark.parametrize('receipt', [[], {}, {'schema': RECEIPT_SCHEMA, 'approvals': []}])
def test_malformed_receipt_fails_closed(case, receipt):
    assert_closed(run(case, receipt=receipt))


def test_duplicate_json_keys_in_evidence_rejected(case):
    data = case['evidence_path'].read_text(encoding='utf-8')
    case['evidence_path'].write_text(data[:-1]+',"verdict":"approved"}', encoding='utf-8')
    case['receipt']['approvals'][0]['evidence']['sha256'] = file_sha256(case['evidence_path'])
    assert_closed(run(case))


def test_matching_hashes_do_not_make_invalid_original_readable(case):
    case['source'].write_bytes(b'not a DXF')
    sha = file_sha256(case['source'])
    case['receipt']['source_sha256'] = sha
    case['evidence']['source_sha256'] = sha
    rewrite_evidence(case)
    assert_closed(run(case))


def test_empty_approval_list_does_not_resolve_diffs(case):
    case['receipt']['approvals'] = []
    result = run(case)
    assert result['validation_errors'] == []
    assert result['approved_exact'] == []
    assert result['unreviewed'] == [case['regression']]


def test_fingerprint_exact_and_order_independent():
    assert fingerprint({'a': 1, 'b': 2}) == fingerprint({'b': 2, 'a': 1})
    assert fingerprint({'a': 1}) != fingerprint({'a': 1.0})
    assert fingerprint({'a': 1}) != fingerprint({'a': 1.000000001})
    with pytest.raises(ValueError):
        fingerprint({'a': float('nan')})


def reviewed_assessment(case, receipt):
    from scripts.arete.sa_development_review import assess_reviewed_cycle
    return assess_reviewed_cycle({}, {}, [case['regression']], receipt,
        source_path=case['source'], baseline_state_path=case['baseline'],
        current_state_path=case['current'],
        evidence_paths={'test-proof': case['evidence_path']},
        accepted_reviewers={'synthetic-test'})


def test_gate_keeps_qa_and_inventory_blockers_after_exact_review(case):
    assessment, review = reviewed_assessment(case, case['receipt'])
    assert review['approved_exact'] == [case['regression']]
    assert review['all_regressions'] == [case['regression']]
    assert not any(p['kind'] == 'regression' for p in assessment['pending'])
    assert any(p['kind'] == 'qa_incomplete' for p in assessment['pending'])
    assert any(p['kind'] == 'inventory_incomplete' for p in assessment['pending'])
    assert assessment['ready_for_publication'] is False
    assert assessment['final_visual_approved'] is False


def test_gate_without_receipt_keeps_every_regression(case):
    assessment, review = reviewed_assessment(case, None)
    assert review['approved_exact'] == []
    assert review['unreviewed'] == [case['regression']]
    assert any(p['message'] == str(case['regression']) for p in assessment['pending'])


def test_invalid_review_adds_explicit_blocker_and_keeps_raw_difference(case):
    case['current'].write_text('{"value":21}', encoding='utf8')
    assessment, review = reviewed_assessment(case, case['receipt'])
    assert review['validation_errors']
    assert review['approved_exact'] == []
    assert any('development_review_invalid' in p['message'] for p in assessment['pending'])
    assert any(p['message'] == str(case['regression']) for p in assessment['pending'])


def test_cycle_rejects_unspecified_reviewer_before_running_sa(tmp_path):
    from scripts.arete.dev_sa_cycle import run_cycle
    with pytest.raises(ValueError, match='explicit accepted reviewer'):
        run_cycle(obra=tmp_path, pav='TEST', db=tmp_path/'db', output=tmp_path/'out',
                  review_receipt=tmp_path/'receipt.json')
    assert not (tmp_path/'out').exists()


@pytest.fixture
def saved_case(case):
    from scripts.arete.sa_development_diff import compare_states
    state={'slabs':[{'name':'TEST_ONLY','height':'19','nivel':'123.25',
                     'points':[[0,0],[20,0],[20,10],[0,10]]}]}
    current=copy.deepcopy(state); current['slabs'][0]['height']='20'
    case['baseline'].write_text(json.dumps(state),encoding='utf8')
    case['current'].write_text(json.dumps(current),encoding='utf8')
    comparison=compare_states(state,current)
    case['regression']={'kind':'numeric_changes',**comparison['numeric_changes'][0]}
    for key,path in [('baseline_state_sha256',case['baseline']),('current_state_sha256',case['current'])]:
        case['receipt'][key]=case['evidence'][key]=file_sha256(path)
    case['evidence']['diff_fingerprint']=fingerprint(case['regression'])
    case['receipt']['approvals'][0]['diff_fingerprint']=fingerprint(case['regression'])
    rewrite_evidence(case)
    case['report']={'source_sha256':file_sha256(case['source']),
        'baseline_state_sha256':file_sha256(case['baseline']),
        'analysis_state_sha256':file_sha256(case['current']),
        'spatial_comparison':comparison,'regressions':[case['regression']],
        'runtime_code':{'status':'unchanged'},
        'isolation':{'status':'passed','changed_files':[],'changed_code_files':[],
                     'rendered_files':[],'published':False},
        'assessment':{'pending':[{'unit':'cycle','kind':'regression','field':None,
                                  'message':str(dict(reversed(list(case['regression'].items()))))},
                                 {'unit':'TEST_ONLY','kind':'qa_pending','field':None,'message':'CAD unproved'}],
                      'pending_count':2,'ready_for_publication':False}}
    return case


def saved_review(case):
    from scripts.arete.sa_development_review import review_saved_cycle
    return review_saved_cycle(case['report'],case['receipt'],source_path=case['source'],
        baseline_state_path=case['baseline'],current_state_path=case['current'],
        evidence_paths={'test-proof':case['evidence_path']},accepted_reviewers={'synthetic-test'})


def test_saved_review_reduces_only_exact_diff_and_keeps_raw_qa(saved_case):
    original=copy.deepcopy(saved_case['report'])
    result=saved_review(saved_case)
    assert result['validation_errors']==[]
    assert result['assessment']['pending_count']==1
    assert result['assessment']['pending'][0]['kind']=='qa_pending'
    assert result['assessment']['ready_for_publication'] is False
    assert result['raw_assessment']==original['assessment']
    assert saved_case['report']==original


@pytest.mark.parametrize('guard',['state_hash','code','render','source','missing_diff'])
def test_saved_cycle_guard_cannot_be_waived(saved_case,guard):
    r=saved_case['report']
    if guard=='state_hash': r.pop('analysis_state_sha256')
    elif guard=='code': r['runtime_code']['status']='changed'
    elif guard=='render': r['isolation']['rendered_files']=['unwanted.svg']
    elif guard=='source': r['source_sha256']='0'*64
    elif guard=='missing_diff': r['regressions']=[]
    result=saved_review(saved_case)
    assert result['validation_errors']
    assert result['assessment']['pending_count']>=2
    assert result['assessment']['ready_for_publication'] is False
    assert result['assessment']['final_visual_approved'] is False
