"""Pre-SA level collection: scoped evidence, never a seal or SA mutation.

Segment ``level`` is a top/reference altitude in metres, including FV. It is
not the physical bottom altitude. Estimated levels keep their original flag.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

FAMILIES = ('fundo', 'lateral_a_para', 'lateral_b_para', 'lateral_a_passa', 'lateral_b_passa')
_LEVEL = re.compile(r'^(?:N[= ]*)?(-?\d+[.,]\d{1,2})$', re.I)


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(str(value).strip().replace(',', '.'))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_scoped_sa(root: Path, floor: str, package: dict) -> dict | None:
    """Reject another tower/revision; never look up old N3/Fase-4 by name."""
    source = next((s for s in package['sources'] if s['source_id'] == package['scope']['recorte_id']), None)
    if not source:
        return None
    tower = (root / source['relative_path']).resolve()
    if not tower.is_relative_to(root.resolve()) or not tower.is_file():
        return None
    if hashlib.sha256(tower.read_bytes()).hexdigest() != source['revision']:
        return None
    manifests = sorted((root / 'Fase-6_Execucao_CAD/production_sa' / floor).glob('*/production_manifest.json'))
    # The latest SA has to belong to this tower; an older run is not a fallback.
    if not manifests:
        return None
    manifest = _json(manifests[-1])
    if Path(manifest.get('source_dxf') or '').resolve() != tower:
        return None
    context = manifest.get('preprocess_context') or {}
    scope = context.get('scope') or {}
    if scope.get('source_revision') != source['revision'] or scope.get('recorte_id') != source['source_id']:
        return None
    state_path = Path(manifest.get('state_path') or '')
    if not state_path.resolve().is_relative_to(root.resolve()) or not state_path.is_file():
        return None
    state = _json(state_path)
    if state.get('pavimento') != floor:
        return None
    db_path = Path(state.get('db_path') or '')
    tables = {}
    if db_path.is_file():
        with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            conn.row_factory = sqlite3.Row
            for table in ('slabs', 'beams'):
                tables[table] = [dict(r) for r in conn.execute(
                    f'SELECT * FROM {table} WHERE project_id=?', (manifest['project_id'],))]
    return {'state': state, 'tables': tables, 'tower_path': tower,
            'evidence_id': str(manifests[-1].relative_to(root)), 'root': root, 'floor': floor}


def enrich_package(root: Path, floor: str, package: dict, progress=None):
    """Execute collection in the preprocessing JOB, then freeze facts in package."""
    inv = package['level_inventory']
    if (inv.get('reference') or {}).get('status') != 'direct_local_reference':
        return
    context = load_scoped_sa(root, floor, package)
    if context is not None:
        from src.core.slab_level_inference import point_inside_ring
        marks = plan_marks(context['tower_path'], inv['reference'])
        # A same-source snapshot can predate the corrected level collection.
        # Recollect if an unambiguous plan annotation differs or was missed.
        for slab in context['state'].get('slabs', []):
            values = {m['value'] for m in marks if point_inside_ring(slab.get('points'), tuple(m['pos']))}
            if len(values) == 1 and number(slab.get('nivel')) not in values:
                context = None
                break
    if context is None:
        # Reuse the canonical contextual SA collectors in a separate process.
        # No production DB, N3, Fase-4 or production state is written.
        import subprocess
        import sys
        import tempfile
        if progress:
            progress({'stage': 'collecting_sa_level_evidence', 'completed': 0, 'total': 1})
        source = next(s for s in package['sources'] if s['source_id'] == package['scope']['recorte_id'])
        with tempfile.TemporaryDirectory(prefix='pre-sa-levels-') as directory:
            output = Path(directory) / 'evidence.json'
            script = Path(__file__).resolve().parents[3] / 'scripts/preprocessamento_coleta_niveis.py'
            subprocess.run([sys.executable, str(script), '--dxf', str(root/source['relative_path']),
                '--obra', str(root), '--pav', floor, '--out', str(output),
                '--reference', json.dumps(inv['reference'])], check=True, timeout=1800)
            context = _json(output)
        context.update(root=root, floor=floor, tower_path=root/source['relative_path'],
                       evidence_id='pre-sa-canonical-collection:'+source['revision'])
    facts = defaultdict(list)
    for f in package['levels']:
        facts[f['item_id']].append(f)
    segments = defaultdict(list)
    for s in inv.get('beam_segments', []):
        segments[s['beam_item_id']].append(s)
    view = {'reference': inv['reference'], 'items': [{**i, 'levels': facts[i['item_id']],
            'segments': segments[i['item_id']]} for i in inv['items']]}
    resolved = merge_sa_levels(view, context)
    package['pre_sa_survey_levels'] = package['levels']
    package['levels'] = [f for i in resolved['items'] for f in i['levels']]
    inv['items'] = [{k:v for k,v in i.items() if k not in ('levels','segments')} for i in resolved['items']]
    inv['beam_segments'] = [{**s, 'beam_item_id': i['item_id']} for i in resolved['items'] for s in i['segments']]
    inv['sa_evidence'] = resolved['sa_evidence']
    inv['segment_coverage'] = {'collected_segments': resolved['sa_evidence']['segments'],
        'estimated_segments': sum(s['status']=='estimated' for s in inv['beam_segments'])}
    package['modules']['levels'] = 'evidence_collected'


def item_level_input(package):
    """Only single, contained CAD levels may replace automatic SA guesses."""
    names = {i['item_id']:i['display_name'] for i in package.get('level_inventory', {}).get('items', [])
             if i['item_class'] == 'slab'}
    groups = defaultdict(list)
    for fact in package.get('levels', []):
        if fact.get('field') == 'slab_level' and fact.get('method') == 'cad_level_inside_slab':
            groups[names.get(fact['item_id'])].append(fact)
    result = {}
    for name, facts in groups.items():
        values = {f['value'] for f in facts if f.get('value') is not None}
        if name and len(values) == 1:
            result[name] = {'value': next(iter(values)), 'unit': 'm',
                            'positions': [p for f in facts for p in f.get('positions', [])],
                            'evidence_ids': sorted({e for f in facts for e in f['evidence_ids']})}
    return result


def consume_item_levels(slabs, levels):
    """Attach proven pre-SA values before the normal SA contextual inference."""
    from src.core.slab_level_inference import point_inside_ring
    consumed = []
    for slab in slabs:
        name = slab.get('name')
        row = levels.get(name)
        if not row or row.get('unit') != 'm' or number(row.get('value')) is None:
            continue
        validated = slab.get('validated_fields') or []
        if 'laje_nivel' in validated or 'level' in validated:
            continue
        if not row.get('positions') or not all(point_inside_ring(slab.get('points'), tuple(p)) for p in row['positions']):
            continue
        links = slab.setdefault('links', {}).setdefault('laje_nivel', {})
        slots = (slab.get('validated_link_classes') or {}).get('laje_nivel') or []
        if 'label' in slots or any(l.get('human') or l.get('validated') or l.get('source') == 'human' for l in links.get('label', []) if isinstance(l, dict)):
            continue
        value = row['value']
        slab.setdefault('fields', {})['laje_nivel'] = str(value)
        slab['laje_nivel'] = str(value)
        links['label'] = [{'text': str(value), 'type': 'text', 'source': 'preprocess_contained_cad_level',
                           'is_inferred': False, 'evidence_ids': row['evidence_ids']}]
        slab['preprocess_level_evidence'] = deepcopy(row)
        slab['level_inference'] = {'status': 'observed', 'reason': 'preprocess_contained_cad_level',
                                   'value': value, 'evidence_ids': row['evidence_ids']}
        consumed.append({'item': name, 'field': 'laje_nivel', 'value': value, 'evidence_ids': row['evidence_ids']})
    return consumed


def plan_marks(path, reference):
    """Only local absolute altitude marks, with CAD handles and coordinates."""
    import ezdxf
    top, height = number(reference.get('top')), number(reference.get('height'))
    if reference.get('unit') != 'm' or top is None or not height:
        return []
    rows = []
    for entity in ezdxf.readfile(path).modelspace().query('TEXT MTEXT'):
        raw = entity.dxf.text if entity.dxftype() == 'TEXT' else entity.plain_text()
        match = _LEVEL.fullmatch(raw.strip())
        if match:
            value = number(match.group(1))
            if value is not None and abs(value - top) <= abs(height) * .25:
                rows.append({'value': value, 'text': raw, 'pos': list(entity.dxf.insert)[:2],
                             'handle': entity.dxf.handle})
    return rows


def merge_sa_levels(tower: dict, context: dict) -> dict:
    """Preserve pre-SA evidence alongside actual SA segment identities."""
    from src.core.slab_level_inference import point_inside_ring
    from src.core.pillar_sa_review import load as load_review
    out = deepcopy(tower)
    state, reference = context['state'], out.get('reference') or {}
    datum = reference.get('datum_id')
    source = context['evidence_id']
    marks = context.get('marks')
    if marks is None:
        marks = plan_marks(context['tower_path'], reference)
    slabs = {s['name']: s for s in state.get('slabs', [])}
    pillars = {p['name']: p for p in state.get('pilares', [])}
    segments = defaultdict(list)
    for family in FAMILIES:
        for seg in (state.get('segmentos') or {}).get(family, []):
            segments[seg['beam_name']].append((family, seg))
    slab_db = {s['name']: s for s in context.get('tables', {}).get('slabs', [])}
    beam_db = {s['name']: json.loads(s['data_json']) for s in context.get('tables', {}).get('beams', [])}
    level_report = (context.get('level_report') or {}).get('lajes') or {}
    slab_quality = {}
    for slab_name, slab in slabs.items():
        direct_values = {m['value'] for m in marks if point_inside_ring(slab.get('points'), tuple(m['pos']))}
        slab_quality[slab_name] = ('observed' if len(direct_values)==1 else
                                   'multiple_parts' if direct_values else 'inferred')

    def fact(item, field, value, method, status='sa_evidence', evidence=(), warnings=(), **extra):
        return {'item_id': item['item_id'], 'fact_id': f"{item['item_id']}:{field}:{len(item['levels'])}",
                'field': field, 'value': number(value), 'unit': 'm', 'datum_id': datum,
                'status': status, 'method': method, 'evidence_ids': [source, *evidence],
                'warnings': list(warnings), **extra}

    # Pre-SA repeats labels; only one SA record per class/name, IDs stay traceable.
    seen = set()
    for item in out['items']:
        name, cls = item['display_name'], item['item_class']
        key = (cls, name)
        if key in seen:
            continue
        seen.add(key)
        original = item['levels']
        item['pre_sa_levels'] = original
        item['levels'] = []
        if cls == 'slab' and name in slabs:
            slab = slabs[name]
            direct = [m for m in marks if point_inside_ring(slab.get('points'), tuple(m['pos']))]
            values = sorted({m['value'] for m in direct})
            row = slab_db.get(name) or {}
            extra = json.loads(row.get('extra_data_json') or '{}')
            inference = extra.get('level_inference') or {}
            stored = number(slab.get('nivel'))
            report = level_report.get(name) or {}
            confidence = number(report.get('confidence'))
            for value in values:
                selected = [m for m in direct if m['value'] == value]
                item['levels'].append(fact(item, 'slab_level', value, 'cad_level_inside_slab',
                    evidence=[f"cad:{m['handle']}" for m in selected], positions=[m['pos'] for m in selected],
                    warnings=['multiple_plan_levels_require_part_review'] if len(values) > 1 else []))
                if number(report.get('level')) == value and confidence is not None and 0 <= confidence <= 1:
                    item['levels'][-1].update(confidence_pct=confidence*100,
                        confidence_method='canonical_sa_level_evidence_score_not_calibrated_probability')
            if stored is not None and stored not in values:
                warning = ['sa_differs_from_contained_plan_level'] if values else ['inferred_level_requires_review']
                item['levels'].append(fact(item, 'slab_level', stored, inference.get('reason') or 'sa_slab_level',
                    status='conflict' if values else 'inferred', warnings=warning, inference=inference))
                if confidence is not None and 0 <= confidence <= 1:
                    item['levels'][-1].update(confidence_pct=confidence*100,
                        confidence_method='canonical_sa_level_evidence_score_not_calibrated_probability')
            if not item['levels']:
                item['levels'] = original
            # Keep rejected alternatives visible. A stored automatic value is
            # not a resolution of contradictory cut evidence.
            item['level_review'] = deepcopy(inference)
            for candidate in inference.get('candidates') or []:
                proposed = number(candidate.get('value'))
                if proposed is None:
                    continue
                differing = any(f.get('value') is not None and abs(f['value']-proposed) > .0025 for f in item['levels'])
                if not differing:
                    continue
                item['levels'].append(fact(item, 'slab_level_candidate', proposed,
                    candidate.get('method') or 'cut_candidate', status='candidate',
                    evidence=['slab:'+str(candidate.get('source_slab') or '')],
                    warnings=['unresolved_cut_level_alternative'], inference=deepcopy(candidate)))
                for f in item['levels']:
                    if f['field']=='slab_level' and f['status']=='inferred':
                        f['warnings'].append('unresolved_cut_level_alternative')
            # Never replace level confidence by the slab GEOMETRY confidence.
        elif cls == 'pillar' and name in pillars:
            pillar = pillars[name]
            manual = load_review(context['root'], context['floor'], name) if context.get('root') else {}
            classification = manual.get('classificacao', pillar.get('classification'))
            item['classification'] = classification
            for field, refkey, humankey in [('base', 'base', 'nivel_saida'), ('top', 'top', 'nivel_chegada')]:
                if humankey in manual:
                    item['levels'].append(fact(item, field, manual[humankey], 'human_sa_review', status='human_review'))
                elif classification == 'NASCE':
                    item['levels'].append(fact(item, field, None, 'nasce_outside_current_storey', status='not_applicable',
                        warnings=['pillar_belongs_to_next_storey'], floor_reference=reference.get(refkey)))
                else:
                    item['levels'].append(fact(item, field, reference.get(refkey), 'scoped_floor_convention',
                        status='floor_reference', warnings=['storey_reference_not_individual_measurement']))
            # Preserve all levels on the pillar faces, never collapse to global max.
            for face, groups in ((pillar.get('interpretacao_abcd') or {}).get('faces', {}) if classification != 'NASCE' else {}).items():
                for family, rows in groups.items():
                    if not isinstance(rows, list):
                        continue
                    for row in rows:
                        raw = str(row.get('nivel') or '').replace('cm', '').strip()
                        value = number(raw)
                        if value is not None and number(reference.get('top')) is not None and abs(value-reference['top']) <= 6:
                            item['levels'].append(fact(item, 'face_'+face, value, 'sa_face_contact',
                                status='inferred', warnings=['face_contact_requires_review'],
                                linked_item=row.get('nome'), face=face, family=family))
        elif cls == 'beam' and name in segments:
            item['segments'] = []
            beam = beam_db.get(name) or {}
            fields = beam.get('fields') or {}
            for family, seg in segments[name]:
                value = number(seg.get('level'))
                method = seg.get('level_source') or 'unresolved'
                estimated = 'estim' in method or 'nearest' in method
                warnings = ['estimated_not_measured'] if estimated else []
                linked = seg.get('level_slabs') or []
                # Propagate weak/conflicting slab evidence to its consumers.
                if any((json.loads((slab_db.get(n) or {}).get('extra_data_json') or '{}').get('level_inference') or {}).get('status') == 'needs_review' for n in linked):
                    warnings.append('source_slab_requires_review')
                if any(slab_quality.get(n) != 'observed' for n in linked):
                    warnings.append('source_slab_level_not_uniquely_observed')
                if method == 'explicit_beam_or_side' and not linked:
                    warnings.append('automatic_beam_field_without_cad_level_provenance')
                state_status = 'estimated' if estimated else 'inferred' if warnings else 'sa_evidence'
                record = fact(item, family, value, method, status='estimated' if estimated else 'sa_evidence',
                    evidence=[seg['uid'], *['slab:'+n for n in linked]], warnings=warnings,
                    segment_id=seg['uid'], segment_label=seg.get('segment_label'), source_slabs=linked)
                record['status'] = state_status
                item['levels'].append(record)
                segment = {**seg, 'segment_id': seg['uid'], 'family': family, 'unit': 'm',
                           'status': record['status'], 'warnings': warnings, 'evidence_ids': record['evidence_ids']}
                # FV height uses its own dimension slot, not an unrelated LV slot.
                if family == 'fundo':
                    dim = fields.get('viga_fundo_seg_'+str(seg.get('segment_label'))+'_dim')
                    match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*', str(dim or ''))
                    height = number(match.group(2)) if match else None
                    if height is not None and value is not None:
                        bottom = round(value - height / 100, 4)
                        segment.update(bottom_level=bottom, height_cm=height)
                        item['levels'].append(fact(item, 'beam_bottom', bottom, 'fv_reference_minus_depth_cm',
                            status=record['status'], evidence=[seg['uid'], 'beam:'+name+':'+str(dim)],
                            warnings=warnings, segment_id=seg['uid'], height_cm=height))
                item['segments'].append(segment)
        else:
            item['levels'] = original
        # A duplicate survey label carries only its own old observations.
    for item in out['items']:
        key = (item['item_class'], item['display_name'])
        if 'pre_sa_levels' not in item and key in seen:
            item['pre_sa_levels'] = item['levels']
            item['levels'] = []
            item['segments'] = []
    unique = [i for i in out['items'] if i.get('levels')]
    counts = Counter(f['status'] for i in unique for f in i['levels'])
    out['sa_evidence'] = {'source': source, 'status_counts': dict(counts),
        'items_with_levels': sum(any(f.get('value') is not None for f in i['levels']) for i in unique),
        'items_not_applicable': sum(all(f['status'] == 'not_applicable' for f in i['levels']) for i in unique),
        'segments': sum(len(i['segments']) for i in unique if i['item_class'] == 'beam')}
    return out
