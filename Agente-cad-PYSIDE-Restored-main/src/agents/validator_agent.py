"""
Validator Agent - Agente de Validação

Responsável por validar interpretações e pontuar resultados.
"""

from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent, AgentConfig, AgentRole


class ValidatorAgent(BaseAgent):
    """
    Agente especializado em validação estrutural.
    
    Responsabilidades:
    - Validar interpretações dos elementos
    - Comparar com padrões conhecidos
    - Pontuar qualidade dos resultados
    - Aprovar/Rejeitar interpretações
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="validator_agent",
                role=AgentRole.VALIDATOR,
                system_prompt=self._get_system_prompt(),
                tools=["validate_element", "compare_pattern", "score_result"]
            )
        super().__init__(config)
        self._register_tools()
    
    def _get_system_prompt(self) -> str:
        return """Você é um agente de validação especializado em verificar interpretações estruturais.

Suas responsabilidades:
1. Validar se as interpretações de pilares, vigas e lajes estão corretas
2. Comparar com padrões conhecidos no banco de vetores
3. Pontuar qualidade (0-100) de cada interpretação
4. Aprovar ou rejeitar interpretações com justificativa

Critérios de validação:
- Dimensões dentro de ranges válidos
- Relações geométricas consistentes
- Nomes seguindo padrões (P-1, V1, L1, etc)
- Associações texto-elemento corretas

Responda em JSON com 'approved', 'score', e 'issues'."""
    
    def _register_tools(self):
        self.register_tool("validate_element", self._tool_validate)
        self.register_tool("compare_pattern", self._tool_compare)
        self.register_tool("score_result", self._tool_score)
    
    def think(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Planeja validação."""
        plan = {
            "validation_steps": [],
            "elements_to_validate": [],
            "validation_rules": []
        }
        
        # Elementos a validar
        interpreted = input_data.get("interpreted_elements", {})
        
        for elem_type, elements in interpreted.items():
            for elem in elements:
                plan["elements_to_validate"].append({
                    "type": elem_type,
                    "element": elem
                })
                plan["validation_steps"].append({
                    "action": "validate",
                    "element_type": elem_type,
                    "element_id": elem.get("id", "unknown")
                })
        
        # Definir regras de validação
        plan["validation_rules"] = [
            {"rule": "dimension_range", "params": {"min": 10, "max": 500}},
            {"rule": "name_pattern", "params": {"patterns": ["P-", "V", "L"]}},
            {"rule": "relation_consistency", "params": {}}
        ]
        
        return plan
    
    def act(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Executa validação."""
        result = {
            "status": "success",
            "validations": [],
            "overall_score": 0.0,
            "approved_count": 0,
            "rejected_count": 0
        }
        
        scores = []
        
        for item in plan["elements_to_validate"]:
            validation = self.use_tool(
                "validate_element",
                element=item["element"],
                element_type=item["type"],
                rules=plan["validation_rules"]
            )
            
            result["validations"].append(validation)
            scores.append(validation["score"])
            
            if validation["approved"]:
                result["approved_count"] += 1
            else:
                result["rejected_count"] += 1
        
        # Calcular score geral
        if scores:
            result["overall_score"] = sum(scores) / len(scores)
        
        return result
    
    def observe(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Analisa resultado da validação."""
        observations = {
            "success": result["status"] == "success",
            "approval_rate": 0.0,
            "average_score": result["overall_score"],
            "common_issues": [],
            "recommendations": []
        }
        
        total = result["approved_count"] + result["rejected_count"]
        if total > 0:
            observations["approval_rate"] = result["approved_count"] / total
        
        # Coletar issues comuns
        issue_counts = {}
        for validation in result["validations"]:
            for issue in validation.get("issues", []):
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        observations["common_issues"] = sorted(
            issue_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Gerar recomendações
        if observations["approval_rate"] < 0.7:
            observations["recommendations"].append(
                "Revisar interpretações - taxa de aprovação baixa"
            )
        
        if observations["average_score"] < 60:
            observations["recommendations"].append(
                "Melhorar qualidade das interpretações"
            )
        
        return observations
    
    # ==================== TOOLS ====================
    
    def _tool_validate(
        self,
        element: Dict,
        element_type: str,
        rules: List[Dict]
    ) -> Dict[str, Any]:
        """Valida um elemento."""
        validation = {
            "element_id": element.get("id", "unknown"),
            "element_type": element_type,
            "approved": True,
            "score": 100.0,
            "issues": [],
            "details": {}
        }
        
        # Aplicar cada regra
        for rule in rules:
            rule_name = rule["rule"]
            params = rule["params"]
            
            if rule_name == "dimension_range":
                dims = element.get("dimensoes", {})
                for dim_name, dim_value in dims.items():
                    if isinstance(dim_value, (int, float)):
                        if dim_value < params["min"] or dim_value > params["max"]:
                            validation["issues"].append(
                                f"Dimensão {dim_name} fora do range"
                            )
                            validation["score"] -= 20
            
            elif rule_name == "name_pattern":
                name = element.get("nome", "")
                if not any(name.startswith(p) for p in params["patterns"]):
                    validation["issues"].append("Nome não segue padrão")
                    validation["score"] -= 10
        
        # Determinar aprovação
        validation["score"] = max(0, validation["score"])
        validation["approved"] = validation["score"] >= 60
        
        return validation
    
    def _tool_compare(self, element: Dict, patterns: List[Dict]) -> Dict[str, Any]:
        """Compara elemento com padrões conhecidos."""
        best_match = None
        best_similarity = 0.0
        
        # Mock - em produção usaria busca vetorial
        
        return {
            "has_match": best_match is not None,
            "similarity": best_similarity,
            "matched_pattern": best_match
        }
    
    def _tool_score(self, validations: List[Dict]) -> Dict[str, Any]:
        """Calcula score agregado."""
        if not validations:
            return {"score": 0, "grade": "F"}
        
        avg = sum(v["score"] for v in validations) / len(validations)
        
        if avg >= 90:
            grade = "A"
        elif avg >= 80:
            grade = "B"
        elif avg >= 70:
            grade = "C"
        elif avg >= 60:
            grade = "D"
        else:
            grade = "F"
        
        return {"score": avg, "grade": grade}
