import os
import sys
from pathlib import Path
import json
import ezdxf
import numpy as np

workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

from src.core.spatial_index import SpatialIndex
from src.core.beam_tracer import BeamTracer
from src.core.learning.bottom_beam_learning_store import BottomBeamLearningStore
from src.core.learning.feedback_models import FeedbackEntry
from src.core.dxf_loader import DXFLoader
from datetime import datetime

def float_converter(obj):
    if isinstance(obj, (float, int)):
        return float(obj)
    if isinstance(obj, np.generic):
        return float(obj)
    return float(obj) # Force conversion, throw ValueError if not possible

def load_n2_truth():
    p = workspace_root / "scripts" / "n2_13pav_truth.json"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {item['viga']: item for item in data}

def process_tracer_on_dxf(dxf_path, store, viga_name):
    dxf_data = DXFLoader.load_dxf(str(dxf_path))
    
    index = SpatialIndex()
    for poly in dxf_data.get('polylines', []):
        pts = poly['points']
        min_x = min(p[0] for p in pts)
        max_x = max(p[0] for p in pts)
        min_y = min(p[1] for p in pts)
        max_y = max(p[1] for p in pts)
        index.insert(poly, (min_x, min_y, max_x, max_y))
        
    for line in dxf_data.get('lines', []):
        p1, p2 = line['start'], line['end']
        min_x, max_x = min(p1[0], p2[0]), max(p1[0], p2[0])
        min_y, max_y = min(p1[1], p2[1]), max(p1[1], p2[1])
        formatted_line = {'points': [p1, p2]}
        index.insert(formatted_line, (min_x, min_y, max_x, max_y))
        
    for txt in dxf_data.get('texts', []):
        p = txt['pos']
        index.insert(txt, (p[0], p[1], p[0], p[1]))
        
    params = store.get_learning_params()
    bt = BeamTracer(index, learning_params_bottom=params)
        
    # O DXFLoader usa 'text' e 'pos', que e o q o BeamTracer espera
    all_texts = dxf_data.get('texts', [])
    lines = dxf_data.get('lines', [])
    polys = dxf_data.get('polylines', [])
    all_lines_and_polys = []
    for l in lines + polys:
        if 'points' in l: all_lines_and_polys.append(l)
        elif 'start' in l: all_lines_and_polys.append({'points': [l['start'], l['end']]})
        
    beams_found = bt.detect_beams(all_texts, all_lines_and_polys)
    
    if not beams_found:
        return 0, []
        
    # Combina os resultados de todas as partes da viga espalhadas no desenho
    matched_cands = []
    for cand in beams_found:
        if viga_name in cand.get('name', ''):
            matched_cands.append(cand)
            
    if not matched_cands:
        return 0, []
        
    seg_longitudinais = []
    seen_centers = set()
    for cand in matched_cands:
        classified = cand.get('geometry', {}).get('classified', {})
        for seg in classified.get('seg_bottom', []):
            cx = round(sum(p[0] for p in seg) / len(seg), 1)
            cy = round(sum(p[1] for p in seg) / len(seg), 1)
            if (cx, cy) not in seen_centers:
                seen_centers.add((cx, cy))
                # Store the whole dictionary structure we need for merging later
                seg_longitudinais.append({
                    'line': seg,
                    'dx': max(p[0] for p in seg) - min(p[0] for p in seg),
                    'dy': max(p[1] for p in seg) - min(p[1] for p in seg)
                })
                
    # Agora refazemos o merge com as pecas deduplicadas (mesma logica do beam_tracer)
    medidas_tracer = []
    if seg_longitudinais:
        largest_seg = max(seg_longitudinais, key=lambda x: max(x['dx'], x['dy']))
        is_horizontal = largest_seg['dx'] > largest_seg['dy']
        if is_horizontal:
            seg_longitudinais.sort(key=lambda x: min(p[0] for p in x['line']))
            current_min = min(p[0] for p in seg_longitudinais[0]['line'])
            current_max = max(p[0] for p in seg_longitudinais[0]['line'])
            for i in range(1, len(seg_longitudinais)):
                item_min = min(p[0] for p in seg_longitudinais[i]['line'])
                item_max = max(p[0] for p in seg_longitudinais[i]['line'])
                if item_min - current_max <= 2.0:
                    current_max = max(current_max, item_max)
                else:
                    if current_max - current_min > 10.0:
                        medidas_tracer.append(current_max - current_min)
                    current_min = item_min
                    current_max = item_max
            if current_max - current_min > 10.0:
                medidas_tracer.append(current_max - current_min)
        else:
            seg_longitudinais.sort(key=lambda x: min(p[1] for p in x['line']))
            current_min = min(p[1] for p in seg_longitudinais[0]['line'])
            current_max = max(p[1] for p in seg_longitudinais[0]['line'])
            for i in range(1, len(seg_longitudinais)):
                item_min = min(p[1] for p in seg_longitudinais[i]['line'])
                item_max = max(p[1] for p in seg_longitudinais[i]['line'])
                if item_min - current_max <= 2.0:
                    current_max = max(current_max, item_max)
                else:
                    if current_max - current_min > 10.0:
                        medidas_tracer.append(current_max - current_min)
                    current_min = item_min
                    current_max = item_max
            if current_max - current_min > 10.0:
                medidas_tracer.append(current_max - current_min)
    return len(medidas_tracer), medidas_tracer

