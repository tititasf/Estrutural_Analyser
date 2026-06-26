import sys
import os
from pathlib import Path
sys.path.append('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main')
from src.core.database import DatabaseManager

db = DatabaseManager('D:/Agente-cad-PYSIDE/project_data.vision')
works = db.get_all_works()
print("Works from DB:", len(works))
print(works[:10])

dados_obras = Path('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/DADOS-OBRAS')
if dados_obras.exists():
    fs_works = [d.name for d in dados_obras.iterdir() if d.is_dir()]
    print("Works from DADOS-OBRAS:", len(fs_works))
    print(fs_works[:10])
else:
    print("DADOS-OBRAS does not exist.")
