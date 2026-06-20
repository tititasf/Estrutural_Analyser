import ezdxf
import glob
files = glob.glob("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/**/FV_V303_motor_*.dxf", recursive=True)
doc = ezdxf.readfile(files[0])
msp = doc.modelspace()
for e in msp.query('HATCH SOLID'):
    print(f"HATCH/SOLID Layer {e.dxf.layer}")
