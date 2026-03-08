
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
🔧 Inicialização Frozen - PilarAnalyzer
========================================================
Módulo de inicialização que configura sys.path corretamente
para funcionar em ambiente frozen (compilado) e desenvolvimento.
Este módulo deve ser importado ANTES de qualquer outro módulo.
"""
import os
import sys

# Flag para garantir que só executa uma vez
_FROZEN_INIT_DONE = getattr(sys, '_PILAR_FROZEN_INIT_DONE', False)

def ensure_frozen_paths():
    """Configura sys.path corretamente para ambiente frozen e dev"""
    global _FROZEN_INIT_DONE
    
    if _FROZEN_INIT_DONE:
        return
    
    # Marcar como feito no módulo sys para evitar execução múltipla
    sys._PILAR_FROZEN_INIT_DONE = True
    _FROZEN_INIT_DONE = True
    
    # Detectar ambiente frozen
    # Nuitka não define sys.frozen automaticamente, usar detecção alternativa
    is_frozen = getattr(sys, 'frozen', False)
    if not is_frozen:
        # Detecção alternativa para Nuitka: verificar se sys.executable é .exe
        if hasattr(sys, 'executable') and sys.executable and sys.executable.endswith('.exe'):
            exe_dir = os.path.dirname(sys.executable)
            # Nuitka standalone geralmente tem .exe na pasta .dist
            if '.dist' in exe_dir or os.path.basename(exe_dir) in ['run.dist', 'dist', 'dist_nuitka']:
                is_frozen = True
    
    if is_frozen:
        # No executável, o diretório base é onde o .exe está
        script_dir = os.path.dirname(sys.executable)
        
        # No Nuitka standalone, tentar múltiplos paths
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
        if parent_dir not in sys.path:
            paths_to_add.append(parent_dir)
        
        # 4. Tentar src/ no parent
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
        utils_dir = os.path.dirname(current_file)
        src_dir = os.path.dirname(utils_dir)
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

# NOTA: Não executar automaticamente - os módulos devem importar e chamar manualmente
# Isso evita problemas de importação circular e permite controle fino sobre quando executar

