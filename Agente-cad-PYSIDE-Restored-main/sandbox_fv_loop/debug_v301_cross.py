import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
polys = dxf_data.get("polylines", [])

print("--- Horizontal lines near V301 (X=1213, Y=3014) ---")
for poly in polys:
    pts = poly.get("points", [])
    if len(pts) < 2: continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    
    if max(xs) - min(xs) > 20 and max(ys) - min(ys) < 10:
        if 2950 < ys[0] < 3100:
            if min(xs) < 1300 and max(xs) > 1100:
                print(f"H-POLY X=[{min(xs):.0f}, {max(xs):.0f}] Y={ys[0]:.0f} dx={max(xs)-min(xs):.0f}")
