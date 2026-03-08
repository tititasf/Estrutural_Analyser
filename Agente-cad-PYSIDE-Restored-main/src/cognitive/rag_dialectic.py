"""
RAG Dialectic - Retrieval Augmented Generation com Dialética

Implementa o paradigma Tese → Antítese → Síntese para
criar profundidade artificial nas respostas.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class DialecticPhase(str, Enum):
    """Fases do processo dialético."""
    THESIS = "thesis"
    ANTITHESIS = "antithesis"
    SYNTHESIS = "synthesis"


@dataclass
class DialecticStep:
    """Passo individual no processo dialético."""
    phase: DialecticPhase
    query: str
    results: List[Dict[str, Any]]
    reasoning: str
    vector: Optional[np.ndarray] = None
    confidence: float = 0.0
    gaps_found: List[str] = field(default_factory=list)


@dataclass
class DialecticResult:
    """Resultado completo do processo dialético."""
    original_query: str
    steps: List[DialecticStep]
    final_context: List[Dict[str, Any]]
    synthesis_vector: Optional[np.ndarray] = None
    overall_confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_dense_context(self) -> str:
        """Retorna contexto denso como texto."""
        parts = []
        for i, ctx in enumerate(self.final_context):
            parts.append(f"[{i+1}] {ctx.get('content', '')}")
        return "\n\n".join(parts)
    
    def get_thesis_results(self) -> List[Dict[str, Any]]:
        """Retorna resultados da tese."""
        for step in self.steps:
            if step.phase == DialecticPhase.THESIS:
                return step.results
        return []
    
    def get_antithesis_results(self) -> List[Dict[str, Any]]:
        """Retorna resultados da antítese."""
        for step in self.steps:
            if step.phase == DialecticPhase.ANTITHESIS:
                return step.results
        return []


class RAGDialectic:
    """
    Implementação de RAG com processo dialético.
    
    O processo segue três passos:
    1. TESE: Busca inicial com a query original
    2. ANTÍTESE: Análise de gaps e busca corretiva
    3. SÍNTESE: Combinação para resposta densa
    """
    
    def __init__(
        self,
        search_fn: Optional[Callable[[np.ndarray, int], List[Dict]]] = None,
        embed_fn: Optional[Callable[[str], np.ndarray]] = None,
        similarity_threshold: float = 0.7,
        max_iterations: int = 3
    ):
        """
        Inicializa RAG Dialético.
        
        Args:
            search_fn: Função de busca (query_vector, k) -> results
            embed_fn: Função de embedding (text) -> vector
            similarity_threshold: Limiar para considerar resultado bom
            max_iterations: Máximo de iterações de refinamento
        """
        self._search = search_fn or self._mock_search
        self._embed = embed_fn or self._mock_embed
        self.similarity_threshold = similarity_threshold
        self.max_iterations = max_iterations
    
    def process(
        self,
        query: str,
        k_thesis: int = 5,
        k_antithesis: int = 3
    ) -> DialecticResult:
        """
        Executa processo dialético completo.
        
        Args:
            query: Query em linguagem natural
            k_thesis: Número de resultados na tese
            k_antithesis: Número de resultados na antítese
            
        Returns:
            Resultado dialético completo
        """
        steps = []
        
        # ========== PASSO 1: TESE ==========
        thesis_step = self._execute_thesis(query, k_thesis)
        steps.append(thesis_step)
        
        # ========== PASSO 2: ANTÍTESE ==========
        antithesis_step = self._execute_antithesis(
            thesis_step.results,
            query,
            k_antithesis
        )
        steps.append(antithesis_step)
        
        # ========== PASSO 3: SÍNTESE ==========
        synthesis_step = self._execute_synthesis(
            thesis_step.results,
            antithesis_step.results,
            query
        )
        steps.append(synthesis_step)
        
        # Construir resultado final
        return DialecticResult(
            original_query=query,
            steps=steps,
            final_context=synthesis_step.results,
            synthesis_vector=synthesis_step.vector,
            overall_confidence=synthesis_step.confidence,
            metadata={
                "thesis_count": len(thesis_step.results),
                "antithesis_count": len(antithesis_step.results),
                "gaps_found": antithesis_step.gaps_found
            }
        )
    
    def _execute_thesis(self, query: str, k: int) -> DialecticStep:
        """Executa fase de tese."""
        # Gerar embedding
        query_vector = self._embed(query)
        
        # Buscar
        results = self._search(query_vector, k)
        
        # Calcular confiança média
        confidence = np.mean([r.get("similarity", 0) for r in results]) if results else 0
        
        return DialecticStep(
            phase=DialecticPhase.THESIS,
            query=query,
            results=results,
            reasoning=f"Busca inicial para: {query}",
            vector=query_vector,
            confidence=float(confidence)
        )
    
    def _execute_antithesis(
        self,
        thesis_results: List[Dict[str, Any]],
        original_query: str,
        k: int
    ) -> DialecticStep:
        """Executa fase de antítese."""
        # Analisar gaps
        gaps = self._find_gaps(thesis_results)
        
        if not gaps:
            return DialecticStep(
                phase=DialecticPhase.ANTITHESIS,
                query="",
                results=[],
                reasoning="Nenhuma lacuna identificada - tese suficiente",
                confidence=0.9,
                gaps_found=[]
            )
        
        # Gerar query corretiva
        corrective_query = self._generate_corrective_query(gaps, original_query)
        corrective_vector = self._embed(corrective_query)
        
        # Buscar
        results = self._search(corrective_vector, k)
        
        # Filtrar resultados já presentes na tese
        thesis_contents = {r.get("content", "") for r in thesis_results}
        new_results = [r for r in results if r.get("content", "") not in thesis_contents]
        
        confidence = np.mean([r.get("similarity", 0) for r in new_results]) if new_results else 0
        
        return DialecticStep(
            phase=DialecticPhase.ANTITHESIS,
            query=corrective_query,
            results=new_results,
            reasoning=f"Busca corretiva para gaps: {gaps}",
            vector=corrective_vector,
            confidence=float(confidence),
            gaps_found=gaps
        )
    
    def _execute_synthesis(
        self,
        thesis_results: List[Dict[str, Any]],
        antithesis_results: List[Dict[str, Any]],
        original_query: str
    ) -> DialecticStep:
        """Executa fase de síntese."""
        # Combinar resultados
        all_results = thesis_results + antithesis_results
        
        # Rankear por similaridade
        ranked = sorted(
            all_results,
            key=lambda x: x.get("similarity", 0),
            reverse=True
        )
        
        # Pegar top N
        top_results = ranked[:5]
        
        # Calcular vetor de síntese (média ponderada)
        if top_results:
            vectors = []
            weights = []
            for r in top_results:
                if "vector" in r and r["vector"] is not None:
                    v = r["vector"]
                    if isinstance(v, list):
                        v = np.array(v)
                    vectors.append(v)
                    weights.append(r.get("similarity", 1.0))
            
            if vectors:
                weights = np.array(weights) / sum(weights)
                synthesis_vector = np.average(vectors, axis=0, weights=weights)
            else:
                synthesis_vector = self._embed(original_query)
        else:
            synthesis_vector = self._embed(original_query)
        
        # Enriquecer resultados com source
        for r in top_results:
            if r in thesis_results:
                r["source"] = "thesis"
            else:
                r["source"] = "antithesis"
        
        confidence = np.mean([r.get("similarity", 0) for r in top_results]) if top_results else 0
        
        return DialecticStep(
            phase=DialecticPhase.SYNTHESIS,
            query=original_query,
            results=top_results,
            reasoning="Síntese de tese e antítese",
            vector=synthesis_vector,
            confidence=float(min(0.95, confidence))
        )
    
    def _find_gaps(self, results: List[Dict[str, Any]]) -> List[str]:
        """Identifica lacunas nos resultados."""
        gaps = []
        
        if not results:
            gaps.append("Nenhum resultado encontrado")
            return gaps
        
        # Gap: baixa similaridade
        avg_sim = np.mean([r.get("similarity", 0) for r in results])
        if avg_sim < self.similarity_threshold:
            gaps.append(f"Baixa similaridade média: {avg_sim:.2f}")
        
        # Gap: poucos resultados
        if len(results) < 3:
            gaps.append(f"Poucos resultados: {len(results)}")
        
        # Gap: resultados muito similares entre si
        if len(results) >= 2:
            contents = [r.get("content", "") for r in results]
            unique_ratio = len(set(contents)) / len(contents)
            if unique_ratio < 0.8:
                gaps.append("Resultados muito homogêneos")
        
        return gaps
    
    def _generate_corrective_query(self, gaps: List[str], original_query: str) -> str:
        """Gera query corretiva."""
        modifiers = []
        
        for gap in gaps:
            if "similaridade" in gap.lower():
                modifiers.append("alternativas para")
            elif "poucos" in gap.lower():
                modifiers.append("mais opções de")
            elif "homogêneos" in gap.lower():
                modifiers.append("diferentes abordagens para")
        
        if modifiers:
            return f"{' '.join(modifiers)} {original_query}"
        return f"expandir {original_query}"
    
    # ========== MOCKS ==========
    
    def _mock_search(self, query_vector: np.ndarray, k: int) -> List[Dict[str, Any]]:
        """Busca mock para testes."""
        return [
            {
                "content": f"Resultado mock {i+1}",
                "vector": np.random.randn(384).tolist(),
                "similarity": 0.85 - (i * 0.1),
                "metadata": {"mock": True, "index": i}
            }
            for i in range(min(k, 5))
        ]
    
    def _mock_embed(self, text: str) -> np.ndarray:
        """Embedding mock para testes."""
        np.random.seed(hash(text) % (2**32))
        return np.random.randn(384).astype(np.float32)
