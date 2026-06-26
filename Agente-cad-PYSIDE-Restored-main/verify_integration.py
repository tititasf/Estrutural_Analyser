import sys
import os
import logging

# Setup environment
sys.path.append(os.getcwd())

from src.core.database import DatabaseManager
from src.core.dxf_loader import DXFLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Verification")

def verify_system():
    print("--- INICIANDO VERIFICACAO DE SISTEMA ---")
    
    # 1. Verificar Database e Projetos
    db = DatabaseManager()
    projects = db.get_projects()
    print(f"1. Projetos no Banco: {len(projects)}")
    
    selected_project = None
    if projects:
        selected_project = projects[0]
        print(f"   Projeto Encontrado: {selected_project['name']} (ID: {selected_project['id']})")
        print(f"   Caminho DXF: {selected_project['dxf_path']}")
    else:
        print("   Nenhum projeto encontrado para teste de carga.")
        # Criar um dummy se precisar? Não, melhor apenas reportar.
        project_id = db.create_project("Projeto Teste CLI", "C:/Users/Ryzen/Desktop/GITHUB/Agente-cad-PYSIDE/ESTRUTURAL.dxf")
        if project_id:
             selected_project = {'id': project_id, 'name': "Projeto Teste CLI", 'dxf_path': "C:/Users/Ryzen/Desktop/GITHUB/Agente-cad-PYSIDE/ESTRUTURAL.dxf"}
             print(f"   Projeto de teste criado: {project_id}")

    # 2. Testar Carregamento DXF (Onde deu erro antes)
    if selected_project:
        dxf_path = selected_project['dxf_path']
        if os.path.exists(dxf_path):
            print(f"2. Testando DXFLoader.load_dxf com: {dxf_path}")
            try:
                # O erro anterior foi aqui: DXFLoader.load_dxf não existia
                entities = DXFLoader.load_dxf(dxf_path)
                if entities:
                    print(f"   SUCESSO: DXF carregado via método estático.")
                    print(f"   Entidades: {len(entities.get('texts', []))} textos, {len(entities.get('lines', []))} linhas.")
                else:
                    print("   FALHA: DXF carregado mas vazio ou None.")
            except Exception as e:
                print(f"   ERRO CRÍTICO: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"   IGNORADO: Arquivo DXF não existe no disco: {dxf_path}")

    # 3. Testar Carga de Pilares do Projeto
    if selected_project:
        print(f"3. Testando Carga de Dados do DB para Projeto {selected_project['id']}")
        try:
            pillars = db.load_pillars(selected_project['id'])
            print(f"   SUCESSO: {len(pillars)} pilares carregados do banco.")
        except Exception as e:
            print(f"   ERRO DB: {e}")
            
    print("--- FIM DA VERIFICACAO ---")

if __name__ == "__main__":
    verify_system()
