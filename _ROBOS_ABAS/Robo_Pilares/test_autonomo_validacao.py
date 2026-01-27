"""
========================================================
🤖 Teste Autônomo de Validação de Scripts
========================================================

Testa automaticamente a geração e comparação de scripts
entre main.py e interface standalone.
"""

import os
import sys
import subprocess
from pathlib import Path

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Adicionar paths
current_dir = os.path.dirname(os.path.abspath(__file__))
# Subir até a raiz do projeto (onde está main.py)
project_root = current_dir
for _ in range(3):
    parent = os.path.dirname(project_root)
    if os.path.exists(os.path.join(parent, "main.py")) or os.path.exists(os.path.join(project_root, "SCRIPTS_ROBOS")):
        if os.path.exists(os.path.join(parent, "main.py")):
            project_root = parent
        break
    project_root = parent
sys.path.insert(0, project_root)

def log(message, level="INFO"):
    """Log formatado"""
    # Usar símbolos ASCII para compatibilidade Windows
    icons = {"INFO": "[INFO]", "SUCCESS": "[OK]", "ERROR": "[ERRO]", "WARNING": "[AVISO]"}
    print(f"{icons.get(level, '[*]')} {message}")

def encontrar_obras_pavimentos():
    """Encontra obras e pavimentos disponíveis nos scripts gerados"""
    obras_pavimentos = []
    
    # Verificar SCRIPTS_ROBOS (main.py)
    scripts_main = Path(project_root) / "SCRIPTS_ROBOS"
    if scripts_main.exists():
        for item in scripts_main.iterdir():
            if item.is_dir():
                # Padrão: {pavimento}_{TIPO}
                nome = item.name
                # Tentar extrair pavimento (antes do último _)
                if '_' in nome:
                    partes = nome.rsplit('_', 1)
                    if len(partes) == 2 and partes[1] in ['CIMA', 'ABCD', 'GRADES']:
                        pavimento = partes[0]
                        # Tentar encontrar obra (assumir "Obra Testes" ou similar)
                        obras_pavimentos.append({
                            'obra': 'Obra Testes',
                            'pavimento': pavimento.replace('_', ' ')
                        })
    
    # Verificar output (standalone)
    output_dir = Path(project_root) / "_ROBOS_ABAS" / "Robo_Pilares" / "pilares-atualizado-09-25" / "output"
    if output_dir.exists():
        scripts_dir = output_dir / "scripts"
        if scripts_dir.exists():
            for item in scripts_dir.iterdir():
                if item.is_dir():
                    nome = item.name
                    if '_' in nome:
                        partes = nome.rsplit('_', 1)
                        if len(partes) == 2 and partes[1] in ['CIMA', 'ABCD', 'GRADES']:
                            pavimento = partes[0]
                            obras_pavimentos.append({
                                'obra': 'Obra Testes',
                                'pavimento': pavimento.replace('_', ' ')
                            })
    
    # Remover duplicatas
    seen = set()
    unique = []
    for item in obras_pavimentos:
        key = (item['obra'], item['pavimento'])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    
    return unique

def executar_teste_comparativo(obra, pavimento):
    """Executa o teste comparativo"""
    log(f"Testando: Obra='{obra}', Pavimento='{pavimento}'", "INFO")
    
    script_path = Path(current_dir) / "test_script_comparison.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), 
             "--obra", obra, 
             "--pavimento", pavimento,
             "--verbose"],
            capture_output=True,
            text=True,
            cwd=current_dir,
            timeout=60
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        log(f"Timeout ao testar {obra}/{pavimento}", "ERROR")
        return False, "", "Timeout"
    except Exception as e:
        log(f"Erro ao executar teste: {e}", "ERROR")
        return False, "", str(e)

def main():
    """Função principal"""
    log("Iniciando validação autônoma...", "INFO")
    log(f"Project Root: {project_root}", "INFO")
    
    # 1. Encontrar obras/pavimentos disponíveis
    log("Buscando obras e pavimentos...", "INFO")
    obras_pavimentos = encontrar_obras_pavimentos()
    
    if not obras_pavimentos:
        log("Nenhuma obra/pavimento encontrada. Testando com valores padrão...", "WARNING")
        obras_pavimentos = [
            {'obra': 'Obra Testes', 'pavimento': 'Subsolo'},
            {'obra': 'Obra Testes', 'pavimento': '1 SS'},
            {'obra': 'Obra Testes', 'pavimento': 'Terreo'}
        ]
    
    log(f"Encontrados {len(obras_pavimentos)} pavimentos para testar", "INFO")
    for item in obras_pavimentos:
        log(f"  - {item['obra']} / {item['pavimento']}", "INFO")
    
    # 2. Executar testes
    resultados = []
    sucessos = 0
    falhas = 0
    
    for item in obras_pavimentos:
        obra = item['obra']
        pavimento = item['pavimento']
        
        sucesso, stdout, stderr = executar_teste_comparativo(obra, pavimento)
        
        resultados.append({
            'obra': obra,
            'pavimento': pavimento,
            'sucesso': sucesso,
            'stdout': stdout,
            'stderr': stderr
        })
        
        if sucesso:
            sucessos += 1
            log(f"[OK] {obra}/{pavimento}: SUCESSO", "SUCCESS")
        else:
            falhas += 1
            log(f"[ERRO] {obra}/{pavimento}: FALHA", "ERROR")
    
    # 3. Resumo
    print("\n" + "="*60)
    log("RESUMO DA VALIDAÇÃO", "INFO")
    print("="*60)
    log(f"Total testado: {len(resultados)}", "INFO")
    log(f"Sucessos: {sucessos}", "SUCCESS" if sucessos > 0 else "INFO")
    log(f"Falhas: {falhas}", "ERROR" if falhas > 0 else "INFO")
    print("="*60)
    
    # 4. Detalhes das falhas
    if falhas > 0:
        log("\nDetalhes das falhas:", "WARNING")
        for r in resultados:
            if not r['sucesso']:
                print(f"\n  {r['obra']} / {r['pavimento']}:")
                if r['stderr']:
                    print(f"    Erro: {r['stderr'][:200]}")
    
    # 5. Exit code
    if falhas == 0:
        log("\n[OK] TODOS OS TESTES PASSARAM!", "SUCCESS")
        return 0
    else:
        log(f"\n[AVISO] {falhas} TESTE(S) FALHARAM", "WARNING")
        return 1

if __name__ == "__main__":
    sys.exit(main())
