import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import sqlite3
import ezdxf
from src.core.beam_interpreters.global_channel_extractor import GlobalBeamChannelExtractor
from src.core.beam_interpreters.channel_confidence_scorer import ChannelConfidenceScorer

db_path = "D:/Agente-cad-PYSIDE/project_data.vision"
dxf_path = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA/torre_1.dxf"

doc = ezdxf.readfile(dxf_path)
raw_lines = []
raw_texts = []
for entity in doc.modelspace():
    dtype = entity.dxftype()
    layer = getattr(entity.dxf, 'layer', '')
    if dtype == "LINE":
        raw_lines.append({"points": [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)], "layer": layer})
    elif dtype == "LWPOLYLINE":
        pts = list(entity.vertices())
        if len(pts) >= 2:
            for i in range(len(pts) - 1):
                raw_lines.append({"points": [(pts[i][0], pts[i][1]), (pts[i+1][0], pts[i+1][1])], "layer": layer})
    elif dtype in ("TEXT", "MTEXT"):
        txt = entity.dxf.text if dtype == "TEXT" else entity.text
        pos = (entity.dxf.insert.x, entity.dxf.insert.y)
        raw_texts.append({"text": txt, "pos": pos, "layer": layer})

extractor = GlobalBeamChannelExtractor()
mesh_fase0 = extractor.extract_channel_mesh(raw_lines, raw_texts=raw_texts)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, name, data_json, links_json FROM beams WHERE project_id = '4869be2b-f17c-410b-a9c8-98a887ec1c95'")
beams_db = cursor.fetchall()
conn.close()

scorer = ChannelConfidenceScorer()
results = []

for b_id, b_name, d_json, l_json in beams_db:
    data = json.loads(d_json) if d_json else {}
    links = json.loads(l_json) if l_json else {}
    width = float(data.get("largura") or data.get("width") or 19.0)
    is_horiz = bool(data.get("is_horizontal", True))
    
    contours = []
    if "contour" in links and isinstance(links["contour"], list):
        contours.extend(links["contour"])
    for k, v in links.items():
        if "viga_fundo" in k and isinstance(v, dict):
            c_list = v.get("contour", [])
            if isinstance(c_list, list):
                contours.extend(c_list)
                
    for idx, c in enumerate(contours):
        pts = c.get("points", [])
        if len(pts) >= 4:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            score_res = scorer.score_segment(bbox, width, is_horiz, mesh_fase0)
            results.append((b_name, idx, score_res))

print("==========================================================================================")
print("--- SISTEMA DE CONFIAVILIDADE E TELEMETRIA: CANAL CONFIDENCE SCORE (FASE 0 x VIGAS DB) ---")
print("==========================================================================================")
high_cnt = sum(1 for r in results if r[2].status_flag == 'HIGH_CONFIDENCE')
mod_cnt = sum(1 for r in results if r[2].status_flag == 'MODERATE_CONFIDENCE')
warn_offset = sum(1 for r in results if r[2].status_flag == 'WARNING_OFFSET')
warn_width = sum(1 for r in results if r[2].status_flag == 'WARNING_WIDTH')
unsupp_cnt = sum(1 for r in results if r[2].status_flag == 'UNSUPPORTED')

print(f"Total de Segmentos Avaliados: {len(results)}")
print(f"  [ALTA CONFIANCA] (Score >= 0.75): {high_cnt}")
print(f"  [MODERADA CONFIANCA] (0.20 <= Score < 0.75): {mod_cnt}")
print(f"  [ALERTA OFFSET] (Deslocamento Transversal > 5cm): {warn_offset}")
print(f"  [ALERTA LARGURA] (Delta de Largura > 1.5cm): {warn_width}")
print(f"  [SEM SUPORTE CANAL]: {unsupp_cnt}\n")

print("Amostra de Pontuacoes de Confianca por Viga:")
for b_name, idx, res in sorted(results, key=lambda x: x[0])[:15]:
    cota_str = f" [Cota: {res.dim_text_matched}]" if res.dim_text_matched else ""
    print(f"  Viga {b_name:<6} (slot #{idx}): Score = {res.confidence_score:.3f} | Status = {res.status_flag:<19} | Overlap = {res.axial_overlap_ratio*100:.0f}% | Offset = {res.transverse_offset_cm}cm{cota_str}")
