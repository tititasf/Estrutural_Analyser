"""Derived lateral continuations across confirmed, vertically separate beams.

Reuse the measured two-wall crossing proof from FV, then require disjoint
absolute panel intervals. Source SA rows and manual geometry remain immutable.
"""
from copy import deepcopy
from math import dist
from shapely.geometry import Polygon, Point, LineString
from .fv_inverted_crossings import _buffered_footprint, extend_normal_soffit


def _panel_interval(contract, side):
    mount = (contract.get('mounting') or {}).get(side) or {}
    base = contract.get('base_level_m')
    low, high = mount.get('panel_base_cm'), mount.get('panel_top_cm')
    if base is None or low is None or high is None:
        return None
    return float(base)+float(low)/100, float(base)+float(high)/100


def _slab_bands(contract):
    top = contract.get('top_level_m')
    if top is None:
        return []
    return [(float(top)-float(s.get('drop_cm') or 0)/100-float(s['height_cm'])/100,
             float(top)-float(s.get('drop_cm') or 0)/100)
            for rows in (contract.get('slabs') or {}).values() for s in rows
            if s.get('height_cm') and float(s['height_cm'])>0]


def _blocks(own, incident, side):
    """A shared slab band and mounting overhang are not beam obstacles.

    The common band needs independently matching absolute level and thickness
    from both contracts. Any remaining positive panel overlap still blocks.
    """
    a = _panel_interval(own, side)
    base = incident.get('base_level_m')
    if a is None or base is None:
        return True
    common = [(max(x[0],y[0]),min(x[1],y[1])) for x in _slab_bands(own)
              for y in _slab_bands(incident)
              if abs(x[0]-y[0])<.001 and abs(x[1]-y[1])<.001]
    for other_side in ('A','B'):
        b = _panel_interval(incident, other_side)
        if b is None:
            return True
        low, high = max(a[0],b[0],float(base)), min(a[1],b[1])
        cursor=low
        for start,end in sorted(common):
            if end<cursor: continue
            if start>cursor+.001: break
            cursor=max(cursor,end)
        if high-cursor>.001:
            return True
    return False


def _remap_cell(proposed, owners):
    """Keep all measured openings in their original physical positions."""
    origin, end = proposed['points']
    length = dist(origin, end)
    unit = [(end[i]-origin[i])/length for i in (0,1)]
    cell = proposed.setdefault('lv_cell', {})
    for kind in ('pillar_openings', 'beam_openings'):
        openings = []
        for owner in owners:
            start, finish = owner['points']
            old_length = dist(start, finish)
            direction = [(finish[i]-start[i])/old_length for i in (0,1)]
            offset = sum((start[i]-origin[i])*unit[i] for i in (0,1))
            sign = sum(direction[i]*unit[i] for i in (0,1))
            for source in (owner.get('lv_cell') or {}).get(kind) or []:
                local_start = float(source['pos_inicio'])
                local_end = float(source.get('pos_fim', local_start+float(
                    source.get('largura') or source.get('abertura_largura') or 0)))
                if kind == 'beam_openings':
                    midpoint = (local_start+local_end)/2
                    physical = [start[i]+direction[i]*midpoint for i in (0,1)]
                    axis = 0 if abs(unit[0])>=abs(unit[1]) else 1
                    if any(source.get('name') == e['incident_beam'] and
                           min(e['from_station_cm'],e['to_station_cm'])-.15 <= physical[axis] <=
                           max(e['from_station_cm'],e['to_station_cm'])+.15
                           for e in proposed.get('normal_inverted_continuations') or []):
                        continue
                opening = deepcopy(source)
                a, b = sorted(offset+sign*t for t in (local_start,local_end))
                opening.update(pos_inicio=a, pos_fim=b,
                    dist_face_inicio=a, dist_face_fim=length-b)
                extra = (float(source.get('abertura', b-a))-(b-a))/2
                opening.update(dist_abertura_inicio=a-extra, dist_abertura_fim=length-b-extra)
                if opening not in openings:
                    openings.append(opening)
        if kind == 'pillar_openings':
            united = []
            for opening in sorted(openings, key=lambda o: o['pos_inicio']):
                previous = united[-1] if united else None
                if (previous and previous.get('name') == opening.get('name')
                        and previous.get('rule') == opening.get('rule')
                        and opening['pos_inicio'] <= previous['pos_fim']+.05):
                    extra = max(previous.get('abertura',0)-(previous['pos_fim']-previous['pos_inicio']),
                                opening.get('abertura',0)-(opening['pos_fim']-opening['pos_inicio']),0)
                    previous['pos_fim'] = max(previous['pos_fim'],opening['pos_fim'])
                    size = previous['pos_fim']-previous['pos_inicio']
                    previous.update(comprimento=size,abertura=size+extra,
                        dist_face_fim=length-previous['pos_fim'],
                        dist_abertura_inicio=previous['pos_inicio']-extra/2,
                        dist_abertura_fim=length-previous['pos_fim']-extra/2)
                else:
                    united.append(opening)
            openings = united
        cell[kind] = openings
    axis = 0 if abs(unit[0])>=abs(unit[1]) else 1
    cell['sections'] = [dict(start=min(origin[axis],end[axis]),
        end=max(origin[axis],end[axis]),depth=cell.get('depth'),dim=cell.get('dim'),
        source='vertically_disjoint_inverted_crossing')]
    if len(owners)>1:
        # A logical continuation does not erase the local vertical evidence.
        cell['source_level_sections'] = [dict(
            start=min(p[axis] for p in owner['points']),
            end=max(p[axis] for p in owner['points']),
            level=(owner.get('lv_cell') or {}).get('level'),
            level_source=owner.get('level_source'), source_uid=owner['uid'])
            for owner in owners]


