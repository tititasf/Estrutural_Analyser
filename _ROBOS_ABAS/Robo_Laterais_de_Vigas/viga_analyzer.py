"""
========================================================
�� Título do Arquivo: viga_analyzer.py
📆 Data de Criação: 23/03/2024
✏️ Autor: Claude & User
🆔 Versão: 1.1
========================================================

🔷 **Prompt Inicial**
Script principal para RoboLateraisViga com sistema de licenciamento online.

📖 **Registro de Desenvolvimento**
🔹 **Parte 1 - Estrutura Inicial**  
📆 23/03/2024: Criada a estrutura inicial do código com sistema de licenciamento.
🔹 **Parte 2 - Otimização da Ativação**
📆 22/03/2025: Otimizado o processo de ativação para execução mais leve.

🔹 **Índice do Código**
1️⃣ [Linha 1-20]📥 Importações  
2️⃣ [Linha 21-55] 🛡️ Sistema de Licenciamento  
3️⃣ [Linha 56-70] 🚀 Código Principal  

📎 **Arquivos Relacionados**
- `robo_laterais_viga_limpo233.py`: Contém a classe principal RoboLateraisViga
- `funcoes_auxiliares.py`: Funções auxiliares para processamento
- `template_robo.xlsx`: Template Excel para exportação
- `fundos_salvos.json`: Arquivo de dados salvos  

📊 **Resumo Geral**
Este script é o ponto de entrada principal para o aplicativo RoboLateraisViga com sistema de licenciamento online.
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

# Importações pesadas colocadas após verificação de licença
requests = None

# Garantir que os módulos do projeto sejam encontrados
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# ========================================================
# 🛡️ Sistema de Licenciamento
# ========================================================

# Substituir pelos valores corretos (serão atualizados no setup.py):
SHEET_ID = "1m7CNUU_iuG79R5OazQkAVq60SpPYYPe36lrRJwoH8Fg"
API_KEY = "AIzaSyD1anb0R8w9mjQcIFyK8pFG4smFZnaDB0s"

# URL para buscar as licenças do Google Sheets
SHEET_URL = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/A:A?key={API_KEY}"

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
        
        response = requests.get(SHEET_URL, timeout=10)
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
        data_atual = datetime.datetime.now()
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
        data_atual = datetime.datetime.now()
        data_expiracao = datetime.datetime.fromisoformat(info_licenca["expira_em"])
        
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
    janela_licenca.title("Ativação do RoboLateraisViga")
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
    ttk.Label(main_frame, text="RoboLateraisViga", font=("Arial", 16, "bold")).pack(pady=10)
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
    hwid_texto = f"HWID: {obter_hwid()[:8]}"
    ttk.Label(main_frame, text=hwid_texto, font=("Arial", 8)).pack(side=tk.BOTTOM, pady=2)
    
    # Vincular tecla Enter para validar
    entrada_chave.bind('<Return>', lambda event: validar_licenca_thread())
    entrada_chave.focus_set()
    
    # Mensagem inicial no log
    adicionar_log("Sistema de ativação do RoboLateraisViga iniciado.")
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
# 🚀 Código Principal
# ========================================================

def main():
    """Função principal do programa"""
    # Garantir que o diretório atual está no path do sistema
    # para evitar problemas de importação após compilação
    import os
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Verificar licença
    try:
        arquivo_licenca = os.path.join(current_dir, ".licenca")
        if os.path.exists(arquivo_licenca):
            with open(arquivo_licenca, "r") as f:
                chave = f.read().strip()
                # Não verificar online aqui, apenas abrir a interface
                if not solicitar_licenca_gui():
                    return
        else:
            # Se não houver arquivo de licença, solicitar licença
            if not solicitar_licenca_gui():
                return
    except Exception as e:
        # Em caso de erro, solicitar licença
        print(f"Erro ao verificar licença: {str(e)}")
        if not solicitar_licenca_gui():
            return
    
    # Importar os módulos necessários apenas após validação da licença
    try:
        # Tentar importação normal primeiro
        try:
            from robo_laterais_viga_limpo233 import RoboLateraisViga
        except (ImportError, ModuleNotFoundError):
            # Se falhar, usar importação dinâmica
            import importlib.util
            
            # Procurar módulo no mesmo diretório
            module_path = os.path.join(current_dir, "robo_laterais_viga_limpo233.py")
            if not os.path.exists(module_path):
                # Se o arquivo .py não existir, pode estar compilado como .pyc ou dentro do executável
                # Tentar importação baseada no nome
                spec = importlib.util.find_spec("robo_laterais_viga_limpo233")
                if spec is None:
                    raise ImportError(f"Não foi possível localizar o módulo 'robo_laterais_viga_limpo233'")
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                RoboLateraisViga = module.RoboLateraisViga
            else:
                # Caso o arquivo exista, importar diretamente
                spec = importlib.util.spec_from_file_location("robo_laterais_viga_limpo233", module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                RoboLateraisViga = module.RoboLateraisViga
        
        # Iniciar o aplicativo
        app = RoboLateraisViga()
        app.mainloop()
    except Exception as e:
        import traceback
        print(f"Erro ao iniciar o aplicativo: {str(e)}")
        traceback.print_exc()
        tk.messagebox.showerror("Erro", f"Erro ao iniciar o aplicativo: {str(e)}\n\nVerifique se todos os arquivos necessários estão presentes.")
        return

if __name__ == "__main__":
    main() 