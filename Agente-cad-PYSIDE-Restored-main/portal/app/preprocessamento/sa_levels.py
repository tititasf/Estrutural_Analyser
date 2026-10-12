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


def enrich_package(root: Path, floor: str, package: dict, progress=None, *, evidence_root=None):
    """Execute collection in the preprocessing JOB, then freeze facts in package."""
    inv = package['level_inventory']
    # A referência absoluta pode estar ausente. Ainda coletamos geometrias,
    # segmentos e cortes; os consumidores mantêm cotas sem prova como None.
    # An old SA snapshot has no proof of the current collectors or their
    # prerequisite conventions. Every requested preprocessing run recollects.
    context = None
    if context is None:
        # Reuse the canonical contextual SA collectors in a separate process.
        # No production DB, N3, Fase-4 or production state is written.
        import subprocess
        import sys
        import tempfile
        if progress:
            progress({'stage': 'collecting_sa_level_evidence', 'completed': 0, 'total': 1})
        source = next(s for s in package['sources'] if s['source_id'] == package['scope']['recorte_id'])
        tower_path = (root/source['relative_path']).resolve()
        if not tower_path.is_relative_to(root.resolve()) or hashlib.sha256(tower_path.read_bytes()).hexdigest() != source['revision']:
            raise ValueError('collection_source_revision_mismatch')
        from .context_resolver import convention_input
        convention, convention_reason = convention_input(package)
        with tempfile.TemporaryDirectory(prefix='pre-sa-levels-') as directory:
            output = Path(directory) / 'evidence.json'
            script = Path(__file__).resolve().parents[3] / 'scripts/preprocessamento_coleta_niveis.py'
            subprocess.run([sys.executable, str(script), '--dxf', str(root/source['relative_path']),
                '--obra', str(root), '--pav', floor, '--out', str(output),
                '--reference', json.dumps(inv['reference']),
                '--convention', json.dumps(convention)], check=True, timeout=1800)
            context = _json(output)
        from .runner import _write_atomic
        evidence_base = Path(evidence_root).resolve() if evidence_root is not None else root
        evidence_path = evidence_base/'preprocessamento/v1/collection_evidence'/package['run_id']/(source['revision']+'.json')
        _write_atomic(evidence_path, context)
        package['collection_evidence'] = {
            'relative_path': str(evidence_path.relative_to(evidence_base)),
            'sha256': hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            'source_revision': source['revision'], 'scope': deepcopy(package['scope'])}
        context.update(root=root, floor=floor, tower_path=root/source['relative_path'],
                       evidence_id='pre-sa-canonical-collection:'+source['revision'])
        context['convention_reason'] = convention_reason
    from .adapters.named_section_slabs import resolve_named_section_slabs
    context['named_section_slab_levels'] = resolve_named_section_slabs(root, package, context)
    package['named_section_slab_levels'] = deepcopy(context['named_section_slab_levels'])
    # A saved tower may still contain an enlarged detail. Derive its region
    # read-only; the adapter must prove dimensions before it can change roles.
    from .adapters.local_pillar_details import inventory_declared_details
    context['local_pillar_details'] = inventory_declared_details(
        root, package, context['tower_path'], context['state'].get('pilares', []))
    package['local_pillar_details'] = deepcopy(context['local_pillar_details'])
    from .adapters.sheet_frames import inventory_sheet_frames
    context['sheet_frames'] = inventory_sheet_frames(context['tower_path'])
    package['sheet_frames'] = deepcopy(context['sheet_frames'])
    from .adapters.dimensioned_section_profiles import inventory_dimensioned_section_profiles
    context['dimensioned_section_profiles'] = inventory_dimensioned_section_profiles(context['tower_path'])
    package['dimensioned_section_profiles'] = deepcopy(context['dimensioned_section_profiles'])
    from .adapters.source_role_reviews import inventory_source_role_reviews
    context['source_role_reviews'] = inventory_source_role_reviews(
        context['tower_path'], context['state'].get('slabs', []))
    package['source_role_reviews'] = deepcopy(context['source_role_reviews'])
    facts = defaultdict(list)
    for f in package['levels']:
        facts[f['item_id']].append(f)
    segments = defaultdict(list)
    for s in inv.get('beam_segments', []):
        segments[s['beam_item_id']].append(s)
    positions = {i['item_id']: i['label_position']
                 for i in (package.get('structural_labels') or {}).get('items') or []
                 if i.get('label_position')}
    view = {'reference': inv['reference'], 'items': [{**i, 'levels': facts[i['item_id']],
            'segments': segments[i['item_id']],
            **({'label_position': positions[i['item_id']]} if i['item_id'] in positions else {})}
            for i in inv['items']]}
    original_labels = {i['item_id']: i for i in
                       (package.get('structural_labels') or {}).get('items', [])}
    for item in view['items']:
        if item['item_class'] == 'beam' and item['item_id'] in original_labels:
            item['source_entity_handles'] = deepcopy(
                original_labels[item['item_id']].get('source_entity_handles') or [])
    # Survey identities alone are insufficient: a nearby pillar label can
    # also have been assigned to a slab region or a section glyph.
    pillar_geometry = pillar_survey_geometry((package.get('pillars') or {}).get('items', []))
    # The footprint adapter may union handles. Such normalized equality cannot
    # prove that the original serialized records were identical.
    original_records = defaultdict(list)
    for survey in (package.get('pillars') or {}).get('items', []):
        original_records[survey['item_id']].append(survey)
    context['nonidentical_original_item_ids'] = {
        identity for identity, records in original_records.items()
        if any(record != records[0] for record in records[1:])}
    for item in view['items']:
        if item['item_class'] == 'pillar' and item['item_id'] in pillar_geometry:
            survey = pillar_geometry[item['item_id']]
            for key in ('geometry', 'source_entity_handles', 'coordinate_system'):
                item[key] = deepcopy(survey.get(key))
    resolved = merge_sa_levels(view, context)
    package['pre_sa_survey_levels'] = package['levels']
    package['levels'] = [f for i in resolved['items'] for f in i['levels']]
    package['levels'].extend(resolved.get('floor_level_sources', []))
    from .canonical_inventory import coverage
    inv['survey_coverage'] = deepcopy(inv.get('coverage') or {})
    inv['coverage'] = {**inv['survey_coverage'], **coverage(resolved['items'])}
    inv['coverage']['slab_levels_observed'] = resolved['sa_evidence']['slabs_with_plan_levels']
    inv['items'] = [resolved_inventory_item(i) for i in resolved['items']]
    inv['beam_segments'] = [{**s, 'beam_item_id': i['item_id']} for i in resolved['items'] for s in i['segments']]
    inv['rejected_cut_level_evidence'] = resolved.get('rejected_cut_level_evidence', [])
    # CAD-cut hops and the per-fact explanation summary keep chains resolvable.
    inv['cut_level_facts'] = resolved.get('cut_level_facts', [])
    inv['evidence_provenance'] = resolved.get('evidence_provenance', {})
    # Slab layers: applied votes and the ones withheld (tie, differs from SA).
    inv['slab_level_layers'] = resolved.get('slab_level_layers', {})
    inv['sa_evidence'] = resolved['sa_evidence']
    inv['sa_evidence']['convention_reason'] = context.get('convention_reason')
    inv['sa_evidence']['convention_consumer_calls'] = context.get('context_calls', [])
    inv['segment_coverage'] = {'collected_segments': resolved['sa_evidence']['segments'],
        'estimated_segments': sum(s['status']=='estimated' for s in inv['beam_segments']),
        'estimated_ranges': sum(r.get('status')=='estimated' for s in inv['beam_segments']
                                for r in s.get('level_ranges', [])),
        'segments_with_estimated_ranges': sum(any(r.get('status')=='estimated'
            for r in s.get('level_ranges', [])) for s in inv['beam_segments'])}
    package['modules']['levels'] = 'evidence_collected'
    package['beam_sections'] = deepcopy(context.get('beam_sections') or {})
    package['modules']['beam_sections'] = ('evidence_collected' if package['beam_sections']
                                          else 'not_available')
    # Only original CAD polygons enter the explicit-cut source union. Generated
    # A/B sections stay in their own inventory and cannot turn into CAD evidence.
    existing = package.setdefault('cuts', {}).setdefault('items', [])
    seen = {i.get('item_id') for i in existing}
    for entry in package['beam_sections'].get('entries', []):
        raw = entry.get('source_cut')
        if entry['kind'] != 'identified' or not raw or raw.get('uid') in seen:
            continue
        existing.append({**deepcopy(raw), 'item_id': raw.get('uid'),
                         'section_geometry': {'points': raw.get('pts') or raw.get('points')},
                         'source_id': package['scope']['recorte_id']})
        seen.add(raw.get('uid'))
    package['cuts']['capability'] = 'explicit_cad_and_canonical_sa_evidence'


