"""
Compara scripts individuais ANTES do combinador
para identificar diferenças na geração
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

def comparar_scripts_individuais(pavimento, tipo):
    """Compara scripts individuais antes do combinador"""
    print(f"\n{'='*70}")
    print(f"COMPARANDO SCRIPTS INDIVIDUAIS: {tipo} - {pavimento}")
    print(f"{'='*70}\n")
    
    # Diretórios
    scripts_main = os.path.join(project_root, "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "SCRIPTS_ROBOS")
    scripts_standalone = os.path.join(project_root, "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "output", "scripts")
    
    pav_safe = pavimento.replace(" ", "_")
    tipo_upper = tipo.upper()
    
    dir_main = os.path.join(scripts_main, f"{pav_safe}_{tipo_upper}")
    dir_standalone = os.path.join(scripts_standalone, f"{pav_safe}_{tipo_upper}")
    
    print(f"[INFO] Diretório main.py: {dir_main}")
    print(f"[INFO] Diretório standalone: {dir_standalone}\n")
    
    # Listar scripts individuais (não os combinados)
    scripts_main_list = []
    scripts_standalone_list = []
    
    if os.path.exists(dir_main):
        for f in os.listdir(dir_main):
            if f.endswith('.scr') and 'Combinados' not in f:
                scripts_main_list.append(os.path.join(dir_main, f))
    
    if os.path.exists(dir_standalone):
        for f in os.listdir(dir_standalone):
            if f.endswith('.scr') and 'Combinados' not in f:
                scripts_standalone_list.append(os.path.join(dir_standalone, f))
    
    print(f"[INFO] Scripts individuais (main.py): {len(scripts_main_list)}")
    for s in scripts_main_list[:5]:
        print(f"  - {os.path.basename(s)}")
    if len(scripts_main_list) > 5:
        print(f"  ... e mais {len(scripts_main_list) - 5}")
    
    print(f"\n[INFO] Scripts individuais (standalone): {len(scripts_standalone_list)}")
    for s in scripts_standalone_list[:5]:
        print(f"  - {os.path.basename(s)}")
    if len(scripts_standalone_list) > 5:
        print(f"  ... e mais {len(scripts_standalone_list) - 5}")
    
    # Comparar por nome
    print(f"\n[INFO] Comparando por nome...")
    main_names = {os.path.basename(s) for s in scripts_main_list}
    standalone_names = {os.path.basename(s) for s in scripts_standalone_list}
    
    comuns = main_names & standalone_names
    apenas_main = main_names - standalone_names
    apenas_standalone = standalone_names - main_names
    
    print(f"  [OK] Nomes comuns: {len(comuns)}")
    print(f"  [AVISO] Apenas main.py: {len(apenas_main)}")
    if apenas_main:
        for n in list(apenas_main)[:5]:
            print(f"    - {n}")
    print(f"  [AVISO] Apenas standalone: {len(apenas_standalone)}")
    if apenas_standalone:
        for n in list(apenas_standalone)[:5]:
            print(f"    - {n}")
    
    return {
        'main_count': len(scripts_main_list),
        'standalone_count': len(scripts_standalone_list),
        'comuns': len(comuns),
        'apenas_main': len(apenas_main),
        'apenas_standalone': len(apenas_standalone)
    }

def main():
    print("="*70)
    print("COMPARACAO DE SCRIPTS INDIVIDUAIS (ANTES DO COMBINADOR)")
    print("="*70)
    
    pavimentos = ["Subsolo", "1 SS", "Terreo"]
    tipos = ["CIMA", "ABCD", "GRADES"]
    
    resultados = {}
    
    for pavimento in pavimentos:
        resultados[pavimento] = {}
        for tipo in tipos:
            resultados[pavimento][tipo] = comparar_scripts_individuais(pavimento, tipo)
    
    # Resumo
    print(f"\n{'='*70}")
    print("RESUMO")
    print(f"{'='*70}\n")
    
    for pavimento in pavimentos:
        print(f"{pavimento}:")
        for tipo in tipos:
            r = resultados[pavimento][tipo]
            print(f"  {tipo}: main={r['main_count']}, standalone={r['standalone_count']}, comuns={r['comuns']}")
        print()

if __name__ == "__main__":
    main()
