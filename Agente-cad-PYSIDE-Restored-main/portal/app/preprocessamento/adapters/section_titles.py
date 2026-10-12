"""Recover explicit section headers omitted from individual derived crops.

This links a source title to an island, never a section to a structural item.
Ambiguous neighbors remain unresolved. Original geometry is not modified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .auxiliary import semantic_roles


def associate_titles(titles, islands):
    links = []
    for title in titles:
        x, y = title['position']
        height = title.get('height', 0)
        if height <= 0:
            continue
        containing, nearby = [], []
        for island in islands:
            x0, y0, x1, y1 = island['bbox']
            if not x0 <= x <= x1:
                continue
            if y0 <= y <= y1:
                containing.append(island)
            elif min(abs(y - y0), abs(y - y1)) <= 4 * height:
                nearby.append(island)
        candidates = containing or nearby
        links.append({**title, 'status': 'unique_island' if len(candidates) == 1 else
                      'ambiguous_islands' if candidates else 'no_island',
                      'candidate_files': [i['file'] for i in candidates],
                      'association_authority': 'explicit_title_and_local_geometry',
                      'item_association_status': 'unresolved'})
    return links


def enrich_section_titles(obra_dir, sources, raw_reference, auxiliary):
    if not raw_reference:
        return
    root = Path(obra_dir)
    raw_path = root / raw_reference['relative_path']
    revision = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if revision != raw_reference['revision']:
        raise ValueError('section_title_raw_revision_changed')
    import ezdxf
    titles = []
    for entity in ezdxf.readfile(raw_path).modelspace().query('TEXT MTEXT'):
        text = {'text': entity.dxf.text if entity.dxftype() == 'TEXT' else entity.plain_mtext(),
                'handle': entity.dxf.handle, 'position': list(entity.dxf.insert)[:2]}
        roles = [r for r in semantic_roles([text]) if r['role'] == 'named_section']
        if roles:
            titles.append({**roles[0], 'height': float(entity.dxf.height if
                           entity.dxftype() == 'TEXT' else entity.dxf.char_height),
                           'origin_source_id': raw_reference['source_id'],
                           'origin_revision': revision})
    by_id = {a['source_id']: a for a in auxiliary}
    directories = {Path(s.relative_path).parent for s in sources
                   if s.bruto_id == raw_reference['bruto_id'] and s.kind.value == 'other'}
    for directory in directories:
        manifest = root / directory / 'islands.json'
        if not manifest.is_file():
            continue
        data = json.loads(manifest.read_text(encoding='utf8'))
        if data.get('source_sha256') != revision:
            continue
        for link in associate_titles(titles, data.get('islands', [])):
            if link['status'] != 'unique_island':
                continue
            file = link['candidate_files'][0]
            matching = [s for s in sources if Path(s.relative_path) == directory / file
                        and s.bruto_id == raw_reference['bruto_id']]
            if len(matching) != 1 or matching[0].source_id not in by_id:
                continue
            evidence = by_id[matching[0].source_id]
            if evidence.get('status') == 'failed':
                continue
            link['title_present_in_crop'] = any(t['handle'] == link['title_handle']
                                                for t in evidence.get('texts', []))
            link['crop_revision'] = matching[0].revision
            link['manifest_revision'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            evidence.setdefault('section_title_links', []).append(link)
    from .section_callouts import enrich_plan_callouts
    enrich_plan_callouts(root, sources, raw_reference, auxiliary)
