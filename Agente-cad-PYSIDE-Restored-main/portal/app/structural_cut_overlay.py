"""Shared, read-only SA section inventory and actual-size structural overlays.

Calculated sections remain separate from CAD originals. A frozen precollection
is evidence for a second pass, never a replacement for its current geometry.
"""
from copy import deepcopy
from math import hypot
import json

from . import ficha_reader, lv_ficha
from .lv_cut_map import section_drawings


def missing_step_sections(entry, state):
    """Only local step regions without a CAD transition section need yellow."""
    missing = {(str(slab.get('name')), str(step.get('uid')))
               for slab in state.get('slabs') or []
               for step in slab.get('slab_steps') or []
               if step.get('uid') and not step.get('sections')}
    pairs = (entry.get('section_contract') or {}).get('pairs') or entry.get('pairs') or []
    return sorted({str(slab.get('name'))
                   for pair in pairs
                   for profile in (pair.get('profiles') or {}).values()
                   for slab in profile.get('slabs') or []
                   if (str(slab.get('name')), str(slab.get('region_id'))) in missing})


def _section_geometry(entry, relative=False):
    anchor = entry['drawing'].get('anchor', [0, 0]) if relative else [0, 0]
    return tuple((p['kind'],
                  tuple(tuple(round(float(v)-anchor[i], 3) for i, v in enumerate(q))
                        for q in p['points']),
                  p.get('text') if p.get('role') != 'section_title' and p.get('size') != 8 else None)
                 for p in entry['drawing']['primitives'])


def _pairs_overlap(first, second):
    """Require a real shared station, not merely the same section elsewhere."""
    for a in first.get('pairs') or []:
        start, end = a['start'], a['end']
        length = hypot(end[0]-start[0], end[1]-start[1])
        if length <= .01:
            continue
        u = [(end[i]-start[i])/length for i in (0, 1)]
        for b in second.get('pairs') or []:
            pts = [b['start'], b['end']]
            # These are points on the same A face, in CAD coordinates.
            if any(abs((p[0]-start[0])*u[1]-(p[1]-start[1])*u[0]) > .1 for p in pts):
                continue
            stations = [sum((p[i]-start[i])*u[i] for i in (0, 1)) for p in pts]
            if min(length, max(stations))-max(0, min(stations)) > .01:
                return True
    return False


def deduplicate_sections(entries):
    """Coalesce Para/Passa presentations of the same physical section.

    Their longest common intervals may have different midpoints. Preserve the
    first canonical drawing and both provenances, including the alternate pairs.
    Also handles frozen inventories generated before this deduplication rule.
    """
    result, seen = [], {}
    for source in entries:
        entry = deepcopy(source)
        if entry.get('fundo_id') and entry['kind'] != 'identified':
            from .lv_cut_coverage import profile_key
            previous = next((e for e in result if e.get('fundo_id') == entry['fundo_id']
                             and e['kind'] == entry['kind']
                             and (profile_key(e['section_contract']) == profile_key(entry['section_contract'])
                                  if e.get('section_contract') and entry.get('section_contract')
                                  else _section_geometry(e, True) == _section_geometry(entry, True))), None)
            if previous is not None:
                previous['behaviors'] = list(dict.fromkeys(previous['behaviors'] + entry['behaviors']))
                continue
        identified = entry['kind'] == 'identified'
        key = (entry['beam'], entry['kind'], _section_geometry(entry, relative=not identified))
        candidate = next((e for e in seen.get(key, [])
                          if (identified or
                              (not set(e.get('behaviors', [e['behavior']])).intersection(
                               entry.get('behaviors', [entry['behavior']])) and
                               _pairs_overlap(e, entry)))), None)
        if candidate is None:
            seen.setdefault(key, []).append(entry)
            result.append(entry)
            continue
        candidate['behaviors'] = list(dict.fromkeys(
            candidate.get('behaviors', [candidate['behavior']]) +
            entry.get('behaviors', [entry['behavior']])))
        candidate.setdefault('alternate_presentations', []).append(dict(
            behavior=entry['behavior'], cut_index=entry['cut_index'],
            anchor=entry['drawing'].get('anchor'), pairs=entry.get('pairs', [])))
    return result


