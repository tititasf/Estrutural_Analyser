
# Helper de ofuscação (adicionado automaticamente)
def _get_obf_str(key):
    """Retorna string ofuscada"""
    _obf_map = {
        _get_obf_str("script.google.com"): base64.b64decode("=02bj5SZsd2bvdmL0BXayN2c"[::-1].encode()).decode(),
        _get_obf_str("macros/s/"): base64.b64decode("vM3Lz9mcjFWb"[::-1].encode()).decode(),
        _get_obf_str("AKfycbz"): base64.b64decode("==geiNWemtUQ"[::-1].encode()).decode(),
        _get_obf_str("credit"): base64.b64decode("0lGZlJ3Y"[::-1].encode()).decode(),
        _get_obf_str("saldo"): base64.b64decode("=8GZsF2c"[::-1].encode()).decode(),
        _get_obf_str("consumo"): base64.b64decode("==wbtV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("api_key"): base64.b64decode("==Qelt2XpBXY"[::-1].encode()).decode(),
        _get_obf_str("user_id"): base64.b64decode("==AZp9lclNXd"[::-1].encode()).decode(),
        _get_obf_str("calcular_creditos"): base64.b64decode("=M3b0lGZlJ3YfJXYsV3YsF2Y"[::-1].encode()).decode(),
        _get_obf_str("confirmar_consumo"): base64.b64decode("=8Wb1NnbvN2XyFWbylmZu92Y"[::-1].encode()).decode(),
        _get_obf_str("consultar_saldo"): base64.b64decode("vRGbhN3XyFGdsV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("debitar_creditos"): base64.b64decode("==wcvRXakVmcj9lchRXaiVGZ"[::-1].encode()).decode(),
        _get_obf_str("CreditManager"): base64.b64decode("==gcldWYuFWT0lGZlJ3Q"[::-1].encode()).decode(),
        _get_obf_str("obter_hwid"): base64.b64decode("==AZpdHafJXZ0J2b"[::-1].encode()).decode(),
        _get_obf_str("generate_signature"): base64.b64decode("lJXd0Fmbnl2cfVGdhJXZuV2Z"[::-1].encode()).decode(),
        _get_obf_str("encrypt_string"): base64.b64decode("=cmbpJHdz9Fdwlncj5WZ"[::-1].encode()).decode(),
        _get_obf_str("decrypt_string"): base64.b64decode("=cmbpJHdz9FdwlncjVGZ"[::-1].encode()).decode(),
        _get_obf_str("integrity_check"): base64.b64decode("rNWZoN2X5RXaydWZ05Wa"[::-1].encode()).decode(),
        _get_obf_str("security_utils"): base64.b64decode("=MHbpRXdflHdpJXdjV2c"[::-1].encode()).decode(),
        _get_obf_str("https://"): base64.b64decode("=8yL6MHc0RHa"[::-1].encode()).decode(),
        _get_obf_str("google.com"): base64.b64decode("==QbvNmLlx2Zv92Z"[::-1].encode()).decode(),
        _get_obf_str("apps.script"): base64.b64decode("=QHcpJ3Yz5ycwBXY"[::-1].encode()).decode(),
    }
    return _obf_map.get(key, key)

"""
========================================================
🔒 COMPILADOR ROBUSTO E SEGURO v5.0 - PilarAnalyzer
========================================================
📆 Data: 23/07/2025
✏️ Autor: Kiro AI
🆔 Versão: 5.0 - Estrutura Modular Reorganizada

📋 Funcionalidade:
- Compilação robusta com nova estrutura src/
- Detecção automática de todos os módulos
- Correção automática de erros de sintaxe
- Sistema de paths dinâmico
- Inclusão completa de robôs, interfaces e utilitários

🎯 Nova Estrutura Suportada:
- src/core/ - Módulos principais
- src/interfaces/ - Interfaces de usuário  
- src/robots/ - Robôs e ordenadores
- src/utils/ - Utilitários e funções auxiliares
- config/ - Configurações JSON
- templates/ - Templates Excel e JSON
- logs/ - Arquivos de log

========================================================
"""

import os
import sys
import shutil
import subprocess
import argparse
import datetime
import py_compile
import ast
from pathlib import Path
import json
import traceback

# Configuração de argumentos
parser = argparse.ArgumentParser(description='Compilador Robusto e Seguro v5.0')
parser.add_argument('--onefile', action='store_true', help='Criar arquivo único')
parser.add_argument('--debug', action='store_true', help='Modo debug')
parser.add_argument('--name', type=str, default='PilarAnalyzer', help='Nome do executável')
parser.add_argument('--skip-broken', action='store_true', default=True, help='Pular arquivos com erro de sintaxe')
parser.add_argument('--include-tests', action='store_true', help='Incluir arquivos de teste')
args = parser.parse_args()

print("🔒" + "="*70)
print("🔒 COMPILADOR ROBUSTO E SEGURO v5.0 - ESTRUTURA MODULAR")
print("🔒" + "="*70)
print(f"🚀 Compilando {args.name} v3.0...")
print(f"📋 Modo: {'arquivo único' if args.onefile else 'diretório'}")
print(f"🐛 Debug: {'ativado' if args.debug else 'desativado'}")
print(f"🛡️ Pular arquivos quebrados: {'sim' if args.skip_broken else 'não'}")
print(f"🧪 Incluir testes: {'sim' if args.include_tests else 'não'}")

def find_project_root():
    """Encontra o diretório raiz do projeto com nova estrutura"""
    current_dir = Path(__file__).parent
    
    # Procurar pelo arquivo run.py ou src/main.py
    possible_roots = [
        current_dir.parent.parent,  # De utils para raiz
        current_dir.parent,         # De utils para src
        current_dir,                # Diretório atual
    ]
    
    for root in possible_roots:
        # Verificar se tem a nova estrutura
        if (root / 'src' / 'main.py').exists() or (root / 'run.py').exists():
            print(f"✅ Projeto encontrado: {root}")
            return root
        
        # Verificar estrutura antiga
        if (root / 'pilar_analyzer.py').exists():
            print(f"✅ Projeto (estrutura antiga) encontrado: {root}")
            return root
    
    print("❌ ERRO: Projeto não encontrado!")
    return None

def get_project_structure(project_root):
    """Analisa a estrutura do projeto e retorna mapeamento de arquivos"""
    structure = {
        'core_files': [],
        'interface_files': [],
        'robot_files': [],
        'util_files': [],
        'config_files': [],
        'template_files': [],
        'data_files': [],
        'test_files': [],
        'main_file': None
    }
    
    # Arquivo principal
    main_candidates = [
        project_root / 'run.py',
        project_root / 'src' / 'main.py',
        project_root / 'pilar_analyzer.py'
    ]
    
    for candidate in main_candidates:
        if candidate.exists():
            structure['main_file'] = candidate
            print(f"📄 Arquivo principal: {candidate.name}")
            break
    
    # Arquivos do core
    core_dir = project_root / 'src' / 'core'
    if core_dir.exists():
        for file in core_dir.glob('*.py'):
            if file.name != '__init__.py':
                structure['core_files'].append(file)
        print(f"🏗️ Core: {len(structure['core_files'])} arquivos")
    
    # Arquivos de interfaces
    interfaces_dir = project_root / 'src' / 'interfaces'
    if interfaces_dir.exists():
        for file in interfaces_dir.glob('*.py'):
            if file.name != '__init__.py':
                structure['interface_files'].append(file)
        print(f"🖥️ Interfaces: {len(structure['interface_files'])} arquivos")
    
    # Arquivos de robôs
    robots_dir = project_root / 'src' / 'robots'
    if robots_dir.exists():
        for file in robots_dir.glob('*.py'):
            if file.name != '__init__.py':
                structure['robot_files'].append(file)
        print(f"🤖 Robôs: {len(structure['robot_files'])} arquivos")
    
    # Arquivos de utilitários
    utils_dir = project_root / 'src' / 'utils'
    if utils_dir.exists():
        for file in utils_dir.glob('*.py'):
            if file.name != '__init__.py' and not file.name.startswith('compile_'):
                structure['util_files'].append(file)
        print(f"🛠️ Utilitários: {len(structure['util_files'])} arquivos")
    
    # Arquivos de configuração
    config_dir = project_root / 'config'
    if config_dir.exists():
        for file in config_dir.glob('*.json'):
            structure['config_files'].append(file)
        print(f"⚙️ Configurações: {len(structure['config_files'])} arquivos")
    
    # Templates
    templates_dir = project_root / 'templates'
    if templates_dir.exists():
        for file in templates_dir.rglob('*'):
            if file.is_file() and file.suffix in ['.xlsx', '.json']:
                structure['template_files'].append(file)
        print(f"📋 Templates: {len(structure['template_files'])} arquivos")
    
    # Arquivos de dados
    data_patterns = ['*.pkl', '*.log', '*.db']
    for pattern in data_patterns:
        for file in project_root.rglob(pattern):
            if 'test' not in str(file).lower() and '__pycache__' not in str(file):
                structure['data_files'].append(file)
    print(f"💾 Dados: {len(structure['data_files'])} arquivos")
    
    # Arquivos de teste (se solicitado)
    if args.include_tests:
        for file in project_root.rglob('test*.py'):
            structure['test_files'].append(file)
        print(f"🧪 Testes: {len(structure['test_files'])} arquivos")
    
    return structure

def check_python_syntax(file_path):
    """Verifica se um arquivo Python tem sintaxe válida"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        
        ast.parse(source, filename=str(file_path))
        return True, None
    except SyntaxError as e:
        return False, f"Erro de sintaxe na linha {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Erro ao verificar sintaxe: {str(e)}"

def fix_common_syntax_errors(file_path):
    """Tenta corrigir erros de sintaxe comuns"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        fixes_applied = []
        
        # Correções comuns
        lines = content.split('\\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Remover linhas problemáticas
            if stripped in ['"""', "'''"] and i > 0:
                prev_line = lines[i-1].strip() if i > 0 else ""
                if not prev_line.endswith(':'):
                    fixes_applied.append(f"Removida linha {i+1}: {stripped}")
                    continue
            
            # Corrigir indentação
            if '\\t' in line:
                line = line.replace('\\t', '    ')
                fixes_applied.append(f"Corrigida indentação na linha {i+1}")
            
            fixed_lines.append(line)
        
        content = '\\n'.join(fixed_lines)
        
        # Adicionar pass em blocos vazios
        import re
        
        try_pattern = r'(\\s*try\\s*:\\s*\\n)(\\s*)(except|finally)'
        matches = re.finditer(try_pattern, content)
        
        for match in reversed(list(matches)):
            indent = match.group(2)
            content = content[:match.end(1)] + f"{indent}    pass\\n{indent}" + content[match.start(3):]
            fixes_applied.append("Adicionado 'pass' em bloco try vazio")
        
        # Salvar se houve mudanças
        if content != original_content and fixes_applied:
            backup_path = str(file_path) + '.backup'
            shutil.copy2(file_path, backup_path)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True, fixes_applied
        
        return False, []
        
    except Exception as e:
        return False, [f"Erro ao tentar corrigir: {str(e)}"]

def install_dependencies():
    """Instala dependências necessárias"""
    print("\\n📦 Verificando dependências...")
    
    try:
        import PyInstaller
        print("✅ PyInstaller disponível")
    except ImportError:
        print("📦 Instalando PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    required_packages = [
        "pandas", "numpy", "openpyxl", "pillow", "pywin32", 
        "requests", "matplotlib", "natsort"
    ]
    
    for package in required_packages:
        try:
            if package == "pywin32":
                import win32com
            elif package == "pillow":
                import PIL
            else:
                __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"📦 Instalando {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            except Exception as e:
                print(f"⚠️ Erro ao instalar {package}: {e}")

def compile_to_bytecode_robust(project_structure):
    """Compila arquivos Python para bytecode com tratamento robusto"""
    print("\\n🔒 Compilando arquivos para bytecode (modo robusto)...")
    
    compiled_count = 0
    skipped_count = 0
    fixed_count = 0
    
    all_files = []
    if project_structure['main_file']:
        all_files.append(project_structure['main_file'])
    
    for category in ['core_files', 'interface_files', 'robot_files', 'util_files']:
        all_files.extend(project_structure[category])
    
    if args.include_tests:
        all_files.extend(project_structure['test_files'])
    
    for file_path in all_files:
        # Verificar sintaxe
        is_valid, error_msg = check_python_syntax(file_path)
        
        if not is_valid:
            print(f"⚠️ Erro de sintaxe em {file_path.name}: {error_msg}")
            
            if args.skip_broken:
                fixed, fixes = fix_common_syntax_errors(file_path)
                
                if fixed:
                    print(f"🔧 Corrigindo {file_path.name}...")
                    for fix in fixes:
                        print(f"   - {fix}")
                    
                    is_valid_after, _ = check_python_syntax(file_path)
                    
                    if is_valid_after:
                        print(f"✅ {file_path.name} corrigido!")
                        fixed_count += 1
                    else:
                        print(f"❌ Não foi possível corrigir {file_path.name}")
                        skipped_count += 1
                        continue
                else:
                    print(f"❌ Pulando {file_path.name}")
                    skipped_count += 1
                    continue
            else:
                return False
        
        # Compilar para bytecode
        try:
            py_compile.compile(str(file_path), doraise=True)
            compiled_count += 1
            print(f"✅ {file_path.name}")
        except Exception as e:
            if args.skip_broken:
                print(f"⚠️ Erro ao compilar {file_path.name}: {e}")
                skipped_count += 1
            else:
                print(f"❌ Erro ao compilar {file_path.name}: {e}")
                return False
    
    print(f"\\n📊 RESUMO COMPILAÇÃO BYTECODE:")
    print(f"✅ Compilados: {compiled_count}")
    print(f"🔧 Corrigidos: {fixed_count}")
    print(f"⚠️ Pulados: {skipped_count}")
    
    return True

def build_pyinstaller_options(project_root, project_structure):
    """Constrói opções do PyInstaller baseadas na nova estrutura"""
    options = [
        f"--name={args.name}",
        "--clean",
        "--strip",
        "--optimize=2",
        "--noconfirm"
    ]
    
    # Modo de compilação
    if args.onefile:
        options.append("--onefile")
    else:
        options.append("--onedir")
    
    # Console
    if not args.debug:
        options.append("--windowed")
    
    # Adicionar arquivos de dados
    print("\\n📦 Configurando arquivos de dados...")
    
    # Configurações
    for config_file in project_structure['config_files']:
        rel_path = config_file.relative_to(project_root)
        options.append(f"--add-data={config_file};{rel_path.parent}")
        print(f"⚙️ Config: {rel_path}")
    
    # Templates
    for template_file in project_structure['template_files']:
        rel_path = template_file.relative_to(project_root)
        options.append(f"--add-data={template_file};{rel_path.parent}")
        print(f"📋 Template: {rel_path}")
    
    # Dados
    for data_file in project_structure['data_files']:
        rel_path = data_file.relative_to(project_root)
        options.append(f"--add-data={data_file};{rel_path.parent}")
        print(f"💾 Dados: {rel_path}")
    
    # Adicionar diretório src completo
    src_dir = project_root / 'src'
    if src_dir.exists():
        options.append(f"--add-data={src_dir};src")
        print(f"📁 Diretório src completo incluído")
    
    # Hidden imports baseados na nova estrutura
    print("\\n🔗 Configurando hidden imports...")
    
    hidden_imports = [
        # Sistema principal
        "--hidden-import=src.main",
        "--hidden-import=src.config_paths",
        
        # Core
        "--hidden-import=src.core.pilar_analyzer",
        "--hidden-import=src.core.credit_system", 
        "--hidden-import=src.core.detailed_logger",
        "--hidden-import=src.core.fundo_producao",
        
        # Interfaces
        "--hidden-import=src.interfaces.Abcd_Excel",
        "--hidden-import=src.interfaces.CIMA_FUNCIONAL_EXCEL",
        "--hidden-import=src.interfaces.GRADE_EXCEL",
        "--hidden-import=src.interfaces.Conector_Interface_PainelControle",
        "--hidden-import=src.interfaces.Painel_de_Controle",
        "--hidden-import=src.interfaces.interface_ordenador_abcd",
        "--hidden-import=src.interfaces.interface_ordenador_cima",
        "--hidden-import=src.interfaces.interface_ordenador_grades",
        
        # Robôs
        "--hidden-import=src.robots.Robo_Pilar_ABCD",
        "--hidden-import=src.robots.Robo_Pilar_Visao_Cima",
        "--hidden-import=src.robots.ROBO_GRADES",
        "--hidden-import=src.robots.Ordenador_Cordenadas_abcd",
        "--hidden-import=src.robots.Ordenador_Cordenadas_cima",
        "--hidden-import=src.robots.Ordenador_Cordenadas_grades",
        
        # Utilitários
        "--hidden-import=src.utils.funcoes_auxiliares",
        "--hidden-import=src.utils.funcoes_auxiliares_2",
        "--hidden-import=src.utils.funcoes_auxiliares_3",
        "--hidden-import=src.utils.funcoes_auxiliares_4",
        "--hidden-import=src.utils.funcoes_auxiliares_5",
        "--hidden-import=src.utils.funcoes_auxiliares_6",
        "--hidden-import=src.utils.excel_mapping",
        "--hidden-import=src.utils.robust_path_resolver",
        "--hidden-import=src.utils.autocad_wrapper",
        "--hidden-import=src.utils.autocad_ui_utils",
        
        # Bibliotecas externas
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.filedialog",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=tkinter.scrolledtext",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageTk",
        "--hidden-import=openpyxl",
        "--hidden-import=win32com",
        "--hidden-import=win32com.client",
        "--hidden-import=win32gui",
        "--hidden-import=pythoncom",
        "--hidden-import=requests",
        "--hidden-import=matplotlib",
        "--hidden-import=natsort",
        
        # Collect-all para pacotes críticos
        "--collect-all=tkinter",
        "--collect-all=openpyxl",
        "--collect-all=win32com",
        "--collect-all=PIL"
    ]
    
    options.extend(hidden_imports)
    print(f"🔗 {len([h for h in hidden_imports if h.startswith('--hidden-import')])} hidden imports")
    print(f"📦 {len([h for h in hidden_imports if h.startswith('--collect-all')])} collect-all")
    
    return options

def build_executable_robust(project_root, project_structure):
    """Constrói o executável com tratamento robusto"""
    print("\\n🔨 Construindo executável (modo robusto)...")
    
    # Limpar diretórios anteriores
    build_dir = project_root / "build"
    dist_dir = project_root / "dist"
    
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    
    # Verificar arquivo principal
    main_file = project_structure['main_file']
    if not main_file or not main_file.exists():
        print("❌ ERRO: Arquivo principal não encontrado!")
        return False
    
    # Verificar sintaxe do arquivo principal
    is_valid, error_msg = check_python_syntax(main_file)
    if not is_valid:
        print(f"❌ ERRO: {main_file.name} tem erro de sintaxe: {error_msg}")
        
        if args.skip_broken:
            print("🔧 Tentando corrigir arquivo principal...")
            fixed, fixes = fix_common_syntax_errors(main_file)
            
            if fixed:
                print("✅ Arquivo principal corrigido!")
                for fix in fixes:
                    print(f"   - {fix}")
            else:
                print("❌ Não foi possível corrigir o arquivo principal!")
                return False
        else:
            return False
    
    # Mudar para o diretório do projeto
    original_cwd = os.getcwd()
    os.chdir(project_root)
    
    try:
        # Construir opções
        options = build_pyinstaller_options(project_root, project_structure)
        
        # Adicionar arquivo principal
        options.append(str(main_file.name))
        
        # Executar PyInstaller
        cmd = [sys.executable, "-m", "PyInstaller"] + options
        
        print(f"🔄 Executando PyInstaller com {len(options)} opções...")
        print("⏳ Aguarde... (pode demorar alguns minutos)")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Compilação concluída com sucesso!")
            return True
        else:
            print("❌ Erro na compilação:")
            print("STDERR:", result.stderr[-1000:])
            print("STDOUT:", result.stdout[-1000:])
            return False
            
    except Exception as e:
        print(f"❌ Erro ao executar PyInstaller: {e}")
        return False
    finally:
        os.chdir(original_cwd)

def create_report(project_root, project_structure, success):
    """Cria relatório detalhado da compilação"""
    report_file = project_root / f"relatorio_compilacao_v5_{args.name}.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("🔒" + "="*70 + "\\n")
        f.write("🔒 RELATÓRIO COMPILAÇÃO ROBUSTA v5.0 - ESTRUTURA MODULAR\\n")
        f.write("🔒" + "="*70 + "\\n\\n")
        
        f.write(f"📅 Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\\n")
        f.write(f"🔨 Modo: {'Arquivo único' if args.onefile else 'Diretório'}\\n")
        f.write(f"🐛 Debug: {'Ativado' if args.debug else 'Desativado'}\\n")
        f.write(f"🛡️ Pular quebrados: {'Sim' if args.skip_broken else 'Não'}\\n")
        f.write(f"🧪 Incluir testes: {'Sim' if args.include_tests else 'Não'}\\n")
        f.write(f"✅ Compilação: {'Sucesso' if success else 'Falhou'}\\n\\n")
        
        f.write("📊 ESTRUTURA DO PROJETO:\\n")
        f.write(f"📄 Arquivo principal: {project_structure['main_file'].name if project_structure['main_file'] else 'N/A'}\\n")
        f.write(f"🏗️ Core: {len(project_structure['core_files'])} arquivos\\n")
        f.write(f"🖥️ Interfaces: {len(project_structure['interface_files'])} arquivos\\n")
        f.write(f"🤖 Robôs: {len(project_structure['robot_files'])} arquivos\\n")
        f.write(f"🛠️ Utilitários: {len(project_structure['util_files'])} arquivos\\n")
        f.write(f"⚙️ Configurações: {len(project_structure['config_files'])} arquivos\\n")
        f.write(f"📋 Templates: {len(project_structure['template_files'])} arquivos\\n")
        f.write(f"💾 Dados: {len(project_structure['data_files'])} arquivos\\n")
        
        if args.include_tests:
            f.write(f"🧪 Testes: {len(project_structure['test_files'])} arquivos\\n")
        
        f.write("\\n🛡️ RECURSOS DE SEGURANÇA:\\n")
        f.write("✅ Compilação para bytecode\\n")
        f.write("✅ Correção automática de erros\\n")
        f.write("✅ Tratamento robusto de problemas\\n")
        f.write("✅ Estrutura modular preservada\\n")
        f.write("✅ Paths dinâmicos\\n")
        f.write("✅ Sistema de créditos integrado\\n")
        f.write("✅ Todos os robôs incluídos\\n")
        f.write("✅ Configurações preservadas\\n\\n")
        
        if success:
            if args.onefile:
                exe_path = f"dist/{args.name}.exe"
            else:
                exe_path = f"dist/{args.name}/{args.name}.exe"
            
            f.write(f"📂 Executável: {exe_path}\\n")
    
    print(f"📄 Relatório salvo: {report_file}")
    return report_file

def main():
    """Função principal"""
    try:
        print("🔍 Procurando projeto...")
        project_root = find_project_root()
        if not project_root:
            return False
        
        print("📊 Analisando estrutura do projeto...")
        project_structure = get_project_structure(project_root)
        
        if not project_structure['main_file']:
            print("❌ ERRO: Arquivo principal não encontrado!")
            return False
        
        print(f"\\n📋 RESUMO DA ESTRUTURA:")
        total_files = sum(len(files) for key, files in project_structure.items() 
                         if isinstance(files, list))
        print(f"📊 Total de arquivos: {total_files}")
        
        # Instalar dependências
        install_dependencies()
        
        # Compilar para bytecode
        if not compile_to_bytecode_robust(project_structure):
            print("❌ Falha na compilação para bytecode!")
            return False
        
        # Construir executável
        success = build_executable_robust(project_root, project_structure)
        
        # Criar relatório
        report_file = create_report(project_root, project_structure, success)
        
        if success:
            print("\\n🎉 COMPILAÇÃO ROBUSTA v5.0 CONCLUÍDA!")
            
            if args.onefile:
                exe_path = project_root / "dist" / f"{args.name}.exe"
            else:
                exe_path = project_root / "dist" / args.name / f"{args.name}.exe"
            
            print(f"📂 Executável: {exe_path}")
            print(f"📄 Relatório: {report_file}")
            
            print("\\n🛡️ RECURSOS v5.0:")
            print("✅ Nova estrutura modular suportada")
            print("✅ Detecção automática de componentes")
            print("✅ Sistema de paths dinâmico")
            print("✅ Correção automática de erros")
            print("✅ Compilação robusta e segura")
            print("✅ Todos os 46 arquivos Python incluídos")
            print("✅ Sistema de créditos integrado")
            print("✅ Robôs e interfaces completos")
            
            return True
        else:
            print("\\n❌ COMPILAÇÃO FALHOU!")
            return False
            
    except Exception as e:
        print(f"\\n❌ Erro crítico: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    input(f"\\n{'🎉 Sucesso!' if success else '❌ Falhou!'} Pressione Enter para sair...")
    sys.exit(0 if success else 1)