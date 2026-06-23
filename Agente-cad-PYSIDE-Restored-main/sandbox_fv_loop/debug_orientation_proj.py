import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
from src.core.spatial_index import SpatialIndex

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
polys = dxf_data.get("polylines", [])

spatial_index = SpatialIndex()
for poly in polys:
    pts = poly.get("points", [])
    if pts:
        bounds = (min(p[0] for p in pts), min(p[1] for p in pts),
                  max(p[0] for p in pts), max(p[1] for p in pts))
        spatial_index.insert(poly, bounds)

def get_orientation_by_projection(pos):
    local_cands = spatial_index.query_bbox((pos[0]-150, pos[1]-150, pos[0]+150, pos[1]+150))
    h_wt = 0
    v_wt = 0
    
    for cand in local_cands:
        if isinstance(cand, dict) and 'points' in cand:
            pts = cand['points']
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            dx = max(xs) - min(xs)
            dy = max(ys) - min(ys)
            
            if max(dx, dy) > 20:
                if dx > dy:
                    # Horizontal: label X must be inside [min_x, max_x] + tolerance
                    if min(xs) - 10 <= pos[0] <= max(xs) + 10:
                        cy = sum(ys)/len(ys)
                        dist = max(1.0, abs(pos[1] - cy))
                        h_wt += dx / dist
                else:
                    # Vertical: label Y must be inside [min_y, max_y] + tolerance
                    if min(ys) - 10 <= pos[1] <= max(ys) + 10:
                        cx = sum(xs)/len(xs)
                        dist = max(1.0, abs(pos[0] - cx))
                        v_wt += dy / dist
                        
    return "HORIZ" if h_wt >= v_wt else "VERT", h_wt, v_wt

for name, pos in [("V302", (1201, 2683)), ("V332", (4690, 2668)), ("V309", (1173, 2310)), ("V301", (1213, 3014)), ("V312", (1600, 2695)), ("V320", (3348, 2695)), ("V322", (3785, 2695)), ("V325", (4222, 2695)), ("V330", (4528, 2695))]:
    ori, hw, vw = get_orientation_by_projection(pos)
    print(f"{name:5s}: {ori}  (H={hw:.1f}, V={vw:.1f})")
