
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path('scripts/arete').resolve()))
from ficha_adapter import query_fichas

for row in query_fichas('PIL', '13_PAV'):
    if row['elemento_id'] == 'P2':
        print(json.dumps(row['campos_json'], indent=2))

