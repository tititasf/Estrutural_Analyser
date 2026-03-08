
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
from tkinter import ttk, messagebox, simpledialog
import os
import sys
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import math
import json

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

# Configurar diretórios dinamicamente
def get_project_directories():
    """Obtém os diretórios do projeto de forma dinâmica"""
    try:
        # Tentar usar config_paths se disponível
        from config_paths import PROJECT_ROOT, CONFIG_DIR
        diretorio_base = os.path.join(PROJECT_ROOT, "output", "scripts")
        diretorio_config = CONFIG_DIR
    except ImportError:
        try:
            from src.config_paths import PROJECT_ROOT, CONFIG_DIR
            diretorio_base = os.path.join(PROJECT_ROOT, "output", "scripts")
            diretorio_config = CONFIG_DIR
        except ImportError:
            # Fallback usando robust_path_resolver
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
            
            diretorio_base = os.path.join(project_root, "output", "scripts")
            diretorio_config = os.path.join(project_root, "config")
    
    return diretorio_base, diretorio_config

# Obter diretórios dinamicamente
diretorio_base, diretorio_config = get_project_directories()

# Garantir que os diretórios existam
os.makedirs(diretorio_base, exist_ok=True)
os.makedirs(diretorio_config, exist_ok=True)

# Classe para gerenciar configurações (modificada)
class ConfigManager:
    def __init__(self, config_file="config_grades.json"):
        self.config_file = os.path.join(diretorio_config, config_file)
        self.templates_file = os.path.join(diretorio_config, "templates_grades.json")
        self.config = self.load_config()
        self.templates = self.load_templates()
    
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                default_config = self.get_default_config()
                self._update_nested_dict(default_config, loaded_config)
                return default_config
            return self.get_default_config()
        except Exception as e:
            print(f"Erro ao carregar configurações: {str(e)}")
            return self.get_default_config()
    
    def _update_nested_dict(self, d1, d2):
        for k, v in d2.items():
            if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                self._update_nested_dict(d1[k], v)
            else:
                d1[k] = v
    
    def get_default_config(self):
        return {
            "layers": {
                "base": "SARR_2.2x7",
                "reforco": "SARR_2.2x10",
                "central": "SARR_3.5x7",
                "primeiro_horizontal": "SARR_2.2x10",
                "demais_horizontais": "SARR_2.2x7",
                "cota": "COTA",
                "texto": "TEXTO",
                "hachura": "HACHURA"
            },
            "drawing_options": {
                "dimstyle": "PAINEL-NOVA",
                "hatch_scale": 1,
                "hatch_angle": 45,
                "scale_factor": 1,
                "use_mline": False
            },
            "coordinates": {
                "x_inicial": 120765.49922,
                "y_inicial": 35668.11998,
                "altura_base": 2.2
            },
            "blocks": {
                "triangulo_esquerdo": "GRA-E",
                "triangulo_direito": "GRA-D"
            },
            "horizontal_positions": {
                "positions": [
                    30.0,  # Primeiro horizontal
                    90.0,  # Segundo horizontal
                    150.0, # Terceiro horizontal
                    210.0, # Quarto horizontal
                    270.0, # Quinto horizontal
                    330.0, # Sexto horizontal
                    390.0, # Sétimo horizontal
                    450.0, # Oitavo horizontal
                    510.0  # Nono horizontal
                ]
            }
        }
    
    def save_config(self):
        """Salva a configuração atual no arquivo JSON"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Erro ao salvar configuração: {e}")
            return False
    
    def get_config(self, *keys):
        """Obtém um valor de configuração usando chaves aninhadas.
        Recarrega do arquivo a cada chamada para garantir que sempre use a configuração mais recente,
        especialmente importante em modo pós-compilação quando templates são atualizados."""
        # Recarregar configuração do arquivo para garantir que sempre temos a versão mais recente
        # Isso é especialmente importante quando templates NOVA/INI são carregados
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                default_config = self.get_default_config()
                self._update_nested_dict(default_config, loaded_config)
                self.config = default_config
        except Exception as e:
            # Se houver erro ao recarregar, usar a configuração em cache
            pass
        
        value = self.config
        for key in keys:
            if key in value:
                value = value[key]
            else:
                return None
        return value
    
    def set_config(self, value, *keys):
        """Define um valor de configuração usando chaves aninhadas"""
        if len(keys) == 0:
            return False
        
        current = self.config
        for i, key in enumerate(keys[:-1]):
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
        return True
    
    def save_template(self, template_name, description=""):
        """Salva o template atual. Se já existir, adiciona sufixo numérico."""
        try:
            # Verificar se o template já existe
            if template_name in self.templates:
                # Encontrar o próximo sufixo disponível
                base_name = template_name
                suffix = 1
                while f"{base_name}.{suffix}" in self.templates:
                    suffix += 1
                template_name = f"{base_name}.{suffix}"
                print(f"Template '{base_name}' já existe. Salvando como '{template_name}'")
            
            template_data = {
                "description": description,
                "layers": self.config["layers"].copy(),
                "drawing_options": self.config["drawing_options"].copy(),
                "coordinates": self.config["coordinates"].copy(),
                "blocks": self.config["blocks"].copy(),
                "horizontal_positions": self.config.get("horizontal_positions", {}).copy()
            }
            
            self.templates[template_name] = template_data
            
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Erro ao salvar template: {str(e)}")
            return False
    
    def load_template(self, template_name):
        """Carrega um template específico"""
        try:
            if template_name in self.templates:
                template = self.templates[template_name]
                # Carregar TODOS os campos do template, preservando estrutura completa
                if "layers" in template:
                    self.config["layers"] = template["layers"].copy()
                if "drawing_options" in template:
                    self.config["drawing_options"] = template["drawing_options"].copy()
                if "coordinates" in template:
                    self.config["coordinates"] = template["coordinates"].copy()
                if "blocks" in template:
                    self.config["blocks"] = template["blocks"].copy()
                if "horizontal_positions" in template:
                    self.config["horizontal_positions"] = template["horizontal_positions"].copy()
                self.save_config()
                return True
            return False
        except Exception as e:
            print(f"Erro ao carregar template: {str(e)}")
            return False
    
    def delete_template(self, template_name):
        """Deleta um template"""
        try:
            if template_name in self.templates:
                del self.templates[template_name]
                with open(self.templates_file, 'w', encoding='utf-8') as f:
                    json.dump(self.templates, f, indent=4, ensure_ascii=False)
                return True
            return False
        except Exception as e:
            print(f"Erro ao deletar template: {str(e)}")
            return False
    
    def get_template_names(self):
        """Retorna a lista de nomes dos templates"""
        return list(self.templates.keys())
    
    def get_template_description(self, template_name):
        """Retorna a descrição de um template"""
        if template_name in self.templates:
            return self.templates[template_name].get("description", "")
        return ""
    
    def load_templates(self):
        """Carrega os templates do arquivo"""
        try:
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Erro ao carregar templates: {str(e)}")
            return {}

# Inicialize a variável global no início do script
quantidade_sarrafos_centrais = 2  # Valor padrão inicial
num_retangulos_horizontais = 3  # Valor padrão inicial

# Inicializar o gerenciador de configuração
config_manager = ConfigManager()

def gerar_nome_arquivo(nome, pavimento, numero_lista=None):
    # Substituir espaços em branco por underscores no nome do pavimento
    pavimento = pavimento.replace(" ", "_")
    
    # Criar o diretório do pavimento se não existir
    # Usar path resolver para obter o caminho correto
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from utils.robust_path_resolver import robust_path_resolver
    diretorio_base = os.path.join(robust_path_resolver.get_project_root(), "output", "scripts")
    diretorio_pavimento = os.path.join(diretorio_base, str(pavimento))
    
    if not os.path.exists(diretorio_pavimento):
        os.makedirs(diretorio_pavimento)
    
    # Gerar nome do arquivo
    if numero_lista is not None:
        nome_arquivo = f"{nome}_{numero_lista}.scr"
    else:
        nome_arquivo = f"{nome}.scr"
    
    caminho_completo = os.path.join(diretorio_pavimento, nome_arquivo)
    
    return caminho_completo

def atualizar_retangulos_verticais(*args):
    try:
        largura_base_vertical = float(largura_base_vertical_entry.get())
        # Atualizar todas as grades
        for grade_campos in [grade1_campos, grade2_campos, grade3_campos]:
            grade_campos['sarr_esquerda_entry'].delete(0, tk.END)
            grade_campos['sarr_esquerda_entry'].insert(0, str(largura_base_vertical))
            grade_campos['sarr_direita_entry'].delete(0, tk.END)
            grade_campos['sarr_direita_entry'].insert(0, str(largura_base_vertical))
            grade_campos['sarr1_altura_entry'].delete(0, tk.END)
            grade_campos['sarr1_altura_entry'].insert(0, str(largura_base_vertical))
            grade_campos['sarr2_altura_entry'].delete(0, tk.END)
            grade_campos['sarr2_altura_entry'].insert(0, str(largura_base_vertical))
            grade_campos['sarr3_altura_entry'].delete(0, tk.END)
            grade_campos['sarr3_altura_entry'].insert(0, str(largura_base_vertical))
        atualizar_preview()
    except ValueError:
        pass

def ajustar_altura(altura):
    """Usa exatamente a altura informada (sem arredondar)."""
    try:
        valor = float(altura)
    except (TypeError, ValueError):
        return 0
    return valor if valor > 0 else 0

def calcular_num_retangulos_horizontais(altura):
    """Calcula o número de retângulos horizontais necessários baseado na altura ajustada"""
    # Ajustar a altura para o valor mais próximo múltiplo de 5
    altura_final = ajustar_altura(altura)
    
    # Obter as posições configuradas
    positions = config_manager.get_config("horizontal_positions", "positions")
    
    # Contar quantos retângulos horizontais são necessários
    # (todos que tiverem valor inferior à altura ajustada - 10)
    num_retangulos = 0
    altura_limite = altura_final - 10
    
    for pos in positions:
        if pos <= altura_limite:
            num_retangulos += 1
    
    return num_retangulos

def calcular_posicao_horizontal(i, altura_base, altura_minima=None, altura_maxima=None):
    """Calcula a posição Y do i-ésimo retângulo horizontal"""
    # Obter as posições configuradas (em cm, não somadas com altura_base ainda)
    positions = config_manager.get_config("horizontal_positions", "positions")
    
    # Se o índice estiver dentro do range das posições configuradas
    if i < len(positions):
        # Comparar a posição relativa (em cm) com a altura mínima (em cm)
        posicao_relativa = positions[i]
        
        # LIMITAÇÃO: Horizontais limitados a 300cm de altura
        # Bloquear qualquer horizontal acima de 300cm
        if posicao_relativa > 300.0:
            return None  # Não desenhar horizontais acima de 300cm
        
        # Se houver altura mínima, usar ela como limite (EM CM, não somado)
        # DIMINUIR -10 do valor da altura para calcular a quantidade de horizontais
        if altura_minima is not None:
            altura_minima_ajustada = altura_minima - 10  # Diminuir -10
            # Limitar também pela altura mínima ajustada (mas não pode ultrapassar 300cm)
            limite_altura = min(altura_minima_ajustada, 300.0)
            if posicao_relativa <= limite_altura:
                # Só agora somar com altura_base para retornar posição absoluta
                return altura_base + posicao_relativa
            else:
                # Posição está acima do limite
                return None
        elif altura_maxima is not None:
            # Se não houver altura mínima, usar a altura máxima
            # DIMINUIR -10 do valor da altura para calcular a quantidade de horizontais
            altura_maxima_ajustada = altura_maxima - 10  # Diminuir -10
            # Limitar também pela altura máxima ajustada (mas não pode ultrapassar 300cm)
            limite_altura = min(altura_maxima_ajustada, 300.0)
            if posicao_relativa <= limite_altura:
                return altura_base + posicao_relativa
            else:
                return None
        else:
            # Se não houver nenhuma altura especificada, não desenhar
            return None
    
    # Se o índice estiver fora do range, retornar None
    return None

def gerar_script_grade(pavimento, nome, grades_ativas, altura_base=None, x_inicial_custom=None, y_inicial_custom=None, distancias=None):
    try:
        # Se não foram fornecidos parâmetros, tenta pegar da interface
        if pavimento is None:
            pavimento = pavimento_entry.get()
        if not pavimento:
            raise ValueError("O campo Pavimento é obrigatório")
            
        if nome is None:
            nome = nome_entry.get()
        if not nome:
            raise ValueError("O campo Nome do Arquivo é obrigatório")

        if not grades_ativas:
            raise ValueError("Nenhuma grade ativa")

        # Obter coordenadas - usar custom se fornecido, senão usar da configuração
        if x_inicial_custom is not None:
            x_inicial = x_inicial_custom
            print(f"[COORDENADAS] Usando x_inicial customizado: {x_inicial}")
        else:
            x_inicial = config_manager.get_config("coordinates", "x_inicial")
            print(f"[COORDENADAS] Usando x_inicial da config: {x_inicial}")
        
        if y_inicial_custom is not None:
            y_inicial = y_inicial_custom
            print(f"[COORDENADAS] Usando y_inicial customizado: {y_inicial}")
        else:
            y_inicial = config_manager.get_config("coordinates", "y_inicial")
            print(f"[COORDENADAS] Usando y_inicial da config: {y_inicial}")
        
        altura_base_horizontal = config_manager.get_config("coordinates", "altura_base")  # 2.2cm
        
        # Salvar altura original antes de sobrescrever altura_base
        altura_original_parametro = altura_base
        
        # Calcular o maior detalhe de todas as grades do conjunto
        maior_detalhe = 0.0
        for grade in grades_ativas:
            # Verificar se há alturas_detalhes na grade
            if 'alturas_detalhes' in grade and grade['alturas_detalhes']:
                # Encontrar o maior valor válido (maior que 0) nos detalhes desta grade
                for altura_detalhe in grade['alturas_detalhes']:
                    if altura_detalhe > maior_detalhe:
                        maior_detalhe = altura_detalhe
            # Também verificar alturas normais (esquerda, direita, alturas[])
            if grade.get('esquerda', 0) > maior_detalhe:
                maior_detalhe = grade['esquerda']
            if grade.get('direita', 0) > maior_detalhe:
                maior_detalhe = grade['direita']
            if 'alturas' in grade and grade['alturas']:
                for altura in grade['alturas']:
                    if altura > maior_detalhe:
                        maior_detalhe = altura
        
        # Se encontrou um maior detalhe, usar ele; senão usar a altura passada como parâmetro ou padrão
        if maior_detalhe > 0:
            altura_pilar = maior_detalhe
            print(f"[ALTURA] Usando maior detalhe encontrado: {maior_detalhe}cm (em vez da altura da interface)")
        else:
            # Usar altura do pilar passada como parâmetro (altura_base é o nome do parâmetro)
            altura_pilar = altura_original_parametro if altura_original_parametro is not None else 300.0
            print(f"[ALTURA] Nenhum detalhe válido encontrado, usando altura da interface: {altura_pilar}cm")
        
        # Manter altura_base para compatibilidade com o resto do código
        altura_base = altura_base_horizontal

        # Obter layers da configuração
        layer_base = config_manager.get_config("layers", "base")
        layer_reforco = config_manager.get_config("layers", "reforco")
        layer_central = config_manager.get_config("layers", "central")
        layer_cota = config_manager.get_config("layers", "cota")
        
        # Obter blocos configurados
        bloco_esquerdo = config_manager.get_config("blocks", "triangulo_esquerdo")
        bloco_direito = config_manager.get_config("blocks", "triangulo_direito")

        # Obter opções de desenho
        dimstyle = config_manager.get_config("drawing_options", "dimstyle")
        use_mline = config_manager.get_config("drawing_options", "use_mline")

        script = f""";
-DIMSTYLE
RESTORE
{dimstyle}
;
_ZOOM
C {x_inicial},{y_inicial} 5
;
LAYER
S
NOMENCLATURA

;
-STYLE
standard

14





;
_TEXT
{x_inicial-10},{y_inicial}
90
{nome}
;
LAYER
S {layer_base}

;
"""
        
        # Desenhar cada grade ativa
        x_offset = x_inicial
        blocks_script = ""  # Variável para armazenar os comandos de inserção dos blocos
        
        # Lista para acumular TODAS as posições Y dos sarrafos horizontais de TODAS as grades do arquivo
        # Isso permite gerar cotas verticais completas na última grade usando todas as posições
        todas_posicoes_y_horizontais = []
        print(f"[INICIO LOOP] Lista todas_posicoes_y_horizontais inicializada (vazia): {todas_posicoes_y_horizontais}")
        
        # Variáveis para cálculo de sarrafos extras
        # Armazenar informações de cada grade para cálculo final
        info_sarrafos_extras = []  # Lista de informações de sarrafos extras de cada grade (quantidade e diferença de altura)

        for i, grade in enumerate(grades_ativas):
            print(f"\n[LOOP INICIO] i={i}, Processando grade {i+1} com x_offset = {x_offset}")
            print(f"[LOOP INICIO] Type i={type(i)}")
            
            # Se NÃO for a primeira grade, adicionar a distância da grade anterior
            if i > 0:
                try:
                    print(f"[DEBUG ESPAÇO ANTES] i={i}, distancias={distancias}")
                    # Determinar qual distância usar
                    if i == 1 and distancias and isinstance(distancias, dict) and 'distancia_grade1' in distancias:
                        distancia = float(distancias['distancia_grade1'])
                        # Se for entre A e B (nome termina com .A ou .B), aumentar distância em 0cm
                        if nome.endswith('.A') or nome.endswith('.B'):
                            distancia += 0.0
                            print(f"[DEBUG ESPAÇO ANTES] ✓ Adicionando {distancia}cm entre Grade 1→2 antes de desenhar Grade 2 (aumentado em 0cm para A/B)")
                        else:
                            print(f"[DEBUG ESPAÇO ANTES] ✓ Adicionando {distancia}cm entre Grade 1→2 antes de desenhar Grade 2")
                        x_offset += distancia
                    elif i == 2 and distancias and isinstance(distancias, dict) and 'distancia_grade2' in distancias:
                        distancia = float(distancias['distancia_grade2'])
                        print(f"[DEBUG ESPAÇO ANTES] ✓ Adicionando {distancia}cm entre Grade 2→3 antes de desenhar Grade 3")
                        x_offset += distancia
                    else:
                        print(f"[DEBUG ESPAÇO ANTES] ✗ Erro: i={i}, distancias={distancias}, usando 22cm padrão")
                        x_offset += 22
                except (ValueError, AttributeError) as e:
                    print(f"[DEBUG ESPAÇO ANTES] ✗ Erro ao obter distância: {e}, usando padrão 22cm")
                    x_offset += 22
            
            # Armazenar alturas originais antes de ajustar
            altura_original_esquerda = grade['esquerda']
            altura_original_direita = grade['direita']
            alturas_originais = grade['alturas'].copy()
            
            # Calcular altura máxima original (antes de ajustar)
            altura_maxima_original = max(
                altura_original_esquerda if altura_original_esquerda > 0 else 0,
                altura_original_direita if altura_original_direita > 0 else 0,
                max([a if a > 0 else 0 for a in alturas_originais]) if alturas_originais else 0
            )
            
            # Ajustar alturas dos sarrafos
            # Usar altura específica do campo 0 para sarrafo da extremidade esquerda
            if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > 0:
                grade['esquerda'] = ajustar_altura(grade['alturas_detalhes'][0]) if grade['alturas_detalhes'][0] > 0 else 0

                # Sarrafo direito: REGRA do cliente → usar a altura do ÚLTIMO central válido
                # Identificar quantos centrais válidos existem
                if 'larguras_detalhes' in grade and grade['larguras_detalhes']:
                    # Contar apenas os primeiros 4 campos (índices 0-3), pois o índice 4 é apenas distância
                    num_sarrafos_preenchidos = 0
                    for k in range(min(4, len(grade['larguras_detalhes']))):  # Apenas índices 0-3
                        if grade['larguras_detalhes'][k] > 0:
                            num_sarrafos_preenchidos = k + 1
                        else:
                            break
                    
                    # O número de centrais é igual ao número de sarrafos preenchidos (índices 0-3)
                    # O índice 4 não é um sarrafo, é apenas distância
                    num_centrals = num_sarrafos_preenchidos

                    # Índice da altura do último central válido:
                    # - alturas_detalhes[0] = altura da extremidade esquerda
                    # - alturas_detalhes[1] = altura do sarrafo central 1 (k=0)
                    # - alturas_detalhes[2] = altura do sarrafo central 2 (k=1)
                    # - alturas_detalhes[3] = altura do sarrafo central 3 (k=2)
                    # - alturas_detalhes[4] = altura do sarrafo central 4 (k=3)
                    # Se temos num_centrals sarrafos, o último central tem índice k = num_centrals - 1
                    # E sua altura está em alturas_detalhes[k+1] = alturas_detalhes[num_centrals]
                    if num_centrals > 0 and num_centrals < len(grade['alturas_detalhes']):
                        grade['direita'] = ajustar_altura(grade['alturas_detalhes'][num_centrals])
                        print(f"[REGRA DIREITA] centrais={num_centrals} → direita = altura[{num_centrals}] = {grade['alturas_detalhes'][num_centrals]}")
                    else:
                        # Fallback: último campo de altura preenchido
                        # NOTA: Usar idx_altura em vez de i para evitar sobrescrever a variável i do loop externo
                        for idx_altura in range(len(grade['alturas_detalhes']) - 1, -1, -1):
                            if grade['alturas_detalhes'][idx_altura] > 0:
                                grade['direita'] = ajustar_altura(grade['alturas_detalhes'][idx_altura])
                                print(f"[REGRA DIREITA][fallback] usando altura[{idx_altura}] = {grade['alturas_detalhes'][idx_altura]}")
                                break
                else:
                    # Fallback: usar último campo de altura preenchido
                    # NOTA: Usar idx_altura em vez de i para evitar sobrescrever a variável i do loop externo
                    for idx_altura in range(len(grade['alturas_detalhes']) - 1, -1, -1):
                        if grade['alturas_detalhes'][idx_altura] > 0:
                            grade['direita'] = ajustar_altura(grade['alturas_detalhes'][idx_altura])
                            print(f"[REGRA DIREITA][fallback] usando altura[{idx_altura}] = {grade['alturas_detalhes'][idx_altura]}")
                            break
            else:
                grade['esquerda'] = ajustar_altura(grade['esquerda']) if grade['esquerda'] > 0 else 0
                grade['direita'] = ajustar_altura(grade['direita']) if grade['direita'] > 0 else 0
            grade['alturas'] = [ajustar_altura(altura) if altura > 0 else 0 for altura in grade['alturas']]
            
            # VERIFICAR SE GRADE TEM LARGURA OU DETALHES VÁLIDOS
            tem_detalhes_validos = False
            if 'larguras_detalhes' in grade and grade['larguras_detalhes']:
                tem_detalhes_validos = any(d > 0 for d in grade['larguras_detalhes'][:4])
            

            # Se não tem largura E não tem detalhes válidos, IGNORAR COMPLETAMENTE esta grade
            if grade['largura'] <= 0 and not tem_detalhes_validos:
                print(f"Grade {i+1} ignorada completamente: largura={grade['largura']}cm, sem detalhes válidos")
                # Não avançar x_offset porque a grade não ocupa espaço
                # O x_offset será atualizado no final do loop se houver próxima grade
                continue  # Pular para a próxima grade
            
            # Retângulo base (só desenha se tiver largura > 0)
            if grade['largura'] > 0:
                script += f"""LAYER
