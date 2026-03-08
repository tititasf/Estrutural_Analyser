
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

"""
========================================================
💳 Módulo: Sistema de Créditos por Unidades - PilarAnalyzer
========================================================

📋 Funcionalidade: Gerenciamento de créditos baseado em unidades/itens
📆 Data: 18/07/2025
🔧 Autor: Claude & User

🎯 Sistema de Cobrança:
- 1 crédito = 1 item simples (Cima, Grade, ABCD)
- 3 créditos = 1 item completo (Cima, Grade, ABCD)
- Pavimento simples = 1 crédito × quantidade de itens
- Pavimento completo = 3 créditos × quantidade de itens

📊 Estrutura:
- CreditManager: Classe principal para gerenciar créditos
- Funções auxiliares para configuração e comunicação
- Sistema de cache para otimizar consultas

========================================================
"""

import os
import sys
import json
from datetime import datetime, timedelta
import threading
import time
import hashlib
import platform
import uuid
import math
import base64
import logging
import traceback
from functools import wraps

# Importações condicionais
requests = None

# Importar módulos de segurança
try:
    from src.core.security_utils import encrypt_string, decrypt_string, generate_signature, verify_signature
    from src.core.integrity_check import verify_executable_integrity
    from src.core.anti_tamper import perform_security_check
    SECURITY_MODULES_AVAILABLE = True
except ImportError:
    try:
        from security_utils import encrypt_string, decrypt_string, generate_signature, verify_signature
        from integrity_check import verify_executable_integrity
        from anti_tamper import perform_security_check
        SECURITY_MODULES_AVAILABLE = True
    except ImportError:
        SECURITY_MODULES_AVAILABLE = False
        print("AVISO: Módulos de segurança não disponíveis")

# Configurações do sistema
# URL criptografada para segurança (descriptografada em runtime)
# URL original (Versão 8): https://script.google.com/macros/s/AKfycbzR5KvC8tN8fXV4eZI9XZkR_nwbOrBFrflqrwoqQ5iEbc_41iUVq-idJbfQHK5A0Kk7/exec
# URL criptografada usando AES (Fernet) baseado em HWID
# OFUSCAÇÃO ADICIONAL: Variável renomeada para dificultar busca
_ASU_ENCRYPTED = b'gAAAAABpFxZwKBR13Zq5f-wT-GdV_ZxPgcqc7u5mdmIGtg62-UiIdP-qIZr4D3Vze4jaPnjc5q0NABIABb88Ya3oHYrCGQZ9EVWTfyKXGY6LkZeoGxt67DqQ2P_fRAED-LY-EzXrslG5Ll9WtXLZCQejoLohvpKvTnprbtFk5EwdSTAdP7q0lUBKUfkdt2gIaV-fuIsEjnWGEr2heGGzto_Bh_pegCmoPwvH63lRXxAJXZLoHOoMWu4='
_ASU_CACHE = None

def _get_apps_script_url():
    """
    Retorna a URL do Google Apps Script descriptografada em runtime
    OFUSCADO: Nome de função e variáveis renomeados para dificultar busca
    
    Returns:
        str: URL do Google Apps Script
    """
    global _ASU_CACHE
    
    # Se já descriptografou, retornar cache
    if _ASU_CACHE:
        return _ASU_CACHE
    
    # Tentar descriptografar se módulos de segurança disponíveis
    if SECURITY_MODULES_AVAILABLE:
        try:
            # Descriptografar URL usando security_utils (ofuscado)
            # Usar variável renomeada para dificultar busca
            _enc_data = _ASU_ENCRYPTED
            _dec_url = _dec_str(_enc_data)
            if _dec_url and _dec_url.startswith(_get_obf_str("https://")):
                _ASU_CACHE = _dec_url
                return _ASU_CACHE
        except Exception as e:
            credit_logger.warning(f"Erro ao descriptografar URL: {e}")
            # Continuar com fallback
    
    # Fallback: URL não criptografada (apenas para desenvolvimento/debug)
    # Em produção compilada, isso não deve acontecer
    # OFUSCADO: String dividida para dificultar busca
    _p1 = _get_obf_str("https://")
    _p2 = _get_obf_str("script.google.com")
    _p3 = "/macros/s/"
    _p4 = "AKfycbzR5KvC8tN8fXV4eZI9XZkR_nwbOrBFrflqrwoqQ5iEbc_41iUVq-idJbfQHK5A0Kk7"
    _p5 = "/exec"
    url_plain = _p1 + _p2 + _p3 + _p4 + _p5
    _ASU_CACHE = url_plain
    return _ASU_CACHE

# Função helper para compatibilidade
def get_apps_script_url():
    """Retorna a URL do Google Apps Script"""
    return _get_apps_script_url()

# Manter compatibilidade: APPS_SCRIPT_URL como variável global (será inicializada)
APPS_SCRIPT_URL = _get_apps_script_url()

# Ação para débito de créditos
# Sistema atualizado para trabalhar com unidades ao invés de área
DEBIT_ACTION = "debit_credits"  # Nova ação no Google Apps Script para sistema por unidades

# ========================================================
# 📝 SISTEMA DE LOGGING E TRATAMENTO DE ERROS
# ========================================================

def setup_logging():
    """Configura o sistema de logging para o módulo de créditos"""
    try:
        # Determinar diretório de logs
        if getattr(sys, 'frozen', False):
            log_dir = os.path.dirname(sys.executable)
        else:
            log_dir = os.path.dirname(os.path.abspath(__file__))
        
        log_file = os.path.join(log_dir, "credit_system.log")
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Logger específico para créditos
        logger = logging.getLogger('CreditSystem')
        logger.info("Sistema de logging inicializado")
        
        return logger
    except Exception as e:
        print(f"Erro ao configurar logging: {e}")
        return logging.getLogger('CreditSystem')

# Inicializar logger global
credit_logger = setup_logging()

