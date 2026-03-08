
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
🏗️ PilarAnalyzer - Sistema Principal
========================================================
📆 Data: 23/07/2025
✏️ Reorganizado por: Kiro AI
🆔 Versão: 3.0.0 - Estrutura Reorganizada

📋 Descrição:
Sistema principal do PilarAnalyzer com estrutura reorganizada
e sistema de créditos integrado.

📁 Nova Estrutura:
- src/: Código fonte principal
- config/: Arquivos de configuração
- templates/: Templates e modelos
- utils/: Utilitários e funções auxiliares
- robots/: Módulos específicos dos robôs
- lisps/: Arquivos LISP e scripts AutoCAD
"""

import os
import sys
import time
from datetime import datetime

# IMPORTAR INICIALIZADOR FROZEN ANTES DE TUDO
_importing_frozen_init = False
if not _importing_frozen_init:
    try:
        _importing_frozen_init = True
        try:
            from utils.__frozen_init__ import ensure_frozen_paths
            ensure_frozen_paths()
        except (ImportError, AttributeError):
            try:
                from src.utils.__frozen_init__ import ensure_frozen_paths
                ensure_frozen_paths()
            except (ImportError, AttributeError):
                pass  # Se não conseguir importar, continua normalmente
    except Exception:
        pass  # Se não conseguir importar, continua normalmente
    finally:
        _importing_frozen_init = False

# Forçar saída sem buffer para logs em tempo real
os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True, write_through=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True, write_through=True)
except Exception:
    pass

# Adicionar diretórios ao path (já feito pelo __frozen_init__, mas fazer fallback)
# Detectar ambiente frozen (executável empacotado)
is_frozen = getattr(sys, 'frozen', False)
if is_frozen:
    # No executável, o diretório base é onde o .exe está
    script_dir = os.path.dirname(sys.executable)
    # No Nuitka standalone, os módulos estão na mesma pasta do exe
    current_dir = script_dir
    project_root = script_dir
    # Adicionar ao path (se não foi adicionado pelo __frozen_init__)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    # Tentar adicionar src também (caso exista)
    src_dir = os.path.join(script_dir, 'src')
    if os.path.exists(src_dir) and src_dir not in sys.path:
        sys.path.insert(0, src_dir)
else:
    # No desenvolvimento, usar estrutura normal
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

def main():
    """Função principal - importa e executa o pilar_analyzer original"""
    start_time = time.time()
    
    # Configurar logging em arquivo para debug (especialmente importante em --windowed)
    log_file = None
    try:
        if is_frozen:
            log_dir = os.path.dirname(sys.executable)
        else:
            log_dir = current_dir
        log_file = os.path.join(log_dir, "pilar_analyzer_startup.log")
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"=== PILAR ANALYZER STARTUP LOG ===\n")
            f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Frozen: {is_frozen}\n")
            f.write(f"Executable: {sys.executable if is_frozen else 'N/A'}\n")
            f.write(f"Current dir: {current_dir}\n")
            f.write(f"Python path: {sys.path[:3]}\n")
            f.write(f"\n")
    except Exception as e:
        pass  # Se não conseguir criar log, continua
    
    def log(msg):
        """Função helper para log"""
        try:
            if log_file:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"{msg}\n")
                    f.flush()
        except Exception:
            pass
    
    log("Iniciando main()...")
    
    # Ajustar sys.path para PyInstaller
    if is_frozen:
        log(f"Ambiente frozen detectado. Executable: {sys.executable}")
        log(f"Current dir antes: {current_dir}")
        
        # PyInstaller onefile extrai módulos para _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            meipass = sys._MEIPASS
            log(f"_MEIPASS encontrado: {meipass}")
            if meipass not in sys.path:
                sys.path.insert(0, meipass)
                log(f"Adicionado _MEIPASS ao path: {meipass}")
            
            # Tentar adicionar src dentro de _MEIPASS
            src_path_mei = os.path.join(meipass, 'src')
            if os.path.exists(src_path_mei) and src_path_mei not in sys.path:
                sys.path.insert(0, src_path_mei)
                log(f"Adicionado src (_MEIPASS) ao path: {src_path_mei}")
        
        # No PyInstaller, os módulos também podem estar no diretório do executável
        exe_dir = os.path.dirname(sys.executable)
        log(f"Exe dir: {exe_dir}")
        
        # Tentar adicionar src ao path se existir
        src_path = os.path.join(exe_dir, 'src')
        if os.path.exists(src_path) and src_path not in sys.path:
            sys.path.insert(0, src_path)
            log(f"Adicionado src ao path: {src_path}")
        
        # PyInstaller pode colocar módulos no diretório do exe diretamente
        if exe_dir not in sys.path:
            sys.path.insert(0, exe_dir)
            log(f"Adicionado exe_dir ao path: {exe_dir}")
        
        log(f"Python path atualizado (primeiros 8): {sys.path[:8]}")
    
    try:
        log("Tentando importar core.pilar_analyzer...")
        try:
            from core.pilar_analyzer import main as pilar_main
            log("Import core.pilar_analyzer bem-sucedido")
        except ImportError:
            log("Tentando import src.core.pilar_analyzer...")
            try:
                from src.core.pilar_analyzer import main as pilar_main
                log("Import src.core.pilar_analyzer bem-sucedido")
            except ImportError:
                log("Tentando import direto...")
                # Adicionar src/core ao path
                if is_frozen:
                    core_path = os.path.join(os.path.dirname(sys.executable), 'src', 'core')
                else:
                    core_path = os.path.join(current_dir, 'core')
                if core_path not in sys.path:
                    sys.path.insert(0, core_path)
                    log(f"Adicionado core_path ao path: {core_path}")
                from pilar_analyzer import main as pilar_main
                log("Import direto bem-sucedido")
        
        log("Executando pilar_main()...")
        resultado = pilar_main()
        log(f"pilar_main() retornou: {resultado}")
        return resultado
    except ImportError as e:
        log(f"ImportError: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        # Tentar mostrar erro em janela
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Erro Fatal", f"Erro ao importar módulos:\n\n{str(e)}\n\nVerifique o log: {log_file}")
            root.destroy()
        except Exception:
            pass
        return None
    except Exception as e:
        log(f"Erro geral em main(): {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        # Tentar mostrar erro em janela
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Erro Fatal", f"Erro ao iniciar aplicação:\n\n{str(e)}\n\nVerifique o log: {log_file}")
            root.destroy()
        except Exception:
            pass

if __name__ == "__main__":
    main()