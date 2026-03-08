
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

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from pathlib import Path
import os
import sys
from natsort import natsorted

# IMPORTAR HELPER FROZEN GLOBAL - garante que paths estão configurados
try:
    from _frozen_helper import ensure_paths
    ensure_paths()
except ImportError:
    try:
        from src._frozen_helper import ensure_paths
        ensure_paths()
    except ImportError:
        try:
            from _ensure_frozen import ensure
            ensure()
        except ImportError:
            # Fallback manual
            if getattr(sys, 'frozen', False):
                script_dir = os.path.dirname(sys.executable)
                if script_dir not in sys.path:
                    sys.path.insert(0, script_dir)
                src_dir = os.path.join(script_dir, 'src')
                if os.path.exists(src_dir) and src_dir not in sys.path:
                    sys.path.insert(0, src_dir)
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                parent_dir = os.path.dirname(current_dir)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)

# Importar Ordenador_Cordenadas_cima com múltiplos fallbacks
try:
    from ..robots.Ordenador_Cordenadas_cima import ProcessadorCoordenadasCima, atualizar_comando_pilar_cima
except ImportError:
    try:
        from robots.Ordenador_Cordenadas_cima import ProcessadorCoordenadasCima, atualizar_comando_pilar_cima
    except ImportError:
        try:
            from src.robots.Ordenador_Cordenadas_cima import ProcessadorCoordenadasCima, atualizar_comando_pilar_cima
        except ImportError:
            try:
                robots_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'robots')
                if robots_dir not in sys.path:
                    sys.path.append(robots_dir)
                from Ordenador_Cordenadas_cima import ProcessadorCoordenadasCima, atualizar_comando_pilar_cima
            except ImportError:
                # Fallback para subprocess se não conseguir importar
                import subprocess
                ProcessadorCoordenadasCima = None
                atualizar_comando_pilar_cima = None

class ConfiguracaoOrdenadorCima:
    def __init__(self):
        # Usar path resolver para encontrar os caminhos corretos
        try:
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from utils.robust_path_resolver import robust_path_resolver
            project_root = robust_path_resolver.get_project_root()
        except:
            # Fallback se não conseguir importar
            project_root = Path(__file__).parent.parent.parent
        
        self.config_file = Path(project_root) / "config" / "configuracao_ordenador_CIMA.json"
        self.templates_dir = Path(project_root) / "config"  # Templates agora estão em config
        self.templates_dir.mkdir(exist_ok=True)
        self.carregar_configuracao()

    def carregar_configuracao(self):
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "numero_colunas": 3,
                "distancia_x_colunas": 1200,
                "distancia_y_linhas": -1000,
                "distancia_y_extra": 200,
                "linhas_para_extra": 2,
                "template_atual": "padrao"
            }
            self.salvar_configuracao()

    def salvar_configuracao(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)

    def listar_templates(self):
        # Filtrar apenas templates que começam com "templates_"
        templates = []
        for f in self.templates_dir.glob("*.json"):
            if f.stem.startswith("templates_"):
                templates.append(f.stem)
        return templates

    def salvar_template(self, nome):
        template_path = self.templates_dir / f"{nome}.json"
        with open(template_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)

    def carregar_template(self, nome):
        template_path = self.templates_dir / f"{nome}.json"
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
                # Se é um template de configuração, pegar o primeiro item
                if isinstance(template_data, dict) and len(template_data) > 0:
                    # Verificar se tem a estrutura de template antigo ou novo
                    first_key = list(template_data.keys())[0]
                    if first_key in ["numero_colunas", "distancia_x_colunas"]:
                        # Template simples - usar diretamente
                        self.config = template_data
                    else:
                        # Template complexo - pegar configurações básicas do primeiro item
                        template_item = template_data[first_key]
                        self.config = {
                            "numero_colunas": template_item.get("numero_colunas", 4),
                            "distancia_x_colunas": template_item.get("distancia_x_colunas", 1585),
                            "distancia_y_linhas": template_item.get("distancia_y_linhas", -1148.6),
                            "distancia_y_extra": template_item.get("distancia_y_extra", 0),
                            "linhas_para_extra": template_item.get("linhas_para_extra", 0),
                            "template_atual": nome
                        }
                else:
                    return False
            self.salvar_configuracao()
            return True
        return False

    def excluir_template(self, nome):
        template_path = self.templates_dir / f"{nome}.json"
        if template_path.exists():
            template_path.unlink()
            return True
        return False

