import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
lines = dxf_data.get("lines", [])
polys = dxf_data.get("polylines", [])

for name, x_center in [("V312", 1600), ("V320", 3348), ("V322", 3785)]:
    print(f"\n--- {name} at X={x_center} ---")
    for poly in polys:
        pts = poly.get("points", [])
        if len(pts) < 2: continue
        ys = [p[1] for p in pts]
        xs = [p[0] for p in pts]
        x_avg = sum(xs) / len(xs)
        if abs(x_avg - x_center) < 40:
            dx = max(xs) - min(xs)
            dy = max(ys) - min(ys)
            if dy > 50 and dx < 40:  
                print(f"VERT POLY x=[{min(xs):.0f}, {max(xs):.0f}]  y=[{min(ys):.0f}, {max(ys):.0f}]")
