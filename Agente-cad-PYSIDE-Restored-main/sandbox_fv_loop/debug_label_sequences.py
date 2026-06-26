import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)

texts = dxf_data.get("texts", [])
for t in texts:
    text = t['text'].strip()
    if text.startswith('V'):
        if 1580 < t['pos'][0] < 1620:
            print(f"X~1600: {text} at Y={t['pos'][1]}")
        if 4200 < t['pos'][0] < 4250:
            print(f"X~4222: {text} at Y={t['pos'][1]}")
