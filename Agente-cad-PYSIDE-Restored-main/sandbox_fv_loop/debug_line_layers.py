import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)

lines = dxf_data.get("lines", [])
polys = dxf_data.get("polylines", [])

print("--- Lines near V312 (X=1600, Y=2695) ---")
for e in lines + polys:
    pts = e.get("points", [])
    if not pts: continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    
    # Line passes through the 100x100 box
    if min(xs) < 1650 and max(xs) > 1550 and min(ys) < 2750 and max(ys) > 2650:
        print(f"{e.get('type')}: layer={e.get('layer')} color={e.get('color')} pts={len(pts)} dx={max(xs)-min(xs):.0f} dy={max(ys)-min(ys):.0f}")
