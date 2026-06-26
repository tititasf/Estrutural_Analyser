import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
lines = dxf_data.get("lines", [])
polys = dxf_data.get("polylines", [])

print("--- Horizontal lines near V312 (X=1600, Y=2670) ---")
for poly in polys:
    pts = poly.get("points", [])
    if len(pts) < 2: continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    
    # Horizontal line
    if max(xs) - min(xs) > 20 and max(ys) - min(ys) < 10:
        if 2650 < ys[0] < 2700:
            if min(xs) < 1650 and max(xs) > 1550:
                print(f"H-POLY X=[{min(xs):.0f}, {max(xs):.0f}] Y={ys[0]:.0f}")

print("\n--- Vertical lines near V312 (X=1600, Y=2670) ---")
for poly in polys:
    pts = poly.get("points", [])
    if len(pts) < 2: continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    
    if max(ys) - min(ys) > 20 and max(xs) - min(xs) < 10:
        if 1580 < xs[0] < 1630:
            if min(ys) < 2720 and max(ys) > 2630:
                print(f"V-POLY Y=[{min(ys):.0f}, {max(ys):.0f}] X={xs[0]:.0f}")
