"""
Script para comparar geração de scripts entre sistema legacy e novo
1. Gera scripts usando sistema legacy (standalone)
2. Gera scripts usando novo sistema (automation_service)
3. Compara os resultados
"""

import os
import sys
import shutil
from pathlib import Path

# Configurar encoding
if sys.platform == 'win32':
    import io
    try:
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
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

def buscar_pilares_do_banco():
    """Busca todos os pilares salvos no banco de dados"""
    print("="*70)
    print("BUSCANDO PILARES NO BANCO DE DADOS")
    print("="*70)
    
    try:
        from core.database import Database
        db = Database()
        
        # Buscar todos os projetos
        projects = db.get_projects()
        print(f"\n[INFO] Encontrados {len(projects)} projetos no banco")
        
        pilares_por_pavimento = {}
        
        for project in projects:
            project_id = project.get('id')
            work_name = project.get('work_name', 'Desconhecida')
            pavement_name = project.get('pavement_name') or project.get('name', 'Desconhecido')
            
            print(f"\n[INFO] Projeto: {work_name} - Pavimento: {pavement_name} (ID: {project_id})")
            
            # Buscar pilares do projeto
            pillars = db.get_project_items(project_id, item_type='pillar')
            print(f"[INFO] Encontrados {len(pillars)} pilares")
            
            if pillars:
                key = (work_name, pavement_name)
                if key not in pilares_por_pavimento:
                    pilares_por_pavimento[key] = []
                
                for p_data in pillars:
                    name = p_data.get('name', 'P?')
                    dim = p_data.get('dim', '')
                    print(f"  - {name} ({dim})")
                    pilares_por_pavimento[key].append(p_data)
        
        return pilares_por_pavimento
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar pilares: {e}")
        import traceback
        traceback.print_exc()
        return {}

def gerar_com_legacy(obra_nome, pavimento_nome, pilares_data):
    """Gera scripts usando sistema legacy (standalone)"""
    print("\n" + "="*70)
    print(f"GERANDO COM SISTEMA LEGACY")
    print(f"Obra: {obra_nome}, Pavimento: {pavimento_nome}")
    print("="*70)
    
    # Diretório de saída legacy (usar SCRIPTS_ROBOS do projeto raiz)
    from utils.robust_path_resolver import robust_path_resolver
    legacy_project_root = robust_path_resolver.get_project_root()
    legacy_output_base = os.path.join(legacy_project_root, "SCRIPTS_ROBOS_LEGACY")
    os.makedirs(legacy_output_base, exist_ok=True)
    
    pav_safe = pavimento_nome.replace(' ', '_')
    legacy_output = os.path.join(legacy_output_base, pav_safe)
    os.makedirs(legacy_output, exist_ok=True)
    
    # Limpar diretórios de saída legacy
    for subdir in ['CIMA', 'ABCD', 'GRADES']:
        subdir_path = os.path.join(legacy_output, subdir)
        if os.path.exists(subdir_path):
            shutil.rmtree(subdir_path)
        os.makedirs(subdir_path, exist_ok=True)
    
    try:
        # Importar módulos legacy
        from interfaces.CIMA_FUNCIONAL_EXCEL import preencher_campos_diretamente_e_gerar_scripts as gerar_cima
        from interfaces.Abcd_Excel import preencher_campos_diretamente_e_gerar_scripts as gerar_abcd
        from interfaces.GRADE_EXCEL import preencher_campos_diretamente_e_gerar_scripts as gerar_grades
        
        # Configurar caminho de saída para legacy (usar SCRIPTS_ROBOS do projeto)
        from utils.robust_path_resolver import robust_path_resolver
        legacy_project_root = robust_path_resolver.get_project_root()
        legacy_scripts_dir = os.path.join(legacy_project_root, "SCRIPTS_ROBOS_LEGACY")
        os.makedirs(legacy_scripts_dir, exist_ok=True)
        
        # Temporariamente redirecionar output do legacy
        import sys
        original_cwd = os.getcwd()
        try:
            os.chdir(legacy_project_root)
        except:
            pass
        
        # Converter dados para formato legacy
        from models.pilar_model import PilarModel
        
        pilares_model = []
        for p_data in pilares_data:
            name = p_data.get('name', 'P?')
            nums = __import__('re').findall(r'\d+', name)
            numero = nums[0] if nums else "0"
            
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
            
            pilar = PilarModel(
                numero=numero,
                nome=name,
                comprimento=comprimento,
                largura=largura,
                pavimento=pavimento_nome,
                altura=300.0
            )
            pilares_model.append(pilar)
        
        # Gerar scripts
        print(f"\n[INFO] Gerando scripts para {len(pilares_model)} pilares...")
        
        for pilar in pilares_model:
            print(f"\n[INFO] Processando pilar: {pilar.nome}")
            
            # Preparar dados (formato completo para legacy)
            dados = {
                'interface_principal': None,
                'pavimento': pavimento_nome,
                'nome': pilar.nome,
                'numero': pilar.numero,
                'comprimento': pilar.comprimento,
                'largura': pilar.largura,
                'altura': pilar.altura,
                'pavimento_anterior': None,
                'nivel_saida': 0.0,
                'nivel_chegada': 0.0,
                'nivel_diferencial': 0.0,
                'parafuso_p1_p2': 0,
                'parafuso_p2_p3': 0,
                'parafuso_p3_p4': 0,
                'parafuso_p4_p5': 0,
                'parafuso_p5_p6': 0,
                'parafuso_p6_p7': 0,
                'parafuso_p7_p8': 0,
                'parafuso_p8_p9': 0,
                'grades_grupo1': {
                    'grade_1': 0.0,
                    'distancia_1': 0.0,
                    'grade_2': 0.0,
                    'distancia_2': 0.0,
                    'grade_3': 0.0,
                }
            }
            
            # Adicionar campos de faces (A-H) vazios
            for face in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
                dados[f'laje_{face}'] = 0.0
                dados[f'posicao_laje_{face}'] = 0.0
                for i in range(1, 4):
                    dados[f'larg{i}_{face}'] = 0.0
                for i in range(1, 6):
                    dados[f'h{i}_{face}'] = 0.0
                    if i >= 2:
                        for l in range(1, 4):
                            dados[f'hachura_l{l}_h{i}_{face}'] = 0
            
            # Gerar CIMA
            try:
                print(f"  [CIMA] Gerando para {pilar.nome}...")
                resultado_cima = gerar_cima(dados)
                if resultado_cima:
                    print(f"  [CIMA] OK - {len(resultado_cima)} caracteres")
                else:
                    print(f"  [CIMA] AVISO - Retornou vazio")
            except Exception as e:
                print(f"  [CIMA] ERRO: {e}")
                import traceback
                traceback.print_exc()
            
            # Gerar ABCD
            try:
                print(f"  [ABCD] Gerando para {pilar.nome}...")
                resultado_abcd = gerar_abcd(dados)
                if resultado_abcd:
                    print(f"  [ABCD] OK - {len(resultado_abcd)} caracteres")
                else:
                    print(f"  [ABCD] AVISO - Retornou vazio")
            except Exception as e:
                print(f"  [ABCD] ERRO: {e}")
                import traceback
                traceback.print_exc()
            
            # Gerar GRADES
            try:
                print(f"  [GRADES] Gerando para {pilar.nome}...")
                resultado_grades = gerar_grades(dados)
                if resultado_grades:
                    print(f"  [GRADES] OK - {len(resultado_grades)} caracteres")
                else:
                    print(f"  [GRADES] AVISO - Retornou vazio")
            except Exception as e:
                print(f"  [GRADES] ERRO: {e}")
                import traceback
                traceback.print_exc()
        
        return legacy_output
        
    except Exception as e:
        print(f"[ERRO] Erro ao gerar com legacy: {e}")
        import traceback
        traceback.print_exc()
        return None

