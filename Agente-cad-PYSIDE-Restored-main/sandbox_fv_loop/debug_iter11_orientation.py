import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
from src.core.spatial_index import SpatialIndex
import re

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)

texts = dxf_data.get("texts", [])
lines = dxf_data.get("lines", [])
polys = dxf_data.get("polylines", [])

beam_labels = []
for t in texts:
    content = t['text'].strip()
    if (content.startswith('V') or content.startswith('v') or content.upper().startswith('CONT') or content.startswith('VF')) and any(c.isdigit() for c in content):
        beam_labels.append(t)

spatial_index = SpatialIndex()
for poly in polys:
    pts = poly.get("points", [])
    if pts:
        bounds = (min(p[0] for p in pts), min(p[1] for p in pts),
                  max(p[0] for p in pts), max(p[1] for p in pts))
        spatial_index.insert(poly, bounds)
for line in lines:
    pts = line.get("points", [])
    if pts:
        bounds = (min(p[0] for p in pts), min(p[1] for p in pts),
                  max(p[0] for p in pts), max(p[1] for p in pts))
        spatial_index.insert(line, bounds)

def get_orientation(pos):
    def _grow(is_h):
        contain_long = 4000
        contain_trans = 80
        if is_h:
            cbox = (pos[0]-contain_long, pos[1]-contain_trans, pos[0]+contain_long, pos[1]+contain_trans)
        else:
            cbox = (pos[0]-contain_trans, pos[1]-contain_long, pos[0]+contain_trans, pos[1]+contain_long)
            
        def _in_box(pts):
            for p in pts:
                if cbox[0] <= p[0] <= cbox[2] and cbox[1] <= p[1] <= cbox[3]:
                    return True
            return False

        def _owns(pts):
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            my_dist = abs(cx - pos[0]) if is_h else abs(cy - pos[1])
            
            for other in beam_labels:
                op = other['pos']
                if abs(op[0] - pos[0]) < 5 and abs(op[1] - pos[1]) < 5:
                    continue
                if is_h and abs(op[1] - pos[1]) < 40:
                    if abs(cx - op[0]) < my_dist: return False
                elif not is_h and abs(op[0] - pos[0]) < 40:
                    if abs(cy - op[1]) < my_dist: return False
            return True

        sementes = []
        seed_cands = spatial_index.query_bbox((pos[0]-60, pos[1]-60, pos[0]+60, pos[1]+60))
        for cand in seed_cands:
            if isinstance(cand, dict) and 'points' in cand and _in_box(cand['points']):
                sementes.append(cand)
                
        visited = set()
        q = []
        res_lines = []
        
        for s in sementes:
            if id(s) not in visited:
                visited.add(id(s))
                q.append(s)
                res_lines.append(s['points'])
                
        while q and len(res_lines) < 1000:
            curr = q.pop(0)
            for pt in curr['points']:
                if not (cbox[0] <= pt[0] <= cbox[2] and cbox[1] <= pt[1] <= cbox[3]):
                    continue
                # For orientation, keeping conn_tol=30 or 400? Iteration 11 had 30.
                vizinhos = spatial_index.query_bbox((pt[0]-30, pt[1]-30, pt[0]+30, pt[1]+30))
                for cand in vizinhos:
                    if isinstance(cand, dict) and 'points' in cand:
                        if id(cand) not in visited and _in_box(cand['points']) and _owns(cand['points']):
                            visited.add(id(cand))
                            q.append(cand)
                            res_lines.append(cand['points'])
                            
        if not res_lines: return 0
        all_x = [p[0] for l in res_lines for p in l]
        all_y = [p[1] for l in res_lines for p in l]
        return (max(all_x)-min(all_x)) if is_h else (max(all_y)-min(all_y))

    len_h = _grow(True)
    len_v = _grow(False)
    return len_h >= len_v, len_h, len_v

for name in ["V302", "V312", "V320", "V322", "V325", "V330", "V332", "V301", "V303"]:
    for t in beam_labels:
        if t['text'].strip() == name:
            is_h, lh, lv = get_orientation(t['pos'])
            print(f"{name:5s}: {'HORIZ' if is_h else 'VERT '} | H={lh:.0f} | V={lv:.0f}")