S {layer_base}

; Retângulo base
_ZOOM
C {x_offset+grade['largura']/2},{y_inicial+altura_base/2} 5
;
"""
            script += gerar_comandos_retangulo(
                x_offset, y_inicial,
                x_offset+grade['largura'], y_inicial+altura_base,
                use_mline,  # Usa a configuração normal de MLINE
                is_horizontal=True  # Indica que é um retângulo horizontal
            )

            # Acumular comandos de inserção dos blocos para executar depois
            blocks_script += f"""; Inserir bloco triangular esquerdo e direito para grade {i+1}
-INSERT
{bloco_esquerdo}
{x_offset},{y_inicial}
1
0
;
-INSERT
{bloco_direito}
{x_offset+grade['largura']},{y_inicial}
1
0
;"""
            
            # Retângulo vertical esquerdo
            # APENAS desenhar se:
            # 1. Tem largura > 0 (grade com largura definida) OU
            # 2. Tem detalhes válidos (desenhar sarrafo esquerdo baseado nos detalhes)
            
            # Determinar largura do sarrafo esquerdo
            # Se não é a primeira grade (tem grade adjacente à esquerda), usar 3.5cm (central)
            # Caso contrário, usar o valor do checkbox
            tem_grade_adjacente_esquerda = (i > 0)  # Não é a primeira grade
            if tem_grade_adjacente_esquerda:
                largura_sarrafo_esq = 3.5  # Sempre 3.5cm quando há grade adjacente
                esquerdo_central_efetivo = True  # Tratar como central para layer
            else:
                largura_sarrafo_esq = 3.5 if grade['esquerdo_central'] else 7.0
                esquerdo_central_efetivo = grade['esquerdo_central']
            
            # Só desenhar se a grade tem largura OU se tem detalhes válidos
            desenhar_extremidades = grade['largura'] > 0 or tem_detalhes_validos
            
            # Desenhar sarrafo esquerdo
            # LIMITAÇÃO: Sarrafos verticais limitados a 300cm
            altura_esquerdo_original = grade['esquerda']
            altura_esquerdo_desenhar = min(altura_esquerdo_original, 300.0)  # Limitar a 300cm
            precisa_sarrafo_extra_esquerdo = altura_esquerdo_original > 300.0
            
            if desenhar_extremidades and esquerdo_central_efetivo:
                script += f"""LAYER
S {layer_central}

; Retângulo vertical esquerdo (formato central)
_ZOOM
C {x_offset+largura_sarrafo_esq/2},{y_inicial+altura_base+altura_esquerdo_desenhar/2} 5
;
"""
                script += gerar_comandos_retangulo(
                    x_offset, y_inicial+altura_base,
                    x_offset+largura_sarrafo_esq, y_inicial+altura_base+altura_esquerdo_desenhar,
                    use_mline,
                    is_horizontal=False
                )
            elif desenhar_extremidades:
                script += f"""LAYER
S {layer_base}

; Retângulo vertical esquerdo
_ZOOM
C {x_offset+largura_sarrafo_esq/2},{y_inicial+altura_base+altura_esquerdo_desenhar/2} 5
;
"""
                script += gerar_comandos_retangulo(
                    x_offset, y_inicial+altura_base,
                    x_offset+largura_sarrafo_esq, y_inicial+altura_base+altura_esquerdo_desenhar,
                    use_mline,
                    is_horizontal=False
                )
            
            # Armazenar altura do sarrafo esquerdo para verificação posterior (após calcular altura_maxima_valida)
            altura_esquerdo_original = grade['esquerda']
            altura_direito_original = grade['direita']  # Inicializar também para sarrafo direito
            
            # NOVA LÓGICA DOS SARRAFOS VERTICAIS
            # 1. Sarrafo esquerdo (já desenhado acima)
            # 2. Sarrafos centrais (baseados nas larguras_detalhes)
            # 3. Sarrafo direito (já desenhado acima)
            
            # Calcular altura_maxima_valida ANTES de desenhar sarrafos centrais (para usar nas cotas)
            # Verificar se há alturas dos detalhes disponíveis
            altura_maxima_valida = 0
            if 'alturas_detalhes' in grade and grade['alturas_detalhes']:
                # Usar alturas ajustadas para comparação
                alturas_validas_ajustadas = [ajustar_altura(altura) for altura in grade['alturas_detalhes'] if altura > 0]
                if alturas_validas_ajustadas:
                    altura_maxima_valida = max(alturas_validas_ajustadas)
                else:
                    # Fallback: usar altura máxima entre esquerda, direita e alturas
                    altura_maxima_valida = max(grade['esquerda'], grade['direita'], max(grade['alturas']) if grade['alturas'] else 0)
            else:
                # Fallback: usar altura máxima entre esquerda, direita e alturas
                altura_maxima_valida = max(grade['esquerda'], grade['direita'], max(grade['alturas']) if grade['alturas'] else 0)
            
            print(f"[ALTURA REFERÊNCIA PRE] Altura máxima válida calculada: {altura_maxima_valida}cm")
            
            # Inicializar quantidade_sarrafos (usado posteriormente para cotas)
            quantidade_sarrafos = 0
            
            # Verificar se há larguras dos detalhes disponíveis
            if 'larguras_detalhes' in grade and grade['larguras_detalhes']:
                print(f"Distâncias dos detalhes: {grade['larguras_detalhes']}")
                
                # Verificar se TODOS os detalhes são 0
                todos_detalhes_zero = all(d == 0 for d in grade['larguras_detalhes'][:4])
                
                if not todos_detalhes_zero:
                    # Verificar se também há alturas dos detalhes disponíveis
                    tem_alturas_detalhes = 'alturas_detalhes' in grade and grade['alturas_detalhes']
                    
                    # LÓGICA CORRETA DOS SARRAFOS CENTRAIS:
                    # - larguras_detalhes[0] = distância da PONTA ESQUERDA do sarrafo esquerdo até o CENTRO do sarrafo 1
                    # - larguras_detalhes[1] = distância do CENTRO do sarrafo 1 até o CENTRO do sarrafo 2
                    # - larguras_detalhes[2] = distância do CENTRO do sarrafo 2 até o CENTRO do sarrafo 3
                    # - larguras_detalhes[3] = distância do CENTRO do sarrafo 3 até o CENTRO do sarrafo 4
                    # - larguras_detalhes[4] = distância do CENTRO do último sarrafo até a PONTA DIREITA do sarrafo direito
                    
                    # Largura do sarrafo esquerdo (pode ser 7cm ou 3.5cm se central)
                    largura_esquerdo = 3.5 if grade['esquerdo_central'] else 7
                    
                    # Posição inicial: PONTA ESQUERDA do sarrafo esquerdo + distância até o primeiro central
                    posicao_x = 0  # Ponto de partida: ponta esquerda do sarrafo esquerdo
                    
                    # Desenhar sarrafos centrais baseados nas larguras_detalhes
                    # REGRA: Desenha todos os sarrafos centrais EXCETO o último preenchido
                    # O último sarrafo preenchido é só distância até extremidade direita
                    
                    # Primeiro, contar quantos sarrafos centrais estão preenchidos
                    # IMPORTANTE: Contar apenas os primeiros 4 campos (índices 0-3), pois o índice 4 é apenas distância até extremidade
                    num_sarrafos_preenchidos = 0
                    for k in range(min(4, len(grade['larguras_detalhes']))):  # Apenas índices 0-3 (sarrafo 1, 2, 3, 4)
                        if grade['larguras_detalhes'][k] > 0:
                            num_sarrafos_preenchidos = k + 1
                        else:
                            break
                    
                    # Verificar se há sobra à direita (índice 4 > 0)
                    # O índice 4 não é um sarrafo, é apenas a distância do último sarrafo até a ponta direita
                    tem_sobra_direita = (
                        len(grade['larguras_detalhes']) >= 5 and grade['larguras_detalhes'][4] > 0
                    )
                    
                    # Calcular número de centrais:
                    # Os índices 0-3 representam sarrafos centrais (1, 2, 3, 4)
                    # O índice 4 é apenas distância, não é um sarrafo
                    # Portanto, num_centrals = num_sarrafos_preenchidos (contando apenas índices 0-3)
                    num_centrals = num_sarrafos_preenchidos
                    
                    # REGRA: Sempre não desenhar o último sarrafo central preenchido
                    # O último sarrafo central preenchido não é desenhado; sua altura é usada no sarrafo da extremidade direita
                    # Exemplo: Se temos 3 sarrafos preenchidos (índices 0, 1, 2), desenhamos apenas os 2 primeiros (índices 0, 1)
                    num_sarrafos_para_desenhar = max(0, num_centrals - 1)  # Sempre não desenhar o último
                    print(f"[VERTICAIS] preenchidos={num_sarrafos_preenchidos}, sobra_direita={tem_sobra_direita}, centrais={num_centrals}, desenhar={num_sarrafos_para_desenhar}, largura={grade['largura']}")
                    
                    # Posição inicial: PONTA ESQUERDA do sarrafo esquerdo
                    posicao_atual = 0  # Ponto de partida: ponta esquerda do sarrafo esquerdo
                    
                    for k in range(num_sarrafos_para_desenhar):
                        distancia_detalhe = grade['larguras_detalhes'][k]
                        
                        # Posição do CENTRO do sarrafo = posição atual + distância
                        posicao_centro_sarrafo = posicao_atual + distancia_detalhe
                        
                        # Usar altura específica do sarrafo central (campo k+1)
                        if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > k+1:
                            altura_para_usar_original = grade['alturas_detalhes'][k+1]  # Usar altura específica do sarrafo central
                        else:
                            # Fallback: usar altura da extremidade esquerda (campo 0)
                            if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > 0:
                                altura_para_usar_original = grade['alturas_detalhes'][0]  # Campo 0 - altura da extremidade esquerda
                            else:
                                altura_para_usar_original = grade['esquerda']  # Fallback final
                        
                        # LIMITAÇÃO: Sarrafos verticais limitados a 300cm
                        altura_para_usar = min(altura_para_usar_original, 300.0)  # Limitar a 300cm
                        precisa_sarrafo_extra_central = altura_para_usar_original > 300.0
                        
                        # Largura fixa para sarrafos centrais: 3.5cm
                        largura_sarrafo = 3.5
                        
                        # Calcular posição da esquerda do sarrafo (centro - metade da largura)
                        posicao_esquerda = posicao_centro_sarrafo - largura_sarrafo/2
                        
                        print(f"Desenhando sarrafo central {k+1}: centro X={posicao_centro_sarrafo}cm, esquerda X={posicao_esquerda}cm, largura={largura_sarrafo}cm, altura={altura_para_usar}cm (original={altura_para_usar_original}cm)")
                        
                        script += f"""LAYER
S {layer_central}

; Sarrafo vertical central {k+1}
_ZOOM
C {x_offset+posicao_centro_sarrafo},{y_inicial+altura_base+altura_para_usar/2} 5
;
"""
                        script += gerar_comandos_retangulo(
                                x_offset+posicao_esquerda, y_inicial+altura_base,
                                x_offset+posicao_esquerda+largura_sarrafo, y_inicial+altura_base+altura_para_usar,
                            use_mline,
                            is_horizontal=False
                        )
                    
                        quantidade_sarrafos += 1
                        
                        # Adicionar cota vertical à esquerda se o sarrafo for menor que a altura máxima
                        altura_para_usar_ajustada = ajustar_altura(altura_para_usar) if altura_para_usar > 0 else 0
                        if altura_para_usar_ajustada > 0 and altura_para_usar_ajustada < altura_maxima_valida and altura_para_usar_ajustada < 300:
                            # Cota vertical à esquerda do sarrafo (3cm à esquerda)
                            x_cota = x_offset + posicao_esquerda - 3
                            y_base = y_inicial + altura_base
                            y_topo = y_inicial + altura_base + altura_para_usar_ajustada
                            y_texto = y_inicial + altura_base + altura_para_usar_ajustada / 2
                            script += f"""LAYER
S COTA

;
_DIMLINEAR
{x_offset+posicao_esquerda},{y_base}
{x_offset+posicao_esquerda},{y_topo}
{x_cota},{y_texto}
;
;
"""
                            print(f"[COTA VERTICAL] Adicionada cota para sarrafo central {k+1} (altura={altura_para_usar_ajustada}cm, max={altura_maxima_valida}cm)")
                        
                        # Atualizar posição para o próximo sarrafo (centro do atual)
                        posicao_atual = posicao_centro_sarrafo
                else:
                    print("Todos os detalhes são 0 - desenhando APENAS extremidades (esquerdo + direito)")
            else:
                print("Nenhuma largura de detalhe encontrada - desenhando APENAS extremidades")
            
            # Retângulo vertical direito
            # APENAS desenhar se desenhar_extremidades = True
            # Determinar largura do sarrafo direito ANTES de verificar desenhar_extremidades
            # Se não é a última grade (tem grade adjacente à direita), usar 3.5cm (central)
            # Caso contrário, usar o valor do checkbox
            tem_grade_adjacente_direita = (i < len(grades_ativas) - 1)  # Não é a última grade
            if tem_grade_adjacente_direita:
                largura_sarrafo_dir = 3.5  # Sempre 3.5cm quando há grade adjacente
                direito_central_efetivo = True  # Tratar como central para layer
            else:
                largura_sarrafo_dir = 3.5 if grade['direito_central'] else 7.0
                direito_central_efetivo = grade['direito_central']
            
            # Inicializar pos_x_direito
            pos_x_direito = None
            
            if desenhar_extremidades:
                # Calcular posição X do sarrafo direito
                # Se tem largura definida, usar grade['largura']
                # Se só tem detalhes, calcular baseado na última posição + largura do último sarrafo
                if grade['largura'] > 0:
                    pos_x_direito = x_offset + grade['largura'] - largura_sarrafo_dir
                else:
                    # Quando só tem detalhes, usar a largura total calculada dos detalhes
                    # (essa lógica será ajustada depois se necessário)
                    pos_x_direito = x_offset + grade['largura'] - largura_sarrafo_dir
                
            if desenhar_extremidades:
                # LIMITAÇÃO: Sarrafos verticais limitados a 300cm
                altura_direito_original = grade['direita']
                altura_direito_desenhar = min(altura_direito_original, 300.0)  # Limitar a 300cm
                precisa_sarrafo_extra_direito = altura_direito_original > 300.0
                
                if direito_central_efetivo:
                    script += f"""LAYER
S {layer_central}

; Retângulo vertical direito (formato central)
_ZOOM
C {pos_x_direito+largura_sarrafo_dir/2},{y_inicial+altura_base+altura_direito_desenhar/2} 5
;
"""
                    script += gerar_comandos_retangulo(
                            pos_x_direito, y_inicial+altura_base,
                            pos_x_direito+largura_sarrafo_dir, y_inicial+altura_base+altura_direito_desenhar,
                        use_mline,
                        is_horizontal=False
                    )
                else:
                    script += f"""LAYER
S {layer_base}

; Retângulo vertical direito
_ZOOM
C {pos_x_direito+largura_sarrafo_dir/2},{y_inicial+altura_base+altura_direito_desenhar/2} 5
;
"""
                    script += gerar_comandos_retangulo(
                            pos_x_direito, y_inicial+altura_base,
                            pos_x_direito+largura_sarrafo_dir, y_inicial+altura_base+altura_direito_desenhar,
                        use_mline,
                        is_horizontal=False
                    )
            
            # Desenhar sarrafos horizontais
            # Usar altura específica do campo 0 para sarrafo da extremidade esquerda
            if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > 0:
                altura_esquerda = ajustar_altura(grade['alturas_detalhes'][0]) if grade['alturas_detalhes'][0] > 0 else 0
                # Usar altura específica do último campo preenchido para sarrafo da extremidade direita
                altura_direita = 0
                # NOTA: Usar idx_altura em vez de i para evitar sobrescrever a variável i do loop externo
                for idx_altura in range(len(grade['alturas_detalhes']) - 1, -1, -1):
                    if grade['alturas_detalhes'][idx_altura] > 0:
                        altura_direita = ajustar_altura(grade['alturas_detalhes'][idx_altura])
                        break
                altura_maxima = max(altura_esquerda, altura_direita, max(grade['alturas']))
            else:
                altura_maxima = max(grade['esquerda'], grade['direita'], max(grade['alturas']))
            
            # Usar a altura do pilar como altura total, mas aplicar o ajuste
            altura_original_ajustada = ajustar_altura(altura_pilar)
            
            # Inicializar num_retangulos_horizontais
            num_retangulos_horizontais = 0
            
            # Verificar se há alturas dos detalhes disponíveis
            if 'alturas_detalhes' in grade and grade['alturas_detalhes']:
                print(f"Usando alturas dos detalhes: {grade['alturas_detalhes']}")
                
                # ENCONTRAR A MENOR ALTURA VÁLIDA (referência para altura da grade)
                # Usar alturas ajustadas para comparação
                alturas_validas_ajustadas = [ajustar_altura(altura) for altura in grade['alturas_detalhes'] if altura > 0]
                alturas_validas_originais = [altura for altura in grade['alturas_detalhes'] if altura > 0]
                if alturas_validas_ajustadas:
                    altura_minima_valida = min(alturas_validas_ajustadas)
                    altura_maxima_valida = max(alturas_validas_ajustadas)
                    print(f"[ALTURA REFERÊNCIA] Menor altura válida (ajustada): {altura_minima_valida}cm, Maior (ajustada): {altura_maxima_valida}cm")
                else:
                    altura_minima_valida = altura_maxima
                    altura_maxima_valida = altura_maxima
                
                # Adicionar cotas verticais para sarrafos menores (esquerdo e direito)
                # Verificar sarrafo esquerdo
                if desenhar_extremidades:
                    altura_esquerdo_ajustada = ajustar_altura(grade['esquerda']) if grade['esquerda'] > 0 else 0
                    if altura_esquerdo_ajustada > 0 and altura_esquerdo_ajustada < altura_maxima_valida and altura_esquerdo_ajustada < 300:
                        # Cota vertical à esquerda do sarrafo esquerdo (3cm à esquerda)
                        x_cota_esq = x_offset - 3
                        y_base = y_inicial + altura_base
                        y_topo = y_inicial + altura_base + altura_esquerdo_ajustada
                        y_texto = y_inicial + altura_base + altura_esquerdo_ajustada / 2
                        script += f"""LAYER
