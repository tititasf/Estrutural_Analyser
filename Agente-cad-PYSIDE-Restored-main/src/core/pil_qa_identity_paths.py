"""Independent nominal identity paths through original rectangular supports.

This is a source-CAD reader, not an SA propagation rule. A measured local pair
may inherit a name only along a completely evidenced, constant-width path.
"""
from __future__ import annotations
import math
import re
from src.core.qa_original_polyline import original_polyline_xyb

_NAME = re.compile(r'(?:V|VF)\d+[A-Z]?', re.I)
_SECTION = re.compile(r'\d+(?:[.,]\d+)?/\d+(?:[.,]\d+)?')


def collect_identity_scene(doc, tolerance_cm):
    """Read immutable DXF entities; no interpreted beam or pillar state accepted."""
    from src.core.cad_object_recognition import section_layer
    from src.core.lv_beam_scene import split_dimension_lines
    from pathlib import Path
    frame_handles=set(); frame_error=None
    source_path=Path(doc.filename) if doc.filename else None
    if source_path and source_path.is_file():
        from portal.app.preprocessamento.adapters.sheet_frames import inventory_sheet_frames
        try:
            frame_inventory=inventory_sheet_frames(source_path)
            frame_handles={h for r in frame_inventory['records'] for h in r['source_entity_handles']}
            frame_error=frame_inventory.get('error')
        except (OSError, ValueError, KeyError) as exc:
            frame_error=str(exc)
    raw, labels, contours, segments = [], [], [], []
    for entity in doc.modelspace():
        if section_layer(entity.dxf.layer):
            continue
        kind = entity.dxftype()
        pairs = []
        if kind == 'LINE':
            pairs = [(entity.dxf.start, entity.dxf.end)]
        elif kind in {'LWPOLYLINE', 'POLYLINE'}:
            pts, flagged_closed = original_polyline_xyb(entity)
            closed = flagged_closed or (len(pts)>3 and abs(pts[0][0]-pts[-1][0])<tolerance_cm and abs(pts[0][1]-pts[-1][1])<tolerance_cm)
            if closed and not any(p[2] for p in pts):
                contours.append((entity.dxf.handle, set((float(p[0]),float(p[1])) for p in pts)))
            pairs = [(a,b) for a,b in zip(pts,pts[1:]+(pts[:1] if flagged_closed else [])) if not a[2]]
        elif kind in {'TEXT','MTEXT'}:
            raw_text = entity.dxf.text if kind=='TEXT' else entity.plain_text()
            height = float(entity.dxf.height if kind=='TEXT' else entity.dxf.char_height)
            footprint = None
            if _NAME.fullmatch(raw_text.strip()):
                from ezdxf.bbox import extents
                bounds = extents([entity])
                if bounds.has_data:
                    footprint = [bounds.extmin.x,bounds.extmin.y,bounds.extmax.x,bounds.extmax.y]
            for token in re.split(r'\s+',raw_text.strip()):
                labels.append(dict(text=token,x=float(entity.dxf.insert.x),y=float(entity.dxf.insert.y),
                    handle=entity.dxf.handle,margin=max(height*2,tolerance_cm),
                    rotation=float(entity.dxf.get('rotation',0) if kind=='TEXT' else entity.get_rotation()),
                    original_name_footprint=footprint))
        for a,b in pairs:
            segment = tuple(float(v) for v in (a[0],a[1],b[0],b[1]))
            segments.append(segment)
            axis = 'x' if abs(a[1]-b[1])<tolerance_cm else 'y' if abs(a[0]-b[0])<tolerance_cm else None
            if axis:
                ai,ti = (0,1) if axis=='x' else (1,0)
                raw.append(dict(axis=axis,pos=float(a[ti]),lo=min(a[ai],b[ai]),hi=max(a[ai],b[ai]),
                    handles=[entity.dxf.handle],kind=kind,segment=segment))
    dimensions = set(split_dimension_lines(segments,[dict(text=t['text'],pos=[t['x'],t['y']]) for t in labels])[1])
    closed_handles = {h for h,_ in contours}
    walls = []
    for wall in sorted(raw,key=lambda w:(w['axis'],w['pos'],w['lo'])):
        if wall['handles'][0] in closed_handles or (wall['kind']=='LINE' and wall['segment'] in dimensions):
            continue
        compatible = [w for w in walls if w['axis']==wall['axis'] and abs(w['pos']-wall['pos'])<=1e-7
            and wall['lo']<=w['hi']+tolerance_cm and wall['hi']>=w['lo']-tolerance_cm]
        if len(compatible)==1:
            target=compatible[0]
            target.update(lo=min(target['lo'],wall['lo']),hi=max(target['hi'],wall['hi']),
                handles=sorted(set(target['handles']+wall['handles'])))
        else:
            walls.append(dict(wall))
    supports=[]
    for handle,vertices in contours:
        if handle in frame_handles:
            continue
        if len(vertices)!=4:
            continue
        x0,x1=min(x for x,y in vertices),max(x for x,y in vertices)
        y0,y1=min(y for x,y in vertices),max(y for x,y in vertices)
        if not all((abs(x-x0)<tolerance_cm or abs(x-x1)<tolerance_cm) and
            (abs(y-y0)<tolerance_cm or abs(y-y1)<tolerance_cm) for x,y in vertices):
            continue
        # Every closed piece blocks a free span, but only a numerically owned
        # pillar may bridge it. A P text inside a piece is not ownership proof.
        supports.append(dict(handle=handle,bounds=(x0,x1,y0,y1),name_handles=[],dimension_handles=[]))
    # Canonical numeric pillar ownership contract: P label, its aligned
    # B/H callout immediately below, and one closed contour of those dimensions.
    # This is the same independent evidence used by QA's pillar-section reader;
    # the label is commonly outside the piece and location alone never suffices.
    from portal.app.qa_cad_gate import _proved_pillar_section_handles, _beam_texts
    bindings=_proved_pillar_section_handles(doc, _beam_texts(doc), return_bindings=True)
    pillar_sections={h for record in bindings for h in record['dimension_handles']}
    for record in bindings:
        for support in supports:
            if support['handle']==record['contour_handle']:
                support.update(name_handles=record['name_handles'],dimension_handles=record['dimension_handles'],
                    label_footprint=record['label_footprint'])
    original_open_walls=[dict(w,handle=w['handles'][0]) for w in raw
        if w['handles'][0] not in closed_handles
        and not (w['kind']=='LINE' and w['segment'] in dimensions)]
    from src.core.pil_qa_dimensioned_sections import collect_dimensioned_sections
    return dict(walls=walls,original_open_walls=original_open_walls,
        source_path=str(source_path) if source_path else None,
        dimensioned_sections=collect_dimensioned_sections(doc,tolerance_cm),
        labels=[t for t in labels if t['handle'] not in pillar_sections],supports=supports,
        sheet_frame_handles=sorted(frame_handles),sheet_frame_error=frame_error)


