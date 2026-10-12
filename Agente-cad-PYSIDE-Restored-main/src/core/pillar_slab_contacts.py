"""Derived physical contacts for N3; no changes to the stored N1 schema."""
import math


def finite_level(value):
    try:
        number = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def contact_slabs(contacts, pillar_top):
    """Keep each interval and its own proof; missing altitude is not zero."""
    result = []
    top = finite_level(pillar_top)
    for index, contact in enumerate(contacts):
        level = finite_level(contact.get('level_m'))
        # A regional change cannot inherit the parent's scalar altitude.
        if level is None and not contact.get('region_ids'):
            level = finite_level(contact.get('principal_level'))
        thickness = finite_level(contact.get('thickness_cm'))
        pending = []
        if contact.get('conflict'):
            pending.append('conflicting_contact_evidence')
            level = None
        if level is None:
            pending.append('missing_contact_level')
        if top is None:
            pending.append('missing_pillar_top')
        if thickness is None or thickness <= 0:
            pending.append('missing_contact_thickness')
        if level is not None and top is not None and level > top + 1e-8:
            pending.append('contact_above_pillar_top')
        result.append({
            'contact_id': f"{contact.get('slab_name', '')}:{index}",
            'slab_name': contact.get('slab_name') or '',
            'slab_dimension': str(thickness) if thickness is not None else '',
            'slab_behavior': 'laje',
            'left_distance': float(contact['left_distance_cm']),
            'right_distance': float(contact['right_distance_cm']),
            'width': float(contact['width_cm']),
            'height': thickness + 2.0 if thickness is not None and thickness > 0 else 0.0,
            'level': level,
            'top_distance': (top - level) * 100 if not pending else 0.0,
            'level_source': 'direct_region' if contact.get('level_m') is not None else 'principal_contact' if level is not None else 'unknown',
            'pending': pending,
        })
    return result


def contacts_from_tables(tables, pillar_top):
    """Convert only physical face intersections and locally supported levels."""
    return {fid: contact_slabs([
        dict(interval, slab_name=row.get('nome'),
             principal_level=row.get('nivel') if row.get('nivel_status') == 'sa' else None)
        for row in face.get('lajes') or []
        for interval in row.get('_contact_intervals') or []
    ], pillar_top) for fid, face in (tables.get('faces') or {}).items()
        if any('_contact_intervals' in row for row in face.get('lajes') or [])}


def apply_contact_openings(robot, contacts_by_face):
    """Replace scalar slab cuts only; preserve beam openings and panel meshes.

    This conversion is shared by batch N3 modes. Unknown contacts remain in the
    payload for item QA and never become an opening at an invented altitude.
    """
    from copy import deepcopy
    result = deepcopy(robot)
    height = finite_level(result.get('altura'))
    contract = result.get('_sa_mode_contract') or {}
    for fid, contacts in contacts_by_face.items():
        slabs = deepcopy(contacts)
        result[f'_portal_slabs_{fid}'] = slabs
        face = (contract.get('faces') or {}).get(fid) or {}
        sources = face.get('fontes_n1') or {}
        face.setdefault('_scalar_slab_sources', deepcopy(sources.get('lajes') or []))
        sources['lajes'] = []
        face['fontes_n1'] = sources
        for key in ('rebaixo_laje_cm', 'vazio_laje_cm', 'espessura_laje'):
            face[key] = 0.0
        face['nivel_laje'] = None
        for prefix in ('rebaixo_laje', 'vazio_laje', 'laje', 'posicao_laje'):
            result[f'{prefix}_{fid}'] = 0.0
        result[f'nivel_laje_{fid}'] = None
        # Rebuild a contiguous list: the generator stops at the first empty slot.
        opening_keys = [key for key in result if key == f'abertura_{fid}'
                        or key.startswith(f'abertura_{fid}_')]
        def order(key):
            suffix = key.removeprefix(f'abertura_{fid}_')
            return int(suffix) if suffix.isdigit() else 0
        beams = [result[key] for key in sorted(opening_keys, key=order)
                 if isinstance(result[key], dict) and result[key].get('_origem') != 'slab_contact']
        for key in opening_keys:
            result.pop(key)
        openings = deepcopy(beams)
        strip = finite_level(result.get(f'h1_geom_{fid}', result.get(f'h1_{fid}', 2))) or 0.0
        for slab in slabs:
            if slab.get('pending') or slab.get('level') is None:
                continue
            bottom = (height - slab['top_distance'] - slab['height']) if height is not None else None
            if bottom is None or bottom < strip - 1e-8:
                slab.setdefault('pending', []).append('contact_outside_pillar_height')
                continue
            if slab['width'] <= 0 or slab['height'] <= 0:
                continue
            openings.append({'lado': 'meio', 'largura': slab['width'], 'altura': slab['height'],
                             'x_offset': slab['left_distance'] + (11.0 if fid in 'AB' else 0.0),
                             'y_rel': bottom - strip, '_origem': 'slab_contact',
                             '_laje': slab.get('slab_name'), '_nivel_origem': slab['level']})
        result[f'abertura_{fid}'] = None
        for i, opening in enumerate(openings, 1):
            result[f'abertura_{fid}_{i}'] = opening
        result[f'abertura_{fid}_{len(openings) + 1}'] = None
    return result
