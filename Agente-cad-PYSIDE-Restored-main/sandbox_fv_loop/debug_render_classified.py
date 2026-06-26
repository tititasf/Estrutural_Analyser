"""Debug: render das linhas capturadas por V302 e V310 para entender a geometria."""
import sys, math
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from src.core.dxf_loader import DXFLoader, RenderMode
from src.core.spatial_index import SpatialIndex
from src.core.beam_tracer import BeamTracer

DXF = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA\EL-(Torre-0)-(TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA)-(Obra_TREINO_1)_1.dxf"

dxf_data = DXFLoader.load_dxf(DXF, mode=RenderMode.TRUE_GEOMETRY)
lines = dxf_data.get("lines", [])
polys = dxf_data.get("polylines", [])
texts = dxf_data.get("texts", [])

spatial_index = SpatialIndex()
for poly in polys:
    pts = poly.get("points", [])
    if pts:
        bounds = (min(p[0] for p in pts), min(p[1] for p in pts),
                  max(p[0] for p in pts), max(p[1] for p in pts))
        spatial_index.insert(poly, bounds)
for line in lines:
    s, e = line["start"], line["end"]
    bounds = (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1]))
    spatial_index.insert(line, bounds)

all_lines_and_polys = []
for l in lines + polys:
    if "points" in l:
        all_lines_and_polys.append(l)
    elif "start" in l:
        all_lines_and_polys.append({"points": [l["start"], l["end"]]})

tracer = BeamTracer(spatial_index)

# Render para V302 e V310
for beam_name in ["V302", "V310"]:
    for txt in texts:
        if txt['text'].strip() == beam_name:
            pos = txt['pos']
            geo = tracer._find_beam_geometry(pos, all_lines_and_polys)
            raw_lines = geo['lines']
            classified = geo['classified']
            
            fig, ax = plt.subplots(1, 1, figsize=(16, 12), facecolor='#0a0a14')
            ax.set_facecolor('#0a0a14')
            
            # Desenhar todas as linhas capturadas em cinza
            all_segs = []
            for l in raw_lines:
                for i in range(len(l)-1):
                    all_segs.append([l[i], l[i+1]])
            if all_segs:
                ax.add_collection(LineCollection(all_segs, colors='#444466', linewidths=0.8))
            
            # seg_side_a em verde
            side_a_segs = []
            for l in classified['seg_side_a']:
                for i in range(len(l)-1):
                    side_a_segs.append([l[i], l[i+1]])
            if side_a_segs:
                ax.add_collection(LineCollection(side_a_segs, colors='#00ff88', linewidths=1.5, label='side_a'))
            
            # seg_side_b em azul
            side_b_segs = []
            for l in classified['seg_side_b']:
                for i in range(len(l)-1):
                    side_b_segs.append([l[i], l[i+1]])
            if side_b_segs:
                ax.add_collection(LineCollection(side_b_segs, colors='#4488ff', linewidths=1.5, label='side_b'))
            
            # seg_bottom em vermelho
            bottom_segs = []
            for l in classified['seg_bottom']:
                for i in range(len(l)-1):
                    bottom_segs.append([l[i], l[i+1]])
            if bottom_segs:
                ax.add_collection(LineCollection(bottom_segs, colors='#ff4444', linewidths=2.5, label='bottom'))
            
            # Label
            ax.plot(pos[0], pos[1], 'o', color='yellow', markersize=8)
            ax.annotate(beam_name, (pos[0], pos[1]), color='yellow', fontsize=12,
                       xytext=(5, 5), textcoords='offset points', fontweight='bold')
            
            # Containment box
            contain_r = 500
            rect_pts = [
                [pos[0]-contain_r, pos[1]-contain_r],
                [pos[0]+contain_r, pos[1]-contain_r],
                [pos[0]+contain_r, pos[1]+contain_r],
                [pos[0]-contain_r, pos[1]+contain_r],
                [pos[0]-contain_r, pos[1]-contain_r],
            ]
            ax.plot([p[0] for p in rect_pts], [p[1] for p in rect_pts], '--', color='#ffaa00', linewidth=1, alpha=0.5)
            
            ax.set_aspect('equal')
            ax.axis('off')
            ax.set_title(f'{beam_name}: {len(raw_lines)} lines | side_a={len(classified["seg_side_a"])} side_b={len(classified["seg_side_b"])} bottom={len(classified["seg_bottom"])} | mbl={classified.get("merged_bottom_lengths",[])}',
                        color='white', fontsize=10)
            ax.autoscale()
            
            out = ROOT / "sandbox_fv_loop" / f"debug_{beam_name}_classified.png"
            fig.savefig(str(out), dpi=130, bbox_inches='tight', facecolor='#0a0a14')
            plt.close(fig)
            print(f"Saved: {out}")
            break