def resolved_inventory_item(item):
    """Index the current collected facts, preserving survey IDs in pre_sa_levels."""
    result = {k:v for k,v in item.items() if k not in ('levels','segments')}
    result['level_fact_ids'] = [f['fact_id'] for f in item.get('levels', [])]
    result['segment_ids'] = [s['segment_id'] for s in item.get('segments', [])]
    return result


def item_level_input(package):
    """Export contained CAD marks or geometrically scoped, proven cut deltas."""
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
                            'evidence_ids': sorted({e for f in facts for e in f['evidence_ids']}),
                            'cad_marks': [deepcopy(m) for f in facts for m in f.get('cad_marks', [])]}
    index={f['fact_id']:f for f in package.get('levels', [])}
    for f in package.get('levels', []):
        name=names.get(f.get('item_id'))
        if (not name or name in result or f.get('field')!='slab_level'
                or f.get('method')!='scoped_cut_wing_relative_delta_cm'
                or f.get('status') not in ('sa_evidence','inferred') or not f.get('target_geometry')):
            continue
        proofs=f.get('cut_region_evidence') or []
        if not proofs or any(p.get('source_fact_id') not in index for p in proofs):
            continue
        from .level_provenance import walk, origin_kind
        roots, cycles, missing = walk(f['fact_id'], index)
        if (cycles or missing or not roots or any(origin_kind(r) not in
                ('cad_direct_level','cad_named_section_level','human_review') for r in roots)):
            continue
        if any(index[p['source_fact_id']].get('status') in ('estimated','conflict','unknown','candidate')
            or number(index[p['source_fact_id']].get('value')) is None
            or number(p.get('delta_cm')) is None
            or abs(index[p['source_fact_id']]['value']+p['delta_cm']/100-f['value'])>.0025 for p in proofs):
            continue
        competing=[r for r in package['levels'] if r.get('item_id')==f['item_id']
            and r.get('field') in ('slab_level','slab_level_candidate') and r.get('value') is not None]
        if any(abs(r['value']-f['value'])>.0025 or r.get('status') in ('conflict','candidate') for r in competing):
            continue
        result[name]={k:deepcopy(f[k]) for k in ('value','unit','evidence_ids','confidence_pct',
            'source_fact_ids','cut_region_evidence','target_geometry','method')}
    from .adapters.named_section_slabs import METHOD as named_section_method
    for f in package.get('levels', []):
        name = names.get(f.get('item_id'))
        if (not name or name in result or f.get('method') != named_section_method
                or f.get('status') != 'sa_evidence' or not f.get('target_geometry')):
            continue
        competing = [r for r in package['levels'] if r.get('item_id') == f['item_id']
                     and r.get('field') in ('slab_level', 'slab_level_candidate')
                     and r.get('value') is not None]
        if any(abs(r['value']-f['value']) > .0025 or r.get('status') in ('conflict', 'candidate') for r in competing):
            continue
        result[name] = {k: deepcopy(f[k]) for k in ('value', 'unit', 'evidence_ids',
                      'confidence_pct', 'target_geometry', 'method', 'source_fact_ids')}
    # NIV-LAJE-CAMADAS-20261003: the owner's convention for a slab without its
    # own mark. Exported as inferred; never over a CAD mark or measured cut.
    for f in package.get('levels', []):
        name=names.get(f.get('item_id'))
        if (not name or name in result or f.get('field')!='slab_level'
                or f.get('method') not in LAYERED_METHODS or f.get('status')!='inferred'
                or number(f.get('value')) is None):
            continue
        competing=[r for r in package['levels'] if r.get('item_id')==f['item_id']
            and r.get('field') in ('slab_level','slab_level_candidate') and r.get('value') is not None]
        if any(abs(r['value']-f['value'])>.0025 or r.get('status') in ('conflict','candidate') for r in competing):
            continue
        result[name]={'value':f['value'],'unit':'m','method':f['method'],
            **{k:deepcopy(f.get(k)) for k in ('evidence_ids','confidence_pct','source_fact_ids')}}
    # Region levels of stepped slabs (principal / step uid). The SA only fills
    # a region that its own reading left empty.
    for f in package.get('levels', []):
        name=names.get(f.get('item_id'))
        if (not name or f.get('field')!='slab_region_level' or number(f.get('value')) is None
                or f.get('status') in ('conflict','candidate','unknown','estimated')):
            continue
        result.setdefault(name,{}).setdefault('regions',{})[f['region_id']]={
            'value':f['value'],'method':f.get('method'),'status':f.get('status'),
            **{k:deepcopy(f.get(k)) for k in ('evidence_ids','confidence_pct','source_fact_ids')}}
    return result