def original_name_in_span(label, axis, span, positions, tolerance_cm):
    """Bind a whole original name straddling a face by its printed extent.

    At least 80% of its longitudinal footprint must belong to this span.
    This fallback never applies to sections or tokens inside longer MTEXT.
    """
    eps=tolerance_cm
    lo,hi=span;bottom,top=sorted(positions)
    if not _NAME.fullmatch(label['text']): return False
    if abs(math.sin(math.radians(label['rotation']-(0 if axis=='x' else 90))))>=1e-6:
        return False
    if not bottom-label['margin']<=label['y' if axis=='x' else 'x']<=top+label['margin']:
        return False
    if lo-eps<=label[axis]<=hi+eps: return True
    footprint=label.get('original_name_footprint')
    if not footprint: return False
    a,b=(footprint[0],footprint[2]) if axis=='x' else (footprint[1],footprint[3])
    length=b-a
    return length>eps and max(0,min(b,hi)-max(a,lo))/length>=.8


def supported_anchor_start(nodes, supports, wall_handles, anchor, tolerance_cm):
    """Locate an original wall pair whose face lies inside one owned support.

    Both original walls must cover the complete distance to that support's
    nearest exit. No open gap, competing exit or anonymous closed piece proves
    continuity. This selects a graph start; it does not transport a section.
    """
    eps = tolerance_cm
    containing = [s for s in supports if s['lo']+eps < anchor < s['hi']-eps]
    if len(containing) != 1:
        return None
    support = containing[0]
    if not support.get('name_handles') or not support.get('dimension_handles'):
        return None
    matches = []
    for i, node in enumerate(nodes):
        if not set(wall_handles).issubset(node['wall_handles']):
            continue
        exits = [x for x, endpoint in ((support['lo'], node['hi']),
                                      (support['hi'], node['lo']))
                 if abs(x-endpoint) <= eps]
        for exit_at in exits:
            lo, hi = sorted((anchor, exit_at))
            if all(w['lo'] <= lo+eps and w['hi'] >= hi-eps for w in node['walls']):
                matches.append((i, dict(pillar_handle=support['handle'],
                    name_handles=support['name_handles'],
                    dimension_handles=support['dimension_handles'],
                    bounds=support['bounds'], anchor=anchor, exit_at=exit_at,
                    wall_handles=node['wall_handles'])))
    return matches[0] if len(matches) == 1 else None


