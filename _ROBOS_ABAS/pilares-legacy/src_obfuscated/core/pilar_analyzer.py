
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
📌 Título do Arquivo: pilar_analyzer.py
📆 Data de Criação: 23/03/2024
✏️ Autor: Claude & User
🆔 Versão: 2.0.0 - Sistema de Créditos Integrado
========================================================

🔷 **Prompt Inicial**
Script principal para PilarAnalyzer com sistema de licenciamento online e créditos por m².

📖 **Registro de Desenvolvimento**
🔹 **Parte 1 - Estrutura Inicial**  
📆 23/03/2024: Criada a estrutura inicial do código com sistema de licenciamento.
🔹 **Parte 2 - Otimização da Ativação**
📆 22/03/2025: Otimizado o processo de ativação para execução mais leve.
🔹 **Parte 3 - Sistema de Créditos**
📆 18/07/2025: Implementado sistema completo de créditos baseado em m² produzidos.

🔹 **Índice do Código**
1️⃣ [Linha 1-50]📥 Importações e Configurações
2️⃣ [Linha 51-300] 🛡️ Sistema de Licenciamento  
3️⃣ [Linha 301-600] 💳 Sistema de Créditos e Interface de Login
4️⃣ [Linha 601-700] 🚀 Código Principal e Integração

📎 **Arquivos Relacionados**
- `credit_system.py`: Sistema completo de gerenciamento de créditos
- `funcoes_auxiliares_2.py`: Classe PilarAnalyzer com métodos de cálculo de área
- `funcoes_auxiliares_6.py`: Operações de desenho integradas com créditos
- `test_credit_system.py`: Testes unitários do sistema de créditos
- `test_integration.py`: Testes de integração completos
- `CREDIT_SYSTEM_DOCS.md`: Documentação completa do sistema

💳 **Sistema de Créditos v2.0.0**
- Cobrança por m² produzido (1 crédito = 1 m²)
- Cálculo automático baseado em dimensões dos pilares
- Modo online/offline com sincronização automática
- Interface de confirmação detalhada
- Logging completo e tratamento de erros robusto
- Testes unitários e de integração (35 testes)

