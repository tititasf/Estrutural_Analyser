"""Debug: entender as linhas horizontais LONGAS que cruzam o Y de V302 (2683).
Se V302 é horizontal, devem existir linhas horizontais paralelas em y~2683 
que vão de x~1179 até x~4700+."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
lines = dxf_data.get("lines", [])
polys = dxf_data.get("polylines", [])

v302_y = 2683
tolerance = 80  # ±80u from V302 label Y

print(f"\nLinhas/polys horizontais (dx>100) com pontos em Y={v302_y}±{tolerance}:")
print(f"{'Type':6s}  {'X_range':20s}  {'Y_range':20s}  {'dx':>8s}  {'dy':>6s}")
print("-"*70)

count = 0
for line in lines:
    s, e = line["start"], line["end"]
    y_avg = (s[1] + e[1]) / 2
    if abs(y_avg - v302_y) < tolerance:
        dx = abs(e[0] - s[0])
        dy = abs(e[1] - s[1])
        if dx > 100 and dy < 5:  # horizontal long
            print(f"{'LINE':6s}  x=[{min(s[0],e[0]):.0f}, {max(s[0],e[0]):.0f}]{'':8s}  y=[{s[1]:.0f}, {e[1]:.0f}]{'':12s}  {dx:>8.0f}  {dy:>6.1f}")
            count += 1

for poly in polys:
    pts = poly.get("points", [])
    if len(pts) < 2:
        continue
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    y_avg = sum(ys) / len(ys)
    if abs(y_avg - v302_y) < tolerance:
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        if dx > 100 and dy < 40:  # horizontal poly
            print(f"{'POLY':6s}  x=[{min(xs):.0f}, {max(xs):.0f}]{'':8s}  y=[{min(ys):.0f}, {max(ys):.0f}]{'':12s}  {dx:>8.0f}  {dy:>6.1f}  npts={len(pts)}")
            count += 1

print(f"\nTotal: {count} linhas horizontais longas perto de V302 Y")

# Also check what the N2 says about V302 panel heights
# V302 has 6 panels, comp=2251.5. If panels are arranged horizontally,
# each panel would be ~375u. Let's see if horizontal lines are spaced ~375u apart.
