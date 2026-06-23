import sys
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dxf_loader import DXFLoader, RenderMode
from src.core.beam_tracer import BeamTracer
from src.core.spatial_index import SpatialIndex

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"
dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)

spatial_index = SpatialIndex()
for poly in dxf_data.get('polylines', []):
    pts = poly.get("points", [])
    if not pts: continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    spatial_index.insert(poly, (min(xs), min(ys), max(xs), max(ys)))

for line in dxf_data.get('lines', []):
    pts = line.get("points", [])
    if not pts: continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    spatial_index.insert(line, (min(xs), min(ys), max(xs), max(ys)))

for txt in dxf_data.get('texts', []):
    p = txt['pos']
    spatial_index.insert(txt, (p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5))

bt = BeamTracer(spatial_index)

beam_labels = []
for t in dxf_data.get('texts', []):
    content = t['text'].strip()
    if (content.startswith('V') or content.startswith('v') or content.upper().startswith('CONT') or content.startswith('VF')) and any(c.isdigit() for c in content):
        beam_labels.append(t)

orientations = {}
orientations_150 = {}

for b_text in beam_labels:
    content = b_text['text'].strip()
    pos = b_text['pos']
    
    # Original logic (60)
    cands_60 = bt.spatial_index.query_bbox((pos[0]-60, pos[1]-60, pos[0]+60, pos[1]+60))
    sum_h_60 = sum_v_60 = 0
    for cand in cands_60:
        if isinstance(cand, dict) and 'points' in cand:
            for i in range(len(cand['points'])-1):
                p1, p2 = cand['points'][i], cand['points'][i+1]
                dx = abs(p2[0]-p1[0])
                dy = abs(p2[1]-p1[1])
                if max(dx, dy) > 10:
                    if dx > dy: sum_h_60 += max(dx, dy)
                    else: sum_v_60 += max(dx, dy)
    
    # New logic (150)
    cands_150 = bt.spatial_index.query_bbox((pos[0]-150, pos[1]-150, pos[0]+150, pos[1]+150))
    sum_h_150 = sum_v_150 = 0
    for cand in cands_150:
        if isinstance(cand, dict) and 'points' in cand:
            for i in range(len(cand['points'])-1):
                p1, p2 = cand['points'][i], cand['points'][i+1]
                dx = abs(p2[0]-p1[0])
                dy = abs(p2[1]-p1[1])
                if max(dx, dy) > 10:
                    if dx > dy: sum_h_150 += max(dx, dy)
                    else: sum_v_150 += max(dx, dy)

    print(f"{content}: 60 -> H={sum_h_60:.0f} V={sum_v_60:.0f} ({sum_h_60 >= sum_v_60}) | 150 -> H={sum_h_150:.0f} V={sum_v_150:.0f} ({sum_h_150 >= sum_v_150})")
