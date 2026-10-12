"""Bind a local numeric beam section to an explicit original change line."""
from __future__ import annotations

import math
import re
import hashlib
import json
from pathlib import Path


def reviewed_section_span(source_path, walls, labels, *, axis, positions,
                          span, anchor, closed_handles, tolerance_cm):
    """A human-selected original boundary is local authority, never a name rule."""
    if not source_path:
        return None
    source = Path(source_path)
    try:
        review = json.loads(source.with_suffix('.beam-section-review.json').read_text(encoding='utf8'))
        if (not isinstance(review, dict) or
                review.get('schema') != 'cad.original_beam_section_review/v1' or
                review.get('authority') != 'human' or
                review.get('source_sha256') != hashlib.sha256(source.read_bytes()).hexdigest()):
            return None
    except (OSError, ValueError):
        return None
    eps = tolerance_cm
    low, high = sorted(positions)
    start, end = sorted(span)
    if min(abs(anchor-start), abs(anchor-end)) > eps:
        return None
    across = 'y' if axis == 'x' else 'x'
    matches = []
    decisions = review.get('boundaries', [])
    if not isinstance(decisions, list):
        return None
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        if any(not isinstance(decision.get(side), dict) or
               not isinstance(decision[side].get('section'), str) or
               not isinstance(decision[side].get('section_handles'), list) or
               not all(isinstance(h, str) for h in decision[side]['section_handles'])
               for side in ('before', 'after')):
            continue
        if decision.get('verdict') != 'accepted' or decision.get('axis') != axis:
            continue
        boundary_kind = decision.get('boundary_kind', 'beam_cap')
        if boundary_kind not in {'beam_cap', 'reviewed_region_edge'}:
            continue
        # Only an explicit human review can select a region edge extending
        # beyond the beam. Automatic section detection still requires a cap.
        caps = [w for w in walls if w['handle'] == decision.get('boundary_handle')
                and w['handle'] not in closed_handles and w['axis'] != axis
                and ((boundary_kind == 'beam_cap' and
                      abs(w['lo']-low) <= eps and abs(w['hi']-high) <= eps)
                     or (boundary_kind == 'reviewed_region_edge' and
                         w['lo'] <= low+eps and w['hi'] >= high-eps))
                and start+eps < w['pos'] < end-eps]
        if len(caps) != 1:
            continue
        coord = caps[0]['pos']
        cells = [(start, coord), (coord, end)]
        valid = True
        for interval, side in zip(cells, ('before', 'after')):
            selected = [t for t in labels if interval[0]+eps < t[axis] < interval[1]-eps
                        and low-t['margin'] <= t[across] <= high+t['margin']
                        and re.fullmatch(r'\d+(?:[.,]\d+)?/\d+(?:[.,]\d+)?', t['text'])
                        and abs(float(t['text'].split('/')[0].replace(',', '.'))-(high-low)) <= eps
                        and abs(math.sin(math.radians(t['rotation']-(0 if axis=='x' else 90)))) < 1e-6]
            specified = decision.get(side) or {}
            valid = valid and {t['text'] for t in selected} == {specified.get('section')}
            valid = valid and bool(specified.get('section_handles')) and set(specified['section_handles']).issubset({t['handle'] for t in selected})
        if not valid or decision.get('before', {}).get('section') == decision.get('after', {}).get('section'):
            continue
        matches.append({'span': cells[0] if abs(anchor-start)<=eps else cells[1],
                        'handles': [caps[0]['handle']],
                        'adjacent_sections': sorted([decision['before']['section'],decision['after']['section']]),
                        'authority': 'human', 'review_id': decision.get('id')})
    return matches[0] if len(matches)==1 else None


