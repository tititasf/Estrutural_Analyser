"""Pure publication-readiness assessment for the development SA cycle.

No CAD measurement, filesystem access or publication occurs here. A ready
cycle has no recorded pending units; it still requires final visual review.
"""
from __future__ import annotations

import math
from collections.abc import Mapping


BLOCKED_LEVEL_STATUSES = {'unknown', 'conflict', 'conflicting', 'candidate', 'estimated'}
QA_FIELDS = {'status', 'divergencias', 'incertos', 'medidos',
             'snapshot_sha256', 'medido_em'}


def _resolved_number(fact, key='value'):
    status = str(fact.get('status') or '').lower()
    value = fact.get(key)
    return (bool(status) and status not in BLOCKED_LEVEL_STATUSES
            and status not in {'not_applicable', 'segmented'}
            and not status.startswith('conflict') and isinstance(value, (int, float))
            and not isinstance(value, bool) and math.isfinite(value))


def _disjoint_region_proof(conflict, current):
    """Recognize distinct measured parcels, preserving the original core issue."""
    if not isinstance(conflict, Mapping) or conflict.get('kind') != 'divergent_values_or_reference' or conflict.get('field') != 'slab_region_level':
        return False
    ids = conflict.get('fact_ids') or []
    matching = [f for f in current if isinstance(f, Mapping) and f.get('fact_id') in ids]
    by_id = {f.get('fact_id'): f for f in matching}
    if len(matching) != len(by_id):
        return False
    if len(ids) < 2 or any(i not in by_id for i in ids):
        return False
    facts = [by_id[i] for i in ids]
    if any(not _resolved_number(f) or not f.get('evidence_ids') for f in facts):
        return False
    if any(not facts[0].get(k) or len({f.get(k) for f in facts}) != 1
           for k in ('item_id', 'unit', 'datum_id')):
        return False
    regions = [f.get('region_id') for f in facts]
    if any(not r for r in regions) or len(set(regions)) != len(regions):
        return False
    try:
        from shapely.geometry import shape
        geometries = [shape(f['region_geometry']) for f in facts]
        if any(g.geom_type not in {'Polygon', 'MultiPolygon'} or not g.is_valid
               or g.is_empty or g.area <= 0 for g in geometries):
            return False
        return all(a.intersection(b).area == 0 for i, a in enumerate(geometries)
                   for b in geometries[i + 1:])
    except (ImportError, KeyError, TypeError, ValueError):
        return False


def _current_fv_top_proof(item_id, current, segments):
    """FV level is the superior datum; require measured facts for every parcel."""
    own = [s for s in segments if str(s.get('beam_item_id')) == item_id
           and s.get('family') == 'fundo' and s.get('status') != 'not_applicable'
           and s.get('applicable') is not False]
    facts = [f for f in current if isinstance(f, Mapping)
             and str(f.get('item_id')) == item_id and f.get('field') == 'fundo']
    return (bool(own) and bool(facts)
            and all(_resolved_number(s, 'level') for s in own)
            and all(_resolved_number(f) and f.get('evidence_ids') for f in facts)
            and all(any(f['value'] == s['level'] for f in facts) for s in own))


