"""Script para gerar a renderização dos 3 casos de validação visual:
Caso 1: Estrutural Limpo (DXF cru)
Caso 2: Destaque Geral de TODAS as vigas (Fase 0 - Canais Mapeados em Ciano)
Caso 3: Destaque das Nossas Vigas e Vínculos (Fase 1 - Slotes/Vínculos em Laranja/Âmbar)
Caso 4: Painel Comparativo e Zoom Estrutural Cruzado
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import sqlite3
import re
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import LineCollection

from src.core.beam_interpreters.global_channel_extractor import GlobalBeamChannelExtractor
from src.core.spatial_index import SpatialIndex
from src.core.beam_tracer import BeamTracer
from scripts.analise_geral_headless import _filter_fv_visual_obstacles


def generate_3_cases():
    obra_name = "Obra_TREINO_1"
    pav_name = "13_PAV"
    
    # 1. Localizar DXF
    dxf_path = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA/torre_1.dxf")
    if not dxf_path.exists():
        dxf_path = Path("D:/Agente-cad-PYSIDE/ESTRUTURAL.dxf")
    
    print(f"[RENDER-3CASOS] Lendo DXF: {dxf_path}")
    doc = ezdxf.readfile(str(dxf_path))
    
    raw_lines = []
    plot_lines = []
    lines_list = []
    polys_list = []
    texts_list = []
    
    for entity in doc.modelspace():
        dtype = entity.dxftype()
        if dtype == "LINE":
            p1 = (entity.dxf.start.x, entity.dxf.start.y)
            p2 = (entity.dxf.end.x, entity.dxf.end.y)
            raw_lines.append([p1, p2])
            plot_lines.append([p1, p2])
            lines_list.append({"start": p1, "end": p2, "layer": entity.dxf.layer})
        elif dtype == "LWPOLYLINE":
            pts = [(v[0], v[1]) for v in entity.vertices()]
            if len(pts) >= 2:
                polys_list.append({"points": pts, "layer": entity.dxf.layer})
                for i in range(len(pts) - 1):
                    raw_lines.append([pts[i], pts[i+1]])
                    plot_lines.append([pts[i], pts[i+1]])
        elif dtype in ("TEXT", "MTEXT"):
            txt_str = entity.dxf.text if dtype == "TEXT" else entity.text
            pos = (entity.dxf.insert.x, entity.dxf.insert.y)
            texts_list.append({"text": txt_str, "pos": pos, "layer": entity.dxf.layer})

    print(f"[RENDER-3CASOS] Entidades extraídas: {len(plot_lines)} segmentos, {len(texts_list)} textos")
    
    # 2. Extrair Canais Globais (Fase 0 - Ciano)
    extractor = GlobalBeamChannelExtractor()
    mesh = extractor.extract_channel_mesh(raw_lines, raw_texts=texts_list)
    print(f"[RENDER-3CASOS] Slots de canais mapeados (Fase 0): {len(mesh.slots)}")
    
    # 3. Detectar Vigas e Contornos com BeamTracer (Fase 1 - Laranja)
    spatial_index = SpatialIndex()
    all_items = []
    for poly in polys_list:
        pts = poly["points"]
        bounds = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        spatial_index.insert(poly, bounds)
        all_items.append(poly)
    for line in lines_list:
        s, e = line["start"], line["end"]
        bounds = (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1]))
        spatial_index.insert(line, bounds)
        all_items.append({"points": [s, e]})
    for txt in texts_list:
        p = txt["pos"]
        spatial_index.insert(txt, (p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5))

    try:
        from scripts.motor_reverso_fv import _get_visual_obstacles
        visual_obstacles = _filter_fv_visual_obstacles(_get_visual_obstacles("13_PAV"))
    except Exception:
        visual_obstacles = []

    beam_tracer = BeamTracer(spatial_index)
    beams_found = beam_tracer.detect_beams(texts_list, all_items, visual_obstacles=visual_obstacles)
    print(f"[RENDER-3CASOS] Vigas detectadas pelo BeamTracer: {len(beams_found)}")

    # Extrair linhas e polígonos dos fundos de vigas (seg_bottom e merged_bottom_groups_coords)
    fundo_lines = []
    viga_labels = []
    
    for b in beams_found:
        name = b.get("name", "")
        if re.match(r"^[LlFf]\.", name) or re.match(r"^[LF]V-", name):
            continue
            
        b_pos = b.get("pos")
        if b_pos:
            viga_labels.append((name, b_pos))
            
        classified = b.get("geometry", {}).get("classified", {})
        seg_bottom = classified.get("seg_bottom", [])
        for seg in seg_bottom:
            if len(seg) >= 2:
                p1, p2 = seg[0], seg[1]
                fundo_lines.append([p1, p2])

    print(f"[RENDER-3CASOS] Linhas de fundo de viga extraídas (Fase 1): {len(fundo_lines)} em {len(viga_labels)} vigas")

    output_dir = Path("D:/Agente-cad-PYSIDE/validacao_visual_3casos")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Calculate bounds
    xs = [p[0] for line in plot_lines for p in line]
    ys = [p[1] for line in plot_lines for p in line]
    margin = 150
    xmin, xmax = min(xs) - margin, max(xs) + margin
    ymin, ymax = min(ys) - margin, max(ys) + margin
    
    # -------------------------------------------------------------
    # CASO 1: Estrutural Limpo
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 12), dpi=180)
    fig.patch.set_facecolor('#1a1a20')
    ax.set_facecolor('#1a1a20')
    
    lc = LineCollection(plot_lines, colors='#61afef', linewidths=0.5, alpha=0.8)
    ax.add_collection(lc)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect('equal')
    ax.set_title("CASO 1: Estrutural Limpo (DXF Cru Sem Marcações)", color='white', fontsize=18, fontweight='bold', pad=15)
    ax.axis('off')
    
    path_c1 = output_dir / "caso1_estrutural_limpo.png"
    plt.tight_layout()
    plt.savefig(path_c1, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[RENDER-3CASOS] Salvo: {path_c1}")
    
    # -------------------------------------------------------------
    # CASO 2: Destaque Geral de TODAS as Vigas (Fase 0 - Canais Teal)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 12), dpi=180)
    fig.patch.set_facecolor('#1a1a20')
    ax.set_facecolor('#1a1a20')
    
    lc = LineCollection(plot_lines, colors='#4b5263', linewidths=0.4, alpha=0.4)
    ax.add_collection(lc)
    
    for slot in mesh.slots:
        x0, y0, x1, y1 = slot.bbox
        rect = patches.Rectangle((x0, y0), x1 - x0, y1 - y0, linewidth=0.8, edgecolor='#00f5d4', facecolor='#00f5d4', alpha=0.35)
        ax.add_patch(rect)
        
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect('equal')
    ax.set_title(f"CASO 2: Destaque Geral de Canais de Vigas (Fase 0 - {len(mesh.slots)} Slots Mapeados)", color='#00f5d4', fontsize=18, fontweight='bold', pad=15)
    ax.axis('off')
    
    path_c2 = output_dir / "caso2_canais_fase0.png"
    plt.tight_layout()
    plt.savefig(path_c2, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[RENDER-3CASOS] Salvo: {path_c2}")

    # -------------------------------------------------------------
    # CASO 3: Destaque das Nossas Vigas e Vínculos (Fase 1 - Laranja/Âmbar)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 12), dpi=180)
    fig.patch.set_facecolor('#1a1a20')
    ax.set_facecolor('#1a1a20')
    
    lc = LineCollection(plot_lines, colors='#4b5263', linewidths=0.4, alpha=0.4)
    ax.add_collection(lc)
    
    lc_fundo = LineCollection(fundo_lines, colors='#ff9f1c', linewidths=3.0, alpha=0.95)
    ax.add_collection(lc_fundo)
    
    for name, (cx, cy) in viga_labels:
        ax.text(cx, cy, name, color='white', fontsize=7, fontweight='bold', ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#ff9f1c', alpha=0.85, edgecolor='none'))

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect('equal')
    ax.set_title(f"CASO 3: Vigas Preenchidas & Vínculos Finais (Fase 1 - {len(viga_labels)} Vigas / {len(fundo_lines)} Segmentos de Fundo)", color='#ff9f1c', fontsize=18, fontweight='bold', pad=15)
    ax.axis('off')
    
    path_c3 = output_dir / "caso3_vigas_vinculos_fase1.png"
    plt.tight_layout()
    plt.savefig(path_c3, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[RENDER-3CASOS] Salvo: {path_c3}")

    # -------------------------------------------------------------
    # CASO 4: Painel Comparativo Visão Cruzada (Tripla Visão + Zoom Detalhado)
    # -------------------------------------------------------------
    fig = plt.figure(figsize=(24, 15), dpi=180)
    fig.patch.set_facecolor('#121216')
    
    ax1 = fig.add_subplot(2, 3, 1)
    ax2 = fig.add_subplot(2, 3, 2)
    ax3 = fig.add_subplot(2, 3, 3)
    ax4 = fig.add_subplot(2, 1, 2)
    
    for ax_item in [ax1, ax2, ax3, ax4]:
        ax_item.set_facecolor('#1a1a20')
        ax_item.axis('off')
        
    # Ax1: Limpo
    ax1.add_collection(LineCollection(plot_lines, colors='#61afef', linewidths=0.4, alpha=0.7))
    ax1.set_xlim(xmin, xmax)
    ax1.set_ylim(ymin, ymax)
    ax1.set_aspect('equal')
    ax1.set_title("1. Estrutural Limpo (DXF Cru)", color='white', fontsize=14, fontweight='bold')
    
    # Ax2: Fase 0
    ax2.add_collection(LineCollection(plot_lines, colors='#4b5263', linewidths=0.3, alpha=0.4))
    for slot in mesh.slots:
        x0, y0, x1, y1 = slot.bbox
        ax2.add_patch(patches.Rectangle((x0, y0), x1 - x0, y1 - y0, linewidth=0.5, edgecolor='#00f5d4', facecolor='#00f5d4', alpha=0.4))
    ax2.set_xlim(xmin, xmax)
    ax2.set_ylim(ymin, ymax)
    ax2.set_aspect('equal')
    ax2.set_title(f"2. Fase 0: Canais Disponíveis ({len(mesh.slots)} Slots)", color='#00f5d4', fontsize=14, fontweight='bold')
    
    # Ax3: Fase 1
    ax3.add_collection(LineCollection(plot_lines, colors='#4b5263', linewidths=0.3, alpha=0.4))
    ax3.add_collection(LineCollection(fundo_lines, colors='#ff9f1c', linewidths=2.0, alpha=0.9))
    for name, (cx, cy) in viga_labels:
        ax3.text(cx, cy, name, color='white', fontsize=5, fontweight='bold', ha='center', va='center')
    ax3.set_xlim(xmin, xmax)
    ax3.set_ylim(ymin, ymax)
    ax3.set_aspect('equal')
    ax3.set_title(f"3. Fase 1: Vigas Preenchidas ({len(viga_labels)} Vigas)", color='#ff9f1c', fontsize=14, fontweight='bold')

    # Ax4: Zoom Visão Cruzada Overlay (Fase 0 + Fase 1 Sobrepostas)
    ax4.add_collection(LineCollection(plot_lines, colors='#abb2bf', linewidths=0.8, alpha=0.8))
    
    # Overlay Teal (Fase 0)
    for slot in mesh.slots:
        x0, y0, x1, y1 = slot.bbox
        ax4.add_patch(patches.Rectangle((x0, y0), x1 - x0, y1 - y0, linewidth=1.0, edgecolor='#00f5d4', facecolor='#00f5d4', alpha=0.25, linestyle='--'))
        
    # Overlay Orange (Fase 1)
    ax4.add_collection(LineCollection(fundo_lines, colors='#ff9f1c', linewidths=3.5, alpha=0.95))
    
    # Região central com maior densidade de vigas
    cx_all = (xmin + xmax) / 2
    cy_all = (ymin + ymax) / 2
    z_width = (xmax - xmin) * 0.45
    z_height = (ymax - ymin) * 0.45
    
    zx_min, zx_max = cx_all - z_width/2, cx_all + z_width/2
    zy_min, zy_max = cy_all - z_height/2, cy_all + z_height/2
    
    for name, (cx, cy) in viga_labels:
        if zx_min <= cx <= zx_max and zy_min <= cy <= zy_max:
            ax4.text(cx, cy, name, color='white', fontsize=8, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor='#1a1a20', alpha=0.85, edgecolor='#ff9f1c', linewidth=1))

    ax4.set_xlim(zx_min, zx_max)
    ax4.set_ylim(zy_min, zy_max)
    ax4.set_aspect('equal')
    ax4.set_title("ZOOM VISÃO CRUZADA: Sobreposição Fase 0 (Canais Teal Pontilhados) x Fase 1 (Segmentos de Fundo Laranja)", color='#61afef', fontsize=16, fontweight='bold', pad=10)

    path_c4 = output_dir / "caso4_comparacao_3casos.png"
    plt.tight_layout()
    plt.savefig(path_c4, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[RENDER-3CASOS] Salvo: {path_c4}")

    return str(path_c1), str(path_c2), str(path_c3), str(path_c4)

if __name__ == "__main__":
    generate_3_cases()
