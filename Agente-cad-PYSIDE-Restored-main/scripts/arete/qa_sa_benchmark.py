"""Measure SA audit decisions against a separate, hashed reference corpus.

No reference is inferred from an agent's opinion. Missing predictions remain in
the denominator. This command never changes SA or certifies a class.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from portal.app.qa_measurement import decisions

CLASSES = {'PIL', 'LAJ', 'FV', 'LV'}
OUTCOMES = {'pass', 'fail', 'inconclusive', 'technical_failure'}
IDENTITY = ('case_id', 'classe', 'behavior', 'unit_id', 'criterion', 'source_sha256')


def _key(row):
    if any(not isinstance(row.get(k), str) or not row[k].strip() for k in IDENTITY):
        raise ValueError('identidade incompleta do caso/critério')
    if row['classe'] not in CLASSES or row['behavior'] not in {'para', 'passa'}:
        raise ValueError('classe/comportamento inválido')
    if len(row['source_sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['source_sha256']):
        raise ValueError('hash da interpretação-fonte inválido')
    return tuple(row[k] for k in IDENTITY)


def _artifact(base, proof):
    relative = Path(proof.get('path', ''))
    if relative.is_absolute() or not proof.get('path'):
        raise ValueError('prova deve ter caminho relativo ao corpus')
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('prova fora do corpus')
    if hashlib.sha256(path.read_bytes()).hexdigest() != proof.get('sha256'):
        raise ValueError('prova mudou: hash incompatível')


def evaluate(corpus, predictions, *, base):
    if corpus.get('schema') != 'cad.qa.sa.reference/v1':
        raise ValueError('schema de referência inválido')
    if corpus.get('split') != 'held_out':
        raise ValueError('medição exige corpus reservado, separado do desenvolvimento')
    if predictions.get('schema') != 'cad.qa.sa.predictions/v1':
        raise ValueError('schema de previsões inválido')
    expected = {}
    for row in corpus.get('cases', []):
        key = _key(row)
        if key in expected:
            raise ValueError('referência duplicada')
        if type(row.get('reference_correct')) is not bool:
            raise ValueError('sem referência independente binária; adjudicar antes de medir')
        if row.get('reference_origin') not in {'human_adjudication', 'independent_cad_measurement'}:
            raise ValueError('origem da referência não independente')
        if not row.get('reviewer') or not row.get('reviewed_at') or not row.get('method'):
            raise ValueError('referência sem responsável, data ou método')
        if row.get('reference_origin') == 'human_adjudication' and row.get('human_label_verified') is not True:
            raise ValueError('adjudicação humana não confirmada')
        if not row.get('proofs'):
            raise ValueError('referência sem provas')
        for proof in row['proofs']:
            _artifact(base, proof)
        expected[key] = row
    if not expected:
        raise ValueError('corpus vazio; não há acurácia a medir')
    observed = {}
    for row in predictions.get('rows', []):
        key = _key(row)
        if key in observed:
            raise ValueError('previsão duplicada')
        if key not in expected:
            raise ValueError('previsão sem referência ou hash-fonte incompatível')
        if row.get('assessment') not in OUTCOMES or not row.get('round_id'):
            raise ValueError('previsão sem veredito ou execução identificada')
        observed[key] = row
    groups, details = {}, []
    for key, reference in expected.items():
        prediction = observed.get(key)
        row = dict(reference_correct=reference['reference_correct'],
                   human_label_verified=reference.get('human_label_verified') is True,
                   assessment=prediction['assessment'] if prediction else 'technical_failure')
        group = reference['classe'] + (':' + reference['behavior'] if reference['classe'] == 'LV' else '')
        groups.setdefault(group, []).append(row)
        details.append({k: reference[k] for k in IDENTITY} | row |
                       {'round_id': prediction.get('round_id') if prediction else None,
                        'missing_prediction': prediction is None})
    reports = {name: decisions(rows) for name, rows in groups.items()}
    for name, rows in groups.items():
        reports[name]['reference_positive'] = sum(r['reference_correct'] for r in rows)
        reports[name]['reference_negative'] = sum(not r['reference_correct'] for r in rows)
    return {'schema': 'cad.qa.sa.benchmark/v1', 'split': 'held_out',
            'unit_of_measurement': 'decisões por critério; não acurácia por item',
            'by_class': reports, 'details': details,
            'missing_classes': sorted({'PIL', 'LAJ', 'FV', 'LV:para', 'LV:passa'} - groups.keys()),
            'missing_predictions': len(expected) - len(observed),
            'calibrated_confidence': False, 'certified': False,
            'limitation': 'Rótulos e independência precisam de auditoria humana; hashes provam integridade, não verdade. Critérios do mesmo item são correlacionados; intervalos não certificam generalização.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(json.loads(args.corpus.read_text(encoding='utf-8')),
                      json.loads(args.predictions.read_text(encoding='utf-8')),
                      base=args.corpus.parent)
    report['corpus_sha256'] = hashlib.sha256(args.corpus.read_bytes()).hexdigest()
    report['predictions_sha256'] = hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
