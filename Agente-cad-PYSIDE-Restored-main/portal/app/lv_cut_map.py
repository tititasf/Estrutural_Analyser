"""Physical footprint of the published A/B pairs; never recompute sections."""
from math import hypot
from pathlib import Path

COLORS = ['#22d3ee', '#fbbf24', '#a78bfa', '#fb7185', '#4ade80', '#fb923c', '#60a5fa', '#e879f9']


def pair_polygon(pair, segment_b):
    """Project the exact common interval onto its opposite B edge."""
    start, end = pair['start'], pair['end']
    length = hypot(end[0]-start[0], end[1]-start[1])
    if length <= .01:
        raise ValueError('intervalo de par vazio')
    u = [(end[i]-start[i])/length for i in (0, 1)]
    mid = [(start[i]+end[i])/2 for i in (0, 1)]
    choices = []
    points = segment_b.get('points') or []
    for p, q in zip(points, points[1:]):
        size = hypot(q[0]-p[0], q[1]-p[1])
        if size <= .01 or abs(sum((q[i]-p[i])*u[i] for i in (0, 1))/size) < .9999:
            continue
        projections = [sum((v[i]-start[i])*u[i] for i in (0, 1)) for v in (p, q)]
        if min(projections) > .05 or max(projections) < length-.05:
            continue
        offset = sum((mid[i]-p[i])*u[i] for i in (0, 1))
        nearest = [p[i]+offset*u[i] for i in (0, 1)]
        delta = [nearest[i]-mid[i] for i in (0, 1)]
        choices.append((hypot(*delta), delta))
    if not choices:
        raise ValueError('face B não cobre o intervalo publicado')
    delta = min(choices, key=lambda row: row[0])[1]
    return [start, end, [end[i]+delta[i] for i in (0, 1)], [start[i]+delta[i] for i in (0, 1)]]


def footprints(cuts, sides):
    b_segments = {s['id']: s for s in sides['B']['segments']}
    result = []
    for index, cut in enumerate(cuts):
        for pair in cut.get('pairs') or []:
            result.append(dict(points=pair_polygon(pair, b_segments[pair['b_id']]),
                               label=f"VC{index+1} · A{pair['a_index']} ↔ B{pair['b_index']}",
                               color=COLORS[index % len(COLORS)], kind='cut_pair',
                               cut_index=index, a_index=pair['a_index'], b_index=pair['b_index']))
    return result


def structural_payload(obra_dir, floor, obra_id, state, beam, behavior, data, cut_index=None):
    from . import lv_ficha, dxf_preview
    targets = []
    source = None
    for side in ('A', 'B'):
        source, items, frame = lv_ficha._torre_context_itens(obra_dir, floor, state, lv_ficha._CLASSES[behavior][side])
        if source is None:
            return None
        targets.extend(i for i in items if str(i.get('beam_name') or '').upper() == beam.upper())
    if not targets:
        return None
    payload = lv_ficha._torre_context_payload(obra_id, source, targets, frame)
    transform = dxf_preview.transform_preview_completo(Path(source['path']), cache_dir=obra_dir/'.previews')
    shapes = footprints(data['cut_views'], data['sides'])
    # A aba representa seções transversais, não os contornos longitudinais.
    payload['highlights'] = []
    from .lv_cut_coverage import soffit_drawings
    cuts = data.get('sa_cut_views', data['cut_views'])
    fundos = [s for s in (state.get('segmentos') or {}).get('fundo', [])
              if str(s.get('beam_name') or '').upper() == beam.upper()]
    drawings, blocked, coverage = soffit_drawings(cuts, data['sides'], fundos, state.get('pilares') or [])
    if cut_index is not None:
        selected = data['cut_views'][cut_index]
        ids = {m['id'] for m in selected.get('section_members') or []} or {selected['id']}
        indexes = {i for i, cut in enumerate(cuts) if cut['id'] in ids}
        drawings = [d for d in drawings if d['cut_index'] in indexes]
        blocked = [d for d in blocked if d['cut_index'] in indexes]
    for drawing in drawings:
        for primitive in drawing['primitives']:
            primitive['points'] = [transform.dxf_para_px(*p) for p in primitive['points']]
    if cut_index is not None and drawings:
        pts = [p for d in drawings for primitive in d['primitives'] for p in primitive['points']]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        pad = max(max(xs)-min(xs), max(ys)-min(ys), 30)
        payload['viewbox'] = [min(xs)-pad, min(ys)-pad,
                              max(xs)-min(xs)+2*pad, max(ys)-min(ys)+2*pad]
    payload['section_drawings'] = drawings
    payload['soffit_coverage'] = coverage
    payload['blocked_drawings'] = blocked
    payload['mapped_pairs'] = len(shapes)
    payload['unlocated_cuts'] = [i+1 for i, c in enumerate(data['cut_views']) if not c.get('pairs')]
    return payload


