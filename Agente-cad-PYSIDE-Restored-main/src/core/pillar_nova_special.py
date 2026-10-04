"""Contour driven Nova special top, from the approved design rules."""
from pathlib import Path
import sys,math,json,itertools
import ezdxf
from ezdxf import bbox
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Matrix44
from shapely.geometry import Polygon,LineString,box
from shapely.ops import unary_union
ROOT=Path(__file__).parent
from src.core.pillar_special_faces import physical_ring

def add(a,b):return (a[0]+b[0],a[1]+b[1])
def mul(a,k):return (a[0]*k,a[1]*k)
def dot(a,b):return a[0]*b[0]+a[1]*b[1]
def polygons(g):return [g] if g.geom_type=='Polygon' else [p for p in getattr(g,'geoms',[]) if p.geom_type=='Polygon']

class Drawing:
    def __init__(self,payload):
        self.ring=physical_ring(payload['geometry_points'])
        self.concrete=Polygon(self.ring)
        assert self.concrete.is_valid and self.concrete.area>0
        if not self.concrete.exterior.is_ccw:self.ring.reverse();self.concrete=Polygon(self.ring)
        self.doc=ezdxf.new('R2018');self.ms=self.doc.modelspace();self.annotations=[]
        for name,color in [('CHAPA',1),('SARRAFO',1),('Madeira',126),('Madeira_textura',126),('Perfil Metalico',224),('Parafuso',8),('COTA',241),('NOMENCLATURA',7)]:self.doc.layers.new(name,dxfattribs={'color':color})
        self.doc.styles.new('COTA_BOLD',dxfattribs={'font':'arialbd.ttf'})
        self.faces=[]
        self.profile_faces=payload.get('metal_profile_faces')
        self.end_cap_faces=set(payload.get('panel_end_cap_faces',[]))
        self.extended_grade_caps=set(payload.get('extended_grade_caps',[]))
        self.inner_bolt_clearance=float(payload.get('inner_bolt_clearance_cm',20))
        self.grade_end_offsets=payload.get('grade_end_offsets',{})
        for i,p in enumerate(self.ring):
            q=self.ring[(i+1)%len(self.ring)];delta=(q[0]-p[0],q[1]-p[1]);L=math.hypot(*delta)
            assert min(abs(delta[0]),abs(delta[1]))<1e-6,'Only orthogonal contours in this prototype'
            u=mul(delta,1/L);n=(u[1],-u[0])
            previous=self.ring[i-1];following=self.ring[(i+2)%len(self.ring)]
            v0=(p[0]-previous[0],p[1]-previous[1]);v1=(following[0]-q[0],following[1]-q[1])
            start_inner=v0[0]*u[1]-v0[1]*u[0]<0;end_inner=u[0]*v1[1]-u[1]*v1[0]<0
            self.faces.append({'index':i,'name':payload.get('face_names',{}).get(str(i),chr(65+i)),'p':p,'u':u,'n':n,'length':L,'inner_start':start_inner,'inner_end':end_inner})
        self.parts={};self.rods=[];self.rod_axes=[];self.bolt_groups={};self.cells=[];self.grade_shapes=[];self.report=[]
        ref=ezdxf.readfile(ROOT/'assets/nova_pillar_details.dxf')
        self.templates={name:[e.copy() for e in ref.blocks.get(name)] for name in ('PONTALETE','MEIO PONTALETE')}
        self.bolt_head=[e.copy() for e in ref.blocks.get('SPECIAL_HEAD')]

    def point(self,f,s,t):return add(f['p'],add(mul(f['u'],s),mul(f['n'],t)))
    def shape(self,f,lo,hi,t0,t1):return Polygon([self.point(f,lo,t0),self.point(f,hi,t0),self.point(f,hi,t1),self.point(f,lo,t1)])
    def drawpoly(self,p,layer):
        for g in polygons(p):
            if g.area>1e-7:self.ms.add_lwpolyline(list(g.exterior.coords)[:-1],close=True,dxfattribs={'layer':layer})
    def panel_hatch(self,p,layer):
        # Approved L: solid sheet and ANSI31 timber, ACI 8. Work in cm;
        # the final x2 transform restores the measured reference spacing.
        for g in polygons(p):
            if g.area<=1e-7:continue
            h=self.ms.add_hatch(color=8,dxfattribs={'layer':layer})
            if layer=='SARRAFO':
                h.set_pattern_fill('ANSI31',color=8,definition=[
                    (45,(0,0),(-.2806330038,.2806330038),[])])
            h.paths.add_polyline_path(list(g.exterior.coords)[:-1],is_closed=True,flags=1)
            for hole in g.interiors:
                h.paths.add_polyline_path(list(hole.coords)[:-1],is_closed=True,flags=0)
    def text(self,label,xy,height=4.2,rotation=0,dim=False):
        e=self.ms.add_text(label,dxfattribs={'layer':'COTA' if dim else 'NOMENCLATURA','height':height,'rotation':rotation,'style':'COTA_BOLD' if dim else 'Standard'})
        e.set_placement(xy,align=TextEntityAlignment.MIDDLE_CENTER)
        if dim:e.rgb=(255,235,242)
        self.annotations.append(e);return e
    def band(self,t0,t1,layer):
        inner=self.concrete.buffer(t0,join_style=2);outer=self.concrete.buffer(t1,join_style=2)
        assert outer.geom_type=='Polygon' and not outer.interiors,'Offset changes topology'
        band=outer.difference(inner)
        pieces=[self.shape(f,-t1,f['length']+t1,t0,t1).intersection(band) for f in self.faces]
        # Butt joints: horizontal owns convex corners, vertical owns reentrant ones.
        for i,f in enumerate(self.faces):
            j=(i+1)%len(self.faces);g=self.faces[j];hit=pieces[i].intersection(pieces[j])
            if hit.area<1e-7:continue
            horizontal_i=abs(f['u'][0])>.5
            winner=i if horizontal_i != f['inner_end'] else j
            loser=j if winner==i else i;pieces[loser]=pieces[loser].difference(hit)
        # Free-end assembly: long sheets/sarrafo extend 11 cm past the cap;
        # the cap has two 7 cm supports and two perpendicular 7 cm returns.
        for i,f in enumerate(self.faces):
            if i in self.end_cap_faces:
                if layer=='GRADE_SPACE' or (layer=='Perfil Metalico' and self.profile_faces is not None and i not in self.profile_faces):
                    pieces[i]=Polygon()
                if layer=='CHAPA':pieces[i]=self.shape(f,0,f['length'],0,1.8)
                if layer=='SARRAFO':
                    L=f['length']
                    pieces[i]=unary_union([self.shape(f,0,7,1.8,4),self.shape(f,L-7,L,1.8,4),self.shape(f,0,2.2,4,11),self.shape(f,L-2.2,L,4,11)])
                continue
            spans=[self.axis_span(f,pieces[i],t) for t in (t0+.001,(t0+t1)/2,t1-.001)]
            if not all(spans):continue
            lo=max(v[0] for v in spans);hi=min(v[1] for v in spans)
            start=(i-1)%len(self.faces);end=(i+1)%len(self.faces)
            if layer in ('CHAPA','SARRAFO'):
                if start in self.end_cap_faces:lo=-11
                if end in self.end_cap_faces:hi=f['length']+11
            elif layer=='GRADE_SPACE':
                if start in self.extended_grade_caps:lo=-11
                if end in self.extended_grade_caps:hi=f['length']+11
            elif layer=='Perfil Metalico':
                if start in self.extended_grade_caps:lo=-18
                if end in self.extended_grade_caps:hi=f['length']+18
            else:continue
            if start in self.end_cap_faces or end in self.end_cap_faces:
                pieces[i]=self.shape(f,lo,hi,t0,t1)
            if layer=='GRADE_SPACE' and f['name'] in self.grade_end_offsets:
                first,last=self.grade_end_offsets[f['name']]
                pieces[i]=self.shape(f,first,f['length']+last,t0,t1)
        for i,p in enumerate(pieces):
            self.parts[layer,i]=p
            if layer!='Perfil Metalico' or self.profile_faces is None or i in self.profile_faces:
                if layer in ('CHAPA','SARRAFO'):self.panel_hatch(p,layer)
                self.drawpoly(p,layer)
                if layer=='Perfil Metalico':
                    # Approved L: inner rectangle is inset 1.8 cm across the
                    # profile, retaining the same longitudinal end positions.
                    f=self.faces[i]
                    hollow=p.intersection(self.shape(f,-t1,f['length']+t1,t0+1.8,t1-1.8))
                    assert hollow.area>0 and p.covers(hollow)
                    self.drawpoly(hollow,layer)
        assert sum(p.area for p in pieces)-unary_union(pieces).area<1e-6
        return pieces
    def axis_span(self,f,p,t):
        l=LineString([self.point(f,-1000,t),self.point(f,f['length']+1000,t)]).intersection(p)
        pts=[]
        for g in [l] if l.geom_type=='LineString' else getattr(l,'geoms',[]):
            if g.geom_type=='LineString':pts.extend(dot((x-f['p'][0],y-f['p'][1]),f['u']) for x,y in g.coords)
        return (min(pts),max(pts)) if pts else None
    def dimension(self,f,a,b,t,label,height=4.2,anchor_t=21):
        self.ms.add_line(self.point(f,a,t),self.point(f,b,t),dxfattribs={'layer':'COTA'})
        for s in (a,b):self.ms.add_line(self.point(f,s,anchor_t),self.point(f,s,t+1),dxfattribs={'layer':'COTA'})
        rot=90 if abs(f['u'][1])>.5 else 0
        e=self.text(label,self.point(f,(a+b)/2,t+5),height,rot,True)
        bb=bbox.extents([e]);axis='x' if rot else 'y';direction=f['n'][0] if rot else f['n'][1]
        target=self.point(f,(a+b)/2,t)[0 if rot else 1]+direction*2.5
        edge=getattr(bb.extmin if direction>0 else bb.extmax,axis)
        e.translate(target-edge if rot else 0,0 if rot else target-edge,0)

    def bolts(self):
        # A station shared with the facing wall produces one transverse rod.
        handled={}
        for f in sorted(self.faces,key=lambda f:-f['length']):
            if f['length']<45:continue
            spans=[self.axis_span(f,self.parts['GRADE_SPACE',f['index']],t) for t in (4.001,7.5,10.999)]
            lo=max(v[0] for v in spans if v);hi=min(v[1] for v in spans if v)
            start_join=f['inner_start'] or self.faces[(f['index']-1)%len(self.faces)]['length']>=45
            end_join=f['inner_end'] or self.faces[(f['index']+1)%len(self.faces)]['length']>=45
            a=self.inner_bolt_clearance if start_join else lo-1.5;b=f['length']-self.inner_bolt_clearance if end_join else hi+1.5
            width=min(face['length'] for face in self.faces)
            inner_stations=[]
            for corner in self.faces:
                delta=(corner['p'][0]-f['p'][0],corner['p'][1]-f['p'][1])
                if corner['inner_start'] and abs(dot(delta,f['n']))<=width+1e-7:
                    position=dot(delta,f['u']);inner_stations.append(position)
                    if 0<=position<=width:a=max(a,position+self.inner_bolt_clearance)
                    if f['length']-width<=position<=f['length']:b=min(b,position-self.inner_bolt_clearance)
            if b<=a:raise ValueError('Insufficient space for internal corner bolt clearance')
            count=max(1,math.ceil((b-a)/50));step=math.floor((b-a)/count)
            stations=([a+round((b-a)*k/count) for k in range(count+1)] if not start_join and not end_join and abs(b-a-round(b-a))<1e-6 else ([b-step*k for k in range(count+1)] if not end_join else [a+step*k for k in range(count+1)]))
            for s in stations:
                if any(abs(s-v)<self.inner_bolt_clearance-1e-7 for v in inner_stations):continue
                sample=min(max(s,.001),f['length']-.001)
                start=self.point(f,s,0);probe=self.point(f,sample,0)
                cut=LineString([add(probe,mul(f['n'],-1000)),add(probe,mul(f['n'],1000))]).intersection(self.concrete)
                segments=[cut] if cut.geom_type=='LineString' else [p for p in getattr(cut,'geoms',[]) if p.geom_type=='LineString']
                if not segments:continue
                material=min(segments,key=lambda p:p.distance(LineString([probe,probe])))
                coords=list(material.coords);ts=sorted(dot((x-probe[0],y-probe[1]),f['n']) for x,y in coords)
                short_width=min(face['length'] for face in self.faces)
                if ts[-1]-ts[0]>short_width*1.5:continue
                key=(round(abs(f['n'][0])),round(min(start[0]+ts[0]*f['n'][0],start[0]+ts[-1]*f['n'][0]),3),round(min(start[1]+ts[0]*f['n'][1],start[1]+ts[-1]*f['n'][1]),3),round(max(start[0]+ts[0]*f['n'][0],start[0]+ts[-1]*f['n'][0]),3),round(max(start[1]+ts[0]*f['n'][1],start[1]+ts[-1]*f['n'][1]),3))
                fixed=[end for end in (add(start,mul(f['n'],ts[0])),add(start,mul(f['n'],ts[-1])))];coordinate=0 if abs(f['n'][0])>.5 else 1
                pair=(coordinate,*sorted(round(end[coordinate],3) for end in fixed))
                axial=dot(start,f['u'])
                # Avoid a second nearly coincident station contributed by the opposite face.
                axial=start[1-coordinate]
                if pair in handled and handled[pair][0]!=f['index']:continue
                if pair not in handled:handled[pair]=[f['index']]
                if any(abs(axial-old)<1e-6 for old in handled[pair][1:]):continue
                handled.setdefault(pair,[]).append(axial)
                end0=add(start,mul(f['n'],ts[0]-23));end1=add(start,mul(f['n'],ts[-1]+23))
                terminal_cells=[]
                for other in self.faces:
                    if other['length']<45:continue
                    ranges=[self.axis_span(other,self.parts['GRADE_SPACE',other['index']],t) for t in (4.001,7.5,10.999)]
                    if not all(ranges):continue
                    left=max(v[0] for v in ranges);right=min(v[1] for v in ranges)
                    terminal_cells.extend([self.shape(other,left,left+7,4,11),self.shape(other,right-7,right,4,11)])
                original_ends=(end0,end1)
                for shift in [0,*itertools.chain.from_iterable((k,-k) for k in range(1,16))]:
                    shifted_s=s+shift
                    if any(abs(shifted_s-v)<self.inner_bolt_clearance-1e-7 for v in inner_stations):continue
                    if start_join and shifted_s<self.inner_bolt_clearance-1e-7:continue
                    if end_join and shifted_s>f['length']-self.inner_bolt_clearance+1e-7:continue
                    trial0=add(original_ends[0],mul(f['u'],shift));trial1=add(original_ends[1],mul(f['u'],shift))
                    rod=LineString([trial0,trial1]).buffer(.5,cap_style=2)
                    if all(rod.distance(c)>=1-1e-7 for c in terminal_cells):
                        end0,end1=trial0,trial1;break
                else:raise ValueError('No corner-safe bolt station')
                self.ms.add_line(end0,end1,dxfattribs={'layer':'Parafuso'})
                self.rod_axes.append(LineString([end0,end1]))
                self.rods.append(LineString([end0,end1]).buffer(.5,cap_style=2))
                junctions=sorted(set(other['p'][1-coordinate] for other in self.faces if other['inner_start']))
                zone=sum(value<end0[1-coordinate] for value in junctions)
                self.bolt_groups.setdefault((*pair,zone),[]).append(end0[1-coordinate])
                for end,angle in [(end1,math.atan2(f['n'][1],f['n'][0])),(end0,math.atan2(-f['n'][1],-f['n'][0]))]:
                    for original in self.bolt_head:
                        e=original.copy();e.transform(Matrix44.z_rotate(angle));e.translate(*end,0);e.dxf.layer='Parafuso';self.ms.add_entity(e)

    def wood(self,f,a,b,t0=4,t1=11,texture=False):
        p=self.shape(f,a,b,t0,t1);self.drawpoly(p,'Madeira')
        if texture:
            self.cells.append(p)
            parts=[e.copy() for e in self.templates['PONTALETE' if b-a>=6 else 'MEIO PONTALETE']]
            pb=bbox.extents(parts);scale=min((b-a)/pb.size.x,(t1-t0)/pb.size.y)
            mat=Matrix44.chain(Matrix44.translate(-pb.center.x,-pb.center.y,0),Matrix44.scale(scale),Matrix44.z_rotate(math.atan2(f['u'][1],f['u'][0])),Matrix44.translate(*self.point(f,(a+b)/2,(t0+t1)/2),0))
            for e in parts:e.transform(mat);e.dxf.layer='Madeira_textura';self.ms.add_entity(e)
        return p
    def grades(self):
        panel=unary_union([p for (name,_),p in self.parts.items() if name in ('CHAPA','SARRAFO')])
        for f in self.faces:
            if f['length']<45:continue
            p=self.parts['GRADE_SPACE',f['index']]
            spans=[self.axis_span(f,p,t) for t in (4.001,7.5,10.999)]
            if not all(spans):continue
            lo=max(s[0] for s in spans);hi=min(s[1] for s in spans)
            safe=lambda a,b:not any(self.shape(f,a,b,4,11).distance(r)<1-1e-7 for r in self.rods)
            candidates=[]
            if hi-lo<45:continue
            # Search sizes and gaps before moving individual internal cells.
            for g1 in range(10,int(hi-lo),5):
                for g2 in (g1-5,g1,g1+5):
                    gap=hi-lo-g1-g2
                    if g2<10 or gap<3:continue
                    a=lo+g1;b=hi-g2
                    if all(safe(x,y) for x,y in [(lo,lo+7),(a-3.5,a),(b,b+3.5),(hi-7,hi)]):candidates.append(((g1-g2)**2+gap**2,g1,g2))
            if not candidates:raise ValueError(f'No feasible grade partition for face {f["name"]}: span {lo,hi}; end clearances {safe(lo,lo+7),safe(hi-7,hi)}')
            _,g1,g2=min(candidates);rows=[(lo,lo+g1,7,3.5),(hi-g2,hi,3.5,7)]
            for a,b,lw,rw in rows:
                self.grade_shapes.append(self.wood(f,a,b))
                assert self.shape(f,a,b,4,11).intersection(panel).area<1e-6, f'Grade crosses panel on face {f["name"]}'
                count=max(0,round((b-a)/30)-1)
                possible=[a+k for k in range(1,int(b-a)) if a+lw+1<a+k-1.75 and a+k+1.75<b-rw-1 and safe(a+k-1.75,a+k+1.75)]
                states={a:(0,[])};ideal=(b-a)/(count+1)
                for _ in range(count):
                    states={c:min([(score+(c-last-ideal)**2,path+[c]) for last,(score,path) in states.items() if c-last>4.5],default=(math.inf,[])) for c in possible}
                _,centers=min([(score+(b-last-ideal)**2,path) for last,(score,path) in states.items()],default=(math.inf,[]))
                if len(centers)!=count:raise ValueError('Wood spacing constraints infeasible')
                intervals=[(a,a+lw),(b-rw,b)]+[(c-1.75,c+1.75) for c in centers]
                for x,y in intervals:assert safe(x,y);self.wood(f,x,y,texture=True)
                # Choose empty label region by measured collision-free text bounds.
                rot=90 if abs(f['u'][1])>.5 else 0
                e=self.text(f'G{b-a:g}',self.point(f,(a+b)/2,7.5),4.5,rot)
                found=False
                for s in sorted([a+k*.5 for k in range(int((b-a)*2))],key=lambda s:abs(s-(a+b)/2)):
                    bb=bbox.extents([e]);center=self.point(f,s,7.5);e.translate(center[0]-bb.center.x,center[1]-bb.center.y,0)
                    bb=bbox.extents([e]);shape=box(bb.extmin.x,bb.extmin.y,bb.extmax.x,bb.extmax.y)
                    if p.covers(shape) and all(shape.distance(c)>.25 for c in self.cells) and all(not shape.intersects(r) for r in self.rods):found=True;break
                assert found,f'No free grade label on {f["name"]}'
                chain=[a,*centers,b]
                for x,y in zip(chain,chain[1:]):self.dimension(f,x,y,28,f'{y-x:g}')
                self.dimension(f,a,b,39,f'{b-a:g}(GRADE)')
                self.report.append({'face':f['name'],'grade_cm':b-a,'gap_cm':hi-lo-g1-g2,'integer_cell_intervals':all(abs(y-x-round(y-x))<1e-6 for x,y in zip(chain,chain[1:]))})
            self.dimension(f,lo,hi,61,f'{hi-lo:g} PAINEL')

    def bolt_dimensions(self):
        # Dimension actual transverse rods, including those supplied by the
        # opposite face. Chain lies between grade total (39) and panel (61).
        for f in self.faces:
            if f['length']<45:continue
            p=self.parts['GRADE_SPACE',f['index']]
            spans=[self.axis_span(f,p,t) for t in (4.001,7.5,10.999)]
            if not all(spans):continue
            lo=max(v[0] for v in spans);hi=min(v[1] for v in spans)
            stations=[]
            guide=LineString([self.point(f,lo-2,7.5),self.point(f,hi+2,7.5)])
            for rod in self.rod_axes:
                hit=rod.intersection(guide)
                if hit.geom_type=='Point':
                    stations.append(dot((hit.x-f['p'][0],hit.y-f['p'][1]),f['u']))
            stations=sorted(set(round(s,6) for s in stations))
            if not stations:continue
            chain=list(stations)
            # Omit tiny outward bolt offsets; keep meaningful end remainder.
            if stations[0]-lo>3:chain.insert(0,lo)
            if hi-stations[-1]>3:chain.append(hi)
            for a,b in zip(chain,chain[1:]):
                self.dimension(f,a,b,50,f'{b-a:g}',4.2)

    def generate(self):
        for t0,t1,layer in [(0,1.8,'CHAPA'),(1.8,4,'SARRAFO'),(4,11,'GRADE_SPACE'),(11,21,'Perfil Metalico')]:
            if layer=='GRADE_SPACE':self.doc.layers.new(layer,dxfattribs={'color':126})
            self.band(t0,t1,layer)
        # The grade-space polygons are construction constraints, not duplicated outlines.
        for e in list(self.ms):
            if e.dxf.layer=='GRADE_SPACE':self.ms.delete_entity(e)
        self.bolts();self.grades();self.bolt_dimensions()
        for f in self.faces:
            rot=90 if abs(f['u'][1])>.5 else 0
            self.text(f['name'],self.point(f,f['length']*.43,-2.5),2.5)
            self.text(f'{f["length"]:g}',self.point(f,f['length']*.62,-3.5),3.5,rot,True)
            if f['length']<45:
                # Free tips: stop at the first outer timber return, without
                # crossing the support to reach the sheet underneath.
                self.dimension(f,0,f['length'],32,f'{f["length"]:g}',3.5,
                               anchor_t=11 if f['index'] in self.end_cap_faces else 21)
        # Preserve normal offset while sliding along the dimension axis.
        placed=[]
        for e in sorted(self.annotations,key=lambda e:e.dxf.layer=='COTA'):
            original=e.copy();bb=bbox.extents([e]);is_vertical=abs(e.dxf.rotation-90)<1
            if e.dxf.layer=='COTA':
                for delta in [0,*itertools.chain.from_iterable((k,-k) for k in range(1,81))]:
                    e.dxf.insert=original.dxf.insert;e.dxf.align_point=original.dxf.align_point
                    e.translate(0 if is_vertical else delta,delta if is_vertical else 0,0)
                    bb=bbox.extents([e]);rect=box(bb.extmin.x,bb.extmin.y,bb.extmax.x,bb.extmax.y).buffer(.6)
                    if all(not rect.intersects(other) for other in placed):break
                else:raise ValueError('Cannot place dimension text without overlap')
            bb=bbox.extents([e]);placed.append(box(bb.extmin.x,bb.extmin.y,bb.extmax.x,bb.extmax.y).buffer(.6))
        # L contract uses two drawing units per centimetre.
        for e in self.ms:e.transform(Matrix44.scale(2))
        self.ms.set_redraw_order({e.dxf.handle:format(i+1,'X') for i,e in enumerate([e for e in self.ms if e not in self.annotations]+self.annotations)})
        assert not self.doc.audit().errors
        return self.doc
