import json
import logging
from typing import Dict, List, Any, Optional

class HierarchicalMemory:
    """
    Sistema de Memória de Aprendizado com 3 Níveis Hierárquicos.
    
    NIVEL 1: Contexto Global do Projeto (Obra, Pavimento, Níveis)
    NIVEL 2: Contexto do Item (Objeto completo, geometria bruta, vizinhos)
    NIVEL 3: Contexto do Campo/Vinculo (Feature específica, geometria local)
    """
    
    def __init__(self, db_manager):
        self.db = db_manager
        
    def save_training_event(self, 
                          project_context: Dict, 
                          item_context: Dict, 
                          field_context: Dict, 
                          label: Any, 
                          event_type: str = 'user_correction'):
        """
        Salva um evento de treinamento estruturado nos 3 níveis.
        """
        
        # Estrutura Hierárquica para vetorização futura
        memory_packet = {
            'level_1_project': {
                'work_name': project_context.get('work_name', ''),
                'pavement': project_context.get('pavement', ''),
                'levels': (project_context.get('level_arr'), project_context.get('level_exit'))
            },
            'level_2_item': {
                'type': item_context.get('type'),
                'name': item_context.get('name'),
                'gross_geometry_hash': self._hash_geometry(item_context.get('geometry')),
                'neighbor_count': len(item_context.get('neighbors', []))
            },
            'level_3_field': {
                'field_name': field_context.get('field_name'),
                'source_link_type': field_context.get('link_type'), # text, ent, line
                'local_geometry_context': field_context.get('local_geometry')
            },
            'target_label': label
        }
        
        # Serializar para JSON para armazenar no DB (SQLite por enquanto)
        # Futuramente isso iria para um VectorDB (Chroma/FAISS)
        dna_json = json.dumps(memory_packet, default=str)
        
        # Salvar no braço 'training_events' do DatabaseManager
        # Precisamos adaptar o DatabaseManager se ele não suportar esse blob complexo ainda,
        # ou salvar como JSON na coluna 'context_dna_json'.
        
        # ID do projeto é fundamental para vincular
        project_id = project_context.get('id')
        role = f"{item_context.get('type')}_{field_context.get('field_name')}"
        
        self.db.log_training_event(
            project_id=project_id,
            type=event_type,
            role=role,
            context_dna=dna_json,
            target_value=str(label),
            status='valid'
        )
        
    def _hash_geometry(self, geometry):
        """Simplificação de hash geométrico para comparação rápida."""
        if not geometry: return "empty"
        # Placeholder
        return str(hash(str(geometry)))
