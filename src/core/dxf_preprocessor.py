import logging
import json
import uuid
import math
from typing import List, Dict, Any, Tuple

class DXFPreprocessor:
    """
    Engine para tratamento prévio de DXF (Marco de Obra).
    Identifica vigas de extremidade, estende 10cm e fecha o contorno (Marco).
    """
    
    def __init__(self, spatial_index, memory):
        self.spatial_index = spatial_index
        self.memory = memory
        self.logger = logging.getLogger("DXFPreprocessor")

    def run_marco_analysis(self, dxf_data: Dict, project_id: str) -> Dict:
        """
        Executa a análise de marco:
        1. Calcula Bounding Box global.
        2. Detecta linhas que tocam/terminam no limite.
        3. Estende 10cm.
        4. Cria polígono de fechamento (Marco).
        """
        if not dxf_data:
            return {"extensions": [], "marco": [], "links": {}}

        lines = dxf_data.get('lines', [])
        polylines = dxf_data.get('polylines', [])
        all_segments = []
        
        # Unificar segmentos para análise geométrica
        for l in lines:
            all_segments.append({'points': [l['start'], l['end']], 'layer': l.get('layer', '')})
        for pl in polylines:
            pts = pl.get('points', [])
            for i in range(len(pts)-1):
                all_segments.append({'points': [pts[i], pts[i+1]], 'layer': pl.get('layer', '')})

        if not all_segments:
            return {"extensions": [], "marco": [], "links": {}}

        # 1. Bounding Box Global
        min_x = min(min(p[0] for p in s['points']) for s in all_segments)
        max_x = max(max(p[0] for p in s['points']) for s in all_segments)
        min_y = min(min(p[1] for p in s['points']) for s in all_segments)
        max_y = max(max(p[1] for p in s['points']) for s in all_segments)
        
        bbox = (min_x, min_y, max_x, max_y)
        threshold = 5.0 # Margem para considerar "no limite" (5cm)
        margin_extension = 10.0 # Extensão de 10cm

        extensions = []
        outer_points = [] # Pontos estendidos que formarão o marco
        vigas_extremidade = [] # Segmentos originais que tocam o limite

        # 2. Identificar pontas de vigas no limite
        # Heurística: se um ponto está muito perto do min/max X ou Y, é candidato.
        for seg in all_segments:
            p1, p2 = seg['points']
            
            # Verificar p1
            is_p1_at_boundary = (abs(p1[0] - min_x) < threshold or abs(p1[0] - max_x) < threshold or
                                 abs(p1[1] - min_y) < threshold or abs(p1[1] - max_y) < threshold)
            # Verificar p2
            is_p2_at_boundary = (abs(p2[0] - min_x) < threshold or abs(p2[0] - max_x) < threshold or
                                 abs(p2[1] - min_y) < threshold or abs(p2[1] - max_y) < threshold)

            # Se apenas UMA ponta está no limite, é uma viga saindo para fora (ou chegando)
            if is_p1_at_boundary != is_p2_at_boundary:
                boundary_pt = p1 if is_p1_at_boundary else p2
                inner_pt = p2 if is_p1_at_boundary else p1
                
                # Calcular direção da extensão (do inner para o boundary)
                dx = boundary_pt[0] - inner_pt[0]
                dy = boundary_pt[1] - inner_pt[1]
                dist = math.sqrt(dx*dx + dy*dy)
                if dist < 0.001: continue
                
                ux, uy = dx/dist, dy/dist
                
                # Ponto estendido (Aprox 10cm, arredondando comprimento total para inteiro)
                original_viga_len = dist
                target_total_len = original_viga_len + 10.0
                final_total_len = round(target_total_len)
                actual_extension_len = final_total_len - original_viga_len
                
                # Ponto estendido real
                ext_pt = [boundary_pt[0] + ux * actual_extension_len, boundary_pt[1] + uy * actual_extension_len]
                
                ext_id = str(uuid.uuid4())[:8]
                ext_obj = {
                    'id': ext_id,
                    'original_points': [boundary_pt, ext_pt],
                    'points': [boundary_pt, ext_pt],
                    'type': 'extension_10cm',
                    'len': actual_extension_len,
                    'total_viga_len': final_total_len,
                    'original_viga_len': original_viga_len
                }
                extensions.append(ext_obj)
                outer_points.append(ext_pt)
                
                # Registrar a viga de extremidade individualizada
                v_ext = {
                    'id': ext_id, # Mesmo ID para parear na tabela
                    'type': 'line',
                    'points': [inner_pt, boundary_pt],
                    'text': f'Viga {ext_id}',
                    'original_len': original_viga_len,
                    'extension_len': actual_extension_len,
                    'final_len': final_total_len
                }
                vigas_extremidade.append(v_ext)

        # 3. Criar o Marco (Unindo os pontos outer de forma ordenada)
        # Ordenação por ângulo em relação ao centro do bounding box para formar um contorno simples
        marco_lines = []
        if len(outer_points) >= 2:
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            
            def get_angle(p):
                return math.atan2(p[1] - center_y, p[0] - center_x)
            
            # Remover duplicatas próximas
            unique_outer = []
            for p in outer_points:
                if not any(math.dist(p, up) < 1.0 for up in unique_outer):
                    unique_outer.append(p)
                    
            unique_outer.sort(key=get_angle)
            
            for i in range(len(unique_outer)):
                p_start = unique_outer[i]
                p_end = unique_outer[(i + 1) % len(unique_outer)]
                marco_lines.append({
                    'points': [p_start, p_end],
                    'type': 'marco_union'
                })

        # 4. Estruturar Vínculos
        # Novo formato: vigas_individuais para suportar a tabela no DetailCard
        links_dict = {
            'unioes_marco': {
                'default': [{'type': 'line', 'points': ml['points'], 'text': 'União'} for ml in marco_lines]
            }
        }
        
        # Popular links individuais para cada viga para aparecer no LinkManager
        for v in vigas_extremidade:
            v_id = v.get('id')
            links_dict[f"ext_viga_{v_id}"] = {
                'default': [{'type': 'line', 'points': v['points'], 'text': f'Ajuste {v_id[:4]}'}]
            }

        marco_item = {
            'id': f"{project_id}_marco_dxf",
            'name': 'Marco Automatizado',
            'type': 'MarcoDXF',
            'vigas_individuais': vigas_extremidade, 
            'links': links_dict,
            'geometry': unique_outer if 'unique_outer' in locals() else [],
            'validated_fields': []
        }

        return {
            "extensions": extensions,
            "marco": marco_lines,
            "item_data": marco_item
        }

    def learn_from_corrections(self, original_marco, corrected_marco):
        """
        Aprende se o usuário ajustou as linhas do marco.
        """
        # TODO: Implementar aprendizado usando HierarchicalMemory
        pass
