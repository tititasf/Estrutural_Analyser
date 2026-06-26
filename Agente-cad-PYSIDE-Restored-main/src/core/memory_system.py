"""
Sistema de Memória Multi-Nível AgenteCAD
Coordenação entre memória de curto, médio e longo prazo

Arquitetura:
- Curto Prazo (RAM): Sessões ativas, cache de cálculos, estado temporário
- Médio Prazo (SQLite/ChromaDB): Contexto de projeto, aprendizado específico, histórico
- Longo Prazo (Byterover): Conhecimento global, padrões universais, insights permanentes

Integração Multimodal:
- Texto: Especificações, comentários, documentação
- Imagens: JPG de desenhos, capturas de tela
- DXF: Geometria estrutural, padrões de forma
- ML: Modelos treinados, vetores de features
"""

import json
import logging
import asyncio
import threading
import time
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

from .agent_identity import (
    AgentIdentity, MemoryTier, ModalityType, MemoryPacket,
    create_memory_packet, AgentContext
)
from .memory import HierarchicalMemory
from .database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class MemoryQuery:
    """Consulta estruturada para sistema de memória"""
    query_type: str  # "semantic", "exact", "pattern", "contextual"
    content: Any
    modality: Optional[ModalityType] = None
    context_filters: Dict[str, Any] = None
    tier_preference: Optional[MemoryTier] = None
    limit: int = 10
    similarity_threshold: float = 0.7


@dataclass
class MemoryResult:
    """Resultado de consulta de memória"""
    packet: MemoryPacket
    relevance_score: float
    tier_source: MemoryTier
    retrieval_time: float
    metadata: Dict[str, Any] = None


