"""Bounded canonical retrieval, reopened evidence, no SA self-confirmation."""
import json
import sqlite3
import time
from pathlib import Path


def retrieve_context_qa(root, package):
    started = time.monotonic()
    scope = package['scope']
    app = Path(__file__).resolve().parents[3]
    db = app/'KB-GLOBAL/obras'/f"{scope['obra_id']}.sqlite"
    result = {'status': 'not_available', 'mode': 'canonical_fts_scoped_once_per_run',
              'numeric_authority': False, 'independent_confirmation': False,
              'hits': [], 'rejected': 0, 'rejection_reasons': {}}
    def reject(reason):
        result['rejected'] += 1
        reasons = result['rejection_reasons']
        reasons[reason] = reasons.get(reason, 0) + 1
    if not db.is_file():
        return result
    try:
        from scripts.kb.kb_query import busca_texto
        from .service import digest
        seen_paths = set()
        package_hash = digest(package)
        with sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True) as conn:
            ids = busca_texto(conn, 'nivel convencao piso TIPO pilares',
                              ' AND instr(c.path, ?) > 0 AND instr(c.path, ?) > 0',
                              ['/pavimentos/'+scope['pavimento_id']+'/', '/preprocessamento/'])
            for cid in ids:
                row = conn.execute('SELECT path FROM chunks WHERE id=?', (cid,)).fetchone()
                if not row:
                    continue
                indexed_path = Path(row[0])
                # The canonical builder stores paths relative to REPO.parent.
                path = (indexed_path if indexed_path.is_absolute() else app.parent/indexed_path).with_suffix('.json').resolve()
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                if Path(root).resolve() not in path.parents:
                    reject('outside_work_root')
                    continue
                # A missing or damaged sidecar must not hide valid later hits.
                try:
                    source = json.loads(path.read_text(encoding='utf-8'))
                    if not isinstance(source, dict):
                        raise ValueError('source_not_object')
                    provenance = source.get('provenance') or {}
                    if not isinstance(provenance, dict) or not all(
                        provenance.get(key) for key in ('run_id', 'source_revision', 'package_hash')
                    ):
                        raise ValueError('incomplete_provenance')
                except (OSError, ValueError, TypeError):
                    reject('missing_or_invalid_provenance')
                    continue
                if source.get('scope') != {'obra_id': scope['obra_id'], 'pavimento_id': scope['pavimento_id']}:
                    reject('scope_mismatch')
                    continue
                exact_package = provenance['package_hash'] == package_hash
                # Fresh runs have different package hashes even for identical
                # CAD sources. Reopen that history only as a consultation pointer,
                # never as current evidence or another independent confirming vote.
                if not exact_package and not (
                    scope.get('recorte_id') and scope.get('source_revision')
                    and provenance.get('recorte_id') == scope['recorte_id']
                    and provenance['source_revision'] == scope['source_revision']
                    and package.get('sources')
                    and provenance.get('sources') == package['sources']
                ):
                    reject('package_or_source_lineage_mismatch')
                    continue
                if str(path) not in {h['path'] for h in result['hits']}:
                    result['hits'].append({'path': str(path), 'run_id': provenance['run_id'],
                                           'source_revision': provenance['source_revision'],
                                           'status': ('reopened_current_pre_sa_evidence' if exact_package
                                                      else 'historical_same_sources_consultation'),
                                           'numeric_authority': False,
                                           'independent_confirmation': False})
                if len(result['hits']) >= 8:
                    break
        result['status'] = ('verified' if any(h['status'] == 'reopened_current_pre_sa_evidence'
                                             for h in result['hits']) else
                            'historical_reference_available' if result['hits'] else 'no_current_evidence')
    except (OSError, ValueError, KeyError, sqlite3.Error, ImportError) as exc:
        result.update(status='unavailable', error=type(exc).__name__)
    result['elapsed_ms'] = round((time.monotonic()-started)*1000, 2)
    return result
