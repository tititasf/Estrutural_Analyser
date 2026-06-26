import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
import ezdxf

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

texts = []
for e in msp.query('TEXT'):
    text = e.dxf.text.strip()
    if text.startswith('V'):
        texts.append({'name': text, 'pos': (e.dxf.insert.x, e.dxf.insert.y)})

print("--- Checking sequences ---")
for t in texts:
    if t['name'] in ["V312", "V320", "V322", "V302", "V325", "V330", "V301", "V332"]:
        x, y = t['pos']
        v_seq = [other['name'] for other in texts if abs(other['pos'][0] - x) < 40 and other['name'] != t['name']]
        h_seq = [other['name'] for other in texts if abs(other['pos'][1] - y) < 40 and other['name'] != t['name']]
        print(f"{t['name']:5s}: V_SEQ={v_seq} | H_SEQ={h_seq}")
