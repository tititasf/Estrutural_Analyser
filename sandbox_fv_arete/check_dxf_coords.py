import ezdxf

doc = ezdxf.readfile("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/FV_preview_V306_n4er.dxf")
msp = doc.modelspace()

x_coords = set()
for entity in msp.query('LINE'):
    x_coords.add(round(entity.dxf.start[0], 2))
    x_coords.add(round(entity.dxf.end[0], 2))

print("X coords:", sorted(list(x_coords)))