LAYERED_METHODS=('slab_neighbor_continuity_without_step_cut','slab_neighbor_majority_vote')


def consume_item_levels(slabs, levels):
    """Attach proven pre-SA values before the normal SA contextual inference."""
    from src.core.slab_level_inference import point_inside_ring
    consumed = []
    for slab in slabs:
        name = slab.get('name')
        row = levels.get(name)
        validated = slab.get('validated_fields') or []
        if not row or 'laje_nivel' in validated or 'level' in validated:
            continue
        if row.get('regions'):
            # Applied by slab_steps.collect_sa_steps, only to empty regions.
            slab['preprocess_region_levels'] = deepcopy(row['regions'])
        if row.get('unit') != 'm' or number(row.get('value')) is None:
            continue
        from .adapters.named_section_slabs import METHOD as named_section_method
        derived=row.get('method') in ('scoped_cut_wing_relative_delta_cm', named_section_method)+LAYERED_METHODS
        if row.get('method') in LAYERED_METHODS:
            pass  # bound to this package's DXF revision; no contained position
        elif derived:
            from shapely.geometry import Polygon, shape
            try:
                current=Polygon(slab.get('points')).buffer(0)
                frozen=shape(row['target_geometry'])
                if current.is_empty or current.symmetric_difference(frozen).area>.01:
                    continue
            except (KeyError,TypeError,ValueError):
                continue
        elif row.get('cad_marks'):
            # The final SA contour may be narrower than the collected contour.
            # Keep only real, individually identified marks inside this contour.
            inside = [m for m in row['cad_marks'] if m.get('handle')
                      and point_inside_ring(slab.get('points'), tuple(m['pos']))]
            if not inside or any(number(m.get('value')) != number(row['value']) for m in inside):
                continue
            row = deepcopy(row)
            handles = {'cad:' + m['handle'] for m in inside}
            row['cad_marks'] = inside
            row['positions'] = [m['pos'] for m in inside]
            row['evidence_ids'] = sorted(handles | {e for e in row['evidence_ids'] if not e.startswith('cad:')})
        elif not row.get('positions') or not all(point_inside_ring(slab.get('points'), tuple(p)) for p in row['positions']):
            continue
        links = slab.setdefault('links', {}).setdefault('laje_nivel', {})
        slots = (slab.get('validated_link_classes') or {}).get('laje_nivel') or []
        if 'label' in slots or any(l.get('human') or l.get('validated') or l.get('source') == 'human' for l in links.get('label', []) if isinstance(l, dict)):
            continue
        value = row['value']
        slab.setdefault('fields', {})['laje_nivel'] = str(value)
        slab['laje_nivel'] = str(value)
        method=('preprocess_layered_slab_level' if row.get('method') in LAYERED_METHODS else
                'preprocess_scoped_cut_level' if derived else 'preprocess_contained_cad_level')
        links['label'] = [{'text': str(value), 'type': 'text', 'source': method,
                           'is_inferred': derived, 'evidence_ids': row['evidence_ids']}]
        slab['preprocess_level_evidence'] = deepcopy(row)
        slab['level_inference'] = {'status': 'inferred' if derived else 'observed', 'reason': method,
                                   'value': value, 'evidence_ids': row['evidence_ids'],
                                   'confidence_pct': row.get('confidence_pct'),
                                   'source_fact_ids': row.get('source_fact_ids',[])}
        consumed.append({'item': name, 'field': 'laje_nivel', 'value': value, 'evidence_ids': row['evidence_ids']})
    return consumed


