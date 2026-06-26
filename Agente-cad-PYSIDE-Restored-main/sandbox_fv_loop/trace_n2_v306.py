import sys
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.fv_loop_runner import load_n2_fv

n2 = load_n2_fv("Obra_TREINO_1", "13", Path("D:/Agente-cad-PYSIDE/project_data.vision"))
for elem_id, campos in n2.items():
    if "V306" in elem_id or (campos.get("Viga") == "V306"):
        print(f"{elem_id}: {campos}")
