"""iNi lateral presentation measured from the registered native DXFs."""
from pathlib import Path
import ezdxf
from ezdxf.addons import Importer

ASSET = Path(__file__).parent / 'assets/ini_lv_symbols.dxf'


def protect_timber(doc):
    """Keep physical timber boundaries out of the generic axis converter."""
    saved = []
    for e in doc.modelspace():
        if any(t in e.dxf.layer.casefold() for t in ('sarr', 'madeira', 'meio', 'pontal')):
            saved.append((e, e.dxf.layer))
            e.dxf.layer = 'INI_LV_GEOMETRY'
    return saved


def restore_timber(saved):
    for e, layer in saved:
        e.dxf.layer = layer


def finish_grades(doc):
    """Front views use the same physical 2.2 cm chords as their sections."""
    from shapely.geometry import Polygon
    timber = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        layer = e.dxf.layer.casefold()
        if 'sarr' in layer or 'meio' in layer:
            timber.append((Polygon(e.get_points('xy')), 'meio' in layer))
    wood_styles(doc)
    rebuild_ab_timber(doc, timber, extend_posts=False)


def wood_rectangle(doc, bounds, half=False):
    x1, y1, x2, y2 = bounds
    if min(x2-x1, y2-y1) < 1e-7:
        return
    horizontal = x2-x1 >= y2-y1
    points = [(x1,(y1+y2)/2),(x2,(y1+y2)/2)] if horizontal else [((x1+x2)/2,y1),((x1+x2)/2,y2)]
    doc.modelspace().add_mline(points, dxfattribs={
        'layer': 'MEIOPONTALETE' if half else 'SARRAFO_2_2X7',
        'style_name': 'INI_LV_MEIO' if half else 'INI_LV_SAR',
        'scale_factor': y2-y1 if horizontal else x2-x1, 'justification': 1})


def rebuild_ab_timber(doc, timber, extend_posts=True):
    from shapely.geometry import box
    m = doc.modelspace()
    for e in list(m):
        if any(t in e.dxf.layer.casefold() for t in ('sarr', 'madeira', 'meio', 'pontal')):
            m.delete_entity(e)
    for name, color in [('SARRAFO_2_2X7',24), ('MEIOPONTALETE',12)]:
        if name not in doc.layers:
            doc.layers.new(name)
        doc.layers.get(name).dxf.color = color
    for geometry, half in timber:
        pieces = [geometry] if geometry.geom_type == 'Polygon' else list(getattr(geometry, 'geoms', []))
        for piece in pieces:
            if piece.geom_type != 'Polygon' or piece.area < 1e-7:
                continue
            if abs(box(*piece.bounds).area-piece.area) < 1e-6:
                bounds = piece.bounds
                if extend_posts and half and bounds[3]-bounds[1] > 7:
                    bounds = (bounds[0],bounds[1]-30,bounds[2],bounds[3])
                wood_rectangle(doc, bounds, half)
                continue
            xs = sorted({p[0] for ring in [piece.exterior, *piece.interiors] for p in ring.coords})
            ys = sorted({p[1] for ring in [piece.exterior, *piece.interiors] for p in ring.coords})
            for a,b in zip(xs,xs[1:]):
                for c,d in zip(ys,ys[1:]):
                    cell = box(a,c,b,d)
                    if cell.area > 1e-7 and piece.covers(cell.representative_point()):
                        wood_rectangle(doc, cell.bounds, half)


def annotate_ab(doc, contract):
    from ezdxf.enums import TextEntityAlignment
    from shapely.geometry import box
    from .lv_nova_design import panel_spans, pontalete_count
    m = doc.modelspace()
    for name,color in [('INI_LV_NUMERACAO',1), ('INI_LV_APOIOS',4)]:
        if name not in doc.layers:
            doc.layers.new(name, dxfattribs={'color':color})
    for e in list(m.query('TEXT')):
        if 'pontalete' in e.dxf.text.casefold():
            m.delete_entity(e)
        elif e.dxf.text == contract['beam']:
            e.dxf.text = f"{contract['beam']}.{contract.get('side','A')}"
    def text(value, point, height, layer='INI_LV_NUMERACAO', rotation=0):
        e = m.add_text(value, dxfattribs={'layer':layer,'height':height,'rotation':rotation})
        e.set_placement(point, align=TextEntityAlignment.MIDDLE_CENTER)
    start = 0.
    number = int(contract.get('panel_number_start',1))
    for seg in contract['segments']:
        length = float(seg['length'])
        body = float(seg.get('body_cm',contract['body_cm']))
        dy = float(seg.get('y_offset_cm',0))
        holes = seg.get('beam_openings', [])
        columns = seg.get('column_openings', [])
        for a,b in panel_spans(length):
            free = box(start+a+1,dy+4,start+b-1,dy+body-5)
            for lo,hi,y in holes:
                free = free.difference(box(start+lo,dy+y,start+hi,dy+body+1))
            for lo,hi in columns:
                free = free.difference(box(start+lo,dy-1,start+hi,dy+body+1))
            regions = [free] if free.geom_type == 'Polygon' else list(getattr(free,'geoms',[]))
            regions = [r for r in regions if r.geom_type=='Polygon' and r.area>1]
            if regions:
                region = max(regions,key=lambda r:r.area)
                point = region.representative_point()
                radius = min(6., (region.bounds[2]-region.bounds[0])/5, (region.bounds[3]-region.bounds[1])/5)
                m.add_circle((point.x,point.y+radius),radius,dxfattribs={'layer':'INI_LV_NUMERACAO'})
                text(str(number),(point.x,point.y+radius),radius*1.1)
                if contract['assembly_variant']=='gradeadas':
                    count = pontalete_count(a,b,[(lo,hi) for lo,hi,y in holes]+columns)
                    text(f'{count}-½PONT.',(point.x,point.y-radius-3),min(4.,radius*.8))
            number += 1
        start += length
    floor = min(float(s.get('y_offset_cm',0)) for s in contract['segments'])
    if contract['assembly_variant']=='gradeadas':
        if 'INI_LV_EXT_TEXT' not in doc.styles:
            doc.styles.new('INI_LV_EXT_TEXT', dxfattribs={'font':'romans.shx','height':0.})
        seen = set()
        for post in m.query('MLINE[layer=="MEIOPONTALETE"]'):
            points = [v.location for v in post.vertices]
            x = points[0].x
            bottom = min(p.y for p in points)
            # Match each upright to the local panel datum, including stepped runs.
            offset = 0.
            for seg in contract['segments']:
                end = offset+float(seg['length'])
                if offset-1e-6 <= x <= end+1e-6:
                    base = float(seg.get('y_offset_cm',0))
                    break
                offset = end
            else:
                continue
            if bottom >= base-1e-6 or (round(x,6),round(bottom,6),round(base,6)) in seen:
                continue
            seen.add((round(x,6),round(bottom,6),round(base,6)))
            dimension = m.add_linear_dim(
                base=(x+6,bottom),p1=(x,bottom),p2=(x,base),angle=90,
                dimstyle='PAINEL',dxfattribs={'layer':'COTA'},
                override={'dimclrd':4,'dimclre':4,'dimclrt':240,'dimtxt':2.5,
                          'dimtxsty':'INI_LV_EXT_TEXT','dimscale':1.,'dimasz':1.,
                          'dimexo':0.,'dimexe':1.5,'dimgap':.5})
            dimension.render()
    for label,x in [(contract.get('support_start',''),-6), (contract.get('support_end',''),start+6)]:
        if label:
            text(label,(x,floor-52),4,'INI_LV_APOIOS',90)
    # Bring annotations forward after filled timber.
    for e in list(m.query('TEXT DIMENSION CIRCLE')):
        m.unlink_entity(e)
        m.add_entity(e)


def wood_styles(doc):
    for name, fill in [('INI_LV_SAR', 17), ('INI_LV_MEIO', 33)]:
        if name not in doc.mline_styles:
            style = doc.mline_styles.new(name)
            style.dxf.flags = 273
            style.dxf.fill_color = fill
            style.elements.append(.5, 256, 'BYLAYER')
            style.elements.append(-.5, 256, 'BYLAYER')
    for e in doc.modelspace().query('MLINE'):
        layer = e.dxf.layer.casefold()
        if any(s in layer for s in ('sarr', 'madeira', 'meio', 'pontal')):
            e.set_style('INI_LV_MEIO' if 'meio' in layer or '3.5' in layer else 'INI_LV_SAR')
            e.update_geometry()
    if 'HIDDEN' not in doc.linetypes:
        doc.linetypes.new('HIDDEN', dxfattribs={'description': 'Hidden', 'pattern': [.75, .5, -.25]})


