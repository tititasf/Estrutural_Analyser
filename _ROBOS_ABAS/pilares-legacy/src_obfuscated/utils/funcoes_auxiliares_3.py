
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
Módulo auxiliar 3 - Classes e funções utilitárias independentes
Modularização do funcoes_auxiliares_2.py para reduzir complexidade
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import win32com.client
import pythoncom
import time
import win32gui
import os
import re
import math

# Tenta importar pywinauto
try:
    from pywinauto import Application
except ImportError:
    Application = None

class AutoCADMessageBalloon:
    """Classe singleton para exibir mensagens balloon no AutoCAD"""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AutoCADMessageBalloon, cls).__new__(cls)
        return cls._instance

    def __init__(self, parent_tk_root=None):
        if not hasattr(self, '_initialized'):
            self._external_root = parent_tk_root
            self.root = None
            self.balcao = None
            self.after_id = None
            self.cancelado = False
            self._initialized = True

    def show(self, mensagem, tempo=None):
        self.cancelado = False
        if self.balcao and self.balcao.winfo_exists():
            self.balcao.destroy()
        if self.after_id:
            try:
                target_root = self._external_root if self._external_root and self._external_root.winfo_exists() else self.root
                if target_root and target_root.winfo_exists():
                    target_root.after_cancel(self.after_id)
            except: pass
            self.after_id = None

        parent_to_use = self._external_root
        if not parent_to_use or not parent_to_use.winfo_exists():
            if not self.root or not self.root.winfo_exists():
                self.root = tk.Tk()
                self.root.withdraw()
                self.root.overrideredirect(True)
            parent_to_use = self.root

        self.balcao = tk.Toplevel(parent_to_use)
        self.balcao.attributes('-topmost', True)
        self.balcao.configure(bg='#fff8b0')
        self.balcao.overrideredirect(True)

        largura, altura = 480, 120
        x = (self.balcao.winfo_screenwidth() - largura) // 2
        y = 40
        self.balcao.geometry(f"{largura}x{altura}+{x}+{y}")
        self.balcao.lift()
        self.balcao.focus_force()

        label = tk.Label(self.balcao, text=mensagem, font=("Arial", 16, "bold"), bg='#fff8b0', fg='#333', wraplength=460)
        label.pack(expand=True, fill=tk.BOTH, padx=10, pady=(10,0))
        self.balcao.bind('<Escape>', lambda e: self.hide())
        self.balcao.update_idletasks()
        self.balcao.update()

    def hide(self):
        self.cancelado = True
        if self.after_id:
            try:
                target_root = self._external_root if self._external_root and self._external_root.winfo_exists() else self.root
                if target_root and target_root.winfo_exists():
                    target_root.after_cancel(self.after_id)
            except: pass
            self.after_id = None
        if self.balcao and self.balcao.winfo_exists():
            try: self.balcao.destroy()
            except: pass
            self.balcao = None

        if self.root and self.root.winfo_exists() and not self._external_root:
            try:
                self.root.quit()
                self.root.destroy()
            except: pass
            self.root = None

def bring_window_to_front(hwnd):
    """Traz uma janela para frente usando pywinauto"""
    try:
        from pywinauto import Application
        if Application is None: return
        app = Application().connect(handle=hwnd)
        window = app.window(handle=hwnd)
        window.set_focus()
        window.restore()
        window.set_focus()
    except: pass

def formatar_valor_numerico(valor, casas_decimais=2, campo_nivel=False):
    """Formata um valor numérico com o número especificado de casas decimais"""
    if valor is None:
        return ""
    try:
        valor_float = float(str(valor).replace(',', '.'))
        if campo_nivel:
            casas_decimais = 2
        valor_arredondado = round(valor_float, casas_decimais)
        valor_formatado = f"{valor_arredondado:.{casas_decimais}f}"
        return valor_formatado
    except (ValueError, TypeError):
        return str(valor) if valor is not None else ""

def numero_para_coluna_excel(n):
    """Converte um número para letra de coluna do Excel (1->A, 2->B, etc.)"""
    result = ""
    while n > 0:
        n -= 1
        result = chr(65 + n % 26) + result
        n //= 26
    return result

