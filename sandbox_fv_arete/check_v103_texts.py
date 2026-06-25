import ezdxf

doc = ezdxf.readfile("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - TÉRREO - FV - R00/FV_V103_motor_178106121177.dxf")
msp = doc.modelspace()

print("V103 texts:")
for e in msp.query('TEXT MTEXT'):
    print(f"  '{e.dxf.text}' at x={e.dxf.insert.x:.1f} y={e.dxf.insert.y:.1f} layer={e.dxf.layer}")
