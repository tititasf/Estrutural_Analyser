import time
from PySide6.QtCore import QObject, Signal, QThread, QRunnable, QThreadPool, QPointF
from PySide6.QtGui import QPainterPath, QTransform

class CanvasEntityWorker(QObject):
    """
    Worker para processar entidades DXF em background.
    Gera QPainterPaths e calcula Snaps fora da thread principal.
    """
    finished = Signal(object, object, object, object) # batches, snap_data, metadata, texts
    progress = Signal(int)
    
    def __init__(self, entities, compute_snaps=True):
        super().__init__()
        self.entities = entities
        self.compute_snaps = compute_snaps
        self._is_running = True
        
    def run(self):
        """Executa o processamento pesado de entidades já achatadas pelo loader."""
        try:
            batched_paths = {}
            raw_snap_data = {'endpoints': [], 'midpoints': [], 'centers': [], 'quadrants': []}
            dxf_metadata = {'layers': set(), 'colors': set(), 'types': set()}
            texts_list = []
            self.stats = {'lines': 0, 'polylines': 0, 'circles': 0, 'hatches': 0, 'texts': 0}
            BATCH_CHUNK_SIZE = 1000

            entities_dict = self.entities

            # 1. Lines
            lines = entities_dict.get('lines', [])
            self.stats['lines'] = len(lines)
            for line in lines:
                s, e = QPointF(*line['start']), QPointF(*line['end'])
                key = (line.get('layer', '0'), line['color'], line.get('lineweight'), line.get('aci'), False)
                
                if key not in batched_paths: 
                    batched_paths[key] = {'path': QPainterPath(), 'count': 0, 'items': []}
                batch = batched_paths[key]
                
                if batch['count'] >= BATCH_CHUNK_SIZE:
                    batch['items'].append(batch['path'])
                    batch['path'] = QPainterPath()
                    batch['count'] = 0
                
                batch['path'].moveTo(s)
                batch['path'].lineTo(e)
                batch['count'] += 1

                if self.compute_snaps:
                    dxf_metadata['layers'].add(key[0])
                    raw_snap_data['endpoints'].append((s.x(), s.y()))
                    raw_snap_data['endpoints'].append((e.x(), e.y()))
                    raw_snap_data['midpoints'].append(((s.x()+e.x())/2, (s.y()+e.y())/2))

            # 2. Polylines
            polys = entities_dict.get('polylines', [])
            self.stats['polylines'] = len(polys)
            for poly in polys:
                pts = [QPointF(p[0], p[1]) for p in poly['points']]
                if not pts: continue
                
                key = (poly.get('layer', '0'), poly.get('color'), poly.get('lineweight'), poly.get('aci'), False)
                if key not in batched_paths: 
                    batched_paths[key] = {'path': QPainterPath(), 'count': 0, 'items': []}
                batch = batched_paths[key]
                
                if batch['count'] >= BATCH_CHUNK_SIZE:
                    batch['items'].append(batch['path'])
                    batch['path'] = QPainterPath()
                    batch['count'] = 0

                batch['path'].moveTo(pts[0])
                for i in range(1, len(pts)):
                    batch['path'].lineTo(pts[i])
                if poly.get('closed'):
                    batch['path'].closeSubpath()
                batch['count'] += 1

                if self.compute_snaps:
                    for p in pts: raw_snap_data['endpoints'].append((p.x(), p.y()))

            # 3. Circles & Arcs
            circles = entities_dict.get('circles', [])
            self.stats['circles'] = len(circles)
            for c in circles:
                center = QPointF(*c['center'])
                radius = c['radius']
                
                key = (c.get('layer', '0'), c.get('color'), c.get('lineweight'), c.get('aci'), False)
                if key not in batched_paths: 
                    batched_paths[key] = {'path': QPainterPath(), 'count': 0, 'items': []}
                batch = batched_paths[key]

                if batch['count'] >= BATCH_CHUNK_SIZE:
                    batch['items'].append(batch['path'])
                    batch['path'] = QPainterPath()
                    batch['count'] = 0
                
                if 'start_angle' in c: # ARC
                    sa = c['start_angle']
                    ea = c['end_angle']
                    span = ea - sa
                    if span < 0: span += 360
                    
                    x, y, w, h = center.x()-radius, center.y()-radius, radius*2, radius*2
                    batch['path'].arcMoveTo(x, y, w, h, sa)
                    batch['path'].arcTo(x, y, w, h, sa, span)
                else: # CIRCLE
                    batch['path'].addEllipse(center, radius, radius)
                
                batch['count'] += 1
                
                if self.compute_snaps:
                    raw_snap_data['centers'].append((center.x(), center.y()))

            # 4. Hatches
            hatches = entities_dict.get('hatches', [])
            self.stats['hatches'] = len(hatches)
            for h in hatches:
                key = (h.get('layer', '0'), h.get('color'), h.get('lineweight'), h.get('aci'), True)
                if key not in batched_paths: 
                    batched_paths[key] = {'path': QPainterPath(), 'count': 0, 'items': []}
                batch = batched_paths[key]
                
                for path_points in h.get('paths', []):
                    if not path_points: continue
                    pts = [QPointF(p[0], p[1]) for p in path_points]
                    
                    batch['path'].moveTo(pts[0])
                    for i in range(1, len(pts)):
                        batch['path'].lineTo(pts[i])
                    batch['path'].closeSubpath()
                batch['count'] += 1

            # 5. Ellipses
            ellipses = entities_dict.get('ellipses', [])
            for ell in ellipses:
                center = QPointF(*ell['center'])
                major_axis = QPointF(*ell['major_axis'])
                ratio = ell['ratio']
                
                import math
                radius_x = math.sqrt(major_axis.x()**2 + major_axis.y()**2)
                radius_y = radius_x * ratio
                angle = math.degrees(math.atan2(major_axis.y(), major_axis.x()))
                
                key = (ell.get('layer', '0'), ell.get('color'), ell.get('lineweight'), ell.get('aci'), False)
                if key not in batched_paths: 
                    batched_paths[key] = {'path': QPainterPath(), 'count': 0, 'items': []}
                batch = batched_paths[key]
                
                temp_path = QPainterPath()
                temp_path.addEllipse(QPointF(0,0), radius_x, radius_y)
                ell_trans = QTransform().translate(center.x(), center.y()).rotate(angle)
                batch['path'].addPath(ell_trans.map(temp_path))
                batch['count'] += 1

            # 6. Splines (Approximation)
            splines = entities_dict.get('splines', [])
            for spline in splines:
                pts = [QPointF(p[0], p[1]) for p in spline['control_points']]
                if not pts: continue
                key = (spline.get('layer', '0'), spline.get('color'), spline.get('lineweight'), spline.get('aci'), False)
                if key not in batched_paths: 
                    batched_paths[key] = {'path': QPainterPath(), 'count': 0, 'items': []}
                batch = batched_paths[key]
                
                batch['path'].moveTo(pts[0])
                for i in range(1, len(pts)): batch['path'].lineTo(pts[i])
                if spline.get('closed'): batch['path'].closeSubpath()
                batch['count'] += 1

            # 7. Final Texts list
            texts_list = entities_dict.get('texts', [])
            self.stats['texts'] = len(texts_list)

            # Finalize open batches
            for b in batched_paths.values():
                if b['count'] > 0:
                    b['items'].append(b['path'])

            print(f"[CanvasWorker] Processing Summary: {self.stats}")
            self.finished.emit(batched_paths, raw_snap_data, dxf_metadata, texts_list)
            
        except Exception as e:
            print(f"[CanvasWorker] Error: {e}")
            import traceback
            traceback.print_exc()
            self.finished.emit({}, {}, {}, [])


    def stop(self):
        self._is_running = False