def displayed_soffit_coverage(groups, entries, state):
    """Audit current displayed intervals, retaining merged source ownership."""
    from shapely.geometry import Point, Polygon
    owners = {s['uid']: s for s in (state.get('segmentos') or {}).get('fundo', [])}
    rows = []
    for group in groups:
        if group.get('grupo') not in ('fundo', 'fundos'):
            continue
        for item in group.get('itens', []):
            uid = item.get('item_id')
            owner = owners.get(uid, {})
            polygon = Polygon(item.get('pontos_dxf') or [])
            hits = [e for e in entries if e.get('beam') == item.get('beam_name')
                    and e.get('drawing', {}).get('anchor')
                    and polygon.buffer(.2).covers(Point(e['drawing']['anchor']))]
            original = [e['cut_index'] for e in hits if e['kind'] == 'identified']
            interpreted = [e['cut_index'] for e in hits if e['kind'] != 'identified']
            index = item.get('display_segment_index')
            rows.append(dict(fundo_id=uid, display_id=f'{uid}:display:{index}' if index else uid,
                beam=item.get('beam_name'), segment=index or item.get('segmento'),
                source_fundo_ids=list(dict.fromkeys([uid, *(owner.get('merged_source_uids') or [])])),
                status='mixed' if original and interpreted else 'original' if original else
                       'interpreted' if interpreted else 'pending',
                cut_indexes=original, interpreted_cut_indexes=interpreted))
    return rows


def runner_sections(root, floor, runner):
    from pathlib import Path
    from src.core.preficha_segments import collect_preficha_segments, serializable_segment
    slabs = list(getattr(runner, 'slabs_found', []) or [])
    segments = collect_preficha_segments(list(getattr(runner, 'beams_found', []) or []), slabs,
        getattr(runner, 'pavimento_pillar_report', {}) or {},
        getattr(runner, 'pavimento_nivel_report', {}) or {})
    state = dict(pavimento=floor, slabs=slabs,
                 pilares=list((getattr(runner, 'pavimento_pillar_report', {}) or {}).values())
                          or list(getattr(runner, 'pillars_found', []) or []),
                 _section_beam_records={str(b['id']): b for b in runner.beams_found if b.get('id')},
                 segmentos={k: [serializable_segment(s) for s in v] for k, v in segments.items()})
    return collect_sections(Path(root), floor, state)