class MultimodalMemorySystem:
    """
    Sistema de Memória Multi-Nível e Multimodal

    Coordena três níveis de memória com processamento multimodal
    preparado para RAG avançado.
    """

    def __init__(self, db_manager: DatabaseManager, agent_identity: AgentIdentity):
        self.db = db_manager
        self.agent = agent_identity

        # Inicializar sistemas de memória por nível
        self.short_term = ShortTermMemoryManager()
        self.medium_term = MediumTermMemoryManager(db_manager)
        self.long_term = LongTermMemoryManager()

        # Sistema de processamento multimodal
        self.multimodal_processor = MultimodalProcessor()

        # Cache de consultas frequentes
        self.query_cache = {}
        self.cache_ttl = timedelta(minutes=30)

        # Executor para operações assíncronas
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Estatísticas de performance
        self.stats = {
            "queries_processed": 0,
            "cache_hits": 0,
            "cross_tier_transfers": 0,
            "multimodal_operations": 0
        }

        # Background tasks
        self._start_background_tasks()

        logger.info("🧠 Sistema de Memória Multi-Nível inicializado")

    def store(self, content: Any, modality: ModalityType, metadata: Dict[str, Any] = None,
              tier: MemoryTier = None, context: AgentContext = None) -> str:
        """
        Armazenar conteúdo no nível apropriado de memória

        Args:
            content: Conteúdo a armazenar
            modality: Tipo de modalidade
            metadata: Metadados adicionais
            tier: Nível específico ou automático
            context: Contexto do agente

        Returns:
            str: ID do pacote armazenado
        """
        # Usar contexto atual se não especificado
        if context is None:
            context = self.agent.current_context

        # Determinar nível automaticamente se não especificado
        if tier is None:
            tier = self._determine_optimal_tier(content, modality, metadata or {})

        # Processar multimodal se necessário
        processed_content = self.multimodal_processor.process(content, modality)

        # Criar pacote de memória
        packet = create_memory_packet(
            content=processed_content,
            tier=tier,
            modality=modality,
            context=context,
            metadata=metadata,
            ttl=self._calculate_ttl(tier)
        )

        # Armazenar usando o sistema de identidade
        success = self.agent.store_memory(packet)

        if success:
            # Trigger de manutenção de memória
            self._trigger_memory_maintenance(tier)

            logger.info(f"💾 Conteúdo armazenado: {modality.value} -> {tier.value} (ID: {packet.id})")
            return packet.id
        else:
            logger.error(f"❌ Falha ao armazenar conteúdo: {modality.value}")
            return None

    def query(self, query: Union[str, MemoryQuery]) -> List[MemoryResult]:
        """
        Consultar memória com busca inteligente multi-nível

        Args:
            query: Consulta simples (string) ou estruturada (MemoryQuery)

        Returns:
            List[MemoryResult]: Resultados ordenados por relevância
        """
        start_time = time.time()

        # Normalizar consulta
        if isinstance(query, str):
            memory_query = MemoryQuery(
                query_type="semantic",
                content=query,
                modality=ModalityType.TEXT
            )
        else:
            memory_query = query

        # Verificar cache
        cache_key = self._generate_cache_key(memory_query)
        if cache_key in self.query_cache:
            cached_result = self.query_cache[cache_key]
            if datetime.now() - cached_result["timestamp"] < self.cache_ttl:
                self.stats["cache_hits"] += 1
                return cached_result["results"]

        # Executar busca multi-nível
        results = self._execute_multilevel_query(memory_query)

        # Processar e ordenar resultados
        processed_results = self._process_query_results(results, memory_query)

        # Cache dos resultados
        self.query_cache[cache_key] = {
            "results": processed_results,
            "timestamp": datetime.now()
        }

        # Estatísticas
        self.stats["queries_processed"] += 1
        query_time = time.time() - start_time

        logger.info(f"🔍 Consulta processada em {query_time:.3f}s: {len(processed_results)} resultados")

        return processed_results

    def _execute_multilevel_query(self, query: MemoryQuery) -> Dict[MemoryTier, List[MemoryPacket]]:
        """Executar consulta em todos os níveis de memória"""
        results = {}

        # Determinar níveis a consultar
        tiers_to_query = self._determine_query_tiers(query)

        # Consultar cada nível em paralelo
        futures = {}
        for tier in tiers_to_query:
            future = self.executor.submit(self._query_single_tier, tier, query)
            futures[tier] = future

        # Coletar resultados
        for tier, future in futures.items():
            try:
                results[tier] = future.result(timeout=10)  # Timeout de 10s
            except Exception as e:
                logger.warning(f"Erro ao consultar {tier.value}: {e}")
                results[tier] = []

        return results

    def _query_single_tier(self, tier: MemoryTier, query: MemoryQuery) -> List[MemoryPacket]:
        """Consultar um nível específico de memória"""
        if tier == MemoryTier.SHORT_TERM:
            return self.short_term.query(query)
        elif tier == MemoryTier.MEDIUM_TERM:
            return self.medium_term.query(query)
        elif tier == MemoryTier.LONG_TERM:
            return self.long_term.query(query)

    def _process_query_results(self, raw_results: Dict[MemoryTier, List[MemoryPacket]],
                              query: MemoryQuery) -> List[MemoryResult]:
        """Processar e ordenar resultados de consulta"""
        processed_results = []

        for tier, packets in raw_results.items():
            for packet in packets:
                # Calcular score de relevância
                relevance_score = self._calculate_relevance_score(packet, query)

                # Filtrar por threshold
                if relevance_score >= query.similarity_threshold:
                    result = MemoryResult(
                        packet=packet,
                        relevance_score=relevance_score,
                        tier_source=tier,
                        retrieval_time=time.time(),
                        metadata={"query_type": query.query_type}
                    )
                    processed_results.append(result)

        # Ordenar por relevância e recência
        processed_results.sort(
            key=lambda x: (x.relevance_score, x.packet.timestamp),
            reverse=True
        )

        # Limitar resultados
        return processed_results[:query.limit]

    def _calculate_relevance_score(self, packet: MemoryPacket, query: MemoryQuery) -> float:
        """Calcular score de relevância entre pacote e consulta"""
        base_score = 0.5

        # Score baseado na modalidade
        if packet.modality == query.modality:
            base_score += 0.2

        # Score baseado no conteúdo (simplificado)
        query_content = str(query.content).lower()
        packet_content = str(packet.content).lower()

        if query_content in packet_content:
            base_score += 0.3
        elif any(word in packet_content for word in query_content.split()):
            base_score += 0.1

        # Score baseado no contexto
        if query.context_filters:
            context_matches = 0
            total_filters = len(query.context_filters)

            for key, value in query.context_filters.items():
                if key in packet.context.__dict__ and packet.context.__dict__[key] == value:
                    context_matches += 1

            base_score += (context_matches / total_filters) * 0.2

        # Recência boost
        hours_old = (datetime.now() - packet.timestamp).total_seconds() / 3600
        recency_boost = max(0, 0.1 * (1 - min(hours_old / 24, 1)))  # Boost de 1 dia

        return min(1.0, base_score + recency_boost)

    def _determine_optimal_tier(self, content: Any, modality: ModalityType,
                               metadata: Dict[str, Any]) -> MemoryTier:
        """Determinar nível ótimo de memória baseado no conteúdo"""
        # Regras de decisão automática
        content_size = len(str(content))

        # Conteúdo pequeno e temporário -> Curto prazo
        if content_size < 1000 and metadata.get("temporary", False):
            return MemoryTier.SHORT_TERM

        # Conteúdo relacionado ao projeto atual -> Médio prazo
        if metadata.get("project_scoped", True):
            return MemoryTier.MEDIUM_TERM

        # Insights importantes, padrões globais -> Longo prazo
        if metadata.get("global_insight", False) or modality in [ModalityType.ML_MODEL]:
            return MemoryTier.LONG_TERM

        # Default: Médio prazo
        return MemoryTier.MEDIUM_TERM

    def _determine_query_tiers(self, query: MemoryQuery) -> List[MemoryTier]:
        """Determinar quais níveis consultar"""
        if query.tier_preference:
            return [query.tier_preference]

        # Busca inteligente: todos os níveis por padrão
        return [MemoryTier.SHORT_TERM, MemoryTier.MEDIUM_TERM, MemoryTier.LONG_TERM]

    def _calculate_ttl(self, tier: MemoryTier) -> Optional[int]:
        """Calcular TTL baseado no nível"""
        ttl_map = {
            MemoryTier.SHORT_TERM: 3600,      # 1 hora
            MemoryTier.MEDIUM_TERM: 604800,   # 1 semana
            MemoryTier.LONG_TERM: None        # Permanente
        }
        return ttl_map.get(tier)

    def _generate_cache_key(self, query: MemoryQuery) -> str:
        """Gerar chave de cache para consulta"""
        query_dict = asdict(query)
        query_str = json.dumps(query_dict, sort_keys=True, default=str)
        return hashlib.md5(query_str.encode()).hexdigest()

    def _trigger_memory_maintenance(self, tier: MemoryTier) -> None:
        """Trigger manutenção específica do nível"""
        if tier == MemoryTier.SHORT_TERM:
            self.short_term.cleanup_expired()
        elif tier == MemoryTier.MEDIUM_TERM:
            self.medium_term.optimize_storage()
        elif tier == MemoryTier.LONG_TERM:
            self.long_term.sync_pending()

    def _start_background_tasks(self) -> None:
        """Iniciar tarefas de background"""
        def maintenance_loop():
            while True:
                try:
                    # Manutenção periódica
                    self.short_term.cleanup_expired()
                    self.medium_term.optimize_storage()
                    self.long_term.sync_pending()

                    # Limpeza de cache antigo
                    self._cleanup_old_cache()

                    time.sleep(300)  # 5 minutos
                except Exception as e:
                    logger.error(f"Erro em manutenção de background: {e}")
                    time.sleep(60)

        # Iniciar thread de manutenção
        maintenance_thread = threading.Thread(target=maintenance_loop, daemon=True)
        maintenance_thread.start()

    def _cleanup_old_cache(self) -> None:
        """Limpar entradas antigas do cache"""
        now = datetime.now()
        expired_keys = [
            key for key, data in self.query_cache.items()
            if now - data["timestamp"] > self.cache_ttl
        ]

        for key in expired_keys:
            del self.query_cache[key]

    def get_system_status(self) -> Dict[str, Any]:
        """Retornar status completo do sistema de memória"""
        return {
            "memory_tiers": {
                "short_term": self.short_term.get_stats(),
                "medium_term": self.medium_term.get_stats(),
                "long_term": self.long_term.get_stats()
            },
            "multimodal_processor": self.multimodal_processor.get_stats(),
            "agent_identity": self.agent.get_health_status(),
            "system_stats": self.stats,
            "cache_size": len(self.query_cache)
        }


