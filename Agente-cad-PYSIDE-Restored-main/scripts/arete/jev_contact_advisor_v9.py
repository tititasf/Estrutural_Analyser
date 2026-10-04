"""Offline safety checks for the frozen v9 straight-edge contact experiment.

No API, SA mutation or QA approval. Confidence is recorded, never used as proof.
This does not classify PARA/PASSA or support ownership.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scripts.arete.jev_calibration.hashing import sha256_json
from scripts.arete.jev_sa_second_read import MODEL
from scripts.arete.jev_source_events_v9 import boundary_distance


def bound_answer(request: dict, response: dict) -> dict:
    if (response.get('schema') != 'jev_sa_second_read_result/1'
            or response.get('request_sha256') != sha256_json(request)
            or response.get('identity') != request.get('identity')
            or response.get('model') != MODEL):
        raise ValueError('response binding failed')
    rows = response.get('results') or []
    full = [r for r in rows if r.get('variant') == 'full']
    if len(full) != 1 or full[0].get('evidence_sha256') != sha256_json(request['evidence']):
        raise ValueError('full evidence binding failed')
    controls = request.get('controls') or []
    if not controls:
        raise ValueError('missing withdrawal control')
    for control in controls:
        matches = [r for r in rows if r.get('variant') == control['id']]
        if (len(matches) != 1
                or matches[0].get('evidence_sha256') != sha256_json(control['evidence'])
                or control.get('expected_choice') != 'INSUFFICIENT'
                or matches[0].get('choice') != 'INSUFFICIENT'):
            raise ValueError('withdrawal control failed')
    return full[0]


def translated_equivalent(original: dict, translated: dict) -> bool:
    if original.get('identity') != translated.get('identity') or original.get('question') != translated.get('question'):
        return False
    a, b = original['evidence'], translated['evidence']
    ca, cb = a['candidate'], b['candidate']
    if any(ca.get(k) != cb.get(k) for k in ('handle', 'etype', 'closed')):
        return False
    pa, pb = ca.get('points') or [], cb.get('points') or []
    if not pa or len(pa) != len(pb) or b.get('target_endpoint') != [0, 0]:
        return False
    origin = a['target_endpoint']
    return all(math.isfinite(float(q[j])) and abs((p[j] - origin[j]) - q[j]) <= 0.00000051
               for p, q in zip(pa, pb) for j in (0, 1))


def assess(request: dict, response: dict, equivalent: tuple[dict, dict] | None = None) -> dict:
    result = {'schema': 'jev_contact_advisor/v9', 'can_write_n1': False,
              'can_approve_qa': False, 'semantic_verdict': None, 'reasons': []}
    try:
        answer = bound_answer(request, response)
        e = request['evidence']
        distance = boundary_distance(e['target_endpoint'], e['candidate']['points'], e['candidate'].get('closed', False))
        if distance is None:
            raise ValueError('missing deterministic geometry')
        reference = 'TOUCH' if distance <= 0.01 else 'SEPARATE'
        result.update(choice=answer.get('choice'), confidence=answer.get('confidence'),
                      deterministic_distance=distance, deterministic_choice=reference)
        if answer.get('choice') == 'INSUFFICIENT':
            result['reasons'].append('MODEL_ABSTAINED')
        elif answer.get('choice') != reference:
            result['reasons'].append('DETERMINISTIC_CONTRADICTION')
        if equivalent is None:
            result['reasons'].append('EQUIVALENCE_NOT_TESTED')
        else:
            other_request, other_response = equivalent
            other = bound_answer(other_request, other_response)
            if not translated_equivalent(request, other_request):
                raise ValueError('equivalent geometry binding failed')
            if other.get('choice') != answer.get('choice'):
                result['reasons'].append('REPRESENTATION_INSTABILITY')
            if other.get('choice') not in (reference, 'INSUFFICIENT'):
                result['reasons'].append('EQUIVALENT_DETERMINISTIC_CONTRADICTION')
            if other.get('choice') == 'INSUFFICIENT':
                result['reasons'].append('EQUIVALENT_ABSTAINED')
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        result['reasons'].append('INVALID_OR_UNBOUND_EVIDENCE')
        result['error'] = str(exc)
    result['decision'] = 'ADVISORY_ONLY' if not result['reasons'] else 'WITHHOLD_ADVICE'
    return result


def replay(folder: Path) -> dict:
    load = lambda p: json.loads(p.read_text(encoding='utf-8'))
    original = load(folder / 'atomic_contact/FREEZE.json')['cases']
    relative = load(folder / 'atomic_contact_relative/FREEZE.json')['cases']
    rows = []
    for index, case in enumerate(original, 1):
        req = case['request']
        match = next((r for r in relative if r['request']['identity'] == req['identity']
                      and r['request']['evidence']['candidate']['handle'] == req['evidence']['candidate']['handle']), None)
        equivalent = None
        if match is not None:
            relative_index = relative.index(match) + 1
            equivalent = (match['request'], load(folder / f'atomic_contact_relative/RESULT-{relative_index:02}.json'))
        rows.append({'case': index, **assess(req, load(folder / f'atomic_contact/RESULT-{index:02}.json'), equivalent)})
    return {'schema': 'jev_contact_advisor_replay/v9', 'new_api_calls': 0,
            'quality_gain_measured': False, 'cases': rows,
            'advisory_only': sum(r['decision'] == 'ADVISORY_ONLY' for r in rows),
            'withheld': sum(r['decision'] == 'WITHHOLD_ADVICE' for r in rows)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.folder)
    target = args.folder / 'ADVISOR-REPLAY.json'
    if target.exists():
        raise SystemExit('Refusing to overwrite a frozen replay')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'advisory_only': report['advisory_only'], 'withheld': report['withheld'], 'new_api_calls': 0}))