def log_operation(operation_type, details=None, error=None):
    """
    Registra operações do sistema de créditos
    
    Args:
        operation_type: Tipo da operação (login, debit, reserve, etc.)
        details: Detalhes da operação
        error: Erro ocorrido (se houver)
    """
    try:
        timestamp = datetime.now().isoformat()
        hwid = _get_hw()[:8]  # Apenas primeiros 8 caracteres para privacidade
        
        log_entry = {
            "timestamp": timestamp,
            "operation": operation_type,
            "hwid": hwid,
            "details": details or {},
            "error": str(error) if error else None
        }
        
        if error:
            credit_logger.error(f"ERRO - {operation_type}: {error}")
            credit_logger.error(f"Detalhes: {json.dumps(log_entry, indent=2)}")
        else:
            credit_logger.info(f"SUCESSO - {operation_type}")
            credit_logger.debug(f"Detalhes: {json.dumps(log_entry, indent=2)}")
            
    except Exception as e:
        print(f"Erro ao registrar log: {e}")

def handle_credit_error(func):
    """
    Decorator para tratamento padronizado de erros em operações de crédito
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            
            # Log de sucesso
            log_operation(
                operation_type=func.__name__,
                details={
                    "args_count": len(args),
                    "kwargs": list(kwargs.keys()),
                    "success": True
                }
            )
            
            return result
            
        except Exception as e:
            # Log de erro
            log_operation(
                operation_type=func.__name__,
                details={
                    "args_count": len(args),
                    "kwargs": list(kwargs.keys()),
                    "success": False
                },
                error=e
            )
            
            # Re-raise com contexto adicional
            raise CreditSystemError(f"Erro em {func.__name__}: {str(e)}") from e
    
    return wrapper

class CreditSystemError(Exception):
    """Exceção personalizada para erros do sistema de créditos"""
    
    def __init__(self, message, error_code=None, details=None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()
        
        # Log automático do erro
        log_operation(
            operation_type="SYSTEM_ERROR",
            details={
                "error_code": error_code,
                "message": message,
                "details": self.details
            },
            error=self
        )

class ConnectionError(CreditSystemError):
    """Erro de conexão com o servidor"""
    pass

class InsufficientCreditsError(CreditSystemError):
    """Erro de créditos insuficientes"""
    pass

class ValidationError(CreditSystemError):
    """Erro de validação de dados"""
    pass

class OfflineError(CreditSystemError):
    """Erro relacionado ao modo offline"""
    pass

def safe_execute(func, *args, **kwargs):
    """
    Executa uma função de forma segura com tratamento de erro padronizado
    
    Returns:
        tuple: (success: bool, result: any, error_message: str)
    """
    try:
        result = func(*args, **kwargs)
        return True, result, None
    except CreditSystemError as e:
        return False, None, str(e)
    except Exception as e:
        error_msg = f"Erro inesperado em {func.__name__}: {str(e)}"
        log_operation(
            operation_type="UNEXPECTED_ERROR",
            details={"function": func.__name__},
            error=e
        )
        return False, None, error_msg

def validate_credit_data(data, required_fields):
    """
    Valida dados de entrada para operações de crédito
    
    Args:
        data: Dados a serem validados
        required_fields: Lista de campos obrigatórios
        
    Raises:
        ValidationError: Se dados inválidos
    """
    if not isinstance(data, dict):
        raise ValidationError("Dados devem ser um dicionário")
    
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(f"Campos obrigatórios ausentes: {', '.join(missing_fields)}")
    
    # Validações específicas
    if 'creditos' in data:
        try:
            creditos = float(data['creditos'])
            if creditos <= 0:
                raise ValidationError("Créditos devem ser maior que zero")
        except (ValueError, TypeError):
            raise ValidationError("Créditos devem ser um número válido")
    
    if 'area' in data:
        try:
            area = float(data['area'])
            if area <= 0:
                raise ValidationError("Área deve ser maior que zero")
        except (ValueError, TypeError):
            raise ValidationError("Área deve ser um número válido")

# Usar diretório do executável, não do módulo
def get_config_file_path():
    """Retorna o caminho correto para o arquivo de configuração"""
    if getattr(sys, 'frozen', False):
        # Executável PyInstaller
        base_path = os.path.dirname(sys.executable)
    else:
        # Código fonte - usar diretório root do projeto para compartilhar entre processos
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        # Subir 2 níveis: src/core -> src -> raiz do projeto
        base_path = os.path.dirname(os.path.dirname(current_file_dir))
    
    config_path = os.path.join(base_path, ".config")
    print(f"[DEBUG] Arquivo de configuração: {config_path}")
    return config_path

CONFIG_FILE = get_config_file_path()

# Chave de criptografia baseada no HWID
def get_encryption_key():
    """Gera uma chave de criptografia baseada no HWID"""
    hwid = _get_hw()
    return hashlib.sha256(hwid.encode()).digest()[:32]

def encrypt_data(data):
    """Criptografa dados usando AES"""
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        key = get_encryption_key()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'pilar_analyzer_salt',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key))
        f = Fernet(key)
        return f.encrypt(json.dumps(data).encode())
    except ImportError:
        # Fallback para versão sem criptografia
        return json.dumps(data).encode()

def decrypt_data(encrypted_data):
    """Descriptografa dados usando AES"""
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        key = get_encryption_key()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'pilar_analyzer_salt',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key))
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_data)
        return json.loads(decrypted.decode())
    except (ImportError, Exception):
        # Fallback para versão sem criptografia
        return json.loads(encrypted_data.decode())

def importar_requests():
    """Importa o módulo requests apenas quando necessário"""
    global requests
    if requests is None:
        try:
            import requests as req
            requests = req
            return True
        except ImportError:
            return False
    return True

def _get_hw():
    """Gera um identificador único de hardware mais robusto"""
    try:
        system_info = platform.uname()
        cpu_info = platform.processor()
        
        # Informações mais robustas para Windows
        if platform.system() == "Windows":
            try:
                import winreg
                import subprocess
                
                # Machine GUID do registro
                registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
                
                # BIOS Serial Number
                try:
                    result = subprocess.run(['wmic', 'bios', 'get', 'serialnumber'], 
                                          capture_output=True, text=True, timeout=30)
                    bios_serial = result.stdout.strip().split('\n')[1] if result.returncode == 0 else ""
                except:
                    bios_serial = ""
                
                # Disk Serial Number
                try:
                    result = subprocess.run(['wmic', 'diskdrive', 'get', 'serialnumber'], 
                                          capture_output=True, text=True, timeout=30)
                    disk_serial = result.stdout.strip().split('\n')[1] if result.returncode == 0 else ""
                except:
                    disk_serial = ""
                
                # MAC Address
                mac_address = str(uuid.getnode())
                
                combined_info = f"{system_info.system}_{system_info.node}_{cpu_info}_{machine_guid}_{bios_serial}_{disk_serial}_{mac_address}"
                
            except Exception as e:
                # Fallback para informações básicas
                machine_guid = str(uuid.getnode())
                combined_info = f"{system_info.system}_{system_info.node}_{cpu_info}_{machine_guid}"
        else:
            # Para outros sistemas operacionais
            machine_guid = str(uuid.getnode())
            combined_info = f"{system_info.system}_{system_info.node}_{cpu_info}_{machine_guid}"
        
        # Hash mais longo para maior segurança
        hwid = hashlib.sha256(combined_info.encode()).hexdigest()[:32]
        return hwid
    except Exception as e:
        # Fallback final
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:32]

def salvar_config_usuario(user_id, api_key):
    """Salva as configurações do usuário localmente com criptografia"""
    try:
        config = {
            _get_obf_str("user_id"): user_id,
            _get_obf_str("api_key"): api_key,
            "hwid": _get_hw(),
            "last_login": datetime.now().isoformat()
        }
        encrypted_data = encrypt_data(config)
        with open(CONFIG_FILE, 'wb') as f:
            f.write(encrypted_data)
        return True
    except Exception as e:
        print(f"Erro ao salvar configuração: {e}")
        return False

def carregar_config_usuario():
    """Carrega as configurações do usuário com descriptografia"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'rb') as f:
                encrypted_data = f.read()
                config = decrypt_data(encrypted_data)
                return config.get(_get_obf_str("user_id")), config.get(_get_obf_str("api_key"))
    except:
        pass
    return None, None