def _same_beam_datum(row, other, entries):
    """Resolve a slab-derived scalar disagreement using the opposite face.

    This only applies to an already proved, two-way disjoint crossing. Keep
    explicit datums and slab steps as seams; retain both source levels rather
    than replacing either with a guessed common elevation.
    """
    for owner in (row, other):
        cell = owner.get('lv_cell') or {}
        source = str(owner.get('level_source') or '')
        if source != 'lv_cell_slabs' and 'estim' not in source:
            return False
        if any('degrau' in str((cell.get(k) or {}).get('type','')).lower()
               for k in ('support_start','support_end')):
            return False
    side = str(row.get('side') or 'A').upper()
    opposite = 'B' if side=='A' else 'A'
    for reference_side in (side, opposite):
        datums = []
        for owner in (row, other):
            levels = {pair.get('profiles',{}).get(reference_side,{}).get('level')
                      for entry in entries if entry.get('beam')==owner.get('beam_name')
                      for pair in entry.get('pairs') or []
                      if owner.get('uid')==pair.get(side.lower()+'_id')}
            datums.append(levels)
        if len(datums[0])==1 and None not in datums[0] and datums[0]==datums[1]:
            return True
    return False


def propose(row, entries, lines, pillars=()):
    result = deepcopy(row)
    points = row.get('points') or []
    if len(points)!=2 or row.get('validated') or row.get('geometry_validated'):
        return result
    axis = 0 if abs(points[1][0]-points[0][0])>=abs(points[1][1]-points[0][1]) else 1
    if abs(points[1][1-axis]-points[0][1-axis])>.05:
        return result
    lo, hi = sorted(p[axis] for p in points)
    across = points[0][1-axis]
    for endpoint, sign in ((lo,-1),(hi,1)):
        inside = [0.,0.]
        inside[axis], inside[1-axis] = endpoint-sign*.2, across
        owners = [e for e in entries if e.get('beam')==row.get('beam_name')
                  and not e.get('pending') and any(
                      len(p.get('footprint') or [])>=3 and
                      _buffered_footprint(p['footprint'],.15).covers(Point(inside))
                      for p in e.get('pairs') or [])]
        if not owners or any((e.get('section_contract') or {}).get('beam_type')=='inverted' for e in owners):
            continue
        side = str(row.get('side') or 'A').upper()
        intervals = [_panel_interval(e.get('section_contract') or {}, side) for e in owners]
        if any(i is None for i in intervals):
            continue
        bounds = next(Polygon(p['footprint']).bounds for e in owners for p in e['pairs']
                      if _buffered_footprint(p['footprint'],.15).covers(Point(inside)))
        low_across, high_across = bounds[1-axis], bounds[3-axis]
        rectangle = [[lo,low_across],[hi,low_across],[hi,high_across],[lo,high_across],[lo,low_across]]
        if axis==1:
            rectangle = [p[::-1] for p in rectangle]
        measured = extend_normal_soffit(dict(row,points=rectangle),entries,lines,pillars)
        events = [e for e in measured.get('normal_inverted_continuations') or []
                  if abs(e['from_station_cm']-endpoint)<.15]
        for event in events:
            gap_low,gap_high=sorted((endpoint,event['to_station_cm']))
            gap = LineString([[gap_low,across],[gap_high,across]] if axis==0 else
                             [[across,gap_low],[across,gap_high]])
            # A measured arrival at the far support face can span its width,
            # just as the bottom does. A support extending beyond that face
            # still blocks; intersection alone incorrectly stopped at near A.
            if any(len(p.get('points') or [])>=3 and
                   Polygon(p['points']).intersection(gap).length>.05 and
                   sign*((Polygon(p['points']).bounds[axis+2] if sign>0 else
                          Polygon(p['points']).bounds[axis])-event['to_station_cm'])>.15
                   for p in pillars):
                continue
            incident = [e for e in entries if e.get('beam')==event['incident_beam'] and any(
                        len(p.get('footprint') or [])>=3 and
                        _buffered_footprint(p['footprint'],.15).intersection(gap).length>.1
                        for p in e.get('pairs') or [])]
            other_intervals = [_panel_interval(e.get('section_contract') or {}, s)
                               for e in incident for s in ('A','B')]
            if not incident or any(i is None for i in other_intervals):
                continue
            if any(_blocks(owner.get('section_contract') or {}, other.get('section_contract') or {}, side)
                   for owner in owners for other in incident):
                continue
            result['points'] = [[event['to_station_cm'] if i==axis and abs(p[i]-endpoint)<.15 else p[i]
                                 for i in (0,1)] for p in result['points']]
            result.setdefault('normal_inverted_continuations',[]).append({**event,
                'source':'confirmed_two_walls_and_disjoint_lateral_panel_levels'})
    if result.get('points')!=points:
        result['length']=dist(*result['points'])
        result['measure_source']='lateral_below_inverted_crossing'
    return result


