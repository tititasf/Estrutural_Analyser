"""Consume human role decisions bound to an unchanged original DXF.

Role ownership is independent of altitude. Preserve entities and footprints;
reject stale reviews, missing handles, altered contours and competing decisions.
"""
import hashlib
import json
from pathlib import Path

from shapely.geometry import Polygon


def inventory_source_role_reviews(path, slabs=()):
    import ezdxf

    path = Path(path)
    revision = hashlib.sha256(path.read_bytes()).hexdigest()
    result = {'source_sha256': revision, 'records': [], 'rejected': [],
              'level_transfer_authorized': False}
    sidecar = path.with_suffix('.source-role-review.json')
    if not sidecar.exists():
        return result
    try:
        review = json.loads(sidecar.read_text(encoding='utf8'))
        if review.get('source_sha256') != revision:
            result['rejected'].append({'reason': 'source_revision_mismatch'})
            return result
        records = review['records']
        if not isinstance(records, list):
            raise ValueError('records must be a list')
    except (ValueError, KeyError, TypeError, AttributeError):
        result['rejected'].append({'reason': 'invalid_review'})
        return result
    doc = ezdxf.readfile(path)
    owners = {}
    for slab in slabs:
        try:
            contour = Polygon(slab['points'])
            if contour.is_valid and contour.area > 0:
                owners.setdefault(slab['name'], []).append(contour)
        except (KeyError, TypeError, ValueError):
            continue
    valid = []
    for record in records:
        try:
            role = record['role']
            handles = record['source_entity_handles']
            if (role not in ('nonstructural_wall', 'slab_region')
                    or record.get('authority') != 'human_owner'
                    or not record.get('decision_id') or not record.get('human_answer')
                    or record.get('level_transfer_authorized') is not False
                    or not isinstance(handles, list) or not handles
                    or any(not isinstance(h, str) or not h for h in handles)):
                raise ValueError('invalid_role_contract')
            expected = Polygon(record['original_points'])
            if not expected.is_valid or expected.area <= 0:
                raise ValueError('invalid_contour')
            for handle in handles:
                entity = doc.entitydb.get(handle)
                if entity is None or entity.dxftype() != 'LWPOLYLINE':
                    raise ValueError('source_handle_missing_or_wrong_type')
                raw = list(entity.get_points())
                if any(p[4] != 0 for p in raw):
                    raise ValueError('curved_contour_not_supported')
                actual = Polygon([p[:2] for p in raw])
                if not actual.is_valid or not actual.equals(expected):
                    raise ValueError('source_contour_mismatch')
            owner = record.get('owner')
            if role == 'slab_region':
                matches = owners.get(owner, [])
                if len(matches) != 1 or not matches[0].covers(expected):
                    raise ValueError('slab_owner_not_unique_or_not_covering_region')
            elif owner != 'outside_pillar_scope':
                raise ValueError('invalid_wall_owner')
            valid.append({**record, 'status': 'proved', 'content_preserved': True,
                          'consumer_authorized': 'source_role_only',
                          'source_sha256': revision})
        except (KeyError, TypeError, ValueError) as error:
            result['rejected'].append({'decision_id': record.get('decision_id') if isinstance(record, dict) else None,
                                       'reason': str(error)})
    for record in valid:
        competing = [other for other in valid if other is not record
                     and set(record['source_entity_handles']) & set(other['source_entity_handles'])
                     and (record['role'], record['owner']) != (other['role'], other['owner'])]
        if competing:
            result['rejected'].append({'decision_id': record['decision_id'], 'reason': 'competing_role_decisions'})
        elif record not in result['records']:
            result['records'].append(record)
    return result
