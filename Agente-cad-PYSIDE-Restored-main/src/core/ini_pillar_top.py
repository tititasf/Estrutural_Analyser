"""Approved iNi pillar top geometry, from SA and native drawing symbols."""
from pathlib import Path
from types import SimpleNamespace
import math, functools
import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer
from ezdxf.math import Matrix44
from ezdxf.enums import TextEntityAlignment
from .pillar_nova_special import Drawing
from .pillar_nova_design import special_payload
from .n5_ini_frames import normalize_resources
@functools.lru_cache(maxsize=1)
def symbols():
    return ezdxf.readfile(Path(__file__).parent/'assets/ini_pillar_symbols.dxf')

def rectangular_top(pj, original, motor):
    d = ezdxf.new('R2018')
    m = d.modelspace()
    d.header['$INSUNITS'] = 5
    imp = Importer(original, d)
    for name in ('PT', 'MEIOPT', 'A$C51C4441F'):
        imp.import_block(name)
    imp.import_block('_Oblique')
    imp.finalize()
    for name in ('L', 'F', 'S7'):
        src = original.mline_styles.get(name)
        st = d.mline_styles.new('INI-' + name)
        for attr in ('flags', 'fill_color', 'start_angle', 'end_angle'):
            st.dxf.set(attr, src.dxf.get(attr))
        st.elements.elements.clear()
        for el in src.elements:
            st.elements.append(el.offset, el.color, el.linetype)
    for name, color in [('INI-CHAPA', 7), ('INI-SARRAFO', 24), ('INI-PERFIL', 7), ('INI-PERFIL-FUNDO', 30), ('INI-PARAFUSO', 1), ('INI-COTA', 4), ('INI-FACES', 1), ('INI-NOME', 7)]:
        d.layers.new(name, dxfattribs={'color': color})
    d.linetypes.new('INI-HIDDEN', dxfattribs={'description': 'Hidden bolt shaft', 'pattern': [1.5, 1, -0.5]})
    d.styles.new('INI-ROMANS', dxfattribs={'font': 'romans.shx'})
    d.dimstyles.new('INI-CIMA', dxfattribs={'dimtxt': 3, 'dimasz': 2 / 3, 'dimclrd': 4, 'dimclre': 4, 'dimclrt': 240, 'dimlfac': 1, 'dimdec': 1, 'dimdsep': 44, 'dimzin': 8, 'dimgap': 1, 'dimexe': 2 / 3, 'dimexo': 2 / 3, 'dimblk': '_Oblique', 'dimtxsty': 'INI-ROMANS'})
    c, w = (float(pj['comprimento']), float(pj['largura']))
    cl, cr = (-c / 2, c / 2)
    bot, top = (-w / 2, w / 2)
    left, right = (cl - 11, cr + 11)

    def ml(a, b, style, width, layer):
        e = m.add_mline([a, b], dxfattribs={'layer': layer, 'style_name': 'INI-' + style, 'scale_factor': width, 'justification': 1})
        e.set_style('INI-' + style)
        return e

    def rect(x, y, ww, hh, layer, color=256, fill=None):
        pts = [(x, y), (x + ww, y), (x + ww, y + hh), (x, y + hh)]
        if fill is not None:
            h = m.add_hatch(color=fill, dxfattribs={'layer': layer})
            h.paths.add_polyline_path(pts, is_closed=True)
        return m.add_lwpolyline(pts, close=True, dxfattribs={'layer': layer, 'color': color})

    def dim(a, b, base, angle=0):
        m.add_linear_dim(base=base, p1=a, p2=b, angle=angle, dimstyle='INI-CIMA', dxfattribs={'layer': 'INI-COTA'}).render()

    def text(value, xy, height, layer):
        e = m.add_text(value, dxfattribs={'height': height, 'layer': layer, 'style': 'INI-ROMANS'})
        e.set_placement(xy, align=TextEntityAlignment.MIDDLE_CENTER)

    def wood(x, y, ww=7, hh=7):
        name = 'PT' if abs(ww - hh) < 1e-05 else 'MEIOPT'
        pb = bbox.extents(list(original.blocks[name]))
        sx = ww / pb.size.x
        sy = hh / pb.size.y
        m.add_blockref(name, (x - pb.extmin.x * sx, y - pb.extmin.y * sy), dxfattribs={'xscale': sx, 'yscale': sy})
    for x in (cl-2.9,cr+2.9):
        for ya,yz in ([(bot,top)] if w>=40 else [(bot,bot+7),(top-7,top)]):
            ml((x,ya),(x,yz),'S7',2.2,'INI-SARRAFO')
    for y in (bot + 1.1, top - 1.1):
        ml((left, y), (cl - 4, y), 'S7', 2.2, 'INI-SARRAFO')
        ml((cr + 4, y), (right, y), 'S7', 2.2, 'INI-SARRAFO')
    ml((cl - 0.9, bot), (cl - 0.9, top), 'F', 1.8, 'INI-CHAPA')
    ml((cr + 0.9, bot), (cr + 0.9, top), 'F', 1.8, 'INI-CHAPA')
    ml((left, bot - 0.9), (right, bot - 0.9), 'L', 1.8, 'INI-CHAPA')
    ml((left, top + 0.9), (right, top + 0.9), 'L', 1.8, 'INI-CHAPA')
    if w >= 40:
        width=w-10
        centres=cd_post_centres(width)
        for x in (left,right-7):
            wood(x,bot+5)
            wood(x,top-12)
            for pos in centres[1:-1]:wood(x,bot+5+pos-1.75,7,3.5)
    contract = motor.cima_layout_contract(pj, c)
    for y, side in ((bot - 8.8, 'a'), (top + 1.8, 'b')):
        for start, width, parts in zip(contract['starts'], contract['widths'], contract['divisions_' + side]):
            x = left + start
            cap_l = 7 if abs(start) < 1e-05 else 3.5
            cap_r = 7 if abs(start + width - (c + 22)) < 1e-05 else 3.5
            wood(x, y, cap_l, 7)
            wood(x + width - cap_r, y, cap_r, 7)
            cursor = 0
            for part in parts[:-1]:
                cursor += part
                wood(x + cursor - 1.75, y, 3.5, 7)
    for y in (bot - 16.3, top + 8.8):
        rect(left - 14, y, c + 50, 7.5, 'INI-PERFIL', fill=30)
        for yy in (y + 1.5, y + 6):
            m.add_line((left - 14, yy), (right + 14, yy), dxfattribs={'layer': 'INI-PERFIL'})
    if w >= 40:
        for x in (left - 7.5, right):
            rect(x, bot - 22.5, 7.5, w + 45, 'INI-PERFIL', fill=30)
            for xx in (x + 1.5, x + 6):
                m.add_line((xx, bot - 22.5), (xx, top + 22.5), dxfattribs={'layer': 'INI-PERFIL'})
    offset = 3.5 if w >= 40 else 1.0
    stations = [left - offset]
    cursor = left - offset
    for i in range(1, 9):
        val = float(pj.get(f'par_{i}_{i + 1}') or 0)
        if val <= 0:
            break
        cursor += val
        if cursor >= right - 1e-05:
            break
        stations.append(cursor)
    stations.append(right + offset)

    def end(x, y, rotation):
        m.add_blockref('A$C51C4441F', (x, y), dxfattribs={'xscale': 0.5, 'yscale': 0.5, 'rotation': rotation, 'layer': 'INI-PARAFUSO'})
    for i, x in enumerate(stations):
        lo, hi = (bot - 16.3, top + 16.3)
        rect(x - 0.5, lo, 1, hi - lo + 18, 'INI-PARAFUSO')
        if 0 < i < len(stations) - 1:
            e = list(m)[-1]
            m.delete_entity(e)
            rect(x - 0.5, lo, 1, bot - lo, 'INI-PARAFUSO')
            e = rect(x - 0.5, bot, 1, w, 'INI-PARAFUSO')
            e.dxf.linetype = 'INI-HIDDEN'
            rect(x - 0.5, top, 1, hi + 18 - top, 'INI-PARAFUSO')
            for yy, direction in ((bot, 1), (top, -1)):
                m.add_lwpolyline([(x - 1.95, yy), (x + 1.95, yy), (x + 0.5, yy + direction * 1), (x - 0.5, yy + direction * 1)], close=True, dxfattribs={'layer': 'INI-PARAFUSO'})
        end(x, top + 16.3, 270)
        rect(x - 3.75, lo - 0.9, 7.5, 0.9, 'INI-PARAFUSO')
    if w >= 40:
        for y in (bot - 12.55, top + 12.55):
            e = rect(left - 7.5, y - 0.5, c + 40, 1, 'INI-PARAFUSO')
            e.dxf.linetype = 'INI-HIDDEN'
            end(right + 7.5, y, 180)
    for start, width, parts in zip(contract['starts'], contract['widths'], contract['divisions_a']):
        x = left + start
        for part in parts:
            dim((x, bot - 8.8), (x + part, bot - 8.8), (x, bot - 24))
            x += part
        dim((left + start, bot - 8.8), (left + start + width, bot - 8.8), (left + start, bot - 30))
    for i, gap in enumerate(contract['gaps']):
        x = left + contract['starts'][i] + contract['widths'][i]
        dim((x, bot - 8.8), (x + gap, bot - 8.8), (x, bot - 30))
    dim((left, bot - 8.8), (right, bot - 8.8), (left, bot - 36))
    inside = m.add_linear_dim(base=(cl, bot + 1), p1=(cl, bot), p2=(cr, bot), dimstyle='INI-CIMA', dxfattribs={'layer': 'INI-COTA'})
    inside.set_location((12, bot + 2.5), leader=False, relative=False)
    inside.render()
    dim((cr, bot), (cr, top), (right + 21, bot), 90)
    if w >= 40:
        dim((left, bot + 5), (left, top - 5), (left - 13, bot + 5), 90)
    chain = stations
    for a, b in zip(chain, chain[1:]):
        dim((a, top + 19), (b, top + 19), (a, top + 28))
    dim((left - 14, top + 16.3), (right + 14, top + 16.3), (left - 14, top + 37.2))
    for x, sgn in ((left, -1), (right, 1)):
        dim((x, top + 16.3), (x + sgn * offset, top + 16.3), (x, top + 22))
    for label, x, y in [('A', -5, bot + 5), ('B', -7, top - 6), ('C', cl + 9, bot + 7), ('D', cr - 9, top - 6)]:
        m.add_circle((x, y), 4.042076434, dxfattribs={'layer': 'INI-FACES'})
        text(label, (x, y), 5, 'INI-FACES')
        list(m)[-1].dxf.oblique = 5
    text(pj['nome'], (left - 41, 9.36), 5.667, 'INI-NOME')
    text(f'({w:g}x{c:g})', (left - 41, -2.14), 5.667, 'INI-NOME')
    for e in list(m):
        e.transform(Matrix44.scale(2))
    for e in m.query('DIMENSION'):
        o = e.override()
        o.update({'dimlfac': 0.5, 'dimtxt': 6, 'dimasz': 4 / 3, 'dimgap': 2})
        if e is inside.dimension:
            o.set_location((24, 2 * (bot + 2.5)), leader=False, relative=False)
        o.render()
    from src.core.lv_formascia_design import normalize_resources
    normalize_resources(d)
    return d

class SpecialTop(Drawing):

    def __init__(self, payload):
        super().__init__(payload)
        self.doc.styles.new('INI-ROMANS', dxfattribs={'font': 'romans.shx'})
        imp = Importer(symbols(), self.doc)
        for name in ('PT', 'MEIOPT', '_Oblique'):
            imp.import_block(name)
        imp.finalize()
        self.doc.dimstyles.new('INI-L-CIMA', dxfattribs={'dimtxt': 3, 'dimasz': 2 / 3, 'dimclrd': 4, 'dimclre': 4, 'dimclrt': 240, 'dimlfac': 1, 'dimdec': 1, 'dimdsep': 44, 'dimzin': 8, 'dimgap': 1, 'dimexe': 2 / 3, 'dimexo': 2 / 3, 'dimblk': '_Oblique', 'dimtxsty': 'INI-ROMANS'})

    def bolts(self):
        before = {e.dxf.handle for e in self.ms}
        # Older deployed Nova has the opposite asset orientation. Keep the
        # iNi correction local rather than changing geometry in another mode.
        from . import pillar_nova_special as base
        originals = self.bolt_head
        if not hasattr(base, 'bolt_head_angles'):
            self.bolt_head = [e.copy() for e in originals]
            for entity in self.bolt_head: entity.transform(Matrix44.z_rotate(math.pi))
        try:
            super().bolts()
        finally:
            self.bolt_head = originals
        from shapely.geometry import LineString
        from shapely.ops import unary_union
        metal = unary_union([p for (layer, i), p in self.parts.items() if layer == 'Perfil Metalico' and (self.profile_faces is None or i in self.profile_faces)])
        entities = [e for e in self.ms if e.dxf.handle not in before and e.dxf.layer == 'Parafuso']
        n = len(self.bolt_head)
        assert len(entities) == len(self.rod_axes) * (1 + 2 * n)
        self.head_contacts = []
        for k in range(len(self.rod_axes)):
            group = entities[k * (1 + 2 * n):(k + 1) * (1 + 2 * n)]
            shaft = group[0]
            start = shaft.dxf.start
            end = shaft.dxf.end
            unit = (end - start).normalize()
            axis = 0 if abs(unit.x) > 0.5 else 1
            sign = 1 if unit[axis] > 0 else -1
            guide = LineString([(start.x - unit.x * 1000, start.y - unit.y * 1000), (end.x + unit.x * 1000, end.y + unit.y * 1000)])
            hit = guide.intersection(metal)
            segments = [hit] if hit.geom_type == 'LineString' else list(getattr(hit, 'geoms', []))
            coords = [c for seg in segments if seg.geom_type == 'LineString' for c in seg.coords]
            assert coords, 'Bolt must meet an actual metal profile'
            outer_min = min((c[axis] * sign for c in coords))
            outer_max = max((c[axis] * sign for c in coords))
            for side, heads, target in [('end', group[1:1 + n], outer_max), ('start', group[1 + n:], outer_min)]:
                b = bbox.extents(heads)
                values = [b.extmin[axis] * sign, b.extmax[axis] * sign]
                near = min(values) if side == 'end' else max(values)
                delta = (target - near) * sign
                for e in heads:
                    e.translate(delta if axis == 0 else 0, delta if axis == 1 else 0, 0)
                b = bbox.extents(heads)
                values = [b.extmin[axis] * sign, b.extmax[axis] * sign]
                contact = min(values) if side == 'end' else max(values)
                assert abs(contact - target) < 1e-07
                self.head_contacts.append({'bolt': k + 1, 'end': side, 'gap_cm': contact - target, 'shift_cm': delta, 'metal_boundary_cm': target * sign})
                if side == 'end':
                    shaft.dxf.end = end + unit * (delta * sign)
                else:
                    shaft.dxf.start = start + unit * (delta * sign)

    def dimension(self, f, a, b, t, label, height=4.2, anchor_t=21):
        if 'PAINEL' in label:
            return
        t = {28: 28, 39: 42, 50: 74, 32: 32}.get(t, t)
        if f['inner_end'] and abs(f['u'][0]) > 0.5 and ('GRADE' in label or t == 42):
            t = 36
        angle = 90 if abs(f['u'][1]) > 0.5 else 0
        text = label.replace('(GRADE)', '-GRADE').replace(' PAINEL', '-PAINEL').replace('.', ',')
        self.ms.add_linear_dim(base=self.point(f, (a + b) / 2, t), p1=self.point(f, a, anchor_t), p2=self.point(f, b, anchor_t), angle=angle, text=text, dimstyle='INI-L-CIMA', dxfattribs={'layer': 'COTA'}).render()
        if not hasattr(self, 'dimension_records'):
            self.dimension_records = []
        self.dimension_records.append({'face': f['name'], 'a': a, 'b': b, 't': t, 'label': text})

    def bolt_dimensions(self):
        super().bolt_dimensions()
        for f in self.faces:
            if f['length'] < 45:
                continue
            grade = sorted((r for r in self.dimension_records if r['face'] == f['name'] and 'GRADE' in r['label']), key=lambda r: r['a'])
            for left, right in zip(grade, grade[1:]):
                if right['a'] > left['b']:
                    self.dimension(f, left['b'], right['a'], 42, f'{right['a'] - left['b']:g}')
            p = self.parts['CHAPA', f['index']]
            spans = [self.axis_span(f, p, t) for t in (0.001, 0.9, 1.799)]
            if all(spans):
                lo = min((v[0] for v in spans))
                hi = max((v[1] for v in spans))
                angle = 90 if abs(f['u'][1]) > 0.5 else 0
                self.ms.add_linear_dim(base=self.point(f, (lo + hi) / 2, 58), p1=self.point(f, lo, 1.8), p2=self.point(f, hi, 1.8), angle=angle, text=f'{hi - lo:g}-PAINEL'.replace('.', ','), dimstyle='INI-L-CIMA', dxfattribs={'layer': 'COTA'}).render()
            p = self.parts['Perfil Metalico', f['index']]
            spans = [self.axis_span(f, p, t) for t in (11.001, 16, 20.999)]
            if all(spans):
                lo = min((v[0] for v in spans))
                hi = max((v[1] for v in spans))
                self.dimension(f, lo, hi, 92, f'{hi - lo:g}')

    def wood(self, f, a, b, t0=4, t1=11, texture=False):
        if not texture:
            return self.shape(f, a, b, t0, t1)
        p = self.shape(f, a, b, t0, t1)
        self.cells.append(p)
        name = 'PT' if b - a >= 6 else 'MEIOPT'
        pb = bbox.extents(symbols().blocks[name])
        mat = Matrix44.chain(Matrix44.translate(-pb.extmin.x, -pb.extmin.y, 0), Matrix44.scale((b - a) / pb.size.x, -(t1 - t0) / pb.size.y, 1), Matrix44.z_rotate(math.atan2(f['u'][1], f['u'][0])), Matrix44.translate(*self.point(f, a, t0), 0))
        actual = []
        for e in symbols().blocks[name]:
            e = e.copy()
            e.transform(mat)
            self.ms.add_entity(e)
            actual.append(e)
        bb = bbox.extents(actual)
        assert abs(bb.extmin.x - p.bounds[0]) < 1e-05 and abs(bb.extmin.y - p.bounds[1]) < 1e-05
        assert abs(bb.extmax.x - p.bounds[2]) < 1e-05 and abs(bb.extmax.y - p.bounds[3]) < 1e-05
        return p

