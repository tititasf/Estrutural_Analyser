import ezdxf

doc = ezdxf.readfile("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/FV_preview_V306_n4er.dxf")
msp = doc.modelspace()

texts = []
for entity in msp.query('TEXT MTEXT'):
    texts.append(entity.dxf.text)

for entity in msp.query('DIMENSION'):
    try:
        texts.append(str(entity.dxf.actual_measurement))
    except Exception:
        pass

for t in sorted(texts):
    if t and ('254' in t or '418' in t or '244' in t or '174' in t or 'ESQ' in t or 'DIR' in t or 'V306' in t):
        print(t)
