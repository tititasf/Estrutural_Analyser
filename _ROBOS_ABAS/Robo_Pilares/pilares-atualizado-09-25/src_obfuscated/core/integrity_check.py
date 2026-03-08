
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
🛡️ Módulo: Validação de Integridade - PilarAnalyzer
========================================================

Funcionalidade: Verificação de integridade do executável
Data: 13/11/2025
Autor: Sistema de Segurança

Funcionalidades:
- Cálculo de checksum SHA256 do executável
- Verificação de modificação do arquivo
- Validação automática na inicialização
"""

import os
import sys
import hashlib
import json
from pathlib import Path


def get_executable_path():
    """
    Retorna o caminho do executável atual
    
    Returns:
        str: Caminho do executável ou script Python
    """
    if getattr(sys, 'frozen', False):
        # Executável compilado (PyInstaller/Nuitka)
        return sys.executable
    else:
        # Script Python em desenvolvimento
        return __file__


def calculate_file_checksum(file_path):
    """
    Calcula o checksum SHA256 de um arquivo
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        str: Hash SHA256 hexadecimal ou None se erro
    """
    try:
        if not os.path.exists(file_path):
            return None
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Ler em chunks para arquivos grandes
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Erro ao calcular checksum: {e}")
        return None


def get_expected_checksum_path():
    """
    Retorna o caminho onde o checksum esperado deve estar armazenado
    
    Returns:
        str: Caminho do arquivo de checksum
    """
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        # Subir para raiz do projeto
        base_path = os.path.dirname(os.path.dirname(base_path))
    
    # Arquivo de checksum em local oculto/ofuscado
    checksum_file = os.path.join(base_path, ".integrity_check")
    return checksum_file


def load_expected_checksum():
    """
    Carrega o checksum esperado do arquivo
    
    Returns:
        str: Checksum esperado ou None se não encontrado
    """
    try:
        checksum_file = get_expected_checksum_path()
        if os.path.exists(checksum_file):
            with open(checksum_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('checksum')
    except Exception:
        pass
    return None


def save_expected_checksum(checksum):
    """
    Salva o checksum esperado em arquivo
    
    Args:
        checksum: Checksum SHA256 a salvar
        
    Returns:
        bool: True se salvou com sucesso
    """
    try:
        checksum_file = get_expected_checksum_path()
        data = {
            'checksum': checksum,
            'version': '3.0.0'
        }
        with open(checksum_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return True
    except Exception as e:
        print(f"Erro ao salvar checksum: {e}")
        return False


def _ver_int(strict_mode=True):
    """
    Verifica a integridade do executável comparando com checksum esperado
    
    Args:
        strict_mode: Se True, bloqueia se integridade falhar. Se False, apenas avisa.
        
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    try:
        exe_path = get_executable_path()
        
        # Calcular checksum atual
        current_checksum = calculate_file_checksum(exe_path)
        if not current_checksum:
            if strict_mode:
                return False, "Não foi possível calcular checksum do executável"
            else:
                return True, "Modo não-strict: continuando sem validação"
        
        # Carregar checksum esperado
        expected_checksum = load_expected_checksum()
        
        if not expected_checksum:
            # Primeira execução ou checksum não configurado
            # Em modo desenvolvimento, permitir
            if not getattr(sys, 'frozen', False):
                return True, "Modo desenvolvimento: checksum não configurado"
            
            # Em modo produção, pode ser suspeito mas não bloquear na primeira vez
            if strict_mode:
                # Salvar checksum atual como esperado (primeira execução)
                save_expected_checksum(current_checksum)
                return True, "Primeira execução: checksum salvo"
            else:
                return True, "Checksum não configurado: continuando"
        
        # Comparar checksums
        if current_checksum == expected_checksum:
            return True, "Integridade verificada com sucesso"
        else:
            message = f"INTEGRIDADE COMPROMETIDA: Executável foi modificado!"
            if strict_mode:
                return False, message
            else:
                return True, f"AVISO: {message} (modo não-strict)"
                
    except Exception as e:
        error_msg = f"Erro ao verificar integridade: {e}"
        if strict_mode:
            return False, error_msg
        else:
            return True, f"AVISO: {error_msg} (modo não-strict)"


def get_file_size(file_path):
    """
    Retorna o tamanho do arquivo em bytes
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        int: Tamanho em bytes ou 0 se erro
    """
    try:
        return os.path.getsize(file_path)
    except Exception:
        return 0


def get_file_modification_time(file_path):
    """
    Retorna o tempo de modificação do arquivo
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        float: Timestamp de modificação ou 0 se erro
    """
    try:
        return os.path.getmtime(file_path)
    except Exception:
        return 0

