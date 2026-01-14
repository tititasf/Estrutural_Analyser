import os
import subprocess
import shutil
import sys

def build():
    # 1. Configurações
    entry_point = "viga_analyzer_v2.py"
    app_name = "AutomacaoVigas"
    dist_dir = "dist"
    build_dir = "build"
    obfuscated_dir = "obfuscated"

    print("--- Iniciando Processo de Build Seguro ---")

    # 2. Limpeza
    for d in [dist_dir, build_dir, obfuscated_dir]:
        if os.path.exists(d):
            print(f"Limpando {d}...")
            shutil.rmtree(d)

    # 3. Ofuscação com PyArmor
    # Nota: Requer 'pip install pyarmor'
    print("\n[1/3] Ofuscando código com PyArmor...")
    try:
        if not os.path.exists(obfuscated_dir):
            os.makedirs(obfuscated_dir)

        # Ofusca apenas os arquivos mais críticos para não estourar limite do PyArmor Trial/Basic
        targets = [
            "viga_analyzer_v2.py",
            "licensing_service_v2.py",
            "login_dialog.py"
        ]
        
        subprocess.run([
            "pyarmor", "gen", 
            "--output", obfuscated_dir
        ] + targets, check=True)
        
        # Copia os outros arquivos para a pasta obfuscated para que o PyInstaller os encontre
        others = [
            "robo_laterais_viga_pyside.py",
            "gerador_script_viga.py",
            "gerador_script_combinados.py",
            "Ordenador_VIGA.py",
            "Combinador_VIGA.py",
            "preview_combinacao.py",
            "preview_principal.py"
        ]
        for f in others:
            shutil.copy2(f, os.path.join(obfuscated_dir, f))
            
        print("Ofuscação e preparação de arquivos concluída.")
    except Exception as e:
        print(f"Erro na ofuscação: {e}")
        return

    # 4. Empacotamento com PyInstaller
    print("\n[2/3] Gerando executável com PyInstaller...")
    try:
        # Quando usamos o spec file, não passamos flags como --console ou --noconfirm
        # Essas configurações devem vir de dentro do arquivo .spec
        subprocess.run([
            "pyinstaller", "vigas_app.spec"
        ], check=True)
        print("Build do PyInstaller concluído.")
    except Exception as e:
        print(f"Erro no PyInstaller: {e}")
        return

    print(f"\n[3/3] Build Finalizado! Verifique a pasta '{dist_dir}'")

if __name__ == "__main__":
    build()