def collect_sections(root, floor, state, behavior='misto', *, beam_names=None):
    entries, blocked, seen, coverage = [], [], {}, {}
    physical_entries = []
    requested = {str(name).upper() for name in beam_names} if beam_names is not None else None
    reference_context = {}
    modes = ('passa', 'para') if behavior == 'misto' else (behavior,)
    for mode in modes:
        names = sorted({s.get('beam_name') for side in ('a', 'b')
                        for s in (state.get('segmentos') or {}).get(f'lateral_{side}_{mode}', [])
                        if s.get('beam_name')})
        for name in names:
            if requested is not None and name.upper() not in requested:
                continue
            try:
                data = lv_ficha.montar_ficha_lv(root, floor, name, mode, state, include_svgs=False,
                                               reference_context=reference_context)
            except ValueError as exc:
                blocked.append(dict(beam=name, behavior=mode, reason=str(exc),
                                    stage='assemble_lateral_sections'))
                continue
            from .lv_cut_coverage import soffit_drawings
            cuts = data.get('sa_cut_views', data['cut_views'])
            # Generation consumes every physical interval, including ones
            # hidden by original-cut precedence or blocked in the overlay.
            from src.core.lv_n3_cut_contract import build_cut_contract
            physical_cuts = data.get('physical_cut_views')
            if physical_cuts is None:
                physical_cuts = [*cuts, *data.get('cap_cut_views', [])]
            for cut in physical_cuts:
                for pair in cut.get('pairs') or [None]:
                    local = deepcopy(cut)
                    local['pairs'] = [deepcopy(pair)] if pair else []
                    if pair and pair.get('profiles'):
                        local['profiles'] = deepcopy(pair['profiles'])
                    physical = dict(beam=name, behavior=mode, pairs=local['pairs'],
                        section_semantics=deepcopy(cut.get('section_semantics') or
                            (cut.get('source_cut') or {}).get('section_semantics') or {}))
                    if pair and not physical['section_semantics'].get('confirmed'):
                        from src.core.beam_vertical_context import end_joint_footprint
                        record = next((r for r in (state.get('_section_beam_records') or {}).values()
                                       if str(r.get('name') or '').upper() == name.upper()), {})
                        joint = end_joint_footprint(pair, record.get('_measured_corridor'), cut.get('width_cm'))
                        if joint:
                            physical['pairs'][0]['joint_footprint'] = joint
                            physical['pairs'][0]['joint_source'] = 'current_measured_concrete_corridor'
                    try:
                        physical['section_contract'] = deepcopy(cut.get('cap_contract')) or build_cut_contract(local)
                    except ValueError as exc:
                        physical['pending'] = str(exc)
                    physical_entries.append(physical)
            fundos = [s for s in (state.get('segmentos') or {}).get('fundo', [])
                      if str(s.get('beam_name') or '').upper() == name.upper()]
            drawings, failures, rows = soffit_drawings(cuts, data['sides'], fundos, state.get('pilares') or [])
            for row in rows:
                previous = coverage.get(row['fundo_id'])
                if previous is None or previous['status'] == 'pending' or row['status'] == 'original':
                    coverage[row['fundo_id']] = dict(row, behavior=mode)
            blocked.extend(dict(beam=name, behavior=mode, **f) for f in failures)
            for drawing in drawings:
                cut = cuts[drawing['cut_index']]
                from src.core.lv_n3_cut_contract import build_cut_contract
                section_contract = drawing.get('section_contract') or build_cut_contract(cut)
                # Identical Para/Passa presentation is drawn once, with both
                # provenances retained. No merging across beams or anchors.
                key = (name, tuple(round(v, 3) for v in drawing['anchor']),
                       tuple((p['kind'], tuple(tuple(round(v, 3) for v in q) for q in p['points']),
                              p.get('text') if p.get('size') != 8 else None)
                             for p in drawing['primitives']))
                if key in seen:
                    seen[key]['behaviors'].append(mode)
                    continue
                entry = {'beam': name, 'behavior': mode, 'behaviors': [mode], 'kind': cut['kind'],
                    'fundo_id': drawing.get('fundo_id'),
                    'cut_index': drawing['cut_index'], 'source_cut': deepcopy(cut.get('source_cut')),
                    'pairs': deepcopy(cut.get('pairs') or []),
                    'fingerprint': (cut.get('layers') or {}).get('n3_cut', {}).get('fingerprint'),
                    'section_contract': deepcopy(section_contract),
                    'drawing': drawing}
                seen[key] = entry
                entries.append(entry)
    entries = deduplicate_sections(entries)
    for segment in (state.get('segmentos') or {}).get('fundo', []):
        if requested is not None and str(segment.get('beam_name') or '').upper() not in requested:
            continue
        coverage.setdefault(segment['uid'], dict(fundo_id=segment['uid'], beam=segment.get('beam_name'),
            segment=segment.get('segment_label'), status='pending', reason='sem laterais A/B disponíveis'))
    slab_sections = []
    for slab in state.get('slabs') or []:
        for step in slab.get('slab_steps') or []:
            for section in step.get('sections') or []:
                try:
                    drawing = slab_section_drawing(slab, step, section)
                    slab_sections.append(dict(slab=slab['name'],
                        item_id=section.get('uid') or f"slab-cut:{slab['name']}:{section.get('handle')}",
                        points=section['points'], drawing=drawing))
                except ValueError as exc:
                    blocked.append(dict(slab=slab['name'], reason=str(exc)))
    from .slab_step_overlay import missing_drawings
    interpreted_slab_sections, step_failures = missing_drawings(state)
    blocked.extend(step_failures)
    return {'schema': 'cad.preprocess.beam_sections/v1', 'entries': entries,
            'relative_originals': [dict(id=r['uid'], beam=r.get('beam_name'),
                kind='identified', source_cut=r) for _, cuts, _ in
                reference_context.get('sources', {}).values() for r in cuts] +
                [dict(id=e['section_contract']['id'], beam=e['beam'], kind='identified',
                    source_cut=e['source_cut']) for e in entries if e.get('kind') == 'identified'],
            'physical_entries': physical_entries,
            'slab_sections': slab_sections,
            'interpreted_slab_sections': interpreted_slab_sections,
            'blocked': blocked, 'total': len(entries),
            'soffit_coverage': list(coverage.values()),
            'calculated': sum(e['kind'] != 'identified' for e in entries),
            'identified': sum(e['kind'] == 'identified' for e in entries)}