class ShortTermMemoryManager:
    """Gerenciador de Memória de Curto Prazo"""

    def __init__(self):
        self.memory = {}
        self.metadata = {}
        self.stats = {"operations": 0, "size": 0, "cleanups": 0}

    def store(self, packet: MemoryPacket) -> bool:
        """Armazenar em memória curta"""
        try:
            self.memory[packet.id] = packet
            self.metadata[packet.id] = {
                "expires_at": datetime.now() + timedelta(seconds=packet.ttl or 3600),
                "access_count": 0,
                "last_access": datetime.now()
            }
            self.stats["size"] += 1
            self.stats["operations"] += 1
            return True
        except Exception as e:
            logger.error(f"Erro ao armazenar em memória curta: {e}")
            return False

    def query(self, query: MemoryQuery) -> List[MemoryPacket]:
        """Consultar memória curta"""
        results = []
        query_str = str(query.content).lower()

        for packet_id, packet in self.memory.items():
            # Verificar expiração
            if self._is_expired(packet_id):
                continue

            # Busca simples por conteúdo
            if query_str in str(packet.content).lower():
                results.append(packet)
                self.metadata[packet_id]["access_count"] += 1
                self.metadata[packet_id]["last_access"] = datetime.now()

        self.stats["operations"] += 1
        return results

    def cleanup_expired(self) -> int:
        """Limpar entradas expiradas"""
        expired_count = 0
        now = datetime.now()

        expired_ids = [
            pid for pid, meta in self.metadata.items()
            if meta["expires_at"] < now
        ]

        for pid in expired_ids:
            del self.memory[pid]
            del self.metadata[pid]
            expired_count += 1

        self.stats["size"] -= expired_count
        self.stats["cleanups"] += 1

        if expired_count > 0:
            logger.info(f"🧹 Limpeza memória curta: {expired_count} entradas expiradas")

        return expired_count

    def _is_expired(self, packet_id: str) -> bool:
        """Verificar se entrada expirou"""
        if packet_id not in self.metadata:
            return True
        return self.metadata[packet_id]["expires_at"] < datetime.now()

    def get_stats(self) -> Dict[str, Any]:
        """Retornar estatísticas"""
        return dict(self.stats)


