"""
Gera scripts via main.py e compara com standalone
"""

import os
import sys
import traceback

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

def gerar_via_main_py(obra_nome, pavimento_nome):
    """Gera scripts via main.py (simulando chamada)"""
    print(f"\n{'='*70}")
    print(f"GERANDO SCRIPTS VIA MAIN.PY")
    print(f"Obra: {obra_nome}, Pavimento: {pavimento_nome}")
    print(f"{'='*70}\n")
    
    try:
        from models.pilar_model import PilarModel
        from models.pavimento_model import PavimentoModel
        from models.obra_model import ObraModel
        from services.automation_service import AutomationOrchestratorService
        
        # Criar service
        service = AutomationOrchestratorService(project_root)
        
        # Buscar obra e pavimento (simular busca)
        # Por enquanto, vamos usar dados de teste
        print(f"[INFO] Buscando obra '{obra_nome}' e pavimento '{pavimento_nome}'...")
        
        # Criar modelos de teste (seria melhor buscar do banco/estado)
        obra = ObraModel(nome=obra_nome)
        pavimento = PavimentoModel(nome=pavimento_nome)
        obra.pavimentos = [pavimento]
        
        # Tentar buscar pilares do robo_pilares se disponível
        # Por enquanto, vamos gerar com pilares vazios e ver o que acontece
        if not pavimento.pilares:
            pavimento.pilares = []
            print(f"[AVISO] Nenhum pilar encontrado. Criando pilar de teste...")
            # Criar pilar de teste
            pilar_teste = PilarModel(
                numero="16A",
                nome="P16A",
                comprimento=20.0,
                largura=40.0,
                pavimento=pavimento_nome,
                altura=300.0
            )
            pavimento.pilares.append(pilar_teste)
        
        print(f"[INFO] Encontrados {len(pavimento.pilares)} pilares")
        
        # Gerar scripts
        print(f"\n[INFO] Gerando scripts CIMA...")
        result_cima = service.generate_scripts_cima(pavimento, obra)
        print(f"[INFO] Resultado CIMA: {result_cima[:100] if result_cima else 'None'}...")
        
        print(f"\n[INFO] Gerando scripts ABCD...")
        result_abcd = service.generate_scripts_abcd(pavimento, obra)
        print(f"[INFO] Resultado ABCD: {result_abcd[:100] if result_abcd else 'None'}...")
        
        print(f"\n[INFO] Gerando scripts GRADES...")
        result_grades = service.generate_grades_script(pavimento, obra)
        print(f"[INFO] Resultado GRADES: {result_grades[:100] if result_grades else 'None'}...")
        
        return True
        
    except Exception as e:
        print(f"[ERRO] Erro ao gerar scripts: {e}")
        traceback.print_exc()
        return False

def comparar_resultados(obra_nome, pavimento_nome):
    """Compara scripts gerados"""
    print(f"\n{'='*70}")
    print(f"COMPARANDO RESULTADOS")
    print(f"{'='*70}\n")
    
    # Importar comparador
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_script_comparison import ScriptComparator
    
    comparator = ScriptComparator(project_root, verbose=True)
    results = comparator.compare_all_scripts(obra_nome, pavimento_nome)
    comparator.print_summary(results)
    
    return results

def main():
    print("="*70)
    print("GERACAO E COMPARACAO DE SCRIPTS")
    print("="*70)
    
    # Testar com Subsolo
    obra = "Obra Testes"
    pavimento = "Subsolo"
    
    # 1. Gerar via main.py
    sucesso = gerar_via_main_py(obra, pavimento)
    
    if sucesso:
        # 2. Comparar
        resultados = comparar_resultados(obra, pavimento)
        
        # 3. Resumo
        print(f"\n{'='*70}")
        print("RESUMO FINAL")
        print(f"{'='*70}\n")
        
        total_matches = sum(len(r['matches']) for r in resultados['tipos'].values())
        total_differences = sum(len(r['differences']) for r in resultados['tipos'].values())
        total_errors = sum(len(r['errors']) for r in resultados['tipos'].values())
        
        print(f"Scripts idênticos: {total_matches}")
        print(f"Scripts diferentes: {total_differences}")
        print(f"Erros: {total_errors}")
        
        if total_differences == 0 and total_errors == 0:
            print("\n[OK] TODOS OS SCRIPTS SAO IDENTICOS!")
        else:
            print(f"\n[AVISO] {total_differences} SCRIPT(S) COM DIFERENCAS")
            if total_errors > 0:
                print(f"[ERRO] {total_errors} ERRO(S) ENCONTRADO(S)")
    else:
        print("\n[ERRO] Falha na geração de scripts")

if __name__ == "__main__":
    main()
