import ezdxf
import glob
files = glob.glob("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/**/FV_V303_motor_*.dxf", recursive=True)
doc = ezdxf.readfile(files[0])
msp = doc.modelspace()
for e in msp.query('TEXT MTEXT DIMENSION'):
    if e.dxftype() in ('TEXT', 'MTEXT'):
        if e.dxf.text in ('19', '29', '49', '193'):
            print(f"{e.dxftype()} Layer {e.dxf.layer} text '{e.dxf.text}'")
    else:
        print(f"DIMENSION Layer {e.dxf.layer}")
