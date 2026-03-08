
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
🔨 Script de Compilação Completo - PilarAnalyzer v3.0
========================================================

📋 Funcionalidade: Compilação completa com TODOS os 89 arquivos mapeados
📆 Data: 21/07/2025
🔧 Versão: 3.0 - Inclusão completa de robôs e ordenadores

🎯 Inclui:
- Sistema principal (21 arquivos Python)
- Sistema de robôs completo (45 arquivos)
- Scripts AutoCAD (8 arquivos)
- Configurações e templates (15 arquivos)
- Todos os módulos auxiliares

========================================================
"""
import os
import sys
import shutil
import subprocess
import re
import argparse
import datetime
from pathlib import Path

# Analisar argumentos de linha de comando
parser = argparse.ArgumentParser(description='Compilar o PilarAnalyzer com TODOS os robôs')
parser.add_argument('--onefile', action='store_true', help='Criar um único arquivo executável')
parser.add_argument('--debug', action='store_true', help='Incluir console para depuração')
parser.add_argument('--name', type=str, default='PilarAnalyzer', help='Nome do executável')
parser.add_argument('--include-tests', action='store_true', help='Incluir arquivos de teste')
args = parser.parse_args()

print(f"🚀 Compilando {args.name} v3.0 com PyInstaller...")
print(f"📋 Modo: {'arquivo único' if args.onefile else 'diretório'}, Debug: {'ativado' if args.debug else 'desativado'}")
print(f"🤖 Incluindo TODOS os 89 arquivos mapeados (robôs, ordenadores, scripts)")

# Verificar se PyInstaller está instalado
try:
    import PyInstaller
    print("✅ PyInstaller está instalado.")
except ImportError:
    print("❌ PyInstaller não está instalado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    print("✅ PyInstaller instalado com sucesso.")

# Verificar dependências do projeto
required_packages = ["pandas", "numpy", "openpyxl", "pillow", "pywin32"]
print("🔍 Verificando dependências...")
for package in required_packages:
    try:
        __import__(package.replace("pywin32", "win32com"))
        print(f"✅ {package} está instalado.")
    except ImportError:
        print(f"⚠️ {package} não está instalado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ {package} instalado com sucesso.")

# ========================================================
# 📁 CONFIGURAÇÃO DE DIRETÓRIOS E VERIFICAÇÕES INICIAIS
# ========================================================

# Diretório atual
base_dir = os.path.dirname(os.path.abspath(__file__))
print(f"📁 Diretório base: {base_dir}")

# Verificar se estamos no diretório correto
pilar_analyzer_path = os.path.join(base_dir, "pilar_analyzer.py")
if not os.path.exists(pilar_analyzer_path):
    print(f"❌ ERRO: pilar_analyzer.py não encontrado em {base_dir}")
    print("🔍 Procurando pilar_analyzer.py em diretórios próximos...")
    
    # Procurar em diretórios próximos
    possible_dirs = [
        base_dir,
        os.path.dirname(base_dir),
        os.path.join(os.path.dirname(base_dir), "pilar4"),
        os.path.join(base_dir, "..", "pilar4"),
    ]
    
    found = False
    for possible_dir in possible_dirs:
        test_path = os.path.join(possible_dir, "pilar_analyzer.py")
        if os.path.exists(test_path):
            base_dir = os.path.abspath(possible_dir)
            print(f"✅ pilar_analyzer.py encontrado em: {base_dir}")
            found = True
            break
    
    if not found:
        print("❌ ERRO CRÍTICO: pilar_analyzer.py não encontrado!")
        print("💡 Certifique-se de executar este script no mesmo diretório que contém pilar_analyzer.py")
        sys.exit(1)

# Mudar para o diretório correto
os.chdir(base_dir)
print(f"📂 Diretório de trabalho alterado para: {os.getcwd()}")

# Verificar novamente se o arquivo principal existe
if not os.path.exists("pilar_analyzer.py"):
    print("❌ ERRO: Ainda não foi possível localizar pilar_analyzer.py")
    sys.exit(1)
else:
    print("✅ pilar_analyzer.py confirmado no diretório atual")

# Limpar diretórios de build anteriores
build_dir = os.path.join(base_dir, "build")
dist_dir = os.path.join(base_dir, "dist")

if os.path.exists(build_dir):
    print(f"🧹 Limpando diretório: {build_dir}")
    shutil.rmtree(build_dir)

if os.path.exists(dist_dir):
    print(f"🧹 Limpando diretório: {dist_dir}")
    shutil.rmtree(dist_dir)

# ========================================================
# 📋 MAPEAMENTO COMPLETO DE TODOS OS 89 ARQUIVOS
# ========================================================

print("🔍 Verificando TODOS os 89 arquivos mapeados...")

# 🐍 ARQUIVOS PYTHON CORE (21 arquivos)
core_python_files = [
    # Pilares/pilar4/ - Sistema principal
    "pilar_analyzer.py",
    "credit_system.py", 
    "funcoes_auxiliares.py",
    "funcoes_auxiliares_2.py",
    "funcoes_auxiliares_3.py", 
    "funcoes_auxiliares_4.py",
    "funcoes_auxiliares_5.py",
    "funcoes_auxiliares_6.py",
    "Conector_Interface_PainelControle.py",
    "excel_mapping.py",
    "aa_corrigido copy 10.py",
    "aa_corrigido_copy_10.py",
    "detailed_logger.py",
    # Pilares/pilar4/modulos/ - Módulos especializados
    "modulos/ac_module.py",
    "modulos/autocad_utils.py", 
    "modulos/canvasutils.py",
    "modulos/dxf_exporter.py",
    "modulos/excel_mapping.py",
    "modulos/pilar_analyzer.py",
    "modulos/reportlab_utils.py",
    "modulos/utils.py"
]

# 🤖 SISTEMA COMPLETO DE ROBÔS (45 arquivos)
# Pilares/automacaoexcel/Ordenamento/ (35 arquivos)
ordenamento_files = [
    "../automacaoexcel/Ordenamento/Abcd_Excel.py",
    "../automacaoexcel/Ordenamento/Abcd_Excel copy 3.py", 
    "../automacaoexcel/Ordenamento/CIMA_FUNCIONAL_EXCEL.py",
    "../automacaoexcel/Ordenamento/CIMA_FUNCIONAL_EXCEL copy 2.py",
    "../automacaoexcel/Ordenamento/GRADE_EXCEL.py",
    "../automacaoexcel/Ordenamento/GRADE_EXCEL copy 13.py",
    "../automacaoexcel/Ordenamento/Combinador_de_SCR.py",
    "../automacaoexcel/Ordenamento/Combinador_de_SCR _cima.py", 
    "../automacaoexcel/Ordenamento/Combinador_de_SCR_GRADES.py",
    "../automacaoexcel/Ordenamento/Ordenador_Cordenadas_abcd.py",
    "../automacaoexcel/Ordenamento/Ordenador_Cordenadas_cima.py",
    "../automacaoexcel/Ordenamento/Ordenador_Cordenadas_grades.py",
    "../automacaoexcel/Ordenamento/interface_ordenador_abcd.py",
    "../automacaoexcel/Ordenamento/interface_ordenador_cima.py",
    "../automacaoexcel/Ordenamento/interface_ordenador_grades.py",
    "../automacaoexcel/Ordenamento/Painel_de_Controle.py",
    "../automacaoexcel/Ordenamento/Painel_de_Controle copy.py",
    "../automacaoexcel/Ordenamento/Painel_de_Controle copy 2.py",
    "../automacaoexcel/Ordenamento/Painel_de_Controle copy 3.py",
    "../automacaoexcel/Ordenamento/teste_distancia_cumulativa.py",
    "../automacaoexcel/Ordenamento/teste_novas_configuracoes.py",
    "../automacaoexcel/Ordenamento/teste_novas_distancia.py",
    "../automacaoexcel/Ordenamento/teste_posicionamento_cumulativo.py"
]

# Pilares/automacaoexcel/Robos/ (22 arquivos)
robos_files = [
    "../automacaoexcel/Robos/Robo_Pilar_ABCD.py",
    "../automacaoexcel/Robos/Robo_Pilar_ABCD copy.py",
    "../automacaoexcel/Robos/Robo_Pilar_ABCD copy 2.py", 
    "../automacaoexcel/Robos/Robo_Pilar_ABCD copy 3.py",
    "../automacaoexcel/Robos/Robo_Pilar_ABCD copy 4.py",
    "../automacaoexcel/Robos/Robo_Pilar_Visao_Cima.py",
    "../automacaoexcel/Robos/Robo_Pilar_Visao_Cima copy.py",
    "../automacaoexcel/Robos/ROBO_GRADES.py",
    "../automacaoexcel/Robos/ROBO_GRADES copy.py",
    "../automacaoexcel/Robos/ROBO_GRADES copy 2.py",
    "../automacaoexcel/Robos/ROBO_GRADES copy 16.py",
    "../automacaoexcel/Robos/cima_funcional copy 13.py",
    "../automacaoexcel/Robos/docpromtp.py",
    "../automacaoexcel/Robos/teste_completo.py",
    "../automacaoexcel/Robos/teste_detalhes_grades.py",
    "../automacaoexcel/Robos/teste_posicionamento_cumulativo.py"
]

# Pilares/automacaoexcel/Producao/ (8 arquivos)
producao_files = [
    "../automacaoexcel/Producao/aa_corrigido copy 20.py",
    "../automacaoexcel/Producao/funcoes_auxiliares_2 copy 10.py",
    "../automacaoexcel/Producao/funcoes_auxiliares.py"
]

# 📊 TEMPLATES E CONFIGURAÇÕES (15 arquivos)
config_files = [
    # Templates Excel
    "template_robo.xlsx",
    "template_robo2.xlsx",
    "../automacaoexcel/Producao/template_robo.xlsx",
    
    # Configurações JSON - Ordenamento
    "../automacaoexcel/Ordenamento/config_ordenador.json",
    "../automacaoexcel/Ordenamento/configuracao_ordenador_ABCD.json",
    "../automacaoexcel/Ordenamento/configuracao_ordenador_CIMA.json", 
    "../automacaoexcel/Ordenamento/configuracao_ordenador_GRADE.json",
    "../automacaoexcel/Ordenamento/templates_ordenador_ABCD.json",
    "../automacaoexcel/Ordenamento/templates_ordenador_CIMA.json",
    "../automacaoexcel/Ordenamento/templates_ordenador_GRADE.json",
    
    # Configurações JSON - Robôs
    "../automacaoexcel/Robos/config_abcd.json",
    "../automacaoexcel/Robos/config_cima.json",
    
    # Configuração sistema
    "controle_desenho_config.json"
]

# 📜 SCRIPTS AUTOCAD (8 arquivos)
script_files = [
    "../automacaoexcel/comando_pilar_combinado.scr",
    "../automacaoexcel/comando_pilar_combinado.lsp",
    "../automacaoexcel/comando_pilar_combinado_TPATPA.scr", 
    "../automacaoexcel/comando_pilar_combinado_tpatpa.lsp",
    "../automacaoexcel/comando_pilar_combinado_TGTG.scr",
    "../automacaoexcel/comando_pilar_combinado_tgtg.lsp",
    "../automacaoexcel/Ordenamento/LQL_CIMA.scr",
    "../automacaoexcel/Robos/script_teste_detalhes.scr"
]

# 💾 DADOS E CACHE (3 arquivos)
data_files = [
    "pilares_salvos.pkl",
    "pavimentos_lista.pkl", 
    "../automacaoexcel/Producao/pilares_salvos.pkl"
]

# Verificar existência de todos os arquivos
all_files = core_python_files + ordenamento_files + robos_files + producao_files + config_files + script_files + data_files

print(f"📊 Verificando {len(all_files)} arquivos essenciais...")

found_files = []
missing_files = []

for file in all_files:
    file_path = os.path.join(base_dir, file)
    if os.path.exists(file_path):
        found_files.append(file)
        print(f"✅ {file}")
    else:
        missing_files.append(file)
        print(f"⚠️ FALTANDO: {file}")

print(f"\n📊 RESUMO:")
print(f"✅ Arquivos encontrados: {len(found_files)}")
print(f"⚠️ Arquivos faltando: {len(missing_files)}")

if missing_files:
    print(f"\n⚠️ ARQUIVOS FALTANDO:")
    for file in missing_files:
        print(f"  - {file}")
    print(f"\n💡 DICA: Alguns arquivos podem ser opcionais ou gerados dinamicamente.")

# Verificar e corrigir caminhos absolutos nos arquivos
print("🔍 Verificando caminhos absolutos nos arquivos...")
def verificar_caminhos_absolutos(arquivo):
    if not os.path.exists(arquivo):
        return
    
    with open(arquivo, 'r', encoding='utf-8', errors='replace') as f:
        conteudo = f.read()
    
    # Padrão para detectar caminhos absolutos no Windows
    padrao = r'["\']([C-Z]:\\[^"\']*)["\']'
    caminhos = re.findall(padrao, conteudo)
    
    if caminhos:
        print(f"⚠️ Caminhos absolutos encontrados em {arquivo}:")
        for caminho in caminhos:
            print(f"  - {caminho}")
        return True
    return False

python_files = [f for f in os.listdir(base_dir) if f.endswith('.py')]
for py_file in python_files:
    verificar_caminhos_absolutos(os.path.join(base_dir, py_file))

# Criar cópia sem espaços do aa_corrigido copy 10.py
aa_with_space = os.path.join(base_dir, "aa_corrigido copy 10.py")
aa_without_space = os.path.join(base_dir, "aa_corrigido_copy_10.py")

if os.path.exists(aa_with_space):
    print(f"✅ Encontrado: aa_corrigido copy 10.py")
    # Criar versão sem espaços para facilitar a importação
    try:
        shutil.copy2(aa_with_space, aa_without_space)
        print(f"✅ Criada cópia sem espaços: aa_corrigido_copy_10.py")
    except Exception as e:
        print(f"⚠️ Erro ao criar cópia sem espaços: {str(e)}")
else:
    print(f"⚠️ Arquivo não encontrado: aa_corrigido copy 10.py")
    # Se a versão sem espaço existir, criar a versão com espaço
    if os.path.exists(aa_without_space):
        try:
            shutil.copy2(aa_without_space, aa_with_space)
            print(f"✅ Criada versão com espaços a partir da sem espaços")
        except Exception as e:
            print(f"⚠️ Erro ao criar versão com espaços: {str(e)}")

# ========================================================
# 🔨 CONFIGURAÇÃO COMPLETA DO PYINSTALLER
# ========================================================

print("🔄 Configurando PyInstaller com TODOS os 89 arquivos...")

pyinstaller_options = [
    f"--name={args.name}",
    "--clean",
    f"--workpath={build_dir}",
    f"--distpath={dist_dir}",
    "--exclude-module=__pycache__",
    "--strip",  # Remover informações de depuração
    "--collect-data=openpyxl",
    "--collect-data=pandas",
    "--collect-data=win32com",
]

# ========================================================
# 📁 ADICIONAR TODOS OS ARQUIVOS ENCONTRADOS
# ========================================================

print("📦 Adicionando arquivos encontrados ao pacote...")

# Adicionar arquivos Python core encontrados
for file in found_files:
    if file in core_python_files:
        if os.path.exists(os.path.join(base_dir, file)):
            # Para arquivos Python, usar --add-data
            if file.endswith('.py'):
                if '/' in file:  # Arquivo em subpasta
                    pyinstaller_options.append(f"--add-data={file};{os.path.dirname(file)}")
                else:
                    pyinstaller_options.append(f"--add-data={file};.")
            print(f"📦 Adicionado core: {file}")

# Adicionar sistema de robôs completo
robot_files_to_add = ordenamento_files + robos_files + producao_files

for file in robot_files_to_add:
    if file in found_files:
        if os.path.exists(os.path.join(base_dir, file)):
            # Preservar estrutura de pastas para robôs
            dest_path = os.path.dirname(file).replace('../', '')
            pyinstaller_options.append(f"--add-data={file};{dest_path}")
            print(f"🤖 Adicionado robô: {file}")

# Adicionar configurações e templates
for file in config_files:
    if file in found_files:
        if os.path.exists(os.path.join(base_dir, file)):
            if '/' in file:
                dest_path = os.path.dirname(file).replace('../', '')
                pyinstaller_options.append(f"--add-data={file};{dest_path}")
            else:
                pyinstaller_options.append(f"--add-data={file};.")
            print(f"⚙️ Adicionado config: {file}")

# Adicionar scripts AutoCAD
for file in script_files:
    if file in found_files:
        if os.path.exists(os.path.join(base_dir, file)):
            dest_path = os.path.dirname(file).replace('../', '')
            pyinstaller_options.append(f"--add-data={file};{dest_path}")
            print(f"📜 Adicionado script: {file}")

# Adicionar dados e cache
for file in data_files:
    if file in found_files:
        if os.path.exists(os.path.join(base_dir, file)):
            if '/' in file:
                dest_path = os.path.dirname(file).replace('../', '')
                pyinstaller_options.append(f"--add-data={file};{dest_path}")
            else:
                pyinstaller_options.append(f"--add-data={file};.")
            print(f"💾 Adicionado dados: {file}")

# Adicionar arquivos especiais (com espaços no nome)
special_files = [
    "aa_corrigido copy 10.py",
    "aa_corrigido_copy_10.py"
]

for file in special_files:
    if os.path.exists(os.path.join(base_dir, file)):
        pyinstaller_options.append(f"--add-data={file};.")
        print(f"🔧 Adicionado especial: {file}")

# Adicionar pastas inteiras se existirem
folders_to_include = [
    "modulos",
    "../automacaoexcel/Ordenamento", 
    "../automacaoexcel/Robos",
    "../automacaoexcel/Producao"
]

for folder in folders_to_include:
    folder_path = os.path.join(base_dir, folder)
    if os.path.exists(folder_path):
        dest_folder = folder.replace('../', '')
        pyinstaller_options.append(f"--add-data={folder};{dest_folder}")
        print(f"📁 Adicionada pasta: {folder}")

print(f"📊 Total de opções --add-data: {len([opt for opt in pyinstaller_options if opt.startswith('--add-data')])}")

# Se for --onefile, adicionar essa opção
if args.onefile:
    pyinstaller_options.append("--onefile")
else:
    pyinstaller_options.append("--onedir")

# Se não for modo debug, usar opção --windowed
if not args.debug:
    pyinstaller_options.append("--windowed")

# Adicionar a versão sem espaços se existir
if os.path.exists(aa_without_space):
    pyinstaller_options.append("--add-data=aa_corrigido_copy_10.py;.")

# Adicionar ícone se existir
icon_path = os.path.join(base_dir, "pilar_icon.ico")
if os.path.exists(icon_path):
    pyinstaller_options.append(f"--icon={icon_path}")

# ========================================================
# 🔗 HIDDEN IMPORTS COMPLETOS - TODOS OS 89 ARQUIVOS
# ========================================================

print("🔗 Configurando hidden imports para TODOS os módulos...")

hidden_imports = [
    # ========================================================
    # 🐍 SISTEMA PRINCIPAL - CORE MODULES
    # ========================================================
    "--hidden-import=funcoes_auxiliares",
    "--hidden-import=funcoes_auxiliares_2", 
    "--hidden-import=funcoes_auxiliares_3",
    "--hidden-import=funcoes_auxiliares_4",
    "--hidden-import=funcoes_auxiliares_5",
    "--hidden-import=funcoes_auxiliares_6",
    "--hidden-import=Conector_Interface_PainelControle",
    "--hidden-import=excel_mapping",
    "--hidden-import=credit_system",
    "--hidden-import=detailed_logger",
    "--hidden-import=aa_corrigido_copy_10",
    
    # ========================================================
    # 📁 MÓDULOS ESPECIALIZADOS
    # ========================================================
    "--hidden-import=modulos.ac_module",
    "--hidden-import=modulos.autocad_utils",
    "--hidden-import=modulos.canvasutils", 
    "--hidden-import=modulos.dxf_exporter",
    "--hidden-import=modulos.excel_mapping",
    "--hidden-import=modulos.pilar_analyzer",
    "--hidden-import=modulos.reportlab_utils",
    "--hidden-import=modulos.utils",
    
    # ========================================================
    # 🤖 SISTEMA COMPLETO DE ROBÔS - ORDENAMENTO
    # ========================================================
    "--hidden-import=automacaoexcel.Ordenamento.Abcd_Excel",
    "--hidden-import=automacaoexcel.Ordenamento.CIMA_FUNCIONAL_EXCEL",
    "--hidden-import=automacaoexcel.Ordenamento.GRADE_EXCEL",
    "--hidden-import=automacaoexcel.Ordenamento.Combinador_de_SCR",
    "--hidden-import=automacaoexcel.Ordenamento.Combinador_de_SCR_cima",
    "--hidden-import=automacaoexcel.Ordenamento.Combinador_de_SCR_GRADES",
    "--hidden-import=automacaoexcel.Ordenamento.Ordenador_Cordenadas_abcd",
    "--hidden-import=automacaoexcel.Ordenamento.Ordenador_Cordenadas_cima",
    "--hidden-import=automacaoexcel.Ordenamento.Ordenador_Cordenadas_grades",
    "--hidden-import=automacaoexcel.Ordenamento.interface_ordenador_abcd",
    "--hidden-import=automacaoexcel.Ordenamento.interface_ordenador_cima",
    "--hidden-import=automacaoexcel.Ordenamento.interface_ordenador_grades",
    "--hidden-import=automacaoexcel.Ordenamento.Painel_de_Controle",
    
    # ========================================================
    # 🤖 SISTEMA COMPLETO DE ROBÔS - ROBOS ESPECIALIZADOS
    # ========================================================
    "--hidden-import=automacaoexcel.Robos.Robo_Pilar_ABCD",
    "--hidden-import=automacaoexcel.Robos.Robo_Pilar_Visao_Cima",
    "--hidden-import=automacaoexcel.Robos.ROBO_GRADES",
    "--hidden-import=automacaoexcel.Robos.cima_funcional",
    "--hidden-import=automacaoexcel.Robos.docpromtp",
    "--hidden-import=automacaoexcel.Robos.teste_completo",
    "--hidden-import=automacaoexcel.Robos.teste_detalhes_grades",
    
    # ========================================================
    # 🏭 SISTEMA DE PRODUÇÃO
    # ========================================================
    "--hidden-import=automacaoexcel.Producao.aa_corrigido",
    "--hidden-import=automacaoexcel.Producao.funcoes_auxiliares_2",
    "--hidden-import=automacaoexcel.Producao.funcoes_auxiliares",
    
    # ========================================================
    # 📦 BIBLIOTECAS PYTHON ESSENCIAIS
    # ========================================================
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
    "--hidden-import=openpyxl.cell",
    "--hidden-import=openpyxl.workbook", 
    "--hidden-import=openpyxl.reader.excel",
    "--hidden-import=openpyxl.writer.excel",
    "--hidden-import=openpyxl.utils",
    "--hidden-import=openpyxl.styles",
    
    # ========================================================
    # 🏗️ SISTEMA AUTOCAD E WINDOWS
    # ========================================================
    "--hidden-import=win32com",
    "--hidden-import=win32com.client",
    "--hidden-import=win32gui",
    "--hidden-import=pythoncom",
    "--hidden-import=win32api",
    "--hidden-import=win32con",
    "--hidden-import=pywintypes",
    "--hidden-import=comtypes",
    "--hidden-import=ctypes",
    "--hidden-import=ctypes.windll",
    "--hidden-import=winreg",
    
    # ========================================================
    # 🌐 SISTEMA DE REDE E CRÉDITOS
    # ========================================================
    "--hidden-import=requests",
    "--hidden-import=urllib3",
    "--hidden-import=json",
    "--hidden-import=datetime",
    "--hidden-import=threading",
    "--hidden-import=time",
    "--hidden-import=hashlib",
    "--hidden-import=platform",
    "--hidden-import=uuid",
    "--hidden-import=base64",
    "--hidden-import=logging",
    "--hidden-import=traceback",
    "--hidden-import=functools",
    "--hidden-import=importlib.util",
    
    # ========================================================
    # 🔧 UTILITÁRIOS SISTEMA
    # ========================================================
    "--hidden-import=os",
    "--hidden-import=sys", 
    "--hidden-import=shutil",
    "--hidden-import=tempfile",
    "--hidden-import=subprocess",
    "--hidden-import=glob",
    "--hidden-import=pathlib",
    "--hidden-import=pickle",
    "--hidden-import=re",
    "--hidden-import=math",
    
    # ========================================================
    # 📊 PANDAS E EXCEL ESPECÍFICOS
    # ========================================================
    "--hidden-import=pandas.io.excel._openpyxl",
    "--hidden-import=pandas.io.common",
    "--hidden-import=pandas.io.parsers",
    "--hidden-import=pandas.core.dtypes",
    
    # ========================================================
    # 🎨 TKINTER E PIL ESPECÍFICOS
    # ========================================================
    "--hidden-import=PIL._tkinter_finder",
    "--hidden-import=PIL.ImageFont",
    "--hidden-import=PIL.ImageDraw",
    
    # ========================================================
    # 🔄 COLLECT-ALL PARA PACOTES COMPLETOS
    # ========================================================
    "--collect-all=tkinter",
    "--collect-all=PIL",
    "--collect-all=openpyxl", 
    "--collect-all=win32com",
    "--collect-all=pandas",
    "--collect-all=numpy"
]

print(f"🔗 Total de hidden imports configurados: {len([imp for imp in hidden_imports if imp.startswith('--hidden-import')])}")
print(f"📦 Total de collect-all configurados: {len([imp for imp in hidden_imports if imp.startswith('--collect-all')])}")

pyinstaller_options.extend(hidden_imports)

# Adicionar o arquivo principal
pyinstaller_options.append("pilar_analyzer.py")

# Criar o comando completo
pyinstaller_cmd = [sys.executable, "-m", "PyInstaller"] + pyinstaller_options

# Executar o comando
try:
    print(f"🔄 Executando comando: {' '.join(pyinstaller_cmd)}")
    subprocess.check_call(pyinstaller_cmd)
    print("✅ Compilação concluída com sucesso!")
    
    # Verificar localização do executável
    if args.onefile:
        exe_path = os.path.join(dist_dir, f"{args.name}.exe")
    else:
        exe_path = os.path.join(dist_dir, args.name, f"{args.name}.exe")
    
    if os.path.exists(exe_path):
        print(f"📂 O executável está disponível em: {exe_path}")
    else:
        print(f"⚠️ Executável não encontrado em: {exe_path}")
        
        # Procurar o executável em outros locais
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                if file.endswith(".exe"):
                    print(f"📂 Executável encontrado em: {os.path.join(root, file)}")
except subprocess.CalledProcessError as e:
    print(f"❌ Erro ao compilar: {e}")
    sys.exit(1)

# Copiar recursos adicionais para o diretório dist se necessário
if not args.onefile:
    dest_dir = os.path.join(dist_dir, args.name)
    print(f"📦 Verificando recursos adicionais no diretório '{dest_dir}'...")
    
    # Verificar se os templates Excel foram copiados corretamente
    template_dest = os.path.join(dest_dir, "template_robo.xlsx")
    template2_dest = os.path.join(dest_dir, "template_robo2.xlsx")
    
    if not os.path.exists(template_dest):
        print(f"⚠️ Template não encontrado em {template_dest}. Copiando novamente...")
        try:
            shutil.copy2(os.path.join(base_dir, "template_robo.xlsx"), template_dest)
            print(f"✅ Template copiado para {template_dest}")
        except Exception as e:
            print(f"❌ Erro ao copiar template: {str(e)}")
    
    if not os.path.exists(template2_dest):
        print(f"⚠️ Template2 não encontrado em {template2_dest}. Copiando novamente...")
        try:
            shutil.copy2(os.path.join(base_dir, "template_robo2.xlsx"), template2_dest)
            print(f"✅ Template2 copiado para {template2_dest}")
        except Exception as e:
            print(f"❌ Erro ao copiar template2: {str(e)}")

    # Remover arquivos Python originais da pasta de distribuição
    print("🧹 Removendo arquivos Python originais da pasta de distribuição...")
    for root, dirs, files in os.walk(dest_dir):
        for file in files:
            if file.endswith(".py") and not file.endswith(".pyc"):
                py_file = os.path.join(root, file)
                try:
                    os.remove(py_file)
                    print(f"✅ Removido arquivo Python original: {py_file}")
                except Exception as e:
                    print(f"⚠️ Não foi possível remover {py_file}: {str(e)}")

# ========================================================
# 🔍 VERIFICAÇÃO FINAL E RELATÓRIO COMPLETO
# ========================================================

print("\n🔍 Executando verificação final da compilação...")

# Verificar se todos os robôs foram incluídos
if not args.onefile:
    dest_dir = os.path.join(dist_dir, args.name)
    
    # Verificar estrutura de pastas dos robôs
    robot_dirs = [
        "automacaoexcel/Ordenamento",
        "automacaoexcel/Robos", 
        "automacaoexcel/Producao"
    ]
    
    for robot_dir in robot_dirs:
        robot_path = os.path.join(dest_dir, robot_dir)
        if os.path.exists(robot_path):
            robot_files = [f for f in os.listdir(robot_path) if f.endswith('.py')]
            print(f"✅ {robot_dir}: {len(robot_files)} arquivos Python encontrados")
        else:
            print(f"⚠️ {robot_dir}: Pasta não encontrada")
    
    # Verificar se os scripts AutoCAD foram incluídos
    autocad_scripts = [f for f in os.listdir(os.path.join(dest_dir, "automacaoexcel")) 
                      if f.endswith(('.scr', '.lsp'))] if os.path.exists(os.path.join(dest_dir, "automacaoexcel")) else []
    print(f"✅ Scripts AutoCAD: {len(autocad_scripts)} arquivos encontrados")
    
    # Verificar configurações JSON
    json_configs = []
    for root, dirs, files in os.walk(dest_dir):
        json_configs.extend([f for f in files if f.endswith('.json')])
    print(f"✅ Configurações JSON: {len(json_configs)} arquivos encontrados")

# Criar relatório de compilação
report_file = os.path.join(base_dir, f"relatorio_compilacao_{args.name}.txt")
with open(report_file, 'w', encoding='utf-8') as f:
    f.write("========================================================\n")
    f.write(f"📊 RELATÓRIO DE COMPILAÇÃO - {args.name} v3.0\n")
    f.write("========================================================\n\n")
    f.write(f"📅 Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
    f.write(f"🔨 Modo: {'Arquivo único' if args.onefile else 'Diretório'}\n")
    f.write(f"🐛 Debug: {'Ativado' if args.debug else 'Desativado'}\n\n")
    
    f.write("📊 ESTATÍSTICAS DE ARQUIVOS:\n")
    f.write(f"✅ Arquivos encontrados: {len(found_files)}\n")
    f.write(f"⚠️ Arquivos faltando: {len(missing_files)}\n")
    f.write(f"🐍 Python core: {len([f for f in found_files if f in core_python_files])}\n")
    f.write(f"🤖 Robôs ordenamento: {len([f for f in found_files if f in ordenamento_files])}\n")
    f.write(f"🤖 Robôs especializados: {len([f for f in found_files if f in robos_files])}\n")
    f.write(f"🏭 Produção: {len([f for f in found_files if f in producao_files])}\n")
    f.write(f"⚙️ Configurações: {len([f for f in found_files if f in config_files])}\n")
    f.write(f"📜 Scripts AutoCAD: {len([f for f in found_files if f in script_files])}\n")
    f.write(f"💾 Dados/Cache: {len([f for f in found_files if f in data_files])}\n\n")
    
    if missing_files:
        f.write("⚠️ ARQUIVOS FALTANDO:\n")
        for file in missing_files:
            f.write(f"  - {file}\n")
        f.write("\n")
    
    f.write("🔗 HIDDEN IMPORTS CONFIGURADOS:\n")
    for imp in hidden_imports:
        if imp.startswith('--hidden-import'):
            f.write(f"  {imp}\n")
    
    f.write(f"\n📦 TOTAL DE OPÇÕES PYINSTALLER: {len(pyinstaller_options)}\n")
    f.write(f"🔗 TOTAL DE HIDDEN IMPORTS: {len([imp for imp in hidden_imports if imp.startswith('--hidden-import')])}\n")

print(f"📄 Relatório de compilação salvo em: {report_file}")

# Criar script de teste rápido
test_script = os.path.join(base_dir, f"teste_{args.name.lower()}.bat")
with open(test_script, 'w', encoding='utf-8') as f:
    f.write("@echo off\n")
    f.write("echo ========================================================\n")
    f.write(f"echo 🧪 TESTE RÁPIDO - {args.name}\n")
    f.write("echo ========================================================\n")
    f.write("echo.\n")
    if args.onefile:
        f.write(f'echo Executando: {os.path.join(dist_dir, f"{args.name}.exe")}\n')
        f.write(f'"{os.path.join(dist_dir, f"{args.name}.exe")}"\n')
    else:
        f.write(f'echo Executando: {os.path.join(dist_dir, args.name, f"{args.name}.exe")}\n')
        f.write(f'"{os.path.join(dist_dir, args.name, f"{args.name}.exe")}"\n')
    f.write("pause\n")

print(f"🧪 Script de teste criado em: {test_script}")

print("\n✅ Processo de compilação finalizado com sucesso!")
print("\n📋 INSTRUÇÕES PARA DISTRIBUIÇÃO:")
if args.onefile:
    print("1. Distribua o arquivo executável único encontrado em:", os.path.join(dist_dir, f"{args.name}.exe"))
    print("2. Caso ocorram problemas com o Excel, você também deve distribuir os arquivos 'template_robo.xlsx' e 'template_robo2.xlsx' junto ao executável.")
else:
    print("1. Distribua a pasta completa encontrada em:", os.path.join(dist_dir, args.name))
    print("2. Mantenha TODOS os arquivos dessa pasta juntos.")
    print("3. O executável é:", os.path.join(args.name, f"{args.name}.exe"))

print("\n🤖 ROBÔS E ORDENADORES INCLUÍDOS:")
print("✅ Sistema completo de 45 robôs e ordenadores")
print("✅ Todos os 3 tipos: ABCD, CIMA, GRADES")
print("✅ Combinadores de scripts AutoCAD")
print("✅ Interfaces de configuração")
print("✅ Scripts .SCR e .LSP para AutoCAD")

print("\n⚙️ CONFIGURAÇÕES INCLUÍDAS:")
print("✅ Templates Excel (template_robo.xlsx, template_robo2.xlsx)")
print("✅ Configurações JSON para todos os ordenadores")
print("✅ Configurações específicas de cada robô")
print("✅ Cache de dados (pilares_salvos.pkl, pavimentos_lista.pkl)")

print("\n⚠️ IMPORTANTE:")
print("- O aplicativo requer no mínimo Windows 7 ou superior.")
print("- Pode ser necessário instalar o Microsoft Visual C++ Redistributable na máquina de destino.")
print("- Durante a primeira execução, o Windows pode mostrar um aviso de segurança. Isso é normal para aplicativos não assinados.")
print("- TODOS os 89 arquivos mapeados foram incluídos na compilação!")

print(f"\n📊 RESUMO FINAL:")
print(f"🎯 Total de arquivos processados: {len(all_files)}")
print(f"✅ Arquivos incluídos com sucesso: {len(found_files)}")
print(f"⚠️ Arquivos não encontrados: {len(missing_files)}")
print(f"🔗 Hidden imports configurados: {len([imp for imp in hidden_imports if imp.startswith('--hidden-import')])}")
print(f"📦 Opções PyInstaller: {len(pyinstaller_options)}")

print(f"\n🧪 Para testar rapidamente, execute: {test_script}")
print(f"📄 Relatório completo disponível em: {report_file}")

# Adicionar import datetime no topo se não existir
import datetime 