def prove_identity_path(scene, *, axis, positions, wall_handles, anchor, requested_name, tolerance_cm):
    """Certify a local constant-width pair via original wall/support graph.

    The local measured span needs its own unique numeric section. Intervening
    spans may omit a section; no height or section is propagated from them.
    An explicit conflicting width or ambiguous section vetoes that span. Every gap
    needs one original named closed rectangular support and both walls at both
    opposing faces. Conflicting aligned names in the first nominal frontiers veto.
    """
    eps=tolerance_cm
    if scene.get('sheet_frame_error'):
        return dict(status='uncertain',reason='original sheet-frame classification failed',error=scene['sheet_frame_error'])
    bottom,top=sorted(positions)
    bands=[[w for w in scene['walls'] if w['axis']==axis and abs(w['pos']-p)<=1e-7] for p in (bottom,top)]
    supports=[]
    for support in scene['supports']:
        x0,x1,y0,y1=support['bounds']
        lo,hi,c0,c1=(x0,x1,y0,y1) if axis=='x' else (y0,y1,x0,x1)
        if c0-eps<=bottom and top<=c1+eps:
            supports.append(dict(support,lo=lo,hi=hi))
    # A true crossing of a separately named perpendicular beam is an identity
    # boundary. A T ending at one band edge does not cross both band walls.
    perpendicular=[w for w in scene['walls'] if w['axis']!=axis and
        w['lo'] < bottom-eps and w['hi'] > top+eps]
    cross_axis='y' if axis=='x' else 'x'
    for i,a in enumerate(perpendicular):
        for b in perpendicular[i+1:]:
            lo,hi=sorted((a['pos'],b['pos']))
            if hi-lo<=eps: continue
            crossing_texts=[t for t in scene['labels'] if lo-t['margin']<=t[axis]<=hi+t['margin'] and
                max(a['lo'],b['lo'])-eps<=t[cross_axis]<=min(a['hi'],b['hi'])+eps and
                abs(math.sin(math.radians(t['rotation']-(90 if axis=='x' else 0))))<1e-6]
            names=[t for t in crossing_texts if _NAME.fullmatch(t['text'])]
            sections=[t for t in crossing_texts if _SECTION.fullmatch(t['text']) and
                abs(float(t['text'].split('/')[0].replace(',','.'))-(hi-lo))<=eps]
            if len({t['text'] for t in names})==1 and len({t['text'] for t in sections})==1:
                supports.append(dict(lo=lo,hi=hi,name_handles=[],dimension_handles=[]))
    nodes=[]
    for a in bands[0]:
        for b in bands[1]:
            lo,hi=max(a['lo'],b['lo']),min(a['hi'],b['hi'])
            if hi-lo<10:
                continue
            intervals=[(lo,hi)]
            for support in supports:
                pieces=[]
                for l,h in intervals:
                    if support['hi']<=l+eps or support['lo']>=h-eps:
                        pieces.append((l,h))
                    else:
                        if support['lo']-l>=10: pieces.append((l,support['lo']))
                        if h-support['hi']>=10: pieces.append((support['hi'],h))
                intervals=pieces
            for l,h in intervals:
                local=[t for t in scene['labels'] if l-eps<=t[axis]<=h+eps and
                    bottom-t['margin']<=t['y' if axis=='x' else 'x']<=top+t['margin'] and
                    abs(math.sin(math.radians(t['rotation']-(0 if axis=='x' else 90))))<1e-6]
                sections=[t for t in local if _SECTION.fullmatch(t['text'])]
                if not sections:
                    from src.core.pil_qa_dimensioned_sections import sections_in_span
                    sections=sections_in_span(scene.get('dimensioned_sections',[]),
                        axis=axis,positions=(bottom,top),span=(l,h),tolerance_cm=eps)
                    if len({t['text'] for t in sections})>1:
                        continue
                if any(abs(float(t['text'].split('/')[0].replace(',','.'))-(top-bottom))>eps
                        for t in sections):
                    continue
                section_cells=None
                if len({t['text'] for t in sections})>1:
                    from src.core.pil_qa_section_boundaries import proved_section_cells
                    section_cells=proved_section_cells(scene.get('original_open_walls', []),local,
                        axis=axis,positions=(bottom,top),span=(l,h),closed_handles=set(),tolerance_cm=eps,
                        source_path=scene.get('source_path'))
                    if not section_cells:
                        continue
                names=[t for t in scene['labels'] if original_name_in_span(t,axis,(l,h),(bottom,top),eps)]
                nodes.append(dict(lo=l,hi=h,walls=(a,b),wall_handles=sorted(set(a['handles']+b['handles'])),
                    section=sections[0]['text'] if sections and not section_cells else None,
                    section_cells=section_cells,
                    section_handles=sorted({handle for t in sections
                        for handle in t.get('evidence_handles',[t['handle']])}),names=names))
    starts=[i for i,n in enumerate(nodes) if n['lo']-eps<=anchor<=n['hi']+eps and
        set(wall_handles).issubset(n['wall_handles'])]
    anchor_support = None
    if not starts:
        supported = supported_anchor_start(nodes, supports, wall_handles, anchor, eps)
        if supported:
            starts = [supported[0]]
            anchor_support = supported[1]
    if len(starts)!=1:
        return dict(status='uncertain',reason='local original wall pair does not identify one graph span')
    edges={i:[] for i in range(len(nodes))}
    for i,a in enumerate(nodes):
        for j,b in enumerate(nodes[i+1:],i+1):
            left,right=(a,b) if a['lo']<b['lo'] else (b,a)
            proofs=[s for s in supports if s['name_handles'] and s['dimension_handles'] and
                abs(left['hi']-s['lo'])<=eps and abs(right['lo']-s['hi'])<=eps
                and all(w['lo']<=s['lo']+eps and w['hi']>=s['lo']-eps for w in left['walls'])
                and all(w['lo']<=s['hi']+eps and w['hi']>=s['hi']-eps for w in right['walls'])]
            if len(proofs)==1:
                edges[i].append((j,proofs[0]));edges[j].append((i,proofs[0]))
            elif not proofs:
                from src.core.pil_qa_t_joints import prove_original_t_joint
                joint=prove_original_t_joint(scene,left,right,axis=axis,
                    positions=(bottom,top),tolerance_cm=eps)
                if joint:
                    edges[i].append((j,joint));edges[j].append((i,joint))
    start=starts[0]
    if not nodes[start]['section_handles']:
        return dict(status='uncertain',reason='local span has no unique numeric section')
    parents={start:None};queue=[start];targets=[]
    for i in queue:
        # An original nominal label ends this branch. Never skip a different
        # name to reach a requested one; both first-name frontiers must agree.
        if nodes[i]['names']:
            targets.append(i)
            continue
        for j,support in edges[i]:
            if j not in parents:
                parents[j]=(i,support);queue.append(j)
    names={t['text'] for i in targets for t in nodes[i]['names']}
    if names!={requested_name}:
        return dict(status='uncertain',reason='first named original frontiers absent or competing',names=sorted(names))
    target=targets[0];path=[];bridges=[]
    cursor=target
    while cursor is not None:
        n=nodes[cursor]
        path.append(dict(lo=n['lo'],hi=n['hi'],wall_handles=n['wall_handles'],section=n['section'],
            section_handles=n['section_handles'],section_cells=n.get('section_cells')))
        parent=parents[cursor]
        if parent is None: break
        cursor,support=parent
        if support.get('kind')=='original_named_t_opening':
            bridges.append(dict(support))
        else:
            bridges.append(dict(pillar_handle=support['handle'],name_handles=support['name_handles'],
                dimension_handles=support['dimension_handles'],bounds=support['bounds']))
    return dict(status='measured',kind='original_constant_width_support_path',beam_handles=[t['handle'] for t in nodes[target]['names']],
        name_footprints={t['handle']:t['original_name_footprint'] for t in nodes[target]['names']
            if t.get('original_name_footprint')},
        wall_pair_positions=[bottom,top],spans=list(reversed(path)),supports=list(reversed(bridges)),
        **({'anchor_support': anchor_support} if anchor_support else {}))
