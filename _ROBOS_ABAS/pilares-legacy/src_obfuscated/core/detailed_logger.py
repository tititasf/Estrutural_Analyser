
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
📝 DetailedLogger - Sistema de Logging Detalhado
========================================================

📋 Funcionalidade: Sistema de logging específico para debug de geração de scripts
📆 Data: 19/07/2025
🔧 Versão: 1.0

🎯 Características:
- Logging estruturado com diferentes níveis
- Formatação específica para debug de scripts
- Gerenciamento de arquivos de log
- Rotação automática de logs

========================================================
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import traceback
import sys
import os


class DetailedLogger:
    """Sistema de logging detalhado para debug de geração de scripts"""
    
    def __init__(
        self, 
        name: str = "ScriptGenerationDebug",
        log_dir: Optional[Path] = None,
        log_level: int = logging.INFO,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        console_output: bool = True
    ):
        """
        Inicializar sistema de logging detalhado
        
        Args:
            name: Nome do logger
            log_dir: Diretório para arquivos de log (None = diretório atual)
            log_level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            max_file_size: Tamanho máximo do arquivo de log em bytes
            backup_count: Número de arquivos de backup a manter
            console_output: Se deve mostrar logs no console
        """
        self.name = name
        self.log_dir = Path(log_dir) if log_dir else Path.cwd()
        self.log_level = log_level
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.console_output = console_output
        
        # Criar diretório de logs se não existir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurar logger principal
        self.logger = self._setup_logger()
        
        # Contadores para estatísticas
        self.stats = {
            'debug': 0,
            'info': 0,
            'warning': 0,
            'error': 0,
            'critical': 0,
            'start_time': datetime.now()
        }
        
        self.logger.info(f"DetailedLogger inicializado: {name}")
        self.logger.info(f"Diretório de logs: {self.log_dir}")
        self.logger.info(f"Nível de logging: {logging.getLevelName(log_level)}")
    
    def _setup_logger(self) -> logging.Logger:
        """Configurar logger com handlers apropriados"""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.log_level)
        
        # Remover handlers existentes para evitar duplicação
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Formatter detalhado
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Formatter simples para console
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Handler para arquivo principal
        main_log_file = self.log_dir / f"{self.name.lower()}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        # Handler para arquivo de erros
        error_log_file = self.log_dir / f"{self.name.lower()}_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)
        
        # Handler para console (se habilitado)
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        return logger
    
    def debug(self, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Log de debug com dados extras opcionais"""
        self.stats['debug'] += 1
        if extra_data:
            message = f"{message} | Extra: {json.dumps(extra_data, default=str)}"
        self.logger.debug(message)
    
    def info(self, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Log de informação com dados extras opcionais"""
        self.stats['info'] += 1
        if extra_data:
            message = f"{message} | Extra: {json.dumps(extra_data, default=str)}"
        self.logger.info(message)
    
    def warning(self, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Log de aviso com dados extras opcionais"""
        self.stats['warning'] += 1
        if extra_data:
            message = f"{message} | Extra: {json.dumps(extra_data, default=str)}"
        self.logger.warning(message)
    
    def error(self, message: str, exception: Optional[Exception] = None, extra_data: Optional[Dict[str, Any]] = None):
        """Log de erro com exceção e dados extras opcionais"""
        self.stats['error'] += 1
        
        if exception:
            message = f"{message} | Exception: {str(exception)}"
            if extra_data:
                message = f"{message} | Extra: {json.dumps(extra_data, default=str)}"
            self.logger.error(message)
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        else:
            if extra_data:
                message = f"{message} | Extra: {json.dumps(extra_data, default=str)}"
            self.logger.error(message)
    
    def critical(self, message: str, exception: Optional[Exception] = None, extra_data: Optional[Dict[str, Any]] = None):
        """Log crítico com exceção e dados extras opcionais"""
        self.stats['critical'] += 1
        
        if exception:
            message = f"{message} | Exception: {str(exception)}"
            if extra_data:
                message = f"{message} | Extra: {json.dumps(extra_data, default=str)}"
            self.logger.critical(message)
            self.logger.critical(f"Traceback: {traceback.format_exc()}")
        else:
            if extra_data:
                message = f"{message} | Extra: {json.dumps(extra_data, default=str)}"
            self.logger.critical(message)
    
    def log_step(self, step_name: str, status: str = "START", details: Optional[Dict[str, Any]] = None):
        """Log de etapa específica do processo"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        message = f"🔄 STEP [{step_name}] - {status} - {timestamp}"
        
        if details:
            message = f"{message} | Details: {json.dumps(details, default=str)}"
        
        if status.upper() in ["ERROR", "FAILED", "CRITICAL"]:
            self.error(message)
        elif status.upper() in ["WARNING", "WARN"]:
            self.warning(message)
        else:
            self.info(message)
    
    def log_performance(self, operation: str, duration: float, details: Optional[Dict[str, Any]] = None):
        """Log de performance de operações"""
        message = f"⏱️ PERFORMANCE [{operation}] - {duration:.3f}s"
        
        if details:
            message = f"{message} | Details: {json.dumps(details, default=str)}"
        
        # Classificar por duração
        if duration > 10.0:
            self.warning(message)
        elif duration > 5.0:
            self.info(message)
        else:
            self.debug(message)
    
    def log_data_validation(self, data_type: str, status: str, issues: Optional[List[str]] = None):
        """Log específico para validação de dados"""
        message = f"✅ VALIDATION [{data_type}] - {status}"
        
        if issues:
            message = f"{message} | Issues: {len(issues)}"
            self.info(message)
            for issue in issues[:5]:  # Mostrar apenas os primeiros 5
                self.debug(f"  └─ Issue: {issue}")
            if len(issues) > 5:
                self.debug(f"  └─ ... e mais {len(issues) - 5} issues")
        else:
            self.info(message)
    
    def log_file_operation(self, operation: str, file_path: Path, status: str, details: Optional[Dict[str, Any]] = None):
        """Log específico para operações de arquivo"""
        message = f"📁 FILE [{operation}] {file_path} - {status}"
        
        if details:
            message = f"{message} | Details: {json.dumps(details, default=str)}"
        
        if status.upper() in ["ERROR", "FAILED"]:
            self.error(message)
        elif status.upper() in ["WARNING", "WARN"]:
            self.warning(message)
        else:
            self.info(message)
    
    def log_script_generation(self, script_name: str, phase: str, status: str, metrics: Optional[Dict[str, Any]] = None):
        """Log específico para geração de scripts"""
        message = f"📋 SCRIPT [{script_name}] {phase} - {status}"
        
        if metrics:
            message = f"{message} | Metrics: {json.dumps(metrics, default=str)}"
        
        if status.upper() in ["ERROR", "FAILED"]:
            self.error(message)
        elif status.upper() in ["WARNING", "WARN"]:
            self.warning(message)
        else:
            self.info(message)
    
    def create_session_logger(self, session_id: str) -> 'SessionLogger':
        """Criar logger de sessão para rastrear operações relacionadas"""
        return SessionLogger(self, session_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obter estatísticas de logging"""
        duration = datetime.now() - self.stats['start_time']
        
        return {
            'session_duration': str(duration),
            'total_logs': sum(self.stats[key] for key in ['debug', 'info', 'warning', 'error', 'critical']),
            'by_level': {
                'debug': self.stats['debug'],
                'info': self.stats['info'],
                'warning': self.stats['warning'],
                'error': self.stats['error'],
                'critical': self.stats['critical']
            },
            'log_files': {
                'main': str(self.log_dir / f"{self.name.lower()}.log"),
                'errors': str(self.log_dir / f"{self.name.lower()}_errors.log")
            }
        }
    
    def generate_summary_report(self) -> str:
        """Gerar relatório resumo da sessão de logging"""
        stats = self.get_statistics()
        
        report = []
        report.append("=" * 60)
        report.append("📝 RELATÓRIO DE LOGGING - DetailedLogger")
        report.append("=" * 60)
        report.append("")
        
        report.append("📊 ESTATÍSTICAS DA SESSÃO:")
        report.append(f"  - Duração: {stats['session_duration']}")
        report.append(f"  - Total de logs: {stats['total_logs']:,}")
        report.append("")
        
        report.append("📋 LOGS POR NÍVEL:")
        for level, count in stats['by_level'].items():
            percentage = (count / stats['total_logs'] * 100) if stats['total_logs'] > 0 else 0
            report.append(f"  - {level.upper()}: {count:,} ({percentage:.1f}%)")
        report.append("")
        
        report.append("📁 ARQUIVOS DE LOG:")
        for log_type, path in stats['log_files'].items():
            if Path(path).exists():
                size = Path(path).stat().st_size
                report.append(f"  - {log_type.upper()}: {path} ({size:,} bytes)")
            else:
                report.append(f"  - {log_type.upper()}: {path} (não existe)")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def close(self):
        """Fechar logger e handlers"""
        self.info("Fechando DetailedLogger")
        
        # Fechar todos os handlers
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)


class SessionLogger:
    """Logger de sessão para rastrear operações relacionadas"""
    
    def __init__(self, parent_logger: DetailedLogger, session_id: str):
        """
        Inicializar logger de sessão
        
        Args:
            parent_logger: Logger pai
            session_id: ID da sessão
        """
        self.parent = parent_logger
        self.session_id = session_id
        self.start_time = datetime.now()
        self.operations = []
        
        self.parent.info(f"🚀 SESSION START [{session_id}]")
    
    def log_operation(self, operation: str, status: str, details: Optional[Dict[str, Any]] = None):
        """Log de operação da sessão"""
        timestamp = datetime.now()
        duration = (timestamp - self.start_time).total_seconds()
        
        operation_data = {
            'operation': operation,
            'status': status,
            'timestamp': timestamp.isoformat(),
            'duration_from_start': duration,
            'details': details or {}
        }
        
        self.operations.append(operation_data)
        
        message = f"🔄 SESSION [{self.session_id}] {operation} - {status} (+{duration:.2f}s)"
        
        if details:
            message = f"{message} | Details: {json.dumps(details, default=str)}"
        
        if status.upper() in ["ERROR", "FAILED"]:
            self.parent.error(message)
        elif status.upper() in ["WARNING", "WARN"]:
            self.parent.warning(message)
        else:
            self.parent.info(message)
    
    def close(self, final_status: str = "COMPLETED"):
        """Fechar sessão"""
        duration = datetime.now() - self.start_time
        
        summary = {
            'session_id': self.session_id,
            'duration': str(duration),
            'total_operations': len(self.operations),
            'final_status': final_status
        }
        
        self.parent.info(f"🏁 SESSION END [{self.session_id}] - {final_status} | Duration: {duration} | Operations: {len(self.operations)}")
        
        return summary


def test_detailed_logger():
    """Função de teste para DetailedLogger"""
    print("🧪 Testando DetailedLogger...")
    
    # Criar logger
    logger = DetailedLogger(
        name="TestLogger",
        log_level=logging.DEBUG,
        console_output=True
    )
    
    try:
        # Testar diferentes tipos de log
        logger.info("Iniciando teste do DetailedLogger")
        logger.debug("Mensagem de debug", {"test_data": "valor_teste"})
        logger.warning("Aviso de teste", {"warning_type": "test"})
        
        # Testar log de etapa
        logger.log_step("Inicialização", "START", {"component": "test"})
        logger.log_step("Processamento", "IN_PROGRESS", {"progress": 50})
        logger.log_step("Finalização", "COMPLETED", {"result": "success"})
        
        # Testar log de performance
        logger.log_performance("Operação de teste", 2.5, {"items_processed": 100})
        
        # Testar log de validação
        logger.log_data_validation("Excel", "VALID", [])
        logger.log_data_validation("Script", "INVALID", ["Sintaxe incorreta", "Comando ausente"])
        
        # Testar log de arquivo
        logger.log_file_operation("READ", Path("test.xlsx"), "SUCCESS", {"size": 1024})
        
        # Testar log de geração de script
        logger.log_script_generation("P1_script", "GENERATION", "SUCCESS", {"lines": 50, "commands": 25})
        
        # Testar logger de sessão
        session = logger.create_session_logger("TEST_SESSION_001")
        session.log_operation("Carregar dados", "SUCCESS", {"rows": 100})
        session.log_operation("Validar estrutura", "SUCCESS", {"errors": 0})
        session.log_operation("Gerar script", "SUCCESS", {"output_size": 2048})
        session.close("COMPLETED")
        
        # Testar tratamento de erro
        try:
            raise ValueError("Erro de teste")
        except Exception as e:
            logger.error("Erro capturado durante teste", e, {"context": "test_function"})
        
        # Gerar relatório
        print("\n" + logger.generate_summary_report())
        
        # Mostrar estatísticas
        stats = logger.get_statistics()
        print(f"\n📊 Estatísticas finais:")
        print(f"  - Total de logs: {stats['total_logs']}")
        print(f"  - Erros: {stats['by_level']['error']}")
        print(f"  - Avisos: {stats['by_level']['warning']}")
        
    finally:
        logger.close()
    
    print("✅ Teste do DetailedLogger concluído!")


if __name__ == "__main__":
    test_detailed_logger()