def finish_ab(doc, contract, timber):
    wood_styles(doc)
    grade = contract['assembly_variant']=='gradeadas'
    rebuild_ab_timber(doc, timber, extend_posts=grade)
    if grade:
        annotate_ab(doc, contract)
    else:
        for label in doc.modelspace().query('TEXT'):
            if label.dxf.text in (contract['beam'], f'Cont. {contract["beam"]}.{contract.get("side", "A")}'):
                prefix = 'Cont. ' if contract.get('continuation') else ''
                label.dxf.text = f'{prefix}{contract["beam"]}.{contract.get("side", "A")}'
    from copy import deepcopy
    native = next(iter(ezdxf.readfile(ASSET).modelspace().query('HATCH')))
    for hatch in doc.modelspace().query('HATCH'):
        if hatch.dxf.pattern_name == 'AR-CONC':
            hatch.dxf.layer = 'CONCRETO'
            hatch.dxf.color = 256
            hatch.dxf.discard('true_color')
            hatch.pattern = deepcopy(native.pattern)
            hatch.dxf.pattern_scale = .1
            hatch.dxf.associative = 0
    # The AB generator emits the slab/void outlines as standalone COTA lines;
    # dimension graphics remain in their own DIMENSION blocks.
    for e in doc.modelspace().query('LINE'):
        if e.dxf.layer.casefold() == 'cota':
            e.dxf.layer = 'CONCRETO'
            e.dxf.color = 256


def finish_sarrafeado_cut(doc):
    """Keep NOVA section geometry/annotations; change only timber presentation."""
    m = doc.modelspace()
    wood_styles(doc)
    for name,color in [('SARRAFO_2_2X7',24),('MEIOPONTALETE',12)]:
        if name not in doc.layers:
            doc.layers.new(name)
        doc.layers.get(name).dxf.color = color
    for e in list(m):
        if e.dxftype()=='HATCH':
            # iNi plywood has hollow outlines; timber fill belongs to MLINE.
            m.delete_entity(e)
        elif e.dxftype()=='LWPOLYLINE' and any(
                s in e.dxf.layer.casefold() for s in ('sarr','madeira','meio','pontal')):
            points = list(e.get_points('xy'))
            bounds = (min(p[0] for p in points),min(p[1] for p in points),
                      max(p[0] for p in points),max(p[1] for p in points))
            half = '3.5' in e.dxf.layer.casefold() or 'meio' in e.dxf.layer.casefold()
            wood_rectangle(doc,bounds,half)
            m.delete_entity(e)
    for e in list(m.query('TEXT DIMENSION')):
        m.unlink_entity(e)
        m.add_entity(e)
    from .lv_formascia_design import normalize_resources
    normalize_resources(doc)


