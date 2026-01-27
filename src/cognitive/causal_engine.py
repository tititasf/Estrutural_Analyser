"""
Causal Vector Engine - Motor de Raciocinio Causal

Motor de raciocinio que mantém trajetória rastreável e auditável,
implementando RAG Dialético (Tese → Antítese → Síntese).
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional, Callable, Protocol
from dataclasses import dataclass
from abc import ABC, abstractmethod
import numpy as np

from .vector_trajectory import VectorTrajectory, TrajectoryNode, TrajectoryPhase

logger = logging.getLogger(__name__)


class VectorStore(Protocol):
    """Interface abstrata para banco de dados vetorial."""
    
    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        """Busca k vizinhos mais proximos."""
        ...
    
    def add(self, vector: np.ndarray, metadata: Dict[str, Any]) -> str:
        """Adiciona vetor ao banco."""
        ...


class EmbeddingModel(Protocol):
    """Interface abstrata para modelo de embeddings."""
    
    def encode(self, text: str) -> np.ndarray:
        """Gera embedding de texto."""
        ...
    
    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Gera embeddings em batch."""
        ...


@dataclass
class SearchResult:
    """Resultado de uma busca vetorial."""
    content: str
    vector: np.ndarray
    similarity: float
    metadata: Dict[str, Any]
    source: str  # "thesis", "antithesis", ou "synthesis"


@dataclass 
class ReasoningStep:
    """Passo individual no raciocinio."""
    phase: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    reasoning: str
    confidence: float
    vector: Optional[np.ndarray] = None


