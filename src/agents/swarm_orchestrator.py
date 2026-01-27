"""
Swarm Orchestrator - Coordenador de Agentes

Coordena a comunicação e colaboração entre os agentes do swarm.
"""

from typing import Dict, Any, List, Optional, Type
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .base_agent import (
    BaseAgent, AgentConfig, AgentRole, 
    AgentMessage, MessageType
)
from .perception_agent import PerceptionAgent
from .interpreter_agent import InterpreterAgent
from .validator_agent import ValidatorAgent
from .generator_agent import GeneratorAgent

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status de uma task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SwarmTask:
    """Representa uma task para o swarm."""
    task_id: str
    task_type: str  # "full_pipeline", "interpret_only", "generate_only"
    input_data: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "has_errors": len(self.errors) > 0
        }


class SwarmOrchestrator:
    """
    Coordenador central do swarm de agentes.
    
    Gerencia:
    - Ciclo de vida dos agentes
    - Roteamento de mensagens
    - Execução de pipelines
    - Agregação de resultados
    """
    
    def __init__(self):
        """Inicializa orchestrator."""
        self.agents: Dict[str, BaseAgent] = {}
        self.message_queue: List[AgentMessage] = []
        self.task_history: List[SwarmTask] = []
        self._task_counter = 0
        
        # Inicializar agentes padrão
        self._initialize_default_agents()
        
        logger.info("SwarmOrchestrator initialized")
    
    def _initialize_default_agents(self):
        """Inicializa agentes padrão."""
        self.register_agent(PerceptionAgent())
        self.register_agent(InterpreterAgent())
        self.register_agent(ValidatorAgent())
        self.register_agent(GeneratorAgent())
    
    def register_agent(self, agent: BaseAgent):
        """
        Registra um agente no swarm.
        
        Args:
            agent: Agente a registrar
        """
        self.agents[agent.config.name] = agent
        agent.state.is_active = True
        logger.info(f"Agent {agent.config.name} registered")
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Retorna agente por nome."""
        return self.agents.get(name)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """Lista todos os agentes."""
        return [agent.get_status() for agent in self.agents.values()]
    
    # ==================== MESSAGING ====================
    
    def send_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Envia mensagem para um agente.
        
        Args:
            message: Mensagem a enviar
            
        Returns:
            Resposta do agente (se houver)
        """
        receiver = self.agents.get(message.receiver)
        if not receiver:
            logger.error(f"Agent {message.receiver} not found")
            return None
        
        # Log mensagem
        self.message_queue.append(message)
        
        # Entregar ao agente
        response = receiver.receive_message(message)
        
        if response:
            self.message_queue.append(response)
        
        return response
    
    def broadcast(self, sender: str, content: Dict[str, Any]) -> List[AgentMessage]:
        """
        Envia mensagem para todos os agentes.
        
        Args:
            sender: Nome do remetente
            content: Conteúdo da mensagem
            
        Returns:
            Lista de respostas
        """
        responses = []
        
        for name, agent in self.agents.items():
            if name != sender:
                msg = AgentMessage(
                    msg_id=f"broadcast_{int(time.time()*1000)}",
                    msg_type=MessageType.QUERY,
                    sender=sender,
                    receiver=name,
                    content=content
                )
                response = self.send_message(msg)
                if response:
                    responses.append(response)
        
        return responses
    
    # ==================== TASK EXECUTION ====================
    
    def create_task(
        self,
        task_type: str,
        input_data: Dict[str, Any]
    ) -> SwarmTask:
        """
        Cria nova task para o swarm.
        
        Args:
            task_type: Tipo da task
            input_data: Dados de entrada
            
        Returns:
            Task criada
        """
        self._task_counter += 1
        task = SwarmTask(
            task_id=f"task_{self._task_counter:06d}",
            task_type=task_type,
            input_data=input_data
        )
        return task
    
    def execute_task(self, task: SwarmTask) -> SwarmTask:
        """
        Executa uma task.
        
        Args:
            task: Task a executar
            
        Returns:
            Task com resultados
        """
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()
        
        try:
            if task.task_type == "full_pipeline":
                task.results = self._execute_full_pipeline(task.input_data)
            elif task.task_type == "interpret_only":
                task.results = self._execute_interpret_only(task.input_data)
            elif task.task_type == "generate_only":
                task.results = self._execute_generate_only(task.input_data)
            elif task.task_type == "validate_only":
                task.results = self._execute_validate_only(task.input_data)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            task.status = TaskStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            task.status = TaskStatus.FAILED
            task.errors.append(str(e))
        
        task.completed_at = datetime.now()
        self.task_history.append(task)
        
        return task
    
    def _execute_full_pipeline(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa pipeline completo: Percepção → Interpretação → Validação → Geração.
        """
        results = {
            "stages": {},
            "final_output": None
        }
        
        # 1. PERCEPÇÃO
        logger.info("Stage 1: Perception")
        perception_agent = self.agents.get("perception_agent")
        if perception_agent:
            perception_msg = AgentMessage(
                msg_id=f"pipeline_perception_{int(time.time()*1000)}",
                msg_type=MessageType.TASK,
                sender="orchestrator",
                receiver="perception_agent",
                content={"task_id": "perception", **input_data}
            )
            perception_response = self.send_message(perception_msg)
            results["stages"]["perception"] = perception_response.content if perception_response else {}
        
        # 2. INTERPRETAÇÃO
        logger.info("Stage 2: Interpretation")
        interpreter_agent = self.agents.get("interpreter_agent")
        if interpreter_agent and results["stages"].get("perception"):
            interpret_msg = AgentMessage(
                msg_id=f"pipeline_interpret_{int(time.time()*1000)}",
                msg_type=MessageType.TASK,
                sender="orchestrator",
                receiver="interpreter_agent",
                content={
                    "task_id": "interpretation",
                    **results["stages"]["perception"].get("result", {})
                }
            )
            interpret_response = self.send_message(interpret_msg)
            results["stages"]["interpretation"] = interpret_response.content if interpret_response else {}
        
        # 3. VALIDAÇÃO
        logger.info("Stage 3: Validation")
        validator_agent = self.agents.get("validator_agent")
        if validator_agent and results["stages"].get("interpretation"):
            validate_msg = AgentMessage(
                msg_id=f"pipeline_validate_{int(time.time()*1000)}",
                msg_type=MessageType.TASK,
                sender="orchestrator",
                receiver="validator_agent",
                content={
                    "task_id": "validation",
                    "interpreted_elements": results["stages"]["interpretation"].get("result", {}).get("classified_elements", {})
                }
            )
            validate_response = self.send_message(validate_msg)
            results["stages"]["validation"] = validate_response.content if validate_response else {}
        
        # 4. GERAÇÃO (apenas se validação passou)
        logger.info("Stage 4: Generation")
        generator_agent = self.agents.get("generator_agent")
        validation_result = results["stages"].get("validation", {}).get("result", {})
        
        if generator_agent and validation_result.get("overall_score", 0) >= 60:
            generate_msg = AgentMessage(
                msg_id=f"pipeline_generate_{int(time.time()*1000)}",
                msg_type=MessageType.TASK,
                sender="orchestrator",
                receiver="generator_agent",
                content={
                    "task_id": "generation",
                    "elements": results["stages"]["interpretation"].get("result", {}).get("classified_elements", {}),
                    "format": input_data.get("output_format", "all")
                }
            )
            generate_response = self.send_message(generate_msg)
            results["stages"]["generation"] = generate_response.content if generate_response else {}
            results["final_output"] = results["stages"]["generation"].get("result", {})
        else:
            results["stages"]["generation"] = {"skipped": True, "reason": "Validation failed"}
        
        return results
    
    def _execute_interpret_only(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Executa apenas interpretação."""
        interpreter = self.agents.get("interpreter_agent")
        if not interpreter:
            return {"error": "Interpreter agent not available"}
        
        msg = AgentMessage(
            msg_id=f"interpret_{int(time.time()*1000)}",
            msg_type=MessageType.TASK,
            sender="orchestrator",
            receiver="interpreter_agent",
            content=input_data
        )
        response = self.send_message(msg)
        return response.content if response else {}
    
    def _execute_generate_only(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Executa apenas geração."""
        generator = self.agents.get("generator_agent")
        if not generator:
            return {"error": "Generator agent not available"}
        
        msg = AgentMessage(
            msg_id=f"generate_{int(time.time()*1000)}",
            msg_type=MessageType.TASK,
            sender="orchestrator",
            receiver="generator_agent",
            content=input_data
        )
        response = self.send_message(msg)
        return response.content if response else {}
    
    def _execute_validate_only(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Executa apenas validação."""
        validator = self.agents.get("validator_agent")
        if not validator:
            return {"error": "Validator agent not available"}
        
        msg = AgentMessage(
            msg_id=f"validate_{int(time.time()*1000)}",
            msg_type=MessageType.TASK,
            sender="orchestrator",
            receiver="validator_agent",
            content=input_data
        )
        response = self.send_message(msg)
        return response.content if response else {}
    
    # ==================== SWARM CONVERSATION ====================
    
    def swarm_discuss(
        self,
        topic: str,
        context: Dict[str, Any],
        max_rounds: int = 3
    ) -> Dict[str, Any]:
        """
        Inicia discussão entre agentes sobre um tópico.
        
        Args:
            topic: Tópico da discussão
            context: Contexto adicional
            max_rounds: Máximo de rodadas
            
        Returns:
            Resultado da discussão
        """
        discussion = {
            "topic": topic,
            "rounds": [],
            "consensus": None
        }
        
        for round_num in range(max_rounds):
            round_results = []
            
            # Cada agente contribui
            for name, agent in self.agents.items():
                query = f"""Tópico: {topic}
Contexto: {context}
Rodada: {round_num + 1}/{max_rounds}
Contribuições anteriores: {round_results}

Dê sua contribuição como {agent.config.role.value}."""
                
                response = agent._call_llm(query)
                round_results.append({
                    "agent": name,
                    "role": agent.config.role.value,
                    "contribution": response
                })
            
            discussion["rounds"].append(round_results)
        
        # Tentar chegar a consenso
        discussion["consensus"] = self._find_consensus(discussion["rounds"])
        
        return discussion
    
    def _find_consensus(self, rounds: List[List[Dict]]) -> Optional[str]:
        """Tenta encontrar consenso das discussões."""
        if not rounds:
            return None
        
        # Pegar última rodada
        last_round = rounds[-1]
        
        # Mock - em produção usaria LLM para sintetizar
        return "Consenso baseado nas contribuições dos agentes"
    
    # ==================== STATUS ====================
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do orchestrator."""
        return {
            "agents": self.list_agents(),
            "pending_messages": len(self.message_queue),
            "tasks_completed": len([t for t in self.task_history if t.status == TaskStatus.COMPLETED]),
            "tasks_failed": len([t for t in self.task_history if t.status == TaskStatus.FAILED]),
            "total_tasks": len(self.task_history)
        }