def compare_sections(frozen, current):
    """Compare physical section + anchor, independent of generated database IDs."""
    def geometry(entry):
        return tuple((p['kind'],
                      tuple(tuple(round(float(v), 2) for v in q) for q in p['points']),
                      p.get('text') if p.get('size') != 8 else None)
                     for p in entry['drawing']['primitives'])
    def keys(inventory):
        return {(e['beam'], e['kind'], e.get('fingerprint'),
                 json.dumps(semantic(e.get('section_contract') or {}),
                            sort_keys=True, ensure_ascii=False),
                 tuple(round(v, 2) for v in e['drawing']['anchor']), geometry(e))
                for e in inventory.get('entries', [])}
    def semantic(value):
        if isinstance(value, dict):
            return {k: semantic(v) for k, v in value.items() if k not in
                    ('id', 'fingerprint', 'pairs', 'evidence_ids', 'source_section_id',
                     'symbol_handles', 'frame')}
        if isinstance(value, list):
            return [semantic(v) for v in value]
        return value
    before, after = keys(frozen), keys(current)
    return {'status': 'matches' if before == after else 'divergent',
            'matched': len(before & after), 'only_preprocessing': len(before - after),
            'only_sa': len(after - before), 'preprocessing_total': len(before),
            'sa_total': len(after), 'human_confirmation': 'pending'}


def slab_section_drawing(slab, step, section):
    """Dimension each measured thickness of a slab step in its CAD orientation."""
    from shapely.geometry import Polygon, LineString, Point
    polygon = Polygon(section['points'])
    region = Polygon(step['points'])
    x0, y0, x1, y1 = polygon.bounds
    vertical = y1-y0 > x1-x0
    lo, hi = (y0, y1) if vertical else (x0, x1)
    primitives = [dict(kind='polygon', points=section['points'], color='#ffe033')]
    samples = {}
    for ratio in (.2, .35, .65, .8):
        station = lo+(hi-lo)*ratio
        line = LineString([(x0-1, station), (x1+1, station)] if vertical else
                          [(station, y0-1), (station, y1+1)])
        intersection = polygon.intersection(line)
        if intersection.is_empty or intersection.geom_type != 'LineString':
            continue
        a, b = list(intersection.coords)[0], list(intersection.coords)[-1]
        inside = region.covers(Point((a[0]+b[0])/2, (a[1]+b[1])/2))
        height = step['height_cm'] if inside else step['owner_height_cm']
        if height <= 0 or hypot(b[0]-a[0], b[1]-a[1]) <= .01:
            continue
        samples.setdefault(inside, (a, b, height))
    if len(samples) != 2:
        raise ValueError('duas espessuras do corte de laje não localizadas')
    for inside, (a, b, height) in samples.items():
        # Offset the dimension away from the section, never across its text.
        offset = -8 if inside else 8
        delta = [0, offset] if vertical else [offset, 0]
        p, q = [[v[i]+delta[i] for i in (0, 1)] for v in (a, b)]
        primitives.append(dict(kind='line', points=[p, q], color='#fff38c'))
        for end in (p, q):
            primitives.append(dict(kind='line', points=[[end[0]-1.5,end[1]-1.5],
                                                       [end[0]+1.5,end[1]+1.5]], color='#fff38c'))
        anchor = [(p[i]+q[i])/2 for i in (0, 1)]
        anchor[1 if vertical else 0] += -6 if inside else 6
        primitives.append(dict(kind='text', points=[anchor, [anchor[0]+1, anchor[1]]],
                               text=f'{height:g}', size=5, color='#ffffff'))
    anchor = [(x0+x1)/2, y1+18]
    primitives.append(dict(kind='text', points=[anchor, [anchor[0]+1,anchor[1]]],
        text=f"{slab['name']} · corte de laje", size=8, color='#ffffff'))
    return dict(anchor=[(x0+x1)/2,(y0+y1)/2], primitives=primitives)