S COTA

; Cota vertical do sarrafo esquerdo (menor por conflito com abertura)
_DIMLINEAR
{x_offset},{y_base}
{x_offset},{y_topo}
{x_cota_esq},{y_texto}
;
;
"""
                        print(f"[COTA VERTICAL] Adicionada cota para sarrafo esquerdo (altura={altura_esquerdo_ajustada}cm, max={altura_maxima_valida}cm)")
                    
                    # Cota extra para sarrafos >= 300cm (apenas extremidade esquerda)
                    elif altura_esquerdo_original >= 300:
                        # Cota vertical à esquerda do sarrafo esquerdo (5cm à esquerda)
                        # Usar altura_esquerdo_desenhar para alinhar visualmente com o sarrafo (limitado a 300cm)
                        x_cota_esq = x_offset - 5
                        y_base = y_inicial + altura_base
                        y_topo = y_inicial + altura_base + altura_esquerdo_desenhar
                        y_texto = y_inicial + altura_base + altura_esquerdo_desenhar / 2
                        script += f"""LAYER
S COTA

; Cota vertical do sarrafo esquerdo (>= 300cm)
_DIMLINEAR
{x_offset},{y_base}
{x_offset},{y_topo}
{x_cota_esq},{y_texto}
;
;
"""
                        print(f"[COTA VERTICAL EXTRA] Adicionada cota para sarrafo esquerdo >= 3m (altura_desenho={altura_esquerdo_desenhar}cm)")
                    
                    # Verificar sarrafo direito
                    if pos_x_direito is not None:
                        altura_direito_ajustada = ajustar_altura(grade['direita']) if grade['direita'] > 0 else 0
                        if altura_direito_ajustada > 0 and altura_direito_ajustada < altura_maxima_valida and altura_direito_ajustada < 300:
                            # Cota vertical à esquerda do sarrafo direito (3cm à esquerda)
                            x_cota_dir = pos_x_direito - 3
                            y_base = y_inicial + altura_base
                            y_topo = y_inicial + altura_base + altura_direito_ajustada
                            y_texto = y_inicial + altura_base + altura_direito_ajustada / 2
                            script += f"""LAYER
S COTA

; Cota vertical do sarrafo direito (menor por conflito com abertura)
_DIMLINEAR
{pos_x_direito},{y_base}
{pos_x_direito},{y_topo}
{x_cota_dir},{y_texto}
;
;
"""
                            print(f"[COTA VERTICAL] Adicionada cota para sarrafo direito (altura={altura_direito_ajustada}cm, max={altura_maxima_valida}cm)")
                
                # Calcular altura mínima para cotas
                if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > 0:
                    altura_minima = min(altura_esquerda, altura_direita, min(grade['alturas']))
                else:
                    altura_minima = min(grade['esquerda'], grade['direita'], min(grade['alturas']))
                if altura_minima == 0:  # Se algum sarrafo não for usado
                    altura_minima = altura_maxima
                
                # Obter posições configuradas
                positions = config_manager.get_config("horizontal_positions", "positions")
                print(f"\n[DEBUG HORIZONTAIS] Grade: usando posições horizontais: {positions}")
                print(f"[DEBUG HORIZONTAIS] Altura mínima válida (limite): {altura_minima_valida}cm")
                print(f"[DEBUG HORIZONTAIS] Altura máxima válida: {altura_maxima_valida}cm")
                print(f"[DEBUG HORIZONTAIS] Todas as alturas dos detalhes desta grade: {grade['alturas_detalhes']}")
                
                # Verificar se altura máxima é >= 300cm (para mover último horizontal para o topo)
                deve_desenhar_horizontal_extra = altura_maxima_valida < 300.0
                posicao_y_topo = 292.2  # 300cm - 10cm + 2.2cm (altura máxima permitida - altura do sarrafo + altura do retângulo base)
                
                # Primeiro, coletar todos os horizontais válidos para identificar o último
                horizontais_validos = []
                for j in range(len(positions)):
                    posicao_y = calcular_posicao_horizontal(j, altura_base, altura_minima_valida, altura_maxima)
                    if posicao_y is not None:
                        horizontais_validos.append((j, posicao_y))
                
                # Desenhar sarrafos horizontais usando posições configuradas, mas APENAS até altura_minima_valida
                for idx, (j, posicao_y_original) in enumerate(horizontais_validos):
                    posicao_relativa = positions[j]
                    posicao_y = posicao_y_original
                    
                    # Se altura >= 300cm e este é o último horizontal válido, mover para 292.2cm
                    if not deve_desenhar_horizontal_extra and idx == len(horizontais_validos) - 1:
                        # Este é o último horizontal válido, mover para 292.2cm (290cm + 2.2cm do retângulo base)
                        posicao_y = posicao_y_topo
                        print(f"[HORIZONTAL TOPO] Movendo último horizontal válido de {posicao_y_original:.2f}cm para o topo (292.2cm) pois altura >= 300cm")
                    
                    print(f"[DEBUG HORIZONTAIS] Posição {j+1}: relativa={posicao_relativa}cm, absoluta={posicao_y:.2f}")
                    print(f"[DEBUG HORIZONTAIS] ✓ Desenhando sarrafo horizontal {num_retangulos_horizontais+1} em y={posicao_y:.2f}")
                    
                    # Adicionar posição Y à lista acumulada (para usar nas cotas verticais da última grade)
                    if posicao_y not in todas_posicoes_y_horizontais:
                        todas_posicoes_y_horizontais.append(posicao_y)
                        print(f"[DEBUG ACUMULO] Adicionada posição Y {posicao_y:.2f} à lista (total: {len(todas_posicoes_y_horizontais)})")
                    
                    # Selecionar o layer apropriado: TODOS os sarrafos horizontais de 10cm usam o mesmo layer (primeiro_horizontal)
                    layer_horizontal = config_manager.get_config("layers", "primeiro_horizontal")
                    
                    script += f"""LAYER
S {layer_horizontal}

; Sarrafo horizontal {num_retangulos_horizontais+1}
_ZOOM
C {x_offset+grade['largura']/2},{y_inicial+posicao_y+5} 5
;
"""
                    # LIMITAÇÃO: Sarrafos horizontais limitados a 300cm
                    largura_grade_original = grade['largura']
                    largura_grade_desenhar = min(largura_grade_original, 300.0)  # Limitar a 300cm
                    precisa_sarrafo_extra_horizontal = largura_grade_original > 300.0
                    
                    script += gerar_comandos_retangulo(
                        x_offset, y_inicial+posicao_y,
                        x_offset+largura_grade_desenhar, y_inicial+posicao_y+10,
                        use_mline,
                        is_horizontal=True
                    )
                    num_retangulos_horizontais += 1
                print(f"[DEBUG HORIZONTAIS] Total de horizontais desenhados: {num_retangulos_horizontais}")
                
                # HORIZONTAL EXTRA DO TOPO: Desenhar um horizontal extra 10cm abaixo do topo
                # NÃO desenhar se altura máxima for >= 300cm (3 metros)
                # Se altura >= 300cm, o último horizontal normal já foi movido para 292.2cm no loop acima
                
                # Verificar se há sarrafos com alturas diferentes (alguns mais altos que outros)
                tem_alturas_diferentes = altura_maxima_valida > altura_minima_valida
                if tem_alturas_diferentes:
                    print(f"[HORIZONTAL EXTRA] Há sarrafos com alturas diferentes: min={altura_minima_valida}cm, max={altura_maxima_valida}cm")
                else:
                    print(f"[HORIZONTAL EXTRA] Todos os sarrafos têm a mesma altura ({altura_maxima_valida}cm)")
                
                # Desenhar horizontal extra APENAS se altura < 300cm
                # Identificar posições X do primeiro e último sarrafo com altura máxima
                x_inicio_extra = None
                x_fim_extra = None
                
                # Se todos têm a mesma altura, o horizontal vai de ponta a ponta
                if not tem_alturas_diferentes:
                    x_inicio_extra = x_offset
                    x_fim_extra = x_offset + grade['largura']
                    print(f"[HORIZONTAL EXTRA] Todos têm mesma altura, horizontal de ponta a ponta: x={x_inicio_extra} até {x_fim_extra}")
                else:
                    # Se há alturas diferentes, identificar apenas os sarrafos altos
                    # IMPORTANTE: O horizontal deve ir apenas até o último sarrafo com altura máxima
                    # Não pode ir além dos sarrafos altos (não pode ficar "no ar")
                    
                    # Flag para parar quando encontrar sarrafo menor (deve estar acessível em todo o escopo)
                    encontrou_sarrafo_menor = False
                    
                    # Verificar sarrafo esquerdo
                    if altura_esquerda == altura_maxima_valida:
                        # Usar largura efetiva (já calculada anteriormente considerando grade adjacente)
                        largura_esquerdo = largura_sarrafo_esq
                        x_inicio_extra = x_offset
                        x_fim_extra = x_offset + largura_esquerdo
                        print(f"[HORIZONTAL EXTRA] Sarrafo esquerdo é alto: x={x_inicio_extra} até {x_fim_extra}")
                    
                    # Verificar sarrafos centrais
                    # IMPORTANTE: 
                    # - Se encontrar sarrafo menor DEPOIS de já ter encontrado sarrafos altos, parar (não atravessar)
                    # - Se encontrar sarrafo menor ANTES de encontrar sarrafos altos, continuar (pode atravessar para chegar aos altos)
                    if 'larguras_detalhes' in grade and grade['larguras_detalhes']:
                        # Recalcular num_sarrafos_para_desenhar para o horizontal extra
                        num_sarrafos_preenchidos_extra = 0
                        for k in range(min(4, len(grade['larguras_detalhes']))):  # Apenas índices 0-3
                            if grade['larguras_detalhes'][k] > 0:
                                num_sarrafos_preenchidos_extra = k + 1
                            else:
                                break
                        num_centrals_extra = num_sarrafos_preenchidos_extra
                        num_sarrafos_para_desenhar_extra = max(0, num_centrals_extra - 1)  # Sempre não desenhar o último
                        
                        posicao_atual = 0
                        encontrou_sarrafo_alto_antes = False  # Flag para saber se já encontrou sarrafo alto antes
                        for k in range(num_sarrafos_para_desenhar_extra):
                            # Se já encontrou sarrafo menor DEPOIS de ter encontrado sarrafo alto, parar
                            if encontrou_sarrafo_menor and encontrou_sarrafo_alto_antes:
                                print(f"[HORIZONTAL EXTRA] Parando: encontrou sarrafo menor após sarrafos altos no índice {k+1}")
                                break
                            
                            distancia_detalhe = grade['larguras_detalhes'][k]
                            posicao_centro_sarrafo = posicao_atual + distancia_detalhe
                            
                            # Verificar altura deste sarrafo central (usar altura ajustada)
                            if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > k+1:
                                altura_sarrafo_central_original = grade['alturas_detalhes'][k+1]
                                altura_sarrafo_central = ajustar_altura(altura_sarrafo_central_original) if altura_sarrafo_central_original > 0 else 0
                            else:
                                altura_sarrafo_central = altura_esquerda if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > 0 else ajustar_altura(grade['esquerda']) if grade['esquerda'] > 0 else 0
                            
                            if altura_sarrafo_central == altura_maxima_valida and altura_sarrafo_central > 0:
                                # Sarrafo é alto: atualizar x_fim_extra
                                encontrou_sarrafo_alto_antes = True  # Marcar que encontrou sarrafo alto
                                encontrou_sarrafo_menor = False  # Resetar flag de sarrafo menor (pode ter encontrado antes)
                                largura_sarrafo = 3.5
                                posicao_esquerda = posicao_centro_sarrafo - largura_sarrafo/2
                                x_esquerda_sarrafo = x_offset + posicao_esquerda
                                x_direita_sarrafo = x_offset + posicao_esquerda + largura_sarrafo
                                
                                # Atualizar início se for o primeiro sarrafo alto encontrado
                                if x_inicio_extra is None:
                                    x_inicio_extra = x_esquerda_sarrafo
                                # Atualizar o fim para este sarrafo alto (último contíguo)
                                x_fim_extra = x_direita_sarrafo
                                print(f"[HORIZONTAL EXTRA] Sarrafo central {k+1} é alto: x={x_esquerda_sarrafo} até {x_direita_sarrafo}")
                            else:
                                # Sarrafo NÃO é alto
                                if encontrou_sarrafo_alto_antes:
                                    # Se já encontrou sarrafo alto antes, parar aqui (não atravessar)
                                    encontrou_sarrafo_menor = True
                                    print(f"[HORIZONTAL EXTRA] Sarrafo central {k+1} NÃO é alto (altura={altura_sarrafo_central}, max={altura_maxima_valida}), parando busca (já encontrou sarrafos altos antes)")
                                    break
                                else:
                                    # Se ainda não encontrou sarrafo alto, continuar procurando (pode atravessar)
                                    print(f"[HORIZONTAL EXTRA] Sarrafo central {k+1} NÃO é alto (altura={altura_sarrafo_central}, max={altura_maxima_valida}), mas continuando busca (ainda não encontrou sarrafos altos)")
                            
                            posicao_atual = posicao_centro_sarrafo
                    
                    # Verificar sarrafo direito APENAS se ele tiver altura máxima E não tiver encontrado sarrafo menor antes
                    # Se tiver aberturas direitas, o sarrafo direito será menor e não deve ser considerado
                    # IMPORTANTE: Se encontrou sarrafo menor no meio, não verificar o sarrafo direito (não pode atravessar)
                    if not encontrou_sarrafo_menor and altura_direita == altura_maxima_valida:
                        # Usar largura efetiva (já calculada anteriormente considerando grade adjacente)
                        largura_direito = largura_sarrafo_dir
                        x_esquerda_direito = x_offset + grade['largura'] - largura_direito
                        x_direita_direito = x_offset + grade['largura']
                        
                        # Atualizar início se for o primeiro sarrafo alto encontrado
                        if x_inicio_extra is None:
                            x_inicio_extra = x_esquerda_direito
                        # Sempre atualizar o fim para o último sarrafo alto encontrado
                        # IMPORTANTE: Só atualizar se o sarrafo direito realmente for alto E não encontrou sarrafo menor antes
                        x_fim_extra = x_direita_direito
                        print(f"[HORIZONTAL EXTRA] Sarrafo direito é alto: x={x_esquerda_direito} até {x_direita_direito}")
                    else:
                        # Se encontrou sarrafo menor antes OU o sarrafo direito não é alto, não atualizar x_fim_extra
                        # O x_fim_extra já foi definido pelos sarrafos centrais ou esquerdo (último contíguo)
                        if encontrou_sarrafo_menor:
                            print(f"[HORIZONTAL EXTRA] Encontrou sarrafo menor antes, não verificando sarrafo direito (parando no último sarrafo alto contíguo)")
                        else:
                            print(f"[HORIZONTAL EXTRA] Sarrafo direito NÃO é alto (altura={altura_direita}, max={altura_maxima_valida}), não atualizando x_fim_extra")
                
                # Desenhar horizontal extra APENAS se altura < 300cm
                if deve_desenhar_horizontal_extra and x_inicio_extra is not None and x_fim_extra is not None:
                    # Posição Y do horizontal extra: 10cm abaixo do topo dos sarrafos altos
                    posicao_y_extra = altura_base + altura_maxima_valida - 10
                    print(f"[HORIZONTAL EXTRA] Desenhando horizontal extra 10cm abaixo do topo (y={posicao_y_extra:.2f})")
                    print(f"[HORIZONTAL EXTRA] Horizontal vai de x={x_inicio_extra:.2f} até x={x_fim_extra:.2f}")
                    
                    # Selecionar o layer apropriado
                    layer_horizontal = config_manager.get_config("layers", "primeiro_horizontal")
                    
                    # LIMITAÇÃO: Sarrafos horizontais limitados a 300cm
                    largura_horizontal_extra = x_fim_extra - x_inicio_extra
                    if largura_horizontal_extra > 300.0:
                        # Limitar horizontal extra a 300cm
                        x_fim_extra_limitado = x_inicio_extra + 300.0
                        precisa_sarrafo_extra_horizontal_extra = True
                    else:
                        x_fim_extra_limitado = x_fim_extra
                        precisa_sarrafo_extra_horizontal_extra = False
                    
                    # Desenhar um único horizontal apenas até o último sarrafo com altura máxima
                    script += f"""LAYER
S {layer_horizontal}

; Sarrafo horizontal extra do topo (10 cm abaixo do topo, apenas até sarrafos altos)
_ZOOM
C {x_inicio_extra+(x_fim_extra_limitado-x_inicio_extra)/2},{y_inicial+posicao_y_extra+5} 5
;
"""
                    script += gerar_comandos_retangulo(
                        x_inicio_extra, y_inicial+posicao_y_extra,
                        x_fim_extra_limitado, y_inicial+posicao_y_extra+10,
                        use_mline,
                        is_horizontal=True
                    )
                    print(f"[HORIZONTAL EXTRA] ✓ Desenhado horizontal extra: x={x_inicio_extra:.2f} até {x_fim_extra:.2f}, y={posicao_y_extra:.2f}")
                    
                    # Adicionar posição Y à lista acumulada
                    if posicao_y_extra not in todas_posicoes_y_horizontais:
                        todas_posicoes_y_horizontais.append(posicao_y_extra)
                        print(f"[DEBUG ACUMULO] Adicionada posição Y extra {posicao_y_extra:.2f} à lista (total: {len(todas_posicoes_y_horizontais)})")
                else:
                    print(f"[HORIZONTAL EXTRA] ⚠️ Nenhum sarrafo encontrado, não desenhando horizontal extra")
            else:
                # Usar lógica antiga se não houver alturas dos detalhes
                print("Usando lógica antiga para sarrafos horizontais")
                num_retangulos_horizontais = calcular_num_retangulos_horizontais(altura_maxima)
                print(f"Desenhando {num_retangulos_horizontais} sarrafos horizontais")
                
                # Encontrar a altura mínima entre os sarrafos
                if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > 0:
                    altura_minima = min(altura_esquerda, altura_direita, min(grade['alturas']))
                else:
                    altura_minima = min(grade['esquerda'], grade['direita'], min(grade['alturas']))
                if altura_minima == 0:  # Se algum sarrafo não for usado
                    altura_minima = altura_maxima
                
                for j in range(num_retangulos_horizontais):
                    posicao_y = calcular_posicao_horizontal(j, altura_base, altura_minima)
                    print(f"Desenhando sarrafo horizontal {j+1} em y={posicao_y}")
                    
                    # Adicionar posição Y à lista acumulada (para usar nas cotas verticais da última grade)
                    if posicao_y is not None and posicao_y not in todas_posicoes_y_horizontais:
                        todas_posicoes_y_horizontais.append(posicao_y)
                        print(f"[DEBUG ACUMULO ANTIGA] Adicionada posição Y {posicao_y:.2f} à lista (total: {len(todas_posicoes_y_horizontais)})")
                    
                    # Selecionar o layer apropriado: TODOS os sarrafos horizontais de 10cm usam o mesmo layer (primeiro_horizontal)
                    layer_horizontal = config_manager.get_config("layers", "primeiro_horizontal")
                    
                    script += f"""LAYER