def overlay_beam(record, state):
    """Project effective geometry into a copied N3 conversion record, never N1."""
    result = deepcopy(record)
    for group, rows in (state.get('segmentos') or {}).items():
        if not group.startswith('lateral_'):
            continue
        _, side, behavior = group.split('_')
        suffix = 'comprimento_total' if behavior=='para' else 'comp_total_passa'
        for row in rows:
            if row.get('beam_name')!=record.get('name') or not row.get('normal_inverted_continuations'):
                continue
            owners = row.get('merged_source_segments') or [row]
            for owner in owners:
                index = str(owner['uid']).split('|')[2]
                result.setdefault('links', {})[f'viga_{side}_seg_{index}_{suffix}'] = {f'seg_side_{side}': []}
            index = str(row['uid']).split('|')[2]
            result['links'][f'viga_{side}_seg_{index}_{suffix}'] = {f'seg_side_{side}': [dict(
                points=deepcopy(row['points']), len=row['length'], lv_cell=deepcopy(row.get('lv_cell') or {}),
                lv_dimensao=(row.get('lv_cell') or {}).get('dim'))]}
            for endpoint, short in (('support_start','ini'),('support_end','end')):
                result.setdefault('fields', {})[f'viga_{side}_seg_{index}_{short}_name'] = (
                    (row.get('lv_cell') or {}).get(endpoint) or {}).get('name','')
            result['_effective_lateral_geometry'] = True
    return result


