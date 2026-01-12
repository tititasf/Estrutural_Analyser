import json
import logging
import uuid
from typing import Dict, List, Any, Optional

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logging.warning("ChromaDB nao encontrado. Active Learning sera limitado.")

class HierarchicalMemory:
    """
    Sistema de Memória de Aprendizado com 3 Níveis Hierárquicos.
    Integra SQLite (Logs) e ChromaDB (Busca Ativa).
    """
    
    def __init__(self, db_manager, vector_db_path="./vector_memory"):
        self.db = db_manager
        self.chroma_client = None
        self.collection = None
        
        if CHROMA_AVAILABLE:
            try:
                self.chroma_client = chromadb.PersistentClient(path=vector_db_path)
                self.collection = self.chroma_client.get_or_create_collection(
                    name="adaptive_learning",
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logging.error(f"Erro ao iniciar ChromaDB: {e}")

    def save_training_event(self, 
                          project_context: Dict, 
                          item_context: Dict, 
                          field_context: Dict, 
                          label: Any, 
                          event_type: str = 'user_correction'):
        """
        Salva evento no SQLite (Log) e ChromaDB (Índice Semântico).
        """
        # 1. Estrutura JSON (Log Completo)
        memory_packet = {
            'level_1_project': project_context,
            'level_2_item': item_context,
            'level_3_field': field_context,
            'target_label': label
        }
        dna_json = json.dumps(memory_packet, default=str)
        
        project_id = project_context.get('id')
        role = f"{item_context.get('type')}_{field_context.get('field_name')}"
        
        # 2. Persistir no SQLite
        self.db.log_training_event(
            project_id=project_id,
            type=event_type,
            role=role,
            context_dna=dna_json,
            target_value=str(label),
            status='valid'
        )
        
        # 3. Indexar no ChromaDB (Active Learning)
        if self.collection:
            try:
                # Construir Vetor de Busca (DNA Nível 2 + Contexto)
                # O DNA deve vir pré-calculado no item_context ou gerado aqui.
                # Assumindo que item_context ['dna_vector'] existe ou geramos dummy
                dna_vector = item_context.get('dna_vector', [0.0]*4)
                
                # Metadata para filtragem exata
                metadata = {
                    "role": role,
                    "item_type": item_context.get('type', 'UNKNOWN'),
                    "field_id": field_context.get('field_name'),
                    "link_type": field_context.get('link_type', 'unknown'),
                    "project_id": str(project_id),
                    # Armazenamos o offset relativo aprendido (Local Geometry Delta)
                    # Assumindo que field_context['local_geometry'] é a posição final correta
                    # E item_context['pos'] é a origem.
                    # Calculamos dx, dy aqui para recuperar depois
                }
                
                # Cálculo do Offset Aprendido (Crucial para corrigir posições)
                item_pos = item_context.get('pos')
                target_pos = field_context.get('local_geometry')
                
                # Check for list of lists (Polyline) vs simple point
                is_valid_point_item = isinstance(item_pos, (list, tuple)) and len(item_pos) >= 2 and isinstance(item_pos[0], (int, float))
                is_valid_point_target = isinstance(target_pos, (list, tuple)) and len(target_pos) >= 2 and isinstance(target_pos[0], (int, float))
                
                if is_valid_point_item and is_valid_point_target:
                     dx = target_pos[0] - item_pos[0]
                     dy = target_pos[1] - item_pos[1]
                     metadata['learned_dx'] = float(dx)
                     metadata['learned_dy'] = float(dy)
                else:
                     # Complex geometry (lines, polys) or missing data -> No simple translation
                     metadata['learned_dx'] = 0.0
                     metadata['learned_dy'] = 0.0

                self.collection.add(
                    ids=[str(uuid.uuid4())],
                    embeddings=[dna_vector],
                    metadatas=[metadata],
                    documents=[json.dumps(field_context, default=str)] # Armazena detalhe como doc
                )
            except Exception as e:
                logging.error(f"Erro ao indexar no Chroma: {e}")

    def retrieve_relevant_context(self, role: str, item_type: str, dna_vector: List[float]) -> Dict:
        """
        Recupera inteligência acumulada similar ao contexto atual.
        Retorna offset médio, blocklists, etc.
        """
        if not self.collection: return None
        
        try:
            # Query por Vetor (Semelhança Geométrica) e Filtro (Mesmo Role/Tipo)
            results = self.collection.query(
                query_embeddings=[dna_vector],
                n_results=5,
                where={
                    "$and": [
                        {"role": {"$eq": role}},
                        {"item_type": {"$eq": item_type}}
                    ]
                }
            )
            
            if not results['ids'] or not results['ids'][0]:
                return None
                
            # Analisar resultados para extrair padrão (Consenso)
            metas = results['metadatas'][0]
            dists = results['distances'][0]
            
            # Filtro de Confiança (Distância Cosine pequena)
            valid_samples = []
            for m, d in zip(metas, dists):
                if d < 0.2: # Limite arbitrário de similaridade (ajustar conforme necessidade)
                    valid_samples.append(m)
            
            if not valid_samples:
                # Se nada for muito similar, talvez retornar média geral se houver muitos dados?
                # Por segurança, retornamos None para não enviesar errado
                return None
                
            # Calcular Offset Médio dos casos similares
            avg_dx = sum(m.get('learned_dx', 0) for m in valid_samples) / len(valid_samples)
            avg_dy = sum(m.get('learned_dy', 0) for m in valid_samples) / len(valid_samples)
            
            return {
                'avg_rel_pos': (avg_dx, avg_dy),
                'samples': len(valid_samples),
                'similarity': 1.0 - (sum(dists[:len(valid_samples)])/len(valid_samples)), # Confiança média
                'blocklist': [] # TODO: Implementar blocklist baseada em erros
            }
            
        except Exception as e:
            logging.error(f"Erro no retrieve Chroma: {e}")
            return None

    def _hash_geometry(self, geometry):
        """Simplificação de hash geométrico para comparison rápida."""
        if not geometry: return "empty"
        return str(hash(str(geometry)))

    def save_sample(self, sample_data: Dict):
        """
        Salva uma amostra diretamente no Vector DB (usado para Sync/Restore de logs).
        """
        if not self.collection: return
        
        try:
            # 1. Parse DNA
            dna_input = sample_data.get('dna')
            if isinstance(dna_input, str):
                dna_dict = json.loads(dna_input)
            else:
                dna_dict = dna_input or {}
                
            # 2. Extract Context
            item_ctx = dna_dict.get('level_2_item', {})
            field_ctx = dna_dict.get('level_3_field', {})
            
            # 3. Vector (Mock or Real)
            # Idealmente, aqui usariamos um encoder real. 
            # Por enquanto, tentamos pegar do JSON ou usamos placeholder.
            dna_vector = item_ctx.get('dna_vector', [0.1, 0.2, 0.3, 0.4]) 
            
            # 4. Metadata
            rel_pos = sample_data.get('rel_pos')
            dx, dy = (0.0, 0.0)
            if rel_pos and isinstance(rel_pos, (list, tuple)) and len(rel_pos) >= 2:
                dx, dy = float(rel_pos[0]), float(rel_pos[1])

            metadata = {
                "role": str(sample_data.get('role', 'unknown')),
                "item_type": str(item_ctx.get('type', 'UNKNOWN')),
                "field_id": str(field_ctx.get('field_name', 'unknown')),
                "link_type": str(field_ctx.get('link_type', 'unknown')),
                "learned_dx": dx,
                "learned_dy": dy,
                "status": str(sample_data.get('status', 'valid')),
                "source": "sync_log"
            }

            # 5. Add to Chroma
            import uuid
            self.collection.add(
                ids=[str(uuid.uuid4())],
                embeddings=[dna_vector],
                metadatas=[metadata],
                documents=[str(sample_data.get('content', ''))]
            )
        except Exception as e:
            logging.error(f"Erro no save_sample Chroma: {e}")
