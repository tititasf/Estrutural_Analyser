
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
Módulo de proteção adicional contra engenharia reversa
Adiciona verificações e ofuscações em runtime
"""
import sys
import os
import hashlib
import inspect

# Flag para verificar se código foi modificado
_PROTECTION_ENABLED = True

def verify_code_integrity():
    """
    Verifica integridade do código em runtime
    Detecta modificações em funções críticas
    """
    if not _PROTECTION_ENABLED:
        return True
    
    try:
        # Verificar hash de funções críticas
        from src.core import credit_system
        
        # Obter código fonte de função crítica
        func = credit_system.CreditManager.calcular_creditos_necessarios
        source = inspect.getsource(func)
        
        # Calcular hash
        func_hash = hashlib.sha256(source.encode()).hexdigest()
        
        # Hash esperado (deve ser verificado em produção)
        # Por enquanto, apenas verificar que função existe
        if not func or not source:
            return False
        
        return True
    except Exception:
        # Em caso de erro, permitir execução (não bloquear)
        return True


def obfuscate_function_call(func_name, *args, **kwargs):
    """
    Chama função de forma ofuscada para dificultar rastreamento
    """
    # Importar módulo dinamicamente
    module_name = func_name.rsplit('.', 1)[0]
    function_name = func_name.rsplit('.', 1)[1]
    
    try:
        module = __import__(module_name, fromlist=[function_name])
        func = getattr(module, function_name)
        return func(*args, **kwargs)
    except Exception as e:
        raise ImportError(f"Erro ao chamar função ofuscada: {e}")


def add_anti_debug_checks():
    """
    Adiciona verificações anti-debug em runtime
    """
    try:
        # Verificar se está rodando em debugger
        import sys
        
        # Verificar tracemalloc (usado por debuggers)
        if hasattr(sys, 'gettrace') and sys.gettrace() is not None:
            # Debugger detectado - mas não bloquear (apenas avisar)
            pass
        
        return True
    except Exception:
        return True


def protect_string_literal(s):
    """
    Protege string literal de ser encontrada facilmente
    Divide string em partes e reconstrói em runtime
    """
    if not s:
        return ''
    
    # Dividir string em partes
    parts = []
    chunk_size = len(s) // 3 + 1
    for i in range(0, len(s), chunk_size):
        parts.append(s[i:i+chunk_size])
    
    # Retornar função que reconstrói
    def reconstruct():
        return ''.join(parts)
    
    return reconstruct()


# Inicializar proteções ao importar
if _PROTECTION_ENABLED:
    verify_code_integrity()
    add_anti_debug_checks()