S {layer_horizontal}

; Sarrafo horizontal {j+1}
_ZOOM
C {x_offset+grade['largura']/2},{y_inicial+posicao_y+5} 5
;
"""
                    # LIMITAÇÃO: Sarrafos horizontais limitados a 300cm
                    largura_grade_original_antiga = grade['largura']
                    largura_grade_desenhar_antiga = min(largura_grade_original_antiga, 300.0)  # Limitar a 300cm
                    precisa_sarrafo_extra_horizontal_antiga = largura_grade_original_antiga > 300.0
                    
                    script += gerar_comandos_retangulo(
                        x_offset, y_inicial+posicao_y,
                        x_offset+largura_grade_desenhar_antiga, y_inicial+posicao_y+10,
                        use_mline,
                        is_horizontal=True
                    )
            
            # DESENHAR SARRAFO EXTRA SE NECESSÁRIO
            # Verificar se alguma dimensão ultrapassou 300cm
            precisa_sarrafo_extra = False
            altura_extra_necessaria = 0
            
            # Verificar alturas dos sarrafos verticais
            if altura_esquerdo_original > 300.0:
                precisa_sarrafo_extra = True
                altura_extra_necessaria = max(altura_extra_necessaria, altura_esquerdo_original - 300.0)
            if altura_direito_original > 300.0:
                precisa_sarrafo_extra = True
                altura_extra_necessaria = max(altura_extra_necessaria, altura_direito_original - 300.0)
            
            # Verificar largura da grade
            if grade['largura'] > 300.0:
                precisa_sarrafo_extra = True
            
            # Verificar sarrafos centrais
            if 'alturas_detalhes' in grade and grade['alturas_detalhes']:
                for altura_detalhe in grade['alturas_detalhes']:
                    if altura_detalhe > 300.0:
                        precisa_sarrafo_extra = True
                        altura_extra_necessaria = max(altura_extra_necessaria, altura_detalhe - 300.0)
            
            # Se precisa de sarrafo extra, coletar informações (sem desenhar ainda)
            if precisa_sarrafo_extra:
                # Armazenar informações para cálculo de quantidade de sarrafos extras
                # Coletar informações de todos os sarrafos desta grade
                quantidade_sarrafos_grade = 0
                diferenca_altura_grade = 0  # Diferença da altura para 300cm (mesma para todos os sarrafos da grade)
                
                # Encontrar a altura máxima da grade (todos os sarrafos têm a mesma altura)
                altura_maxima_grade = 0
                if altura_esquerdo_original > altura_maxima_grade:
                    altura_maxima_grade = altura_esquerdo_original
                if altura_direito_original > altura_maxima_grade:
                    altura_maxima_grade = altura_direito_original
                
                # Verificar sarrafos centrais para encontrar altura máxima
                if 'alturas_detalhes' in grade and grade['alturas_detalhes']:
                    for altura_detalhe in grade['alturas_detalhes']:
                        if altura_detalhe > altura_maxima_grade:
                            altura_maxima_grade = altura_detalhe
                
                # Calcular diferença da altura máxima para 300cm
                if altura_maxima_grade > 300.0:
                    diferenca_altura_grade = altura_maxima_grade - 300.0
                
                # Contar sarrafo esquerdo
                if altura_esquerdo_original > 0:
                    quantidade_sarrafos_grade += 1
                
                # Contar sarrafo direito
                if altura_direito_original > 0:
                    quantidade_sarrafos_grade += 1
                
                # Contar sarrafos centrais
                if 'alturas_detalhes' in grade and grade['alturas_detalhes']:
                    # Contar apenas os sarrafos centrais preenchidos (índices 1-4, que correspondem aos sarrafos centrais)
                    num_sarrafos_preenchidos_contagem = 0
                    for k in range(min(4, len(grade['larguras_detalhes']))):  # Apenas índices 0-3
                        if grade['larguras_detalhes'][k] > 0:
                            num_sarrafos_preenchidos_contagem = k + 1
                        else:
                            break
                    
                    # Contar sarrafos centrais (excluindo o último que não é desenhado)
                    num_centrals_contagem = num_sarrafos_preenchidos_contagem
                    num_sarrafos_centrais_contagem = max(0, num_centrals_contagem - 1)  # Sempre não contar o último
                    quantidade_sarrafos_grade += num_sarrafos_centrais_contagem
                
                # Armazenar informações para cálculo final (sem desenhar ainda)
                info_sarrafos_extras.append({
                    'quantidade_sarrafos': quantidade_sarrafos_grade,
                    'diferenca_altura': diferenca_altura_grade
                })
            
            # Calcular posições para as cotas
            # Usar larguras efetivas (já calculadas anteriormente considerando grades adjacentes)
            largura_esquerdo = largura_sarrafo_esq
            largura_direito = largura_sarrafo_dir
            
            # Posição da ponta esquerda do sarrafo esquerdo
            ponta_esquerda = x_offset
            # Posição da ponta direita do sarrafo direito
            ponta_direita = x_offset + grade['largura']
            
            # Posição Y das cotas: 15cm abaixo do fundo dos verticais
            y_cota = y_inicial + altura_base - 15
            
            # Se há sarrafos centrais desenhados
            if quantidade_sarrafos > 0 and 'larguras_detalhes' in grade and grade['larguras_detalhes']:
                # Calcular posições dos centros dos sarrafos centrais (usar a mesma lógica do desenho)
                posicoes_centros = []
                posicao_x = 0  # Ponto de partida: ponta esquerda do sarrafo esquerdo
                
                # Contar quantos sarrafos centrais estão preenchidos
                # IMPORTANTE: Contar apenas os primeiros 4 campos (índices 0-3), pois o índice 4 é apenas distância até extremidade
                num_sarrafos_preenchidos = 0
                for k in range(min(4, len(grade['larguras_detalhes']))):  # Apenas índices 0-3 (sarrafo 1, 2, 3, 4)
                    if grade['larguras_detalhes'][k] > 0:
                        num_sarrafos_preenchidos = k + 1
                    else:
                        break
                
                # Verificar se há sobra à direita (índice 4 > 0)
                # O índice 4 não é um sarrafo, é apenas a distância do último sarrafo até a ponta direita
                tem_sobra_direita = (
                    len(grade['larguras_detalhes']) >= 5 and grade['larguras_detalhes'][4] > 0
                )
                
                # Calcular número de centrais:
                # Os índices 0-3 representam sarrafos centrais (1, 2, 3, 4)
                # O índice 4 é apenas distância, não é um sarrafo
                num_centrals = num_sarrafos_preenchidos
                
                # Calcular posições apenas dos sarrafos que serão desenhados
                # REGRA: Sempre não desenhar o último sarrafo central preenchido
                num_sarrafos_para_desenhar = max(0, num_centrals - 1)  # Sempre não desenhar o último
                
                for k in range(num_sarrafos_para_desenhar):
                    distancia_detalhe = grade['larguras_detalhes'][k]
                    posicao_centro = posicao_x + distancia_detalhe
                    posicoes_centros.append(posicao_centro)
                    posicao_x = posicao_centro  # Atualizar para o próximo sarrafo
                
                # 1. Cota da ponta esquerda até o centro do primeiro sarrafo central
                if posicoes_centros:
                    primeiro_centro = posicoes_centros[0]
                    script += f""";
_DIMLINEAR
{x_offset},{y_cota}
{x_offset+primeiro_centro},{y_cota}
{x_offset + primeiro_centro/2},{y_cota-5}
;
;
"""
                
                # 2. Cotas entre os centros dos sarrafos centrais
                # NOTA: Usar idx_cota em vez de i para evitar sobrescrever a variável i do loop externo
                for idx_cota in range(len(posicoes_centros) - 1):
                    centro_atual = posicoes_centros[idx_cota]
                    proximo_centro = posicoes_centros[idx_cota + 1]
                    script += f""";
_DIMLINEAR
{x_offset+centro_atual},{y_cota}
{x_offset+proximo_centro},{y_cota}
{x_offset+centro_atual + (proximo_centro - centro_atual)/2},{y_cota-5}
;
;
"""
                
                # 3. Cota do centro do último sarrafo central até a ponta direita
                # Usar o último centro desenhado (não o último preenchido)
                ultimo_centro_desenhado = posicoes_centros[-1]
                script += f""";
_DIMLINEAR
{x_offset+ultimo_centro_desenhado},{y_cota}
{x_offset+grade['largura']},{y_cota}
{x_offset+ultimo_centro_desenhado + (grade['largura'] - ultimo_centro_desenhado)/2},{y_cota-5}
;
;
"""
            else:
                # Se não há sarrafos centrais, cota direta da ponta esquerda até a ponta direita
                script += f""";
_DIMLINEAR
{x_offset},{y_cota}
{x_offset+grade['largura']},{y_cota}
{x_offset + grade['largura']/2},{y_cota-5}
;
;
"""

            # Adicionar cotas verticais para os sarrafos horizontais APENAS na última grade
            # Regra: Cotas verticais sempre aparecem na última grade (se há 1 grade vai nela, se 2 vai na segunda, se 3 vai na terceira)
            is_ultima_grade = (i == len(grades_ativas) - 1)
            
            print(f"[DEBUG COTAS VERTICAIS CHECK] i={i}, len(grades_ativas)={len(grades_ativas)}, is_ultima_grade={is_ultima_grade}")
            print(f"[DEBUG COTAS VERTICAIS CHECK] todas_posicoes_y_horizontais tem {len(todas_posicoes_y_horizontais)} elementos")
            
            if is_ultima_grade:
                print(f"\n[COTAS VERTICAIS] ========== GERANDO COTAS VERTICAIS ==========")
                print(f"[COTAS VERTICAIS] Última grade (índice {i} de {len(grades_ativas)-1})")
                print(f"[COTAS VERTICAIS] Total de posições Y acumuladas: {len(todas_posicoes_y_horizontais)}")
                print(f"[COTAS VERTICAIS] Posições Y acumuladas: {todas_posicoes_y_horizontais}")
                print(f"[COTAS VERTICAIS] num_retangulos_horizontais nesta grade: {num_retangulos_horizontais}")
                
                # Cota total vertical (sempre gerada na última grade)
                script += f""";
_DIMLINEAR
{x_offset+grade['largura']},{y_inicial+altura_base}
{x_offset+grade['largura']},{y_inicial+altura_base+altura_original_ajustada}
{x_offset+grade['largura']+50},{y_inicial+altura_base+altura_original_ajustada/2}
;
;
"""
            
                first_horizontal_y = None  # Inicializar antes do bloco
                # Verificar se há sarrafos horizontais de TODAS as grades para gerar cotas
                # Usar a lista acumulada de todas as posições Y de todas as grades do arquivo
                if todas_posicoes_y_horizontais:
                    print(f"[COTAS VERTICAIS] ✓ Lista tem {len(todas_posicoes_y_horizontais)} posições - GERANDO COTAS")
                    # Usar todas as posições Y acumuladas de todas as grades do arquivo
                    posicoes_y_unicas = sorted(set(todas_posicoes_y_horizontais))
                    print(f"[COTAS VERTICAIS] Usando {len(posicoes_y_unicas)} posições Y únicas de todas as grades do arquivo")
                    
                    # Usar um set para rastrear cotas já adicionadas (baseado nas coordenadas reais)
                    cotas_adicionadas = set()  # Set de tuplas (x, y1, y2)
                    
                    # Se houver sarrafos horizontais desenhados, gerar todas as cotas verticais
                    # Cota do topo da base até o fundo do primeiro sarrafo horizontal
                    first_horizontal_y = posicoes_y_unicas[0]
                    cota_key_base = (x_offset+grade['largura'], y_inicial+altura_base, y_inicial+first_horizontal_y)
                    if cota_key_base not in cotas_adicionadas:
                        cotas_adicionadas.add(cota_key_base)
                        script += f""";
_DIMLINEAR
{x_offset+grade['largura']},{y_inicial+altura_base}
{x_offset+grade['largura']},{y_inicial+first_horizontal_y}
{x_offset+grade['largura']+30},{y_inicial+altura_base+(first_horizontal_y-altura_base)/2}
;
;
"""
                    
                    # Gerar cotas para cada sarrafo horizontal (sem duplicatas)
                    for idx, posicao_y in enumerate(posicoes_y_unicas):
                        # Cota da largura do sarrafo horizontal (10cm)
                        cota_key_largura = (x_offset+grade['largura'], y_inicial+posicao_y, y_inicial+posicao_y+10)
                        if cota_key_largura not in cotas_adicionadas:
                            cotas_adicionadas.add(cota_key_largura)
                            script += f""";
_DIMLINEAR
{x_offset+grade['largura']},{y_inicial+posicao_y}
{x_offset+grade['largura']},{y_inicial+posicao_y+10}
{x_offset+grade['largura']+30},{y_inicial+posicao_y+5}
;
;
"""
                        
                        # Se existir próximo sarrafo horizontal, adicionar cota da distância entre eles
                        if idx < len(posicoes_y_unicas) - 1:
                            proxima_posicao_y = posicoes_y_unicas[idx + 1]
                            cota_key_entre = (x_offset+grade['largura'], y_inicial+posicao_y+10, y_inicial+proxima_posicao_y)
                            if cota_key_entre not in cotas_adicionadas:
                                cotas_adicionadas.add(cota_key_entre)
                                script += f""";
_DIMLINEAR
{x_offset+grade['largura']},{y_inicial+posicao_y+10}
{x_offset+grade['largura']},{y_inicial+proxima_posicao_y}
{x_offset+grade['largura']+30},{y_inicial+posicao_y+10+(proxima_posicao_y-(posicao_y+10))/2}
;
;
"""
                    
                    # Cota do último sarrafo horizontal até o topo (apenas uma vez)
                    # Só gerar se a distância for maior que 0 (evitar cota 0)
                    ultimo_posicao_y = posicoes_y_unicas[-1]
                    distancia_ate_topo = (altura_base + altura_original_ajustada) - (ultimo_posicao_y + 10)
                    if distancia_ate_topo > 0.1:  # Só gerar cota se a distância for maior que 0.1cm
                        cota_key_final = (x_offset+grade['largura'], y_inicial+ultimo_posicao_y+10, y_inicial+altura_base+altura_original_ajustada)
                        if cota_key_final not in cotas_adicionadas:
                            cotas_adicionadas.add(cota_key_final)
                            script += f""";
_DIMLINEAR
{x_offset+grade['largura']},{y_inicial+ultimo_posicao_y+10}
{x_offset+grade['largura']},{y_inicial+altura_base+altura_original_ajustada}
{x_offset+grade['largura']+30},{y_inicial+ultimo_posicao_y+10+(altura_base+altura_original_ajustada-(ultimo_posicao_y+10))/2}
;
;
"""
                    else:
                        print(f"[COTAS VERTICAIS] Distância do último horizontal até o topo é {distancia_ate_topo:.2f}cm (muito pequena), não gerando cota")
                else:
                    print(f"[COTAS VERTICAIS] ✗ AVISO: Lista de posições Y está VAZIA! Não há sarrafos horizontais para gerar cotas.")
                    print(f"[COTAS VERTICAIS] Isso pode significar que nenhum sarrafo horizontal foi desenhado ou as posições não foram acumuladas.")
                    print(f"[COTAS VERTICAIS] Apenas a cota total vertical será gerada (já gerada acima).")
            else:
                print(f"[DEBUG COTAS VERTICAIS CHECK] NÃO é última grade (i={i} de {len(grades_ativas)-1}), pulando geração de cotas verticais")
            
            # Cota horizontal total da grade (largura total)
            # Texto posicionado na mesma altura das cotas entre grades (y_inicial-40)
            script += f""";
_DIMLINEAR
{x_offset},{y_inicial}
{x_offset+grade['largura']},{y_inicial}
{x_offset+grade['largura']/2},{y_inicial-40}
;
;
"""

            # Atualizar x_offset com a largura da grade (para a próxima iteração)
            x_offset += grade['largura']
            
            print(f"[DEBUG FIM LOOP] Grade {i+1} processada. x_offset atualizado para: {x_offset}")

        # =================================================================
        # =================================================================
        # DESENHAR SARRAFO EXTRA ÚNICO (À DIREITA DA ÚLTIMA GRADE)
        # E CALCULAR QUANTIDADE DE SARRAFOS EXTRAS DE TODAS AS GRADES
        # =================================================================
        if info_sarrafos_extras:
            # Somar quantidade de sarrafos de todas as grades
            total_quantidade_sarrafos = sum(info['quantidade_sarrafos'] for info in info_sarrafos_extras)
            
            # Calcular quantidade de sarrafos extras necessários
            # Para cada grade: quantidade_sarrafos * diferenca_altura = quantidade_cm_da_grade
            # Somar todas as quantidades_cm e dividir por 300cm
            quantidade_total_cm = 0
            for info in info_sarrafos_extras:
                diferenca_ajustada = max(info['diferenca_altura'], 150.0)
                quantidade_total_cm += info['quantidade_sarrafos'] * diferenca_ajustada
            
            if quantidade_total_cm > 0:
                quantidade_sarrafos_extras = math.ceil(quantidade_total_cm / 300.0)
                
                print(f"[CALCULO SARRAFOS EXTRAS] Total sarrafos: {total_quantidade_sarrafos}, Quantidade total cm: {quantidade_total_cm}cm, Quantidade extras: {quantidade_sarrafos_extras}")
                
                # Posição do sarrafo extra: 60cm à direita da última grade (x_offset final)
                x_sarrafo_extra = x_offset + 60
                # Altura de 100cm do fundo dos demais sarrafos
                y_base_sarrafo_extra = y_inicial + altura_base + 100
                # Altura de 300cm a partir desse ponto
                y_topo_sarrafo_extra = y_base_sarrafo_extra + 300
                
                # Largura do sarrafo extra: 3.5cm (central)
                largura_sarrafo_extra = 3.5
                
                # Desenhar o sarrafo extra único
                script += f"""LAYER
S {layer_central}

; Sarrafo central extra (quando dimensões ultrapassam 300cm) - único para todas as grades
_ZOOM
C {x_sarrafo_extra+largura_sarrafo_extra/2},{y_base_sarrafo_extra+150} 5
;
"""
                script += gerar_comandos_retangulo(
                    x_sarrafo_extra, y_base_sarrafo_extra,
                    x_sarrafo_extra+largura_sarrafo_extra, y_topo_sarrafo_extra,
                    use_mline,
                    is_horizontal=False
                )
                
                # Cota do sarrafo extra com texto a 20cm à direita
                x_cota_extra = x_sarrafo_extra + largura_sarrafo_extra + 20
                y_texto_cota_extra = y_base_sarrafo_extra + 150  # Meio do sarrafo
                
                script += f"""LAYER
S {layer_cota}

;
_DIMLINEAR
{x_sarrafo_extra},{y_base_sarrafo_extra}
{x_sarrafo_extra},{y_topo_sarrafo_extra}
{x_cota_extra},{y_texto_cota_extra}
;
;
"""
                
                # Adicionar texto acima do sarrafo extra (40cm acima do topo)
                x_texto = x_sarrafo_extra
                y_texto = y_topo_sarrafo_extra + 40  # 40cm acima do topo
                
                # Texto com quebra de linha conforme especificação (centralizado)
                script += f"""LAYER
S nomenclatura

;
;
-STYLE
standard

8





