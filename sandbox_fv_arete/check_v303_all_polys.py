import ezdxf
import glob
files = glob.glob("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/**/FV_V303_motor_*.dxf", recursive=True)
doc = ezdxf.readfile(files[0])
msp = doc.modelspace()
for e in msp.query('LWPOLYLINE'):
    if e.dxf.layer.upper() in ('PAINÉIS', 'PAINEIS', '5', '0'):
        pts = list(e.get_points())
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        print(f"Layer {e.dxf.layer} - X: {min(xs):.1f} to {max(xs):.1f}, Y: {min(ys):.1f} to {max(ys):.1f}")