def _inverted_segments(rows, entries, pillars, protected_uids):
    """Remove only named lower-beam seams; retain section/slab-step seams.

    Local vertical profiles remain separate inside the joined logical segment.
    A terminal pillar opening is retained, not treated as a free-span collision.
    """
    from .beam_vertical_context import partition_inverted_lateral
    from .lv_generation_contract import _terminal_pillar_profiles
    bboxes = {p.get('name'): Polygon(p['points']).bounds for p in pillars
              if len(p.get('points') or []) >= 3}

    def profiles(row):
        own = [e for e in entries if e.get('beam') == row.get('beam_name')
               and (e.get('section_contract') or {}).get('beam_type') == 'inverted']
        own = _terminal_pillar_profiles(row, own, bboxes, row.get('side', 'A')) if own else []
        pieces = partition_inverted_lateral(row['points'], own, row.get('side', 'A')) if own else []
        return pieces if pieces and not any(p.get('pending') for p in pieces) else []

    result = deepcopy(rows)
    changed = True
    while changed:
        changed = False
        for i, row in enumerate(result):
            if row.get('uid') in protected_uids or row.get('validated') or row.get('geometry_validated'):
                continue
            own = profiles(row)
            if not own:
                continue
            for j, other in enumerate(result):
                if j <= i or other.get('beam_name') != row.get('beam_name') or other.get('side') != row.get('side'):
                    continue
                if other.get('uid') in protected_uids or other.get('validated') or other.get('geometry_validated'):
                    continue
                ca, cb = row.get('lv_cell') or {}, other.get('lv_cell') or {}
                if any(ca.get(k) != cb.get(k) for k in ('depth', 'dim')):
                    continue
                shared = [(a,b) for a in (0,1) for b in (0,1)
                          if dist(row['points'][a],other['points'][b]) < .15]
                if len(shared) != 1:
                    continue
                a,b = shared[0]
                sa = ca.get('support_start' if a==0 else 'support_end') or {}
                sb = cb.get('support_start' if b==0 else 'support_end') or {}
                if sa.get('type') != 'viga' or sb.get('type') != 'viga' or sa.get('name') != sb.get('name'):
                    continue
                opposite = profiles(other)
                if not opposite:
                    continue
                seam = Point(row['points'][a])
                axis = 0 if abs(row['points'][1][0]-row['points'][0][0]) >= abs(row['points'][1][1]-row['points'][0][1]) else 1
                width = float(own[0]['section_contract'].get('width_cm') or 0)
                def touches_crossing(pair):
                    if len(pair.get('footprint') or [])<3:
                        return False
                    polygon = Polygon(pair['footprint'])
                    bounds = polygon.bounds
                    # An incident measurement can end at the opposite wall of
                    # the owner; extend only across its confirmed beam width.
                    return (bounds[axis]-.15 <= seam.coords[0][axis] <= bounds[axis+2]+.15
                            and polygon.distance(seam) <= width+.15)
                incident = [e for e in entries if e.get('beam')==sa['name'] and not e.get('pending')
                            and (e.get('section_contract') or {}).get('beam_type') != 'inverted'
                            and any(touches_crossing(p) for p in e.get('pairs') or [])]
                # At a crossing, a missing slab profile is not a measured notch.
                # Use only adjacent, confirmed same-height contracts matching
                # the incident slab band; never infer from the beam name alone.
                nearby = [e['section_contract'] for e in entries
                          if e.get('beam')==row.get('beam_name') and not e.get('pending')
                          and (e.get('section_contract') or {}).get('beam_type')=='inverted'
                          and (e.get('section_contract') or {}).get('height_cm')==ca.get('depth')
                          and any(LineString([p['start'],p['end']]).distance(seam) <
                                  float((e.get('section_contract') or {}).get('width_cm') or 0)+.2
                                  for p in e.get('pairs') or [])]
                side = row.get('side','A')
                if not incident or any(not any(not _blocks(c,e['section_contract'],side) for c in nearby)
                                       for e in incident):
                    continue
                merged = deepcopy(row)
                merged['points'][a] = deepcopy(other['points'][1-b])
                line = LineString(merged['points'])
                if abs(line.length - (dist(*row['points'])+dist(*other['points']))) > .15:
                    continue
                merged['length'] = line.length
                owners = [*(row.get('merged_source_segments') or [row]),
                          *(other.get('merged_source_segments') or [other])]
                merged['merged_source_segments'] = deepcopy(owners)
                merged['merged_source_uids'] = [p['uid'] for p in owners]
                axis = 0 if abs(merged['points'][1][0]-merged['points'][0][0]) >= abs(merged['points'][1][1]-merged['points'][0][1]) else 1
                incident_bounds = [Polygon(p['footprint']).bounds for e in incident for p in e['pairs']
                                   if touches_crossing(p)]
                events = [*(row.get('normal_inverted_continuations') or []),
                          *(other.get('normal_inverted_continuations') or []),
                          dict(incident_beam=sa['name'], from_station_cm=min(b[axis] for b in incident_bounds),
                               to_station_cm=max(b[axis+2] for b in incident_bounds),
                               source='inverted_above_confirmed_lower_beam')]
                merged['normal_inverted_continuations'] = events
                merged['lv_cell']['support_start' if a==0 else 'support_end'] = deepcopy(
                    cb.get('support_start' if 1-b==0 else 'support_end') or {})
                _remap_cell(merged, owners)
                merged['lv_cell']['sections'] = [deepcopy(s) for owner in owners
                                                 for s in (owner.get('lv_cell') or {}).get('sections') or []]
                # The joined face touches every slab of its source cells (V330 2-A: L308 + L316).
                merged['lv_cell']['slabs'] = list({s.get('name'): deepcopy(s) for owner in owners
                                                   for s in (owner.get('lv_cell') or {}).get('slabs') or []}.values())
                result[i] = merged
                del result[j]
                changed = True
                break
            if changed:
                break
    joined_beams = {r.get('beam_name') for r in result if any(
        e.get('source') == 'inverted_above_confirmed_lower_beam'
        for e in r.get('normal_inverted_continuations') or [])}
    counters = {}
    for row in result:
        if row.get('beam_name') in joined_beams:
            name = row['beam_name']
            counters[name] = counters.get(name, 0) + 1
            row['segment_label'] = f"{counters[name]}-{row.get('side', 'A')}"
    return result


