"""
Teste completo de geração de scripts via ambas interfaces
"""

import os
import sys

# Configurar encoding
if sys.platform == 'win32':
    import io
    try:
        if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except:
        pass

# Adicionar paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
for _ in range(3):
    parent = os.path.dirname(project_root)
    if os.path.exists(os.path.join(parent, "main.py")):
        project_root = parent
        break
    project_root = parent

pilares_dir = os.path.join(project_root, "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25")
if pilares_dir not in sys.path:
    sys.path.insert(0, pilares_dir)

src_dir = os.path.join(pilares_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

def testar_mapeamento():
    """Testa o mapeamento PilarModel -> dict"""
    print("[INFO] Testando mapeamento de dados...")
    
    try:
        from models.pilar_model import PilarModel
        from services.automation_service import AutomationOrchestratorService
        
        # Criar pilar de teste
        pilar = PilarModel(
            numero="16A",
            nome="P16A",
            comprimento=20.0,
            largura=40.0,
            pavimento="Subsolo",
            altura=300.0
        )
        
        # Criar service
        service = AutomationOrchestratorService(project_root)
        
        # Testar mapeamento
        dict_result = service._pilar_model_to_legacy_dict(pilar, "Subsolo")
        
        print(f"[INFO] Nome no dict: {dict_result.get('nome')}")
        print(f"[INFO] Numero no dict: {dict_result.get('numero')}")
        
        # Verificar se nome está correto
        if dict_result.get('nome') == "P16A":
            print("[OK] Nome mapeado corretamente")
            return True
        else:
            print(f"[ERRO] Nome incorreto: esperado 'P16A', obtido '{dict_result.get('nome')}'")
            return False
            
    except Exception as e:
        print(f"[ERRO] Erro ao testar mapeamento: {e}")
        import traceback
        traceback.print_exc()
        return False

def verificar_geradores():
    """Verifica se os geradores estão disponíveis"""
    print("[INFO] Verificando geradores...")
    
    try:
        from services.automation_service import AutomationOrchestratorService
        
        service = AutomationOrchestratorService(project_root)
        
        geradores = {
            "CIMA": service._get_legacy_generator("CIMA_FUNCIONAL_EXCEL", "preencher_campos_diretamente_e_gerar_scripts"),
            "ABCD": service._get_legacy_generator("Abcd_Excel", "preencher_campos_diretamente_e_gerar_scripts"),
            "GRADES": service._get_legacy_generator("GRADE_EXCEL", "preencher_campos_diretamente_e_gerar_scripts")
        }
        
        todos_ok = True
        for tipo, gen in geradores.items():
            if gen:
                print(f"[OK] Gerador {tipo} disponível")
            else:
                print(f"[ERRO] Gerador {tipo} não encontrado")
                todos_ok = False
        
        return todos_ok
        
    except Exception as e:
        print(f"[ERRO] Erro ao verificar geradores: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*70)
    print("TESTE COMPLETO DE GERACAO")
    print("="*70)
    print()
    
    sucesso = True
    
    # 1. Testar mapeamento
    if not testar_mapeamento():
        sucesso = False
    
    print()
    
    # 2. Verificar geradores
    if not verificar_geradores():
        sucesso = False
    
    print()
    print("="*70)
    if sucesso:
        print("[OK] TODOS OS TESTES PASSARAM!")
    else:
        print("[AVISO] Alguns testes falharam")
    print("="*70)
    
    return 0 if sucesso else 1

if __name__ == "__main__":
    sys.exit(main())