📊 **Resumo Geral**
Este script é o ponto de entrada principal para o aplicativo PilarAnalyzer com sistema 
integrado de licenciamento e créditos. Inclui interface de login, validação de créditos,
e integração completa com operações de desenho.
"""

# ========================================================
# 📥 Importações
# ========================================================
import os
import sys
import hashlib
import platform
import uuid
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import json
import datetime
import threading
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

# Importações pesadas colocadas após verificação de licença
requests = None

# Sistema de logs de depuração
pilar_logger = None

# Configurar paths do projeto
try:
    from ..config_paths import setup_paths, PROJECT_ROOT, CORE_DIR
    setup_paths()
except ImportError:
    try:
        from config_paths import setup_paths, PROJECT_ROOT, CORE_DIR
        setup_paths()
    except ImportError:
        try:
            from src.config_paths import setup_paths, PROJECT_ROOT, CORE_DIR
            setup_paths()
        except ImportError:
            # Fallback para estrutura antiga
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

# ========================================================
# 🛡️ Sistema de Licenciamento
# ========================================================

# Substituir pelos valores corretos (serão atualizados no setup.py):
SHEET_ID = "1m7CNUU_iuG79R5OazQkAVq60SpPYYPe36lrRJwoH8Fg"
API_KEY = "AIzaSyD1anb0R8w9mjQcIFyK8pFG4smFZnaDB0s"

# URL para buscar as licenças do Google Sheets
SHEET_URL = _get_obf_str("https://")

# Chave de teste embutida
TEST_KEY = "Q4JU-X26H-04EN-R39F"

def obter_hwid():
    """
    Gera um identificador único de hardware para o computador atual.
    Combina informações do sistema para criar um ID único.
    """
    try:
        # Coletar informações do sistema
        system_info = platform.uname()
        cpu_info = platform.processor()
        
        # Obter ID único do sistema (varia por OS)
        if platform.system() == "Windows":
            machine_guid = str(uuid.getnode())  # MAC address como fallback
            try:
                import winreg
                registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
            except:
                pass
        else:
            machine_guid = str(uuid.getnode())
        
        # Combinar informações e criar hash
        combined_info = f"{system_info.system}_{system_info.node}_{cpu_info}_{machine_guid}"
        hwid = hashlib.sha256(combined_info.encode()).hexdigest()
        return hwid
    except:
        # Fallback para MAC address se algo der errado
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()

def importar_requests():
    """Importa o módulo requests apenas quando necessário"""
    global requests
    if requests is None:
        try:
            import requests as req
            requests = req
            return True
        except ImportError:
            return False
    return True

def verificar_licenca_online(chave, log_callback=None):
    """
    Verifica se a chave fornecida está na planilha do Google Sheets.
    A chave deve estar no formato: XXXX-XXXX-XXXX-XXXX-HWID
    onde HWID é o hardware ID do computador.
    """
    if log_callback:
        log_callback("Iniciando verificação de licença...")
    
    # Verificar se é a chave de teste
    if chave == TEST_KEY:
        if log_callback:
            log_callback("Chave de teste detectada. Ativando temporariamente.")
        return True, "Licença de teste ativada com sucesso!"
    
    # Importar requests apenas quando necessário
    if not importar_requests():
        if log_callback:
            log_callback("Erro: Módulo requests não disponível. Verificando modo offline.")
        return verificar_modo_offline(chave, obter_hwid(), log_callback)
    
    try:
        # Obter HWID do computador atual
        hwid = obter_hwid()
        if log_callback:
            log_callback(f"HWID deste computador: {hwid[:8]}...")
        
        # Verificar formato da chave
        if not chave or len(chave.split('-')) < 4:
            if log_callback:
                log_callback("Erro: Formato de chave inválido.")
            return False, "Formato de chave inválido."
        
        # Verificar parte da chave correspondente ao HWID
        partes_chave = chave.split('-')
        if len(partes_chave) >= 5:
            # Se a chave inclui HWID, verificar se corresponde ao computador atual
            if partes_chave[-1] != hwid[:8]:
                if log_callback:
                    log_callback(f"Erro: HWID da chave ({partes_chave[-1]}) não corresponde ao do computador ({hwid[:8]}).")
                return False, "Esta licença não é válida para este computador."
        
        # Consultar planilha do Google Sheets
        if log_callback:
            log_callback("Conectando ao servidor de licenças...")
        
        response = requests.get(SHEET_URL, timeout=30)
        if log_callback:
            log_callback(f"Resposta do servidor: código {response.status_code}")
        
        if response.status_code != 200:
            # Se não puder se conectar, permitir execução offline por 7 dias
            if log_callback:
                log_callback("Não foi possível conectar ao servidor. Verificando modo offline.")
            return verificar_modo_offline(chave, hwid, log_callback)
            
        data = response.json()
        chaves_validas = [row[0] for row in data.get("values", []) if row]
        
        if log_callback:
            log_callback(f"Verificando chave nas {len(chaves_validas)} licenças registradas...")
        
        # Verificar se a chave base (sem HWID) está na lista
        chave_base = '-'.join(partes_chave[:4])
        for chave_valida in chaves_validas:
            if chave_valida.startswith(chave_base):
                # Salvar chave para modo offline
                if log_callback:
                    log_callback("Chave válida encontrada! Salvando para uso offline...")
                salvar_para_modo_offline(chave, hwid)
                return True, "Licença válida!"
        
        if log_callback:
            log_callback("Chave não encontrada no servidor de licenças.")
        return False, "Licença inválida ou revogada. Contate o suporte."
    except Exception as e:
        # Tentar modo offline em caso de erro
        if log_callback:
            log_callback(f"Erro durante verificação online: {str(e)}")
            log_callback("Tentando verificação offline...")
        return verificar_modo_offline(chave, hwid, log_callback)

def salvar_para_modo_offline(chave, hwid):
    """Salva a chave e data de validação para permitir modo offline"""
    try:
        data_atual = datetime.now()
        info_licenca = {
            "chave": chave,
            "hwid": hwid,
            "ultima_verificacao": data_atual.isoformat(),
            "expira_em": (data_atual + datetime.timedelta(days=7)).isoformat()
        }
        
        with open(os.path.join(current_dir, ".licenca_temp"), "w") as f:
            json.dump(info_licenca, f)
    except:
        # Ignorar erros ao salvar informações offline
        pass

def verificar_modo_offline(chave, hwid, log_callback=None):
    """Verifica se há uma licença offline válida"""
    try:
        arquivo_licenca = os.path.join(current_dir, ".licenca_temp")
        if not os.path.exists(arquivo_licenca):
            if log_callback:
                log_callback("Nenhuma licença offline encontrada.")
            return False, "Não foi possível validar a licença online. Verifique sua conexão."
            
        with open(arquivo_licenca, "r") as f:
            info_licenca = json.load(f)
        
        if log_callback:
            log_callback("Verificando licença offline salva...")
            
        # Verificar se é a mesma chave e HWID
        if info_licenca["chave"] != chave or info_licenca["hwid"] != hwid:
            if log_callback:
                log_callback("Licença offline inválida para este computador/chave.")
            return False, "Licença offline inválida para este computador."
            
        # Verificar se a licença ainda não expirou
        data_atual = datetime.now()
        data_expiracao = datetime.fromisoformat(info_licenca["expira_em"])
        
        if data_atual > data_expiracao:
            if log_callback:
                log_callback("Licença offline expirada.")
            return False, "Licença offline expirada. Conecte-se à internet para revalidar."
            
        dias_restantes = (data_expiracao - data_atual).days
        if log_callback:
            log_callback(f"Licença offline válida por mais {dias_restantes} dias.")
        return True, "Licença offline válida. Expira em: " + str(dias_restantes) + " dias."
    except Exception as e:
        if log_callback:
            log_callback(f"Erro na verificação offline: {str(e)}")
        return False, "Erro ao verificar licença offline."

def solicitar_licenca_gui():
    """Abre uma janela para o usuário inserir a chave de licença"""
    global ativacao_bem_sucedida
    ativacao_bem_sucedida = False  # Variável global para rastrear o sucesso da ativação
    
    # Criar janela
    janela_licenca = tk.Tk()
    janela_licenca.title("Ativação do PilarAnalyzer")
    janela_licenca.geometry("500x350")
    janela_licenca.resizable(False, False)
    
    # Centralizar na tela
    janela_licenca.update_idletasks()
    width = janela_licenca.winfo_width()
    height = janela_licenca.winfo_height()
    x = (janela_licenca.winfo_screenwidth() // 2) - (width // 2)
    y = (janela_licenca.winfo_screenheight() // 2) - (height // 2)
    janela_licenca.geometry(f'{width}x{height}+{x}+{y}')
    
    # Variável para armazenar resultado
    resultado = {"valido": False, "chave": ""}
    
    # Função para adicionar mensagem ao log
    def adicionar_log(mensagem):
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, f"{mensagem}\n")
        log_text.see(tk.END)  # Rolagem automática
        log_text.config(state=tk.DISABLED)
        janela_licenca.update()  # Atualizar a interface para mostrar as mensagens
    
    # Função para validar a licença inserida em uma thread separada
    def validar_licenca_thread():
        btn_ativar.config(state=tk.DISABLED)  # Desabilitar botão durante a validação
        chave = entrada_chave.get().strip()
        
        if not chave:
            adicionar_log("⚠️ Erro: Insira uma chave de licença válida.")
            btn_ativar.config(state=tk.NORMAL)
            return
        
        # Executar validação em uma thread separada
        def executar_validacao():
            nonlocal resultado
            adicionar_log("🔄 Iniciando processo de verificação de licença...")
            
            # Mostrar indicador de progresso
            progress_bar.start(10)
            
            valido, mensagem = verificar_licenca_online(chave, adicionar_log)
            
            # Parar indicador de progresso
            progress_bar.stop()
            
            if valido:
                # Salvar chave para uso futuro
                try:
                    with open(os.path.join(current_dir, ".licenca"), "w") as f:
                        f.write(chave)
                    adicionar_log("✅ Chave salva com sucesso!")
                except Exception as e:
                    adicionar_log(f"⚠️ Aviso: Não foi possível salvar a chave: {str(e)}")
                
                adicionar_log(f"✅ SUCESSO: {mensagem}")
                resultado["valido"] = True
                resultado["chave"] = chave
                
                # Usar thread principal para atualizar interface
                janela_licenca.after(1000, lambda: janela_licenca.destroy())
            else:
                adicionar_log(f"❌ ERRO: {mensagem}")
                btn_ativar.config(state=tk.NORMAL)  # Reativar botão
        
        # Iniciar thread de validação
        threading.Thread(target=executar_validacao, daemon=True).start()
    
    # Adicionar elementos à janela
    # Frame principal
    main_frame = ttk.Frame(janela_licenca, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Título
    ttk.Label(main_frame, text="PilarAnalyzer", font=("Arial", 16, "bold")).pack(pady=10)
    ttk.Label(main_frame, text="Digite sua chave de licença:").pack(pady=5)
    
    # Campo de entrada
    entrada_chave = ttk.Entry(main_frame, width=40)
    entrada_chave.pack(pady=5)
    
    # Verificar se há uma chave salva
    try:
        if os.path.exists(os.path.join(current_dir, ".licenca")):
            with open(os.path.join(current_dir, ".licenca"), "r") as f:
                chave_salva = f.read().strip()
                if chave_salva:
                    entrada_chave.insert(0, chave_salva)
    except:
        # Usar chave de teste como fallback
        entrada_chave.insert(0, TEST_KEY)
    
    # Barra de progresso
    progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
    progress_bar.pack(fill=tk.X, pady=5)
    
    # Botão de ativação
    btn_ativar = ttk.Button(main_frame, text="Ativar", command=validar_licenca_thread)
    btn_ativar.pack(pady=5)
    
    # Área de log
    log_frame = ttk.LabelFrame(main_frame, text="Log de Ativação")
    log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
    
    log_text = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
    log_text.pack(fill=tk.BOTH, expand=True)
    
    # Texto de ajuda
    ttk.Label(main_frame, text=f"Para testes, use a chave: {TEST_KEY}", font=("Arial", 8)).pack(side=tk.BOTTOM, pady=0)
    
    # HWID do sistema
    hwid_texto = _get_obf_str("obter_hwid")
    ttk.Label(main_frame, text=hwid_texto, font=("Arial", 8)).pack(side=tk.BOTTOM, pady=2)
    
    # Vincular tecla Enter para validar
    entrada_chave.bind('<Return>', lambda event: validar_licenca_thread())
    entrada_chave.focus_set()
    
    # Mensagem inicial no log
    adicionar_log("Sistema de ativação do PilarAnalyzer iniciado.")
    adicionar_log("Digite sua chave de licença e clique em 'Ativar'.")
    adicionar_log(f"Este sistema está operando no computador: {platform.node()}")
    
    # Executar loop
    janela_licenca.mainloop()
    
    # Verificar novamente após fechamento da janela
    try:
        with open(os.path.join(current_dir, ".licenca"), "r") as f:
            chave = f.read().strip()
            valido, _ = verificar_licenca_online(chave)
            return valido
    except:
        return False

# ========================================================
# 💳 Sistema de Créditos - Interface de Login
# ========================================================

def criar_interface_login():
    """
    Cria interface de login para o sistema de créditos.
    Idêntica ao FundoAnalyzer para manter consistência.
    """
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    import threading
    import traceback
    
    # Importar módulo de créditos
    try:
        from .credit_system import CreditManager, salvar_config_usuario, carregar_config_usuario, obter_hwid, definir_gerenciador_creditos
    except ImportError:
        try:
            # Fallback para import direto
            import credit_system
            CreditManager = credit_system.CreditManager
            salvar_config_usuario = credit_system.salvar_config_usuario
            carregar_config_usuario = credit_system.carregar_config_usuario
            obter_hwid = credit_system.obter_hwid
            definir_gerenciador_creditos = credit_system.definir_gerenciador_creditos
        except ImportError:
            try:
                # Fallback para estrutura reorganizada
                from core.credit_system import CreditManager, salvar_config_usuario, carregar_config_usuario, obter_hwid, definir_gerenciador_creditos
            except ImportError as e:
                try:
                    messagebox.showerror("Erro", _get_obf_str("credit"))
                except Exception:
                    import traceback
                    traceback.print_exc()
                return None
    
    # Variável para armazenar o resultado
    resultado = {"credit_manager": None, "sucesso": False}
    
    # Criar janela de login
    try:
        janela_login = tk.Tk()
        janela_login.title("Sistema de Créditos - PilarAnalyzer")
        janela_login.geometry("600x500")
        janela_login.resizable(False, False)
    except Exception as e:
        error_msg = f"Erro ao criar janela de login: {str(e)}\n{traceback.format_exc()}"
        try:
            # Tentar criar uma janela temporária para mostrar o erro
            error_window = tk.Tk()
            error_window.withdraw()
            messagebox.showerror("Erro", f"Erro ao criar janela de login:\n\n{str(e)}")
            error_window.destroy()
        except Exception:
            pass
        return None
    
    # Centralizar na tela
    janela_login.update_idletasks()
    width = janela_login.winfo_width()
    height = janela_login.winfo_height()
    x = (janela_login.winfo_screenwidth() // 2) - (width // 2)
    y = (janela_login.winfo_screenheight() // 2) - (height // 2)
    janela_login.geometry(f'{width}x{height}+{x}+{y}')
    
    # Frame principal
    main_frame = ttk.Frame(janela_login, padding=15)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Título
    titulo_frame = ttk.Frame(main_frame)
    titulo_frame.pack(fill=tk.X, pady=(0, 15))
    
    ttk.Label(titulo_frame, text="💳 Sistema de Créditos", font=("Arial", 16, "bold")).pack()
    ttk.Label(titulo_frame, text="PilarAnalyzer - Login de Usuário", font=("Arial", 10)).pack()
    
    # Frame de credenciais
    cred_frame = ttk.LabelFrame(main_frame, text="Credenciais de Acesso", padding=10)
    cred_frame.pack(fill=tk.X, pady=(0, 10))
    
    # User ID
    ttk.Label(cred_frame, text="User ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
    entry_user_id = ttk.Entry(cred_frame, width=40)
    entry_user_id.grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=2)
    
    # API Key
    ttk.Label(cred_frame, text="API Key:").grid(row=1, column=0, sticky=tk.W, pady=2)
    entry_api_key = ttk.Entry(cred_frame, width=40, show="*")
    entry_api_key.grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=2)
    
    cred_frame.columnconfigure(1, weight=1)
    
    # Frame de status
    status_frame = ttk.Frame(main_frame)
    status_frame.pack(fill=tk.X, pady=(0, 10))
    
    # Indicador de status de conexão
    status_label = ttk.Label(status_frame, text="⚪ Desconectado", font=("Arial", 9))
    status_label.pack(side=tk.LEFT)
    
    # Saldo atual
    saldo_label = ttk.Label(status_frame, text="Saldo: --", font=("Arial", 9, "bold"))
    saldo_label.pack(side=tk.RIGHT)
    
    # Barra de progresso
    progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
    progress_bar.pack(fill=tk.X, pady=(0, 10))
    
    # Botões
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=(0, 10))
    
    btn_login = ttk.Button(btn_frame, text="🔑 Fazer Login")
    btn_login.pack(side=tk.LEFT, padx=(0, 10))
    
    btn_testar = ttk.Button(btn_frame, text="🔍 Testar Conexão")
    btn_testar.pack(side=tk.LEFT, padx=(0, 10))
    
    btn_offline = ttk.Button(btn_frame, text="Iniciar offline")
    btn_offline.pack(side=tk.LEFT, padx=(0, 10))
    
    btn_sair = ttk.Button(btn_frame, text="❌ Cancelar", command=lambda: cancelar_login())
    btn_sair.pack(side=tk.RIGHT)
    
    # Área de log
    log_frame = ttk.LabelFrame(main_frame, text="Log de Atividades", padding=5)
    log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD, state=tk.DISABLED)
    log_text.pack(fill=tk.BOTH, expand=True)
    
    # Informações do sistema
    info_frame = ttk.Frame(main_frame)
    info_frame.pack(fill=tk.X)
    
    hwid_atual = obter_hwid()
    ttk.Label(info_frame, text=f"HWID: {hwid_atual[:16]}...", font=("Arial", 8)).pack(side=tk.LEFT)
    ttk.Label(info_frame, text=f"Sistema: {platform.node()}", font=("Arial", 8)).pack(side=tk.RIGHT)
    
    # Função para adicionar mensagem ao log (thread-safe)
    def adicionar_log(mensagem, cor="black"):
        """Adiciona mensagem ao log de forma thread-safe"""
        def _adicionar_log_ui():
            try:
                log_text.config(state=tk.NORMAL)
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_text.insert(tk.END, f"[{timestamp}] {mensagem}\n")
                log_text.see(tk.END)
                log_text.config(state=tk.DISABLED)
            except Exception as e:
                # Se a janela foi fechada, ignorar erro
                pass
        
        # Agendar execução na thread principal
        try:
            janela_login.after(0, _adicionar_log_ui)
        except Exception:
            # Se a janela não existe mais, tentar executar diretamente (pode falhar, mas não é crítico)
            try:
                _adicionar_log_ui()
            except Exception:
                pass
    
    # Função para atualizar status de conexão (thread-safe)
    def atualizar_status_conexao(conectado, saldo=None):
        """Atualiza status de conexão de forma thread-safe"""
        def _atualizar_status_ui():
            try:
                if conectado:
                    status_label.config(text="🟢 Conectado")
                    if saldo is not None:
                        saldo_label.config(text=_get_obf_str("saldo"))
                else:
                    status_label.config(text="🔴 Desconectado")
                    saldo_label.config(text="Saldo: --")
            except Exception:
                # Se a janela foi fechada, ignorar erro
                pass
        
        # Agendar execução na thread principal
        try:
            janela_login.after(0, _atualizar_status_ui)
        except Exception:
            # Se a janela não existe mais, tentar executar diretamente (pode falhar, mas não é crítico)
            try:
                _atualizar_status_ui()
            except Exception:
                pass
    
    # Funções auxiliares thread-safe para modificar widgets
    def _atualizar_botao(botao, estado):
        """Atualiza estado de botão de forma thread-safe"""
        def _atualizar():
            try:
                botao.config(state=estado)
            except Exception:
                pass
        try:
            janela_login.after(0, _atualizar)
        except Exception:
            pass
    
    def _iniciar_progress():
        """Inicia barra de progresso de forma thread-safe"""
        def _iniciar():
            try:
                progress_bar.start(10)
            except Exception:
                pass
        try:
            janela_login.after(0, _iniciar)
        except Exception:
            pass
    
    def _parar_progress():
        """Para barra de progresso de forma thread-safe"""
        def _parar():
            try:
                progress_bar.stop()
            except Exception:
                pass
        try:
            janela_login.after(0, _parar)
        except Exception:
            pass
    
    # Função para testar conexão
    def testar_conexao():
        # Obter valores ANTES de iniciar a thread (thread-safe)
        try:
            user_id = entry_user_id.get().strip()
            api_key = entry_api_key.get().strip()
        except Exception:
            return
        
        def executar_teste():
            _atualizar_botao(btn_testar, tk.DISABLED)
            _iniciar_progress()
            
            adicionar_log("🔄 Testando conexão com servidor de créditos...")
            
            if not user_id or not api_key:
                adicionar_log("⚠️ Preencha User ID e API Key para testar conexão")
                _parar_progress()
                _atualizar_botao(btn_testar, tk.NORMAL)
                return
            
            try:
                temp_manager = CreditManager(user_id, api_key)
                conectado = temp_manager.verificar_conexao(adicionar_log)
                
                if conectado:
                    adicionar_log("✅ Conexão estabelecida com sucesso!")
                    sucesso, saldo = temp_manager.consultar_saldo(adicionar_log)
                    if sucesso:
                        atualizar_status_conexao(True, saldo)
                    else:
                        atualizar_status_conexao(True)
                else:
                    adicionar_log("❌ Falha na conexão com servidor")
                    atualizar_status_conexao(False)
                    
            except Exception as e:
                adicionar_log(f"❌ Erro durante teste: {str(e)}")
                atualizar_status_conexao(False)
            
            _parar_progress()
            _atualizar_botao(btn_testar, tk.NORMAL)
        
        threading.Thread(target=executar_teste, daemon=True).start()
    
    # Função para fazer login
    def fazer_login():
        """
        Realiza o login do usuário
        
        IMPORTANTE: Aceita QUALQUER senha (api_key) que esteja cadastrada no Google Sheets.
        Não há validação de formato ou padrão - a senha será validada no servidor
        comparando com o valor armazenado na planilha do Google Sheets.
        """
        # Obter valores ANTES de iniciar a thread (thread-safe)
        try:
            user_id = entry_user_id.get().strip()
            api_key = entry_api_key.get().strip()
        except Exception:
            return
        
        def executar_login():
            _atualizar_botao(btn_login, tk.DISABLED)
            _atualizar_botao(btn_testar, tk.DISABLED)
            _iniciar_progress()
            
            # Validação apenas verifica se os campos não estão vazios
            # NÃO há validação de formato de senha - aceita QUALQUER valor
            if not user_id or not api_key:
                adicionar_log("⚠️ Preencha todos os campos obrigatórios")
                _parar_progress()
                _atualizar_botao(btn_login, tk.NORMAL)
                _atualizar_botao(btn_testar, tk.NORMAL)
                return
            
            adicionar_log("🔄 Iniciando processo de login...")
            
            try:
                # Criar gerenciador de créditos
                # Aceita QUALQUER senha - validação será feita no servidor Google Apps Script
                credit_manager = CreditManager(user_id, api_key)
                
                # Testar conexão
                adicionar_log("🔍 Verificando conexão...")
                if not credit_manager.verificar_conexao(adicionar_log):
                    adicionar_log("❌ Não foi possível conectar ao servidor")
                    _parar_progress()
                    _atualizar_botao(btn_login, tk.NORMAL)
                    _atualizar_botao(btn_testar, tk.NORMAL)
                    return
                
                # Consultar saldo
                adicionar_log("💰 Consultando saldo de créditos...")
                sucesso, saldo = credit_manager.consultar_saldo(adicionar_log)
                
                if sucesso:
                    # Salvar credenciais
                    if salvar_config_usuario(user_id, api_key):
                        adicionar_log("💾 Credenciais salvas com sucesso")
                    else:
                        adicionar_log("⚠️ Aviso: Não foi possível salvar credenciais")
                    
                    # Definir gerenciador global
                    definir_gerenciador_creditos(credit_manager)
                    
                    # Atualizar interface
                    atualizar_status_conexao(True, saldo)
                    adicionar_log(f"✅ Login realizado com sucesso!")
                    adicionar_log(_get_obf_str("saldo"))
                    
                    # Definir resultado
                    resultado["credit_manager"] = credit_manager
                    resultado["sucesso"] = True
                    
                    # Fechar janela após 2 segundos
                    def fechar_janela():
                        try:
                            janela_login.quit()  # Sair do mainloop primeiro
                            janela_login.destroy()  # Depois destruir a janela
                        except Exception:
                            pass  # Ignorar erros ao fechar
                    
                    try:
                        janela_login.after(2000, fechar_janela)
                    except Exception:
                        pass
                    
                else:
                    adicionar_log("❌ Falha na consulta de saldo")
                    atualizar_status_conexao(False)
                    
            except Exception as e:
                adicionar_log(f"❌ Erro durante login: {str(e)}")
                atualizar_status_conexao(False)
            
            _parar_progress()
            _atualizar_botao(btn_login, tk.NORMAL)
            _atualizar_botao(btn_testar, tk.NORMAL)
        
        threading.Thread(target=executar_login, daemon=True).start()
    
    # Função para iniciar em modo offline
    def iniciar_offline():
        """Inicia a interface em modo offline sem capacidades de desenho"""
        adicionar_log("📴 Iniciando modo offline...")
        adicionar_log("⚠️ Modo offline: Sem capacidade de gerar scripts de desenho")
        
        try:
            # Criar CreditManager em modo offline (sem conexão)
            # Usar credenciais vazias ou especiais para modo offline
            credit_manager = CreditManager("offline", "offline_mode")
            
            # Definir saldo como 0 e modo offline
            credit_manager.saldo_atual = 0
            credit_manager.modo_offline = True  # Flag para indicar modo offline
            
            # Definir gerenciador global
            definir_gerenciador_creditos(credit_manager)
            
            # Atualizar interface
            atualizar_status_conexao(False)
            saldo_label.config(text="Saldo: 0.00 m² (Offline)")
            adicionar_log("✅ Modo offline ativado")
            adicionar_log("🔒 Botões de desenho serão bloqueados")
            
            # Definir resultado
            resultado["credit_manager"] = credit_manager
            resultado["sucesso"] = True
            resultado["modo_offline"] = True  # Flag adicional para identificar modo offline
            
            # Fechar janela após 1 segundo
            def fechar_janela():
                try:
                    janela_login.quit()
                    janela_login.destroy()
                except Exception:
                    pass
            
            janela_login.after(1000, fechar_janela)
            
        except Exception as e:
            adicionar_log(f"❌ Erro ao iniciar modo offline: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Configurar eventos dos botões
    btn_login.config(command=fazer_login)
    btn_testar.config(command=testar_conexao)
    btn_offline.config(command=iniciar_offline)
    
    # Vincular tecla Enter para fazer login
    def on_enter(event):
        fazer_login()
    
    entry_user_id.bind('<Return>', on_enter)
    entry_api_key.bind('<Return>', on_enter)
    
    # Interceptar fechamento da janela (X)
    def on_closing():
        resultado["sucesso"] = False
        resultado["credit_manager"] = None
        janela_login.destroy()
    
    janela_login.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Carregar credenciais salvas
    try:
        user_id_salvo, api_key_salva = carregar_config_usuario()
        if user_id_salvo and api_key_salva:
            entry_user_id.insert(0, user_id_salvo)
            entry_api_key.insert(0, api_key_salva)
            adicionar_log("📋 Credenciais carregadas automaticamente")
    except Exception as e:
        adicionar_log(f"⚠️ Não foi possível carregar credenciais salvas: {str(e)}")
    
    # Focar no primeiro campo vazio
    if not entry_user_id.get():
        entry_user_id.focus_set()
    elif not entry_api_key.get():
        entry_api_key.focus_set()
    else:
        btn_login.focus_set()
    
    # Mensagem inicial
    adicionar_log("🚀 Sistema de créditos PilarAnalyzer iniciado")
    adicionar_log("💡 Preencha suas credenciais e clique em 'Fazer Login'")
    adicionar_log("🔧 Use 'Testar Conexão' para verificar conectividade")
    adicionar_log("📴 Use 'Iniciar offline' para usar a interface sem gerar scripts")
    
    # Função para cancelar login
    def cancelar_login():
        resultado["sucesso"] = False
        resultado["credit_manager"] = None
        janela_login.destroy()
    
    # Garantir que a janela está visível antes de iniciar o loop
    try:
        janela_login.deiconify()  # Garantir que a janela está visível
        janela_login.lift()  # Trazer para frente
        janela_login.focus_force()  # Forçar foco
    except Exception as e:
        import traceback
        traceback.print_exc()
    
    # Executar loop da janela
    try:
        janela_login.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None
    
    # Aguardar um pouco para garantir que a janela foi completamente destruída
    # Isso evita conflitos com a criação da próxima janela Tkinter
    time.sleep(0.5)
    
    # Verificar se a janela foi fechada sem sucesso
    if not resultado["sucesso"]:
        return None
    
    # Retornar resultado
    if resultado["sucesso"]:
        return resultado["credit_manager"]
    else:
        return None

# ========================================================
# 🚀 Código Principal
# ========================================================

def executar_diagnostico_desenvolvimento():
    """Executar diagnóstico completo para desenvolvimento (apenas se compilado)"""
    try:
        if getattr(sys, 'frozen', False):
            try:
                from utils.sistema_diagnostico import SistemaDiagnostico
            except ImportError:
                try:
                    import sistema_diagnostico
                    SistemaDiagnostico = sistema_diagnostico.SistemaDiagnostico
                except ImportError:
                    return True
            
            diagnostico = SistemaDiagnostico()
            return diagnostico.executar_diagnostico_completo()
    except Exception:
        return False
    
    return True

def main():
    """Função principal do programa"""
    start_time = time.time()
    
    # Garantir que o diretório atual está no path do sistema
    import os
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Executar diagnóstico se compilado (para desenvolvimento)
    if getattr(sys, 'frozen', False):
        try:
            import threading
            diagnostico_thread = threading.Thread(target=executar_diagnostico_desenvolvimento)
            diagnostico_thread.daemon = True
            diagnostico_thread.start()
        except Exception:
            pass
    
    # Executar interface de login do sistema de créditos (substitui a validação antiga)
    try:
        from core.credit_system import definir_gerenciador_creditos
    except ImportError:
        try:
            import credit_system
            definir_gerenciador_creditos = credit_system.definir_gerenciador_creditos
        except ImportError:
            return False
    
    try:
        credit_manager = criar_interface_login()
    except Exception as e:
        # Log do erro para debug
        import traceback
        error_msg = f"Erro ao criar interface de login: {str(e)}\n{traceback.format_exc()}"
        try:
            # Tentar criar uma janela temporária para mostrar o erro
            error_window = tk.Tk()
            error_window.withdraw()  # Ocultar janela principal
            messagebox.showerror(
                "Erro ao Iniciar",
                f"Erro ao iniciar interface de login:\n\n{str(e)}\n\n"
                "Verifique os logs para mais detalhes."
            )
            error_window.destroy()
        except Exception:
            pass
        credit_manager = None
    
    if credit_manager is None:
        try:
            # Tentar criar uma janela temporária para mostrar a mensagem
            error_window = tk.Tk()
            error_window.withdraw()  # Ocultar janela principal
            messagebox.showerror(
                "Acesso Negado", 
                "Sistema de créditos não foi ativado.\n\n"
                "É necessário fazer login para usar o PilarAnalyzer.\n\n"
                "O programa será encerrado."
            )
            error_window.destroy()
        except Exception as e:
            pass
        import sys
        sys.exit(1)
    
    # Executar interface principal (Painel_de_Controle)
    try:
        import sys
        import os
        
        # Garantir que credit_manager está definido globalmente
        if credit_manager:
            definir_gerenciador_creditos(credit_manager)
        
        import sys
        
        # Importar e executar funcoes_auxiliares_2.PilarAnalyzer
        # Suporte completo para PyInstaller (frozen) e desenvolvimento
        is_frozen = getattr(sys, 'frozen', False)
        PilarAnalyzer = None
        
        # Tentar múltiplas formas de importação
        import_attempts = [
            lambda: __import__('src.utils.funcoes_auxiliares_2', fromlist=['PilarAnalyzer']).PilarAnalyzer,
            lambda: __import__('utils.funcoes_auxiliares_2', fromlist=['PilarAnalyzer']).PilarAnalyzer,
        ]
        
        # Se frozen, adicionar tentativas com _MEIPASS
        if is_frozen and hasattr(sys, '_MEIPASS'):
            meipass = sys._MEIPASS
            # Adicionar src/utils ao path se existir
            src_utils_mei = os.path.join(meipass, 'src', 'utils')
            if os.path.exists(src_utils_mei) and src_utils_mei not in sys.path:
                sys.path.insert(0, src_utils_mei)
            # Adicionar utils direto se existir
            utils_mei = os.path.join(meipass, 'utils')
            if os.path.exists(utils_mei) and utils_mei not in sys.path:
                sys.path.insert(0, utils_mei)
            # Adicionar src ao path
            src_mei = os.path.join(meipass, 'src')
            if os.path.exists(src_mei) and src_mei not in sys.path:
                sys.path.insert(0, src_mei)
            # Adicionar _MEIPASS ao path
            if meipass not in sys.path:
                sys.path.insert(0, meipass)
            
            import_attempts.insert(0, lambda: __import__('funcoes_auxiliares_2', fromlist=['PilarAnalyzer']).PilarAnalyzer)
        
        # Tentar importações relativas
        try:
            from ..utils.funcoes_auxiliares_2 import PilarAnalyzer
        except (ImportError, AttributeError, ValueError) as e:
            # Tentar importações absolutas
            for i, attempt in enumerate(import_attempts):
                try:
                    PilarAnalyzer = attempt()
                    break
                except (ImportError, AttributeError) as e:
                    continue
        
        # Se ainda não conseguiu, tentar importação dinâmica
        if PilarAnalyzer is None:
            try:
                import importlib
                # Tentar src.utils.funcoes_auxiliares_2
                try:
                    module = importlib.import_module('src.utils.funcoes_auxiliares_2')
                    PilarAnalyzer = module.PilarAnalyzer
                except (ImportError, AttributeError) as e:
                    # Tentar utils.funcoes_auxiliares_2
                    try:
                        module = importlib.import_module('utils.funcoes_auxiliares_2')
                        PilarAnalyzer = module.PilarAnalyzer
                    except (ImportError, AttributeError) as e:
                        # Tentar funcoes_auxiliares_2 direto
                        try:
                            module = importlib.import_module('funcoes_auxiliares_2')
                            PilarAnalyzer = module.PilarAnalyzer
                        except (ImportError, AttributeError) as e:
                            raise
            except (ImportError, AttributeError) as e:
                error_msg = f"Erro ao importar funcoes_auxiliares_2.PilarAnalyzer: {e}\n"
                error_msg += f"  Frozen: {is_frozen}\n"
                if is_frozen and hasattr(sys, '_MEIPASS'):
                    error_msg += f"  _MEIPASS: {sys._MEIPASS}\n"
                error_msg += f"  sys.path (primeiros 10): {sys.path[:10]}\n"
                try:
                    messagebox.showerror(
                        "Erro ao Iniciar",
                        f"Erro ao iniciar a interface principal:\n\n"
                        f"Não foi possível importar funcoes_auxiliares_2.py\n\n"
                        f"Verifique se todos os arquivos necessários estão presentes.\n\n"
                        f"Detalhes: {str(e)}"
                    )
                except Exception:
                    pass
                raise ImportError(f"Não foi possível importar PilarAnalyzer: {e}")
        
        if PilarAnalyzer is None:
            raise ImportError("Nao foi possivel importar PilarAnalyzer apos todas as tentativas")
        
        try:
            app = PilarAnalyzer()
            
            # Injetar credit_manager na instância se necessário
            if credit_manager:
                if hasattr(app, 'definir_credit_manager'):
                    app.definir_credit_manager(credit_manager)
                else:
                    try:
                        app.credit_manager = credit_manager
                        if hasattr(app, 'atualizar_creditos_interface'):
                            app.atualizar_creditos_interface()
                    except Exception:
                        pass
            
            # CRITICO: Garantir que a janela seja exibida corretamente
            try:
                app.update_idletasks()
                app.update()
                # Verificar se a janela está oculta e exibir
                try:
                    app.deiconify()
                except:
                    pass
            except Exception as e:
                import traceback
                traceback.print_exc()
            
            app.mainloop()
        except tk.TclError:
            raise
        except Exception:
            raise
                    
    except Exception as e:
        tk.messagebox.showerror("Erro", f"Erro ao iniciar a interface principal: {str(e)}\n\nVerifique se todos os arquivos necessários estão presentes.")
        return False
    
    return True

if __name__ == "__main__":
    main() 