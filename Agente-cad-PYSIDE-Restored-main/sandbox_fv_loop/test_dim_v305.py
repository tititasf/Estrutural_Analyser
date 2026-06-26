import sys
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
from src.core.spatial_index import SpatialIndex

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)

spatial_index = SpatialIndex()
for txt in dxf_data.get('texts', []):
    p = txt['pos']
    spatial_index.insert(txt, (p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5))

beam_labels = []
for t in dxf_data.get('texts', []):
    content = t['text'].strip()
    if (content.startswith('V') or content.startswith('v') or content.upper().startswith('CONT') or content.startswith('VF')) and any(c.isdigit() for c in content):
        beam_labels.append(t)

for b in beam_labels:
    content = b['text'].strip()
    if content == 'V305':
        pos = b['pos']
        cands = spatial_index.query_bbox((pos[0]-300, pos[1]-300, pos[0]+300, pos[1]+300))
        best_dim = None
        min_d = float('inf')
        
        for cand in cands:
            if isinstance(cand, dict) and 'text' in cand:
                t = cand['text'].strip()
                m = re.search(r"(\d+(?:\.\d+)?)\s*[/xX]\s*(\d+(?:\.\d+)?)", t)
                if m:
                    cp = cand['pos']
                    d = abs(cp[0]-pos[0]) + abs(cp[1]-pos[1])
                    if d < min_d:
                        min_d = d
                        best_dim = t
                        first = float(m.group(1))
                        second = float(m.group(2))
                        h = min(first, second)
        print(f"V305: found {best_dim} -> h={h} (dist={min_d:.1f})")