def identified_frame(cut, width, height):
    """Recover the original soffit and orientation from the measured polygon."""
    raw = cut.get('source_cut') or {}
    polygon = raw.get('points') or raw.get('pts') or []
    if len(polygon) < 4:
        raise ValueError('polígono original do corte ausente')
    semantics = raw.get('section_semantics') or {}
    frame = semantics.get('frame') or {}
    if semantics.get('confirmed') and semantics.get('beam_type') == 'inverted' and frame:
        ex, ey = frame['ex'], frame['ey']
        measured_height = semantics['measured_height_cm']
        center = [frame['base_center'][i]+ey[i]*measured_height/2 for i in (0,1)]
        return center, ex, ey, measured_height, polygon
    centroid = [sum(p[i] for p in polygon)/len(polygon) for i in (0,1)]
    candidates = []
    for p,q in zip(polygon, polygon[1:]+polygon[:1]):
        size = hypot(q[0]-p[0],q[1]-p[1])
        if abs(size-width) > .1:
            continue
        ex = [(q[i]-p[i])/size for i in (0,1)]
        ey = [-ex[1],ex[0]]
        mid = [(p[i]+q[i])/2 for i in (0,1)]
        if sum((centroid[i]-mid[i])*ey[i] for i in (0,1)) < 0:
            ex = [-v for v in ex]; ey = [-v for v in ey]
        depths = [sum((v[i]-mid[i])*ey[i] for i in (0,1)) for v in polygon]
        if min(depths) >= -.1 and max(depths) > .1:
            measured_height = max(depths)
            candidates.append(([mid[i]+ey[i]*measured_height/2 for i in (0,1)],ex,ey,measured_height))
    if len(candidates) > 1:
        # Topo e fundo têm a mesma largura: a laje desenhada no símbolo diz
        # qual é o topo.  Primeiro as duas faces da laje; se o símbolo for
        # genérico (espessura desenhada diferente da laje real, VF301/L303),
        # só a face superior da laje, que é a que fixa a orientação.
        # O rebaixo conta do topo DESENHADO (measured_h): a altura do SA pode
        # diferir do símbolo (V408 14_PAV: desenho 60, SA 55).
        from src.core.lv_n3_cut_contract import build_cut_contract
        contract = build_cut_contract(cut)
        slabs = [s for side in ('A','B') for s in contract['slabs'][side]]

        def matching(offsets):
            found = []
            for candidate in candidates:
                center, ex, ey, measured_h = candidate
                expected = {round(measured_h/2-s['drop_cm']-offset(s), 3) for s in slabs for offset in offsets}
                actual = {round(sum((p[i]-center[i])*ey[i] for i in (0,1)), 3)
                          for p in polygon
                          if abs(sum((p[i]-center[i])*ex[i] for i in (0,1))) > width/2+.1}
                if expected and expected <= actual:
                    found.append(candidate)
            return found
        full = matching((lambda s: 0, lambda s: s['height_cm']))
        candidates = full or matching((lambda s: 0,))
    if len(candidates) != 1:
        raise ValueError('fundo original do corte não identificado univocamente')
    return (*candidates[0],polygon)


