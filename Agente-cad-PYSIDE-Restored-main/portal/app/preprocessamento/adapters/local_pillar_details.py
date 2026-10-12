"""Read useful enlarged details without creating another plan pillar.

Region detection only scopes the evidence. An explicit equality caption and exact canonical contour correspondence identify
a candidate. Numeric co-presence does not prove dimension-to-edge association.
Complete original dimension chains can authorize a detail for contextual use.
This inventory never changes plan geometry or claims actual SA consumption.
"""
from collections import Counter
import hashlib
import math
from pathlib import Path
import re
from shapely.affinity import scale, translate
from shapely.geometry import Polygon, Point, LineString, box

CAPTION = re.compile(r'\s*(P\d+(?:\s*=\s*P\d+)+)\s*', re.I)
PRINTED_SCALE = re.compile(r'\s*ESC\.?\s*:?\s*1\s*:\s*(\d+(?:[.,]\d+)?)\s*', re.I)
NUMBER = re.compile(r'\s*(\d+(?:[.,]\d+)?)\s*')
# DXF coordinates are stored to six decimals. This permits rounding only, not
# snapping a nearby feature or bridging a missing dimension extension.
COORD_EPS = 1e-4


def _axis(a, b):
    if abs(a[1]-b[1]) <= COORD_EPS and abs(a[0]-b[0]) > COORD_EPS:
        return 0
    if abs(a[0]-b[0]) <= COORD_EPS and abs(a[1]-b[1]) > COORD_EPS:
        return 1
    return None


def dimension_chain_proof(points, texts, lines):
    """Measure only explicit exploded dimensions tied to contour vertices.

    Both ends require a centered diagonal tick, a perpendicular extension, and
    an original zero-length dimension definition point on the source contour.
    A unique aligned numeric label must sit inside that span, within half its
    own text height of the dimension line. Every contour edge must be covered.
    The independent span/value ratios must agree in both drawing axes.
    """
    vertices=list(Polygon(points).exterior.coords)[:-1]
    chains=[]
    for spine in lines:
        a,b=spine['start'],spine['end'];axis=_axis(a,b)
        if axis is None:
            continue
        perp=1-axis;lo,hi=sorted((a[axis],b[axis]));endpoint_proofs=[]
        for end in (a,b):
            ticks=[l for l in lines if
                abs((l['start'][0]+l['end'][0])/2-end[0])<=COORD_EPS and
                abs((l['start'][1]+l['end'][1])/2-end[1])<=COORD_EPS and
                abs(l['start'][0]-l['end'][0])>COORD_EPS and
                abs(l['start'][1]-l['end'][1])>COORD_EPS and
                abs(abs(l['start'][0]-l['end'][0])-abs(l['start'][1]-l['end'][1]))<=COORD_EPS]
            if not ticks:
                break
            proofs=[]
            for vertex in vertices:
                if abs(vertex[axis]-end[axis])>COORD_EPS:
                    continue
                markers=[l for l in lines if math.dist(l['start'],vertex)<=COORD_EPS and math.dist(l['end'],vertex)<=COORD_EPS]
                if not markers:
                    continue
                for extension in lines:
                    s,t=extension['start'],extension['end']
                    if _axis(s,t)!=perp or abs(s[axis]-end[axis])>COORD_EPS:
                        continue
                    if not min(s[perp],t[perp])-COORD_EPS<=end[perp]<=max(s[perp],t[perp])+COORD_EPS:
                        continue
                    near=min((s,t),key=lambda p:abs(p[perp]-vertex[perp]))
                    # The extension must reach towards the source vertex. Its
                    # drafting gap cannot exceed half the actual tick length.
                    if (near[perp]-vertex[perp])*(end[perp]-vertex[perp])<=0:
                        continue
                    valid_ticks=[tick for tick in ticks if abs(near[perp]-vertex[perp])<=math.dist(tick['start'],tick['end'])/2+COORD_EPS]
                    if valid_ticks:
                        proofs.append(dict(vertex=list(vertex),extension_handles=[extension['handle']],
                            marker_handles=[m['handle'] for m in markers],tick_handles=[t['handle'] for t in valid_ticks]))
            # Multiple extension entities may coincide in a dimension chain;
            # different possible source vertices remain genuinely ambiguous.
            unique={tuple(p['vertex']) for p in proofs}
            if len(unique)!=1:
                break
            endpoint_proofs.append(proofs)
        if len(endpoint_proofs)!=2:
            continue
        labels=[]
        for text in texts:
            if not NUMBER.fullmatch(text['text']) or float(text['text'].replace(',','.'))<=0:
                continue
            pos=text['position'];height=text.get('height',0)
            rotation=text.get('rotation',0)%180
            if (height>0 and abs(rotation-axis*90)<=1e-6 and
                    lo+COORD_EPS<pos[axis]<hi-COORD_EPS and
                    abs(pos[perp]-a[perp])<=height/2+COORD_EPS):
                labels.append(text)
        if len(labels)!=1:
            continue
        value=float(labels[0]['text'].replace(',','.'))
        chains.append(dict(axis=axis,span=[lo,hi],value=value,
            drawing_to_physical_factor=(hi-lo)/value,text=dict(labels[0]),
            spine_handle=spine['handle'],endpoint_proofs=endpoint_proofs))
    edges=[]
    for a,b in zip(vertices,vertices[1:]+vertices[:1]):
        axis=_axis(a,b)
        if axis is None:
            return dict(status='unproved',reason='non_axis_aligned_contour')
        span=sorted((a[axis],b[axis]))
        matches=[c for c in chains if c['axis']==axis and all(abs(x-y)<=COORD_EPS for x,y in zip(span,c['span']))]
        if not matches:
            return dict(status='unproved',reason='incomplete_original_dimension_chains')
        edges.extend(matches)
    factors=[c['drawing_to_physical_factor'] for c in edges]
    factor=sum(factors)/len(factors)
    if any(abs(v-factor)>1e-6*max(1,factor) for v in factors):
        return dict(status='unproved',reason='conflicting_original_dimension_scales')
    unique={c['spine_handle']:c for c in edges}
    return dict(status='proved',drawing_to_physical_factor=factor,chains=list(unique.values()),
                tolerance_drawing_units=COORD_EPS)


