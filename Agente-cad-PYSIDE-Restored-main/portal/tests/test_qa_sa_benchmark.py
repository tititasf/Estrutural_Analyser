"""Contract fixtures only; these tests are not an engineering accuracy corpus."""
import copy
import hashlib
import pytest
from scripts.arete.qa_sa_benchmark import evaluate


def sample(tmp_path):
    proof = tmp_path / 'reference.txt'
    proof.write_text('Contract-test fixture, not a real drawing or adjudication.')
    cases = []
    for classe, behavior in [('PIL','para'),('LAJ','para'),('FV','para'),('LV','para'),('LV','passa')]:
        for n, label in enumerate((True, False)):
            cases.append(dict(case_id=classe+behavior+str(n), classe=classe, behavior=behavior,
                              unit_id='fixture', criterion='geometry', source_sha256='a'*64,
                              reference_correct=label, reference_origin='human_adjudication',
                              human_label_verified=True, reviewer='test fixture',
                              reviewed_at='2026-10-03', method='contract fixture',
                              proofs=[{'path':proof.name,'sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}]))
    corpus = {'schema':'cad.qa.sa.reference/v1','split':'held_out','cases':cases}
    rows = [{k:r[k] for k in ('case_id','classe','behavior','unit_id','criterion','source_sha256')} |
            {'round_id':'fixture','assessment':'pass' if r['reference_correct'] else 'fail'} for r in cases]
    return corpus, {'schema':'cad.qa.sa.predictions/v1','rows':rows}


def test_all_classes_count_missing_and_uncertain_without_false_certification(tmp_path):
    corpus, predictions = sample(tmp_path)
    predictions['rows'][1]['assessment']='pass'  # false approval
    predictions['rows'][2]['assessment']='inconclusive'
    predictions['rows'].pop()
    report = evaluate(corpus,predictions,base=tmp_path)
    assert report['missing_classes']==[] and report['missing_predictions']==1
    assert report['by_class']['PIL']['false_approval_rate']==1
    assert report['by_class']['LAJ']['end_to_end_accuracy']==.5
    assert report['by_class']['LAJ']['selective_accuracy']==1
    assert report['by_class']['LV:passa']['technical']==1
    assert report['by_class']['LV:passa']['end_to_end_accuracy']==.5
    assert report['certified'] is False and report['calibrated_confidence'] is False


@pytest.mark.parametrize('mutation', ['duplicate_reference','duplicate_prediction','source_drift',
    'unlabeled','agent_reference','not_held_out','unverified','changed_proof','escape'])
def test_rejects_invalid_reference_and_prediction_integrity(tmp_path, mutation):
    corpus, predictions = sample(tmp_path)
    if mutation=='duplicate_reference': corpus['cases'].append(copy.deepcopy(corpus['cases'][0]))
    elif mutation=='duplicate_prediction': predictions['rows'].append(copy.deepcopy(predictions['rows'][0]))
    elif mutation=='source_drift': predictions['rows'][0]['source_sha256']='b'*64
    elif mutation=='unlabeled': corpus['cases'][0]['reference_correct']=None
    elif mutation=='agent_reference': corpus['cases'][0]['reference_origin']='agent_opinion'
    elif mutation=='not_held_out': corpus['split']='development'
    elif mutation=='unverified': corpus['cases'][0]['human_label_verified']=False
    elif mutation=='changed_proof': (tmp_path/'reference.txt').write_text('changed')
    elif mutation=='escape': corpus['cases'][0]['proofs'][0]['path']='../outside.txt'
    with pytest.raises(ValueError): evaluate(corpus,predictions,base=tmp_path)
