"""Source parcel identity for homonymous slab labels, without assigning datums.

Display labels remain unchanged. Separate source labels or disjoint source
polygons cannot authorize copying a level or human decision between parcels.
"""
from __future__ import annotations

import hashlib
import json
from shapely.geometry import Polygon


def source_label_handle(item):
    return str(item.get('source_label_handle') or
               (item.get('trace_diagnostics') or {}).get('source_label_handle') or '')


def source_label_position(item):
    value = item.get('source_label_position') or item.get('pos')
    try:
        return tuple(float(v) for v in value[:2]) if len(value) >= 2 else None
    except (TypeError, ValueError):
        return None


def parcel_polygon(item):
    try:
        p = Polygon(item.get('points') or [])
        return p if p.is_valid and p.area > 0 else None
    except (ValueError, TypeError):
        return None


def same_source_parcel(a, b):
    if str(a.get('name') or '') != str(b.get('name') or ''):
        return False
    ha, hb = source_label_handle(a), source_label_handle(b)
    if ha and hb:
        return ha == hb
    pa, pb = source_label_position(a), source_label_position(b)
    if pa is not None and pb is not None:
        return pa == pb
    ga, gb = parcel_polygon(a), parcel_polygon(b)
    if ga is not None and gb is not None:
        # Partial overlap is not evidence of one source label or ownership.
        return ga.equals(gb)
    return False


def parcel_identity(item):
    handle = source_label_handle(item)
    pos = source_label_position(item)
    poly = parcel_polygon(item)
    if handle:
        token = ('handle', handle)
    elif pos is not None:
        token = ('label_position', pos)
    elif poly is not None:
        token = ('polygon', poly.normalize().wkb_hex)
    else:
        token = ('unlocated', str(item.get('id') or ''))
    return hashlib.sha256(json.dumps([item.get('name'), token]).encode()).hexdigest()


def group_source_parcels(items):
    groups = []
    for item in items or []:
        matches = [g for g in groups if all(same_source_parcel(item, r) for r in g)]
        if len(matches) == 1:
            matches[0].append(item)
        else:
            groups.append([item])
    return groups


def accepted_level_for_parcel(parcel, accepted_records, field='level_str'):
    """Read only independently accepted records for this physical source unit.

    Mere proximity, display name, or overlapping geometry is insufficient for
    authorizing a level. The caller must supply accepted records; this helper
    never converts units, resolves a conflict, or accepts raw OCR candidates.
    """
    values = []
    for record in accepted_records or []:
        if record.get('name') != parcel.get('name'):
            continue
        ha, hb = source_label_handle(parcel), source_label_handle(record)
        pa, pb = source_label_position(parcel), source_label_position(record)
        ga, gb = parcel_polygon(parcel), parcel_polygon(record)
        if ha and hb:
            match = ha == hb
        elif pa is not None and pb is not None:
            match = pa == pb
        else:
            match = ga is not None and gb is not None and ga.equals(gb)
        if match:
            values.append(str(record.get(field) or '').strip())
    return values[0] if values and len(set(values)) == 1 else ''
