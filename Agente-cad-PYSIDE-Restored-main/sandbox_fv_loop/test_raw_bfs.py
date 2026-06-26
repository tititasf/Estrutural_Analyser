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

for b in beam_labels:
    content = b['text'].strip()
    pos = b['pos']
    
    # RAW BFS
    visited = set()
    q = []
    
    # Seed
    seed_cands = bt.spatial_index.query_bbox((pos[0]-60, pos[1]-60, pos[0]+60, pos[1]+60))
    for s in seed_cands:
        if isinstance(s, dict) and 'points' in s:
            q.append(s)
            visited.add(id(s))
            
    all_x = []
    all_y = []
    
    while q and len(visited) < 1000:
        curr = q.pop(0)
        pts = curr['points']
        for p in pts:
            all_x.append(p[0])
            all_y.append(p[1])
            
        # só pegar 1 ponto representativo
        pt = pts[0]
        vizinhos = bt.spatial_index.query_bbox((pt[0]-400, pt[1]-400, pt[0]+400, pt[1]+400))
        for cand in vizinhos:
            if isinstance(cand, dict) and 'points' in cand:
                if id(cand) not in visited:
                    visited.add(id(cand))
                    q.append(cand)
                    
    if all_x and all_y:
        dx = max(all_x) - min(all_x)
        dy = max(all_y) - min(all_y)
        is_h = dx > dy
        print(f"{content}: dx={dx:.1f}, dy={dy:.1f} -> is_h={is_h}")
