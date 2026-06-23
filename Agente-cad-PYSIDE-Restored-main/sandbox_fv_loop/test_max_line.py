import sys
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
from src.core.beam_tracer import BeamTracer
from src.core.spatial_index import SpatialIndex

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)

spatial_index = SpatialIndex()
for poly in dxf_data.get('polylines', []):
    pts = poly.get("points", [])
    if not pts: continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    spatial_index.insert(poly, (min(xs), min(ys), max(xs), max(ys)))

for line in dxf_data.get('lines', []):
    pts = line.get("points", [])
    if not pts: continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    spatial_index.insert(line, (min(xs), min(ys), max(xs), max(ys)))

for txt in dxf_data.get('texts', []):
    p = txt['pos']
    spatial_index.insert(txt, (p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5))

bt = BeamTracer(spatial_index)

beam_labels = []
for t in dxf_data.get('texts', []):
    content = t['text'].strip()
    if (content.startswith('V') or content.startswith('v') or content.upper().startswith('CONT') or content.startswith('VF')) and any(c.isdigit() for c in content):
        beam_labels.append(t)

correct_count = 0
total = 0

for b in beam_labels:
    content = b['text'].strip()
    pos = b['pos']
    
    cands = bt.spatial_index.query_bbox((pos[0]-400, pos[1]-400, pos[0]+400, pos[1]+400))
    
    best_h_len = 0
    best_v_len = 0
    
    for cand in cands:
        if isinstance(cand, dict) and 'points' in cand:
            for i in range(len(cand['points'])-1):
                p1, p2 = cand['points'][i], cand['points'][i+1]
                dx = abs(p2[0]-p1[0])
                dy = abs(p2[1]-p1[1])
                l = max(dx, dy)
                if l < 10: continue
                
                # Check distance to label
                if dx > dy:
                    # Horizontal line, check Y distance
                    cy = (p1[1] + p2[1]) / 2
                    if abs(cy - pos[1]) <= 60:
                        best_h_len = max(best_h_len, l)
                else:
                    # Vertical line, check X distance
                    cx = (p1[0] + p2[0]) / 2
                    if abs(cx - pos[0]) <= 60:
                        best_v_len = max(best_v_len, l)
                        
    is_h = best_h_len >= best_v_len
    
    is_h_gt = None
    if content in ['V301', 'V302', 'V303', 'V304', 'V305', 'V306', 'V307', 'V313', 'V315', 'V317', 'V319', 'V325']:
        is_h_gt = True
    elif content in ['V309', 'V310', 'V311', 'V312', 'V322', 'V332', 'V331', 'V330', 'V329', 'V328', 'V327', 'V326', 'V309A']:
        is_h_gt = False
        
    if is_h_gt is not None:
        total += 1
        if is_h == is_h_gt:
            correct_count += 1
        else:
            print(f"FAIL {content}: is_h={is_h} (H:{best_h_len:.1f}, V:{best_v_len:.1f})")

print(f"Accuracy: {correct_count}/{total} ({correct_count/total*100:.1f}%)")
