
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
Helper para garantir paths frozen em QUALQUER módulo.
Use no início de QUALQUER arquivo Python.
"""
import os
import sys

_FROZEN_PATHS_ENSURED = False

def ensure():
    """Garante que sys.path está configurado - seguro chamar múltiplas vezes"""
    global _FROZEN_PATHS_ENSURED
    
    if _FROZEN_PATHS_ENSURED or getattr(sys, '_PILAR_FROZEN_PATHS_ENSURED', False):
        return
    
    sys._PILAR_FROZEN_PATHS_ENSURED = True
    _FROZEN_PATHS_ENSURED = True
    
    is_frozen = getattr(sys, 'frozen', False)
    
    if is_frozen:
        script_dir = os.path.dirname(sys.executable)
        paths_to_add = []
        
        if script_dir not in sys.path:
            paths_to_add.append(script_dir)
        
        src_dir = os.path.join(script_dir, 'src')
        if os.path.exists(src_dir) and src_dir not in sys.path:
            paths_to_add.append(src_dir)
        
        parent_dir = os.path.dirname(script_dir)
        if parent_dir and parent_dir not in sys.path:
            paths_to_add.append(parent_dir)
        
        if parent_dir:
            parent_src = os.path.join(parent_dir, 'src')
            if os.path.exists(parent_src) and parent_src not in sys.path:
                paths_to_add.append(parent_src)
        
        for path in paths_to_add:
            if path not in sys.path:
                sys.path.insert(0, path)
    else:
        # Dev mode - garantir que src está no path
        try:
            current_file = os.path.abspath(__file__)
            src_dir = os.path.dirname(current_file)
            project_root = os.path.dirname(src_dir)
            
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
        except:
            pass

# Executar automaticamente
ensure()