def normalized(polygon):
    return translate(polygon,xoff=-polygon.bounds[0],yoff=-polygon.bounds[1])


def equivalent(a,b):
    a=normalized(a)
    return any(a.symmetric_difference(normalized(scale(b,xfact=x,yfact=y,origin=(0,0)))).area<1e-6
               for x,y in ((1,1),(-1,1),(1,-1),(-1,-1)))


def bind_region(region, contours, texts, pillars, lines=None):
    captions=[t for t in texts if CAPTION.fullmatch(t['text'])]
    if len(captions)!=1:
        return dict(status='unresolved',reason='missing_or_ambiguous_explicit_pillar_equality')
    caption=captions[0];names=re.findall(r'P\d+',caption['text'].upper())
    owners={name:[p for p in pillars if p.get('name')==name and p.get('points')] for name in names}
    if any(len(rows)!=1 for rows in owners.values()):
        return dict(status='unresolved',reason='canonical_caption_owner_missing_or_ambiguous',pillar_names=names)
    canonical=[Polygon(rows[0]['points']) for rows in owners.values()]
    if any(not p.is_valid or p.area<=0 for p in canonical):
        return dict(status='unresolved',reason='invalid_canonical_contour',pillar_names=names)
    dimension_texts=[t for t in texts if NUMBER.fullmatch(t['text'])]
    values=Counter(round(float(t['text'].replace(',','.')),3) for t in dimension_texts)
    matched=[]
    for contour in contours:
        original=Polygon(contour['points'])
        if not original.is_valid or original.area<=0:
            continue
        c=canonical[0];drawing_scale=math.sqrt(original.area/c.area)
        physical=scale(original,xfact=1/drawing_scale,yfact=1/drawing_scale,origin=(0,0))
        if not all(equivalent(physical,p) for p in canonical):
            continue
        edges=Counter(round(math.dist(a,b)/drawing_scale,3)
            for a,b in zip(original.exterior.coords,list(original.exterior.coords)[1:]) if math.dist(a,b)>1e-6)
        if any(values[v]<count for v,count in edges.items()):
            continue
        matched.append((contour,physical,drawing_scale,edges))
    if len(matched)!=1:
        return dict(status='unresolved',reason='numeric_edge_dimensions_or_unique_contour_not_proved',pillar_names=names)
    contour,physical,factor,edges=matched[0]
    widths=physical.bounds[2]-physical.bounds[0];height=physical.bounds[3]-physical.bounds[1]
    printed=[t for t in texts if PRINTED_SCALE.fullmatch(t['text'])]
    record=dict(status='candidate',role='pillar_detail_candidate',pillar_names=names,
        source_entity_handles=[contour['handle']],caption=dict(caption),
        unbound_numeric_text_candidates=[dict(t) for t in dimension_texts if round(float(t['text'].replace(',','.')),3) in edges],
        printed_scale_evidence=[dict(t) for t in printed],
        original_points=contour['points'],candidate_drawing_to_physical_factor=factor,
        canonical_correspondence_dimensions_cm=dict(width=round(widths,3),height=round(height,3),edge_lengths=sorted(edges.elements())),
        region_bbox=[float(v) for v in region['bbox']],candidate_method='explicit_equality_numeric_copresence_exact_canonical_contour',
        dimension_chain_bound=False,consumer_authorized=False,
        proves='candidate correspondence only; dimension chains and consumer integration remain unproved',
        creates_plan_pillar=False)
    proof=dimension_chain_proof(contour['points'],texts,lines or [])
    record['dimension_chain_proof']=proof
    if proof['status']=='proved':
        measured_factor=proof['drawing_to_physical_factor']
        measured=scale(Polygon(contour['points']),xfact=1/measured_factor,yfact=1/measured_factor,origin=(0,0))
        if not all(equivalent(measured,p) for p in canonical):
            record['dimension_chain_proof']=dict(status='unproved',reason='measured_contour_disagrees_with_canonical_owners')
        else:
            record.update(status='proved',role='pillar_detail',dimension_chain_bound=True,consumer_authorized=True,
                drawing_to_physical_factor=measured_factor,
                physical_dimensions_cm=dict(width=round(measured.bounds[2]-measured.bounds[0],3),
                    height=round(measured.bounds[3]-measured.bounds[1],3),edge_lengths=sorted(edges.elements())),
                proves='original dimension chains, physical contour and caption owners; no plan location, altitude or classification',
                binding_method='original_vertex_markers_extensions_ticks_unique_aligned_numeric_labels_exact_canonical_confirmation')
    return record


