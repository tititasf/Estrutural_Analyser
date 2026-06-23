"""Debug: mostrar quantas linhas o region growing captura por viga."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
from src.core.spatial_index import SpatialIndex
from src.core.beam_tracer import BeamTracer

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
for txt in texts:
    p = txt["pos"]
    spatial_index.insert(txt, (p[0]-5, p[1]-5, p[0]+5, p[1]+5))

all_lines_and_polys = []
for l in lines + polys:
    if "points" in l:
        all_lines_and_polys.append(l)
    elif "start" in l:
        all_lines_and_polys.append({"points": [l["start"], l["end"]]})

tracer = BeamTracer(spatial_index)

# Check 3 beams to see how many lines they each capture
sample_beams = ["V302", "V309", "VF203", "V301", "V332"]
for txt in texts:
    name = txt['text'].strip()
    if name in sample_beams:
        geo = tracer._find_beam_geometry(txt['pos'], all_lines_and_polys)
        n_lines = len(geo['lines'])
        seg_b = geo['classified']['seg_bottom']
        mbl = geo['classified'].get('merged_bottom_lengths', [])
        
        # Check bbox of all lines captured
        all_pts = [p for l in geo['lines'] for p in l]
        if all_pts:
            xmin = min(p[0] for p in all_pts)
            xmax = max(p[0] for p in all_pts)
            ymin = min(p[1] for p in all_pts)
            ymax = max(p[1] for p in all_pts)
            bbox_w = xmax - xmin
            bbox_h = ymax - ymin
        else:
            bbox_w = bbox_h = 0
        
        print(f"\n{name} @ ({txt['pos'][0]:.0f}, {txt['pos'][1]:.0f}):")
        print(f"  lines captured: {n_lines}  bbox: {bbox_w:.0f} x {bbox_h:.0f}")
        print(f"  seg_bottom: {len(seg_b)}  merged_lengths: {mbl}")