def cd_post_centres(width):
    return [3.5]+([width*i/max(2,math.ceil(width/30)) for i in range(1,max(2,math.ceil(width/30)))] if width>30 else [])+[width-3.5]

def special_top(pj):
    v=SpecialTop(special_payload(pj));d=v.generate();m=d.modelspace()
    from .pillar_u_nova_contract import u_nova_payload
    is_u = u_nova_payload(pj) is not None
    face_map = ({name: name for name in 'ABCDEFGH'} if is_u else
                {'E':'A','F':'B','A':'E','B':'F','C':'D','D':'C'})
    for e in m:
     layer=e.dxf.layer
     if layer=='CHAPA':
      if e.dxftype()=='HATCH':
       # Match native F/L sheet fills according to principal orientation.
       path=e.paths.paths[0];bb=ezdxf.math.BoundingBox([(x,y,0) for x,y,*_ in path.vertices]);e.set_solid_fill(color=241 if bb.size.x>bb.size.y else 13)
      else:e.dxf.color=7
     elif layer=='SARRAFO':
      if e.dxftype()=='HATCH':e.set_solid_fill(color=17)
      else:e.dxf.color=24
     elif layer=='Perfil Metalico':e.dxf.color=7
     elif layer=='Parafuso':e.dxf.color=1
     elif layer=='NOMENCLATURA' and e.dxftype()=='TEXT':
      if e.dxf.text.startswith('G') and e.dxf.text not in face_map:m.delete_entity(e);continue
      e.dxf.style='INI-ROMANS';e.dxf.color=1;e.dxf.height=5
      if e.dxf.text in face_map:
       # Elevation identities use the opposite arm convention.
       e.dxf.text=face_map[e.dxf.text]
       # Center short end-face identities inside the concrete; enlarge labels
       # to match their prominence relative to dimension text in the reference.
       face=next(f for f in v.faces if face_map[f['name']]==e.dxf.text)
       fraction=.5 if is_u else {'A':.75,'B':.52,'C':.5,'D':.5,'E':.4,'F':.4}[e.dxf.text]
       xy=v.point(face,face['length']*fraction,-min(f['length'] for f in v.faces)/2)
       e.set_placement((xy[0]*2,xy[1]*2),align=TextEntityAlignment.MIDDLE_CENTER)
       e.dxf.height=8
       m.add_circle(e.dxf.align_point,6.5,dxfattribs={'color':1,'layer':'INI-FACES'})
      else:e.dxf.color=240;e.dxf.height=3
    # Fill actual profile polygons; keep white inner channel edges above fill.
    for e in list(m.query('LWPOLYLINE')):
     if e.dxf.layer!='Perfil Metalico' or not e.closed:continue
     h=m.add_hatch(color=30,dxfattribs={'layer':'INI-PERFIL-FUNDO'})
     h.paths.add_polyline_path(e.get_points('xy'),is_closed=True)
    # Ensure orange fill behind profile linework.
    from ezdxf import reorder
    handles=[e.dxf.handle for e in m if e.dxf.layer=='INI-PERFIL-FUNDO']+[e.dxf.handle for e in m if e.dxf.layer!='INI-PERFIL-FUNDO']
    m.set_redraw_order({h:str(i+1) for i,h in enumerate(handles)})
    # Remove redundant free numerical labels inside the concrete; retain faces.
    for e in list(m.query('TEXT')):
     if e.dxf.layer=='COTA':m.delete_entity(e)
    b=bbox.extents(m)
    for label,y in [(str(pj.get('nome','?')),b.center.y+10),('(VAR.)',b.center.y-10)]:
     e=m.add_text(label,dxfattribs={'height':8,'color':7,'style':'INI-ROMANS'})
     e.set_placement((b.extmin.x-35,y),align=TextEntityAlignment.MIDDLE_CENTER)
    # Drawing.generate already applies the CIMA scale 2x.
    for e in m.query('DIMENSION'):
     # Dimension text already carries physical centimetres and semantic suffix.
     o=e.override();o.update({'dimlfac':.5,'dimtxt':6,'dimasz':4/3,'dimgap':2});o.render()
    normalize_resources(d)
    return d

def top(pj, namespace):
    return special_top(pj) if special_payload(pj) else rectangular_top(pj,symbols(),SimpleNamespace(**namespace))

def hole_stations(pj, namespace):
    if special_payload(pj):
        from scripts.pl_panel_drilling import top_stations
        return top_stations(namespace,pj,'NOVA')
    from ezdxf import bbox
    doc=top(pj,namespace);width=float(pj['comprimento'])+22
    axes=sorted({round(b.center.x/2+width/2,6) for e in doc.modelspace().query('LWPOLYLINE') if e.dxf.layer=='INI-PARAFUSO' and e.closed and (b:=bbox.extents([e])).size.y>2 and abs(b.size.x-2)<1e-6})
    return {'A':[x for x in axes if 0<x<width],'B':sorted(width-x for x in axes if 0<x<width)}