def run_real_training_loop():
    truth = load_n2_truth()
    
    target_dir = Path(r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes_reversos")
    fv_dir = None
    for d in target_dir.iterdir():
        if "13" in d.name and "FV" in d.name and "motor" not in d.name:
            fv_dir = d
            break
            
    dxf_files_all = list(fv_dir.glob("*.dxf"))
    latest_dxfs = {}
    for dxf in dxf_files_all:
        name_parts = dxf.stem.split('_')
        viga_name = ""
        for p in name_parts:
            if p.startswith('V') or p.startswith('VF'):
                viga_name = p
                break
        if not viga_name:
            viga_name = dxf.stem
            
        timestamp_part = name_parts[-1]
        try:
            ts = float(timestamp_part)
        except ValueError:
            ts = 0.0
            
        if viga_name not in latest_dxfs or ts > latest_dxfs[viga_name][1]:
            latest_dxfs[viga_name] = (dxf, ts)
            
    dxf_files = [item[0] for item in latest_dxfs.values()]
    
    # Loop de epocas
    for epoch in range(1, 6):
        print(f"\n{'='*50}\n🚀 ÉPOCA {epoch} - MOTOR CEGO VS N2 GABARITO\n{'='*50}")
        
        store = BottomBeamLearningStore(project_uuid="13_PAV_TRAINING")
        if epoch == 1:
            try: os.remove(store._get_file_path())
            except: pass
            
        params = store.get_learning_params()
        print(f"⚙️ Parâmetros do Cérebro: Sensibilidade={params.get('segmentation_sensitivity', 1.0):.2f}, Tolerância={params.get('gap_tolerance', 0.02):.2f}\n")
        print(f"{'VIGA':<8} | {'N2 SEGS':<8} | {'TRACER SEGS':<12} | {'STATUS':<6} | MEDIDAS TRACER")
        print("-" * 80)
        
        total_vigas = 0
        vigas_perfeitas = 0
        total_n2_segs = 0
        total_tracer_segs = 0
        total_dimensoes_batendo = 0
        
        for dxf in dxf_files:
            name_parts = dxf.stem.split('_')
            viga_name = ""
            for p in name_parts:
                if p.startswith('V') or p.startswith('VF'):
                    viga_name = p
                    break
            if not viga_name:
                viga_name = dxf.stem
                
            if viga_name not in truth:
                continue
                
            count_n2 = truth[viga_name]['segs']
            medidas_n2 = truth[viga_name]['medidas']
            
            count_tracer, medidas_tracer = process_tracer_on_dxf(dxf, store, viga_name)
            was_correct = (count_tracer == count_n2)
            
            total_vigas += 1
            total_n2_segs += count_n2
            total_tracer_segs += count_tracer
            
            medidas_n2_copy = list(medidas_n2)
            for mt in medidas_tracer:
                for i, mn in enumerate(medidas_n2_copy):
                    if abs(mt - mn) <= 2.0:
                        total_dimensoes_batendo += 1
                        medidas_n2_copy.pop(i)
                        break
                        
            todas_dimensoes_ok = (len(medidas_n2_copy) == 0 and len(medidas_tracer) == count_n2)
            if was_correct and todas_dimensoes_ok:
                vigas_perfeitas += 1
                status = "OK"
            else:
                status = "FALHA"
                
            entry = FeedbackEntry(
                class_type="bottom_beam",
                element_id=viga_name,
                field_name="segment_count",
                predicted_value=count_tracer,
                actual_value=count_n2,
                was_correct=(was_correct and todas_dimensoes_ok),
                confidence_at_prediction=0.8,
                context_signature={'teacher': 'eng_reversa_real'},
                timestamp=datetime.now().isoformat(),
                pavimento="13_PAV",
                project_uuid="13_PAV_TRAINING"
            )
            store.record_feedback(entry)
            print(f"{viga_name:<8} | {count_n2:<8} | {count_tracer:<12} | {status:<6} | {medidas_tracer}")
            
        print("-" * 80)
        perc_quantidade = (min(total_tracer_segs, total_n2_segs) / max(total_n2_segs, 1)) * 100
        perc_dimensao = (total_dimensoes_batendo / max(total_n2_segs, 1)) * 100
        perc_vigas = (vigas_perfeitas / max(total_vigas, 1)) * 100
        
        print(f"📊 RESULTADO ÉPOCA {epoch}:")
        print(f"   🎯 Quantidade de Segmentos Reconhecidos: {perc_quantidade:.1f}%")
        print(f"   📏 Similaridade de Dimensões (Match): {perc_dimensao:.1f}%")
        print(f"   🏆 Vigas 100% Idênticas (Perfeitas): {perc_vigas:.1f}% ({vigas_perfeitas}/{total_vigas})\n")
        
        if perc_vigas >= 95.0:
            print("🏆 REDE NEURAL ESTABILIZADA COM SUCESSO!")
            break

if __name__ == "__main__":
    try:
        run_real_training_loop()
    except TypeError:
        # Se falhar pelo JSON np.float, vamos recarregar e limpar
        p = workspace_root / "scripts" / "n2_13pav_truth.json"
        with open(p, "r", encoding="utf-8") as f:
            raw = f.read()
            raw = raw.replace("np.float64(", "").replace(")", "")
        with open(p, "w", encoding="utf-8") as f:
            f.write(raw)
        run_real_training_loop()
