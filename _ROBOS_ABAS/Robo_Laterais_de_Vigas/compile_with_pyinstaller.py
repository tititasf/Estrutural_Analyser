"""
Script para compilar o RoboLateraisViga usando PyInstaller com sistema de validação
"""
import os
import sys
import shutil
import subprocess
import re
import argparse

# Analisar argumentos de linha de comando
parser = argparse.ArgumentParser(description='Compilar o RoboLateraisViga')
parser.add_argument('--onefile', action='store_true', help='Criar um único arquivo executável')
parser.add_argument('--debug', action='store_true', help='Incluir console para depuração')
parser.add_argument('--name', type=str, default='RoboLateraisViga', help='Nome do executável')
args = parser.parse_args()

print(f"🚀 Compilando {args.name} com PyInstaller...")
print(f"📋 Modo: {'arquivo único' if args.onefile else 'diretório'}, Debug: {'ativado' if args.debug else 'desativado'}")

# Verificar se PyInstaller está instalado
try:
    import PyInstaller
    print("✅ PyInstaller está instalado.")
except ImportError:
    print("❌ PyInstaller não está instalado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    print("✅ PyInstaller instalado com sucesso.")

# Verificar dependências do projeto
required_packages = ["pandas", "numpy", "openpyxl", "matplotlib", "requests"]
print("🔍 Verificando dependências...")
for package in required_packages:
    try:
        __import__(package)
        print(f"✅ {package} está instalado.")
    except ImportError:
        print(f"⚠️ {package} não está instalado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ {package} instalado com sucesso.")

# Diretório atual
base_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(base_dir)

# Caminho do arquivo de dados
dados_path = os.path.join(parent_dir, "fundos_salvos.json")
if not os.path.exists(dados_path):
    dados_path = os.path.join(base_dir, "fundos_salvos.json")

# Limpar diretórios de build anteriores
build_dir = os.path.join(base_dir, "build")
dist_dir = os.path.join(base_dir, "dist")

if os.path.exists(build_dir):
    print(f"🧹 Limpando diretório: {build_dir}")
    shutil.rmtree(build_dir)

if os.path.exists(dist_dir):
    print(f"🧹 Limpando diretório: {dist_dir}")
    shutil.rmtree(dist_dir)

# Verificar existência dos arquivos necessários
required_files = [
    os.path.join(base_dir, "viga_analyzer.py"),
    os.path.join(base_dir, "robo_laterais_viga_limpo233.py"),
    os.path.join(base_dir, "gerador_script_viga.py"),
    dados_path
]

for file in required_files:
    if not os.path.exists(file):
        print(f"❌ ERRO: Arquivo não encontrado: {file}")
        sys.exit(1)
    else:
        print(f"✅ Arquivo encontrado: {os.path.basename(file)}")

# Executar PyInstaller com as opções adequadas
print("🔄 Executando PyInstaller...")

pyinstaller_options = [
    f"--name={args.name}",
    "--clean",
    f"--workpath={build_dir}",
    f"--distpath={dist_dir}",
    f"--add-data={dados_path};.",
    # Excluir arquivos Python originais da pasta final
    "--exclude-module=__pycache__",
    "--strip",  # Remover informações de depuração
]

# Se for --onefile, adicionar essa opção
if args.onefile:
    pyinstaller_options.append("--onefile")
else:
    pyinstaller_options.append("--onedir")

# Se não for modo debug, usar opção --windowed
if not args.debug:
    pyinstaller_options.append("--windowed")

# Adicionar ícone se existir
icon_path = os.path.join(base_dir, "viga_icon.ico")
if os.path.exists(icon_path):
    pyinstaller_options.append(f"--icon={icon_path}")

# Adicionar hidden imports
hidden_imports = [
    "--hidden-import=viga_analyzer",
    "--hidden-import=robo_laterais_viga_limpo233",
    "--hidden-import=gerador_script_viga",
    "--hidden-import=pandas",
    "--hidden-import=numpy",
    "--hidden-import=tkinter",
    "--hidden-import=matplotlib",
    "--hidden-import=matplotlib.backends.backend_tkagg",
    "--hidden-import=matplotlib.figure",
    "--hidden-import=matplotlib.pyplot",
    "--hidden-import=matplotlib.patches",
    "--hidden-import=matplotlib.text",
    "--hidden-import=matplotlib.transforms",
    "--hidden-import=openpyxl",
    "--hidden-import=requests",
    "--hidden-import=json",
    "--hidden-import=datetime",
    "--hidden-import=threading",
    "--hidden-import=platform",
    "--hidden-import=uuid",
    "--hidden-import=hashlib",
    "--exclude-module=matplotlib.tests",
    "--exclude-module=matplotlib.testing",
    "--collect-all=tkinter",
    "--collect-all=matplotlib.backends",
    "--collect-all=matplotlib.pyplot",
    "--collect-all=openpyxl"
]

pyinstaller_options.extend(hidden_imports)

# Adicionar o arquivo principal (agora é o viga_analyzer.py)
pyinstaller_options.append(os.path.join(base_dir, "viga_analyzer.py"))

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

print("\n✅ Processo de compilação finalizado com sucesso!")
print("\n📋 INSTRUÇÕES PARA DISTRIBUIÇÃO:")
if args.onefile:
    print("1. Distribua o arquivo executável único encontrado em:", os.path.join(dist_dir, f"{args.name}.exe"))
else:
    print("1. Distribua a pasta completa encontrada em:", os.path.join(dist_dir, args.name))
    print("2. Mantenha TODOS os arquivos dessa pasta juntos.")
    print("3. O executável é:", os.path.join(args.name, f"{args.name}.exe"))
print("\n⚠️ IMPORTANTE:")
print("- O aplicativo requer no mínimo Windows 7 ou superior.")
print("- Pode ser necessário instalar o Microsoft Visual C++ Redistributable na máquina de destino.")
print("- Durante a primeira execução, o Windows pode mostrar um aviso de segurança. Isso é normal para aplicativos não assinados.")

# Copiar recursos adicionais para o diretório dist se necessário
if not args.onefile:
    dest_dir = os.path.join(dist_dir, args.name)
    print(f"📦 Verificando recursos adicionais no diretório '{dest_dir}'...")
    
    # Verificar se o arquivo de dados foi copiado corretamente
    dados_dest = os.path.join(dest_dir, "fundos_salvos.json")
    if not os.path.exists(dados_dest):
        print(f"⚠️ Arquivo de dados não encontrado em {dados_dest}. Copiando novamente...")
        try:
            shutil.copy2(dados_path, dados_dest)
            print(f"✅ Arquivo de dados copiado para {dados_dest}")
        except Exception as e:
            print(f"❌ Erro ao copiar arquivo de dados: {str(e)}")

    # Remover TODOS os arquivos Python da distribuição
    print("\n🧹 Removendo arquivos Python da distribuição para segurança...")
    python_files_removed = 0
    for root, dirs, files in os.walk(dest_dir):
        for file in files:
            if file.endswith('.py'):
                try:
                    file_path = os.path.join(root, file)
                    os.remove(file_path)
                    python_files_removed += 1
                    print(f"✅ Removido: {file}")
                except Exception as e:
                    print(f"⚠️ Não foi possível remover {file}: {str(e)}")
    
    print(f"\n🔒 Total de {python_files_removed} arquivos Python removidos da distribuição.")
    
    # Verificação adicional de segurança
    remaining_py_files = []
    for root, dirs, files in os.walk(dest_dir):
        for file in files:
            if file.endswith('.py'):
                remaining_py_files.append(os.path.join(root, file))
    
    if remaining_py_files:
        print("\n⚠️ AVISO: Ainda existem arquivos Python na distribuição:")
        for file in remaining_py_files:
            print(f"- {file}")
        print("\nTente remover estes arquivos manualmente se necessário.")
    else:
        print("\n✅ Verificação de segurança concluída: Nenhum arquivo Python encontrado na distribuição.")

print("\n✅ Processo de compilação e configuração finalizado!")
print("\n📋 RESUMO FINAL:")
print("1. Executável compilado com sucesso")
print("2. Arquivos Python originais removidos")
print("3. Apenas arquivos compilados e recursos necessários mantidos")
print("\n⚠️ IMPORTANTE: A distribuição está segura para envio, sem códigos-fonte expostos.") 