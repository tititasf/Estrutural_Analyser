import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
texts = dxf_data.get("texts", [])

for name in ["V301", "V302", "V312", "V320", "V322", "V325", "V330", "V332"]:
    for t in texts:
        if t["text"].strip() == name:
            print(f"{name}: layer={t.get('layer')} rotation={t.get('rotation')} color={t.get('color')}")