def reconcile_state(state, inventory, lines, protected_uids=()):
    result=deepcopy(state)
    entries=inventory.get('physical_entries') or []
    for key, originals in (state.get('segmentos') or {}).items():
        if not key.startswith('lateral_'):
            continue
        rows=deepcopy(originals)
        removed=set()
        for i,row in enumerate(originals):
            if i in removed or row.get('uid') in protected_uids:
                continue
            proposed=propose(row,entries,lines,state.get('pilares') or [])
            if proposed.get('points')==row.get('points'):
                continue
            candidate=LineString(proposed['points'])
            overlaps=[j for j,other in enumerate(originals) if j!=i and j not in removed
                      and other.get('beam_name')==row.get('beam_name')
                      and candidate.intersection(LineString(other['points'])).length>.05]
            if overlaps:
                continue
            # An opposite arrival into the same proved gap is one lateral.
            matches=[]
            opposite_arrival=False
            for j,other in enumerate(originals):
                if j==i or j in removed:
                    continue
                if str(other.get('uid','')).split('|')[1:2]!=str(row.get('uid','')).split('|')[1:2]:
                    continue
                if other.get('beam_name')!=row.get('beam_name') or other.get('side')!=row.get('side'):
                    continue
                shared=[(a,b) for a in (0,1) for b in (0,1)
                        if dist(proposed['points'][a],row['points'][a])>.15
                        and dist(proposed['points'][a],other['points'][b])<.15]
                if len(shared)!=1:
                    continue
                opposite_arrival=True
                if other.get('uid') in protected_uids:
                    continue
                reverse=propose(other,entries,lines,state.get('pilares') or [])
                if reverse.get('points')==other.get('points'):
                    continue
                ca,cb=row.get('lv_cell') or {},other.get('lv_cell') or {}
                if any(ca.get(k)!=cb.get(k) for k in ('depth','dim','sobre_cota')):
                    continue
                if ca.get('level')!=cb.get('level') and not _same_beam_datum(row,other,entries):
                    continue
                if any(p.get('geometry_validated') or p.get('validated') for p in (row,other)):
                    continue
                matches.append((j,shared[0]))
            if len(matches)>1 or (opposite_arrival and not matches):
                continue
            if matches:
                j,(a,b)=matches[0]
                other=originals[j]
                proposed['points'][a]=deepcopy(other['points'][1-b])
                proposed['length']=dist(*proposed['points'])
                proposed['merged_source_uids']=[row['uid'],other['uid']]
                proposed['merged_source_segments']=[deepcopy(row),deepcopy(other)]
                cell=proposed.setdefault('lv_cell',{})
                cell['support_start' if a==0 else 'support_end']=deepcopy(
                    (other.get('lv_cell') or {}).get('support_start' if 1-b==0 else 'support_end') or {})
                cell['slabs']=list({s.get('name'):s for owner in (row,other)
                                    for s in (owner.get('lv_cell') or {}).get('slabs') or []}.values())
                removed.add(j)
            _remap_cell(proposed, [row, originals[matches[0][0]]] if matches else [row])
            for event in proposed.get('normal_inverted_continuations') or []:
                cell=proposed.setdefault('lv_cell',{})
                for support in ('support_start','support_end'):
                    if (cell.get(support) or {}).get('name')==event['incident_beam']:
                        cell[support]={'type':'extremidade','name':'',
                            'rule':'vertically_disjoint_inverted_crossing'}
            rows[i]=proposed
        result['segmentos'][key]=_inverted_segments(
            [r for j,r in enumerate(rows) if j not in removed], entries,
            state.get('pilares') or [], protected_uids)
    return result
