import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
import ezdxf

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

for e in msp.query('TEXT'):
    if e.dxf.text in ["V302", "V312", "V320", "V322", "V325", "V330", "V332", "V301", "V303"]:
        print(f"{e.dxf.text}: halign={e.dxf.halign} valign={e.dxf.valign} width={e.dxf.width}")
