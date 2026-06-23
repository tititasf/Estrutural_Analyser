import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
texts = dxf_data.get("texts", [])

v302_y = 2683
tolerance = 40

print(f"Labels in Y={v302_y}±{tolerance}:")
labels_in_strip = []
for txt in texts:
    pos = txt['pos']
    if abs(pos[1] - v302_y) < tolerance:
        content = txt['text'].strip()
        if (content.startswith('V') or content.upper().startswith('CONT')) and any(c.isdigit() for c in content):
            labels_in_strip.append((pos[0], content))

for x, label in sorted(labels_in_strip):
    print(f"  {label:10s} at X={x:.0f}")

