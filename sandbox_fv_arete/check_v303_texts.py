import ezdxf
import glob
files = glob.glob("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/**/FV_V303_motor_*.dxf", recursive=True)
doc = ezdxf.readfile(files[0])
msp = doc.modelspace()
for t in msp.query('TEXT MTEXT'):
    if '303' in t.dxf.text.upper() or 'CONT' in t.dxf.text.upper() or 'L' in t.dxf.text.upper():
        print(f"Text: '{t.dxf.text}' at ({t.dxf.insert.x:.1f}, {t.dxf.insert.y:.1f}) rot={getattr(t.dxf, 'rotation', 0)}")