class MediumTermMemoryManager:
    """Gerenciador de Memória de Médio Prazo - SQLite/ChromaDB"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.hierarchical_memory = HierarchicalMemory(db_manager)
        self.stats = {"operations": 0, "size": 0, "optimizations": 0}

    def store(self, packet: MemoryPacket) -> bool:
        """Armazenar em memória média usando sistema existente"""
        try:
            # Usar sistema existente de aprendizado hierárquico
            self.hierarchical_memory.save_training_event(
                project_context=packet.context.project_context,
                item_context={"type": packet.modality.value, "dna_vector": packet.vector_embedding or [0.1] * 10},
                field_context={"field_name": "content", "link_type": "memory_packet"},
                label=packet.content
            )

            self.stats["operations"] += 1
            self.stats["size"] += 1
            return True
        except Exception as e:
            logger.error(f"Erro ao armazenar em memória média: {e}")
            return False

    def query(self, query: MemoryQuery) -> List[MemoryPacket]:
        """Consultar memória média"""
        try:
            # Usar busca existente
            dna_vector = query.content if isinstance(query.content, list) else [0.1] * 10
            results = self.hierarchical_memory.retrieve_relevant_context(
                role=query.query_type,
                item_type=query.modality.value if query.modality else "unknown",
                dna_vector=dna_vector
            )

            # Converter para formato padronizado
            packets = []
            if results and "samples" in results:
                # Criar pacotes mock (simplificado)
                for i in range(min(results["samples"], 5)):
                    packet = MemoryPacket(
                        id=f"medium_{i}",
                        tier=MemoryTier.MEDIUM_TERM,
                        modality=query.modality or ModalityType.TEXT,
                        content=f"Resultado {i}",
                        metadata={"similarity": results.get("similarity", 0.5)},
                        context=self.db,  # Placeholder
                        timestamp=datetime.now()
                    )
                    packets.append(packet)

            self.stats["operations"] += 1
            return packets

        except Exception as e:
            logger.error(f"Erro ao consultar memória média: {e}")
            return []

    def optimize_storage(self) -> None:
        """Otimizar armazenamento (placeholder)"""
        self.stats["optimizations"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Retornar estatísticas"""
        return dict(self.stats)


class LongTermMemoryManager:
    """Gerenciador de Memória de Longo Prazo - Byterover"""

    def __init__(self):
        self.pending_sync = []
        self.stats = {"operations": 0, "size": 0, "syncs": 0}

    def store(self, packet: MemoryPacket) -> bool:
        """Enfileirar para sincronização com Byterover"""
        try:
            self.pending_sync.append(packet)
            self.stats["operations"] += 1
            self.stats["size"] += 1
            return True
        except Exception as e:
            logger.error(f"Erro ao enfileirar para longo prazo: {e}")
            return False

    def query(self, query: MemoryQuery) -> List[MemoryPacket]:
        """Consulta em Byterover (placeholder)"""
        # TODO: Implementar busca real no Byterover
        self.stats["operations"] += 1
        return []

    def sync_pending(self) -> int:
        """Sincronizar pendências com Byterover"""
        synced_count = 0

        # TODO: Implementar sincronização real
        if self.pending_sync:
            logger.info(f"📤 Sincronizando {len(self.pending_sync)} itens com Byterover...")
            # Simular sincronização
            synced_count = len(self.pending_sync)
            self.pending_sync.clear()
            self.stats["syncs"] += 1

        return synced_count

    def get_stats(self) -> Dict[str, Any]:
        """Retornar estatísticas"""
        return dict(self.stats)