;
_TEXT
J
MC
{x_texto},{y_texto}
0
Fornecer meio pontalete
_TEXT
J
MC
{x_texto},{y_texto-10}
0
de 3.5 x 7cm para
_TEXT
J
MC
{x_texto},{y_texto-20}
0
grade ({quantidade_sarrafos_extras} pcs)
;
"""
                print(f"[SARRAFO EXTRA] Desenhado sarrafo extra único em x={x_sarrafo_extra}, y_base={y_base_sarrafo_extra}, y_topo={y_topo_sarrafo_extra}")
                print(f"[TEXTO SARRAFOS EXTRAS] Adicionado texto em x={x_texto}, y={y_texto}, quantidade={quantidade_sarrafos_extras}")

        # DESENHAR COTAS ENTRE GRADES (APÓS TODAS AS GRADES PROCESSADAS)
        # =================================================================
        print(f"\n[DEBUG COTA ENTRE GRADES] ARQUIVO: {nome}")
        print(f"[DEBUG COTA ENTRE GRADES] EXTENSÃO: {'.A' if nome.endswith('.A') else '.B' if nome.endswith('.B') else 'OUTRO'}")
        print(f"[DEBUG COTA ENTRE GRADES] Iniciando cálculo de cotas entre grades")
        print(f"[DEBUG COTA ENTRE GRADES] Total de grades ativas: {len(grades_ativas)}")
        print(f"[DEBUG COTA ENTRE GRADES] Distâncias recebidas: {distancias}")

        # Resetar x_offset para calcular posições das cotas
        x_offset_cota = x_inicial

        # Desenhar cotas entre grades
        for j in range(len(grades_ativas) - 1):  # Para N grades, há N-1 cotas entre elas
            print(f"\n[DEBUG COTA #{j}] Calculando cota entre Grade {j+1} → Grade {j+2}")

            # Calcular posição da cota: no final da grade atual
            posicao_cota = x_offset_cota + grades_ativas[j]['largura']

            try:
                # Usar distâncias fornecidas se disponíveis
                # j=0: entre Grade 1 e Grade 2 → usar distancia_grade1
                # j=1: entre Grade 2 e Grade 3 → usar distancia_grade2
                if j == 0 and distancias and 'distancia_grade1' in distancias:
                    distancia_original = float(distancias['distancia_grade1'])
                    # Se for entre A e B (nome termina com .A ou .B), aumentar distância em 0cm
                    if nome.endswith('.A') or nome.endswith('.B'):
                        distancia = distancia_original
                        print(f"[✓] Grade {j+1}→{j+2}: {distancia}cm (do Excel {distancia_original}cm)")
                    else:
                        distancia = distancia_original
                        print(f"[✓] Grade {j+1}→{j+2}: {distancia}cm (do Excel)")
                elif j == 1 and distancias and 'distancia_grade2' in distancias:
                    distancia = float(distancias['distancia_grade2'])
                    print(f"[✓] Grade {j+2}→{j+3}: {distancia}cm (do Excel)")
                elif j == 1 and distancias and 'distancia_grade2' in distancias:
                    distancia = float(distancias['distancia_grade2'])
                    print(f"[✓] Grade {j+2}→{j+3}: {distancia}cm (do Excel)")
                else:
                    distancia = 22
                    print(f"[✗] Grade {j+1}→{j+2}: {distancia}cm (padrão)")

                # Desenhar cota entre grades
                print(f"[DEBUG COTA FIM] Desenhando cota HORIZONTAL entre grade {j+1} e {j+2}: x1={posicao_cota}, x2={posicao_cota+distancia}")
                script += f"""LAYER
S {layer_cota}

;
_DIMLINEAR
{posicao_cota},{y_inicial}
{posicao_cota+distancia},{y_inicial}
{posicao_cota+distancia/2},{y_inicial-40}
;
;
"""

            except (ValueError, AttributeError) as e:
                distancia = 22
                print(f"[ERRO COTA #{j}] Erro ao processar distância: {e}, usando padrão: {distancia}cm")
                script += f"""LAYER
S {layer_cota}

;
_DIMLINEAR
{posicao_cota},{y_inicial}
{posicao_cota+distancia},{y_inicial}
{posicao_cota+distancia/2},{y_inicial-40}
;
;
"""

            # Atualizar posição para próxima cota (largura + distância)
            x_offset_cota += grades_ativas[j]['largura'] + distancia

        # =================================================================

        # Adicionar os comandos de inserção dos blocos após todos os retângulos
        script += f"""LAYER
S {layer_base}

;
{blocks_script}
;
_ZOOM
E
;
"""

        # =================================================================
        # ADICIONAR LINHAS HORIZONTAIS ESPECIAIS (apenas para A)
        # =================================================================
        if nome.endswith('.A'):
            # Calcular posições X: 100cm antes do A até 350cm depois do final
            # x_inicial é o início da primeira grade (A)
            # x_offset_cota já está no final da última grade
            x_inicio_linha = x_inicial - 100.0
            x_fim_linha = x_offset_cota + 350.0  # Aumentado para 350cm
            
            # Calcular alturas
            # Altura sem descontos: usar altura_original_parametro (parâmetro original) se disponível, senão altura_pilar
            # altura_original_parametro é o parâmetro original passado para a função, antes de qualquer processamento
            if altura_original_parametro is not None and altura_original_parametro > 0:
                altura_sem_descontos = altura_original_parametro
                print(f"[LINHAS ESPECIAIS] Usando altura_original_parametro: {altura_sem_descontos}cm (sem descontos)")
            else:
                altura_sem_descontos = altura_pilar
                print(f"[LINHAS ESPECIAIS] Usando altura_pilar: {altura_sem_descontos}cm (pode ter descontos)")
            
            # Altura com descontos de 16-21 e laje, exceto aberturas
            # altura_original_ajustada já tem o ajuste de múltiplo de 5 (16-21) aplicado
            # Mas pode não ter desconto de laje se não foi aplicado
            # Vamos usar altura_original_ajustada como base, que já tem o ajuste de múltiplo de 5
            # O desconto de laje já está aplicado nos detalhes se o checkbox estava ativo
            # Então vamos pegar o maior detalhe que não foi afetado por aberturas
            maior_detalhe_sem_aberturas = 0.0
            for grade in grades_ativas:
                if 'alturas_detalhes' in grade and grade['alturas_detalhes']:
                    for altura_detalhe in grade['alturas_detalhes']:
                        if altura_detalhe > maior_detalhe_sem_aberturas:
                            maior_detalhe_sem_aberturas = altura_detalhe
            
            # Se encontrou um detalhe maior que altura_original_ajustada, usar ele
            # Caso contrário, usar altura_original_ajustada (que já tem ajuste de múltiplo de 5)
            if maior_detalhe_sem_aberturas > 0 and maior_detalhe_sem_aberturas < altura_sem_descontos:
                # O detalhe já tem descontos aplicados (laje + múltiplo de 5)
                altura_com_descontos_laje = maior_detalhe_sem_aberturas
                print(f"[LINHAS ESPECIAIS] Usando maior detalhe sem aberturas: {maior_detalhe_sem_aberturas}cm (já com descontos)")
            else:
                # Fallback: calcular altura com desconto de laje aproximado
                # Se altura_original_ajustada < altura_sem_descontos, já tem algum desconto
                # Caso contrário, usar altura_original_ajustada (só tem ajuste de múltiplo de 5)
                if altura_original_ajustada < altura_sem_descontos:
                    altura_com_descontos_laje = altura_original_ajustada
                    print(f"[LINHAS ESPECIAIS] Usando altura_original_ajustada: {altura_com_descontos_laje}cm (com ajuste múltiplo de 5)")
                else:
                    # Se são iguais, não há desconto de laje, apenas ajuste de múltiplo de 5
                    altura_com_descontos_laje = altura_original_ajustada
                    print(f"[LINHAS ESPECIAIS] Usando altura_original_ajustada: {altura_com_descontos_laje}cm (sem desconto de laje, apenas ajuste múltiplo de 5)")
            
            # Linha 1: Na altura do fundo (altura_base = 2.2cm) - descer 2.2cm mais para baixo
            y_linha_fundo = y_inicial  # y_inicial já está na base, sem adicionar altura_base
            script += f"""LAYER
S PEDIREITO

;
_LINETYPE
S
hidden

;
; Linha horizontal na altura do fundo (100cm antes do A até 350cm depois do final)
_LINE
{x_inicio_linha},{y_linha_fundo}
{x_fim_linha},{y_linha_fundo}

;
;
_LINETYPE
S
continuous

;
"""
            
            # Linha 2: Altura sem descontos (16-21, laje, aberturas)
            # Verificar se altura_sem_descontos é válida antes de desenhar
            if altura_sem_descontos > 0:
                y_linha_sem_descontos = y_inicial + altura_base + altura_sem_descontos - 2.2
                script += f"""LAYER
S PEDIREITO

;
_LINETYPE
S
hidden

;
; Linha horizontal na altura sem descontos (16-21, laje, aberturas)
_LINE
{x_inicio_linha},{y_linha_sem_descontos}
{x_fim_linha},{y_linha_sem_descontos}

;
;
_LINETYPE
S
continuous

;
"""
                print(f"[LINHA SEM DESCONTOS] Desenhada linha em y={y_linha_sem_descontos:.2f}cm (altura={altura_sem_descontos:.2f}cm)")
                
                # COTA VERTICAL APENAS NO ARQUIVO A (da linha do fundo até a linha sem descontos)
                if nome.endswith('.A'):
                    x_cota_vertical = x_inicio_linha + 40.0  # 40cm à direita do início das linhas
                    script += f"""LAYER
S {layer_cota}

;
_DIMLINEAR
{x_cota_vertical},{y_linha_fundo}
{x_cota_vertical},{y_linha_sem_descontos}
{x_cota_vertical-20},{y_linha_fundo + (y_linha_sem_descontos - y_linha_fundo)/2}
;
"""
                    print(f"[COTA VERTICAL A] Adicionada cota em x={x_cota_vertical:.2f}cm, de y={y_linha_fundo:.2f} até y={y_linha_sem_descontos:.2f}")
            else:
                print(f"[LINHA SEM DESCONTOS] ⚠️ Altura sem descontos é {altura_sem_descontos:.2f}cm, não desenhando linha")
            
            # Linha 3: Altura com descontos (16-21 e laje, exceto aberturas)
            y_linha_com_descontos = y_inicial + altura_base + altura_com_descontos_laje
            script += f"""LAYER
S PEDIREITO

;
_LINETYPE
S
hidden

;
; Linha horizontal na altura com descontos (16-21 e laje, exceto aberturas)
_LINE
{x_inicio_linha},{y_linha_com_descontos}
{x_fim_linha},{y_linha_com_descontos}

;
;
_LINETYPE
S
continuous

