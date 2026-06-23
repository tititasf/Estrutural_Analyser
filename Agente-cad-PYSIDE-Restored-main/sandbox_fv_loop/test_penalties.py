import sys
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
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

beam_labels = []
for t in dxf_data.get('texts', []):
    content = t['text'].strip()
    if (content.startswith('V') or content.startswith('v') or content.upper().startswith('CONT') or content.startswith('VF')) and any(c.isdigit() for c in content):
        beam_labels.append(t)

def _grow(pos, is_h):
    cbox = (pos[0]-60, pos[1]-30, pos[0]+60, pos[1]+30) if is_h else (pos[0]-30, pos[1]-60, pos[0]+30, pos[1]+60)
    
    def _in_box(pts):
        for p in pts:
            if cbox[0] <= p[0] <= cbox[2] and cbox[1] <= p[1] <= cbox[3]:
                return True
        return False

    seed_cands = spatial_index.query_bbox((pos[0]-20, pos[1]-20, pos[0]+20, pos[1]+20))
    sementes = [cand for cand in seed_cands if isinstance(cand, dict) and 'points' in cand and _in_box(cand['points'])]
    
    visited = set()
    q = []
    res_lines = []
    
    for s in sementes:
        if id(s) not in visited:
            visited.add(id(s))
            q.append(s)
            res_lines.append(s['points'])
            
    while q and len(res_lines) < 2000:
        curr = q.pop(0)
        for pt in curr['points']:
            if not (cbox[0] <= pt[0] <= cbox[2] and cbox[1] <= pt[1] <= cbox[3]):
                continue
            vizinhos = spatial_index.query_bbox((pt[0]-200, pt[1]-200, pt[0]+200, pt[1]+200))
            for cand in vizinhos:
                if isinstance(cand, dict) and 'points' in cand:
                    if id(cand) not in visited and _in_box(cand['points']):
                        visited.add(id(cand))
                        q.append(cand)
                        res_lines.append(cand['points'])
                        
    if not res_lines: return 0, float('inf')
    all_x = [p[0] for l in res_lines for p in l]
    all_y = [p[1] for l in res_lines for p in l]
    
    min_dist = float('inf')
    for line in res_lines:
        if not line: continue
        if is_h:
            l_min_x, l_max_x = min(p[0] for p in line), max(p[0] for p in line)
            if l_min_x - 5 <= pos[0] <= l_max_x + 5:
                cy = sum(p[1] for p in line)/len(line)
                min_dist = min(min_dist, abs(cy - pos[1]))
        else:
            l_min_y, l_max_y = min(p[1] for p in line), max(p[1] for p in line)
            if l_min_y - 5 <= pos[1] <= l_max_y + 5:
                cx = sum(p[0] for p in line)/len(line)
                min_dist = min(min_dist, abs(cx - pos[0]))
                
    length = (max(all_x)-min(all_x)) if is_h else (max(all_y)-min(all_y))
    return length, min_dist

for p in [1.0, 1.2, 1.5, 2.0, 2.6]:
    print(f"--- PENALTY {p} ---")
    correct_count = 0
    total = 0
    
    for b in beam_labels:
        content = b['text'].strip()
        pos = b['pos']
        
        len_h, dist_h = _grow(pos, True)
        len_v, dist_v = _grow(pos, False)
        
        score_h = len_h / (max(10.0, dist_h) ** p) if dist_h != float('inf') else 0
        score_v = len_v / (max(10.0, dist_v) ** p) if dist_v != float('inf') else 0
        
        is_h = score_h >= score_v
        
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
                print(f"  FAIL {content}: is_h={is_h} (H:{score_h:.1f}, V:{score_v:.1f}) (L_h:{len_h:.1f}, L_v:{len_v:.1f}) (d_h:{dist_h:.1f}, d_v:{dist_v:.1f})")
                
    print(f"  Accuracy: {correct_count}/{total} ({correct_count/total*100:.1f}%)")
