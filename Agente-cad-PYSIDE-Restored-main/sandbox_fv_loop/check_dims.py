import sys
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)

texts = dxf_data.get('texts', [])
print("DIMENSIONS NEAR V302 (Y ~ 2680):")
for t in texts:
    pos = t['pos']
    text = t['text'].strip()
    if 2600 < pos[1] < 2740:
        if re.match(r'^\d+([.,]\d+)?$', text):
            print(f"DIM: {text} at X={pos[0]:.0f}, Y={pos[1]:.0f}")

