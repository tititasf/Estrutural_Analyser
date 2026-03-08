
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

from difflib import restore
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import math
import re
from datetime import datetime
import logging
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import win32com.client
import pyautogui
import time
from typing import List, Tuple, Optional, Union
import json
import copy

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

# Configurar logging
logging.basicConfig(
    filename='pilares.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ConfigManager:
    def __init__(self, config_file: str = "config_abcd.json"):
        # Garantir que sys está importado no escopo local
        import sys
        
        # Usar sistema de paths robusto que funciona em frozen e desenvolvimento
        try:
            from config_paths import CONFIG_DIR, TEMPLATES_DIR
            self.config_file = os.path.join(CONFIG_DIR, config_file)
            self.templates_file = os.path.join(TEMPLATES_DIR, "templates_pilar_abcd.json")
        except ImportError:
            # Fallback usando robust_path_resolver com múltiplos fallbacks
            try:
                from utils.robust_path_resolver import robust_path_resolver
                project_root = robust_path_resolver.get_project_root()
            except ImportError:
                try:
                    from src.utils.robust_path_resolver import robust_path_resolver
                    project_root = robust_path_resolver.get_project_root()
                except ImportError:
                    # Fallback final para estrutura relativa
                    if getattr(sys, 'frozen', False):
                        project_root = os.path.dirname(sys.executable)
                    else:
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(current_dir))
            
            # Usar caminhos relativos baseados na nova estrutura (tudo em config)
            self.config_file = os.path.join(project_root, "config", config_file)
            self.templates_file = os.path.join(project_root, "config", "templates_pilar_abcd.json")
        self.config = self.load_config()
        self.templates = self.load_templates()

    def load_config(self) -> dict:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Verifica se há chaves com encoding incorreto e corrige
                    if "layers" in loaded_config:
                        layers = loaded_config["layers"]
                        # Corrigir "painÃ©is" para "paineis_abcd"
                        if "painÃ©is" in layers:
                            layers["paineis_abcd"] = layers.pop("painÃ©is")
                        # Corrigir "nÃ­vel" para "nivel" se existir
                        if "nÃ­vel" in layers:
                            layers["nivel"] = layers.pop("nÃ­vel")
                    return loaded_config
            return self.get_default_config()
        except Exception as e:
            logging.error(f"Erro ao carregar configurações: {str(e)}")
            return self.get_default_config()

    def get_default_config(self) -> dict:
        """Retorna configurações padrão sem valores predefinidos"""
        return {
            "layers": {
                "paineis_abcd": 0,
                "pe_direito": 0,
                "cotas": 0,
                "sarrafos": 0,
                "nomenclatura": 0,
                "laje": 0,
                "textos_titulos": 0,
                "linhas_hidden": 0  # Novo campo para layer das linhas hidden
            },
            "blocks": {
                "furacao": None,
                "split_ee": None,
                "split_dd": None,
                "moldura": None,
                "numeracao": {
                    "ativar": False,
                    "n1": "n1",
                    "n2": "n2", 
                    "n3": "n3",
                    "n4": "n4",
                    "n5": "n5"
                }
            },
            "abertura_commands": {
                "normal": {
                    "esquerda": None,
                    "direita": None,
                    "centro": None
                },
                "pequena": {
                    "esquerda": None,
                    "direita": None
                },
                "ajuste": {
                    "esquerda": None,
                    "direita": None,
                    "pre_abertura": None
                }
            },
            "hatch_commands": {
                "simples": None,
                "duplo": None,
                "centro": None,
                "laje": None,
                "paineis_sem_recorte": None,
                "paineis_com_recorte": None
            },
            "drawing_options": {
                "zoom_factor": 10,
                "cota_offset": 15,
                "texto_offset": 20,
                "sarrafo_offset": 7,
                "cotas_furacao_vertical": False,  # Valor padrão alterado para False
                "cotas_furacao_horizontal": False,  # Valor padrão alterado para False
                "modo_sarrafos": "Pline",  # Opções: "Pline" ou "MLINE"
                "desenhar_sarrafos_cd": True,  # Nova opção para controlar sarrafos C e D
                "espacamento_base": 30,
                "espacamento_vertical": 50,
                "espacamento_parafusos": 50,
                "offset_parafuso": 24,
                "offset_moldura": 38,
                "offset_texto_info": {
                    "x": 30,
                    "y": 680
                },
                "offset_painel": {
                    "inicial": 115,
                    "entre_paineis": 115
                },
                "linetype_pedireito": "DASHED",
                "linetype_sarrafos_hidden": "DASHED"
            },
            "dimensoes_padrao": {
                "altura_h1": 2,
                "max_altura_ab": 122,
                "max_altura_cd": 244,
                "max_largura_ab": 244,
                "max_largura_cd": 122,
                "min_abertura_normal": 12,
                "min_abertura_pequena": 7
            },
            "parafusos": {
                "ab": {
                    "medida_fundo_primeiro_ab": 30,
                    "medida_1_2_ab": 50,
                    "medida_2_3_ab": 55,
                    "medida_3_4_ab": 55,
                    "medida_4_5_ab": 55,
                    "medida_5_6_ab": 55,
                    "medida_6_7_ab": 55,
                    "medida_7_8_ab": 55,
                    "medida_8_9_ab": 55,
                    "medida_9_10_ab": 55
                },
                "cdefgh": {
                    "medida_fundo_primeiro_cdefgh": 30,
                    "medida_1_2_cdefgh": 50,
                    "medida_2_3_cdefgh": 55,
                    "medida_3_4_cdefgh": 55,
                    "medida_4_5_cdefgh": 55,
                    "medida_5_6_cdefgh": 55,
                    "medida_6_7_cdefgh": 55,
                    "medida_7_8_cdefgh": 55,
                    "medida_8_9_cdefgh": 55,
                    "medida_9_10_cdefgh": 55
                }
            }
        }

    def save_config(self) -> None:
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logging.error(f"Erro ao salvar configurações: {str(e)}")

    def get_config(self, *keys: str) -> Optional[Union[str, dict]]:
        try:
            value = self.config
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return None

    def load_templates(self) -> dict:
        """Carrega os templates salvos."""
        try:
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Erro ao carregar templates: {str(e)}")
        return {}

    def save_template(self, template_name: str, config: dict, sobrescrever: bool = False):
        """
        Salva um novo template. 
        
        Args:
            template_name: Nome do template
            config: Configuração a ser salva
            sobrescrever: Se True, sobrescreve template existente. Se False, adiciona sufixo numérico.
                         Para templates "NOVA" e "INI", sempre sobrescreve para garantir que os roundbuttons funcionem.
        """
        # Templates especiais "NOVA" e "INI" sempre sobrescrevem para garantir funcionamento dos roundbuttons
        if template_name.upper() in ["NOVA", "INI"]:
            sobrescrever = True
        
        # Debug: verificar se parafusos está no config
        if "parafusos" in config:
            ab_val = config.get("parafusos", {}).get("ab", {}).get("medida_fundo_primeiro_ab", "N/A")
            cdefgh_val = config.get("parafusos", {}).get("cdefgh", {}).get("medida_fundo_primeiro_cdefgh", "N/A")
            print(f"[DEBUG CONFIGMANAGER] Salvando template '{template_name}' com parafusos AB={ab_val}, CDEFGH={cdefgh_val}")
            print(f"[DEBUG CONFIGMANAGER] Estrutura de parafusos recebida: {json.dumps(config.get('parafusos', {}), indent=2)}")
        else:
            print(f"[DEBUG CONFIGMANAGER] ⚠️ Config não contém seção 'parafusos'!")
        
        # Verificar se o template já existe
        if template_name in self.templates:
            if sobrescrever:
                logging.info(f"Template '{template_name}' já existe. Sobrescrevendo...")
                print(f"[DEBUG CONFIGMANAGER] Template '{template_name}' será sobrescrito")
            else:
                # Encontrar o próximo sufixo disponível
                base_name = template_name
                suffix = 1
                while f"{base_name}.{suffix}" in self.templates:
                    suffix += 1
                template_name = f"{base_name}.{suffix}"
                logging.info(f"Template '{base_name}' já existe. Salvando como '{template_name}'")
                print(f"[DEBUG CONFIGMANAGER] Template '{base_name}' será salvo como '{template_name}'")
        
        # Criar cópia profunda para garantir que os dados sejam preservados
        self.templates[template_name] = copy.deepcopy(config)
        
        # Verificar o que foi salvo
        if "parafusos" in self.templates[template_name]:
            ab_val_salvo = self.templates[template_name].get("parafusos", {}).get("ab", {}).get("medida_fundo_primeiro_ab", "N/A")
            cdefgh_val_salvo = self.templates[template_name].get("parafusos", {}).get("cdefgh", {}).get("medida_fundo_primeiro_cdefgh", "N/A")
            print(f"[DEBUG CONFIGMANAGER] Valores salvos no template: AB={ab_val_salvo}, CDEFGH={cdefgh_val_salvo}")
        else:
            print(f"[DEBUG CONFIGMANAGER] ⚠️ Template salvo não contém seção 'parafusos'!")
        
        try:
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, indent=4, ensure_ascii=False)
            print(f"[DEBUG CONFIGMANAGER] ✅ Template '{template_name}' salvo no arquivo: {self.templates_file}")
            
            # Verificar o que foi escrito no arquivo
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    templates_carregados = json.load(f)
                    if template_name in templates_carregados:
                        if "parafusos" in templates_carregados[template_name]:
                            ab_val_arquivo = templates_carregados[template_name].get("parafusos", {}).get("ab", {}).get("medida_fundo_primeiro_ab", "N/A")
                            cdefgh_val_arquivo = templates_carregados[template_name].get("parafusos", {}).get("cdefgh", {}).get("medida_fundo_primeiro_cdefgh", "N/A")
                            print(f"[DEBUG CONFIGMANAGER] ✅ Valores no arquivo: AB={ab_val_arquivo}, CDEFGH={cdefgh_val_arquivo}")
                        else:
                            print(f"[DEBUG CONFIGMANAGER] ⚠️ Template no arquivo não contém seção 'parafusos'!")
        except Exception as e:
            logging.error(f"Erro ao salvar template: {str(e)}")
            print(f"[DEBUG CONFIGMANAGER] ❌ Erro ao salvar template: {e}")
            import traceback
            traceback.print_exc()

    def delete_template(self, template_name: str):
        """Remove um template existente."""
        if template_name in self.templates:
            del self.templates[template_name]
            try:
                with open(self.templates_file, 'w', encoding='utf-8') as f:
                    json.dump(self.templates, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logging.error(f"Erro ao deletar template: {str(e)}")

class PainelData:
    def __init__(self):
        self.alturas = []
        self.larguras = []
        self.laje = {
            "altura": 0.0,
            "posicao": 0
        }
        self.aberturas = []

    def add_altura(self, altura: float) -> None:
        self.alturas.append(altura)

    def add_largura(self, largura: float) -> None:
        self.larguras.append(largura)

    def set_laje(self, altura: float, posicao: int) -> None:
        self.laje["altura"] = altura
        self.laje["posicao"] = posicao

    def add_abertura(self, abertura: dict) -> None:
        self.aberturas.append(abertura)

class AplicacaoUnificada:
    def __init__(self):
        try:
            self.root = tk.Tk()
            self.root.title("Gerador de Pilares")
            self.root.state('zoomed')  # Iniciar maximizado
            
            # Inicializar gerenciador de configurações
            self.config_manager = ConfigManager()
            
            # Configurar estilo
            style = ttk.Style()
            style.configure('TNotebook.Tab', padding=[12, 4])
            
            # Criar notebook para abas
            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(fill='both', expand=True)
            
            # Criar frames para cada aba
            self.frame_gerador = ttk.Frame(self.notebook)
            
            # Adicionar frames ao notebook em ordem invertida
            self.notebook.add(self.frame_gerador, text='VISAO ABCD') # Depois adiciona a VISÃO ABCD
            
            # Passar a referência 'self' (AplicacaoUnificada) para as classes
            self.gerador_pilares = GeradorPilares(self.frame_gerador, master=self)
            
            # Configurar redimensionamento
            self.root.grid_columnconfigure(0, weight=1)
            self.root.grid_rowconfigure(0, weight=1)
            
            logging.info("Aplicação inicializada com sucesso")
            
            # Variável para armazenar o resultado da sincronização
            self.sincronizacao_sucesso = tk.BooleanVar(self.root, value=False)
            self.sincronizando_locks = False  # Flag para evitar loop infinito
            
        except Exception as e:
            logging.error(f"Erro ao inicializar aplicação: {str(e)}")
            raise

    def iniciar(self):
        try:
            self.root.mainloop()
        except Exception as e:
            logging.error(f"Erro durante execução da aplicação: {str(e)}")
            raise

    def registrar_sincronizacao(self, sucesso):
        """Registra o resultado da sincronização."""
        self.sincronizacao_sucesso.set(sucesso)

    def sincronizar_locks_parafusos(self, interface_origem, indice):
        """Sincroniza os locks dos parafusos entre as interfaces.

        Args:
            interface_origem: A interface onde o lock foi alterado ('abcd' ou 'cima').
            indice: O índice do lock que foi alterado (0 a 7).
        """
        if self.sincronizando_locks:
            return  # Evita loop infinito

        self.sincronizando_locks = True  # Ativa a flag

        try:
            if interface_origem == 'abcd':
                pass #remove pass
        finally:
            self.sincronizando_locks = False  # Desativa a flag

# Classe GeradorPilares existente
class GeradorPilares:
    def __init__(self, parent, master=None):
        self.root = parent
        self.master = master  # Adicionar a referência master
        
        # Acessar o gerenciador de configurações através do master
        self.config_manager = self.master.config_manager if self.master else ConfigManager()
        
        # Configurar estilos
        self.configurar_estilos()
        
        # Coordenadas iniciais
        self.x_inicial = -7000
        self.y_inicial = -100
        
        # Dicionários para armazenar campos
        self.campos = {}
        self.campos_ab = {}
        self.campos_cd = {}
        self.campos_altura = {}
        
        # Dicionários para armazenar locks
        self.largura_locks = {
            'a': [], 'b': [], 'c': [], 'd': []
        }
        self.altura_locks = {
            'a': [], 'b': [], 'c': [], 'd': []
        }
        
        # Variáveis para posição das lajes
        self.pos_laje_a = tk.IntVar(self.root, value=0)
        self.pos_laje_b = tk.IntVar(self.root, value=0)
        self.pos_laje_c = tk.IntVar(self.root, value=0)
        self.pos_laje_d = tk.IntVar(self.root, value=0)
        
        # Variáveis para os campos de laje
        self.laje_a_var = tk.StringVar(self.root)
        self.laje_b_var = tk.StringVar(self.root)
        self.laje_c_var = tk.StringVar(self.root)
        self.laje_d_var = tk.StringVar(self.root)
        
        # Configurar callbacks
        self.laje_a_var.trace_add("write", lambda *args: self.atualizar_posicao_laje('a'))
        self.laje_b_var.trace_add("write", lambda *args: self.atualizar_posicao_laje('b'))
        self.laje_c_var.trace_add("write", lambda *args: self.atualizar_posicao_laje('c'))
        self.laje_d_var.trace_add("write", lambda *args: self.atualizar_posicao_laje('d'))
        
        # Variáveis booleanas para join de sarrafos
        self.join_sarrafos_a = tk.BooleanVar(self.root)
        self.join_sarrafos_b = tk.BooleanVar(self.root)
        self.join_sarrafos_c = tk.BooleanVar(self.root)
        self.join_sarrafos_d = tk.BooleanVar(self.root)
        
        # Variáveis booleanas para sarrafos horizontais
        self.sarrafo_horizontal_a = tk.BooleanVar(self.root)
        self.sarrafo_horizontal_b = tk.BooleanVar(self.root)
        
        # Listas para armazenar as opções de hatch
        # Inicializar com 5 linhas e 3 colunas para cada painel
        self.hatch_opcoes_a = [[tk.StringVar(value="0") for _ in range(3)] for _ in range(5)]
        self.hatch_opcoes_b = [[tk.StringVar(value="0") for _ in range(3)] for _ in range(5)]
        self.hatch_opcoes_c = [[tk.StringVar(value="0") for _ in range(3)] for _ in range(5)]
        self.hatch_opcoes_d = [[tk.StringVar(value="0") for _ in range(3)] for _ in range(5)]
        
        # Variáveis para os locks dos parafusos em ABCD
        self.parafuso_locks_abcd = [tk.BooleanVar(value=False) for _ in range(8)]
        
        # Adicionar variáveis para os campos de abertura de laje (1=laje, 0=normal)
        self.abertura_laje = {
            'a': {
                'esq1': tk.StringVar(value="0"), 
                'esq2': tk.StringVar(value="0"),
                'dir1': tk.StringVar(value="0"),
                'dir2': tk.StringVar(value="0")
            },
            'b': {
                'esq1': tk.StringVar(value="0"),
                'esq2': tk.StringVar(value="0"), 
                'dir1': tk.StringVar(value="0"),
                'dir2': tk.StringVar(value="0")
            },
            'c': {
                'esq1': tk.StringVar(value="0"),
                'esq2': tk.StringVar(value="0"),
                'dir1': tk.StringVar(value="0"),
                'dir2': tk.StringVar(value="0")
            },
            'd': {
                'esq1': tk.StringVar(value="0"),
                'esq2': tk.StringVar(value="0"),
                'dir1': tk.StringVar(value="0"),
                'dir2': tk.StringVar(value="0")
            }
        }
        
        # Adicionar variáveis para os checkboxes de abertura do topo2
        self.abertura_topo2 = {
            'a': {
                'esq1': tk.BooleanVar(value=False), 
                'esq2': tk.BooleanVar(value=False),
                'dir1': tk.BooleanVar(value=False),
                'dir2': tk.BooleanVar(value=False)
            },
            'b': {
                'esq1': tk.BooleanVar(value=False),
                'esq2': tk.BooleanVar(value=False), 
                'dir1': tk.BooleanVar(value=False),
                'dir2': tk.BooleanVar(value=False)
            },
            'c': {
                'esq1': tk.BooleanVar(value=False),
                'esq2': tk.BooleanVar(value=False),
                'dir1': tk.BooleanVar(value=False),
                'dir2': tk.BooleanVar(value=False)
            },
            'd': {
                'esq1': tk.BooleanVar(value=False),
                'esq2': tk.BooleanVar(value=False),
                'dir1': tk.BooleanVar(value=False),
                'dir2': tk.BooleanVar(value=False)
            }
        }
        
        # Criar a interface primeiro
        self.criar_interface()
        
        # Configurar binds
        self.configurar_binds()
        
        # Carregar configurações depois que a interface estiver criada
        self.carregar_configuracoes()

    def formatar_numero(self, valor):
        """Formata um número para exibir sempre com 2 casas decimais"""
        try:
            # Converter o valor para float, aceitando tanto . quanto ,
            if isinstance(valor, str):
                valor = valor.replace(',', '.')
            numero = float(valor)
            return f"{numero:.2f}".replace('.', ',')
        except (ValueError, TypeError):
            return "0,00"

    def converter_para_float(self, valor):
        """Converte uma string para float, aceitando tanto . quanto ,"""
        try:
            if isinstance(valor, str):
                valor = valor.replace(',', '.')
            return float(valor)
        except (ValueError, TypeError):
            return 0.0

    def validar_entrada_numerica(self, P):
        """Validação para entrada de números com até 2 casas decimais"""
        # Permite campo vazio
        if P == "":
            return True
        # Permite números com até 2 casas decimais
        try:
            # Aceita tanto , quanto .
            valor = P.replace(',', '.')
            # Verifica se é um número válido
            if '.' in valor:
                partes = valor.split('.')
                if len(partes) > 2:  # Não permite mais de um ponto/vírgula
                    return False
                if len(partes[1]) > 2:  # Não permite mais de 2 casas decimais
                    return False
            float(valor)  # Tenta converter para float
            return True
        except ValueError:
            return False

    def carregar_configuracoes(self):
        """Carrega as configurações salvas do usuário"""
        try:
            # Carregar configurações do arquivo
            config = self.config_manager.load_config()
            
            # Atualizar as configurações da interface
            if config:
                # Atualizar layers
                if "layers" in config:
                    if hasattr(self, 'log_text'):
                        self.log_mensagem("Carregando configurações de layers...", "info")
                    else:
                        logging.info("Carregando configurações de layers...")
                
                # Atualizar blocos
                if "blocks" in config:
                    if hasattr(self, 'log_text'):
                        self.log_mensagem("Carregando configurações de blocos...", "info")
                    else:
                        logging.info("Carregando configurações de blocos...")
                
                # Atualizar comandos de abertura
                if "abertura_commands" in config:
                    if hasattr(self, 'log_text'):
                        self.log_mensagem("Carregando configurações de comandos de abertura...", "info")
                    else:
                        logging.info("Carregando configurações de comandos de abertura...")
                
                # Atualizar comandos de hatch
                if "hatch_commands" in config:
                    if hasattr(self, 'log_text'):
                        self.log_mensagem("Carregando configurações de comandos de hatch...", "info")
                    else:
                        logging.info("Carregando configurações de comandos de hatch...")
                
                # Atualizar opções de desenho
                if "drawing_options" in config:
                    if hasattr(self, 'log_text'):
                        self.log_mensagem("Carregando opções de desenho...", "info")
                    else:
                        logging.info("Carregando opções de desenho...")
                
                if hasattr(self, 'log_text'):
                    self.log_mensagem("Configurações carregadas com sucesso!", "sucesso")
                else:
                    logging.info("Configurações carregadas com sucesso!")
            else:
                if hasattr(self, 'log_text'):
                    self.log_mensagem("Usando configurações padrão", "info")
                else:
                    logging.info("Usando configurações padrão")
        
        except Exception as e:
            if hasattr(self, 'log_text'):
                self.log_mensagem(f"Erro ao carregar configurações: {str(e)}", "erro")
            else:
                logging.error(f"Erro ao carregar configurações: {str(e)}")
            logging.error(f"Erro ao carregar configurações: {str(e)}")

    def salvar_configuracoes(self):
        """Salva as configurações atuais do usuário"""
        try:
            # Criar dicionário com as configurações atuais
            config = {
                "layers": {
                    "paineis_abcd": self.config_manager.get_config("layers", "paineis_abcd"),
                    "pe_direito": self.config_manager.get_config("layers", "pe_direito"),
                    "cotas": self.config_manager.get_config("layers", "cotas"),
                    "sarrafos": self.config_manager.get_config("layers", "sarrafos"),
                    "nomenclatura": self.config_manager.get_config("layers", "nomenclatura"),
                    "laje": self.config_manager.get_config("layers", "laje"),
                    "textos_titulos": self.config_manager.get_config("layers", "textos_titulos")
                },
                "blocks": {
                    "furacao": self.config_manager.get_config("blocks", "furacao"),
                    "split_ee": self.config_manager.get_config("blocks", "split_ee"),
                    "split_dd": self.config_manager.get_config("blocks", "split_dd"),
                    "moldura": self.config_manager.get_config("blocks", "moldura")
                },
                "abertura_commands": self.config_manager.get_config("abertura_commands"),
                "hatch_commands": self.config_manager.get_config("hatch_commands"),
                "drawing_options": {
                    "zoom_factor": self.config_manager.get_config("drawing_options", "zoom_factor"),
                    "cota_offset": self.config_manager.get_config("drawing_options", "cota_offset"),
                    "texto_offset": self.config_manager.get_config("drawing_options", "texto_offset"),
                    "sarrafo_offset": self.config_manager.get_config("drawing_options", "sarrafo_offset"),
                    "cotas_furacao_vertical": self.config_manager.get_config("drawing_options", "cotas_furacao_vertical"),
                    "cotas_furacao_horizontal": self.config_manager.get_config("drawing_options", "cotas_furacao_horizontal"),
                    "modo_sarrafos": self.config_manager.get_config("drawing_options", "modo_sarrafos"),
                    "espacamento_base": self.config_manager.get_config("drawing_options", "espacamento_base"),
                    "espacamento_vertical": self.config_manager.get_config("drawing_options", "espacamento_vertical"),
                    "espacamento_parafusos": self.config_manager.get_config("drawing_options", "espacamento_parafusos"),
                    "offset_parafuso": self.config_manager.get_config("drawing_options", "offset_parafuso"),
                    "offset_moldura": self.config_manager.get_config("drawing_options", "offset_moldura"),
                    "offset_texto_info": self.config_manager.get_config("drawing_options", "offset_texto_info"),
                    "offset_painel": self.config_manager.get_config("drawing_options", "offset_painel")
                }
            }
            
            # Salvar configurações no arquivo
            self.config_manager.config = config
            self.config_manager.save_config()
            
            self.log_mensagem("Configurações salvas com sucesso!", "sucesso")
        
        except Exception as e:
            self.log_mensagem(f"Erro ao salvar configurações: {str(e)}", "erro")
            logging.error(f"Erro ao salvar configurações: {str(e)}")

    def get_config(self, categoria, subcategoria=None, chave=None):
        """Obtém uma configuração específica"""
        try:
            if subcategoria and chave:
                return self.config_manager.get_config(categoria, subcategoria, chave)
            elif subcategoria:
                return self.config_manager.get_config(categoria, subcategoria)
            else:
                return self.config_manager.get_config(categoria)
        except Exception as e:
            self.log_mensagem(f"Erro ao obter configuração: {str(e)}", "erro")
            return None

    def configurar_estilos(self):
        """Configura os estilos personalizados para a interface"""
        style = ttk.Style()
        
        # Estilo para labels de título
        style.configure('Titulo.TLabel', 
                       font=('Arial', 11, 'bold'),
                       padding=4)
        
        # Estilo para frames de painéis
        style.configure('Painel.TFrame',
                       padding=4,
                       relief='solid',
                       borderwidth=2)
        
        # Estilo para frames de opções
        style.configure('Opcoes.TLabelframe',
                       padding=2,
                       relief='solid',
                       borderwidth=1)
        style.configure('Opcoes.TLabelframe.Label',
                       font=('Arial', 9, 'bold'))
        
        # Estilo para botões
        style.configure('Botao.TButton',
                       padding=3,
                       font=('Arial', 9))
        
        # Estilo para campos de entrada
        style.configure('Campo.TEntry',
                       padding=1)
        
        # Estilo para comboboxes
        style.configure('Combo.TCombobox',
                       padding=1)
        
        # Configurar cores para os painéis (mais vibrantes)
        self.cores_paineis = {
            'a': {'bg': '#C8E6C9', 'fg': '#1B5E20', 'border': '#2E7D32'},  # Verde mais forte
            'b': {'bg': '#BBDEFB', 'fg': '#0D47A1', 'border': '#1565C0'},  # Azul mais forte
            'c': {'bg': '#FFE0B2', 'fg': '#E65100', 'border': '#F57C00'},  # Laranja mais forte
            'd': {'bg': '#E1BEE7', 'fg': '#4A148C', 'border': '#7B1FA2'}   # Roxo mais forte
        }
        
    def configurar_binds(self):
        """Configura os binds para os locks de largura e altura"""
        try:
            for tipo_painel in ['a', 'b', 'c', 'd']:
                # Configurar binds para locks de largura
                num_larguras = 3 if tipo_painel in ['a', 'b'] else 2
                for i in range(num_larguras):
                    if i < len(self.largura_locks[tipo_painel]):
                        self.largura_locks[tipo_painel][i].trace_add('write', 
                            lambda *args, t=tipo_painel, idx=i: self.atualizar_estado_campo(
                                self.campos_ab[f'comp{idx+1}_{t}'] if t in ['a', 'b'] else self.campos_cd[f'comp{idx+1}_{t}'],
                                self.largura_locks[t][idx]
                            ))
                
                # Configurar binds para locks de altura
                num_alturas = 5 if tipo_painel in ['a', 'b'] else 4
                for i in range(num_alturas):
                    if i < len(self.altura_locks[tipo_painel]):
                        self.altura_locks[tipo_painel][i].trace_add('write',
                            lambda *args, t=tipo_painel, idx=i: self.atualizar_estado_campo(
                                self.campos_altura[t][idx],
                                self.altura_locks[t][idx]
                            ))
            
            self.log_mensagem("Binds configurados para todos os locks", "info")
        except Exception as e:
            self.log_mensagem(f"Erro ao configurar binds: {str(e)}", "erro")

    def atualizar_estado_campo(self, entry, lock_var):
        if lock_var.get():
            entry.config(state='readonly')
        else:
            entry.config(state='normal')
        self.log_mensagem(f"Estado do campo atualizado: {'bloqueado' if lock_var.get() else 'desbloqueado'}", "info")

    def criar_painel_tabela(self, frame_pai, titulo, num_alturas, tipo_painel):
        """Cria uma tabela completa para um painel"""
        frame_painel = ttk.LabelFrame(frame_pai, text=titulo, padding="3")
        
        # Campos de largura no topo
        frame_larguras = ttk.Frame(frame_painel)
        frame_larguras.grid(row=0, column=1, columnspan=2, pady=(0,5))
        
        ttk.Label(frame_larguras, text="Largura 1:").grid(row=0, column=0, padx=2)
        largura1 = ttk.Entry(frame_larguras, width=10)
        largura1.grid(row=0, column=1, padx=2)
        
        ttk.Label(frame_larguras, text="Largura 2:").grid(row=0, column=2, padx=2)
        largura2 = ttk.Entry(frame_larguras, width=10)
        largura2.grid(row=0, column=3, padx=2)
        
        # Armazenar campos de largura
        if tipo_painel in ['a', 'b']:
            self.campos_ab[f'comp1_{tipo_painel}'] = largura1
            self.campos_ab[f'comp2_{tipo_painel}'] = largura2
        else:
            self.campos_cd[f'comp1_{tipo_painel}'] = largura1
            self.campos_cd[f'comp2_{tipo_painel}'] = largura2
        
        # Cabeçalhos da tabela
        ttk.Label(frame_painel, text="").grid(row=1, column=0)  # Célula vazia para canto
        ttk.Label(frame_painel, text="Largura 1").grid(row=1, column=1, padx=2)
        ttk.Label(frame_painel, text="Largura 2").grid(row=1, column=2, padx=2)
        
        # Lista para armazenar campos de altura e opções de hatch
        campos_altura = []
        opcoes_hatch = []
        
        # Criar linhas da tabela
        for i in range(num_alturas):
            # Frame para a linha
            frame_linha = ttk.Frame(frame_painel)
            frame_linha.grid(row=i+2, column=0, columnspan=3, sticky="ew", pady=1)
            
            # Campo de altura
            ttk.Label(frame_linha, text=f"Altura {i+1}:").grid(row=0, column=0, padx=(2,5), sticky="e")
            campo_altura = ttk.Entry(frame_linha, width=10)
            campo_altura.grid(row=0, column=1, padx=2)
            campos_altura.append(campo_altura)
            
            # Opções de hatch para cada largura (agora campos de texto)
            linha_hatch = []
            for j in range(2):  # 2 larguras
                var = tk.StringVar(value="0")  # Valor padrão: "Nenhum"
                campo_hatch = ttk.Entry(frame_linha, textvariable=var, width=12)
                campo_hatch.grid(row=0, column=j+2, padx=2)
                linha_hatch.append(var)
            opcoes_hatch.append(linha_hatch)
        
        # Armazenar referências
        self.campos_altura[tipo_painel] = campos_altura
        setattr(self, f'hatch_opcoes_{tipo_painel}', opcoes_hatch)
        
        return frame_painel
        
    def criar_interface(self):
        # Dividir em duas colunas principais
        frame_info = ttk.Frame(self.root, padding="2")
        frame_paineis = ttk.Frame(self.root, padding="2")
        
        frame_info.grid(row=0, column=0, sticky="nsew", padx=1)
        frame_paineis.grid(row=0, column=1, sticky="nsew", padx=1)
        
        # === COLUNA 1: INFORMAÇÕES E CONTROLES ===
        # Seção: Informações do Pilar
        frame_info_pilar = ttk.LabelFrame(frame_info, text="Informações do Pilar", padding="2")
        frame_info_pilar.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        
        # Frame para nome
        ttk.Label(frame_info_pilar, text="Nome:").grid(row=0, column=0, sticky=tk.W, padx=2, pady=1)
        nome_entry = ttk.Entry(frame_info_pilar, width=10)
        nome_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=2, pady=1)
        
        # Frame para pavimento e pavimento anterior (na mesma linha)
        frame_pavimentos = ttk.Frame(frame_info_pilar)
        frame_pavimentos.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=1)
        
        ttk.Label(frame_pavimentos, text="Pavimento:").grid(row=0, column=0, sticky=tk.W, padx=2)
        pavimento_entry = ttk.Entry(frame_pavimentos, width=10)
        pavimento_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=2)
        
        ttk.Label(frame_pavimentos, text="Pavimento Anterior:").grid(row=0, column=2, sticky=tk.W, padx=2)
        pavimento_anterior_entry = ttk.Entry(frame_pavimentos, width=10)
        pavimento_anterior_entry.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=2)
        
        self.campos = {
            'nome': nome_entry,
            'pavimento': pavimento_entry,
            'pavimento_anterior': pavimento_anterior_entry
        }
        
        # Criar campos numéricos com validação
        vcmd = (frame_info_pilar.register(self.validar_entrada_numerica), '%P')
        
        # Campo nível de saída com validação
        ttk.Label(frame_info_pilar, text="N/Saída:").grid(row=2, column=0, sticky=tk.W, padx=2, pady=1)
        nivel_saida_entry = ttk.Entry(frame_info_pilar, width=10, validate='key', validatecommand=vcmd)
        nivel_saida_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=2, pady=1)
        nivel_saida_entry.bind('<FocusOut>', lambda e: self.formatar_campo_ao_sair(nivel_saida_entry))
        nivel_saida_entry.bind('<FocusOut>', self.atualizar_altura, add='+')
        
        # Campo nível de chegada com validação
        ttk.Label(frame_info_pilar, text="N/Chegada:").grid(row=3, column=0, sticky=tk.W, padx=2, pady=1)
        nivel_chegada_entry = ttk.Entry(frame_info_pilar, width=10, validate='key', validatecommand=vcmd)
        nivel_chegada_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=2, pady=1)
        nivel_chegada_entry.bind('<FocusOut>', lambda e: self.formatar_campo_ao_sair(nivel_chegada_entry))
        nivel_chegada_entry.bind('<FocusOut>', self.atualizar_altura, add='+')
        
        self.campos.update({
            'nivel_saida': nivel_saida_entry,
            'nivel_chegada': nivel_chegada_entry,
            'comprimento': self.criar_campo(frame_info_pilar, "Comprimento:", 4),
            'largura': self.criar_campo(frame_info_pilar, "Largura:", 5),
            'altura': self.criar_campo(frame_info_pilar, "Altura:", 6),
        })
        
        # Seção: Lajes
        frame_lajes = ttk.LabelFrame(frame_info, text="Lajes", padding="2")
        frame_lajes.grid(row=1, column=0, sticky="ew", padx=1, pady=1)
        
        # Criar campos de laje com botões de rádio
        self.criar_campo_laje(frame_lajes, "Laje A:", 0, self.pos_laje_a, 5)
        self.criar_campo_laje(frame_lajes, "Laje B:", 2, self.pos_laje_b, 5)
        self.criar_campo_laje(frame_lajes, "Laje C:", 4, self.pos_laje_c, 4)
        self.criar_campo_laje(frame_lajes, "Laje D:", 6, self.pos_laje_d, 4)
        
        # Frame para parafusos
        self.parafusos_frame = ttk.LabelFrame(frame_info, text="Parafusos", padding="5")
        self.parafusos_frame.grid(row=2, column=0, sticky="ew", padx=1, pady=1)

        # Títulos das caixas de texto para parafusos
        parafuso_labels = ["P1-P2", "P2-P3", "P3-P4", "P4-P5", "P5-P6", "P6-P7", "P7-P8", "P8-P9"]
        for i, label in enumerate(parafuso_labels):
            ttk.Label(self.parafusos_frame, text=label).grid(row=0, column=i*2, padx=2)

        # Caixas de texto para as distâncias entre parafusos
        self.parafuso_entries = []
        for i in range(8):
            entry = ttk.Entry(self.parafusos_frame, width=8)
            entry.grid(row=1, column=i*2, padx=2, pady=2)
            self.parafuso_entries.append(entry)
            # Checkbox para travar o campo
            lock_var = tk.BooleanVar(value=False)
            self.parafuso_locks_abcd[i] = lock_var  # Armazenar a variável na lista
            # Associar a função de callback ao Checkbutton
            ttk.Checkbutton(self.parafusos_frame, variable=lock_var,
                            command=lambda i=i: self.master.sincronizar_locks_parafusos('abcd', i)
                            ).grid(row=1, column=i*2+1, padx=2)
        
        # Botões abaixo das lajes
        frame_botoes = ttk.Frame(frame_info)
        frame_botoes.grid(row=3, column=0, sticky="ew", padx=1, pady=2)
        
        # Botões em coluna (um abaixo do outro)
        ttk.Button(frame_botoes, text="Preencher com Teste", style='Botao.TButton',
                  command=self.preencher_dados_teste).grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        
        ttk.Button(frame_botoes, text="Calcular Dimensões", style='Botao.TButton',
                  command=lambda: [self.calcular_dimensoes_ab(), 
                                 self.calcular_dimensoes_cd(), 
                                 self.calcular_alturas()]).grid(row=1, column=0, sticky="ew", padx=1, pady=1)
        
        ttk.Button(frame_botoes, text="Limpar Campos", style='Botao.TButton',
                  command=lambda: [self.limpar_campos()]).grid(row=2, column=0, sticky="ew", padx=1, pady=1)
        
        ttk.Button(frame_botoes, text="Gerar Script", style='Botao.TButton',
                  command=lambda: [self.validar_entrada() and self.gerar_script(), self.master.interface.gerar_script()]).grid(row=3, column=0, sticky="ew", padx=1, pady=1)
        
        ttk.Button(frame_botoes, text="Salvar Script", style='Botao.TButton',
                  command=lambda: [self.salvar_script()]).grid(row=4, column=0, sticky="ew", padx=1, pady=1)
        
        # Adicionar botão de configurações
        ttk.Button(frame_botoes, text="Configurações", style='Botao.TButton',
                  command=self.criar_janela_configuracoes).grid(row=5, column=0, sticky="ew", padx=1, pady=1)
        
        # Mini log abaixo dos botões
        log_frame = ttk.LabelFrame(frame_info, text="Log", padding="1")
        log_frame.grid(row=6, column=0, sticky="ew", padx=1, pady=1)
        
        self.log_text = tk.Text(log_frame, height=3, width=35)
        self.log_text.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # Configurar tags para o log
        self.log_text.tag_configure("erro", foreground="red")
        self.log_text.tag_configure("sucesso", foreground="green")
        self.log_text.tag_configure("info", foreground="blue")
        
        # === COLUNA 2: PAINÉIS ===
        # Frame para os painéis A e B (primeira linha)
        frame_ab = ttk.Frame(frame_paineis)
        frame_ab.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        
        # Criar painéis A e B com cores de fundo
        frame_a = self.criar_painel_colorido(frame_ab, "A", 0, 5, "#E8F5E9")
        frame_b = self.criar_painel_colorido(frame_ab, "B", 1, 5, "#E3F2FD")
        
        # Frame para os painéis C e D (segunda linha)
        frame_cd = ttk.Frame(frame_paineis)
        frame_cd.grid(row=1, column=0, sticky="ew", padx=1, pady=1)
        
        # Criar painéis C e D com cores de fundo
        frame_c = self.criar_painel_colorido(frame_cd, "C", 0, 4, "#FFF8E1")
        frame_d = self.criar_painel_colorido(frame_cd, "D", 1, 4, "#FBE9E7")
        
        # Configurar pesos das colunas para expansão
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=5)  # Aumentar o peso da coluna dos painéis
        
        # Configurar pesos das linhas para expansão
        self.root.rowconfigure(0, weight=1)
        
        # Configurar pesos das colunas e linhas dos frames para expansão
        frame_info.columnconfigure(0, weight=1)
        frame_paineis.columnconfigure(0, weight=1)
        frame_ab.columnconfigure(0, weight=1)
        frame_ab.columnconfigure(1, weight=1)
        frame_cd.columnconfigure(0, weight=1)
        frame_cd.columnconfigure(1, weight=1)
        
        # Configurar pesos das linhas dos frames para expansão
        for i in range(4):
            frame_info.rowconfigure(i, weight=1)
        frame_paineis.rowconfigure(0, weight=1)
        frame_paineis.rowconfigure(1, weight=1)

    def criar_painel_colorido(self, frame_pai, tipo_painel, coluna, num_alturas, cor_fundo):
        """Cria um painel com layout otimizado e compacto"""
        # Frame principal para o painel com borda
        frame_conjunto = ttk.Frame(frame_pai, style='Painel.TFrame')
        frame_conjunto.grid(row=0, column=coluna, sticky="nsew", padx=2, pady=1)
        
        # Frame para o painel com cor de fundo
        frame_painel = tk.Frame(frame_conjunto, 
                              bg=self.cores_paineis[tipo_painel.lower()]['bg'],
                              relief='solid',
                              borderwidth=2)
        frame_painel.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        
        # Título do painel
        titulo = tk.Label(frame_painel, 
                         text=f"Painel {tipo_painel}",
                         bg=self.cores_paineis[tipo_painel.lower()]['bg'],
                         fg=self.cores_paineis[tipo_painel.lower()]['fg'],
                         font=('Arial', 10, 'bold'))
        titulo.grid(row=0, column=0, columnspan=5, pady=1, sticky="ew")
        
        # Frame para configurações em grid compacto
        frame_config = ttk.LabelFrame(frame_painel, text="Configurações", style='Opcoes.TLabelframe')
        frame_config.grid(row=1, column=0, columnspan=5, sticky="ew", padx=2, pady=1)
        
        # Frame para larguras em linha única
        frame_larguras = ttk.Frame(frame_config)
        frame_larguras.grid(row=0, column=0, columnspan=5, pady=1)
        
        tipo = tipo_painel.lower()
        num_larguras = 3 if tipo in ['a', 'b'] else 2
        
        # Criar campos de largura com locks em linha única
        for i in range(num_larguras):
            frame_largura = ttk.Frame(frame_larguras)
            frame_largura.grid(row=0, column=i, padx=1)
            
            ttk.Label(frame_largura, text=f"L{i+1}:").grid(row=0, column=0, padx=1)
            largura = ttk.Entry(frame_largura, width=7)
            largura.grid(row=0, column=1, padx=1)
            
            lock_var = tk.BooleanVar()
            cb = ttk.Checkbutton(frame_largura, variable=lock_var, padding=0)
            cb.grid(row=0, column=2, padx=0)
            self.largura_locks[tipo].append(lock_var)
            
            if tipo in ['a', 'b']:
                self.campos_ab[f'comp{i+1}_{tipo}'] = largura
            else:
                self.campos_cd[f'comp{i+1}_{tipo}'] = largura
        
        # Cabeçalhos compactos
        ttk.Label(frame_config, text="Alt").grid(row=1, column=0, padx=1)
        ttk.Label(frame_config, text="Val").grid(row=1, column=1, padx=1)
        ttk.Label(frame_config, text="Lk").grid(row=1, column=2, padx=1)
        for i in range(num_larguras):
            ttk.Label(frame_config, text=f"H{i+1}").grid(row=1, column=3+i, padx=1)
        
        # Lista para campos de altura e opções de hatch
        campos_altura = []
        opcoes_hatch = []
        
        # Criar linhas da tabela em ordem inversa de forma compacta
        for i in range(num_alturas-1, -1, -1):
            idx_real = i
            idx_visual = num_alturas - 1 - i
            
            ttk.Label(frame_config, text=f"H{idx_real+1}:").grid(row=idx_visual+2, column=0, padx=1, sticky="e")
            
            frame_altura = ttk.Frame(frame_config)
            frame_altura.grid(row=idx_visual+2, column=1, columnspan=2, sticky="w")
            
            campo_altura = ttk.Entry(frame_altura, width=7)
            campo_altura.grid(row=0, column=0, padx=1)
            campos_altura.insert(0, campo_altura)
            
            # Adicionar campo de altura ao dicionário self.campos
            self.campos[f'altura_h{idx_real+1}_{tipo}'] = campo_altura
            
            lock_var = tk.BooleanVar()
            cb = ttk.Checkbutton(frame_altura, variable=lock_var, padding=0)
            cb.grid(row=0, column=1, padx=0)
            self.altura_locks[tipo].append(lock_var)
            
            linha_hatch = []
            for j in range(num_larguras):
                var = tk.StringVar(value="0")  # Valor padrão: "Nenhum"
                campo_hatch = ttk.Entry(frame_config, textvariable=var, width=12)
                campo_hatch.grid(row=idx_visual+2, column=j+3, padx=1)
                linha_hatch.append(var)
            
            opcoes_hatch.insert(0, linha_hatch)
        
        # Frame para aberturas e sarrafos em linha única
        frame_inferior = ttk.Frame(frame_painel)
        frame_inferior.grid(row=2, column=0, columnspan=5, sticky="ew", padx=2, pady=1)
        
        # Criar frame de aberturas com novo layout
        self.criar_frame_abertura(frame_inferior, tipo_painel, 0)
        
        # Armazenar referências
        self.campos_altura[tipo] = campos_altura
        setattr(self, f'hatch_opcoes_{tipo}', opcoes_hatch)
        
        return frame_conjunto

    def configurar_estado_sarrafo_horizontal(self, tipo_painel):
        """Configura o estado inicial do checkbox de sarrafo horizontal."""
        altura_laje_str = getattr(self, f'laje_{tipo_painel}_var').get()
        try:
            altura_laje = self.converter_para_float(altura_laje_str)
            # Ativar checkbox se altura da laje for menor ou igual a 26
            getattr(self, f'sarrafo_horizontal_{tipo_painel}').set(altura_laje <= 26)
        except ValueError:
            # Em caso de erro, ativar checkbox por padrão
            getattr(self, f'sarrafo_horizontal_{tipo_painel}').set(True)

    def atualizar_estado_sarrafo_horizontal(self, tipo_painel):
        """Atualiza o estado do checkbox de sarrafo horizontal com base na altura da laje."""
        self.configurar_estado_sarrafo_horizontal(tipo_painel)

    def criar_frame_abertura(self, frame_pai, tipo_painel, row):
        """Cria um frame para as opções de abertura de um painel com layout compacto para 4 aberturas"""
        frame = ttk.LabelFrame(frame_pai, text="Aberturas", style='Opcoes.TLabelframe')
        frame.grid(row=row, column=0, columnspan=5, sticky="ew", padx=6, pady=3)
        
        # Frame principal para todas as aberturas em linha
        frame_aberturas = ttk.Frame(frame)
        frame_aberturas.grid(row=0, column=0, padx=2, pady=2)
        
        # Criar frames para cada abertura em sequência horizontal
        frames_nomes = ["Esquerda 1", "Esquerda 2", "Direita 1", "Direita 2"]
        frames_ids = ['esq1', 'esq2', 'dir1', 'dir2']
        
        for i, (nome, frame_id) in enumerate(zip(frames_nomes, frames_ids)):
            frame_abertura = ttk.LabelFrame(frame_aberturas, text=nome, padding="2")
            frame_abertura.grid(row=0, column=i, padx=2, pady=2)
            
            # Frame para os checkboxes
            frame_checks = ttk.Frame(frame_abertura)
            frame_checks.grid(row=0, column=0, columnspan=2, padx=1, pady=1)
            
            # Checkbox do topo2 (novo)
            ttk.Checkbutton(frame_checks, text="Do Topo2", 
                           variable=self.abertura_topo2[tipo_painel.lower()][frame_id],
                           padding=0).grid(row=0, column=0, columnspan=2, padx=1, pady=1)
            
            # Campo de abertura laje (1=laje, 0=normal)
            ttk.Label(frame_checks, text="Laje:").grid(row=1, column=0, padx=1, sticky="e")
            laje_entry = ttk.Entry(frame_checks, width=3, textvariable=self.abertura_laje[tipo_painel.lower()][frame_id])
            laje_entry.grid(row=1, column=1, padx=1, pady=1)
            
            # Campo de posição (novo)
            ttk.Label(frame_abertura, text="Pos:").grid(row=2, column=0, padx=1, sticky="e")
            pos = ttk.Entry(frame_abertura, width=8)
            pos.grid(row=2, column=1, padx=1)
            
            # Campos de entrada existentes
            ttk.Label(frame_abertura, text="Dist:").grid(row=3, column=0, padx=1, sticky="e")
            dist = ttk.Entry(frame_abertura, width=8)
            dist.grid(row=3, column=1, padx=1)
            
            ttk.Label(frame_abertura, text="Prof:").grid(row=4, column=0, padx=1, sticky="e")
            prof = ttk.Entry(frame_abertura, width=8)
            prof.grid(row=4, column=1, padx=1)
            
            ttk.Label(frame_abertura, text="Larg:").grid(row=5, column=0, padx=1, sticky="e")
            larg = ttk.Entry(frame_abertura, width=8)
            larg.grid(row=5, column=1, padx=1)
            
            # Armazenar campos no dicionário
            self.campos[f'abertura_{frame_id}_pos_{tipo_painel.lower()}'] = pos
            self.campos[f'abertura_{frame_id}_dist_{tipo_painel.lower()}'] = dist
            self.campos[f'abertura_{frame_id}_prof_{tipo_painel.lower()}'] = prof
            self.campos[f'abertura_{frame_id}_larg_{tipo_painel.lower()}'] = larg
        
        # Frame para sarrafos à direita das aberturas
        frame_sarrafos = ttk.LabelFrame(frame, text="Sarrafos", style='Opcoes.TLabelframe')
        frame_sarrafos.grid(row=0, column=1, sticky="ns", padx=2, pady=2)
        
        # Configurar sarrafos
        self.configurar_sarrafos(frame_sarrafos, tipo_painel)
        
        return frame

    def configurar_sarrafos(self, frame_sarrafos, tipo_painel):
        """Configura os controles de sarrafos para um painel"""
        # Checkbox para join de sarrafos
        join_var = getattr(self, f'join_sarrafos_{tipo_painel.lower()}')
        ttk.Checkbutton(frame_sarrafos, text="Join Vertical", 
                       variable=join_var, padding=0).grid(row=0, column=0, padx=2)
        
        # Checkbox para sarrafos horizontais (apenas para painéis A e B)
        if tipo_painel.lower() in ['a', 'b']:
            horiz_var = getattr(self, f'sarrafo_horizontal_{tipo_painel.lower()}')
            # Configurar estado inicial do checkbox
            self.configurar_estado_sarrafo_horizontal(tipo_painel.lower())
            # Adicionar checkbox na interface
            ttk.Checkbutton(frame_sarrafos, text="Horizontal", 
                           variable=horiz_var, padding=0).grid(row=1, column=0, padx=2)
            # Adicionar rastreamento para mudanças na altura da laje
            getattr(self, f'laje_{tipo_painel.lower()}_var').trace_add(
                "write", 
                lambda *args, tp=tipo_painel.lower(): self.atualizar_estado_sarrafo_horizontal(tp)
            )
        
        return frame_sarrafos

    def gerar_comandos_abertura(self, x1, y1, x2, y2, lado, tipo_painel, abertura_id):
        """Gera comandos para aberturas"""
        # Ajustar zoom baseado na largura da abertura
        largura = abs(x2 - x1)
        
        # Zoom centralizado com fator 10 para aberturas pequenas
        if largura < 13:
            script = f""";
;
"""
        else:
            # Zoom normal para aberturas maiores
            script = f""";
_ZOOM
C
{min(x1,x2)-3},{y2-3}
10
;
"""
        
        # Verificar se é uma abertura de laje (prioridade máxima)
        laje_value = self.abertura_laje[tipo_painel.lower()][abertura_id].get().strip()
        
        # DEBUG: Verificar valores de abertura de laje
        print(f"🔍 DEBUG GERAÇÃO COMANDOS ABERTURA:")
        print(f"  Painel: {tipo_painel}, Abertura: {abertura_id}")
        print(f"  Valor lido: '{laje_value}' (tipo: {type(laje_value)})")
        print(f"  Comparação: '{laje_value}' == '1'? {laje_value == '1'}")
        
        # Tentar ler diretamente da interface principal se disponível
        if hasattr(self, 'master') and self.master and hasattr(self.master, 'abertura_laje'):
            try:
                interface_value = self.master.abertura_laje[tipo_painel.lower()][abertura_id].get().strip()
                print(f"  🔄 Valor da interface principal: '{interface_value}'")
                if interface_value == "1":
                    laje_value = "1"
                    print(f"  ✅ Usando valor da interface principal: '{laje_value}'")
            except Exception as e:
                print(f"  ⚠️ Erro ao ler da interface principal: {e}")
        
        # DEBUG: Verificar se o campo existe e tem valor
        print(f"  🔍 Verificando campo abertura_laje[{tipo_painel.lower()}][{abertura_id}]")
        print(f"  🔍 Campo existe? {hasattr(self, 'abertura_laje')}")
        if hasattr(self, 'abertura_laje'):
            print(f"  🔍 Painel existe? {tipo_painel.lower() in self.abertura_laje}")
            if tipo_painel.lower() in self.abertura_laje:
                print(f"  🔍 Abertura existe? {abertura_id in self.abertura_laje[tipo_painel.lower()]}")
                if abertura_id in self.abertura_laje[tipo_painel.lower()]:
                    campo = self.abertura_laje[tipo_painel.lower()][abertura_id]
                    print(f"  🔍 Tipo do campo: {type(campo)}")
                    print(f"  🔍 Valor do campo: '{campo.get()}'")
                    print(f"  🔍 Valor após strip: '{campo.get().strip()}'")
        
        
        if laje_value == "1":
            comando = self.config_manager.get_config("comandos", "aberturas", "ABVLJ") or "ABVLJ"
            print(f"  ✅ GERANDO COMANDO ABVLJ para {tipo_painel}.{abertura_id}")
            print(f"  Comando: {comando}")
            script += f""";
_ZOOM
C
{x1},{y1}
10
;
app
{x1},{y1}
{x2},{y2}
;
;
_ZOOM
C
{x1},{y1}
10
;
{comando}
{x1},{y1}
{x2},{y2}
;"""
            return script
        else:
            print(f"  ❌ NÃO gerando ABVLJ para {tipo_painel}.{abertura_id} (valor: '{laje_value}')")
        
        # Se não for abertura de laje, continua com a lógica normal
        # Escolher o comando apropriado baseado na largura e lado
        if largura < 13:
            comando_tipo = self.config_manager.get_config("comandos", "aberturas", "abve12") if lado == 'esquerda' else self.config_manager.get_config("comandos", "aberturas", "abvd12")
            if largura < 7:
                comando_tipo = self.config_manager.get_config("comandos", "aberturas", "abve12") if lado == 'esquerda' else self.config_manager.get_config("comandos", "aberturas", "abvd12")
        else:
            comando_tipo = self.config_manager.get_config("comandos", "aberturas", "abve") if lado == 'esquerda' else self.config_manager.get_config("comandos", "aberturas", "abvd")
        
        script += f""";
_ZOOM
C
{x1},{y1}
10
;
app
{x1},{y1}
{x2},{y2}
;
_ZOOM
C
{x1},{y1}
10
;
{comando_tipo}
{x1},{y1}
{x2},{y2}
;"""

        # Adicionar comando appla/applad para aberturas com largura < 7
        if largura < 7:
            ajuste = 7 - largura
            if lado == 'esquerda':
                # Para aberturas esquerdas, crescer para a direita e usar appla
                x_ajustado = x2 + ajuste
                script += f"""
_ZOOM
C
{x1+7},{y1}
10
;
break2
{x1+7},{y1}
{x1+7},{y2}
{x1+7},{y1}
;"""
            else:
                # Para aberturas direitas, crescer para a esquerda e usar applad
                x_ajustado = x1 + (-ajuste)
                script += f"""
_ZOOM
C
{x2-7},{y1}
10
;
break2
{x2-7},{y1}
{x2-7},{y2}
{x2-7},{y1}
;"""
        
        return script

    def gerar_comandos_abertura_normal(self, x1, y1, x2, y2, lado, tipo_painel, abertura_id):
        """Gera comandos para aberturas normais (>= 12cm)"""
        # Manter zoom mais amplo para aberturas normais
        script = f""";
_ZOOM
C
{x1},{y1}
10
;
"""
        
        # Verificar se é uma abertura de laje (prioridade máxima)
        laje_value = self.abertura_laje[tipo_painel.lower()][abertura_id].get().strip()
        
        # DEBUG: Verificar valores de abertura de laje
        print(f"🔍 DEBUG GERAÇÃO COMANDOS ABERTURA:")
        print(f"  Painel: {tipo_painel}, Abertura: {abertura_id}")
        print(f"  Valor lido: '{laje_value}' (tipo: {type(laje_value)})")
        print(f"  Comparação: '{laje_value}' == '1'? {laje_value == '1'}")
        
        # Tentar ler diretamente da interface principal se disponível
        if hasattr(self, 'master') and self.master and hasattr(self.master, 'abertura_laje'):
            try:
                interface_value = self.master.abertura_laje[tipo_painel.lower()][abertura_id].get().strip()
                print(f"  🔄 Valor da interface principal: '{interface_value}'")
                if interface_value == "1":
                    laje_value = "1"
                    print(f"  ✅ Usando valor da interface principal: '{laje_value}'")
            except Exception as e:
                print(f"  ⚠️ Erro ao ler da interface principal: {e}")
        
        # DEBUG: Verificar se o campo existe e tem valor
        print(f"  🔍 Verificando campo abertura_laje[{tipo_painel.lower()}][{abertura_id}]")
        print(f"  🔍 Campo existe? {hasattr(self, 'abertura_laje')}")
        if hasattr(self, 'abertura_laje'):
            print(f"  🔍 Painel existe? {tipo_painel.lower() in self.abertura_laje}")
            if tipo_painel.lower() in self.abertura_laje:
                print(f"  🔍 Abertura existe? {abertura_id in self.abertura_laje[tipo_painel.lower()]}")
                if abertura_id in self.abertura_laje[tipo_painel.lower()]:
                    campo = self.abertura_laje[tipo_painel.lower()][abertura_id]
                    print(f"  🔍 Tipo do campo: {type(campo)}")
                    print(f"  🔍 Valor do campo: '{campo.get()}'")
                    print(f"  🔍 Valor após strip: '{campo.get().strip()}'")
        
        
        if laje_value == "1":
            comando = self.config_manager.get_config("comandos", "aberturas", "ABVLJ") or "ABVLJ"
            print(f"  ✅ GERANDO COMANDO ABVLJ para {tipo_painel}.{abertura_id}")
            print(f"  Comando: {comando}")
            script += f""";
_ZOOM
C
{x1},{y1}
10
;
app
{x1},{y1}
{x2},{y2}
;
_ZOOM
C
{x1},{y1}
10
;
{comando}
{x1},{y1}
{x2},{y2}
;"""
            return script
        else:
            print(f"  ❌ NÃO gerando ABVLJ para {tipo_painel}.{abertura_id} (valor: '{laje_value}')")
        
        # Se não for abertura de laje, continua com a lógica normal
        comando_tipo = self.config_manager.get_config("comandos", "aberturas", "abve") if lado == 'esquerda' else self.config_manager.get_config("comandos", "aberturas", "abvd") if lado == 'direita' else self.config_manager.get_config("comandos", "aberturas", "abv")
        hatch_laje = self.config_manager.get_config("comandos", "hatches", "laje") or "HHHH"
        script += f""";
_ZOOM
C
{x1},{y1}
10
;
app
{x1},{y1}
{x2},{y2}
;
_ZOOM
C
{x1},{y1}
10
;
{comando_tipo}
{x1},{y1}
{x2},{y2}
"""
        
        script += f""";
{hatch_laje}
{(x1 + x2) / 2},{(y1 + y2) / 2}
;
"""
        
        return script

    def gerar_cotas_abertura(self, x1, y1, x2, y2, prof, y1_original=None):
        """Gera as cotas para uma abertura"""
        # Usar y1_original se fornecido, senão usar y1
        y_top = y1_original if y1_original is not None else y1
        
        script = f""";
_ZOOM
C
{x1},{y1}
10
;
_DIMLINEAR
{x1},{y1}
{x1},{y2}
{x1 - 15},{(y1 + y2) / 2}
;
"""
        
        # Ajustar posição da cota horizontal
        y_cota = y2 + prof + 20
        
        script += f""";
_ZOOM
C
{x1},{y1}
10
;
_DIMLINEAR
{x1},{y_top}
{x2},{y_top}
{(x1 + x2) / 2},{y_cota}
;
"""
        
        return script

    def criar_tabela_painel(self, frame_pai, tipo_painel, coluna, num_alturas):
        """Cria uma tabela completa para um painel"""
        # Frame principal para o painel e sua abertura
        frame_conjunto = ttk.Frame(frame_pai)
        frame_conjunto.grid(row=0, column=coluna, sticky="nsew", padx=1)  # Reduzido padding horizontal
        
        # Frame para a tabela do painel
        frame_painel = ttk.LabelFrame(frame_conjunto, text=f"Painel {tipo_painel}", padding="2")  # Reduzido padding
        frame_painel.grid(row=0, column=0, sticky="nsew", pady=1)
        
        # Campos de largura no topo
        frame_larguras = ttk.Frame(frame_painel)
        frame_larguras.grid(row=0, column=0, columnspan=5, pady=(0,3))  # Reduzido padding vertical
        
        # Inicializar listas de locks para este painel
        tipo = tipo_painel.lower()
        self.largura_locks[tipo] = []
        self.altura_locks[tipo] = []
        
        # Número de larguras baseado no tipo de painel
        num_larguras = 3 if tipo in ['a', 'b'] else 2
        
        # Criar campos de largura com locks
        for i in range(num_larguras):
            # Frame para cada par entrada/lock
            frame_largura = ttk.Frame(frame_larguras)
            frame_largura.grid(row=0, column=i*2, padx=1)  # Reduzido padding
            
            ttk.Label(frame_largura, text=f"L{i+1}:").grid(row=0, column=0, padx=1)  # Reduzido padding
            largura = ttk.Entry(frame_largura, width=6)  # Reduzido width
            largura.grid(row=0, column=1, padx=1)  # Reduzido padding
            
            # Lock checkbox
            lock_var = tk.BooleanVar()
            cb = ttk.Checkbutton(frame_largura, variable=lock_var)
            cb.grid(row=0, column=2, padx=(0,1))  # Reduzido padding
            self.largura_locks[tipo].append(lock_var)
            
            # Armazenar campos de largura
            if tipo in ['a', 'b']:
                self.campos_ab[f'comp{i+1}_{tipo}'] = largura
            else:
                self.campos_cd[f'comp{i+1}_{tipo}'] = largura
        
        # Cabeçalhos da tabela
        ttk.Label(frame_painel, text="Alt").grid(row=1, column=0, padx=1)
        ttk.Label(frame_painel, text="Val").grid(row=1, column=1, padx=1)  # Abreviado
        ttk.Label(frame_painel, text="Lk").grid(row=1, column=2, padx=1)  # Abreviado
        for i in range(num_larguras):
            ttk.Label(frame_painel, text=f"H{i+1}").grid(row=1, column=3+i, padx=1)
        
        # Lista para armazenar campos de altura e opções de hatch
        campos_altura = []
        opcoes_hatch = []
        
        # Criar linhas da tabela
        for i in range(num_alturas):
            ttk.Label(frame_painel, text=f"H{i+1}:").grid(row=i+2, column=0, padx=1, sticky="e")
            
            # Frame para altura e lock
            frame_altura = ttk.Frame(frame_painel)
            frame_altura.grid(row=i+2, column=1, columnspan=2, sticky="w")
            
            # Campo de altura
            campo_altura = ttk.Entry(frame_altura, width=6)  # Reduzido width
            campo_altura.grid(row=0, column=0, padx=1)
            campos_altura.append(campo_altura)
            
            # Lock checkbox para altura
            lock_var = tk.BooleanVar()
            cb = ttk.Checkbutton(frame_altura, variable=lock_var)
            cb.grid(row=0, column=1, padx=(0,1))
            self.altura_locks[tipo].append(lock_var)
            
            # Opções de hatch para cada largura (agora campos de texto)
            linha_hatch = []
            for j in range(num_larguras):
                var = tk.StringVar(value="0")  # Valor padrão: "Nenhum"
                campo_hatch = ttk.Entry(frame_painel, textvariable=var, width=12)
                campo_hatch.grid(row=i+2, column=j+3, padx=1)
                linha_hatch.append(var)
            opcoes_hatch.append(linha_hatch)
        
        # Armazenar referências
        self.campos_altura[tipo] = campos_altura
        setattr(self, f'hatch_opcoes_{tipo}', opcoes_hatch)
        
        # Criar frame de abertura abaixo da tabela
        self.criar_frame_abertura(frame_conjunto, tipo_painel, 1)
        
        return frame_conjunto
        
    def criar_campo(self, frame, label, row):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, padx=2, pady=1)
        
        # Criar validação para o campo
        vcmd = (frame.register(self.validar_entrada_numerica), '%P')
        
        entry = ttk.Entry(frame, width=10, validate='key', validatecommand=vcmd)
        entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=2, pady=1)
        
        # Adicionar binding para formatar o número quando o campo perder o foco
        entry.bind('<FocusOut>', lambda e, campo=entry: self.formatar_campo_ao_sair(campo))
        
        return entry

    def formatar_campo_ao_sair(self, campo):
        """Formata o campo numérico quando ele perde o foco"""
        valor_atual = campo.get().strip()
        if valor_atual:
            valor_formatado = self.formatar_numero(valor_atual)
            campo.delete(0, tk.END)
            campo.insert(0, valor_formatado)

    def criar_campo_laje(self, frame, label, row, var_posicao, num_posicoes):
        """Cria um campo de laje com botões de rádio para posição"""
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, padx=2, pady=1)
        
        # Campo para altura da laje usando StringVar
        tipo_laje = label[-2].lower()  # Extrai 'a', 'b', 'c' ou 'd' do label
        entry = ttk.Entry(frame, textvariable=getattr(self, f'laje_{tipo_laje}_var'), width=10)
        entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=2, pady=1)
        self.campos[f'laje_{tipo_laje}'] = entry
        
        # Frame para os botões de rádio
        frame_radio = ttk.Frame(frame)
        frame_radio.grid(row=row+1, column=0, columnspan=2, sticky=tk.W, padx=2, pady=1)
        
        ttk.Label(frame_radio, text="Pos:").grid(row=0, column=0, padx=1)
        
        # Ajustar número de posições baseado no tipo de painel
        max_posicoes = 6 if tipo_laje in ['a', 'b'] else 5
        
        # Criar botões de rádio para cada posição possível
        for i in range(max_posicoes):
            ttk.Radiobutton(frame_radio, text=str(i), variable=var_posicao, 
                           value=i, width=2).grid(row=0, column=i+1, padx=1)
        
    def atualizar_posicao_laje(self, tipo_painel):
        """Atualiza a posição da laje baseada na altura inserida e no tipo de painel"""
        try:
            # Obter altura da laje e pé direito
            altura_laje_str = getattr(self, f'laje_{tipo_painel}_var').get().strip()
            pe_direito_str = self.campos['altura'].get().strip()
            
            if not altura_laje_str or not pe_direito_str:
                return
            
            altura_laje = self.converter_para_float(altura_laje_str)
            pe_direito = self.converter_para_float(pe_direito_str)
            
            if altura_laje < 0 or pe_direito <= 0:
                self.log_mensagem(f"Erro: Altura da laje deve ser não-negativa e pé direito positivo", "erro")
                return
            
            # Selecionar divisor baseado no tipo de painel
            # C e D usam 242, A e B usam 120
            divisor = 242 if tipo_painel in ['c', 'd'] else 120
            
            # Calcular posição usando a fórmula
            posicao = ((pe_direito - altura_laje) / divisor) + 1
            
            # Arredondar para cima
            posicao_final = math.ceil(posicao)
            
            # Ajustar posição máxima baseado no tipo de painel
            max_posicao = 4 if tipo_painel in ['c', 'd'] else 5
            posicao_final = min(posicao_final, max_posicao)
            posicao_final = max(0, posicao_final)  # Garantir que não seja negativo
            
            # Atualizar a posição
            pos_var = getattr(self, f'pos_laje_{tipo_painel}')
            pos_var.set(posicao_final)
            
            # Atualizar o log
            self.log_mensagem(f"Posição da laje {tipo_painel.upper()} atualizada para {posicao_final} (PE={pe_direito}, LAJE={altura_laje}, DIV={divisor})", "info")
            
        except ValueError as e:
            self.log_mensagem(f"Erro de valor: {str(e)}", "erro")
        except Exception as e:
            self.log_mensagem(f"Erro ao atualizar posição da laje: {str(e)}", "erro")
        
    def calcular_dimensoes_ab(self):
        """Calcula as dimensões dos painéis A e B"""
        try:
            comprimento = self.campos['comprimento'].get().strip()
            if not comprimento:
                return
            
            comprimento = self.converter_para_float(comprimento)
            if comprimento <= 0:
                self.log_mensagem("Erro: Comprimento deve ser maior que zero", "erro")
                return
            
            # Calcular para painel A
            self.calcular_dimensoes_painel('a', comprimento)
            
            # Calcular para painel B
            self.calcular_dimensoes_painel('b', comprimento)
            
            # Atualizar posição das lajes
            self.atualizar_posicao_laje('a')
            self.atualizar_posicao_laje('b')
            
            # Preencher caixas de texto com distâncias calculadas
            # Só atualiza os campos se os locks estiverem desativados
            distancias = self.calcular_distancia_parafusos(comprimento)
            for i, entry in enumerate(self.parafuso_entries):
                if not self.parafuso_locks_abcd[i].get():
                    entry.delete(0, tk.END)
                    entry.insert(0, self.formatar_numero(distancias[i]))
            
            self.log_mensagem(f"Dimensões dos painéis A e B calculadas para comprimento {self.formatar_numero(comprimento)}", "info")
            
        except Exception as e:
            self.log_mensagem(f"Erro ao calcular dimensões A/B: {str(e)}", "erro")

    def calcular_dimensoes_cd(self):
        """Calcula as dimensões dos painéis C e D"""
        try:
            largura = self.campos['largura'].get().strip()
            if not largura:
                return
            
            largura = self.converter_para_float(largura)
            if largura <= 0:
                self.log_mensagem("Erro: Largura deve ser maior que zero", "erro")
                return
            
            # Calcular para painel C
            self.calcular_dimensoes_painel('c', largura)
            
            # Calcular para painel D
            self.calcular_dimensoes_painel('d', largura)
            
            # Atualizar posição das lajes
            self.atualizar_posicao_laje('c')
            self.atualizar_posicao_laje('d')
            
            # Preencher caixas de texto com distâncias calculadas
            # Só atualiza os campos se os locks estiverem desativados
            distancias = self.calcular_distancia_parafusos(largura)
            for i, entry in enumerate(self.parafuso_entries):
                if not self.parafuso_locks_abcd[i].get():
                    entry.delete(0, tk.END)
                    entry.insert(0, self.formatar_numero(distancias[i]))
            
            self.log_mensagem(f"Dimensões dos painéis C e D calculadas para largura {self.formatar_numero(largura)}", "info")
            
        except Exception as e:
            self.log_mensagem(f"Erro ao calcular dimensões C/D: {str(e)}", "erro")

    def calcular_distancia_parafusos(self, dimensao):
        """Calcula a distância entre os parafusos com base na dimensão do pilar."""
        quantidade_parafusos = math.ceil((dimensao + 24) / 70) + 1
        if quantidade_parafusos > 1:
            distancia_parafusos = (dimensao + 24) / (quantidade_parafusos - 1)
            distancia_inteira = round(distancia_parafusos)
            total_distancia = distancia_inteira * (quantidade_parafusos - 1)
            diferenca = int((dimensao + 24) - total_distancia)

            distancias = [distancia_inteira] * (quantidade_parafusos - 1)
            for i in range(abs(diferenca)):
                if diferenca > 0:
                    distancias[len(distancias) // 2 + i // 2] += 1
                else:
                    distancias[len(distancias) // 2 + i // 2] -= 1
            
            # Preencher o resto da lista com zeros se necessário
            while len(distancias) < 8:
                distancias.append(0)
        else:
            distancias = [0] * 8  # Retorna uma lista com 8 zeros se não houver parafusos suficientes
        return distancias

    def calcular_dimensoes_painel(self, tipo_painel, dimensao):
        """Calcula as dimensões para um painel específico"""
        try:
            campos = self.campos_ab if tipo_painel in ['a', 'b'] else self.campos_cd
            locks = self.largura_locks[tipo_painel]
            
            # Obter campos de largura
            campo1 = campos[f'comp1_{tipo_painel}']
            campo2 = campos[f'comp2_{tipo_painel}']
            campo3 = campos.get(f'comp3_{tipo_painel}')  # Pode ser None para painéis C/D
            
            # Verificar se todos os campos estão travados
            if tipo_painel in ['a', 'b']:
                todos_travados = all(locks[i].get() for i in range(3))
            else:
                todos_travados = all(locks[i].get() for i in range(2))
                
            if todos_travados:
                self.log_mensagem(f"Todos os campos do painel {tipo_painel} estão travados", "info")
                return
            
            # Obter valores atuais dos campos travados
            valores_travados = []
            espaco_usado = 0
            if tipo_painel in ['a', 'b']:
                for i in range(3):
                    if locks[i].get():
                        try:
                            valor = self.converter_para_float(campos[f'comp{i+1}_{tipo_painel}'].get())
                            valores_travados.append((i, valor))
                            espaco_usado += valor
                        except ValueError:
                            valores_travados.append((i, 0))
            else:
                for i in range(2):
                    if locks[i].get():
                        try:
                            valor = self.converter_para_float(campos[f'comp{i+1}_{tipo_painel}'].get())
                            valores_travados.append((i, valor))
                            espaco_usado += valor
                        except ValueError:
                            valores_travados.append((i, 0))
            
            # Calcular espaço disponível após considerar campos travados
            espaco_disponivel = dimensao
            if tipo_painel in ['a', 'b']:
                espaco_disponivel += 22  # Adicionar 22 para painéis A e B
            espaco_disponivel -= espaco_usado
            
            if tipo_painel in ['a', 'b']:
                # Distribuir espaço disponível entre campos não travados
                campos_livres = [i for i in range(3) if not locks[i].get()]
                if campos_livres:
                    # Se os campos 1 e 2 estão travados, campo 3 assume papel do campo 1
                    if locks[0].get() and locks[1].get() and not locks[2].get():
                        if espaco_disponivel <= 244:
                            campo3.delete(0, tk.END)
                            campo3.insert(0, self.formatar_numero(espaco_disponivel))
                        else:
                            campo3.delete(0, tk.END)
                            campo3.insert(0, "244,00")
                    # Se apenas o campo 1 está travado, campo 2 assume papel do campo 1 e campo 3 do campo 2
                    elif locks[0].get() and not locks[1].get():
                        if espaco_disponivel <= 244:
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, self.formatar_numero(espaco_disponivel))
                            if 2 in campos_livres:
                                campo3.delete(0, tk.END)
                                campo3.insert(0, "0,00")
                        elif espaco_disponivel <= 366:
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, "122,00")
                            if 2 in campos_livres:
                                campo3.delete(0, tk.END)
                                campo3.insert(0, self.formatar_numero(espaco_disponivel - 122))
                        else:  # espaco_disponivel > 366
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, "244,00")
                            if 2 in campos_livres:
                                campo3.delete(0, tk.END)
                                campo3.insert(0, self.formatar_numero(espaco_disponivel - 244))
                    # Lógica normal quando campo 1 não está travado
                    else:
                        if espaco_disponivel <= 244:
                            if 0 in campos_livres:
                                campo1.delete(0, tk.END)
                                campo1.insert(0, self.formatar_numero(espaco_disponivel))
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, "0,00")
                            if 2 in campos_livres:
                                campo3.delete(0, tk.END)
                                campo3.insert(0, "0,00")
                        elif espaco_disponivel <= 366:
                            if 0 in campos_livres:
                                campo1.delete(0, tk.END)
                                campo1.insert(0, "122,00")
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, self.formatar_numero(espaco_disponivel - 122))
                            if 2 in campos_livres:
                                campo3.delete(0, tk.END)
                                campo3.insert(0, "0,00")
                        elif espaco_disponivel <= 428:
                            if 0 in campos_livres:
                                campo1.delete(0, tk.END)
                                campo1.insert(0, "244,00")
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, self.formatar_numero(espaco_disponivel - 244))
                            if 2 in campos_livres:
                                campo3.delete(0, tk.END)
                                campo3.insert(0, self.formatar_numero(espaco_disponivel - 122))
                        elif espaco_disponivel < 488:
                            if 0 in campos_livres:
                                campo1.delete(0, tk.END)
                                campo1.insert(0, "244,00")
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, "122,00")
                            if 2 in campos_livres:
                                campo3.delete(0, tk.END)
                                campo3.insert(0, self.formatar_numero(espaco_disponivel - 244 - 122))
                        else:  # espaco_disponivel >= 488
                            if 0 in campos_livres:
                                campo1.delete(0, tk.END)
                                campo1.insert(0, "244,00")
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, "244,00")
                            if 2 in campos_livres:
                                campo3.delete(0, tk.END)
                                campo3.insert(0, self.formatar_numero(espaco_disponivel - 244 - 122))
            else:  # tipo_painel in ['c', 'd']
                # Distribuir espaço disponível entre campos não travados
                campos_livres = [i for i in range(2) if not locks[i].get()]
                if campos_livres:
                    # Se o primeiro campo está travado, o segundo campo recebe todo o espaço disponível
                    if locks[0].get() and not locks[1].get():
                        campo2.delete(0, tk.END)
                        campo2.insert(0, self.formatar_numero(espaco_disponivel))
                    # Lógica normal quando o primeiro campo não está travado
                    else:
                        if espaco_disponivel <= 122:
                            # Usar apenas o primeiro campo livre
                            if 0 in campos_livres:
                                campo1.delete(0, tk.END)
                                campo1.insert(0, self.formatar_numero(espaco_disponivel))
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, "0,00")
                        else:
                            # Distribuir entre dois campos
                            if 0 in campos_livres:
                                campo1.delete(0, tk.END)
                                campo1.insert(0, "122,00")
                            if 1 in campos_livres:
                                campo2.delete(0, tk.END)
                                campo2.insert(0, self.formatar_numero(espaco_disponivel - 122))
            
            self.log_mensagem(f"Dimensões calculadas para painel {tipo_painel}", "info")
        except Exception as e:
            self.log_mensagem(f"Erro ao calcular dimensões do painel {tipo_painel}: {str(e)}", "error")

    def calcular_alturas_painel(self, tipo_painel):
        """Calcula as alturas para um painel específico"""
        try:
            # Atualizar a altura antes de prosseguir
            self.atualizar_altura()
            
            altura_total = self.converter_para_float(self.campos['altura'].get())
            campos = self.campos_altura[tipo_painel]
            locks = self.altura_locks[tipo_painel]
            
            # Obter altura da laje
            try:
                laje_altura = self.converter_para_float(self.campos[f'laje_{tipo_painel}'].get())
            except ValueError:
                laje_altura = 0
            
            # Subtrair altura da laje e do primeiro painel (2cm) da altura total
            altura_disponivel = altura_total - laje_altura - 2
            
            # Verificar se todos os campos estão travados
            if all(lock.get() for lock in locks):
                self.log_mensagem(f"Todos os campos de altura do painel {tipo_painel} estão travados", "info")
                return
            
            # Obter valores atuais dos campos travados
            valores_travados = []
            altura_usada = 0
            for i, campo in enumerate(campos):
                if locks[i].get():
                    try:
                        valor_str = campo.get().strip()
                        # Usar processar_valor_altura para reconhecer formato X+Y
                        altura_processada, _ = self.processar_valor_altura(valor_str)
                        valores_travados.append((i, altura_processada))
                        altura_usada += altura_processada
                    except (ValueError, TypeError):
                        valores_travados.append((i, 0))
            
            # Se o primeiro campo (2cm) não está travado, garantir que ele seja 2cm
            if not locks[0].get():
                campos[0].delete(0, tk.END)
                campos[0].insert(0, "2,00")
                altura_usada += 2
            
            # Calcular altura disponível
            altura_disponivel = altura_total - altura_usada
            
            # Identificar campos livres (exceto o primeiro que já foi tratado)
            campos_livres = [i for i in range(1, len(campos)) if not locks[i].get()]
            
            if not campos_livres:
                return
            
            # Calcular quantos painéis completos cabem na altura disponível
            max_altura = 122 if tipo_painel in ['a', 'b'] else 244
            num_paineis_completos = int(altura_disponivel // max_altura)
            altura_restante = altura_disponivel % max_altura
            
            # Reordenar campos livres para assumirem a ordem sequencial
            campos_livres.sort()  # Garante que os campos estão em ordem crescente
            
            # Distribuir alturas nos campos livres, tratando-os como se fossem campos sequenciais
            posicao_atual = 1  # Começamos do 1 pois H1 já foi tratado
            for i in campos_livres:
                if posicao_atual <= num_paineis_completos:
                    # Campo recebe altura máxima
                    campos[i].delete(0, tk.END)
                    campos[i].insert(0, self.formatar_numero(max_altura))
                elif posicao_atual == num_paineis_completos + 1 and altura_restante > 0:
                    # Campo recebe altura restante
                    campos[i].delete(0, tk.END)
                    campos[i].insert(0, self.formatar_numero(altura_restante))
                else:
                    # Campo recebe zero
                    campos[i].delete(0, tk.END)
                    campos[i].insert(0, "0,00")
                posicao_atual += 1
            
            self.log_mensagem(f"Alturas calculadas para painel {tipo_painel} (laje: {laje_altura})", "info")
        except Exception as e:
            self.log_mensagem(f"Erro ao calcular alturas do painel {tipo_painel}: {str(e)}", "error")

    def calcular_alturas(self):
        """Calcula as alturas para todos os painéis"""
        try:
            # Validar altura total
            if not self.campos['altura'].get():
                self.log_mensagem("Altura total não informada", "error")
                return
            
            # Calcular alturas para cada painel
            for tipo_painel in ['a', 'b', 'c', 'd']:
                self.calcular_alturas_painel(tipo_painel)
            
            self.log_mensagem("Alturas calculadas para todos os painéis", "info")
        except Exception as e:
            self.log_mensagem(f"Erro ao calcular alturas: {str(e)}", "error")

    def gerar_script(self, larguras_especiais=None, salvar_arquivo=True):
        """
        INTERFACE VISAO ABCD
        Gera o script para a vista lateral dos pilares (A, B, C, D)
        
        Args:
            larguras_especiais: Dicionário com larguras especiais para os painéis
            salvar_arquivo: Se True, salva o arquivo automaticamente. Se False, apenas retorna o conteúdo.
        """
        try:
            print(f"[DEBUG GERAR_SCRIPT] Iniciando geração de script...")
            print(f"[DEBUG GERAR_SCRIPT] Validando entrada...")
            if not self.validar_entrada():
                print(f"[DEBUG GERAR_SCRIPT] ❌ Validação falhou!")
                return
            print(f"[DEBUG GERAR_SCRIPT] ✅ Validação passou!")
                
            # Obter layer dos painéis das configurações
            print(f"[DEBUG GERAR_SCRIPT] Obtendo layer dos painéis...")
            layer_paineis = self.config_manager.get_config("layers", "paineis_abcd")
            # Normalizar caracteres problemáticos
            if layer_paineis:
                layer_paineis = str(layer_paineis).replace('PainÃ©is', 'Painéis').replace('painÃ©is', 'Painéis')
            print(f"[DEBUG GERAR_SCRIPT] Layer painéis: {layer_paineis}")
            
            script = f""";
_LAYER
S
{layer_paineis}

;
"""
            print(f"[DEBUG GERAR_SCRIPT] Criando cabeçalho...")
            script += self.criar_cabecalho()
            print(f"[DEBUG GERAR_SCRIPT] Gerando ped...")
            script += self.gerar_ped()
            print(f"[DEBUG GERAR_SCRIPT] Gerando painéis...")
            script += self.gerar_paineis(larguras_especiais)
            
            # Garantir que o layer de pe direito seja o último a ser definido
            layer_pe_direito = self.config_manager.get_config("layers", "pe_direito")
            # Normalizar caracteres problemáticos
            if layer_pe_direito:
                layer_pe_direito = str(layer_pe_direito).replace('NÃ­vel', 'Nível').replace('nÃ­vel', 'Nível')
            script += f""";
_LAYER
S
{layer_pe_direito}

;
"""
            
            # Aplicar filtro para remover linhas em branco entre ; e comandos _zoom
            # Exemplo: ";\n\n_zoom" -> ";\n_zoom"
            # Padrão: ; seguido de uma ou mais linhas em branco (com ou sem espaços/tabs), seguido de _zoom (case insensitive)
            # Substituir por ; seguido de uma única quebra de linha e _zoom
            # O padrão captura: ; + (espaços/tabs opcionais na mesma linha) + quebra de linha + (uma ou mais linhas em branco) + _zoom
            # Usar padrão que captura múltiplas linhas em branco entre ; e _zoom
            script = re.sub(r';\s*\n(\s*\n)+\s*_zoom', r';\n_zoom', script, flags=re.IGNORECASE | re.MULTILINE)
            
            # Garantir que o script termine com uma nova linha em branco para o AutoCAD processar corretamente
            # IMPORTANTE: O AutoCAD precisa de uma nova linha no final do arquivo para processar o último comando
            # Normalizar para terminar com \r\n (nova linha do Windows)
            if not script.endswith('\r\n'):
                # Remover qualquer \n final e adicionar \r\n
                script = script.rstrip('\n').rstrip('\r') + '\r\n'
            
            # Atualizar o log
            self.log_mensagem("Script gerado com sucesso!", "sucesso")
            
            # CORREÇÃO: Salvar arquivo apenas se salvar_arquivo=True
            # Isso permite que _gerar_script_com_dados_especiais() salve com o nome correto
            if salvar_arquivo:
                # Criar diretório "scripts gerados" se não existir
                pavimento = self.campos['pavimento'].get().strip()
                # Usar path resolver para obter o caminho correto
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                from utils.robust_path_resolver import robust_path_resolver
                diretorio_base = os.path.join(robust_path_resolver.get_project_root(), "output", "scripts")
                # Formatar o nome da pasta: substituir espaços por "_" e adicionar "_ABCD" (evitar duplicidade)
                nome_pasta_pavimento = pavimento.replace(" ", "_")
                if not nome_pasta_pavimento.upper().endswith("_ABCD"):
                    nome_pasta_pavimento += "_ABCD"
                diretorio_pavimento = os.path.join(diretorio_base, nome_pasta_pavimento)
                os.makedirs(diretorio_pavimento, exist_ok=True)

                # Gerar nome de arquivo único com o nome do pilar e sufixo _ABCD
                nome_pilar = self.campos['nome'].get().strip()
                nome_arquivo_base = os.path.join(diretorio_pavimento, nome_pilar)
                nome_arquivo = f"{nome_arquivo_base}_ABCD.scr"
                
                # Sempre sobrescrever o arquivo, não criar sufixos

                # Normalizar caracteres problemáticos no script antes de salvar
                # Corrigir problemas de encoding que podem ocorrer
                script = script.replace('PainÃ©is', 'Painéis')
                script = script.replace('painÃ©is', 'Painéis')
                script = script.replace('NÃ­vel', 'Nível')
                script = script.replace('nÃ­vel', 'Nível')
                
                # Salvar script com o nome do pilar usando UTF-16 LE (com BOM) para compatibilidade com AutoCAD e outros scripts
                with open(nome_arquivo, 'wb') as f:
                    # Adicionar BOM UTF-16 LE
                    f.write(b'\xFF\xFE')
                    # Converter conteúdo para UTF-16 LE (script já tem nova linha no final)
                    f.write(script.encode('utf-16-le'))

                self.log_mensagem(f"Script salvo como: {os.path.basename(nome_arquivo)}", "sucesso")
                
                print(f"[DEBUG GERAR_SCRIPT] ✅ Script gerado com sucesso! Tamanho: {len(script)} caracteres")
                print(f"[DEBUG GERAR_SCRIPT] Arquivo salvo: {nome_arquivo}")
            else:
                print(f"[DEBUG GERAR_SCRIPT] ✅ Script gerado com sucesso! Tamanho: {len(script)} caracteres (não salvo automaticamente)")
            
            return script

        except ValueError as e:
            print(f"[DEBUG GERAR_SCRIPT] ❌ Erro ValueError: {str(e)}")
            self.log_mensagem(f"Erro: Verifique se os valores numéricos são válidos - {str(e)}", "erro")
            return None
        except Exception as e:
            print(f"[DEBUG GERAR_SCRIPT] ❌ Erro Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            self.log_mensagem(f"Erro ao gerar script: {str(e)}", "erro")
            return None
      
    def criar_cabecalho(self):
        """
        INTERFACE VISAO ABCD
        Cria o cabeçalho do script para a vista lateral dos pilares
        """
        return f""";
_ZOOM
C
{self.x_inicial},{self.y_inicial}
10
;"""

    def _obter_nivel_diferencial(self):
        """
        FUNÇÃO GLOBAL ROBUSTA - Tenta obter o nível diferencial do master (interface principal).
        Tenta todos os caminhos possíveis: master.nivel_diferencial, master.interface.nivel_diferencial, etc.
        Retorna o valor em float ou None se não encontrar.
        """
        nivel_diferencial_str = None
        
        # PRIMEIRA TENTATIVA: Acesso direto via getattr (pode funcionar mesmo se hasattr falhar)
        # Isso é especialmente importante em modo frozen ou quando o objeto não expõe atributos via hasattr
        if hasattr(self, 'master') and self.master:
            try:
                nivel_dif = getattr(self.master, 'nivel_diferencial', None)
                if nivel_dif:
                    if hasattr(nivel_dif, 'get'):
                        try:
                            valor = nivel_dif.get()
                            if valor is not None:
                                valor_str = str(valor).strip()
                                if valor_str and valor_str != '':
                                    nivel_diferencial_str = valor_str
                                    print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado via PRIMEIRA TENTATIVA (getattr direto) em master.nivel_diferencial: {nivel_diferencial_str}")
                        except Exception as e:
                            print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro na primeira tentativa (getattr direto): {str(e)}")
                    elif isinstance(nivel_dif, (str, int, float)):
                        valor_str = str(nivel_dif).strip()
                        if valor_str and valor_str != '':
                            nivel_diferencial_str = valor_str
                            print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado via PRIMEIRA TENTATIVA (getattr direto - valor direto) em master.nivel_diferencial: {nivel_diferencial_str}")
            except Exception as e:
                print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro na primeira tentativa (getattr direto): {str(e)}")
        
        # Se já encontrou na primeira tentativa, retornar
        if nivel_diferencial_str:
            try:
                valor_float = self.converter_para_float(nivel_diferencial_str)
                print(f"[NIVEL_DIFERENCIAL] ✅ Valor convertido (primeira tentativa): {valor_float}")
                return valor_float
            except Exception as e:
                print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro ao converter valor da primeira tentativa: {str(e)}")
        
        # SEGUNDA TENTATIVA: Acesso via vars() e __dict__ (pode funcionar quando getattr falha)
        if not nivel_diferencial_str and hasattr(self, 'master') and self.master:
            try:
                # Tentar via vars()
                master_vars = vars(self.master)
                if 'nivel_diferencial' in master_vars:
                    nivel_dif = master_vars['nivel_diferencial']
                    if nivel_dif:
                        if hasattr(nivel_dif, 'get'):
                            try:
                                valor = nivel_dif.get()
                                if valor is not None:
                                    valor_str = str(valor).strip()
                                    if valor_str and valor_str != '':
                                        nivel_diferencial_str = valor_str
                                        print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado via SEGUNDA TENTATIVA (vars()) em master.nivel_diferencial: {nivel_diferencial_str}")
                            except:
                                pass
                        elif isinstance(nivel_dif, (str, int, float)):
                            valor_str = str(nivel_dif).strip()
                            if valor_str and valor_str != '':
                                nivel_diferencial_str = valor_str
                                print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado via SEGUNDA TENTATIVA (vars() - valor direto) em master.nivel_diferencial: {nivel_diferencial_str}")
            except Exception as e:
                print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro na segunda tentativa (vars()): {str(e)}")
        
        # Se já encontrou na segunda tentativa, retornar
        if nivel_diferencial_str:
            try:
                valor_float = self.converter_para_float(nivel_diferencial_str)
                print(f"[NIVEL_DIFERENCIAL] ✅ Valor convertido (segunda tentativa): {valor_float}")
                return valor_float
            except Exception as e:
                print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro ao converter valor da segunda tentativa: {str(e)}")
        
        # Lista de objetos para tentar acessar (em ordem de prioridade)
        objetos_para_tentar = []
        
        # Adicionar master e suas variações
        if hasattr(self, 'master') and self.master:
            objetos_para_tentar.append(('master', self.master))
            
            # Se master tem interface, adicionar também
            if hasattr(self.master, 'interface') and self.master.interface:
                objetos_para_tentar.append(('master.interface', self.master.interface))
            
            # Tentar também se master tem algum atributo que seja a interface
            try:
                if hasattr(self.master, '__dict__'):
                    for attr_name, attr_value in self.master.__dict__.items():
                        if 'interface' in attr_name.lower() and attr_value:
                            objetos_para_tentar.append((f'master.{attr_name}', attr_value))
            except:
                pass
            
            # Tentar também através de root ou parent do master
            try:
                if hasattr(self.master, 'root') and self.master.root:
                    objetos_para_tentar.append(('master.root', self.master.root))
            except:
                pass
            
            try:
                if hasattr(self.master, 'parent') and self.master.parent:
                    objetos_para_tentar.append(('master.parent', self.master.parent))
            except:
                pass
            
            # Tentar também se master é uma instância de uma classe específica (PilarAnalyzer, etc)
            try:
                if hasattr(self.master, '__class__'):
                    class_name = self.master.__class__.__name__
                    print(f"[NIVEL_DIFERENCIAL] 🔍 Tipo do master: {class_name}")
                    # Se o master tem um atributo que seja ele mesmo (self)
                    if hasattr(self.master, 'self') and self.master.self:
                        objetos_para_tentar.append(('master.self', self.master.self))
            except:
                pass
        
        # Tentar também acessar diretamente se self tem nivel_diferencial
        if hasattr(self, 'nivel_diferencial'):
            objetos_para_tentar.insert(0, ('self', self))
        
        # Tentar também através de main_app se disponível (usado pelo conector)
        try:
            if hasattr(self, 'main_app') and self.main_app:
                objetos_para_tentar.append(('main_app', self.main_app))
        except:
            pass
        
        # Tentar também através de root se disponível
        try:
            if hasattr(self, 'root') and self.root:
                objetos_para_tentar.append(('root', self.root))
        except:
            pass
        
        # Tentar acessar nivel_diferencial em cada objeto
        for nome_obj, obj in objetos_para_tentar:
            if nivel_diferencial_str:
                break
                
            try:
                # Tentar obter nivel_diferencial do objeto
                if hasattr(obj, 'nivel_diferencial'):
                    nivel_dif = getattr(obj, 'nivel_diferencial', None)
                    if nivel_dif:
                        # Verificar se tem método get (Entry, StringVar, etc)
                        if hasattr(nivel_dif, 'get'):
                            try:
                                valor = nivel_dif.get()
                                if valor is not None:
                                    valor_str = str(valor).strip()
                                    if valor_str and valor_str != '':
                                        nivel_diferencial_str = valor_str
                                        print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado em {nome_obj}.nivel_diferencial: {nivel_diferencial_str}")
                                        break
                            except Exception as e:
                                print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro ao obter valor de {nome_obj}.nivel_diferencial: {str(e)}")
                                pass
                        # Se não tem get, mas é um valor direto (string, int, float)
                        elif isinstance(nivel_dif, (str, int, float)):
                            valor_str = str(nivel_dif).strip()
                            if valor_str and valor_str != '':
                                nivel_diferencial_str = valor_str
                                print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado diretamente em {nome_obj}.nivel_diferencial: {nivel_diferencial_str}")
                                break
                
                # Tentar também variações do nome do atributo
                variacoes_nome = ['nivel_diferencial', 'nivelDiferencial', 'NivelDiferencial', 'NIVEL_DIFERENCIAL']
                for var_nome in variacoes_nome:
                    if hasattr(obj, var_nome):
                        nivel_dif = getattr(obj, var_nome, None)
                        if nivel_dif:
                            if hasattr(nivel_dif, 'get'):
                                try:
                                    valor = nivel_dif.get()
                                    if valor is not None:
                                        valor_str = str(valor).strip()
                                        if valor_str and valor_str != '':
                                            nivel_diferencial_str = valor_str
                                            print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado em {nome_obj}.{var_nome}: {nivel_diferencial_str}")
                                            break
                                except:
                                    pass
                            elif isinstance(nivel_dif, (str, int, float)):
                                valor_str = str(nivel_dif).strip()
                                if valor_str and valor_str != '':
                                    nivel_diferencial_str = valor_str
                                    print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado diretamente em {nome_obj}.{var_nome}: {nivel_diferencial_str}")
                                    break
                    if nivel_diferencial_str:
                        break
                
                if nivel_diferencial_str:
                    break
                    
            except Exception as e:
                print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro ao acessar {nome_obj}: {str(e)}")
                pass
        
        # Se ainda não encontrou, tentar buscar recursivamente em atributos do master
        if not nivel_diferencial_str and hasattr(self, 'master') and self.master:
            try:
                # Tentar acessar diretamente através de __dict__
                try:
                    if hasattr(self.master, '__dict__'):
                        master_dict = self.master.__dict__
                        if 'nivel_diferencial' in master_dict:
                            nivel_dif = master_dict['nivel_diferencial']
                            if nivel_dif:
                                if hasattr(nivel_dif, 'get'):
                                    try:
                                        valor = nivel_dif.get()
                                        if valor is not None:
                                            valor_str = str(valor).strip()
                                            if valor_str and valor_str != '':
                                                nivel_diferencial_str = valor_str
                                                print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado em master.__dict__['nivel_diferencial']: {nivel_diferencial_str}")
                                    except:
                                        pass
                except:
                    pass
                
                # Tentar também através de vars()
                if not nivel_diferencial_str:
                    try:
                        master_vars = vars(self.master)
                        if 'nivel_diferencial' in master_vars:
                            nivel_dif = master_vars['nivel_diferencial']
                            if nivel_dif:
                                if hasattr(nivel_dif, 'get'):
                                    try:
                                        valor = nivel_dif.get()
                                        if valor is not None:
                                            valor_str = str(valor).strip()
                                            if valor_str and valor_str != '':
                                                nivel_diferencial_str = valor_str
                                                print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado em vars(master)['nivel_diferencial']: {nivel_diferencial_str}")
                                    except:
                                        pass
                    except:
                        pass
                
                # Buscar em todos os atributos do master que contenham 'nivel' e 'diferencial'
                if not nivel_diferencial_str:
                    for attr_name in dir(self.master):
                        if not attr_name.startswith('_') and 'nivel' in attr_name.lower() and 'diferencial' in attr_name.lower():
                            try:
                                attr_value = getattr(self.master, attr_name)
                                if attr_value:
                                    if hasattr(attr_value, 'get'):
                                        try:
                                            valor = attr_value.get()
                                            if valor is not None:
                                                valor_str = str(valor).strip()
                                                if valor_str and valor_str != '':
                                                    nivel_diferencial_str = valor_str
                                                    print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado em master.{attr_name}: {nivel_diferencial_str}")
                                                    break
                                        except:
                                            pass
                                    elif isinstance(attr_value, (str, int, float)):
                                        valor_str = str(attr_value).strip()
                                        if valor_str and valor_str != '':
                                            nivel_diferencial_str = valor_str
                                            print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado diretamente em master.{attr_name}: {nivel_diferencial_str}")
                                            break
                            except:
                                pass
                        if nivel_diferencial_str:
                            break
            except Exception as e:
                print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro ao buscar recursivamente: {str(e)}")
        
        # ÚLTIMA TENTATIVA: Se ainda não encontrou e temos master, tentar acessar diretamente através de getattr com tratamento robusto
        # (pode funcionar mesmo se hasattr falhar em alguns casos de frozen mode)
        if not nivel_diferencial_str and hasattr(self, 'master') and self.master:
            try:
                # Tentar getattr direto (pode funcionar mesmo se hasattr falhar em alguns casos)
                nivel_dif = getattr(self.master, 'nivel_diferencial', None)
                if nivel_dif:
                    if hasattr(nivel_dif, 'get'):
                        try:
                            valor = nivel_dif.get()
                            if valor is not None:
                                valor_str = str(valor).strip()
                                if valor_str and valor_str != '':
                                    nivel_diferencial_str = valor_str
                                    print(f"[NIVEL_DIFERENCIAL] ✅ Valor encontrado via getattr direto (última tentativa) em master.nivel_diferencial: {nivel_diferencial_str}")
                        except Exception as e:
                            print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro ao obter valor via getattr direto: {str(e)}")
            except Exception as e:
                print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro ao tentar getattr direto: {str(e)}")
        
        if not nivel_diferencial_str:
            master_info = f"Master existe: {hasattr(self, 'master')}"
            if hasattr(self, 'master'):
                master_info += f", Master não é None: {self.master is not None}"
                if self.master:
                    master_info += f", Tipo do master: {type(self.master).__name__}"
                    # Tentar listar atributos do master para debug
                    try:
                        master_attrs = [attr for attr in dir(self.master) if not attr.startswith('_') and 'nivel' in attr.lower()]
                        if master_attrs:
                            master_info += f", Atributos relacionados a 'nivel': {master_attrs[:10]}"
                    except:
                        pass
            print(f"[NIVEL_DIFERENCIAL] ⚠️ Nível diferencial não encontrado. {master_info}")
        
        # Se encontrou o valor, converter e retornar
        if nivel_diferencial_str:
            try:
                # Converter para float (suporta vírgula ou ponto)
                valor_float = self.converter_para_float(nivel_diferencial_str)
                print(f"[NIVEL_DIFERENCIAL] ✅ Valor convertido: {valor_float}")
                return valor_float
            except Exception as e:
                print(f"[NIVEL_DIFERENCIAL] ⚠️ Erro ao converter valor '{nivel_diferencial_str}': {str(e)}")
                return None
        
        return None
    
    def gerar_ped(self):
        """
        INTERFACE VISAO ABCD
        Gera os comandos para desenhar as linhas PED horizontais e a cota do pé direito
        na vista lateral dos pilares
        """
        script = ""
        altura = self.converter_para_float(self.campos['altura'].get())
        
        # Obter layer do pé direito das configurações
        layer_pe_direito = self.config_manager.get_config("layers", "pe_direito")
        # Normalizar caracteres problemáticos
        if layer_pe_direito:
            layer_pe_direito = str(layer_pe_direito).replace('NÃ­vel', 'Nível').replace('nÃ­vel', 'Nível')
        
        # Obter tipo de bloco moldura
        bloco_moldura = self.config_manager.get_config("blocks", "moldura")
        
        # Obter nível diferencial para ajuste da coordenada Y (se existir)
        print(f"[GERAR_PED] Iniciando obtenção de nível diferencial...")
        nivel_diferencial_float = self._obter_nivel_diferencial()
        print(f"[GERAR_PED] nivel_diferencial_float obtido: {nivel_diferencial_float} (tipo: {type(nivel_diferencial_float)})")
        
        # Inicializar ajuste como 0 (sempre definido)
        nivel_diferencial_ajuste = 0.0
        
        # Calcular ajuste se nível diferencial for válido
        if nivel_diferencial_float is not None and nivel_diferencial_float != 0:
            print(f"[GERAR_PED] 🔍 DEBUG: Calculando nivel_diferencial_ajuste...")
            print(f"[GERAR_PED] 🔍 DEBUG: nivel_diferencial_float (antes do cálculo) = {nivel_diferencial_float} (tipo: {type(nivel_diferencial_float)})")
            nivel_diferencial_float_convertido = float(nivel_diferencial_float)
            print(f"[GERAR_PED] 🔍 DEBUG: nivel_diferencial_float_convertido = {nivel_diferencial_float_convertido}")
            nivel_diferencial_ajuste = nivel_diferencial_float_convertido / 100.0
            print(f"[GERAR_PED] 🔍 DEBUG: nivel_diferencial_ajuste = {nivel_diferencial_float_convertido} / 100.0 = {nivel_diferencial_ajuste}")
            print(f"[GERAR_PED] ✅ nivel_diferencial_ajuste calculado: {nivel_diferencial_ajuste} (de {nivel_diferencial_float} / 100)")
        else:
            if nivel_diferencial_float is None:
                nivel_diferencial_float = 0.0
            print(f"[GERAR_PED] ⚠️ nivel_diferencial_float é None ou 0, usando ajuste = {nivel_diferencial_ajuste}")
        
        # Garantir que nivel_diferencial_float seja sempre um float
        if nivel_diferencial_float is None:
            nivel_diferencial_float = 0.0
        else:
            nivel_diferencial_float = float(nivel_diferencial_float)
        
        print(f"[GERAR_PED] ✅ Valores finais: nivel_diferencial_float={nivel_diferencial_float}, nivel_diferencial_ajuste={nivel_diferencial_ajuste}")
        
        # Definir comprimento da linha e posição das cotas baseado no tipo de moldura
        bloco_moldura_str = str(bloco_moldura).lower().strip()
        print(f"[GERAR_PED] 🔍 Verificando bloco_moldura: '{bloco_moldura}' (original) -> '{bloco_moldura_str}' (lower/strip)")
        print(f"[GERAR_PED] 🔍 Comparação: '{bloco_moldura_str}' == 'muldura2'? {bloco_moldura_str == 'muldura2'}")
        
        if bloco_moldura_str == "muldura2":
            print(f"[GERAR_PED] ✅ Entrando no bloco muldura2...")
            print(f"[GERAR_PED] 🔍 DEBUG: Antes de calcular comprimento_linha e x_cota")
            comprimento_linha = 1051  # Comprimento específico para muldura2
            x_cota = self.x_inicial + 70  # Nova posição das cotas para muldura2
            print(f"[GERAR_PED] 🔍 DEBUG: comprimento_linha={comprimento_linha}, x_cota={x_cota}")
            
            # Calcular coordenada Y ajustada (soma nível diferencial / 100 se existir)
            print(f"[GERAR_PED] 🔍 DEBUG: Antes de calcular y_ped_inferior")
            print(f"[GERAR_PED] 🔍 DEBUG: self.y_inicial={self.y_inicial}, altura={altura}, nivel_diferencial_ajuste={nivel_diferencial_ajuste} (tipo: {type(nivel_diferencial_ajuste)})")
            print(f"[GERAR_PED] 🔍 DEBUG: Cálculo: y_ped_inferior = {self.y_inicial} - {altura} + 18 + {nivel_diferencial_ajuste}")
            y_ped_inferior = self.y_inicial - altura + 18 + nivel_diferencial_ajuste
            print(f"[GERAR_PED] 🔍 DEBUG: y_ped_inferior (resultado) = {y_ped_inferior}")
            print(f"[GERAR_PED] ✅ y_ped_inferior calculado: {y_ped_inferior} (y_inicial={self.y_inicial}, altura={altura}, nivel_diferencial_ajuste={nivel_diferencial_ajuste})")
            
            # Adicionar os blocos PED para muldura2
            print(f"[GERAR_PED] 🔍 DEBUG: Antes de adicionar os dois primeiros PEDs")
            script += f""";
_ZOOM
C
{x_cota - 30},{self.y_inicial + 18}
10
;
-INSERT
PED
{x_cota - 30},{self.y_inicial + 18}
1
0
;
-INSERT
PED
{x_cota - 30},{self.y_inicial - altura + 18}
1
0
;"""
        else:
            # Valores padrão para quando não é muldura2
            print(f"[GERAR_PED] ⚠️ Não é muldura2, usando valores padrão")
            comprimento_linha = 1000  # Valor padrão para comprimento da linha
            x_cota = self.x_inicial + 50  # Posição padrão das cotas
            print(f"[GERAR_PED] 🔍 DEBUG: comprimento_linha={comprimento_linha}, x_cota={x_cota}")
        
        script += f""";
_LAYER
S
{layer_pe_direito}

;
-DIMSTYLE
restore
{"PAINEL-PATRIARCA" if str(bloco_moldura).lower().strip() == "PAINEL-NOVA" else "PAINEL-NOVA"}
;
_LAYER
S
{layer_pe_direito}

;
_LINETYPE
S
{(self.config_manager.get_config("drawing_options", "linetype_pedireito") or "DASHED").upper()}

;
-STYLE
Arial

12




;
_ZOOM
C
{self.x_inicial},{self.y_inicial}
10
;
_PLINE
{self.x_inicial},{self.y_inicial}
{self.x_inicial + comprimento_linha},{self.y_inicial}

;
_ZOOM
C
{self.x_inicial},{self.y_inicial-altura}
10
;
_PLINE
{self.x_inicial},{self.y_inicial-altura}
{self.x_inicial + comprimento_linha},{self.y_inicial-altura}

;
_LINETYPE
S
continuous

;"""
        
        # Adicionar cota do pé direito
        x_texto = x_cota - 20  # Texto 20cm à esquerda da linha de cota
        
        # Obter layer de cotas das configurações
        layer_cotas = self.config_manager.get_config("layers", "cotas")
        layer_pe_direito = self.config_manager.get_config("layers", "pe_direito")
        script += f""";
_LAYER
S
{layer_cotas}

;
_DIMLINEAR
{x_cota},{self.y_inicial-altura}
{x_cota},{self.y_inicial}
{x_texto},{self.y_inicial-altura/2}
;"""
        
        # --- NOVA LINHA EXTRA ---
        # Calcular y_linha_extra = base_do_pilar + (soma alturas painel A) + laje_a
        y_linha_extra = self.y_inicial - altura  # Começa na base
        
        # Somar alturas do Painel A (h1_a a h5_a)
        altura_extra = 0
        if 'a' in self.campos_altura:
            for entry in self.campos_altura['a']:
                try:
                    valor = self.converter_para_float(entry.get() or 0)
                    altura_extra += valor
                except (ValueError, TypeError):
                    continue
        
        # Adicionar altura da laje A (ou E no Script 2)
        try:
            if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                # Script 2: usar laje E
                if hasattr(self, 'master') and self.master:
                    try:
                        if hasattr(self.master, 'laje_E'):
                            laje_var = getattr(self.master, 'laje_E')
                            if hasattr(laje_var, 'get'):
                                altura_extra += self.converter_para_float(laje_var.get() or 0)
                        elif hasattr(self.master, 'campos') and 'laje_E' in self.master.campos:
                            altura_extra += self.converter_para_float(self.master.campos['laje_E'].get() or 0)
                    except Exception as e:
                        print(f"[LAJE SCRIPT 2] Erro ao acessar laje E: {e}")
            else:
                # Script 1: usar laje A normal
                altura_extra += self.converter_para_float(self.laje_a_var.get() or 0)
        except (ValueError, TypeError):
            pass

        # Só desenha a linha extra se a altura_extra for maior que a altura
        if altura_extra > altura:
            y_linha_extra += altura_extra
            
            # Desenhar linha extra e cotas
            script += f""";
-LINETYPE
S
{(self.config_manager.get_config("drawing_options", "linetype_pedireito") or "DASHED").upper()}

;
_LAYER
S
{layer_pe_direito}

;
_ZOOM
C
{self.x_inicial},{y_linha_extra}
10
;
_PLINE
{self.x_inicial},{y_linha_extra}
{self.x_inicial + comprimento_linha},{y_linha_extra}

;
_LINETYPE
S
continuous

;
_LAYER
S
{layer_cotas}

;
_DIMLINEAR
{x_cota},{self.y_inicial}
{x_cota},{y_linha_extra}
{x_texto},{y_linha_extra/2}

;
_DIMLINEAR
{x_cota-30},{self.y_inicial-altura}
{x_cota-30},{y_linha_extra}
{x_texto-30},{y_linha_extra/2}
;"""
        
        print(f"[GERAR_PED] 🔍 DEBUG: Finalizando função gerar_ped - script tem {len(script)} caracteres")
        if bloco_moldura_str == "muldura2":
            # Verificar se o terceiro PED está no script
            ped_count = script.count("PED")
            print(f"[GERAR_PED] 🔍 DEBUG: Total de comandos PED no script: {ped_count}")
            try:
                # Verificar se o terceiro PED está no script procurando pela coordenada y_ped_inferior
                if 'y_ped_inferior' in locals():
                    coord_str = f"{x_cota - 30},{y_ped_inferior}"
                    print(f"[GERAR_PED] 🔍 DEBUG: Procurando coordenada '{coord_str}' no script: {coord_str in script}")
            except:
                pass
        
        return script
        
    def desenhar_laje_com_centro(self, script, x_inicial, y_atual, largura_total, laje_altura, pos_laje=0, total_paineis=0):
        """Desenha a laje com linhas separadas e adiciona o comando HHHH no centro"""
        # Obter layers das configurações
        layer_laje = self.config_manager.get_config("layers", "laje") or "COTA"
        layer_paineis = self.config_manager.get_config("layers", "paineis_abcd") or "Painéis"
        
        # Obter comando de hatch da laje das configurações
        hatch_laje = self.config_manager.get_config("comandos", "hatches", "laje") or "HHHH"
        
        # Calcular coordenadas da laje
        x_final = x_inicial + largura_total
        y_superior = y_atual + laje_altura
        
        # Determinar quais linhas desenhar baseado na posição da laje
        desenhar_linha_esquerda = True   # Sempre desenhar
        desenhar_linha_direita = True    # Sempre desenhar
        desenhar_linha_fundo = False     # Só se posição 0
        desenhar_linha_topo = False      # Só se acima de todos os painéis
        
        if pos_laje == 0:
            # Laje na posição 0: desenhar esquerda, direita e fundo
            desenhar_linha_fundo = True
            print(f"[LAJE] Posição 0: desenhando esquerda, direita e fundo")
        elif pos_laje >= total_paineis:
            # Laje acima de todos os painéis: desenhar esquerda, direita e topo
            desenhar_linha_topo = True
            print(f"[LAJE] Acima de todos: desenhando esquerda, direita e topo")
        else:
            # Laje entre painéis: desenhar apenas esquerda e direita
            print(f"[LAJE] Entre painéis: desenhando apenas esquerda e direita")
        
        # Configurar layer para as linhas da laje
        script += f""";
_LAYER
S
{layer_laje}

;"""
        
        # Desenhar linha da esquerda (vertical)
        if desenhar_linha_esquerda:
            script += f""";
_ZOOM
C
{x_inicial},{y_atual}
10
;
_PLINE
{x_inicial},{y_atual}
{x_inicial},{y_superior}

;"""
        
        # Desenhar linha da direita (vertical)
        if desenhar_linha_direita:
            script += f""";
_ZOOM
C
{x_final},{y_atual}
10
;
_PLINE
{x_final},{y_atual}
{x_final},{y_superior}

;"""
        
        # Desenhar linha do fundo (horizontal inferior) - só se posição 0
        if desenhar_linha_fundo:
            script += f""";
_ZOOM
C
{x_inicial},{y_atual}
10
;
_PLINE
{x_inicial},{y_atual}
{x_final},{y_atual}

;"""
        
        # Desenhar linha do topo (horizontal superior) - só se acima de todos os painéis
        if desenhar_linha_topo:
            script += f""";
_ZOOM
C
{x_inicial},{y_superior}
10
;
_PLINE
{x_inicial},{y_superior}
{x_final},{y_superior}

;"""
        
        # Não aplicar hatch aqui - será aplicado após as aberturas
        script += f""";
_LAYER
S
{layer_paineis}

;"""
        return script

    def calcular_largura_total_painel(self, tipo_painel, larguras_especiais=None):
        """
        Calcula a largura total de um painel baseada nas globais de larguras.
        Usa as 8 variáveis globais (A-H) para obter as larguras corretas.
        
        Args:
            tipo_painel: Tipo do painel (a, b, c, d, e, f, g, h)
            larguras_especiais: DEPRECATED - mantido para compatibilidade
        """
        try:
            # Verificar se existem globais de larguras
            if hasattr(self, 'larguras_globais') and self.larguras_globais:
                painel_key = tipo_painel.lower()
                if painel_key in self.larguras_globais:
                    largura_total = self.larguras_globais[painel_key]
                    print(f"[GLOBAL_LARGURA] Painel {tipo_painel.upper()}: usando global = {largura_total}cm")
                    return largura_total
            
            # Fallback: usar campos existentes (para pilares comuns)
            if tipo_painel.lower() in ['a', 'b']:
                # Painéis A e B: usar comprimento + 22 (compatibilidade)
                comprimento = self.converter_para_float(self.campos['comprimento'].get() or 0)
                return comprimento + 22
            elif tipo_painel.lower() in ['c', 'd']:
                # Painéis C e D: usar largura (compatibilidade)
                largura = self.converter_para_float(self.campos['largura'].get() or 0)
                return largura
            else:
                # Para pilares especiais (E, F, G, H) - fallback
                print(f"[LARGURA_TOTAL] Painel {tipo_painel.upper()}: Usando largura padrão (globais não encontradas)")
                return 100  # Largura padrão para especiais
                
        except (ValueError, AttributeError) as e:
            print(f"[LARGURA_TOTAL] Erro ao calcular largura do painel {tipo_painel}: {e}")
            # Fallback para valores padrão
            if tipo_painel.lower() in ['a', 'b']:
                return 122  # Comprimento padrão + 22
            elif tipo_painel.lower() in ['c', 'd']:
                return 50   # Largura padrão
            else:
                return 100  # Largura padrão para especiais

    def processar_valor_altura(self, valor_str: str) -> tuple:
        """
        Processa um valor de altura que pode estar no formato 'X+Y' ou apenas um número.
        Retorna uma tupla (altura_total, altura_linha_central) onde altura_linha_central é None se não houver '+'.
        """
        try:
            if '+' in valor_str:
                partes = valor_str.split('+')
                if len(partes) == 2:
                    altura1 = self.converter_para_float(partes[0].strip())
                    altura2 = self.converter_para_float(partes[1].strip())
                    return (altura1 + altura2, altura1)
            return (self.converter_para_float(valor_str), None)
        except (ValueError, TypeError):
            return (0, None)

    def desenhar_painel_com_hatch(self, script, x_atual, y_atual, comprimento_painel, altura_painel, tipo_painel, indice_altura, indice_largura, hatch_opcoes):
        """Desenha um painel e adiciona o hatch se necessário"""
        # Obter layer dos painéis das configurações
        layer_paineis = self.config_manager.get_config("layers", "paineis_abcd")
        layer_cotas = self.config_manager.get_config("layers", "cotas")
        
        # Verificar se o valor original estava no formato X+Y
        valor_original = self.campos_altura[tipo_painel][indice_altura].get().strip()
        altura_total, altura_linha_central = self.processar_valor_altura(valor_original)
        
        # Desenhar o painel com 4 linhas separadas
        script += f""";
_ZOOM
C
{x_atual},{y_atual}
10
;
_PLINE
{x_atual},{y_atual}
{x_atual + comprimento_painel},{y_atual}

;
_ZOOM
C
{x_atual + comprimento_painel},{y_atual}
10
;
_PLINE
{x_atual + comprimento_painel},{y_atual}
{x_atual + comprimento_painel},{y_atual + altura_painel}

;
_ZOOM
C
{x_atual + comprimento_painel},{y_atual + altura_painel}
10
;
_PLINE
{x_atual + comprimento_painel},{y_atual + altura_painel}
{x_atual},{y_atual + altura_painel}

;
_ZOOM
C
{x_atual},{y_atual + altura_painel}
10
;
_PLINE
{x_atual},{y_atual + altura_painel}
{x_atual},{y_atual}

;"""

        # Se houver altura da linha central, desenhar a linha e as cotas
        if altura_linha_central is not None:
            # Desenhar a linha central
            script += f""";
_LAYER
S
{layer_paineis}

;
_ZOOM
C
{x_atual},{y_atual + altura_linha_central}
10
;
_PLINE
{x_atual},{y_atual + altura_linha_central}
{x_atual + comprimento_painel},{y_atual + altura_linha_central}

;"""
            # Desenhar as cotas verticais
            script += f""";
_LAYER
S
{layer_cotas}

;
_DIMLINEAR
{x_atual + comprimento_painel},{y_atual + altura_linha_central}
{x_atual + comprimento_painel},{y_atual}
{x_atual + comprimento_painel + 15},{y_atual + altura_linha_central}

;
_DIMLINEAR
{x_atual + comprimento_painel},{y_atual + altura_linha_central}
{x_atual + comprimento_painel},{y_atual + altura_painel}
{x_atual + comprimento_painel + 15},{y_atual + altura_linha_central}
;
_LAYER
S
{layer_paineis}

;"""
        
        # Verificar se precisa adicionar hatch
        # NÃO aplicar hatch em painéis de 2cm (altura_painel <= 2.0)
        if altura_painel <= 2.0:
            print(f"[HATCH] Pulando hatch para painel de 2cm: {tipo_painel}[{indice_altura}] - altura: {altura_painel}cm")
        elif indice_altura < len(hatch_opcoes) and indice_largura < len(hatch_opcoes[indice_altura]):
            hatch_tipo = hatch_opcoes[indice_altura][indice_largura].get()
            
            # NOVO: Verificar se há globais de hatch dos painéis E-F-G-H para Script 2
            # Só usar globais se for Script 2 (quando usar_paineis_efgh=True)
            if (hasattr(self, 'hatches_globais_efgh') and self.hatches_globais_efgh and 
                hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh):
                # Mapear painéis A-B-C-D para E-F-G-H
                mapeamento_paineis = {'a': 'e', 'b': 'f', 'c': 'g', 'd': 'h'}
                painel_orig = mapeamento_paineis.get(tipo_painel.lower(), tipo_painel.lower())
                
                # Tentar usar global de hatch
                global_hatch_nome = f"hatch_{painel_orig}_{indice_altura + 1}"
                hatch_global = self.hatches_globais_efgh.get(global_hatch_nome, None)
                
                if hatch_global is not None and hatch_global != "0":
                    hatch_tipo = hatch_global
                    print(f"[GLOBAL_HATCH] Script 2 - Usando global para {tipo_painel}[{indice_altura}]: {hatch_tipo} (de {global_hatch_nome})")
                else:
                    print(f"[GLOBAL_HATCH] Script 2 - Global {global_hatch_nome} não encontrada ou é '0', usando valor normal")
            
            # Verificar se há valores salvos dos checkboxes do preview
            # NÃO usar preview values se for Script 2 (usar_paineis_efgh=True)
            if (hasattr(self, 'master') and self.master and hasattr(self.master, 'hatch_preview_values') and
                not (hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh)):
                if tipo_painel.lower() in self.master.hatch_preview_values:
                    if indice_altura in self.master.hatch_preview_values[tipo_painel.lower()]:
                        preview_value = self.master.hatch_preview_values[tipo_painel.lower()][indice_altura]
                        if preview_value != "0":
                            hatch_tipo = preview_value
                            print(f"[HATCH PREVIEW] Script 1 - Usando valor do preview para {tipo_painel}[{indice_altura}]: {hatch_tipo}")
            elif hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                print(f"[HATCH PREVIEW] Script 2 - Pulando preview values para {tipo_painel}[{indice_altura}] (usando apenas globais)")
            
            if hatch_tipo != "0":  # Se não for "0", desenha o hatch
                # Calcular centro do painel e ajustar posição
                x_centro = x_atual + (comprimento_painel / 2)
                y_centro = y_atual + (altura_painel / 2)
                
                # Ajustar posição: 12cm abaixo e 7cm à direita do centro
                x_hatch = x_centro + 7  # 7cm à direita do centro
                y_hatch = y_centro - 12  # 12cm abaixo do centro
                
                if hatch_tipo == "1":
                    script += f""";
_ZOOM
C
{x_hatch},{y_hatch}
5
;
HH
{x_hatch},{y_hatch}
;
_LAYER
S
{layer_paineis}

;"""
                elif hatch_tipo == "2":
                    script += f""";
_ZOOM
C
{x_hatch},{y_hatch}
5
;
HHH
{x_hatch},{y_hatch}
;
_LAYER
S
{layer_paineis}

;"""
        
        # Verificar se a numeração está ativada
        numeracao_config = self.config_manager.get_config("blocks", "numeracao")
        if numeracao_config and numeracao_config.get("ativar"):
            # Só numerar a partir da altura 2 (índice 1)
            if indice_altura > 0:
                # Calcular centro exato do painel
                x_centro = x_atual + (comprimento_painel / 2)
                y_centro = y_atual + (altura_painel / 2)
                
                # Calcular numeração cumulativa entre painéis
                numero_cumulativo = self.calcular_numero_cumulativo(tipo_painel, indice_altura)
                
                # Determinar qual bloco usar (n1 a n15)
                bloco_num = f"n{numero_cumulativo}"
                if bloco_num in numeracao_config and numero_cumulativo <= 15:
                    nome_bloco = numeracao_config[bloco_num]
                    script += f""";
_ZOOM
C
{x_centro},{y_centro}
5
;
-INSERT
{nome_bloco}
{x_centro - 6},{y_centro}
1
0
;"""
        
        return script


    def desenhar_aberturas(self, script, tipo_painel, x_inicial, y_inicial, largura_total):
        """Desenha todas as aberturas (esq1, esq2, dir1, dir2) para um painel"""
        tipo = tipo_painel.lower()
        
        try:
            # Obter layer dos painéis das configurações
            layer_paineis = self.config_manager.get_config("layers", "paineis_abcd")
            script += f""";
_LAYER
S
{layer_paineis}

;"""
            
            # Lista de todas as aberturas a serem processadas
            aberturas = [
                ('esq1', 'esquerda'), ('esq2', 'esquerda'),
                ('dir1', 'direita'), ('dir2', 'direita')
            ]
            
            # Obter a altura da laje para este painel
            # No Script 2 (usar_paineis_efgh=True), usar lajes E,F,G,H em vez de A,B,C,D
            if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                # Mapear A→E, B→F, C→G, D→H para lajes do Script 2
                mapeamento_lajes = {'a': 'e', 'b': 'f', 'c': 'g', 'd': 'h'}
                painel_laje = mapeamento_lajes.get(tipo_painel.lower(), tipo_painel.lower())
                
                # Buscar laje do master (interface principal) que tem E,F,G,H
                if hasattr(self, 'master') and self.master:
                    try:
                        # Tentar múltiplas formas de acessar as variáveis
                        laje_altura = 0
                        laje_posicao = 0
                        
                        # Tentar atributos diretos com maiúscula
                        laje_attr_upper = f'laje_{painel_laje.upper()}'
                        pos_attr_upper = f'posicao_laje_{painel_laje.upper()}'
                        
                        if hasattr(self.master, laje_attr_upper):
                            laje_var = getattr(self.master, laje_attr_upper)
                            if hasattr(laje_var, 'get'):
                                laje_altura = self.converter_para_float(laje_var.get() or 0)
                        
                        # Tentar atributos diretos com minúscula
                        laje_attr_lower = f'laje_{painel_laje.lower()}'
                        pos_attr_lower = f'posicao_laje_{painel_laje.lower()}'
                        
                        if laje_altura == 0 and hasattr(self.master, laje_attr_lower):
                            laje_var = getattr(self.master, laje_attr_lower)
                            if hasattr(laje_var, 'get'):
                                laje_altura = self.converter_para_float(laje_var.get() or 0)
                        
                        # Tentar via dicionário campos com maiúscula
                        if laje_altura == 0 and hasattr(self.master, 'campos'):
                            if laje_attr_upper in self.master.campos:
                                laje_altura = self.converter_para_float(self.master.campos[laje_attr_upper].get() or 0)
                        
                        # Tentar via dicionário campos com minúscula
                        if laje_altura == 0 and hasattr(self.master, 'campos'):
                            if laje_attr_lower in self.master.campos:
                                laje_altura = self.converter_para_float(self.master.campos[laje_attr_lower].get() or 0)
                        
                        # Fazer o mesmo para posição
                        if hasattr(self.master, pos_attr_upper):
                            pos_var = getattr(self.master, pos_attr_upper)
                            if hasattr(pos_var, 'get'):
                                pos_raw = pos_var.get()
                                print(f"[DEBUG LAJE POS] posicao_laje_{painel_laje.upper()} valor RAW: '{pos_raw}' (tipo: {type(pos_raw)})")
                                laje_posicao = self.converter_para_float(pos_raw or 0)
                        elif hasattr(self.master, pos_attr_lower):
                            pos_var = getattr(self.master, pos_attr_lower)
                            if hasattr(pos_var, 'get'):
                                laje_posicao = self.converter_para_float(pos_var.get() or 0)
                        elif hasattr(self.master, 'campos') and pos_attr_upper in self.master.campos:
                            laje_posicao = self.converter_para_float(self.master.campos[pos_attr_upper].get() or 0)
                        elif hasattr(self.master, 'campos') and pos_attr_lower in self.master.campos:
                            laje_posicao = self.converter_para_float(self.master.campos[pos_attr_lower].get() or 0)
                        
                        print(f"[LAJE SCRIPT 2] Painel {tipo_painel} usando laje {painel_laje.upper()}: altura={laje_altura}, posicao={laje_posicao}")
                        
                        # Debug adicional para verificar se as variáveis existem
                        print(f"[DEBUG LAJE] Verificando variáveis para {painel_laje.upper()}:")
                        print(f"[DEBUG LAJE] master tem posicao_laje_{painel_laje.upper()}: {hasattr(self.master, f'posicao_laje_{painel_laje.upper()}')}")
                        print(f"[DEBUG LAJE] master tem posicao_laje_{painel_laje.lower()}: {hasattr(self.master, f'posicao_laje_{painel_laje.lower()}')}")
                        if hasattr(self.master, 'campos'):
                            print(f"[DEBUG LAJE] campos tem posicao_laje_{painel_laje.upper()}: {f'posicao_laje_{painel_laje.upper()}' in self.master.campos}")
                            print(f"[DEBUG LAJE] campos tem posicao_laje_{painel_laje.lower()}: {f'posicao_laje_{painel_laje.lower()}' in self.master.campos}")
                    except Exception as e:
                        print(f"[LAJE SCRIPT 2] Erro ao acessar laje {painel_laje}: {e}")
                        laje_altura = 0
                        laje_posicao = 0
                else:
                    laje_altura = 0
                    laje_posicao = 0
            else:
                # Script 1: usar lajes normais A,B,C,D
                laje_altura = self.converter_para_float(getattr(self, f'laje_{tipo_painel}_var').get() or 0)
                laje_posicao = self.converter_para_float(getattr(self, f'pos_laje_{tipo_painel}').get() or 0)
            
            # Obter a altura total do pilar
            altura_total = self.converter_para_float(self.campos['altura'].get() or 0)
            
            # Determinar se há painéis acima da laje
            tem_paineis_acima = False
            if tipo in ['a', 'b']:
                num_alturas = 5
            else:
                num_alturas = 4
            
            # Verificar se a posição da laje é entre painéis
            if 0 < laje_posicao < num_alturas - 1:
                tem_paineis_acima = True
            
            # Calcular o ajuste de altura para aberturas
            ajuste_altura = laje_altura
            
            # Calcular a altura total dos painéis acima da laje
            altura_paineis_acima = 0
            if tem_paineis_acima:
                altura_paineis_acima = self.calcular_altura_paineis_acima_laje(tipo_painel)
            
            # Calcular a linha extra para aberturas do topo2
            y_linha_extra = y_inicial - altura_paineis_acima
            
            # Calcular a nova referência para aberturas (soma h1-h5 + laje)
            y_referencia_aberturas = y_inicial - self.calcular_soma_alturas_painel(tipo_painel)
            
            # Processar cada abertura
            for abertura_id, lado in aberturas:
                # Obter valores da abertura
                # NOVO: Usar globais de aberturas E-F-G-H se disponíveis
                if hasattr(self, 'aberturas_globais_efgh') and self.aberturas_globais_efgh:
                    # Mapear painéis A-B-C-D para E-F-G-H
                    mapeamento_paineis = {'a': 'e', 'b': 'f', 'c': 'g', 'd': 'h'}
                    painel_orig = mapeamento_paineis.get(tipo, tipo)
                    
                    # Tentar usar global primeiro
                    global_nome = f"abertura_{abertura_id}_{{tipo}}_{painel_orig}"
                    dist_global = self.aberturas_globais_efgh.get(f"abertura_{abertura_id}_dist_{painel_orig}", None)
                    prof_global = self.aberturas_globais_efgh.get(f"abertura_{abertura_id}_prof_{painel_orig}", None)
                    larg_global = self.aberturas_globais_efgh.get(f"abertura_{abertura_id}_larg_{painel_orig}", None)
                    pos_global = self.aberturas_globais_efgh.get(f"abertura_{abertura_id}_pos_{painel_orig}", None)
                    
                    if dist_global is not None and prof_global is not None and larg_global is not None:
                        # Usar globais
                        dist = dist_global
                        prof = prof_global
                        larg = larg_global
                        pos = pos_global if pos_global is not None else '0'
                        print(f"[GLOBAL_ABERTURAS] Usando global para {tipo}.{abertura_id}: dist={dist}, prof={prof}, larg={larg}, pos={pos}")
                    else:
                        # Fallback para campos normais
                        dist = self.campos[f'abertura_{abertura_id}_dist_{tipo}'].get()
                        prof = self.campos[f'abertura_{abertura_id}_prof_{tipo}'].get()
                        larg = self.campos[f'abertura_{abertura_id}_larg_{tipo}'].get()
                        pos = self.campos[f'abertura_{abertura_id}_pos_{tipo}'].get()
                        print(f"[GLOBAL_ABERTURAS] Usando campo normal para {tipo}.{abertura_id}: dist={dist}, prof={prof}, larg={larg}, pos={pos}")
                else:
                    # Usar campos normais
                    dist = self.campos[f'abertura_{abertura_id}_dist_{tipo}'].get()
                    prof = self.campos[f'abertura_{abertura_id}_prof_{tipo}'].get()
                    larg = self.campos[f'abertura_{abertura_id}_larg_{tipo}'].get()
                    pos = self.campos[f'abertura_{abertura_id}_pos_{tipo}'].get()
                
                # Para o painel B, ser mais permissivo com aberturas
                if tipo == 'b':
                    # Para painel B, verificar apenas se prof e larg existem (permitir dist=0)
                    if not prof or not larg or prof.strip() == '' or larg.strip() == '':
                        continue
                else:
                    # Para outros painéis, manter validação original
                    if not all([dist, prof, larg]):
                        continue
                
                try:
                    dist = self.converter_para_float(dist)
                    prof = self.converter_para_float(prof)
                    larg = self.converter_para_float(larg)
                    
                    # Para todos os painéis, não desenhar aberturas com boca (larg) = 0
                    # EXCETO para o painel B que pode ter largura 0, mas ainda precisa ter profundidade > 0
                    if larg == 0 and tipo != 'b':
                        continue
                    if larg == 0 and tipo == 'b' and prof == 0:
                        continue
                    
                    # Calcular coordenadas X baseadas no lado
                    if lado == 'esquerda':
                        x1 = x_inicial + dist
                        x2 = x1 + larg
                    else:  # direita
                        x1 = x_inicial + largura_total - dist - larg
                        x2 = x1 + larg
                    
                    # Calcular Y1 baseado no campo de posição
                    # y1_original sempre na posição de referência (sem rebaixo)
                    y1_original = y_referencia_aberturas
                    
                    if pos:
                        try:
                            pos_val = self.converter_para_float(pos)
                            y1 = y_referencia_aberturas - pos_val  # Y com rebaixo aplicado
                            prof_ajustado = prof
                        except ValueError:
                            y1 = y_referencia_aberturas
                            prof_ajustado = prof
                    else:
                        y1 = y_referencia_aberturas
                        prof_ajustado = prof
                    
                    # --- VERIFICAÇÃO TOPO LAJE ---
                    y_topo_laje = y_inicial - self.calcular_soma_alturas_painel(tipo_painel)
                    abertura_ajustada = False
                    
                    # Verificar se laje está no topo
                    try:
                        if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                            # Script 2: usar laje_posicao (E,F,G,H)
                            pos_laje_para_verificacao = laje_posicao
                        else:
                            # Script 1: usar pos_laje (A,B,C,D)
                            pos_laje_para_verificacao = self.converter_para_float(getattr(self, f'pos_laje_{tipo_painel}').get() or 0)
                        
                        # Obter alturas dos painéis para calcular se laje está no topo
                        alturas_paineis = []
                        
                        # Usar a mesma lógica do gerar_paineis para obter alturas
                        if hasattr(self, 'campos_altura') and tipo_painel.lower() in self.campos_altura:
                            for campo in self.campos_altura[tipo_painel.lower()]:
                                try:
                                    valor = campo.get().strip()
                                    if valor:
                                        altura_total, _ = self.processar_valor_altura(valor)
                                        if altura_total > 0:
                                            alturas_paineis.append(altura_total)
                                except ValueError:
                                    continue
                        else:
                            # Fallback: tentar acessar h1_A, h2_A, etc. diretamente
                            for i in range(1, 6):  # h1 a h5
                                try:
                                    if hasattr(self, f'h{i}_{tipo_painel}'):
                                        altura = self.converter_para_float(getattr(self, f'h{i}_{tipo_painel}').get() or 0)
                                        if altura > 0:
                                            alturas_paineis.append(altura)
                                except:
                                    continue
                        
                        # Verificar se laje está no topo (posição >= número de painéis)
                        # Se pos_laje = 0, significa que não há laje
                        # Se pos_laje >= número de painéis, significa que está no topo
                        # Se não há painéis definidos (lista vazia), considerar posição >= 3 como topo
                        if len(alturas_paineis) > 0:
                            # Há painéis definidos: verificar se posição >= número de painéis
                            laje_no_topo = (pos_laje_para_verificacao > 0 and 
                                          pos_laje_para_verificacao >= len(alturas_paineis))
                        else:
                            # Não há painéis definidos: considerar posição >= 3 como topo
                            laje_no_topo = (pos_laje_para_verificacao > 0 and 
                                          pos_laje_para_verificacao >= 3)
                        
                        print(f"[DEBUG ABERTURA] Painel {tipo_painel}: pos_laje={pos_laje_para_verificacao}, num_paineis={len(alturas_paineis)}, laje_no_topo={laje_no_topo}")
                        print(f"[DEBUG ABERTURA] Alturas painéis: {alturas_paineis}")
                        print(f"[DEBUG ABERTURA] Comparação: {pos_laje_para_verificacao} > 0 AND {pos_laje_para_verificacao} >= {len(alturas_paineis)} = {laje_no_topo}")
                        
                    except Exception as e:
                        print(f"[DEBUG ABERTURA] Erro ao verificar posição da laje: {e}")
                        laje_no_topo = False
                    
                    # Só aplicar ajuste se laje estiver no topo
                    if abs(y1 - y_topo_laje) < 0.01 and laje_altura > 0 and laje_no_topo:
                        prof_ajustado = prof - laje_altura
                        y1 = y1 - laje_altura
                        if prof_ajustado < 0:
                            prof_ajustado = 0
                        abertura_ajustada = True
                        print(f"[DEBUG ABERTURA] ✅ AJUSTE APLICADO para {tipo_painel}: prof_original={prof}, prof_ajustado={prof_ajustado}, laje_altura={laje_altura}")
                    else:
                        print(f"[DEBUG ABERTURA] ❌ AJUSTE NÃO APLICADO para {tipo_painel}: y1={y1}, y_topo_laje={y_topo_laje}, laje_altura={laje_altura}, laje_no_topo={laje_no_topo}")
                    y2 = y1 - prof_ajustado
                    
                    # Desenhar a abertura
                    script += f""";
"""
                    
                    # Processar aberturas para todos os painéis, independente da distância
                    if True:
                        # Verificar se é uma abertura de laje
                        # Mapear abertura_id para o nome do campo de tipo
                        # abertura_id vem como 'esq1', 'esq2', 'dir1', 'dir2'
                        # Precisamos converter para 'esq_1', 'esq_2', 'dir_1', 'dir_2'
                        if abertura_id.startswith('esq'):
                            num = abertura_id[3:]  # '1' ou '2'
                            campo_tipo_nome = f"tipo_esq_{num}_{tipo.upper()}"
                        elif abertura_id.startswith('dir'):
                            num = abertura_id[3:]  # '1' ou '2'
                            campo_tipo_nome = f"tipo_dir_{num}_{tipo.upper()}"
                        else:
                            campo_tipo_nome = f"tipo_{abertura_id}_{tipo.upper()}"
                        
                        # DEBUG: Verificar valores de abertura de laje no desenhar_aberturas
                        print(f"🔍 DEBUG DESENHAR_ABERTURAS:")
                        print(f"  Painel: {tipo}, Abertura: {abertura_id}")
                        print(f"  Campo tipo: {campo_tipo_nome}")
                        
                        # Tentar ler da interface principal se disponível
                        laje_value = "0"  # Valor padrão
                        if hasattr(self, 'master') and self.master and hasattr(self.master, campo_tipo_nome):
                            try:
                                campo_tipo = getattr(self.master, campo_tipo_nome)
                                # Para Entry widgets, usar .get() diretamente
                                if hasattr(campo_tipo, 'get'):
                                    laje_value = campo_tipo.get().strip()
                                    print(f"  🔄 Valor da interface principal: '{laje_value}'")
                                else:
                                    print(f"  ⚠️ Campo não é um Entry widget: {type(campo_tipo)}")
                            except Exception as e:
                                print(f"  ⚠️ Erro ao ler da interface principal: {e}")
                        # Fallback: usar valores carregados via Excel no próprio gerador (self.abertura_laje)
                        if laje_value != "1":
                            try:
                                if hasattr(self, 'abertura_laje') and tipo in self.abertura_laje and abertura_id in self.abertura_laje[tipo]:
                                    laje_excel = self.abertura_laje[tipo][abertura_id].get().strip()
                                    print(f"  🔁 Fallback abertura_laje[{tipo}][{abertura_id}] = '{laje_excel}'")
                                    if laje_excel == "1":
                                        laje_value = "1"
                                        print("  ✅ Usando valor de fallback (Excel -> gerador)")
                            except Exception as e:
                                print(f"  ⚠️ Erro no fallback de abertura_laje: {e}")
                        
                        print(f"  Valor final: '{laje_value}' (tipo: {type(laje_value)})")
                        print(f"  Comparação: '{laje_value}' == '1'? {laje_value == '1'}")
                        
                        # Definir is_central antes de usar
                        is_central = dist > 0
                        
                        if laje_value == "1":
                            comando = self.config_manager.get_config("comandos", "aberturas", "ABVLJ") or "ABVLJ"
                            print(f"  ✅ GERANDO COMANDO ABVLJ no desenhar_aberturas para {tipo}.{abertura_id}")
                            print(f"  Comando: {comando}")
                            script += f""";
_ZOOM
C
{x1},{y1}
10
;
app
{x1},{y1}
{x2},{y2}
;
_ZOOM
C
{x1},{y1}
10
;
{comando}
{x1},{y1}
{x2},{y2}
;"""
                        else:
                            print(f"  ❌ NÃO gerando ABVLJ no desenhar_aberturas para {tipo}.{abertura_id} (valor: '{laje_value}')")
                            largura_abertura = abs(x2 - x1)
                            # Escolher comando considerando centralidade e largura
                            if is_central:
                                if largura_abertura < 13:
                                    comando = self.config_manager.get_config("comandos", "aberturas", "abv12") or "abv12"
                                else:
                                    comando = self.config_manager.get_config("comandos", "aberturas", "abv") or "abv"
                            else:
                                if largura_abertura < 13:
                                    comando = self.config_manager.get_config("comandos", "aberturas", "abve12") if lado == 'esquerda' else self.config_manager.get_config("comandos", "aberturas", "abvd12")
                                else:
                                    comando = self.config_manager.get_config("comandos", "aberturas", "abve") if lado == 'esquerda' else self.config_manager.get_config("comandos", "aberturas", "abvd")
                            print(f"  ▶️ Comando escolhido para {tipo}.{abertura_id}: {comando} | lado={lado} | dist={dist} | larg={largura_abertura} | prof={prof_ajustado} | pos='{pos}'")
                            
                            script += f""";
_ZOOM
C
{x1},{y1}
10
;
app
{x1},{y1}
{x2},{y2}
;
_ZOOM
C
{x1},{y1}
10
;
{comando}
{x1},{y1}
{x2},{y2}
;"""
                        # Adicionar linha extra e cota para aberturas abv
                        # Só desenhar linha horizontal se NÃO for abertura central com tipo laje
                        desenhar_linha_horizontal = True
                        
                        # Verificar se é abertura central (dist > 0) e tipo laje (laje_value == "1")
                        if is_central and laje_value == "1":
                            desenhar_linha_horizontal = False
                            print(f"  🚫 PULANDO linha horizontal para abertura central tipo laje: {tipo}.{abertura_id}")
                        
                        if desenhar_linha_horizontal:
                            if lado == 'esquerda':
                                script += f""";
_LAYER
S
{layer_paineis}

;
_ZOOM
C
{x1},{y2}
5
;
_PLINE
{x1},{y2}
{x_inicial},{y2}

;
;
"""
                            else:
                                script += f""";
_LAYER
S
{layer_paineis}

;
_ZOOM
C
{x2},{y2}
5
;
_PLINE
{x2},{y2}
{x_inicial + largura_total},{y2}

;
;
"""
                    else:
                        script += self.gerar_comandos_abertura(x1, y1, x2, y2, lado, tipo_painel, abertura_id)
                    # Adicionar erase no topo da abertura se foi ajustada
                    if abertura_ajustada:
                        script += f""";
_ZOOM
C
{x1 + 5},{y1}
5
;
appdel
{x1 + 5},{y1}
;
appdel
{x1 + 5},{y1}
;
appdel
{x1 + 5},{y1}
;
"""
                    # Adicionar hatch
                    if larg >= 1:
                        hatch_laje = self.config_manager.get_config("comandos", "hatches", "laje") or "HHHH"
                        script += f""";
_ZOOM
C
{x1 + 5},{y1}
5
;
{hatch_laje}
{(x1 + x2) / 2},{(y1 + y2) / 2}
;
"""
                    
                    # Adicionar cotas
                    # COTA VERTICAL: fixa nas bordas do painel, independente da distância da abertura
                    # Para aberturas da esquerda, cota na borda esquerda do painel (x_inicial)
                    # Para aberturas da direita, cota na borda direita do painel (x_inicial + largura_total)
                    if lado == 'esquerda':
                        cota_vertical_x = x_inicial
                        cota_vertical_offset = x_inicial - 15
                    else:  # direita
                        cota_vertical_x = x_inicial + largura_total
                        cota_vertical_offset = x_inicial + largura_total + 15
                    
                    script += f""";
;
;
_ZOOM
C
{cota_vertical_x},{y1}
10
;
_DIMLINEAR
{cota_vertical_x},{y1}
{cota_vertical_x},{y2}
{cota_vertical_offset},{(y1 + y2) / 2}

;
_DIMLINEAR
{x1},{y1_original}
{x2},{y1_original}
{(x1 + x2) / 2},{y1_original + 10}
;
"""
                    
                except ValueError as e:
                    self.log_mensagem(f"Erro ao processar valores da abertura {abertura_id}: {str(e)}", "erro")
                    continue
                except Exception as e:
                    self.log_mensagem(f"Erro ao desenhar abertura {abertura_id}: {str(e)}", "erro")
                    continue
            
            return script
        
        except Exception as e:
            self.log_mensagem(f"Erro ao desenhar aberturas do painel {tipo_painel}: {str(e)}", "erro")
        
        return script

    def gerar_comandos_abertura(self, x1, y1, x2, y2, lado, tipo_painel, abertura_id):
        """Gera comandos para aberturas"""
        # Ajustar zoom baseado na largura da abertura
        largura = abs(x2 - x1)
        
        # Zoom centralizado com fator 10 para aberturas pequenas
        if largura < 13:
            script = f""";
_ZOOM
C
{min(x1,x2)-3},{y2-3}
10
;
"""
        else:
            # Zoom normal para aberturas maiores
            script = f""";
_ZOOM
C
{min(x1,x2)-3},{y2-3}
10
;
"""
        
        # Verificar se é uma abertura de laje (prioridade máxima)
        # Mapear abertura_id para o nome do campo de tipo
        # abertura_id vem como 'esq1', 'esq2', 'dir1', 'dir2'
        # Precisamos converter para 'esq_1', 'esq_2', 'dir_1', 'dir_2'
        if abertura_id.startswith('esq'):
            num = abertura_id[3:]  # '1' ou '2'
            campo_tipo_nome = f"tipo_esq_{num}_{tipo_painel.upper()}"
        elif abertura_id.startswith('dir'):
            num = abertura_id[3:]  # '1' ou '2'
            campo_tipo_nome = f"tipo_dir_{num}_{tipo_painel.upper()}"
        else:
            campo_tipo_nome = f"tipo_{abertura_id}_{tipo_painel.upper()}"
        
        # DEBUG: Verificar valores de abertura de laje
        print(f"🔍 DEBUG GERAÇÃO COMANDOS ABERTURA:")
        print(f"  Painel: {tipo_painel}, Abertura: {abertura_id}")
        print(f"  Campo tipo: {campo_tipo_nome}")
        
        # Tentar ler da interface principal se disponível
        laje_value = "0"  # Valor padrão
        if hasattr(self, 'master') and self.master and hasattr(self.master, campo_tipo_nome):
            try:
                campo_tipo = getattr(self.master, campo_tipo_nome)
                # Para Entry widgets, usar .get() diretamente
                if hasattr(campo_tipo, 'get'):
                    laje_value = campo_tipo.get().strip()
                    print(f"  🔄 Valor da interface principal: '{laje_value}'")
                else:
                    print(f"  ⚠️ Campo não é um Entry widget: {type(campo_tipo)}")
            except Exception as e:
                print(f"  ⚠️ Erro ao ler da interface principal: {e}")

        # Fallback: usar valores carregados via Excel no próprio gerador (self.abertura_laje)
        if laje_value != "1":
            try:
                painel_key = tipo_painel.lower()
                if hasattr(self, 'abertura_laje') and painel_key in self.abertura_laje and abertura_id in self.abertura_laje[painel_key]:
                    laje_excel = self.abertura_laje[painel_key][abertura_id].get().strip()
                    print(f"  🔁 Fallback abertura_laje[{painel_key}][{abertura_id}] = '{laje_excel}'")
                    if laje_excel == "1":
                        laje_value = "1"
                        print("  ✅ Usando valor de fallback (Excel -> gerador)")
            except Exception as e:
                print(f"  ⚠️ Erro no fallback de abertura_laje: {e}")
        
        # DEBUG: Verificar se o campo existe e tem valor
        print(f"  🔍 Verificando campo {campo_tipo_nome}")
        print(f"  🔍 Campo existe? {hasattr(self.master, campo_tipo_nome) if hasattr(self, 'master') and self.master else False}")
        
        # DEBUG: Listar todos os campos que começam com 'tipo_esq_1_'
        if hasattr(self, 'master') and self.master:
            campos_tipo = [attr for attr in dir(self.master) if attr.startswith('tipo_esq_1_')]
            print(f"  🔍 Campos tipo_esq_1_ encontrados: {campos_tipo}")
            campos_tipo = [attr for attr in dir(self.master) if attr.startswith('tipo_')]
            print(f"  🔍 Todos os campos tipo_ encontrados: {campos_tipo[:10]}...")  # Mostrar apenas os primeiros 10
        
        if hasattr(self, 'master') and self.master and hasattr(self.master, campo_tipo_nome):
            campo = getattr(self.master, campo_tipo_nome)
            print(f"  🔍 Tipo do campo: {type(campo)}")
            print(f"  🔍 Valor do campo: '{campo.get()}'")
            print(f"  🔍 Valor após strip: '{campo.get().strip()}'")
        
        print(f"  Valor final: '{laje_value}' (tipo: {type(laje_value)})")
        print(f"  Comparação: '{laje_value}' == '1'? {laje_value == '1'}")
        
        
        if laje_value == "1":
            comando = self.config_manager.get_config("comandos", "aberturas", "ABVLJ") or "ABVLJ"
            print(f"  ✅ GERANDO COMANDO ABVLJ para {tipo_painel}.{abertura_id}")
            print(f"  Comando: {comando}")
            script += f""";
_ZOOM
C
{x1},{y1}
10
;
app
{x1},{y1}
{x2},{y2}
;
_ZOOM
C
{x1},{y1}
10
;
{comando}
{x1},{y1}
{x2},{y2}
;"""
            return script
        else:
            print(f"  ❌ NÃO gerando ABVLJ para {tipo_painel}.{abertura_id} (valor: '{laje_value}')")
        
        # Se não for abertura de laje, continua com a lógica normal
        # Escolher o comando apropriado baseado na largura e lado
        if largura < 13:
            comando_tipo = self.config_manager.get_config("comandos", "aberturas", "abve12") if lado == 'esquerda' else self.config_manager.get_config("comandos", "aberturas", "abvd12")
            if largura < 7:
                comando_tipo = self.config_manager.get_config("comandos", "aberturas", "abve12") if lado == 'esquerda' else self.config_manager.get_config("comandos", "aberturas", "abvd12")
        else:
            comando_tipo = self.config_manager.get_config("comandos", "aberturas", "abve") if lado == 'esquerda' else self.config_manager.get_config("comandos", "aberturas", "abvd")
        
        script += f""";
_ZOOM
C
{x1},{y1}
10
;
app
{x1},{y1}
{x2},{y2}
;
_ZOOM
C
{x1},{y1}
10
;
{comando_tipo}
{x1},{y1}
{x2},{y2}
;"""

        # Adicionar comando appla/applad para aberturas com largura < 7
        if largura < 7:
            ajuste = 7 - largura
            if lado == 'esquerda':
                # Para aberturas esquerdas, crescer para a direita e usar appla
                x_ajustado = x2 + ajuste
                script += f"""
_ZOOM
C
{x1+7},{y1}
10
;
break2
{x1+7},{y1}
{x1+7},{y2}
{x1+7},{y1}
;"""
            else:
                # Para aberturas direitas, crescer para a esquerda e usar applad
                x_ajustado = x1 + (-ajuste)
                script += f"""
_ZOOM
C
{x2-7},{y1}
10
;
break2
{x2-7},{y1}
{x2-7},{y2}
{x2-7},{y1}
;"""
        
        return script

    def gerar_paineis(self, larguras_especiais=None):
        try:
            script = self.criar_cabecalho()
            
            # CORREÇÃO: Reler valores AQUI para garantir valores atualizados (Script 2)
            altura = self.converter_para_float(self.campos['altura'].get())
            comprimento = self.converter_para_float(self.campos['comprimento'].get())
            largura = self.converter_para_float(self.campos['largura'].get())
            print(f"[GERAR_PAINEIS] Valores lidos para validação: comprimento={comprimento}, largura={largura}")
            
            if altura <= 0 or comprimento <= 0 or largura <= 0:
                self.log_mensagem("Erro: Dimensões devem ser maiores que zero", "erro")
                return ""
            
            # Inserir bloco MOLDURA antes de desenhar os painéis
            script = self.inserir_bloco_moldura(script)
            
            # Desenhar texto informativo antes dos painéis
            script = self.desenhar_texto_informativo(script, self.x_inicial, self.y_inicial)
            
            # Definir layer Painéis antes de começar a desenhar
            layer_paineis = self.config_manager.get_config("layers", "paineis_abcd")
            script += f""";
_LAYER
S
{layer_paineis}

;"""
            
            # Obter tipo de bloco moldura e logar para debug
            bloco_moldura = self.config_manager.get_config("blocks", "moldura")
            self.log_mensagem(f"Tipo de moldura configurado: {bloco_moldura}", "info")
            
            # Definir posições iniciais e espaçamentos
            x_a = self.x_inicial
            y_a = self.y_inicial
            
            # Ajustar posições baseado no tipo de moldura
            if str(bloco_moldura).lower().strip() == "muldura2":
                self.log_mensagem("Usando configuração MULDURA2", "info")
                # Posição inicial do painel A (140cm da parede)
                x_a += 140
                
                # CORREÇÃO: Usar largura calculada individualmente para posicionamento
                largura_a = self.calcular_largura_total_painel('a', larguras_especiais)
                largura_b = self.calcular_largura_total_painel('b', larguras_especiais)
                largura_c = self.calcular_largura_total_painel('c', larguras_especiais)
                largura_d = self.calcular_largura_total_painel('d', larguras_especiais)
                
                # Posições dos demais painéis com espaçamento fixo de 100cm
                x_b = x_a + largura_a + 100  # 100cm entre A e B
                x_c = x_b + largura_b + 100  # 100cm entre B e C
                x_d = x_c + largura_c + 100  # 100cm entre C e D
            else:
                self.log_mensagem("Usando configuração padrão MULDURA", "info")
                # Configuração original
                x_a += 80  # 80cm da parede
                espacamento = self.calcular_espacamento_paineis(comprimento)
                
                # CORREÇÃO: Usar largura calculada individualmente para posicionamento
                largura_a = self.calcular_largura_total_painel('a', larguras_especiais)
                largura_b = self.calcular_largura_total_painel('b', larguras_especiais)
                largura_c = self.calcular_largura_total_painel('c', larguras_especiais)
                largura_d = self.calcular_largura_total_painel('d', larguras_especiais)
                
                x_b = x_a + largura_a + espacamento
                x_c = x_b + largura_b + espacamento
                x_d = x_c + largura_c + (espacamento - 70)
            
            y_b = y_a
            y_c = y_a
            y_d = y_a
            
            # Logar posições para debug
            self.log_mensagem(f"Posições: A({x_a}), B({x_b}), C({x_c}), D({x_d})", "info")
            
            # Lista para armazenar informações das aberturas
            aberturas_para_desenhar = []
            
            # Desenhar painéis na ordem correta
            paineis_info = []  # Lista para armazenar informações dos painéis
            for tipo_painel, x_inicial, y_inicial in [
                ('a', x_a, y_a),
                ('b', x_b, y_b),
                ('c', x_c, y_c),
                ('d', x_d, y_d)
            ]:
                try:
                    # Obter dados do painel
                    alturas = []
                    for campo in self.campos_altura[tipo_painel]:
                        valor = campo.get().strip()
                        if valor:
                            try:
                                altura_total, _ = self.processar_valor_altura(valor)
                                if altura_total > 0:
                                    alturas.append(altura_total)
                            except ValueError:
                                continue
                    
                    if not alturas:
                        continue
                    
                    # Obter altura da laje e posição
                    try:
                        # No Script 2 (usar_paineis_efgh=True), usar lajes E,F,G,H em vez de A,B,C,D
                        if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                            # Script 2: mapear A→E, B→F, C→G, D→H
                            mapeamento_lajes = {'a': 'e', 'b': 'f', 'c': 'g', 'd': 'h'}
                            painel_laje = mapeamento_lajes.get(tipo_painel.lower(), tipo_painel.lower())
                            
                            # Buscar laje do master (interface principal)
                            laje_altura = 0
                            pos_laje = 0
                            
                            if hasattr(self, 'master') and self.master:
                                try:
                                    # Tentar múltiplas formas de acessar as variáveis
                                    laje_attr_upper = f'laje_{painel_laje.upper()}'
                                    pos_attr_upper = f'posicao_laje_{painel_laje.upper()}'
                                    
                                    if hasattr(self.master, laje_attr_upper):
                                        laje_var = getattr(self.master, laje_attr_upper)
                                        if hasattr(laje_var, 'get'):
                                            laje_altura = self.converter_para_float(laje_var.get() or 0)
                                    elif hasattr(self.master, 'campos') and laje_attr_upper in self.master.campos:
                                        laje_altura = self.converter_para_float(self.master.campos[laje_attr_upper].get() or 0)
                                    
                                    if hasattr(self.master, pos_attr_upper):
                                        pos_var = getattr(self.master, pos_attr_upper)
                                        if hasattr(pos_var, 'get'):
                                            pos_laje = self.converter_para_float(pos_var.get() or 0)
                                    elif hasattr(self.master, 'campos') and pos_attr_upper in self.master.campos:
                                        pos_laje = self.converter_para_float(self.master.campos[pos_attr_upper].get() or 0)
                                    
                                    print(f"[LAJE SCRIPT 2] Painel {tipo_painel} usando laje {painel_laje.upper()}: altura={laje_altura}, posicao={pos_laje}")
                                except Exception as e:
                                    print(f"[LAJE SCRIPT 2] Erro ao acessar laje {painel_laje}: {e}")
                                    laje_altura = 0
                                    pos_laje = 0
                        else:
                            # Script 1: usar lajes normais A,B,C,D
                            laje_altura = self.converter_para_float(self.campos[f'laje_{tipo_painel}'].get() or 0)
                            pos_laje = self.converter_para_float(getattr(self, f'pos_laje_{tipo_painel}').get() or 0)
                    except (ValueError, AttributeError):
                        laje_altura = 0
                        pos_laje = 0
                    
                    # CORREÇÃO: Usar largura calculada individualmente para todos os painéis
                    largura_total = self.calcular_largura_total_painel(tipo_painel, larguras_especiais)
                    paineis_info.append({
                        'tipo': tipo_painel,
                        'x_inicial': x_inicial,
                        'y_inicial': y_inicial,
                        'largura': largura_total,
                        'alturas': alturas,
                        'laje_altura': laje_altura,
                        'parafusos': [self.converter_para_float(self.parafuso_entries[i].get() or 0) for i in range(8)] if tipo_painel in ['a', 'b'] else []
                    })
                    
                    # Obter comprimentos baseado no tipo de painel
                    if tipo_painel in ['a', 'b']:
                        try:
                            comp1 = self.converter_para_float(self.campos_ab[f'comp1_{tipo_painel}'].get() or 0)
                            comp2 = self.converter_para_float(self.campos_ab[f'comp2_{tipo_painel}'].get() or 0)
                            comp3 = self.converter_para_float(self.campos_ab[f'comp3_{tipo_painel}'].get() or 0)
                            comprimentos = [c for c in [comp1, comp2, comp3] if c > 0]
                            # CORREÇÃO: Usar função para calcular largura total individualmente
                            largura_total = self.calcular_largura_total_painel(tipo_painel, larguras_especiais)
                        except ValueError:
                            continue
                    else:  # tipo_painel in ['c', 'd', 'e', 'f', 'g', 'h']
                        try:
                            if tipo_painel in ['c', 'd']:
                                comp1 = self.converter_para_float(self.campos_cd[f'comp1_{tipo_painel}'].get() or 0)
                                comp2 = self.converter_para_float(self.campos_cd[f'comp2_{tipo_painel}'].get() or 0)
                                comprimentos = [c for c in [comp1, comp2] if c > 0]
                            else:  # tipo_painel in ['e', 'f', 'g', 'h']
                                comp1 = self.converter_para_float(getattr(self, f'comp1_{tipo_painel.upper()}', tk.StringVar()).get() or 0)
                                comp2 = self.converter_para_float(getattr(self, f'comp2_{tipo_painel.upper()}', tk.StringVar()).get() or 0)
                                comprimentos = [c for c in [comp1, comp2] if c > 0]
                            # CORREÇÃO: Usar função para calcular largura total individualmente
                            largura_total = self.calcular_largura_total_painel(tipo_painel, larguras_especiais)
                        except ValueError:
                            continue
                    
                    if not comprimentos:
                        continue
                    
                    # Primeiro painel sempre começa com 2cm
                    if alturas[0] != 2:
                        alturas.insert(0, 2)
                    
                    # Calcular posição inicial baseada na posição da laje
                    y_atual = y_inicial - altura  # Começar da linha inferior do pé direito
                    
                    # Obter opções de hatch para este painel
                    hatch_opcoes = getattr(self, f'hatch_opcoes_{tipo_painel}', [])
                    
                    # Variável para controlar se a laje já foi desenhada
                    laje_desenhada = False
                    
                    # Se a laje está na posição 0, desenhar ela primeiro
                    if pos_laje == 0 and laje_altura > 0:
                        script = self.desenhar_laje_com_centro(script, x_inicial, y_atual, largura_total, laje_altura, pos_laje, len(alturas))
                        y_atual += laje_altura
                        laje_desenhada = True
                    
                    # Desenhar painéis
                    for i, altura_painel in enumerate(alturas):
                        # Se chegamos na posição da laje e não é posição 0, desenhar a laje
                        if i == pos_laje and pos_laje > 0 and laje_altura > 0:
                            script = self.desenhar_laje_com_centro(script, x_inicial, y_atual, largura_total, laje_altura, pos_laje, len(alturas))
                            y_atual += laje_altura
                            laje_desenhada = True
                        
                        # Desenhar painel com hatch
                        x_atual = x_inicial
                        for j, comprimento_painel in enumerate(comprimentos):
                            script = self.desenhar_painel_com_hatch(script, x_atual, y_atual, 
                                                                  comprimento_painel, altura_painel,
                                                                  tipo_painel, i, j, hatch_opcoes)
                            x_atual += comprimento_painel
                        
                        y_atual += altura_painel
                    
                    # Se a laje deve ficar acima do último painel E ainda não foi desenhada
                    if pos_laje >= len(alturas) and laje_altura > 0 and not laje_desenhada:
                        script = self.desenhar_laje_com_centro(script, x_inicial, y_atual, largura_total, laje_altura, pos_laje, len(alturas))
                    
                    # Armazenar informações das aberturas para desenhar depois
                    aberturas_para_desenhar.append((tipo_painel, x_inicial, y_inicial, largura_total))
                    
                except Exception as e:
                    self.log_mensagem(f"Erro ao desenhar painel {tipo_painel}: {str(e)}", "erro")
                    continue
            
            # Adicionar chamada para desenhar sarrafos após desenhar os painéis
            for info in paineis_info:
                if info['tipo'] in ['a', 'b', 'c', 'd']:  # Incluir painéis A e B
                    script = self.desenhar_sarrafos(
                        script,
                        info['tipo'],
                        info['x_inicial'],
                        info['y_inicial'],
                        info['largura'],
                        info['alturas'],
                        info['laje_altura']
                    )
            
            # Desenhar cotas para cada painel
            layer_cotas = self.config_manager.get_config("layers", "cotas")
            script += f""";
_LAYER
S
{layer_cotas}

;"""
            
            for info in paineis_info:
                # Obter comprimentos do painel
                if info['tipo'] in ['a', 'b']:
                    comprimentos = [
                        self.converter_para_float(self.campos_ab[f'comp1_{info["tipo"]}'].get() or 0),
                        self.converter_para_float(self.campos_ab[f'comp2_{info["tipo"]}'].get() or 0),
                        self.converter_para_float(self.campos_ab[f'comp3_{info["tipo"]}'].get() or 0)
                    ]
                else:
                    comprimentos = [
                        self.converter_para_float(self.campos_cd[f'comp1_{info["tipo"]}'].get() or 0),
                        self.converter_para_float(self.campos_cd[f'comp2_{info["tipo"]}'].get() or 0)
                    ]
                
                # Filtrar apenas comprimentos maiores que zero
                comprimentos = [c for c in comprimentos if c > 0]
                
                # Desenhar cotas verticais e horizontais
                script = self.desenhar_cotas_verticais(
                    script,
                    info['tipo'],
                    info['x_inicial'],
                    info['y_inicial'],
                    info['alturas'],
                    info['laje_altura']
                )
                
                script = self.desenhar_cotas_horizontais(
                    script,
                    info['tipo'],
                    info['x_inicial'],
                    info['y_inicial'],
                    comprimentos
                )
                
                # Inserir blocos SLIPTEE e SLIPTDD para painéis A e B
                script = self.inserir_blocos_split(
                    script,
                    info['tipo'],
                    info['x_inicial'],
                    info['y_inicial'],
                    info['largura']
                )
                
                # Inserir blocos de furação para painéis A e B
                if info['tipo'] in ['a', 'b']:
                    script = self.inserir_blocos_furacao(
                        script,
                        info['tipo'],
                        info['x_inicial'],
                        info['y_inicial'],
                        info['parafusos'],
                        info['alturas'],
                        info['laje_altura']
                    )
                
                # Inserir parafusos no centro para painéis C e D (largura >= 40cm)
                if info['tipo'] in ['c', 'd']:
                    script = self.inserir_parafusos_centro_cd(
                        script,
                        info['tipo'],
                        info['x_inicial'],
                        info['y_inicial'],
                        info['largura'],
                        info['alturas'],
                        info['laje_altura']
                    )
            
            # Adicionar textos verticais para cada painel
            for tipo_painel, x_inicial, y_inicial in [
                ('a', x_a, y_a),
                ('b', x_b, y_b),
                ('c', x_c, y_c),
                ('d', x_d, y_d)
            ]:
                script = self.desenhar_texto_painel(script, tipo_painel, x_inicial, y_inicial)
            
            # Desenhar todas as aberturas por último
            if aberturas_para_desenhar:
                script += f""";
_LAYER
S
{layer_paineis}

;"""
                for tipo_painel, x_inicial, y_inicial, largura_total in aberturas_para_desenhar:
                    script = self.desenhar_aberturas(script, tipo_painel, x_inicial, y_inicial, largura_total)
            
            # Aplicar hatch das lajes após as aberturas
            for info in paineis_info:
                if info['laje_altura'] > 0:
                    # Obter alturas do painel para calcular posição
                    alturas = info['alturas']
                    laje_altura = info['laje_altura']
                    
                    # Buscar pos_laje do master
                    try:
                        if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                            # Script 2: mapear A→E, B→F, C→G, D→H
                            mapeamento_lajes = {'a': 'e', 'b': 'f', 'c': 'g', 'd': 'h'}
                            painel_laje = mapeamento_lajes.get(info['tipo'].lower(), info['tipo'].lower())
                            pos_attr_upper = f'posicao_laje_{painel_laje.upper()}'
                            
                            pos_laje = 0
                            if hasattr(self, 'master') and self.master:
                                if hasattr(self.master, pos_attr_upper):
                                    pos_var = getattr(self.master, pos_attr_upper)
                                    if hasattr(pos_var, 'get'):
                                        pos_laje = int(self.converter_para_float(pos_var.get() or 0))
                        else:
                            # Script 1: usar pos_laje do campo
                            pos_laje = int(self.converter_para_float(getattr(self, f'pos_laje_{info["tipo"]}').get() or 0))
                    except:
                        pos_laje = 0
                    
                    # Calcular posição Y da laje seguindo a mesma lógica de desenho
                    # y_atual começa em y_inicial - altura
                    altura = self.converter_para_float(self.campos['altura'].get())
                    y_inicial = info['y_inicial']
                    y_atual = y_inicial - altura
                    
                    # Se pos_laje == 0, laje está na base (y_atual atual)
                    if pos_laje == 0:
                        y_laje = y_atual
                    # Se pos_laje >= len(alturas), laje está no topo
                    elif pos_laje >= len(alturas):
                        # Calcular soma de todas as alturas dos painéis
                        soma_alturas = sum(alturas)
                        y_laje = y_atual + soma_alturas
                    # Se pos_laje está entre painéis, calcular posição
                    else:
                        # Somar alturas dos painéis até pos_laje
                        soma_alturas = 0
                        for i in range(pos_laje):
                            soma_alturas += alturas[i]
                        y_laje = y_atual + soma_alturas
                    
                    # Calcular centro Y da laje
                    y_centro = y_laje + (laje_altura / 2)
                    x_centro = info['x_inicial'] + (info['largura'] / 2)
                    
                    hatch_laje = self.config_manager.get_config("comandos", "hatches", "laje") or "HHHH"
                    
                    script += f""";
_ZOOM
C
{x_centro},{y_centro}
10
;
{hatch_laje}
{x_centro},{y_centro}
;
_ZOOM
C
{x_centro},{y_centro}
10
;
"""
            
            return script
        except Exception as e:
            self.log_mensagem(f"Erro ao gerar painéis: {str(e)}", "erro")
            return ""


    def desenhar_sarrafos(self, script, tipo_painel, x_inicial, y_inicial, largura, alturas, altura_laje):
        """Desenha os sarrafos para os painéis seguindo as regras especificadas."""
        try:
            pe_direito = self.converter_para_float(self.campos['altura'].get())
        except ValueError:
            self.log_mensagem("Erro: Altura inválida.", "erro")
            return script

        # Verificar se deve desenhar sarrafos para painéis C e D
        if tipo_painel in ['c', 'd']:
            desenhar_sarrafos_cd = self.config_manager.get_config("drawing_options", "desenhar_sarrafos_cd")
            if not desenhar_sarrafos_cd:
                return script

        # Obter layers de sarrafos das configurações
        layer_sarrafos_verticais = self.config_manager.get_config("layers", "linhas_hidden")  # Sarrafos verticais
        layer_sarrafos_horizontais = self.config_manager.get_config("layers", "sarrafos")      # Sarrafos horizontais

        # Obter offset dos sarrafos das configurações
        sarrafo_offset = self.config_manager.get_config("drawing_options", "sarrafo_offset") or 7
        
        # Obter modo de sarrafos (PLINE ou MLINE)
        modo_sarrafos = self.config_manager.get_config("drawing_options", "modo_sarrafos") or "Pline"

        # Iniciar na base do pilar
        y_atual = y_inicial - pe_direito

        # Obter o comprimento do pilar para painéis A e B
        comprimento_pilar = 0
        if tipo_painel in ['a', 'b']:
            try:
                comprimento_pilar = self.converter_para_float(self.campos['comprimento'].get())
            except ValueError:
                comprimento_pilar = 0

        for i, altura in enumerate(alturas):
            if altura <= 0 or i == 0:  # Pular alturas zeradas e o painel de altura 1 (H1)
                y_atual += altura
                continue

            # Verificar se há laje e se está na posição atual
            altura_laje = 0
            posicao_laje = -1

            # Usar função auxiliar para obter laje correta (Script 1 ou 2)
            laje_altura_total, pos_laje_total = self.obter_laje_correta(tipo_painel)
            
            if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                # Script 2: verificar posição da laje E,F,G,H
                if pos_laje_total == i + 1:
                    altura_laje = laje_altura_total
                    posicao_laje = i + 1
            else:
                # Script 1: verificar posição da laje A,B,C,D
                if tipo_painel == 'a' and self.pos_laje_a.get() == i + 1:
                    altura_laje = laje_altura_total
                    posicao_laje = i + 1
                elif tipo_painel == 'b' and self.pos_laje_b.get() == i + 1:
                    altura_laje = laje_altura_total
                    posicao_laje = i + 1
                elif tipo_painel == 'c' and self.pos_laje_c.get() == i + 1:
                    altura_laje = laje_altura_total
                    posicao_laje = i + 1
                elif tipo_painel == 'd' and self.pos_laje_d.get() == i + 1:
                    altura_laje = laje_altura_total
                    posicao_laje = i + 1

            # Posições dos sarrafos verticais
            if modo_sarrafos == "Pline" or tipo_painel in ['a', 'b']:  # Sempre usar PLINE para painéis A e B
                x_esquerdo = x_inicial + sarrafo_offset
                x_direito = x_inicial + largura - sarrafo_offset
            else:  # MLINE apenas para painéis C e D
                x_esquerdo = x_inicial  # Sobreposto à parede esquerda
                x_direito = x_inicial + largura - sarrafo_offset  # Mantém offset na direita

            # Definir tipo de linha com base no tipo de painel
            if tipo_painel in ['a', 'b']:
                script += f""";
_LINETYPE
S
{(self.config_manager.get_config("drawing_options", "linetype_sarrafos_hidden") or "DASHED").upper()}

;"""
            else:
                script += f""";
_LINETYPE
S
CONTINUOUS

;"""

            # Desenhar sarrafos verticais para o painel atual
            if posicao_laje == -1:
                # Sem laje na posição atual
                if tipo_painel in ['c', 'd'] and largura < 30:
                    # Sarrafos verticais apenas para C e D
                    if modo_sarrafos == "Pline":
                        # C e D usando PLINE - usar layer_sarrafos_verticais
                        script += f""";
_LAYER
S
{layer_sarrafos_verticais}

;
_ZOOM
C
{x_esquerdo},{y_atual}
10
;
_PLINE
{x_esquerdo},{y_atual}
{x_esquerdo},{y_atual + altura}

;
_ZOOM
C
{x_direito},{y_atual}
10
;
_PLINE
{x_direito},{y_atual}
{x_direito},{y_atual + altura}

;
;
_LINETYPE
S
CONTINUOUS

;"""
                    else:  # MLINE apenas para painéis C e D
                        # C e D verticais também usam layer_sarrafos_verticais
                        script += f""";
_LAYER
S
{layer_sarrafos_verticais}

;
_ZOOM
C
{x_esquerdo},{y_atual}
10
;
_MLINE
ST
SAR2
S
7
{x_esquerdo},{y_atual}
{x_esquerdo},{y_atual + altura}

;
_ZOOM
C
{x_direito},{y_atual}
10
;
_MLINE
ST
SAR2
S
7
{x_direito},{y_atual}
{x_direito},{y_atual + altura}

;
;
_LINETYPE
S
CONTINUOUS

;"""
                    y_atual += altura
                elif tipo_painel in ['c', 'd'] and largura >= 30:
                    # Sarrafos horizontais - usar layer correto
                    script += f""";
_LAYER
S
{layer_sarrafos_horizontais}

;"""
                    
                    if modo_sarrafos == "Pline":
                        # Desenha apenas se não for o primeiro painel (altura 2cm)
                        if i > 0:  # Não desenha no painel de 2cm
                            script += f""";
_ZOOM
C
{x_inicial},{y_atual + sarrafo_offset}
10
;
_PLINE
{x_inicial},{y_atual + sarrafo_offset}
{x_inicial + largura},{y_atual + sarrafo_offset}

;
_ZOOM
C
{x_inicial},{y_atual + altura - sarrafo_offset}
10
;
_PLINE
{x_inicial},{y_atual + altura - sarrafo_offset}
{x_inicial + largura},{y_atual + altura - sarrafo_offset}

;"""
                    else:  # MLINE
                        # Para MLINE, desenha a linha +7 apenas uma vez, acima do painel de 2cm
                        if i == 1:  # Desenha apenas no primeiro painel após o de 2cm
                            script += f""";
_ZOOM
C
{x_inicial},{y_atual + 7}
10
;
_MLINE
ST
SAR2
S
7
{x_inicial},{y_atual + 7}
{x_inicial + largura},{y_atual + 7}

;"""
                        # A linha superior continua sendo desenhada normalmente
                        script += f""";
_ZOOM
C
{x_inicial},{y_atual + altura}
10
;
_MLINE
ST
SAR2
S
7
{x_inicial},{y_atual + altura}
{x_inicial + largura},{y_atual + altura}

;"""
                    y_atual += altura
                elif tipo_painel in ['a', 'b']:
                    # Sarrafos verticais para painéis A e B (sempre PLINE para HIDDEN)
                    # Usar o layer de linhas hidden para sarrafos verticais dos painéis A e B
                    script += f""";
_LAYER
S
{layer_sarrafos_verticais}

;
_ZOOM
C
{x_esquerdo},{y_atual}
10
;
_PLINE
{x_esquerdo},{y_atual}
{x_esquerdo},{y_atual + altura}

;
_ZOOM
C
{x_direito},{y_atual}
10
;
_PLINE
{x_direito},{y_atual}
{x_direito},{y_atual + altura}

;
;
_LINETYPE
S
CONTINUOUS

;"""
                    y_atual += altura
            else:
                # Com laje na posição atual
                if tipo_painel in ['c', 'd'] and largura < 30:
                    # Sarrafos verticais até a laje apenas para C e D
                    if modo_sarrafos == "Pline":
                        # C e D usando PLINE - usar layer_sarrafos_verticais
                        script += f""";
_LAYER
S
{layer_sarrafos_verticais}

;
_ZOOM
C
{x_esquerdo},{y_atual}
10
;
_PLINE
{x_esquerdo},{y_atual}
{x_esquerdo},{y_atual + altura}

;
_ZOOM
C
{x_direito},{y_atual}
10
;
_PLINE
{x_direito},{y_atual}
{x_direito},{y_atual + altura}

;
;
_LINETYPE
S
CONTINUOUS

;"""
                    else:  # MLINE apenas para painéis C e D
                        # C e D verticais também usam layer_sarrafos_verticais
                        script += f""";
_LAYER
S
{layer_sarrafos_verticais}

;
_ZOOM
C
{x_esquerdo},{y_atual}
10
;
_MLINE
ST
SAR2
S
7
{x_esquerdo},{y_atual}
{x_esquerdo},{y_atual + altura}

;
_MLINE
ST
SAR2
S
7
{x_direito},{y_atual}
{x_direito},{y_atual + altura}

;"""
                    y_atual += altura + altura_laje
                elif tipo_painel in ['c', 'd'] and largura >= 30:
                    # Sarrafos horizontais até a laje
                    if y_atual > (y_inicial - pe_direito):
                        if modo_sarrafos == "Pline":
                            script += f""";
_ZOOM
C
{x_inicial},{y_atual + sarrafo_offset}
10
;
_PLINE
{x_inicial},{y_atual + sarrafo_offset}
{x_inicial + largura},{y_atual + sarrafo_offset}

;"""
                        else:  # MLINE
                            script += f""";
_ZOOM
C
{x_inicial},{y_atual}
10
;
_MLINE
ST
SAR2
S
7
{x_inicial},{y_atual}
{x_inicial + largura},{y_atual}

;"""
                    else:
                        if modo_sarrafos == "Pline":
                            script += f""";
_ZOOM
C
{x_inicial},{y_atual}
10
;
_PLINE
{x_inicial},{y_atual}
{x_inicial + largura},{y_atual}

;"""
                        else:  # MLINE
                            script += f""";
_ZOOM
C
{x_inicial},{y_atual}
10
;
_MLINE
ST
SAR2
S
7
{x_inicial},{y_atual}
{x_inicial + largura},{y_atual}

;"""
                    
                    if modo_sarrafos == "Pline":
                        script += f""";
_ZOOM
C
{x_inicial},{y_atual + altura - 7}
10
;
_PLINE
{x_inicial},{y_atual + altura - 7}
{x_inicial + largura},{y_atual + altura - 7}

;"""
                    else:  # MLINE
                        script += f""";
_ZOOM
C
{x_inicial},{y_atual + altura}
10
;
_MLINE
ST
SAR2
S
7
{x_inicial},{y_atual + altura}
{x_inicial + largura},{y_atual + altura}

;"""
                    y_atual += altura + altura_laje
                elif tipo_painel in ['a', 'b']:
                    # Sarrafos verticais até a laje para painéis A e B
                    # Usar o layer de linhas hidden para sarrafos verticais dos painéis A e B
                    script += f""";
_LAYER
S
{layer_sarrafos_verticais}

;
_ZOOM
C
{x_esquerdo},{y_atual}
10
;
_PLINE
{x_esquerdo},{y_atual}
{x_esquerdo},{y_atual + altura}

;
_ZOOM
C
{x_direito},{y_atual}
10
;
_PLINE
{x_direito},{y_atual}
{x_direito},{y_atual + altura}

;
;
_LINETYPE
S
CONTINUOUS

;"""
                    y_atual += altura + altura_laje
                    
                    # Linha horizontal extra abaixo da laje
                    if i > 0 and i < len(alturas) - 1 and altura_laje > 0:
                        # Verificar se deve desenhar a linha extra abaixo da laje
                        # Não desenhar se comprimento >= 223 e laje está entre painéis
                        if comprimento_pilar < 223:  # Só desenha se comprimento < 223
                            y_linha_extra = y_atual - altura_laje - 7
                            # Linha horizontal usa layer de sarrafos horizontais
                            script += f""";
_LAYER
S
{layer_sarrafos_horizontais}

;
_LINETYPE
S
CONTINUOUS

;
"""
                            if modo_sarrafos == "Pline":
                                script += f""";
_ZOOM
C
{x_inicial},{y_linha_extra}
5
;
_PLINE
{x_inicial},{y_linha_extra}
{x_inicial + largura},{y_linha_extra}

;"""
                            else:  # MLINE
                                script += f"""
_ZOOM
C
{x_inicial},{y_linha_extra + 7}
5
;
_MLINE
ST
SAR
S
7
{x_inicial},{y_linha_extra + 7}
{x_inicial + largura},{y_linha_extra + 7}

;"""

        # Lógica para sarrafos horizontais (apenas para painéis A e B)
        if tipo_painel in ['a', 'b']:
            horizontal_ativo = (tipo_painel == 'a' and self.sarrafo_horizontal_a.get()) or (
                tipo_painel == 'b' and self.sarrafo_horizontal_b.get()
            )

            if horizontal_ativo:
                script += f""";
_LAYER
S
{layer_sarrafos_horizontais}

;
_LINETYPE
S
CONTINUOUS

;"""

                y_atual = y_inicial - pe_direito
                ultimo_painel = None
                for i, altura in enumerate(alturas):
                    if i == 0:
                        y_atual += altura
                        continue

                    altura_laje = 0
                    pos_laje = 0
                    # Usar função auxiliar para obter laje correta
                    laje_altura_total, pos_laje_total = self.obter_laje_correta(tipo_painel)
                    
                    if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                        # Script 2: verificar posição da laje E,F,G,H
                        if pos_laje_total == i + 1:
                            altura_laje = laje_altura_total
                    else:
                        # Script 1: verificar posição da laje A,B,C,D
                        if tipo_painel == 'a':
                            pos_laje = self.pos_laje_a.get()
                            if pos_laje == i + 1:
                                altura_laje = laje_altura_total
                        elif tipo_painel == 'b':
                            pos_laje = self.pos_laje_b.get()
                            if pos_laje == i + 1:
                                altura_laje = laje_altura_total

                    if altura > 0:
                        # Verificar se este painel está abaixo de uma laje entre painéis
                        laje_entre_paineis = pos_laje > 0 and pos_laje < len(alturas)
                        painel_abaixo_laje = i <= pos_laje
                        
                        # Só desenha o sarrafo horizontal se:
                        # - Não há laje entre painéis, ou
                        # - O painel não está abaixo da laje, ou
                        # - O comprimento é < 223
                        if not laje_entre_paineis or not painel_abaixo_laje or comprimento_pilar < 223:
                            ultimo_painel = {"y": y_atual, "altura": altura - 7}
                    y_atual += altura + altura_laje

                if ultimo_painel and ultimo_painel["altura"] > 7:
                    x_atual = x_inicial
                    if tipo_painel in ["a", "b"]:
                        try:
                            comp1 = self.converter_para_float(self.campos_ab[f"comp1_{tipo_painel}"].get() or 0)
                            comp2 = self.converter_para_float(self.campos_ab[f"comp2_{tipo_painel}"].get() or 0)
                            comp3 = self.converter_para_float(self.campos_ab[f"comp3_{tipo_painel}"].get() or 0)
                            comprimentos = [c for c in [comp1, comp2, comp3] if c > 0]
                        except ValueError:
                            comprimentos = []
                            self.log_mensagem(
                                f"Erro: Comprimento inválido para painel {tipo_painel.upper()}.",
                                "erro",
                            )

                        # Verificar se o comprimento está fora do intervalo 223-279
                        if comprimento_pilar < 223 or comprimento_pilar > 279:
                            for comprimento in comprimentos:
                                if modo_sarrafos == "Pline":
                                    script += f""";
_ZOOM
C
{x_atual},{ultimo_painel['y'] + ultimo_painel['altura']}
5
;
_PLINE
{x_atual},{ultimo_painel['y'] + ultimo_painel['altura']}
{x_atual + comprimento},{ultimo_painel['y'] + ultimo_painel['altura']}

;"""
                                else:  # MLINE
                                    script += f""";
_ZOOM
C
{x_atual},{ultimo_painel['y'] + ultimo_painel['altura'] + 7}
5
;
_MLINE
ST
SAR2
S
7
{x_atual},{ultimo_painel['y'] + ultimo_painel['altura'] + 7}
{x_atual + comprimento},{ultimo_painel['y'] + ultimo_painel['altura'] + 7}

;"""
                                x_atual += comprimento

                            # Verificar se deve desenhar sarrafos especiais abaixo da laje
                            if comprimento_pilar >= 279:
                                # Verificar se há laje entre painéis
                                pos_laje = 0
                                altura_laje = 0
                                # Usar função auxiliar para obter laje correta
                                laje_altura_total, pos_laje_total = self.obter_laje_correta(tipo_painel)
                                
                                if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                                    # Script 2: usar posição da laje E,F,G,H
                                    pos_laje = pos_laje_total
                                    altura_laje = laje_altura_total
                                else:
                                    # Script 1: usar posição da laje A,B,C,D
                                    if tipo_painel == 'a':
                                        pos_laje = self.pos_laje_a.get()
                                        altura_laje = laje_altura_total
                                    elif tipo_painel == 'b':
                                        pos_laje = self.pos_laje_b.get()
                                        altura_laje = laje_altura_total

                                if pos_laje > 0 and pos_laje < len(alturas):
                                    # Calcular a altura acumulada até a posição da laje
                                    y_laje = y_inicial - pe_direito
                                    for idx in range(pos_laje):
                                        y_laje += alturas[idx]

                                    # Desenhar um sarrafo para cada painel de largura
                                    x_atual = x_inicial
                                    for comprimento in comprimentos:
                                        if modo_sarrafos == "Pline":
                                            script += f""";
_LINETYPE
S
CONTINUOUS

;
_ZOOM
C
{x_atual},{y_laje - 7}
5
;
_PLINE
{x_atual},{y_laje - 7}
{x_atual + comprimento},{y_laje - 7}

;"""
                                        else:  # MLINE
                                            script += f""";
_ZOOM
C
{x_atual},{y_laje}
5
;
_MLINE
ST
SAR2
S
7
{x_atual},{y_laje}
{x_atual + comprimento},{y_laje}

;"""
                                        x_atual += comprimento

                        else:
                            # Desenhar sarrafo especial para comprimentos entre 223 e 279
                            # Encontrar o último painel com altura válida (de H5 até H1)
                            ultimo_painel_valido = None
                            altura_acumulada = 0
                            
                            # Começar do fim (H5) e ir até H1
                            for idx in range(len(alturas)-1, -1, -1):
                                if alturas[idx] > 0:
                                    ultimo_painel_valido = idx
                                    break
                            
                            if ultimo_painel_valido is not None:
                                # Verificar se há laje entre painéis e obter sua altura
                                altura_laje_entre_paineis = 0
                                pos_laje = 0
                                
                                # Usar função auxiliar para obter laje correta
                                laje_altura_total, pos_laje_total = self.obter_laje_correta(tipo_painel)
                                
                                if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                                    # Script 2: usar posição da laje E,F,G,H
                                    pos_laje = pos_laje_total
                                    if pos_laje > 0 and pos_laje <= ultimo_painel_valido:
                                        altura_laje_entre_paineis = laje_altura_total
                                else:
                                    # Script 1: usar posição da laje A,B,C,D
                                    if tipo_painel == 'a':
                                        pos_laje = self.pos_laje_a.get()
                                        if pos_laje > 0 and pos_laje <= ultimo_painel_valido:
                                            altura_laje_entre_paineis = laje_altura_total
                                    elif tipo_painel == 'b':
                                        pos_laje = self.pos_laje_b.get()
                                        if pos_laje > 0 and pos_laje <= ultimo_painel_valido:
                                            altura_laje_entre_paineis = laje_altura_total
                                
                                # Calcular altura acumulada incluindo painéis e laje
                                for idx in range(ultimo_painel_valido + 1):
                                    altura_acumulada += alturas[idx]
                                    # Se a laje está após este painel, adicionar sua altura
                                    if pos_laje == idx + 1:
                                        altura_acumulada += altura_laje_entre_paineis
                                
                                # Calcular posição y para o sarrafo especial
                                y_sarrafo = y_inicial - pe_direito  # Base do pilar
                                y_sarrafo += altura_acumulada  # Adicionar todas as alturas até o painel encontrado
                                
                                # Desenhar sarrafo da largura 1 até largura 2
                                if modo_sarrafos == "Pline":
                                    script += f""";
_LINETYPE
S
CONTINUOUS

;   
_ZOOM
C
{x_inicial},{y_sarrafo - 7}
5
;
_PLINE
{x_inicial},{y_sarrafo - 7}
{x_inicial + comp1 + comp2},{y_sarrafo - 7}

;"""
                                else:  # MLINE
                                    script += f"""
_ZOOM
C
{x_inicial},{y_sarrafo}
5
;
_MLINE
ST
SAR
S
7
{x_inicial},{y_sarrafo}
{x_inicial + comp1 + comp2},{y_sarrafo}

;"""

        # Ao finalizar, retornar para o layer de painéis para não interferir nas cotas
        try:
            layer_paineis = self.config_manager.get_config("layers", "paineis_abcd")
            script += f""";
_LAYER
S
{layer_paineis}

;"""
        except Exception:
            pass

        return script

    def atualizar_join_automatico(self):
        """Atualiza automaticamente os joins baseado nas alturas."""
        try:
            altura_total = self.converter_para_float(self.campos['altura'].get())
            # Usar função auxiliar para obter lajes corretas
            if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                # Script 2: usar lajes G e H
                altura_laje_c, _ = self.obter_laje_correta('c')  # G
                altura_laje_d, _ = self.obter_laje_correta('d')  # H
            else:
                # Script 1: usar lajes C e D normais
                altura_laje_c = self.converter_para_float(self.laje_c_var.get() or 0)
                altura_laje_d = self.converter_para_float(self.laje_d_var.get() or 0)
            if altura_total - altura_laje_c <= 300:
                self.join_sarrafos_c.set(True)
            if altura_total - altura_laje_d <= 300:
                self.join_sarrafos_d.set(True)
        except ValueError:
            pass

    def log_mensagem(self, mensagem, tipo="info"):
        """Adiciona mensagem ao log com formatação"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        texto = f"[{timestamp}] {mensagem}\n"
        self.log_text.insert(tk.END, texto, tipo)
        self.log_text.see(tk.END)
        
        # Também registrar no arquivo de log
        if tipo == "erro":
            logging.error(mensagem)
        elif tipo == "sucesso":
            logging.info(mensagem)
        else:
            logging.info(mensagem)
    
    def limpar_campos(self):
        """Limpa todos os campos da interface"""
        # Limpar campos de informações
        for campo in self.campos.values():
            campo.delete(0, tk.END)
            
        # Limpar campos de largura AB (incluindo a terceira largura)
        for campo in self.campos_ab.values():
            campo.delete(0, tk.END)
            
        # Limpar campos de largura CD
        for campo in self.campos_cd.values():
            campo.delete(0, tk.END)
            
        # Limpar campos de altura
        for campos in self.campos_altura.values():
            for campo in campos:
                campo.delete(0, tk.END)
                
        # Resetar posições das lajes
        self.pos_laje_a.set(0)
        self.pos_laje_b.set(0)
        self.pos_laje_c.set(0)
        self.pos_laje_d.set(0)
        
        # Limpar alturas das lajes
        self.laje_a_var.set("")
        self.laje_b_var.set("")
        self.laje_c_var.set("")
        self.laje_d_var.set("")
        
        # Resetar opções de hatch
        for tipo_painel in ['a', 'b', 'c', 'd']:
            hatch_opcoes = getattr(self, f'hatch_opcoes_{tipo_painel}', [])
            for linha in hatch_opcoes:
                for var in linha:
                    var.set("0")
            
        # Limpar campos de abertura de laje (definir como "0")
        for tipo_painel in ['a', 'b', 'c', 'd']:
            self.abertura_laje[tipo_painel]['esq1'].set("0")
            self.abertura_laje[tipo_painel]['esq2'].set("0")
            self.abertura_laje[tipo_painel]['dir1'].set("0")
            self.abertura_laje[tipo_painel]['dir2'].set("0")
            
        # Desativar checkboxes Topo2 em todas as aberturas de todos os painéis
        for tipo_painel in ['a', 'b', 'c', 'd']:
            for abertura in ['esq1', 'esq2', 'dir1', 'dir2']:
                self.abertura_topo2[tipo_painel][abertura].set(False)
        
        self.log_mensagem("Todos os campos foram limpos", "info")
    
    def teste_campos(self):
        """Método para testar se os campos estão funcionando corretamente"""
        try:
            self.log_mensagem("Testando campos...", "info")
            
            # Listar alguns campos importantes para verificação
            campos_teste = ['nome', 'pavimento', 'comprimento', 'largura']
            for campo in campos_teste:
                if campo in self.campos:
                    valor = self.campos[campo].get()
                    self.log_mensagem(f"{campo}: {valor}", "info")
            
            self.log_mensagem("Teste de campos concluído!", "sucesso")
            
        except Exception as e:
            self.log_mensagem(f"Erro no teste de campos: {str(e)}", "erro")

    def preencher_dados_teste(self):
        """Preenche os campos com dados de teste para facilitar o uso dinâmico"""
        try:
            # Preencher campos básicos
            self.campos['nome'].delete(0, 'end')
            self.campos['nome'].insert(0, "teste")
            
            self.campos['pavimento'].delete(0, 'end')
            self.campos['pavimento'].insert(0, "terreoteste")
            
            self.campos['pavimento_anterior'].delete(0, 'end')
            self.campos['pavimento_anterior'].insert(0, "subteste")
            
            self.campos['nivel_saida'].delete(0, 'end')
            self.campos['nivel_saida'].insert(0, "3")
            
            self.campos['nivel_chegada'].delete(0, 'end')
            self.campos['nivel_chegada'].insert(0, "6")
            
            self.campos['comprimento'].delete(0, 'end')
            self.campos['comprimento'].insert(0, "200")
            
            self.campos['largura'].delete(0, 'end')
            self.campos['largura'].insert(0, "20")
            
            # Preencher lajes
            self.laje_a_var.set("20")
            self.laje_b_var.set("0")
            self.laje_c_var.set("50")
            self.laje_d_var.set("100")
            
            # Preencher aberturas do Painel A (abertura esquerda 1)
            if 'abertura_esq1_pos_a' in self.campos:
                self.campos['abertura_esq1_pos_a'].delete(0, 'end')
                self.campos['abertura_esq1_pos_a'].insert(0, "0")
                
            if 'abertura_esq1_dist_a' in self.campos:
                self.campos['abertura_esq1_dist_a'].delete(0, 'end')
                self.campos['abertura_esq1_dist_a'].insert(0, "0")
                
            if 'abertura_esq1_prof_a' in self.campos:
                self.campos['abertura_esq1_prof_a'].delete(0, 'end')
                self.campos['abertura_esq1_prof_a'].insert(0, "64")
                
            if 'abertura_esq1_larg_a' in self.campos:
                self.campos['abertura_esq1_larg_a'].delete(0, 'end')
                self.campos['abertura_esq1_larg_a'].insert(0, "10")
            
            # Preencher aberturas do Painel B (abertura esquerda 1)
            if 'abertura_esq1_pos_b' in self.campos:
                self.campos['abertura_esq1_pos_b'].delete(0, 'end')
                self.campos['abertura_esq1_pos_b'].insert(0, "0")
                
            if 'abertura_esq1_dist_b' in self.campos:
                self.campos['abertura_esq1_dist_b'].delete(0, 'end')
                self.campos['abertura_esq1_dist_b'].insert(0, "0")
                
            if 'abertura_esq1_prof_b' in self.campos:
                self.campos['abertura_esq1_prof_b'].delete(0, 'end')
                self.campos['abertura_esq1_prof_b'].insert(0, "64")
                
            if 'abertura_esq1_larg_b' in self.campos:
                self.campos['abertura_esq1_larg_b'].delete(0, 'end')
                self.campos['abertura_esq1_larg_b'].insert(0, "10")
            
            # Preencher parafusos - apenas o primeiro campo para testar centralização Y
            for i, entry in enumerate(self.parafuso_entries):
                entry.delete(0, 'end')
                if i == 0:  # Apenas o primeiro parafuso preenchido
                    entry.insert(0, "50")
                else:
                    entry.insert(0, "0")
            
            self.log_mensagem("Dados de teste preenchidos com sucesso!", "sucesso")
            
        except Exception as e:
            self.log_mensagem(f"Erro ao preencher dados de teste: {str(e)}", "erro")
    
    def validar_entrada(self):
        """Valida os campos obrigatórios antes de gerar o script"""
        campos_obrigatorios = {
            'nome': "Nome do Projeto",
            'comprimento': "Comprimento",
            'largura': "Largura",
            'altura': "Altura"
        }
        
        for campo, nome in campos_obrigatorios.items():
            if not self.campos[campo].get().strip():
                messagebox.showerror("Erro", f"O campo {nome} é obrigatório!")
                return False
                
        try:
            # Validar valores numéricos, permitindo vírgula ou ponto
            comprimento = self.converter_para_float(self.campos['comprimento'].get())
            largura = self.converter_para_float(self.campos['largura'].get())
            altura = self.converter_para_float(self.campos['altura'].get())
            
            # CORREÇÃO: Para Script 2 especial (usar_paineis_efgh=True), comprimento e largura podem ser 0
            # porque são calculados a partir dos painéis E,F,G,H, não dos painéis A,B,C,D
            is_script2_especial = hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh
            
            if is_script2_especial:
                # Para Script 2 especial, validar apenas altura (comprimento e largura são calculados dos painéis E,F,G,H)
                if altura <= 0:
                    print(f"[DEBUG GERAR_SCRIPT] ⚠️ Validação Script 2 especial: altura={altura} (comprimento e largura podem ser 0)")
                    messagebox.showerror("Erro", "A altura deve ser maior que zero!")
                    return False
                print(f"[DEBUG GERAR_SCRIPT] ✅ Validação Script 2 especial passou: comprimento={comprimento}, largura={largura}, altura={altura}")
            else:
                # Para Script 1 ou pilar normal, validar todas as dimensões
                if comprimento <= 0 or largura <= 0 or altura <= 0:
                    messagebox.showerror("Erro", "As dimensões devem ser maiores que zero!")
                    return False
                
        except ValueError:
            messagebox.showerror("Erro", "As dimensões devem ser valores numéricos!")
            return False
            
        return True

    def salvar_script(self):
        """Salva o script diretamente no arquivo teste.scr"""
        try:
            if not self.validar_entrada():
                return
                
            print("\n=== DEPURAÇÃO - VALORES DOS CAMPOS ===")
            print("Painel A:")
            for i in range(1, 6):
                altura_var = self.campos.get(f'altura_h{i}_a')
                print(f"Campo altura_h{i}_a: {altura_var}")
                if altura_var:
                    print(f"H{i}: {altura_var.get()}")
            
            print("\nPainel B:")
            for i in range(1, 6):
                altura_var = self.campos.get(f'altura_h{i}_b')
                print(f"Campo altura_h{i}_b: {altura_var}")
                if altura_var:
                    print(f"H{i}: {altura_var.get()}")
            
            print("\nPainel C:")
            for i in range(1, 6):
                altura_var = self.campos.get(f'altura_h{i}_c')
                print(f"Campo altura_h{i}_c: {altura_var}")
                if altura_var:
                    print(f"H{i}: {altura_var.get()}")
            
            print("\nPainel D:")
            for i in range(1, 6):
                altura_var = self.campos.get(f'altura_h{i}_d')
                print(f"Campo altura_h{i}_d: {altura_var}")
                if altura_var:
                    print(f"H{i}: {altura_var.get()}")
            
            print("\n=== DEPURAÇÃO - REFERÊNCIAS DE ABERTURAS ===")
            for tipo in ['a', 'b', 'c', 'd']:
                print(f"\nPainel {tipo.upper()}:")
                for i in range(1, 4):  # Aberturas 1, 2 e 3
                    pos_entry = self.campos.get(f'abertura_{i}_pos_{tipo}')
                    print(f"Campo abertura_{i}_pos_{tipo}: {pos_entry}")
                    if pos_entry:
                        print(f"Abertura {i} - Posição: {pos_entry.get()}")
                        altura_total = self.calcular_altura_paineis_acima_laje(tipo)
                        print(f"Altura total: {altura_total}")
                        try:
                            pos = self.converter_para_float(pos_entry.get())
                            if pos > 0:
                                print(f"Posição final: {altura_total - pos}")
                        except ValueError:
                            pass
                
            # Obter layer dos painéis das configurações
            layer_paineis = self.config_manager.get_config("layers", "paineis_abcd")
            script = f""";
_LAYER
S
{layer_paineis}

;
"""
            script += self.criar_cabecalho()
            script += self.gerar_ped()
            script += self.gerar_paineis()
            
            # Caminho fixo para o arquivo
            # Usar path resolver para obter caminho dinâmico
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from utils.robust_path_resolver import robust_path_resolver
            caminho_arquivo = os.path.join(robust_path_resolver.get_project_root(), "output", "teste_abcd.scr")
            
            # Salvar arquivo (sobrescreve se já existir)
            with open(caminho_arquivo, "w", encoding="utf-16") as f:
                f.write(script)
                
            self.log_mensagem(f"Script salvo com sucesso em teste.scr", "sucesso")
            
        except Exception as e:
            self.log_mensagem(f"Erro ao salvar script: {str(e)}", "erro")
            logging.error(f"Erro ao salvar script: {str(e)}")

    def desenhar_cotas_verticais(self, script, tipo_painel, x_inicial, y_inicial, alturas, laje_altura):
        """Desenha as cotas verticais para um painel"""
        # CORREÇÃO: Usar largura calculada individualmente para todos os painéis
        largura_total = self.calcular_largura_total_painel(tipo_painel, None)
            
        x_linha_cota = x_inicial + largura_total  # Linha de cota toca a parede
        x_texto = x_linha_cota + 50  # Texto 50cm à direita da linha para cotas individuais
        x_texto_total = x_linha_cota + 50  # Texto 50cm à direita da linha para cotas totais
        
        # Obter posição da laje
        pos_laje = getattr(self, f'pos_laje_{tipo_painel}').get()
        
        # Desenhar cotas individuais
        y_atual = y_inicial - self.converter_para_float(self.campos['altura'].get())
        
        # Desenhar cotas para cada altura, exceto altura 2 para painéis A e B
        for i, altura in enumerate(alturas):
            if altura > 0:
                # Verificar se a laje está antes deste painel
                if i == pos_laje and laje_altura > 0:
                    # Ajustar posição do texto para a laje
                    script += f""";
_DIMLINEAR
{x_linha_cota},{y_atual}
{x_linha_cota},{y_atual + laje_altura}
{x_texto},{y_atual + (laje_altura/2)}
;"""
                    y_atual += laje_altura
                
                # Ajustar posição do texto para diferentes alturas
                if tipo_painel in ['a', 'b'] and i <= 1:  # H1 e H2 apenas para painéis A e B
                    x_texto_ajustado = x_linha_cota + 25  # 25cm à direita para H1 e H2
                else:
                    x_texto_ajustado = x_texto  # 50cm à direita para todos os outros
                
                if not (tipo_painel in ['a', 'b'] and i == 1):  # Não desenhar cota para H2 em painéis A e B
                    script += f""";
_DIMLINEAR
{x_linha_cota},{y_atual}
{x_linha_cota},{y_atual + altura}
{x_texto_ajustado},{y_atual + (altura/2)}
;"""
                y_atual += altura
        
        # Desenhar cota da laje se existir e estiver após os painéis
        if laje_altura > 0 and pos_laje >= len(alturas):
            script += f""";
_DIMLINEAR
{x_linha_cota},{y_atual}
{x_linha_cota},{y_atual + laje_altura}
{x_texto},{y_atual + (laje_altura/2)}
;"""
            y_atual += laje_altura
        
        # Desenhar cota total apenas para painéis de altura 1 e 2
        if tipo_painel in ['a', 'b']:
            y_total = y_inicial - self.converter_para_float(self.campos['altura'].get()) + alturas[0] - 2 # Posição inicial é a mesma de H1
            altura_total_paineis = sum(alturas[:2])  # Soma alturas 1 e 2
            
            if altura_total_paineis > 0:
                script += f""";
_DIMLINEAR
{x_linha_cota},{y_total}
{x_linha_cota},{y_total + altura_total_paineis}
{x_texto_total},{y_total + altura_total_paineis/2}
;"""
        
        return script

    def desenhar_cotas_horizontais(self, script, tipo_painel, x_inicial, y_inicial, comprimentos):
        """Desenha as cotas horizontais para um painel"""
        # Garantir que o layer ativo para cotas esteja selecionado
        layer_cotas = self.config_manager.get_config("layers", "cotas")
        script += f""";
_LAYER
S
{layer_cotas}

;"""
        # Obter offset das cotas das configurações
        cota_offset = self.config_manager.get_config("drawing_options", "cota_offset") or 15
        
        # Linha de cota toca a parte inferior do painel
        y_linha_cota = y_inicial - self.converter_para_float(self.campos['altura'].get())
        y_texto = y_linha_cota - cota_offset * 2  # 2x o offset abaixo da linha
        
        x_atual = x_inicial
        total_comprimento = 0  # Para calcular o comprimento total
        
        for i, comprimento in enumerate(comprimentos):
            if comprimento > 0:
                total_comprimento += comprimento
                tem_cota_total = tipo_painel in ['a', 'b']
                ultima_cota = i == len(comprimentos) - 1
                
                if ultima_cota and not tem_cota_total:
                    script += f""";
;
_DIMLINEAR
{x_atual},{y_linha_cota}
{x_atual + comprimento},{y_linha_cota}
{x_atual + (comprimento/2)},{y_texto}
;"""
                else:
                    script += f"""
;
_DIMLINEAR
{x_atual},{y_linha_cota}
{x_atual + comprimento},{y_linha_cota}
{x_atual + (comprimento/2)},{y_texto}
;"""
                x_atual += comprimento
        
        # Adicionar cota total se houver mais de um painel
        if len([c for c in comprimentos if c > 0]) > 1:
            y_texto_total = y_linha_cota - cota_offset * 3  # 3x o offset abaixo da linha para a cota total
            script += f""";
;
_DIMLINEAR
{x_inicial},{y_linha_cota}
{x_inicial + total_comprimento},{y_linha_cota}
{x_inicial + (total_comprimento/2)},{y_texto_total}
;"""
        
        return script

    def desenhar_cotas_sarrafos(self, script, tipo_painel, x_inicial, y_inicial, largura):
        """Desenha as cotas horizontais dos sarrafos para painéis A e B"""
        if tipo_painel not in ['a', 'b']:
            return script
        
        # Garantir que o layer ativo para cotas esteja selecionado
        layer_cotas = self.config_manager.get_config("layers", "cotas")
        script += f""";
_LAYER
S
{layer_cotas}

;"""
            
        # Obter offsets das configurações
        cota_offset = self.config_manager.get_config("drawing_options", "cota_offset") or 15
        sarrafo_offset = self.config_manager.get_config("drawing_options", "sarrafo_offset") or 7
        texto_offset = self.config_manager.get_config("drawing_options", "texto_offset") or 20
        
        # Posição vertical das cotas (na base do painel)
        y_linha_cota = y_inicial - self.converter_para_float(self.campos['altura'].get())  # Sem deslocamento vertical
        y_texto = y_linha_cota - cota_offset  # 1x o offset abaixo da linha
        
        # Posições dos sarrafos usando offset das configurações
        x_sarrafo_esq = x_inicial + sarrafo_offset
        x_sarrafo_dir = x_inicial + largura - sarrafo_offset
        
        # Cota do sarrafo esquerdo até a parede esquerda
        x_texto_esq = x_inicial - texto_offset  # Usar offset de texto das configurações
        script += f""";
;
_DIMLINEAR
{x_inicial},{y_linha_cota}
{x_sarrafo_esq},{y_linha_cota}
{x_texto_esq},{y_texto}
;"""
        
        # Cota do sarrafo direito até a parede direita
        x_texto_dir = x_inicial + largura + texto_offset  # Usar offset de texto das configurações
        script += f""";
;
_DIMLINEAR
{x_sarrafo_dir},{y_linha_cota}
{x_inicial + largura},{y_linha_cota}
{x_texto_dir},{y_texto}
;"""
        
        return script

    def inserir_blocos_split(self, script, tipo_painel, x_inicial, y_inicial, largura):
        """Insere os blocos SLIPTEE e SLIPTDD nas pontas inferiores dos painéis A e B"""
        if tipo_painel not in ['a', 'b']:
            return script
            
        # Calcular posição y (parte inferior do painel)
        y_base = y_inicial - self.converter_para_float(self.campos['altura'].get()) + 3  # Adicionado +3 para subir 3cm
        
        # Obter nomes dos blocos das configurações
        split_ee = self.config_manager.get_config("blocks", "split_ee")
        split_dd = self.config_manager.get_config("blocks", "split_dd")
        
        # Inserir SLIPTEE na ponta esquerda (3cm à direita)
        script += f""";
-INSERT
{split_ee}
{x_inicial},{y_base}
1
0
;"""
        
        # Inserir SLIPTDD na ponta direita (3cm à direita)
        script += f""";
-INSERT
{split_dd}
{x_inicial + largura},{y_base}
1
0
;"""
        
        return script

    def desenhar_texto_painel(self, script, tipo_painel, x_inicial, y_inicial):
        """Desenha o texto vertical para identificação do painel e textos de sarrafos"""
        # Obter layer de nomenclatura das configurações
        layer_nomenclatura = self.config_manager.get_config("layers", "nomenclatura") or "0"
        
        # Mudar para layer de nomenclatura
        script += f""";
_LAYER
S
{layer_nomenclatura}

;"""
        # Obter o nome do pilar da interface
        nome_pilar = self.campos['nome'].get().strip()
        
        # Posicionar texto do nome do painel
        x_texto = x_inicial - 20  # 20cm à esquerda
        
        # Posicionar na parte inferior do painel
        y_texto = y_inicial - self.converter_para_float(self.campos['altura'].get())
        
        # Verificar se é script especial 2 (usar_paineis_efgh)
        is_script2_especial = hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh
        
        # Gerar o texto com o sufixo do painel
        if is_script2_especial:
            # Script 2 especial: mapear A→E, B→F, C→G, D→H
            mapeamento_efgh = {'a': 'E', 'b': 'F', 'c': 'G', 'd': 'H'}
            sufixo = mapeamento_efgh.get(tipo_painel.lower(), tipo_painel.upper())
            texto = f"{nome_pilar}.{sufixo}"
        else:
            # Script 1 normal: usar A, B, C, D
            texto = f"{nome_pilar}.{tipo_painel.upper()}"
        
        # Adicionar o comando de texto vertical (rotacionado 90 graus)
        script += f""";
-STYLE
Romans

12





;
_TEXT
J
L
{x_texto + 5},{y_texto + 5}
90
{texto}
;"""

        # Verificar condições para desenhar textos de sarrafos
        desenhar_sarrafos = False
        # CORREÇÃO: Usar largura calculada individualmente para todos os painéis
        try:
            largura_total = self.calcular_largura_total_painel(tipo_painel, None)
            if tipo_painel.lower() in ['a', 'b']:
                desenhar_sarrafos = largura_total > 244
            else:  # painéis C, D, E, F, G, H
                desenhar_sarrafos = largura_total >= 30
        except ValueError:
            desenhar_sarrafos = False

        if desenhar_sarrafos:
            # Obter alturas do painel
            alturas = []
            for campo in self.campos_altura[tipo_painel.lower()]:
                try:
                    altura = self.converter_para_float(campo.get() or 0)
                    alturas.append(altura)
                except ValueError:
                    alturas.append(0)

            # Calcular posição Y inicial
            y_atual = y_inicial - self.converter_para_float(self.campos['altura'].get())

            # CORREÇÃO: Usar largura calculada individualmente (já calculada acima)
            # largura_total já foi calculada na verificação anterior

            # Posição X para os textos de sarrafos (35cm à direita do painel - 30+5)
            x_sarrafos = x_inicial + largura_total + 45

            # Desenhar textos para cada altura
            for i, altura in enumerate(alturas):
                if i == 0 or altura <= 0:  # Pular altura 1 (2cm) e alturas zeradas
                    y_atual += altura
                    continue

                # Calcular quantidade de sarrafos
                qtd_sarrafos = math.ceil((altura + 15) / 30)  # Removido o +1 do final

                # Posicionar texto no centro da altura do painel (60cm mais abaixo)
                y_texto_sarrafos = y_atual + (altura / 2) - 40
                
                # Obter layer de nomenclatura das configurações
                layer_nomenclatura = self.config_manager.get_config("layers", "nomenclatura")
            
                # Adicionar texto de quantidade de sarrafos (rotacionado 90 graus)
                script += f""";
_LAYER
S
{layer_nomenclatura}

;
_TEXT
{x_sarrafos + 20},{y_texto_sarrafos}
90
{qtd_sarrafos} sarr.
;"""

                y_atual += altura

        return script

    def inserir_bloco_moldura(self, script):
        """Insere o bloco MULDURA na ponta esquerda do pé direito inferior"""
        # Calcular posição y (parte inferior do pé direito)
        y_base = self.y_inicial - self.converter_para_float(self.campos['altura'].get()) + 38
        
        # Obter nome do bloco das configurações
        bloco_moldura = self.config_manager.get_config("blocks", "moldura")
        
        # Inserir MULDURA na ponta esquerda do pé direito
        script += f""";
-INSERT
{bloco_moldura}
{self.x_inicial},{y_base}
1
0
;"""
        
        return script

    def desenhar_texto_informativo(self, script, x_inicial, y_inicial):
        """Desenha o texto informativo 350cm acima dos painéis e 25cm à direita"""
        try:
            # Obter layer de nomenclatura das configurações
            layer_nomenclatura = self.config_manager.get_config("layers", "nomenclatura")
            
            # Obter tipo de bloco moldura
            bloco_moldura = self.config_manager.get_config("blocks", "moldura")
            
            # Mudar para layer "nomenclatura"
            script += f""";
_LAYER
S
{layer_nomenclatura}

;"""
            # Obter os valores dos campos
            pavimento = self.campos['pavimento'].get().strip()
            pavimento_anterior = self.campos['pavimento_anterior'].get().strip()
            n_saida = self.campos['nivel_saida'].get().strip()
            nome_pilar = self.campos['nome'].get().strip()
            comprimento = self.campos['comprimento'].get().strip()
            largura = self.campos['largura'].get().strip()
            altura = self.converter_para_float(self.campos['altura'].get())
            
            # Calcular PD corretamente (soma alturas + laje)
            try:
                alturas_painel_a = []
                if 'a' in self.campos_altura:
                    for entry in self.campos_altura['a']:
                        try:
                            valor = self.converter_para_float(entry.get() or 0)
                            alturas_painel_a.append(valor)
                            self.log_mensagem(f"Altura Painel A: {valor} cm", "info")
                        except (ValueError, TypeError):
                            continue
                laje_a = 0.0
                
                # No Script 2 (usar_paineis_efgh=True), usar laje E em vez de A para o cálculo do PD
                if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                    # Script 2: usar laje E para o cálculo do PD
                    if hasattr(self, 'master') and self.master:
                        try:
                            # Tentar múltiplas formas de acessar a laje E
                            if hasattr(self.master, 'laje_E'):
                                laje_var = getattr(self.master, 'laje_E')
                                if hasattr(laje_var, 'get'):
                                    laje_a = self.converter_para_float(laje_var.get() or 0)
                            elif hasattr(self.master, 'laje_e'):
                                laje_var = getattr(self.master, 'laje_e')
                                if hasattr(laje_var, 'get'):
                                    laje_a = self.converter_para_float(laje_var.get() or 0)
                            elif hasattr(self.master, 'campos') and 'laje_E' in self.master.campos:
                                laje_a = self.converter_para_float(self.master.campos['laje_E'].get() or 0)
                            elif hasattr(self.master, 'campos') and 'laje_e' in self.master.campos:
                                laje_a = self.converter_para_float(self.master.campos['laje_e'].get() or 0)
                            
                            self.log_mensagem(f"[SCRIPT 2] Laje E para PD: {laje_a} cm", "info")
                        except Exception as e:
                            self.log_mensagem(f"[SCRIPT 2] Erro ao acessar laje E para PD: {e}", "erro")
                            laje_a = 0.0
                else:
                    # Script 1: usar laje A normal
                    if self.laje_a_var.get():
                        laje_a = self.converter_para_float(self.laje_a_var.get())
                        self.log_mensagem(f"[SCRIPT 1] Laje A para PD: {laje_a} cm", "info")
                if not alturas_painel_a and laje_a == 0:
                    self.log_mensagem("Nenhum dado válido para cálculo do PD", "aviso")
                    pd_texto = "0,00"
                else:
                    pd_total_cm = sum(alturas_painel_a) + laje_a
                    pd_metros = pd_total_cm / 100
                    pd_texto = f"{pd_metros:.2f}".replace('.', ',')
                    self.log_mensagem(f"PD calculado: {pd_total_cm}cm ({pd_texto}m)", "sucesso")
            except Exception as e:
                self.log_mensagem(f"Erro cálculo PD: {str(e)}", "erro")
                pd_texto = "ERRO"
                pd_total_cm = 0
            # Calcular nível de chegada
            try:
                if pd_texto not in ["ERRO", "0,00"]:
                    pd_float = self.converter_para_float(pd_texto)
                    # Aceitar n_saida mesmo quando for "0" (verificar se não está vazio)
                    if n_saida and n_saida.strip():
                        n_saida_float = self.converter_para_float(n_saida)
                    else:
                        n_saida_float = 0.0
                    n_chegada = n_saida_float + pd_float
                    n_chegada_texto = f"{n_chegada:.2f}".replace('.', ',')
                else:
                    n_chegada_texto = "INDEFINIDO"
            except Exception as e:
                n_chegada_texto = "ERRO"
            
            # Obter nível diferencial e calcular nível de chegada ajustado
            nivel_diferencial = self._obter_nivel_diferencial()
            # Se for None, considerar como 0
            if nivel_diferencial is None:
                nivel_diferencial = 0.0
            n_chegada_ajustado_texto = n_chegada_texto
            try:
                # Se temos nível diferencial e nível de chegada válido, somar (nível diferencial / 100)
                if nivel_diferencial != 0:
                    if n_chegada_texto and n_chegada_texto != "INDEFINIDO" and n_chegada_texto != "ERRO":
                        try:
                            n_chegada_float = self.converter_para_float(n_chegada_texto.replace(',', '.'))
                            n_chegada_ajustado = n_chegada_float + (nivel_diferencial / 100)
                            n_chegada_ajustado_texto = f"{n_chegada_ajustado:.2f}".replace('.', ',')
                        except:
                            n_chegada_ajustado_texto = n_chegada_texto
            except Exception as e:
                # Se houver erro, usar o valor original
                n_chegada_ajustado_texto = n_chegada_texto
            
            # Calcular posição do texto informativo
            try:
                altura_total = self.converter_para_float(self.campos['altura'].get()) if self.campos['altura'].get() else 0
                # Ajustar posições e tamanho do texto baseado no tipo de moldura
                if str(bloco_moldura).lower().strip() == "muldura2":
                    x_texto = x_inicial + 30 + 420  # Adiciona 420 para muldura2
                    y_texto = (y_inicial - altura_total) + 680 + 120  # Adiciona 120 para muldura2
                    tamanho_texto = 10  # Tamanho base para muldura2
                    tamanho_texto_grande = 25  # Tamanho maior para nome e dimensões
                    
                    # Preparar textos para muldura2
                    linha1 = f"{nome_pilar}"  # Nome do pilar
                    linha2 = f"({comprimento} x {largura})"  # Dimensões
                    # Formatar nível de saída (aceita 0 como valor válido)
                    if n_saida and n_saida.strip():
                        try:
                            n_saida_float = self.converter_para_float(n_saida)
                            n_saida_formatado = f"{n_saida_float:.2f}".replace('.', ',')
                        except:
                            n_saida_formatado = n_saida
                    else:
                        n_saida_formatado = "N/D"
                    linha3 = f"NÍVEL DE SAÍDA: {n_saida_formatado}"
                    linha4 = f"NÍVEL DE CHEGADA: {n_chegada_ajustado_texto}"
                    
                    # Adicionar textos com tamanhos diferentes
                    script += f""";
-STYLE
Romans

17





;
_TEXT
J
C
{x_texto + 50},{y_texto + 60}
0
{linha1}
;
_TEXT
J
C
{x_texto + 50},{y_texto + 30}
0
{linha2}
;
;
-STYLE
Arial

7.5




;
_TEXT
J
L
{x_texto},{y_texto + 10}
0
{linha3}
;
_TEXT
J
L
{x_texto},{y_texto - 5}
0
{linha4}
;"""

                    # Adicionar textos para os PEDs (10cm acima e 10cm à direita)
                    x_cota = self.x_inicial + 70  # Mesma posição usada no gerar_ped
                    script += f"""
_LAYER
S
Detalhes

;
;
-STYLE
Arial

12




;
_TEXT
J
L
{x_cota - 50},{self.y_inicial + 20}
0
{n_chegada_texto}
;
_TEXT
J
L
{x_cota - 50},{self.y_inicial - altura + 20}
0
{f"{self.converter_para_float(n_saida):.2f}".replace('.', ',') if (n_saida and n_saida.strip()) else "N/D"}
;
"""
                    # Adicionar cota do nível diferencial (mesma posição X do nível de chegada, Y = nível de chegada + nível diferencial)
                    try:
                        # Tentar obter nível diferencial usando a função auxiliar
                        nivel_diferencial = self._obter_nivel_diferencial()
                        
                        # Se for None, considerar como 0
                        if nivel_diferencial is None:
                            nivel_diferencial = 0.0
                        
                        # Se ainda for None após tentar calcular, considerar como 0
                        if nivel_diferencial is None:
                            # Calcular como diferença entre chegada e saída
                            # Aceitar n_saida mesmo quando for "0" (verificar se não está vazio)
                            if n_saida and n_saida.strip() and n_chegada_texto and n_chegada_texto != "INDEFINIDO" and n_chegada_texto != "ERRO":
                                try:
                                    n_saida_float = self.converter_para_float(n_saida)
                                    n_chegada_float = self.converter_para_float(n_chegada_texto.replace(',', '.'))
                                    nivel_diferencial = n_chegada_float - n_saida_float
                                except:
                                    nivel_diferencial = None
                        
                        # Se temos nível diferencial válido e diferente de zero, adicionar a cota
                        # Verificar se é diferente de zero (incluindo 0.0, "0", etc)
                        nivel_diferencial_valido = False
                        if nivel_diferencial is not None:
                            try:
                                nivel_dif_float = float(nivel_diferencial)
                                # Considerar válido apenas se for diferente de zero (com tolerância para erros de ponto flutuante)
                                if abs(nivel_dif_float) > 0.01:
                                    nivel_diferencial_valido = True
                            except (ValueError, TypeError):
                                pass
                        
                        if nivel_diferencial_valido:
                            # Calcular posição Y: self.y_inicial - altura + nivel_diferencial (já está em unidades do AutoCAD)
                            y_diferencial = self.y_inicial + nivel_diferencial
                            
                            # Calcular valor exibido: nível de chegada + (nível diferencial / 100)
                            if n_chegada_texto and n_chegada_texto != "INDEFINIDO" and n_chegada_texto != "ERRO":
                                try:
                                    n_chegada_float = self.converter_para_float(n_chegada_texto.replace(',', '.'))
                                    valor_diferencial = n_chegada_float + (nivel_diferencial / 100)
                                    nivel_diferencial_texto = f"{valor_diferencial:.2f}".replace('.', ',')
                                except:
                                    nivel_diferencial_texto = f"{nivel_diferencial:.2f}".replace('.', ',')
                            else:
                                nivel_diferencial_texto = f"{nivel_diferencial:.2f}".replace('.', ',')
                            
                            # Coordenadas para texto e bloco PED (mesmas coordenadas)
                            x_ped_diferencial = x_cota - 50
                            y_ped_diferencial = y_diferencial + 20
                            
                            # Inserir bloco PED na mesma posição do texto
                            script += f""";
-INSERT
PED
{x_ped_diferencial + 20},{y_ped_diferencial}
1
0
;
_TEXT
J
L
{x_ped_diferencial},{y_ped_diferencial}
0
{nivel_diferencial_texto}
;"""
                    except Exception as e:
                        # Se houver erro, apenas continuar sem adicionar a cota do diferencial
                        pass
                    
                    script += """;
_LAYER
S
Nomenclatura

;"""

                else:
                    # Configuração original para muldura
                    x_texto = x_inicial + 30
                    y_texto = (y_inicial - altura_total) + 680
                    tamanho_texto = 19
                    
                    # Preparar textos originais
                    linha1 = f"{pavimento} - PD: {pd_texto}" if pavimento else f"PD: {pd_texto}"
                    # Formatar nível de saída (aceita 0 como valor válido)
                    if n_saida and n_saida.strip():
                        try:
                            n_saida_float = self.converter_para_float(n_saida)
                            n_saida_formatado = f"{n_saida_float:.2f}".replace('.', ',')
                        except:
                            n_saida_formatado = n_saida if n_saida else "N/D"
                    else:
                        n_saida_formatado = "N/D"
                    linha2 = f"NÍVEL DE SAÍDA: {n_saida_formatado}"
                    linha3 = f"NÍVEL DE CHEGADA: {n_chegada_ajustado_texto}"
                    
                    # Adicionar textos originais
                    script += f""";
-STYLE
Romans

15





;
_TEXT
J
L
{x_texto + 1},{y_texto - 20}
0
{linha1}
;
_TEXT
J
L
{x_texto + 1},{y_texto - 45}
0
{linha2}
;
_TEXT
J
L
{x_texto + 1},{y_texto - 70}
0
{linha3}
;"""
                    
            except Exception as e:
                self.log_mensagem(f"Erro no posicionamento do texto: {str(e)}", "erro")
                return script

            return script
        except Exception as e:
            self.log_mensagem(f"Erro ao desenhar texto informativo: {str(e)}", "erro")
            return script

    def atualizar_e_sincronizar_campo(self, campo, valor, callback=None):
        """Atualiza o valor do campo na interface."""
        try:
            campo.delete(0, tk.END)
            campo.insert(0, valor)
            if callback:
                callback(True)  # Indica sucesso
        except Exception as e:
            if callback:
                callback(False)  # Indica erro
            print(f"Erro ao atualizar campo: {e}")

    def sincronizar_nome(self, event):
        """Sincroniza o campo 'nome' com a OutraInterface."""
        valor = self.campos['nome'].get()  # Obtém o valor do campo 'nome'
        self.log_text.insert(tk.END, f"Campo 'nome' alterado para: {valor}\n", "info")
        self.master.sincronizacao_sucesso.set(False)  # Resetar a variável
        # Agenda a atualização do campo correspondente na OutraInterface
        self.master.interface.root.after_idle(
            lambda: self.master.interface.atualizar_e_sincronizar_campo(
                self.master.interface.nome_pilar_entry,  # Campo a ser atualizado
                valor,
                lambda sucesso: self.master.registrar_sincronizacao(sucesso)  # Callback
            )
        )
        self.master.interface.root.after_idle(self.verificar_sincronizacao_nome)

    def verificar_sincronizacao_nome(self):
        """Verifica se a sincronização do campo 'nome' foi bem-sucedida."""
        if self.master.sincronizacao_sucesso.get():
            self.log_text.insert(tk.END, "  > Sincronização com 'nome_pilar_entry' bem-sucedida.\n", "sucesso")
        else:
            self.log_text.insert(tk.END, "  > Erro ao sincronizar 'nome_pilar_entry'.\n", "erro")

    def sincronizar_comprimento(self, event):
        """Sincroniza o campo 'comprimento' com a OutraInterface."""
        valor = self.campos['comprimento'].get()  # Obtém o valor do campo 'comprimento'
        self.log_text.insert(tk.END, f"Campo 'comprimento' alterado para: {valor}\n", "info")
        self.master.sincronizacao_sucesso.set(False)  # Resetar a variável
        # Agenda a atualização do campo correspondente na OutraInterface
        self.master.interface.root.after_idle(
            lambda: self.master.interface.atualizar_e_sincronizar_campo(
                self.master.interface.comprimento_pilar_entry,  # Campo a ser atualizado
                valor,
                lambda sucesso: self.master.registrar_sincronizacao(sucesso)  # Callback
            )
        )
        self.master.interface.root.after_idle(self.verificar_sincronizacao_comprimento)

    def verificar_sincronizacao_comprimento(self):
        """Verifica se a sincronização do campo 'comprimento' foi bem-sucedida."""
        if self.master.sincronizacao_sucesso.get():
            self.log_text.insert(tk.END, "  > Sincronização com 'comprimento_pilar_entry' bem-sucedida.\n", "sucesso")
        else:
            self.log_text.insert(tk.END, "  > Erro ao sincronizar 'comprimento_pilar_entry'.\n", "erro")

    def sincronizar_largura(self, event):
        """Sincroniza o campo 'largura' com a OutraInterface."""
        valor = self.campos['largura'].get()  # Obtém o valor do campo 'largura'
        self.log_text.insert(tk.END, f"Campo 'largura' alterado para: {valor}\n", "info")
        self.master.sincronizacao_sucesso.set(False)  # Resetar a variável
        # Agenda a atualização do campo correspondente na OutraInterface
        self.master.interface.root.after_idle(
            lambda: self.master.interface.atualizar_e_sincronizar_campo(
                self.master.interface.largura_pilar_entry,  # Campo a ser atualizado
                valor,
                lambda sucesso: self.master.registrar_sincronizacao(sucesso)  # Callback
            )
        )
        self.master.interface.root.after_idle(self.verificar_sincronizacao_largura)

    def verificar_sincronizacao_largura(self):
        """Verifica se a sincronização do campo 'largura' foi bem-sucedida."""
        if self.master.sincronizacao_sucesso.get():
            self.log_text.insert(tk.END, "  > Sincronização com 'largura_pilar_entry' bem-sucedida.\n", "sucesso")
        else:
            self.log_text.insert(tk.END, "  > Erro ao sincronizar 'largura_pilar_entry'.\n", "erro")

    def atualizar_altura(self, event=None):
        """Calcula a altura com base nos níveis de saída e chegada."""
        try:
            nivel_saida = self.converter_para_float(self.campos['nivel_saida'].get())
            nivel_chegada = self.converter_para_float(self.campos['nivel_chegada'].get())
            
            # Formatar os campos de nível ao sair
            self.campos['nivel_saida'].delete(0, tk.END)
            self.campos['nivel_saida'].insert(0, self.formatar_numero(nivel_saida))
            
            self.campos['nivel_chegada'].delete(0, tk.END)
            self.campos['nivel_chegada'].insert(0, self.formatar_numero(nivel_chegada))
            
            # Calcular altura em centímetros
            altura = (nivel_chegada - nivel_saida) * 100
            
            # Atualizar campo de altura
            self.campos['altura'].delete(0, tk.END)
            self.campos['altura'].insert(0, self.formatar_numero(altura))
            
            self.log_mensagem(f"Altura atualizada: {self.formatar_numero(altura)}", "info")
        except Exception as e:
            self.log_mensagem(f"Erro ao calcular altura: {str(e)}", "erro")

    def atualizar_campo_parafuso(self, index, valor, callback=None):
        """Atualiza o valor do campo de parafuso na interface."""
        try:
            self.parafuso_entries[index].delete(0, tk.END)
            self.parafuso_entries[index].insert(0, valor)
            if callback:
                callback(True)  # Indica sucesso
        except Exception as e:
            if callback:
                callback(False)  # Indica erro
            self.log_mensagem(f"Erro ao atualizar campo parafuso P{index+1}-P{index+2}: {e}", "erro")

    def inserir_parafusos_centro_cd(self, script, tipo_painel, x_inicial, y_inicial, largura, alturas, laje_altura):
        """Insere parafusos no centro dos painéis C e D quando largura >= 40cm"""
        
        # Verificar se é painel C ou D
        if tipo_painel not in ['c', 'd']:
            return script
        
        # Verificar se é script especial 2 (usar_paineis_efgh)
        # No script especial 2: C→G, D→H (não devem ter furações)
        is_script2_especial = hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh
        
        # Verificar se é pilar especial script 1
        is_pilar_especial_script1 = (hasattr(self.master, 'ativar_pilar_especial') and 
                                     hasattr(self.master.ativar_pilar_especial, 'get') and 
                                     self.master.ativar_pilar_especial.get() and
                                     not is_script2_especial)
        
        # Para pilares especiais (script 1 ou script 2), não desenhar furações nos painéis C e D
        # Script 1 especial: C e D não têm furações
        # Script 2 especial: C→G e D→H não têm furações
        if is_pilar_especial_script1 or is_script2_especial:
            self.log_mensagem(f"[PILAR_ESPECIAL] Não desenhando furações no painel {tipo_painel.upper()} (especial)", "info")
            return script
            
        # Verificar se a largura é >= 40cm
        if largura < 40:
            return script
        
        # Obter configurações de medidas Y dos parafusos do grupo C-D-E-F-G-H
        grupo = "cdefgh"
        try:
            # Tentar obter do grupo cdefgh primeiro
            medida_fundo_primeiro_val = self.config_manager.get_config("parafusos", grupo, "medida_fundo_primeiro_" + grupo)
            medida_fundo_primeiro = self.converter_para_float(medida_fundo_primeiro_val) if medida_fundo_primeiro_val is not None else None
            if medida_fundo_primeiro is None:
                # Fallback para estrutura antiga ou padrão
                medida_fundo_primeiro_val_old = self.config_manager.get_config("parafusos", "medida_fundo_primeiro")
                medida_fundo_primeiro = self.converter_para_float(medida_fundo_primeiro_val_old) if medida_fundo_primeiro_val_old is not None else 30
                print(f"[DEBUG PARAFUSOS CD] ⚠️ Usando fallback hardcoded 30 para medida_fundo_primeiro (valor não encontrado no config)")
            else:
                print(f"[DEBUG PARAFUSOS CD] ✅ Usando valor do template: {medida_fundo_primeiro} (obtido de parafusos.{grupo}.medida_fundo_primeiro_{grupo})")
            
            medida_1_2_val = self.config_manager.get_config("parafusos", grupo, "medida_1_2_" + grupo)
            medida_1_2 = self.converter_para_float(medida_1_2_val) if medida_1_2_val is not None else None
            if medida_1_2 is None:
                medida_1_2_val_old = self.config_manager.get_config("parafusos", "medida_1_2")
                medida_1_2 = self.converter_para_float(medida_1_2_val_old) if medida_1_2_val_old is not None else 50
            
            medida_2_3_val = self.config_manager.get_config("parafusos", grupo, "medida_2_3_" + grupo)
            medida_2_3 = self.converter_para_float(medida_2_3_val) if medida_2_3_val is not None else None
            if medida_2_3 is None:
                medida_2_3_val_old = self.config_manager.get_config("parafusos", "medida_2_3")
                medida_2_3 = self.converter_para_float(medida_2_3_val_old) if medida_2_3_val_old is not None else 55
            
            medida_3_4_val = self.config_manager.get_config("parafusos", grupo, "medida_3_4_" + grupo)
            medida_3_4 = self.converter_para_float(medida_3_4_val) if medida_3_4_val is not None else None
            if medida_3_4 is None:
                medida_3_4_val_old = self.config_manager.get_config("parafusos", "medida_3_4")
                medida_3_4 = self.converter_para_float(medida_3_4_val_old) if medida_3_4_val_old is not None else 55
            
            medida_4_5_val = self.config_manager.get_config("parafusos", grupo, "medida_4_5_" + grupo)
            medida_4_5 = self.converter_para_float(medida_4_5_val) if medida_4_5_val is not None else None
            if medida_4_5 is None:
                medida_4_5_val_old = self.config_manager.get_config("parafusos", "medida_4_5")
                medida_4_5 = self.converter_para_float(medida_4_5_val_old) if medida_4_5_val_old is not None else 55
            
            medida_5_6_val = self.config_manager.get_config("parafusos", grupo, "medida_5_6_" + grupo)
            medida_5_6 = self.converter_para_float(medida_5_6_val) if medida_5_6_val is not None else 55
            
            medida_6_7_val = self.config_manager.get_config("parafusos", grupo, "medida_6_7_" + grupo)
            medida_6_7 = self.converter_para_float(medida_6_7_val) if medida_6_7_val is not None else 55
            
            medida_7_8_val = self.config_manager.get_config("parafusos", grupo, "medida_7_8_" + grupo)
            medida_7_8 = self.converter_para_float(medida_7_8_val) if medida_7_8_val is not None else 55
            
            medida_8_9_val = self.config_manager.get_config("parafusos", grupo, "medida_8_9_" + grupo)
            medida_8_9 = self.converter_para_float(medida_8_9_val) if medida_8_9_val is not None else 55
            
            medida_9_10_val = self.config_manager.get_config("parafusos", grupo, "medida_9_10_" + grupo)
            medida_9_10 = self.converter_para_float(medida_9_10_val) if medida_9_10_val is not None else 55
            
            # Log de debug para verificar valores obtidos
            self.log_mensagem(f"[DEBUG CD] Configurações obtidas para grupo {grupo}: medida_fundo_primeiro={medida_fundo_primeiro}, medida_1_2={medida_1_2}", "info")
        except (KeyError, TypeError, AttributeError) as e:
            # Fallback para valores padrão se houver erro ao acessar configurações
            self.log_mensagem(f"[DEBUG CD] Erro ao obter configurações: {e}, usando valores padrão", "aviso")
            medida_fundo_primeiro = 30
            medida_1_2 = 50
            medida_2_3 = 55
            medida_3_4 = 55
            medida_4_5 = 55
            medida_5_6 = 55
            medida_6_7 = 55
            medida_7_8 = 55
            medida_8_9 = 55
            medida_9_10 = 55
        
        # Configurações (mantidas para compatibilidade)
        ESPACO_BASE = medida_fundo_primeiro  # Medida do fundo até primeiro parafuso
        ESPACAMENTO_VERTICAL = medida_1_2  # Medida do primeiro ao segundo (usado para cálculo de fileiras)
        
        # Obter offset das cotas das configurações
        OFFSET_COTA = self.config_manager.get_config("drawing_options", "cota_offset") or 15
        
        # Obter nome do bloco de furação das configurações
        bloco_furacao = self.config_manager.get_config("blocks", "furacao")
        
        # Verificar se o bloco de furação está configurado
        if not bloco_furacao:
            self.log_mensagem("Aviso: Bloco de furação não configurado. Não serão inseridos blocos de furação.", "aviso")
            return script
        
        # Obter configurações de cotas de furação
        cotas_vertical = self.config_manager.get_config("drawing_options", "cotas_furacao_vertical")
        cotas_horizontal = self.config_manager.get_config("drawing_options", "cotas_furacao_horizontal")
        
        # Calcular posição central do painel
        x_centro = x_inicial + (largura / 2)
        
        y_base = y_inicial - self.converter_para_float(self.campos['altura'].get()) + ESPACO_BASE
        altura_total = self.converter_para_float(self.campos['altura'].get() or 0)
        
        # Obter posição da laje
        pos_laje = getattr(self, f'pos_laje_{tipo_painel}').get()
        
        # Calcular altura disponível para parafusos
        altura_disponivel = altura_total - 55  # Subtrai 45cm inicial
        
        # Se a laje está entre painéis, considerar apenas os painéis abaixo da laje
        if pos_laje > 0 and pos_laje < len(alturas):
            altura_disponivel = 0
            # Somar apenas as alturas dos painéis abaixo da laje
            for i in range(pos_laje):
                altura_disponivel += alturas[i]
            altura_disponivel -= 45  # Subtrai 45cm inicial
        
        # Descontar a altura da laje se ela existir
        if laje_altura > 0:
            altura_disponivel -= laje_altura
            self.log_mensagem(f"Debug furação CD - Descontando altura da laje: {laje_altura}cm", "info")
        
        # Garantir que a altura disponível não seja negativa
        if altura_disponivel < 0:
            altura_disponivel = 0
            self.log_mensagem(f"Aviso: Altura disponível para parafusos CD é negativa após desconto da laje. Definindo como 0.", "aviso")
        
        # Adicionar nível diferencial à altura disponível (se existir)
        nivel_diferencial = self._obter_nivel_diferencial()
        if nivel_diferencial is None:
            nivel_diferencial = 0.0
        else:
            nivel_diferencial = float(nivel_diferencial)
        
        # O nível diferencial está em centímetros, somar diretamente à altura disponível
        if nivel_diferencial != 0:
            altura_disponivel += nivel_diferencial
            self.log_mensagem(f"[NIVEL_DIFERENCIAL CD] Adicionando {nivel_diferencial}cm à altura disponível. Nova altura: {altura_disponivel}cm", "info")
        
        # Cálculo da quantidade de fileiras baseado na altura disponível
        qtd_fileiras = int(altura_disponivel // ESPACAMENTO_VERTICAL) + 1
        
        # Função auxiliar para calcular posição Y baseada nas configurações (painéis C e D)
        def calcular_y_posicao_cd(j):
            """Calcula a posição Y do parafuso baseado na fileira j usando as configurações (painéis C e D)"""
            medidas = [medida_1_2, medida_2_3, medida_3_4, medida_4_5,
                      medida_5_6, medida_6_7, medida_7_8, medida_8_9, medida_9_10]
            
            if j == 0:
                return y_base  # Primeira posição: medida_fundo_primeiro (já está em y_base)
            elif j <= len(medidas):
                # Soma todas as medidas até a posição j (j-1 porque j=1 é a primeira medida após o fundo)
                return y_base + sum(medidas[:j])
            else:
                # Para fileiras além da décima, usar medida_9_10 como espaçamento padrão
                y_decima = y_base + sum(medidas)
                return y_decima + (j - len(medidas) - 1) * medida_9_10
        
        # Adicionar cota vertical do primeiro parafuso até o fundo do painel (apenas se cotas_vertical estiver habilitado)
        if cotas_vertical and qtd_fileiras > 0:
            y_fundo = y_inicial - altura_total
            y_primeiro_parafuso = calcular_y_posicao_cd(0)
            script += f""";
_DIMLINEAR
{x_centro},{y_primeiro_parafuso}
{x_centro},{y_fundo}
{x_centro + 15},{(y_primeiro_parafuso + y_fundo) / 2}
;"""
        
        # Inserir parafusos no centro do painel usando configurações
        for j in range(qtd_fileiras):
            y_pos = calcular_y_posicao_cd(j)
            script += f""";
-INSERT
{bloco_furacao}
{x_centro},{y_pos}
1
0
;"""
        
        # Adicionar cotas verticais entre furos consecutivos (apenas se cotas_vertical estiver habilitado e houver mais de 1 fileira)
        if cotas_vertical and qtd_fileiras > 1:
            for j in range(qtd_fileiras - 1):
                y_atual_cota = calcular_y_posicao_cd(j)
                y_proximo = calcular_y_posicao_cd(j + 1)
                x_texto = x_centro + OFFSET_COTA
                
                script += f""";
_DIMLINEAR
{x_centro},{y_atual_cota}
{x_centro},{y_proximo}
{x_texto},{(y_atual_cota + y_proximo) / 2}
;"""
        
        # Adicionar cotas horizontais: parede esquerda até parafuso e parafuso até parede direita
        if cotas_horizontal and qtd_fileiras > 0:
            x_parede_esquerda = x_inicial
            x_parede_direita = x_inicial + largura
            y_cota = y_base  # Usar y_base para as cotas horizontais
            
            # Cota da parede esquerda até o parafuso centralizado
            script += f""";
_DIMLINEAR
{x_parede_esquerda},{y_cota}
{x_centro},{y_cota}
{(x_parede_esquerda + x_centro) / 2},{y_cota - OFFSET_COTA}
;"""
            
            # Cota do parafuso centralizado até a parede direita
            script += f""";
_DIMLINEAR
{x_centro},{y_cota}
{x_parede_direita},{y_cota}
{(x_centro + x_parede_direita) / 2},{y_cota - OFFSET_COTA}
;"""
        
        self.log_mensagem(f"Parafusos inseridos no centro do painel {tipo_painel.upper()} (largura: {largura}cm)", "info")
        return script

    def obter_laje_correta(self, tipo_painel):
        """Obtém a laje correta (A,B,C,D para Script 1 ou E,F,G,H para Script 2)"""
        try:
            if hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh:
                # Script 2: mapear A→E, B→F, C→G, D→H
                mapeamento_lajes = {'a': 'e', 'b': 'f', 'c': 'g', 'd': 'h'}
                painel_laje = mapeamento_lajes.get(tipo_painel.lower(), tipo_painel.lower())
                
                # Buscar laje do master (interface principal)
                laje_altura = 0
                pos_laje = 0
                
                if hasattr(self, 'master') and self.master:
                    try:
                        # Tentar múltiplas formas de acessar as variáveis
                        laje_attr_upper = f'laje_{painel_laje.upper()}'
                        pos_attr_upper = f'posicao_laje_{painel_laje.upper()}'
                        
                        if hasattr(self.master, laje_attr_upper):
                            laje_var = getattr(self.master, laje_attr_upper)
                            if hasattr(laje_var, 'get'):
                                laje_altura = self.converter_para_float(laje_var.get() or 0)
                        elif hasattr(self.master, 'campos') and laje_attr_upper in self.master.campos:
                            laje_altura = self.converter_para_float(self.master.campos[laje_attr_upper].get() or 0)
                        
                        if hasattr(self.master, pos_attr_upper):
                            pos_var = getattr(self.master, pos_attr_upper)
                            if hasattr(pos_var, 'get'):
                                pos_laje = self.converter_para_float(pos_var.get() or 0)
                        elif hasattr(self.master, 'campos') and pos_attr_upper in self.master.campos:
                            pos_laje = self.converter_para_float(self.master.campos[pos_attr_upper].get() or 0)
                        
                        print(f"[LAJE SCRIPT 2] Painel {tipo_painel} usando laje {painel_laje.upper()}: altura={laje_altura}, posicao={pos_laje}")
                    except Exception as e:
                        print(f"[LAJE SCRIPT 2] Erro ao acessar laje {painel_laje}: {e}")
                        laje_altura = 0
                        pos_laje = 0
                
                return laje_altura, pos_laje
            else:
                # Script 1: usar lajes normais A,B,C,D
                laje_altura = self.converter_para_float(getattr(self, f'laje_{tipo_painel}_var').get() or 0)
                pos_laje = self.converter_para_float(getattr(self, f'pos_laje_{tipo_painel}').get() or 0)
                return laje_altura, pos_laje
        except Exception as e:
            print(f"[LAJE] Erro ao obter laje para {tipo_painel}: {e}")
            return 0, 0

    def verificar_condicoes_pilar_especial(self, tipo_painel):
        """
        Verifica as condições específicas para desenhar blocos de furação nos pilares especiais.
        
        Regras:
        - Pilar 1 especial: Se comprimento1 - largura2 <= 60, não desenhar blocos nos lados A e B
        - Pilar 2 especial: Se comprimento2 - largura1 <= 60, não desenhar blocos nos lados A e B (E,F especial)
        
        Returns:
            bool: True se deve desenhar os blocos, False se deve pular
        """
        try:
            # Verificar se é pilar especial (pode ser Script 1 ou Script 2)
            is_pilar_especial = (hasattr(self, 'usar_paineis_efgh') and 
                               (self.usar_paineis_efgh or 
                                (hasattr(self, 'master') and self.master and 
                                 hasattr(self.master, 'ativar_pilar_especial') and 
                                 self.master.ativar_pilar_especial.get())))
            
            if not is_pilar_especial:
                return True  # Não é pilar especial, desenhar normalmente
            
            # Verificar se temos acesso às dimensões do pilar especial
            if not (hasattr(self, 'master') and self.master and hasattr(self.master, 'comp_1')):
                self.log_mensagem("[PILAR_ESPECIAL] Dimensões não disponíveis, desenhando normalmente", "aviso")
                return True
            
            # Obter dimensões
            comp_1 = self.converter_para_float(self.master.comp_1.get() or 0)
            comp_2 = self.converter_para_float(self.master.comp_2.get() or 0)
            larg_1 = self.converter_para_float(self.master.larg_1.get() or 0)
            larg_2 = self.converter_para_float(self.master.larg_2.get() or 0)
            
            # Verificar se as dimensões são válidas
            if comp_1 <= 0 or comp_2 <= 0 or larg_1 <= 0 or larg_2 <= 0:
                self.log_mensagem("[PILAR_ESPECIAL] Dimensões inválidas, desenhando normalmente", "aviso")
                return True
            
            # Aplicar regras específicas
            if tipo_painel in ['a', 'b']:
                # Verificar se é Script 1 especial (usar_paineis_efgh=False) ou Script 2 especial (usar_paineis_efgh=True)
                is_script2 = hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh
                
                if not is_script2:
                    # Script 1 especial: Se comprimento1 - largura2 <= 60, não desenhar
                    diferenca_pilar1 = comp_1 - larg_2
                    if diferenca_pilar1 <= 60:
                        self.log_mensagem(f"[PILAR_ESPECIAL] Script 1 - Pular blocos A/B: comp_1({comp_1}) - larg_2({larg_2}) = {diferenca_pilar1} <= 60", "info")
                        return False
                    else:
                        self.log_mensagem(f"[PILAR_ESPECIAL] Script 1 - Desenhar blocos A/B: comp_1({comp_1}) - larg_2({larg_2}) = {diferenca_pilar1} > 60", "info")
                        return True
                else:
                    # Script 2 especial: Se comprimento2 - largura1 <= 60, não desenhar (E,F especial)
                    diferenca_pilar2 = comp_2 - larg_1
                    if diferenca_pilar2 <= 60:
                        self.log_mensagem(f"[PILAR_ESPECIAL] Script 2 - Pular blocos A/B (E,F): comp_2({comp_2}) - larg_1({larg_1}) = {diferenca_pilar2} <= 60", "info")
                        return False
                    else:
                        self.log_mensagem(f"[PILAR_ESPECIAL] Script 2 - Desenhar blocos A/B (E,F): comp_2({comp_2}) - larg_1({larg_1}) = {diferenca_pilar2} > 60", "info")
                        return True
            
            # Para outros painéis, desenhar normalmente
            return True
            
        except Exception as e:
            self.log_mensagem(f"[PILAR_ESPECIAL] Erro ao verificar condições: {str(e)}, desenhando normalmente", "erro")
            return True

    def inserir_blocos_furacao(self, script, tipo_painel, x_inicial, y_inicial, parafusos, alturas, laje_altura):
        """Insere os blocos de furação no script"""
        # Verificar condições específicas do pilar especial
        if not self.verificar_condicoes_pilar_especial(tipo_painel):
            return script  # Pular desenho dos blocos
        
        # Verificar se é script especial 2 (usar_paineis_efgh)
        is_script2_especial = hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh
        
        # Determinar qual grupo de configurações usar baseado no tipo de painel
        # Script especial 2: A→E, B→F (usam cdefgh)
        # Script normal: A, B usam ab; C, D usam cdefgh
        if is_script2_especial:
            # Script 2 especial: todos os painéis (A→E, B→F, C→G, D→H) usam cdefgh
            grupo = "cdefgh"
        elif tipo_painel.lower() in ['a', 'b']:
            grupo = "ab"
        else:  # C, D
            grupo = "cdefgh"
        
        # Obter configurações de medidas Y dos parafusos do grupo correto
        # Com fallback para estrutura antiga ou valores padrão
        try:
            # Tentar obter do grupo correto primeiro (ab ou cdefgh)
            medida_fundo_primeiro_val = self.config_manager.get_config("parafusos", grupo, "medida_fundo_primeiro_" + grupo)
            medida_fundo_primeiro = self.converter_para_float(medida_fundo_primeiro_val) if medida_fundo_primeiro_val is not None else None
            if medida_fundo_primeiro is None:
                # Fallback para estrutura antiga ou padrão
                medida_fundo_primeiro_val_old = self.config_manager.get_config("parafusos", "medida_fundo_primeiro")
                medida_fundo_primeiro = self.converter_para_float(medida_fundo_primeiro_val_old) if medida_fundo_primeiro_val_old is not None else 30
            
            medida_1_2_val = self.config_manager.get_config("parafusos", grupo, "medida_1_2_" + grupo)
            medida_1_2 = self.converter_para_float(medida_1_2_val) if medida_1_2_val is not None else None
            if medida_1_2 is None:
                medida_1_2_val_old = self.config_manager.get_config("parafusos", "medida_1_2")
                medida_1_2 = self.converter_para_float(medida_1_2_val_old) if medida_1_2_val_old is not None else 50
            
            medida_2_3_val = self.config_manager.get_config("parafusos", grupo, "medida_2_3_" + grupo)
            medida_2_3 = self.converter_para_float(medida_2_3_val) if medida_2_3_val is not None else None
            if medida_2_3 is None:
                medida_2_3_val_old = self.config_manager.get_config("parafusos", "medida_2_3")
                medida_2_3 = self.converter_para_float(medida_2_3_val_old) if medida_2_3_val_old is not None else 55
            
            medida_3_4_val = self.config_manager.get_config("parafusos", grupo, "medida_3_4_" + grupo)
            medida_3_4 = self.converter_para_float(medida_3_4_val) if medida_3_4_val is not None else None
            if medida_3_4 is None:
                medida_3_4_val_old = self.config_manager.get_config("parafusos", "medida_3_4")
                medida_3_4 = self.converter_para_float(medida_3_4_val_old) if medida_3_4_val_old is not None else 55
            
            medida_4_5_val = self.config_manager.get_config("parafusos", grupo, "medida_4_5_" + grupo)
            medida_4_5 = self.converter_para_float(medida_4_5_val) if medida_4_5_val is not None else None
            if medida_4_5 is None:
                medida_4_5_val_old = self.config_manager.get_config("parafusos", "medida_4_5")
                medida_4_5 = self.converter_para_float(medida_4_5_val_old) if medida_4_5_val_old is not None else 55
            
            medida_5_6_val = self.config_manager.get_config("parafusos", grupo, "medida_5_6_" + grupo)
            medida_5_6 = self.converter_para_float(medida_5_6_val) if medida_5_6_val is not None else 55
            
            medida_6_7_val = self.config_manager.get_config("parafusos", grupo, "medida_6_7_" + grupo)
            medida_6_7 = self.converter_para_float(medida_6_7_val) if medida_6_7_val is not None else 55
            
            medida_7_8_val = self.config_manager.get_config("parafusos", grupo, "medida_7_8_" + grupo)
            medida_7_8 = self.converter_para_float(medida_7_8_val) if medida_7_8_val is not None else 55
            
            medida_8_9_val = self.config_manager.get_config("parafusos", grupo, "medida_8_9_" + grupo)
            medida_8_9 = self.converter_para_float(medida_8_9_val) if medida_8_9_val is not None else 55
            
            medida_9_10_val = self.config_manager.get_config("parafusos", grupo, "medida_9_10_" + grupo)
            medida_9_10 = self.converter_para_float(medida_9_10_val) if medida_9_10_val is not None else 55
            
            # Log de debug para verificar valores obtidos
            self.log_mensagem(f"[DEBUG FURAÇÃO] Configurações obtidas para grupo {grupo} (painel {tipo_painel}): medida_fundo_primeiro={medida_fundo_primeiro}, medida_1_2={medida_1_2}", "info")
        except (KeyError, TypeError, AttributeError) as e:
            # Fallback para valores padrão se houver erro ao acessar configurações
            self.log_mensagem(f"[DEBUG FURAÇÃO] Erro ao obter configurações: {e}, usando valores padrão", "aviso")
            medida_fundo_primeiro = 30
            medida_1_2 = 50
            medida_2_3 = 55
            medida_3_4 = 55
            medida_4_5 = 55
            medida_5_6 = 55
            medida_6_7 = 55
            medida_7_8 = 55
            medida_8_9 = 55
            medida_9_10 = 55
        
        # Configurações (mantidas para compatibilidade)
        ESPACO_BASE = medida_fundo_primeiro  # Medida do fundo até primeiro parafuso
        ESPACAMENTO_VERTICAL = medida_1_2  # Medida do primeiro ao segundo (usado para cálculo de fileiras)
        
        # Obter offset das cotas das configurações
        OFFSET_COTA = self.config_manager.get_config("drawing_options", "cota_offset") or 15
        
        # Obter nome do bloco de furação das configurações
        bloco_furacao = self.config_manager.get_config("blocks", "furacao")
        
        # Verificar se o bloco de furação está configurado
        if not bloco_furacao:
            self.log_mensagem("Aviso: Bloco de furação não configurado. Não serão inseridos blocos de furação.", "aviso")
            return script
        
        # Obter configurações de cotas de furação
        cotas_vertical = self.config_manager.get_config("drawing_options", "cotas_furacao_vertical")
        cotas_horizontal = self.config_manager.get_config("drawing_options", "cotas_furacao_horizontal")
        
        y_base = y_inicial - self.converter_para_float(self.campos['altura'].get()) + ESPACO_BASE
        altura_total = self.converter_para_float(self.campos['altura'].get() or 0)
        comprimento_total = self.converter_para_float(self.campos['comprimento'].get() or 0)
        
        # Obter posição da laje
        pos_laje = getattr(self, f'pos_laje_{tipo_painel}').get()
        
        # Calcular altura disponível para parafusos
        altura_disponivel = altura_total - 55  # Subtrai 45cm inicial
        
        # Se a laje está entre painéis, considerar apenas os painéis abaixo da laje
        if pos_laje > 0 and pos_laje < len(alturas):
            altura_disponivel = 0
            # Somar apenas as alturas dos painéis abaixo da laje
            for i in range(pos_laje):
                altura_disponivel += alturas[i]
            altura_disponivel -= 45  # Subtrai 45cm inicial
        
        # Descontar a altura da laje se ela existir
        if laje_altura > 0:
            altura_disponivel -= laje_altura
            self.log_mensagem(f"Debug furação - Descontando altura da laje: {laje_altura}cm", "info")
        
        # Garantir que a altura disponível não seja negativa
        if altura_disponivel < 0:
            altura_disponivel = 0
            self.log_mensagem(f"Aviso: Altura disponível para parafusos é negativa após desconto da laje. Definindo como 0.", "aviso")
        
        # Adicionar nível diferencial à altura disponível (se existir)
        nivel_diferencial = self._obter_nivel_diferencial()
        if nivel_diferencial is None:
            nivel_diferencial = 0.0
        else:
            nivel_diferencial = float(nivel_diferencial)
        
        # O nível diferencial está em centímetros, somar diretamente à altura disponível
        if nivel_diferencial != 0:
            altura_disponivel += nivel_diferencial
            self.log_mensagem(f"[NIVEL_DIFERENCIAL] Adicionando {nivel_diferencial}cm à altura disponível. Nova altura: {altura_disponivel}cm", "info")
        
        # Cálculo da quantidade de parafusos
        quantidade_parafusos = math.ceil((comprimento_total + 24) / 70) + 1
        
        # Debug: Log das informações importantes
        self.log_mensagem(f"Debug furação - Painel {tipo_painel}: bloco={bloco_furacao}, altura_disponivel={altura_disponivel}, qtd_parafusos={quantidade_parafusos}", "info")
        self.log_mensagem(f"Debug parafusos entrada - Painel {tipo_painel}: parafusos={parafusos}", "info")
        
        if tipo_painel == 'a':
            # Verificar se é pilar especial
            is_pilar_especial = hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh
            
            # Para Script 1: usar globais de parafusos especiais A
            usar_globais_especiais = hasattr(self, 'parafusos_globais_especiais_a') and self.parafusos_globais_especiais_a and not is_pilar_especial
            
            # Para Script 2: usar globais de parafusos especiais E
            usar_globais_e = is_pilar_especial and hasattr(self, 'parafusos_globais_especiais_e') and self.parafusos_globais_especiais_e
            
            self.log_mensagem(f"[DEBUG] is_pilar_especial: {is_pilar_especial}, usar_globais_especiais: {usar_globais_especiais}, usar_globais_e: {usar_globais_e}", "info")
            
            if usar_globais_especiais:
                # Script 1: Usar globais de parafusos especiais A
                parafusos_validos = [p for p in self.parafusos_globais_especiais_a if p > 0]
                self.log_mensagem(f"[GLOBAIS_PARAFUSOS] Usando globais especiais A: {parafusos_validos}", "info")
            elif usar_globais_e:
                # Script 2: Usar globais de parafusos especiais E para painel A
                parafusos_validos = [p for p in self.parafusos_globais_especiais_e if p > 0]
                # Remover o último parafuso válido para Script 2
                if len(parafusos_validos) > 0:
                    parafusos_validos = parafusos_validos[:-1]
                    self.log_mensagem(f"[PILAR_ESPECIAL] Removendo último parafuso válido do painel A (E) no segundo script", "info")
                self.log_mensagem(f"[GLOBAIS_PARAFUSOS] Script 2 - Usando globais especiais E para painel A: {parafusos_validos}", "info")
            else:
                # Filtrar parafusos válidos (maiores que 0) - comportamento normal
                parafusos_validos = [p for p in parafusos if p > 0]
                self.log_mensagem(f"[DEBUG PARAFUSOS] Parafusos válidos ANTES da remoção: {parafusos_validos} (total: {len(parafusos_validos)})", "info")
                
                # No segundo script do pilar especial, remover o último parafuso válido
                if is_pilar_especial and len(parafusos_validos) > 0:
                    # Remover o último parafuso válido para lados A e B no segundo script
                    ultimo_removido = parafusos_validos[-1]
                    parafusos_validos = parafusos_validos[:-1]
                    self.log_mensagem(f"[PILAR_ESPECIAL] Removendo último parafuso válido ({ultimo_removido}) do painel A no segundo script", "info")
                elif not is_pilar_especial and len(parafusos_validos) > 1:
                    # PILARES COMUNS: Remover o último parafuso válido se houver mais de 1
                    # Para pilares comuns, identificar valores únicos e remover o último valor único
                    # Exemplo: [52, 51, 51, 70] → valores únicos: [52, 51, 70] → remove 70 → fica [52, 51, 51] (desenha 3 parafusos)
                    # Exemplo: [52, 51, 70] → remove 70 → fica [52, 51] (desenha 2 parafusos)
                    # Exemplo: [56, 56, 56, 56, 105] → valores únicos: [56, 105] → remove 105 → fica [56, 56, 56, 56] → remove último → [56, 56, 56] (desenha 3 parafusos)
                    
                    # Obter valores únicos mantendo a ordem de primeira ocorrência
                    valores_unicos = []
                    for parafuso in parafusos_validos:
                        if parafuso not in valores_unicos:
                            valores_unicos.append(parafuso)
                    
                    # Se temos mais de 1 valor único, remover o último valor único
                    if len(valores_unicos) > 1:
                        ultimo_valor_unico = valores_unicos[-1]
                        # Remover todos os parafusos que correspondem ao último valor único
                        parafusos_validos = [p for p in parafusos_validos if p != ultimo_valor_unico]
                        
                        # CORREÇÃO: NÃO remover duplicados consecutivos aqui!
                        # Se temos [56, 56, 56, 56], cada um representa uma fileira diferente
                        # Apenas removemos o último elemento (pilares comuns não desenham o último)
                        if len(parafusos_validos) > 0:
                            ultimo_removido = parafusos_validos[-1]
                            parafusos_validos = parafusos_validos[:-1]
                            self.log_mensagem(f"[PILAR_COMUM] Removendo último parafuso válido único ({ultimo_valor_unico}) e último elemento ({ultimo_removido}) do painel A (pilares comuns não desenham o último). Restam {len(parafusos_validos)} parafuso(s) para desenhar: {parafusos_validos}", "info")
                        else:
                            self.log_mensagem(f"[PILAR_COMUM] Removendo último parafuso válido único ({ultimo_valor_unico}) do painel A. Nenhum parafuso restante.", "info")
                    else:
                        # Se só temos 1 valor único, remover o último elemento normalmente
                        ultimo_removido = parafusos_validos[-1]
                        parafusos_validos = parafusos_validos[:-1]
                        self.log_mensagem(f"[PILAR_COMUM] Removendo último parafuso válido ({ultimo_removido}) do painel A (pilares comuns não desenham o último). Restam {len(parafusos_validos)} parafuso(s) para desenhar: {parafusos_validos}", "info")
                
                self.log_mensagem(f"[DEBUG] Usando parafusos normais: {parafusos_validos}", "info")
            
            if not parafusos_validos:
                return script  # Retorna sem desenhar se não houver valores válidos
            
            # Verificar se apenas 1 campo de parafuso está preenchido
            apenas_um_parafuso = len(parafusos_validos) == 1 and not is_pilar_especial
            
            # PILARES COMUNS com apenas 1 parafuso: verificar se comprimento >= 48
            if apenas_um_parafuso and not is_pilar_especial:
                if comprimento_total < 48:
                    self.log_mensagem(f"[PILAR_COMUM] Apenas 1 parafuso preenchido mas comprimento ({comprimento_total}cm) < 48cm. Não desenhando furações.", "info")
                    return script  # Retorna sem desenhar se comprimento < 48
            self.log_mensagem(f"Debug parafusos A - parafusos_validos: {parafusos_validos}, is_pilar_especial: {is_pilar_especial}, usar_globais_especiais: {usar_globais_especiais}, apenas_um_parafuso: {apenas_um_parafuso}", "info")
            
            # Aplicar desconto apenas no primeiro parafuso preenchido
            if len(parafusos_validos) > 0:
                if usar_globais_e:
                    # Script 2 (Painel E): Descontar 3.5 do primeiro
                    parafusos_validos[0] -= 4.5
                    self.log_mensagem(f"[SCRIPT2_PAINEL_E] Aplicando desconto de 3.5 ao primeiro parafuso: {parafusos_validos[0]}", "info")
                else:
                    # Script 1 (Painel A): Descontar 1 do primeiro
                    parafusos_validos[0] -= 1
                    
                    # Para pilares comuns, armazenar os valores processados para reutilizar no painel B
                    if not is_pilar_especial:
                        self.parafusos_a_processados = parafusos_validos.copy()
                        self.log_mensagem(f"[PAINEL_A_PROCESSADOS] Armazenando valores processados do painel A para reutilizar no painel B: {self.parafusos_a_processados}", "info")
            
            # Guardar o último parafuso para desenhar sua cota
            ultimo_parafuso = None
            if len(parafusos_validos) > 1:
                ultimo_parafuso = parafusos_validos[-1]
                # NÃO remover o último elemento - desenhar TODOS os parafusos
            
            # Se apenas 1 parafuso está preenchido, centralizar X
            if apenas_um_parafuso:
                # Para pilares comuns, centralizar no centro do painel A individual
                largura_a = self.calcular_largura_total_painel('a')
                # Para painel A, o centro é x_inicial + largura_a/2
                x_centro = x_inicial + (largura_a / 2)
                x_atual = x_centro
                self.log_mensagem(f"Debug centralização X A (COMUM) - x_inicial: {x_inicial}, largura_a: {largura_a}, x_centro: {x_centro}", "info")
            else:
                # Começar da parede esquerda com o primeiro valor válido
                x_atual = x_inicial + parafusos_validos[0]
            
            # Adicionar cota vertical do primeiro parafuso até o fundo do painel H1 (apenas se cotas_vertical estiver habilitado)
            if cotas_vertical:
                y_fundo = y_inicial - altura_total
                script += f""";
_DIMLINEAR
{x_atual},{y_base}
{x_atual},{y_fundo}
{x_atual + 15},{(y_base + y_fundo) / 2}
;"""
            
            # Adicionar cota horizontal da parede esquerda até o primeiro furacao
            if cotas_horizontal:
                script += f""";
_DIMLINEAR
{x_inicial},{y_base}
{x_atual},{y_base}
{(x_inicial + x_atual) / 2},{y_base - OFFSET_COTA}
;"""
            
            # Desenhar furações para cada parafuso válido
            # Para pilares especiais com globais, desenhar TODOS os parafusos válidos
            if usar_globais_especiais:
                max_parafusos = len(parafusos_validos)
            else:
                max_parafusos = min(len(parafusos_validos), quantidade_parafusos)
            
            for i in range(max_parafusos):
                # Cálculo do número de fileiras baseado na altura disponível
                qtd_fileiras = int(altura_disponivel // ESPACAMENTO_VERTICAL) + 1
                
                # Função auxiliar para calcular posição Y baseada nas configurações
                def calcular_y_posicao(j):
                    """Calcula a posição Y do parafuso baseado na fileira j usando as configurações"""
                    medidas = [medida_1_2, medida_2_3, medida_3_4, medida_4_5,
                              medida_5_6, medida_6_7, medida_7_8, medida_8_9, medida_9_10]
                    
                    if j == 0:
                        return y_base  # Primeira posição: medida_fundo_primeiro (já está em y_base)
                    elif j <= len(medidas):
                        # Soma todas as medidas até a posição j (j-1 porque j=1 é a primeira medida após o fundo)
                        return y_base + sum(medidas[:j])
                    else:
                        # Para fileiras além da décima, usar medida_9_10 como espaçamento padrão
                        y_decima = y_base + sum(medidas)
                        return y_decima + (j - len(medidas) - 1) * medida_9_10
                
                # Se apenas 1 parafuso está preenchido, centralizar apenas X (Y mantém distribuição normal)
                if apenas_um_parafuso:
                    # Usar distribuição normal em Y baseada nas configurações
                    for j in range(qtd_fileiras):
                        y_pos = calcular_y_posicao(j)
                        self.log_mensagem(f"Debug centralização A - y_base: {y_base}, y_pos: {y_pos} (distribuição configurável, fileira {j+1}/{qtd_fileiras})", "info")
                        script += f""";
-INSERT
{bloco_furacao}
{x_atual},{y_pos}
1
0
;"""
                else:
                    # Geração das furações usando configurações
                    for j in range(qtd_fileiras):
                        y_pos = calcular_y_posicao(j)
                        script += f""";
-INSERT
{bloco_furacao}
{x_atual},{y_pos}
1
0
;"""
                
                # Cotas verticais entre furações (apenas na primeira coluna, quando há múltiplas fileiras)
                # Para pilares comuns, desenhar cotas mesmo quando há apenas 1 parafuso em X (mas múltiplas fileiras em Y)
                if i == 0 and cotas_vertical and qtd_fileiras > 1:
                    # Cotas individuais entre furos consecutivos usando configurações
                    for j in range(qtd_fileiras - 1):
                        y_atual_cota = calcular_y_posicao(j)
                        y_proximo = calcular_y_posicao(j + 1)
                        x_texto = x_atual + OFFSET_COTA
                        
                        script += f""";
_DIMLINEAR
{x_atual},{y_atual_cota}
{x_atual},{y_proximo}
{x_texto},{(y_atual_cota + y_proximo) / 2}
;"""
                
                # Cota horizontal entre parafusos (não no último)
                if cotas_horizontal and i < len(parafusos_validos) - 1:
                    x_proximo = x_atual + parafusos_validos[i+1]
                    script += f""";
_DIMLINEAR
{x_atual},{y_base}
{x_proximo},{y_base}
{(x_atual + x_proximo) / 2},{y_base - OFFSET_COTA}
;"""
                
                # Mover para a próxima posição (se não for o último parafuso)
                if i < len(parafusos_validos) - 1:
                    x_atual += parafusos_validos[i+1]
            
            # Adicionar cota do último parafuso até a parede direita (se existir)
            if cotas_horizontal:
                if ultimo_parafuso:
                    # Se há mais de 1 parafuso, cota do último até a parede direita
                    x_ultimo_parafuso = x_atual + ultimo_parafuso
                    largura_total = self.calcular_largura_total_painel('a')
                    x_parede_direita = x_inicial + largura_total
                    script += f""";
_DIMLINEAR
{x_ultimo_parafuso},{y_base}
{x_parede_direita},{y_base}
{(x_ultimo_parafuso + x_parede_direita) / 2},{y_base - OFFSET_COTA}
;"""
                elif apenas_um_parafuso:
                    # Se há apenas 1 parafuso, cota do parafuso até a parede direita
                    largura_total = self.calcular_largura_total_painel('a')
                    x_parede_direita = x_inicial + largura_total
                    script += f""";
_DIMLINEAR
{x_atual},{y_base}
{x_parede_direita},{y_base}
{(x_atual + x_parede_direita) / 2},{y_base - OFFSET_COTA}
;"""
                    
        elif tipo_painel == 'b':
            # Verificar se é pilar especial
            is_pilar_especial = hasattr(self, 'usar_paineis_efgh') and self.usar_paineis_efgh
            
            # Para Script 1: usar globais de parafusos especiais A
            usar_globais_especiais = hasattr(self, 'parafusos_globais_especiais_a') and self.parafusos_globais_especiais_a and not is_pilar_especial
            
            # Para Script 2: usar globais de parafusos especiais F
            usar_globais_f = is_pilar_especial and hasattr(self, 'parafusos_globais_especiais_f') and self.parafusos_globais_especiais_f
            
            self.log_mensagem(f"[DEBUG B] is_pilar_especial: {is_pilar_especial}, usar_globais_especiais: {usar_globais_especiais}, usar_globais_f: {usar_globais_f}", "info")
            
            if usar_globais_especiais:
                # Script 1: Usar globais de parafusos especiais A para painel B (invertido)
                parafusos_globais = [p for p in self.parafusos_globais_especiais_a if p > 0]
                # Inverter a ordem dos parafusos para o painel B
                valores_validos = parafusos_globais[::-1]  # Inverte a lista
                self.log_mensagem(f"[GLOBAIS_PARAFUSOS] Script 1 - Usando globais especiais A para B: {valores_validos}", "info")
            elif usar_globais_f:
                # Script 2: Usar globais de parafusos especiais F para painel B
                valores_validos = [p for p in self.parafusos_globais_especiais_f if p > 0]
                # Remover o último parafuso válido para Script 2
                if len(valores_validos) > 0:
                    valores_validos = valores_validos[:-1]
                    self.log_mensagem(f"[PILAR_ESPECIAL] Removendo último parafuso válido do painel B (F) no segundo script", "info")
                self.log_mensagem(f"[GLOBAIS_PARAFUSOS] Script 2 - Usando globais especiais F para painel B: {valores_validos}", "info")
            else:
                # Para pilares comuns, reutilizar os valores processados do painel A
                if not is_pilar_especial:
                    if hasattr(self, 'parafusos_a_processados') and self.parafusos_a_processados:
                        # PILARES COMUNS: Usar os mesmos valores processados do painel A
                        valores_validos = self.parafusos_a_processados.copy()
                        self.log_mensagem(f"[PAINEL_B_REUTILIZA] Reutilizando valores processados do painel A para painel B: {valores_validos}", "info")
                    else:
                        # PILARES COMUNS: Se valores do painel A não estão disponíveis, processar da mesma forma que o painel A
                        # (não apenas inverter, mas processar igual ao painel A)
                        parafusos_validos_temp = [p for p in parafusos if p > 0]
                        self.log_mensagem(f"[DEBUG PARAFUSOS B] Parafusos válidos ANTES da remoção: {parafusos_validos_temp} (total: {len(parafusos_validos_temp)})", "info")
                        
                        # Processar da mesma forma que o painel A (remover último valor único, depois último elemento)
                        if len(parafusos_validos_temp) > 1:
                            # Obter valores únicos mantendo a ordem de primeira ocorrência
                            valores_unicos = []
                            for parafuso in parafusos_validos_temp:
                                if parafuso not in valores_unicos:
                                    valores_unicos.append(parafuso)
                            
                            # Se temos mais de 1 valor único, remover o último valor único
                            if len(valores_unicos) > 1:
                                ultimo_valor_unico = valores_unicos[-1]
                                # Remover todos os parafusos que correspondem ao último valor único
                                parafusos_validos_temp = [p for p in parafusos_validos_temp if p != ultimo_valor_unico]
                                
                                # CORREÇÃO: NÃO remover duplicados consecutivos aqui!
                                # Se temos [56, 56, 56, 56], cada um representa uma fileira diferente
                                # Apenas removemos o último elemento (pilares comuns não desenham o último)
                                if len(parafusos_validos_temp) > 0:
                                    valores_validos = parafusos_validos_temp[:-1]
                                else:
                                    valores_validos = parafusos_validos_temp
                            else:
                                # Se só temos 1 valor único, remover o último elemento normalmente
                                valores_validos = parafusos_validos_temp[:-1]
                        else:
                            valores_validos = parafusos_validos_temp
                        
                        # Aplicar desconto de 1cm (mesmo que o painel A)
                        if len(valores_validos) > 0:
                            valores_validos[0] -= 1
                        
                        self.log_mensagem(f"[PAINEL_B_PROCESSADO] Processando valores do painel B (mesma lógica do painel A): {valores_validos}", "info")
                else:
                    # PILARES ESPECIAIS: Processar normalmente (inverter e processar)
                    # Inverter a ordem dos parafusos para o painel B - comportamento normal
                    parafusos_invertidos = parafusos[::-1]  # Inverte a lista
                    # Filtrar apenas os valores válidos (maiores que 0)
                    valores_validos = [x for x in parafusos_invertidos if x > 0]
                    self.log_mensagem(f"[DEBUG PARAFUSOS B] Parafusos válidos ANTES da remoção: {valores_validos} (total: {len(valores_validos)})", "info")
                    
                    # No segundo script do pilar especial, remover o último parafuso válido
                    if is_pilar_especial and len(valores_validos) > 0:
                        # Remover o último parafuso válido para lados A e B no segundo script
                        ultimo_removido = valores_validos[-1]
                        valores_validos = valores_validos[:-1]
                        self.log_mensagem(f"[PILAR_ESPECIAL] Removendo último parafuso válido ({ultimo_removido}) do painel B no segundo script", "info")
                
                self.log_mensagem(f"[DEBUG B] Usando parafusos normais: {valores_validos}", "info")
            
            if not valores_validos:
                return script  # Retorna sem desenhar se não houver valores válidos
            
            # Verificar se apenas 1 campo de parafuso está preenchido
            apenas_um_parafuso = len(valores_validos) == 1 and not is_pilar_especial
            
            # PILARES COMUNS com apenas 1 parafuso: verificar se comprimento >= 48
            if apenas_um_parafuso and not is_pilar_especial:
                if comprimento_total < 48:
                    self.log_mensagem(f"[PILAR_COMUM] Apenas 1 parafuso preenchido mas comprimento ({comprimento_total}cm) < 48cm. Não desenhando furações.", "info")
                    return script  # Retorna sem desenhar se comprimento < 48
            self.log_mensagem(f"Debug parafusos B - valores_validos: {valores_validos}, is_pilar_especial: {is_pilar_especial}, usar_globais_especiais: {usar_globais_especiais}, apenas_um_parafuso: {apenas_um_parafuso}", "info")
            
            # Aplicar desconto apenas para pilares especiais (pilares comuns já têm desconto aplicado)
            if len(valores_validos) > 0 and not usar_globais_f:
                # Para pilares comuns, o desconto já foi aplicado (seja reutilizando valores do painel A ou processando)
                # Aplicar desconto apenas para pilares especiais
                if is_pilar_especial:
                    valores_validos[0] -= 1  # Desconta 1 do primeiro (apenas Script 1)
                    self.log_mensagem(f"[PAINEL_B_DESCONTO] Aplicando desconto de 1cm ao primeiro parafuso (especial): {valores_validos[0]}", "info")
                else:
                    self.log_mensagem(f"[PAINEL_B_SEM_DESCONTO] Desconto já aplicado (pilar comum)", "info")
            
            # Guardar o último parafuso para desenhar sua cota
            ultimo_parafuso = None
            if len(valores_validos) > 1:
                ultimo_parafuso = valores_validos[-1]
                # NÃO remover o último elemento - desenhar TODOS os parafusos
            
            # Se apenas 1 parafuso está preenchido, centralizar X
            if apenas_um_parafuso:
                # Para pilares comuns, centralizar no centro do painel B individual
                largura_b = self.calcular_largura_total_painel('b')
                # Para painel B, o centro é x_inicial + largura_b/2
                x_centro = x_inicial + (largura_b / 2)
                x_atual = x_centro
                self.log_mensagem(f"Debug centralização X B (COMUM) - x_inicial: {x_inicial}, largura_b: {largura_b}, x_centro: {x_centro}", "info")
            else:
                if usar_globais_f:
                    # Script 2 (Painel F): Começar da parede DIREITA (espelhado)
                    # Calcular largura total do painel
                    largura_total = self.calcular_largura_total_painel('b')
                    x_final = x_inicial + largura_total  # Posição da parede direita
                    # Começar da parede direita menos o primeiro valor
                    x_atual = x_final - valores_validos[0]
                    self.log_mensagem(f"[SCRIPT2_PAINEL_F] Espelhando da direita para esquerda - x_inicial: {x_inicial}, largura_total: {largura_total}, x_final: {x_final}, x_atual: {x_atual}", "info")
                else:
                    # Script 1 (Painel B): Para pilares comuns, espelhar do painel A (começar da parede direita)
                    if not is_pilar_especial:
                        # Pilares comuns: espelhar - começar da parede direita
                        largura_total = self.calcular_largura_total_painel('b')
                        x_final = x_inicial + largura_total  # Posição da parede direita
                        # Começar da parede direita menos o primeiro valor (espelho)
                        x_atual = x_final - valores_validos[0]
                        self.log_mensagem(f"[PAINEL_B_ESPELHO] Espelhando da direita para esquerda (comum) - x_inicial: {x_inicial}, largura_total: {largura_total}, x_final: {x_final}, x_atual: {x_atual}", "info")
                    else:
                        # Pilares especiais: Começar da parede esquerda (comportamento original)
                        x_atual = x_inicial + valores_validos[0]
            
            # Adicionar cota vertical do primeiro parafuso até o fundo do painel H1 (apenas se cotas_vertical estiver habilitado)
            if cotas_vertical:
                y_fundo = y_inicial - altura_total
                script += f""";
_DIMLINEAR
{x_atual},{y_base}
{x_atual},{y_fundo}
{x_atual + 15},{(y_base + y_fundo) / 2}
;"""
            
            # Adicionar cota horizontal da parede até o primeiro furacao
            if cotas_horizontal:
                if usar_globais_f:
                    # Script 2 (Painel F): Cota da parede direita até o primeiro furo
                    largura_total = self.calcular_largura_total_painel('b')
                    x_parede_direita = x_inicial + largura_total
                    script += f""";
_DIMLINEAR
{x_parede_direita},{y_base}
{x_atual},{y_base}
{(x_parede_direita + x_atual) / 2},{y_base - OFFSET_COTA}
;"""
                else:
                    # Script 1 (Painel B): Cota baseada no tipo de pilar
                    if not is_pilar_especial:
                        # Pilares comuns: Cota da parede direita até o primeiro furo (espelho)
                        largura_total = self.calcular_largura_total_painel('b')
                        x_parede_direita = x_inicial + largura_total
                        script += f""";
_DIMLINEAR
{x_parede_direita},{y_base}
{x_atual},{y_base}
{(x_parede_direita + x_atual) / 2},{y_base - OFFSET_COTA}
;"""
                    else:
                        # Pilares especiais: Cota da parede esquerda até o primeiro furo
                        script += f""";
_DIMLINEAR
{x_inicial},{y_base}
{x_atual},{y_base}
{(x_inicial + x_atual) / 2},{y_base - OFFSET_COTA}
;"""
            
            # Desenhar furações para cada parafuso válido no painel B
            # Para pilares especiais com globais, desenhar TODOS os parafusos válidos
            if usar_globais_especiais:
                max_parafusos = len(valores_validos)
            else:
                max_parafusos = min(len(valores_validos), quantidade_parafusos)
            
            for i in range(max_parafusos):
                # Cálculo do número de fileiras baseado na altura disponível
                qtd_fileiras = int(altura_disponivel // ESPACAMENTO_VERTICAL) + 1
                
                # Função auxiliar para calcular posição Y baseada nas configurações
                def calcular_y_posicao_b(j):
                    """Calcula a posição Y do parafuso baseado na fileira j usando as configurações (painel B)"""
                    medidas = [medida_1_2, medida_2_3, medida_3_4, medida_4_5,
                              medida_5_6, medida_6_7, medida_7_8, medida_8_9, medida_9_10]
                    
                    if j == 0:
                        return y_base  # Primeira posição: medida_fundo_primeiro (já está em y_base)
                    elif j <= len(medidas):
                        # Soma todas as medidas até a posição j (j-1 porque j=1 é a primeira medida após o fundo)
                        return y_base + sum(medidas[:j])
                    else:
                        # Para fileiras além da décima, usar medida_9_10 como espaçamento padrão
                        y_decima = y_base + sum(medidas)
                        return y_decima + (j - len(medidas) - 1) * medida_9_10
                
                # Se apenas 1 parafuso está preenchido, centralizar apenas X (Y mantém distribuição normal)
                if apenas_um_parafuso:
                    # Usar distribuição normal em Y baseada nas configurações
                    for j in range(qtd_fileiras):
                        y_pos = calcular_y_posicao_b(j)
                        self.log_mensagem(f"Debug centralização B - y_base: {y_base}, y_pos: {y_pos} (distribuição configurável, fileira {j+1}/{qtd_fileiras})", "info")
                        script += f""";
-INSERT
{bloco_furacao}
{x_atual},{y_pos}
1
0
;"""
                else:
                    # Geração das furações usando configurações
                    for j in range(qtd_fileiras):
                        y_pos = calcular_y_posicao_b(j)
                        script += f""";
-INSERT
{bloco_furacao}
{x_atual},{y_pos}
1
0
;"""
                
                # Cotas verticais entre furações (apenas na primeira coluna, quando há múltiplas fileiras)
                # Para pilares comuns, desenhar cotas mesmo quando há apenas 1 parafuso em X (mas múltiplas fileiras em Y)
                if i == 0 and cotas_vertical and qtd_fileiras > 1:
                    # Cotas individuais entre furos consecutivos usando configurações
                    for j in range(qtd_fileiras - 1):
                        y_atual_cota = calcular_y_posicao_b(j)
                        y_proximo = calcular_y_posicao_b(j + 1)
                        x_texto = x_atual + OFFSET_COTA
                        
                        script += f""";
_DIMLINEAR
{x_atual},{y_atual_cota}
{x_atual},{y_proximo}
{x_texto},{(y_atual_cota + y_proximo) / 2}
;"""
                
                # Cota horizontal entre parafusos (não no último)
                if cotas_horizontal and i < len(valores_validos) - 1:
                    if usar_globais_f:
                        # Script 2 (Painel F): Proximo está à esquerda
                        x_proximo = x_atual - valores_validos[i+1]
                    else:
                        # Script 1 (Painel B): Próximo baseado no tipo de pilar
                        if not is_pilar_especial:
                            # Pilares comuns: Próximo está à esquerda (espelho)
                            x_proximo = x_atual - valores_validos[i+1]
                        else:
                            # Pilares especiais: Próximo está à direita
                            x_proximo = x_atual + valores_validos[i+1]
                    
                    script += f""";
_DIMLINEAR
{x_atual},{y_base}
{x_proximo},{y_base}
{(x_atual + x_proximo) / 2},{y_base - OFFSET_COTA}
;"""
                
                # Mover para a próxima posição (se não for o último parafuso)
                if i < len(valores_validos) - 1:
                    if usar_globais_f:
                        # Script 2 (Painel F): Mover para a esquerda (subtrair)
                        x_atual -= valores_validos[i+1]
                    else:
                        # Script 1 (Painel B): Mover baseado no tipo de pilar
                        if not is_pilar_especial:
                            # Pilares comuns: Mover para a esquerda (subtrair - espelho)
                            x_atual -= valores_validos[i+1]
                        else:
                            # Pilares especiais: Mover para a direita (somar)
                            x_atual += valores_validos[i+1]
            
            # Adicionar cota do último parafuso até a parede esquerda (se existir) para painel B
            if cotas_horizontal:
                if ultimo_parafuso:
                    # Se há mais de 1 parafuso, cota do último até a parede esquerda
                    if not is_pilar_especial:
                        # Pilares comuns: Cota da parede esquerda até o último parafuso (espelho)
                        x_ultimo_parafuso = x_atual
                        script += f""";
_DIMLINEAR
{x_inicial},{y_base}
{x_ultimo_parafuso},{y_base}
{(x_inicial + x_ultimo_parafuso) / 2},{y_base - OFFSET_COTA}
;"""
                    else:
                        # Pilares especiais: Cota do último parafuso até a parede direita
                        x_ultimo_parafuso = x_atual + ultimo_parafuso
                        largura_total = self.calcular_largura_total_painel('b')
                        x_parede_direita = x_inicial + largura_total
                        script += f""";
_DIMLINEAR
{x_ultimo_parafuso},{y_base}
{x_parede_direita},{y_base}
{(x_ultimo_parafuso + x_parede_direita) / 2},{y_base - OFFSET_COTA}
;"""
                elif apenas_um_parafuso:
                    # Se há apenas 1 parafuso, cota da parede esquerda até o parafuso
                    if not is_pilar_especial:
                        script += f""";
_DIMLINEAR
{x_inicial},{y_base}
{x_atual},{y_base}
{(x_inicial + x_atual) / 2},{y_base - OFFSET_COTA}
;"""
        
        return script
    
    def _atualizar_todos_campos_configuracao(self):
        """Atualiza todos os campos da janela de configurações com os valores atuais do config_manager"""
        if not (hasattr(self, 'config_window') and self.config_window.winfo_exists()):
            return
        
        try:
            # Atualizar campos de layers
            if hasattr(self, 'entry_paineis'):
                self.entry_paineis.delete(0, tk.END)
                self.entry_paineis.insert(0, self.config_manager.get_config("layers", "paineis_abcd") or "")
                
                self.entry_pe_direito.delete(0, tk.END)
                self.entry_pe_direito.insert(0, self.config_manager.get_config("layers", "pe_direito") or "")
                
                self.entry_cotas.delete(0, tk.END)
                self.entry_cotas.insert(0, self.config_manager.get_config("layers", "cotas") or "")
                
                self.entry_sarrafos.delete(0, tk.END)
                self.entry_sarrafos.insert(0, self.config_manager.get_config("layers", "sarrafos") or "")
                
                self.entry_nomenclatura.delete(0, tk.END)
                self.entry_nomenclatura.insert(0, self.config_manager.get_config("layers", "nomenclatura") or "")
                
                self.entry_laje.delete(0, tk.END)
                self.entry_laje.insert(0, self.config_manager.get_config("layers", "laje") or "")
                
                self.entry_linhas_hidden.delete(0, tk.END)
                self.entry_linhas_hidden.insert(0, self.config_manager.get_config("layers", "linhas_hidden") or "")
                
                if hasattr(self, 'entry_hatch_laje'):
                    self.entry_hatch_laje.delete(0, tk.END)
                    self.entry_hatch_laje.insert(0, self.config_manager.get_config("comandos", "hatches", "laje") or "HHHH")
            
            # Atualizar campos de blocos
            if hasattr(self, 'entry_furacao'):
                self.entry_furacao.delete(0, tk.END)
                self.entry_furacao.insert(0, self.config_manager.get_config("blocks", "furacao") or "")
                
                self.entry_split_ee.delete(0, tk.END)
                self.entry_split_ee.insert(0, self.config_manager.get_config("blocks", "split_ee") or "")
                
                self.entry_split_dd.delete(0, tk.END)
                self.entry_split_dd.insert(0, self.config_manager.get_config("blocks", "split_dd") or "")
                
                self.entry_moldura.delete(0, tk.END)
                self.entry_moldura.insert(0, self.config_manager.get_config("blocks", "moldura") or "")
            
            # Atualizar campos de parafusos A-B
            if hasattr(self, 'entries_parafusos_ab'):
                medidas_ab_keys = ["medida_fundo_primeiro_ab", "medida_1_2_ab", "medida_2_3_ab", "medida_3_4_ab", 
                                   "medida_4_5_ab", "medida_5_6_ab", "medida_6_7_ab", "medida_7_8_ab", 
                                   "medida_8_9_ab", "medida_9_10_ab"]
                defaults_ab = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                for key, default in zip(medidas_ab_keys, defaults_ab):
                    if key in self.entries_parafusos_ab:
                        self.entries_parafusos_ab[key].delete(0, tk.END)
                        # Usar get_config com múltiplos argumentos para acessar parafusos.ab.key
                        valor = self.config_manager.get_config("parafusos", "ab", key)
                        # Debug: verificar valor obtido
                        if key == "medida_fundo_primeiro_ab":
                            print(f"[DEBUG UPDATE] Campo {key}: valor obtido = {valor}, default = {default}")
                        self.entries_parafusos_ab[key].insert(0, str(valor if valor is not None else default))
            
            # Atualizar campos de parafusos C-D-E-F-G-H
            if hasattr(self, 'entries_parafusos_cdefgh'):
                medidas_cdefgh_keys = ["medida_fundo_primeiro_cdefgh", "medida_1_2_cdefgh", "medida_2_3_cdefgh", "medida_3_4_cdefgh",
                                      "medida_4_5_cdefgh", "medida_5_6_cdefgh", "medida_6_7_cdefgh", "medida_7_8_cdefgh",
                                      "medida_8_9_cdefgh", "medida_9_10_cdefgh"]
                defaults_cdefgh = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                for key, default in zip(medidas_cdefgh_keys, defaults_cdefgh):
                    if key in self.entries_parafusos_cdefgh:
                        self.entries_parafusos_cdefgh[key].delete(0, tk.END)
                        # Usar get_config com múltiplos argumentos para acessar parafusos.cdefgh.key
                        valor = self.config_manager.get_config("parafusos", "cdefgh", key)
                        # Debug: verificar valor obtido
                        if key == "medida_fundo_primeiro_cdefgh":
                            print(f"[DEBUG UPDATE] Campo {key}: valor obtido = {valor}, default = {default}")
                        self.entries_parafusos_cdefgh[key].insert(0, str(valor if valor is not None else default))
            
            # Atualizar lista de templates
            if hasattr(self, 'atualizar_lista_templates'):
                self.atualizar_lista_templates()
                
        except Exception as e:
            self.log_mensagem(f"Erro ao atualizar campos de configuração: {str(e)}", "erro")

    def calcular_altura_painel(self, tipo_painel):
        """
        Calcula a altura total dos painéis válidos acima da laje
        """
        alturas = []
        tem_laje = False
        
        # Itera pelos painéis de baixo para cima (H1 até H5)
        for i in range(1, 6):
            altura_var = self.campos.get(f'altura_h{i}_{tipo_painel.lower()}')
            if not altura_var:
                continue
                
            altura_str = altura_var.get().strip()
            if not altura_str:
                continue
                
            try:
                altura = self.converter_para_float(altura_str)
                if altura > 0:
                    # Verifica se tem laje após este painel
                    laje_var = self.campos.get(f'laje_h{i}_{tipo_painel.lower()}')
                    if laje_var and laje_var.get():
                        tem_laje = True
                        break
                    alturas.append(altura)
            except ValueError:
                continue
        
        # Se não encontrou laje, considera todos os painéis válidos
        if not tem_laje:
            alturas = []
            for i in range(1, 6):
                altura_var = self.campos.get(f'altura_h{i}_{tipo_painel.lower()}')
                if altura_var:
                    altura_str = altura_var.get().strip()
                    try:
                        altura = self.converter_para_float(altura_str)
                        if altura > 0:
                            alturas.append(altura)
                    except ValueError:
                        continue
        
        return sum(alturas)

    def calcular_altura_painel_acima_laje(self, tipo_painel):
        """
        Encontra especificamente a altura do painel que está imediatamente acima da laje
        """
        try:
            # Primeiro encontra a posição da laje
            pos_laje = 0
            altura_total = 0
            
            # Encontrar em qual posição está a laje
            for i in range(1, 6):
                laje_var = self.campos.get(f'laje_h{i}_{tipo_painel.lower()}')
                if laje_var and laje_var.get():
                    pos_laje = i
                    break
            
            if pos_laje == 0:
                return 0  # Retorna 0 se não encontrar laje
                
            # Agora vamos somar todas as alturas até a posição atual
            for i in range(1, pos_laje + 1):
                altura_var = self.campos.get(f'altura_h{i}_{tipo_painel.lower()}')
                if altura_var:
                    altura_str = altura_var.get().strip()
                    try:
                        altura = self.converter_para_float(altura_str)
                        if altura > 0:
                            altura_total += altura
                    except ValueError:
                        continue
                    
            self.log_mensagem(f"Altura acumulada até a laje (pos {pos_laje}): {altura_total}", "info")
            
            # Agora soma as alturas dos painéis acima da laje
            for i in range(pos_laje + 1, 6):
                altura_var = self.campos.get(f'altura_h{i}_{tipo_painel.lower()}')
                if altura_var:
                    altura_str = altura_var.get().strip()
                    try:
                        altura = self.converter_para_float(altura_str)
                        if altura > 0:
                            altura_total += altura
                            self.log_mensagem(f"Adicionando altura do painel H{i}: {altura}", "info")
                    except ValueError:
                        continue
            
            self.log_mensagem(f"Altura total final: {altura_total}", "info")
            return altura_total
        
        except Exception as e:
            self.log_mensagem(f"Erro ao calcular altura dos painéis acima da laje: {str(e)}", "erro")
            return 0

    def calcular_altura_ultimo_painel(self, tipo_painel):
        """
        Encontra a altura do último painel válido (H5, H4, H3, etc)
        """
        # Itera pelos painéis de cima para baixo (H5 até H1)
        for i in range(5, 0, -1):
            altura_var = self.campos.get(f'altura_h{i}_{tipo_painel.lower()}')
            if altura_var:
                altura_str = altura_var.get().strip()
                try:
                    altura = self.converter_para_float(altura_str)
                    if altura > 0:
                        return altura  # Retorna a altura do primeiro painel válido encontrado
                except ValueError:
                    continue
        return 0

    def calcular_altura_paineis_acima_laje(self, tipo_painel):
        """
        Calcula a soma de todas as alturas dos painéis e da laje
        Reconhece o formato especial 'X+Y' nos campos de altura
        """
        altura_total = 0
        
        # Somar todas as alturas dos painéis usando processar_valor_altura
        for i in range(1, 6):
            altura_var = self.campos.get(f'altura_h{i}_{tipo_painel.lower()}')
            if altura_var:
                altura_str = altura_var.get().strip()
                try:
                    if altura_str:  # Se há valor no campo
                        # Usar processar_valor_altura para reconhecer formato X+Y
                        altura_processada, _ = self.processar_valor_altura(altura_str)
                        if altura_processada > 0:
                            altura_total += altura_processada
                except (ValueError, TypeError):
                    continue
        
        return altura_total

    def calcular_posicao_abertura(self, tipo_painel, abertura_id):
        """
        Calcula a posição da abertura baseada no campo de posição
        """
        self.log_mensagem(f"Calculando posição para abertura {abertura_id} do painel {tipo_painel}", "info")
        
        # Obter o valor do campo de posição
        pos_entry = self.campos.get(f'abertura_{abertura_id}_pos_{tipo_painel.lower()}')
        self.log_mensagem(f"Campo de posição encontrado: {pos_entry is not None}", "info")
        
        if pos_entry:
            try:
                pos = self.converter_para_float(pos_entry.get())
                self.log_mensagem(f"Valor do campo de posição: {pos}", "info")
                
                if pos > 0:
                    # Calcular a altura total somando todos os campos
                    altura_total = 0
                    
                    # Somar as alturas dos painéis usando processar_valor_altura
                    for i in range(1, 6):
                        altura_var = self.campos.get(f'altura_h{i}_{tipo_painel.lower()}')
                        if altura_var:
                            try:
                                altura_str = altura_var.get().strip()
                                if altura_str:  # Se há valor no campo
                                    # Usar processar_valor_altura para reconhecer formato X+Y
                                    altura_processada, _ = self.processar_valor_altura(altura_str)
                                    if altura_processada > 0:
                                        altura_total += altura_processada
                            except (ValueError, TypeError):
                                continue
                    
                    self.log_mensagem(f"Altura total: {altura_total}, Posição final: {altura_total - pos}", "info")
                    return altura_total - pos
            except ValueError as e:
                self.log_mensagem(f"Erro ao converter posição: {str(e)}", "erro")
                pass

        # Se não houver posição válida, usa a distância especificada
        dist_entry = self.campos[f'abertura_{abertura_id}_dist_{tipo_painel.lower()}']
        try:
            dist = self.converter_para_float(dist_entry.get())
            self.log_mensagem(f"Usando distância: {dist}", "info")
            return dist
        except ValueError as e:
            self.log_mensagem(f"Erro ao converter distância: {str(e)}", "erro")
            return 0

    def criar_janela_configuracoes(self):
        """Cria uma janela para editar as configurações"""
        # Verificar se a janela já está aberta
        if hasattr(self, 'config_window') and self.config_window.winfo_exists():
            # Janela já está aberta, apenas recarregar e atualizar campos
            try:
                print(f"[DEBUG CONFIG] Janela já aberta, recarregando do arquivo: {self.config_manager.config_file}")
                print(f"[DEBUG CONFIG] Arquivo existe: {os.path.exists(self.config_manager.config_file)}")
                
                # Ler diretamente do arquivo para garantir que estamos usando os valores mais recentes
                import json
                if os.path.exists(self.config_manager.config_file):
                    with open(self.config_manager.config_file, 'r', encoding='utf-8') as f:
                        config_do_arquivo = json.load(f)
                    
                    # Debug: verificar valores de parafusos no arquivo
                    parafusos_arquivo_ab = config_do_arquivo.get("parafusos", {}).get("ab", {}).get("medida_fundo_primeiro_ab", "N/A")
                    parafusos_arquivo_cdefgh = config_do_arquivo.get("parafusos", {}).get("cdefgh", {}).get("medida_fundo_primeiro_cdefgh", "N/A")
                    print(f"[DEBUG CONFIG] Valores no ARQUIVO: AB={parafusos_arquivo_ab}, CDEFGH={parafusos_arquivo_cdefgh}")
                    
                    # Atualizar o config_manager com os valores do arquivo
                    self.config_manager.config = config_do_arquivo
                else:
                    # Se o arquivo não existe, usar load_config normal
                    self.config_manager.config = self.config_manager.load_config()
                
                self.config_manager.templates = self.config_manager.load_templates()
                
                # Debug: verificar valores após recarregar
                parafusos_config_ab = self.config_manager.config.get("parafusos", {}).get("ab", {}).get("medida_fundo_primeiro_ab", "N/A")
                parafusos_config_cdefgh = self.config_manager.config.get("parafusos", {}).get("cdefgh", {}).get("medida_fundo_primeiro_cdefgh", "N/A")
                print(f"[DEBUG CONFIG] Valores no CONFIG_MANAGER após recarregar: AB={parafusos_config_ab}, CDEFGH={parafusos_config_cdefgh}")
                
                # Atualizar todos os campos com os valores recarregados
                self._atualizar_todos_campos_configuracao()
                
                # Trazer janela para frente
                self.config_window.lift()
                self.config_window.focus_force()
                return
            except Exception as e:
                self.log_mensagem(f"Erro ao atualizar janela existente: {str(e)}", "erro")
        
        # Recarregar configurações do arquivo para garantir que os valores mais recentes sejam exibidos
        # Isso é importante quando os templates são carregados pelos roundbuttons INI/NOVA
        try:
            print(f"[DEBUG CONFIG] Recarregando configurações do arquivo: {self.config_manager.config_file}")
            print(f"[DEBUG CONFIG] Arquivo existe: {os.path.exists(self.config_manager.config_file)}")
            
            # Ler diretamente do arquivo para garantir que estamos usando os valores mais recentes
            # Isso evita qualquer cache que possa estar sendo usado pelo load_config()
            import json
            config_antes = self.config_manager.config.copy() if self.config_manager.config else {}
            
            if os.path.exists(self.config_manager.config_file):
                with open(self.config_manager.config_file, 'r', encoding='utf-8') as f:
                    config_do_arquivo = json.load(f)
                self.config_manager.config = config_do_arquivo
            else:
                # Se o arquivo não existe, usar load_config normal
                self.config_manager.config = self.config_manager.load_config()
            
            config_depois = self.config_manager.config.copy() if self.config_manager.config else {}
            
            # Debug: verificar valores de parafusos
            parafusos_antes_ab = config_antes.get("parafusos", {}).get("ab", {}).get("medida_fundo_primeiro_ab", "N/A")
            parafusos_depois_ab = config_depois.get("parafusos", {}).get("ab", {}).get("medida_fundo_primeiro_ab", "N/A")
            parafusos_antes_cdefgh = config_antes.get("parafusos", {}).get("cdefgh", {}).get("medida_fundo_primeiro_cdefgh", "N/A")
            parafusos_depois_cdefgh = config_depois.get("parafusos", {}).get("cdefgh", {}).get("medida_fundo_primeiro_cdefgh", "N/A")
            
            print(f"[DEBUG CONFIG] Parafusos AB - Antes: {parafusos_antes_ab}, Depois: {parafusos_depois_ab}")
            print(f"[DEBUG CONFIG] Parafusos CDEFGH - Antes: {parafusos_antes_cdefgh}, Depois: {parafusos_depois_cdefgh}")
            
            # Verificar se há discrepância
            if parafusos_antes_ab != parafusos_depois_ab or parafusos_antes_cdefgh != parafusos_depois_cdefgh:
                print(f"[DEBUG CONFIG] ⚠️ DISCREPÂNCIA: Valores mudaram após recarregar do arquivo!")
                print(f"[DEBUG CONFIG]   Isso pode indicar que o arquivo tem valores diferentes do ConfigManager em memória")
            else:
                print(f"[DEBUG CONFIG] ✅ Valores consistentes após recarregar")
            
            print(f"[DEBUG CONFIG] ========================================\n")
            
            # Também recarregar templates para garantir que a lista esteja atualizada
            self.config_manager.templates = self.config_manager.load_templates()
            print(f"[DEBUG CONFIG] Templates recarregados: {list(self.config_manager.templates.keys())}")
        except Exception as e:
            self.log_mensagem(f"Erro ao recarregar configurações: {str(e)}", "erro")
            import traceback
            traceback.print_exc()
        
        # Criar janela de configurações
        config_window = tk.Toplevel(self.root)
        config_window.title("Configurações")
        # Aumentar +50px na altura e trazer à frente
        try:
            config_window.update_idletasks()
            # Largura fixa 600, altura base 450 + 50 = 500
            # Preserva posição atual se já tiver geometry aplicada
            geo = config_window.geometry()
            width, height = 600, 500
            try:
                size, x_str, y_str = geo.split('+')
                config_window.geometry(f"{width}x{height}+{x_str}+{y_str}")
            except ValueError:
                config_window.geometry(f"{width}x{height}")
            config_window.deiconify()
            config_window.lift()
            config_window.attributes('-topmost', True)
            config_window.focus_force()
            config_window.attributes('-topmost', False)
        except Exception:
            config_window.geometry("600x500")
            try:
                config_window.lift()
                config_window.focus_force()
            except Exception:
                pass
        # Aumentado para acomodar a nova aba
        self.config_window = config_window  # Salvar referência para a janela
        
        # Criar notebook para abas
        notebook = ttk.Notebook(config_window)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Aba de Layers
        frame_layers = ttk.Frame(notebook)
        notebook.add(frame_layers, text='Layers')
        
        # Criar campos para layers
        ttk.Label(frame_layers, text="Layer Painéis:").grid(row=0, column=0, padx=5, pady=5)
        self.entry_paineis = ttk.Entry(frame_layers)
        self.entry_paineis.insert(0, self.config_manager.get_config("layers", "paineis_abcd") or "")
        self.entry_paineis.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(frame_layers, text="Layer Pé Direito:").grid(row=1, column=0, padx=5, pady=5)
        self.entry_pe_direito = ttk.Entry(frame_layers)
        self.entry_pe_direito.insert(0, self.config_manager.get_config("layers", "pe_direito") or "")
        self.entry_pe_direito.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame_layers, text="Layer Cotas:").grid(row=2, column=0, padx=5, pady=5)
        self.entry_cotas = ttk.Entry(frame_layers)
        self.entry_cotas.insert(0, self.config_manager.get_config("layers", "cotas") or "")
        self.entry_cotas.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(frame_layers, text="Layer Sarrafos:").grid(row=3, column=0, padx=5, pady=5)
        self.entry_sarrafos = ttk.Entry(frame_layers)
        self.entry_sarrafos.insert(0, self.config_manager.get_config("layers", "sarrafos") or "")
        self.entry_sarrafos.grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Label(frame_layers, text="Layer Nomenclatura:").grid(row=4, column=0, padx=5, pady=5)
        self.entry_nomenclatura = ttk.Entry(frame_layers)
        self.entry_nomenclatura.insert(0, self.config_manager.get_config("layers", "nomenclatura") or "")
        self.entry_nomenclatura.grid(row=4, column=1, padx=5, pady=5)
        
        ttk.Label(frame_layers, text="Layer Laje:").grid(row=5, column=0, padx=5, pady=5)
        self.entry_laje = ttk.Entry(frame_layers)
        self.entry_laje.insert(0, self.config_manager.get_config("layers", "laje") or "")
        self.entry_laje.grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(frame_layers, text="Layer Linhas Hidden:").grid(row=6, column=0, padx=5, pady=5)
        self.entry_linhas_hidden = ttk.Entry(frame_layers)
        self.entry_linhas_hidden.insert(0, self.config_manager.get_config("layers", "linhas_hidden") or "")
        self.entry_linhas_hidden.grid(row=6, column=1, padx=5, pady=5)
        
        ttk.Label(frame_layers, text="Hatch Laje:").grid(row=5, column=2, padx=5, pady=5)
        self.entry_hatch_laje = ttk.Entry(frame_layers)
        self.entry_hatch_laje.insert(0, self.config_manager.get_config("comandos", "hatches", "laje") or "HHHH")
        self.entry_hatch_laje.grid(row=5, column=3, padx=5, pady=5)
        
        # Aba de Blocos
        frame_blocks = ttk.Frame(notebook)
        notebook.add(frame_blocks, text='Blocos')
        
        # Criar campos para blocos
        ttk.Label(frame_blocks, text="Bloco Furação:").grid(row=0, column=0, padx=5, pady=5)
        self.entry_furacao = ttk.Entry(frame_blocks)
        self.entry_furacao.insert(0, self.config_manager.get_config("blocks", "furacao") or "")
        self.entry_furacao.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(frame_blocks, text="Bloco Split EE:").grid(row=1, column=0, padx=5, pady=5)
        self.entry_split_ee = ttk.Entry(frame_blocks)
        self.entry_split_ee.insert(0, self.config_manager.get_config("blocks", "split_ee") or "")
        self.entry_split_ee.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame_blocks, text="Bloco Split DD:").grid(row=2, column=0, padx=5, pady=5)
        self.entry_split_dd = ttk.Entry(frame_blocks)
        self.entry_split_dd.insert(0, self.config_manager.get_config("blocks", "split_dd") or "")
        self.entry_split_dd.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(frame_blocks, text="Bloco Moldura:").grid(row=3, column=0, padx=5, pady=5)
        self.entry_moldura = ttk.Entry(frame_blocks)
        self.entry_moldura.insert(0, self.config_manager.get_config("blocks", "moldura") or "")
        self.entry_moldura.grid(row=3, column=1, padx=5, pady=5)
        
        # Adicionar frame para numeração
        frame_numeracao = ttk.LabelFrame(frame_blocks, text="Numeração de Painéis")
        frame_numeracao.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Checkbox para ativar/desativar numeração
        self.var_numeracao = tk.BooleanVar(value=self.config_manager.get_config("blocks", "numeracao", "ativar") or False)
        ttk.Checkbutton(frame_numeracao, text="Ativar Numeração", variable=self.var_numeracao).grid(row=0, column=0, columnspan=2, padx=5, pady=2)
        
        # Campos para blocos de numeração
        self.entries_numeracao = {}
        blocos_numeracao = ['n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8', 'n9', 'n10', 'n11', 'n12', 'n13', 'n14', 'n15']
        
        # Criar duas colunas para os campos de numeração
        for i, num in enumerate(blocos_numeracao):
            coluna = 0 if i < 8 else 2  # Primeira coluna para n1-n8, segunda para n9-n15
            linha = (i % 8) + 1  # Reset da linha a cada 8 items
            
            ttk.Label(frame_numeracao, text=f"Bloco {num}:").grid(row=linha, column=coluna, padx=5, pady=2, sticky="e")
            entry = ttk.Entry(frame_numeracao, width=15)
            entry.insert(0, self.config_manager.get_config("blocks", "numeracao", num) or num)
            entry.grid(row=linha, column=coluna+1, padx=5, pady=2)
            self.entries_numeracao[num] = entry
        
        # Aba de Opções de Desenho
        frame_options = ttk.Frame(notebook)
        notebook.add(frame_options, text='Opções')
        
        # Campos para opções de desenho
        ttk.Label(frame_options, text="Fator de Zoom:").grid(row=0, column=0, padx=5, pady=5)
        self.entry_zoom = ttk.Entry(frame_options)
        self.entry_zoom.insert(0, str(self.config_manager.get_config("drawing_options", "zoom_factor") or "10"))
        self.entry_zoom.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(frame_options, text="Offset de Cota:").grid(row=1, column=0, padx=5, pady=5)
        self.entry_cota = ttk.Entry(frame_options)
        self.entry_cota.insert(0, str(self.config_manager.get_config("drawing_options", "cota_offset") or "15"))
        self.entry_cota.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame_options, text="Offset de Texto:").grid(row=2, column=0, padx=5, pady=5)
        self.entry_texto = ttk.Entry(frame_options)
        self.entry_texto.insert(0, str(self.config_manager.get_config("drawing_options", "texto_offset") or "20"))
        self.entry_texto.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(frame_options, text="Offset de Sarrafo:").grid(row=3, column=0, padx=5, pady=5)
        self.entry_sarrafo = ttk.Entry(frame_options)
        self.entry_sarrafo.insert(0, str(self.config_manager.get_config("drawing_options", "sarrafo_offset") or "7"))
        self.entry_sarrafo.grid(row=3, column=1, padx=5, pady=5)
        
        # Adicionar checkboxes para opções booleanas
        ttk.Label(frame_options, text="Cotas de Furação:").grid(row=4, column=0, columnspan=2, padx=5, pady=5)
        
        self.var_cota_vertical = tk.BooleanVar(value=self.config_manager.get_config("drawing_options", "cotas_furacao_vertical") or False)
        ttk.Checkbutton(frame_options, text="Vertical", variable=self.var_cota_vertical).grid(row=5, column=0, padx=5, pady=2)
        
        self.var_cota_horizontal = tk.BooleanVar(value=self.config_manager.get_config("drawing_options", "cotas_furacao_horizontal") or False)
        ttk.Checkbutton(frame_options, text="Horizontal", variable=self.var_cota_horizontal).grid(row=5, column=1, padx=5, pady=2)
        
        # Modo de sarrafos
        ttk.Label(frame_options, text="Modo de Sarrafos:").grid(row=6, column=0, padx=5, pady=5)
        self.modo_sarrafos = ttk.Combobox(frame_options, values=["Pline", "MLINE"])
        self.modo_sarrafos.set(self.config_manager.get_config("drawing_options", "modo_sarrafos") or "normal")
        self.modo_sarrafos.grid(row=6, column=1, padx=5, pady=5)
        
        # Checkbox para desenhar sarrafos C e D
        self.var_sarrafos_cd = tk.BooleanVar(value=self.config_manager.get_config("drawing_options", "desenhar_sarrafos_cd") or False)
        ttk.Checkbutton(frame_options, text="Desenhar Sarrafos C e D", variable=self.var_sarrafos_cd).grid(row=7, column=0, columnspan=2, padx=5, pady=5)
        
        # Linetypes dinâmicos
        ttk.Label(frame_options, text="Linetype Pé-direito:").grid(row=8, column=0, padx=5, pady=5)
        self.entry_linetype_pedireito = ttk.Entry(frame_options)
        self.entry_linetype_pedireito.insert(0, self.config_manager.get_config("drawing_options", "linetype_pedireito") or "DASHED")
        self.entry_linetype_pedireito.grid(row=8, column=1, padx=5, pady=5)

        ttk.Label(frame_options, text="Linetype Sarrafos Hidden:").grid(row=9, column=0, padx=5, pady=5)
        self.entry_linetype_sarrafos = ttk.Entry(frame_options)
        self.entry_linetype_sarrafos.insert(0, self.config_manager.get_config("drawing_options", "linetype_sarrafos_hidden") or "DASHED")
        self.entry_linetype_sarrafos.grid(row=9, column=1, padx=5, pady=5)
        
        # Aba de Comandos
        frame_comandos = ttk.Frame(notebook)
        notebook.add(frame_comandos, text='Comandos')
        
        # Frame para comandos de aberturas
        frame_aberturas = ttk.LabelFrame(frame_comandos, text="Comandos de Aberturas", padding="10")
        frame_aberturas.pack(fill="x", pady=5)
        
        # Campos para comandos de aberturas
        self.entries_comandos = {}
        comandos = [
            ("abv", "Comando ABV:"),
            ("abve", "Comando ABVE:"),
            ("abve12", "Comando ABVE12:"),
            ("abvd", "Comando ABVD:"),
            ("abvd12", "Comando ABVD12:"),
            ("ABVLJ", "Comando ABVLJ:")
        ]
        
        for i, (comando, label) in enumerate(comandos):
            ttk.Label(frame_aberturas, text=label).grid(row=i, column=0, padx=5, pady=2, sticky="e")
            entry = ttk.Entry(frame_aberturas, width=15)
            entry.insert(0, self.config_manager.get_config("comandos", "aberturas", comando) or comando)
            entry.grid(row=i, column=1, padx=5, pady=2)
            self.entries_comandos[comando] = entry
        
        # Aba para Templates
        frame_templates = ttk.Frame(notebook)
        notebook.add(frame_templates, text='Templates')
        
        # Frame para gerenciar templates
        manage_frame = ttk.LabelFrame(frame_templates, text="Gerenciar Templates", padding="10")
        manage_frame.pack(fill="x", pady=5)
        
        # Entrada para nome do template
        ttk.Label(manage_frame, text="Nome do Template:").pack(anchor='w')
        self.template_name_entry = ttk.Entry(manage_frame)
        self.template_name_entry.pack(fill="x", pady=2)
        
        # Botões de ação
        btn_frame = ttk.Frame(manage_frame)
        btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="Salvar Template", command=lambda: self.salvar_template(self.template_name_entry.get())).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Carregar Template", command=lambda: self.carregar_template(self.template_name_entry.get())).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Deletar Template", command=lambda: self.deletar_template(self.template_name_entry.get())).pack(side="left", padx=2)
        
        # Lista de templates existentes
        list_frame = ttk.LabelFrame(frame_templates, text="Templates Salvos", padding="10")
        list_frame.pack(fill="both", expand=True, pady=5)
        
        self.template_list = tk.Listbox(list_frame)
        self.template_list.pack(fill="both", expand=True)
        self.atualizar_lista_templates()
        
        # Vincular evento de clique na lista
        self.template_list.bind("<<ListboxSelect>>", self.selecionar_template)
        
        # Aba Parafusos
        frame_parafusos = ttk.Frame(notebook)
        notebook.add(frame_parafusos, text='Parafusos')
        
        # Frame principal com scroll
        canvas_parafusos = tk.Canvas(frame_parafusos)
        scrollbar_parafusos = ttk.Scrollbar(frame_parafusos, orient="vertical", command=canvas_parafusos.yview)
        scrollable_frame_parafusos = ttk.Frame(canvas_parafusos)
        
        scrollable_frame_parafusos.bind(
            "<Configure>",
            lambda e: canvas_parafusos.configure(scrollregion=canvas_parafusos.bbox("all"))
        )
        
        canvas_parafusos.create_window((0, 0), window=scrollable_frame_parafusos, anchor="nw")
        canvas_parafusos.configure(yscrollcommand=scrollbar_parafusos.set)
        
        canvas_parafusos.pack(side="left", fill="both", expand=True)
        scrollbar_parafusos.pack(side="right", fill="y")
        
        # Grupo 1: Painéis A-B
        frame_ab = ttk.LabelFrame(scrollable_frame_parafusos, text="Painéis A-B", padding="10")
        frame_ab.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Cabeçalho da tabela para A-B
        ttk.Label(frame_ab, text="Medida", font=("Arial", 9, "bold")).grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Label(frame_ab, text="Valor (cm)", font=("Arial", 9, "bold")).grid(row=0, column=1, padx=5, pady=2)
        
        # Campos para A-B (10 campos em 2 colunas)
        medidas_ab = [
            ("Fundo até 1º", "medida_fundo_primeiro_ab", "30"),
            ("1º ao 2º", "medida_1_2_ab", "50"),
            ("2º ao 3º", "medida_2_3_ab", "55"),
            ("3º ao 4º", "medida_3_4_ab", "55"),
            ("4º ao 5º", "medida_4_5_ab", "55"),
            ("5º ao 6º", "medida_5_6_ab", "55"),
            ("6º ao 7º", "medida_6_7_ab", "55"),
            ("7º ao 8º", "medida_7_8_ab", "55"),
            ("8º ao 9º", "medida_8_9_ab", "55"),
            ("9º ao 10º", "medida_9_10_ab", "55")
        ]
        
        self.entries_parafusos_ab = {}
        for i, (label, key, default) in enumerate(medidas_ab):
            row = (i // 2) + 1
            col = (i % 2) * 2
            
            ttk.Label(frame_ab, text=f"{label}:").grid(row=row, column=col, padx=5, pady=2, sticky="e")
            entry = ttk.Entry(frame_ab, width=15)
            entry.insert(0, str(self.config_manager.get_config("parafusos", "ab", key) or default))
            entry.grid(row=row, column=col+1, padx=5, pady=2)
            self.entries_parafusos_ab[key] = entry
        
        # Grupo 2: Painéis C-D-E-F-G-H
        frame_cdefgh = ttk.LabelFrame(scrollable_frame_parafusos, text="Painéis C-D-E-F-G-H", padding="10")
        frame_cdefgh.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Cabeçalho da tabela para C-D-E-F-G-H
        ttk.Label(frame_cdefgh, text="Medida", font=("Arial", 9, "bold")).grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Label(frame_cdefgh, text="Valor (cm)", font=("Arial", 9, "bold")).grid(row=0, column=1, padx=5, pady=2)
        
        # Campos para C-D-E-F-G-H (10 campos em 2 colunas)
        medidas_cdefgh = [
            ("Fundo até 1º", "medida_fundo_primeiro_cdefgh", "30"),
            ("1º ao 2º", "medida_1_2_cdefgh", "50"),
            ("2º ao 3º", "medida_2_3_cdefgh", "55"),
            ("3º ao 4º", "medida_3_4_cdefgh", "55"),
            ("4º ao 5º", "medida_4_5_cdefgh", "55"),
            ("5º ao 6º", "medida_5_6_cdefgh", "55"),
            ("6º ao 7º", "medida_6_7_cdefgh", "55"),
            ("7º ao 8º", "medida_7_8_cdefgh", "55"),
            ("8º ao 9º", "medida_8_9_cdefgh", "55"),
            ("9º ao 10º", "medida_9_10_cdefgh", "55")
        ]
        
        self.entries_parafusos_cdefgh = {}
        for i, (label, key, default) in enumerate(medidas_cdefgh):
            row = (i // 2) + 1
            col = (i % 2) * 2
            
            ttk.Label(frame_cdefgh, text=f"{label}:").grid(row=row, column=col, padx=5, pady=2, sticky="e")
            entry = ttk.Entry(frame_cdefgh, width=15)
            entry.insert(0, str(self.config_manager.get_config("parafusos", "cdefgh", key) or default))
            entry.grid(row=row, column=col+1, padx=5, pady=2)
            self.entries_parafusos_cdefgh[key] = entry
        
        # Função auxiliar para atualizar campos de parafusos
        def atualizar_campos_parafusos():
            """Atualiza os campos de parafusos com os valores atuais do config_manager"""
            # Atualizar campos A-B
            if hasattr(self, 'entries_parafusos_ab'):
                medidas_ab_keys = ["medida_fundo_primeiro_ab", "medida_1_2_ab", "medida_2_3_ab", "medida_3_4_ab", 
                                   "medida_4_5_ab", "medida_5_6_ab", "medida_6_7_ab", "medida_7_8_ab", 
                                   "medida_8_9_ab", "medida_9_10_ab"]
                defaults_ab = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                for key, default in zip(medidas_ab_keys, defaults_ab):
                    if key in self.entries_parafusos_ab:
                        self.entries_parafusos_ab[key].delete(0, tk.END)
                        self.entries_parafusos_ab[key].insert(0, str(self.config_manager.get_config("parafusos", "ab", key) or default))
            
            # Atualizar campos C-D-E-F-G-H
            if hasattr(self, 'entries_parafusos_cdefgh'):
                medidas_cdefgh_keys = ["medida_fundo_primeiro_cdefgh", "medida_1_2_cdefgh", "medida_2_3_cdefgh", "medida_3_4_cdefgh",
                                      "medida_4_5_cdefgh", "medida_5_6_cdefgh", "medida_6_7_cdefgh", "medida_7_8_cdefgh",
                                      "medida_8_9_cdefgh", "medida_9_10_cdefgh"]
                defaults_cdefgh = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                for key, default in zip(medidas_cdefgh_keys, defaults_cdefgh):
                    if key in self.entries_parafusos_cdefgh:
                        self.entries_parafusos_cdefgh[key].delete(0, tk.END)
                        self.entries_parafusos_cdefgh[key].insert(0, str(self.config_manager.get_config("parafusos", "cdefgh", key) or default))
        
        # Atualizar campos de parafusos após criar (garantir que usam valores recarregados)
        atualizar_campos_parafusos()
        
        # Configurar scroll do canvas
        def on_mousewheel(event):
            canvas_parafusos.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas_parafusos.bind_all("<MouseWheel>", on_mousewheel)
        
        # Criar frame para botões de ação
        frame_botoes = ttk.Frame(config_window)
        frame_botoes.pack(fill='x', padx=10, pady=10)
        
        # Função para salvar configurações
        def salvar_configuracoes():
            try:
                # Atualizar configurações com os valores dos campos
                config = {
                    "layers": {
                        "paineis_abcd": self.entry_paineis.get().strip(),
                        "pe_direito": self.entry_pe_direito.get().strip(),
                        "cotas": self.entry_cotas.get().strip(),
                        "sarrafos": self.entry_sarrafos.get().strip(),
                        "nomenclatura": self.entry_nomenclatura.get().strip(),
                        "laje": self.entry_laje.get().strip(),
                        "textos_titulos": self.config_manager.get_config("layers", "textos_titulos") or "",
                        "linhas_hidden": self.entry_linhas_hidden.get().strip()
                    },
                    "blocks": {
                        "furacao": self.entry_furacao.get().strip(),
                        "split_ee": self.entry_split_ee.get().strip(),
                        "split_dd": self.entry_split_dd.get().strip(),
                        "moldura": self.entry_moldura.get().strip(),
                        "numeracao": {
                            "ativar": self.var_numeracao.get(),
                            "n1": self.entries_numeracao['n1'].get().strip(),
                            "n2": self.entries_numeracao['n2'].get().strip(),
                            "n3": self.entries_numeracao['n3'].get().strip(),
                            "n4": self.entries_numeracao['n4'].get().strip(),
                            "n5": self.entries_numeracao['n5'].get().strip(),
                            "n6": self.entries_numeracao['n6'].get().strip(),
                            "n7": self.entries_numeracao['n7'].get().strip(),
                            "n8": self.entries_numeracao['n8'].get().strip(),
                            "n9": self.entries_numeracao['n9'].get().strip(),
                            "n10": self.entries_numeracao['n10'].get().strip(),
                            "n11": self.entries_numeracao['n11'].get().strip(),
                            "n12": self.entries_numeracao['n12'].get().strip(),
                            "n13": self.entries_numeracao['n13'].get().strip(),
                            "n14": self.entries_numeracao['n14'].get().strip(),
                            "n15": self.entries_numeracao['n15'].get().strip()
                        }
                    },
                    "comandos": {
                        "aberturas": {
                            "abv": self.entries_comandos['abv'].get().strip(),
                            "abve": self.entries_comandos['abve'].get().strip(),
                            "abve12": self.entries_comandos['abve12'].get().strip(),
                            "abvd": self.entries_comandos['abvd'].get().strip(),
                            "abvd12": self.entries_comandos['abvd12'].get().strip(),
                            "ABVLJ": self.entries_comandos['ABVLJ'].get().strip()
                        },
                        "hatches": {
                            "laje": self.entry_hatch_laje.get().strip()
                        }
                    },
                    "drawing_options": {
                        "zoom_factor": self.converter_para_float(self.entry_zoom.get() or "10"),
                        "cota_offset": self.converter_para_float(self.entry_cota.get() or "15"),
                        "texto_offset": self.converter_para_float(self.entry_texto.get() or "20"),
                        "sarrafo_offset": self.converter_para_float(self.entry_sarrafo.get() or "7"),
                        "cotas_furacao_vertical": self.var_cota_vertical.get(),
                        "cotas_furacao_horizontal": self.var_cota_horizontal.get(),
                        "modo_sarrafos": self.modo_sarrafos.get(),
                        "desenhar_sarrafos_cd": self.var_sarrafos_cd.get(),
                        "espacamento_base": self.config_manager.get_config("drawing_options", "espacamento_base") or 30,
                        "espacamento_vertical": self.config_manager.get_config("drawing_options", "espacamento_vertical") or 50,
                        "espacamento_parafusos": self.config_manager.get_config("drawing_options", "espacamento_parafusos") or 50,
                        "offset_parafuso": self.config_manager.get_config("drawing_options", "offset_parafuso") or 24,
                        "offset_moldura": self.config_manager.get_config("drawing_options", "offset_moldura") or 38,
                        "offset_texto_info": self.config_manager.get_config("drawing_options", "offset_texto_info") or {"x": 30, "y": 680},
                        "offset_painel": self.config_manager.get_config("drawing_options", "offset_painel") or {"inicial": 115, "entre_paineis": 115},
                        "linetype_pedireito": self.entry_linetype_pedireito.get().strip() or "DASHED",
                        "linetype_sarrafos_hidden": self.entry_linetype_sarrafos.get().strip() or "DASHED"
                    },
                    "parafusos": {
                        "ab": {},
                        "cdefgh": {}
                    }
                }
                
                # Salvar medidas A-B
                print(f"[DEBUG SALVAR CONFIG] Coletando valores de parafusos AB da UI...")
                if hasattr(self, 'entries_parafusos_ab'):
                    medidas_ab_keys = ["medida_fundo_primeiro_ab", "medida_1_2_ab", "medida_2_3_ab", "medida_3_4_ab", 
                                       "medida_4_5_ab", "medida_5_6_ab", "medida_6_7_ab", "medida_7_8_ab", 
                                       "medida_8_9_ab", "medida_9_10_ab"]
                    defaults_ab = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                    valores_ab_coletados = {}
                    for key, default in zip(medidas_ab_keys, defaults_ab):
                        if key in self.entries_parafusos_ab:
                            valor_ui = self.entries_parafusos_ab[key].get().strip()
                            valor_final = self.converter_para_float(valor_ui or default)
                            config["parafusos"]["ab"][key] = valor_final
                            valores_ab_coletados[key] = valor_final
                            print(f"[DEBUG SALVAR CONFIG]   {key}: '{valor_ui}' -> {valor_final}")
                        else:
                            valor_final = self.converter_para_float(default)
                            config["parafusos"]["ab"][key] = valor_final
                            valores_ab_coletados[key] = valor_final
                            print(f"[DEBUG SALVAR CONFIG]   {key}: (campo não existe) -> {valor_final} (default)")
                    print(f"[DEBUG SALVAR CONFIG] ✅ Valores AB coletados: {valores_ab_coletados}")
                else:
                    print(f"[DEBUG SALVAR CONFIG] ⚠️ entries_parafusos_ab não existe!")
                
                # Salvar medidas C-D-E-F-G-H
                print(f"[DEBUG SALVAR CONFIG] Coletando valores de parafusos CDEFGH da UI...")
                if hasattr(self, 'entries_parafusos_cdefgh'):
                    medidas_cdefgh_keys = ["medida_fundo_primeiro_cdefgh", "medida_1_2_cdefgh", "medida_2_3_cdefgh", "medida_3_4_cdefgh",
                                          "medida_4_5_cdefgh", "medida_5_6_cdefgh", "medida_6_7_cdefgh", "medida_7_8_cdefgh",
                                          "medida_8_9_cdefgh", "medida_9_10_cdefgh"]
                    defaults_cdefgh = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                    valores_cdefgh_coletados = {}
                    for key, default in zip(medidas_cdefgh_keys, defaults_cdefgh):
                        if key in self.entries_parafusos_cdefgh:
                            valor_ui = self.entries_parafusos_cdefgh[key].get().strip()
                            valor_final = self.converter_para_float(valor_ui or default)
                            config["parafusos"]["cdefgh"][key] = valor_final
                            valores_cdefgh_coletados[key] = valor_final
                            print(f"[DEBUG SALVAR CONFIG]   {key}: '{valor_ui}' -> {valor_final}")
                        else:
                            valor_final = self.converter_para_float(default)
                            config["parafusos"]["cdefgh"][key] = valor_final
                            valores_cdefgh_coletados[key] = valor_final
                            print(f"[DEBUG SALVAR CONFIG]   {key}: (campo não existe) -> {valor_final} (default)")
                    print(f"[DEBUG SALVAR CONFIG] ✅ Valores CDEFGH coletados: {valores_cdefgh_coletados}")
                else:
                    print(f"[DEBUG SALVAR CONFIG] ⚠️ entries_parafusos_cdefgh não existe!")
                
                # Debug: mostrar estrutura completa de parafusos antes de salvar
                print(f"[DEBUG SALVAR CONFIG] Estrutura completa de parafusos a ser salva:")
                print(f"[DEBUG SALVAR CONFIG] {json.dumps(config.get('parafusos', {}), indent=2)}")
                
                # Salvar configurações
                print(f"[DEBUG SALVAR CONFIG] Atualizando config_manager.config com os valores coletados...")
                self.config_manager.config = config
                
                # Verificar valores antes de salvar
                ab_val = self.config_manager.get_config("parafusos", "ab", "medida_fundo_primeiro_ab")
                cdefgh_val = self.config_manager.get_config("parafusos", "cdefgh", "medida_fundo_primeiro_cdefgh")
                print(f"[DEBUG SALVAR CONFIG] Valores no config_manager antes de save_config(): AB={ab_val}, CDEFGH={cdefgh_val}")
                
                self.config_manager.save_config()
                
                # Verificar valores após salvar
                ab_val_apos = self.config_manager.get_config("parafusos", "ab", "medida_fundo_primeiro_ab")
                cdefgh_val_apos = self.config_manager.get_config("parafusos", "cdefgh", "medida_fundo_primeiro_cdefgh")
                print(f"[DEBUG SALVAR CONFIG] Valores no config_manager após save_config(): AB={ab_val_apos}, CDEFGH={cdefgh_val_apos}")
                
                # Atualizar configurações na interface
                self.carregar_configuracoes()
                
                # Fechar janela
                config_window.destroy()
                
                # Mostrar mensagem de sucesso
                messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar configurações: {str(e)}")
        
        # Adicionar botões
        ttk.Button(frame_botoes, text="Salvar", command=salvar_configuracoes).pack(side='right', padx=5)
        ttk.Button(frame_botoes, text="Cancelar", command=config_window.destroy).pack(side='right', padx=5)
    
    def deletar_template(self, template_name):
        """Deleta um template existente."""
        if template_name in self.config_manager.templates:
            self.config_manager.delete_template(template_name)
            self.atualizar_lista_templates()
            messagebox.showinfo("Sucesso", f"Template '{template_name}' removido!")
        else:
            messagebox.showerror("Erro", "Template não encontrado")
    
    def atualizar_lista_templates(self):
        """Atualiza a lista de templates na interface."""
        if hasattr(self, 'template_list'):
            self.template_list.delete(0, tk.END)
            for template in self.config_manager.templates:
                self.template_list.insert(tk.END, template)
    
    def calcular_espacamento_paineis(self, comprimento):
        """Calcula o espaçamento entre painéis baseado no comprimento do pilar"""
        # Para moldura padrão, usar cálculo baseado no comprimento
        if comprimento > 300:
            return 140
        elif 250 < comprimento <= 300:
            return 180
        elif 200 < comprimento <= 250:
            return 200
        elif 150 < comprimento <= 200:
            return 230
        elif 100 < comprimento <= 150:
            return 270
        else:  # comprimento <= 100
            return 300
    
    def selecionar_template(self, event):
        """Seleciona um template da lista."""
        if hasattr(self, 'template_list'):
            selection = self.template_list.curselection()
            if selection:
                template_name = self.template_list.get(selection[0])
                self.template_name_entry.delete(0, tk.END)
                self.template_name_entry.insert(0, template_name)

    def salvar_template(self, template_name):
        """Salva o template atual com o nome especificado."""
        if template_name:
            # IMPORTANTE: Coletar valores da UI antes de salvar o template
            # Isso garante que os valores da aba "Parafusos" sejam incluídos
            config_para_template = copy.deepcopy(self.config_manager.config)
            
            # Sempre tentar coletar valores da UI se a janela estiver aberta
            if hasattr(self, 'config_window') and self.config_window.winfo_exists():
                try:
                    print(f"[DEBUG TEMPLATE] Iniciando salvamento do template '{template_name}'")
                    print(f"[DEBUG TEMPLATE] Config inicial tem 'parafusos': {'parafusos' in config_para_template}")
                    
                    # Garantir que a seção parafusos existe
                    if "parafusos" not in config_para_template:
                        config_para_template["parafusos"] = {"ab": {}, "cdefgh": {}}
                    if "ab" not in config_para_template["parafusos"]:
                        config_para_template["parafusos"]["ab"] = {}
                    if "cdefgh" not in config_para_template["parafusos"]:
                        config_para_template["parafusos"]["cdefgh"] = {}
                    
                    # Coletar valores de parafusos da UI se os campos existirem
                    if hasattr(self, 'entries_parafusos_ab') and self.entries_parafusos_ab:
                        print(f"[DEBUG TEMPLATE] Coletando valores de parafusos AB da UI...")
                        medidas_ab_keys = ["medida_fundo_primeiro_ab", "medida_1_2_ab", "medida_2_3_ab", "medida_3_4_ab", 
                                           "medida_4_5_ab", "medida_5_6_ab", "medida_6_7_ab", "medida_7_8_ab", 
                                           "medida_8_9_ab", "medida_9_10_ab"]
                        defaults_ab = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                        valores_coletados_ab = {}
                        for key, default in zip(medidas_ab_keys, defaults_ab):
                            if key in self.entries_parafusos_ab:
                                valor_ui = self.entries_parafusos_ab[key].get().strip()
                                valor_final = self.converter_para_float(valor_ui or default)
                                config_para_template["parafusos"]["ab"][key] = valor_final
                                valores_coletados_ab[key] = valor_final
                            else:
                                # Se o campo não existe, usar valor do config ou default
                                valor_existente = config_para_template["parafusos"]["ab"].get(key)
                                if valor_existente is None:
                                    valor_final = self.converter_para_float(default)
                                    config_para_template["parafusos"]["ab"][key] = valor_final
                                valores_coletados_ab[key] = config_para_template["parafusos"]["ab"].get(key, self.converter_para_float(default))
                        print(f"[DEBUG TEMPLATE] Valores AB coletados: {valores_coletados_ab}")
                    else:
                        print(f"[DEBUG TEMPLATE] ⚠️ entries_parafusos_ab não existe ou está vazio!")
                        # Garantir valores padrão se não conseguir coletar da UI
                        if not config_para_template["parafusos"]["ab"]:
                            medidas_ab_keys = ["medida_fundo_primeiro_ab", "medida_1_2_ab", "medida_2_3_ab", "medida_3_4_ab", 
                                               "medida_4_5_ab", "medida_5_6_ab", "medida_6_7_ab", "medida_7_8_ab", 
                                               "medida_8_9_ab", "medida_9_10_ab"]
                            defaults_ab = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                            for key, default in zip(medidas_ab_keys, defaults_ab):
                                if key not in config_para_template["parafusos"]["ab"]:
                                    config_para_template["parafusos"]["ab"][key] = self.converter_para_float(default)
                    
                    if hasattr(self, 'entries_parafusos_cdefgh') and self.entries_parafusos_cdefgh:
                        print(f"[DEBUG TEMPLATE] Coletando valores de parafusos CDEFGH da UI...")
                        medidas_cdefgh_keys = ["medida_fundo_primeiro_cdefgh", "medida_1_2_cdefgh", "medida_2_3_cdefgh", "medida_3_4_cdefgh",
                                              "medida_4_5_cdefgh", "medida_5_6_cdefgh", "medida_6_7_cdefgh", "medida_7_8_cdefgh",
                                              "medida_8_9_cdefgh", "medida_9_10_cdefgh"]
                        defaults_cdefgh = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                        valores_coletados_cdefgh = {}
                        for key, default in zip(medidas_cdefgh_keys, defaults_cdefgh):
                            if key in self.entries_parafusos_cdefgh:
                                valor_ui = self.entries_parafusos_cdefgh[key].get().strip()
                                valor_final = self.converter_para_float(valor_ui or default)
                                config_para_template["parafusos"]["cdefgh"][key] = valor_final
                                valores_coletados_cdefgh[key] = valor_final
                            else:
                                # Se o campo não existe, usar valor do config ou default
                                valor_existente = config_para_template["parafusos"]["cdefgh"].get(key)
                                if valor_existente is None:
                                    valor_final = self.converter_para_float(default)
                                    config_para_template["parafusos"]["cdefgh"][key] = valor_final
                                valores_coletados_cdefgh[key] = config_para_template["parafusos"]["cdefgh"].get(key, self.converter_para_float(default))
                        print(f"[DEBUG TEMPLATE] Valores CDEFGH coletados: {valores_coletados_cdefgh}")
                    else:
                        print(f"[DEBUG TEMPLATE] ⚠️ entries_parafusos_cdefgh não existe ou está vazio!")
                        # Garantir valores padrão se não conseguir coletar da UI
                        if not config_para_template["parafusos"]["cdefgh"]:
                            medidas_cdefgh_keys = ["medida_fundo_primeiro_cdefgh", "medida_1_2_cdefgh", "medida_2_3_cdefgh", "medida_3_4_cdefgh",
                                                  "medida_4_5_cdefgh", "medida_5_6_cdefgh", "medida_6_7_cdefgh", "medida_7_8_cdefgh",
                                                  "medida_8_9_cdefgh", "medida_9_10_cdefgh"]
                            defaults_cdefgh = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                            for key, default in zip(medidas_cdefgh_keys, defaults_cdefgh):
                                if key not in config_para_template["parafusos"]["cdefgh"]:
                                    config_para_template["parafusos"]["cdefgh"][key] = self.converter_para_float(default)
                    
                    # Debug: verificar valores coletados
                    if "parafusos" in config_para_template:
                        ab_val = config_para_template["parafusos"].get("ab", {}).get("medida_fundo_primeiro_ab", "N/A")
                        cdefgh_val = config_para_template["parafusos"].get("cdefgh", {}).get("medida_fundo_primeiro_cdefgh", "N/A")
                        print(f"[DEBUG TEMPLATE] ✅ Template '{template_name}' preparado com parafusos AB={ab_val}, CDEFGH={cdefgh_val}")
                        print(f"[DEBUG TEMPLATE] Estrutura completa de parafusos: {json.dumps(config_para_template.get('parafusos', {}), indent=2)}")
                    else:
                        print(f"[DEBUG TEMPLATE] ⚠️ Seção 'parafusos' não encontrada no config após coleta!")
                    
                except Exception as e:
                    print(f"[DEBUG TEMPLATE] ❌ Erro ao coletar valores da UI: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # Janela não está aberta, usar config atual (que já deve ter os valores se foram salvos antes)
                print(f"[DEBUG TEMPLATE] Janela de configurações não está aberta, usando config atual")
                # Garantir que a seção parafusos existe mesmo se a janela não estiver aberta
                if "parafusos" not in config_para_template:
                    config_para_template["parafusos"] = {"ab": {}, "cdefgh": {}}
                if "ab" not in config_para_template["parafusos"]:
                    config_para_template["parafusos"]["ab"] = {}
                if "cdefgh" not in config_para_template["parafusos"]:
                    config_para_template["parafusos"]["cdefgh"] = {}
            
            # Usar a configuração preparada
            config_final = config_para_template
            
            # Salvar o template e obter o nome final usado
            nome_original = template_name
            self.config_manager.save_template(template_name, config_final)
            
            # Verificar se o nome foi alterado (adicionado sufixo)
            if nome_original in self.config_manager.templates:
                # O nome original foi mantido
                nome_final = nome_original
            else:
                # Procurar pelo template com sufixo
                for nome_template in self.config_manager.templates.keys():
                    if nome_template.startswith(nome_original + "."):
                        nome_final = nome_template
                        break
                else:
                    nome_final = nome_original
            
            self.atualizar_lista_templates()
            
            if nome_final == nome_original:
                messagebox.showinfo("Sucesso", f"Template '{nome_final}' salvo com sucesso!")
            else:
                messagebox.showinfo("Sucesso", f"Template '{nome_original}' já existia. Salvo como '{nome_final}'!")
        else:
            messagebox.showerror("Erro", "Digite um nome para o template")
    
    def carregar_template(self, template_name):
        """Carrega um template salvo para a configuração atual."""
        print(f"\n{'='*80}")
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL] ========================================")
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL] Carregando template '{template_name}' MANUALMENTE")
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL] ========================================")
        
        # Informações do arquivo de templates
        templates_file = self.config_manager.templates_file
        templates_path_abs = os.path.abspath(templates_file) if templates_file else "N/A"
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL] Arquivo de templates:")
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Nome: {os.path.basename(templates_file) if templates_file else 'N/A'}")
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Path completo: {templates_path_abs}")
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Arquivo existe: {os.path.exists(templates_path_abs) if templates_file else False}")
        
        # Informações do arquivo de configuração
        config_file = self.config_manager.config_file
        config_path_abs = os.path.abspath(config_file) if config_file else "N/A"
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL] Arquivo de configuração:")
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Nome: {os.path.basename(config_file) if config_file else 'N/A'}")
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Path completo: {config_path_abs}")
        print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Arquivo existe: {os.path.exists(config_path_abs) if config_file else False}")
        
        if template_name in self.config_manager.templates:
            # Carrega o template para a configuração atual
            template_config = self.config_manager.templates[template_name].copy()
            
            print(f"[DEBUG CARREGAR TEMPLATE MANUAL] Template '{template_name}' encontrado em config_manager.templates")
            print(f"[DEBUG CARREGAR TEMPLATE MANUAL] Estrutura do template carregado: {list(template_config.keys())}")
            
            # Garantir que a seção "parafusos" exista (para compatibilidade com templates antigos)
            if "parafusos" not in template_config:
                template_config["parafusos"] = {
                    "ab": {
                        "medida_fundo_primeiro_ab": 30,
                        "medida_1_2_ab": 50,
                        "medida_2_3_ab": 55,
                        "medida_3_4_ab": 55,
                        "medida_4_5_ab": 55,
                        "medida_5_6_ab": 55,
                        "medida_6_7_ab": 55,
                        "medida_7_8_ab": 55,
                        "medida_8_9_ab": 55,
                        "medida_9_10_ab": 55
                    },
                    "cdefgh": {
                        "medida_fundo_primeiro_cdefgh": 30,
                        "medida_1_2_cdefgh": 50,
                        "medida_2_3_cdefgh": 55,
                        "medida_3_4_cdefgh": 55,
                        "medida_4_5_cdefgh": 55,
                        "medida_5_6_cdefgh": 55,
                        "medida_6_7_cdefgh": 55,
                        "medida_7_8_cdefgh": 55,
                        "medida_8_9_cdefgh": 55,
                        "medida_9_10_cdefgh": 55
                    }
                }
            else:
                # Migrar templates antigos para nova estrutura
                if "ab" not in template_config["parafusos"]:
                    # Template antigo - migrar para nova estrutura
                    old_config = template_config["parafusos"]
                    template_config["parafusos"] = {
                        "ab": {
                            "medida_fundo_primeiro_ab": old_config.get("medida_fundo_primeiro", 30),
                            "medida_1_2_ab": old_config.get("medida_1_2", 50),
                            "medida_2_3_ab": old_config.get("medida_2_3", 55),
                            "medida_3_4_ab": old_config.get("medida_3_4", 55),
                            "medida_4_5_ab": old_config.get("medida_4_5", 55),
                            "medida_5_6_ab": 55,
                            "medida_6_7_ab": 55,
                            "medida_7_8_ab": 55,
                            "medida_8_9_ab": 55,
                            "medida_9_10_ab": 55
                        },
                        "cdefgh": {
                            "medida_fundo_primeiro_cdefgh": old_config.get("medida_fundo_primeiro", 30),
                            "medida_1_2_cdefgh": old_config.get("medida_1_2", 50),
                            "medida_2_3_cdefgh": old_config.get("medida_2_3", 55),
                            "medida_3_4_cdefgh": old_config.get("medida_3_4", 55),
                            "medida_4_5_cdefgh": old_config.get("medida_4_5", 55),
                            "medida_5_6_cdefgh": 55,
                            "medida_6_7_cdefgh": 55,
                            "medida_7_8_cdefgh": 55,
                            "medida_8_9_cdefgh": 55,
                            "medida_9_10_cdefgh": 55
                        }
                    }
                # Garantir que ambos os grupos existam
                if "ab" not in template_config["parafusos"]:
                    template_config["parafusos"]["ab"] = {
                        "medida_fundo_primeiro_ab": 30, "medida_1_2_ab": 50, "medida_2_3_ab": 55,
                        "medida_3_4_ab": 55, "medida_4_5_ab": 55, "medida_5_6_ab": 55,
                        "medida_6_7_ab": 55, "medida_7_8_ab": 55, "medida_8_9_ab": 55, "medida_9_10_ab": 55
                    }
                if "cdefgh" not in template_config["parafusos"]:
                    template_config["parafusos"]["cdefgh"] = {
                        "medida_fundo_primeiro_cdefgh": 30, "medida_1_2_cdefgh": 50, "medida_2_3_cdefgh": 55,
                        "medida_3_4_cdefgh": 55, "medida_4_5_cdefgh": 55, "medida_5_6_cdefgh": 55,
                        "medida_6_7_cdefgh": 55, "medida_7_8_cdefgh": 55, "medida_8_9_cdefgh": 55, "medida_9_10_cdefgh": 55
                    }
            
            # Aplicar o template ao config_manager
            self.config_manager.config = template_config
            
            # IMPORTANTE: Salvar no arquivo de configuração para que os valores persistam
            # Isso garante que quando a janela de configurações for aberta novamente, os valores estarão corretos
            try:
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL] Salvando valores do template '{template_name}' no arquivo de configuração...")
                self.config_manager.save_config()
                
                # DEPURAÇÃO COMPLETA: Mostrar TODOS os valores de TODAS as abas após carregar
                print(f"\n[DEBUG CARREGAR TEMPLATE MANUAL] {'='*80}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL] DEPURAÇÃO COMPLETA - TODAS AS ABAS E CAMPOS APÓS CARREGAR")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL] {'='*80}")
                
                # ABA: Layers
                print(f"\n[DEBUG CARREGAR TEMPLATE MANUAL] ━━━ ABA: LAYERS ━━━")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   paineis_abcd: {self.config_manager.get_config('layers', 'paineis_abcd')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   pe_direito: {self.config_manager.get_config('layers', 'pe_direito')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   cotas: {self.config_manager.get_config('layers', 'cotas')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   sarrafos: {self.config_manager.get_config('layers', 'sarrafos')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   nomenclatura: {self.config_manager.get_config('layers', 'nomenclatura')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   laje: {self.config_manager.get_config('layers', 'laje')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   linhas_hidden: {self.config_manager.get_config('layers', 'linhas_hidden')}")
                
                # ABA: Blocks
                print(f"\n[DEBUG CARREGAR TEMPLATE MANUAL] ━━━ ABA: BLOCKS ━━━")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   furacao: {self.config_manager.get_config('blocks', 'furacao')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   split_ee: {self.config_manager.get_config('blocks', 'split_ee')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   split_dd: {self.config_manager.get_config('blocks', 'split_dd')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   moldura: {self.config_manager.get_config('blocks', 'moldura')}")
                
                # ABA: Blocks - Numeração
                numeracao_ativar = self.config_manager.get_config('blocks', 'numeracao', 'ativar')
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   numeracao.ativar: {numeracao_ativar}")
                if numeracao_ativar:
                    for n_key in ['n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8', 'n9', 'n10', 'n11', 'n12', 'n13', 'n14', 'n15']:
                        n_val = self.config_manager.get_config('blocks', 'numeracao', n_key)
                        if n_val:
                            print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   numeracao.{n_key}: {n_val}")
                
                # ABA: Drawing Options
                print(f"\n[DEBUG CARREGAR TEMPLATE MANUAL] ━━━ ABA: DRAWING OPTIONS ━━━")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   zoom_factor: {self.config_manager.get_config('drawing_options', 'zoom_factor')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   cota_offset: {self.config_manager.get_config('drawing_options', 'cota_offset')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   texto_offset: {self.config_manager.get_config('drawing_options', 'texto_offset')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   sarrafo_offset: {self.config_manager.get_config('drawing_options', 'sarrafo_offset')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   cotas_furacao_vertical: {self.config_manager.get_config('drawing_options', 'cotas_furacao_vertical')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   cotas_furacao_horizontal: {self.config_manager.get_config('drawing_options', 'cotas_furacao_horizontal')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   desenhar_sarrafos_cd: {self.config_manager.get_config('drawing_options', 'desenhar_sarrafos_cd')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   modo_sarrafos: {self.config_manager.get_config('drawing_options', 'modo_sarrafos')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   linetype_pedireito: {self.config_manager.get_config('drawing_options', 'linetype_pedireito')}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   linetype_sarrafos_hidden: {self.config_manager.get_config('drawing_options', 'linetype_sarrafos_hidden')}")
                
                # ABA: Comandos
                print(f"\n[DEBUG CARREGAR TEMPLATE MANUAL] ━━━ ABA: COMANDOS ━━━")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   hatches.laje: {self.config_manager.get_config('comandos', 'hatches', 'laje')}")
                for cmd in ['abv', 'abve', 'abve12', 'abvd', 'abvd12', 'ABVLJ']:
                    cmd_val = self.config_manager.get_config('comandos', 'aberturas', cmd)
                    if cmd_val:
                        print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   aberturas.{cmd}: {cmd_val}")
                
                # ABA: Parafusos
                print(f"\n[DEBUG CARREGAR TEMPLATE MANUAL] ━━━ ABA: PARAFUSOS ━━━")
                parafusos_ab = self.config_manager.get_config('parafusos', 'ab')
                parafusos_cdefgh = self.config_manager.get_config('parafusos', 'cdefgh')
                
                if parafusos_ab:
                    print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Parafusos AB:")
                    for key in ['medida_fundo_primeiro_ab', 'medida_1_2_ab', 'medida_2_3_ab', 'medida_3_4_ab', 
                               'medida_4_5_ab', 'medida_5_6_ab', 'medida_6_7_ab', 'medida_7_8_ab', 
                               'medida_8_9_ab', 'medida_9_10_ab']:
                        val = parafusos_ab.get(key) if isinstance(parafusos_ab, dict) else None
                        if val is not None:
                            print(f"[DEBUG CARREGAR TEMPLATE MANUAL]     {key}: {val}")
                
                if parafusos_cdefgh:
                    print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Parafusos CDEFGH:")
                    for key in ['medida_fundo_primeiro_cdefgh', 'medida_1_2_cdefgh', 'medida_2_3_cdefgh', 'medida_3_4_cdefgh',
                               'medida_4_5_cdefgh', 'medida_5_6_cdefgh', 'medida_6_7_cdefgh', 'medida_7_8_cdefgh',
                               'medida_8_9_cdefgh', 'medida_9_10_cdefgh']:
                        val = parafusos_cdefgh.get(key) if isinstance(parafusos_cdefgh, dict) else None
                        if val is not None:
                            print(f"[DEBUG CARREGAR TEMPLATE MANUAL]     {key}: {val}")
                
                # Resumo dos valores principais
                ab_val = self.config_manager.get_config("parafusos", "ab", "medida_fundo_primeiro_ab")
                cdefgh_val = self.config_manager.get_config("parafusos", "cdefgh", "medida_fundo_primeiro_cdefgh")
                print(f"\n[DEBUG CARREGAR TEMPLATE MANUAL] {'='*80}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL] ✅ RESUMO - Valores principais salvos no arquivo:")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Parafusos AB (medida_fundo_primeiro_ab): {ab_val}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Parafusos CDEFGH (medida_fundo_primeiro_cdefgh): {cdefgh_val}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL]   Arquivo salvo em: {config_path_abs}")
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL] {'='*80}\n")
            except Exception as e:
                print(f"[DEBUG CARREGAR TEMPLATE MANUAL] ⚠️ Erro ao salvar no arquivo: {e}")
                import traceback
                traceback.print_exc()
            
            # Atualiza os campos da interface se a janela de configurações estiver aberta
            if hasattr(self, 'config_window') and self.config_window.winfo_exists():
                # Atualiza todos os campos de layers
                if hasattr(self, 'entry_paineis'):
                    self.entry_paineis.delete(0, tk.END)
                    self.entry_paineis.insert(0, self.config_manager.get_config("layers", "paineis_abcd") or "")
                    
                    self.entry_pe_direito.delete(0, tk.END)
                    self.entry_pe_direito.insert(0, self.config_manager.get_config("layers", "pe_direito") or "")
                    
                    self.entry_cotas.delete(0, tk.END)
                    self.entry_cotas.insert(0, self.config_manager.get_config("layers", "cotas") or "")
                    
                    self.entry_sarrafos.delete(0, tk.END)
                    self.entry_sarrafos.insert(0, self.config_manager.get_config("layers", "sarrafos") or "")
                    
                    self.entry_nomenclatura.delete(0, tk.END)
                    self.entry_nomenclatura.insert(0, self.config_manager.get_config("layers", "nomenclatura") or "")
                    
                    self.entry_laje.delete(0, tk.END)
                    self.entry_laje.insert(0, self.config_manager.get_config("layers", "laje") or "")
                    
                    self.entry_linhas_hidden.delete(0, tk.END)
                    self.entry_linhas_hidden.insert(0, self.config_manager.get_config("layers", "linhas_hidden") or "")
                    
                    # Atualiza o campo de hatch da laje
                    if hasattr(self, 'entry_hatch_laje'):
                        self.entry_hatch_laje.delete(0, tk.END)
                        self.entry_hatch_laje.insert(0, self.config_manager.get_config("comandos", "hatches", "laje") or "HHHH")
                
                # Atualiza os blocos
                if hasattr(self, 'entry_furacao'):
                    self.entry_furacao.delete(0, tk.END)
                    self.entry_furacao.insert(0, self.config_manager.get_config("blocks", "furacao") or "")
                    
                    self.entry_split_ee.delete(0, tk.END)
                    self.entry_split_ee.insert(0, self.config_manager.get_config("blocks", "split_ee") or "")
                    
                    self.entry_split_dd.delete(0, tk.END)
                    self.entry_split_dd.insert(0, self.config_manager.get_config("blocks", "split_dd") or "")
                    
                    self.entry_moldura.delete(0, tk.END)
                    self.entry_moldura.insert(0, self.config_manager.get_config("blocks", "moldura") or "")
                
                # Atualiza opções de desenho
                if hasattr(self, 'entry_zoom'):
                    self.entry_zoom.delete(0, tk.END)
                    self.entry_zoom.insert(0, str(self.config_manager.get_config("drawing_options", "zoom_factor") or "10"))
                    
                    self.entry_cota.delete(0, tk.END)
                    self.entry_cota.insert(0, str(self.config_manager.get_config("drawing_options", "cota_offset") or "15"))
                    
                    self.entry_texto.delete(0, tk.END)
                    self.entry_texto.insert(0, str(self.config_manager.get_config("drawing_options", "texto_offset") or "20"))
                    
                    self.entry_sarrafo.delete(0, tk.END)
                    self.entry_sarrafo.insert(0, str(self.config_manager.get_config("drawing_options", "sarrafo_offset") or "7"))
                
                # Atualiza checkboxes
                if hasattr(self, 'var_cota_vertical'):
                    self.var_cota_vertical.set(self.config_manager.get_config("drawing_options", "cotas_furacao_vertical") or False)
                    self.var_cota_horizontal.set(self.config_manager.get_config("drawing_options", "cotas_furacao_horizontal") or False)
                    self.var_sarrafos_cd.set(self.config_manager.get_config("drawing_options", "desenhar_sarrafos_cd") or False)
                
                # Atualiza modo de sarrafos
                if hasattr(self, 'modo_sarrafos'):
                    self.modo_sarrafos.set(self.config_manager.get_config("drawing_options", "modo_sarrafos") or "normal")
                
                # Atualiza campos de linetype
                if hasattr(self, 'entry_linetype_pedireito'):
                    self.entry_linetype_pedireito.delete(0, tk.END)
                    self.entry_linetype_pedireito.insert(0, self.config_manager.get_config("drawing_options", "linetype_pedireito") or "DASHED")
                    
                    self.entry_linetype_sarrafos.delete(0, tk.END)
                    self.entry_linetype_sarrafos.insert(0, self.config_manager.get_config("drawing_options", "linetype_sarrafos_hidden") or "DASHED")
                
                # Atualiza numeração
                if hasattr(self, 'var_numeracao'):
                    self.var_numeracao.set(self.config_manager.get_config("blocks", "numeracao", "ativar") or False)
                    
                    for key in ['n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8', 'n9', 'n10', 'n11', 'n12', 'n13', 'n14', 'n15']:
                        if key in self.entries_numeracao:
                            self.entries_numeracao[key].delete(0, tk.END)
                            self.entries_numeracao[key].insert(0, self.config_manager.get_config("blocks", "numeracao", key) or "")
                
                # Atualiza comandos de aberturas
                if hasattr(self, 'entries_comandos'):
                    for comando in ['abv', 'abve', 'abve12', 'abvd', 'abvd12', 'ABVLJ']:
                        if comando in self.entries_comandos:
                            self.entries_comandos[comando].delete(0, tk.END)
                            self.entries_comandos[comando].insert(0, self.config_manager.get_config("comandos", "aberturas", comando) or comando)
                
                # Atualizar campos de parafusos A-B
                print(f"[DEBUG CARREGAR TEMPLATE] Atualizando campos de parafusos AB na UI...")
                if hasattr(self, 'entries_parafusos_ab') and self.entries_parafusos_ab:
                    medidas_ab_keys = ["medida_fundo_primeiro_ab", "medida_1_2_ab", "medida_2_3_ab", "medida_3_4_ab", 
                                       "medida_4_5_ab", "medida_5_6_ab", "medida_6_7_ab", "medida_7_8_ab", 
                                       "medida_8_9_ab", "medida_9_10_ab"]
                    defaults_ab = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                    for key, default in zip(medidas_ab_keys, defaults_ab):
                        if key in self.entries_parafusos_ab:
                            self.entries_parafusos_ab[key].delete(0, tk.END)
                            valor = self.config_manager.get_config("parafusos", "ab", key)
                            valor_final = str(valor if valor is not None else default)
                            self.entries_parafusos_ab[key].insert(0, valor_final)
                            if key == "medida_fundo_primeiro_ab":
                                print(f"[DEBUG CARREGAR TEMPLATE]   Campo {key} atualizado para: {valor_final}")
                else:
                    print(f"[DEBUG CARREGAR TEMPLATE] ⚠️ entries_parafusos_ab não existe ou está vazio!")
                
                # Atualizar campos de parafusos C-D-E-F-G-H
                print(f"[DEBUG CARREGAR TEMPLATE] Atualizando campos de parafusos CDEFGH na UI...")
                if hasattr(self, 'entries_parafusos_cdefgh') and self.entries_parafusos_cdefgh:
                    medidas_cdefgh_keys = ["medida_fundo_primeiro_cdefgh", "medida_1_2_cdefgh", "medida_2_3_cdefgh", "medida_3_4_cdefgh",
                                          "medida_4_5_cdefgh", "medida_5_6_cdefgh", "medida_6_7_cdefgh", "medida_7_8_cdefgh",
                                          "medida_8_9_cdefgh", "medida_9_10_cdefgh"]
                    defaults_cdefgh = ["30", "50", "55", "55", "55", "55", "55", "55", "55", "55"]
                    for key, default in zip(medidas_cdefgh_keys, defaults_cdefgh):
                        if key in self.entries_parafusos_cdefgh:
                            self.entries_parafusos_cdefgh[key].delete(0, tk.END)
                            valor = self.config_manager.get_config("parafusos", "cdefgh", key)
                            valor_final = str(valor if valor is not None else default)
                            self.entries_parafusos_cdefgh[key].insert(0, valor_final)
                            if key == "medida_fundo_primeiro_cdefgh":
                                print(f"[DEBUG CARREGAR TEMPLATE]   Campo {key} atualizado para: {valor_final}")
                else:
                    print(f"[DEBUG CARREGAR TEMPLATE] ⚠️ entries_parafusos_cdefgh não existe ou está vazio!")
            
            messagebox.showinfo("Sucesso", f"Template '{template_name}' carregado com sucesso!")
        else:
            messagebox.showerror("Erro", "Template não encontrado")

    def calcular_soma_alturas_painel(self, tipo_painel):
        """
        Calcula a soma de todas as alturas dos painéis e subtrai da altura total
        Reconhece o formato especial 'X+Y' nos campos de altura
        """
        altura_total = 0
        
        # Somar todas as alturas dos painéis usando processar_valor_altura
        for i in range(1, 6):
            altura_var = self.campos.get(f'altura_h{i}_{tipo_painel.lower()}')
            if altura_var:
                try:
                    valor_str = altura_var.get().strip()
                    if valor_str:  # Se há valor no campo
                        # Usar processar_valor_altura para reconhecer formato X+Y
                        altura_processada, _ = self.processar_valor_altura(valor_str)
                        if altura_processada > 0:
                            altura_total += altura_processada
                except (ValueError, TypeError):
                    continue
        
        # Adicionar a altura da laje duas vezes
        try:
            # Usar função auxiliar para obter laje correta
            laje_altura, _ = self.obter_laje_correta(tipo_painel)
            altura_total += laje_altura * 1
        except ValueError:
            pass
        
        # Subtrair a altura total do campo altura da interface
        try:
            altura_interface = self.converter_para_float(self.campos['altura'].get())
            altura_total = altura_interface - altura_total
        except ValueError:
            pass
        
        return altura_total

    def calcular_numero_cumulativo(self, tipo_painel, indice_altura):
        """Calcula o número cumulativo para numeração sequencial entre painéis"""
        # Ignorar painéis com altura de 2cm (índice 0)
        if indice_altura == 0:
            return 0
            
        # Contar quantos painéis válidos (altura > 2cm) existem antes do atual no mesmo tipo de painel
        numero = 0
        for i in range(1, indice_altura):  # Começar do 1 para ignorar altura de 2cm
            try:
                altura_var = self.campos.get(f'altura_h{i+1}_{tipo_painel.lower()}')
                if altura_var:
                    valor = self.converter_para_float(altura_var.get() or 0)
                    if valor > 0:
                        numero += 1
            except (ValueError, TypeError):
                continue
                
        # Retornar o número do painel atual (começando de 1)
        return numero + 1

if __name__ == "__main__":
    import sys
    if '--config' in sys.argv:
        root = tk.Tk()
        root.withdraw()  # Oculta a janela principal
        app = GeradorPilares(root)
        app.criar_janela_configuracoes()
        root.mainloop()
    else:
        app = AplicacaoUnificada()
        app.iniciar()
