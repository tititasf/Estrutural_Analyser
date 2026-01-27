"""
========================================================
🧪 Teste Comparativo de Scripts: main.py vs Standalone
========================================================

Valida que os scripts gerados pela interface do main.py
são idênticos aos gerados pela interface standalone.

Uso:
    python test_script_comparison.py --obra "NomeObra" --pavimento "NomePavimento"
    python test_script_comparison.py --obra "NomeObra" --pavimento "NomePavimento" --verbose
"""

import os
import sys
import argparse
import difflib
from pathlib import Path
from typing import List, Tuple, Optional

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Adicionar paths necessários
current_dir = os.path.dirname(os.path.abspath(__file__))
pilares_dir = os.path.join(current_dir, "pilares-atualizado-09-25")
if pilares_dir not in sys.path:
    sys.path.insert(0, pilares_dir)

src_dir = os.path.join(pilares_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


class ScriptComparator:
    """Compara scripts gerados por diferentes interfaces"""
    
    def __init__(self, project_root: str, verbose: bool = False):
        self.project_root = project_root
        self.verbose = verbose
        
        # Scripts do main.py podem estar em:
        # 1. SCRIPTS_ROBOS na raiz
        # 2. _ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/SCRIPTS_ROBOS
        scripts_main_1 = os.path.join(project_root, "SCRIPTS_ROBOS")
        scripts_main_2 = os.path.join(project_root, "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "SCRIPTS_ROBOS")
        
        if os.path.exists(scripts_main_2) and os.listdir(scripts_main_2):
            self.scripts_main_dir = scripts_main_2
        else:
            self.scripts_main_dir = scripts_main_1
        
        # Output standalone está em _ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/output
        pilares_output = os.path.join(project_root, "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "output")
        if os.path.exists(pilares_output):
            self.scripts_standalone_dir = pilares_output
        else:
            # Fallback para output na raiz
            self.scripts_standalone_dir = os.path.join(project_root, "output")
        
    def log(self, message: str, level: str = "INFO"):
        """Log com níveis"""
        prefix = {
            "INFO": "[INFO]",
            "SUCCESS": "[OK]",
            "ERROR": "[ERRO]",
            "WARNING": "[AVISO]",
            "DEBUG": "[DEBUG]"
        }.get(level, "[*]")
        print(f"{prefix} {message}")
        if self.verbose and level == "DEBUG":
            print(f"   [DEBUG] {message}")
    
    def find_script_files(self, base_dir: str, pavimento: str, tipo: str) -> List[str]:
        """Encontra arquivos de script em um diretório"""
        tipo_upper = tipo.upper()
        pav_safe = pavimento.replace(" ", "_").replace("-", "_")
        
        scripts = []
        
        # Padrão 1: {pavimento}_{TIPO}/Combinados/*.scr (main.py)
        patterns_main = [
            f"{pav_safe}_{tipo_upper}",
            f"{pavimento}_{tipo_upper}",
        ]
        
        # Padrão 2: output/scripts/{pavimento}_{TIPO}/Combinados/*.scr (standalone)
        # Ou output/scripts/{pavimento}_{TIPO}/*.scr (standalone sem combinador)
        scripts_dir = os.path.join(base_dir, "scripts")
        if os.path.exists(scripts_dir):
            base_dir = scripts_dir
        
        patterns = patterns_main + [tipo_upper]
        
        for pattern in patterns:
            # Tentar Combinados primeiro
            target_dir = os.path.join(base_dir, pattern, "Combinados")
            if os.path.exists(target_dir):
                for file in os.listdir(target_dir):
                    if file.lower().endswith('.scr'):
                        scripts.append(os.path.join(target_dir, file))
            
            # Tentar diretório direto (sem Combinados)
            target_dir = os.path.join(base_dir, pattern)
            if os.path.exists(target_dir) and os.path.isdir(target_dir):
                for file in os.listdir(target_dir):
                    if file.lower().endswith('.scr') and file not in [os.path.basename(s) for s in scripts]:
                        scripts.append(os.path.join(target_dir, file))
        
        return scripts
    
    def read_script_file(self, filepath: str) -> Optional[str]:
        """Lê arquivo de script, tratando diferentes encodings"""
        try:
            # Tentar UTF-16 LE primeiro (padrão AutoCAD)
            with open(filepath, 'rb') as f:
                bom = f.read(2)
                if bom == b'\xFF\xFE':  # UTF-16 LE BOM
                    content = f.read().decode('utf-16-le')
                    return content
                else:
                    # Tentar UTF-8
                    f.seek(0)
                    content = f.read().decode('utf-8', errors='ignore')
                    return content
        except Exception as e:
            self.log(f"Erro ao ler {filepath}: {e}", "ERROR")
            return None
    
    def validate_encoding(self, filepath: str) -> Tuple[bool, str]:
        """Valida se o arquivo está em UTF-16 LE com BOM"""
        try:
            with open(filepath, 'rb') as f:
                bom = f.read(2)
                if bom == b'\xFF\xFE':
                    return True, "UTF-16 LE (BOM)"
                elif bom == b'\xFE\xFF':
                    return False, "UTF-16 BE (BOM) - incorreto"
                else:
                    # Tentar detectar encoding
                    f.seek(0)
                    content = f.read(1024)
                    try:
                        content.decode('utf-8')
                        return False, "UTF-8 - deveria ser UTF-16 LE"
                    except:
                        return False, "Encoding desconhecido"
        except Exception as e:
            return False, f"Erro: {e}"
    
    def validate_autocad_syntax(self, content: str) -> Tuple[bool, List[str]]:
        """Valida sintaxe básica de comandos AutoCAD"""
        errors = []
        lines = content.split('\n')
        
        # Verificar comandos básicos
        valid_commands = ['_LAYER', '_LINE', '_CIRCLE', '_RECTANG', '_ZOOM', '_MOVE', '_ROTATE', '_SCALE']
        
        for i, line in enumerate(lines[:100], 1):  # Verificar primeiras 100 linhas
            line = line.strip()
            if line and not line.startswith(';'):
                # Verificar se é um comando válido
                if line.startswith('_'):
                    cmd = line.split()[0] if line.split() else ""
                    if cmd and cmd not in valid_commands and not cmd.startswith('_'):
                        errors.append(f"Linha {i}: Comando suspeito '{cmd}'")
        
        return len(errors) == 0, errors
    
    def compare_scripts(self, main_script: str, standalone_script: str) -> Tuple[bool, List[str]]:
        """Compara dois scripts linha por linha"""
        main_lines = main_script.splitlines(keepends=True)
        standalone_lines = standalone_script.splitlines(keepends=True)
        
        if main_lines == standalone_lines:
            return True, []
        
        # Gerar diff
        diff = list(difflib.unified_diff(
            main_lines,
            standalone_lines,
            fromfile="main.py",
            tofile="standalone",
            lineterm=''
        ))
        
        return False, diff
    
    def compare_all_scripts(self, obra: str, pavimento: str) -> dict:
        """Compara todos os tipos de scripts (CIMA, ABCD, GRADES)"""
        results = {
            "obra": obra,
            "pavimento": pavimento,
            "tipos": {}
        }
        
        tipos = ["CIMA", "ABCD", "GRADES"]
        
        for tipo in tipos:
            self.log(f"\nComparando scripts {tipo}...", "INFO")
            
            # Encontrar scripts
            main_scripts = self.find_script_files(self.scripts_main_dir, pavimento, tipo)
            standalone_scripts = self.find_script_files(self.scripts_standalone_dir, pavimento, tipo)
            
            tipo_result = {
                "main_scripts": len(main_scripts),
                "standalone_scripts": len(standalone_scripts),
                "matches": [],
                "differences": [],
                "errors": []
            }
            
            if not main_scripts:
                tipo_result["errors"].append(f"Nenhum script {tipo} encontrado em {self.scripts_main_dir}")
                self.log(f"[ERRO] Nenhum script {tipo} encontrado (main.py)", "ERROR")
            
            if not standalone_scripts:
                tipo_result["errors"].append(f"Nenhum script {tipo} encontrado em {self.scripts_standalone_dir}")
                self.log(f"[ERRO] Nenhum script {tipo} encontrado (standalone)", "ERROR")
            
            # Comparar cada par de scripts
            for main_script_path in main_scripts:
                main_content = self.read_script_file(main_script_path)
                if not main_content:
                    tipo_result["errors"].append(f"Erro ao ler {main_script_path}")
                    continue
                
                # Validar encoding
                encoding_ok, encoding_msg = self.validate_encoding(main_script_path)
                if not encoding_ok:
                    tipo_result["errors"].append(f"Encoding inválido em {main_script_path}: {encoding_msg}")
                
                # Validar sintaxe
                syntax_ok, syntax_errors = self.validate_autocad_syntax(main_content)
                if not syntax_ok:
                    tipo_result["errors"].extend(syntax_errors)
                
                # Procurar correspondente no standalone
                found_match = False
                for standalone_script_path in standalone_scripts:
                    standalone_content = self.read_script_file(standalone_script_path)
                    if not standalone_content:
                        continue
                    
                    # Comparar conteúdo
                    identical, diff = self.compare_scripts(main_content, standalone_content)
                    
                    if identical:
                        tipo_result["matches"].append({
                            "main": main_script_path,
                            "standalone": standalone_script_path,
                            "size_main": len(main_content),
                            "size_standalone": len(standalone_content)
                        })
                        self.log(f"Scripts identicos: {os.path.basename(main_script_path)}", "SUCCESS")
                        found_match = True
                        break
                    else:
                        # Guardar diferenças
                        tipo_result["differences"].append({
                            "main": main_script_path,
                            "standalone": standalone_script_path,
                            "diff_lines": len(diff),
                            "diff_preview": diff[:20]  # Primeiras 20 linhas do diff
                        })
                
                if not found_match and standalone_scripts:
                    self.log(f"Diferencas encontradas em {os.path.basename(main_script_path)}", "WARNING")
            
            results["tipos"][tipo] = tipo_result
        
        return results
    
    def print_summary(self, results: dict):
        """Imprime resumo dos resultados"""
        print("\n" + "="*60)
        print("RESUMO DA COMPARACAO")
        print("="*60)
        print(f"Obra: {results['obra']}")
        print(f"Pavimento: {results['pavimento']}")
        print()
        
        total_matches = 0
        total_differences = 0
        total_errors = 0
        
        for tipo, tipo_result in results["tipos"].items():
            print(f"\n{tipo}:")
            print(f"  Scripts (main.py): {tipo_result['main_scripts']}")
            print(f"  Scripts (standalone): {tipo_result['standalone_scripts']}")
            print(f"  [OK] Identicos: {len(tipo_result['matches'])}")
            print(f"  [AVISO] Diferentes: {len(tipo_result['differences'])}")
            print(f"  [ERRO] Erros: {len(tipo_result['errors'])}")
            
            total_matches += len(tipo_result['matches'])
            total_differences += len(tipo_result['differences'])
            total_errors += len(tipo_result['errors'])
            
            # Mostrar detalhes de diferenças
            if tipo_result['differences'] and self.verbose:
                for diff in tipo_result['differences'][:3]:  # Primeiras 3 diferenças
                    print(f"\n    Diferenças em {os.path.basename(diff['main'])}:")
                    print(f"      Linhas de diff: {diff['diff_lines']}")
                    if diff['diff_preview']:
                        print("      Preview:")
                        for line in diff['diff_preview'][:10]:
                            print(f"        {line.rstrip()}")
            
            # Mostrar erros
            if tipo_result['errors']:
                for error in tipo_result['errors'][:5]:  # Primeiros 5 erros
                    print(f"    [ERRO] {error}")
        
        print("\n" + "="*60)
        print(f"TOTAL: {total_matches} idênticos, {total_differences} diferentes, {total_errors} erros")
        print("="*60)
        
        if total_differences == 0 and total_errors == 0:
            print("\n[OK] TODOS OS SCRIPTS SAO IDENTICOS!")
        elif total_differences > 0:
            print(f"\n[AVISO] {total_differences} SCRIPT(S) COM DIFERENCAS DETECTADAS")
        if total_errors > 0:
            print(f"\n[ERRO] {total_errors} ERRO(S) ENCONTRADO(S)")


def main():
    parser = argparse.ArgumentParser(description="Compara scripts gerados por main.py vs standalone")
    parser.add_argument("--obra", required=True, help="Nome da obra")
    parser.add_argument("--pavimento", required=True, help="Nome do pavimento")
    parser.add_argument("--project-root", default=None, help="Diretório raiz do projeto")
    parser.add_argument("--verbose", "-v", action="store_true", help="Modo verbose")
    
    args = parser.parse_args()
    
    # Determinar project root
    if args.project_root:
        project_root = args.project_root
    else:
        # Tentar detectar automaticamente
        current = os.path.dirname(os.path.abspath(__file__))
        # Subir até encontrar main.py ou SCRIPTS_ROBOS
        project_root = current
        for _ in range(5):
            if os.path.exists(os.path.join(project_root, "main.py")) or \
               os.path.exists(os.path.join(project_root, "SCRIPTS_ROBOS")):
                break
            project_root = os.path.dirname(project_root)
    
    if not os.path.exists(project_root):
        print(f"[ERRO] Diretorio raiz nao encontrado: {project_root}")
        sys.exit(1)
    
    print(f"[INFO] Project Root: {project_root}")
    print(f"[INFO] Obra: {args.obra}")
    print(f"[INFO] Pavimento: {args.pavimento}")
    print()
    
    comparator = ScriptComparator(project_root, verbose=args.verbose)
    results = comparator.compare_all_scripts(args.obra, args.pavimento)
    comparator.print_summary(results)
    
    # Exit code baseado em resultados
    total_errors = sum(len(r['errors']) for r in results['tipos'].values())
    total_differences = sum(len(r['differences']) for r in results['tipos'].values())
    
    if total_errors > 0:
        sys.exit(2)  # Erros críticos
    elif total_differences > 0:
        sys.exit(1)  # Diferenças encontradas
    else:
        sys.exit(0)  # Tudo OK


if __name__ == "__main__":
    main()
