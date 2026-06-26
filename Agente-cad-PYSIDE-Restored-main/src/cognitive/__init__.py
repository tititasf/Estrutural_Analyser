"""
Cognitive System - AgenteCAD

Sistema Operacional Cognitivo com CausalVectorEngine e RAG Dialetico.
"""

from .vector_trajectory import VectorTrajectory, TrajectoryNode
from .causal_engine import CausalVectorEngine
from .rag_dialectic import RAGDialectic

__all__ = [
    'VectorTrajectory',
    'TrajectoryNode', 
    'CausalVectorEngine',
    'RAGDialectic'
]