def crosscheck_sa_details(inventory, report, source_revision):
    """Compare proved detail measurements to actual SA output without changing N1."""
    calls=[];blocked=[]
    if inventory.get('status')=='unavailable':
        return dict(status='blocked',consumer_calls=[],blocked=[dict(
            reason='detail_region_detection_unavailable',detail=inventory.get('reason'),
            source_revision=inventory.get('source_revision'))])
    for record in inventory.get('records') or []:
        if not (record.get('status')=='proved' and record.get('dimension_chain_bound')
                and record.get('consumer_authorized')):
            continue
        reason=None
        if record.get('source_role') == 'declared_raw_detail':
            if record.get('plan_source_revision') != source_revision:
                reason='detail_plan_source_revision_mismatch'
            try:
                current=hashlib.sha256(Path(record['source_path']).read_bytes()).hexdigest()
                if current != record.get('source_revision'):
                    reason=reason or 'detail_external_source_revision_mismatch'
            except (OSError, KeyError, TypeError):
                reason=reason or 'detail_external_source_unavailable'
        elif record.get('source_revision') != source_revision:
            reason='detail_source_revision_mismatch'
        factor=record.get('drawing_to_physical_factor')
        try:
            expected=scale(Polygon(record['original_points']),xfact=1/factor,yfact=1/factor,origin=(0,0))
        except (ValueError, TypeError, KeyError, ZeroDivisionError):
            reason='invalid_proved_detail_geometry';expected=None
        for name in record.get('pillar_names') or []:
            owners=[(key,item) for key,item in report.items() if item.get('name',key)==name]
            owner_reason=reason
            if len(owners)!=1 or not owners[0][1].get('points'):
                owner_reason=owner_reason or 'actual_sa_owner_missing_or_ambiguous'
            elif expected is not None:
                actual=Polygon(owners[0][1]['points'])
                if not actual.is_valid or not equivalent(expected,actual):
                    owner_reason=owner_reason or 'actual_sa_contour_disagrees_with_detail'
            evidence=dict(item=name,source_revision=record.get('source_revision'),
                source_role=record.get('source_role','tower'),
                plan_source_revision=record.get('plan_source_revision',source_revision),
                source_entity_handles=record.get('source_entity_handles'),
                dimension_chains=record.get('dimension_chain_proof',{}).get('chains',[]),
                expected_dimensions_cm=record.get('physical_dimensions_cm'),
                field='points',matches=owner_reason is None,geometry_modified=False)
            if owner_reason:
                blocked.append(dict(evidence,reason=owner_reason))
            else:
                calls.append(dict(evidence,report_key=owners[0][0],actual_points=owners[0][1]['points']))
    return dict(status='blocked' if blocked else 'checked' if calls else 'no_proved_detail',
                consumer_calls=calls,blocked=blocked)


