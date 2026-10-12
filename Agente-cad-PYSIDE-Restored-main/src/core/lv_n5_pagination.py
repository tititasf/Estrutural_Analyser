"""Paginate native AB geometry at physical panel boundaries, at scale one.

Page edges are display cuts, never new construction extremities. Original N3
files remain immutable; only dimensions spanning a page edge are remeasured.
"""
from io import StringIO

import ezdxf
from ezdxf import bbox
from shapely.geometry import Polygon, LineString, box
from .lv_nova_design import panel_spans


def _parts(geometry):
    return geometry.geoms if hasattr(geometry, 'geoms') else [geometry]


def paginate_ab(source, contract, maximum_width, first_width=None):
    bounds=bbox.extents(source.modelspace())
    if bounds.size.x <= (first_width or maximum_width) + .01:
        return [(source, None)]
    boundaries, start = [0.], 0.
    for segment in contract['segments']:
        boundaries.extend(start + end for _, end in panel_spans(segment['length']))
        start += segment['length']
    # Reserve dimension tails and names; never scale the fabrication geometry.
    reserve = max(0.,bounds.extmax.x-start)+max(0.,-bounds.extmin.x)+10
    capacity = maximum_width - reserve
    windows, left = [], 0.
    while left < start - 1e-6:
        available = first_width-reserve if not windows and first_width is not None else capacity
        candidates = [p for p in boundaries if left < p <= left + available]
        if not candidates:
            raise ValueError('Painel individual excede a área útil da moldura')
        right = max(candidates)
        windows.append((left, right))
        left = right
    stream = StringIO()
    source.write(stream)
    result = []
    for page, (left, right) in enumerate(windows):
        doc = ezdxf.read(StringIO(stream.getvalue()))
        ms = doc.modelspace()
        clip = box(left, -1e6, right, 1e6)
        final = page == len(windows)-1
        for e in list(ms):
            original = e.copy()
            typ = e.dxftype()
            if typ == 'LINE':
                a, b = e.dxf.start, e.dxf.end
                # A shared vertical edge belongs to the preceding window.
                if page and abs(a.x-left)<1e-6 and abs(b.x-left)<1e-6:
                    ms.delete_entity(e)
                    continue
                geometry = LineString([(a.x,a.y),(b.x,b.y)]).intersection(clip)
                ms.delete_entity(e)
                for part in _parts(geometry):
                    if part.geom_type == 'LineString' and part.length > 1e-7:
                        copy = original.copy()
                        copy.dxf.start, copy.dxf.end = part.coords[0], part.coords[-1]
                        ms.add_entity(copy)
            elif typ == 'HATCH':
                # AB voids use polygon paths. Preserve pattern, scale and origin.
                paths = list(e.paths)
                if any(not hasattr(p, 'vertices') or any(v[2] for v in p.vertices) for p in paths):
                    raise ValueError('Hachura AB curva não suporta paginação poligonal')
                geometry = None
                for p in paths:
                    polygon = Polygon([(v[0],v[1]) for v in p.vertices])
                    if geometry is None:
                        geometry = polygon
                    elif p.path_type_flags & 1:
                        geometry = geometry.union(polygon)
                    else:
                        geometry = geometry.difference(polygon)
                ms.delete_entity(e)
                for polygon in _parts(geometry.intersection(clip)):
                    if polygon.geom_type != 'Polygon' or polygon.area < 1e-7:
                        continue
                    copy = original.copy(); copy.paths.clear()
                    copy.paths.add_polyline_path(list(polygon.exterior.coords)[:-1], is_closed=True, flags=1)
                    for ring in polygon.interiors:
                        copy.paths.add_polyline_path(list(ring.coords)[:-1], is_closed=True, flags=0)
                    ms.add_entity(copy)
            elif typ == 'DIMENSION':
                a, b = e.dxf.defpoint2, e.dxf.defpoint3
                lo, hi = sorted((a.x,b.x))
                if hi < left+1e-6 or lo > right-1e-6:
                    # Keep the right-side height dimensions only on the last page.
                    if not (final and lo >= right and abs(a.x-b.x)<1e-6):
                        ms.delete_entity(e)
                elif lo < left-1e-6 or hi > right+1e-6:
                    if e.dxf.get('angle',0) % 180:
                        raise ValueError('Cota AB não horizontal atravessa uma quebra de folha')
                    override = e.get_acad_dstyle(e.get_dim_style())
                    base = e.dxf.defpoint
                    attrs = {'layer':e.dxf.layer, 'color':e.dxf.get('color',256)}
                    ms.delete_entity(e)
                    def witness_y(x, original_x, original_y, at_right=False):
                        if abs(x-original_x)<1e-6:
                            return original_y
                        offset=0.
                        for segment in contract['segments']:
                            end=offset+segment['length']
                            if x < end-1e-6 or (at_right and x <= end+1e-6):
                                return segment.get('y_offset_cm',0.)
                            offset=end
                        return contract['segments'][-1].get('y_offset_cm',0.)
                    x1,x2=max(lo,left),min(hi,right)
                    start_point,end_point=(a,b) if a.x<=b.x else (b,a)
                    d = ms.add_linear_dim(base=(x1,base.y),
                        p1=(x1,witness_y(x1,start_point.x,start_point.y)),
                        p2=(x2,witness_y(x2,end_point.x,end_point.y,True)),
                        dimstyle=original.dxf.dimstyle, override=override, dxfattribs=attrs)
                    d.render()
            elif typ in ('TEXT','MTEXT'):
                x = e.dxf.insert.x
                if x < left or (x >= right and not final):
                    ms.delete_entity(e)
            else:
                raise ValueError(f'Entidade AB não suportada na paginação: {typ}')
        if page:
            offset=0.
            for segment in contract['segments']:
                if offset+segment['length']>left+1e-6:
                    title_y=segment.get('total_cm',contract['total_cm'])+segment.get('y_offset_cm',0)+5
                    break
                offset+=segment['length']
            ms.add_text(f'Cont. {contract["beam"]}.{contract.get("side","A")}',
                        dxfattribs={'height':13,'layer':'Texto Seção',
                                    'insert':(left+5,title_y)})
        if bbox.extents(ms).size.x > maximum_width+.01 or doc.audit().has_errors:
            raise ValueError('Paginação AB excede a moldura ou produz DXF inválido')
        result.append((doc, [left,right]))
    return result