;
"""
            print(f"[LINHAS ESPECIAIS A] Adicionadas 3 linhas horizontais (apenas arquivo A):")
            print(f"  - Linha fundo: y={y_linha_fundo:.2f}cm (x={x_inicio_linha:.2f} até {x_fim_linha:.2f})")
            print(f"  - Linha sem descontos: y={y_linha_sem_descontos:.2f}cm (altura={altura_sem_descontos:.2f}cm)")
            print(f"  - Linha com descontos (laje): y={y_linha_com_descontos:.2f}cm (altura={altura_com_descontos_laje:.2f}cm)")

        return script
        
    except ValueError as e:
        print(f"Erro ao gerar script: {str(e)}")
        raise
    except Exception as e:
        print(f"Erro inesperado ao gerar script: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        raise

def atualizar_preview(*args):
    """
    Atualiza o preview do desenho.
    Args:
        *args: Argumentos opcionais passados pelo Tkinter (evento)
    """
    try:
        # Limpar o gráfico anterior
        ax.clear()
        
        # Lista para armazenar as grades ativas
        grades_ativas = []
        
        # Processar Grade 1
        if grade1_campos['ativar_var'].get():
            try:
                largura_horizontal = float(grade1_campos['largura_horizontal_entry'].get() or 0)
                sarr_esquerda = float(grade1_campos['sarr_esquerda_entry'].get() or 0)
                sarr_direita = float(grade1_campos['sarr_direita_entry'].get() or 0)
                sarr1_altura = float(grade1_campos['sarr1_altura_entry'].get() or 0)
                sarr2_altura = float(grade1_campos['sarr2_altura_entry'].get() or 0)
                sarr3_altura = float(grade1_campos['sarr3_altura_entry'].get() or 0)
                
                grades_ativas.append({
                    'largura': largura_horizontal,
                    'esquerda': sarr_esquerda,
                    'direita': sarr_direita,
                    'alturas': [sarr1_altura, sarr2_altura, sarr3_altura],
                    'esquerdo_central': grade1_campos['esquerdo_central_var'].get(),
                    'direito_central': grade1_campos['direito_central_var'].get(),
                    'distancias': [
                        float(grade1_campos['sarr1_distancia_entry'].get() or 0),
                        float(grade1_campos['sarr2_distancia_entry'].get() or 0),
                        float(grade1_campos['sarr3_distancia_entry'].get() or 0)
                    ]
                })
            except ValueError:
                pass
        
        # Processar Grade 2
        if grade2_campos['ativar_var'].get():
            try:
                largura_horizontal = float(grade2_campos['largura_horizontal_entry'].get() or 0)
                sarr_esquerda = float(grade2_campos['sarr_esquerda_entry'].get() or 0)
                sarr_direita = float(grade2_campos['sarr_direita_entry'].get() or 0)
                sarr1_altura = float(grade2_campos['sarr1_altura_entry'].get() or 0)
                sarr2_altura = float(grade2_campos['sarr2_altura_entry'].get() or 0)
                sarr3_altura = float(grade2_campos['sarr3_altura_entry'].get() or 0)
                
                grades_ativas.append({
                    'largura': largura_horizontal,
                    'esquerda': sarr_esquerda,
                    'direita': sarr_direita,
                    'alturas': [sarr1_altura, sarr2_altura, sarr3_altura],
                    'esquerdo_central': grade2_campos['esquerdo_central_var'].get(),
                    'direito_central': grade2_campos['direito_central_var'].get(),
                    'distancias': [
                        float(grade2_campos['sarr1_distancia_entry'].get() or 0),
                        float(grade2_campos['sarr2_distancia_entry'].get() or 0),
                        float(grade2_campos['sarr3_distancia_entry'].get() or 0)
                    ]
                })
            except ValueError:
                pass
        
        # Processar Grade 3
        if grade3_campos['ativar_var'].get():
            try:
                largura_horizontal = float(grade3_campos['largura_horizontal_entry'].get() or 0)
                sarr_esquerda = float(grade3_campos['sarr_esquerda_entry'].get() or 0)
                sarr_direita = float(grade3_campos['sarr_direita_entry'].get() or 0)
                sarr1_altura = float(grade3_campos['sarr1_altura_entry'].get() or 0)
                sarr2_altura = float(grade3_campos['sarr2_altura_entry'].get() or 0)
                sarr3_altura = float(grade3_campos['sarr3_altura_entry'].get() or 0)
                
                grades_ativas.append({
                    'largura': largura_horizontal,
                    'esquerda': sarr_esquerda,
                    'direita': sarr_direita,
                    'alturas': [sarr1_altura, sarr2_altura, sarr3_altura],
                    'esquerdo_central': grade3_campos['esquerdo_central_var'].get(),
                    'direito_central': grade3_campos['direito_central_var'].get(),
                    'distancias': [
                        float(grade3_campos['sarr1_distancia_entry'].get() or 0),
                        float(grade3_campos['sarr2_distancia_entry'].get() or 0),
                        float(grade3_campos['sarr3_distancia_entry'].get() or 0)
                    ]
                })
            except ValueError:
                pass
        
        if not grades_ativas:
            return
            
        # Configurações do grafo
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.set_title('Preview da Grade')
        
        # Desenhar cada grade
        x_offset = 0
        altura_base = 2.2  # Altura base padrão
        
        for i, grade in enumerate(grades_ativas):
            # Desenhar base
            ax.add_patch(plt.Rectangle((x_offset, 0), grade['largura'], altura_base, fill=False, edgecolor='black', linewidth=2))
            
            # Desenhar sarrafo esquerdo
            if grade['esquerdo_central']:
                ax.add_patch(plt.Rectangle((x_offset, altura_base), 3.5, grade['esquerda'], fill=False, edgecolor='g', linewidth=2))
            else:
                ax.add_patch(plt.Rectangle((x_offset, altura_base), 7, grade['esquerda'], fill=False, edgecolor='r', linewidth=2))
            
            # Desenhar sarrafos centrais (apenas os necessários)
            quantidade_sarrafos = calcular_quantidade_sarrafos_centrais(grade['largura'])
            for k in range(quantidade_sarrafos):
                altura = grade['alturas'][k]
                distancia = grade['distancias'][k]
                if altura > 0 and distancia > 0:
                    ax.add_patch(plt.Rectangle((x_offset+distancia+0.875-1.75, altura_base), 3.5, altura, fill=False, edgecolor='g', linewidth=2))
            
            # Desenhar sarrafo direito
            if grade['direito_central']:
                ax.add_patch(plt.Rectangle((x_offset+grade['largura']-3.5, altura_base), 3.5, grade['direita'], fill=False, edgecolor='g', linewidth=2))
            else:
                ax.add_patch(plt.Rectangle((x_offset+grade['largura']-7, altura_base), 7, grade['direita'], fill=False, edgecolor='r', linewidth=2))
            
            # Desenhar retângulos horizontais
            if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > 0:
                altura_esquerda = ajustar_altura(grade['alturas_detalhes'][0]) if grade['alturas_detalhes'][0] > 0 else 0
                # Usar altura específica do último campo preenchido para sarrafo da extremidade direita
                altura_direita = 0
                # NOTA: Usar idx_altura em vez de i para evitar sobrescrever a variável i do loop externo
                for idx_altura in range(len(grade['alturas_detalhes']) - 1, -1, -1):
                    if grade['alturas_detalhes'][idx_altura] > 0:
                        altura_direita = ajustar_altura(grade['alturas_detalhes'][idx_altura])
                        break
                altura_maxima = max(altura_esquerda, altura_direita, max(grade['alturas']))
                altura_minima = min(altura_esquerda, altura_direita, min(grade['alturas']))
            else:
                altura_maxima = max(grade['esquerda'], grade['direita'], max(grade['alturas']))
                altura_minima = min(grade['esquerda'], grade['direita'], min(grade['alturas']))
            if altura_minima == 0:
                altura_minima = altura_maxima
            
            # Obter todas as posições configuradas
            positions = config_manager.get_config("horizontal_positions", "positions")
            
            # Desenhar cada retângulo horizontal
            for j in range(len(positions)):
                posicao_y = calcular_posicao_horizontal(j, altura_base, altura_minima, altura_maxima)
                if posicao_y is not None:
                    ax.add_patch(plt.Rectangle(
                        (x_offset, posicao_y),
                        grade['largura'],
                        10,
                        fill=False,
                        edgecolor='blue',
                        linewidth=2
                    ))
            
            # Atualizar offset para próxima grade
            if i < len(grades_ativas) - 1:
                try:
                    distancia = float(distancia_grade1_entry.get() if i == 0 else distancia_grade2_entry.get() or 0)
                    x_offset += grade['largura'] + distancia
                except ValueError:
                    x_offset += grade['largura'] + 20  # Distância padrão se não especificada
        
        # Definir os limites do gráfico com uma margem
        all_x = x_offset
        # Usar altura específica do campo 0 para sarrafo da extremidade esquerda
        all_y = 0
        for grade in grades_ativas:
            if 'alturas_detalhes' in grade and grade['alturas_detalhes'] and len(grade['alturas_detalhes']) > 0:
                altura_esquerda = ajustar_altura(grade['alturas_detalhes'][0]) if grade['alturas_detalhes'][0] > 0 else 0
                # Usar altura específica do último campo preenchido para sarrafo da extremidade direita
                altura_direita = 0
                # NOTA: Usar idx_altura em vez de i para evitar sobrescrever a variável i do loop externo
                for idx_altura in range(len(grade['alturas_detalhes']) - 1, -1, -1):
                    if grade['alturas_detalhes'][idx_altura] > 0:
                        altura_direita = ajustar_altura(grade['alturas_detalhes'][idx_altura])
                        break
                altura_maxima = max(altura_esquerda, altura_direita, max(grade['alturas']))
            else:
                altura_maxima = max(grade['esquerda'], grade['direita'], max(grade['alturas']))
            all_y = max(all_y, altura_maxima)
        all_y += altura_base
        margin = 10
        ax.set_xlim(-margin, all_x + margin)
        ax.set_ylim(-margin, all_y + margin)
        
        # Manter a proporção
        ax.set_aspect('equal')
        
        # Atualizar o canvas
        canvas.draw()
        print("Preview atualizado com sucesso")
        
    except Exception as e:
        print(f"Erro ao atualizar preview: {str(e)}")
        print(f"Tipo do erro: {type(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")

def atualizar_informacoes():
    try:
        # Atualizar o preview do desenho
        atualizar_preview()
    except ValueError:
        print("Erro ao atualizar informações: Verifique os valores inseridos.")

def criar_janela_configuracoes():
    """Cria uma janela para configurar os layers, opções e templates"""
    config_window = tk.Toplevel(root)
    config_window.title("Configurações")
    config_window.geometry("700x600")
    config_window.resizable(False, False)
    
    # Frame principal
    main_frame = ttk.Frame(config_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Notebook para abas
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=10)
    
    # Aba de Layers
    layers_frame = ttk.LabelFrame(notebook, text="Layers", padding="10")
    notebook.add(layers_frame, text="Layers")
    
    # Criar campos para cada layer
    layer_entries = {}
    layer_config = config_manager.get_config("layers")
    
    # Criar um frame específico para layers horizontais
    horizontal_frame = ttk.LabelFrame(layers_frame, text="Layers Horizontais", padding="5")
    horizontal_frame.pack(fill="x", pady=5)
    
    # Campo para primeiro sarrafo horizontal
    primeiro_horizontal_frame = ttk.Frame(horizontal_frame)
    primeiro_horizontal_frame.pack(fill="x", pady=2)
    ttk.Label(primeiro_horizontal_frame, text="Primeiro Horizontal:").pack(side="left")
    primeiro_horizontal_entry = ttk.Entry(primeiro_horizontal_frame)
    primeiro_horizontal_entry.insert(0, layer_config.get("primeiro_horizontal", ""))
    primeiro_horizontal_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    layer_entries["primeiro_horizontal"] = primeiro_horizontal_entry
    
    # Campo para demais sarrafos horizontais
    demais_horizontais_frame = ttk.Frame(horizontal_frame)
    demais_horizontais_frame.pack(fill="x", pady=2)
    ttk.Label(demais_horizontais_frame, text="Demais Horizontais:").pack(side="left")
    demais_horizontais_entry = ttk.Entry(demais_horizontais_frame)
    demais_horizontais_entry.insert(0, layer_config.get("demais_horizontais", ""))
    demais_horizontais_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    layer_entries["demais_horizontais"] = demais_horizontais_entry
    
    # Frame para os demais layers
    outros_layers_frame = ttk.LabelFrame(layers_frame, text="Outros Layers", padding="5")
    outros_layers_frame.pack(fill="x", pady=5)
    
    # Adicionar os demais layers (exceto os horizontais)
    for key, value in layer_config.items():
        if key not in ["primeiro_horizontal", "demais_horizontais"]:
            frame = ttk.Frame(outros_layers_frame)
            frame.pack(fill="x", pady=2)
            
            ttk.Label(frame, text=key.capitalize() + ":").pack(side="left")
            entry = ttk.Entry(frame)
            entry.insert(0, value)
            entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
            layer_entries[key] = entry
    
    # Aba de Posições Horizontais
    positions_frame = ttk.LabelFrame(notebook, text="Posições Horizontais", padding="10")
    notebook.add(positions_frame, text="Posições")
    
    # Criar campos para cada posição horizontal
    position_entries = []
    positions = config_manager.get_config("horizontal_positions", "positions")
    
    for i, pos in enumerate(positions, 1):
        frame = ttk.Frame(positions_frame)
        frame.pack(fill="x", pady=2)
        
        ttk.Label(frame, text=f"Posição {i}:").pack(side="left")
        entry = ttk.Entry(frame)
        entry.insert(0, str(pos))
        entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
        position_entries.append(entry)
    
    # Aba de Opções de Desenho
    drawing_frame = ttk.LabelFrame(notebook, text="Opções de Desenho", padding="10")
    notebook.add(drawing_frame, text="Opções")
    
    # Campo para dimstyle
    dimstyle_frame = ttk.Frame(drawing_frame)
    dimstyle_frame.pack(fill="x", pady=2)
    
    ttk.Label(dimstyle_frame, text="Estilo de Cota:").pack(side="left")
    dimstyle_entry = ttk.Entry(dimstyle_frame)
    dimstyle_entry.insert(0, config_manager.get_config("drawing_options", "dimstyle"))
    dimstyle_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    # Campo para hatch_scale
    hatch_scale_frame = ttk.Frame(drawing_frame)
    hatch_scale_frame.pack(fill="x", pady=2)
    
    ttk.Label(hatch_scale_frame, text="Escala do Hatch:").pack(side="left")
    hatch_scale_entry = ttk.Entry(hatch_scale_frame)
    hatch_scale_entry.insert(0, str(config_manager.get_config("drawing_options", "hatch_scale")))
    hatch_scale_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    # Campo para hatch_angle
    hatch_angle_frame = ttk.Frame(drawing_frame)
    hatch_angle_frame.pack(fill="x", pady=2)
    
    ttk.Label(hatch_angle_frame, text="Ângulo do Hatch:").pack(side="left")
    hatch_angle_entry = ttk.Entry(hatch_angle_frame)
    hatch_angle_entry.insert(0, str(config_manager.get_config("drawing_options", "hatch_angle")))
    hatch_angle_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    # Campo para scale_factor
    scale_frame = ttk.Frame(drawing_frame)
    scale_frame.pack(fill="x", pady=2)
    
    ttk.Label(scale_frame, text="Fator de Escala:").pack(side="left")
    scale_entry = ttk.Entry(scale_frame)
    scale_entry.insert(0, str(config_manager.get_config("drawing_options", "scale_factor")))
    scale_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    # Checkbox para use_mline
    use_mline_frame = ttk.Frame(drawing_frame)
    use_mline_frame.pack(fill="x", pady=2)
    
    use_mline_var = tk.BooleanVar(value=config_manager.get_config("drawing_options", "use_mline"))
    ttk.Checkbutton(use_mline_frame, text="Usar MLine", variable=use_mline_var).pack(side="left")
    
    # Aba de Coordenadas
    coordinates_frame = ttk.LabelFrame(notebook, text="Coordenadas", padding="10")
    notebook.add(coordinates_frame, text="Coordenadas")
    
    # Campo para x_inicial
    x_inicial_frame = ttk.Frame(coordinates_frame)
    x_inicial_frame.pack(fill="x", pady=2)
    
    ttk.Label(x_inicial_frame, text="X Inicial:").pack(side="left")
    x_inicial_entry = ttk.Entry(x_inicial_frame)
    x_inicial_entry.insert(0, str(config_manager.get_config("coordinates", "x_inicial")))
    x_inicial_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    # Campo para y_inicial
    y_inicial_frame = ttk.Frame(coordinates_frame)
    y_inicial_frame.pack(fill="x", pady=2)
    
    ttk.Label(y_inicial_frame, text="Y Inicial:").pack(side="left")
    y_inicial_entry = ttk.Entry(y_inicial_frame)
    y_inicial_entry.insert(0, str(config_manager.get_config("coordinates", "y_inicial")))
    y_inicial_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    # Campo para altura_base
    altura_base_frame = ttk.Frame(coordinates_frame)
    altura_base_frame.pack(fill="x", pady=2)
    
    ttk.Label(altura_base_frame, text="Altura Base:").pack(side="left")
    altura_base_entry = ttk.Entry(altura_base_frame)
    altura_base_entry.insert(0, str(config_manager.get_config("coordinates", "altura_base")))
    altura_base_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    # Aba de Blocos
    blocks_frame = ttk.LabelFrame(notebook, text="Blocos", padding="10")
    notebook.add(blocks_frame, text="Blocos")
    
    # Campo para triangulo_esquerdo
    triangulo_esquerdo_frame = ttk.Frame(blocks_frame)
    triangulo_esquerdo_frame.pack(fill="x", pady=2)
    
    ttk.Label(triangulo_esquerdo_frame, text="Triângulo Esquerdo:").pack(side="left")
    triangulo_esquerdo_entry = ttk.Entry(triangulo_esquerdo_frame)
    triangulo_esquerdo_entry.insert(0, config_manager.get_config("blocks", "triangulo_esquerdo"))
    triangulo_esquerdo_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    # Campo para triangulo_direito
    triangulo_direito_frame = ttk.Frame(blocks_frame)
    triangulo_direito_frame.pack(fill="x", pady=2)
    
    ttk.Label(triangulo_direito_frame, text="Triângulo Direito:").pack(side="left")
    triangulo_direito_entry = ttk.Entry(triangulo_direito_frame)
    triangulo_direito_entry.insert(0, config_manager.get_config("blocks", "triangulo_direito"))
    triangulo_direito_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    # Frame para botões
    button_frame = ttk.Frame(config_window)
    button_frame.pack(fill=tk.X, pady=10)
    
    def salvar_configuracoes():
        # Atualizar layers
        for key, entry in layer_entries.items():
            config_manager.set_config(entry.get(), "layers", key)
        
        # Atualizar posições horizontais
        positions = [float(entry.get()) for entry in position_entries]
        config_manager.set_config(positions, "horizontal_positions", "positions")
        
        # Atualizar opções de desenho
        config_manager.set_config(dimstyle_entry.get(), "drawing_options", "dimstyle")
        config_manager.set_config(float(hatch_scale_entry.get()), "drawing_options", "hatch_scale")
        config_manager.set_config(float(hatch_angle_entry.get()), "drawing_options", "hatch_angle")
        config_manager.set_config(float(scale_entry.get()), "drawing_options", "scale_factor")
        config_manager.set_config(use_mline_var.get(), "drawing_options", "use_mline")
        
        # Atualizar coordenadas
        config_manager.set_config(float(x_inicial_entry.get()), "coordinates", "x_inicial")
        config_manager.set_config(float(y_inicial_entry.get()), "coordinates", "y_inicial")
        config_manager.set_config(float(altura_base_entry.get()), "coordinates", "altura_base")
        
        # Atualizar blocos
        config_manager.set_config(triangulo_esquerdo_entry.get(), "blocks", "triangulo_esquerdo")
        config_manager.set_config(triangulo_direito_entry.get(), "blocks", "triangulo_direito")
        
        # Salvar configuração
        if config_manager.save_config():
            messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")
            config_window.destroy()
        else:
            messagebox.showerror("Erro", "Erro ao salvar configurações!")
    
    ttk.Button(button_frame, text="Salvar", command=salvar_configuracoes).pack(side=tk.RIGHT, padx=5)
    ttk.Button(button_frame, text="Cancelar", command=config_window.destroy).pack(side=tk.RIGHT, padx=5)

    # Aba de Templates
    templates_frame = ttk.LabelFrame(notebook, text="Templates", padding="10")
    notebook.add(templates_frame, text="Templates")
    
    # Frame para lista de templates
    list_frame = ttk.Frame(templates_frame)
    list_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(list_frame, text="Templates Salvos:").pack(side=tk.LEFT)
    template_listbox = tk.Listbox(list_frame, height=5, width=40)
    template_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
    
    # Frame para descrição
    desc_frame = ttk.LabelFrame(templates_frame, text="Descrição", padding="5")
    desc_frame.pack(fill=tk.X, pady=5)
    
    description_text = tk.Text(desc_frame, height=3, width=40)
    description_text.pack(fill=tk.X, expand=True)
    
    # Frame para botões de template
    template_buttons_frame = ttk.Frame(templates_frame)
    template_buttons_frame.pack(fill=tk.X, pady=5)
    
    def atualizar_lista_templates():
        template_listbox.delete(0, tk.END)
        for name in config_manager.get_template_names():
            template_listbox.insert(tk.END, name)
    
    def carregar_template():
        selection = template_listbox.curselection()
        if selection:
            template_name = template_listbox.get(selection[0])
            if config_manager.load_template(template_name):
                # IMPORTANTE: Atualizar os campos da interface com os valores carregados do template
                # Isso garante que a interface mostre os valores corretos após carregar o template
                x_inicial_entry.delete(0, tk.END)
                x_inicial_entry.insert(0, str(config_manager.get_config("coordinates", "x_inicial")))
                y_inicial_entry.delete(0, tk.END)
                y_inicial_entry.insert(0, str(config_manager.get_config("coordinates", "y_inicial")))
                altura_base_entry.delete(0, tk.END)
                altura_base_entry.insert(0, str(config_manager.get_config("coordinates", "altura_base")))
                
                # Atualizar layers (usar layer_entries que é um dicionário)
                if "base" in layer_entries:
                    layer_entries["base"].delete(0, tk.END)
                    layer_entries["base"].insert(0, config_manager.get_config("layers", "base"))
                if "reforco" in layer_entries:
                    layer_entries["reforco"].delete(0, tk.END)
                    layer_entries["reforco"].insert(0, config_manager.get_config("layers", "reforco"))
                if "central" in layer_entries:
                    layer_entries["central"].delete(0, tk.END)
                    layer_entries["central"].insert(0, config_manager.get_config("layers", "central"))
                if "cota" in layer_entries:
                    layer_entries["cota"].delete(0, tk.END)
                    layer_entries["cota"].insert(0, config_manager.get_config("layers", "cota"))
                if "primeiro_horizontal" in layer_entries:
                    layer_entries["primeiro_horizontal"].delete(0, tk.END)
                    layer_entries["primeiro_horizontal"].insert(0, config_manager.get_config("layers", "primeiro_horizontal"))
                if "demais_horizontais" in layer_entries:
                    layer_entries["demais_horizontais"].delete(0, tk.END)
                    layer_entries["demais_horizontais"].insert(0, config_manager.get_config("layers", "demais_horizontais"))
                
                # Atualizar drawing_options
                dimstyle_entry.delete(0, tk.END)
                dimstyle_entry.insert(0, config_manager.get_config("drawing_options", "dimstyle"))
                hatch_scale_entry.delete(0, tk.END)
                hatch_scale_entry.insert(0, str(config_manager.get_config("drawing_options", "hatch_scale")))
                hatch_angle_entry.delete(0, tk.END)
                hatch_angle_entry.insert(0, str(config_manager.get_config("drawing_options", "hatch_angle")))
                scale_entry.delete(0, tk.END)
                scale_entry.insert(0, str(config_manager.get_config("drawing_options", "scale_factor")))
                use_mline_var.set(config_manager.get_config("drawing_options", "use_mline"))
                
                # Atualizar blocks
                triangulo_esquerdo_entry.delete(0, tk.END)
                triangulo_esquerdo_entry.insert(0, config_manager.get_config("blocks", "triangulo_esquerdo"))
                triangulo_direito_entry.delete(0, tk.END)
                triangulo_direito_entry.insert(0, config_manager.get_config("blocks", "triangulo_direito"))
                
                # IMPORTANTE: Atualizar posições horizontais (aba Posições)
                positions = config_manager.get_config("horizontal_positions", "positions")
                for i, entry in enumerate(position_entries):
                    if i < len(positions):
                        entry.delete(0, tk.END)
                        entry.insert(0, str(positions[i]))
                
                messagebox.showinfo("Sucesso", "Template carregado com sucesso!")
            else:
                messagebox.showerror("Erro", "Erro ao carregar template")
    
    def salvar_template():
        template_name = simpledialog.askstring("Salvar Template", "Nome do template:")
        if template_name:
            # IMPORTANTE: Atualizar self.config com os valores da interface ANTES de salvar o template
            # Isso garante que as coordenadas e outras configurações da interface sejam salvas
            config_manager.set_config(float(x_inicial_entry.get()), "coordinates", "x_inicial")
            config_manager.set_config(float(y_inicial_entry.get()), "coordinates", "y_inicial")
            config_manager.set_config(float(altura_base_entry.get()), "coordinates", "altura_base")
            
            # Atualizar layers (usar layer_entries que é um dicionário)
            for key, entry in layer_entries.items():
                config_manager.set_config(entry.get(), "layers", key)
            
            # Atualizar drawing_options
            config_manager.set_config(dimstyle_entry.get(), "drawing_options", "dimstyle")
            config_manager.set_config(float(hatch_scale_entry.get()), "drawing_options", "hatch_scale")
            config_manager.set_config(float(hatch_angle_entry.get()), "drawing_options", "hatch_angle")
            config_manager.set_config(float(scale_entry.get()), "drawing_options", "scale_factor")
            config_manager.set_config(use_mline_var.get(), "drawing_options", "use_mline")
            
            # Atualizar blocks
            config_manager.set_config(triangulo_esquerdo_entry.get(), "blocks", "triangulo_esquerdo")
            config_manager.set_config(triangulo_direito_entry.get(), "blocks", "triangulo_direito")
            
            # IMPORTANTE: Atualizar posições horizontais (aba Posições) antes de salvar template
            positions = [float(entry.get()) for entry in position_entries]
            config_manager.set_config(positions, "horizontal_positions", "positions")
            
            # Salvar configuração atual antes de salvar template
            config_manager.save_config()
            
            # Salvar o template e obter o nome final usado
            nome_original = template_name
            description = description_text.get("1.0", tk.END).strip()
            
            if config_manager.save_template(template_name, description):
                # Verificar se o nome foi alterado (adicionado sufixo)
                if nome_original in config_manager.templates:
                    # O nome original foi mantido
                    nome_final = nome_original
                else:
                    # Procurar pelo template com sufixo
                    for nome_template in config_manager.templates.keys():
                        if nome_template.startswith(nome_original + "."):
                            nome_final = nome_template
                            break
                    else:
                        nome_final = nome_original
                
                atualizar_lista_templates()
                
                if nome_final == nome_original:
                    messagebox.showinfo("Sucesso", f"Template '{nome_final}' salvo com sucesso!")
                else:
                    messagebox.showinfo("Sucesso", f"Template '{nome_original}' já existia. Salvo como '{nome_final}'!")
            else:
                messagebox.showerror("Erro", "Erro ao salvar template")
    
    def deletar_template():
        selection = template_listbox.curselection()
        if selection:
            template_name = template_listbox.get(selection[0])
            if messagebox.askyesno("Confirmar", f"Deseja realmente excluir o template {template_name}?"):
                if config_manager.delete_template(template_name):
                    atualizar_lista_templates()
                    messagebox.showinfo("Sucesso", "Template excluído com sucesso!")
                else:
                    messagebox.showerror("Erro", "Erro ao excluir template")
    
    def on_template_select(event):
        selection = template_listbox.curselection()
        if selection:
            template_name = template_listbox.get(selection[0])
            description = config_manager.get_template_description(template_name)
            description_text.delete("1.0", tk.END)
            description_text.insert("1.0", description)
    
    template_listbox.bind('<<ListboxSelect>>', on_template_select)
    
    ttk.Button(template_buttons_frame, text="Carregar", command=carregar_template).pack(side=tk.LEFT, padx=5)
    ttk.Button(template_buttons_frame, text="Salvar Atual", command=salvar_template).pack(side=tk.LEFT, padx=5)
    ttk.Button(template_buttons_frame, text="Excluir", command=deletar_template).pack(side=tk.LEFT, padx=5)
    
    # Carregar templates existentes
    atualizar_lista_templates()

def salvar_script_teste():
    try:
        # Obter valores dos campos
        pavimento = pavimento_entry.get()
        if not pavimento:
            raise ValueError("O campo Pavimento é obrigatório")
            
        nome = nome_entry.get()
        if not nome:
            raise ValueError("O campo Nome do Arquivo é obrigatório")
            
        # Lista para armazenar as grades ativas
        grades_ativas = []
        
        # Processar Grade 1
        if grade1_campos['ativar_var'].get():
            try:
                largura_horizontal = float(grade1_campos['largura_horizontal_entry'].get() or 0)
                sarr_esquerda = float(grade1_campos['sarr_esquerda_entry'].get() or 0)
                sarr_direita = float(grade1_campos['sarr_direita_entry'].get() or 0)
                sarr1_altura = float(grade1_campos['sarr1_altura_entry'].get() or 0)
                sarr2_altura = float(grade1_campos['sarr2_altura_entry'].get() or 0)
                sarr3_altura = float(grade1_campos['sarr3_altura_entry'].get() or 0)
                
                grades_ativas.append({
                    'largura': largura_horizontal,
                    'esquerda': sarr_esquerda,
                    'direita': sarr_direita,
                    'alturas': [sarr1_altura, sarr2_altura, sarr3_altura],
                    'esquerdo_central': grade1_campos['esquerdo_central_var'].get(),
                    'direito_central': grade1_campos['direito_central_var'].get(),
                    'distancias': [
                        float(grade1_campos['sarr1_distancia_entry'].get() or 0),
                        float(grade1_campos['sarr2_distancia_entry'].get() or 0),
                        float(grade1_campos['sarr3_distancia_entry'].get() or 0)
                    ]
                })
            except ValueError:
                print("Valores inválidos na Grade 1")
        
        # Processar Grade 2
        if grade2_campos['ativar_var'].get():
            try:
                largura_horizontal = float(grade2_campos['largura_horizontal_entry'].get() or 0)
                sarr_esquerda = float(grade2_campos['sarr_esquerda_entry'].get() or 0)
                sarr_direita = float(grade2_campos['sarr_direita_entry'].get() or 0)
                sarr1_altura = float(grade2_campos['sarr1_altura_entry'].get() or 0)
                sarr2_altura = float(grade2_campos['sarr2_altura_entry'].get() or 0)
                sarr3_altura = float(grade2_campos['sarr3_altura_entry'].get() or 0)
                
                grades_ativas.append({
                    'largura': largura_horizontal,
                    'esquerda': sarr_esquerda,
                    'direita': sarr_direita,
                    'alturas': [sarr1_altura, sarr2_altura, sarr3_altura],
                    'esquerdo_central': grade2_campos['esquerdo_central_var'].get(),
                    'direito_central': grade2_campos['direito_central_var'].get(),
                    'distancias': [
                        float(grade2_campos['sarr1_distancia_entry'].get() or 0),
                        float(grade2_campos['sarr2_distancia_entry'].get() or 0),
                        float(grade2_campos['sarr3_distancia_entry'].get() or 0)
                    ]
                })
            except ValueError:
                print("Valores inválidos na Grade 2")
        
        # Processar Grade 3
        if grade3_campos['ativar_var'].get():
            try:
                largura_horizontal = float(grade3_campos['largura_horizontal_entry'].get() or 0)
                sarr_esquerda = float(grade3_campos['sarr_esquerda_entry'].get() or 0)
                sarr_direita = float(grade3_campos['sarr_direita_entry'].get() or 0)
                sarr1_altura = float(grade3_campos['sarr1_altura_entry'].get() or 0)
                sarr2_altura = float(grade3_campos['sarr2_altura_entry'].get() or 0)
                sarr3_altura = float(grade3_campos['sarr3_altura_entry'].get() or 0)
                
                grades_ativas.append({
                    'largura': largura_horizontal,
                    'esquerda': sarr_esquerda,
                    'direita': sarr_direita,
                    'alturas': [sarr1_altura, sarr2_altura, sarr3_altura],
                    'esquerdo_central': grade3_campos['esquerdo_central_var'].get(),
                    'direito_central': grade3_campos['direito_central_var'].get(),
                    'distancias': [
                        float(grade3_campos['sarr1_distancia_entry'].get() or 0),
                        float(grade3_campos['sarr2_distancia_entry'].get() or 0),
                        float(grade3_campos['sarr3_distancia_entry'].get() or 0)
                    ]
                })
            except ValueError:
                print("Valores inválidos na Grade 3")
        
        if not grades_ativas:
            messagebox.showerror("Erro", "Nenhuma grade ativa para gerar o script")
            return
        
        # Gerar o script
        script = gerar_script_grade(pavimento, "TESTEGRADE", grades_ativas)
            
        # Salvar o script no arquivo de teste
        # Usar path resolver para obter caminho dinâmico
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from utils.robust_path_resolver import robust_path_resolver
        nome_arquivo = os.path.join(robust_path_resolver.get_project_root(), "output", "teste_grades.scr")
        with open(nome_arquivo, 'w', encoding='utf-16') as f:
            f.write(script)
        
        messagebox.showinfo("Sucesso", f"Script de teste salvo em {nome_arquivo}")
        
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao gerar script: {str(e)}")
        print(f"Erro inesperado ao gerar script: {str(e)}")

def gerar_script():
    try:
        # Obter valores dos campos
        pavimento = pavimento_entry.get()
        if not pavimento:
            raise ValueError("O campo Pavimento é obrigatório")
            
        nome = nome_entry.get()
        if not nome:
            raise ValueError("O campo Nome do Arquivo é obrigatório")
            
        # Lista para armazenar as grades ativas
        grades_ativas = []
        
        # Processar Grade 1
        if grade1_campos['ativar_var'].get():
            try:
                largura_horizontal = float(grade1_campos['largura_horizontal_entry'].get() or 0)
                sarr_esquerda = float(grade1_campos['sarr_esquerda_entry'].get() or 0)
                sarr_direita = float(grade1_campos['sarr_direita_entry'].get() or 0)
                sarr1_altura = float(grade1_campos['sarr1_altura_entry'].get() or 0)
                sarr2_altura = float(grade1_campos['sarr2_altura_entry'].get() or 0)
                sarr3_altura = float(grade1_campos['sarr3_altura_entry'].get() or 0)
                
                grades_ativas.append({
                    'largura': largura_horizontal,
                    'esquerda': sarr_esquerda,
                    'direita': sarr_direita,
                    'alturas': [sarr1_altura, sarr2_altura, sarr3_altura],
                    'esquerdo_central': grade1_campos['esquerdo_central_var'].get(),
                    'direito_central': grade1_campos['direito_central_var'].get(),
                    'distancias': [
                        float(grade1_campos['sarr1_distancia_entry'].get() or 0),
                        float(grade1_campos['sarr2_distancia_entry'].get() or 0),
                        float(grade1_campos['sarr3_distancia_entry'].get() or 0)
                    ]
                })
            except ValueError:
                print("Valores inválidos na Grade 1")
        
        # Processar Grade 2
        if grade2_campos['ativar_var'].get():
            try:
                largura_horizontal = float(grade2_campos['largura_horizontal_entry'].get() or 0)
                sarr_esquerda = float(grade2_campos['sarr_esquerda_entry'].get() or 0)
                sarr_direita = float(grade2_campos['sarr_direita_entry'].get() or 0)
                sarr1_altura = float(grade2_campos['sarr1_altura_entry'].get() or 0)
                sarr2_altura = float(grade2_campos['sarr2_altura_entry'].get() or 0)
                sarr3_altura = float(grade2_campos['sarr3_altura_entry'].get() or 0)
                
                grades_ativas.append({
                    'largura': largura_horizontal,
                    'esquerda': sarr_esquerda,
                    'direita': sarr_direita,
                    'alturas': [sarr1_altura, sarr2_altura, sarr3_altura],
                    'esquerdo_central': grade2_campos['esquerdo_central_var'].get(),
                    'direito_central': grade2_campos['direito_central_var'].get(),
                    'distancias': [
                        float(grade2_campos['sarr1_distancia_entry'].get() or 0),
                        float(grade2_campos['sarr2_distancia_entry'].get() or 0),
                        float(grade2_campos['sarr3_distancia_entry'].get() or 0)
                    ]
                })
            except ValueError:
                print("Valores inválidos na Grade 2")
        
        # Processar Grade 3
        if grade3_campos['ativar_var'].get():
            try:
                largura_horizontal = float(grade3_campos['largura_horizontal_entry'].get() or 0)
                sarr_esquerda = float(grade3_campos['sarr_esquerda_entry'].get() or 0)
                sarr_direita = float(grade3_campos['sarr_direita_entry'].get() or 0)
                sarr1_altura = float(grade3_campos['sarr1_altura_entry'].get() or 0)
                sarr2_altura = float(grade3_campos['sarr2_altura_entry'].get() or 0)
                sarr3_altura = float(grade3_campos['sarr3_altura_entry'].get() or 0)
                
                grades_ativas.append({
                    'largura': largura_horizontal,
                    'esquerda': sarr_esquerda,
                    'direita': sarr_direita,
                    'alturas': [sarr1_altura, sarr2_altura, sarr3_altura],
                    'esquerdo_central': grade3_campos['esquerdo_central_var'].get(),
                    'direito_central': grade3_campos['direito_central_var'].get(),
                    'distancias': [
                        float(grade3_campos['sarr1_distancia_entry'].get() or 0),
                        float(grade3_campos['sarr2_distancia_entry'].get() or 0),
                        float(grade3_campos['sarr3_distancia_entry'].get() or 0)
                    ]
                })
            except ValueError:
                print("Valores inválidos na Grade 3")
        
        if not grades_ativas:
            messagebox.showerror("Erro", "Nenhuma grade ativa para gerar o script")
            return
        
        # Gerar o script
        script = gerar_script_grade(pavimento, nome, grades_ativas)
            
        # Salvar o script no diretório do pavimento
        nome_arquivo = gerar_nome_arquivo(nome, pavimento)
        with open(nome_arquivo, 'w', encoding='utf-16') as f:
            f.write(script)
        
        messagebox.showinfo("Sucesso", f"Script gerado com sucesso em {nome_arquivo}")
        
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao gerar script: {str(e)}")
        print(f"Erro inesperado ao gerar script: {str(e)}")

def adicionar_cotas(script, x_inicial, y_inicial, largura_horizontal, sarr1_distancia, sarr2_distancia, sarr3_distancia):
    """Adiciona as cotas ao script do AutoCAD"""
    # Adicionar cotas
    script += f"""LAYER
