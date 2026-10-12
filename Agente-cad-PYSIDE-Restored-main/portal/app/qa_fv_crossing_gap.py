"""Original wall/label evidence for crossings, independent of SA ownership."""
import math
import re


def crossing_gap_evidence(lo, hi, band, angle, texts, strokes, epsilon=.05):
    """Link a transverse original wall pair, its name and numeric section.

    Coordinates are in the measured fundo's local frame. A transverse pair
    must reach a band edge and share a substantial real span beyond it. This
    identifies a crossing corridor without manufacturing a wall in the gap.
    Equal depth is evidence, not authorization for either beam to pass.
    """
    sides={lo:[],hi:[]}
    for stroke in strokes:
        a,b,handle=stroke
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=math.hypot(dx,dy)
        if not handle or length<=0 or abs(dx)/length>math.sin(math.radians(.1)):
            continue
        for side in sides:
            if max(abs(a[0]-side),abs(b[0]-side))<=epsilon:
                sides[side].append((min(a[1],b[1]),max(a[1],b[1]),handle))
    proofs=[]
    for a0,a1,ah in sides[lo]:
        for b0,b1,bh in sides[hi]:
            start,end=max(a0,b0),min(a1,b1)
            if end-start<=1e-9:
                continue
            if min(abs(start-band[1]),abs(end-band[0]))>epsilon:
                continue
            # A common source wall span can be above or below the fundo band.
            names=[];sections=[]
            for text in texts:
                rotation=float(text.get('rotation',0))%180
                diff=abs(rotation-(angle+90)%180)
                if min(diff,180-diff)>.1 or not text.get('handle'):
                    continue
                x,y=text['local_position']
                if not start-epsilon<=y<=end+epsilon or not lo-30<=x<=hi+30:
                    continue
                content=str(text.get('text','')).strip()
                if re.fullmatch(r'(?:V|VF)\d+[A-Z]?',content,re.I):
                    names.append((content.upper(),text['handle']))
                match=re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)',content)
                if match:
                    width,depth=[float(v.replace(',','.')) for v in match.groups()]
                    if width>0 and depth>0 and abs(width-(hi-lo))<=epsilon:
                        sections.append((width,depth,text['handle']))
            if len({n for n,h in names})!=1 or len({d for w,d,h in sections})!=1:
                continue
            proofs.append(dict(beam_name=names[0][0],depth_cm=sections[0][1],
                physical_width_cm=hi-lo,wall_handles=sorted({ah,bh}),
                name_handles=sorted({h for n,h in names}),
                section_handles=sorted({h for w,d,h in sections}),
                original_wall_span_cm=[start,end]))
    identities={(p['beam_name'],p['depth_cm']) for p in proofs}
    if len(identities)!=1:
        return None
    return dict(beam_name=proofs[0]['beam_name'],depth_cm=proofs[0]['depth_cm'],
                gap_span_cm=[lo,hi],
                physical_width_cm=hi-lo,
                wall_handles=sorted({h for p in proofs for h in p['wall_handles']}),
                name_handles=sorted({h for p in proofs for h in p['name_handles']}),
                section_handles=sorted({h for p in proofs for h in p['section_handles']}),
                original_wall_spans_cm=[p['original_wall_span_cm'] for p in proofs],
                authority='original_transverse_name_section_wall_pair',
                owner_status='unproved')


def _merged(intervals,epsilon):
    result=[]
    for lo,hi in sorted(intervals):
        if result and lo-result[-1][1]<=epsilon:
            result[-1][1]=max(result[-1][1],hi)
        else:result.append([lo,hi])
    return result


