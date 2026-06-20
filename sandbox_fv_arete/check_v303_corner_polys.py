import ezdxf
import glob
files = glob.glob("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/**/FV_V303_motor_*.dxf", recursive=True)
doc = ezdxf.readfile(files[0])
msp = doc.modelspace()
for e in msp.query('LWPOLYLINE POLYLINE'):
    pts = list(e.get_points()) if e.dxftype() == 'LWPOLYLINE' else [v.dxf.location for v in e.vertices]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    # Check if this might be the L-corner at the end of the 174-wide panel (which ends at x=4450.7 or starts there)
    if min(xs) >= 4450.0 and max(xs) <= 4500.0:
        print(f"L-corner candidate: Layer {e.dxf.layer} - X: {min(xs):.1f} to {max(xs):.1f}, Y: {min(ys):.1f} to {max(ys):.1f}")