def gerar_com_novo(obra_nome, pavimento_nome, pilares_data):
    """Gera scripts usando novo sistema (automation_service)"""
    print("\n" + "="*70)
    print(f"GERANDO COM SISTEMA NOVO")
    print(f"Obra: {obra_nome}, Pavimento: {pavimento_nome}")
    print("="*70)
    
    try:
        from models.pavimento_model import PavimentoModel
        from models.obra_model import ObraModel
        from models.pilar_model import PilarModel
        from services.automation_service import AutomationOrchestratorService
        from utils.robust_path_resolver import robust_path_resolver
        
        # Converter dados
        pilares_model = []
        for p_data in pilares_data:
            name = p_data.get('name', 'P?')
            nums = __import__('re').findall(r'\d+', name)
            numero = nums[0] if nums else "0"
            
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
            
            pilar = PilarModel(
                numero=numero,
                nome=name,
                comprimento=comprimento,
                largura=largura,
                pavimento=pavimento_nome,
                altura=300.0
            )
            pilares_model.append(pilar)
        
        # Criar modelos
        obra = ObraModel(nome=obra_nome)
        pavimento = PavimentoModel(nome=pavimento_nome)
        pavimento.pilares = pilares_model
        obra.pavimentos = [pavimento]
        
        # Criar service
        actual_project_root = robust_path_resolver.get_project_root()
        service = AutomationOrchestratorService(actual_project_root)
        
        # Gerar scripts
        print(f"\n[INFO] Gerando scripts para {len(pilares_model)} pilares...")
        
        print(f"\n[INFO] Gerando CIMA...")
        service.generate_scripts_cima(pavimento, obra)
        
        print(f"\n[INFO] Gerando ABCD...")
        service.generate_abcd_script(pavimento, obra)
        
        print(f"\n[INFO] Gerando GRADES...")
        service.generate_grades_script(pavimento, obra)
        
        # Diretório de saída novo (automation_service já salva em SCRIPTS_ROBOS)
        novo_output = os.path.join(actual_project_root, "SCRIPTS_ROBOS")
        
        return novo_output
        
    except Exception as e:
        print(f"[ERRO] Erro ao gerar com novo: {e}")
        import traceback
        traceback.print_exc()
        return None

