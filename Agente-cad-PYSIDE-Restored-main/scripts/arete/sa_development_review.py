"""Explicit evidence-bound review; never replace baselines or hide differences.

This validates a responsible reviewer's attestation, not the engineering truth
of their reasoning. The reviewer must inspect source evidence and counterproof
before writing an approval. QA failures remain independent blockers.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

RECEIPT_SCHEMA = 'cad.sa.development_review/v1'
EVIDENCE_SCHEMA = 'cad.sa.development_review_evidence/v1'
REVIEWABLE_KINDS = {'geometry_changes', 'numeric_changes', 'contact_changes'}


def assess_reviewed_cycle(package, qa_report, regressions, receipt=None, **review_args):
    """Keep raw diffs; exact reviewed corrections never waive QA or isolation."""
    from portal.app.sa_development_gate import assess_cycle
    review = review_regressions(regressions, receipt, **review_args)
    blockers = list(review['unreviewed'])
    if review['validation_errors']:
        blockers.append({'reason': 'development_review_invalid',
                         'errors': review['validation_errors']})
    return assess_cycle(package, qa_report, regressions=blockers), review


def review_saved_cycle(report, receipt, **review_args):
    """Review a frozen fast-cycle result without recomputing SA or publication.

    Original QA/level blockers remain verbatim; only exact reviewed regression
    records are removed from the pending list of a separate reviewed artifact.
    Reports lacking producer state hashes cannot certify a saved cycle.
    """
    import copy
    from scripts.arete.sa_development_diff import compare_states
    source = review_args['source_path']
    baseline = review_args['baseline_state_path']
    current = review_args['current_state_path']
    errors = []
    for key, path in [('source_sha256',source),('baseline_state_sha256',baseline),
                      ('analysis_state_sha256',current)]:
        if report.get(key) != file_sha256(path): errors.append('frozen report '+key+' mismatch')
    comparison = compare_states(_json(baseline), _json(current))
    if fingerprint(comparison) != fingerprint(report.get('spatial_comparison')):
        errors.append('frozen report spatial comparison mismatch')
    spatial_diffs = {fingerprint(dict(kind=kind,**record))
                     for kind in ('geometry_changes','numeric_changes','geometry_errors','contact_changes')
                     for record in comparison[kind]}
    reported_diffs = {fingerprint(record) for record in report['regressions']
                      if record.get('kind') in ('geometry_changes','numeric_changes','geometry_errors','contact_changes')}
    if spatial_diffs != reported_diffs:
        errors.append('raw regressions do not match actual spatial differences')
    isolation = report.get('isolation') or {}
    runtime = report.get('runtime_code') or {}
    if (isolation.get('status') != 'passed' or isolation.get('changed_files')
            or isolation.get('changed_code_files') or isolation.get('rendered_files')
            or isolation.get('published') is not False or runtime.get('status') != 'unchanged'):
        errors.append('frozen cycle isolation or code guard not approved')
    if not review_args.get('accepted_reviewers'):
        errors.append('explicit accepted reviewer required')
    review = review_regressions(report['regressions'], receipt, **review_args)
    errors.extend(review['validation_errors'])
    assessment = copy.deepcopy(report['assessment'])
    approved = {fingerprint(r) for r in review['approved_exact']} if not errors else set()
    def approved_pending(p):
        if p.get('kind') != 'regression': return False
        import ast
        try: return fingerprint(ast.literal_eval(p['message'])) in approved
        except (ValueError,SyntaxError,TypeError,KeyError): return False
    assessment['pending'] = [p for p in assessment['pending'] if not approved_pending(p)]
    if errors:
        assessment['pending'].append(dict(unit='cycle',kind='regression',field=None,
            message=str({'reason':'development_review_invalid','errors':errors})))
    assessment['pending_count'] = len(assessment['pending'])
    assessment['pending_by_unit'] = {unit:[p for p in assessment['pending'] if p['unit']==unit]
        for unit in sorted({p['unit'] for p in assessment['pending']})}
    assessment['ready_for_publication'] = not assessment['pending'] and not errors
    assessment['final_visual_approved'] = False
    assessment['visual_review_required'] = True
    return dict(schema='cad.sa.saved_cycle_review/v1', assessment=assessment,
                raw_assessment=copy.deepcopy(report['assessment']), regression_review=review,
                validation_errors=errors, published=False)


def fingerprint(value):
    """Exact semantic JSON fingerprint; no rounding or item-name shortcuts."""
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _hash(value):
    return isinstance(value, str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _json(path):
    def reject_constant(value):
        raise ValueError('nonfinite JSON value: '+value)
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: '+key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      parse_constant=reject_constant, object_pairs_hook=unique_keys)


def review_regressions(regressions, receipt, *, source_path, baseline_state_path,
                       current_state_path, evidence_paths, accepted_reviewers=None):
    """Validate exact approvals against actual files and retain every regression.

    `evidence_paths` explicitly maps evidence IDs to approved local paths; no
    path inside an untrusted receipt is followed. `receipt` is a parsed object.
    A malformed/stale approval invalidates the whole receipt, failing closed.
    New differences are unreviewed. Nothing modifies files, QA or a baseline.
    An optional accepted_reviewers set constrains the explicit reviewer ID.
    """
    all_regressions = list(regressions)
    result = dict(schema='cad.sa.development_review_result/v1',
                  all_regressions=all_regressions, approved_exact=[],
                  unreviewed=list(all_regressions), validation_errors=[])
    if receipt is None:
        return result
    errors=result['validation_errors']
    def fail(message):
        errors.append(message)
    try:
        live = {'source_sha256': file_sha256(source_path),
                'baseline_state_sha256': file_sha256(baseline_state_path),
                'current_state_sha256': file_sha256(current_state_path)}
        result['live_hashes']=live
        if not isinstance(receipt,dict) or receipt.get('schema')!=RECEIPT_SCHEMA:
            fail('receipt schema invalid')
            return result
        for key,value in live.items():
            if receipt.get(key)!=value:
                fail('receipt '+key+' does not match actual file')
        reviewer=receipt.get('reviewer')
        if not isinstance(reviewer,dict) or not isinstance(reviewer.get('id'),str) or not reviewer['id'].strip():
            fail('explicit reviewer missing')
            reviewer={}
        if reviewer.get('authority') not in {'human','agent'}:
            fail('reviewer authority invalid')
        if accepted_reviewers is not None and reviewer.get('id') not in accepted_reviewers:
            fail('reviewer not accepted by caller')
        fingerprints=[fingerprint(r) for r in all_regressions]
        if len(set(fingerprints))!=len(fingerprints):
            fail('ambiguous duplicate regression fingerprints')
        indexed=dict(zip(fingerprints,all_regressions))
        approvals=receipt.get('approvals')
        if not isinstance(approvals,list):
            fail('approvals must be a list')
            return result
        seen=set();valid=set();source_handles=None
        for index,approval in enumerate(approvals):
            prefix=f'approval {index}: '
            if not isinstance(approval,dict):
                fail(prefix+'invalid record');continue
            fp=approval.get('diff_fingerprint')
            if not _hash(fp) or fp not in indexed:
                fail(prefix+'extra or unknown exact difference');continue
            if fp in seen:
                fail(prefix+'duplicate approval');continue
            seen.add(fp)
            if indexed[fp].get('kind') not in REVIEWABLE_KINDS:
                fail(prefix+'QA status or invalid geometry cannot be waived');continue
            if approval.get('verdict')!='approved':
                fail(prefix+'explicit approved verdict missing');continue
            ref=approval.get('evidence')
            if not isinstance(ref,dict) or ref.get('id') not in evidence_paths or not _hash(ref.get('sha256')):
                fail(prefix+'evidence reference missing or unregistered');continue
            path=evidence_paths[ref['id']]
            try:
                if file_sha256(path)!=ref['sha256']:
                    fail(prefix+'evidence bytes changed');continue
                evidence=_json(path)
            except (OSError,ValueError,TypeError) as exc:
                fail(prefix+'evidence unavailable: '+str(exc));continue
            if not isinstance(evidence,dict) or evidence.get('schema')!=EVIDENCE_SCHEMA:
                fail(prefix+'evidence schema invalid');continue
            if any(evidence.get(k)!=v for k,v in live.items()) or evidence.get('diff_fingerprint')!=fp:
                fail(prefix+'evidence source/state/difference binding mismatch');continue
            if evidence.get('reviewer_id')!=reviewer.get('id') or evidence.get('verdict')!='approved':
                fail(prefix+'evidence reviewer/verdict mismatch');continue
            proof=evidence.get('source_proof');counter=evidence.get('counterproof')
            if (not isinstance(proof,dict) or proof.get('basis')!='original_cad'
                    or not _text(proof.get('rule'))
                    or not isinstance(proof.get('facts'), (dict,list)) or not proof['facts']):
                fail(prefix+'original source proof missing');continue
            if not isinstance(counter,dict) or counter.get('checked') is not True or counter.get('baseline_fails') is not True or counter.get('current_satisfies') is not True or not _text(counter.get('reason')):
                fail(prefix+'baseline/current counterproof missing');continue
            handles=proof.get('source_handles')
            counter_handles=counter.get('source_handles')
            if any(not isinstance(h,list) or not h or any(not isinstance(v,str) or not v for v in h)
                   for h in (handles,counter_handles)):
                fail(prefix+'source/counterproof handles missing');continue
            # Verify source provenance really exists in the hashed DXF; a
            # receipt cannot silently cite entities from another drawing.
            if source_handles is None:
                import ezdxf
                try:
                    doc=ezdxf.readfile(source_path)
                except ezdxf.DXFError as exc:
                    fail(prefix+'original CAD unreadable: '+str(exc));continue
                source_handles=set(doc.entitydb)
            if any(h not in source_handles for h in handles+counter_handles):
                fail(prefix+'cited handle does not exist in actual original source');continue
            valid.add(fp)
        if not errors:
            result['approved_exact']=[r for fp,r in zip(fingerprints,all_regressions) if fp in valid]
            result['unreviewed']=[r for fp,r in zip(fingerprints,all_regressions) if fp not in valid]
    except (OSError,ValueError,TypeError,AttributeError) as exc:
        fail('review validation failed: '+str(exc))
    return result
