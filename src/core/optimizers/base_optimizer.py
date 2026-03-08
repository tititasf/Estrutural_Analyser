from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseOptimizer(ABC):
    """
    Interface base para os motores de otimização da Fase 8.
    """
    
    @abstractmethod
    def optimize(self, elements: List[Dict[str, Any]], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa a otimização sobre os elementos estruturais/geométricos fornecidos.
        
        Args:
            elements: Lista de dicionários representando os elementos estruturais.
            context: Contexto adicional da obra (opcional).
            
        Returns:
            Dicionário com os resultados da otimização (ex: plano de corte, peças, eficiência).
        """
        pass
        
    @abstractmethod
    def report(self) -> str:
        """
        Gera um relatório legível ou estruturado dos resultados.
        """
        pass
