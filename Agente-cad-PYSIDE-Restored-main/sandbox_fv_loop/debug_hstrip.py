"""Debug: ver quais linhas do strip h estão sendo adicionadas para V302."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
from src.core.spatial_index import SpatialIndex

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
lines = dxf_data.get("lines", [])
polys = dxf_data.get("polylines", [])
texts = dxf_data.get("texts", [])

spatial_index = SpatialIndex()
for poly in polys:
    pts = poly.get("points", [])
    if pts:
        bounds = (min(p[0] for p in pts), min(p[1] for p in pts),
                  max(p[0] for p in pts), max(p[1] for p in pts))
        spatial_index.insert(poly, bounds)
for line in lines:
    s, e = line["start"], line["end"]
    bounds = (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1]))
    spatial_index.insert(line, bounds)

# V302 label pos
pos = (1201, 2683)
sweep_long = 800
sweep_trans = 40

# h_strip
h_strip = (pos[0] - sweep_long, pos[1] - sweep_trans,
           pos[0] + sweep_long, pos[1] + sweep_trans)
print(f"h_strip: x=[{h_strip[0]:.0f}, {h_strip[2]:.0f}]  y=[{h_strip[1]:.0f}, {h_strip[3]:.0f}]")

cands = spatial_index.query_bbox(h_strip)
line_cands = [c for c in cands if isinstance(c, dict) and 'points' in c]
print(f"Candidates in h_strip: {len(line_cands)}")

for c in line_cands:
    pts = c['points']
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    if dx > 50:  # horizontal significativa
        in_strip = any(h_strip[0] <= p[0] <= h_strip[2] and h_strip[1] <= p[1] <= h_strip[3] for p in pts)
        print(f"  HORIZ dx={dx:.0f} dy={dy:.0f} x=[{min(xs):.0f},{max(xs):.0f}] y=[{min(ys):.0f},{max(ys):.0f}] in_strip={in_strip}")