S COTAS

;
"""
    # Cota da largura total
    script += f"""
_DIMLINEAR
{x_inicial},{y_inicial}
{x_inicial+largura_horizontal},{y_inicial}
{x_inicial+largura_horizontal/2},{y_inicial-40}
;
;
"""
    # Cotas dos sarrafos centrais apenas se tiverem distâncias válidas
    # NOTA: As distâncias já são cumulativas vindas do Excel
    if sarr1_distancia > 0:
        # Cota do sarrafo esquerdo até o primeiro sarrafo central
        script += f"""
_DIMLINEAR
{x_inicial},{y_inicial}
{x_inicial+sarr1_distancia},{y_inicial}
{x_inicial+(sarr1_distancia)/2},{y_inicial-20}
;
;
"""
        # Se for o último sarrafo central, cota até o sarrafo direito
        if sarr2_distancia == 0:
            script += f"""
_DIMLINEAR
{x_inicial+sarr1_distancia},{y_inicial}
{x_inicial+largura_horizontal},{y_inicial}
{x_inicial+(sarr1_distancia+largura_horizontal)/2},{y_inicial-20}
;
;
"""
        # Cota do primeiro sarrafo central até o segundo
        elif sarr2_distancia > 0:
            script += f"""
_DIMLINEAR
{x_inicial+sarr1_distancia},{y_inicial}
{x_inicial+sarr2_distancia},{y_inicial}
{x_inicial+(sarr1_distancia+sarr2_distancia)/2},{y_inicial-20}
;
;
"""
            # Se for o último sarrafo central, cota até o sarrafo direito
            if sarr3_distancia == 0:
                script += f"""
_DIMLINEAR
{x_inicial+sarr2_distancia},{y_inicial}
{x_inicial+largura_horizontal},{y_inicial}
{x_inicial+(sarr2_distancia+largura_horizontal)/2},{y_inicial-20}
;
;
"""
            # Cota do segundo sarrafo central até o terceiro
            elif sarr3_distancia > 0:
                script += f"""
_DIMLINEAR
{x_inicial+sarr2_distancia},{y_inicial}
{x_inicial+sarr3_distancia},{y_inicial}
{x_inicial+(sarr2_distancia+sarr3_distancia)/2},{y_inicial-20}
;
;
"""
                # Cota do terceiro sarrafo central até o sarrafo direito
                script += f"""
_DIMLINEAR
{x_inicial+sarr3_distancia},{y_inicial}
{x_inicial+largura_horizontal},{y_inicial}
{x_inicial+(sarr3_distancia+largura_horizontal)/2},{y_inicial-20}
;
;
"""
    return script

def gerar_comandos_retangulo(x1, y1, x2, y2, use_mline=False, is_horizontal=False):
    """
    Gera os comandos para desenhar um retângulo usando LINE ou MLINE
    
    Args:
        x1, y1: Coordenadas do ponto inferior esquerdo
        x2, y2: Coordenadas do ponto superior direito
        use_mline: Se True, usa MLINE; se False, usa LINE
        is_horizontal: Se True, é um retângulo horizontal (sarrafo horizontal)
    """
    if use_mline:
        if is_horizontal:  # Para retângulos horizontais
            # Identificar se é o retângulo base verificando se está no nível do solo (y1 == y_inicial)
            if y1 == config_manager.get_config("coordinates", "y_inicial"):
                mline_size = "2.2"  # Retângulo base
            else:
                mline_size = "10"   # Sarrafos horizontais normais
            
            return f""";
_MLINE
ST
TRAVA
S
{mline_size}
{x1},{y2}
{x2},{y2}

;
"""
        else:  # Para retângulos verticais
            # Verificar se é central ou lateral
            if abs(x2 - x1) == 3.5:  # Se for central
                mline_size = "7"
                # Mover 3.5cm para a esquerda
                x_pos = x2 - 3.5
                return f""";
_MLINE
ST
MEIOPONT
S
{mline_size}
{x_pos},{y1}
{x_pos},{y2}

;
"""
            else:  # Se for lateral
                mline_size = "7"
                # Mover 7cm para a esquerda
                x_pos = x2 - 7
                return f""";
_MLINE
ST
PONT1
S
{mline_size}
{x_pos},{y1}
{x_pos},{y2}

;
"""
    else:
        # Para LINE, precisamos desenhar as 4 linhas do retângulo
        return f"""_LINE
{x1},{y1}
{x2},{y1}

;
_LINE
{x2},{y1}
{x2},{y2}

;
_LINE
{x2},{y2}
{x1},{y2}

;
_LINE
{x1},{y2}
{x1},{y1}

