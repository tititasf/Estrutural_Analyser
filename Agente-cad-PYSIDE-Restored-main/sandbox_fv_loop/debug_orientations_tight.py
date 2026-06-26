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

def _grow_geometry(pos):
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
                vizinhos = spatial_index.query_bbox((pt[0]-400, pt[1]-400, pt[0]+400, pt[1]+400))
                for cand in vizinhos:
                    if isinstance(cand, dict) and 'points' in cand:
                        if id(cand) not in visited and _in_box(cand['points']):
                            visited.add(id(cand))
                            q.append(cand)
                            res_lines.append(cand['points'])
                            
        if not res_lines: return 0, [], float('inf')
        all_x = [p[0] for l in res_lines for p in l]
        all_y = [p[1] for l in res_lines for p in l]
        
        min_dist = float('inf')
        for line in res_lines:
            if not line: continue
            if is_h:
                l_min_x, l_max_x = min(p[0] for p in line), max(p[0] for p in line)
                if l_min_x - 5 <= pos[0] <= l_max_x + 5:  # <--- TIGHT TOLERANCE
                    cy = sum(p[1] for p in line)/len(line)
                    min_dist = min(min_dist, abs(cy - pos[1]))
            else:
                l_min_y, l_max_y = min(p[1] for p in line), max(p[1] for p in line)
                if l_min_y - 5 <= pos[1] <= l_max_y + 5:  # <--- TIGHT TOLERANCE
                    cx = sum(p[0] for p in line)/len(line)
                    min_dist = min(min_dist, abs(cx - pos[0]))
                    
        length = (max(all_x)-min(all_x)) if is_h else (max(all_y)-min(all_y))
        return length, res_lines, min_dist

    len_h, lines_h, dist_h = _grow(True)
    len_v, lines_v, dist_v = _grow(False)
    
    score_h = len_h / max(15.0, dist_h) if dist_h != float('inf') else 0
    score_v = len_v / max(15.0, dist_v) if dist_v != float('inf') else 0
    
    # Se ambos score 0, fallback puramente por comprimento
    if score_h == 0 and score_v == 0:
        is_horiz = len_h >= len_v
    else:
        is_horiz = score_h >= score_v
        
    return is_horiz, score_h, score_v, len_h, dist_h, len_v, dist_v

for t in texts:
    content = t['text'].strip()
    if re.match(r'^(V|VF|CONT)(\d+)[A-Z]?$', content) and content in ["V302", "V312", "V320", "V322", "V325", "V330", "V332", "V301", "V303"]:
        is_h, sh, sv, lh, dh, lv, dv = _grow_geometry(t['pos'])
        print(f"{content:5s}: {'HORIZ' if is_h else 'VERT '} | H(len={lh:.0f}, dist={dh:.1f}, score={sh:.1f}) | V(len={lv:.0f}, dist={dv:.1f}, score={sv:.1f})")
