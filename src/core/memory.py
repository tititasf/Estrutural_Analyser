# -*- coding: utf-8 -*-
"""
Hierarchical Memory - Active Learning Memory System

Armazena exemplos de treinamento em memória usando ChromaDB (Vector DB)
para busca semântica e SQLite para log de eventos.

Dois níveis de memória:
- Local (adaptive_learning): específica do projeto
- Global (global_intelligence): compartilhada entre projetos
"""

import json
import logging
import os
import traceback
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logging.warning("ChromaDB nao encontrado. Active Learning sera limitado.")


class HierarchicalMemory:
    """
    Memória hierárquica com duas camadas (Local + Global).

    Usa ChromaDB para indexação semântica e busca por similaridade.
    SQLite (via db_manager) para log persistente de eventos.
    """

    def __init__(
        self,
        db_manager,
        vector_db_path: str = None,
        global_vector_db_path: str = None,
    ):
        self.db = db_manager
        self.chroma_client = None
        self.local_collection = None
        self.global_collection = None
        self.global_chroma = None
        self._vector_db_path = vector_db_path
        self._global_vector_db_path = global_vector_db_path
        self._chroma_initialized = False

    def _ensure_chroma(self):
        """Lazy-load ChromaDB apenas quando necessário."""
        if self._chroma_initialized:
            return

        if not CHROMA_AVAILABLE:
            return

        try:
            # Inicializa cliente local
            self.chroma_client = chromadb.PersistentClient(
                path=self._vector_db_path,
                settings=Settings(),
            )
            self.local_collection = self.chroma_client.get_or_create_collection(
                name="adaptive_learning",
                metadata={"hnsw:space": "cosine"},
            )

            # Inicializa cliente global se path existir
            if self._global_vector_db_path and os.path.exists(
                os.path.dirname(self._global_vector_db_path) or "."
            ):
                self.global_chroma = chromadb.PersistentClient(
                    path=self._global_vector_db_path,
                    settings=Settings(),
                )
                self.global_collection = self.global_chroma.get_or_create_collection(
                    name="global_intelligence",
                    metadata={"hnsw:space": "cosine"},
                )

            self._chroma_initialized = True
            logging.info("ChromaDB inicializado (lazy)")

        except Exception as e:
            logging.error(f"Erro ao iniciar ChromaDB: {e}")

    def save_training_event(
        self,
        project_context: Dict[str, Any],
        item_context: Dict[str, Any],
        field_context: Dict[str, Any],
        label: str,
        event_type: str = "training",
    ):
        """
        Salva evento no SQLite (Log) e ChromaDB (Índice Semântico).
        """
        try:
            # Empacota dados para log
            memory_packet = {
                "id": str(project_context.get("id", "")) + "_" + str(item_context.get("type", "")),
                "type": event_type,
                "field_name": field_context.get("field_name", ""),
                "valid": label,
            }

            # DNA vector para indexação
            dna_json = json.dumps(field_context.get("dna_vector", []))
            project_id = str(project_context.get("id", "UNKNOWN"))
            role = str(item_context.get("type", "unknown"))
            dna_vector = field_context.get("dna_vector", [])
            link_type = item_context.get("link_type", "")

            # Salva no SQLite via db_manager
            self.db.log_training_event(memory_packet)

            # Indexa no ChromaDB
            self._ensure_chroma()
            if self.local_collection:
                metadata = {
                    "project_id": project_id,
                    "role": role,
                    "item_type": str(item_context.get("type", "")),
                    "field_name": field_context.get("field_name", ""),
                    "valid": str(label),
                    "link_type": str(link_type),
                }

                self.local_collection.add(
                    ids=[str(uuid.uuid4())],
                    embeddings=[dna_vector] if dna_vector else None,
                    metadatas=[metadata],
                )

        except Exception as e:
            logging.error(f"Erro ao indexar no Chroma: {e}")

    def remove_training_event(
        self,
        project_id: str,
        role: str,
        item_type: str,
    ):
        """
        Remove vetores associados do ChromaDB (Undo).
        """
        try:
            self._ensure_chroma()
            if self.local_collection:
                self.local_collection.delete(
                    where={
                        "$and": [
                            {"project_id": {"$eq": project_id}},
                            {"role": {"$eq": role}},
                            {"item_type": {"$eq": item_type}},
                        ]
                    }
                )
                logging.info(
                    f"\U0001f5d1\ufe0f Vetores removidos da memória: {item_type}"
                    f" para projeto {project_id}"
                )
        except Exception as e:
            logging.error(f"Erro ao remover vetores da memória: {e}")
            print(traceback.format_exc())

    def retrieve_relevant_context(
        self,
        role: str,
        item_type: str,
        dna_vector: List[float],
    ) -> Dict[str, Any]:
        """
        Recupera inteligência acumulada (Local + Global) similar ao contexto atual.
        Prioriza local se a confiança for alta.
        """
        self._ensure_chroma()

        results_local = self._query_collection(
            self.local_collection, role, item_type, dna_vector
        )
        results_global = self._query_collection(
            self.global_collection, role, item_type, dna_vector
        )

        # Mescla resultados priorizando local
        avg_pos = results_local.get("avg_rel_pos", results_global.get("avg_rel_pos"))
        merged_status = max(
            results_local.get("predicted_status", "valid"),
            results_global.get("predicted_status", "valid"),
        )

        return {
            "similarity": results_local.get("similarity", 0),
            "avg_rel_pos": avg_pos,
            "predicted_status": merged_status,
            "samples": list(
                set(
                    results_local.get("samples", [])
                    + results_global.get("samples", [])
                )
            ),
            "blocklist": results_local.get("blocklist", []),
        }

    def _query_collection(
        self,
        collection,
        role: str,
        item_type: str,
        dna_vector: List[float],
    ) -> Dict[str, Any]:
        """Consulta uma coleção ChromaDB por similaridade."""
        if not collection or not dna_vector:
            return {}

        try:
            results = collection.query(
                query_embeddings=[dna_vector],
                where={
                    "$and": [
                        {"role": {"$eq": role}},
                        {"item_type": {"$eq": item_type}},
                    ]
                },
                include=["metadatas", "distances"],
            )

            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]

            if not metas:
                return {}

            # Calcula estatísticas
            valid_samples_all = []
            na_count = 0
            total_count = 0

            for m, d in zip(metas, dists):
                total_count += 1
                valid = m.get("valid", "")
                status = m.get("status", "")

                if valid == "na" or status == "user_na":
                    na_count += 1
                else:
                    valid_samples_all.append((m, d))

            # Predição de status
            if total_count == 0:
                predicted_status = "valid"
            elif na_count > total_count / 2:
                predicted_status = "na"
            else:
                predicted_status = "valid"

            # Média de posição relativa
            valid_pos_samples = [
                m for m, _ in valid_samples_all if m.get("rel_pos")
            ]
            if valid_pos_samples:
                avg_dx = sum(float(m.get("rel_pos_dx", 0)) for m in valid_pos_samples) / len(valid_pos_samples)
                avg_dy = sum(float(m.get("rel_pos_dy", 0)) for m in valid_pos_samples) / len(valid_pos_samples)
            else:
                avg_dx, avg_dy = 0, 0

            return {
                "similarity": 1.0 - (dists[0] if dists else 1.0),
                "predicted_status": predicted_status,
                "avg_rel_pos": (avg_dx, avg_dy),
                "samples": [str(m) for m in metas[:5]],
            }

        except Exception:
            return {}

    def _hash_geometry(self, geometry) -> str:
        """Simplificação de hash geométrico para comparison rápida."""
        if not geometry:
            return "empty"
        return str(hash(str(geometry)))

    def save_sample(
        self,
        sample_data: Dict[str, Any],
        dna_input=None,
    ):
        """
        Salva uma amostra diretamente no Vector DB (usado para Sync/Restore de logs).
        """
        try:
            collection = self.local_collection

            # Parse DNA
            dna_dict = sample_data.get("dna", {})
            if isinstance(dna_dict, str):
                dna_dict = json.loads(dna_dict)

            item_ctx = sample_data.get("level_2_item", {})
            field_ctx = sample_data.get("level_3_field", {})

            dna_vector = field_ctx.get("dna_vector", dna_input)
            if isinstance(dna_vector, (list, tuple)) and len(dna_vector) == 0:
                return

            # Posição relativa
            rel_pos = field_ctx.get("rel_pos", {})
            dx = float(rel_pos.get("dx", 0)) if isinstance(rel_pos, dict) else 0
            dy = float(rel_pos.get("dy", 0)) if isinstance(rel_pos, dict) else 0

            metadata = {
                "role": str(item_ctx.get("role", "unknown")),
                "item_type": str(item_ctx.get("type", "UNKNOWN")),
                "field_name": str(field_ctx.get("field_name", "")),
                "link_type": str(item_ctx.get("link_type", "")),
                "status": str(field_ctx.get("status", "valid")),
                "valid": str(field_ctx.get("valid", "")),
                "content": str(field_ctx.get("content", "")),
                "rel_pos_dx": str(dx),
                "rel_pos_dy": str(dy),
                "sync_log": "true",
            }

            self._ensure_chroma()
            if collection:
                collection.add(
                    ids=[str(uuid.uuid4())],
                    embeddings=[dna_vector] if dna_vector else None,
                    metadatas=[metadata],
                )

        except Exception as e:
            logging.error(f"Erro no save_sample Chroma: {e}")
