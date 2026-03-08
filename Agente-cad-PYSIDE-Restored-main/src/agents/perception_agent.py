"""
Perception Agent - Agente de Percepção

Responsável por ler DXFs e extrair dados geométricos.
"""

from typing import Dict, Any, List, Optional
import json
from .base_agent import BaseAgent, AgentConfig, AgentRole


class PerceptionAgent(BaseAgent):
    """
    Agente especializado em percepção visual/geométrica.
    
    Responsabilidades:
    - Ler arquivos DXF
    - Extrair entidades geométricas
    - Identificar elementos estruturais (pilares, vigas, lajes)
    - Criar representação vetorial inicial
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="perception_agent",
                role=AgentRole.PERCEPTION,
                system_prompt=self._get_system_prompt(),
                tools=["read_dxf", "extract_geometry", "identify_elements"]
            )
        super().__init__(config)
        
        # Registrar tools
        self._register_tools()
    
    def _get_system_prompt(self) -> str:
        return """Você é um agente de percepção especializado em análise de arquivos DXF estruturais.
        
Suas responsabilidades:
1. Ler e interpretar arquivos DXF de projetos estruturais
2. Extrair entidades geométricas (linhas, polilinhas, textos, blocos)
3. Identificar elementos estruturais: pilares, vigas, lajes
4. Associar textos aos elementos correspondentes

Você deve retornar suas análises em formato JSON estruturado."""
    
    def _register_tools(self):
        """Registra ferramentas do agente."""
        self.register_tool("read_dxf", self._tool_read_dxf)
        self.register_tool("extract_geometry", self._tool_extract_geometry)
        self.register_tool("identify_elements", self._tool_identify_elements)
    
    def think(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa input e planeja extração.
        
        Args:
            input_data: Deve conter 'dxf_path' ou 'dxf_content'
            
        Returns:
            Plano de extração
        """
        plan = {
            "steps": [],
            "input_type": None,
            "expected_elements": []
        }
        
        # Determinar tipo de input
        if "dxf_path" in input_data:
            plan["input_type"] = "file"
            plan["steps"].append({
                "action": "read_dxf",
                "params": {"path": input_data["dxf_path"]}
            })
        elif "dxf_content" in input_data:
            plan["input_type"] = "content"
            plan["steps"].append({
                "action": "parse_content",
                "params": {"content": input_data["dxf_content"]}
            })
        else:
            plan["error"] = "No valid input found"
            return plan
        
        # Adicionar passos de extração
        plan["steps"].extend([
            {"action": "extract_geometry", "params": {}},
            {"action": "identify_elements", "params": {}}
        ])
        
        # Usar LLM para enriquecer plano
        llm_prompt = f"""Analise o seguinte input e sugira elementos esperados:
Input type: {plan['input_type']}
Additional context: {input_data.get('context', 'None')}

Responda em JSON com 'expected_elements' (lista de tipos esperados)."""
        
        llm_response = self._call_llm(llm_prompt)
        try:
            llm_data = json.loads(llm_response)
            plan["expected_elements"] = llm_data.get("expected_elements", [])
        except:
            plan["expected_elements"] = ["pilares", "vigas", "lajes"]
        
        return plan
    
    def act(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa plano de extração.
        
        Args:
            plan: Plano gerado por think()
            
        Returns:
            Dados extraídos
        """
        result = {
            "status": "success",
            "entities": [],
            "elements": {
                "pilares": [],
                "vigas": [],
                "lajes": []
            },
            "texts": [],
            "metadata": {}
        }
        
        if "error" in plan:
            result["status"] = "error"
            result["error"] = plan["error"]
            return result
        
        # Executar cada passo
        current_data = None
        for step in plan["steps"]:
            action = step["action"]
            params = step["params"]
            
            if action == "read_dxf":
                current_data = self.use_tool("read_dxf", **params)
            elif action == "extract_geometry":
                if current_data:
                    geometry = self.use_tool("extract_geometry", data=current_data)
                    result["entities"] = geometry.get("entities", [])
                    result["texts"] = geometry.get("texts", [])
            elif action == "identify_elements":
                if result["entities"]:
                    elements = self.use_tool("identify_elements", entities=result["entities"])
                    result["elements"] = elements
        
        return result
    
    def observe(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa resultado e extrai aprendizados.
        
        Args:
            result: Resultado do act()
            
        Returns:
            Observações
        """
        observations = {
            "success": result["status"] == "success",
            "element_counts": {},
            "issues": [],
            "suggestions": []
        }
        
        if result["status"] == "success":
            # Contar elementos
            for elem_type, elems in result["elements"].items():
                observations["element_counts"][elem_type] = len(elems)
            
            # Verificar problemas
            total = sum(observations["element_counts"].values())
            if total == 0:
                observations["issues"].append("Nenhum elemento identificado")
                observations["suggestions"].append("Verificar se DXF está correto")
            
            # Verificar textos não associados
            if result["texts"]:
                unassociated = len([t for t in result["texts"] if not t.get("associated")])
                if unassociated > 0:
                    observations["issues"].append(f"{unassociated} textos não associados")
        
        return observations
    
    # ==================== TOOLS ====================
    
    def _tool_read_dxf(self, path: str) -> Dict[str, Any]:
        """Ferramenta: Ler arquivo DXF."""
        # Mock - em produção usaria ezdxf
        return {
            "status": "read",
            "path": path,
            "entities_count": 0,
            "layers": [],
            "mock": True
        }
    
    def _tool_extract_geometry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ferramenta: Extrair geometria."""
        # Mock - em produção processaria entidades
        return {
            "entities": [],
            "texts": [],
            "bounds": {"min": [0, 0], "max": [1000, 1000]}
        }
    
    def _tool_identify_elements(self, entities: List[Dict]) -> Dict[str, List]:
        """Ferramenta: Identificar elementos estruturais."""
        # Mock - em produção usaria classificador
        return {
            "pilares": [],
            "vigas": [],
            "lajes": []
        }
