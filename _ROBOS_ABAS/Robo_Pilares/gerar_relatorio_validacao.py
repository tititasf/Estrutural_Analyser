"""
Gera relatório detalhado de validação comparando scripts
"""

import os
import sys
from pathlib import Path

# Configurar encoding apenas se necessário
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    try:
        import io
        if not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if not isinstance(sys.stderr, io.TextIOWrapper) and hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass  # Se falhar, continua sem modificar

# Adicionar paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
for _ in range(3):
    parent = os.path.dirname(project_root)
    if os.path.exists(os.path.join(parent, "main.py")):
        project_root = parent
        break
    project_root = parent

sys.path.insert(0, os.path.join(current_dir, "pilares-atualizado-09-25", "src"))

from test_script_comparison import ScriptComparator

def main():
    print("="*70)
    print("RELATORIO DE VALIDACAO DE SCRIPTS")
    print("="*70)
    print()
    
    comparator = ScriptComparator(project_root, verbose=True)
    
    # Testar pavimentos conhecidos
    pavimentos = ["Subsolo", "1 SS", "Terreo", "5pav"]
    
    resultados_gerais = {
        "total_pavimentos": len(pavimentos),
        "pavimentos_com_scripts_main": 0,
        "pavimentos_com_scripts_standalone": 0,
        "pavimentos_com_diferencas": 0,
        "pavimentos_identicos": 0,
        "detalhes": []
    }
    
    for pavimento in pavimentos:
        print(f"\n{'='*70}")
        print(f"PAVIMENTO: {pavimento}")
        print(f"{'='*70}\n")
        
        results = comparator.compare_all_scripts("Obra Testes", pavimento)
        comparator.print_summary(results)
        
        # Analisar resultados
        tem_main = any(len(r['main_scripts']) > 0 for r in results['tipos'].values())
        tem_standalone = any(len(r['standalone_scripts']) > 0 for r in results['tipos'].values())
        tem_diferencas = any(len(r['differences']) > 0 for r in results['tipos'].values())
        identicos = all(
            len(r['matches']) > 0 and len(r['differences']) == 0 and len(r['errors']) == 0
            for r in results['tipos'].values()
            if r['main_scripts'] > 0 and r['standalone_scripts'] > 0
        )
        
        if tem_main:
            resultados_gerais["pavimentos_com_scripts_main"] += 1
        if tem_standalone:
            resultados_gerais["pavimentos_com_scripts_standalone"] += 1
        if tem_diferencas:
            resultados_gerais["pavimentos_com_diferencas"] += 1
        if identicos and tem_main and tem_standalone:
            resultados_gerais["pavimentos_identicos"] += 1
        
        resultados_gerais["detalhes"].append({
            "pavimento": pavimento,
            "tem_main": tem_main,
            "tem_standalone": tem_standalone,
            "tem_diferencas": tem_diferencas,
            "identicos": identicos,
            "tipos": {tipo: {
                "main": r['main_scripts'],
                "standalone": r['standalone_scripts'],
                "matches": len(r['matches']),
                "differences": len(r['differences']),
                "errors": len(r['errors'])
            } for tipo, r in results['tipos'].items()}
        })
    
    # Resumo final
    print(f"\n{'='*70}")
    print("RESUMO GERAL")
    print(f"{'='*70}")
    print(f"Total de pavimentos testados: {resultados_gerais['total_pavimentos']}")
    print(f"Pavimentos com scripts (main.py): {resultados_gerais['pavimentos_com_scripts_main']}")
    print(f"Pavimentos com scripts (standalone): {resultados_gerais['pavimentos_com_scripts_standalone']}")
    print(f"Pavimentos com diferencas: {resultados_gerais['pavimentos_com_diferencas']}")
    print(f"Pavimentos identicos: {resultados_gerais['pavimentos_identicos']}")
    print(f"{'='*70}\n")
    
    # Recomendações
    print("RECOMENDACOES:")
    print("-" * 70)
    
    if resultados_gerais['pavimentos_com_scripts_main'] < resultados_gerais['pavimentos_com_scripts_standalone']:
        print("[AVISO] Alguns pavimentos tem scripts apenas no standalone.")
        print("        E necessario gerar scripts via main.py para comparacao.")
    
    if resultados_gerais['pavimentos_com_diferencas'] > 0:
        print("[AVISO] Foram encontradas diferencas entre os scripts gerados.")
        print("        Verifique:")
        print("        1. Se os dados de entrada sao identicos")
        print("        2. Se o mapeamento PilarModel -> dict esta correto")
        print("        3. Se os geradores estao usando a mesma versao")
    
    if resultados_gerais['pavimentos_identicos'] == 0 and resultados_gerais['pavimentos_com_scripts_main'] > 0:
        print("[ERRO] Nenhum pavimento tem scripts identicos!")
        print("        Isso indica um problema sistemico na geracao.")
    
    return 0 if resultados_gerais['pavimentos_identicos'] > 0 else 1

if __name__ == "__main__":
    sys.exit(main())