class JanelaConfiguracaoCima:
    def __init__(self, parent, config_manager):
        self.janela = tk.Toplevel(parent)
        self.janela.title("Configurações do Ordenador CIMA")
        self.janela.geometry("500x600")
        self.config_manager = config_manager
        
        # Recarregar configuração para refletir templates salvos dinamicamente
        print("[CONFIGURAÇÃO] Recarregando configuração CIMA para refletir templates salvos")
        self.config_manager.carregar_configuracao()
        
        # Frame principal
        frame_principal = ttk.Frame(self.janela, padding="10")
        frame_principal.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Frame para configurações principais
        frame_config = ttk.LabelFrame(frame_principal, text="Configurações Principais", padding="10")
        frame_config.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 1. Quantidade de colunas
        ttk.Label(frame_config, text="Quantidade de Colunas:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_colunas = ttk.Entry(frame_config, width=15)
        self.entry_colunas.insert(0, str(self.config_manager.config.get("numero_colunas", 3)))
        self.entry_colunas.grid(row=0, column=1, padx=5, pady=5)
        
        # 2. Distância X entre colunas
        ttk.Label(frame_config, text="Distância X entre Colunas:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_distancia_x = ttk.Entry(frame_config, width=15)
        self.entry_distancia_x.insert(0, str(self.config_manager.config.get("distancia_x_colunas", 1200)))
        self.entry_distancia_x.grid(row=1, column=1, padx=5, pady=5)
        
        # 3. Distância Y entre linhas
        ttk.Label(frame_config, text="Distância Y entre Linhas:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_distancia_y = ttk.Entry(frame_config, width=15)
        self.entry_distancia_y.insert(0, str(self.config_manager.config.get("distancia_y_linhas", -1000)))
        self.entry_distancia_y.grid(row=2, column=1, padx=5, pady=5)
        
        # 4. Distância Y extra
        ttk.Label(frame_config, text="Distância Y Extra:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_y_extra = ttk.Entry(frame_config, width=15)
        self.entry_y_extra.insert(0, str(self.config_manager.config.get("distancia_y_extra", 200)))
        self.entry_y_extra.grid(row=3, column=1, padx=5, pady=5)
        
        # 5. A cada quantas linhas aplicar Y extra
        ttk.Label(frame_config, text="A cada quantas linhas aplicar Y extra:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_linhas_extra = ttk.Entry(frame_config, width=15)
        self.entry_linhas_extra.insert(0, str(self.config_manager.config.get("linhas_para_extra", 2)))
        self.entry_linhas_extra.grid(row=4, column=1, padx=5, pady=5)
        
        # Frame para templates
        frame_templates = ttk.LabelFrame(frame_principal, text="Templates", padding="10")
        frame_templates.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # Lista de templates
        self.lista_templates = tk.Listbox(frame_templates, height=5)
        self.lista_templates.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        self.atualizar_lista_templates()
        
        # Botões de template
        frame_botoes_template = ttk.Frame(frame_templates)
        frame_botoes_template.grid(row=1, column=0, columnspan=2, pady=5)
        
        ttk.Button(frame_botoes_template, text="Carregar", command=self.carregar_template).grid(row=0, column=0, padx=5)
        ttk.Button(frame_botoes_template, text="Excluir", command=self.excluir_template).grid(row=0, column=1, padx=5)
        
        # Frame para salvar template
        frame_salvar_template = ttk.Frame(frame_templates)
        frame_salvar_template.grid(row=2, column=0, columnspan=2, pady=5)
        
        self.entry_nome_template = ttk.Entry(frame_salvar_template, width=20)
        self.entry_nome_template.grid(row=0, column=0, padx=5)
        ttk.Button(frame_salvar_template, text="Salvar Template", command=self.salvar_template).grid(row=0, column=1, padx=5)
        
        # Botões de ação
        frame_botoes = ttk.Frame(frame_principal)
        frame_botoes.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(frame_botoes, text="Salvar", command=self.salvar_configuracao).grid(row=0, column=0, padx=5)
        ttk.Button(frame_botoes, text="Cancelar", command=self.janela.destroy).grid(row=0, column=1, padx=5)

    def atualizar_lista_templates(self):
        self.lista_templates.delete(0, tk.END)
        for template in self.config_manager.listar_templates():
            self.lista_templates.insert(tk.END, template)

    def salvar_template(self):
        nome = self.entry_nome_template.get().strip()
        if nome:
            self.config_manager.salvar_template(nome)
            self.atualizar_lista_templates()
            self.entry_nome_template.delete(0, tk.END)
            messagebox.showinfo("Sucesso", f"Template '{nome}' salvo com sucesso!")
        else:
            messagebox.showwarning("Aviso", "Digite um nome para o template!")

    def carregar_template(self):
        selecao = self.lista_templates.curselection()
        if selecao:
            nome = self.lista_templates.get(selecao[0])
            if self.config_manager.carregar_template(nome):
                self.atualizar_campos()
                messagebox.showinfo("Sucesso", f"Template '{nome}' carregado com sucesso!")
            else:
                messagebox.showerror("Erro", f"Erro ao carregar template '{nome}'!")
        else:
            messagebox.showwarning("Aviso", "Selecione um template para carregar!")

    def excluir_template(self):
        selecao = self.lista_templates.curselection()
        if selecao:
            nome = self.lista_templates.get(selecao[0])
            if messagebox.askyesno("Confirmar", f"Deseja realmente excluir o template '{nome}'?"):
                if self.config_manager.excluir_template(nome):
                    self.atualizar_lista_templates()
                    messagebox.showinfo("Sucesso", f"Template '{nome}' excluído com sucesso!")
                else:
                    messagebox.showerror("Erro", f"Erro ao excluir template '{nome}'!")
        else:
            messagebox.showwarning("Aviso", "Selecione um template para excluir!")

    def atualizar_campos(self):
        """Atualiza todos os campos com os valores da configuração atual"""
        self.entry_colunas.delete(0, tk.END)
        self.entry_colunas.insert(0, str(self.config_manager.config.get("numero_colunas", 3)))
        
        self.entry_distancia_x.delete(0, tk.END)
        self.entry_distancia_x.insert(0, str(self.config_manager.config.get("distancia_x_colunas", 1200)))
        
        self.entry_distancia_y.delete(0, tk.END)
        self.entry_distancia_y.insert(0, str(self.config_manager.config.get("distancia_y_linhas", -1000)))
        
        self.entry_y_extra.delete(0, tk.END)
        self.entry_y_extra.insert(0, str(self.config_manager.config.get("distancia_y_extra", 200)))
        
        self.entry_linhas_extra.delete(0, tk.END)
        self.entry_linhas_extra.insert(0, str(self.config_manager.config.get("linhas_para_extra", 2)))

    def salvar_configuracao(self):
        try:
            # Valida e salva todas as configurações
            self.config_manager.config["numero_colunas"] = int(self.entry_colunas.get())
            self.config_manager.config["distancia_x_colunas"] = float(self.entry_distancia_x.get())
            self.config_manager.config["distancia_y_linhas"] = float(self.entry_distancia_y.get())
            self.config_manager.config["distancia_y_extra"] = float(self.entry_y_extra.get())
            self.config_manager.config["linhas_para_extra"] = int(self.entry_linhas_extra.get())
            
            self.config_manager.salvar_configuracao()
            messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")
            self.janela.destroy()
        except ValueError as e:
            messagebox.showerror("Erro", "Todos os campos devem conter valores numéricos válidos!")

class InterfaceOrdenadorCima:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Ordenador de Coordenadas CIMA")
        self.root.geometry("400x250")
        
        self.config_manager = ConfiguracaoOrdenadorCima()
        
        # Frame principal
        frame_principal = ttk.Frame(self.root, padding="20")
        frame_principal.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Título
        ttk.Label(frame_principal, text="Ordenador de Coordenadas CIMA", font=("Arial", 14, "bold")).grid(row=0, column=0, pady=10)
        
        # Botões
        ttk.Button(frame_principal, text="Selecionar Pasta", command=self.selecionar_pasta).grid(row=1, column=0, pady=10)
        ttk.Button(frame_principal, text="Configurações", command=self.abrir_configuracoes).grid(row=2, column=0, pady=10)
        
        # Status
        self.label_status = ttk.Label(frame_principal, text="Pronto para processar")
        self.label_status.grid(row=3, column=0, pady=10)

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta com os arquivos SCR")
        if pasta:
            self.label_status.config(text="Processando...")
            self.root.update()
            
            try:
                # Cria processador com as configurações atuais
                config = self.config_manager.config
                processador = ProcessadorCoordenadasCima(
                    numero_colunas=config.get("numero_colunas", 3),
                    distancia_x_colunas=config.get("distancia_x_colunas", 1200),
                    distancia_y_linhas=config.get("distancia_y_linhas", -1000),
                    distancia_y_extra=config.get("distancia_y_extra", 200),
                    linhas_para_extra=config.get("linhas_para_extra", 2)
                )
                
                # Processa os arquivos
                arquivos = natsorted([f for f in os.listdir(pasta) if f.endswith('.scr')])
                
                self.label_status.config(text=f"Processando {len(arquivos)} arquivos...")
                self.root.update()
                
                for arquivo in arquivos:
                    caminho_completo = os.path.join(pasta, arquivo)
                    processador.processar_arquivo(caminho_completo)
                
                atualizar_comando_pilar_cima(pasta)
                self.label_status.config(text="Processamento concluído com sucesso!")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro durante o processamento: {str(e)}")
                self.label_status.config(text="Erro no processamento")

    def abrir_configuracoes(self):
        JanelaConfiguracaoCima(self.root, self.config_manager)

    def iniciar(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = InterfaceOrdenadorCima()
    app.iniciar()