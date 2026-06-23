import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
lines = dxf_data.get("lines", [])
polys = dxf_data.get("polylines", [])

v302_x = 1201
tolerance = 80

print(f"\nLinhas/polys verticais (dy>100) com pontos em X={v302_x}±{tolerance}:")
count = 0
for line in lines:
    s, e = line["start"], line["end"]
    x_avg = (s[0] + e[0]) / 2
    if abs(x_avg - v302_x) < tolerance:
        dx = abs(e[0] - s[0])
        dy = abs(e[1] - s[1])
        if dy > 100 and dx < 5:  
            print(f"LINE  x=[{s[0]:.0f}, {e[0]:.0f}]  y=[{min(s[1],e[1]):.0f}, {max(s[1],e[1]):.0f}]  dx={dx:.1f} dy={dy:.0f}")
            count += 1

for poly in polys:
    pts = poly.get("points", [])
    if len(pts) < 2:
        continue
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    x_avg = sum(xs) / len(xs)
    if abs(x_avg - v302_x) < tolerance:
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        if dy > 100 and dx < 40:  
            print(f"POLY  x=[{min(xs):.0f}, {max(xs):.0f}]  y=[{min(ys):.0f}, {max(ys):.0f}]  dx={dx:.1f} dy={dy:.0f}")
            count += 1

print(f"\nTotal: {count}")