def inventory_local_details(source, pillars, detection=None):
    import ezdxf
    from scripts.obra_crop_engine import detect_regions
    path=Path(source);revision=hashlib.sha256(path.read_bytes()).hexdigest()
    detection=detection or detect_regions(path)
    if detection.get('error'):
        return dict(status='unavailable',reason=str(detection['error']),records=[],
                    source_revision=revision,production_files_modified=False)
    doc=ezdxf.readfile(path);result=[]
    for region in detection.get('detalhes') or []:
        scope=box(*region['bbox']);contours=[];texts=[];lines=[]
        for entity in doc.modelspace():
            kind=entity.dxftype()
            if kind in ('TEXT','MTEXT'):
                position=(entity.dxf.insert.x,entity.dxf.insert.y)
                if scope.buffer(.01).covers(Point(position)):
                    texts.append(dict(handle=entity.dxf.handle,text=entity.dxf.text if kind=='TEXT' else entity.plain_text(),position=list(position),
                        height=float(entity.dxf.get('height',0) if kind=='TEXT' else entity.dxf.get('char_height',0)),
                        rotation=float(entity.dxf.get('rotation',0) if kind=='TEXT' else entity.get_rotation())))
            elif kind=='LINE':
                start=list(entity.dxf.start)[:2];end=list(entity.dxf.end)[:2]
                geometry=Point(start) if math.dist(start,end)<=COORD_EPS else LineString([start,end])
                if scope.buffer(.01).intersects(geometry):
                    lines.append(dict(handle=entity.dxf.handle,start=start,end=end))
            elif kind=='LWPOLYLINE' and not any(abs(p[4])>1e-8 for p in entity.get_points()):
                points=[list(p) for p in entity.get_points('xy')]
                if len(points)>=4 and (entity.closed or points[0]==points[-1]):
                    polygon=Polygon(points)
                    if polygon.is_valid and scope.buffer(.01).covers(polygon):
                        contours.append(dict(handle=entity.dxf.handle,points=points))
        record=bind_region(region,contours,texts,pillars,lines)
        record.update(source_revision=revision,source_path=str(path),region_id=int(region['idx']) if region.get('idx') is not None else None)
        result.append(record)
    return dict(status='proved_details' if any(r['status']=='proved' for r in result) else 'candidates' if any(r['status']=='candidate' for r in result) else 'unresolved',
                records=result,source_revision=revision,production_files_modified=False)


def inventory_declared_details(root, package, tower_path, pillars):
    """Include a detail in the declared original of this tower's own sheet.

    No folder search, floor guessing or neighboring sheet is accepted. External
    handles retain their namespace and cannot reclassify contours of the crop.
    Dimensions still require complete original chains and actual SA crosscheck.
    """
    root=Path(root).resolve();tower=Path(tower_path).resolve()
    inventory=inventory_local_details(tower,pillars)
    if inventory['status']=='unavailable':return inventory
    tower_revision=inventory['source_revision'];scope=package.get('scope') or {}
    sources=package.get('sources') or []
    owners=[s for s in sources if s.get('kind')=='tower'
        and s.get('revision')==tower_revision
        and (root/str(s.get('relative_path',''))).resolve()==tower]
    if len(owners)!=1:return inventory
    owner=owners[0]
    declared=[s for s in sources if s.get('kind')=='raw_level_reference'
        and s.get('bruto_id')==owner.get('bruto_id')
        and s.get('obra_id')==scope.get('obra_id')
        and s.get('pavimento_id')==scope.get('pavimento_id')]
    if not declared:return inventory
    if len(declared)!=1:
        return dict(inventory,status='unavailable',reason='ambiguous_declared_detail_original')
    source=declared[0]
    raw=(root/str(source.get('relative_path',''))).resolve()
    try:
        if not source.get('validated') or not raw.is_relative_to(root):
            raise ValueError('unvalidated_or_outside_declared_detail_original')
        if hashlib.sha256(raw.read_bytes()).hexdigest()!=source.get('revision'):
            raise ValueError('declared_detail_original_revision_mismatch')
    except (OSError, ValueError) as exc:
        return dict(inventory,status='unavailable',reason=str(exc))
    if raw==tower:return inventory
    external=inventory_local_details(raw,pillars)
    if external['status']=='unavailable':
        return dict(inventory,status='unavailable',reason='declared_detail_detector_unavailable:'+str(external.get('reason')))
    already={n for r in inventory['records'] if r.get('status')=='proved' for n in r.get('pillar_names',[])}
    for record in external['records']:
        if record.get('status')!='proved' or set(record.get('pillar_names',[]))<=already:continue
        inventory['records'].append(dict(record,source_role='declared_raw_detail',
            plan_source_revision=tower_revision,declared_source_id=source.get('source_id')))
    if any(r.get('status')=='proved' for r in inventory['records']):inventory['status']='proved_details'
    return inventory