def align_highlight_dividers(spans, lines, labels=()):
    """Prefer a unique full-width CAD divider over a stored label midpoint."""
    if len(spans) < 2:
        return spans
    result = deepcopy(spans)
    for left, right in zip(result, result[1:]):
        a, b = left['geometry'], right['geometry']
        shared = set(map(tuple, a)) & set(map(tuple, b))
        if len(shared) != 2:
            continue
        shared = sorted(shared)
        if (abs(shared[0][0]-shared[1][0]) >= .001
                and abs(shared[0][1]-shared[1][1]) >= .001):
            continue
        axis = 1 if abs(shared[0][1]-shared[1][1]) < .001 else 0
        transverse = 1-axis
        boundary = shared[0][axis]
        centers = [sum((min(p[axis] for p in pts), max(p[axis] for p in pts)))/2 for pts in (a,b)]
        lo, hi = sorted(centers)
        wall_lo, wall_hi = sorted(p[transverse] for p in shared)
        direction = 1 if centers[1] > centers[0] else -1
        label_stations = []
        for row, side in ((left, -1), (right, 1)):
            stations = [r['pos'][axis] for r in labels
                        if r.get('text', '').strip().replace(' ', '') == row.get('dim_text')
                        and wall_lo-40 <= r['pos'][transverse] <= wall_hi+40
                        and (r['pos'][axis]-boundary)*direction*side > 0]
            if stations:
                label_stations.append(min(stations, key=lambda s: abs(s-boundary)))
        if len(label_stations) == 2:
            lo, hi = sorted(label_stations)
        candidates = set()
        for x0,y0,x1,y1 in lines:
            p,q = [x0,y0],[x1,y1]
            if (abs(p[axis]-q[axis]) < .001 and lo < p[axis] < hi
                    and abs(min(p[transverse],q[transverse])-wall_lo) <= .15
                    and abs(max(p[transverse],q[transverse])-wall_hi) <= .15):
                candidates.add(p[axis])
        if len(candidates) != 1:
            continue
        measured = candidates.pop()
        delta = (measured-boundary) * (1 if centers[1] > centers[0] else -1)
        left['vertical_partition']['end_cm'] += delta
        right['vertical_partition']['start_cm'] += delta
        left['length'] += delta
        right['length'] -= delta
        for row in (left,right):
            for p in row['geometry']:
                if abs(p[axis]-boundary) < .001:
                    p[axis] = measured
            row['highlight_boundary_source'] = 'structural_transverse_divider'
    return result


