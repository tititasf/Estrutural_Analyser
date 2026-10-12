"""Recover a cropped-out level unit from the exact immutable parent drawing.

Only unchanged geometric elevation markers qualify. This confirms floor-marker
units, never establishes an item, face, region or independent evidence vote.
"""
from pathlib import Path
import hashlib

from .level_convention import extract_level_convention, _LEVEL_UNIT


def _fingerprint(entity):
    if entity is None:
        return None
    kind = entity.dxftype()
    if kind in {'TEXT', 'MTEXT'}:
        text = entity.dxf.text if kind == 'TEXT' else entity.plain_mtext()
        height = entity.dxf.height if kind == 'TEXT' else entity.dxf.char_height
        return kind, text, tuple(entity.dxf.insert), height, entity.dxf.get('rotation', 0)
    if kind == 'POLYLINE':
        return kind, entity.is_closed, tuple(
            (tuple(v.dxf.location), v.dxf.get('bulge', 0)) for v in entity.vertices)
    if kind == 'LWPOLYLINE':
        return kind, entity.is_closed, entity.dxf.get('elevation', 0), tuple(entity.get_points())
    return None


def _inside(root, relative):
    target = (root / relative).resolve()
    return target if root in target.parents and target.is_file() else None


def enrich_source_level_units(obra_dir, sources, raw_reference, auxiliary):
    """Inherit explicit COTAS/NÍVEIS units after scope, hashes and entity checks.

    Generic drawing units do not certify elevation units. Ambiguous raw readings,
    altered copies and another parent drawing stay unresolved.
    """
    if not raw_reference:
        return
    root = Path(obra_dir).resolve()
    raw_path = _inside(root, raw_reference['relative_path'])
    if raw_path is None or hashlib.sha256(raw_path.read_bytes()).hexdigest() != raw_reference['revision']:
        return
    raw_levels = extract_level_convention(raw_path)
    declarations = [t for t in raw_levels['unit_declarations'] if _LEVEL_UNIT.search(t['text'])]
    unit = raw_levels['unit']
    if unit not in {'m', 'cm'} or not declarations:
        return
    import ezdxf
    original = ezdxf.readfile(str(raw_path))
    originals = {row['floor_text_handle']: row for row in raw_levels['direct_floor_levels']}
    by_id = {source.source_id: source for source in sources}
    for entry in auxiliary:
        convention = entry.get('level_convention') or {}
        pending = [row for row in convention.get('direct_floor_levels', [])
                   if row.get('selected') and row['selected'].get('method') == 'elevation_triangle'
                   and not row['selected'].get('unit')]
        if not pending:
            continue
        source = by_id.get(entry['source_id'])
        if source is None or entry.get('source_revision') != source.revision:
            continue
        if any(getattr(source, key) != raw_reference.get(key)
               for key in ('obra_id', 'pavimento_id', 'bruto_id')):
            continue
        crop_path = _inside(root, source.relative_path)
        if crop_path is None or hashlib.sha256(crop_path.read_bytes()).hexdigest() != source.revision:
            continue
        crop = ezdxf.readfile(str(crop_path))
        for row in pending:
            selected = row['selected']
            original_row = originals.get(row['floor_text_handle']) or {}
            original_selected = original_row.get('selected') or {}
            if (original_row.get('status') != 'direct'
                    or original_selected.get('method') != 'elevation_triangle'
                    or original_selected.get('unit') != unit
                    or original_row.get('floor_label') != row['floor_label']
                    or any(selected.get(key) != original_selected.get(key)
                           for key in ('text_handle', 'marker_handle', 'raw', 'value', 'position'))):
                continue
            handles = [row['floor_text_handle'], selected['text_handle'], selected['marker_handle']]
            if any(_fingerprint(original.entitydb.get(handle)) is None
                   or _fingerprint(original.entitydb.get(handle)) != _fingerprint(crop.entitydb.get(handle))
                   for handle in handles):
                continue
            selected['unit'] = unit
            # Candidates and selected may be distinct after JSON serialization.
            for candidate in row.get('candidates', []):
                if candidate.get('text_handle') == selected['text_handle']:
                    candidate['unit'] = unit
            row['unit_provenance'] = {
                'status': 'confirmed_same_original_entities',
                'origin_source_id': raw_reference['source_id'],
                'origin_revision': raw_reference['revision'],
                'declaration_handles': [t['handle'] for t in declarations],
                'matched_entity_handles': handles,
                'unit': unit, 'independent_vote_count': 0,
                'authority': 'explicit_parent_level_unit',
                'item_numeric_authority': 'none',
            }
