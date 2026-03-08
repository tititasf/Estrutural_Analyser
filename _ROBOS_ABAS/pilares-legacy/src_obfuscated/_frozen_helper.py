
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
🔧 Helper Frozen Global - PilarAnalyzer
========================================================
Helper global que pode ser importado por QUALQUER módulo
em qualquer nível para garantir que sys.path está configurado.
"""

import os
import sys

def ensure_paths():
    """
    Garante que sys.path está configurado corretamente.
    Esta função pode ser chamada por QUALQUER módulo em qualquer nível.
    É seguro chamar múltiplas vezes (idempotente).
    """
    # Flag global para evitar execução múltipla
    if getattr(sys, '_PILAR_PATHS_CONFIGURED', False):
        return
    
    sys._PILAR_PATHS_CONFIGURED = True
    
    # Detectar ambiente frozen
    is_frozen = getattr(sys, 'frozen', False)
    
    if is_frozen:
        # No executável, o diretório base é onde o .exe está
        script_dir = os.path.dirname(sys.executable)
        
        # Adicionar múltiplos paths de fallback
        paths_to_add = []
        
        # 1. Diretório do executável
        if script_dir not in sys.path:
            paths_to_add.append(script_dir)
        
        # 2. Tentar src/ dentro do diretório do exe
        src_dir = os.path.join(script_dir, 'src')
        if os.path.exists(src_dir) and src_dir not in sys.path:
            paths_to_add.append(src_dir)
        
        # 3. Tentar parent (caso estrutura esteja em src/run.dist/)
        parent_dir = os.path.dirname(script_dir)
        if parent_dir and parent_dir not in sys.path:
            paths_to_add.append(parent_dir)
        
        # 4. Tentar src/ no parent
        if parent_dir:
            parent_src = os.path.join(parent_dir, 'src')
            if os.path.exists(parent_src) and parent_src not in sys.path:
                paths_to_add.append(parent_src)
        
        # Adicionar todos os paths encontrados no início
        for path in paths_to_add:
            if path not in sys.path:
                sys.path.insert(0, path)
    else:
        # No desenvolvimento, garantir que src/ está no path
        # Obter diretório deste arquivo
        current_file = os.path.abspath(__file__)
        src_dir = os.path.dirname(current_file)
        project_root = os.path.dirname(src_dir)
        
        paths_to_add = []
        
        # Adicionar src/ se não estiver
        if src_dir not in sys.path:
            paths_to_add.append(src_dir)
        
        # Adicionar project_root se não estiver
        if project_root not in sys.path:
            paths_to_add.append(project_root)
        
        # Adicionar paths
        for path in paths_to_add:
            if path not in sys.path:
                sys.path.insert(0, path)


def safe_import(module_name, from_module=None, fallback_module=None):
    """
    Função helper para fazer imports seguros com múltiplos fallbacks.
    
    Args:
        module_name: Nome do módulo a importar (ex: 'utils.robust_path_resolver')
        from_module: Se especificado, importa de (ex: 'src.utils.robust_path_resolver')
        fallback_module: Módulo de fallback (ex: 'robust_path_resolver')
    
    Returns:
        O módulo importado ou None se falhar
    """
    ensure_paths()  # Garantir que paths estão configurados
    
    # Tentar 1: from_module se especificado
    if from_module:
        try:
            if '.' in from_module:
                parts = from_module.split('.')
                module = __import__(from_module, fromlist=[parts[-1]])
                for part in parts[1:]:
                    module = getattr(module, part)
                return module
            else:
                return __import__(from_module)
        except (ImportError, AttributeError):
            pass
    
    # Tentar 2: module_name principal
    try:
        if '.' in module_name:
            parts = module_name.split('.')
            module = __import__(module_name, fromlist=[parts[-1]])
            for part in parts[1:]:
                module = getattr(module, part)
            return module
        else:
            return __import__(module_name)
    except (ImportError, AttributeError):
        pass
    
    # Tentar 3: fallback_module se especificado
    if fallback_module:
        try:
            if '.' in fallback_module:
                parts = fallback_module.split('.')
                module = __import__(fallback_module, fromlist=[parts[-1]])
                for part in parts[1:]:
                    module = getattr(module, part)
                return module
            else:
                return __import__(fallback_module)
        except (ImportError, AttributeError):
            pass
    
    # Tentar 4: src.* se não estiver tentado
    if not from_module or not from_module.startswith('src.'):
        try:
            src_module_name = f"src.{module_name}"
            if '.' in src_module_name:
                parts = src_module_name.split('.')
                module = __import__(src_module_name, fromlist=[parts[-1]])
                for part in parts[1:]:
                    module = getattr(module, part)
                return module
            else:
                return __import__(src_module_name)
        except (ImportError, AttributeError):
            pass
    
    return None


# Executar automaticamente ao importar
ensure_paths()