def aplicar_regras_de_soma(aberturas):
    """Aplica regras específicas de soma para aberturas"""
    if not aberturas:
        return []
    
    # Se há apenas uma abertura, retorna como está
    if len(aberturas) == 1:
        return aberturas
    
    # Ordena as aberturas por posição
    aberturas_ordenadas = sorted(aberturas, key=lambda x: x[0])
    
    # Aplica regras de soma baseadas na proximidade
    resultado = []
    i = 0
    while i < len(aberturas_ordenadas):
        abertura_atual = aberturas_ordenadas[i]
        pos_atual, largura_atual, altura_atual = abertura_atual
        
        # Verifica se a próxima abertura está próxima o suficiente para somar
        if i + 1 < len(aberturas_ordenadas):
            proxima_abertura = aberturas_ordenadas[i + 1]
            pos_proxima, largura_proxima, altura_proxima = proxima_abertura
            
            # Se estão próximas (menos de 10cm de distância), soma
            if abs(pos_proxima - (pos_atual + largura_atual)) < 10:
                # Soma as larguras e mantém a maior altura
                nova_largura = largura_atual + largura_proxima + abs(pos_proxima - (pos_atual + largura_atual))
                nova_altura = max(altura_atual, altura_proxima)
                resultado.append((pos_atual, nova_largura, nova_altura))
                i += 2  # Pula as duas aberturas
            else:
                resultado.append(abertura_atual)
                i += 1
        else:
            resultado.append(abertura_atual)
            i += 1
    
    return resultado

def localizar_template():
    """Localiza o arquivo template Excel"""
    # Ordem de procura: mesmo diretório do script, depois diretório atual
    script_dir = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
    current_dir = os.getcwd()
    
    nomes_template = [os.path.join('templates', 'template_robo.xlsx'), os.path.join('templates', 'template_robo2.xlsx')]
    diretorios = [script_dir, current_dir]
    
    for diretorio in diretorios:
        for nome in nomes_template:
            caminho = os.path.join(diretorio, nome)
            if os.path.exists(caminho):
                return caminho
    
    # Se não encontrou, retorna None
    return None

def parse_valor_soma(valor_str):
    """
    Parseia uma string que pode conter soma de valores
    Ex: "12+8" retorna 20, "15" retorna 15
    """
    if not valor_str:
        return 0
    
    try:
        # Remove espaços
        valor_str = str(valor_str).strip()
        
        # Se contém '+', faz a soma
        if '+' in valor_str:
            partes = valor_str.split('+')
            total = 0
            for parte in partes:
                parte_limpa = parte.strip().replace(',', '.')
                if parte_limpa:
                    total += float(parte_limpa)
            return total
        else:
            # Valor simples
            return float(valor_str.replace(',', '.'))
    
    except (ValueError, TypeError):
        return 0

