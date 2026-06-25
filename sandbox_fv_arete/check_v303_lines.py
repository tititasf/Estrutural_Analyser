import ezdxf
import glob
files = glob.glob("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/**/FV_V303_motor_*.dxf", recursive=True)
doc = ezdxf.readfile(files[0])
msp = doc.modelspace()
for e in msp.query('LINE'):
    if e.dxf.layer.upper() in ('PAINÉIS', 'PAINEIS', '5', '0'):
        print(f"LINE Layer {e.dxf.layer} - ({e.dxf.start.x:.1f}, {e.dxf.start.y:.1f}) to ({e.dxf.end.x:.1f}, {e.dxf.end.y:.1f})")