def original_corridor_priority(name,band,angle,texts,strokes,epsilon=.05,solid_polygons=None,anchor_span=None):
    """Recompute D-79/D-83 from original paired walls and named junctions.

    Every parallel name on the anchored physical component must identify the
    same beam. Disconnected components do not contribute names or sections.
    All original matching section labels must agree. A gap is bridged
    only by a separately named, numerically linked transverse source pair;
    pillar holes and arbitrary missing walls stay disconnected. Thus a sum
    of interrupted spans cannot masquerade as one continuous panel.
    """
    labels=[];sections=[];sides=[[],[]]
    for text in texts:
        rotation=float(text.get('rotation',0))%180
        diff=abs(rotation-angle%180)
        if min(diff,180-diff)>.1 or not text.get('handle'):continue
        x,y=text['local_position']
        if not band[0]-20<=y<=band[1]+20:continue
        content=str(text.get('text','')).strip()
        if re.fullmatch(r'(?:V|VF)\d+[A-Z]?',content,re.I):
            labels.append((content.upper(),x,text['handle']))
        match=re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)',content)
        if match:
            width,depth=[float(v.replace(',','.')) for v in match.groups()]
            if width>0 and depth>0 and abs(width-(band[1]-band[0]))<=epsilon:
                sections.append((width,depth,x,text['handle']))
    for a,b,handle in strokes:
        length=math.dist(a,b)
        if not handle or length<=1e-9 or abs(a[1]-b[1])/length>math.sin(math.radians(.1)):continue
        for i,side in enumerate(band):
            if max(abs(a[1]-side),abs(b[1]-side))<=epsilon:
                sides[i].append((min(a[0],b[0]),max(a[0],b[0])))
    sides=[_merged(side,epsilon) for side in sides]
    paired=_merged([(max(a,c),min(b,d)) for a,b in sides[0] for c,d in sides[1]
                    if min(b,d)-max(a,c)>1e-9],epsilon)
    if not paired:return None
    bridges=[];physical=[]
    for lo,hi in paired:
        if physical:
            gap=crossing_gap_evidence(physical[-1][1],lo,band,angle,texts,strokes,epsilon)
            if gap:
                bridges.append(dict(local_span_cm=[physical[-1][1],lo],crossing=gap))
                physical[-1][1]=hi
                continue
        physical.append([lo,hi])
    if anchor_span is not None:
        physical=[p for p in physical if p[0]-epsilon<=anchor_span[0] and p[1]+epsilon>=anchor_span[1]]
        if len(physical)!=1:return None
        bridges=[b for b in bridges if physical[0][0]<=b['local_span_cm'][0] and b['local_span_cm'][1]<=physical[0][1]]
    labels=[s for s in labels if any(lo-epsilon<=s[1]<=hi+epsilon for lo,hi in physical)]
    sections=[s for s in sections if any(lo-epsilon<=s[2]<=hi+epsilon for lo,hi in physical)]
    if {n for n,x,h in labels}!={name.upper()}:return None
    if len({(w,d) for w,d,x,h in sections})!=1:return None
    width,depth=sections[0][:2]
    lengths=[hi-lo for lo,hi in physical]
    solid_proof=False
    if solid_polygons is not None:
        from shapely.geometry import box
        from shapely.ops import unary_union
        solids=unary_union(solid_polygons)
        clipped=unary_union([box(lo,band[0],hi,band[1]) for lo,hi in physical]).difference(solids)
        pieces=[clipped] if clipped.geom_type=='Polygon' else list(getattr(clipped,'geoms',[]))
        if any(p.geom_type!='Polygon' or p.interiors for p in pieces):return None
        lengths=[p.bounds[2]-p.bounds[0] for p in pieces if p.area>0]
        solid_proof=True
    development=sum(lengths)
    if not development:return None
    return dict(beam_name=name.upper(),depth_cm=depth,width_cm=width,
                continuity=max(lengths)/development,development_cm=development,
                physical_components_cm=physical,original_paired_spans_cm=paired,
                original_bridges=bridges,name_handles=sorted(h for n,x,h in labels),
                section_handles=sorted(h for w,d,x,h in sections),
                solid_inventory_checked=solid_proof,
                authority='original_source_wide_unique_named_paired_corridor')


def crossing_owner_evidence(name,band,angle,texts,strokes,crossing,epsilon=.05,
                            solid_polygons=None,human_ownership_checked=False,
                            source_inventory_checked=False,inventory_scope=None):
    """Use the canonical automatic rule; missing source inventory fails closed."""
    own=original_corridor_priority(name,band,angle,texts,strokes,epsilon,solid_polygons,crossing['gap_span_cm'])
    if own is None:return None
    # A +90 degree frame maps (x,y) to (y,-x).
    other_texts=[{**t,'local_position':(t['local_position'][1],-t['local_position'][0])} for t in texts]
    other_strokes=[((a[1],-a[0]),(b[1],-b[0]),h) for a,b,h in strokes]
    lo,hi=crossing['gap_span_cm']
    from shapely import affinity
    other_solids=None if solid_polygons is None else [affinity.rotate(p,-90,origin=(0,0)) for p in solid_polygons]
    other=original_corridor_priority(crossing['beam_name'],(-hi,-lo),angle+90,
                                     other_texts,other_strokes,epsilon,other_solids,(-band[1],-band[0]))
    if other is None:return None
    if inventory_scope is not None:
        source_inventory_checked = inventory_scope(own,other)
    # Equal-depth T uses D-90, not the through-crossing continuity ranking.
    # Original wall pairs must extend on both sides of the junction in both
    # corridors before D-79/D-83 can certify the automatic owner.
    def through(proof,span):
        return any(lo<span[0]-epsilon and hi>span[1]+epsilon
                   for lo,hi in proof['physical_components_cm'])
    junction='through_crossing' if through(own,(lo,hi)) and through(other,(-band[1],-band[0])) else 'T_or_terminal'
    # Numeric dimensions were independently required to match physical walls.
    # Use those linked numbers, not sub-EPS drawing noise, for section ranking.
    priorities=[(p['depth_cm'],p['width_cm'],p['continuity'],p['development_cm'],p['beam_name']) for p in (own,other)]
    winner=(own,other)[priorities[1]>priorities[0]]
    return dict(owner_name=winner['beam_name'],rule='D-79/D-83',
                own=own,transverse=other,
                junction_topology=junction,
                authority='original_source_recomputed_automatic_owner',
                owner_status=('proved' if solid_polygons is not None and
                              (human_ownership_checked or source_inventory_checked) and
                              (junction=='through_crossing' or own['depth_cm']!=other['depth_cm'])
                              else 'candidate_requires_inventory_or_T_rule'))
