"""
Generator Agent - Agente de Geração

Responsável por gerar outputs: SCR, DXF, JSON, vetores.
"""

from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent, AgentConfig, AgentRole


class GeneratorAgent(BaseAgent):
    """
    Agente especializado em geração de outputs.
    
    Responsabilidades:
    - Gerar scripts SCR para AutoCAD
    - Gerar arquivos DXF
    - Gerar JSONs de configuração
    - Popular bancos vetoriais
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="generator_agent",
                role=AgentRole.GENERATOR,
                system_prompt=self._get_system_prompt(),
                tools=["generate_scr", "generate_dxf", "generate_json", "populate_vector"]
            )
        super().__init__(config)
        self._register_tools()
    
    def _get_system_prompt(self) -> str:
        return """Você é um agente de geração especializado em criar outputs estruturais.

Suas responsabilidades:
1. Gerar scripts SCR para AutoCAD com comandos de desenho
2. Gerar arquivos DXF com elementos estruturais
3. Gerar JSONs de configuração para os robôs
4. Popular bancos vetoriais com embeddings

Formatos de saída:
- SCR: Comandos AutoCAD (LINE, PLINE, TEXT, HATCH)
- DXF: Formato 2010 com layers organizados
- JSON: Schema padronizado do AgenteCAD
- Vetores: Embeddings + metadados

Responda em JSON com 'output_type', 'content', e 'metadata'."""
    
    def _register_tools(self):
        self.register_tool("generate_scr", self._tool_generate_scr)
        self.register_tool("generate_dxf", self._tool_generate_dxf)
        self.register_tool("generate_json", self._tool_generate_json)
        self.register_tool("populate_vector", self._tool_populate_vector)
    
    def think(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Planeja geração."""
        plan = {
            "outputs_to_generate": [],
            "elements": input_data.get("elements", {}),
            "output_format": input_data.get("format", "all")
        }
        
        output_format = plan["output_format"]
        
        # Determinar outputs necessários
        if output_format in ["all", "scr"]:
            plan["outputs_to_generate"].append({
                "type": "scr",
                "action": "generate_scr"
            })
        
        if output_format in ["all", "dxf"]:
            plan["outputs_to_generate"].append({
                "type": "dxf",
                "action": "generate_dxf"
            })
        
        if output_format in ["all", "json"]:
            plan["outputs_to_generate"].append({
                "type": "json",
                "action": "generate_json"
            })
        
        if output_format in ["all", "vector"]:
            plan["outputs_to_generate"].append({
                "type": "vector",
                "action": "populate_vector"
            })
        
        return plan
    
    def act(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Executa geração."""
        result = {
            "status": "success",
            "outputs": {},
            "files_created": [],
            "vectors_added": 0
        }
        
        elements = plan["elements"]
        
        for output_config in plan["outputs_to_generate"]:
            output_type = output_config["type"]
            action = output_config["action"]
            
            if action == "generate_scr":
                scr_result = self.use_tool("generate_scr", elements=elements)
                result["outputs"]["scr"] = scr_result
                result["files_created"].extend(scr_result.get("files", []))
            
            elif action == "generate_dxf":
                dxf_result = self.use_tool("generate_dxf", elements=elements)
                result["outputs"]["dxf"] = dxf_result
                result["files_created"].extend(dxf_result.get("files", []))
            
            elif action == "generate_json":
                json_result = self.use_tool("generate_json", elements=elements)
                result["outputs"]["json"] = json_result
                result["files_created"].extend(json_result.get("files", []))
            
            elif action == "populate_vector":
                vector_result = self.use_tool("populate_vector", elements=elements)
                result["outputs"]["vector"] = vector_result
                result["vectors_added"] = vector_result.get("count", 0)
        
        return result
    
    def observe(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Analisa resultado da geração."""
        observations = {
            "success": result["status"] == "success",
            "outputs_generated": list(result["outputs"].keys()),
            "total_files": len(result["files_created"]),
            "vectors_added": result["vectors_added"],
            "issues": [],
            "metrics": {}
        }
        
        # Verificar cada output
        for output_type, output_data in result["outputs"].items():
            if output_data.get("status") != "success":
                observations["issues"].append(f"Falha em {output_type}")
        
        # Métricas
        observations["metrics"]["files_per_type"] = {}
        for output_type in result["outputs"]:
            files = result["outputs"][output_type].get("files", [])
            observations["metrics"]["files_per_type"][output_type] = len(files)
        
        return observations
    
    # ==================== TOOLS ====================
    
    def _tool_generate_scr(self, elements: Dict) -> Dict[str, Any]:
        """Gera scripts SCR."""
        result = {
            "status": "success",
            "files": [],
            "content": {}
        }
        
        # Gerar SCR para pilares
        for pilar in elements.get("pilares", []):
            scr_content = self._generate_pilar_scr(pilar)
            filename = f"pilar_{pilar.get('nome', 'unknown')}.scr"
            result["files"].append(filename)
            result["content"][filename] = scr_content
        
        # Gerar SCR para vigas
        for viga in elements.get("vigas", []):
            scr_content = self._generate_viga_scr(viga)
            filename = f"viga_{viga.get('nome', 'unknown')}.scr"
            result["files"].append(filename)
            result["content"][filename] = scr_content
        
        # Gerar SCR para lajes
        for laje in elements.get("lajes", []):
            scr_content = self._generate_laje_scr(laje)
            filename = f"laje_{laje.get('nome', 'unknown')}.scr"
            result["files"].append(filename)
            result["content"][filename] = scr_content
        
        return result
    
    def _generate_pilar_scr(self, pilar: Dict) -> str:
        """Gera SCR de um pilar."""
        lines = [
            f"; SCR para pilar {pilar.get('nome', '')}",
            "-LAYER S GRADE",
            "",
        ]
        
        # Adicionar comandos de desenho
        dims = pilar.get("dimensoes", {})
        largura = dims.get("largura", 40)
        altura = dims.get("altura", 150)
        
        lines.append(f"RECTANG 0,0 {largura},{altura}")
        lines.append("")
        
        return "\n".join(lines)
    
    def _generate_viga_scr(self, viga: Dict) -> str:
        """Gera SCR de uma viga."""
        lines = [
            f"; SCR para viga {viga.get('nome', '')}",
            "-LAYER S VIGA",
            "",
        ]
        return "\n".join(lines)
    
    def _generate_laje_scr(self, laje: Dict) -> str:
        """Gera SCR de uma laje."""
        lines = [
            f"; SCR para laje {laje.get('nome', '')}",
            "-LAYER S LAJE",
            "",
        ]
        return "\n".join(lines)
    
    def _tool_generate_dxf(self, elements: Dict) -> Dict[str, Any]:
        """Gera arquivos DXF."""
        # Mock - em produção usaria ezdxf
        return {
            "status": "success",
            "files": [],
            "mock": True
        }
    
    def _tool_generate_json(self, elements: Dict) -> Dict[str, Any]:
        """Gera JSONs de configuração."""
        result = {
            "status": "success",
            "files": [],
            "content": {}
        }
        
        for elem_type, elems in elements.items():
            for elem in elems:
                filename = f"{elem_type}_{elem.get('nome', 'unknown')}.json"
                result["files"].append(filename)
                result["content"][filename] = elem
        
        return result
    
    def _tool_populate_vector(self, elements: Dict) -> Dict[str, Any]:
        """Popula banco vetorial."""
        count = 0
        
        # Mock - em produção adicionaria ao ChromaDB
        for elem_type, elems in elements.items():
            count += len(elems)
        
        return {
            "status": "success",
            "count": count,
            "mock": True
        }
