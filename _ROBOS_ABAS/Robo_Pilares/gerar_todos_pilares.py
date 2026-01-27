"""
Gera scripts para TODOS os pilares encontrados no robo_pilares
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

def buscar_pilares_reais(obra_nome, pavimento_nome):
    """Busca pilares reais do banco de dados ou estado do robo_pilares"""
    print(f"[INFO] Buscando pilares reais para obra '{obra_nome}', pavimento '{pavimento_nome}'...")
    
    try:
        # Tentar buscar do banco de dados
        from core.database import Database
        db = Database()
        
        # Buscar projeto
        projects = db.get_projects()
        project = None
        for p in projects:
            if p.get('work_name') == obra_nome and (p.get('pavement_name') or p.get('name')) == pavimento_nome:
                project = p
                break
        
        if not project:
            print(f"[AVISO] Projeto não encontrado no banco")
            return None
        
        project_id = project.get('id')
        print(f"[INFO] Projeto encontrado: ID={project_id}")
        
        # Buscar pilares do projeto
        pillars = db.get_project_items(project_id, item_type='pillar')
        print(f"[INFO] Encontrados {len(pillars)} pilares no banco")
        
        if not pillars:
            return None
        
        # Converter para PilarModel
        from models.pilar_model import PilarModel
        
        pilares_model = []
        for p_data in pillars:
            # Extrair dados
            name = p_data.get('name', 'P?')
            nums = __import__('re').findall(r'\d+', name)
            numero = nums[0] if nums else "0"
            
            # Dimensões
            dim_text = p_data.get('dim', '')
            match = __import__('re').search(r'(\d+)[xX/](\d+)', str(dim_text))
            
            if match:
                v1 = float(match.group(1))
                v2 = float(match.group(2))
                comprimento = max(v1, v2)
                largura = min(v1, v2)
            else:
                comprimento = 20.0
                largura = 40.0
            
            # Criar PilarModel
            pilar = PilarModel(
                numero=numero,
                nome=name,
                comprimento=comprimento,
                largura=largura,
                pavimento=pavimento_nome,
                altura=300.0  # Default
            )
            
            pilares_model.append(pilar)
            print(f"  - {pilar.nome} (numero={pilar.numero})")
        
        return pilares_model
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar pilares: {e}")
        import traceback
        traceback.print_exc()
        return None

def gerar_scripts_completos(obra_nome, pavimento_nome):
    """Gera scripts para todos os pilares"""
    print(f"\n{'='*70}")
    print(f"GERANDO SCRIPTS PARA TODOS OS PILARES")
    print(f"Obra: {obra_nome}, Pavimento: {pavimento_nome}")
    print(f"{'='*70}\n")
    
    # Buscar pilares reais
    pilares = buscar_pilares_reais(obra_nome, pavimento_nome)
    
    if not pilares:
        print(f"[AVISO] Nenhum pilar encontrado. Usando pilar de teste...")
        from models.pilar_model import PilarModel
        pilares = [PilarModel(
            numero="16A",
            nome="P16A",
            comprimento=20.0,
            largura=40.0,
            pavimento=pavimento_nome,
            altura=300.0
        )]
    
    print(f"\n[INFO] Gerando scripts para {len(pilares)} pilares...")
    
    try:
        from models.pavimento_model import PavimentoModel
        from models.obra_model import ObraModel
        from services.automation_service import AutomationOrchestratorService
        
        # Criar modelos
        obra = ObraModel(nome=obra_nome)
        pavimento = PavimentoModel(nome=pavimento_nome)
        pavimento.pilares = pilares
        obra.pavimentos = [pavimento]
        
        # Criar service - usar o diretório raiz do projeto (onde está main.py)
        # O robust_path_resolver retorna o diretório raiz, então precisamos usar o mesmo
        from utils.robust_path_resolver import robust_path_resolver
        actual_project_root = robust_path_resolver.get_project_root()
        print(f"[DEBUG] Project root do automation_service: {project_root}")
        print(f"[DEBUG] Project root do robust_path_resolver: {actual_project_root}")
        # Usar o mesmo project_root que o robust_path_resolver usa
        service = AutomationOrchestratorService(actual_project_root)
        
        # Gerar scripts
        print(f"\n[INFO] Gerando CIMA...")
        result_cima = service.generate_scripts_cima(pavimento, obra)
        print(f"[OK] CIMA gerado: {len(result_cima) if result_cima else 0} caracteres")
        
        print(f"\n[INFO] Gerando ABCD...")
        result_abcd = service.generate_abcd_script(pavimento, obra)
        print(f"[OK] ABCD gerado: {len(result_abcd) if result_abcd else 0} caracteres")
        
        print(f"\n[INFO] Gerando GRADES...")
        result_grades = service.generate_grades_script(pavimento, obra)
        print(f"[OK] GRADES gerado: {len(result_grades) if result_grades else 0} caracteres")
        
        return True
        
    except Exception as e:
        print(f"[ERRO] Erro ao gerar scripts: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*70)
    print("GERACAO DE SCRIPTS PARA TODOS OS PILARES")
    print("="*70)
    
    obra = "Obra Testes"
    pavimento = "Subsolo"
    
    sucesso = gerar_scripts_completos(obra, pavimento)
    
    if sucesso:
        print(f"\n{'='*70}")
        print("[OK] GERACAO CONCLUIDA!")
        print(f"{'='*70}\n")
        print("Execute: python test_script_comparison.py --obra \"Obra Testes\" --pavimento \"Subsolo\"")
    else:
        print(f"\n{'='*70}")
        print("[ERRO] FALHA NA GERACAO")
        print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
