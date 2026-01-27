"""
Vector Trajectory - Blockchain de Pensamentos

Implementa uma cadeia sequencial de estados vetoriais com hash encadeado,
permitindo rastrear, auditar e debugar a trajetoria de raciocinio da IA.
"""

from __future__ import annotations
import hashlib
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from pydantic import BaseModel, Field, ConfigDict


class TrajectoryPhase(str, Enum):
    """Fases da trajetoria de raciocinio."""
    PERCEPTION = "perception"           # Percepcao visual/geometrica
    INTERPRETATION = "interpretation"   # Interpretacao logica
    VALIDATION = "validation"           # Validacao estrutural
    GENERATION = "generation"           # Geracao de output
    SYNTHESIS = "synthesis"             # Sintese final


class TrajectoryNodeModel(BaseModel):
    """Modelo Pydantic para um no da trajetoria."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    node_id: str = Field(..., description="ID unico do no")
    phase: TrajectoryPhase = Field(..., description="Fase do raciocinio")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Vetor de estado
    vector: List[float] = Field(..., description="Embedding do estado")
    vector_dimension: int = Field(..., description="Dimensao do vetor")
    
    # Metadados do momento
    metadata: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    
    # Hash encadeado (blockchain)
    prev_hash: Optional[str] = Field(None, description="Hash do no anterior")
    current_hash: str = Field(..., description="Hash deste no")
    
    # Debug info
    reasoning: Optional[str] = Field(None, description="Explicacao do raciocinio")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    
    def compute_hash(self) -> str:
        """Computa hash SHA-256 do no."""
        data = {
            "node_id": self.node_id,
            "phase": self.phase.value,
            "timestamp": self.timestamp.isoformat(),
            "vector": self.vector[:10] if self.vector else [],  # Primeiros 10 para hash
            "prev_hash": self.prev_hash
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()


@dataclass
class TrajectoryNode:
    """
    No individual na cadeia de trajetoria.
    
    Cada no representa um estado do raciocinio da IA,
    encadeado ao anterior via hash (similar a blockchain).
    """
    node_id: str
    phase: TrajectoryPhase
    vector: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    reasoning: Optional[str] = None
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    prev_hash: Optional[str] = None
    current_hash: str = field(default="")
    
    def __post_init__(self):
        """Computa hash apos inicializacao."""
        if not self.current_hash:
            self.current_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Computa hash SHA-256 do no."""
        data = {
            "node_id": self.node_id,
            "phase": self.phase.value,
            "timestamp": self.timestamp.isoformat(),
            "vector_sample": self.vector[:10].tolist() if len(self.vector) > 10 else self.vector.tolist(),
            "prev_hash": self.prev_hash
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa no para dicionario."""
        return {
            "node_id": self.node_id,
            "phase": self.phase.value,
            "vector": self.vector.tolist(),
            "vector_dimension": len(self.vector),
            "metadata": self.metadata,
            "context": self.context,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "prev_hash": self.prev_hash,
            "current_hash": self.current_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TrajectoryNode:
        """Deserializa no de dicionario."""
        return cls(
            node_id=data["node_id"],
            phase=TrajectoryPhase(data["phase"]),
            vector=np.array(data["vector"]),
            metadata=data.get("metadata", {}),
            context=data.get("context", {}),
            reasoning=data.get("reasoning"),
            confidence=data.get("confidence", 0.0),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            prev_hash=data.get("prev_hash"),
            current_hash=data["current_hash"]
        )


class VectorTrajectory:
    """
    Cadeia completa de trajetoria de raciocinio.
    
    Gerencia uma sequencia de TrajectoryNodes, garantindo
    integridade via hashes encadeados e fornecendo
    interface para debug e auditoria.
    """
    
    def __init__(self, trajectory_id: Optional[str] = None):
        """
        Inicializa trajetoria.
        
        Args:
            trajectory_id: ID unico da trajetoria (auto-gerado se None)
        """
        self.trajectory_id = trajectory_id or self._generate_id()
        self.nodes: List[TrajectoryNode] = []
        self.created_at = datetime.now()
        self._node_counter = 0
    
    def _generate_id(self) -> str:
        """Gera ID unico para trajetoria."""
        return f"traj_{int(time.time() * 1000)}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
    
    def _generate_node_id(self) -> str:
        """Gera ID unico para no."""
        self._node_counter += 1
        return f"{self.trajectory_id}_node_{self._node_counter:04d}"
    
    def append(
        self,
        phase: TrajectoryPhase,
        vector: Union[np.ndarray, List[float]],
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        reasoning: Optional[str] = None,
        confidence: float = 0.0
    ) -> TrajectoryNode:
        """
        Adiciona novo no a trajetoria.
        
        Args:
            phase: Fase do raciocinio
            vector: Embedding do estado
            metadata: Metadados do momento
            context: Contexto adicional
            reasoning: Explicacao do raciocinio
            confidence: Nivel de confianca (0-1)
            
        Returns:
            No criado e adicionado
        """
        if isinstance(vector, list):
            vector = np.array(vector)
        
        # Hash do no anterior
        prev_hash = self.nodes[-1].current_hash if self.nodes else None
        
        # Criar no
        node = TrajectoryNode(
            node_id=self._generate_node_id(),
            phase=phase,
            vector=vector,
            metadata=metadata or {},
            context=context or {},
            reasoning=reasoning,
            confidence=confidence,
            prev_hash=prev_hash
        )
        
        self.nodes.append(node)
        return node
    
    def validate_chain(self) -> tuple[bool, Optional[str]]:
        """
        Valida integridade da cadeia de hashes.
        
        Returns:
            (is_valid, error_message)
        """
        for i, node in enumerate(self.nodes):
            # Verificar hash do no
            expected_hash = node._compute_hash()
            if node.current_hash != expected_hash:
                return False, f"Hash invalido no node {i}: {node.node_id}"
            
            # Verificar encadeamento
            if i > 0:
                if node.prev_hash != self.nodes[i-1].current_hash:
                    return False, f"Encadeamento quebrado no node {i}: {node.node_id}"
        
        return True, None
    
    def get_phase_nodes(self, phase: TrajectoryPhase) -> List[TrajectoryNode]:
        """Retorna todos os nos de uma fase especifica."""
        return [n for n in self.nodes if n.phase == phase]
    
    def get_debug_trail(self) -> List[Dict[str, Any]]:
        """
        Retorna trilha de debug para analise.
        
        Returns:
            Lista de dicionarios com info de debug de cada no
        """
        trail = []
        for i, node in enumerate(self.nodes):
            trail.append({
                "step": i + 1,
                "phase": node.phase.value,
                "reasoning": node.reasoning or "Sem explicacao",
                "confidence": node.confidence,
                "timestamp": node.timestamp.isoformat(),
                "vector_norm": float(np.linalg.norm(node.vector)),
                "hash": node.current_hash[:16] + "...",
                "metadata_keys": list(node.metadata.keys())
            })
        return trail
    
    def find_divergence_point(self, expected_trajectory: VectorTrajectory) -> Optional[int]:
        """
        Encontra ponto onde trajetoria divergiu do esperado.
        
        Args:
            expected_trajectory: Trajetoria esperada para comparacao
            
        Returns:
            Indice do ponto de divergencia ou None se identicas
        """
        min_len = min(len(self.nodes), len(expected_trajectory.nodes))
        
        for i in range(min_len):
            # Comparar fases
            if self.nodes[i].phase != expected_trajectory.nodes[i].phase:
                return i
            
            # Comparar vetores (similaridade coseno)
            v1 = self.nodes[i].vector
            v2 = expected_trajectory.nodes[i].vector
            
            if len(v1) == len(v2):
                similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
                if similarity < 0.9:  # Threshold de divergencia
                    return i
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa trajetoria completa."""
        return {
            "trajectory_id": self.trajectory_id,
            "created_at": self.created_at.isoformat(),
            "node_count": len(self.nodes),
            "nodes": [node.to_dict() for node in self.nodes]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VectorTrajectory:
        """Deserializa trajetoria de dicionario."""
        trajectory = cls(trajectory_id=data["trajectory_id"])
        trajectory.created_at = datetime.fromisoformat(data["created_at"])
        trajectory.nodes = [TrajectoryNode.from_dict(n) for n in data["nodes"]]
        trajectory._node_counter = len(trajectory.nodes)
        return trajectory
    
    def __len__(self) -> int:
        return len(self.nodes)
    
    def __getitem__(self, index: int) -> TrajectoryNode:
        return self.nodes[index]
    
    def __repr__(self) -> str:
        return f"VectorTrajectory(id={self.trajectory_id}, nodes={len(self.nodes)})"