def comparar_scripts(legacy_dir, novo_dir, pavimento_nome):
    """Compara scripts gerados por ambos os sistemas"""
    print("\n" + "="*70)
    print("COMPARANDO SCRIPTS")
    print("="*70)
    
    tipos = ['CIMA', 'ABCD', 'GRADES']
    resultados = {}
    
    for tipo in tipos:
        print(f"\n[{tipo}] Comparando...")
        
        pav_safe = pavimento_nome.replace(' ', '_')
        legacy_subdir = os.path.join(legacy_dir, tipo)
        novo_subdir = os.path.join(novo_dir, f"{pav_safe}_{tipo}")
        
        if not os.path.exists(legacy_subdir):
            print(f"  [AVISO] Diretório legacy não encontrado: {legacy_subdir}")
            continue
        
        if not os.path.exists(novo_subdir):
            print(f"  [AVISO] Diretório novo não encontrado: {novo_subdir}")
            continue
        
        # Listar arquivos
        legacy_files = {f.name: f for f in Path(legacy_subdir).glob("*.scr")}
        novo_files = {f.name: f for f in Path(novo_subdir).glob("*.scr")}
        
        print(f"  Legacy: {len(legacy_files)} arquivos")
        print(f"  Novo: {len(novo_files)} arquivos")
        
        # Comparar arquivos comuns
        arquivos_comuns = set(legacy_files.keys()) & set(novo_files.keys())
        arquivos_apenas_legacy = set(legacy_files.keys()) - set(novo_files.keys())
        arquivos_apenas_novo = set(novo_files.keys()) - set(legacy_files.keys())
        
        print(f"  Comuns: {len(arquivos_comuns)}")
        if arquivos_apenas_legacy:
            print(f"  Apenas legacy: {arquivos_apenas_legacy}")
        if arquivos_apenas_novo:
            print(f"  Apenas novo: {arquivos_apenas_novo}")
        
        # Comparar conteúdo dos arquivos comuns
        identicos = 0
        diferentes = 0
        
        for nome_arquivo in arquivos_comuns:
            legacy_path = legacy_files[nome_arquivo]
            novo_path = novo_files[nome_arquivo]
            
            try:
                # Ler arquivos (UTF-16 LE)
                with open(legacy_path, 'rb') as f:
                    legacy_content = f.read()
                with open(novo_path, 'rb') as f:
                    novo_content = f.read()
                
                if legacy_content == novo_content:
                    identicos += 1
                else:
                    diferentes += 1
                    print(f"    [DIFERENTE] {nome_arquivo}")
                    print(f"      Legacy: {len(legacy_content)} bytes")
                    print(f"      Novo: {len(novo_content)} bytes")
            except Exception as e:
                print(f"    [ERRO] Erro ao comparar {nome_arquivo}: {e}")
        
        resultados[tipo] = {
            'identicos': identicos,
            'diferentes': diferentes,
            'total_comuns': len(arquivos_comuns)
        }
        
        print(f"  [RESULTADO] Idênticos: {identicos}, Diferentes: {diferentes}")
    
    return resultados

def main():
    print("="*70)
    print("COMPARAÇÃO LEGACY vs NOVO - GERAÇÃO DE SCRIPTS")
    print("="*70)
    
    # 1. Buscar pilares do banco
    pilares_por_pavimento = buscar_pilares_do_banco()
    
    if not pilares_por_pavimento:
        print("\n[AVISO] Nenhum pilar encontrado no banco. Usando pilar de teste...")
        # Usar pilar de teste
        from models.pilar_model import PilarModel
        pilares_por_pavimento = {
            ("Obra Testes", "Subsolo"): [{
                'name': 'P16A',
                'dim': '20x40'
            }]
        }
    
    # 2. Processar cada pavimento
    for (obra_nome, pavimento_nome), pilares_data in pilares_por_pavimento.items():
        print(f"\n{'='*70}")
        print(f"PROCESSANDO: {obra_nome} - {pavimento_nome}")
        print(f"{'='*70}")
        
        # Gerar com legacy
        legacy_dir = gerar_com_legacy(obra_nome, pavimento_nome, pilares_data)
        
        # Gerar com novo
        novo_dir = gerar_com_novo(obra_nome, pavimento_nome, pilares_data)
        
        # Comparar
        if legacy_dir and novo_dir:
            resultados = comparar_scripts(legacy_dir, novo_dir, pavimento_nome)
            
            # Resumo
            print("\n" + "="*70)
            print("RESUMO DA COMPARAÇÃO")
            print("="*70)
            for tipo, resultado in resultados.items():
                print(f"\n[{tipo}]")
                print(f"  Idênticos: {resultado['identicos']}/{resultado['total_comuns']}")
                print(f"  Diferentes: {resultado['diferentes']}/{resultado['total_comuns']}")
    
    print("\n" + "="*70)
    print("COMPARAÇÃO CONCLUÍDA")
    print("="*70)

if __name__ == "__main__":
    main()