class AC_Module:
    """Módulo para interação com AutoCAD"""
    
    def __init__(self, parent_tk_root=None):
        self._parent_tk_root = parent_tk_root
        self.message_balloon = AutoCADMessageBalloon(parent_tk_root)
        self.acad = None
        self.doc = None

    def get_autocad_selection(self, prompt_message="Selecione os objetos e pressione Enter", tipo_selecao=None):
        """Obtém uma seleção do usuário no AutoCAD"""
        try:
            # Definir mensagem específica baseada no tipo de seleção
            mensagem = prompt_message
            if tipo_selecao == "retangulo":
                mensagem = "Selecione o retângulo principal do pilar e pressione Enter"
            elif tipo_selecao == "aberturas":
                mensagem = "Selecione as linhas das aberturas e pressione Enter"
            elif tipo_selecao == "textos":
                mensagem = "Selecione os textos das aberturas (formato N/N ou NxN) e pressione Enter"
            elif tipo_selecao == "laje":
                mensagem = "Selecione o texto da laje (formato n/n ou d=n) e pressione Enter"
            elif tipo_selecao == "nivel":
                mensagem = "Selecione o texto do nível (ex: 752,00) e pressione Enter"
            
            # Mostrar mensagem de instrução
            self.message_balloon.show(mensagem)
            
            # Inicializar COM
            pythoncom.CoInitialize()
            
            # Conectar ao AutoCAD
            app = win32com.client.Dispatch("AutoCAD.Application")
            doc = app.ActiveDocument
            app.Visible = True
            
            # Trazer janela do AutoCAD para frente
            try:
                acad_window = win32gui.FindWindow(None, app.Caption)
                if acad_window:
                    win32gui.SetForegroundWindow(acad_window)
                    win32gui.ShowWindow(acad_window, 5)
            except:
                pass
                
            # Configurar OSMODE para melhor seleção
            try:
                if hasattr(app, 'ActiveDocument') and hasattr(app.ActiveDocument, 'SetVariable'):
                    app.ActiveDocument.SetVariable("OSMODE", 35)
            except:
                pass
                
            # Criar conjunto de seleção com nome único
            sel_name = f"TempSel_{int(time.time())}"
            
            # Remover conjunto existente se houver
            try:
                for sel_set in doc.SelectionSets:
                    if sel_set.Name == sel_name:
                        sel_set.Delete()
                        break
            except:
                pass
                
            # Criar novo conjunto de seleção
            selection_set = doc.SelectionSets.Add(sel_name)
            
            # Realizar seleção do usuário
            selection_set.SelectOnScreen()
            
            # Verificar se algo foi selecionado
            if selection_set.Count == 0:
                self.message_balloon.hide()
                selection_set.Delete()
                return None
                
            # Converter para lista de objetos
            objects = []
            for i in range(selection_set.Count):
                objects.append(selection_set.Item(i))
                
            # Limpar conjunto de seleção
            selection_set.Delete()
            self.message_balloon.hide()
            
            return objects
            
        except Exception as e:
            self.message_balloon.hide()
            print(f"Erro na seleção do AutoCAD: {e}")
            return None
        finally:
            try:
                pythoncom.CoUninitialize()
            except:
                pass

    def get_rectangle_info(self, entity):
        """Extrai informações de um retângulo (polyline fechada)"""
        try:
            # Verificar se é uma polyline
            if hasattr(entity, 'ObjectName') and 'Polyline' in str(entity.ObjectName):
                coordinates = entity.Coordinates
                
                # Para polyline 2D, pega apenas coordenadas X e Y
                points = []
                for i in range(0, len(coordinates), 2):
                    if i + 1 < len(coordinates):
                        points.append((coordinates[i], coordinates[i + 1]))
                
                if len(points) >= 4:
                    # Calcular caixa delimitadora
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    
                    min_x, max_x = min(x_coords), max(x_coords)
                    min_y, max_y = min(y_coords), max(y_coords)
                    
                    largura = abs(max_x - min_x)
                    altura = abs(max_y - min_y)
                    
                    return {
                        'largura': largura,
                        'altura': altura,
                        'min_x': min_x,
                        'max_x': max_x,
                        'min_y': min_y,
                        'max_y': max_y,
                        'centro_x': (min_x + max_x) / 2,
                        'centro_y': (min_y + max_y) / 2
                    }
                    
        except Exception as e:
            print(f"Erro ao extrair informações do retângulo: {e}")
            
        return None

    def get_text_objects(self, selection):
        """Extrai objetos de texto da seleção"""
        text_objects = []
        
        if not selection:
            return text_objects
            
        for entity in selection:
            try:
                if hasattr(entity, 'ObjectName'):
                    obj_name = str(entity.ObjectName)
                    
                    # Verificar se é texto ou mtext
                    if 'Text' in obj_name:
                        text_content = ""
                        position = None
                        
                        if hasattr(entity, 'TextString'):
                            text_content = str(entity.TextString)
                        elif hasattr(entity, 'Text'):
                            text_content = str(entity.Text)
                            
                        # Obter posição
                        if hasattr(entity, 'InsertionPoint'):
                            pos = entity.InsertionPoint
                            position = (pos[0], pos[1])
                        elif hasattr(entity, 'TextAlignmentPoint'):
                            pos = entity.TextAlignmentPoint
                            position = (pos[0], pos[1])
                            
                        if text_content and position:
                            text_objects.append({
                                'text': text_content,
                                'position': position,
                                'entity': entity
                            })
                            
            except Exception as e:
                print(f"Erro ao processar entidade de texto: {e}")
                continue
                
        return text_objects

    def get_line_intersections(self, rectangle_entity, lines, doc):
        """Encontra interseções entre linhas e um retângulo"""
        try:
            rect_info = self.get_rectangle_info(rectangle_entity)
            if not rect_info:
                return []
                
            intersections = []
            
            # Definir as bordas do retângulo
            rect_lines = [
                # Borda inferior
                ((rect_info['min_x'], rect_info['min_y']), (rect_info['max_x'], rect_info['min_y'])),
                # Borda direita  
                ((rect_info['max_x'], rect_info['min_y']), (rect_info['max_x'], rect_info['max_y'])),
                # Borda superior
                ((rect_info['max_x'], rect_info['max_y']), (rect_info['min_x'], rect_info['max_y'])),
                # Borda esquerda
                ((rect_info['min_x'], rect_info['max_y']), (rect_info['min_x'], rect_info['min_y']))
            ]
            
            for line in lines:
                try:
                    if hasattr(line, 'StartPoint') and hasattr(line, 'EndPoint'):
                        line_start = (line.StartPoint[0], line.StartPoint[1])
                        line_end = (line.EndPoint[0], line.EndPoint[1])
                        
                        # Verificar intersecões com cada borda do retângulo
                        for i, rect_line in enumerate(rect_lines):
                            intersection = self._line_intersection(
                                line_start, line_end,
                                rect_line[0], rect_line[1]
                            )
                            
                            if intersection:
                                side_names = ['bottom', 'right', 'top', 'left']
                                intersections.append({
                                    'point': intersection,
                                    'side': side_names[i],
                                    'line_entity': line
                                })
                                
                except Exception as e:
                    print(f"Erro ao processar linha: {e}")
                    continue
                    
            return intersections
            
        except Exception as e:
            print(f"Erro ao calcular interseções: {e}")
            return []

    def _line_intersection(self, p1, p2, p3, p4):
        """Calcula a interseção entre duas linhas definidas por pontos"""
        try:
            x1, y1 = p1
            x2, y2 = p2
            x3, y3 = p3
            x4, y4 = p4
            
            denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            
            if abs(denom) < 1e-10:  # Linhas paralelas
                return None
                
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
            u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
            
            # Verificar se a interseção está dentro dos segmentos
            if 0 <= t <= 1 and 0 <= u <= 1:
                x = x1 + t * (x2 - x1)
                y = y1 + t * (y2 - y1)
                return (x, y)
                
            return None
            
        except Exception as e:
            print(f"Erro no cálculo de interseção: {e}")
            return None

    def rastrear_textos_proximidade_linhas(self, *args, **kwargs):
        """Método de compatibilidade - placeholder"""
        return []

    def extract_laje_value_from_text(self, text_content):
        """Extrai valor da laje de um texto"""
        try:
            text_content = str(text_content).strip()
            
            # Padrões para extrair valores de laje
            patterns = [
                r'd\s*=\s*(\d+(?:\.\d+)?)',  # d=15 ou d = 15
                r'(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)',  # 15/20
                r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)',  # 15x20
                r'(\d+(?:\.\d+)?)',  # apenas número
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 1:
                        return float(match.group(1))
                    elif len(match.groups()) == 2:
                        # Para formato x/y ou x*y, retorna o primeiro valor
                        return float(match.group(1))
                        
            return None
            
        except Exception as e:
            print(f"Erro ao extrair valor da laje: {e}")
            return None

# Cache global para o módulo AC
_ac_module_cache = None

def load_ac_functions(force_reload=False, parent_tk_root=None):
    """Carrega funções do AutoCAD com cache"""
    global _ac_module_cache
    
    if _ac_module_cache is None or force_reload:
        try:
            _ac_module_cache = AC_Module(parent_tk_root)
        except Exception as e:
            print(f"Erro ao carregar módulo AC: {e}")
            _ac_module_cache = None
            
    return _ac_module_cache

# Configuração do mapeamento Excel
EXCEL_MAPPING = None

def set_excel_mapping(mapping):
    """Define o mapeamento Excel global"""
    global EXCEL_MAPPING
    EXCEL_MAPPING = mapping

def get_excel_mapping():
    """Obtém o mapeamento Excel atual"""
    global EXCEL_MAPPING
    if EXCEL_MAPPING is not None:
        return EXCEL_MAPPING
    try:
        from excel_mapping import EXCEL_MAPPING
        return EXCEL_MAPPING
    except ImportError:
        return {}