def plan_marks(path, reference):
    """Only local absolute altitude marks, with CAD handles and coordinates."""
    from src.core.dxf_loader import DXFLoader
    from src.core.level_text_semantics import elevation_value
    top, height = number(reference.get('top')), number(reference.get('height'))
    if reference.get('unit') != 'm' or top is None or not height:
        return []
    rows = []
    for token in (DXFLoader.load_dxf(str(path)) or {}).get('texts', []):
        value = elevation_value(token, reference_level=top, floor_height=height)
        if value is not None and abs(value - top) <= abs(height) * .25:
            rows.append({'value': value, 'text': token.get('text'), 'pos': list(token['pos'])[:2],
                         'handle': token.get('handle')})
    return rows


def slab_receivers(items, slabs):
    """The repeated label inside the SA contour owns that slab.

    One label, or no single label inside the contour, keeps the first item.
    """
    from src.core.slab_level_inference import point_inside_ring
    groups = defaultdict(list)
    for item in items:
        if item.get('item_class') == 'slab':
            groups[item.get('display_name')].append(item)
    chosen = {}
    for name, group in groups.items():
        if len(group) < 2:
            continue
        points = (slabs.get(name) or {}).get('points')
        inside = [item for item in group
                  if item.get('label_position') and points
                  and point_inside_ring(points, tuple(item['label_position']))]
        if len(inside) == 1:
            chosen[name] = inside[0]['item_id']
    return chosen