class MultimodalProcessor:
    """
    Processador Multimodal - Preparado para RAG Avançado

    Interfaces para processamento de diferentes modalidades:
    - Texto: Análise semântica
    - Imagens: OCR, feature extraction
    - DXF: Análise geométrica
    - ML: Vetores de modelo
    """

    def __init__(self):
        self.processors = {
            ModalityType.TEXT: self._process_text,
            ModalityType.IMAGE_JPG: self._process_image,
            ModalityType.DXF_GEOMETRY: self._process_dxf,
            ModalityType.ML_MODEL: self._process_ml,
            ModalityType.STRUCTURAL_PATTERN: self._process_structural
        }
        self.stats = {"processed": 0, "errors": 0}

    def process(self, content: Any, modality: ModalityType) -> Any:
        """Processar conteúdo baseado na modalidade"""
        try:
            processor = self.processors.get(modality, self._process_generic)
            processed = processor(content)
            self.stats["processed"] += 1
            return processed
        except Exception as e:
            logger.error(f"Erro no processamento {modality.value}: {e}")
            self.stats["errors"] += 1
            return content  # Retornar original em caso de erro

    def _process_text(self, content: str) -> Dict[str, Any]:
        """Processar texto - extrair entidades, tópicos"""
        return {
            "original": content,
            "type": "text",
            "entities": [],  # TODO: Implementar NER
            "topics": [],    # TODO: Implementar topic modeling
            "sentiment": 0.0  # TODO: Implementar análise de sentimento
        }

    def _process_image(self, content: bytes) -> Dict[str, Any]:
        """Processar imagem - OCR, features (placeholder)"""
        return {
            "original": content,
            "type": "image",
            "ocr_text": "",      # TODO: Implementar OCR
            "features": [],      # TODO: Implementar feature extraction
            "dimensions": None   # TODO: Extrair dimensões
        }

    def _process_dxf(self, content: Any) -> Dict[str, Any]:
        """Processar geometria DXF"""
        return {
            "original": content,
            "type": "dxf",
            "entities": [],      # TODO: Analisar entidades DXF
            "bounds": None,      # TODO: Calcular bounding box
            "complexity": 0      # TODO: Medir complexidade
        }

    def _process_ml(self, content: Any) -> Dict[str, Any]:
        """Processar modelo de ML"""
        return {
            "original": content,
            "type": "ml_model",
            "architecture": "unknown",  # TODO: Detectar arquitetura
            "parameters": 0,            # TODO: Contar parâmetros
            "performance": {}           # TODO: Métricas de performance
        }

    def _process_structural(self, content: Any) -> Dict[str, Any]:
        """Processar padrão estrutural"""
        return {
            "original": content,
            "type": "structural_pattern",
            "pattern_type": "unknown",  # TODO: Classificar padrão
            "confidence": 0.0,          # TODO: Score de confiança
            "metadata": {}              # TODO: Metadados específicos
        }

    def _process_generic(self, content: Any) -> Dict[str, Any]:
        """Processamento genérico"""
        return {
            "original": content,
            "type": "generic",
            "processed": False
        }

    def get_stats(self) -> Dict[str, Any]:
        """Retornar estatísticas"""
        return dict(self.stats)


# Função utilitária para integração com sistema existente
def integrate_memory_system(db_manager: DatabaseManager) -> MultimodalMemorySystem:
    """
    Integrar sistema de memória multi-nível com aplicação existente

    Args:
        db_manager: Instância do DatabaseManager existente

    Returns:
        MultimodalMemorySystem: Sistema configurado
    """
    from .agent_identity import AgentIdentity

    # Criar identidade do agente
    agent = AgentIdentity(db_manager)

    # Criar sistema de memória
    memory_system = MultimodalMemorySystem(db_manager, agent)

    logger.info("🔗 Sistema de memória integrado com sucesso")

    return memory_system