class CausalVectorEngine:
    """
    Motor de Raciocinio Causal com RAG Dialetico.
    
    Implementa um sistema de raciocinio onde cada passo e rastreavel,
    usando o paradigma Tese → Antitese → Sintese para profundidade artificial.
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_model: Optional[EmbeddingModel] = None,
        similarity_threshold: float = 0.7
    ):
        """
        Inicializa o motor causal.
        
        Args:
            vector_store: Banco de dados vetorial (None = mock)
            embedding_model: Modelo de embeddings (None = mock)
            similarity_threshold: Limiar de similaridade para matches
        """
        self.vector_store = vector_store or MockVectorStore()
        self.embedding_model = embedding_model or MockEmbeddingModel()
        self.similarity_threshold = similarity_threshold
        
        # Trajetoria atual
        self.current_trajectory: Optional[VectorTrajectory] = None
        
        # Historico de trajetorias
        self.trajectory_history: List[VectorTrajectory] = []
        
        # Callbacks para extensao
        self._pre_thesis_hooks: List[Callable] = []
        self._post_synthesis_hooks: List[Callable] = []
    
    def start_trajectory(self, context: Optional[Dict[str, Any]] = None) -> VectorTrajectory:
        """
        Inicia nova trajetoria de raciocinio.
        
        Args:
            context: Contexto inicial (opcional)
            
        Returns:
            Nova trajetoria
        """
        self.current_trajectory = VectorTrajectory()
        
        if context:
            # Adicionar no inicial com contexto
            context_vector = self._encode_context(context)
            self.current_trajectory.append(
                phase=TrajectoryPhase.PERCEPTION,
                vector=context_vector,
                context=context,
                reasoning="Inicio da trajetoria com contexto inicial",
                confidence=1.0
            )
        
        return self.current_trajectory
    
    def _encode_context(self, context: Dict[str, Any]) -> np.ndarray:
        """Codifica contexto em vetor."""
        # Serializar contexto para texto
        context_str = " ".join([f"{k}: {v}" for k, v in context.items() if v])
        return self.embedding_model.encode(context_str)
    
    # ==================== RAG DIALETICO ====================
    
    def thesis(self, query: str, k: int = 5) -> List[SearchResult]:
        """
        Passo 1 do RAG Dialetico: TESE
        
        Gera vetor da query inicial e busca resultados.
        
        Args:
            query: Query em linguagem natural
            k: Numero de resultados
            
        Returns:
            Lista de resultados iniciais
        """
        # Executar hooks pre-thesis
        for hook in self._pre_thesis_hooks:
            hook(query)
        
        # Gerar embedding da query
        query_vector = self.embedding_model.encode(query)
        
        # Registrar na trajetoria
        if self.current_trajectory:
            self.current_trajectory.append(
                phase=TrajectoryPhase.PERCEPTION,
                vector=query_vector,
                metadata={"query": query, "k": k},
                reasoning=f"TESE: Busca inicial para '{query}'",
                confidence=0.8
            )
        
        # Buscar no vector store
        raw_results = self.vector_store.search(query_vector, k=k)
        
        # Converter para SearchResult
        results = []
        for r in raw_results:
            results.append(SearchResult(
                content=r.get("content", ""),
                vector=np.array(r.get("vector", [])),
                similarity=r.get("similarity", 0.0),
                metadata=r.get("metadata", {}),
                source="thesis"
            ))
        
        return results
    
    def antithesis(
        self, 
        thesis_results: List[SearchResult],
        original_query: str,
        k: int = 3
    ) -> List[SearchResult]:
        """
        Passo 2 do RAG Dialetico: ANTITESE
        
        Analisa lacunas/falhas do resultado inicial e gera busca corretiva.
        
        Args:
            thesis_results: Resultados da tese
            original_query: Query original
            k: Numero de resultados corretivos
            
        Returns:
            Lista de resultados corretivos
        """
        # Analisar lacunas
        gaps = self._analyze_gaps(thesis_results, original_query)
        
        if not gaps:
            # Sem lacunas identificadas
            if self.current_trajectory:
                self.current_trajectory.append(
                    phase=TrajectoryPhase.INTERPRETATION,
                    vector=np.zeros(384),  # Placeholder
                    metadata={"gaps": []},
                    reasoning="ANTITESE: Nenhuma lacuna identificada",
                    confidence=0.9
                )
            return []
        
        # Gerar query corretiva
        corrective_query = self._generate_corrective_query(gaps, original_query)
        corrective_vector = self.embedding_model.encode(corrective_query)
        
        # Registrar na trajetoria
        if self.current_trajectory:
            self.current_trajectory.append(
                phase=TrajectoryPhase.INTERPRETATION,
                vector=corrective_vector,
                metadata={
                    "gaps": gaps,
                    "corrective_query": corrective_query
                },
                reasoning=f"ANTITESE: Corrigindo lacunas - '{corrective_query}'",
                confidence=0.7
            )
        
        # Buscar resultados corretivos
        raw_results = self.vector_store.search(corrective_vector, k=k)
        
        results = []
        for r in raw_results:
            results.append(SearchResult(
                content=r.get("content", ""),
                vector=np.array(r.get("vector", [])),
                similarity=r.get("similarity", 0.0),
                metadata=r.get("metadata", {}),
                source="antithesis"
            ))
        
        return results
    
    def synthesis(
        self,
        thesis_results: List[SearchResult],
        antithesis_results: List[SearchResult],
        original_query: str
    ) -> Dict[str, Any]:
        """
        Passo 3 do RAG Dialetico: SINTESE
        
        Combina contextos para gerar resposta final densa.
        
        Args:
            thesis_results: Resultados da tese
            antithesis_results: Resultados da antitese
            original_query: Query original
            
        Returns:
            Resposta sintetizada com contexto denso
        """
        # Combinar todos os resultados
        all_results = thesis_results + antithesis_results
        
        # Rankear por relevancia
        ranked_results = sorted(
            all_results,
            key=lambda x: x.similarity,
            reverse=True
        )
        
        # Construir contexto denso
        context_parts = []
        for i, result in enumerate(ranked_results[:5]):  # Top 5
            context_parts.append({
                "rank": i + 1,
                "content": result.content,
                "source": result.source,
                "similarity": result.similarity
            })
        
        # Gerar vetor de sintese
        if ranked_results:
            synthesis_vector = np.mean([r.vector for r in ranked_results if len(r.vector) > 0], axis=0)
        else:
            synthesis_vector = self.embedding_model.encode(original_query)
        
        # Registrar na trajetoria
        if self.current_trajectory:
            self.current_trajectory.append(
                phase=TrajectoryPhase.SYNTHESIS,
                vector=synthesis_vector,
                metadata={
                    "thesis_count": len(thesis_results),
                    "antithesis_count": len(antithesis_results),
                    "total_combined": len(all_results)
                },
                context={"ranked_results": context_parts},
                reasoning="SINTESE: Combinacao de tese e antitese",
                confidence=min(0.95, max(r.similarity for r in ranked_results) if ranked_results else 0.5)
            )
        
        # Executar hooks pos-sintese
        for hook in self._post_synthesis_hooks:
            hook(context_parts)
        
        return {
            "query": original_query,
            "dense_context": context_parts,
            "synthesis_vector": synthesis_vector.tolist(),
            "confidence": self.current_trajectory.nodes[-1].confidence if self.current_trajectory else 0.5,
            "trajectory_id": self.current_trajectory.trajectory_id if self.current_trajectory else None
        }
    
    def dialectic_search(self, query: str, k_thesis: int = 5, k_antithesis: int = 3) -> Dict[str, Any]:
        """
        Executa busca dialetica completa (Tese → Antitese → Sintese).
        
        Args:
            query: Query em linguagem natural
            k_thesis: Resultados da tese
            k_antithesis: Resultados da antitese
            
        Returns:
            Resposta sintetizada
        """
        # Iniciar trajetoria se nao existir
        if not self.current_trajectory:
            self.start_trajectory({"query": query})
        
        # Passo 1: TESE
        thesis_results = self.thesis(query, k=k_thesis)
        
        # Passo 2: ANTITESE
        antithesis_results = self.antithesis(thesis_results, query, k=k_antithesis)
        
        # Passo 3: SINTESE
        synthesis_result = self.synthesis(thesis_results, antithesis_results, query)
        
        # Finalizar trajetoria
        self.end_trajectory()
        
        return synthesis_result
    
    def _analyze_gaps(self, results: List[SearchResult], query: str) -> List[str]:
        """Analisa lacunas nos resultados."""
        gaps = []
        
        # Gap 1: Baixa similaridade geral
        if results:
            avg_similarity = sum(r.similarity for r in results) / len(results)
            if avg_similarity < self.similarity_threshold:
                gaps.append(f"Baixa similaridade media ({avg_similarity:.2f})")
        
        # Gap 2: Poucos resultados
        if len(results) < 3:
            gaps.append("Poucos resultados encontrados")
        
        # Gap 3: Diversidade baixa (resultados muito similares entre si)
        if len(results) >= 2:
            vectors = [r.vector for r in results if len(r.vector) > 0]
            if vectors:
                similarities = []
                for i in range(len(vectors)):
                    for j in range(i+1, len(vectors)):
                        sim = np.dot(vectors[i], vectors[j]) / (
                            np.linalg.norm(vectors[i]) * np.linalg.norm(vectors[j]) + 1e-9
                        )
                        similarities.append(sim)
                if similarities and np.mean(similarities) > 0.95:
                    gaps.append("Resultados muito homogeneos")
        
        return gaps
    
    def _generate_corrective_query(self, gaps: List[str], original_query: str) -> str:
        """Gera query corretiva baseada nas lacunas."""
        # Estrategia simples: adicionar modificadores
        modifiers = []
        
        if "Baixa similaridade" in str(gaps):
            modifiers.append("alternativo")
        if "Poucos resultados" in str(gaps):
            modifiers.append("similar a")
        if "homogeneos" in str(gaps):
            modifiers.append("diferente abordagem")
        
        if modifiers:
            return f"{' '.join(modifiers)} {original_query}"
        return original_query
    
    # ==================== TRAJETORIA ====================
    
    def end_trajectory(self) -> Optional[VectorTrajectory]:
        """
        Finaliza trajetoria atual e armazena no historico.
        
        Returns:
            Trajetoria finalizada
        """
        if self.current_trajectory:
            # Validar cadeia
            is_valid, error = self.current_trajectory.validate_chain()
            if not is_valid:
                logger.warning(f"Trajetoria invalida: {error}")
            
            # Adicionar ao historico
            self.trajectory_history.append(self.current_trajectory)
            
            trajectory = self.current_trajectory
            self.current_trajectory = None
            return trajectory
        
        return None
    
    def get_debug_info(self) -> Dict[str, Any]:
        """
        Retorna informacoes de debug da trajetoria atual.
        
        Returns:
            Dicionario com info de debug
        """
        if not self.current_trajectory:
            return {"error": "Nenhuma trajetoria ativa"}
        
        is_valid, error = self.current_trajectory.validate_chain()
        
        return {
            "trajectory_id": self.current_trajectory.trajectory_id,
            "node_count": len(self.current_trajectory),
            "is_valid": is_valid,
            "validation_error": error,
            "debug_trail": self.current_trajectory.get_debug_trail(),
            "phases_covered": list(set(n.phase.value for n in self.current_trajectory.nodes))
        }
    
    def diagnose_failure(self, trajectory: Optional[VectorTrajectory] = None) -> Dict[str, Any]:
        """
        Diagnostica falhas na trajetoria de raciocinio.
        
        Args:
            trajectory: Trajetoria a diagnosticar (default: atual)
            
        Returns:
            Diagnostico detalhado
        """
        traj = trajectory or self.current_trajectory
        if not traj:
            return {"error": "Nenhuma trajetoria para diagnosticar"}
        
        diagnosis = {
            "trajectory_id": traj.trajectory_id,
            "issues": [],
            "recommendations": []
        }
        
        # Analisar cada no
        for i, node in enumerate(traj.nodes):
            # Issue: Confianca baixa
            if node.confidence < 0.5:
                diagnosis["issues"].append({
                    "step": i + 1,
                    "phase": node.phase.value,
                    "issue": "Baixa confianca",
                    "value": node.confidence
                })
                diagnosis["recommendations"].append(
                    f"Revisar logica na fase {node.phase.value}"
                )
            
            # Issue: Vetor anomalo (norma muito baixa ou alta)
            norm = np.linalg.norm(node.vector)
            if norm < 0.1 or norm > 100:
                diagnosis["issues"].append({
                    "step": i + 1,
                    "phase": node.phase.value,
                    "issue": "Vetor anomalo",
                    "value": float(norm)
                })
        
        # Issue: Falta de fases
        covered_phases = set(n.phase for n in traj.nodes)
        expected_phases = {TrajectoryPhase.PERCEPTION, TrajectoryPhase.INTERPRETATION}
        missing = expected_phases - covered_phases
        if missing:
            diagnosis["issues"].append({
                "issue": "Fases faltantes",
                "missing": [p.value for p in missing]
            })
        
        return diagnosis


# ==================== MOCKS PARA TESTE ====================

class MockVectorStore:
    """Mock de vector store para testes."""
    
    def __init__(self):
        self.vectors: List[Dict[str, Any]] = []
    
    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        """Busca simulada."""
        # Retornar resultados mock
        return [
            {
                "content": f"Resultado mock {i+1}",
                "vector": np.random.randn(384).tolist(),
                "similarity": 0.8 - (i * 0.1),
                "metadata": {"mock": True}
            }
            for i in range(min(k, 5))
        ]
    
    def add(self, vector: np.ndarray, metadata: Dict[str, Any]) -> str:
        """Adiciona vetor simulado."""
        doc_id = f"mock_{len(self.vectors)}"
        self.vectors.append({
            "id": doc_id,
            "vector": vector.tolist(),
            "metadata": metadata
        })
        return doc_id


class MockEmbeddingModel:
    """Mock de modelo de embeddings para testes."""
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
    
    def encode(self, text: str) -> np.ndarray:
        """Gera embedding mock."""
        # Usar hash do texto como seed para reproducibilidade
        seed = hash(text) % (2**32)
        np.random.seed(seed)
        return np.random.randn(self.dimension).astype(np.float32)
    
    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Gera embeddings em batch."""
        return np.array([self.encode(t) for t in texts])
