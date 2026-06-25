import ezdxf
import sys
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')

import glob
files = glob.glob("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/**/FV_V303_motor_*.dxf", recursive=True)
doc = ezdxf.readfile(files[0])
msp = doc.modelspace()

polys = list(msp.query('LWPOLYLINE'))
poly_paineis = [p for p in polys if p.dxf.layer.upper() in ('PAINÉIS', 'PAINEIS')]

for i, p in enumerate(poly_paineis):
    pts = list(p.get_points())
    print(f"Poly {i} verts:")
    for pt in pts:
        print(f"  {pt[0]:.1f}, {pt[1]:.1f}")
    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    print(f"  Width: {max(xs) - min(xs):.1f}")
    print(f"  Height: {max(ys) - min(ys):.1f}")
