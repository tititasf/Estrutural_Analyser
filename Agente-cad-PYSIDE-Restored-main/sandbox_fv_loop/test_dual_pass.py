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

for b in beam_labels:
    content = b['text'].strip()
    pos = b['pos']
    
    # 1. Run as Horizontal
    lines_h = bt._capture_geometry(pos, True, {}, beam_labels, content)
    geo_h = bt._process_beam_geometry(pos, lines_h, True)
    lengths_h = bt._group_bottom_lengths(geo_h['classified']['seg_bottom'], True)
    score_h = sum(lengths_h)
    
    # 2. Run as Vertical
    lines_v = bt._capture_geometry(pos, False, {}, beam_labels, content)
    geo_v = bt._process_beam_geometry(pos, lines_v, False)
    lengths_v = bt._group_bottom_lengths(geo_v['classified']['seg_bottom'], False)
    score_v = sum(lengths_v)
    
    # Determine winner
    is_h = score_h >= score_v
    print(f"{content}: H={score_h:.1f}, V={score_v:.1f} -> is_h={is_h}")

