
# Helper de ofuscação (adicionado automaticamente)
def _get_obf_str(key):
    """Retorna string ofuscada"""
    _obf_map = {
        _get_obf_str("script.google.com"): base64.b64decode("=02bj5SZsd2bvdmL0BXayN2c"[::-1].encode()).decode(),
        _get_obf_str("macros/s/"): base64.b64decode("vM3Lz9mcjFWb"[::-1].encode()).decode(),
        _get_obf_str("AKfycbz"): base64.b64decode("==geiNWemtUQ"[::-1].encode()).decode(),
        _get_obf_str("credit"): base64.b64decode("0lGZlJ3Y"[::-1].encode()).decode(),
        _get_obf_str("saldo"): base64.b64decode("=8GZsF2c"[::-1].encode()).decode(),
        _get_obf_str("consumo"): base64.b64decode("==wbtV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("api_key"): base64.b64decode("==Qelt2XpBXY"[::-1].encode()).decode(),
        _get_obf_str("user_id"): base64.b64decode("==AZp9lclNXd"[::-1].encode()).decode(),
        _get_obf_str("calcular_creditos"): base64.b64decode("=M3b0lGZlJ3YfJXYsV3YsF2Y"[::-1].encode()).decode(),
        _get_obf_str("confirmar_consumo"): base64.b64decode("=8Wb1NnbvN2XyFWbylmZu92Y"[::-1].encode()).decode(),
        _get_obf_str("consultar_saldo"): base64.b64decode("vRGbhN3XyFGdsV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("debitar_creditos"): base64.b64decode("==wcvRXakVmcj9lchRXaiVGZ"[::-1].encode()).decode(),
        _get_obf_str("CreditManager"): base64.b64decode("==gcldWYuFWT0lGZlJ3Q"[::-1].encode()).decode(),
        _get_obf_str("obter_hwid"): base64.b64decode("==AZpdHafJXZ0J2b"[::-1].encode()).decode(),
        _get_obf_str("generate_signature"): base64.b64decode("lJXd0Fmbnl2cfVGdhJXZuV2Z"[::-1].encode()).decode(),
        _get_obf_str("encrypt_string"): base64.b64decode("=cmbpJHdz9Fdwlncj5WZ"[::-1].encode()).decode(),
        _get_obf_str("decrypt_string"): base64.b64decode("=cmbpJHdz9FdwlncjVGZ"[::-1].encode()).decode(),
        _get_obf_str("integrity_check"): base64.b64decode("rNWZoN2X5RXaydWZ05Wa"[::-1].encode()).decode(),
        _get_obf_str("security_utils"): base64.b64decode("=MHbpRXdflHdpJXdjV2c"[::-1].encode()).decode(),
        _get_obf_str("https://"): base64.b64decode("=8yL6MHc0RHa"[::-1].encode()).decode(),
        _get_obf_str("google.com"): base64.b64decode("==QbvNmLlx2Zv92Z"[::-1].encode()).decode(),
        _get_obf_str("apps.script"): base64.b64decode("=QHcpJ3Yz5ycwBXY"[::-1].encode()).decode(),
    }
    return _obf_map.get(key, key)

#!/usr/bin/env python3
"""
========================================================
🔍 Sistema de Logs de Depuração - PilarAnalyzer
========================================================
📆 Data: 23/07/2025
✏️ Autor: Kiro AIinstco

📋 Descrição:
Sistema centralizado de logs de depuração para todos os componentes
do PilarAnalyzer. Cada componente terá seu próprio arquivo de log
na pasta logs/depuracao/.
"""

import os
import sys
import logging
import datetime
from pathlib import Path
from typing import Optional

# Importar inicializador frozen ANTES de qualquer outra coisa
# Mas evitar import circular se já estamos dentro de utils
_importing_frozen_init = False
if not _importing_frozen_init:
    try:
        _importing_frozen_init = True
        # Tentar importar de múltiplas formas
        try:
            from utils.__frozen_init__ import ensure_frozen_paths
            ensure_frozen_paths()
        except (ImportError, AttributeError):
            try:
                import importlib.util
                current_file = os.path.abspath(__file__)
                utils_dir = os.path.dirname(current_file)
                frozen_init_path = os.path.join(utils_dir, '__frozen_init__.py')
                if os.path.exists(frozen_init_path):
                    spec = importlib.util.spec_from_file_location("__frozen_init__", frozen_init_path)
                    if spec and spec.loader:
                        frozen_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(frozen_module)
                        if hasattr(frozen_module, 'ensure_frozen_paths'):
                            frozen_module.ensure_frozen_paths()
            except Exception:
                pass  # Se não conseguir importar, continua normalmente
    except Exception:
        pass  # Se não conseguir importar, continua normalmente
    finally:
        _importing_frozen_init = False


def _is_frozen() -> bool:
    return getattr(sys, 'frozen', False) is True


def _user_logs_dir() -> Path:
    if _is_frozen():
        base = os.getenv('LOCALAPPDATA') or os.path.expanduser('~')
        return Path(os.path.join(base, 'PilarAnalyzer', 'logs'))
    return Path("logs/depuracao")


class DebugLogger:
    """Sistema centralizado de logs de depuração"""
    
    def __init__(self, component_name: str, log_dir: str = "logs/depuracao"):
        """
        Inicializa o logger de depuração para um componente específico
        
        Args:
            component_name: Nome do componente (ex: 'pilar_analyzer', 'robo_abcd')
            log_dir: Diretório onde os logs serão salvos
        """
        self.component_name = component_name
        # Em ambiente frozen, redirecionar para %LOCALAPPDATA%/PilarAnalyzer/logs
        if _is_frozen():
            self.log_dir = str(_user_logs_dir())
        else:
            self.log_dir = log_dir
        self.logger = None
        self._setup_logger()
    
    def _setup_logger(self):
        """Configura o logger para o componente"""
        # Criar diretório de logs se não existir
        log_path = Path(self.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Nome do arquivo de log com timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{self.component_name}_{timestamp}.log"
        log_filepath = log_path / log_filename
        
        # Configurar logger
        self.logger = logging.getLogger(f"debug_{self.component_name}")
        self.logger.setLevel(logging.DEBUG)
        
        # Evitar duplicação de handlers
        if not self.logger.handlers:
            # Handler para arquivo
            file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # Handler para console (DEBUG para ver tudo no terminal)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            # Configurar encoding UTF-8 para o console
            if hasattr(console_handler.stream, 'reconfigure'):
                console_handler.stream.reconfigure(encoding='utf-8')
            
            # Formato das mensagens
            formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
        
        # Log inicial
        self.logger.info(f"Iniciando logs de depuração para {self.component_name}")
        self.logger.info(f"Arquivo de log: {log_filepath}")
    
    def debug(self, message: str):
        """Log de nível DEBUG"""
        self.logger.debug(f"🔍 {message}")
    
    def info(self, message: str):
        """Log de nível INFO"""
        self.logger.info(f"ℹ️ {message}")
    
    def warning(self, message: str):
        """Log de nível WARNING"""
        self.logger.warning(f"⚠️ {message}")
    
    def error(self, message: str):
        """Log de nível ERROR"""
        self.logger.error(f"❌ {message}")
    
    def critical(self, message: str):
        """Log de nível CRITICAL"""
        self.logger.critical(f"🚨 {message}")
    
    def section(self, title: str):
        """Cria uma seção no log para organizar melhor"""
        separator = "=" * 60
        self.logger.info(f"\n{separator}")
        self.logger.info(f"📋 {title}")
        self.logger.info(f"{separator}")
    
    def subsection(self, title: str):
        """Cria uma subseção no log"""
        separator = "-" * 40
        self.logger.info(f"\n{separator}")
        self.logger.info(f"📌 {title}")
        self.logger.info(f"{separator}")
    
    def function_entry(self, function_name: str, **kwargs):
        """Log de entrada em função com parâmetros"""
        params = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        self.logger.debug(f"🔽 Entrando em {function_name}({params})")
    
    def function_exit(self, function_name: str, result=None):
        """Log de saída de função com resultado"""
        if result is not None:
            self.logger.debug(f"🔼 Saindo de {function_name} -> {result}")
        else:
            self.logger.debug(f"🔼 Saindo de {function_name}")
    
    def data_processing(self, operation: str, data_info: str):
        """Log específico para processamento de dados"""
        self.logger.info(f"🔄 {operation}: {data_info}")
    
    def file_operation(self, operation: str, file_path: str, status: str = "OK"):
        """Log específico para operações de arquivo"""
        self.logger.info(f"📁 {operation}: {file_path} -> {status}")
    
    def api_call(self, endpoint: str, method: str = "GET", status: str = "OK"):
        """Log específico para chamadas de API"""
        self.logger.info(f"🌐 {method} {endpoint} -> {status}")
    
    def performance(self, operation: str, duration: float):
        """Log específico para métricas de performance"""
        self.logger.info(f"⏱️ {operation}: {duration:.3f}s")


# Função de conveniência para criar loggers
def get_debug_logger(component_name: str) -> DebugLogger:
    """
    Função de conveniência para criar um logger de depuração
    
    Args:
        component_name: Nome do componente
        
    Returns:
        DebugLogger: Instância do logger configurado
    """
    return DebugLogger(component_name)


# Loggers pré-configurados para componentes principais
def get_pilar_analyzer_logger() -> DebugLogger:
    """Logger para o PilarAnalyzer principal"""
    return get_debug_logger("pilar_analyzer")


def get_interface_logger() -> DebugLogger:
    """Logger para a Interface Principal"""
    return get_debug_logger("interface_principal")


def get_robo_abcd_logger() -> DebugLogger:
    """Logger para o Robô ABCD"""
    return get_debug_logger("robo_abcd")


def get_robo_cima_logger() -> DebugLogger:
    """Logger para o Robô CIMA"""
    return get_debug_logger("robo_cima")


def get_robo_grades_logger() -> DebugLogger:
    """Logger para o Robô GRADES"""
    return get_debug_logger("robo_grades")


def get_combinador_logger() -> DebugLogger:
    """Logger para o Combinador"""
    return get_debug_logger("combinador")


def get_ponte_excel_cima_logger() -> DebugLogger:
    """Logger para a Ponte Excel CIMA"""
    return get_debug_logger("ponte_excel_cima")


def get_ponte_abcd_logger() -> DebugLogger:
    """Logger para a Ponte ABCD"""
    return get_debug_logger("ponte_abcd")


def get_ponte_grades_logger() -> DebugLogger:
    """Logger para a Ponte GRADES"""
    return get_debug_logger("ponte_grades")


def get_credit_system_logger() -> DebugLogger:
    """Logger para o Sistema de Créditos"""
    return get_debug_logger("credit_system")


def get_ordenador_logger() -> DebugLogger:
    """Logger para os Ordenadores"""
    return get_debug_logger("ordenador")


# Context manager para logging automático de funções
class FunctionLogger:
    """Context manager para logging automático de entrada e saída de funções"""
    
    def __init__(self, logger: DebugLogger, function_name: str, **kwargs):
        self.logger = logger
        self.function_name = function_name
        self.kwargs = kwargs
    
    def __enter__(self):
        self.logger.function_entry(self.function_name, **self.kwargs)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.logger.error(f"Erro em {self.function_name}: {exc_val}")
        else:
            self.logger.function_exit(self.function_name)


# Decorator para logging automático de funções
def log_function(logger: Optional[DebugLogger] = None):
    """
    Decorator para logging automático de funções
    
    Args:
        logger: Logger a ser usado (se None, será criado um novo)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Usar logger fornecido ou criar um baseado no nome da função
            if logger is None:
                func_logger = get_debug_logger(f"function_{func.__name__}")
            else:
                func_logger = logger
            
            func_logger.function_entry(func.__name__, *args, **kwargs)
            
            try:
                result = func(*args, **kwargs)
                func_logger.function_exit(func.__name__, result)
                return result
            except Exception as e:
                func_logger.error(f"Erro em {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator
