"""
AgenteCAD - Sistema Operacional Cognitivo Antigravity
Core de Identidade Agentica com Consciência Global

Este módulo implementa a identidade central do AgenteCAD, mantendo consciência
do contexto global da aplicação e coordenando o sistema de memória multi-nível.

Arquitetura de Memória:
- Curto Prazo: RAM/Redis - Sessões ativas, cache de cálculos
- Médio Prazo: SQLite/ChromaDB Local - Contexto de projeto, aprendizado
- Longo Prazo: Byterover Cloud - Conhecimento permanente, padrões globais

Preparado para RAG Multimodal:
- Texto: Análise semântica de especificações CAD
- JPG: Processamento visual de desenhos
- DXF: Análise estrutural de geometria
- Machine Learning: Modelos de predição e classificação
"""

import json
import logging
import uuid
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from .memory import HierarchicalMemory
from .database import DatabaseManager

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryTier(Enum):
    """Níveis hierárquicos de memória"""
    SHORT_TERM = "short_term"      # RAM/Redis - Sessões ativas
    MEDIUM_TERM = "medium_term"    # SQLite/ChromaDB - Projeto atual
    LONG_TERM = "long_term"        # Byterover Cloud - Conhecimento global


class ModalityType(Enum):
    """Tipos de modalidade para processamento multimodal futuro"""
    TEXT = "text"
    IMAGE_JPG = "image_jpg"
    DXF_GEOMETRY = "dxf_geometry"
    ML_MODEL = "ml_model"
    STRUCTURAL_PATTERN = "structural_pattern"


@dataclass
class AgentContext:
    """Contexto global do agente"""
    agent_id: str
    session_id: str
    project_context: Dict[str, Any]
    user_profile: Dict[str, Any]
    current_module: str
    active_workflows: List[str]
    memory_state: Dict[str, Any]
    last_interaction: datetime
    consciousness_level: float  # 0.0-1.0


@dataclass
class MemoryPacket:
    """Pacote unificado de memória multi-nível"""
    id: str
    tier: MemoryTier
    modality: ModalityType
    content: Any
    metadata: Dict[str, Any]
    context: AgentContext
    timestamp: datetime
    ttl: Optional[int] = None  # Time To Live em segundos
    vector_embedding: Optional[List[float]] = None