def finish_cut(doc, contract):
    m = doc.modelspace()
    # Native iNi uses filled MLINE timber, with hollow plywood outlines.
    timber = []
    axes = []
    for e in list(m):
        layer = e.dxf.layer.casefold()
        if layer in ('madeira', 'sarr_3.5x7', 'meiopontalete', 'sarrafo_2_2x7') and e.dxftype() == 'LWPOLYLINE':
            pts = list(e.get_points('xy'))
            timber.append((min(p[0] for p in pts), min(p[1] for p in pts),
                           max(p[0] for p in pts), max(p[1] for p in pts), layer))
        if layer == 'tensor7' and e.dxftype() == 'LINE':
            axes.append(e.dxf.start.y)
        if (e.dxftype() == 'HATCH' or (e.dxftype() == 'LWPOLYLINE' and layer in ('madeira', 'sarr_3.5x7', 'meiopontalete',
                'sarrafo_2_2x7')) or layer in ('barrote', 'presilha', 'sco-___-laj', 'tensor7')
                or (e.dxftype() == 'LINE' and layer == '0')):
            m.delete_entity(e)
    wood_styles(doc)
    for name, color in [('SARRAFO_2_2X7',24), ('MEIOPONTALETE',12)]:
        if name not in doc.layers: doc.layers.new(name)
        doc.layers.get(name).dxf.color = color

    def wood(x1,y1,x2,y2,half=False):
        if x2<=x1 or y2<=y1: return
        horizontal = x2-x1 >= y2-y1
        points = [(x1,(y1+y2)/2),(x2,(y1+y2)/2)] if horizontal else [((x1+x2)/2,y1),((x1+x2)/2,y2)]
        m.add_mline(points,dxfattribs={'layer':'MEIOPONTALETE' if half else 'SARRAFO_2_2X7',
            'style_name':'INI_LV_MEIO' if half else 'INI_LV_SAR', 'scale_factor':y2-y1 if horizontal else x2-x1,
            'justification':1})

    grade = contract.get('assembly_variant') == 'gradeadas'
    grade_extensions = []
    for x1,y1,x2,y2,layer in timber:
        # The native grade upright continues 20 cm below the plywood base.
        if grade and abs(x2-x1-7)<.01 and y2-y1>7:
            panel_base = y1
            y1 -= 20
            grade_extensions.append((x1,x2,panel_base,y1))
        wood(x1,y1,x2,y2,'3.5' in layer or 'meio' in layer or
             (grade and abs(x2-x1-7)<.01 and y2-y1>7))
    # Each face has its own extension dimension, measured from the actual
    # plywood base to the bottom of its upright, inside the section opening.
    b = float(contract['width_cm'])
    if grade_extensions and 'INI_LV_EXT_TEXT' not in doc.styles:
        doc.styles.new('INI_LV_EXT_TEXT', dxfattribs={'font':'romans.shx','height':0.})
    for x1,x2,panel_base,grade_bottom in grade_extensions:
        x = 3. if (x1+x2)/2 < b/2 else b-3.
        edge = x2 if x < b/2 else x1
        dimension = m.add_linear_dim(
            base=(x,grade_bottom), p1=(edge,grade_bottom), p2=(edge,panel_base),
            angle=90, dimstyle='PAINEL', dxfattribs={'layer':'COTA'},
            override={'dimclrd':4,'dimclre':4,'dimclrt':240,'dimtxt':2.5,
                      'dimtxsty':'INI_LV_EXT_TEXT','dimscale':1.,'dimasz':1.,
                      'dimexo':0.,'dimexe':1.5,'dimgap':.5})
        dimension.render()
    if grade and not contract.get('inverted'):
        source = ezdxf.readfile(ASSET)
        importer = Importer(source,doc)
        for name in ('INI_LV_HEAD_LEFT','INI_LV_HEAD_RIGHT','INI_LV_PVC','PRESILHA','PRESILHA2'):
            importer.import_block(name,rename=False)
        importer.finalize()
        for name,color in [('BARRA_ANCORAGEM',1),('Barra de Ancoragem',20),('Tubo de PVC',51)]:
            doc.layers.get(name).dxf.color=color
        b = float(contract['width_cm'])
        for yy in axes:
            m.add_blockref('INI_LV_HEAD_LEFT',(-9,yy))
            m.add_blockref('INI_LV_HEAD_RIGHT',(b+9,yy))
            m.add_blockref('INI_LV_PVC',(0,yy),dxfattribs={'xscale':b/19})
            for dy in (-.749,.749):
                m.add_line((-18.261,yy+dy),(b+18.261,yy+dy),dxfattribs={'layer':'BARRA_ANCORAGEM'})
        for name,x in [('PRESILHA2',-12.429),('PRESILHA',b+12.486)]:
            m.add_blockref(name,(x,-5.433),dxfattribs={'layer':'COMPENSADO','xscale':-.5,'yscale':.5,'zscale':.5})
        for yy in (-6,-5):
            m.add_line((-12.429,yy),(b+12.486,yy),dxfattribs={'layer':'BARRA_ANCORAGEM'})
    for e in m.query('TEXT'):
        if e.dxf.text in ('a','b','c'):
            e.dxf.text=e.dxf.text.upper()
            if e.dxf.text == 'C':
                e.dxf.insert = (float(contract['width_cm'])/2,-12,0)
                e.dxf.align_point = e.dxf.insert
    # Timber fill must be drawn before the face letters and measurements.
    for e in list(m.query('TEXT DIMENSION')):
        m.unlink_entity(e)
        m.add_entity(e)
    from .lv_formascia_design import normalize_resources
    normalize_resources(doc)