def viewer_groups(root, floor, state, transform, groups, behavior='misto', inventory=None):
    """Upgrade original cuts and publish calculated ones as a distinct group."""
    inventory = inventory if inventory is not None else state.get('_current_beam_sections')
    inventory = inventory if inventory is not None else collect_sections(root, floor, state, behavior)
    result = deepcopy(groups)
    from .structural_review import load as load_reviews, status as review_status, entry_id
    decisions = load_reviews(root, floor) if root is not None else {}
    # Use the complete physical inventory, including repeated local profiles.
    # A beam name or one representative section cannot classify a whole span.
    from src.core.beam_vertical_context import split_inverted_soffit
    from src.core.beam_vertical_context import partition_inverted_lateral
    from src.core.lv_generation_contract import _terminal_pillar_profiles
    pillar_bboxes = {}
    for pillar in state.get('pilares') or []:
        points = pillar.get('points') or []
        if points:
            pillar_bboxes[str(pillar.get('name') or pillar.get('id') or '')] = (
                min(float(p[0]) for p in points), min(float(p[1]) for p in points),
                max(float(p[0]) for p in points), max(float(p[1]) for p in points))
    lateral_sources = {str(s.get('uid')): s
                       for key, rows in (state.get('segmentos') or {}).items()
                       if key.startswith('lateral_') for s in rows}
    for group in result:
        if not str(group.get('grupo') or '').startswith(('lat_', 'lateral')):
            continue
        highlighted = []
        inverted_segment_count = 0
        for item in group.get('itens', []):
            name = str(item.get('beam_name') or '').upper()
            side = str(item.get('lado') or '').upper()
            if side not in ('A', 'B'):
                side = 'B' if '_b_' in str(item.get('classe_sa') or group['grupo']) else 'A'
            entries = [e for e in inventory.get('physical_entries', [])
                       if str(e.get('beam') or '').upper() == name
                       and (e.get('section_contract') or {}).get('beam_type') == 'inverted']
            try:
                source = lateral_sources.get(str(item.get('item_id'))) or {}
                if entries and str(item.get('classe_sa') or group['grupo']).endswith('_passa'):
                    entries = _terminal_pillar_profiles(
                        dict(points=item.get('pontos_dxf'), lv_cell=source.get('lv_cell') or {}),
                        entries, pillar_bboxes, side)
                spans = partition_inverted_lateral(item.get('pontos_dxf'), entries, side) if entries else []
            except ValueError:
                spans = []
            if not spans or any(s.get('pending') for s in spans):
                highlighted.append(item)
                continue
            # One solid color per logical segment, including all its local pieces.
            inverted_color = ('#ff4545', '#ffffff')[inverted_segment_count % 2]
            inverted_segment_count += 1
            piece = deepcopy(item)
            piece.update(highlight_color=inverted_color, beam_type='inverted',
                         vertical_partitions=[deepcopy(s['vertical_partition']) for s in spans])
            # The structural viewer shows logical segments. Local mounting
            # profiles remain available to N3 without drawing extra seams.
            highlighted.append(piece)
        group['itens'] = highlighted
        group['total'] = len(highlighted)
    for group in result:
        if group.get('grupo') not in ('fundo', 'fundos'):
            continue
        highlighted = []
        split_beams = set()
        for item in group.get('itens', []):
            highlighted.append(item)
            name = str(item.get('beam_name') or '').upper()
            entries = [e for e in inventory.get('physical_entries', [])
                       if name and str(e.get('beam') or '').upper() == name]
            if not entries or not item.get('pontos_dxf'):
                continue
            try:
                spans = split_inverted_soffit(dict(geometry=item['pontos_dxf']), entries)
            except ValueError:
                continue
            if spans:
                if len(spans) > 1 and root is not None:
                    from .ficha_reader import _fonte_estrutural_producao
                    from src.core.fv_inverted_crossings import structural_lines_from_dxf
                    source = None
                    if source is None:
                        # Persisted SA may have no production manifest; resolve
                        # its own project rather than another floor's drawing.
                        import re
                        import sqlite3
                        from pathlib import Path
                        match = re.search(r'\|([a-f0-9-]{36})_b_', str(item.get('item_id') or ''))
                        db_path = Path(str(state.get('db_path') or ''))
                        if match and db_path.is_file():
                            with sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro', uri=True) as db:
                                row = db.execute('SELECT dxf_path FROM projects WHERE id=?',
                                                 (match.group(1),)).fetchone()
                            candidate = Path(row[0]).resolve() if row and row[0] else None
                            if candidate and candidate.is_file() and candidate.is_relative_to(Path(root).resolve()):
                                source = candidate
                    if source is None:
                        source = _fonte_estrutural_producao(root, floor)
                    if source:
                        from .lv_cut_sources import _dimension_labels
                        stat = source.stat()
                        spans = align_highlight_dividers(spans, structural_lines_from_dxf(
                            str(source), (stat.st_mtime_ns, stat.st_size)),
                            _dimension_labels(str(source), (stat.st_mtime_ns, stat.st_size)))
                # Keep the measured SA owner, but draw each physical height
                # interval separately. Coloring the owner polygon alone hid
                # transitions even though split_inverted_soffit found them.
                highlighted.pop()
                if len(spans) > 1:
                    split_beams.add(name)
                for span in spans:
                    piece = deepcopy(item)
                    points = span['geometry']
                    piece.update(pontos_dxf=points,
                                 pontos_px=[transform.dxf_para_px(*p) for p in points],
                                 bbox_dxf=[min(p[0] for p in points), min(p[1] for p in points),
                                           max(p[0] for p in points), max(p[1] for p in points)],
                                 highlight_color='#ff4545', beam_type='inverted',
                                 form_role='top_cap',
                                 vertical_partition=span['vertical_partition'],
                                 highlight_source='confirmed_physical_sections')
                    if span.get('highlight_boundary_source'):
                        piece['highlight_boundary_source'] = span['highlight_boundary_source']
                    if len(spans) > 1:
                        piece['rotulo'] = f"{item['rotulo']} · {span['dim_text']}"
                    highlighted.append(piece)
        # A physical height transition creates distinct displayed segments.
        # Preserve owner identity for navigation, but number the complete beam
        # sequence so a split cannot duplicate the next owner's segment label.
        import re
        display_numbers = {}
        for piece in highlighted:
            name = str(piece.get('beam_name') or '').upper()
            if name not in split_beams:
                continue
            display_numbers[name] = display_numbers.get(name, 0) + 1
            label = str(piece.get('rotulo') or name)
            piece['source_segment_label'] = label
            piece['display_segment_index'] = display_numbers[name]
            piece['rotulo'] = re.sub(r'\bSEG\s*\d+\b',
                                    f"SEG {display_numbers[name]}", label,
                                    flags=re.IGNORECASE)
        group['itens'] = highlighted
        group['total'] = len(highlighted)
    original = next((g for g in result if g['grupo'] == 'cortes'), None)
    if original is None:
        original = dict(grupo='cortes', rotulo='Visão de Cortes', itens=[])
        result.append(original)
    # Match originals by source geometry, not a guessed CAD/SA identifier.
    def geometry(points):
        return frozenset(tuple(round(float(v), 3) for v in p[:2]) for p in points or [])
    by_geometry = {geometry(i.get('pontos_dxf')): i for i in original['itens']}
    calculated = []
    def attach(item, drawing, color):
        drawing = deepcopy(drawing)
        for p in drawing['primitives']:
            if p['color'] == '#a8fff0':
                p['color'] = color
            p['points'] = [transform.dxf_para_px(*v) for v in p['points']]
        item['section_drawing'] = drawing
        item['highlight_color'] = color
        item['detail_status'] = 'dimensioned'
    displayed_entries = deduplicate_sections(inventory['entries'])
    for entry in displayed_entries:
        raw = entry.get('source_cut') or {}
        if entry['kind'] == 'identified':
            key = geometry(raw.get('points') or raw.get('pts'))
            item = by_geometry.get(key)
            if item is None:
                item = dict(item_id=raw.get('uid'), classe_sa='cortes', rotulo=entry['beam'],
                            pontos_dxf=raw.get('points') or raw.get('pts'), fora_do_frame=False)
                original['itens'].append(item)
                by_geometry[key] = item
            attach(item, entry['drawing'], '#a8fff0')
        else:
            # One source cut can supply distinct local profiles at a slab step.
            # Keep their viewer identities distinct without renumbering the VC.
            contract = entry.get('section_contract') or {}
            uid = entry_id(entry)
            review = review_status(decisions, uid, entry)
            if review == 'deleted':
                continue
            item = dict(item_id=uid, review_status=review,
                        classe_sa='cortes_interpretados', rotulo=entry['beam'],
                        beam_name=entry['beam'], pairs=entry['pairs'], fora_do_frame=False)
            confidence = entry['drawing'].get('confidence', 'review')
            if review == 'validated':
                confidence = 'high'
            missing_steps = missing_step_sections(entry, state)
            color = ('#ff4545' if contract.get('beam_type') == 'inverted' else
                     '#7dd3fc' if confidence == 'high' else '#ff9a1f')
            item.update(confidence=confidence, beam_type=contract.get('beam_type', 'normal'),
                        slab_steps_without_original_cut=missing_steps)
            attach(item, entry['drawing'], color)
            calculated.append(item)
    for slab in state.get('slabs') or []:
        for step in slab.get('slab_steps') or []:
            for section in step.get('sections') or []:
                item = by_geometry.get(geometry(section['points']))
                if item is not None:
                    try:
                        attach(item, slab_section_drawing(slab, step, section), '#ffe033')
                    except ValueError as exc:
                        item['detail_status'] = str(exc)
    for section in inventory.get('slab_sections', []):
        item = by_geometry.get(geometry(section['points']))
        if item is None:
            item = dict(item_id=section.get('item_id') or f"slab-section:{section['slab']}:{len(original['itens'])}",
                        classe_sa='cortes', rotulo=section['slab'],
                        pontos_dxf=section['points'], fora_do_frame=False)
            original['itens'].append(item)
            by_geometry[geometry(section['points'])] = item
        attach(item, section['drawing'], '#ffe033')
    from .slab_step_overlay import missing_drawings
    slab_sections = inventory.get('interpreted_slab_sections')
    step_failures = []
    if slab_sections is None:
        slab_sections, step_failures = missing_drawings(state)
    originals = {step.get('uid') for slab in state.get('slabs') or []
                 for step in slab.get('slab_steps') or [] if step.get('sections')}
    for section in slab_sections:
        if section['step_uid'] in originals:
            continue
        uid = f"interpreted:slab-step:{section['step_uid']}"
        review = review_status(decisions, uid, section)
        if review == 'deleted':
            continue
        item = dict(item_id=uid, review_status=review,
                    classe_sa='cortes_interpretados', rotulo=f"{section['slab']} · Degrau de laje",
                    slab_name=section['slab'], step_uid=section['step_uid'],
                    section_kind='slab_step', confidence='high' if review == 'validated' else section['drawing']['confidence'],
                    pontos_dxf=section['drawing']['points'], fora_do_frame=False)
        attach(item, section['drawing'], '#ffe033')
        calculated.append(item)
    # Unresolved evidence keeps its true outline and an external pending label;
    # no fabricated dimension or giant label over the CAD section.
    for item in original['itens']:
        if not item.get('section_drawing') and item.get('pontos_dxf'):
            points = item['pontos_dxf']
            anchor = [(min(p[0] for p in points)+max(p[0] for p in points))/2,
                      max(p[1] for p in points)+18]
            drawing = dict(primitives=[dict(kind='polygon',points=points,color='#a8fff0'),
                dict(kind='text',points=[anchor,[anchor[0]+1,anchor[1]]],size=8,color='#fff',
                     text=f"{item['rotulo']} · medidas pendentes")])
            attach(item, drawing, item.get('highlight_color') or '#a8fff0')
            item['detail_status'] = 'pending'
    original.update(total=len(original['itens']), fora_do_frame=sum(i['fora_do_frame'] for i in original['itens']))
    result.append(dict(grupo='cortes_interpretados', rotulo='Cortes de viga interpretados',
                       total=len(calculated), fora_do_frame=0, itens=calculated,
                       soffit_coverage=displayed_soffit_coverage(result, displayed_entries, state)
                           or inventory.get('soffit_coverage', []),
                       source_soffit_coverage=inventory.get('soffit_coverage', []),
                       blocked=[*inventory['blocked'], *step_failures]))
    return result