def assess_cycle(package, qa_report, regressions=()):
    """Return pending evidence by unit; never grant final visual approval.

    Canonical package facts can be flat (``levels``/``beam_segments``) or
    embedded in inventory items. Current facts supersede preliminary history
    for the same item/field; unresolved current facts still block the cycle.
    """
    pending = []
    preserved_notes = []
    conflicts = []
    seen = set()

    def add(unit, kind, message, field=None):
        key = (str(unit), kind, str(message), field)
        if key not in seen:
            seen.add(key)
            pending.append(dict(unit=str(unit), kind=kind, message=str(message), field=field))

    if not isinstance(package, Mapping) or not package:
        add('cycle', 'package_incomplete', 'Pacote pré/SA ausente ou vazio')
        package = {}
    inventory = package.get('level_inventory') or {}
    items = inventory.get('items') if isinstance(inventory, Mapping) else None
    if not isinstance(items, list) or not items:
        add('cycle', 'inventory_incomplete', 'Inventário de unidades ausente ou vazio')
        items = []
    names = {str(i.get('item_id')): str(i.get('display_name') or i.get('item_id'))
             for i in items if isinstance(i, Mapping)}
    for source, data in [('package', package), ('level_inventory', inventory),
                         ('context_qa', package.get('context_qa') or {})]:
        if not isinstance(data, Mapping):
            add('cycle', 'package_incomplete', f'{source} inválido')
            continue
        if data.get('error') or data.get('status') in {'failed', 'error'}:
            add('cycle', 'pre_failed', f'{source}: {data.get("error") or data.get("status")}')
        for conflict in data.get('conflicts') or []:
            unit = names.get(str(conflict.get('item_id')), 'cycle') if isinstance(conflict, Mapping) else 'cycle'
            conflicts.append((unit, conflict))

    segments = list(inventory.get('beam_segments') or []) if isinstance(inventory, Mapping) else []
    for item in items:
        if isinstance(item, Mapping):
            segments.extend(item.get('segments') or [])
    def fact_key(fact):
        return (str(fact.get('item_id')), fact.get('field')) if isinstance(fact, Mapping) else None

    facts = []
    current = list(package.get('levels') or [])
    flat_keys = {fact_key(fact) for fact in current}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        for fact in item.get('levels') or []:
            bound = dict(fact, item_id=item.get('item_id')) if isinstance(fact, Mapping) else fact
            if fact_key(bound) not in flat_keys:
                current.append(bound)
    current_keys = {fact_key(fact) for fact in current}
    historical = list(package.get('pre_sa_survey_levels') or [])
    for item in items:
        if isinstance(item, Mapping):
            historical.extend(dict(fact, item_id=item.get('item_id')) if isinstance(fact, Mapping) else fact
                              for fact in item.get('pre_sa_levels') or [])
    effective = list(current)
    for fact in historical:
        if fact_key(fact) in current_keys:
            continue
        if isinstance(fact, Mapping) and fact.get('field') == 'beam_top' and _current_fv_top_proof(str(fact.get('item_id')), current, segments):
            preserved_notes.append(dict(kind='historical_level_superseded',
                                        fact=fact, proof='current_measured_fv_superior_datum'))
            continue
        effective.append(fact)
    for unit, conflict in conflicts:
        if _disjoint_region_proof(conflict, current):
            preserved_notes.append(dict(unit=unit, kind='disjoint_measured_regions',
                                        conflict=conflict, proof='same_datum_disjoint_polygon_interiors'))
        else:
            add(unit, 'pre_conflict', str(conflict))
    for fact in effective:
        unit = names.get(str(fact.get('item_id')), fact.get('display_name') or 'cycle') if isinstance(fact, Mapping) else 'cycle'
        facts.append((fact, unit))

    expected = set()
    for item in items:
        if not isinstance(item, Mapping):
            add('cycle', 'item_incomplete', 'Unidade de inventário inválida')
            continue
        name = str(item.get('display_name') or item.get('item_id') or 'cycle')
        if not item.get('item_id') or not item.get('display_name'):
            add(name, 'item_incomplete', 'Identidade da unidade incompleta')
        if item.get('status') == 'not_applicable' or item.get('applicable') is False:
            continue
        own = [s for s in segments if s.get('beam_item_id') == item.get('item_id')
               or s.get('beam_name') == name or s in (item.get('segments') or [])]
        own = [s for s in own if s.get('status') != 'not_applicable' and s.get('applicable') is not False]
        cls = item.get('item_class')
        if cls == 'pillar':
            expected.add(('PIL', name))
        elif cls == 'slab':
            expected.add(('LAJ', name))
        elif cls == 'beam':
            for segment in own:
                family = str(segment.get('family') or segment.get('kind') or '')
                if family == 'fundo':
                    expected.add(('FV', name))
                elif family.startswith('lateral_'):
                    behavior = str(segment.get('behavior') or family.split('_')[-1]).lower()
                    expected.add(('LV', name + '|' + behavior))
                else:
                    add(name, 'segment_incomplete', 'Família do segmento não identificada')
            if not own and not any(s.get('status') == 'not_applicable' or s.get('applicable') is False
                                   for s in segments if s.get('beam_item_id') == item.get('item_id')
                                   or s.get('beam_name') == name):
                add(name, 'segment_incomplete', 'Viga sem segmentos aplicáveis inventariados')
        else:
            add(name, 'item_incomplete', 'Classe da unidade não identificada')
        if not any(isinstance(f, Mapping) and str(f.get('item_id')) == str(item.get('item_id')) for f, _ in facts):
            add(name, 'levels_incomplete', 'Fatos de nível da unidade ausentes')
        present_ids = {str(f.get('fact_id')) for f, _ in facts if isinstance(f, Mapping)}
        for fact_id in item.get('level_fact_ids') or []:
            if str(fact_id) not in present_ids:
                add(name, 'levels_incomplete', 'Fato de nível referenciado ausente', str(fact_id))

    def level(fact, unit, field=None):
        if not isinstance(fact, Mapping):
            add(unit, 'levels_incomplete', 'Fato de nível inválido', field)
            return
        status = str(fact.get('status') or '').lower()
        if status == 'not_applicable' or fact.get('applicable') is False:
            return
        field = field or fact.get('field')
        if not field or not status:
            add(unit, 'levels_incomplete', 'Campo ou status do nível ausente', field)
        if status in BLOCKED_LEVEL_STATUSES or status.startswith('conflict'):
            add(unit, 'level_pending', 'Nível ' + status, field)
        if status == 'segmented' and not fact.get('level_ranges') and (fact in segments
                or not any(s.get('beam_name') == unit for s in segments)):
            add(unit, 'levels_incomplete', 'Nível segmentado sem parcelas medidas', field)
        value = fact.get('value', fact.get('level'))
        if status != 'segmented' and (value is None or isinstance(value, bool)
                or not isinstance(value, (int, float)) or not math.isfinite(value)):
            add(unit, 'levels_incomplete', 'Valor numérico de nível ausente ou inválido', field)
        for index, part in enumerate(fact.get('level_ranges') or []):
            level(part, unit, f'{field}:range:{index}')

    for fact, unit in facts:
        level(fact, unit)
    for segment in segments:
        unit = str(segment.get('beam_name') or names.get(str(segment.get('beam_item_id')), 'cycle'))
        segment_id = str(segment.get('segment_id') or segment.get('uid') or 'segment')
        level(segment, unit, segment_id)

    if not isinstance(qa_report, Mapping) or not qa_report:
        add('cycle', 'qa_incomplete', 'Relatório QA CAD ausente ou vazio')
        qa_report = {}
    if qa_report.get('schema') != 'cad.qa_gate_pavimento/v1':
        add('cycle', 'qa_incomplete', 'Schema QA CAD ausente ou não reconhecido')
    if not qa_report.get('source') or not qa_report.get('source_sha256'):
        add('cycle', 'qa_incomplete', 'Fonte/revisão QA CAD ausente')
    selected = (package.get('scope') or {}).get('recorte_id')
    for source in package.get('sources') or []:
        if source.get('source_id') == selected and source.get('revision') != qa_report.get('source_sha256'):
            add('cycle', 'qa_incomplete', 'QA CAD medido em revisão diferente da fonte selecionada')
    classes = qa_report.get('classes')
    if not isinstance(classes, Mapping) or not classes:
        add('cycle', 'qa_incomplete', 'Classes QA CAD ausentes ou vazias')
        classes = {}
    for cls, name in sorted(expected):
        if not isinstance(classes.get(cls), Mapping) or name not in classes[cls]:
            add(name, 'qa_missing', f'Medição {cls} ausente')
    for cls, bucket in classes.items():
        if not isinstance(bucket, Mapping):
            add('cycle', 'qa_incomplete', f'Classe {cls} inválida')
            continue
        for name, entry in bucket.items():
            if not isinstance(entry, Mapping):
                add(name, 'qa_incomplete', f'Medição {cls} inválida')
                continue
            if entry.get('status') == 'not_applicable':
                continue
            if not QA_FIELDS.issubset(entry) or not entry.get('snapshot_sha256') or not entry.get('medido_em'):
                add(name, 'qa_incomplete', f'Campos QA {cls} incompletos')
            for key in ('divergencias', 'incertos'):
                if not isinstance(entry.get(key), list):
                    add(name, 'qa_incomplete', f'{cls}: {key} ausente ou inválido')
                for message in entry.get(key) or []:
                    add(name, 'qa_pending', f'{cls}: {message}')
            if entry.get('status') != 'confere':
                add(name, 'qa_pending', f'{cls}: status {entry.get("status") or "ausente"}')
            measured = entry.get('medidos')
            if isinstance(measured, bool) or not isinstance(measured, int) or measured <= 0:
                add(name, 'qa_incomplete', f'{cls}: nenhuma medição comprovada')
    for regression in regressions:
        unit = (regression.get('unit') or regression.get('name') or regression.get('item_id') or 'cycle') if isinstance(regression, Mapping) else 'cycle'
        add(unit, 'regression', str(regression))
    return dict(schema='cad.sa_development_gate/v1', ready_for_publication=not pending,
                final_visual_approved=False,
                visual_review_required=True, pending_count=len(pending), pending=pending,
                preserved_notes=preserved_notes,
                pending_by_unit={unit: [p for p in pending if p['unit'] == unit]
                                 for unit in sorted({p['unit'] for p in pending})},
                assessed_units=len(items), expected_qa_units=len(expected))
