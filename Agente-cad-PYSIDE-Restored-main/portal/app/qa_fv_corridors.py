"""Independent local polygon corridors; partial evidence cannot approve a fund."""
import math
import re
from pathlib import Path
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


def measure_source_polygon(source,row,unit,epsilon=.05,*,original_solids=None,human_ownership_checked=False,source_inventory_checked=False,source_inventory=None):
    """Read raw CAD entities; shared parsing is not shared SA interpretation."""
    from .preprocessamento.oriented_beam_section import _source_evidence
    source=Path(source);stat=source.stat()
    texts,strokes=_source_evidence(str(source.resolve()),stat.st_mtime_ns,stat.st_size)
    return measure_polygon(row,texts,strokes,unit,epsilon,original_solids=original_solids,
                           human_ownership_checked=human_ownership_checked,source_inventory_checked=source_inventory_checked,
                           source_inventory=source_inventory)


def measure_polygon(row, texts, strokes, unit, epsilon=.05,*,original_solids=None,human_ownership_checked=False,source_inventory_checked=False,source_inventory=None):
    """Emit ordinary QA contacts, retaining unknown wall gaps, caps and slivers.

    Inputs are original CAD texts (rotation/position/handle) and straight
    strokes (a/b/handle). Local sweep cells preserve the real polygon; no
    bbox rectangle is substituted. Name/section authority and end supports
    remain distinct guards. The caller supplies the canonical extraction EPS.
    """
    name=str(row.get('beam_name') or '');item=f"{name} seg {row.get('segment_label','?')}"
    def rec(aspect,status='uncertain',**facts):
        return dict(unit_path=unit,item=item,aspect=aspect,status=status,errors={},
                    blocks_promotion=True,**facts)
    try:poly=Polygon(row.get('points') or [])
    except (TypeError,ValueError):poly=None
    if poly is None or not poly.is_valid or poly.area<=0:
        return [rec('contorno',guards=['identidade_contorno'],reason='polígono real inválido')]
    names=[t for t in texts if str(t.get('text','')).strip().upper()==name.upper()
           and t.get('handle') and poly.distance(Point(t['position']))<=30]
    if not names:
        # Trecho de continuação: o rótulo único da viga fica em outro vão, mas
        # sobre a mesma linha de centro (V319 seg 2, V420 seg 3). Vale o rótulo
        # cujo afastamento perpendicular ao corredor, no seu próprio eixo, cabe
        # na mesma tolerância de 30 cm.
        def across(t):
            local_poly=affinity.rotate(poly,-float(t.get('rotation',0)),origin=(0,0))
            y=affinity.rotate(Point(t['position']),-float(t.get('rotation',0)),origin=(0,0)).y
            lo,hi=local_poly.bounds[1],local_poly.bounds[3]
            return max(lo-y,0,y-hi)
        names=[t for t in texts if str(t.get('text','')).strip().upper()==name.upper()
               and t.get('handle') and across(t)<=30]
    angles={round(float(t.get('rotation',0))%180,3) for t in names}
    if len(angles)!=1:
        return [rec('eixo local',guards=['identidade_contorno','dimensoes'],reason='nome/eixo original ausente ou ambíguo')]
    angle=angles.pop();local=affinity.rotate(poly,-angle,origin=(0,0));coords=list(local.exterior.coords)
    local_solids=None if original_solids is None else [affinity.rotate(p,-angle,origin=(0,0)) for p in original_solids]
    def rotate(point):
        r=math.radians(-angle);x,y=point
        return (x*math.cos(r)-y*math.sin(r),x*math.sin(r)+y*math.cos(r))
    originals=[(rotate(s['a']),rotate(s['b']),s['handle']) for s in strokes if 'a' in s and 'b' in s]
    original_local_texts=[{**t,'local_position':rotate(t['position'])} for t in texts]
    # Collapse only numerically equal vertex positions, never epsilon-wide
    # material. A thin real sliver must remain visible to the gate.
    xs=sorted(set(round(x,9) for x,y in coords));contacts=[]
    sections=[]
    for t in texts:
        m=re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*',str(t.get('text','')))
        if not m or not t.get('handle'):continue
        rotation=float(t.get('rotation',0))%180;diff=abs(rotation-angle)
        if min(diff,180-diff)>.1:continue
        x,y=rotate(t['position']);width,height=[float(v.replace(',','.')) for v in m.groups()]
        if xs[0]-epsilon<=x<=xs[-1]+epsilon and local.distance(Point(x,y))<=20:
            sections.append(dict(width=width,height=height,handle=t['handle']))
    if not sections:
        contacts.append(rec('seção',guards=['dimensoes'],reason='seção numérica alinhada não vinculada ao corredor original'))
    def coverage(a,b):
        edge=LineString([a,b]);hits=[];pieces=[]
        if edge.length<=1e-9:return 0,[]
        ux=(b[0]-a[0])/edge.length;uy=(b[1]-a[1])/edge.length
        for c,d,handle in originals:
            line=LineString([c,d])
            if line.length<=1e-9:continue
            if abs(ux*(d[1]-c[1])-uy*(d[0]-c[0]))/line.length>math.sin(math.radians(.1)):continue
            if max(abs((p[0]-a[0])*uy-(p[1]-a[1])*ux) for p in (c,d))>epsilon:continue
            clipped=line.intersection(edge.buffer(epsilon,cap_style=2))
            if not clipped.is_empty:
                lo,hi=sorted([(p[0]-a[0])*ux+(p[1]-a[1])*uy for p in (c,d)])
                lo,hi=max(0,lo),min(edge.length,hi)
                if hi>lo:pieces.append(LineString([(lo,0),(hi,0)]));hits.append(handle)
        return (unary_union(pieces).length/edge.length if pieces else 0),sorted(set(hits))
    ymin,ymax=local.bounds[1],local.bounds[3]
    def spans(x):
        cut=local.intersection(LineString([(x,ymin-1),(x,ymax+1)]))
        parts=[cut] if cut.geom_type=='LineString' else list(getattr(cut,'geoms',[]))
        return sorted([(g.bounds[1],g.bounds[3]) for g in parts if g.geom_type=='LineString' and g.length>1e-9])
    for index,(lo,hi) in enumerate(zip(xs,xs[1:])):
        if hi-lo<=1e-9:continue
        # Tampa quase perpendicular (V303 seg 6: 3370,3825 × 3370,4): a fatia
        # ≤ EPS na ponta é a própria tampa, que as guardas de extremo medem.
        if hi-lo<=epsilon and index in (0,len(xs)-2):continue
        samples=[spans(lo+(hi-lo)*f) for f in (.25,.5,.75)]
        if len({len(x) for x in samples})!=1:
            contacts.append(rec(f'topologia corredor {index}',
                guards=['identidade_contorno','inventario_segmentos'],
                local_span_cm=[lo,hi],branch_counts=[len(x) for x in samples],
                reason='quantidade de faixas varia dentro do intervalo; contorno exige subdivisão comprovada'))
            continue
        for branch,mid in enumerate(samples[1]):
            low1,high1=samples[0][branch];low2,high2=samples[2][branch]
            width=mid[1]-mid[0];sloped=abs(low2-low1)>epsilon or abs(high2-high1)>epsilon
            facts=dict(axis_deg=angle,local_span_cm=[lo,hi],measured_width_cm=width,
                       source_name_handles=sorted(t['handle'] for t in names))
            if sloped:
                from .qa_fv_oblique_boundary_candidate import prove_oblique_boundary
                proof=prove_oblique_boundary(local,(lo,hi),originals,epsilon)
                contacts.append(rec(f'paredes oblíquas corredor {index}/{branch}',
                    status=proof['status'],guards=['identidade_contorno'],
                    original_boundary_proof=proof,**facts))
                contacts.append(rec(f'corredor {index}/{branch}',guards=['identidade_contorno','apoios_limites'],
                    reason='ponta/trecho oblíquo exige prova própria de limite',**facts));continue
            covers=[];handles=[]
            for y in mid:
                cov,hs=coverage((lo,y),(hi,y));covers.append(cov);handles.extend(hs)
            uncovered=[max(0.,(1-c)*(hi-lo)) for c in covers]
            full=max(uncovered)<=epsilon
            crossing=None
            if not full:
                from .qa_fv_crossing_gap import crossing_gap_evidence
                crossing=crossing_gap_evidence(lo,hi,mid,angle,original_local_texts,originals,epsilon)
                if crossing:
                    facts['original_crossing']=crossing
                    from .qa_fv_crossing_gap import crossing_owner_evidence
                    def checked_scope(own,other):
                        from shapely.geometry import box
                        from .qa_fv_source_inventory import inventory_scope_checked
                        own_region=unary_union([box(a,mid[0],b,mid[1]) for a,b in own['physical_components_cm']])
                        clo,chi=crossing['gap_span_cm']
                        other_region=unary_union([box(clo,a,chi,b) for a,b in other['physical_components_cm']])
                        region=affinity.rotate(own_region.union(other_region),angle,origin=(0,0))
                        return inventory_scope_checked(source_inventory,region)
                    owner=crossing_owner_evidence(name,mid,angle,original_local_texts,originals,crossing,epsilon,
                                                  local_solids,human_ownership_checked,source_inventory_checked,
                                                  checked_scope if source_inventory is not None else None)
                    if owner:
                        crossing['owner_proof']=owner
                        if owner['owner_status']=='proved' and owner['owner_name']==name.upper():
                            full=True
            contacts.append(rec(f'paredes corredor {index}/{branch}',status='measured' if full else 'uncertain',
                guards=['identidade_contorno'],coverage=covers,uncovered_cm=uncovered,wall_handles=sorted(set(handles)),
                **({} if full else {'reason':('lacuna coincide com corredor transversal original; dono/continuidade do fundo não comprovados'
                    if crossing else 'intervalo sem duas paredes originais; encontro/apoio ainda não comprovado')}),**facts))
            dims={(t['width'],t['height']) for t in sections if abs(t['width']-width)<=epsilon}
            if len(dims)==1 and full:
                bw,depth=dims.pop()
                section=rec(f'seção corredor {index}/{branch}',status='measured',guards=['dimensoes'],
                    declared_section_width_cm=bw,height_cm=depth,
                    section_handles=sorted(t['handle'] for t in sections if t['width']==bw and t['height']==depth),**facts)
                # A fundo's width/length can be a bounding-box inventory value.
                # Compare height only when the row actually declares it.
                heights=[]
                for key in ('height_cm','declared_height_cm','depth_cm','height','depth'):
                    try:value=float(str(row[key]).replace(',','.'))
                    except (KeyError,TypeError,ValueError):continue
                    if math.isfinite(value) and value>0:heights.append((key,value))
                if heights:
                    section['declared_height_fields']=dict(heights)
                    if any(abs(value-depth)>epsilon for key,value in heights):
                        section['errors']['dimensoes']='altura declarada difere da seção numérica original vinculada'
                contacts.append(section)
            else:
                contacts.append(rec(f'seção corredor {index}/{branch}',guards=['dimensoes'],
                    reason='tira/variação de largura, seção ambígua ou paredes não comprovadas',**facts))
    # Every actual edge on the first/last local cap needs original evidence;
    # diagonal caps remain unknown instead of borrowing the rectangular gate.
    for end,x in [('início',xs[0]),('fim',xs[-1])]:
        edges=[(a,b) for a,b in zip(coords,coords[1:]) if min(a[0],b[0])-1e-8<=x<=max(a[0],b[0])+1e-8 and abs(a[0]-b[0])<=epsilon]
        results=[(*coverage(a,b),LineString([a,b]).length) for a,b in edges if LineString([a,b]).length>epsilon]
        uncovered=[max(0.,(1-c)*length) for c,h,length in results]
        full=bool(results) and all(missing<=epsilon for missing in uncovered)
        contacts.append(rec(f'extremo {end}',status='measured' if full else 'uncertain',guards=['apoios_limites'],
            coverage=[c for c,h,length in results],uncovered_cm=uncovered,
            wall_handles=sorted({h for c,hs,length in results for h in hs}),
            **({} if full else {'reason':'limite real sem fechamento original inequívoco; não inferir por bbox'})))
    # This helper does not establish the completeness of the SA's encounter
    # inventory. The rectangular branch's openings audit must not disappear
    # merely because a polygon has measurable local walls and labels.
    contacts.append(rec('inventário de encontros',guards=['inventario_segmentos'],
        reason='medição local não certifica inventário completo de encontros/aberturas do fundo'))
    return contacts
