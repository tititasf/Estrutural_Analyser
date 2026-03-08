
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
📁 Configuração de Paths - PilarAnalyzer
========================================================
📆 Data: 23/07/2025
✏️ Autor: Kiro AI

📋 Descrição:
Centraliza todos os caminhos e configurações de diretórios
para facilitar a manutenção após reorganização.
"""

import os
import sys

# Diretório raiz do projeto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Diretórios principais
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
CONFIG_DIR = os.path.join(PROJECT_ROOT, 'config')
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, 'templates')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')

# Subdiretórios do src
CORE_DIR = os.path.join(SRC_DIR, 'core')
ROBOTS_DIR = os.path.join(SRC_DIR, 'robots')
UTILS_DIR = os.path.join(SRC_DIR, 'utils')
INTERFACES_DIR = os.path.join(SRC_DIR, 'interfaces')

# Adicionar todos os diretórios ao path do Python
def setup_paths():
    """Adiciona todos os diretórios necessários ao sys.path"""
    paths_to_add = [
        PROJECT_ROOT,
        SRC_DIR,
        CORE_DIR,
        ROBOTS_DIR,
        UTILS_DIR,
        INTERFACES_DIR
    ]
    
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.append(path)

# Configurações de arquivos específicos
CONFIG_FILES = {
    'abcd': os.path.join(CONFIG_DIR, 'config_abcd.json'),
    'cima': os.path.join(CONFIG_DIR, 'config_cima.json'),
    'grades': os.path.join(CONFIG_DIR, 'config_grades.json'),
    'ordenador_abcd': os.path.join(CONFIG_DIR, 'configuracao_ordenador_ABCD.json'),
    'ordenador_cima': os.path.join(CONFIG_DIR, 'configuracao_ordenador_CIMA.json'),
    'ordenador_grades': os.path.join(CONFIG_DIR, 'configuracao_ordenador_GRADES.json'),
}

# Templates
TEMPLATE_FILES = {
    'abcd': os.path.join(TEMPLATES_DIR, 'templates_configuracao_ordenador_ABCD'),
    'cima': os.path.join(TEMPLATES_DIR, 'templates_configuracao_ordenador_CIMA'),
    'grades': os.path.join(TEMPLATES_DIR, 'templates_configuracao_ordenador_GRADES'),
}

# Logs
LOG_FILES = {
    'main': os.path.join(LOGS_DIR, 'pilares.log'),
    _get_obf_str("credit"): os.path.join(LOGS_DIR, 'credit_system.log'),
    'robots': os.path.join(LOGS_DIR, 'robots.log'),
}

# Executar setup automaticamente quando importado
setup_paths()