def calcular_soma_string(valor_soma):
    """
    Calcula o valor total de uma string no formato de soma (ex: '122+132').
    Retorna 0.0 se o formato for inválido.
    """
    try:
        if not valor_soma:
            return 0.0
            
        if isinstance(valor_soma, str):
            # Remover espaços e converter vírgulas para pontos
            valor_soma = valor_soma.strip().replace(',', '.')
            
            if '+' in valor_soma:
                # Somar todas as partes convertidas para float
                partes = valor_soma.split('+')
                return sum(float(parte.strip()) for parte in partes)
            else:
                # Valor único
                return float(valor_soma)
        else:
            # Valor numérico direto
            return float(valor_soma)
    except (ValueError, TypeError):
        return 0.0

class CreditManager:
    """Gerenciador de créditos para o sistema PilarAnalyzer"""
    
    def __init__(self, user_id, api_key):
        """
        Inicializa o gerenciador de créditos
        
        IMPORTANTE: Aceita QUALQUER senha (api_key) que esteja cadastrada no Google Sheets.
        Não há validação de formato ou padrão - a senha será validada no servidor
        comparando com o valor armazenado na planilha do Google Sheets.
        
        Args:
            user_id: ID do usuário (deve existir no Google Sheets)
            api_key: Senha/API Key do usuário (pode ser QUALQUER valor que esteja no Sheets)
        """
        # Limpar espaços em branco e garantir que não está vazio
        self._uid = str(user_id).strip() if user_id else ""
        self._ak = str(api_key).strip() if api_key else ""  # Aceita QUALQUER senha - validação feita no servidor
        self._sa = 0
        self.last_check = None
        self.cache_timeout = 300  # 5 minutos
        self.hwid = _get_hw()
        self.session_token = None
        self.creditos_reservados = 0
        # Flag para modo offline (sem capacidade de desenho)
        self.modo_offline = (user_id == "offline" and api_key == "offline_mode")
        
        # Validações de segurança
        self.integrity_valid = True
        self.security_warnings = []
        
        # Validar integridade do executável (MODO STRICT ATIVADO)
        if SECURITY_MODULES_AVAILABLE and not self.modo_offline:
            try:
                # MODO STRICT: Bloqueia operações se integridade falhar
                integrity_valid, integrity_msg = _ver_int(strict_mode=True)
                self.integrity_valid = integrity_valid
                if not integrity_valid:
                    self.security_warnings.append(f"Integridade: {integrity_msg}")
                    credit_logger.error(f"ERRO DE SEGURANÇA: {integrity_msg}")
                    # Em modo strict, definir modo offline para bloquear operações
                    if not integrity_valid:
                        self.modo_offline = True
                        credit_logger.error("MODO OFFLINE ATIVADO: Executável foi modificado!")
            except Exception as e:
                credit_logger.warning(f"Erro ao verificar integridade: {e}")
        
        # Verificação anti-tampering (MODO STRICT ATIVADO)
        # NOTA: Desabilitado temporariamente durante inicialização para evitar bloqueios
        # A verificação será feita após o login ser bem-sucedido
        if SECURITY_MODULES_AVAILABLE and not self.modo_offline:
            try:
                # MODO STRICT: Bloqueia operações se problemas críticos forem detectados
                # Mas NÃO bloqueia durante a inicialização (apenas avisa)
                is_secure, issues, warnings = _sec_chk(strict_mode=False)  # Modo não-strict durante init
                if issues:
                    self.security_warnings.extend(issues)
                    credit_logger.warning(f"AVISOS DE SEGURANÇA (não bloqueante): {', '.join(issues)}")
                    # NÃO ativar modo offline durante inicialização - apenas avisar
                if warnings:
                    self.security_warnings.extend(warnings)
                    credit_logger.warning(f"Avisos de segurança: {', '.join(warnings)}")
            except Exception as e:
                credit_logger.warning(f"Erro na verificação de segurança: {e}")
                # Não bloquear se houver erro na verificação
        
        self._validate_environment()
    
    def _validate_environment(self):
        """
        Valida o ambiente de execução
        
        NOTA: NÃO há validação de formato de senha aqui.
        Qualquer senha será aceita e validada no servidor Google Apps Script,
        que compara com o valor armazenado no Google Sheets.
        """
        try:
            # NENHUMA validação de formato de senha - aceita QUALQUER valor
            # A validação será feita dinamicamente no servidor Google Apps Script
            # O servidor compara a senha fornecida com a armazenada no Google Sheets
            
            # Verificar se não está sendo executado em ambiente virtualizado (opcional)
            if self._detect_virtualization():
                print("⚠️ Ambiente virtualizado detectado - continuando mesmo assim")
                
        except Exception as e:
            print(f"Aviso de validação: {e}")
            # Não interrompe mais a execução
    
    def _detect_virtualization(self):
        """Detecta se está sendo executado em ambiente virtualizado"""
        try:
            if platform.system() == "Windows":
                import subprocess
                result = subprocess.run(['wmic', 'computersystem', 'get', 'model'], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    model = result.stdout.lower()
                    vm_indicators = ['virtual', 'vmware', 'vbox', 'qemu', 'xen']
                    return any(indicator in model for indicator in vm_indicators)
        except:
            pass
        return False
    
    def verificar_conexao(self, log_callback=None):
        """Verifica se pode conectar ao servidor de créditos"""
        if not importar_requests():
            if log_callback:
                log_callback("❌ Módulo requests não disponível.")
            return False
        
        try:
            if log_callback:
                log_callback(f"🌐 Testando conexão com servidor...")
            response = requests.get(_get_apps_script_url() + "?ping=true", timeout=10)
            if response.status_code == 200:
                if log_callback:
                    log_callback("✅ Conexão com servidor estabelecida")
                return True
            else:
                if log_callback:
                    log_callback(f"⚠️ Servidor respondeu com código: {response.status_code}")
                return False
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                if log_callback:
                    log_callback("❌ Timeout: Servidor não respondeu a tempo")
                return False
            elif "connection" in error_str or "connect" in error_str:
                if log_callback:
                    log_callback("❌ Erro de conexão: Não foi possível conectar ao servidor")
                    log_callback("💡 Verifique sua conexão com a internet")
                return False
            else:
                if log_callback:
                    log_callback(f"❌ Erro de conexão: {str(e)}")
                return False
    
    def _cons_sal(self, log_callback=None, force_refresh=False):
        """Consulta o saldo atual do usuário"""
        # Verificar cache se não for refresh forçado
        if not force_refresh and self.last_check:
            tempo_cache = (datetime.now() - self.last_check).total_seconds()
            if tempo_cache < self.cache_timeout:
                if log_callback:
                    log_callback(_get_obf_str("saldo"))
                return True, float(self._sa)
        
        if not importar_requests():
            if log_callback:
                log_callback("❌ Módulo requests não disponível.")
            return False, 0.0
        
        try:
            # Garantir que user_id e api_key estão limpos (sem espaços)
            user_id_clean = str(self._uid).strip()
            api_key_clean = str(self._ak).strip()
            
            payload = {
                "userId": user_id_clean,
                "apiKey": api_key_clean,
                "action": "check_balance"
            }
            
            # Debug: mostrar user_id (mas não a senha completa por segurança)
            if log_callback:
                api_key_preview = api_key_clean[:3] + "..." if len(api_key_clean) > 3 else "***"
                log_callback(_get_obf_str("api_key"))
            
            response = requests.post(
                _get_apps_script_url(),
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10  # Timeout aumentado para conexões mais lentas
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self._sa = float(data.get("balance", 0))
                    self.last_check = datetime.now()
                    if log_callback:
                        log_callback(_get_obf_str("saldo"))
                    return True, float(self._sa)
                else:
                    error_msg = data.get("message", "Erro desconhecido")
                    # Mensagem mais detalhada para ajudar no debug
                    if log_callback:
                        log_callback(f"❌ {error_msg}")
                        if "não autorizado" in error_msg.lower() or "credenciais" in error_msg.lower():
                            log_callback("💡 Dica: Verifique se o UserID e a senha correspondem exatamente ao que está no Google Sheets")
                            log_callback("💡 Atenção: A comparação é case-sensitive (diferencia maiúsculas/minúsculas)")
                    return False, 0.0
            else:
                if log_callback:
                    log_callback(f"❌ Erro HTTP: {response.status_code}")
                    try:
                        error_data = response.json()
                        if error_data.get("message"):
                            log_callback(f"📋 Detalhes: {error_data.get('message')}")
                    except:
                        pass
                return False, 0.0
                
        except Exception as e:
            error_msg = f"Erro de conexão: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, 0.0
    
    def calcular_area_pilar(self, dados_pilar):
        """Calcula a área de um pilar individual em m²"""
        try:
            # Validar dados do pilar
            if not dados_pilar:
                return 0.0
                
            # Obter dimensões do pilar (comprimento e largura em cm)
            comprimento = calcular_soma_string(dados_pilar.get('comprimento', 0))
            largura = calcular_soma_string(dados_pilar.get('largura', 0))
            
            # Validar dimensões
            if comprimento <= 0 or largura <= 0:
                return 0.0
            
            # Calcular área em cm² e converter para m²
            area_cm2 = comprimento * largura
            area_m2 = area_cm2 / 10000  # Converter cm² para m²
            
            return area_m2
            
        except Exception as e:
            print(f"Erro ao calcular área do pilar: {str(e)}")
            return 0.0
    
    def calcular_area_pavimento(self, lista_dados_pilares):
        """Calcula a área total de um pavimento (soma de todos os pilares) em m²"""
        try:
            if not lista_dados_pilares:
                return 0.0
            
            area_total = 0.0
            for dados_pilar in lista_dados_pilares:
                area_pilar = self.calcular_area_pilar(dados_pilar)
                area_total += area_pilar
            
            return area_total
            
        except Exception as e:
            print(f"Erro ao calcular área do pavimento: {str(e)}")
            return 0.0
    
    def _calc_cr_nec(self, quantidade_itens, tipo_operacao="item_simples", quantidade_especiais=0):
        """
        Calcula quantos créditos são necessários baseado na quantidade de itens e tipo de operação
        
        Args:
            quantidade_itens: Número total de itens a serem processados
            tipo_operacao: "item_simples" (1 crédito/item comum, 2 créditos/item especial), 
                          "item_completo" (3 créditos/item)
            quantidade_especiais: Número de itens especiais (para CIMA/ABCD/GRADES: 2 créditos cada)
        
        Returns:
            int: Número de créditos necessários
        """
        if tipo_operacao == "item_completo":
            return quantidade_itens * 3
        elif tipo_operacao == "item_simples":
            # Itens especiais: 2 créditos cada
            # Itens comuns: 1 crédito cada
            quantidade_comuns = quantidade_itens - quantidade_especiais
            return (quantidade_comuns * 1) + (quantidade_especiais * 2)
        else:
            return quantidade_itens * 1
    
    def gerar_descricao_detalhada(self, obra="", pavimento="", nivel_saida="", nivel_chegada="", 
                                   numero_item="", nome="", tipo="", area_m2=0, parte_desenho=""):
        """
        Gera descrição detalhada formatada para logs de transação
        
        Args:
            obra: Nome da obra
            pavimento: Nome do pavimento
            nivel_saida: Nível de saída (apenas se 1 item)
            nivel_chegada: Nível de chegada (apenas se 1 item)
            numero_item: Número do item (apenas se 1 item)
            nome: Nome do item (apenas se 1 item)
            tipo: Tipo do item (comum/especial)
            area_m2: Área em m² (do item ou do pavimento completo)
            parte_desenho: Parte do desenho (CIMA, ABCD, GRADES, PAVIMENTO COMPLETO, 1 ITEM SOMENTE)
        
        Returns:
            str: Descrição formatada
        """
        partes = []
        
        if obra:
            partes.append(f"Obra: {obra}")
        if pavimento:
            partes.append(f"Pavimento: {pavimento}")
        if nivel_saida:
            partes.append(f"Nivel Saida: {nivel_saida}")
        if nivel_chegada:
            partes.append(f"Nivel Chegada: {nivel_chegada}")
        if numero_item:
            partes.append(f"Numero Item: {numero_item}")
        if nome:
            partes.append(f"Nome: {nome}")
        if tipo:
            partes.append(f"Tipo: {tipo}")
        if area_m2:
            partes.append(f"Area m2: {area_m2:.2f}")
        if parte_desenho:
            partes.append(f"Parte do desenho: {parte_desenho}")
        
        return ", ".join(partes) if partes else "Transação de créditos"
    
    def reservar_creditos(self, creditos, log_callback=None):
        """Reserva créditos antes da execução"""
        try:
            # Verificar saldo atual
            sucesso, saldo = self._cons_sal(log_callback, force_refresh=True)
            if not sucesso:
                return False, "Erro ao consultar saldo"
            
            if float(saldo) < creditos:
                return False, _get_obf_str("credit")
            
            # Reservar créditos localmente
            self.creditos_reservados += creditos
            
            if log_callback:
                log_callback(_get_obf_str("credit"))
            
            return True, _get_obf_str("credit")
            
        except Exception as e:
            error_msg = f"Erro ao reservar créditos: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, error_msg
    
    def liberar_creditos_reservados(self, creditos, log_callback=None):
        """Libera créditos reservados em caso de erro"""
        try:
            self.creditos_reservados = max(0, self.creditos_reservados - creditos)
            
            if log_callback:
                log_callback(_get_obf_str("credit"))
            
            return True, _get_obf_str("credit")
            
        except Exception as e:
            error_msg = f"Erro ao liberar créditos: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, error_msg
    
    def _conf_cons(self, creditos, descricao, log_callback=None):
        """Confirma o consumo de créditos após operação bem-sucedida"""
        try:
            if not importar_requests():
                error_msg = "❌ Módulo requests não disponível."
                print(f"[DEBUG] {error_msg}")
                if log_callback:
                    log_callback(error_msg)
                return False, "Erro de conexão"
            
            # Gerar assinatura digital para validação reforçada
            timestamp = str(int(time.time()))
            
            # Converter créditos para int (a API pode não aceitar float)
            creditos_int = int(creditos)
            
            # Criar assinatura digital usando módulo de segurança se disponível
            if SECURITY_MODULES_AVAILABLE:
                try:
                    signature_data = {
                        'userId': self._uid,
                        'credits': creditos_int,
                        'timestamp': timestamp,
                        'hwid': self.hwid
                    }
                    signature = _gen_sig(signature_data, secret_key=self._ak)
                except Exception:
                    # Fallback para assinatura simples
                    signature_data = _get_obf_str("credit")
                    signature = hashlib.sha256(signature_data.encode()).hexdigest()
            else:
                # Assinatura simples se módulos de segurança não disponíveis
                signature_data = _get_obf_str("credit")
                signature = hashlib.sha256(signature_data.encode()).hexdigest()
            
            # Rate limiting local (máximo 10 requisições por minuto)
            if not hasattr(self, '_request_timestamps'):
                self._request_timestamps = []
            
            current_time = time.time()
            # Remover timestamps antigos (mais de 1 minuto)
            self._request_timestamps = [t for t in self._request_timestamps if current_time - t < 60]
            
            if len(self._request_timestamps) >= 10:
                error_msg = "Rate limit excedido: muitas requisições. Aguarde alguns segundos."
                if log_callback:
                    log_callback(f"❌ {error_msg}")
                return False, error_msg
            
            self._request_timestamps.append(current_time)
            
            # Sistema por unidades - enviar créditos diretamente
            payload = {
                'userId': self._uid,
                'apiKey': self._ak,
                'action': DEBIT_ACTION,  # "debit_credits" - novo sistema por unidades
                'credits': creditos_int,  # Quantidade de créditos a debitar (unidades)
                'description': descricao,
                'timestamp': timestamp,
                'hwid': self.hwid,
                'signature': signature,
                _get_obf_str("integrity_check"): self.integrity_valid  # Informar servidor sobre integridade
            }
            
            # Logs reduzidos para melhor performance
            response = requests.post(
                _get_apps_script_url(),
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=5  # Timeout otimizado para resposta mais rápida (mantendo segurança)
            )
            
            # Tratar erro 429 (Too Many Requests) - aguardar e tentar novamente
            if response.status_code == 429:
                print("[DEBUG] Erro 429 - Muitas requisições. Aguardando 2 segundos e tentando novamente...")
                time.sleep(2)  # Aguardar 2 segundos
                
                # Tentar novamente uma vez
                print("[DEBUG] Tentando novamente após espera...")
                response = requests.post(
                    _get_apps_script_url(),
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=5  # Timeout otimizado
                )
                if response.status_code == 429:
                    error_msg = "Muitas requisições ao servidor. Aguarde alguns segundos e tente novamente."
                    print(f"[DEBUG] ❌ Ainda recebendo 429 após retry: {error_msg}")
                    if log_callback:
                        log_callback(f"❌ {error_msg}")
                    return False, error_msg
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if data.get('status') == 'success':
                        self._sa = float(data.get('newBalance', 0))
                        self.creditos_reservados = max(0, self.creditos_reservados - creditos)
                        self.last_check = datetime.now()
                        
                        success_msg = _get_obf_str("credit")
                        balance_msg = _get_obf_str("saldo")
                        
                        if log_callback:
                            log_callback(success_msg)
                            log_callback(balance_msg)
                        
                        return True, _get_obf_str("credit")
                    else:
                        error_msg = data.get('message', 'Erro ao debitar créditos')
                        
                        if log_callback:
                            log_callback(f"❌ {error_msg}")
                        return False, error_msg
                except json.JSONDecodeError as json_err:
                    error_msg = f"Erro ao parsear JSON da resposta: {json_err}"
                    if log_callback:
                        log_callback(f"❌ {error_msg}")
                    return False, error_msg
            else:
                error_msg = f"Erro HTTP: {response.status_code}"
                if log_callback:
                    log_callback(f"❌ {error_msg}")
                return False, error_msg
                
        except requests.exceptions.RequestException as req_err:
            error_msg = f"Erro na requisição HTTP: {str(req_err)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = _get_obf_str("consumo")
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, error_msg
    
    def debitar_credito_por_area(self, dados_pilar, log_callback=None):
        """Debita créditos baseado na área calculada de um pilar"""
        try:
            # Calcular área total
            area_total = float(self.calcular_area_pilar(dados_pilar))
            if area_total <= 0:
                if log_callback:
                    log_callback("❌ Área inválida calculada")
                return False, "Área inválida"
            
            # Arredondar para cima para garantir cobertura
            creditos_necessarios = self._calc_cr_nec(area_total)
            
            if log_callback:
                log_callback(f"📐 Área calculada: {area_total:.2f} m²")
                log_callback(_get_obf_str("credit"))
            
            # Confirmar consumo
            return self._conf_cons(creditos_necessarios, f"Pilar {dados_pilar.get('nome', '')}", log_callback)
            
        except Exception as e:
            error_msg = f"Erro ao processar área: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, error_msg
    
    def debitar_multiplos_pilares(self, lista_dados_pilares, log_callback=None):
        """Debita créditos para múltiplos pilares (usado no pavimento)"""
        if not lista_dados_pilares:
            return True, "Nenhum pilar para processar"
        
        try:
            area_total_pavimento = self.calcular_area_pavimento(lista_dados_pilares)
            if area_total_pavimento <= 0:
                erro_msg = "❌ Área total inválida do pavimento"
                if log_callback:
                    log_callback(erro_msg)
                return False, erro_msg
            
            creditos_necessarios = self._calc_cr_nec(area_total_pavimento)
            
            if log_callback:
                log_callback(f"🏢 Processando pavimento com {len(lista_dados_pilares)} pilares")
                log_callback(f"📐 Área total do pavimento: {area_total_pavimento:.2f} m²")
                log_callback(_get_obf_str("credit"))
            
            # Verificar saldo
            sucesso_saldo, saldo_atual = self._cons_sal(log_callback, force_refresh=True)
            if not sucesso_saldo or float(saldo_atual) < creditos_necessarios:
                error_msg = _get_obf_str("credit")
                if log_callback:
                    log_callback(f"❌ {error_msg}")
                return False, error_msg
            
            # Confirmar consumo
            return self._conf_cons(creditos_necessarios, f"Pavimento com {len(lista_dados_pilares)} pilares", log_callback)
                
        except Exception as e:
            error_msg = f"Erro de conexão: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, error_msg

    # ========================================================
    # 🔄 SISTEMA DE MODO OFFLINE
    # ========================================================
    
    def _get_offline_file_path(self):
        """Retorna o caminho do arquivo de transações offline"""
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, ".offline_transactions")
    
    def _get_offline_cache_path(self):
        """Retorna o caminho do arquivo de cache offline"""
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, ".offline_cache")
    
    def verificar_conectividade(self):
        """Verifica se há conectividade com o servidor"""
        try:
            if not importar_requests():
                return False
            
            # Verificação simplificada - assumir online se requests está disponível
            # A verificação real será feita na consulta de saldo
            return True
                
        except Exception as e:
            # Em caso de erro, assumir online para não bloquear desnecessariamente
            return True
    
    def salvar_transacao_offline(self, creditos, descricao, log_callback=None):
        """Salva uma transação para sincronização posterior quando online"""
        try:
            transacao = {
                "id": hashlib.sha256(_get_obf_str("credit").encode()).hexdigest()[:16],
                _get_obf_str("user_id"): self._uid,
                "creditos": creditos,
                "descricao": descricao,
                "timestamp": datetime.now().isoformat(),
                "hwid": self.hwid,
                "status": "pending"
            }
            
            # Carregar transações existentes
            transacoes_offline = self._carregar_transacoes_offline()
            transacoes_offline.append(transacao)
            
            # Salvar com criptografia
            encrypted_data = encrypt_data(transacoes_offline)
            with open(self._get_offline_file_path(), 'wb') as f:
                f.write(encrypted_data)
            
            if log_callback:
                log_callback(_get_obf_str("credit"))
            
            return True, transacao["id"]
            
        except Exception as e:
            error_msg = f"Erro ao salvar transação offline: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, error_msg
    
    def _carregar_transacoes_offline(self):
        """Carrega transações offline salvas"""
        try:
            offline_file = self._get_offline_file_path()
            if os.path.exists(offline_file):
                with open(offline_file, 'rb') as f:
                    encrypted_data = f.read()
                    return decrypt_data(encrypted_data)
        except:
            pass
        return []
    
    def sincronizar_transacoes_offline(self, log_callback=None):
        """Sincroniza transações offline com o servidor quando conectado"""
        try:
            if not self.verificar_conectividade():
                if log_callback:
                    log_callback("❌ Sem conectividade para sincronização")
                return False, "Sem conectividade"
            
            transacoes = self._carregar_transacoes_offline()
            if not transacoes:
                if log_callback:
                    log_callback("✅ Nenhuma transação offline para sincronizar")
                return True, "Nenhuma transação pendente"
            
            transacoes_sincronizadas = 0
            transacoes_falha = []
            
            for transacao in transacoes:
                if transacao.get("status") == "pending":
                    sucesso, mensagem = self._conf_cons(
                        transacao["creditos"], 
                        f"[OFFLINE] {transacao['descricao']}", 
                        log_callback
                    )
                    
                    if sucesso:
                        transacao["status"] = "synchronized"
                        transacao["sync_timestamp"] = datetime.now().isoformat()
                        transacoes_sincronizadas += 1
                    else:
                        transacao["status"] = "failed"
                        transacao["error"] = mensagem
                        transacoes_falha.append(transacao)
            
            # Salvar transações atualizadas
            encrypted_data = encrypt_data(transacoes)
            with open(self._get_offline_file_path(), 'wb') as f:
                f.write(encrypted_data)
            
            if log_callback:
                log_callback(f"🔄 Sincronizadas {transacoes_sincronizadas} transações")
                if transacoes_falha:
                    log_callback(f"⚠️ {len(transacoes_falha)} transações falharam")
            
            return True, f"Sincronizadas {transacoes_sincronizadas} transações"
            
        except Exception as e:
            error_msg = f"Erro na sincronização: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, error_msg
    
    def salvar_cache_offline(self, saldo, log_callback=None):
        """Salva o saldo em cache para uso offline"""
        try:
            cache_data = {
                _get_obf_str("saldo"): saldo,
                "timestamp": datetime.now().isoformat(),
                "hwid": self.hwid,
                _get_obf_str("user_id"): self._uid,
                "expires_at": (datetime.now() + timedelta(days=7)).isoformat()
            }
            
            encrypted_data = encrypt_data(cache_data)
            with open(self._get_offline_cache_path(), 'wb') as f:
                f.write(encrypted_data)
            
            if log_callback:
                log_callback(_get_obf_str("saldo"))
            
            return True
            
        except Exception as e:
            if log_callback:
                log_callback(f"❌ Erro ao salvar cache offline: {str(e)}")
            return False
    
    def carregar_cache_offline(self, log_callback=None):
        """Carrega o saldo do cache offline"""
        try:
            cache_file = self._get_offline_cache_path()
            if not os.path.exists(cache_file):
                return False, 0.0, "Cache não encontrado"
            
            with open(cache_file, 'rb') as f:
                encrypted_data = f.read()
                cache_data = decrypt_data(encrypted_data)
            
            # Verificar se o cache não expirou
            expires_at = datetime.fromisoformat(cache_data["expires_at"])
            if datetime.now() > expires_at:
                if log_callback:
                    log_callback("⚠️ Cache offline expirado (7 dias)")
                return False, 0.0, "Cache expirado"
            
            # Verificar se é do mesmo usuário e HWID
            if (cache_data.get(_get_obf_str("user_id")) != self._uid or 
                cache_data.get("hwid") != self.hwid):
                if log_callback:
                    log_callback("⚠️ Cache offline inválido para este usuário/computador")
                return False, 0.0, "Cache inválido"
            
            saldo = float(cache_data[_get_obf_str("saldo")])
            timestamp = cache_data["timestamp"]
            
            if log_callback:
                log_callback(_get_obf_str("saldo"))
                log_callback(f"📅 Última atualização: {timestamp}")
            
            return True, saldo, "Cache válido"
            
        except Exception as e:
            error_msg = f"Erro ao carregar cache offline: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, 0.0, error_msg
    
    def consultar_saldo_offline_first(self, log_callback=None):
        """Consulta saldo priorizando modo offline quando não há conectividade"""
        try:
            # Tentar conexão online primeiro
            if self.verificar_conectividade():
                if log_callback:
                    log_callback("🌐 Conectividade disponível, consultando online...")
                
                sucesso, saldo = self._cons_sal(log_callback, force_refresh=True)
                if sucesso:
                    # Salvar em cache para uso offline
                    self.salvar_cache_offline(saldo, log_callback)
                    return True, saldo
            
            # Se não há conectividade ou falha online, usar cache offline
            if log_callback:
                log_callback("📱 Sem conectividade, usando cache offline...")
            
            sucesso_cache, saldo_cache, mensagem = self.carregar_cache_offline(log_callback)
            if sucesso_cache:
                return True, saldo_cache
            else:
                if log_callback:
                    log_callback(f"❌ Falha no cache offline: {mensagem}")
                return False, 0.0
                
        except Exception as e:
            error_msg = f"Erro na consulta offline-first: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, 0.0
    
    def _deb_cr_imm(self, creditos, descricao, log_callback=None):
        """Debita créditos imediatamente - usado antes de executar operações"""
        try:
            # Converter para int/float para comparação correta
            creditos_int = int(float(creditos))
            
            # Consultar saldo diretamente (já valida conexão online)
            # Não fazer verificação extra de conectividade para economizar tempo
            sucesso_saldo, saldo_atual = self._cons_sal(log_callback, force_refresh=False)  # Usar cache se disponível
            
            if not sucesso_saldo:
                return False, "Erro ao consultar saldo"
            
            # Converter para float para comparação correta
            saldo_atual_float = float(saldo_atual)
            
            # Verificar se há créditos suficientes
            if saldo_atual_float < creditos_int:
                return False, _get_obf_str("credit")
            
            # Tentar débito online imediatamente (sem delay)
            sucesso_debito, mensagem_debito = self._conf_cons(creditos_int, descricao, log_callback)
            if sucesso_debito:
                # Atualizar cache offline com novo saldo (apenas para exibição)
                self.salvar_cache_offline(self._sa, log_callback)
                return True, "Débito online realizado"
            else:
                return False, f"Falha ao debitar créditos online: {mensagem_debito}"
                
        except Exception as e:
            print(f"❌ Erro ao debitar créditos: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Erro: {str(e)}"

    def reservar_creditos(self, creditos, descricao, log_callback=None):
        """Reserva créditos com suporte a modo offline"""
        try:
            # Tentar reserva online primeiro
            if self.verificar_conectividade():
                sucesso, saldo = self._cons_sal(log_callback, force_refresh=True)
                if sucesso and float(saldo) >= creditos:
                    self.creditos_reservados += creditos
                    # Salvar cache atualizado
                    self.salvar_cache_offline(saldo, log_callback)
                    
                    if log_callback:
                        log_callback(_get_obf_str("credit"))
                    
                    return True, f"reserva_online_{int(time.time())}"
            
            # Modo offline - usar cache
            if log_callback:
                log_callback("📱 Modo offline ativado para reserva...")
            
            sucesso_cache, saldo_cache, mensagem = self.carregar_cache_offline(log_callback)
            if sucesso_cache and float(saldo_cache) >= creditos:
                self.creditos_reservados += creditos
                
                if log_callback:
                    log_callback(_get_obf_str("credit"))
                
                return True, f"reserva_offline_{int(time.time())}"
            else:
                error_msg = _get_obf_str("credit")
                if log_callback:
                    log_callback(f"❌ {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Erro ao reservar créditos: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False, error_msg
    
    def confirmar_debito_creditos(self, id_transacao, log_callback=None):
        """Confirma débito de créditos com suporte a modo offline"""
        try:
            creditos = self.creditos_reservados
            
            if self.verificar_conectividade():
                # Modo online - débito imediato
                if log_callback:
                    log_callback("🌐 Confirmando débito online...")
                
                sucesso, mensagem = self._conf_cons(creditos, f"Transação {id_transacao}", log_callback)
                if sucesso:
                    self.creditos_reservados = max(0, self.creditos_reservados - creditos)
                    return True
                else:
                    if log_callback:
                        log_callback(f"❌ Falha no débito online: {mensagem}")
                    return False
            else:
                # Modo offline - salvar para sincronização posterior
                if log_callback:
                    log_callback("📱 Salvando transação para sincronização offline...")
                
                sucesso, transacao_id = self.salvar_transacao_offline(
                    creditos, 
                    f"Transação {id_transacao}", 
                    log_callback
                )
                
                if sucesso:
                    self.creditos_reservados = max(0, self.creditos_reservados - creditos)
                    # Atualizar cache local subtraindo os créditos
                    sucesso_cache, saldo_cache, _ = self.carregar_cache_offline()
                    if sucesso_cache:
                        novo_saldo = max(0, saldo_cache - creditos)
                        self.salvar_cache_offline(novo_saldo, log_callback)
                    
                    return True
                else:
                    return False
                    
        except Exception as e:
            error_msg = f"Erro ao confirmar débito: {str(e)}"
            if log_callback:
                log_callback(f"❌ {error_msg}")
            return False
    
    def liberar_creditos_reservados(self, id_transacao, log_callback=None):
        """Libera créditos reservados (compatibilidade com versão anterior)"""
        try:
            creditos_liberados = self.creditos_reservados
            self.creditos_reservados = 0
            
            if log_callback:
                log_callback(_get_obf_str("credit"))
            
            return True
            
        except Exception as e:
            if log_callback:
                log_callback(f"❌ Erro ao liberar créditos: {str(e)}")
            return False

# Função de conveniência para criar um CreditManager
def criar_gerenciador_creditos():
    """Cria um gerenciador de créditos carregando as configurações salvas"""
    user_id, api_key = carregar_config_usuario()
    if user_id and api_key:
        return _CM(user_id, api_key)
    return None

# Variável global para cache do gerenciador (singleton pattern)
_global_credit_manager = None

def obter_gerenciador_creditos():
    """Obtém o gerenciador de créditos global (singleton)"""
    global _global_credit_manager
    if _global_credit_manager is None:
        _global_credit_manager = criar_gerenciador_creditos()
    return _global_credit_manager

def definir_gerenciador_creditos(credit_manager):
    """Define o gerenciador de créditos global"""
    global _global_credit_manager
    _global_credit_manager = credit_manager