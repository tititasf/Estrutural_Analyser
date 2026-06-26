"""
Interpreter Agent - Agente de Interpretação

Responsável por interpretar, classificar e contextualizar elementos.
"""

from typing import Dict, Any, List, Optional
import json
from .base_agent import BaseAgent, AgentConfig, AgentRole


class InterpreterAgent(BaseAgent):
    """
    Agente especializado em interpretação lógica.
    
    Responsabilidades:
    - Classificar elementos por tipo e formato
    - Associar textos aos elementos
    - Criar relações entre elementos (pilar-viga, viga-laje)
    - Gerar contexto semântico
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="interpreter_agent",
                role=AgentRole.INTERPRETER,
                system_prompt=self._get_system_prompt(),
                tools=["classify_element", "associate_text", "build_relations"]
            )
        super().__init__(config)
        
        self._register_tools()
    
    def _get_system_prompt(self) -> str:
        return """Você é um agente de interpretação especializado em análise estrutural.

Suas responsabilidades:
1. Classificar pilares por formato (RETANGULAR, CIRCULAR, L, T, U)
2. Associar textos (nomes, dimensões) aos elementos corretos
3. Identificar relações: qual viga chega em qual pilar, qual laje toca qual viga
4. Gerar contexto semântico para cada elemento

Regras de classificação de faces de pilares:
- RETANGULAR: faces A, B, C, D
- CIRCULAR: sem faces (topo/fundo)
- L: faces A-F
- T: faces A-H
- U: faces A-H

Responda sempre em JSON estruturado."""
    
    def _register_tools(self):
        self.register_tool("classify_element", self._tool_classify)
        self.register_tool("associate_text", self._tool_associate_text)
        self.register_tool("build_relations", self._tool_build_relations)
    
    def think(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Planeja interpretação."""
        plan = {
            "steps": [],
            "elements_to_process": [],
            "relation_types": []
        }
        
        # Identificar elementos a processar
        elements = input_data.get("elements", {})
        texts = input_data.get("texts", [])
        
        # Pilares
        if elements.get("pilares"):
            plan["steps"].append({
                "action": "classify_pilares",
                "params": {"pilares": elements["pilares"]}
            })
            plan["elements_to_process"].extend(elements["pilares"])
        
        # Vigas
        if elements.get("vigas"):
            plan["steps"].append({
                "action": "classify_vigas",
                "params": {"vigas": elements["vigas"]}
            })
        
        # Lajes
        if elements.get("lajes"):
            plan["steps"].append({
                "action": "classify_lajes",
                "params": {"lajes": elements["lajes"]}
            })
        
        # Associar textos
        if texts:
            plan["steps"].append({
                "action": "associate_texts",
                "params": {"texts": texts}
            })
        
        # Construir relações
        plan["steps"].append({
            "action": "build_relations",
            "params": {}
        })
        
        plan["relation_types"] = ["pilar_viga", "pilar_laje", "viga_laje"]
        
        return plan
    
    def act(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Executa interpretação."""
        result = {
            "status": "success",
            "classified_elements": {
                "pilares": [],
                "vigas": [],
                "lajes": []
            },
            "text_associations": [],
            "relations": {
                "pilar_viga": [],
                "pilar_laje": [],
                "viga_laje": []
            },
            "context": {}
        }
        
        for step in plan["steps"]:
            action = step["action"]
            params = step["params"]
            
            if action == "classify_pilares":
                for pilar in params.get("pilares", []):
                    classified = self.use_tool("classify_element", 
                                               element=pilar, 
                                               element_type="pilar")
                    result["classified_elements"]["pilares"].append(classified)
            
            elif action == "classify_vigas":
                for viga in params.get("vigas", []):
                    classified = self.use_tool("classify_element",
                                               element=viga,
                                               element_type="viga")
                    result["classified_elements"]["vigas"].append(classified)
            
            elif action == "classify_lajes":
                for laje in params.get("lajes", []):
                    classified = self.use_tool("classify_element",
                                               element=laje,
                                               element_type="laje")
                    result["classified_elements"]["lajes"].append(classified)
            
            elif action == "associate_texts":
                associations = self.use_tool("associate_text",
                                            texts=params.get("texts", []),
                                            elements=result["classified_elements"])
                result["text_associations"] = associations
            
            elif action == "build_relations":
                relations = self.use_tool("build_relations",
                                         elements=result["classified_elements"])
                result["relations"] = relations
        
        return result
    
    def observe(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Analisa resultado da interpretação."""
        observations = {
            "success": result["status"] == "success",
            "classification_stats": {},
            "relation_stats": {},
            "issues": [],
            "quality_score": 0.0
        }
        
        # Estatísticas de classificação
        for elem_type, elems in result["classified_elements"].items():
            classified = len([e for e in elems if e.get("classification")])
            total = len(elems)
            observations["classification_stats"][elem_type] = {
                "classified": classified,
                "total": total,
                "ratio": classified / total if total > 0 else 0
            }
        
        # Estatísticas de relações
        for rel_type, rels in result["relations"].items():
            observations["relation_stats"][rel_type] = len(rels)
        
        # Calcular score de qualidade
        total_elements = sum(
            stats["total"] 
            for stats in observations["classification_stats"].values()
        )
        total_classified = sum(
            stats["classified"] 
            for stats in observations["classification_stats"].values()
        )
        
        if total_elements > 0:
            observations["quality_score"] = total_classified / total_elements
        
        # Identificar problemas
        if observations["quality_score"] < 0.8:
            observations["issues"].append("Baixa taxa de classificação")
        
        if sum(observations["relation_stats"].values()) == 0:
            observations["issues"].append("Nenhuma relação identificada")
        
        return observations
    
    # ==================== TOOLS ====================
    
    def _tool_classify(self, element: Dict, element_type: str) -> Dict[str, Any]:
        """Classifica um elemento."""
        classified = element.copy()
        
        if element_type == "pilar":
            # Determinar formato baseado na geometria
            vertices = element.get("vertices", [])
            if len(vertices) == 4:
                classified["formato"] = "RETANGULAR"
                classified["faces"] = ["A", "B", "C", "D"]
            else:
                classified["formato"] = "COMPLEXO"
        
        elif element_type == "viga":
            classified["lados"] = ["A", "B"]
        
        elif element_type == "laje":
            vertices = element.get("vertices", [])
            classified["tipo_geometria"] = "RETANGULAR" if len(vertices) == 4 else "COMPLEXA"
        
        classified["classification"] = True
        return classified
    
    def _tool_associate_text(self, texts: List[Dict], elements: Dict) -> List[Dict]:
        """Associa textos aos elementos."""
        associations = []
        
        for text in texts:
            association = {
                "text": text,
                "associated_to": None,
                "confidence": 0.0
            }
            
            # Lógica simples de associação por proximidade
            # Em produção, usaria spatial index
            
            associations.append(association)
        
        return associations
    
    def _tool_build_relations(self, elements: Dict) -> Dict[str, List]:
        """Constrói relações entre elementos."""
        relations = {
            "pilar_viga": [],
            "pilar_laje": [],
            "viga_laje": []
        }
        
        # Em produção, analisaria geometria para encontrar relações
        # Aqui apenas retorna estrutura vazia
        
        return relations