;
"""

def gerar_script_automatico(dados_excel):
    """
    Gera o script automaticamente com base nos dados do Excel
    
    Args:
        dados_excel (dict): Dicionário contendo os dados do Excel com as seguintes chaves:
            - nome_arquivo: Nome do arquivo a ser gerado
            - pavimento: Pavimento onde a grade será inserida
            - x_inicial: Coordenada X inicial
            - y_inicial: Coordenada Y inicial
            - altura_base: Altura base da grade
            - grade1: Dicionário com dados da primeira grade
            - grade2: Dicionário com dados da segunda grade (opcional)
            - grade3: Dicionário com dados da terceira grade (opcional)
            - numero_lista: Número da lista (opcional)
            - distancias: Dicionário com as distâncias entre grades (opcional)
    """
    try:
        # Atualiza as configurações com os dados do Excel
        config_manager.set_config(dados_excel["x_inicial"], "coordinates", "x_inicial")
        config_manager.set_config(dados_excel["y_inicial"], "coordinates", "y_inicial")
        config_manager.set_config(dados_excel["altura_base"], "coordinates", "altura_base")
        
        # Configura as grades
        grades_ativas = []
        for i, grade_key in enumerate(["grade1", "grade2", "grade3"], 1):
            if grade_key in dados_excel and dados_excel[grade_key].get("ativar", False):
                grade_data = dados_excel[grade_key]
                grades_ativas.append({
                    'largura': grade_data['largura_horizontal'],
                    'esquerda': grade_data['sarr_esquerda'],
                    'direita': grade_data['sarr_direita'],
                    'alturas': [
                        grade_data['sarr1_altura'],
                        grade_data['sarr2_altura'],
                        grade_data['sarr3_altura']
                    ],
                    'esquerdo_central': False,
                    'direito_central': False,
                    'distancias': [
                        grade_data['sarr1_distancia'],
                        grade_data['sarr2_distancia'],
                        grade_data['sarr3_distancia']
                    ]
                })
        
        # Obter as distâncias entre grades
        distancias = dados_excel.get("distancias", {
            'distancia_grade1': 150,  # Valor padrão aumentado para 50cm
            'distancia_grade2': 150   # Valor padrão aumentado para 50cm
                })
        
        # Gera o nome do arquivo
        nome_arquivo = gerar_nome_arquivo(
            dados_excel["nome_arquivo"], 
            dados_excel["pavimento"],
            dados_excel.get("numero_lista")
        )
        
        # Gera o script
        script = gerar_script_grade(
            pavimento=dados_excel["pavimento"],
            nome=dados_excel["nome_arquivo"],
            grades_ativas=grades_ativas,
            distancias=distancias
        )
        
        return script
        
    except Exception as e:
        print(f"Erro ao gerar script automático: {e}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        return None

def gerar_script_simplificado(dados):
    """
    Gera o script automaticamente com base nos dados fornecidos
    
    Args:
        dados (dict): Dicionário contendo os dados com as seguintes chaves:
            - nome_arquivo: Nome do arquivo a ser gerado
            - pavimento: Pavimento onde a grade será inserida
            - x_inicial: Coordenada X inicial
            - y_inicial: Coordenada Y inicial
            - altura_base: Altura base da grade
            - grade1: Dicionário com dados da primeira grade
            - grade2: Dicionário com dados da segunda grade (opcional)
            - grade3: Dicionário com dados da terceira grade (opcional)
            - distancias: Dicionário com as distâncias entre grades (opcional)
    """
    # Atualiza as configurações com os dados
    config_manager.set_config(dados["x_inicial"], "coordinates", "x_inicial")
    config_manager.set_config(dados["y_inicial"], "coordinates", "y_inicial")
    config_manager.set_config(dados["altura_base"], "coordinates", "altura_base")
    
    # Lista para armazenar as grades ativas
    grades_ativas = []
    
    # Configura as grades
    for i, grade_key in enumerate(["grade1", "grade2", "grade3"], 1):
        if grade_key in dados:
            grade_data = dados[grade_key]
            config_manager.set_config(True, "grades", f"grade{i}", "ativar")
            
            # Criar dicionário com os dados da grade no formato esperado por gerar_script
            grade_dict = {
                'largura': grade_data.get('largura', 0),
                'esquerda': grade_data.get('altura_esquerda', 0),
                'direita': grade_data.get('altura_direita', 0),
                'alturas': [
                    grade_data.get('altura_sarrafo1', 0),
                    grade_data.get('altura_sarrafo2', 0),
                    grade_data.get('altura_sarrafo3', 0)
                ],
                'esquerdo_central': grade_data.get('esquerdo_central', False),
                'direito_central': grade_data.get('direito_central', False),
                'distancias': [
                    grade_data.get('distancia_sarrafo1', 0),
                    grade_data.get('distancia_sarrafo2', 0),
                    grade_data.get('distancia_sarrafo3', 0)
                ]
            }
            grades_ativas.append(grade_dict)
        else:
            config_manager.set_config(False, "grades", f"grade{i}", "ativar")
    
    # Obter as distâncias entre grades
    distancias = dados.get("distancias", {
        'distancia_grade1': 150,  # Valor padrão aumentado para 50cm
        'distancia_grade2': 150   # Valor padrão aumentado para 50cm
    })
    
    # Gera o nome do arquivo
    nome_arquivo = gerar_nome_arquivo(dados["nome_arquivo"], dados["pavimento"])
    
    # Gera o script passando os parâmetros corretos
    script = gerar_script_grade(
        pavimento=dados["pavimento"],
        nome=dados["nome_arquivo"],
        grades_ativas=grades_ativas,
        distancias=distancias
    )
    
    # Salva o script no arquivo com UTF-16 LE (com BOM) para compatibilidade com AutoCAD
    with open(nome_arquivo, 'wb') as f:
        # Adicionar BOM UTF-16 LE
        f.write(b'\xFF\xFE')
        # Converter conteúdo para UTF-16 LE
        f.write(script.encode('utf-16-le'))
    
    return nome_arquivo

def processar_colunas_excel(dados_excel, coluna_inicial='E'):
    """
    Processa múltiplas colunas do Excel e gera scripts separados para cada uma.
    
    Args:
        dados_excel (dict): Dicionário contendo os dados do Excel
        coluna_inicial (str): Coluna inicial para processar (padrão: 'E')
    """
    try:
        # Converter a letra da coluna para número
        coluna_num = ord(coluna_inicial.upper()) - ord('A')
        
        # Processar cada coluna
        for coluna in range(coluna_num, 26):  # 26 é o número de colunas no Excel (A-Z)
            letra_coluna = chr(coluna + ord('A'))
            
            # Criar uma cópia dos dados para esta coluna
            dados_coluna = dados_excel.copy()
            
            # Atualizar o nome do arquivo para incluir a coluna
            nome_original = dados_coluna.get("nome_arquivo", "")
            dados_coluna["nome_arquivo"] = f"{nome_original}_COL{letra_coluna}"
            
            # Gerar o script para esta coluna
            nome_arquivo = gerar_script_automatico(dados_coluna)
            
            if nome_arquivo:
                print(f"Script gerado com sucesso para a coluna {letra_coluna}: {nome_arquivo}")
            else:
                print(f"Erro ao gerar script para a coluna {letra_coluna}")
                
    except Exception as e:
        print(f"Erro ao processar colunas do Excel: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")

def calcular_posicoes_sarrafos(largura):
    """
    Calcula as posições dos sarrafos centrais baseado na largura da grade.
    Nova regra: tamanho da grade / 30.2 arredondado para baixo
    Exceção: grades acima de 120cm permitem até 4 sarrafos centrais
    
    Args:
        largura (float): Largura total da grade
        
    Returns:
        list: Lista com as posições dos sarrafos [pos1, pos2, pos3] ou [pos1, pos2, pos3, pos4]
    """
    try:
        largura = float(largura)
        
        # Calcular quantidade de sarrafos centrais: largura / 30.2 arredondado para baixo
        quantidade_sarrafos = math.floor(largura / 30.2)
        
        # Aplicar limite: 3 para grades <= 120, 4 para grades > 120
        if largura > 120:
            quantidade_sarrafos = min(4, quantidade_sarrafos)
        else:
            quantidade_sarrafos = min(3, quantidade_sarrafos)
        
        print(f"Grade de {largura}cm: {largura}/30.2 = {largura/30.2:.2f} -> {quantidade_sarrafos} sarrafos centrais")
        
        if quantidade_sarrafos <= 0:
            return [0, 0, 0, 0]  # Nenhum sarrafo central
            
        elif quantidade_sarrafos == 1:
            # 1 sarrafo central - posição central
            centro = largura / 2
            return [centro, 0, 0, 0]
            
        elif quantidade_sarrafos == 2:
            # 2 sarrafos centrais - dividir em 3 partes
            pos1 = largura / 3
            pos2 = 2 * largura / 3
            return [pos1, pos2, 0, 0]
            
        elif quantidade_sarrafos == 3:
            # 3 sarrafos centrais - usar 3 posições
            pos1 = largura / 4
            pos2 = largura / 2  # Central
            pos3 = 3 * largura / 4
            return [pos1, pos2, pos3, 0]
            
        else:  # quantidade_sarrafos == 4 (apenas para grades > 120)
            # 4 sarrafos centrais - dividir em 5 partes
            pos1 = largura / 5
            pos2 = 2 * largura / 5
            pos3 = 3 * largura / 5
            pos4 = 4 * largura / 5
            return [pos1, pos2, pos3, pos4]
            
    except (ValueError, TypeError):
        return [0, 0, 0, 0]

def calcular_quantidade_sarrafos_centrais(largura):
    """
    Calcula apenas a quantidade de sarrafos centrais baseada na largura da grade.
    Regra: tamanho da grade / 30.2 arredondado para baixo
    Exceção: grades acima de 120cm permitem até 4 sarrafos centrais
    
    Args:
        largura (float): Largura total da grade
        
    Returns:
        int: Quantidade de sarrafos centrais (0, 1, 2, 3 ou 4 se largura > 120)
    """
    try:
        largura = float(largura)
        quantidade = math.floor(largura / 30.2)
        # Exceção: grades acima de 120cm permitem até 4 sarrafos
        if largura > 120:
            return max(0, min(4, quantidade))  # Limitar entre 0 e 4 para grades > 120
        else:
            return max(0, min(3, quantidade))  # Limitar entre 0 e 3 para grades <= 120
    except (ValueError, TypeError):
        return 0

def criar_campos_grade(frame, grade_num):
    # Checkbox de ativação
    ativar_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(frame, text=f"Grade {grade_num}", variable=ativar_var).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=1)

    # Largura
    ttk.Label(frame, text="Largura:", width=8).grid(row=1, column=0, sticky=tk.W, pady=1)
    largura_horizontal_entry = ttk.Entry(frame, width=5)
    largura_horizontal_entry.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=1)

    # Cabeçalho para distância e altura
    ttk.Label(frame, text="Distância", font=('Arial', 8), width=6).grid(row=2, column=1, pady=1)
    ttk.Label(frame, text="Altura", font=('Arial', 8), width=6).grid(row=2, column=2, pady=1)

    # Sarrafo Esquerdo
    ttk.Label(frame, text="Esquerdo:", width=8).grid(row=3, column=0, sticky=tk.W, pady=1)
    sarr_esquerda_entry = ttk.Entry(frame, width=5)
    sarr_esquerda_entry.grid(row=3, column=2, sticky=(tk.W, tk.E), pady=1)
    esquerdo_central_var = tk.BooleanVar()
    ttk.Checkbutton(frame, text="Central", variable=esquerdo_central_var).grid(row=3, column=1, sticky=tk.W, pady=1)

# Sarrafo 1
    ttk.Label(frame, text="Sarrafo 1:", width=8).grid(row=4, column=0, sticky=tk.W, pady=1)
    sarr1_distancia_entry = ttk.Entry(frame, width=5)
    sarr1_distancia_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=1)
    sarr1_altura_entry = ttk.Entry(frame, width=5)
    sarr1_altura_entry.grid(row=4, column=2, sticky=(tk.W, tk.E), pady=1)

# Sarrafo 2
    ttk.Label(frame, text="Sarrafo 2:", width=8).grid(row=5, column=0, sticky=tk.W, pady=1)
    sarr2_distancia_entry = ttk.Entry(frame, width=5)
    sarr2_distancia_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=1)
    sarr2_altura_entry = ttk.Entry(frame, width=5)
    sarr2_altura_entry.grid(row=5, column=2, sticky=(tk.W, tk.E), pady=1)

# Sarrafo 3
    ttk.Label(frame, text="Sarrafo 3:", width=8).grid(row=6, column=0, sticky=tk.W, pady=1)
    sarr3_distancia_entry = ttk.Entry(frame, width=5)
    sarr3_distancia_entry.grid(row=6, column=1, sticky=(tk.W, tk.E), pady=1)
    sarr3_altura_entry = ttk.Entry(frame, width=5)
    sarr3_altura_entry.grid(row=6, column=2, sticky=(tk.W, tk.E), pady=1)

    # Sarrafo Direito
    ttk.Label(frame, text="Direito:", width=8).grid(row=7, column=0, sticky=tk.W, pady=1)
    sarr_direita_entry = ttk.Entry(frame, width=5)
    sarr_direita_entry.grid(row=7, column=2, sticky=(tk.W, tk.E), pady=1)
    direito_central_var = tk.BooleanVar()
    ttk.Checkbutton(frame, text="Central", variable=direito_central_var).grid(row=7, column=1, sticky=tk.W, pady=1)

    # Vincular o evento de alteração da largura ao cálculo automático dos sarrafos
    campos = {
        'ativar_var': ativar_var,
        'largura_horizontal_entry': largura_horizontal_entry,
        'sarr_esquerda_entry': sarr_esquerda_entry,
        'esquerdo_central_var': esquerdo_central_var,
        'sarr1_distancia_entry': sarr1_distancia_entry,
        'sarr1_altura_entry': sarr1_altura_entry,
        'sarr2_distancia_entry': sarr2_distancia_entry,
        'sarr2_altura_entry': sarr2_altura_entry,
        'sarr3_distancia_entry': sarr3_distancia_entry,
        'sarr3_altura_entry': sarr3_altura_entry,
        'sarr_direita_entry': sarr_direita_entry,
        'direito_central_var': direito_central_var
    }
    
    # Vincular eventos de atualização automática dos sarrafos
    def atualizar_campos_sarrafos(*args):
        atualizar_sarrafos_centrais(None, campos)
        atualizar_preview()

    # Vincular tanto ao KeyRelease quanto ao FocusOut
    largura_horizontal_entry.bind("<KeyRelease>", atualizar_campos_sarrafos)
    largura_horizontal_entry.bind("<FocusOut>", atualizar_campos_sarrafos)

    return campos

def atualizar_sarrafos_centrais(event, grade_campos):
    """Atualiza as posições dos sarrafos centrais quando a largura é alterada"""
    try:
        largura = float(grade_campos['largura_horizontal_entry'].get() or 0)
        if largura > 0:  # Só calcula se tiver uma largura válida
            posicoes = calcular_posicoes_sarrafos(largura)
            
            # Atualizar os campos de distância dos sarrafos
            for i, (entry, pos) in enumerate(zip(
                [grade_campos['sarr1_distancia_entry'],
                 grade_campos['sarr2_distancia_entry'],
                 grade_campos['sarr3_distancia_entry']], 
                posicoes)):
                entry.delete(0, tk.END)
                if pos > 0:
                    entry.insert(0, str(pos))
        else:
            # Limpar os campos se a largura não for válida
            for entry in [grade_campos['sarr1_distancia_entry'],
                         grade_campos['sarr2_distancia_entry'],
                         grade_campos['sarr3_distancia_entry']]:
                entry.delete(0, tk.END)

    except ValueError:
        # Limpar os campos se houver erro na conversão
        for entry in [grade_campos['sarr1_distancia_entry'],
                     grade_campos['sarr2_distancia_entry'],
                     grade_campos['sarr3_distancia_entry']]:
            entry.delete(0, tk.END)

if __name__ == "__main__":
    import sys
    if '--config' in sys.argv:
        root = tk.Tk()
        root.withdraw()  # Oculta a janela principal
        criar_janela_configuracoes()
        root.mainloop()
    else:
        # Criar janela principal
        root = tk.Tk()
        root.title("Gerador de Script AutoCAD")
        root.geometry("1200x800")  # Definir tamanho inicial da janela

        # Criar menu (modificado)
        menu_bar = tk.Menu(root)
        root.config(menu=menu_bar)

        # Menu Arquivo simplificado
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Arquivo", menu=file_menu)
        file_menu.add_command(label="Configurações", command=criar_janela_configuracoes)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=root.quit)

        # Criar frame para entrada de dados
        input_frame = ttk.Frame(root, padding="10")
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Criar frame para preview
        preview_frame = ttk.Frame(root, padding="10")
        preview_frame.grid(row=0, column=1, rowspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))

        # Criar área de preview
        fig, ax = plt.subplots(figsize=(8, 6))  # Aumentar o tamanho do canvas
        canvas = FigureCanvasTkAgg(fig, master=preview_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Configurar o redimensionamento da janela
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        # Criar campos de entrada
        ttk.Label(input_frame, text="Pavimento:", width=15).grid(row=0, column=0, sticky=tk.W, pady=5)
        pavimento_entry = ttk.Entry(input_frame, width=20)
        pavimento_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(input_frame, text="Nome do Arquivo:", width=15).grid(row=1, column=0, sticky=tk.W, pady=5)
        nome_entry = ttk.Entry(input_frame, width=20)
        nome_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)

        # Altura
        ttk.Label(input_frame, text="Altura:", width=15).grid(row=2, column=0, sticky=tk.W, pady=5)
        largura_base_vertical_entry = ttk.Entry(input_frame, width=20)
        largura_base_vertical_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        largura_base_vertical_entry.bind("<KeyRelease>", atualizar_retangulos_verticais)

        # Sarrafos Centrais
        ttk.Label(input_frame, text="Sarrafos Centrais:", width=15).grid(row=3, column=0, sticky=tk.W, pady=5)

        # Frame para os sarrafos centrais
        sarrafos_frame1 = ttk.LabelFrame(input_frame, text="Grade 1", padding="5")
        sarrafos_frame1.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=2)

        # Campo de distância entre grades
        distancia_frame1 = ttk.Frame(input_frame, padding="5")
        distancia_frame1.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2)
        ttk.Label(distancia_frame1, text="Distância:", width=8).grid(row=0, column=0, sticky=tk.W, pady=1)
        distancia_grade1_entry = ttk.Entry(distancia_frame1, width=5)
        distancia_grade1_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=1)

        # Grade 2
        sarrafos_frame2 = ttk.LabelFrame(input_frame, text="Grade 2", padding="5")
        sarrafos_frame2.grid(row=4, column=2, sticky=(tk.W, tk.E), pady=2)

        # Campo de distância entre grades
        distancia_frame2 = ttk.Frame(input_frame, padding="5")
        distancia_frame2.grid(row=4, column=3, sticky=(tk.W, tk.E), pady=2)
        ttk.Label(distancia_frame2, text="Distância:", width=8).grid(row=0, column=0, sticky=tk.W, pady=1)
        distancia_grade2_entry = ttk.Entry(distancia_frame2, width=5)
        distancia_grade2_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=1)

        # Grade 3
        sarrafos_frame3 = ttk.LabelFrame(input_frame, text="Grade 3", padding="5")
        sarrafos_frame3.grid(row=4, column=4, sticky=(tk.W, tk.E), pady=2)

        # Criar campos para cada grade
        grade1_campos = criar_campos_grade(sarrafos_frame1, 1)
        grade2_campos = criar_campos_grade(sarrafos_frame2, 2)
        grade3_campos = criar_campos_grade(sarrafos_frame3, 3)

        # Vincular a função de atualização aos campos de entrada
        for grade_campos in [grade1_campos, grade2_campos, grade3_campos]:
            grade_campos['largura_horizontal_entry'].bind("<KeyRelease>", atualizar_preview)
            grade_campos['sarr_esquerda_entry'].bind("<KeyRelease>", atualizar_preview)
            grade_campos['sarr_direita_entry'].bind("<KeyRelease>", atualizar_preview)
            grade_campos['sarr1_altura_entry'].bind("<KeyRelease>", atualizar_preview)
            grade_campos['sarr1_distancia_entry'].bind("<KeyRelease>", atualizar_preview)
            grade_campos['sarr2_altura_entry'].bind("<KeyRelease>", atualizar_preview)
            grade_campos['sarr2_distancia_entry'].bind("<KeyRelease>", atualizar_preview)
            grade_campos['sarr3_altura_entry'].bind("<KeyRelease>", atualizar_preview)
            grade_campos['sarr3_distancia_entry'].bind("<KeyRelease>", atualizar_preview)
            grade_campos['esquerdo_central_var'].trace_add("write", lambda *args: atualizar_preview())
            grade_campos['direito_central_var'].trace_add("write", lambda *args: atualizar_preview())

        # Vincular campos de distância
        distancia_grade1_entry.bind("<KeyRelease>", atualizar_preview)
        distancia_grade2_entry.bind("<KeyRelease>", atualizar_preview)

        # Botões
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        ttk.Button(button_frame, text="Atualizar Preview", command=atualizar_preview).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Gerar Script", command=gerar_script).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="Salvar Teste", command=salvar_script_teste).grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="Configurações", command=criar_janela_configuracoes).grid(row=0, column=3, padx=5)

        # Adicionar botão para processar múltiplas colunas
        def processar_multiplas_colunas():
            try:
                # Obter dados da interface
                dados_excel = {
                    "nome_arquivo": nome_entry.get(),
                    "pavimento": pavimento_entry.get(),
                    "x_inicial": config_manager.get_config("coordinates", "x_inicial"),
                    "y_inicial": config_manager.get_config("coordinates", "y_inicial"),
                    "altura_base": config_manager.get_config("coordinates", "altura_base"),
                    "distancias": {
                        "distancia_grade1": float(distancia_grade1_entry.get() or 0),
                        "distancia_grade2": float(distancia_grade2_entry.get() or 0)
                    },
                    "grade1": {
                        "ativar": grade1_campos['ativar_var'].get(),
                        "largura_horizontal": float(grade1_campos['largura_horizontal_entry'].get() or 0),
                        "sarr_esquerda": float(grade1_campos['sarr_esquerda_entry'].get() or 0),
                        "sarr_direita": float(grade1_campos['sarr_direita_entry'].get() or 0),
                        "sarr1_altura": float(grade1_campos['sarr1_altura_entry'].get() or 0),
                        "sarr2_altura": float(grade1_campos['sarr2_altura_entry'].get() or 0),
                        "sarr3_altura": float(grade1_campos['sarr3_altura_entry'].get() or 0),
                        "sarr1_distancia": float(grade1_campos['sarr1_distancia_entry'].get() or 0),
                        "sarr2_distancia": float(grade1_campos['sarr2_distancia_entry'].get() or 0),
                        "sarr3_distancia": float(grade1_campos['sarr3_distancia_entry'].get() or 0)
                    },
                    "grade2": {
                        "ativar": grade2_campos['ativar_var'].get(),
                        "largura_horizontal": float(grade2_campos['largura_horizontal_entry'].get() or 0),
                        "sarr_esquerda": float(grade2_campos['sarr_esquerda_entry'].get() or 0),
                        "sarr_direita": float(grade2_campos['sarr_direita_entry'].get() or 0),
                        "sarr1_altura": float(grade2_campos['sarr1_altura_entry'].get() or 0),
                        "sarr2_altura": float(grade2_campos['sarr2_altura_entry'].get() or 0),
                        "sarr3_altura": float(grade2_campos['sarr3_altura_entry'].get() or 0),
                        "sarr1_distancia": float(grade2_campos['sarr1_distancia_entry'].get() or 0),
                        "sarr2_distancia": float(grade2_campos['sarr2_distancia_entry'].get() or 0),
                        "sarr3_distancia": float(grade2_campos['sarr3_distancia_entry'].get() or 0)
                    },
                    "grade3": {
                        "ativar": grade3_campos['ativar_var'].get(),
                        "largura_horizontal": float(grade3_campos['largura_horizontal_entry'].get() or 0),
                        "sarr_esquerda": float(grade3_campos['sarr_esquerda_entry'].get() or 0),
                        "sarr_direita": float(grade3_campos['sarr_direita_entry'].get() or 0),
                        "sarr1_altura": float(grade3_campos['sarr1_altura_entry'].get() or 0),
                        "sarr2_altura": float(grade3_campos['sarr2_altura_entry'].get() or 0),
                        "sarr3_altura": float(grade3_campos['sarr3_altura_entry'].get() or 0),
                        "sarr1_distancia": float(grade3_campos['sarr1_distancia_entry'].get() or 0),
                        "sarr2_distancia": float(grade3_campos['sarr2_distancia_entry'].get() or 0),
                        "sarr3_distancia": float(grade3_campos['sarr3_distancia_entry'].get() or 0)
                    }
                }
                
                # Processar as colunas
                processar_colunas_excel(dados_excel)
                messagebox.showinfo("Sucesso", "Scripts gerados com sucesso para todas as colunas!")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao processar colunas: {str(e)}")

        ttk.Button(button_frame, text="Processar Colunas", command=processar_multiplas_colunas).grid(row=0, column=4, padx=5)

        # Label para mostrar o resultado
        resultado_label = ttk.Label(input_frame, text="")
        resultado_label.grid(row=10, column=0, columnspan=2, pady=5)

        # Inicializar preview
        atualizar_preview()

        # Adicionar bindings para atualizar preview quando as distâncias entre grades forem alteradas
        for i in range(1, 3):
            if i == 1:
                distancia_grade1_entry.bind('<KeyRelease>', lambda event: atualizar_preview())
            else:
                distancia_grade2_entry.bind('<KeyRelease>', lambda event: atualizar_preview())

        # Adicionar bindings para atualizar preview quando as grades forem ativadas/desativadas
        grade2_campos['ativar_var'].trace_add('write', lambda *args: atualizar_preview())
        grade3_campos['ativar_var'].trace_add('write', lambda *args: atualizar_preview())

        root.mainloop()