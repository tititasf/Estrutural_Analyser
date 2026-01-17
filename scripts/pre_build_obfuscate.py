"""
Script de pré-processamento para ofuscar código antes do build PyInstaller
Executa ofuscação de strings e nomes críticos
"""
import os
import re
import sys
import shutil
from pathlib import Path

# Diretório do projeto
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
OBFUSCATED_DIR = PROJECT_ROOT / "src_obfuscated"

# Strings sensíveis para ofuscar (EXPANDIDO)
SENSITIVE_STRINGS = [
    "script.google.com",
    "macros/s/",
    "AKfycbz",
    "credit",
    "saldo",
    "consumo",
    "api_key",
    "user_id",
    "calcular_creditos",
    "confirmar_consumo",
    "consultar_saldo",
    "debitar_creditos",
    "CreditManager",
    "obter_hwid",
    "generate_signature",
    "encrypt_string",
    "decrypt_string",
    "integrity_check",
    "security_utils",
    "https://",
    "google.com",
    "apps.script",
]

# Nomes de funções/variáveis para renomear (ofuscar) - EXPANDIDO
FUNCTION_RENAMES = {
    "calcular_creditos_necessarios": "_calc_cr_nec",
    "confirmar_consumo": "_conf_cons",
    "consultar_saldo": "_cons_sal",
    "debitar_creditos_imediato": "_deb_cr_imm",
    "APPS_SCRIPT_URL": "_ASU",
    "user_id": "_uid",
    "api_key": "_ak",
    "saldo_atual": "_sa",
    "CreditManager": "_CM",
    "obter_hwid": "_get_hw",
    "generate_signature": "_gen_sig",
    "verify_signature": "_ver_sig",
    "encrypt_string": "_enc_str",
    "decrypt_string": "_dec_str",
    "verify_executable_integrity": "_ver_int",
    "perform_security_check": "_sec_chk",
}

def obfuscate_string_in_code(content, string_to_obfuscate):
    """Ofusca uma string específica no código"""
    # Padrão para encontrar strings
    patterns = [
        rf'"{re.escape(string_to_obfuscate)}"',
        rf"'{re.escape(string_to_obfuscate)}'",
        rf'f"([^"]*{re.escape(string_to_obfuscate)}[^"]*)"',
        rf"f'([^']*{re.escape(string_to_obfuscate)}[^']*)'",
    ]
    
    for pattern in patterns:
        # Substituir por chamada de função ofuscada
        replacement = f'_get_obf_str("{string_to_obfuscate}")'
        content = re.sub(pattern, replacement, content)
    
    return content

def obfuscate_function_names(content):
    """Ofusca nomes de funções críticas"""
    for original, obfuscated in FUNCTION_RENAMES.items():
        # Substituir definições de função
        content = re.sub(
            rf'\bdef {original}\b',
            f'def {obfuscated}',
            content
        )
        # Substituir chamadas de função
        content = re.sub(
            rf'\b{original}\(',
            f'{obfuscated}(',
            content
        )
        # Substituir atributos
        content = re.sub(
            rf'\.{original}\b',
            f'.{obfuscated}',
            content
        )
    
    return content

def add_obfuscation_helper(content):
    """Adiciona função helper de ofuscação no início do arquivo"""
    helper = '''
# Helper de ofuscação (adicionado automaticamente)
def _get_obf_str(key):
    """Retorna string ofuscada"""
    _obf_map = {
'''
    
    # Adicionar mapeamento de strings ofuscadas
    for s in SENSITIVE_STRINGS:
        # Ofuscação simples: base64 + reversão
        import base64
        obf = base64.b64encode(s.encode()).decode()[::-1]
        helper += f'        "{s}": base64.b64decode("{obf}"[::-1].encode()).decode(),\n'
    
    helper += '''    }
    return _obf_map.get(key, key)
'''
    
    # Inserir após imports
    import_match = re.search(r'(^import |^from )', content, re.MULTILINE)
    if import_match:
        insert_pos = content.rfind('\n', 0, import_match.end()) + 1
        # Encontrar fim dos imports
        lines = content[:insert_pos].split('\n')
        last_import = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                last_import = i
        
        if last_import > 0:
            lines.insert(last_import + 1, helper)
            content = '\n'.join(lines) + content[insert_pos:]
        else:
            content = helper + '\n' + content
    else:
        content = helper + '\n' + content
    
    return content

def process_file(file_path, output_dir):
    """Processa um arquivo Python para ofuscação"""
    print(f"Processando: {file_path.relative_to(PROJECT_ROOT)}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Aplicar ofuscações
    original_content = content
    
    # 1. Adicionar helper de ofuscação
    content = add_obfuscation_helper(content)
    
    # 2. Ofuscar strings sensíveis
    for sensitive_str in SENSITIVE_STRINGS:
        content = obfuscate_string_in_code(content, sensitive_str)
    
    # 3. Ofuscar nomes de funções (em arquivos críticos)
    critical_files = ['credit_system', 'security_utils', 'integrity_check', 'anti_tamper']
    if any(cf in str(file_path) for cf in critical_files):
        content = obfuscate_function_names(content)
    
    # Criar diretório de saída
    rel_path = file_path.relative_to(SRC_DIR)
    output_path = output_dir / rel_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Salvar arquivo ofuscado
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return content != original_content

def main():
    """Função principal"""
    print("=" * 60)
    print("PRÉ-PROCESSAMENTO: Ofuscação de Código")
    print("=" * 60)
    print()
    
    # Limpar diretório de ofuscação anterior
    if OBFUSCATED_DIR.exists():
        print(f"Removendo diretório anterior: {OBFUSCATED_DIR}")
        shutil.rmtree(OBFUSCATED_DIR)
    
    # Criar diretório de ofuscação
    OBFUSCATED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Processar arquivos Python
    python_files = list(SRC_DIR.rglob("*.py"))
    processed = 0
    
    for py_file in python_files:
        if process_file(py_file, OBFUSCATED_DIR):
            processed += 1
    
    print()
    print(f"Processados: {processed}/{len(python_files)} arquivos")
    print(f"Arquivos ofuscados salvos em: {OBFUSCATED_DIR}")
    print()
    print("=" * 60)
    print("PRÉ-PROCESSAMENTO CONCLUÍDO")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

