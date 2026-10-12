"""Canonical development cycle: fresh preprocessing, full SA, post-SA CAD QA.

This entry point never publishes or renders. Exit 3 means unresolved findings;
the JSON report remains available for the next correction and complete rerun.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import uuid

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, payload):
    from portal.app.preprocessamento.runner import _write_atomic
    _write_atomic(Path(path), payload)


def snapshot_database(source, destination):
    """SQLite backup includes committed WAL content without editing the source."""
    with sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)


def protected_files(obra, db):
    """Guard current published runs and indices, avoiding historical renders."""
    production = obra / 'Fase-6_Execucao_CAD/production_sa'
    preprocessing = obra / 'preprocessamento/v1'
    paths = [db]
    for root in (production, preprocessing):
        if root.is_dir():
            paths.extend([root, *root.glob('*')])
    if production.is_dir():
        for floor in production.iterdir():
            if floor.is_dir():
                runs = sorted(p for p in floor.iterdir() if p.is_dir())
                if runs:
                    paths.extend([runs[-1], *runs[-1].rglob('*')])
    return {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in paths if p.exists() and p.suffix != '.lock'}


def runtime_source_hashes(repo=REPO):
    """Conservative code guard, including added/deleted runtime source files.

    Reports and rendered artifacts are outside the scope. Hash source bytes,
    not mtimes: another session can deploy while this isolated cycle runs.
    """
    repo = Path(repo)
    paths = set()
    for folder in (repo / 'src', repo / 'portal/app'):
        if folder.is_dir():
            paths.update(folder.rglob('*.py'))
    folder = repo / 'scripts/arete'
    if folder.is_dir():
        paths.update(folder.glob('*.py'))
    return {p.relative_to(repo).as_posix(): sha(p) for p in sorted(paths)
            if '__pycache__' not in p.parts}


@contextmanager
def canonical_locks(wait):
    from scripts.arete.headless_sa_analise import _headless_lock_plan, _release_headless_locks
    from scripts.arete.single_instance import acquire_lock, wait_for_lock
    acquire = wait_for_lock if wait else acquire_lock
    handles = []
    try:
        names, _ = _headless_lock_plan(None, None, False)
        for name in ['headless_sa', *names]:
            handle, holder = acquire(name)
            if handle is None:
                raise RuntimeError(f'Queue occupied: {name}: {holder}; use --wait')
            handles.append(handle)
        yield
    finally:
        _release_headless_locks(handles)


def run_cycle(*, obra, pav, db, output, project_id=None, input_manifest=None,
              baseline=None, baseline_state=None, wait=False,
              review_receipt=None, review_evidence=None, accepted_reviewers=None):
    if review_receipt and not accepted_reviewers:
        raise ValueError('An explicit accepted reviewer is required with a review receipt')
    from scripts.arete.sa_development_review import _json, assess_reviewed_cycle
    explicit_review = _json(review_receipt) if review_receipt else None
    code_before = runtime_source_hashes()
    from portal.app.preprocessamento.service import run_floor, read_floor, digest
    from portal.app.preprocessamento.context_resolver import convention_input
    from portal.app.preprocessamento.knowledge_qa import retrieve_context_qa
    from portal.app.qa_cad_gate_run import measure_state
    from scripts.arete.headless_sa_analise import run_analysis
    from src.core.sa_project_source import resolve_sa_project_from_db

    obra, db, output = Path(obra).resolve(), Path(db).resolve(), Path(output).resolve()
    if output == REPO or output == REPO.parent or output.is_relative_to(obra):
        raise ValueError('Output must be a new isolated directory outside the production work')
    if output.exists():
        raise FileExistsError('Use a new output directory for each complete cycle')
    seed = json.loads(Path(input_manifest).read_text(encoding='utf-8')) if input_manifest else read_floor(obra, pav)
    if not seed or seed.get('pavimento_id') != pav:
        raise ValueError('A matching canonical source manifest is required')
    declarations = seed.get('declarations') or [
        {'bruto_id': s['bruto_id'], 'item_id': s['item_id']}
        for s in seed['sources'] if s['kind'] != 'raw_level_reference']
    output.mkdir(parents=True)
    temporary_db = output / 'project_snapshot.sqlite3'
    started = time.perf_counter()
    timings = {}
    with canonical_locks(wait):
        # Begin the guarded interval after acquiring the queue. Publications by
        # the previous owner while we wait are not mutations by this cycle.
        before = protected_files(obra, db)
        database_hash = sha(db)
        snapshot_database(db, temporary_db)
        project = resolve_sa_project_from_db(str(temporary_db), str(obra), pav, project_id)
        source = Path(project['dxf_path']).resolve()
        source_hash = sha(source)
        stage = time.perf_counter()
        floor = run_floor(obra_dir=obra, obra_id=seed['obra_id'], pavimento=pav,
                          declarations=declarations, output_root=output / 'pre',
                          run_id=uuid.uuid4().hex,
                          progress=lambda event: print('[PRE]', event, flush=True))
        timings['preprocessing_s'] = time.perf_counter() - stage
        matching = [s for s in floor['sources'] if s['kind'] == 'tower'
                    and (obra / s['relative_path']).resolve() == source]
        if len(matching) != 1:
            raise ValueError('Project source must match exactly one fresh preprocessing tower')
        reference = floor['towers'][matching[0]['source_id']]
        package_path = output / 'pre' / pav / 'runs' / floor['run_id'] / reference['path']
        package = json.loads(package_path.read_text(encoding='utf-8'))
        if package['status'] == 'failed':
            raise RuntimeError(package.get('error', 'Preprocessing failed'))
        convention, reason = convention_input(package)
        context = {'schema': 'cad.sa.context/v1', 'context_run_id': floor['run_id'],
                   'scope': package['scope'], 'project_id': str(project['id']),
                   'obra_dir': str(obra), 'source_dxf': str(source),
                   'package_hash': digest(package), 'package': package,
                   'convention': convention, 'reason': reason,
                   'knowledge_qa': retrieve_context_qa(obra, package)}
        context['context_hash'] = digest(context)
        context_path = output / 'context.json'
        write(context_path, context)
        stage = time.perf_counter()
        result = run_analysis(str(obra), pav, project_id=str(project['id']),
                              db_path=str(temporary_db), run_diagnostics=False,
                              persist_db=False, generate_n3=False, production_web=True,
                              context_manifest=str(context_path), context_hash=context['context_hash'],
                              development=True, development_workspace=str(output))
        timings['sa_s'] = time.perf_counter() - stage
        receipt = result.get('preprocess_context') or {}
        if receipt.get('status') not in ('consumed', 'accepted_no_item_effect'):
            raise RuntimeError(f'Fresh context not consumed: {receipt}')
        state = result['analysis_state']
        stage = time.perf_counter()
        qa = measure_state(source, state, pav)
        timings['post_sa_qa_s'] = time.perf_counter() - stage
        regressions = []
        regressions.extend({'kind': 'pillar_detail_context', **entry}
                           for entry in receipt.get('pillar_detail_crosscheck', {}).get('blocked', []))
        regressions.extend({'kind': 'lateral_level_context', **entry}
                           for entry in receipt.get('segment_level_consumption', {}).get('blocked', []))
        comparison = None
        state_baseline = Path(baseline_state) if baseline_state else (
            Path(baseline).parent / 'analysis_state.json' if baseline else None)
        if state_baseline and state_baseline.is_file():
            from scripts.arete.sa_development_diff import compare_states
            previous_state = json.loads(state_baseline.read_text(encoding='utf-8'))
            comparison = compare_states(previous_state, state)
            for group in ('geometry_changes', 'numeric_changes', 'geometry_errors', 'contact_changes'):
                regressions.extend({'kind': group, **entry} for entry in comparison[group])
        else:
            regressions.append({'reason': 'spatial_regression_baseline_missing'})
        if baseline:
            previous = json.loads(Path(baseline).read_text(encoding='utf-8'))
            previous_qa = previous.get('qa', previous)
            for cls, bucket in previous_qa.get('classes', {}).items():
                current = qa.get('classes', {}).get(cls, {})
                for name, item in bucket.items():
                    if item.get('status') == 'confere' and current.get(name, {}).get('status') != 'confere':
                        regressions.append({'class': cls, 'item': name, 'reason': 'previously_confirmed_now_not_confirmed'})
        # Write exactly once: review hashes must refer to the final state bytes.
        write(output / 'analysis_state.json', state)
        assessment, regression_review = assess_reviewed_cycle(
            package, qa, regressions, explicit_review,
            source_path=source, baseline_state_path=state_baseline,
            current_state_path=output / 'analysis_state.json',
            evidence_paths=review_evidence or {}, accepted_reviewers=accepted_reviewers)
        after = protected_files(obra, db)
        changed = sorted(path for path in set(before) | set(after)
                         if before.get(path) != after.get(path))
        if database_hash != sha(db) and str(db) not in changed:
            changed.append(str(db))
        if source_hash != sha(source):
            changed.append(str(source))
        visual_files = [str(p.relative_to(output)) for p in output.rglob('*')
                        if p.suffix.lower() in ('.svg', '.png', '.html', '.pdf')]
        code_after = runtime_source_hashes()
        changed_code = sorted(path for path in set(code_before) | set(code_after)
                              if code_before.get(path) != code_after.get(path))
        isolation_failed = bool(changed or visual_files or changed_code)
        if isolation_failed:
            assessment['ready_for_publication'] = False
        timings['total_s'] = time.perf_counter() - started
        report = {'schema': 'cad.sa.development_cycle/v1', 'pavimento': pav,
                  'analysis_state_sha256': sha(output / 'analysis_state.json'),
                  'baseline_state_sha256': sha(state_baseline) if state_baseline and state_baseline.is_file() else None,
                  'source_sha256': source_hash, 'timings_s': timings,
                  'sa_timings_s': result['timings_s'], 'qa': qa, 'assessment': assessment,
                  'context_receipt': receipt, 'regressions': regressions,
                  'regression_review': regression_review,
                  'development_rendering': result.get('development_rendering'),
                  'spatial_comparison': comparison,
                  'runtime_code': {'status': 'changed' if changed_code else 'unchanged',
                                   'before_sha256': code_before, 'after_sha256': code_after,
                                   'changed_files': changed_code},
                  'isolation': {'status': 'failed' if isolation_failed else 'passed',
                                'guarded_files': len(before), 'changed_files': changed,
                                'changed_code_files': changed_code,
                                'rendered_files': visual_files, 'published': False}}
        write(output / 'cycle_report.json', report)
        if isolation_failed:
            raise RuntimeError(f'Isolation failed: changed={changed}, code={changed_code}, rendered={visual_files}; '
                               f'diagnostic report preserved: {output / "cycle_report.json"}')
        print(json.dumps({'timings_s': timings, 'ready_for_publication': assessment['ready_for_publication'],
                          'pending_count': assessment['pending_count'],
                          'report': str(output / 'cycle_report.json')}, ensure_ascii=False), flush=True)
        return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('obra', 'pav', 'db', 'out'):
        ap.add_argument('--' + name, required=True)
    ap.add_argument('--project-id')
    ap.add_argument('--input-manifest')
    ap.add_argument('--baseline')
    ap.add_argument('--baseline-state')
    ap.add_argument('--review-receipt')
    ap.add_argument('--review-evidence', action='append', default=[], metavar='ID=PATH')
    ap.add_argument('--reviewer', action='append', default=[])
    ap.add_argument('--wait', action='store_true')
    args = ap.parse_args()
    evidence = {}
    for entry in args.review_evidence:
        identity, separator, path = entry.partition('=')
        if not separator or not identity or not path or identity in evidence:
            ap.error('--review-evidence requires a unique nonempty ID=PATH')
        evidence[identity] = Path(path).resolve()
    if args.review_receipt and not args.reviewer:
        ap.error('--review-receipt requires at least one explicit --reviewer')
    os.environ.update(QT_QPA_PLATFORM='offscreen', CAD_MOTOR_HEADLESS='1',
                      CAD_SA_DISABLE_FAST_CACHE='1')
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(['dev_sa_cycle'])
    app.setQuitOnLastWindowClosed(False)
    report = run_cycle(obra=args.obra, pav=args.pav, db=args.db, output=args.out,
                       project_id=args.project_id, input_manifest=args.input_manifest,
                       baseline=args.baseline, baseline_state=args.baseline_state, wait=args.wait,
                       review_receipt=args.review_receipt, review_evidence=evidence,
                       accepted_reviewers=set(args.reviewer) if args.reviewer else None)
    return 0 if report['assessment']['ready_for_publication'] else 3


if __name__ == '__main__':
    sys.exit(main())
