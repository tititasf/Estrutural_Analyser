import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
texts = dxf_data.get("texts", [])

rotations = set()
for txt in texts:
    rotations.add(txt.get('rotation', 0))

print(f"Unique rotations found in all texts: {rotations}")

vert_beams = []
horiz_beams = []
for txt in texts:
    content = txt['text'].strip()
    if content.startswith('V') and any(c.isdigit() for c in content):
        rot = txt.get('rotation', 0)
        if abs(rot - 90) < 5 or abs(rot - 270) < 5:
            vert_beams.append(content)
        else:
            horiz_beams.append(content)

print(f"Vertical beams (by text rotation): {vert_beams}")
print(f"Horizontal beams (by text rotation): {horiz_beams[:20]}...")