def pillar_survey_geometry(surveys):
    """Union duplicate source handles only when their footprints agree."""
    from shapely.geometry import shape
    from shapely.errors import ShapelyError

    def same_geometry(a, b):
        if a == b:
            return True
        try:
            return shape(a).equals(shape(b))
        except (TypeError, ValueError, KeyError, ShapelyError):
            return False
    result = {}
    for survey in surveys:
        existing = result.get(survey['item_id'])
        if existing is None:
            result[survey['item_id']] = deepcopy(survey)
        elif existing.get('geometry') and survey.get('geometry') and same_geometry(existing['geometry'], survey['geometry']):
            existing['source_entity_handles'] = sorted(set(existing.get('source_entity_handles') or [])
                                                      | set(survey.get('source_entity_handles') or []))
        else:
            # Rounded survey IDs may collide; never pick one footprint silently.
            existing['geometry'] = None
            existing['source_entity_handles'] = []
    return result


def pillar_ownership(items, context):
    """Bind footprints, preserving unrelated candidates and proven CAD roles.

    A name is only a candidate group. Neither a missing SA match nor proximity
    proves that a survey geometry is disposable. Foreign roles require an
    identical source contour and a matching original DXF handle.
    """
    from shapely.geometry import Polygon, shape
    from shapely.errors import ShapelyError

    def polygon(value):
        try:
            result = shape(value) if isinstance(value, dict) else Polygon(value)
            return result if result.is_valid and not result.is_empty and result.area > 0 else None
        except (TypeError, ValueError, KeyError, ShapelyError):
            return None

    canonical = {p['name']: polygon(p.get('points')) for p in context['state'].get('pilares', [])}
    foreign = []
    for review in (context.get('source_role_reviews') or {}).get('records', []):
        if (review.get('status') == 'proved' and review.get('content_preserved')
                and review.get('consumer_authorized') == 'source_role_only'
                and review.get('level_transfer_authorized') is False
                and review.get('source_entity_handles')):
            foreign.append((review['role'], review['owner'],
                            polygon(review.get('original_points')),
                            set(review['source_entity_handles'])))
    for section in (context.get('dimensioned_section_profiles') or {}).get('records', []):
        if (section.get('status') == 'proved'
                and section.get('consumer_authorized') == 'source_role_only'
                and section.get('level_transfer_authorized') is False
                and section.get('dimension_evidence_handles')
                and section.get('source_entity_handles')):
            foreign.append(('slab_section_glyph', 'unassigned_section',
                            polygon(section.get('original_points')),
                            set(section['source_entity_handles'])))
    for frame in (context.get('sheet_frames') or {}).get('records', []):
        if frame.get('status') == 'proved' and frame.get('content_preserved') and frame.get('source_entity_handles'):
            foreign.append(('sheet_frame', 'original_sheet', polygon(frame.get('original_points')),
                            set(frame['source_entity_handles'])))
    for detail in (context.get('local_pillar_details') or {}).get('records', []):
        # Raw and tower handles are different namespaces. External details
        # provide dimensions, never the role of a contour in this tower crop.
        if detail.get('source_role') == 'declared_raw_detail':
            continue
        if (detail.get('status') == 'proved' and detail.get('dimension_chain_bound')
                and detail.get('consumer_authorized') and detail.get('source_entity_handles')):
            for owner in detail.get('pillar_names') or []:
                if canonical.get(owner) is not None:
                    foreign.append(('pillar_detail', owner, polygon(detail.get('original_points')),
                                    set(detail['source_entity_handles'])))
    # A named cut association is independent of the homonymous pillar survey.
    # The handle must come from extraction, never from a contour lookup.
    for slab in context['state'].get('slabs', []):
        for field in ('laje_visao_corte', 'laje_nivel'):
            for cut in ((slab.get('links') or {}).get(field) or {}).get('cut_view_geom') or []:
                owner = (cut.get('ficha') or {}).get('beam_name')
                if (cut.get('role') == 'Cut_view_geom_auto' and owner
                        and cut.get('source_entity_handles')):
                    foreign.append(('beam_section', owner,
                                    polygon(cut.get('original_pts') or cut.get('points')),
                                    set(cut['source_entity_handles'])))
    for slab in context['state'].get('slabs', []):
        for step in slab.get('slab_steps') or []:
            foreign.append(('slab_region', slab['name'], polygon(step.get('points')),
                            set(step.get('evidence_handles') or [])))
            for section in step.get('sections') or []:
                foreign.append(('slab_section', slab['name'], polygon(section.get('points')),
                                {section['handle']} if section.get('handle') else set()))
    groups = defaultdict(list)
    roles = {}
    for item in items:
        if item['item_class'] != 'pillar':
            continue
        geometry = polygon(item.get('geometry'))
        groups[item['display_name']].append((item, geometry))
        if geometry is None or any(own is not None and geometry.equals(own) for own in canonical.values()):
            continue
        handles = set(item.get('source_entity_handles') or [])
        proofs = [(role, owner, sorted(handles & evidence)) for role, owner, contour, evidence in foreign
                  if contour is not None and handles & evidence and geometry.equals(contour)]
        if proofs:
            roles[item['item_id']] = [{'role': role, 'owner': owner, 'source_entity_handles': evidence}
                                      for role, owner, evidence in proofs]
    receivers = {}
    for name, group in groups.items():
        own = canonical.get(name)
        if own is None or not any(g is not None for _, g in group):
            continue  # Legacy inputs without footprint evidence retain their contract.
        matches = {i['item_id'] for i, g in group if g is not None and g.equals(own)}
        receivers[name] = next(iter(matches)) if len(matches) == 1 else None
    return receivers, roles


