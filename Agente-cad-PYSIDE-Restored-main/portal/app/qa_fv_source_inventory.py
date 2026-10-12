"""Fail-closed original contour/convention inventory for automatic FV owners."""
import math
import re
from pathlib import Path
from shapely.geometry import Point, Polygon


def original_convention(source, adjacent_convention):
    """Read explicit original declarations, including the same crop's details."""
    from .preprocessamento.adapters.pillar_convention import extract_pillar_convention
    mappings=[adjacent_convention] if adjacent_convention else []
    source=Path(source)
    for path in (source, source.parent/'detalhes.dxf'):
        if not path.is_file():continue
        declaration=extract_pillar_convention(path)
        if declaration.get('conflicts'):return {}
        if declaration.get('status')!='complete':continue
        mapping={e['label']:{'label':e['label'],'sig':e['signature']}
                 for e in declaration.get('entries',[]) if e.get('line_count',0)>=4}
        if mapping:mappings.append(mapping)
    if not mappings:return {}
    first=mappings[0]
    if any({k:v['sig'] for k,v in m.items()}!={k:v['sig'] for k,v in first.items()} for m in mappings):return {}
    return first


def declaration_signature(source):
    path=Path(source).parent/'detalhes.dxf'
    if not path.is_file():return 'no_adjacent_details'
    stat=path.stat()
    return str((str(path.resolve()),stat.st_size,stat.st_mtime_ns))


def pillar_solids(doc, source_data, convention, epsilon=.05):
    """Return physical polygons only after original names and symbols agree.

    Closed contours alone are not pillars (sheet frames and sections exist).
    Multiple nearby names or unclassified symbols keep the inventory unknown.
    A NASCE symbol excludes only its own contour, never an overlapping solid.
    """
    from src.core.pillar_convention_recognition import recognize
    from src.core.pil_qa_identity_paths import collect_identity_scene
    if not convention:
        return None, {'checked':False,'reason':'original_pillar_convention_missing'}
    labels=[]
    for e in doc.modelspace().query('TEXT MTEXT'):
        text=(e.dxf.text if e.dxftype()=='TEXT' else e.plain_text()).strip()
        if re.fullmatch(r'P\d+[A-Z]?',text,re.I):
            labels.append((text.upper(),Point(e.dxf.insert.x,e.dxf.insert.y),e.dxf.handle))
    supports={p['handle']:p for p in collect_identity_scene(doc,epsilon)['supports']
              if p['name_handles'] and p['dimension_handles']}
    candidates=[];raw_named=[]
    for e in doc.modelspace().query('LWPOLYLINE'):
        pts=list(e.get_points('xyb'))
        if len(pts)<4 or any(p[2] for p in pts):continue
        if not e.closed and math.dist(pts[0][:2],pts[-1][:2])>epsilon:continue
        poly=Polygon([p[:2] for p in pts])
        if not poly.is_valid or poly.area<=0:continue
        raw_nearby=[l for l in labels if poly.distance(l[1])<=30]
        if len({l[0] for l in raw_nearby})==1:
            raw_named.append((poly,e.dxf.handle,raw_nearby))
        ownership=supports.get(e.dxf.handle)
        if ownership is None:continue
        nearby=[l for l in labels if l[2] in ownership['name_handles']]
        if len({l[0] for l in nearby})!=1:continue
        candidates.append((poly,e.dxf.handle,nearby))
    # A larger enclosing frame/detail cannot replace the nearest small contour.
    selected=[];uncertain=[]
    for name,point,handle in labels:
        choices=[c for c in candidates if any(l[2]==handle for l in c[2])]
        if not choices:
            possible=[c for c in raw_named if any(l[2]==handle for l in c[2])]
            if possible:
                # No numeric ownership means none can be picked as the solid.
                # Preserve every possible original polygon as a local blocker.
                uncertain.extend({'reason':'original_pillar_name_without_unique_contour','handle':handle,
                                  'contour_handle':c[1],'points':list(c[0].exterior.coords)} for c in possible)
            else:
                uncertain.append({'reason':'original_pillar_name_without_unique_contour','handle':handle,
                                  'point':[point.x,point.y]})
            continue
        ranked=sorted(choices,key=lambda c:(c[0].distance(point),c[0].area))
        if len(ranked)>1 and abs(ranked[0][0].distance(point)-ranked[1][0].distance(point))<=epsilon and abs(ranked[0][0].area-ranked[1][0].area)<=epsilon**2:
            uncertain.append({'reason':'original_pillar_contour_ambiguous','handle':handle,
                              'points':list(ranked[0][0].exterior.coords)})
            continue
        selected.append(ranked[0])
    solids=[];proof=[];seen=set()
    for poly,handle,names in selected:
        if handle in seen:continue
        seen.add(handle)
        kind,evidence=recognize(list(poly.exterior.coords),source_data,convention)
        if kind not in {'NASCE','SEGUE','MORRE'}:
            uncertain.append({'reason':'original_pillar_symbol_unclassified','handle':handle,
                              'points':list(poly.exterior.coords),'evidence':evidence})
            continue
        proof.append({'handle':handle,'classification':kind,'name_handles':[l[2] for l in names],
                      'dimension_handles':supports[handle]['dimension_handles']})
        if kind!='NASCE':solids.append(poly)
    if not proof and not uncertain:
        return None, {'checked':False,'reason':'original_named_pillar_inventory_empty'}
    return solids, {'checked':not uncertain,'pillars':proof,'uncertainties':uncertain,
                    'local_scope_available':True,'authority':'original_named_contours_and_source_convention'}


def inventory_scope_checked(inventory, region):
    """Remote ambiguity cannot change a local physically connected corridor."""
    if not inventory.get('local_scope_available'):return inventory.get('checked',False)
    for pending in inventory.get('uncertainties',[]):
        # An unmatched name has no physical contour: retain its nearby region
        # conservatively; known ambiguous contours retain their exact polygon.
        obstacle=Polygon(pending['points']) if 'points' in pending else Point(pending['point']).buffer(30)
        if obstacle.intersects(region):return False
    return True


def competing_ownership_checked(rows):
    """Manual/validated polygons must be reconciled rather than overwritten."""
    return not any(r.get('validated_fields') or r.get('validated') or r.get('is_validated')
                   or r.get('manual') or r.get('manual_contour')
                   or str(r.get('geometry_source','')).lower().startswith(('manual','human','validated'))
                   for r in rows)
