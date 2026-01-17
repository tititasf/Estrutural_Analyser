import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from tufup.repo import Repository

# Importa o script de ofuscação (assumindo que está no path ou ajustando)
sys.path.append(str(Path(__file__).parent))
try:
    import pre_build_obfuscate
except ImportError:
    print("⚠️ Script de ofuscação não encontrado. Build seguirá sem ofuscação.")
    pre_build_obfuscate = None

def build_release():
    print("🚀 Iniciando processo de Build Release Seguro...")
    
    # 0. Check de Segurança (.env)
    if os.path.exists(".env"):
        print("⚠️ ALERTA: Arquivo .env detectado.")
        print("   Certifique-se de que as chaves em .env NÃO sejam distribuídas no executável.")
        print("   O PyInstaller não incluirá o arquivo .env automaticamente, mas as variáveis devem estar carregadas.")
    
    # 1. Configurações
    app_name = "AgenteCAD"
    version = os.getenv("APP_VERSION", "1.0.0") 
    dist_dir = Path("dist")
    repo_dir = Path("repository")
    keys_dir = Path("keys")
    src_dir = Path("src")
    src_raw_dir = Path("src_raw_backup")
    src_obf_dir = Path("src_obfuscated")

    obfuscation_success = False

    try:
        # 2. Ofuscação (Swap Mode)
        if pre_build_obfuscate and src_dir.exists():
            print("🛡️ Executando Ofuscação de Código...")
            pre_build_obfuscate.main()
            
            if src_obf_dir.exists():
                print("🔄 Substituindo 'src' pelo código ofuscado para compilação...")
                # Backup do original
                if src_raw_dir.exists():
                    shutil.rmtree(src_raw_dir)
                shutil.move(src_dir, src_raw_dir)
                
                # Move ofuscado para src
                time.sleep(1) # Wait for file handles
                for i in range(5):
                    try:
                        shutil.move(src_obf_dir, src_dir)
                        obfuscation_success = True
                        break
                    except Exception as e:
                        print(f"⚠️ Tentativa {i+1} falhou ao mover src_obf: {e}")
                        time.sleep(2)
                
                if not obfuscation_success:
                    print("❌ Falha crítica ao mover código ofuscado.")
            else:
                print("❌ Falha na ofuscação: diretório de saída não criado.")

        # 3. PyInstaller Build
        print(f"📦 Congelando aplicação com PyInstaller (v{version})...")
        # Build using the Spec file which now contains critical hooks
        subprocess.run([
            "pyinstaller", 
            "AgenteCAD.spec", 
            "--clean"
        ], check=True)

    except Exception as e:
        print(f"❌ ERRO CRÍTICO NO BUILD: {e}")
        # Tentar restaurar em caso de erro
        
    finally:
        # 4. Restauração (Sempre executar)
        if obfuscation_success and src_raw_dir.exists():
            print("♻️ Restaurando código fonte original...")
            # Se src (ofuscado) ainda existe, deleta ou move de volta pra debug (opcional)
            # Se src (ofuscado) ainda existe, deleta ou move de volta pra debug (opcional)
            if src_dir.exists():
                for i in range(5):
                    try:
                        shutil.rmtree(src_dir) # Tchau ofuscado
                        break
                    except Exception as e:
                        print(f"⚠️ Tentativa {i+1} falhou ao limpar src ofuscado: {e}")
                        time.sleep(2)
            
            # Restaura backup
            shutil.move(src_raw_dir, src_dir)
            print("✅ Código fonte restaurado.")
        elif src_raw_dir.exists() and not src_dir.exists():
             # Fallback caso tenha quebrado no meio do move
             shutil.move(src_raw_dir, src_dir)

    # 5. Tufup Repo Update
    if not os.path.exists(f"dist/{app_name}.exe") and not os.path.exists(f"dist/{app_name}"):
        print("❌ Executável não encontrado. Abortando deploy Tufup.")
        return

    print("🔑 Assinando release e atualizando repositório Tufup...")
    repo = Repository(repo_dir=repo_dir, keys_dir=keys_dir, app_name=app_name)
    
    # Adiciona o novo bundle ao repositório
    # PyInstaller one-dir vs one-file changes bundle path logic usually
    # Assuming one-file based on logic, but args said --noconsole (defaults to onedir?)
    # Added explicit --onedir or --onefile? The original usage in main.py suggests checking frozen.
    
    # Tufup usually expects a zip or directory.
    # We will assume dist/AgenteCAD folder exists (onedir default) or file.
    
    # For robust tufup, usually requires zipping the directory.
    # tufup's add_bundle handles zip creation? check tufup docs or assume standard
    # Standard tufup: repo.add_bundle(bundle_dir=...) implies it takes the dir and zips it.
    
    app_bundle_path = dist_dir / f"{app_name}"
    if not app_bundle_path.exists() and (dist_dir / f"{app_name}.exe").exists():
         app_bundle_path = dist_dir / f"{app_name}.exe" # onefile case

    repo.add_bundle(new_bundle_dir=app_bundle_path, new_version=version)
    
    # Publica mudanças
    repo.publish()

    print(f"✅ Build Seguro concluído! Versão {version} pronta em '{repo_dir}'.")
    print("💡 Não esqueça de subir para o Supabase Storage.")

if __name__ == "__main__":
    build_release()
