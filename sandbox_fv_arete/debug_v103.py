import ezdxf
import sys
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')
from motor_reverso_fv import _extract_fv_from_geometry, _poly_bboxes, _base_code, _nomenclatura_labels, _elem_codes

doc = ezdxf.readfile("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - TÉRREO - FV - R00/FV_V103_motor_178106121177.dxf")
msp = doc.modelspace()

polys = _poly_bboxes(msp)
print(f"Total polys: {len(polys)}")

target = _base_code('V103').upper()
noms = _nomenclatura_labels(msp)
print(f"Target: {target}")
print(f"Noms: {noms}")

own = [n for n in noms if target in _elem_codes(n[0])]
print(f"Own: {own}")