def section_drawings(cuts, sides, pillars=()):
    """One actual-size SA cross-section at a real A/B common interval."""
    from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError
    b_segments = {s['id']: s for s in sides['B']['segments']}
    drawings, blocked = [], []
    placed = []
    for index, cut in enumerate(cuts):
        identified = cut.get('kind') == 'identified'
        if not identified and not cut.get('pairs'):
            continue
        try:
            contract = build_cut_contract(cut)
            w, h = contract['width_cm'], contract['height_cm']
            inverted = contract.get('beam_type') == 'inverted'
            tail_top = min((s['drop_cm']-h/2 if inverted else h/2-s['drop_cm']-s['height_cm']
                            for side in ('A','B') for s in contract['slabs'][side]), default=h/2)
            tail_length = tail_top+h/2
            # Fit the schematic to its free interval before moving it away.
            # Slab contacts keep their size; only the uninterrupted tail shrinks.
            head_length = h-tail_length
            tail_display = min(tail_length, max(3, 50-head_length)) if not identified else tail_length
            if not identified:
                longest_pair = max(p['length_cm'] for p in cut['pairs'])
                if h-tail_length+tail_display > longest_pair:
                    tail_display = min(tail_display, max(3, longest_pair-head_length-2))
            shortened = tail_display < tail_length-.01
            removed = tail_length-tail_display if shortened else 0
            strong_break = shortened and tail_display/tail_length < .35
            pair = None
            original = None
            source_anchor = None
            if identified:
                center, ex, ey, measured_h, original = identified_frame(cut,w,h)
                # Keep the measured soffit as anchor; dimensions come from SA.
                center = [center[i]+ey[i]*(h-measured_h)/2 for i in (0,1)]
            else:
                # The complete displayed beam must fit its own free pair, not
                # merely have its midpoint outside a support.
                candidates = sorted(cut['pairs'], key=lambda p:p['length_cm'], reverse=True)
                fitting = [p for p in candidates if p['length_cm'] >= h-removed-.01]
                pair = (fitting or candidates)[0]
                quad = pair_polygon(pair, b_segments[pair['b_id']])
                center = [sum(p[i] for p in quad)/4 for i in (0, 1)]
                delta = [quad[3][i]-quad[0][i] for i in (0, 1)]
                distance = hypot(*delta)
                if distance <= .01:
                    raise ValueError('faces coincidentes')
                ex = [v/distance for v in delta]
                ey = [-ex[1], ex[0]]
                from shapely.geometry import Polygon
                displayed_h = h-removed
                axis = [(pair['end'][i]-pair['start'][i])/pair['length_cm'] for i in (0,1)]
                margin = displayed_h/2
                free = max(0,pair['length_cm']-2*margin)
                positions = ([pair['length_cm']/2, margin, margin+free]
                             + [margin+free*r for r in (.25,.75)]) if fitting else []
                solutions = []
                for station in positions:
                    anchor = [center[i]+axis[i]*(station-pair['length_cm']/2) for i in (0,1)]
                    shape = Polygon([[anchor[i]+ex[i]*x+ey[i]*y for i in (0,1)]
                                     for x,y in [(-w/2,-displayed_h/2),(w/2,-displayed_h/2),
                                                 (w/2,displayed_h/2),(-w/2,displayed_h/2)]])
                    if any(shape.intersection(Polygon(p['points'])).area > .1
                           for p in pillars if len(p.get('points') or []) >= 3):
                        continue
                    overlap = sum(shape.intersection(p).area for p in placed)
                    solutions.append((overlap,abs(station-pair['length_cm']/2),anchor,shape))
                direct = min(solutions,key=lambda s:(s[0],s[1])) if solutions else None
                if direct is not None and direct[0] <= .1:
                    _,_,center,shape = direct
                else:
                    # A short valid interval still has a section. Keep its real
                    # midpoint as the reference and move only the annotation,
                    # with a leader. Never turn a layout failure into lost data.
                    source_anchor = list(center)
                    annotation_w = w+2*20+80
                    annotation_h = displayed_h+50
                    options = []
                    for ring in range(1,33):
                        for across in (-ring,ring):
                            for along in (0,-ring,ring):
                                anchor = [source_anchor[i]+ex[i]*across*annotation_w
                                          +ey[i]*along*annotation_h for i in (0,1)]
                                shape = Polygon([[anchor[i]+ex[i]*x+ey[i]*y for i in (0,1)]
                                    for x,y in [(-annotation_w/2,-annotation_h/2),
                                                (annotation_w/2,-annotation_h/2),
                                                (annotation_w/2,annotation_h/2),
                                                (-annotation_w/2,annotation_h/2)]])
                                if any(shape.intersection(Polygon(p['points'])).area > .1
                                       for p in pillars if len(p.get('points') or []) >= 3):
                                    continue
                                if any(shape.intersection(p).area > .1 for p in placed):
                                    continue
                                options.append((hypot(*(anchor[i]-source_anchor[i] for i in (0,1))),anchor,shape))
                        if options:
                            break
                    if not options:
                        raise ValueError('sem espaço para detalhe conectado ao par')
                    _,center,shape = min(options,key=lambda row:row[0])
                placed.append(shape)
            primitives = []
            # Shorten only the straight tail below all slab contacts. Measurements
            # remain in physical coordinates; only presentation points change.
            def display_y(y):
                if not shortened:
                    return y
                value = -y if inverted else y
                # Compress inside the stem only. Labels and dimension ticks
                # outside it retain their physical spacing from the edge.
                if value < -h/2:
                    value += removed
                elif value < tail_top:
                    value = tail_top+(value-tail_top)*tail_display/tail_length
                value -= removed/2
                return -value if inverted else value
            def points(local):
                return [[center[i]+ex[i]*x+ey[i]*display_y(y) for i in (0,1)] for x,y in local]
            def line(local, color='#a8fff0'):
                primitives.append(dict(kind='line', points=points(local), color=color))
            def label(x,y,text,size=3):
                primitives.append(dict(kind='text',points=points([(x,y),(x+1,y)]),text=text,size=size,color='#ffffff'))
            def box(x,y,width,height):
                primitives.append(dict(kind='polygon',points=points([(x,y),(x+width,y),(x+width,y+height),(x,y+height)]),color='#a8fff0'))
            def wall_dimension(x, low, high, text_offset):
                if high-low <= .005:
                    return
                line([(x,low),(x,high)],'#fff38c')
                for y in (low,high):
                    line([(x-1.5,y-1.5),(x+1.5,y+1.5)],'#fff38c')
                label(x+text_offset,(low+high)/2,f'{high-low:g}',5)
            if original:
                local_original = [[sum((p[i]-center[i])*axis[i] for i in (0,1))
                                   for axis in (ex,ey)] for p in original]
                reach = max(abs(p[0]) for p in local_original)-w/2
                consistent = abs(measured_h-h) <= .1
                for side in ('A','B'):
                    sign = -1 if side == 'A' else 1
                    actual = {round(p[1],3) for p in local_original if sign*p[0] > w/2+.1}
                    expected = {round(y,3) for slab in contract['slabs'][side]
                                for y in (h/2-slab['drop_cm'],h/2-slab['drop_cm']-slab['height_cm'])}
                    consistent = consistent and actual == expected
                if consistent:
                    primitives.append(dict(kind='polygon',points=original,color='#a8fff0'))
                else:
                    # Correct presentation of a schematic symbol, never the source DXF.
                    original = None
                    box(-w/2,-h/2,w,h)
            else:
                box(-w/2,-h/2,w,h)
                reach = 20
            for side in ('A','B'):
                boundaries = {-h/2,h/2}
                for slab in contract['slabs'][side]:
                    x = -w/2-reach if side == 'A' else w/2
                    y = h/2-slab['drop_cm']-slab['height_cm']
                    if not original:
                        box(x,y,reach,slab['height_cm'])
                    boundaries.update((max(-h/2,min(h/2,y)), max(-h/2,min(h/2,y+slab['height_cm']))))
                levels = sorted(boundaries)
                dim_side_x = -w/2-reach-5 if side == 'A' else w/2+reach+5
                for low,high in zip(levels,levels[1:]):
                    wall_dimension(dim_side_x,low,high,-6 if side == 'A' else 6)
            # CAD-style dimension ticks, no panel/fastener geometry in SA.
            dim_y=-h/2-5
            line([(-w/2,dim_y),(w/2,dim_y)],'#fff38c')
            for x in (-w/2,w/2): line([(x-1.5,dim_y-1.5),(x+1.5,dim_y+1.5)],'#fff38c')
            label(0,dim_y-6,f'{w:g}',5)
            wall_dimension(w/2+reach+22,-h/2,h/2,6)
            if shortened:
                # Rectangular interruption, distinct from the original paired
                # inclined strokes identifying an inverted structural beam.
                y = -h/2+tail_length/2
                if inverted:
                    y = -y
                amplitude = min(2,tail_display/8)*tail_length/tail_display
                for offset in (-amplitude, amplitude):
                    line([(-w/2,y+offset),(-w/2-2,y+offset),
                          (-w/2-2,y-offset),(w/2,y-offset)], '#fff38c')
                marker_y = (h/2+4 if inverted else -h/2-20) if tail_display < 10 else y
                label(0,marker_y,'COMP. MAX' if strong_break else 'COMP.',5)
                primitives[-1]['role'] = 'compression_label'
            label(0,h/2+12,f'{cut["beam"]} - VC{index+1} - ({w:g}/{h:g})',8)
            primitives[-1]['role'] = 'section_title'
            if inverted:
                label(0,h/2+22,'INVERTIDA',8)
                primitives[-1]['role'] = 'beam_type_label'
            if source_anchor is not None:
                # End at the section edge, keeping the leader off its dimensions.
                direction = [source_anchor[i]-center[i] for i in (0,1)]
                side = -1 if sum(direction[i]*ex[i] for i in (0,1)) < 0 else 1
                endpoint = [center[i]+ex[i]*side*(w/2+20) for i in (0,1)]
                primitives.append(dict(kind='line',points=[source_anchor,endpoint],color='#a8fff0'))
                for axis in (ex,ey):
                    primitives.append(dict(kind='line',points=[
                        [source_anchor[i]-axis[i]*2 for i in (0,1)],
                        [source_anchor[i]+axis[i]*2 for i in (0,1)]],color='#a8fff0'))
            drawings.append(dict(cut_index=index,a_index=pair['a_index'] if pair else None,b_index=pair['b_index'] if pair else None,
                                 anchor=source_anchor or center,detail_center=center,displaced=source_anchor is not None,
                                 primitives=primitives,compressed_tail_cm=removed,
                                 compression_ratio=tail_display/tail_length if tail_length else 1,
                                 strong_break=strong_break))
        except (CutContractError, ValueError) as exc:
            blocked.append(dict(cut_index=index,reason=str(exc)))
    return drawings, blocked
