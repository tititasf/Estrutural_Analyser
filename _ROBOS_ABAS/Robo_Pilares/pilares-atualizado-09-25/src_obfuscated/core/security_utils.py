
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
🔐 Módulo: Utilitários de Segurança - PilarAnalyzer
========================================================

Funcionalidade: Criptografia e utilitários de segurança
Data: 13/11/2025
Autor: Sistema de Segurança

Funcionalidades:
- Criptografia/descriptografia de strings usando AES
- Geração de chaves baseadas em HWID
- Ofuscação básica de strings
"""

import os
import sys
import hashlib
import base64
import platform
import uuid

# Tentar importar cryptography, usar fallback se não disponível
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False


def _get_hw():
    """Gera um identificador único de hardware"""
    try:
        system_info = platform.uname()
        cpu_info = platform.processor()
        
        if platform.system() == "Windows":
            try:
                import winreg
                import subprocess
                
                registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
                
                try:
                    result = subprocess.run(['wmic', 'bios', 'get', 'serialnumber'], 
                                          capture_output=True, text=True, timeout=30)
                    bios_serial = result.stdout.strip().split('\n')[1] if result.returncode == 0 else ""
                except:
                    bios_serial = ""
                
                mac_address = str(uuid.getnode())
                combined_info = f"{system_info.system}_{system_info.node}_{cpu_info}_{machine_guid}_{bios_serial}_{mac_address}"
                
            except Exception:
                machine_guid = str(uuid.getnode())
                combined_info = f"{system_info.system}_{system_info.node}_{cpu_info}_{machine_guid}"
        else:
            machine_guid = str(uuid.getnode())
            combined_info = f"{system_info.system}_{system_info.node}_{cpu_info}_{machine_guid}"
        
        hwid = hashlib.sha256(combined_info.encode()).hexdigest()[:32]
        return hwid
    except Exception:
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:32]


def get_encryption_key():
    """
    Gera uma chave de criptografia baseada no HWID usando PBKDF2
    
    Returns:
        bytes: Chave de 32 bytes para uso com Fernet
    """
    hwid = _get_hw()
    
    if CRYPTOGRAPHY_AVAILABLE:
        # Usar PBKDF2 para derivar chave do HWID
        salt = b'pilar_analyzer_security_salt_v3'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(hwid.encode()))
        return key
    else:
        # Fallback: usar hash simples
        key = hashlib.sha256((hwid + "pilar_security_v3").encode()).digest()[:32]
        return base64.urlsafe_b64encode(key)


def _enc_str(plaintext):
    """
    Criptografa uma string usando AES (Fernet)
    
    Args:
        plaintext: String a ser criptografada
        
    Returns:
        bytes: Dados criptografados em base64
    """
    if not plaintext:
        return b''
    
    try:
        if CRYPTOGRAPHY_AVAILABLE:
            key = get_encryption_key()
            f = Fernet(key)
            encrypted = f.encrypt(plaintext.encode('utf-8'))
            return encrypted
        else:
            # Fallback: XOR simples (não seguro, mas melhor que nada)
            key = _get_hw()[:16]
            encrypted = bytearray()
            for i, char in enumerate(plaintext.encode('utf-8')):
                encrypted.append(char ^ ord(key[i % len(key)]))
            return base64.b64encode(bytes(encrypted))
    except Exception as e:
        print(f"Erro ao criptografar string: {e}")
        return plaintext.encode('utf-8')


def _dec_str(encrypted_data):
    """
    Descriptografa uma string usando AES (Fernet)
    
    Args:
        encrypted_data: Dados criptografados (bytes)
        
    Returns:
        str: String descriptografada
    """
    if not encrypted_data:
        return ''
    
    try:
        if CRYPTOGRAPHY_AVAILABLE:
            key = get_encryption_key()
            f = Fernet(key)
            decrypted = f.decrypt(encrypted_data)
            return decrypted.decode('utf-8')
        else:
            # Fallback: XOR simples
            try:
                encrypted_bytes = base64.b64decode(encrypted_data)
            except:
                encrypted_bytes = encrypted_data
            
            key = _get_hw()[:16]
            decrypted = bytearray()
            for i, byte in enumerate(encrypted_bytes):
                decrypted.append(byte ^ ord(key[i % len(key)]))
            return bytes(decrypted).decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Erro ao descriptografar string: {e}")
        return ''


def _gen_sig(data_dict, secret_key=None):
    """
    Gera assinatura digital para validação de integridade
    
    Args:
        data_dict: Dicionário com dados a assinar
        secret_key: Chave secreta adicional (opcional)
        
    Returns:
        str: Assinatura hexadecimal
    """
    try:
        # Ordenar chaves para garantir consistência
        sorted_items = sorted(data_dict.items())
        data_string = '|'.join(f"{k}:{v}" for k, v in sorted_items)
        
        if secret_key:
            data_string += f"|{secret_key}"
        
        # Adicionar HWID
        hwid = _get_hw()
        data_string += f"|{hwid}"
        
        signature = hashlib.sha256(data_string.encode()).hexdigest()
        return signature
    except Exception as e:
        print(f"Erro ao gerar assinatura: {e}")
        return ''


def _ver_sig(data_dict, signature, secret_key=None):
    """
    Verifica assinatura digital
    
    Args:
        data_dict: Dicionário com dados a verificar
        signature: Assinatura a verificar
        secret_key: Chave secreta adicional (opcional)
        
    Returns:
        bool: True se assinatura é válida
    """
    try:
        expected_signature = _gen_sig(data_dict, secret_key)
        return expected_signature == signature
    except Exception:
        return False


def obfuscate_string(s):
    """
    Ofusca uma string simplesmente (não é criptografia real)
    Útil para dificultar busca de strings no binário
    
    Args:
        s: String a ofuscar
        
    Returns:
        str: String ofuscada
    """
    if not s:
        return ''
    
    # Converter para base64 e adicionar ruído
    encoded = base64.b64encode(s.encode('utf-8')).decode('utf-8')
    # Reverter (ofuscação simples)
    return encoded[::-1]


def deobfuscate_string(s):
    """
    Remove ofuscação de uma string
    
    Args:
        s: String ofuscada
        
    Returns:
        str: String original
    """
    if not s:
        return ''
    
    try:
        # Reverter ofuscação
        encoded = s[::-1]
        decoded = base64.b64decode(encoded).decode('utf-8')
        return decoded
    except Exception:
        return s

