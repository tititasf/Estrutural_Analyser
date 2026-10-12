"""Original sheet borders enclosing independently detected plan and detail.

Only border entities receive a role. The original source and every contained
entity remain intact; scale, labels, levels and classifications are untouched.
"""
import hashlib
from pathlib import Path
from shapely.geometry import Polygon, Point, LineString, box

EPS=1e-4  # six-decimal DXF serialization rounding, never geometric snapping


def prove_sheet_frames(contours, primitives, detection):
    towers=[box(*r['bbox']) for r in detection.get('torres',[])]
    details=[box(*r['bbox']) for r in detection.get('detalhes',[])]
    separated=[(a,b) for a in towers for b in details if a.distance(b)>EPS]
    candidates=[]
    for contour in contours:
        p=Polygon(contour['points'])
        coords=list(p.exterior.coords)[:-1]
        if not p.is_valid or len(coords)!=4 or not p.equals(box(*p.bounds)):
            continue
        pairs=[(a,b) for a,b in separated if p.contains(a) and p.contains(b)]
        if not pairs:
            continue
        incident=[r for r in primitives if r['handle']!=contour['handle'] and p.boundary.distance(r['geometry'])<=EPS]
        if incident:
            continue
        candidates.append((contour,p,pairs))
    records=[]
    for contour,p,pairs in candidates:
        nested=[other['handle'] for other,q,_ in candidates if other['handle']!=contour['handle'] and (p.contains(q) or q.contains(p))]
        if not nested:
            continue
        children=sorted({r['handle'] for r in primitives if r['handle']!=contour['handle'] and p.contains(r['geometry'])})
        records.append(dict(status='proved',role='sheet_frame',source_entity_handles=[contour['handle']],
            original_points=contour['points'],nested_border_handles=nested,
            contained_entity_handles=children,content_preserved=True,
            detection_evidence=[dict(tower_bbox=list(a.bounds),detail_bbox=list(b.bounds)) for a,b in pairs],
            binding_method='original_nested_rectangular_borders_no_boundary_incidents_separate_detected_plan_and_detail',
            tolerance_drawing_units=EPS))
    return records


def inventory_sheet_frames(source,detection=None):
    import ezdxf
    from scripts.obra_crop_engine import detect_regions
    path=Path(source);revision=hashlib.sha256(path.read_bytes()).hexdigest()
    detection=detect_regions(path) if detection is None else detection
    if detection.get('error'):
        # An optional border proof failing must not discard valid conventions,
        # levels or structural analysis collected by the other modules. No
        # entity can receive a sheet-frame role without the missing proof.
        return dict(status='region_detection_failed', records=[],
                    error='sheet_frame_region_detection_failed',
                    detection_error=str(detection['error']),
                    source_revision=revision, production_files_modified=False)
    contours=[];primitives=[]
    for entity in ezdxf.readfile(path).modelspace():
        kind=entity.dxftype();handle=entity.dxf.handle;geometry=None
        if kind=='LWPOLYLINE' and not any(abs(p[4])>EPS for p in entity.get_points()):
            points=[list(p) for p in entity.get_points('xy')]
            if len(points)>=4 and (entity.closed or points[0]==points[-1]):
                geometry=Polygon(points)
                if geometry.is_valid:
                    contours.append(dict(handle=handle,points=points))
                    geometry=LineString(geometry.exterior.coords)
            elif len(points)>=2:geometry=LineString(points)
        elif kind=='LINE':
            a=list(entity.dxf.start)[:2];b=list(entity.dxf.end)[:2]
            geometry=Point(a) if a==b else LineString([a,b])
        elif kind in ('TEXT','MTEXT'):
            geometry=Point(list(entity.dxf.insert)[:2])
        elif kind=='CIRCLE':
            geometry=Point(list(entity.dxf.center)[:2]).buffer(entity.dxf.radius)
        if geometry is not None and geometry.is_valid:
            primitives.append(dict(handle=handle,geometry=geometry))
    records=prove_sheet_frames(contours,primitives,detection)
    for record in records:record.update(source_revision=revision,source_path=str(path))
    return dict(status='proved_frames' if records else 'not_proved',records=records,
                source_revision=revision,production_files_modified=False)
