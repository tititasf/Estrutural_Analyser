import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)

lines = dxf_data.get("lines", [])
polys = dxf_data.get("polylines", [])

for e in lines + polys:
    pts = e.get("points", [])
    if not pts: continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    
    if min(xs) - 5 <= 4690 <= max(xs) + 5 and max(xs) - min(xs) > 20 and max(ys) - min(ys) < 10:
        print(f"H-LINE: X=[{min(xs):.0f}, {max(xs):.0f}] Y=[{min(ys):.0f}, {max(ys):.0f}] pts={len(pts)}")
