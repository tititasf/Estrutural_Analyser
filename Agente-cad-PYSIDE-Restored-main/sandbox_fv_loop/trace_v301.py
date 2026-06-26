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
for b_text in beam_labels:
    content = b_text['text'].strip()
    pos = b_text['pos']
    is_h = bt._determine_orientation(pos)
    orientations[content] = is_h

for b in beam_labels:
    if b['text'].strip() == 'V301':
        pos = b['pos']
        lines = bt._capture_geometry(pos, orientations['V301'], orientations, beam_labels, 'V301')
        print(f"RAW LINES CAPTURED: {len(lines)}")
        geo = bt._process_beam_geometry(pos, lines, [])
        valid_lines = []
        horizontal_weight = 0
        vertical_weight = 0
        for line in lines:
            if len(line) < 2: continue
            xs = [p[0] for p in line]
            ys = [p[1] for p in line]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            dx = max_x - min_x
            dy = max_y - min_y
            length = max(dx, dy)
            if length < 10: continue
            if dx > dy: 
                horizontal_weight += length
            else: 
                vertical_weight += length
        print(f"H-weight: {horizontal_weight}, V-weight: {vertical_weight}")
        print(f"is_horizontal = {horizontal_weight > vertical_weight}")
