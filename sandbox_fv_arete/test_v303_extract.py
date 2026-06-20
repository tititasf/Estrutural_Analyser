import sys
import glob
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')
import ezdxf
from motor_reverso_fv import _extract_fv_from_geometry

files = glob.glob("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/**/FV_V303_motor_*.dxf", recursive=True)
doc = ezdxf.readfile(files[0])
res = _extract_fv_from_geometry(doc.modelspace(), 'V303')
print("Extracted:")
print(res)
