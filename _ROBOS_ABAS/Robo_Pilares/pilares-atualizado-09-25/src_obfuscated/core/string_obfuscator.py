
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
Módulo de ofuscação avançada de strings para proteção contra extração
Usa múltiplas camadas de ofuscação e criptografia
"""
import base64
import hashlib
import os
import sys

# Chave baseada em HWID para ofuscação
def _get_obfuscation_key():
    """Gera chave de ofuscação baseada em HWID"""
    try:
        import platform
        import uuid
        
        # Obter identificadores únicos do sistema
        hwid_parts = [
            platform.machine(),
            platform.processor(),
            str(uuid.getnode()),
            platform.system(),
        ]
        hwid = ''.join(hwid_parts)
        
        # Gerar hash SHA256
        key = hashlib.sha256(hwid.encode()).digest()[:16]
        return key
    except Exception:
        # Fallback: usar chave fixa (menos seguro, mas funciona)
        return b'default_key_12345'


def obfuscate_string_advanced(s):
    """
    Ofusca string com múltiplas camadas para dificultar extração
    
    Camadas:
    1. Base64 encoding
    2. XOR com chave baseada em HWID
    3. Reversão
    4. Adição de ruído
    
    Args:
        s: String a ofuscar
        
    Returns:
        bytes: String ofuscada como bytes
    """
    if not s:
        return b''
    
    try:
        # Camada 1: Base64
        encoded = base64.b64encode(s.encode('utf-8'))
        
        # Camada 2: XOR com chave
        key = _get_obfuscation_key()
        xored = bytes(a ^ b for a, b in zip(encoded, key * (len(encoded) // len(key) + 1)))
        
        # Camada 3: Reversão
        reversed_bytes = xored[::-1]
        
        # Camada 4: Adicionar ruído (prefixo e sufixo aleatórios)
        noise_pre = b'\x42\x4f\x42'  # "BOB" em hex
        noise_suf = b'\x41\x4c\x49\x43\x45'  # "ALICE" em hex
        
        result = noise_pre + reversed_bytes + noise_suf
        
        # Camada 5: Base64 final (para facilitar armazenamento)
        final = base64.b64encode(result)
        
        return final
    except Exception:
        # Fallback: ofuscação simples
        return base64.b64encode(s.encode('utf-8'))


def deobfuscate_string_advanced(obfuscated):
    """
    Remove ofuscação de string
    
    Args:
        obfuscated: String ofuscada (bytes ou str)
        
    Returns:
        str: String original
    """
    if not obfuscated:
        return ''
    
    try:
        # Converter para bytes se necessário
        if isinstance(obfuscated, str):
            obfuscated = obfuscated.encode('utf-8')
        
        # Camada 5: Remover Base64 final
        decoded = base64.b64decode(obfuscated)
        
        # Camada 4: Remover ruído
        if decoded.startswith(b'\x42\x4f\x42') and decoded.endswith(b'\x41\x4c\x49\x43\x45'):
            decoded = decoded[3:-5]
        
        # Camada 3: Reverter reversão
        reversed_bytes = decoded[::-1]
        
        # Camada 2: Remover XOR
        key = _get_obfuscation_key()
        xored = bytes(a ^ b for a, b in zip(reversed_bytes, key * (len(reversed_bytes) // len(key) + 1)))
        
        # Camada 1: Remover Base64
        original = base64.b64decode(xored).decode('utf-8')
        
        return original
    except Exception:
        # Fallback: tentar decodificar como base64 simples
        try:
            if isinstance(obfuscated, bytes):
                return base64.b64decode(obfuscated).decode('utf-8')
            return obfuscated
        except Exception:
            return str(obfuscated)


def obfuscate_constant(name, value):
    """
    Ofusca uma constante e retorna código Python ofuscado
    
    Args:
        name: Nome da variável
        value: Valor da constante
        
    Returns:
        str: Código Python ofuscado
    """
    obfuscated = obfuscate_string_advanced(value)
    # Converter bytes para representação segura
    obf_bytes_repr = obfuscated.hex()
    
    # Retornar código que ofusca o nome também
    obf_name = ''.join(chr(ord(c) + 1) if c.isalpha() else c for c in name)
    
    code = f"""
# Ofuscado
import base64
_{obf_name}_data = bytes.fromhex('{obf_bytes_repr}')
def _{obf_name}_decrypt():
    from src.core.string_obfuscator import deobfuscate_string_advanced
    return deobfuscate_string_advanced(_{obf_name}_data)
{name} = _{obf_name}_decrypt()
"""
    return code


# Strings pré-ofuscadas para uso comum
_OBFUSCATED_STRINGS = {
    _get_obf_str("credit"): obfuscate_string_advanced(_get_obf_str("credit")),
    _get_obf_str("saldo"): obfuscate_string_advanced(_get_obf_str("saldo")),
    _get_obf_str("consumo"): obfuscate_string_advanced(_get_obf_str("consumo")),
    _get_obf_str("api_key"): obfuscate_string_advanced(_get_obf_str("api_key")),
    _get_obf_str("user_id"): obfuscate_string_advanced(_get_obf_str("user_id")),
}


def get_obfuscated_string(key):
    """Retorna string ofuscada pré-computada"""
    return _OBFUSCATED_STRINGS.get(key, obfuscate_string_advanced(key))

