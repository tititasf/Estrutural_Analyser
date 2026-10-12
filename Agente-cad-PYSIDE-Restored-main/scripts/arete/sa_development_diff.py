"""Pure spatial comparison of canonical SA states; no CAD loading or writes.

Panels are unioned per item/family, so splitting an unchanged panel is not a
regression. Levels are compared on the shared physical region, not by unstable
segment IDs. Every change remains reviewable; this module never approves it.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import re

from shapely.geometry import GeometryCollection, LineString, Polygon
from shapely.ops import unary_union


def numeric_value(value):
    """Normalize numeric spelling without guessing/converting measurement units."""
    text = str(value if value is not None else '').strip()
    match = re.fullmatch(r'([+-]?\d+(?:[.,]\d+)?)\s*(m|cm)?', text)
    if not match:
        return ('text', text)
    try:
        return ('number', str(Decimal(match[1].replace(',', '.')).normalize()), match[2] or '')
    except InvalidOperation:
        return ('text', text)


def _index(state):
    groups = defaultdict(list)
    scalars = {}
    for collection, family in (('pilares', 'PIL'), ('slabs', 'LAJ')):
        for row in state.get(collection, []) or []:
            name = str(row.get('name') or row.get('key') or '')
            groups[(family, name)].append(row)
            scalars[(family, name)] = {
                field: numeric_value(row.get(field))
                for field in (('nivel_str',) if family == 'PIL' else ('nivel', 'height'))
            }
    for family, rows in (state.get('segmentos') or {}).items():
        for row in rows or []:
            groups[(family, str(row.get('beam_name') or ''))].append(row)
    return groups, scalars


def _geometry(rows, *, allow_lines=False):
    polygons = []
    errors = []
    for row in rows:
        points = row.get('points') or []
        try:
            polygon = LineString(points) if allow_lines and len(points) == 2 else Polygon(points)
            measure = polygon.length if isinstance(polygon, LineString) else polygon.area
            if polygon.is_empty or not polygon.is_valid or measure <= 0:
                raise ValueError('empty, invalid or zero-size geometry')
            polygons.append(polygon)
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))
    return unary_union(polygons) if polygons else GeometryCollection(), errors


def _pillar_contacts(state):
    """Canonical contact identity survives row order and duplicate display rows."""
    contacts = defaultdict(set)
    for pillar in state.get('pilares', []) or []:
        name = str(pillar.get('name') or pillar.get('key') or '')
        # Keep an empty pillar in the inventory so a deleted pillar is explicit.
        contacts[name]
        faces = (pillar.get('interpretacao_abcd') or {}).get('faces') or {}
        for face, groups in faces.items():
            for role in ('chega', 'passa', 'interior', 'lajes'):
                for row in groups.get(role, []) or []:
                    item = str(row.get('nome') or '').strip()
                    if item and item.casefold() not in {'nenhuma', '—', '-'}:
                        contacts[name].add((str(face), role, item))
    return contacts


def compare_states(before, after, *, area_epsilon_cm2=1e-6,
                   length_epsilon_cm=1e-6, coordinate_epsilon_cm=1e-9):
    """Return unapproved physical/numeric changes, including missing items.

    Epsilons handle floating point geometry noise only. Source coordinates
    and levels are never rounded. Lateral two-point traces are valid lines;
    their lost/gained spans and displacement are measured in cm. Invalid
    geometries remain explicit blockers instead of being silently repaired.
    """
    old, old_scalars = _index(before)
    new, new_scalars = _index(after)
    geometry_changes, numeric_changes, errors = [], [], []
    for key in sorted(set(old) | set(new)):
        family, name = key
        allow_lines = family.startswith('lateral_')
        a, bad_a = _geometry(old.get(key, []), allow_lines=allow_lines)
        b, bad_b = _geometry(new.get(key, []), allow_lines=allow_lines)
        for phase, bad in (('before', bad_a), ('after', bad_b)):
            if bad:
                errors.append(dict(family=family, item=name, phase=phase, errors=bad))
        removed, added = a.difference(b).area, b.difference(a).area
        linear = allow_lines and a.area == 0 and b.area == 0
        lost_length = a.difference(b.buffer(coordinate_epsilon_cm)).length if linear else 0
        gained_length = b.difference(a.buffer(coordinate_epsilon_cm)).length if linear else 0
        hausdorff = None if a.is_empty or b.is_empty else a.hausdorff_distance(b)
        line_changed = linear and (
            max(lost_length, gained_length) > length_epsilon_cm
            or (hausdorff is not None and hausdorff > coordinate_epsilon_cm))
        if key not in old or key not in new or max(removed, added) > area_epsilon_cm2 or line_changed:
            geometry_changes.append(dict(
                family=family, item=name, change='added_item' if key not in old else
                'removed_item' if key not in new else 'geometry_changed',
                before_area_cm2=a.area, after_area_cm2=b.area,
                removed_area_cm2=removed, added_area_cm2=added,
                before_length_cm=a.length if linear else None,
                after_length_cm=b.length if linear else None,
                removed_length_cm=lost_length, added_length_cm=gained_length,
                hausdorff_cm=hausdorff))
        multiple_slab_parcels = family == 'LAJ' and max(len(old.get(key, [])), len(new.get(key, []))) > 1
        if key in old_scalars and key in new_scalars and not multiple_slab_parcels:
            for field in old_scalars[key]:
                if old_scalars[key][field] != new_scalars[key][field]:
                    numeric_changes.append(dict(family=family, item=name, field=field,
                        before=old_scalars[key][field], after=new_scalars[key][field]))
        elif key in old and key in new:
            shared = a.intersection(b.buffer(coordinate_epsilon_cm)) if linear else a.intersection(b)
            fields = ('nivel', 'height') if multiple_slab_parcels else ('level',)
            for field in fields:
                old_levels, new_levels = defaultdict(list), defaultdict(list)
                for row in old[key]:
                    old_levels[numeric_value(row.get(field))].append(row)
                for row in new[key]:
                    new_levels[numeric_value(row.get(field))].append(row)
                for level in sorted(set(old_levels) | set(new_levels)):
                    left, _ = _geometry(old_levels.get(level, []), allow_lines=allow_lines)
                    right, _ = _geometry(new_levels.get(level, []), allow_lines=allow_lines)
                    lost = left.intersection(shared).difference(right).area
                    gained = right.intersection(shared).difference(left).area
                    lost_span = left.intersection(shared).difference(right.buffer(coordinate_epsilon_cm)).length if linear else 0
                    gained_span = right.intersection(shared.buffer(coordinate_epsilon_cm)).difference(left.buffer(coordinate_epsilon_cm)).length if linear else 0
                    if max(lost, gained) > area_epsilon_cm2 or max(lost_span, gained_span) > length_epsilon_cm:
                        numeric_changes.append(dict(family=family, item=name,
                            field=field+'_on_physical_region', level=level,
                            removed_region_cm2=lost, added_region_cm2=gained,
                            removed_span_cm=lost_span, added_span_cm=gained_span))
    old_contacts, new_contacts = _pillar_contacts(before), _pillar_contacts(after)
    contact_changes = []
    for name in sorted(set(old_contacts) | set(new_contacts)):
        removed = sorted(old_contacts[name] - new_contacts[name])
        added = sorted(new_contacts[name] - old_contacts[name])
        if removed or added:
            contact_changes.append(dict(family='PIL', item=name,
                change='contact_inventory_changed', removed_contacts=removed,
                added_contacts=added, original_source_review_required=True))
    changes = [*geometry_changes, *numeric_changes, *errors, *contact_changes]
    return dict(schema='cad.sa.development_diff/v2',
                geometry_changes=geometry_changes, numeric_changes=numeric_changes,
                geometry_errors=errors, pending_count=len(changes),
                contact_changes=contact_changes,
                unchanged=not changes, reviewed=False,
                area_epsilon_cm2=area_epsilon_cm2,
                length_epsilon_cm=length_epsilon_cm,
                coordinate_epsilon_cm=coordinate_epsilon_cm)
