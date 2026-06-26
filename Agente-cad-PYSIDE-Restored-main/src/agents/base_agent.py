"""
Base Agent - Classe Base para Todos os Agentes

Define interface comum e funcionalidades compartilhadas.
"""

from __future__ import annotations
import logging
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Papéis possíveis de agentes."""
    PERCEPTION = "perception"
    INTERPRETER = "interpreter"
    VALIDATOR = "validator"
    GENERATOR = "generator"
    ORCHESTRATOR = "orchestrator"


class MessageType(str, Enum):
    """Tipos de mensagens entre agentes."""
    TASK = "task"
    RESULT = "result"
    ERROR = "error"
    QUERY = "query"
    FEEDBACK = "feedback"


@dataclass
class AgentConfig:
    """Configuração de um agente."""
    name: str
    role: AgentRole
    model: str = "llama3.2:3b"  # Modelo padrão
    temperature: float = 0.3
    max_tokens: int = 2048
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)
    ollama_base_url: str = "http://localhost:11434"


@dataclass
class AgentMessage:
    """Mensagem trocada entre agentes."""
    msg_id: str
    msg_type: MessageType
    sender: str
    receiver: str
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentMessage:
        return cls(
            msg_id=data["msg_id"],
            msg_type=MessageType(data["msg_type"]),
            sender=data["sender"],
            receiver=data["receiver"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class AgentState:
    """Estado interno de um agente."""
    is_active: bool = False
    current_task: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Classe base para todos os agentes do swarm.
    
    Define interface comum: think, act, observe.
    """
    
    def __init__(self, config: AgentConfig):
        """
        Inicializa agente.
        
        Args:
            config: Configuração do agente
        """
        self.config = config
        self.state = AgentState()
        self._message_handlers: Dict[MessageType, Callable] = {}
        self._tools: Dict[str, Callable] = {}
        
        # Registrar handlers padrão
        self._register_default_handlers()
        
        # Log
        logger.info(f"Agent {config.name} ({config.role.value}) initialized")
    
    def _register_default_handlers(self):
        """Registra handlers padrão de mensagens."""
        self._message_handlers[MessageType.TASK] = self._handle_task
        self._message_handlers[MessageType.QUERY] = self._handle_query
        self._message_handlers[MessageType.FEEDBACK] = self._handle_feedback
    
    # ==================== INTERFACE PRINCIPAL ====================
    
    @abstractmethod
    def think(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa input e decide ação.
        
        Args:
            input_data: Dados de entrada
            
        Returns:
            Plano de ação
        """
        pass
    
    @abstractmethod
    def act(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa ação baseada no plano.
        
        Args:
            plan: Plano de ação
            
        Returns:
            Resultado da ação
        """
        pass
    
    @abstractmethod
    def observe(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Observa resultado e extrai aprendizado.
        
        Args:
            result: Resultado da ação
            
        Returns:
            Observações e aprendizados
        """
        pass
    
    # ==================== LLM INTEGRATION ====================
    
    def _call_llm(self, prompt: str, system: Optional[str] = None) -> str:
        """
        Chama modelo LLM via Ollama.
        
        Args:
            prompt: Prompt para o modelo
            system: System prompt (opcional)
            
        Returns:
            Resposta do modelo
        """
        try:
            url = f"{self.config.ollama_base_url}/api/generate"
            
            payload = {
                "model": self.config.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens
                }
            }
            
            if system or self.config.system_prompt:
                payload["system"] = system or self.config.system_prompt
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "")
            
        except requests.exceptions.ConnectionError:
            logger.warning("Ollama not available, using mock response")
            return self._mock_llm_response(prompt)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return self._mock_llm_response(prompt)
    
    def _mock_llm_response(self, prompt: str) -> str:
        """Resposta mock quando Ollama não disponível."""
        return json.dumps({
            "status": "mock",
            "message": "Ollama não disponível - resposta simulada",
            "prompt_length": len(prompt)
        })
    
    # ==================== MESSAGING ====================
    
    def receive_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Recebe e processa mensagem.
        
        Args:
            message: Mensagem recebida
            
        Returns:
            Resposta (opcional)
        """
        logger.debug(f"{self.config.name} received {message.msg_type.value} from {message.sender}")
        
        handler = self._message_handlers.get(message.msg_type)
        if handler:
            return handler(message)
        else:
            logger.warning(f"No handler for message type: {message.msg_type}")
            return None
    
    def send_message(
        self,
        receiver: str,
        msg_type: MessageType,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentMessage:
        """
        Cria mensagem para envio.
        
        Args:
            receiver: Destinatário
            msg_type: Tipo da mensagem
            content: Conteúdo
            metadata: Metadados (opcional)
            
        Returns:
            Mensagem criada
        """
        msg = AgentMessage(
            msg_id=f"{self.config.name}_{int(time.time()*1000)}",
            msg_type=msg_type,
            sender=self.config.name,
            receiver=receiver,
            content=content,
            metadata=metadata or {}
        )
        
        # Log na história
        self.state.history.append({
            "action": "send_message",
            "message": msg.to_dict(),
            "timestamp": datetime.now().isoformat()
        })
        
        return msg
    
    def _handle_task(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handler para mensagens de task."""
        self.state.current_task = message.content
        
        # Executar ciclo think-act-observe
        plan = self.think(message.content)
        result = self.act(plan)
        observations = self.observe(result)
        
        # Criar resposta
        return self.send_message(
            receiver=message.sender,
            msg_type=MessageType.RESULT,
            content={
                "task_id": message.content.get("task_id"),
                "result": result,
                "observations": observations
            }
        )
    
    def _handle_query(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handler para queries."""
        query = message.content.get("query", "")
        response = self._call_llm(query)
        
        return self.send_message(
            receiver=message.sender,
            msg_type=MessageType.RESULT,
            content={"response": response}
        )
    
    def _handle_feedback(self, message: AgentMessage) -> None:
        """Handler para feedback."""
        feedback = message.content
        logger.info(f"{self.config.name} received feedback: {feedback}")
        
        # Armazenar feedback para aprendizado
        self.state.history.append({
            "action": "feedback_received",
            "feedback": feedback,
            "timestamp": datetime.now().isoformat()
        })
    
    # ==================== TOOLS ====================
    
    def register_tool(self, name: str, func: Callable):
        """
        Registra ferramenta disponível para o agente.
        
        Args:
            name: Nome da ferramenta
            func: Função da ferramenta
        """
        self._tools[name] = func
        logger.debug(f"Tool '{name}' registered for {self.config.name}")
    
    def use_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Usa ferramenta registrada.
        
        Args:
            tool_name: Nome da ferramenta
            **kwargs: Argumentos
            
        Returns:
            Resultado da ferramenta
        """
        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        result = self._tools[tool_name](**kwargs)
        
        # Log uso da ferramenta
        self.state.history.append({
            "action": "tool_use",
            "tool": tool_name,
            "args": kwargs,
            "timestamp": datetime.now().isoformat()
        })
        
        return result
    
    # ==================== UTILITIES ====================
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do agente."""
        return {
            "name": self.config.name,
            "role": self.config.role.value,
            "is_active": self.state.is_active,
            "current_task": self.state.current_task,
            "history_length": len(self.state.history),
            "tools": list(self._tools.keys()),
            "metrics": self.state.metrics
        }
    
    def reset(self):
        """Reseta estado do agente."""
        self.state = AgentState()
        logger.info(f"Agent {self.config.name} reset")
