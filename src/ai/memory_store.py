import chromadb
import uuid
import json
from typing import List, Dict, Any

class MemoryStore:
    """
    Gerencia a memória de longo prazo (Vector DB) usando ChromaDB.
    Permite salvar assinaturas de pilares e buscar similares.
    """
    def __init__(self, persistence_path: str = "./vector_memory"):
        self.client = chromadb.PersistentClient(path=persistence_path)
        self.collection = self.client.get_or_create_collection(name="structural_elements")
        self.train_collection = self.client.get_or_create_collection(name="training_samples")

    def save_sample(self, data: Dict[str, Any]):
        """Salva um exemplo de treinamento (vetor relativo, role e DNA geográfico)."""
        # data format: {role, content, rel_pos: (dx, dy), dna: [f1, f2...], status, comment}
        doc_text = f"Role: {data['role']} Value: {data['content']} PilarType: {data.get('pilar_type', 'UNKNOWN')}"
        
        dna = data.get('dna', [0.0, 0.0, 0.0, 0.0]) # DNA Padrão: [area, num_vizinhos, dist_media, perimetro]
        
        metadata = {
            "role": data['role'],
            "dx": float(data['rel_pos'][0]),
            "dy": float(data['rel_pos'][1]),
            "pilar_type": data.get('pilar_type', 'UNKNOWN'),
            "field_id": data.get('field_id', 'UNKNOWN'),
            "status": data['status'],
            "comment": data.get('comment', ''),
            "dna_0": float(dna[0]), # Area
            "dna_1": float(dna[1]), # Num Vizinhos
            "dna_2": float(dna[2]), # Distância Média
            "dna_3": float(dna[3])  # Complexidade (Perímetro/Área)
        }
        
        self.train_collection.add(
            documents=[doc_text],
            metadatas=[metadata],
            ids=[str(uuid.uuid4())]
        )

    def get_training_context(self, role: str, pilar_type: str = None, current_dna: List[float] = None) -> Dict[str, Any]:
        """
        Recupera vetores relativos e blocklists otimizados por DNA Geográfico.
        """
        # 1. Recuperar viciados (Valid) para offset
        query_and = [{"role": {"$eq": role}}, {"status": {"$eq": "valid"}}]
        if pilar_type:
            query_and.append({"pilar_type": {"$eq": pilar_type}})
            
        where_valid = {"$and": query_and}
        res_valid = self.train_collection.get(where=where_valid)
        
        # 2. Recuperar falhas (Fail) para blocklist
        query_fail = [{"role": {"$eq": role}}, {"status": {"$eq": "fail"}}]
        # Blocklist pode ser global por role para ser mais agressiva em evitar erros comuns
        where_fail = {"$and": query_fail}
        res_fail = self.train_collection.get(where=where_fail)
        
        blocklist = []
        if res_fail['metadatas']:
            # Normalizar blocklist agressivamente (remover espaços, etc)
            import re
            def clean(s): return re.sub(r'[^A-Z0-9/X]', '', str(s).upper())
            blocklist = [clean(m.get('content')) for m in res_fail['metadatas'] if m.get('content')]

        if not res_valid['ids']:
            return {
                'avg_rel_pos': (0, 0),
                'samples': 0,
                'blocklist': blocklist,
                'top_similarity': 0.5
            }
            
        metas = res_valid['metadatas']
        
        # 3. Ranking por Similaridade de DNA (Ponderada e Normalizada)
        similarity_score = 0.5
        if current_dna and len(current_dna) >= 4:
            def calc_dist(m):
                # Normalização: d = ((v1 - v2) / scale)**2
                # scales baseadas em ordens de grandeza típicas
                # dna_0 (Area): scale 1000
                # dna_1 (Vizinhos): scale 5
                # dna_2 (Dist Media): scale 100
                # dna_3 (Perímetro): scale 200
                d0 = ((m.get('dna_0', 0) - current_dna[0]) / (current_dna[0] + 1))**2
                d1 = ((m.get('dna_1', 0) - current_dna[1]) / 5.0)**2
                d2 = ((m.get('dna_2', 0) - current_dna[2]) / 100.0)**2
                d3 = ((m.get('dna_3', 0) - current_dna[3]) / 200.0)**2
                return (d0 + d1 + d2 + d3)**0.5

            # Ordenar por distância (menor é mais similar)
            metas.sort(key=calc_dist)
            
            # Filtro de similaridade mínima (distância < 1.0 é um match razoável)
            best_match_dist = calc_dist(metas[0])
            if best_match_dist < 0.2: similarity_score = 0.95
            elif best_match_dist < 0.5: similarity_score = 0.85
            elif best_match_dist < 1.5: similarity_score = 0.65
            
            # Pegar os top 3 matches para cálculo de tendência (outlier removal)
            valid_samples = [m for m in metas if calc_dist(m) < 2.0][:3]
            if not valid_samples: valid_samples = [metas[0]] # Fallback no melhor
            
            avg_dx = sum(m['dx'] for m in valid_samples) / len(valid_samples)
            avg_dy = sum(m['dy'] for m in valid_samples) / len(valid_samples)
            
            return {
                'avg_rel_pos': (avg_dx, avg_dy),
                'samples': len(valid_samples),
                'blocklist': blocklist,
                'top_similarity': similarity_score
            }
        
        # Fallback se não há DNA (média global do role)
        avg_dx = sum(m['dx'] for m in metas) / len(metas)
        avg_dy = sum(m['dy'] for m in metas) / len(metas)
        
        return {
            'avg_rel_pos': (avg_dx, avg_dy),
            'samples': len(metas),
            'blocklist': blocklist,
            'top_similarity': 0.6
        }

    def _generate_embedding_text(self, shape_data: Dict[str, Any]) -> str:
        type_str = shape_data.get('type', 'UNKNOWN')
        area = shape_data.get('area', '0')
        return f"{type_str} area:{area}"

    def add_memory(self, item_data: Dict[str, Any]):
        """Adiciona um item validado à memória."""
        doc_text = self._generate_embedding_text(item_data)
        
        # Metadata para filtragem
        metadata = {
            "type": item_data.get('type', 'UNKNOWN'),
            "name": item_data.get('name', 'N/A')
        }
        
        self.collection.add(
            documents=[doc_text],
            metadatas=[metadata],
            ids=[str(uuid.uuid4())]
        )

    def find_similar(self, item_data: Dict[str, Any], n_results: int = 3) -> List[Dict]:
        """Busca itens similares na memória."""
        query_text = self._generate_embedding_text(item_data)
        
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        # Formatar retorno
        similar_items = []
        if results['ids']:
            for i in range(len(results['ids'][0])):
                similar_items.append({
                    'id': results['ids'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if results['distances'] else 0.0
                })
                
        return similar_items
