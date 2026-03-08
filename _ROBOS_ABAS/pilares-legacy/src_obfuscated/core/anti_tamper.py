
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
🔒 Módulo: Anti-Tampering - PilarAnalyzer
========================================================

Funcionalidade: Detecção de modificações e debuggers
Data: 13/11/2025
Autor: Sistema de Segurança

Funcionalidades:
- Detecção de debuggers
- Detecção de ambientes virtualizados
- Verificação de integridade em memória
- Detecção de patches em runtime
"""

import os
import sys
import platform
import ctypes
from ctypes import wintypes


def detect_debugger():
    """
    Detecta se um debugger está anexado ao processo
    
    Returns:
        tuple: (is_debugger_present: bool, debugger_name: str)
    """
    try:
        if platform.system() != "Windows":
            return False, ""
        
        # Verificar se debugger está presente usando Windows API
        kernel32 = ctypes.windll.kernel32
        
        # CheckRemoteDebuggerPresent
        debugger_present = ctypes.c_bool()
        if kernel32.CheckRemoteDebuggerPresent(
            kernel32.GetCurrentProcess(),
            ctypes.byref(debugger_present)
        ):
            if debugger_present.value:
                return True, "Remote Debugger"
        
        # IsDebuggerPresent
        if kernel32.IsDebuggerPresent():
            return True, "Local Debugger"
        
        # Verificar processos comuns de debug
        debugger_processes = [
            "ollydbg.exe",
            "x64dbg.exe",
            "x32dbg.exe",
            "windbg.exe",
            "ida.exe",
            "ida64.exe",
            "idaq.exe",
            "idaq64.exe",
            "ghidra.exe",
            "devenv.exe",  # Visual Studio
            "wireshark.exe",
            "fiddler.exe",
            "procmon.exe",
            "processhacker.exe"
        ]
        
        try:
            import subprocess
            result = subprocess.run(
                ['tasklist', '/FO', 'CSV'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output_lower = result.stdout.lower()
                for debugger in debugger_processes:
                    if debugger.lower() in output_lower:
                        return True, debugger
        except Exception:
            pass
        
        return False, ""
        
    except Exception:
        # Em caso de erro, assumir que não há debugger (evitar falsos positivos)
        return False, ""


def detect_vm():
    """
    Detecta se está sendo executado em ambiente virtualizado
    
    Returns:
        tuple: (is_vm: bool, vm_name: str)
    """
    try:
        if platform.system() != "Windows":
            return False, ""
        
        # Verificar modelo do computador
        try:
            import subprocess
            result = subprocess.run(
                ['wmic', 'computersystem', 'get', 'model'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                model = result.stdout.lower()
                vm_indicators = {
                    'virtualbox': 'VirtualBox',
                    'vmware': 'VMware',
                    'vbox': 'VirtualBox',
                    'qemu': 'QEMU',
                    'xen': 'Xen',
                    'hyper-v': 'Hyper-V',
                    'parallels': 'Parallels',
                    'virtual': 'Virtual Machine'
                }
                
                for indicator, name in vm_indicators.items():
                    if indicator in model:
                        return True, name
        except Exception:
            pass
        
        # Verificar MAC address (VMs têm MACs específicos)
        try:
            import uuid
            mac = uuid.getnode()
            mac_str = ':'.join(['{:02x}'.format((mac >> elements) & 0xff) 
                               for elements in range(0, 2*6, 8)][::-1])
            
            # MACs conhecidos de VMs
            vm_mac_prefixes = [
                '08:00:27',  # VirtualBox
                '00:0c:29',  # VMware
                '00:1c:14',  # VMware
                '00:50:56',  # VMware
                '00:05:69',  # Xen
            ]
            
            for prefix in vm_mac_prefixes:
                if mac_str.lower().startswith(prefix.lower()):
                    return True, "VM (detectado por MAC)"
        except Exception:
            pass
        
        return False, ""
        
    except Exception:
        return False, ""


def verify_critical_functions():
    """
    Verifica integridade de funções críticas em memória
    (Implementação básica - pode ser expandida)
    
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    try:
        # Verificar se funções críticas do sistema de créditos existem
        from src.core import credit_system
        
        critical_functions = [
            _get_obf_str("CreditManager"),
            _get_obf_str("confirmar_consumo"),
            'calcular_creditos_necessarios',
            'debitar_creditos_imediato'
        ]
        
        missing = []
        for func_name in critical_functions:
            if func_name == _get_obf_str("CreditManager"):
                if not hasattr(credit_system, func_name):
                    missing.append(func_name)
            else:
                if not hasattr(credit_system._CM, func_name):
                    missing.append(func_name)
        
        if missing:
            return False, f"Funções críticas ausentes: {', '.join(missing)}"
        
        return True, "Funções críticas verificadas"
        
    except Exception as e:
        return False, f"Erro ao verificar funções: {e}"


def check_runtime_modifications():
    """
    Verifica se houve modificações em runtime
    (Implementação básica - pode ser expandida)
    
    Returns:
        tuple: (is_clean: bool, message: str)
    """
    try:
        # Verificar se módulos críticos foram modificados
        import importlib
        
        critical_modules = [
            'src.core.credit_system',
            'src.core.security_utils'
        ]
        
        for module_name in critical_modules:
            try:
                module = sys.modules.get(module_name)
                if module:
                    # Verificar se arquivo do módulo ainda existe e não foi modificado
                    if hasattr(module, '__file__') and module.__file__:
                        if not os.path.exists(module.__file__):
                            return False, f"Módulo {module_name} foi removido"
            except Exception:
                pass
        
        return True, "Nenhuma modificação em runtime detectada"
        
    except Exception as e:
        return True, f"Verificação de runtime não disponível: {e}"


def _sec_chk(strict_mode=True):
    """
    Realiza todas as verificações de segurança
    
    Args:
        strict_mode: Se True, bloqueia se problemas forem detectados
        
    Returns:
        tuple: (is_secure: bool, issues: list, warnings: list)
    """
    issues = []
    warnings = []
    
    # Verificar debugger
    has_debugger, debugger_name = detect_debugger()
    if has_debugger:
        msg = f"Debugger detectado: {debugger_name}"
        if strict_mode:
            issues.append(msg)
        else:
            warnings.append(msg)
    
    # Verificar VM (apenas aviso, não bloqueia)
    is_vm, vm_name = detect_vm()
    if is_vm:
        warnings.append(f"Ambiente virtualizado detectado: {vm_name}")
    
    # Verificar funções críticas
    funcs_valid, funcs_msg = verify_critical_functions()
    if not funcs_valid:
        if strict_mode:
            issues.append(funcs_msg)
        else:
            warnings.append(funcs_msg)
    
    # Verificar modificações em runtime
    runtime_clean, runtime_msg = check_runtime_modifications()
    if not runtime_clean:
        if strict_mode:
            issues.append(runtime_msg)
        else:
            warnings.append(runtime_msg)
    
    is_secure = len(issues) == 0
    
    return is_secure, issues, warnings

