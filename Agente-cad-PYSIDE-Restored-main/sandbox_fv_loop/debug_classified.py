"""Debug: entender a geometria local de vigas-chave (V302, V310, V319)"""
import sys, json, math
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

# Para V302, V310, V319 - investigar classified em detalhe
sample_beams = ["V302", "V310", "V319", "V309"]
for txt in texts:
    name = txt['text'].strip()
    if name in sample_beams:
        geo = tracer._find_beam_geometry(txt['pos'], all_lines_and_polys)
        classified = geo['classified']
        seg_b = classified['seg_bottom']
        mbl = classified.get('merged_bottom_lengths', [])
        
        print(f"\n{'='*60}")
        print(f"{name} @ ({txt['pos'][0]:.0f}, {txt['pos'][1]:.0f}):")
        print(f"  total lines: {len(geo['lines'])}")
        print(f"  seg_side_a: {len(classified['seg_side_a'])}")
        print(f"  seg_side_b: {len(classified['seg_side_b'])}")
        print(f"  seg_bottom: {len(seg_b)}")
        print(f"  merged_bottom_lengths: {mbl}")
        
        # Mostrar cada seg_bottom em detalhe
        for i, s in enumerate(seg_b):
            xs = [p[0] for p in s]
            ys = [p[1] for p in s]
            dx = max(xs) - min(xs)
            dy = max(ys) - min(ys)
            is_closed = len(s) >= 4 and math.sqrt((s[0][0]-s[-1][0])**2 + (s[0][1]-s[-1][1])**2) < 5.0
            print(f"  seg_bottom[{i}]: {len(s)} pts, dx={dx:.1f} dy={dy:.1f} closed={is_closed} xrange=[{min(xs):.0f},{max(xs):.0f}] yrange=[{min(ys):.0f},{max(ys):.0f}]")
        
        # N2 esperado
        if name == "V302":
            print(f"  N2: 6 panels, comp=2251.5")
        elif name == "V310":
            print(f"  N2: 1 panel, comp=152.0")
        elif name == "V319":
            print(f"  N2: 1 panel, comp=351.0")
        elif name == "V309":
            print(f"  N2: 1 panel, comp=320.0")

        # Verificar dimension texts capturados
        dim_texts = geo.get('dimension_texts', [])
        print(f"  dimension_texts ({len(dim_texts)}):")
        for dt in dim_texts[:5]:
            print(f"    '{dt.get('text', '')}' @ ({dt.get('pos', [0,0])[0]:.0f}, {dt.get('pos', [0,0])[1]:.0f})")
