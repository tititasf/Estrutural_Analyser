"""
Script para corrigir o mapeamento de dados e garantir scripts idênticos
"""

import os
import sys

# Configurar encoding
if sys.platform == 'win32':
    import io
    try:
        if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

# Adicionar paths
current_dir = os.path.dirname(os.path.abspath(__file__))
pilares_dir = os.path.join(current_dir, "pilares-atualizado-09-25")
if pilares_dir not in sys.path:
    sys.path.insert(0, pilares_dir)

src_dir = os.path.join(pilares_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

def corrigir_automation_service():
    """Corrige o mapeamento em automation_service.py"""
    print("[INFO] Corrigindo mapeamento de dados...")
    
    file_path = os.path.join(src_dir, "services", "automation_service.py")
    
    if not os.path.exists(file_path):
        print(f"[ERRO] Arquivo não encontrado: {file_path}")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar se já foi corrigido
    if "'numero': pilar.numero" in content:
        print("[OK] Mapeamento já inclui campo 'numero'")
        return True
    
    # Procurar a linha onde adicionar o campo numero
    old_pattern = "            'nome': pilar.nome,"
    new_pattern = """            'nome': nome_final,
            'numero': pilar.numero,  # ADICIONAR campo numero"""
    
    if old_pattern in content:
        # Adicionar lógica de nome antes do data dict
        nome_logic = """        # Garantir que nome está no formato correto
        # Se nome está vazio ou é só número, usar formato completo
        nome_final = pilar.nome
        if not nome_final or nome_final.strip() == "" or nome_final == pilar.numero:
            # Se nome está vazio ou igual ao número, construir nome completo
            if pilar.numero and pilar.numero != "0":
                nome_final = f"P{pilar.numero}" if not pilar.nome.startswith("P") else pilar.nome
            else:
                nome_final = pilar.nome if pilar.nome else "P?"
        
        data = {"""
        
        # Substituir
        content = content.replace("        data = {", nome_logic)
        content = content.replace(old_pattern, new_pattern)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("[OK] Mapeamento corrigido com sucesso!")
        return True
    else:
        print("[AVISO] Padrão não encontrado. Verificando estrutura...")
        return False

def verificar_diretorio_saida():
    """Verifica se o diretório de saída está correto"""
    print("[INFO] Verificando diretório de saída...")
    
    file_path = os.path.join(src_dir, "services", "automation_service.py")
    
    if not os.path.exists(file_path):
        print(f"[ERRO] Arquivo não encontrado: {file_path}")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar se scripts_dir está correto
    if "self.scripts_dir = os.path.join(project_root, \"SCRIPTS_ROBOS\")" in content:
        print("[OK] Diretório de saída está correto (SCRIPTS_ROBOS)")
        return True
    else:
        print("[AVISO] Verificar diretório de saída")
        return False

def main():
    print("="*70)
    print("CORRECAO DE MAPEAMENTO DE DADOS")
    print("="*70)
    print()
    
    sucesso = True
    
    # 1. Corrigir mapeamento
    if not corrigir_automation_service():
        sucesso = False
    
    # 2. Verificar diretório
    if not verificar_diretorio_saida():
        sucesso = False
    
    print()
    print("="*70)
    if sucesso:
        print("[OK] CORRECOES APLICADAS COM SUCESSO!")
    else:
        print("[AVISO] Algumas verificacoes falharam")
    print("="*70)
    
    return 0 if sucesso else 1

if __name__ == "__main__":
    sys.exit(main())