def proved_section_cells(walls, labels, *, axis, positions, span,
                         closed_handles, tolerance_cm, source_path=None):
    """Partition continuous original walls only when every cell is numerical.

    This describes numeric ownership along one physical wall pair. It does
    not bridge a gap or assign an identity to that pair.
    """
    eps = tolerance_cm
    low, high = sorted(positions)
    start, end = sorted(span)
    across = 'y' if axis == 'x' else 'x'
    reviewed = reviewed_section_span(source_path, walls, labels, axis=axis,
        positions=positions, span=span, anchor=start,
        closed_handles=closed_handles, tolerance_cm=eps)
    if reviewed:
        coord = reviewed['span'][1]
        cells = []
        for a, b in ((start, coord), (coord, end)):
            tokens = [t for t in labels if a+eps < t[axis] < b-eps
                and low-t['margin'] <= t[across] <= high+t['margin']
                and re.fullmatch(r'\d+(?:[.,]\d+)?/\d+(?:[.,]\d+)?', t['text'])
                and abs(float(t['text'].split('/')[0].replace(',', '.'))-(high-low)) <= eps
                and abs(math.sin(math.radians(t['rotation']-(0 if axis=='x' else 90)))) < 1e-6]
            cells.append({'span': (a, b), 'section': tokens[0]['text'],
                          'section_handles': sorted({t['handle'] for t in tokens})})
        return {'cells': cells, 'handles': reviewed['handles'],
                'authority': reviewed['authority'], 'review_id': reviewed['review_id']}
    caps = [w for w in walls if w['axis'] != axis
            and w['handle'] not in closed_handles
            and abs(w['lo']-low) <= eps and abs(w['hi']-high) <= eps
            and start+eps < w['pos'] < end-eps]
    bounds = [start, *sorted({w['pos'] for w in caps}), end]
    if len(bounds) < 3:
        return None
    raw_values=[]
    for a,b in zip(bounds,bounds[1:]):
        raw_values.append({t['text'] for t in labels
            if re.fullmatch(r'\d+(?:[.,]\d+)?/\d+(?:[.,]\d+)?', t['text'])
            and abs(float(t['text'].split('/')[0].replace(',', '.'))-(high-low)) <= eps
            and abs(math.sin(math.radians(t['rotation']-(0 if axis == 'x' else 90)))) < 1e-6
            and a+eps < t[axis] < b-eps
            and low-t['margin'] <= t[across] <= high+t['margin']})
    changes=[i for i in range(1,len(raw_values)) if len(raw_values[i-1])==1 and
             len(raw_values[i])==1 and raw_values[i-1]!=raw_values[i]]
    if not changes:
        return None
    bounds=[start,*[bounds[i] for i in changes],end]
    cells = []
    for a, b in zip(bounds, bounds[1:]):
        tokens = [t for t in labels
            if re.fullmatch(r'\d+(?:[.,]\d+)?/\d+(?:[.,]\d+)?', t['text'])
            and abs(float(t['text'].split('/')[0].replace(',', '.'))-(high-low)) <= eps
            and abs(math.sin(math.radians(t['rotation']-(0 if axis == 'x' else 90)))) < 1e-6
            and a+eps < t[axis] < b-eps
            and low-t['margin'] <= t[across] <= high+t['margin']]
        if len({t['text'] for t in tokens}) != 1:
            return None
        cells.append({'span': (a,b), 'section': tokens[0]['text'],
                      'section_handles': sorted({t['handle'] for t in tokens})})
    if any(a['section'] == b['section'] for a,b in zip(cells,cells[1:])):
        return None
    return {'cells': cells, 'handles': sorted({w['handle'] for w in caps if w['pos'] in bounds[1:-1]})}


def own_section_span(walls, labels, *, axis, positions, span, anchor,
                     closed_handles, tolerance_cm, source_path=None):
    """Return the cell adjacent to the pillar only with bilateral numeric proof.

    An open original transverse segment must terminate on both beam walls.
    Each cell immediately beside it must contain one distinct, longitudinal
    section of the same measured width. A dimension, contour edge, partial or
    extended stroke, or an unlabelled/conflicting cell cannot define a change.
    No identity, height or measurement is transported across the change line.
    """
    reviewed = reviewed_section_span(source_path, walls, labels, axis=axis,
        positions=positions, span=span, anchor=anchor,
        closed_handles=closed_handles, tolerance_cm=tolerance_cm)
    if reviewed:
        return reviewed
    eps = tolerance_cm
    low, high = sorted(positions)
    start, end = sorted(span)
    if abs(anchor-start) > eps and abs(anchor-end) > eps:
        return None
    across = 'y' if axis == 'x' else 'x'
    sections = [t for t in labels
                if re.fullmatch(r'\d+(?:[.,]\d+)?/\d+(?:[.,]\d+)?', t['text'])
                and abs(float(t['text'].split('/')[0].replace(',', '.'))-(high-low)) <= eps
                and abs(math.sin(math.radians(t['rotation']-(0 if axis == 'x' else 90)))) < 1e-6
                and start-eps <= t[axis] <= end+eps
                and low-t['margin'] <= t[across] <= high+t['margin']]
    caps = [w for w in walls if w['axis'] != axis and
            w['handle'] not in closed_handles and
            abs(w['lo']-low) <= eps and abs(w['hi']-high) <= eps and
            start+eps < w['pos'] < end-eps]
    boundaries = sorted({w['pos'] for w in caps})
    if not boundaries:
        return None
    limits = [start, *boundaries, end]
    cells = [{t['text'] for t in sections if a+eps < t[axis] < b-eps}
             for a, b in zip(limits, limits[1:])]
    # A complete transverse stroke alone is not a numeric change. Diagrams
    # can contain additional full caps with no section callout on one side.
    # Keep only boundaries whose two immediate original cells independently
    # prove distinct sections, then require one section across the entire
    # anchor-side interval. Never skip a conflicting callout to reach a cap.
    changes=[i for i in range(1,len(cells)) if len(cells[i-1])==1 and
             len(cells[i])==1 and cells[i-1]!=cells[i]]
    if not changes:
        return None
    from_start=abs(anchor-start)<=eps
    index=changes[0] if from_start else changes[-1]
    coord=limits[index]
    own_span=(start,coord) if from_start else (coord,end)
    own_values={t['text'] for t in sections if own_span[0]+eps<t[axis]<own_span[1]-eps}
    opposite=cells[index] if from_start else cells[index-1]
    if len(own_values)!=1 or own_values==opposite:
        return None
    return {'span': own_span,
            'handles': sorted({w['handle'] for w in caps if abs(w['pos']-coord) <= eps}),
            'adjacent_sections': sorted(own_values | opposite)}