def deduplicate_identical_source_records(records, excluded_identities=()):
    """Remove repeated serialization only, never reconcile identities/evidence.

    A shared ID is insufficient: geometry, handles, facts and every metadata
    field must agree. Divergent records retain their original ordering.
    """
    result = []
    seen = defaultdict(list)
    for record in records:
        identity = record.get('item_id') if isinstance(record, dict) else None
        if (identity and identity not in excluded_identities and record.get('source_entity_handles')
                and any(record == previous for previous in seen[identity])):
            continue
        result.append(record)
        if identity:
            seen[identity].append(record)
    return result


def merge_sa_levels(tower: dict, context: dict) -> dict:
    """Preserve pre-SA evidence alongside actual SA segment identities."""
    from src.core.slab_level_inference import point_inside_ring
    from src.core.pillar_sa_review import load as load_review
    out = deepcopy(tower)
    out['items'] = deduplicate_identical_source_records(
        out['items'], context.get('nonidentical_original_item_ids', ()))
    from .canonical_inventory import include_geometry
    include_geometry(out['items'], context)
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
    # A second text with the same name stays a label. The SA slab belongs to
    # the text that sits inside its contour.
    receivers = slab_receivers(out['items'], slabs)
    pillar_receivers, foreign_pillar_roles = pillar_ownership(out['items'], context)
    from .repeated_beam_labels import parcel_receivers
    parcel_owners, parcel_proofs = parcel_receivers(
        out['items'], segments, context.get('tower_path'))
    beam_primary = {}
    for candidate in out['items']:
        if candidate['item_class'] == 'beam':
            beam_primary.setdefault(candidate['display_name'], candidate['item_id'])
    own_parcels = set(parcel_owners.values())
    seen = set()
    for item in out['items']:
        name, cls = item['display_name'], item['item_class']
        key = (cls, name)
        if cls == 'pillar' and item['item_id'] in foreign_pillar_roles:
            item['pre_sa_levels'] = item['levels']
            item['identity_role_proof'] = foreign_pillar_roles[item['item_id']]
            item['canonical_geometry_available'] = False
            item['levels'] = [fact(item, field, None, 'source_geometry_has_non_pillar_role',
                                  status='not_applicable',
                                  evidence=['cad:' + h for proof in item['identity_role_proof']
                                            for h in proof['source_entity_handles']],
                                  identity_role_proof=deepcopy(item['identity_role_proof']))
                              for field in ('base', 'top')]
            item['segments'] = []
            continue
        if cls == 'pillar' and name in pillar_receivers and item['item_id'] != pillar_receivers[name]:
            # Preserve unresolved unmatched geometries as pending; do not
            # transfer another pillar's floor or contact facts by its name.
            item['canonical_geometry_available'] = False
            item['canonical_owner_item_id'] = pillar_receivers[name]
            continue
        if key in seen and not (cls == 'beam' and item['item_id'] in own_parcels):
            continue
        if cls == 'slab' and name in receivers and item['item_id'] != receivers[name]:
            continue
        seen.add(key)
        original = item['levels']
        item['pre_sa_levels'] = original
        item['levels'] = []
        if cls == 'slab' and name in slabs:
            slab = slabs[name]
            item['slab_steps'] = deepcopy(slab.get('slab_steps') or [])
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
                    cad_marks=[{k:deepcopy(m[k]) for k in ('handle','pos','value')} for m in selected],
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
                item['levels'] = original or [fact(item, 'slab_level', None,
                    'canonical_geometry_without_level_evidence', status='unknown')]
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
                        status='floor_reference' if number(reference.get(refkey)) is not None else 'unknown',
                        warnings=['storey_reference_not_individual_measurement']))
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
                owner = parcel_owners.get(seg['uid'], beam_primary[name])
                if owner != item['item_id']:
                    continue
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
                human_fields = seg.get('level_evidence_fields') or []
                if method == 'explicit_beam_or_side' and not linked and not human_fields:
                    warnings.append('automatic_beam_field_without_cad_level_provenance')
                state_status = ('unknown' if value is None else 'human_review' if human_fields else
                                'estimated' if estimated else 'inferred' if warnings else 'sa_evidence')
                record = fact(item, family, value, method, status='estimated' if estimated else 'sa_evidence',
                    evidence=[seg['uid'], *['slab:'+n for n in linked], *['human_field:'+f for f in human_fields]], warnings=warnings,
                    segment_id=seg['uid'], segment_label=seg.get('segment_label'), source_slabs=linked)
                record['status'] = state_status
                item['levels'].append(record)
                segment = {**seg, 'segment_id': seg['uid'], 'family': family, 'unit': 'm',
                           'status': record['status'], 'warnings': warnings, 'evidence_ids': record['evidence_ids']}
                if seg['uid'] in parcel_proofs:
                    segment['original_label_parcel_proof'] = deepcopy(parcel_proofs[seg['uid']])
                # Validate width and spatial scope before using a section dimension.
                if family == 'fundo':
                    from .beam_cut_continuity import fund_section
                    section = fund_section(seg, fields, segments[name], context.get('tower_path')) or {}
                    height = section.get('height_cm')
                    segment.update(section)
                    if height is not None and value is not None:
                        bottom = round(value - height / 100, 4)
                        segment.update(bottom_level=bottom, height_cm=height)
                        item['levels'].append(fact(item, 'beam_bottom', bottom, 'fv_reference_minus_depth_cm',
                            status=record['status'], evidence=[seg['uid'], 'beam:'+name+':'+str(section.get('section_source')),
                                *['cad:'+handle for handle in section.get('source_entity_handles', [])]],
                            warnings=warnings, segment_id=seg['uid'], height_cm=height))
                item['segments'].append(segment)
        else:
            item['levels'] = original
        # A duplicate survey label carries only its own old observations.
    for item in out['items']:
        key = (item['item_class'], item['display_name'])
        if 'pre_sa_levels' not in item and key in seen and not (item['item_class'] == 'pillar'
                and item['display_name'] in pillar_receivers):
            item['pre_sa_levels'] = item['levels']
            item['levels'] = []
            item['segments'] = []
    from .adapters.named_section_slabs import attach_named_section_facts
    attach_named_section_facts(out['items'], context.get('named_section_slab_levels', []), reference)
    from .segment_levels import resolve
    resolve(out, context)
    unique = [i for i in out['items'] if i.get('levels')]
    counts = Counter(f['status'] for i in unique for f in i['levels'])
    out['sa_evidence'] = {'source': source, 'status_counts': dict(counts),
        'items_with_levels': sum(any(f.get('value') is not None and f['field'] != 'slab_level_candidate' for f in i['levels']) for i in unique),
        'items_not_applicable': sum(all(f['status'] == 'not_applicable' for f in i['levels']) for i in unique),
        'slabs_with_plan_levels': sum(i['item_class']=='slab' and any(f.get('method')=='cad_level_inside_slab' for f in i['levels']) for i in unique),
        'slabs_with_inferred_levels': sum(i['item_class']=='slab' and any(f['field']=='slab_level' and f['status']=='inferred' for f in i['levels']) for i in unique),
        'slabs_with_multiple_parts': sum(i['item_class']=='slab' and len({f['value'] for f in i['levels'] if f.get('method')=='cad_level_inside_slab'})>1 for i in unique),
        'segments': sum(len(i['segments']) for i in unique if i['item_class'] == 'beam'),
        'confidence_method': 'level_evidence_completeness_v1',
        'shortened_cuts_excluded_from_absolute_levels': len(out.get('rejected_cut_level_evidence', []))}
    return out