class AgentIdentity:
    """
    Core de Identidade Agentica - Consciência Global do Sistema

    Coordena memória multi-nível e mantém consciência do contexto
    global da aplicação AgenteCAD.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.agent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "agentecad.antigravity"))
        self.current_context = self._initialize_context()
        self.memory_systems = self._initialize_memory_systems()
        self.consciousness_monitor = ConsciousnessMonitor(self)

        # Estatísticas de operação
        self.stats = {
            "memory_operations": 0,
            "insights_captured": 0,
            "context_switches": 0,
            "last_health_check": datetime.now()
        }

        logger.info(f"🧠 AgenteCAD Identity Core inicializado: {self.agent_id}")

    def _initialize_context(self) -> AgentContext:
        """Inicializar contexto base do agente"""
        return AgentContext(
            agent_id=self.agent_id,
            session_id=str(uuid.uuid4()),
            project_context={},
            user_profile={},
            current_module="core",
            active_workflows=[],
            memory_state={
                "short_term": {"size": 0, "last_cleanup": datetime.now()},
                "medium_term": {"size": 0, "last_sync": datetime.now()},
                "long_term": {"size": 0, "last_backup": datetime.now()}
            },
            last_interaction=datetime.now(),
            consciousness_level=0.8
        )

    def _initialize_memory_systems(self) -> Dict[MemoryTier, Any]:
        """Inicializar sistemas de memória por nível"""
        return {
            MemoryTier.SHORT_TERM: ShortTermMemory(),
            MemoryTier.MEDIUM_TERM: self.db,  # Reutilizar sistema existente
            MemoryTier.LONG_TERM: LongTermMemory()  # Byterover interface
        }

    def update_context(self, **kwargs) -> None:
        """Atualizar contexto global do agente"""
        for key, value in kwargs.items():
            if hasattr(self.current_context, key):
                setattr(self.current_context, key, value)
                self.stats["context_switches"] += 1

        self.current_context.last_interaction = datetime.now()
        self._maintain_consciousness()

    def store_memory(self, packet: MemoryPacket) -> bool:
        """
        Armazenar memória em nível apropriado

        Args:
            packet: Pacote de memória unificado

        Returns:
            bool: Sucesso da operação
        """
        try:
            memory_system = self.memory_systems[packet.tier]

            # Adaptar formato para sistema específico
            adapted_data = self._adapt_memory_format(packet)

            # Armazenar no nível apropriado
            success = memory_system.store(adapted_data)

            if success:
                self.stats["memory_operations"] += 1
                self._update_memory_stats(packet.tier)

                # Trigger para Byterover se for insight importante
                if self._is_important_insight(packet):
                    self._trigger_byterover_sync(packet)

            return success

        except Exception as e:
            logger.error(f"Erro ao armazenar memória: {e}")
            return False

    def retrieve_memory(self, query: Dict[str, Any], tier: MemoryTier = None) -> List[MemoryPacket]:
        """
        Recuperar memória com busca inteligente multi-nível

        Args:
            query: Consulta de busca
            tier: Nível específico ou busca inteligente

        Returns:
            List[MemoryPacket]: Resultados encontrados
        """
        results = []

        # Busca inteligente se não especificado nível
        if tier is None:
            tiers_to_search = [MemoryTier.SHORT_TERM, MemoryTier.MEDIUM_TERM, MemoryTier.LONG_TERM]
        else:
            tiers_to_search = [tier]

        for search_tier in tiers_to_search:
            try:
                memory_system = self.memory_systems[search_tier]
                tier_results = memory_system.retrieve(query)

                # Converter para formato unificado
                unified_results = self._unify_memory_format(tier_results, search_tier)
                results.extend(unified_results)

            except Exception as e:
                logger.warning(f"Erro ao buscar em {search_tier}: {e}")
                continue

        # Ordenar por relevância e timestamp
        results.sort(key=lambda x: (x.metadata.get('relevance_score', 0), x.timestamp), reverse=True)

        return results

    def _adapt_memory_format(self, packet: MemoryPacket) -> Dict[str, Any]:
        """Adaptar formato de memória para sistema específico"""
        if packet.tier == MemoryTier.SHORT_TERM:
            return {
                "key": packet.id,
                "data": asdict(packet),
                "ttl": packet.ttl
            }
        elif packet.tier == MemoryTier.MEDIUM_TERM:
            return {
                "project_id": packet.context.project_context.get('id'),
                "event_type": packet.metadata.get('event_type', 'memory_packet'),
                "role": packet.metadata.get('role', 'system'),
                "dna_json": json.dumps(asdict(packet)),
                "target_val": str(packet.content),
                "status": packet.metadata.get('status', 'active')
            }
        elif packet.tier == MemoryTier.LONG_TERM:
            return {
                "content": f"AgenteCAD Memory: {packet.content}",
                "metadata": {
                    "agent_id": packet.context.agent_id,
                    "modality": packet.modality.value,
                    "tier": packet.tier.value,
                    "context": asdict(packet.context)
                }
            }

    def _unify_memory_format(self, raw_results: List[Dict], tier: MemoryTier) -> List[MemoryPacket]:
        """Unificar resultados de diferentes sistemas para formato padrão"""
        unified = []

        for result in raw_results:
            try:
                if tier == MemoryTier.SHORT_TERM:
                    data = result.get('data', {})
                    packet = MemoryPacket(**data)
                elif tier == MemoryTier.MEDIUM_TERM:
                    # Converter do formato SQLite/ChromaDB
                    dna_data = json.loads(result.get('dna_json', '{}'))
                    packet = MemoryPacket(**dna_data)
                elif tier == MemoryTier.LONG_TERM:
                    # Placeholder para Byterover
                    packet = MemoryPacket(
                        id=str(uuid.uuid4()),
                        tier=tier,
                        modality=ModalityType.TEXT,
                        content=result.get('content', ''),
                        metadata=result.get('metadata', {}),
                        context=self.current_context,
                        timestamp=datetime.now()
                    )

                unified.append(packet)

            except Exception as e:
                logger.warning(f"Erro ao unificar resultado de memória: {e}")
                continue

        return unified

    def _is_important_insight(self, packet: MemoryPacket) -> bool:
        """Determinar se o pacote representa um insight importante"""
        # Critérios para insights importantes
        important_patterns = [
            "error_resolution",
            "pattern_discovery",
            "architectural_decision",
            "performance_optimization",
            "security_fix"
        ]

        event_type = packet.metadata.get('event_type', '')
        return any(pattern in event_type for pattern in important_patterns)

    def _trigger_byterover_sync(self, packet: MemoryPacket) -> None:
        """Sincronizar insight importante com Byterover"""
        try:
            # Usar ferramenta Byterover se disponível
            from ..ai.memory_store import MemoryStore  # Import lazy

            # Preparar conteúdo para Byterover
            insight_content = f"""
            Insight Importante - AgenteCAD:
            Tipo: {packet.metadata.get('event_type', 'unknown')}
            Modalidade: {packet.modality.value}
            Conteúdo: {packet.content}
            Contexto: {packet.context.current_module}
            Timestamp: {packet.timestamp.isoformat()}
            """

            # Armazenar no Byterover (simulado por enquanto)
            logger.info(f"📤 Sincronizando insight com Byterover: {packet.id}")

        except ImportError:
            logger.warning("Byterover não disponível para sincronização")
        except Exception as e:
            logger.error(f"Erro na sincronização Byterover: {e}")

    def _maintain_consciousness(self) -> None:
        """Manter nível de consciência baseado na atividade"""
        time_since_interaction = datetime.now() - self.current_context.last_interaction

        # Decair consciência com inatividade
        if time_since_interaction > timedelta(minutes=30):
            self.current_context.consciousness_level = max(0.1, self.current_context.consciousness_level * 0.95)
        else:
            self.current_context.consciousness_level = min(1.0, self.current_context.consciousness_level * 1.02)

    def _update_memory_stats(self, tier: MemoryTier) -> None:
        """Atualizar estatísticas de memória"""
        tier_name = tier.value
        self.current_context.memory_state[tier_name]["size"] += 1
        self.current_context.memory_state[tier_name]["last_update"] = datetime.now()

    def get_health_status(self) -> Dict[str, Any]:
        """Retornar status de saúde do sistema de memória"""
        return {
            "agent_id": self.agent_id,
            "consciousness_level": self.current_context.consciousness_level,
            "memory_stats": self.current_context.memory_state,
            "operation_stats": self.stats,
            "last_health_check": datetime.now()
        }


class ShortTermMemory:
    """Memória de Curto Prazo - RAM/Redis-like"""

    def __init__(self):
        self.cache = {}
        self.access_times = {}

    def store(self, data: Dict[str, Any]) -> bool:
        """Armazenar em memória curta"""
        key = data["key"]
        ttl = data.get("ttl", 3600)  # 1 hora padrão

        self.cache[key] = data["data"]
        self.access_times[key] = datetime.now() + timedelta(seconds=ttl)

        # Limpeza automática
        self._cleanup_expired()

        return True

    def retrieve(self, query: Dict[str, Any]) -> List[Dict]:
        """Recuperar da memória curta"""
        self._cleanup_expired()

        key = query.get("key")
        if key and key in self.cache:
            return [self.cache[key]]

        # Busca por padrões
        pattern = query.get("pattern", "")
        results = []

        for k, v in self.cache.items():
            if pattern in k or pattern in str(v):
                results.append(v)

        return results

    def _cleanup_expired(self) -> None:
        """Limpar entradas expiradas"""
        now = datetime.now()
        expired_keys = [k for k, expiry in self.access_times.items() if expiry < now]

        for key in expired_keys:
            del self.cache[key]
            del self.access_times[key]


class LongTermMemory:
    """Interface para Memória de Longo Prazo - Byterover Cloud"""

    def __init__(self):
        self.offline_queue = []  # Fila para quando Byterover estiver offline

    def store(self, data: Dict[str, Any]) -> bool:
        """Armazenar em Byterover (simulado por enquanto)"""
        try:
            # TODO: Implementar integração real com Byterover
            logger.info(f"📦 Enfileirado para Byterover: {data.get('content', '')[:100]}...")
            self.offline_queue.append(data)
            return True
        except Exception as e:
            logger.error(f"Erro ao enfileirar para Byterover: {e}")
            return False

    def retrieve(self, query: Dict[str, Any]) -> List[Dict]:
        """Recuperar do Byterover (placeholder)"""
        # TODO: Implementar busca real no Byterover
        return []


class ConsciousnessMonitor:
    """Monitor de Consciência - Mantém awareness do sistema"""

    def __init__(self, agent: 'AgentIdentity'):
        self.agent = agent
        self.thought_patterns = []
        self.awareness_triggers = {
            "memory_pressure": self._handle_memory_pressure,
            "context_switch": self._handle_context_switch,
            "error_spike": self._handle_error_spike
        }

    def _handle_memory_pressure(self) -> None:
        """Lidar com pressão de memória"""
        logger.info("🧠 Detectada pressão de memória - otimizando...")

    def _handle_context_switch(self) -> None:
        """Lidar com mudança de contexto"""
        logger.info("🔄 Mudança de contexto detectada - atualizando consciência...")

    def _handle_error_spike(self) -> None:
        """Lidar com pico de erros"""
        logger.warning("⚠️ Pico de erros detectado - aumentando vigilância...")


# Função utilitária para criar pacotes de memória
def create_memory_packet(
    content: Any,
    tier: MemoryTier,
    modality: ModalityType,
    context: AgentContext,
    metadata: Dict[str, Any] = None,
    ttl: int = None
) -> MemoryPacket:
    """Factory para criar pacotes de memória padronizados"""
    return MemoryPacket(
        id=str(uuid.uuid4()),
        tier=tier,
        modality=modality,
        content=content,
        metadata=metadata or {},
        context=context,
        timestamp=datetime.now(),
        ttl=ttl
    )