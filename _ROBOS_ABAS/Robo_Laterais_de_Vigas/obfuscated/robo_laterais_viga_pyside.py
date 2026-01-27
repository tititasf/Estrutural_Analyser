import sys
import os
import json
import json
import shutil
import re
import traceback
import uuid
import copy
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Literal
# Excel imports removed
# Excel imports removed

# Try to import PySide6
try:
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                   QHBoxLayout, QTabWidget, QLabel, QLineEdit, 
                                   QPushButton, QCheckBox, QRadioButton, QGroupBox,
                                   QScrollArea, QFrame, QSplitter, QComboBox,
                                   QMessageBox, QGraphicsView, QGraphicsScene,
                                   QGraphicsLineItem, QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QGraphicsItemGroup,
                                   QDialog, QGridLayout, QMenu, QTreeWidget, QTreeWidgetItem,
                                   QToolBar, QStyleFactory, QStackedWidget, QInputDialog,
                                   QToolButton, QStyle, QFormLayout, QDialogButtonBox, QFileDialog, 
                                   QListWidget, QTableWidget, QTableWidgetItem, QHeaderView)
    from PySide6.QtCore import Qt, Signal, QObject, QTimer, QRectF, QSize, QPoint
    from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainter, QAction, QIcon, QPalette, QCursor
except ImportError:
    print("PySide6 not found. Please install it with: pip install PySide6")
    sys.exit(1)

# Try to import AutoCAD integration libraries
try:
    import win32com.client
    import win32gui
    import pythoncom
    import pyautogui
except ImportError:
    pass

# --- Model / Logic Layer ---

@dataclass
class PanelData:
    width: float = 0.0
    height1: str = ""
    height2: str = ""
    type1: str = "Sarrafeado" # Sarrafeado or Grade
    type2: str = "Sarrafeado"
    grade_h1: float = 0.0
    grade_h2: float = 0.0
    slab_top: float = 0.0
    slab_bottom: float = 0.0
    slab_center: float = 0.0
    uid: str = ""
    uid_h2: str = ""
    reused_from: str = ""  # ID do painel do qual este painel foi extraído (H1)
    reused_in: str = ""    # ID do painel para o qual este painel foi enviado (H1)
    reused_from_h2: str = "" # ID origem H2
    reused_in_h2: str = ""   # ID destino H2
    link_saved: bool = False

@dataclass
class HoleData:
    dist: float = 0.0
    depth: float = 0.0
    width: float = 0.0
    force_h1: bool = False

@dataclass
class PillarDetail:
    dist: float = 0.0
    width: float = 0.0

@dataclass
class VigaState:
    # Metadata
    number: str = ""
    name: str = ""
    floor: str = "Térreo"
    obs: str = ""
    level_beam: str = ""
    level_opposite: str = ""
    level_ceiling: str = ""
    adjust: str = ""
    text_left: str = ""
    text_right: str = ""
    side: str = "A"
    continuation: str = "Proxima Parte"
    segment_class: str = "Lista Geral"
    
    # Combination
    combined_faces: List[Dict[str, str]] = field(default_factory=list) # [{'name': '...', 'id': '...'}, ...]
    unique_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    total_width: float = 0.0
    total_height: str = "0.0"
    bottom: str = ""   # Novo campo: Fundo da Viga
    height2_global: str = ""
    
    # Panels (Fixed 6 slots)
    panels: List[PanelData] = field(default_factory=lambda: [PanelData() for _ in range(6)])
    
    # Holes (4 slots: T/E, F/E, T/D, F/D)
    holes: List[HoleData] = field(default_factory=lambda: [HoleData() for _ in range(4)])
    
    # Options
    sarrafo_left: bool = True
    sarrafo_right: bool = True
    sarrafo_h2_left: bool = False
    sarrafo_h2_right: bool = False
    
    # Pillar Details
    pillar_left: PillarDetail = field(default_factory=PillarDetail)
    pillar_right: PillarDetail = field(default_factory=PillarDetail)

    # Production / Sequence Settings (Migrated from ProductionDialog)
    prod_holes: List[bool] = field(default_factory=lambda: [False, False, False, False])
    prod_force_h1: List[bool] = field(default_factory=lambda: [False, False, False, False])
    prod_pillar_l: bool = False
    prod_pillar_r: bool = False
    prod_viga_nivel: bool = False
    prod_p1_type: str = "Sarrafeado"
    prod_p2_type: str = "Sarrafeado"

    # Calculated
    area_util: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VigaState':
        # Basic deserialization aid
        state = cls()
        # Copy simple fields... in a real app use dacite or similar
        # For now, we trust the structure or just manually map criticals if needed
        # Implementation skipped for brevity, relies on pickle mostly
        return state

class AutoCADService(QObject):
    def __init__(self):
        super().__init__()
        self.ac = None
        self._seq_finalizada = False

    def connect_acad(self):
        """Conecta ao AutoCAD de forma estável, priorizando instância aberta."""
        try:
            pythoncom.CoInitialize()
            try:
                # Tenta pegar instância existente
                app = win32com.client.GetActiveObject("AutoCAD.Application")
            except:
                self.ac = None
                return False

            # Dispatch dinâmico uma única vez
            self.ac = win32com.client.dynamic.Dispatch(app)
            
            # Tenta tornar visível, mas ignora falha (AutoCAD pode estar ocupado)
            try:
                self.ac.Visible = True
            except: pass
            
            print("AutoCAD Conectado e Estabilizado.")
            return True
        except Exception as e:
            print(f"Connection Error: {e}")
            self.ac = None
            return False

    def _get_doc(self):
        try:
            # First check if we have a valid connection
            if self.ac:
                try:
                    # Test access to a property
                    _ = self.ac.Visible 
                    raw_doc = self.ac.ActiveDocument
                    return win32com.client.dynamic.Dispatch(raw_doc)
                except:
                    # Stale connection
                    self.ac = None
            
            # Reconnect
            try:
                self.ac = win32com.client.GetActiveObject("AutoCAD.Application")
            except:
                self.ac = win32com.client.Dispatch("AutoCAD.Application")
            
            if self.ac:
                self.ac.Visible = True
                try:
                    raw_doc = self.ac.ActiveDocument
                    return win32com.client.dynamic.Dispatch(raw_doc)
                except:
                    return None
            return None
        except:
            return None

    def _bring_acad_to_front(self):
        if not self.ac: return
        try:
            hwnd = win32gui.FindWindow(None, self.ac.Caption)
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)
                # win32gui.ShowWindow(hwnd, 5) 
                # try:
                #     pyautogui.press('f8') 
                # except: pass
        except: pass
        import time
        time.sleep(0.3) # Wait for focus to settle

    def _wait_for_cad_idle(self, doc, timeout=2.0):
        """Tenta verificar se o CAD está aceitando chamadas (idle) antes de prosseguir."""
        import time
        t0 = time.time()
        while (time.time() - t0) < timeout:
            try:
                # Tenta uma chamada leve (Read-Only)
                _ = doc.Name
                # Se não deu erro, pode estar OK.
                # Tenta ver variável de comando
                if doc.GetVariable("CMDNAMES") == "":
                    return True
                # Se tem comando rodando, não está idle, mas a chamada não falhou.
                # Retorna True para tentar interagir (ex: ESC) ou False?
                # A intenção é evitar 'Call Rejected'. Se ler CMDNAMES funcionou, não foi rejected.
                return True
            except:
                # Se deu erro (Rejected ou outro), espera um pouco
                time.sleep(0.25)
        return False

    def send_command(self, cmd: str):
        doc = self._get_doc()
        if doc:
            try: doc.SendCommand(cmd)
            except: pass

    def select_text_content(self) -> Optional[str]:
        # Legacy Wrapper
        return self.select_or_type_text("Selecione Texto")

    def _get_selection_set(self, doc, name="GratSelSet"):
        """Safely get or create a SelectionSet with retry for busy COM."""
        import time
        # Garante que o documento e a coleção de SelectionSets sejam dinâmicos
        try:
            doc = win32com.client.dynamic.Dispatch(doc)
            ss_coll = win32com.client.dynamic.Dispatch(doc.SelectionSets)
        except:
            return None

        for _ in range(3):
            try:
                # Use a completely unique name every time to avoid defects in Item/Delete
                unique_name = f"Sel_{uuid.uuid4().hex[:8]}"
                return ss_coll.Add(unique_name)
            except Exception as e:
                if "rejected" in str(e).lower() or "-2147418111" in str(e):
                    time.sleep(0.5)
                    continue
                # If Add failed, maybe try Item (unlikely with unique name) or just retry
                time.sleep(0.2)
                continue
        return None
        return None

    def select_or_type_text(self, prompt_msg: str) -> Optional[str]:
        """Versão ultra-robusta com 3 tentativas de recuperação total (2s + ESC + Reconnect)."""
        import time
        retries = 0
        max_retries = 3
        
        while retries < max_retries:
            try:
                # 0. Garantir Conexão e Documento
                doc = self._get_doc()
                if not doc:
                    print(f"CAD_DEBUG: [TENTATIVA {retries+1}] Sem documento. Aguardando 2s p/ reconectar...")
                    self.ac = None # Força reset
                    time.sleep(2)
                    retries += 1
                    continue

                self._bring_acad_to_front()
                
                # Probing preemptivo para evitar Call Rejected imediato
                self._wait_for_cad_idle(doc, timeout=1.5)

                # 1. Limpeza Crítica (ESC)
                try:
                    # Só envia ESC se houver comando ativo, evitando 'Invalid input'
                    if doc.GetVariable("CMDNAMES") != "":
                        doc.SendCommand(chr(27)*3) 
                        time.sleep(0.5)
                except Exception as e:
                    # Erro de 'Invalid input' no ESC geralmente significa que o CAD já está limpo
                    if "invalid input" in str(e).lower():
                        pass 
                    else:
                        print(f"CAD_DEBUG: [TENTATIVA {retries+1}] Alerta no ESC: {e}. Tentando seguir...")
                        # Não resetamos a conexão aqui por erro de input

                # 2. Tentar Seleção por Janela
                try:
                    print(f"CAD_DEBUG: [TENTATIVA {retries+1}] Aguardando sua seleção no CAD -> {prompt_msg}")
                    doc.Utility.Prompt(f"\n{prompt_msg} (Janela ou ENTER p/ digitar): ")
                    
                    ss = self._get_selection_set(doc, "RoboVigaSel")
                    if not ss: raise Exception("Falha no SelectionSet")
                    
                    # ss.Clear() # Not needed for new unique sets
                    ss.SelectOnScreen()
                    
                    if ss.Count > 0:
                        for i in range(ss.Count):
                            obj = ss.Item(i)
                            if obj.ObjectName in ["AcDbText", "AcDbMText", "AcDbAttributeDefinition"]:
                                val = obj.TextString
                                print(f"CAD_DEBUG: Sucesso! Encontrado: '{val}'")
                                ss.Clear()
                                return val
                            if obj.ObjectName == "AcDbBlockReference" and obj.HasAttributes:
                                for att in obj.GetAttributes():
                                    if att.TextString: 
                                        print(f"CAD_DEBUG: Sucesso! Atributo: '{att.TextString}'")
                                        ss.Clear()
                                        return att.TextString
                        ss.Clear()
                        print("CAD_DEBUG: Seleção feita, mas nenhum texto útil encontrado.")
                    else:
                        print("CAD_DEBUG: Seleção pulada no CAD (Usuário deu ENTER/ESC).")

                    # 3. Fallback: Digitação Manual (Só entra aqui se a seleção foi pulada sem erro de COM)
                    print(f"CAD_DEBUG: Iniciando Digitação Manual no CAD...")
                    val = doc.Utility.GetString(1, f"\n{prompt_msg} [Digite o valor e ENTER]: ")
                    if val:
                        print(f"CAD_DEBUG: Sucesso! Digitado: '{val}'")
                        return val
                    
                    # Se chegou aqui é porque o usuário deu ENTER vazio em tudo.
                    return None

                except Exception as e:
                    err_s = str(e).lower()
                    # DETECÇÃO AGRESSIVA DE FALHA DE COM
                    if any(x in err_s for x in ["rejected", "-2147418111", "unknown", "attributeerror", "server", "falha no selectionset", "rpc"]):
                        print(f"CAD_DEBUG: [TENTATIVA {retries+1}] Erro de Comunicação/Seleção: {e}. Aguardando 2s...")
                        self.ac = None # Force reconnect
                        time.sleep(2)
                        retries += 1
                        continue
                    else:
                        # Erro de cancelamento de usuário ou algo não crítico
                        print(f"CAD_DEBUG: Interação encerrada: {e}")
                        return None

            except Exception as e:
                print(f"CAD_DEBUG: Erro inesperado no loop (Tentativa {retries+1}): {e}")
                self.ac = None
                time.sleep(2)
                retries += 1
                
        print(f"CAD_DEBUG: Passo '{prompt_msg}' falhou após 3 tentativas de recuperação.")
        return None

    def select_line_length(self) -> float:
        doc = self._get_doc()
        if not doc: return 0.0

        self._bring_acad_to_front()
        try:
            doc.SendCommand("._LINE ")
            import time
            time.sleep(1.5) 
            
            last_ent = doc.ModelSpace.Item(doc.ModelSpace.Count - 1)
            if last_ent.ObjectName == "AcDbLine":
                p1 = last_ent.StartPoint
                p2 = last_ent.EndPoint
                length = ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5
                
                # Solicitar Ajuste (Soma ou Subtração)
                try:
                    prompt = f"\nComprimento medido: {length:.2f}\nDigite o AJUSTE (positivo p/ somar, negativo p/ subtrair, ou ENTER para 0): "
                    desc_str = doc.Utility.GetString(0, prompt) # 0 allows empty string (Enter)
                    if not desc_str: desc_str = "0"
                    
                    # Tenta converter virgula pra ponto
                    desc_val = float(desc_str.replace(',', '.'))
                except:
                    desc_val = 0.0
                
                # Soma o ajuste ao comprimento medido
                final_length = length + desc_val
                
                # Opcional: Remover a linha auxiliar criada? Normalmente sim para não sujar o desenho.
                try: last_ent.Delete()
                except: pass
                
                return round(final_length, 2)
            elif last_ent.ObjectName == "AcDbPolyline":
                # Handle 2 points polyline as generic distance
                # Simplified for now
                pass
                pass
        except Exception:
            traceback.print_exc()
            print("Line selection error (Stack Trace above).")
        return 0.0

    def select_levels(self) -> Dict[str, float]:
        """
        Selects two levels sequentially: Slab and Beam.
        Returns {'slab': float, 'beam': float, 'ceiling': float}
        """
        res = {'slab': 0.0, 'beam': 0.0, 'ceiling': 0.0}
        doc = self._get_doc()
        if not doc: return res
        self._bring_acad_to_front()
        
        # 1. Slab
        # We rely on interaction pausing. 
        # Since we can't easily print prompts to user inside here without UI ref,
        # we assume the user follows the external prompt "Selecione Nivel Laje e Nivel Viga".
        
        def get_level_val(prompt_idx):
            try:
                sel_name = f"TempSelLvl{prompt_idx}"
                # Legacy cleanup (optional safety)
                try: doc.SelectionSets.Item(sel_name).Delete()
                except: pass
                
                # Cria SelectionSet com nome único temporário para evitar colisão
                # Mas limpa se já existir
                try: 
                    doc.SelectionSets.Item(sel_name).Delete()
                    time.sleep(0.2)
                except: pass
                
                # Double check if deleted
                try:
                    doc.SelectionSets.Item(sel_name)
                    # If it still exists, use a different name
                    sel_name = f"SS_{int(time.time()*1000)}"
                except:
                    pass

                print(f"CAD_DEBUG: Criando SelectionSet '{sel_name}'...")
                selection = doc.SelectionSets.Add(sel_name)
                
                # Tenta focar no AutoCAD antes de pedir seleção
                try: doc.Activate() 
                except: pass
                
                selection.SelectOnScreen()
                
                val = 0.0
                if selection.Count > 0:
                     print(f"CAD_DEBUG: Objeto de nível selecionado.")
                     ent = selection.Item(0)
                     if ent.ObjectName in ["AcDbText", "AcDbMText"]:
                         import re
                         match = re.search(r"([0-9]+[\.,]?[0-9]*)", ent.TextString)
                         if match:
                             val = float(match.group(1).replace(",", "."))
                             print(f"CAD_DEBUG: Nível detectado: {val}")
                else:
                    print(f"CAD_DEBUG: Seleção de nível {prompt_idx} ignorada (ENTER/ESC).")
                
                selection.Clear()
                selection.Delete()
                return val
            except Exception as e: 
                print(f"CAD_DEBUG: Falha na seleção de nível: {e}")
                return 0.0

        # Attempt 1: Slab
        res['slab'] = get_level_val(1)
        
        # Attempt 2: Beam
        res['beam'] = get_level_val(2)
        
        # Ceiling? Usually calculated or selected 3rd?
        # Original logic implies just 2 or inferred.
        # Let's return what we have.
        
        return res

    def select_opening_dims(self) -> Dict[str, float]:
        # Select text like "20x60" or "20/60"
        txt = self.select_text_content()
        res = {'w': 0.0, 'd': 0.0}
        if txt:
            import re
            match = re.search(r"([0-9]+[\.,]?[0-9]*)\s*[x/]\s*([0-9]+[\.,]?[0-9]*)", txt)
            if match:
                res['w'] = float(match.group(1).replace(",", "."))
                res['d'] = float(match.group(2).replace(",", "."))
        return res

    def select_pillar_dims(self, prompt="") -> Dict[str, float]:
        """
        Captura dimensões de pilar usando o comando LINE do AutoCAD. 
        Reconhece 2 pontos (1 linha) ou 3 pontos (2 linhas).
        """
        doc = self._get_doc()
        res = {'dist': 0.0, 'width': 0.0}
        if not doc: return res

        self._bring_acad_to_front()
        import time, math
        
        # Limpa qualquer comando residual antes de começar
        try: doc.SendCommand("\x1b\x1b")
        except: pass
        time.sleep(0.2)
        
        if prompt:
            doc.Utility.Prompt(f"\n{prompt}\n")
        
        # Registra o estado inicial
        start_count = doc.ModelSpace.Count
        
        # DISPARA O COMANDO LINE
        doc.SendCommand("._LINE ")
        
        # Espera o usuário terminar o desenho
        doc.Utility.Prompt("\n>>> DESENHE O PILAR (2 ou 3 pontos) e finalize com ENTER no CAD <<<\n")
        
        try:
            time.sleep(1.0) # Tempo para o comando iniciar
            timeout = 120 # 2 minutos para desenhar
            slept = 0
            while slept < timeout:
                try:
                    # Se CMDNAMES estiver vazio, o comando LINE terminou
                    if doc.GetVariable("CMDNAMES") == "":
                        break
                except:
                    # Se der erro aqui, é porque o CAD está ocupado (processando cliques)
                    # Apenas ignoramos e continuamos esperando
                    pass
                time.sleep(0.5)
                slept += 0.5
        except:
            time.sleep(1.0)

        # Analisa o que foi desenhado
        try:
            new_count = doc.ModelSpace.Count
            new_ents = []
            # Pega as entidades criadas a partir do start_count
            for i in range(start_count, new_count):
                ent = doc.ModelSpace.Item(i)
                if ent.ObjectName == "AcDbLine":
                    new_ents.append(ent)
            
            if len(new_ents) == 1:
                # 1 Linha -> Largura
                e = new_ents[0]
                p1, p2 = e.StartPoint, e.EndPoint
                res['width'] = round(math.hypot(p1[0]-p2[0], p1[1]-p2[1]), 2)
            elif len(new_ents) >= 2:
                # 2 Linhas -> 1ª Distância, 2ª Largura
                e1, e2 = new_ents[0], new_ents[1]
                res['dist'] = round(math.hypot(e1.StartPoint[0]-e1.EndPoint[0], e1.StartPoint[1]-e1.EndPoint[1]), 2)
                res['width'] = round(math.hypot(e2.StartPoint[0]-e2.EndPoint[0], e2.StartPoint[1]-e2.EndPoint[1]), 2)
            
            # Limpa as linhas de apoio
            for ent in new_ents:
                try: ent.Delete()
                except: pass
                
        except Exception as e:
            print(f"DEBUG: Erro ao extrair medidas do pilar: {e}")

        return res

# --- UI Components ---

class ModernDarkPalette(QPalette):
    def __init__(self):
        super().__init__()
        self.setColor(QPalette.Window, QColor(53, 53, 53))
        self.setColor(QPalette.WindowText, Qt.white)
        self.setColor(QPalette.Base, QColor(25, 25, 25))
        self.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        self.setColor(QPalette.ToolTipBase, Qt.white)
        self.setColor(QPalette.ToolTipText, Qt.white)
        self.setColor(QPalette.Text, Qt.white)
        self.setColor(QPalette.Button, QColor(53, 53, 53))
        self.setColor(QPalette.ButtonText, Qt.white)
        self.setColor(QPalette.BrightText, Qt.red)
        self.setColor(QPalette.Link, QColor(42, 130, 218))
        self.setColor(QPalette.Highlight, QColor(42, 130, 218))
        self.setColor(QPalette.HighlightedText, Qt.black)

class TagLabel(QLabel):
    def __init__(self, text, color="#5C6BC0", parent=None):
        super().__init__(text, parent)
        self.set_text(text)
        self.setFixedWidth(80) # Fixed width for tags
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(18)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                border-radius: 4px;
                padding: 1px 4px;
                font-weight: bold;
                font-size: 10px;
            }}
        """)

    def set_text(self, text):
        self.setText(text.upper() if text else "-")

class FloatingLabel(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        layout = QVBoxLayout(self)
        self.label = QLabel(text)
        self.label.setStyleSheet("""
            background-color: #FFF9C4; border: 2px solid #FFC107; 
            border-radius: 5px; padding: 10px; color: #333; 
            font-weight: bold; font-size: 16px;
        """)
        layout.addWidget(self.label)
        self.adjustSize()
        
    def show_msg(self, text):
        self.label.setText(text)
        self.adjustSize()
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() // 4))
        self.show()

class PreviewWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#2b2b2b"))) # Dark bg for preview
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.zoom = 1.0

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0: self.scale(1.1, 1.1)
        else: self.scale(0.9, 0.9)

    def _safe_float(self, text):
        try: return float(str(text).replace(',', '.'))
        except: return 0.0

    def draw(self, state: VigaState):
        """Draws a single VigaState."""
        self.scene.clear()
        if not state: return
        
        root = self.scene.createItemGroup([])
        self._draw_viga_on_item(state, root)
        
        # Center view
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def draw_dual_view(self, model1: VigaState, model2: VigaState):
        """Draws two beams for comparison in Recycling Mode."""
        self.scene.clear()
        if not model1: return
        
        # 1. Main Beam
        root1 = self.scene.createItemGroup([])
        self._draw_viga_on_item(model1, root1)
        
        if not model2:
            self.scene.setSceneRect(self.scene.itemsBoundingRect())
            return
            
        # 2. Separator Label
        # Robust Offset Calculation
        # We need to find the Bottom-most point of Model 1 (Dimensions) 
        # and Top-most visual point of Model 2 (Structure extending up)
        
        # Calculate Model 1 Bottom
        m1_bottom = 500 # Default margin if empty
        if model1 and model1.panels:
            for p in model1.panels:
                # Dim line is at y=0 to y_bot_struct (positive)
                # Text is at y+150, y+350
                try: sb = float(str(p.slab_bottom).replace(',','.'))
                except: sb = 0.0
                curr_bot = max(sb * 15.0, 500) # Text is around 480
                if curr_bot > m1_bottom: m1_bottom = curr_bot
                
        # Calculate Model 2 Top (Height)
        m2_height = 500 
        if model2 and model2.panels:
            for p in model2.panels:
                 try: h1 = float(str(p.height1).replace(',','.'));
                 except: h1=0
                 try: h2 = float(str(p.height2).replace(',','.'));
                 except: h2=0
                 try: sc = float(str(p.slab_center).replace(',','.'));
                 except: sc=0
                 m2_height = max(m2_height, (h1+h2+sc) * 15.0)
                 
        # Additional buffer
        offset_y = m1_bottom + m2_height + 4000 
        
        # Draw separator line and text
        c_sep = QColor("#FFA726") # Orange
        sep_font = QFont("Segoe UI", 24, QFont.Bold)
        
        # Add "VIGA DE REAPROVEITAMENTO" label
        # Adjust Label Y position relative to offset_y (which is M2 Origin)
        # It must be ABOVE M2 structure
        label_y = offset_y - m2_height - 1500
        
        title_txt = f"Viga da lista de reaproveitamento - {model2.name if model2 else ''}"
        txt = QGraphicsTextItem(title_txt)
        txt.setFont(sep_font)
        txt.setDefaultTextColor(c_sep)
        txt.setScale(8.0)
        txt.setPos(0, label_y)
        self.scene.addItem(txt)
        
        line = QGraphicsLineItem(-1000, label_y + 800, max(model1.total_width, model2.total_width if model2 else 0) * 15.0 + 1000, label_y + 800)
        line.setPen(QPen(c_sep, 5, Qt.DashLine))
        self.scene.addItem(line)

        # 3. Recycled Beam
        root2 = self.scene.createItemGroup([])
        # Draw Viga 2 at Offset Y
        self._draw_viga_on_item(model2, root2, custom_title=None)
        root2.setPos(0, offset_y)
        
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def draw_multiple(self, states: List[VigaState]):
        """Draws multiple VigaStates stacked vertically."""
        self.scene.clear()
        if not states: return
        
        y_offset = 0.0
        
        for state in states:
            root = self.scene.createItemGroup([])
            self._draw_viga_on_item(state, root)
            root.setPos(0, y_offset)
            
            # Update bounds to calculate next offset correctly
            rect = root.childrenBoundingRect()
            height = rect.height()
            
            # Add spacing (reduced by half as requested)
            y_offset += height + 2500 
            
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def _draw_viga_on_item(self, state: VigaState, root_item, custom_title=None):
        """Internal method to draw viga content onto a specific QGraphicsItem parent."""
        try:
            base_scale = 15.0
            x = 0
            y = 0
            
            # Helpers to add items to root
            def add_line(x1, y1, x2, y2, pen):
                item = QGraphicsLineItem(x1, y1, x2, y2)
                item.setPen(pen)
                self.scene.addItem(item)
                item.setParentItem(root_item)
                return item
                
            def add_rect(x, y, w, h, pen, brush):
                 item = QGraphicsRectItem(x, y, w, h)
                 item.setPen(pen)
                 item.setBrush(brush)
                 self.scene.addItem(item)
                 item.setParentItem(root_item)
                 return item
                 
            def add_text(text, font, color, scale, pos_x, pos_y):
                item = QGraphicsTextItem(text)
                item.setFont(font)
                item.setDefaultTextColor(color)
                # Center-align multiline text internally
                option = item.document().defaultTextOption()
                option.setAlignment(Qt.AlignCenter)
                item.document().setDefaultTextOption(option)
                
                item.setScale(scale)
                item.setPos(pos_x, pos_y)
                self.scene.addItem(item)
                item.setParentItem(root_item)
                return item

            def add_hatch_rect(x, y, w, h, brush):
                item = QGraphicsRectItem(x, y, w, h)
                item.setPen(Qt.NoPen)
                item.setBrush(brush)
                item.setZValue(100)
                self.scene.addItem(item)
                item.setParentItem(root_item)
                return item

            # Colors (Dark Theme Adapted)
            c_line = QColor("#888888")
            c_dim = QColor("#64B5F6") # Light Blue
            c_panel_fill = QBrush(QColor("#37474F"))
            c_panel_stroke = QPen(c_line)
            c_sarrafo = QBrush(QColor("#FFB74D")) # Orange
            c_grade = QBrush(QColor("#81C784")) # Green
            c_slab = QBrush(QColor("#757575")) # Gray
            c_pillar = QBrush(QColor("#E91E63")) # Pink/Red for Pillars
            c_hole = QBrush(QColor("#00BCD4"), Qt.Dense4Pattern) # Cyan Hatched for Holes
            
            # Draw Main Dimension
            if state.total_width > 0:
                add_line(x, y, x + state.total_width * base_scale, y, QPen(c_dim, 2))
                add_text(f"LARGURA TOTAL: {state.total_width:.2f}", 
                         QFont("Segoe UI", 14, QFont.Bold), c_dim, 4.5, 
                         state.total_width * base_scale / 2 - 200, y + 350)
            
            # --- Draw Title (Beam Name) ---
            t_title = None
            display_name = custom_title if custom_title else f"VIGA: {state.name}"
            if state.name or custom_title:
                t_title = add_text(display_name, QFont("Segoe UI", 24, QFont.Bold), Qt.yellow, 6.0, 0, 0)
                t_title.setZValue(10)

            current_x = x
            
            # --- Draw Panels ---
            valid_indices = [i for i, p in enumerate(state.panels) if p.width > 0]
            first_idx = valid_indices[0] if valid_indices else -1
            last_idx = valid_indices[-1] if valid_indices else -1
            
            cumulative_w = 0.0
            
            for i, p in enumerate(state.panels):
                w = p.width * base_scale
                w_real = p.width
                if w <= 0: continue
                
                is_first = (i == first_idx)
                is_last = (i == last_idx)
                
                # --- Heights ---
                try: h1 = float(str(p.height1).replace(',', '.')) if p.height1 else 0.0
                except: h1 = 0.0
                try: h2 = float(str(p.height2).replace(',', '.')) if p.height2 else 0.0
                except: h2 = 0.0
                
                h1_px = h1 * base_scale
                h2_px = h2 * base_scale
                
                # --- Draw H1 ---
                if h1 > 0:
                    add_rect(current_x, -h1_px, w, h1_px, c_panel_stroke, c_panel_fill)
                    add_text(f"{h1:.2f} x {w_real:.2f}", QFont("Segoe UI", 12, QFont.Bold), Qt.white, 5.4,
                             current_x + w/2 - 150, -h1_px/2 - 50)

                if p.type1 == "Sarrafeado":
                    add_rect(current_x, -h1_px, w, 7*base_scale, QPen(Qt.NoPen), c_sarrafo)
                elif p.type1 == "Grade":
                     grade_h = 2.2 * base_scale
                     off_start = 15 * base_scale if is_first else 0
                     off_end = 15 * base_scale if is_last else 0
                     gx = current_x + off_start; gw = w - off_start - off_end; gy = -h1_px
                     add_rect(gx, gy, gw, grade_h, QPen(Qt.NoPen), c_grade)
                     v_w = 3.5 * base_scale
                     v_h = (p.grade_h1 if p.grade_h1 > 0 else 0) * base_scale
                     if v_h > 0:
                         vy = gy + grade_h 
                         add_rect(current_x + (15 * base_scale if is_first else 0), vy, v_w, v_h, QPen(Qt.NoPen), c_grade)
                         add_rect(current_x + w - v_w - (15 * base_scale if is_last else 0), vy, v_w, v_h, QPen(Qt.NoPen), c_grade)
            
                # --- Draw Slab Center ---
                s_c = p.slab_center * base_scale
                top_y = -h1_px
                if s_c > 0:
                    add_rect(current_x, top_y - s_c, w, s_c, QPen(Qt.NoPen), c_slab)
                    top_y -= s_c
                
                # --- Draw H2 ---
                if h2 > 0:
                    add_rect(current_x, top_y - h2_px, w, h2_px, c_panel_stroke, c_panel_fill)
                    add_text(f"{h2:.2f} x {w_real:.2f}", QFont("Segoe UI", 12, QFont.Bold), Qt.white, 5.4,
                             current_x + w/2 - 150, top_y - h2_px/2 - 50)
                    if p.type2 == "Sarrafeado":
                         add_rect(current_x, top_y - h2_px, w, 7*base_scale, QPen(Qt.NoPen), c_sarrafo)
                    elif p.type2 == "Grade":
                         grade_h = 2.2 * base_scale
                         off_start = 15 * base_scale if is_first else 0
                         off_end = 15 * base_scale if is_last else 0
                         gx = current_x + off_start; gw = w - off_start - off_end; gy = top_y - h2_px
                         add_rect(gx, gy, gw, grade_h, QPen(Qt.NoPen), c_grade)
                         v_w = 3.5 * base_scale
                         v_h = (p.grade_h2 if p.grade_h2 > 0 else 0) * base_scale
                         if v_h > 0:
                             vy = gy + grade_h
                             add_rect(current_x + (15 * base_scale if is_first else 0), vy, v_w, v_h, QPen(Qt.NoPen), c_grade)
                             add_rect(current_x + w - v_w - (15 * base_scale if is_last else 0), vy, v_w, v_h, QPen(Qt.NoPen), c_grade)
                    top_y -= h2_px
                    
                # --- Draw Slab Top ---
                s_t = p.slab_top * base_scale
                if s_t > 0:
                    add_rect(current_x, top_y - s_t, w, s_t, QPen(Qt.NoPen), c_slab)
                    
                # --- Draw Slab Bottom ---
                s_b = p.slab_bottom * base_scale
                if s_b > 0:
                    add_rect(current_x, 0, w, s_b, QPen(Qt.NoPen), c_slab)
                    
                # Panel Width Dimension
                add_text(f"P{i+1}: {w_real:.2f}", QFont("Segoe UI", 11, QFont.Bold), c_dim, 4.8, 
                         current_x + w/2 - 120, 150)

                # --- Draw Reuse (Reap) Visuals ---
                hatch_type = getattr(p, '_preview_hatch_type', None)
                if hatch_type:
                    # Calculate total height for the hatch overlay
                    val_sc = p.slab_center if p.slab_center else 0.0
                    val_st = p.slab_top if p.slab_top else 0.0
                    val_sb = p.slab_bottom if p.slab_bottom else 0.0
                    
                    y_top_px = -(h1 + val_sc + h2 + val_st) * base_scale
                    y_bot_px = val_sb * base_scale
                    panel_h = abs(y_top_px) + y_bot_px
                    
                    # Determine Color/Pattern
                    # Green = Exact matching, Yellow = Cut required
                    hatch_color = QColor("#4CAF50") if hatch_type == 'green' else QColor("#FFEB3B")
                    hatch_color.setAlpha(120) 
                    pattern = Qt.FDiagPattern if hatch_type == 'green' else Qt.DiagCrossPattern
                    brush_hatch = QBrush(hatch_color, pattern)
                    
                    add_hatch_rect(current_x, y_top_px, w, panel_h, brush_hatch)

                tag_text = getattr(p, '_preview_tag_text', None)
                if tag_text:
                    scale_val = 8.0
                    t_item = add_text(tag_text, QFont("Segoe UI", 12, QFont.Bold), QColor("#FFD54F"), scale_val, 0, 0)
                    t_item.setZValue(200)
                    
                    br = t_item.boundingRect()
                    t_item.setTextWidth(br.width())
                    txt_w = br.width() * scale_val
                    
                    panel_center_x = current_x + (w / 2)
                    final_x = panel_center_x - (txt_w / 2)
                    
                    # Position tags below the panel structure
                    val_sb = p.slab_bottom if p.slab_bottom else 0.0
                    y_base_px = max(val_sb * base_scale, 200)
                    t_item.setPos(final_x, y_base_px + 250)

                current_x += w
                cumulative_w += w_real

            # --- Obstacle Visual ---
            if state.continuation == "Obstaculo" and last_idx != -1:
                obs_w = 30 * base_scale
                # Calculate Y based on last panel
                last_p = state.panels[last_idx]
                h1_last = self._safe_float(last_p.height1)
                h2_last = self._safe_float(last_p.height2)
                sc_last = last_p.slab_center
                st_last = last_p.slab_top
                si_last = last_p.slab_bottom
                
                total_h_px = (h1_last + h2_last + sc_last + st_last + si_last) * base_scale
                y_top_obs = - (h1_last + sc_last + h2_last + st_last) * base_scale
                y_base_obs = si_last * base_scale
                
                item_obs = QGraphicsRectItem(current_x, y_top_obs, obs_w, total_h_px)
                item_obs.setPen(QPen(QColor("#888888")))
                item_obs.setBrush(QBrush(QColor("#888888")))
                self.scene.addItem(item_obs)
                item_obs.setParentItem(root_item)
                

                    
            # --- Draw Vertical Dimensions ---
            first_panel_idx = -1
            valid_indices = [i for i, p in enumerate(state.panels) if p.width > 0]
            if valid_indices: first_panel_idx = valid_indices[0]
            
            p0 = state.panels[0] if valid_indices else None
            y_sc_top = 0 
            y_top_struct = -140 * base_scale
            y_bot_struct = 0
            
            if p0:
                try: h1_v = float(str(p0.height1).replace(',', '.') or 0)
                except: h1_v = 0
                try: h2_v = float(str(p0.height2).replace(',', '.') or 0)
                except: h2_v = 0
                try: sc_v = float(str(p0.slab_center).replace(',', '.') or 0)
                except: sc_v = 0
                try: st_v = float(str(p0.slab_top).replace(',', '.') or 0)
                except: st_v = 0
                try: sb_v = float(str(p0.slab_bottom).replace(',', '.') or 0)
                except: sb_v = 0
                y_top_struct = -(h1_v + h2_v + sc_v + st_v) * base_scale
                y_bot_struct = sb_v * base_scale
                y_sc_top = -(h1_v + sc_v) * base_scale
            
            if first_panel_idx != -1:
                p = state.panels[first_panel_idx]
                try: h1 = float(str(p.height1).replace(',', '.') or 0); 
                except: h1 = 0.0
                try: h2 = float(str(p.height2).replace(',', '.') or 0); 
                except: h2 = 0.0
                try: s_c = float(str(p.slab_center).replace(',', '.') or 0); 
                except: s_c = 0.0
                try: s_t = float(str(p.slab_top).replace(',', '.') or 0); 
                except: s_t = 0.0
                try: s_b = float(str(p.slab_bottom).replace(',', '.') or 0); 
                except: s_b = 0.0

                h1_px = h1 * base_scale; h2_px = h2 * base_scale
                sc_px = s_c * base_scale; st_px = s_t * base_scale; sb_px = s_b * base_scale
                dim_x = x - 150
                
                if s_b > 0:
                    add_line(dim_x, 0, dim_x, sb_px, QPen(c_dim, 2))
                    add_text(f"Li:{s_b:.1f}", QFont("Arial"), c_dim, 4.5, dim_x-250, sb_px/2-40)

                curr_y = 0
                if h1 > 0:
                    add_line(dim_x, curr_y, dim_x, curr_y - h1_px, QPen(c_dim, 2))
                    add_text(f"H1:{h1:.1f}", QFont("Arial"), c_dim, 4.5, dim_x-250, curr_y - h1_px/2 - 40)
                    curr_y -= h1_px
                if s_c > 0:
                    add_line(dim_x, curr_y, dim_x, curr_y - sc_px, QPen(c_dim, 2))
                    add_text(f"Lc:{s_c:.1f}", QFont("Arial"), c_dim, 4.5, dim_x-250, curr_y - sc_px/2 - 40)
                    curr_y -= sc_px
                if h2 > 0:
                    add_line(dim_x, curr_y, dim_x, curr_y - h2_px, QPen(c_dim, 2))
                    add_text(f"H2:{h2:.1f}", QFont("Arial"), c_dim, 4.5, dim_x-250, curr_y - h2_px/2 - 40)
                    curr_y -= h2_px
                if s_t > 0:
                    add_line(dim_x, curr_y, dim_x, curr_y - st_px, QPen(c_dim, 2))
                    add_text(f"Ls:{s_t:.1f}", QFont("Arial"), c_dim, 4.5, dim_x-250, curr_y - st_px/2 - 40)
                    curr_y -= st_px

                total_h_val = float(h1 + h2 + s_c + s_t + s_b)
                if total_h_val > 0:
                    dim_x_total = x - 500
                    y_bottom = sb_px; y_top = curr_y
                    add_line(dim_x_total, y_bottom, dim_x_total, y_top, QPen(Qt.yellow, 3))
                    add_line(dim_x_total-20, y_bottom, dim_x_total+20, y_bottom, QPen(Qt.yellow, 2))
                    add_line(dim_x_total-20, y_top, dim_x_total+20, y_top, QPen(Qt.yellow, 2))
                    mid_y = (y_bottom + y_top) / 2
                    add_text(f"TOTAL: {total_h_val:.2f}", QFont("Segoe UI", 16, QFont.Bold), Qt.yellow, 5.0, dim_x_total - 450, mid_y - 50)

            # --- Draw Pillars ---
            p_height_px = y_bot_struct - y_top_struct
            p_y_start = y_top_struct 
            
            if state.pillar_left.dist > 0 or state.pillar_left.width > 0:
                pd = state.pillar_left.dist * base_scale; pw = state.pillar_left.width * base_scale
                item = QGraphicsRectItem(pd, p_y_start, pw, p_height_px)
                item.setPen(QPen(Qt.black)); item.setBrush(c_pillar)
                self.scene.addItem(item); item.setParentItem(root_item)

            if state.pillar_right.dist > 0 or state.pillar_right.width > 0:
                pd = state.pillar_right.dist * base_scale; pw = state.pillar_right.width * base_scale
                start_x = (state.total_width * base_scale) - pd - pw
                item = QGraphicsRectItem(start_x, p_y_start, pw, p_height_px)
                item.setPen(QPen(Qt.black)); item.setBrush(c_pillar)
                self.scene.addItem(item); item.setParentItem(root_item)

            # --- Draw Openings (Holes) ---
            c_hole_pen = QPen(QColor("#81C784"), 3)
            
            def draw_hole(h, side: Literal['L', 'R'], pos: Literal['T', 'F']):
                if h.width <= 0: return
                w_px = h.width * base_scale; h_px = h.depth * base_scale
                if side == 'L': start_x = h.dist * base_scale
                else: start_x = (state.total_width * base_scale) - (h.dist * base_scale) - w_px
                
                if pos == 'T': sy = y_sc_top if h.force_h1 else y_top_struct
                else: sy = (0 - h_px) if h.force_h1 else (y_bot_struct - h_px)
                
                add_rect(start_x, sy, w_px, h_px, c_hole_pen, c_hole)
                add_text(f"{h.depth:.2f} x {h.width:.2f}", QFont("Segoe UI", 10, QFont.Bold), Qt.white, 4.5, start_x + w_px/2 - 120, sy + h_px/2 - 60)

            draw_hole(state.holes[0], 'L', 'T')
            draw_hole(state.holes[1], 'L', 'F')
            draw_hole(state.holes[2], 'R', 'T')
            draw_hole(state.holes[3], 'R', 'F')
            
            # Reposition Title
            if t_title:
                rect_b = root_item.childrenBoundingRect()
                t_title.setPos(0, rect_b.top() - 300)

        except Exception as e:
            print(f"CRITICAL ERROR in PreviewWidget.draw: {e}")
            import traceback
            traceback.print_exc()


from PySide6.QtWidgets import QButtonGroup
        
from PySide6.QtWidgets import QButtonGroup # Add import if missing

class VigaMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robô das Laterais de Viga - PySide6 Ultimate")
        self.resize(1400, 900)
        
        # Apply Dark Theme
        app = QApplication.instance()
        app.setStyle(QStyleFactory.create("Fusion"))
        app.setPalette(ModernDarkPalette())
        
        self.model = VigaState()
        self.recycle_model = None # For comparison in Recycling Mode
        self.acad_service = AutoCADService()
        
        # Data Management
        self.project_data = {} # Dict[Obra, Dict[Pav, Dict[VigaName, VigaState]]]
        self.current_obra = ""
        self.current_pavimento = ""
        # Definir caminho absoluto adaptável para Dev ou EXE
        if getattr(sys, 'frozen', False):
            self.app_root = os.path.dirname(sys.executable)
            # No EXE, salvamos os dados e config na mesma pasta do executável
            self.persistence_file = os.path.join(self.app_root, "dados_vigas_ultima_sessao.json")
            self.config_file = os.path.join(self.app_root, "config.json")
        else:
            self.app_root = os.path.dirname(os.path.abspath(__file__))
            # Em Dev, dados ficam em A_B e config na raiz do projeto (pai de A_B)
            self.persistence_file = os.path.join(self.app_root, "dados_vigas_ultima_sessao.json")
            self.config_file = os.path.join(os.path.dirname(self.app_root), "config.json")
            
        self.config = self._carregar_config()
        
        self._updating = False
        
        # Licensing Service (Injected by entry point)
        self.licensing_service = None
        self.init_ui()
        self.create_actions()
        
        # State trackers
        self.current_class_view = None
        self.last_loaded_key = None
        
        # Load saved session
        self.load_session_data()
        self.update_obra_combo()
        
        # Initial license display (will show Connected if service injected later)
        self.update_license_display()

    def _carregar_config(self):
        """Carrega as configurações do arquivo config.json."""
        try:
            defaults = self._obter_config_padrao()
            loaded_config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
            
            # Mesclar loaded_config sobre defaults para preservar configs do usuário mas garantir chaves novas
            return self._merge_dicts(defaults, loaded_config)
        except Exception as e:
            print(f"Erro ao carregar configurações: {str(e)}")
            return self._obter_config_padrao()

    def _merge_dicts(self, default, user):
        """Deep merge dictionaries."""
        for k, v in default.items():
            if k not in user:
                user[k] = v
            else:
                if isinstance(v, dict) and isinstance(user[k], dict):
                    self._merge_dicts(v, user[k])
        return user

    def _obter_config_padrao(self):
        """Retorna configurações padrão para o gerador de scripts (Legacy)."""
        return {
            "layers": {
                "paineis": "Painéis",
                "sarrafos_verticais": "SARR_2.2x7",
                "sarrafos_horizontais": "SARR_2.2x7",
                "sarrafos_horizontais_pequenos": "SARR_2.2x5",
                "nome_observacoes": "NOMENCLATURA",
                "textos_laterais": "5",
                "cotas": "COTA",
                "laje": "COTA",
                "sarrafos_verticais_extremidades": "SARR_2.2x7",
                "sarrafos_verticais_grades": "SARR_2.2x3.5",
                "obstaculo": "COTAS",
                "texto_pontaletes": "ESTRUTURACAO"
            },
            "comandos": {
                "extensor1": "ex2",
                "extensor2": "Bextend",
                "app": "APP",
                "appdel": "appdel",
                "ABVET": "ABVET",
                "ABVEF": "ABVEF",
                "ABFDT": "ABFDT",
                "ABVDT": "ABVDT",
                "ABVDTV": "ABVDTV",
                "ABVDF": "ABVDF",
                "ABFDF": "ABFDF",
                "apv2e": "apv2e",
                "apv2": "apv2",
                "apv2D": "apv2D",
                "HHHH": "HHHH",
                "HH": "HH",
                "HHHH": "HHHH",
                "HH": "HH",
                "HHH": "HHH",
                "hatch_amarelo_reap": "HHH"
            },
            "opcoes": {
                "tipo_linha": "PLINE"
            },
            "numeracao_blocos": {
                "ativo": False,
                "comandos": {str(i): f"N{i}" for i in range(1, 21)}
            }
        }

    def _salvar_config(self):
        """Salva as configurações no arquivo config.json."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar configurações: {e}")

    def create_actions(self):
        # Toolbar for File Operations
        tb = QToolBar("Arquivo")
        self.addToolBar(tb)
        
        act_new = tb.addAction("Novo", self.reset_fundo)
        act_new.setToolTip("Inicia uma nova viga do zero (limpa os campos).")
        
        act_save = tb.addAction("Salvar", self.save_current_fundo)
        act_save.setToolTip("Salva a viga atual no banco de dados do pavimento selecionado.")
        
        act_gen = tb.addAction("Gerar Script Atual", self.generate_script_current)
        act_gen.setToolTip("Cria o arquivo .SCR para processar esta viga no AutoCAD.")
        
        act_gen_all = tb.addAction("Gerar Pavimento", self.generate_pavimento_scripts)
        act_gen_all.setToolTip("Gera scripts .SCR para TODAS as vigas listadas neste pavimento.")

        act_gen_conj = tb.addAction("Gerar Conjunto", self.generate_conjunto_scripts)
        act_gen_conj.setToolTip("Gera scripts .SCR apenas para o conjunto (segmentos) da viga atual.")
        
        act_lisp = tb.addAction("Criar LISP", self.action_create_lisp)
        act_lisp.setToolTip("Gera um arquivo de rotina LISP para automação avançada no AutoCAD.")
        
        tb.addSeparator()
        
        act_config = tb.addAction("Configurações", self.show_settings)
        act_config.setToolTip("Abre a janela de configurações do sistema.")
        
        # Modes
        tb.addSeparator()
        self.chk_recycling = QCheckBox("Modo Reaproveitamento")
        self.chk_recycling.setToolTip("Ativado: tenta reaproveitar fôrmas existentes no estoque.")
        self.chk_recycling.stateChanged.connect(self.toggle_recycling)
        
        # Add Widgets to Toolbar is tricky, better use a layout or QAction with widgets
        # For simplicity, we keep them in UI or add to toolbar via widget
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0,0,0,0)
        l.addWidget(self.chk_recycling)
        tb.addWidget(w)

    def show_settings(self):
        """Abre uma janela de diálogo para configurações gerais e de layers (Legacy)."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Configurações do Robô")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        layout = QVBoxLayout(dialog)
        
        tabs = QTabWidget()
        
        # --- Tab 1: Geral ---
        tab_geral = QWidget()
        layout_geral = QVBoxLayout(tab_geral)
        form_geral = QFormLayout()
        
        self.cfg_scripts_path = QLineEdit(os.path.join(os.path.dirname(os.path.abspath(__file__)), "SCRIPTS"))
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(lambda: self._browse_folder(self.cfg_scripts_path))
        
        h_path = QHBoxLayout()
        h_path.addWidget(self.cfg_scripts_path)
        h_path.addWidget(btn_browse)
        form_geral.addRow("Pasta de Scripts:", h_path)
        
        self.cfg_auto_save = QCheckBox("Salvar sessão automaticamente ao fechar")
        self.cfg_auto_save.setChecked(True)
        form_geral.addRow("Auto-Save:", self.cfg_auto_save)
        
        layout_geral.addLayout(form_geral)
        layout_geral.addStretch()
        tabs.addTab(tab_geral, "Geral")

        # --- Tab 2: Layers (AutoCAD) ---
        tab_layers = QWidget()
        layout_layers = QVBoxLayout(tab_layers)
        form_layers = QFormLayout()

        # Dicionário para guardar referências aos inputs
        self.inputs_layers = {}
        
        # Garante que a chave 'layers' existe
        if "layers" not in self.config:
            self.config["layers"] = self._obter_config_padrao()["layers"]

        # Mapeamento de nomes amigáveis para as chaves
        labels_map = {
            "paineis": "Layer Painéis:",
            "sarrafos_verticais": "Sarrafo Vertical (Padrão):",
            "sarrafos_horizontais": "Sarrafo Horizontal (Padrão):",
            "sarrafos_horizontais_pequenos": "Sarrafo Horizontal (Pequeno):",
            "nome_observacoes": "Layer Textos/Nomes:",
            "textos_laterais": "Layer Textos Laterais:",
            "cotas": "Layer Cotas:",
            "laje": "Layer Laje:",
            "sarrafos_verticais_extremidades": "Sarrafo Vertical Extremidade (7cm):",
            "sarrafos_verticais_extremidades": "Sarrafo Vertical Extremidade (7cm):",
            "sarrafos_verticais_grades": "Sarrafo Vertical Central Grade (3.5cm):",
            "obstaculo": "Layer Obstáculo:",
            "texto_pontaletes": "Layer Texto Pontaletes:"
        }

        # Cria inputs baseados na config padrão para manter ordem e integridade
        default_layers = self._obter_config_padrao()["layers"]
        for key, default_val in default_layers.items():
            current_val = self.config["layers"].get(key, default_val)
            le = QLineEdit(str(current_val))
            label_text = labels_map.get(key, f"Layer {key}:")
            form_layers.addRow(label_text, le)
            self.inputs_layers[key] = le

        layout_layers.addLayout(form_layers)
        
        # Botão para restaurar padrões de layers
        btn_reset_layers = QPushButton("Restaurar Padrões de Layers")
        btn_reset_layers.clicked.connect(lambda: self._reset_layers_ui(default_layers))
        layout_layers.addWidget(btn_reset_layers)
        
        tabs.addTab(tab_layers, "Layers (AutoCAD)")

        # --- Tab 3: Opções Avançadas e Comandos Personalizados ---
        tab_opts = QWidget()
        layout_opts = QVBoxLayout(tab_opts)
        
        # Scroll Area para acomodar muitos comandos
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        form_opts = QFormLayout(scroll_content)
        
        self.inputs_cmds = {}
        if "comandos" not in self.config: self.config["comandos"] = self._obter_config_padrao()["comandos"]
        if "opcoes" not in self.config: self.config["opcoes"] = self._obter_config_padrao()["opcoes"]

        # Tipo de Linha
        self.combo_linetype = QComboBox()
        self.combo_linetype.addItems(["PLINE", "MLINE", "LINE"])
        curr_line = self.config["opcoes"].get("tipo_linha", "PLINE")
        self.combo_linetype.setCurrentText(curr_line)
        form_opts.addRow("Tipo de Linha (Desenho):", self.combo_linetype)

        # Separador visual
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        form_opts.addRow(sep)
        form_opts.addRow(QLabel("<b>Comandos Personalizados (LISP/AutoCAD):</b>"))

        # Extensores e Comandos Diversos (Dinamico)
        # Mesclar defaults com o que já existe para garantir que novos comandos apareçam
        defaults_cmds = self._obter_config_padrao()["comandos"]
        current_cmds = self.config["comandos"]
        
        # Unir chaves
        all_keys = sorted(set(list(defaults_cmds.keys()) + list(current_cmds.keys())))
        
        # Filtra chaves numéricas (1 a 20) para não exibir nesta aba
        filtered_keys = []
        for k in all_keys:
            if not (k.isdigit() and 1 <= int(k) <= 20):
                filtered_keys.append(k)
        
        # Mapeamento de descrições amigáveis (Opcional, mas ajuda)
        desc_map = {
            "extensor1": "Extensor 1 (ex2):",
            "extensor2": "Extensor 2 (Bextend):",
            "app": "Abertura Parede (app):",
            "appdel": "Limpeza Laje (appdel):",
            "ABVET": "Grade Vert. Topo/Esq (ABVET):",
            "ABVEF": "Grade Vert. Fundo/Esq (ABVEF):",
            "ABFDT": "Grade Sarraf. Topo/Dir (ABFDT):",
            "HHHH": "Obstáculo (Hatch):",
            "HH": "Hatch Painel (Verde):",
            "HHH": "Hatch Laje (Geral/Padrão):",
            "hatch_amarelo_reap": "Hatch Reaproveitamento (Amarelo):"
        }

        for key in filtered_keys:
            # Pega valor atual ou default
            val = current_cmds.get(key, defaults_cmds.get(key, ""))
            le = QLineEdit(str(val))
            label_txt = desc_map.get(key, f"Comando {key}:")
            form_opts.addRow(label_txt, le)
            self.inputs_cmds[key] = le

        scroll_area.setWidget(scroll_content)
        layout_opts.addWidget(scroll_area)
        
        tabs.addTab(tab_opts, "Avançado")

        # --- Tab 4: Templates de Configuração ---
        tab_templates = QWidget()
        layout_templates = QVBoxLayout(tab_templates)
        
        if "templates" not in self.config:
            self.config["templates"] = {}

        self.list_templates = QListWidget()
        self.list_templates.addItems(sorted(self.config["templates"].keys()))
        layout_templates.addWidget(QLabel("Templates Salvos:"))
        layout_templates.addWidget(self.list_templates)

        btn_group_tmpl = QHBoxLayout()
        btn_save_tmpl = QPushButton("Salvar Config Atual como Template")
        btn_load_tmpl = QPushButton("Carregar Template Selecionado")
        btn_del_tmpl = QPushButton("Excluir Template")
        
        btn_group_tmpl.addWidget(btn_save_tmpl)
        btn_group_tmpl.addWidget(btn_load_tmpl)
        btn_group_tmpl.addWidget(btn_del_tmpl)
        layout_templates.addLayout(btn_group_tmpl)
        
        tabs.addTab(tab_templates, "Templates")

        # --- Tab 5: Numeração (Blocos) ---
        tab_num = QWidget()
        layout_num = QVBoxLayout(tab_num)
        
        # Ativar/Desativar
        self.rb_num_ativo = QRadioButton("Ativado")
        self.rb_num_desativo = QRadioButton("Desativado")
        
        bg_num = QButtonGroup(tab_num)
        bg_num.addButton(self.rb_num_ativo)
        bg_num.addButton(self.rb_num_desativo)
        
        # Carregar estado atual
        if "numeracao_blocos" not in self.config:
            self.config["numeracao_blocos"] = self._obter_config_padrao()["numeracao_blocos"]
        
        is_active = self.config["numeracao_blocos"].get("ativo", False)
        if is_active:
            self.rb_num_ativo.setChecked(True)
        else:
            self.rb_num_desativo.setChecked(True)
            
        h_num_status = QHBoxLayout()
        h_num_status.addWidget(QLabel("Numeração de Painéis:"))
        h_num_status.addWidget(self.rb_num_ativo)
        h_num_status.addWidget(self.rb_num_desativo)
        h_num_status.addStretch()
        layout_num.addLayout(h_num_status)
        
        layout_num.addWidget(QLabel("Definição dos Blocos (Comandos):"))
        
        # Scroll area para os 20 campos
        scroll_num = QScrollArea()
        scroll_num.setWidgetResizable(True)
        content_num = QWidget()
        form_num = QFormLayout(content_num)
        
        self.inputs_num_blocos = {}
        cmds_num = self.config["numeracao_blocos"].get("comandos", {})
        
        for i in range(1, 21):
            key = str(i)
            val = cmds_num.get(key, f"N{i}")
            le = QLineEdit(val)
            form_num.addRow(f"Número {i}:", le)
            self.inputs_num_blocos[key] = le
            
        scroll_num.setWidget(content_num)
        layout_num.addWidget(scroll_num)
        
        tabs.addTab(tab_num, "Numeração")

        # --- Funções dos Templates ---
        def save_current_as_template():
            name, ok = QInputDialog.getText(dialog, "Novo Template", "Nome do Template:")
            if ok and name:
                # Captura o estado atual da UI
                current_state = {
                    "layers": {k: v.text() for k, v in self.inputs_layers.items()},
                    "comandos": {k: v.text() for k, v in self.inputs_cmds.items()},
                    "opcoes": {"tipo_linha": self.combo_linetype.currentText()}
                }
                self.config["templates"][name] = current_state
                # Atualiza lista
                self.list_templates.clear()
                self.list_templates.addItems(sorted(self.config["templates"].keys()))
                QMessageBox.information(dialog, "Sucesso", f"Template '{name}' salvo!")

        def load_selected_template():
            item = self.list_templates.currentItem()
            if not item: return
            name = item.text()
            data = self.config["templates"].get(name, {})
            
            # Carregar Layers
            layers_data = data.get("layers", {})
            for k, val in layers_data.items():
                if k in self.inputs_layers:
                    self.inputs_layers[k].setText(str(val))
                    
            # Carregar Comandos
            cmds_data = data.get("comandos", {})
            for k, val in cmds_data.items():
                if k in self.inputs_cmds:
                    self.inputs_cmds[k].setText(str(val))
            
            # Carregar Opções
            opts_data = data.get("opcoes", {})
            if "tipo_linha" in opts_data:
                self.combo_linetype.setCurrentText(opts_data["tipo_linha"])
                
            QMessageBox.information(dialog, "Carregado", f"Template '{name}' aplicado na tela.\nClique em OK para salvar definitivamente.")

        def delete_template():
            item = self.list_templates.currentItem()
            if not item: return
            name = item.text()
            res = QMessageBox.question(dialog, "Confirmar", f"Excluir template '{name}'?", QMessageBox.Yes | QMessageBox.No)
            if res == QMessageBox.Yes:
                del self.config["templates"][name]
                self.list_templates.takeItem(self.list_templates.row(item))
                
        btn_save_tmpl.clicked.connect(save_current_as_template)
        btn_load_tmpl.clicked.connect(load_selected_template)
        btn_del_tmpl.clicked.connect(delete_template)

        layout.addWidget(tabs)
        
        # Botões Principais
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        if dialog.exec_() == QDialog.Accepted:
            # Salvar Configurações
            
            # 1. Layers
            for key, le in self.inputs_layers.items():
                self.config["layers"][key] = le.text()
            
            # 2. Comandos
            # 2. Comandos (Evitar salvar chaves numericas que estao na aba Numeracao)
            for key, le in self.inputs_cmds.items():
                # Se for chave 1..20, nao sobrescreve comandos gerais, ou salva em local separado se necessario
                # Na verdade, o dicionário self.config["comandos"] é o geral.
                # Se quisermos separar, não devemos gravar 1..20 aqui se eles forem gerenciados apenas na aba Numeracao.
                if not (key.isdigit() and 1 <= int(key) <= 20):
                    self.config["comandos"][key] = le.text()
                
            # 3. Opções
            self.config["opcoes"]["tipo_linha"] = self.combo_linetype.currentText()
            
            # 4. Numeração
            self.config["numeracao_blocos"]["ativo"] = self.rb_num_ativo.isChecked()
            for key, le in self.inputs_num_blocos.items():
                self.config["numeracao_blocos"]["comandos"][key] = le.text()
                # Remove do dicionário principal se existir para não duplicar visualmente
                if key in self.config["comandos"]:
                    del self.config["comandos"][key]
            
            # Persistir no arquivo config.json
            self._salvar_config()
            
            QMessageBox.information(self, "Sucesso", "Configurações salvas com sucesso!")

    def _reset_layers_ui(self, defaults):
        for key, val in defaults.items():
            if key in self.inputs_layers:
                self.inputs_layers[key].setText(val)

    def _browse_folder(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if path:
            line_edit.setText(path)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        
        # --- LEFT PANEL: LISTS ---
        left_splitter = QSplitter(Qt.Vertical)
        
        # List 1: "Lista de Vigas" with Hierarchy
        self.grp_list1 = QGroupBox("")
        l_list1 = QVBoxLayout(self.grp_list1)
        
        # --- Hierarchy Controls ---
        # Obra
        h_obra = QHBoxLayout()
        h_obra.addLayout(self._add_info("Obra:", "Selecione ou crie o nome do projeto/edifício atual."))
        self.cmb_obra = QComboBox()
        self.cmb_obra.setEditable(False)
        self.cmb_obra.currentTextChanged.connect(self.on_obra_changed)
        h_obra.addWidget(self.cmb_obra)
        
        btn_add_obra = QPushButton("+"); btn_add_obra.setFixedWidth(25)
        btn_add_obra.setToolTip("Adicionar nova Obra ao banco de dados.")
        btn_add_obra.clicked.connect(self.add_obra)
        btn_del_obra = QPushButton("-"); btn_del_obra.setFixedWidth(25)
        btn_del_obra.setToolTip("Excluir Obra e todos os seus pavimentos.")
        btn_del_obra.clicked.connect(self.del_obra)
        h_obra.addWidget(self._wrap_button(btn_add_obra, "Inicia o cadastro de um novo empreendimento/projeto."))
        h_obra.addWidget(self._wrap_button(btn_del_obra, "Apaga permanentemente o projeto selecionado e todos os seus dados."))
        l_list1.addLayout(h_obra)
        
        # Pavimento
        h_pav = QHBoxLayout()
        h_pav.addLayout(self._add_info("Pav:", "Selecione o nível ou pavimento (ex: 2º Pav, Cobertura)."))
        self.cmb_pav = QComboBox()
        self.cmb_pav.setEditable(False)
        self.cmb_pav.currentTextChanged.connect(self.on_pav_changed)
        h_pav.addWidget(self.cmb_pav)
        
        btn_add_pav = QPushButton("+"); btn_add_pav.setFixedWidth(25)
        btn_add_pav.setToolTip("Adicionar novo Pavimento à Obra selecionada.")
        btn_add_pav.clicked.connect(self.add_pavimento)
        
        btn_copy_pav = QPushButton("📋"); btn_copy_pav.setFixedWidth(25)
        btn_copy_pav.setToolTip("Copiar pavimentos e todas as suas vigas para um novo pavimento.")
        btn_copy_pav.clicked.connect(self.copy_pavimento)
        
        btn_del_pav = QPushButton("-"); btn_del_pav.setFixedWidth(25)
        btn_del_pav.setToolTip("Excluir Pavimento e todas as suas vigas.")
        btn_del_pav.clicked.connect(self.del_pavimento)
        
        h_pav.addWidget(self._wrap_button(btn_add_pav, "Cria um novo pavimento/nível dentro da obra atual."))
        h_pav.addWidget(self._wrap_button(btn_copy_pav, "Cria uma cópia idêntica deste pavimento com todas as suas vigas."))
        h_pav.addWidget(self._wrap_button(btn_del_pav, "Remove este pavimento e todas as vigas cadastradas nele."))
        l_list1.addLayout(h_pav)
        
        # Pavimento Metadata
        h_pav_meta = QHBoxLayout()
        self.edt_pav_level_in = QLineEdit()
        self.edt_pav_level_in.setPlaceholderText("Chegada")
        self.edt_pav_level_in.textChanged.connect(self.save_pavimento_metadata)
        
        self.edt_pav_level_out = QLineEdit()
        self.edt_pav_level_out.setPlaceholderText("Saída")
        self.edt_pav_level_out.textChanged.connect(self.save_pavimento_metadata)
        
        h_pav_meta.addWidget(QLabel("Nív. Cheg:"))
        h_pav_meta.addWidget(self.edt_pav_level_in)
        h_pav_meta.addWidget(QLabel("Nív. Saí:"))
        h_pav_meta.addWidget(self.edt_pav_level_out)
        l_list1.addLayout(h_pav_meta)
        
        # Filter / Info
        h_fil1 = QHBoxLayout()
        self.lbl_total_m2 = QLabel("Total m²: 0.00")
        self.lbl_total_m2.setStyleSheet("color: #64B5F6; font-weight: bold;")
        h_fil1.addWidget(self.lbl_total_m2)
        l_list1.addLayout(h_fil1)
        
        self.tree1 = QTreeWidget()
        self.tree1.setHeaderLabels(["Nº", "Nome", "Pav", "Face Combinada"]) 
        self.tree1.itemClicked.connect(self.on_viga_tree_clicked)
        self.tree1.setColumnWidth(0, 40)  # Nº
        self.tree1.setColumnWidth(1, 80)  # Nome reduzido
        self.tree1.setColumnWidth(2, 80)  # Pav reduzido
        self.tree1.header().setStretchLastSection(True) # Faz 'Face Combinada' ocupar o resto
        self.tree1.setSelectionMode(QTreeWidget.ExtendedSelection)
        l_list1.addWidget(self.tree1)
        
        # NOTE: Removed buttons to move them to common container
        
        
        # NOTE: Removed buttons from here to move them below proper lists
        
        left_splitter.addWidget(self.grp_list1)
        
        # List 2 (Hidden by default)
        self.grp_list2 = QGroupBox("Vigas para Reaproveitamento")
        l_list2 = QVBoxLayout(self.grp_list2)
        self.cmb_filter2 = QComboBox()
        self.cmb_filter2.setPlaceholderText("Selecione um Pavimento...")
        self.cmb_filter2.currentTextChanged.connect(self._filter_recycling_list)
        l_list2.addWidget(self.cmb_filter2)
        
        self.tree2 = QTreeWidget()
        self.tree2.setHeaderLabels(["Sel", "Nº", "Nome", "Pav"])
        self.tree2.setColumnWidth(0, 30)
        l_list2.addWidget(self.tree2)
        left_splitter.addWidget(self.grp_list2)
        self.grp_list2.hide() # Initially hidden
        
        # --- BOTOES COMUNS (Movidos para fora da Lista 1) ---
        self.btn_container_common = QWidget()
        layout_btns_common = QVBoxLayout(self.btn_container_common)
        layout_btns_common.setContentsMargins(0, 5, 0, 0)

        # JSON Buttons
        h_json = QHBoxLayout()
        btn_import = QPushButton("Importar JSON")
        btn_import.setToolTip("Lê um arquivo externo de dados para carregar novas vigas no projeto.")
        btn_import.clicked.connect(self.import_data_json)
        btn_export = QPushButton("Exportar JSON")
        btn_export.setToolTip("Salva os dados de todas as vigas deste pavimento em um arquivo JSON externo.")
        btn_export.clicked.connect(self.export_data_json)
        h_json.addWidget(self._wrap_button(btn_import, "Lê um arquivo externo de dados para carregar novas vigas no projeto."))
        h_json.addWidget(self._wrap_button(btn_export, "Salva os dados de todas as vigas deste pavimento em um arquivo JSON externo."))
        # Combine Buttons
        h_combine = QHBoxLayout()
        btn_combine = QPushButton("Combinar Face")
        btn_combine.setToolTip("Vincula a viga selecionada a outra viga (outra face) do projeto.")
        btn_combine.setStyleSheet("background-color: #4DB6AC; color: black; font-weight: bold;")
        btn_combine.clicked.connect(self.action_combine_faces)
        
        btn_uncombine = QPushButton("Descombinar")
        btn_uncombine.setToolTip("Remove o vínculo de combinação da viga selecionada.")
        btn_uncombine.setStyleSheet("background-color: #80CBC4; color: black;")
        btn_uncombine.clicked.connect(self.action_uncombine_faces)
        
        h_combine.addWidget(self._wrap_button(btn_combine, "Permite vincular duas faces de uma mesma viga para processos futuros."))
        h_combine.addWidget(self._wrap_button(btn_uncombine, "Remove qualquer vínculo de combinação existente."))
        layout_btns_common.addLayout(h_combine)

        layout_btns_common.addLayout(h_json)

        btn_infra = QPushButton("Criar Infra LISP")
        btn_infra.setToolTip("Gera a estrutura de arquivos necessária para o funcionamento das rotinas LISP.")
        btn_infra.setStyleSheet("background-color: #5C6BC0; color: white; font-weight: bold;")
        btn_infra.clicked.connect(self.action_create_lisp)
        layout_btns_common.addWidget(self._wrap_button(btn_infra, "Gera a estrutura de arquivos necessária para o funcionamento das rotinas LISP."))
        
        btn_delete_vigas = QPushButton("Excluir Selecionados")
        btn_delete_vigas.setStyleSheet("background-color: #ef5350; color: white; font-weight: bold;")
        btn_delete_vigas.clicked.connect(self.delete_selected_vigas)
        layout_btns_common.addWidget(self._wrap_button(btn_delete_vigas, "Exclui permanentemente as vigas selecionadas na lista."))
        
        
        # --- BOTOES Reaproveitamento (Ocultos por padrão) ---
        self.btn_container_recycling = QWidget()
        layout_btns_rec = QVBoxLayout(self.btn_container_recycling)
        
        btn_reap_conjunto = QPushButton("Reaproveitar Conjunto de Vigas Iguais")
        btn_reap_conjunto.clicked.connect(self.action_reuse_sets) # Connected!
        
        btn_reap_all = QPushButton("Reaproveitar todos demais paineis sem reciclar")
        btn_reap_all.clicked.connect(self.action_reuse_all)

        btn_reap_sel = QPushButton("Reaproveitar vigas selecionadas")
        btn_reap_sel.clicked.connect(self.action_reuse_selected_vigas)
        
        btn_clear_reap = QPushButton("Limpar todos vínculos (Pav. Selecionado)")
        btn_clear_reap.clicked.connect(self.action_clear_pav_links)
        
        for b in [btn_reap_conjunto, btn_reap_all, btn_reap_sel]:
            b.setStyleSheet("background-color: #FFA726; color: black; font-weight: bold;")
            layout_btns_rec.addWidget(b)
            
        btn_clear_reap.setStyleSheet("background-color: #EF5350; color: white; font-weight: bold;")
        layout_btns_rec.addWidget(btn_clear_reap)
            
        self.btn_container_recycling.hide()

        left_container = QWidget()
        lc_layout = QVBoxLayout(left_container)
        
        lbl_title = QLabel("<b>LISTA DE VIGAS</b>")
        lbl_title.setStyleSheet("font-size: 14pt; color: #4FC3F7; margin-bottom: 5px;")
        lc_layout.addWidget(lbl_title, 0)
        
        lc_layout.addWidget(left_splitter)
        lc_layout.addWidget(self.btn_container_recycling)
        lc_layout.addWidget(self.btn_container_common)
        lc_layout.setContentsMargins(5,5,5,5)
        left_container.setFixedWidth(355)
        
        # --- CENTER PANEL: PREVIEW ---
        # --- CENTER PANEL: PREVIEW & PANELS TABLE ---
        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        
        center_splitter = QSplitter(Qt.Vertical)
        
        # Top: Preview
        preview_container = QWidget()
        prev_layout = QVBoxLayout(preview_container)
        prev_layout.setContentsMargins(0,0,0,0)
        self.preview = PreviewWidget()
        prev_layout.addWidget(QLabel("<b>Visualização</b>"))
        prev_layout.addWidget(self.preview)
        center_splitter.addWidget(preview_container)
        
        # Tables Section
        tables_container = QWidget()
        tables_layout = QVBoxLayout(tables_container)
        tables_layout.setContentsMargins(0,0,0,0)
        
        self.tables_splitter = QSplitter(Qt.Vertical)
        
        # Table 1: Current Beam
        t1_cont = QWidget()
        t1_lay = QVBoxLayout(t1_cont)
        t1_lay.setContentsMargins(0,0,0,0)
        t1_lay.addWidget(QLabel("<b>Painéis da Viga em Edição</b>"))
        self.table_panels = QTableWidget()
        cols = [
            "Fornecimento:", "Reap. em:", "ID", "Pavimento", "Conjunto", "Viga", "Painel", "Dimensão",
            "Reap. Pav", "Reap. Conj", "Reap. Viga/P",
            "Sarr. Esq 7", "Sarr. Dir 7", "Tipo",
            "Abert. Esq", "Abert. Dir", "Pilar"
        ]
        self.table_panels.setColumnCount(len(cols))
        self.table_panels.setHorizontalHeaderLabels(cols)
        self.table_panels.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive) # Changed from ResizeToContents to fix geometry error
        t1_lay.addWidget(self.table_panels)
        self.tables_splitter.addWidget(t1_cont)
        
        # Table 2: Recycle Beam
        self.cont_recycle_table = QWidget()
        t2_lay = QVBoxLayout(self.cont_recycle_table)
        t2_lay.setContentsMargins(0,5,0,0)
        t2_lay.addWidget(QLabel("<b>Painéis da Viga de Reaproveitamento (Comparativo)</b>"))
        self.table_panels_recycle = QTableWidget()
        self.table_panels_recycle.setColumnCount(len(cols))
        self.table_panels_recycle.setHorizontalHeaderLabels(cols)
        self.table_panels_recycle.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive) # Changed from ResizeToContents
        t2_lay.addWidget(self.table_panels_recycle)
        self.tables_splitter.addWidget(self.cont_recycle_table)
        self.cont_recycle_table.hide() # Only in recycling mode
        
        tables_layout.addWidget(self.tables_splitter)
        
        # --- Botoes de Vinculo (Reaproveitamento) ---
        self.btn_container_linking = QWidget()
        h_link_btns = QHBoxLayout(self.btn_container_linking)
        h_link_btns.setContentsMargins(0, 5, 0, 5)
        
        btn_v_verde = QPushButton("Vincular Verde")
        btn_v_ama = QPushButton("Vincular Amarelo")
        btn_v_und = QPushButton("Desfazer Vínculo")
        btn_v_save = QPushButton("Salvar Vínculo")
        btn_v_save_green = QPushButton("Salvar Verdes")
        btn_v_save_yellow = QPushButton("Salvar Amarelos")
        btn_v_auto = QPushButton("Sugestão Automática")
        
        btn_v_verde.clicked.connect(self.link_selected_verde)
        btn_v_ama.clicked.connect(self.link_selected_amarelo)
        btn_v_und.clicked.connect(self.unlink_selected)
        btn_v_save.clicked.connect(self.save_selected_link)
        btn_v_save_green.clicked.connect(lambda: self.save_links_by_type('green'))
        btn_v_save_yellow.clicked.connect(lambda: self.save_links_by_type('yellow'))
        btn_v_auto.clicked.connect(lambda: [self._run_matching_suggestion(), self._update_all_rec_ui()])
        
        btn_v_unlink_all = QPushButton("Desvincular Todos")
        btn_v_unlink_all.clicked.connect(self.unlink_multiple_selected)

        # Style
        btn_v_verde.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        btn_v_ama.setStyleSheet("background-color: #FBC02D; color: black; font-weight: bold;")
        btn_v_und.setStyleSheet("background-color: #C62828; color: white; font-weight: bold;")
        btn_v_unlink_all.setStyleSheet("background-color: #B71C1C; color: white; font-weight: bold;") # Darker Red
        btn_v_save.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold;")
        btn_v_save_green.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_v_save_yellow.setStyleSheet("background-color: #FFEB3B; color: black; font-weight: bold;")
        
        for b in [btn_v_verde, btn_v_ama, btn_v_und, btn_v_unlink_all, btn_v_save, btn_v_save_green, btn_v_save_yellow, btn_v_auto]:
            h_link_btns.addWidget(b)
            
        tables_layout.addWidget(self.btn_container_linking)
        self.btn_container_linking.hide() # Hidden by default
        
        center_splitter.addWidget(tables_container)
        
        # Set stretch 75% / 25% (Preview vs Tables Area)
        center_splitter.setStretchFactor(0, 3)
        center_splitter.setStretchFactor(1, 1)
        
        center_layout.addWidget(center_splitter)
        
        # --- RIGHT PANEL: INPUTS ---
        right_panel = QFrame()
        right_panel.setFixedWidth(550) # Wider for all fields
        right_layout = QVBoxLayout(right_panel)
        
        # Command Buttons Grid
        cmd_grp = QGroupBox("Comandos")
        grid_cmd = QGridLayout(cmd_grp)
        
        cmd_infos = {
            "Próxima Viga": "<b>Para que serve:</b> Finaliza a viga atual (apenas salva os dados) e inicia o processo de captura automático para a próxima viga.<br><br><b>Passo a passo:</b><br>1. Marque na aba Geral quais dados deseja capturar (furos, pilares, níveis).<br>2. Clique neste botão.<br>3. O sistema salva a viga atual, incrementa o número e inicia os comandos no AutoCAD.",
            "Próximo Segmento": "<b>Para que serve:</b> Finaliza a viga atual (salva) e inicia a captura do próximo segmento/trecho da viga composta.<br><br><b>Passo a passo:</b><br>1. Clique no botão.<br>2. O sistema mantém o nome base, incrementa o sufixo (ex: .1 para .2) e volta para a captura no AutoCAD.",
            "Select Nomes": "<b>Para que serve:</b> Cadastra várias vigas rapidamente lendo os textos do desenho.<br><br><b>Passo a passo:</b><br>1. Clique no botão.<br>2. No AutoCAD, selecione os textos (Text/MText) que contém os nomes (ex: V1, V2).<br>3. Pressione ENTER. As vigas aparecerão na lista automaticamente.",
            "Select Linha": "<b>Para que serve:</b> Captura o comprimento real do painel lateral.<br><br><b>Passo a passo:</b><br>1. Selecione a viga na lista.<br>2. Clique neste botão.<br>3. No AutoCAD, clique em 2 pontos para definir o comprimento da face da viga.<br>4. O campo 'Largura' será preenchido.",
            "Select Níveis": "<b>Para que serve:</b> Automatiza o cálculo de níveis e altura H2.<br><br><b>Passo a passo:</b><br>1. Clique no botão.<br>2. Selecione o texto do nível da face da viga (Lado A ou B) que está fazendo.<br>3. Selecione o texto do nível da face oposta da viga.<br>4. O sistema calcula a diferença e preenche 'Nível Viga' e 'Nível Oposto' automaticamente.",
            "Selecionar Nível Pé Direito": "<b>Para que serve:</b> Refina a captura do nível do teto para cálculo do pé-direito.<br><br><b>Passo a passo:</b><br>Siga as mesmas instruções do 'Select Níveis' clicando no texto de nível de teto/pavimento superior.",
            "Select Pilar": "<b>Para que serve:</b> Define a posição e largura das aberturas para as grades do Pilar, sendo sarrafeado este local demarcado.<br><br><b>Passo a passo:</b><br>1. Clique no botão.<br>2. No AutoCAD, selecione o pilar esquerdo (clique em 2 pontos para definir a largura).<br>3. Repita para o pilar direito.<br>4. Os dados serão salvos na aba 'Detalhes'.",
            "Select Abertura": "<b>Para que serve:</b> Detecta onde devem ser feitas as aberturas para as vigas que chegam (conexões). Encontra a intersecção automaticamente.<br><br><b>Passo a passo:</b><br>1. Clique no botão.<br>2. No AutoCAD, selecione o texto da dimensão da viga que chega (ex: 20x50).<br>3. A localização (Topo, Fundo, Esq, Dir) deve ser selecionada previamente na tabela de Aberturas.<br>4. <b>Importante:</b> A distância padrão é 0 (esquina do painel). Para alterar a posição, edite manualmente o campo 'Dist'.",
            "Gerar Script": "<b>Para que serve:</b> Cria o arquivo .SCR apenas para a viga atual em edição.<br><br><b>Passo a passo:</b><br>1. Finalize os dados da viga.<br>2. Clique em 'Gerar Script'.<br>3. Carregue o arquivo no AutoCAD usando o comando SCRIPT.",
            "Gerar Pavimento": "<b>Para que serve:</b> Exporta todos os scripts do pavimento atual de uma só vez.<br><br><b>Passo a passo:</b><br>Use este comando ao final do projeto para obter todos os arquivos organizados em pastas por obra/pavimento.",
            "Gerar conjunto de Viga": "<b>Para que serve:</b> Exporta apenas os scripts que pertencem ao mesmo conjunto da viga atual (ex: todos os segmentos de V1.A).<br><br><b>Passo a passo:</b><br>1. Selecione a viga desejada.<br>2. Clique neste botão para gerar o conjunto completo (necessita do ordenador e combinador).",
            "Combinar": "<b>Para que serve:</b> Une vários scripts individuais em um único arquivo mestre.<br><br><b>Passo a passo:</b><br>1. Escolha a pasta das vigas.<br>2. O sistema cria um arquivo único para desenhar tudo sequencialmente no CAD.",
            "Ordenar": "<b>Para que serve:</b> Organiza a ordem lógica dos scripts gerados.<br><br><b>Passo a passo:</b><br>Selecione a pasta dos scripts. O sistema renomeará os arquivos para respeitar a ordem numérica (V1, V2, V3...).",
            "Salvar": "<b>Para que serve:</b> Salva manualmente os dados editados na interface para a viga atual.<br><br><b>Passo a passo:</b><br>1. Altere os valores nos campos (ex: furos, larguras).<br>2. Clique em Salvar para garantir que o preview e os dados internos sejam atualizados."
        }
        
        cmds = [
            ("Próxima Viga", self.action_next_beam),
            ("Próximo Segmento", self.action_next_segment),
            ("Select Nomes", self.action_select_names),
            ("Select Linha", self.action_select_line),
            ("Select Níveis", self.action_select_levels),
            ("Selecionar Nível Pé Direito", lambda: print("Required separate impl")),
            ("Select Pilar", self.action_select_pillar),
            ("Select Abertura", self.action_select_opening),
            ("Gerar Script", self.generate_script_current),
            ("Gerar Pavimento", self.generate_pavimento_scripts),
            ("Gerar conjunto de Viga", self.generate_conjunto_scripts),
            ("Reiniciar Seleção", self.action_restart_sequence),
            ("Combinar", self.action_combine_scripts),
            ("Ordenar", self.action_sort_scripts),
            ("Salvar", self.save_current_fundo),
        ]
        
        r, c = 0, 0
        for text, func in cmds:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            btn.setToolTip(cmd_infos.get(text, ""))
            if text in ["Próxima Viga", "Próximo Segmento"]:
                btn.setStyleSheet("background-color: #2E7D32; font-weight: bold;")
            elif text == "Salvar" or text == "Gerar conjunto de Viga":
                btn.setStyleSheet("background-color: #1976D2; font-weight: bold;")
            elif text == "Gerar Pavimento":
                btn.setStyleSheet("background-color: #C62828; font-weight: bold;") # Red for destructive/bulk action
            
            wrapped = self._wrap_button(btn, cmd_infos.get(text, "Sem informações disponíveis."))
            grid_cmd.addWidget(wrapped, r, c)
            c += 1
            if c > 2: # Reduced columns to accommodate info buttons
                c = 0
                r += 1
        
        # Add info button for the group (optional now, but keeping for general help)
        grid_cmd.addLayout(self._add_info("Ajuda de Comandos:", "Estes botões executam ações diretas de sincronização com o AutoCAD ou processamento de dados."), r+1, 0, 1, 3)
        
        right_layout.addWidget(cmd_grp)
        
        # Tabs
        self.tabs = QTabWidget()
        self.init_tab_general()
        self.init_tab_panels()
        self.init_tab_details()
        self.init_tab_class()
        
        right_layout.addWidget(self.tabs)
        
        main_layout.addWidget(left_container)
        main_layout.addWidget(center_panel)
        main_layout.addWidget(right_panel)
        
        # Connect Tree Selection
        self.tree1.itemSelectionChanged.connect(self.on_tree1_selection_changed)
        self.tree2.itemSelectionChanged.connect(self.on_tree2_selection_changed)

    def _add_info(self, label_text, info_text):
        """Creates a layout with a label and an info [i] button."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        lbl = QLabel(label_text)
        btn = QToolButton()
        # Use standard information icon or text if preferred
        btn.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        btn.setToolTip(info_text)
        btn.setFixedSize(18, 18)
        btn.setStyleSheet("border: none; background: transparent; color: #4FC3F7;")
        # Also show message box on click for mobile/different users
        btn.clicked.connect(lambda: QMessageBox.information(self, "Informação", info_text))
        
        layout.addWidget(lbl)
        layout.addWidget(btn)
        layout.addStretch()
        return layout

    def _wrap_button(self, button, info_text):
        """Wraps a button into a layout with an info icon next to it."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        info_btn = QToolButton()
        info_btn.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        info_btn.setToolTip(info_text)
        info_btn.setFixedSize(16, 16)
        info_btn.setStyleSheet("border: none; background: transparent; color: #4FC3F7;")
        info_btn.clicked.connect(lambda: QMessageBox.information(self, "Informação", info_text))
        
        layout.addWidget(button)
        layout.addWidget(info_btn)
        return container

    def _wrap_chk(self, chk, info):
        """Wraps a checkbox with an info button in a single widget."""
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(4)
        l.addWidget(chk)
        btn = QToolButton()
        btn.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        btn.setToolTip(info)
        btn.setFixedSize(18, 18)
        btn.setStyleSheet("border: none; background: transparent; color: #4FC3F7;")
        btn.clicked.connect(lambda: QMessageBox.information(self, "Informação", info))
        l.addWidget(btn)
        # l.addStretch() # Removed stretch to keep it tight
        return w

    def init_tab_general(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Basic Info Grid
        form = QGridLayout()
        
        # Segment Class Controls
        form.addLayout(self._add_info("Conjunto de Segmentos da Viga:", "Organize suas vigas em grupos (Cards na lista lateral). Isso facilita a separação por etapas ou tipos."), 0, 0)
        self.cmb_classes = QComboBox()
        self.cmb_classes.addItems(["Lista Geral"])
        self.cmb_classes.currentTextChanged.connect(self.update_model)
        form.addWidget(self.cmb_classes, 0, 1)
        
        h_btn_class = QHBoxLayout()
        btn_add_class = QPushButton("+"); btn_add_class.setFixedWidth(25)
        btn_add_class.clicked.connect(self.add_segment_class)
        btn_rem_class = QPushButton("-"); btn_rem_class.setFixedWidth(25)
        btn_rem_class.clicked.connect(self.remove_segment_class)
        h_btn_class.addWidget(self._wrap_button(btn_add_class, "Criar novo conjunto de segmentos neste pavimento."))
        h_btn_class.addWidget(self._wrap_button(btn_rem_class, "Excluir conjunto atual (vigas retornam à Lista Geral)."))
        h_btn_class.addStretch()
        form.addLayout(h_btn_class, 0, 2)
        
        self.edt_num = QLineEdit(); form.addLayout(self._add_info("Número:", "<b>Para que serve:</b> Identificador numérico interno da viga para organização na lista lateral.<br><br><b>Exemplo:</b> 104."), 1, 0); form.addWidget(self.edt_num, 1, 1)
        self.lbl_pav_tag = TagLabel(""); form.addLayout(self._add_info("Pavimento:", "Nível ou pavimento selecionado."), 1, 2); form.addWidget(self.lbl_pav_tag, 1, 3)
        
        self.edt_name = QLineEdit(); form.addLayout(self._add_info("Nome:", "<b>Para que serve:</b> Nome que será escrito no rótulo da fôrma no AutoCAD.<br><br><b>Exemplo:</b> V104-A (Onde A é o lado)."), 2, 0); form.addWidget(self.edt_name, 2, 1)
        self.edt_obs = QLineEdit(); form.addLayout(self._add_info("Obs:", "Anotações internas que não saem no desenho final."), 2, 2); form.addWidget(self.edt_obs, 2, 3)
        
        self.edt_lvl_beam = QLineEdit(); form.addLayout(self._add_info("Nível Viga:", "<b>Para que serve:</b> Nível estrutural do topo da viga. <br><br><b>IMPORTANTE:</b> Este campo em conjunto com o 'Nível Oposto' calcula automaticamente a altura H2 (degrau) da viga."), 3, 0); form.addWidget(self.edt_lvl_beam, 3, 1)
        self.edt_lvl_opp = QLineEdit(); form.addLayout(self._add_info("Nível Oposto:", "<b>Para que serve:</b> Nível da laje ou elemento do outro lado da viga.<br><br><b>Cálculo:</b> Se Nível Viga=100 e Nível Oposto=80, o H2 será de 20cm."), 3, 2); form.addWidget(self.edt_lvl_opp, 3, 3)
        
        self.edt_pe = QLineEdit(); form.addLayout(self._add_info("Pé Direito:", "<b>Para que serve:</b> Altura total do pavimento (piso a piso). Usado como base para cálculos de altura total da face."), 4, 0); form.addWidget(self.edt_pe, 4, 1)
        self.edt_adjust = QLineEdit(); form.addLayout(self._add_info("Ajuste:", "<b>Para que serve:</b> Valor de compensação manual (folga).<br><br><b>Exemplo:</b> Digite -2 para subtrair 2cm da altura final da fôrma por questões de montagem."), 4, 2); form.addWidget(self.edt_adjust, 4, 3)
        
        self.edt_txt_l = QLineEdit(); form.addLayout(self._add_info("Texto Esq:", "Texto que aparecerá na extremidade esquerda da viga."), 5, 0); form.addWidget(self.edt_txt_l, 5, 1)
        self.edt_txt_r = QLineEdit(); form.addLayout(self._add_info("Texto Dir:", "Texto que aparecerá na extremidade direita da viga."), 5, 2); form.addWidget(self.edt_txt_r, 5, 3)
        
        self.edt_bottom = QLineEdit(); form.addLayout(self._add_info("Fundo da Viga:", "<b>Para que serve:</b> Largura do fundo da viga (menor dimensão da seção).<br><br><b>Exemplo:</b> Numa viga 30x70, o fundo é 30."), 6, 0); form.addWidget(self.edt_bottom, 6, 1)
        
        layout.addLayout(form)
        
        # 2 - Detalhes de Salvamento
        h_cont = QHBoxLayout()
        grp_cont = QGroupBox("2 - Detalhes de Salvamento")
        lc = QVBoxLayout(grp_cont)
        
        # Row 1: Continuation (Vertical + Wrap)
        v_cont_layout = QVBoxLayout()
        v_cont_layout.addWidget(QLabel("<b>Deseja continuar a viga?</b>"))
        
        h_radios_layout = QHBoxLayout() # Novo layout horizontal para os botões
        self.rb_cont_obs = QRadioButton("Viga continua após\nObstáculo")
        self.rb_cont_next = QRadioButton("Último Segmento\ndeste lado da Viga")
        self.rb_cont_next.setChecked(True)
        self.rb_cont_cont = QRadioButton("Próximo segmento continua\nabertura de viga")
        
        h_radios_layout.addWidget(self.rb_cont_obs)
        h_radios_layout.addWidget(self.rb_cont_next)
        h_radios_layout.addWidget(self.rb_cont_cont)
        
        v_cont_layout.addLayout(h_radios_layout) # Adiciona o horizontal dentro do vertical (abaixo do label)
        lc.addLayout(v_cont_layout)

        # Row 2: Heights Types
        h_r2 = QHBoxLayout()
        h_r2.addWidget(QLabel("Altura 1:"))
        self.rb_p1_sarr = QRadioButton("Sarrafeado"); self.rb_p1_grade = QRadioButton("Grade")
        self.rb_p1_sarr.setChecked(True)
        h_r2.addWidget(self.rb_p1_sarr); h_r2.addWidget(self.rb_p1_grade)
        
        # Grouping for Isolation
        self.bg_p1_geral = QButtonGroup(self)
        self.bg_p1_geral.addButton(self.rb_p1_sarr); self.bg_p1_geral.addButton(self.rb_p1_grade)
        
        h_r2.addSpacing(30)
        h_r2.addWidget(QLabel("Altura 2:"))
        self.rb_p2_sarr = QRadioButton("Sarrafeado"); self.rb_p2_grade = QRadioButton("Grade")
        self.rb_p2_sarr.setChecked(True)
        h_r2.addWidget(self.rb_p2_sarr); h_r2.addWidget(self.rb_p2_grade)
        
        self.bg_p2_geral = QButtonGroup(self)
        self.bg_p2_geral.addButton(self.rb_p2_sarr); self.bg_p2_geral.addButton(self.rb_p2_grade)
        
        h_r2.addStretch()
        lc.addLayout(h_r2)

        # Row 3: Side
        h_r3 = QHBoxLayout()
        h_r3.addWidget(QLabel("Lado:"))
        self.rb_side_a = QRadioButton("A"); self.rb_side_a.setChecked(True)
        self.rb_side_b = QRadioButton("B")
        h_r3.addWidget(self.rb_side_a); h_r3.addWidget(self.rb_side_b)
        h_r3.addStretch()
        lc.addLayout(h_r3)
        
        h_cont.addWidget(grp_cont)
        layout.addLayout(h_cont)

        # 1 - Opções Para Próxima Seleção
        grp_next = QGroupBox("1 - Opções Para Próxima Seleção")
        l_next = QGridLayout(grp_next)
        
        # Headers
        l_next.addWidget(QLabel("<b>Vigas (Seleção de Lado)</b>"), 0, 0)
        l_next.addWidget(QLabel("<b>Altura da Viga</b>"), 0, 1)

        # Row 1: H0
        self.chk_prod_h0 = QCheckBox("Lado Esquerdo / Topo")
        self.chk_prod_fh0 = QCheckBox("Forçar H1")
        l_next.addWidget(self._wrap_chk(self.chk_prod_h0, "O robô pedirá para selecionar o texto da abertura (ex: 20x50) para o Topo Esquerdo."), 1, 0)
        l_next.addWidget(self._wrap_chk(self.chk_prod_fh0, "Ignora o degrau H2 e desenha o furo considerando a altura total da viga (H1)."), 1, 1)
        
        # Row 2: H1
        self.chk_prod_h1 = QCheckBox("Lado Esquerdo / Fundo")
        self.chk_prod_fh1 = QCheckBox("Forçar H1")
        l_next.addWidget(self._wrap_chk(self.chk_prod_h1, "Captura abertura para o Fundo Esquerdo via seleção de texto no CAD."), 2, 0)
        l_next.addWidget(self._wrap_chk(self.chk_prod_fh1, "Força a altura H1 para este furo."), 2, 1)
        
        # Row 3: H2
        self.chk_prod_h2 = QCheckBox("Lado Direito / Topo")
        self.chk_prod_fh2 = QCheckBox("Forçar H1")
        l_next.addWidget(self._wrap_chk(self.chk_prod_h2, "Captura abertura para o Topo Direito via seleção de texto no CAD."), 3, 0)
        l_next.addWidget(self._wrap_chk(self.chk_prod_fh2, "Força a altura H1 para este furo."), 3, 1)
        
        # Row 4: H3
        self.chk_prod_h3 = QCheckBox("Lado Direito / Fundo")
        self.chk_prod_fh3 = QCheckBox("Forçar H1")
        l_next.addWidget(self._wrap_chk(self.chk_prod_h3, "Captura abertura para o Fundo Direito via seleção de texto no CAD."), 4, 0)
        l_next.addWidget(self._wrap_chk(self.chk_prod_fh3, "Força a altura H1 para este furo."), 4, 1)
        
        # Pillar Section
        l_next.addWidget(QLabel("<b>Detalhe do Pilar:</b>"), 5, 0, 1, 2)
        self.chk_prod_pil_l = QCheckBox("Pilar Esquerda")
        self.chk_prod_pil_r = QCheckBox("Pilar Direita")
        l_next.addWidget(self._wrap_chk(self.chk_prod_pil_l, "Ativa a captura automática das dimensões do pilar esquerdo (Distância e Largura)."), 6, 0)
        l_next.addWidget(self._wrap_chk(self.chk_prod_pil_r, "Ativa a captura automática das dimensões do pilar direito (Distância e Largura)."), 6, 1)
        
        # Level Section
        self.chk_prod_lvl = QCheckBox("Ajustes de Nível da viga")
        l_next.addWidget(self._wrap_chk(self.chk_prod_lvl, "Ativa a captura dos níveis estruturais (Laje e Viga) para cálculo automático de altura e degraus."), 7, 0, 1, 2)
        
        lbl_help_prod = QLabel("<b>Como funciona:</b> Após clicar em 'Próxima Viga', o robô seguirá sequencialmente os itens marcados acima no AutoCAD, solicitando os cliques necessários.")
        lbl_help_prod.setWordWrap(True)
        lbl_help_prod.setStyleSheet("color: #AAA; font-size: 9pt; font-style: italic;")
        l_next.addWidget(lbl_help_prod, 8, 0, 1, 2)
        
        layout.addWidget(grp_next)
        
        # Calculated Area
        self.lbl_area_calc = QLabel("M² = 0.00")
        self.lbl_area_calc.setStyleSheet("font-size: 14pt; color: #4FC3F7; font-weight: bold;")
        layout.addWidget(self.lbl_area_calc)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Geral")
        
        # Connect signals
        for w in [self.edt_num, self.edt_name, self.edt_obs, 
                  self.edt_lvl_beam, self.edt_lvl_opp, self.edt_pe, self.edt_adjust,
                  self.edt_txt_l, self.edt_txt_r]:
            w.textChanged.connect(self.update_model)
        
        self.rb_side_a.toggled.connect(self.update_model)
        self.rb_side_b.toggled.connect(self.update_model) # Connect both for reliability
        
        # Connect logic for auto-calculation of H2
        self.edt_lvl_beam.textChanged.connect(self.update_levels_logic)
        self.edt_lvl_opp.textChanged.connect(self.update_levels_logic)
        
        # Continuation Signals
        self.rb_cont_obs.toggled.connect(self.update_model)
        self.rb_cont_next.toggled.connect(self.update_model)
        self.rb_cont_cont.toggled.connect(self.update_model)
        
        # Name Suffix Logic
        self.rb_side_a.toggled.connect(self.update_name_suffix)
        self.rb_side_b.toggled.connect(self.update_name_suffix) # Connect both for reliability
        self.edt_name.editingFinished.connect(self.update_name_suffix)
        
        # Auto-Rename on Number Change
        # self.edt_num.editingFinished.connect(self.update_name_from_number) # REMOVIDO: Numero nao altera nome

    def init_tab_panels(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # --- Universal Controls ---
        grp_uni = QGroupBox("Universal")
        l_uni = QGridLayout(grp_uni)
        # --- Row 1: Dimensions ---
        row1 = QHBoxLayout()
        row1.addLayout(self._add_info("Lar. Total:", "Define o comprimento total.")); self.u_width = QLineEdit(); row1.addWidget(self.u_width)
        row1.addLayout(self._add_info("Alt. Geral:", "Altura (PD) global.")); self.u_h1 = QLineEdit(); row1.addWidget(self.u_h1)
        row1.addLayout(self._add_info("Alt. 2 Geral:", "H2 global.")); self.u_h2 = QLineEdit(); row1.addWidget(self.u_h2)
        l_uni.addLayout(row1, 0, 0, 1, 6)
        
        # --- Row 2: Types (More Spaced) ---
        row2 = QHBoxLayout()
        row2.addLayout(self._add_info("Tipo 1:", "Sarr: Sarrafeado / Grade: Proteção."))
        self.u_rb_sarr1 = QRadioButton("Sarr"); self.u_rb_grade1 = QRadioButton("Grade")
        self.u_rb_sarr1.setChecked(True)
        self.bg_u1_panels = QButtonGroup(self); self.bg_u1_panels.addButton(self.u_rb_sarr1); self.bg_u1_panels.addButton(self.u_rb_grade1)
        # Grade H1 Universal
        self.u_gh1 = QLineEdit("7.0"); self.u_gh1.setFixedWidth(40)
        row2.addWidget(self.u_rb_sarr1); row2.addWidget(self.u_rb_grade1); row2.addWidget(QLabel(" H:")); row2.addWidget(self.u_gh1)
        
        row2.addSpacing(40)
        
        row2.addLayout(self._add_info("Tipo 2:", "Tipo para H2."))
        self.u_rb_sarr2 = QRadioButton("Sarr"); self.u_rb_grade2 = QRadioButton("Grade")
        self.u_rb_sarr2.setChecked(True)
        self.bg_u2_panels = QButtonGroup(self); self.bg_u2_panels.addButton(self.u_rb_sarr2); self.bg_u2_panels.addButton(self.u_rb_grade2)
        # Grade H2 Universal
        self.u_gh2 = QLineEdit("7.0"); self.u_gh2.setFixedWidth(40)
        row2.addWidget(self.u_rb_sarr2); row2.addWidget(self.u_rb_grade2); row2.addWidget(QLabel(" H:")); row2.addWidget(self.u_gh2)
        row2.addStretch()
        l_uni.addLayout(row2, 1, 0, 1, 6)
        
        # --- Row 3: Slabs ---
        row3 = QHBoxLayout()
        row3.addLayout(self._add_info("L.Sup:", "Laje Superior.")); self.u_slab_t = QLineEdit(); row3.addWidget(self.u_slab_t)
        row3.addLayout(self._add_info("L.Inf:", "Laje Inferior.")); self.u_slab_b = QLineEdit(); row3.addWidget(self.u_slab_b)
        row3.addLayout(self._add_info("L.Cen:", "Espessura L.Cen.")); self.u_slab_c = QLineEdit(); row3.addWidget(self.u_slab_c)
        l_uni.addLayout(row3, 2, 0, 1, 6)
        
        layout.addWidget(grp_uni)
        
        # --- Individual Panels Grid ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        p_widget = QWidget()
        p_grid = QGridLayout(p_widget)
        p_grid.setContentsMargins(10, 10, 10, 10)
        p_grid.setSpacing(8)
        p_grid.setAlignment(Qt.AlignTop)
        
        # Headers
        headers = ["P", "Largura", "Alt 1", "Grade H1", "Tipo 1", "Alt 2", "Grade H2", "Tipo 2", "L.Sup", "L.Inf", "L.Cen"]
        for c, h in enumerate(headers):
            lbl = QLabel(f"<b>{h}</b>")
            lbl.setAlignment(Qt.AlignCenter)
            p_grid.addWidget(lbl, 0, c)
            
        p_grid.setSpacing(4) # Reduzido de 8 para 4 para economizar espaço
            
        self.panel_rows = []
        for i in range(6):
            row = i + 1
            p_label = QLabel(f"P{i+1}")
            p_label.setFixedWidth(20)
            p_grid.addWidget(p_label, row, 0)
            
            w = QLineEdit(); w.setFixedWidth(45); p_grid.addWidget(w, row, 1)
            h1 = QLineEdit(); h1.setFixedWidth(45); p_grid.addWidget(h1, row, 2)
            g_h1 = QLineEdit(); g_h1.setFixedWidth(35); p_grid.addWidget(g_h1, row, 3)
            
            # Type 1
            t1_w = QWidget(); t1_l = QHBoxLayout(t1_w); t1_l.setContentsMargins(0,0,0,0); t1_l.setSpacing(2)
            rb1_s = QRadioButton("S"); rb1_g = QRadioButton("G"); rb1_s.setChecked(True)
            t1_l.addWidget(rb1_s); t1_l.addWidget(rb1_g)
            p_grid.addWidget(t1_w, row, 4)
            bg1 = QButtonGroup(p_widget); bg1.addButton(rb1_s); bg1.addButton(rb1_g)
            
            h2 = QLineEdit(); h2.setFixedWidth(45); p_grid.addWidget(h2, row, 5)
            g_h2 = QLineEdit(); g_h2.setFixedWidth(35); p_grid.addWidget(g_h2, row, 6)
            
            # Type 2
            t2_w = QWidget(); t2_l = QHBoxLayout(t2_w); t2_l.setContentsMargins(0,0,0,0); t2_l.setSpacing(2)
            rb2_s = QRadioButton("S"); rb2_g = QRadioButton("G"); rb2_s.setChecked(True)
            t2_l.addWidget(rb2_s); t2_l.addWidget(rb2_g)
            p_grid.addWidget(t2_w, row, 7)
            bg2 = QButtonGroup(p_widget); bg2.addButton(rb2_s); bg2.addButton(rb2_g)
            
            ls = QLineEdit(); ls.setFixedWidth(35); p_grid.addWidget(ls, row, 8)
            li = QLineEdit(); li.setFixedWidth(35); p_grid.addWidget(li, row, 9)
            lc = QLineEdit(); lc.setFixedWidth(35); p_grid.addWidget(lc, row, 10)
            
            self.panel_rows.append({
                'w': w, 'h1': h1, 'h2': h2,
                'rb1_s': rb1_s, 'rb1_g': rb1_g, 'g_h1': g_h1,
                'rb2_s': rb2_s, 'rb2_g': rb2_g, 'g_h2': g_h2,
                'ls': ls, 'li': li, 'lc': lc
            })
            
            # Connect
            for widget in [w, h1, h2, g_h1, g_h2, ls, li, lc]: 
                widget.textChanged.connect(self.update_model)
            
            w.textChanged.connect(self.recalculate_total_width) # Auto-sum panels
            
            rb1_s.toggled.connect(self.update_model)
            rb2_s.toggled.connect(self.update_model)


        p_grid.setRowStretch(7, 1) # Empurra tudo para cima
        scroll.setWidget(p_widget)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "Painéis")
        
        # Connect Universal
        self.u_width.textChanged.connect(self.update_model)
        self.u_width.textChanged.connect(self.divide_total_width) # Distribute width
        self.u_h1.textChanged.connect(lambda t: [r['h1'].setText(t) for r in self.panel_rows])
        self.u_h2.textChanged.connect(lambda t: [r['h2'].setText(t) for r in self.panel_rows])
        
        # Universal Slabs Logic
        self.u_slab_t.textChanged.connect(lambda t: [r['ls'].setText(t) for r in self.panel_rows])
        self.u_slab_b.textChanged.connect(lambda t: [r['li'].setText(t) for r in self.panel_rows])
        self.u_slab_c.textChanged.connect(lambda t: [r['lc'].setText(t) for r in self.panel_rows])
        
        # Universal Type Bindings
        self.u_rb_sarr1.toggled.connect(lambda checked: [r['rb1_s'].setChecked(True) for r in self.panel_rows] if checked else None)
        self.u_rb_grade1.toggled.connect(lambda checked: [r['rb1_g'].setChecked(True) for r in self.panel_rows] if checked else None)
        self.u_rb_sarr2.toggled.connect(lambda checked: [r['rb2_s'].setChecked(True) for r in self.panel_rows] if checked else None)
        self.u_rb_grade2.toggled.connect(lambda checked: [r['rb2_g'].setChecked(True) for r in self.panel_rows] if checked else None)
        
        # --- Cross-Tab Bindings (Geral <-> Painéis) ---
        # Sync Geral to Universal
        self.rb_p1_sarr.toggled.connect(lambda c: self.u_rb_sarr1.setChecked(True) if c else None)
        self.rb_p1_grade.toggled.connect(lambda c: self.u_rb_grade1.setChecked(True) if c else None)
        self.rb_p2_sarr.toggled.connect(lambda c: self.u_rb_sarr2.setChecked(True) if c else None)
        self.rb_p2_grade.toggled.connect(lambda c: self.u_rb_grade2.setChecked(True) if c else None)
        
        # Sync Universal to Geral (Avoid infinite loops by checking already state)
        self.u_rb_sarr1.toggled.connect(lambda c: self.rb_p1_sarr.setChecked(True) if c else None)
        self.u_rb_grade1.toggled.connect(lambda c: self.rb_p1_grade.setChecked(True) if c else None)
        self.u_rb_sarr2.toggled.connect(lambda c: self.rb_p2_sarr.setChecked(True) if c else None)
        self.u_rb_grade2.toggled.connect(lambda c: self.rb_p2_grade.setChecked(True) if c else None)
        
        # Universal Grade Height Bindings
        self.u_gh1.textChanged.connect(lambda t: [r['g_h1'].setText(t) for r in self.panel_rows])
        self.u_gh2.textChanged.connect(lambda t: [r['g_h2'].setText(t) for r in self.panel_rows])
        
        # Logic to subtract 2.2 from Height when auto-filling Grade Height
        def _apply_grade_offset(t, target):
            try:
                val = float(t.replace(',', '.'))
                # Subtract 2.2 (Sarrafo thickness?)
                target.setText(f"{max(0, val - 2.2):.1f}") 
            except: pass

        # Link General Height to Universal Grade Height (and propagate)
        self.u_h1.textChanged.connect(lambda t: _apply_grade_offset(t, self.u_gh1))
        self.u_h2.textChanged.connect(lambda t: _apply_grade_offset(t, self.u_gh2))


    def init_tab_details(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Options
        grp_opt = QGroupBox("Opções")
        l_opt = QGridLayout(grp_opt)
        self.chk_sv_l = QCheckBox("Sarrafo vert. esq"); self.chk_sv_l.setChecked(True)
        self.chk_sv_r = QCheckBox("Sarrafo vert. dir"); self.chk_sv_r.setChecked(True)
        self.chk_sh2_l = QCheckBox("Sarrafo H2 esq")
        self.chk_sh2_r = QCheckBox("Sarrafo H2 dir")
        
        l_opt.addWidget(self.chk_sv_l, 0, 0); l_opt.addWidget(self.chk_sv_r, 0, 1)
        l_opt.addWidget(self.chk_sh2_l, 1, 0); l_opt.addWidget(self.chk_sh2_r, 1, 1)
        layout.addWidget(grp_opt)
        
        # Aberturas
        grp_ab = QGroupBox("Aberturas")
        l_ab = QGridLayout(grp_ab)
        l_ab.addLayout(self._add_info("Dist", "<b>Para que serve:</b> Distância linear do início do painel correspondente até a face do furo.<br><br><b>Dica:</b> O sistema organiza as fôrmas considerando este deslocamento para o corte preciso."), 0, 1)
        l_ab.addLayout(self._add_info("Prof", "<b>Para que serve:</b> Profundidade ou altura vertical do furo (em cm)."), 0, 2)
        l_ab.addLayout(self._add_info("Larg", "<b>Para que serve:</b> Comprimento horizontal do vão ou tubulação."), 0, 3)
        l_ab.addLayout(self._add_info("Forçar H1", "<b>Para que serve:</b> Força o sistema a desenhar o furo considerando a altura total H1, ignorando possíveis degraus (H2)."), 0, 4)
        
        labels = ["Topo/Esq", "Fundo/Esq", "Topo/Dir", "Fundo/Dir"]
        self.hole_rows = []
        for i, lab in enumerate(labels):
            l_ab.addWidget(QLabel(lab), i+1, 0)
            d = QLineEdit(); p = QLineEdit(); w = QLineEdit(); chk = QCheckBox()
            l_ab.addWidget(d, i+1, 1); l_ab.addWidget(p, i+1, 2); l_ab.addWidget(w, i+1, 3); l_ab.addWidget(chk, i+1, 4)
            self.hole_rows.append((d,p,w,chk))
            for widget in [d,p,w]: widget.textChanged.connect(self.update_model)
            chk.stateChanged.connect(self.update_model)
            
        layout.addWidget(grp_ab)
        
        # Pilares
        grp_pil = QGroupBox("Pilares")
        l_pil = QGridLayout(grp_pil)
        l_pil.addLayout(self._add_info("Distância", "<b>Para que serve:</b> Define onde o pilar se encontra em relação ao início (0) da viga.<br><br><b>Pilar Esq:</b> Geralmente 0.<br><b>Pilar Dir:</b> Coincide com o final da viga."), 0, 1)
        l_pil.addLayout(self._add_info("Largura", "<b>Para que serve:</b> Largura da seção do pilar. Usada para calcular o encontro de fôrmas e sarrafos verticais."), 0, 2)
        
        l_pil.addWidget(QLabel("Pilar Esq:"), 1, 0)
        self.pe_d = QLineEdit(); self.pe_w = QLineEdit()
        l_pil.addWidget(self.pe_d, 1, 1); l_pil.addWidget(self.pe_w, 1, 2)
        
        l_pil.addWidget(QLabel("Pilar Dir:"), 2, 0)
        self.pd_d = QLineEdit(); self.pd_w = QLineEdit()
        l_pil.addWidget(self.pd_d, 2, 1); l_pil.addWidget(self.pd_w, 2, 2)
        
        layout.addWidget(grp_pil)
        layout.addStretch()
        self.tabs.addTab(tab, "Detalhes")
        
        # Connect
        for w in [self.chk_sv_l, self.chk_sv_r, self.chk_sh2_l, self.chk_sh2_r]: w.stateChanged.connect(self.update_model)
        for w in [self.pe_d, self.pe_w, self.pd_d, self.pd_w]: w.textChanged.connect(self.update_model)
        
        # Sincronização 'Forçar H1' Geral <-> Detalhes
        # Geral: chk_prod_fh0..3
        # Detalhes: hole_rows[0..3][3]
        
        # Helper para evitar loops: só setChecked se for diferente
        def sync_chk(source, target):
            if source.isChecked() != target.isChecked():
                target.setChecked(source.isChecked())

        # 0: Topo/Esq
        self.chk_prod_fh0.toggled.connect(lambda c: sync_chk(self.chk_prod_fh0, self.hole_rows[0][3]))
        self.hole_rows[0][3].toggled.connect(lambda c: sync_chk(self.hole_rows[0][3], self.chk_prod_fh0))
        
        # 1: Fundo/Esq
        self.chk_prod_fh1.toggled.connect(lambda c: sync_chk(self.chk_prod_fh1, self.hole_rows[1][3]))
        self.hole_rows[1][3].toggled.connect(lambda c: sync_chk(self.hole_rows[1][3], self.chk_prod_fh1))
        
        # 2: Topo/Dir
        self.chk_prod_fh2.toggled.connect(lambda c: sync_chk(self.chk_prod_fh2, self.hole_rows[2][3]))
        self.hole_rows[2][3].toggled.connect(lambda c: sync_chk(self.hole_rows[2][3], self.chk_prod_fh2))
        
        # 3: Fundo/Dir
        self.chk_prod_fh3.toggled.connect(lambda c: sync_chk(self.chk_prod_fh3, self.hole_rows[3][3]))
        self.hole_rows[3][3].toggled.connect(lambda c: sync_chk(self.hole_rows[3][3], self.chk_prod_fh3))

    def toggle_recycling(self, state):
        if state:
            self._populate_recycling_options()
            self.grp_list2.show()
            self.btn_container_recycling.show()
            self.cont_recycle_table.show()
            self.btn_container_linking.show()
            QMessageBox.information(self, "Modo Reaproveitamento", "Selecione um item na lista 'Vigas para Reaproveitamento' para comparar e vincular.")
        else:
            self.grp_list2.hide()
            self.btn_container_recycling.hide()
            self.cont_recycle_table.hide()
            self.btn_container_linking.hide()
            self.recycle_model = None
            self.preview.draw(self.model) # Return to single view
            
    def toggle_combine(self, state):
        pass

    def recalculate_total_width(self):
        """Soma as larguras dos painéis e atualiza a Largura Total."""
        if self._updating: return
        self._updating = True
        try:
            total = 0.0
            for row in self.panel_rows:
                try:
                    val = float(row['w'].text().replace(',', '.'))
                    total += val
                except: pass
            
            self.u_width.setText(self._clean_str(total))
        finally:
            self._updating = False

    def init_tab_class(self):
        """Initializes the Class View Tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Header Info
        self.lbl_class_name = QLabel("Classe: -")
        self.lbl_class_name.setStyleSheet("font-size: 14pt; font-weight: bold; color: #4FC3F7;")
        layout.addWidget(self.lbl_class_name)
        
        # Scroll Area for the list of items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.container_class_items = QWidget()
        self.layout_class_items = QVBoxLayout(self.container_class_items)
        self.layout_class_items.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.container_class_items)
        layout.addWidget(scroll)
        
        self.tabs.addTab(tab, "Classe")
        # Initially hide the Class tab or just manage switching
        
    def on_tree1_selection_changed(self):
        """Handles selection changes in the Tree Widget."""
        items = self.tree1.selectedItems()
        if not items:
            return

        # Consider the first selected item for mode switching
        item = items[0]
        data = item.data(0, Qt.UserRole)
        
        if not data:
            return
            
        if isinstance(data, dict) and data.get('type') == 'class':
            # Class Selected
            cls_name = data.get('key')
            self.load_class_view(cls_name)
        else:
            # Beam Selected (or legacy string key)
            key = data if isinstance(data, str) else data.get('key')
            self.load_beam_view(key)

    def load_class_view(self, class_name):
        """Loads the Class View: Enables Class Tab, Disables others, Draws Multiple."""
        self.current_class_view = class_name
        
        # 1. Manage Tabs
        # Indices: 0=Geral, 1=Paineis, 2=Detalhes, 3=Classe (assuming order)
        self.tabs.setTabEnabled(0, False) # Geral
        self.tabs.setTabEnabled(1, False) # Paineis
        self.tabs.setTabEnabled(2, False) # Detalhes
        self.tabs.setTabEnabled(3, True)  # Classe
        self.tabs.setCurrentIndex(3)
        
        self.lbl_class_name.setText(f"Classe: {class_name}")
        
        # 2. Clear Previous List
        while self.layout_class_items.count():
            child = self.layout_class_items.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        # 3. Fetch Beams
        if not self.current_obra or not self.current_pavimento: return
        pav_data = self.project_data[self.current_obra][self.current_pavimento].get('vigas', {})
        
        class_beams = []
        for k, v in pav_data.items():
            v_cls = getattr(v, 'segment_class', 'Lista Geral') if not isinstance(v, dict) else v.get('segment_class', 'Lista Geral')
            if v_cls == class_name:
                class_beams.append(v)
        
        # Sort by Name
        class_beams.sort(key=lambda x: (x.name if hasattr(x, 'name') else x.get('name', '')))
        
        # 4. Populate List UI with Pairs Grouping
        # Mapping for easy lookup
        uid_to_beam = {}
        for b in class_beams:
            state = self._dict_to_state(b) if isinstance(b, dict) else b
            uid_to_beam[state.unique_id] = state
        
        # Identify all unique pairs (minID, maxID)
        unique_pairs = set()
        for state in uid_to_beam.values():
            uid = state.unique_id
            combined = getattr(state, 'combined_faces', [])
            for link in combined:
                partner_uid = link.get('id')
                if partner_uid in uid_to_beam:
                    pair = tuple(sorted((uid, partner_uid)))
                    unique_pairs.add(pair)
        
        # Identify beams that belong to at least one pair
        beams_in_pairs = set()
        for u1, u2 in unique_pairs:
            beams_in_pairs.add(u1)
            beams_in_pairs.add(u2)
            
        # Draw Pairs in UI
        pair_count = 1
        # Sort pairs for stable UI order (by first beam name then second)
        sorted_pairs = sorted(list(unique_pairs), key=lambda x: (uid_to_beam[x[0]].name, uid_to_beam[x[1]].name))
        
        for u1, u2 in sorted_pairs:
            s1 = uid_to_beam[u1]
            s2 = uid_to_beam[u2]
            
            # Pair Box
            pair_box = QGroupBox(f"Visão de Corte {pair_count}")
            pair_box.setStyleSheet("QGroupBox { border: 2px solid #4CAF50; border-radius: 8px; margin-top: 15px; padding: 10px; background-color: #252525; }")
            pair_layout = QVBoxLayout(pair_box)
            
            # Add Cards for both
            pair_layout.addWidget(self._create_class_beam_card(s1))
            pair_layout.addWidget(self._create_class_beam_card(s2))
            
            self.layout_class_items.addWidget(pair_box)
            pair_count += 1
            
        # Show Singles (beams with no links to items in this same class)
        for state in uid_to_beam.values():
             if state.unique_id not in beams_in_pairs:
                 self.layout_class_items.addWidget(self._create_class_beam_card(state))
            
        # 5. Draw Multiple in Preview
        states_to_draw = list(uid_to_beam.values())
        self.preview.draw_multiple(states_to_draw)

    def _create_class_beam_card(self, state):
        """Helper to create a beam info card for Class View."""
        b_name = state.name
        card = QGroupBox(f"{b_name}")
        card.setStyleSheet("QGroupBox { border: 1px solid #555; border-radius: 5px; margin-top: 10px; font-weight: bold; } "
                         "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; color: #4FC3F7; }")
        cl = QGridLayout(card)
        cl.setSpacing(10)
        
        def add_info(row, col, label, value):
            l_lbl = QLabel(f"<span style='color: #AAA;'>{label}:</span>")
            l_val = QLabel(f"<b>{value}</b>")
            cl.addWidget(l_lbl, row, col*2)
            cl.addWidget(l_val, row, col*2 + 1)

        p0 = state.panels[0] if state.panels else PanelData()
        add_info(0, 0, "Nº", state.number)
        add_info(0, 1, "Lar. Total", f"{state.total_width:.2f}")
        add_info(0, 2, "Painéis", len(state.panels))
        add_info(1, 0, "Alt. Geral (H1)", state.total_height)
        add_info(1, 1, "Alt. 2 Geral (H2)", state.height2_global if state.height2_global else "0.0")
        add_info(1, 2, "Fundo", state.bottom if state.bottom else "0.0")
        add_info(2, 0, "Tipo 1", f"{state.prod_p1_type} (H:{p0.grade_h1})")
        add_info(2, 1, "Tipo 2", f"{state.prod_p2_type} (H:{p0.grade_h2})")
        add_info(3, 0, "L.Sup", f"{p0.slab_top:.2f}")
        add_info(3, 1, "L.Inf", f"{p0.slab_bottom:.2f}")
        add_info(3, 2, "L.Cen", f"{p0.slab_center:.2f}")
        return card

    def load_beam_view(self, key):
        """Loads a single beam into the main editor tabs."""
        self.current_class_view = None
        self.last_loaded_key = key
        
        # 1. Manage Tabs
        self.tabs.setTabEnabled(0, True)
        self.tabs.setTabEnabled(1, True)
        self.tabs.setTabEnabled(2, True)
        self.tabs.setTabEnabled(3, False)
        self.tabs.setCurrentIndex(0) # Go to General
        
        # 2. Load Data (Logic from load_selected_fundo/on_tree_click)
        if not self.current_obra or not self.current_pavimento: return
        pav_data = self.project_data[self.current_obra][self.current_pavimento].get('vigas', {})
        
        if key not in pav_data: return
        
        data = pav_data[key]
        if isinstance(data, dict):
            try: state = VigaState(**data)
            except: 
                print(f"Error loading state for {key}")
                return
        else:
            state = data
            
        self.model = state
        self._ensure_panel_ids(self.model)
        try:
            self.populate_ui_from_state(self.model)
        except Exception as e:
            print(f"Error populating UI: {e}")
            
        # Draw Preview logic
        if self.chk_recycling.isChecked() and self.recycle_model:
            # Clear previous suggestions when loading a beam to start fresh (Manual Only)
            self._clear_unsaved_suggestions(self.model)
            
            # self._run_matching_suggestion() # REMOVED AUTO SUGGESTION per user request
            
            # FORCE PREPARE STATE ON MAIN WINDOW SIDE (Controller)

            self._prepare_preview_state(self.model)
            self._prepare_preview_state(self.recycle_model)
            
            self.preview.draw_dual_view(self.model, self.recycle_model)
            self._populate_panel_list_recycle() # Refresh comparative table
        else:
            self._prepare_preview_state(self.model)
            self.preview.draw(self.model)

        self._populate_panel_list() # Populate the table_panels

    def divide_total_width(self, text):
        """Distribui a largura total entre os painéis (Lógica Legada)."""
        if self._updating: return
        self._updating = True
        try:
            try:
                largura = float(text.replace(',', '.'))
            except:
                # No clear on error to let user type
                return

            # Clear all
            for row in self.panel_rows: row['w'].clear()
            
            # Padrão: Painéis de 244
            num_paineis = int((largura + 243) // 244)
            largura_restante = largura
            paineis = []
            
            for i in range(num_paineis):
                if i == num_paineis - 1:
                    if largura_restante < 60 and len(paineis) > 0:
                         # Ajuste legadizado: se o último for pequeno demais, funde ou divide?
                         # O legado inseria 122 se < 60? Na verdade vou seguir o script legado literal
                         paineis.append(largura_restante)
                    else:
                         paineis.append(largura_restante)
                else:
                    paineis.append(244.0)
                    largura_restante -= 244.0
            
            for i, val in enumerate(paineis[:6]):
                self.panel_rows[i]['w'].setText(self._clean_str(val))
                
        finally:
            self._updating = False
            self.update_model()


    def collect_current_data(self):
        """Coleta os dados atuais da UI e retorna um dicionário compatível com o gerador de scripts."""
        m = self.model
        data = {
            'numero': m.number,
            'pavimento': m.floor,
            'nome': m.name,
            'texto_esq': self.edt_txt_l.text(),
            'texto_dir': self.edt_txt_r.text(),
            'obs': self.edt_obs.text(),
            'largura': m.total_width,
            'altura_geral': self.u_h1.text(), # Assuming universal H1 map to general height var
            'paineis_larguras': [p.width for p in m.panels],
            'paineis_alturas': [p.height1 for p in m.panels],
            'paineis_alturas2': [p.height2 for p in m.panels],
            'aberturas': [[h.dist, h.depth, h.width] for h in m.holes],
            'forcar_altura1': m.prod_force_h1,
            'sarrafo_esq': self.chk_sv_l.isChecked(),
            'sarrafo_dir': self.chk_sv_r.isChecked(),
            'lajes_sup': [p.slab_top for p in m.panels],
            'lajes_inf': [p.slab_bottom for p in m.panels],
            'lajes_central_alt': [p.slab_center for p in m.panels],
            'detalhe_pilar_esq': [self._safe_float(self.pe_d.text()), self._safe_float(self.pe_w.text())],
            'detalhe_pilar_dir': [self._safe_float(self.pd_d.text()), self._safe_float(self.pd_w.text())],
            'nivel_oposto': self.edt_lvl_opp.text(),
            'nivel_viga': self.edt_lvl_beam.text(),
            'nivel_pe_direito': self.edt_pe.text(),
            'ajuste': self.edt_adjust.text(),
            'altura_2_geral': self.u_h2.text(),
            'fundo_viga': self.edt_bottom.text(),
            'paineis_tipo1': [p.type1 for p in m.panels],
            'paineis_tipo2': [p.type2 for p in m.panels],
            'paineis_grade_altura1': [p.grade_h1 if p.grade_h1 > 0.1 else 7.0 for p in m.panels],
            'paineis_grade_altura2': [p.grade_h2 if p.grade_h2 > 0.1 else 7.0 for p in m.panels],
            'paineis_hatch': self._calculate_hatch_types(m),
            'continuacao': m.continuation,
            'lado': m.side,
        }
        
        # Merge global config (preserving beam data if collision)
        final_data = self.config.copy()
        final_data.update(data)
        
        return final_data

    def add_segment_class(self):
        if not self.current_obra or not self.current_pavimento:
            QMessageBox.warning(self, "Aviso", "Selecione uma Obra e Pavimento primeiro.")
            return
            
        name, ok = QInputDialog.getText(self, "Novo Conjunto", "Nome do Conjunto de Segmentos:")
        if ok and name.strip():
            pav_data = self.project_data[self.current_obra][self.current_pavimento]
            if 'metadata' not in pav_data: pav_data['metadata'] = {}
            if 'segment_classes' not in pav_data['metadata']: pav_data['metadata']['segment_classes'] = ["Lista Geral"]
            
            if name.strip() not in pav_data['metadata']['segment_classes']:
                pav_data['metadata']['segment_classes'].append(name.strip())
                self.update_classes_combo()
                # Selecionar o recém criado
                self.cmb_classes.setCurrentText(name.strip())
                self.save_session_data()

    def remove_segment_class(self):
        cls = self.cmb_classes.currentText()
        if cls == "Lista Geral":
            QMessageBox.warning(self, "Aviso", "Não é possível remover a Lista Geral.")
            return
            
        reply = QMessageBox.question(self, "Confirmar", f"Deseja remover o conjunto '{cls}'? As vigas vinculadas voltarão para a Lista Geral.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            pav_data = self.project_data[self.current_obra][self.current_pavimento]
            classes = pav_data['metadata'].get('segment_classes', [])
            if cls in classes:
                classes.remove(cls)
                # Reassign vigas
                vigas = pav_data.get('vigas', {})
                for v in vigas.values():
                    if getattr(v, 'segment_class', '') == cls:
                        v.segment_class = "Lista Geral"
                    elif isinstance(v, dict) and v.get('segment_class', '') == cls:
                        v['segment_class'] = "Lista Geral"
                
                self.update_classes_combo()
                self.update_vigas_list()
                self.save_session_data()

    def update_classes_combo(self):
        self.cmb_classes.blockSignals(True)
        current = self.cmb_classes.currentText()
        self.cmb_classes.clear()
        
        pav_data = self.project_data.get(self.current_obra, {}).get(self.current_pavimento, {})
        classes = pav_data.get('metadata', {}).get('segment_classes', ["Lista Geral"])
        
        self.cmb_classes.addItems(classes)
        idx = self.cmb_classes.findText(current)
        if idx >= 0: self.cmb_classes.setCurrentIndex(idx)
        else: self.cmb_classes.setCurrentText("Lista Geral")
        self.cmb_classes.blockSignals(False)

    def _safe_float(self, val):
        if not val: return 0.0
        try:
            return float(str(val).replace(',', '.'))
        except:
            return 0.0

    def update_model(self):
        if self._updating: return
        self._updating = True
        
        try:
            # Collect data from UI
            name = self.edt_name.text()
            
            try: total_w = float(self.u_width.text().replace(',', '.'))
            except: total_w = 0.0
            
            # Preserve identity and combination fields
            old_id = getattr(self.model, 'unique_id', str(uuid.uuid4()))
            old_comb_faces = getattr(self.model, 'combined_faces', [])
            
            # Panels
            old_panels = []
            if getattr(self, 'model', None) and hasattr(self.model, 'panels'):
                 old_panels = self.model.panels[:]
                 
            panels = []
            for i, row in enumerate(self.panel_rows):
                p = PanelData()
                try: p.width = float(row['w'].text().replace(',', '.'))
                except: p.width = 0.0
                
                p.height1 = row['h1'].text()
                p.height2 = row['h2'].text()
                
                p.type1 = "Sarrafeado" if row['rb1_s'].isChecked() else "Grade"
                p.type2 = "Sarrafeado" if row['rb2_s'].isChecked() else "Grade"
                
                try: p.grade_h1 = float(row['g_h1'].text().replace(',', '.'))
                except: p.grade_h1 = 0.0
                try: p.grade_h2 = float(row['g_h2'].text().replace(',', '.'))
                except: p.grade_h2 = 0.0
                
                try: p.slab_top = float(row['ls'].text().replace(',', '.'))
                except: p.slab_top = 0.0
                try: p.slab_bottom = float(row['li'].text().replace(',', '.'))
                except: p.slab_bottom = 0.0
                try: p.slab_center = float(row['lc'].text().replace(',', '.'))
                except: p.slab_center = 0.0
                
                # --- UID Preservation & Link Breaking ---
                if i < len(old_panels):
                    p_old = old_panels[i]
                    p.uid = p_old.uid
                    p.uid_h2 = p_old.uid_h2
                    p.reused_from = p_old.reused_from
                    p.reused_in = p_old.reused_in
                    p.reused_from_h2 = p_old.reused_from_h2
                    p.reused_in_h2 = p_old.reused_in_h2
                    p.link_saved = p_old.link_saved

                    # --- Robust Broken link check ---
                    h1_new = self._safe_float(p.height1); h1_old = self._safe_float(p_old.height1)
                    h2_new = self._safe_float(p.height2); h2_old = self._safe_float(p_old.height2)
                    
                    w_diff = abs(p.width - p_old.width)
                    h1_diff = abs(h1_new - h1_old)
                    h2_diff = abs(h2_new - h2_old)

                    # If the link was already SAVED, we are very tolerant to manual edits (5 cm)
                    # This prevents P1 loss when user makes small adjustments to the beam geometry.
                    break_limit = 0.01 if not p.link_saved else 5.0
                    
                    should_break = (w_diff > break_limit or h1_diff > break_limit or h2_diff > break_limit)
                    
                    if should_break:

                        # Clear links if dimensions change significantly
                        if p.reused_from or p.reused_from_h2:
                            self._clear_panel_links(p, is_source=False)
                        if p.reused_in or p.reused_in_h2:
                            self._clear_panel_links(p, is_source=True)
                        p.link_saved = False # Also reset saved status if we broke it


                panels.append(p)
                
            # Holes (kept as is)
            holes = []
            for i, (d_widget, pr_widget, w_widget, chk) in enumerate(self.hole_rows):
                h = HoleData()
                try: h.dist = float(d_widget.text().replace(',', '.'))
                except: h.dist = 0.0
                try: h.depth = float(pr_widget.text().replace(',', '.'))
                except: h.depth = 0.0
                try: h.width = float(w_widget.text().replace(',', '.'))
                except: h.width = 0.0
                h.force_h1 = chk.isChecked()
                holes.append(h)
                
            # Pillars
            pl = PillarDetail()
            try: pl.dist = float(self.pe_d.text().replace(',', '.'))
            except: pl.dist = 0.0
            try: pl.width = float(self.pe_w.text().replace(',', '.'))
            except: pl.width = 0.0
            
            pr = PillarDetail()
            try: pr.dist = float(self.pd_d.text().replace(',', '.'))
            except: pr.dist = 0.0
            try: pr.width = float(self.pd_w.text().replace(',', '.'))
            except: pr.width = 0.0
            
            # Continuation
            if self.rb_cont_obs.isChecked(): cont_val = "Obstaculo"
            elif self.rb_cont_cont.isChecked(): cont_val = "Viga Continuacao"
            else: cont_val = "Proxima Parte"
            
            # Create State
            self.model = VigaState(
                number=self.edt_num.text(),
                floor=self.lbl_pav_tag.text(),
                name=self.edt_name.text(),
                obs=self.edt_obs.text(),
                level_beam=self.edt_lvl_beam.text(),
                level_opposite=self.edt_lvl_opp.text(),
                level_ceiling=self.edt_pe.text(),
                adjust=self.edt_adjust.text(),
                text_left=self.edt_txt_l.text(),
                text_right=self.edt_txt_r.text(),
                bottom=self.edt_bottom.text(),
                side="A" if self.rb_side_a.isChecked() else "B",
                continuation=cont_val,
                segment_class=self.cmb_classes.currentText() if self.cmb_classes.currentText() else (self.current_class_view if self.current_class_view else "Lista Geral"),
                
                total_width=self._safe_float(self.u_width.text()),
                total_height=self.u_h1.text(),
                height2_global=self.u_h2.text(),
                
                sarrafo_left=self.chk_sv_l.isChecked(),
                sarrafo_right=self.chk_sv_r.isChecked(),
                sarrafo_h2_left=self.chk_sh2_l.isChecked(),
                sarrafo_h2_right=self.chk_sh2_r.isChecked(),
                
                prod_holes=[self.chk_prod_h0.isChecked(), self.chk_prod_h1.isChecked(), 
                            self.chk_prod_h2.isChecked(), self.chk_prod_h3.isChecked()],
                prod_force_h1=[self.chk_prod_fh0.isChecked(), self.chk_prod_fh1.isChecked(),
                               self.chk_prod_fh2.isChecked(), self.chk_prod_fh3.isChecked()],
                
                prod_pillar_l=self.chk_prod_pil_l.isChecked(),
                prod_pillar_r=self.chk_prod_pil_r.isChecked(),
                prod_viga_nivel=self.chk_prod_lvl.isChecked(),
                prod_p1_type="Sarrafeado" if self.rb_p1_sarr.isChecked() else "Grade",
                prod_p2_type="Sarrafeado" if self.rb_p2_sarr.isChecked() else "Grade",
                
                # Restore preserved identity
                unique_id=old_id,
                combined_faces=old_comb_faces,
                panels=panels,
                holes=holes,
                pillar_left=pl,
                pillar_right=pr,
            )
            
            # Ensure New Panels get structured IDs
            self._ensure_panel_ids(self.model)

            # Calculate Area
            self.model.area_util = self.calculate_total_area(self.model)
            self.lbl_area_calc.setText(f"M² = {self.model.area_util:.2f}")
            self.lbl_total_m2.setText(f"Total m²: {self.model.area_util:.2f}")
            
            # Update Preview
            if hasattr(self, 'preview'):
                self._prepare_preview_state(self.model)
                self.preview.draw(self.model)
            
            self._populate_panel_list()
                 
        except Exception as e:
            traceback.print_exc()
        finally:
            self._updating = False

    def calculate_total_area(self, state: VigaState) -> float:
        """Calcula a área total da fôrma (m²) somando os painéis."""
        total_area = 0.0
        for p in state.panels:
            try:
                w = p.width # cm
                h1 = self._safe_float(p.height1)
                h2 = self._safe_float(p.height2)
                sc = p.slab_center
                
                # Area do Painel (Lado) = Largura * (H1 + H2 + Miolo Laje)
                panel_h = h1 + h2 + sc
                total_area += (w * panel_h)
            except: pass
            
        # Convert cm² to m² (cm * cm = cm². /10000 = m²)
        return total_area / 10000.0

    def update_levels_logic(self):
        """Calculates H2 based on Beam Level and Opposite Level."""
        try:
            lvl_beam_str = self.edt_lvl_beam.text().replace(',', '.')
            lvl_opp_str = self.edt_lvl_opp.text().replace(',', '.')
            
            if not lvl_beam_str or not lvl_opp_str: return
            
            lvl_beam = float(lvl_beam_str)
            lvl_opp = float(lvl_opp_str)
            
            # Logic from Tkinter: altura2 = (nivel_oposto - nivel_viga) * 100
            h2 = (lvl_opp - lvl_beam) * 100
            if h2 < 0: h2 = 0
            
            self.u_h2.setText(f"{h2:.2f}")
            
        except: pass

    def update_name_suffix(self):
        """Manteve o sufixo .A ou .B no nome de acordo com o lado selecionado."""
        if self._updating: return
        
        name = self.edt_name.text().strip()
        if not name: return
        
        side = "A" if self.rb_side_a.isChecked() else "B"
        
        # Remove todos os sufixos existentes tipo .A, .B, .Aa, .Ba, etc no final
        import re
        new_base = re.sub(r'(\.[AB][a-z]*)+$', '', name)
        
        new_name = f"{new_base}.{side}"
        if self.edt_name.text() != new_name:
            self._updating = True
            self.edt_name.setText(new_name)
            self._updating = False
            self.update_model()

    # def update_name_from_number(self): -> REMOVIDO

    def _lookup_panel_info(self, target_uid):
        """Finds panel info (pav, viga, class) by UID in project_data."""
        if not target_uid: return None
        for obra_key, obra_val in self.project_data.items():
            for pav_key, pav_val in obra_val.items():
                vigas_dict = pav_val.get('vigas', {})
                for vpk, vpv in vigas_dict.items():
                    panels_list = []
                    v_floor = pav_key
                    # v_class = vpv.get('segment_class', "Lista Geral") if isinstance(vpv, dict) else vpv.segment_class # Simplified
                    
                    if isinstance(vpv, dict): panels_list = vpv.get('panels', [])
                    else: panels_list = vpv.panels
                    
                    for p_item in panels_list:
                        p_uid = p_item.get('uid', "") if isinstance(p_item, dict) else p_item.uid
                        p_uid_h2 = p_item.get('uid_h2', "") if isinstance(p_item, dict) else p_item.uid_h2
                        
                        if p_uid == target_uid or (p_uid_h2 and p_uid_h2 == target_uid):
                            v_name = vpk
                            return {'pav': v_floor, 'viga': v_name, 'panel_obj': p_item}
        return None

    def _prepare_preview_state(self, state: VigaState):
        """Injects visual metadata (_preview_hatch_type, _preview_tag_text) into panels for drawing."""
        if not state: return
        
        for p in state.panels:
            # Clear previous injections
            p._preview_hatch_type = None
            p._preview_tag_text = ""
            tags = []
            
            # 1. Reuse FROM (Hatch)
            # Priorities: H1 link, then H2 link
            from_uid = p.reused_from or p.reused_from_h2
            # Only visualize if the link is explicitly SAVED by the user
            if from_uid and p.link_saved:
                from_uid_clean = str(from_uid).strip().split(' ')[0] # Remove (S) if present
                info = self._lookup_panel_info(from_uid_clean)
                if info:
                    tags.append(f"Reaproveitado de: {info['pav']} / {info['viga']}")
                    # Determine Green (Exact) or Yellow (Cut)
                    src = info['panel_obj']
                    # Handle dict vs object
                    sw = src.get('width', 0.0) if isinstance(src, dict) else src.width
                    sh1 = self._safe_float(src.get('height1', 0) if isinstance(src, dict) else src.height1)
                    sh2 = self._safe_float(src.get('height2', 0) if isinstance(src, dict) else src.height2)
                    
                    tw = self._safe_float(p.width)
                    th1 = self._safe_float(p.height1)
                    th2 = self._safe_float(p.height2)
                    
                    if abs(sw - tw) < 0.01 and abs(sh1 - th1) < 0.01 and abs(sh2 - th2) < 0.01:
                        p._preview_hatch_type = 'green'
                    else:
                        p._preview_hatch_type = 'yellow'
                else:
                    tags.append("Reaproveitado (Fonte não encontrada)")
                    p._preview_hatch_type = 'yellow'
            
            # 2. Reuse IN (Tag for Source View)
            in_uid = p.reused_in or p.reused_in_h2
            # Only visualize if the link is explicitly SAVED by the user
            if in_uid and p.link_saved:
                in_uid_clean = str(in_uid).strip().split(' ')[0]
                info = self._lookup_panel_info(in_uid_clean)
                if info:
                    vname = info['viga']
                    pavname = info['pav']
                    tags.append(f"Reaproveitado em: {pavname} / {vname}")
                else:
                    # Fallback: Link exists but target info missing
                    tags.append("Reaproveitado (Destino não carregado)")

            if tags:
                p._preview_tag_text = "\n".join(tags)

    def _safe_float(self, text):
        try: return float(str(text).replace(',', '.'))
        except: return 0.0

    def calculate_total_area(self, state: VigaState):
        """Calcula a área total da viga em m²."""
        total_area_cm2 = 0.0
        for p in state.panels:
            if p.width <= 0: continue
            h1 = self._safe_float(p.height1)
            h2 = self._safe_float(p.height2)
            total_area_cm2 += p.width * (h1 + h2 + p.slab_center)
        return total_area_cm2 / 10000.0 # Convert from cm² to m²

    def update_license_display(self):
        """Atualiza a barra de status com informações do usuário e créditos."""
        if hasattr(self, 'licensing_service') and self.licensing_service and self.licensing_service.user_data:
            user = self.licensing_service.user_data
            nome = user.get('nome', 'Usuário')
            creditos = user.get('creditos', 0.0)
            status_text = f"🟢 Conectado: {nome} | Saldo: {creditos:.2f} m²"
            self.statusBar().showMessage(status_text)
            self.statusBar().setStyleSheet("color: #4CAF50; font-weight: bold; background-color: #1e1e1e;")
        else:
            self.statusBar().showMessage("🔴 Desconectado (Modo Offline)")
            self.statusBar().setStyleSheet("color: #f44336; font-weight: bold; background-color: #1e1e1e;")

    def action_next_beam(self):
        """Finaliza a viga atual e prepara a próxima viga."""
        self.update_model()
        self.save_current_fundo()
        
        # Prepare new (Increments to next integer)
        self.prepare_new()
        
        # Re-run sequence
        self.run_sequence_logic()

    def action_restart_sequence(self):
        """Reinicia a sequência de capturas no AutoCAD."""
        self.run_sequence_logic()

    def action_next_segment(self):
        """Finaliza o segmento atual e prepara a continuação (viga composta)."""
        self.update_model()
        self.save_current_fundo()
        
        self.prepare_continuation()
        
        # Re-run sequence
        self.run_sequence_logic()

    def run_sequence_logic(self):
        """Core logic for automated capture sequence in CAD."""
        self.hide()
        self.showMinimized()
        
        try:
            # Step 1: Names (only if it's a new beam or requested, usually handled by action_select_names)
            # For next_beam, we might want to auto-ask if it's not set.
            if not self.edt_name.text():
                self._select_names_logic()
            
            # Step 2: Line (Width)
            self.display_floating("Clique em 2 PONTOS para a LARGURA e pressione Enter")
            val = self.acad_service.select_line_length()
            if val > 0: self.u_width.setText(f"{val:.2f}")
            
            # Step 3: Levels
            if self.chk_prod_lvl.isChecked():
                 self.display_floating("Selecione NÍVEL LAJE e depois NÍVEL VIGA")
                 res = self.acad_service.select_levels()
                 if res.get('beam'): self.edt_lvl_beam.setText(str(res['beam']))
                 if res.get('slab'): self.edt_lvl_opp.setText(str(res['slab']))
                 # H2 calculation is auto-triggered via signals

            # Step 4: Openings
            # checkboxes: Topo/Esq, Fundo/Esq, Topo/Dir, Fundo/Dir
            chks = [
                (self.chk_prod_h0, "Topo/Esq"),
                (self.chk_prod_h1, "Fundo/Esq"),
                (self.chk_prod_h2, "Topo/Dir"),
                (self.chk_prod_h3, "Fundo/Dir")
            ]
            for i, (chk, label) in enumerate(chks):
                if chk.isChecked():
                    self.display_floating(f"Selecione dimensão (ex: 20x50) para: {label}")
                    res = self.acad_service.select_opening_dims()
                    if res.get('w', 0) > 0:
                        # hole_rows[i] = (d, p, w, chk)
                        self.hole_rows[i][1].setText(str(res['d']))
                        self.hole_rows[i][2].setText(str(res['w']))
            
            # Step 5: Pillars
            if self.chk_prod_pil_l.isChecked():
                self.display_floating("Selecione PILAR ESQUERDA (2 pontos de largura)")
                res = self.acad_service.select_pillar_dims()
                if res.get('dist') is not None: self.pe_d.setText(str(res['dist']))
                if res.get('width') is not None: self.pe_w.setText(str(res['width']))
                
            if self.chk_prod_pil_r.isChecked():
                self.display_floating("Selecione PILAR DIREITA (2 pontos de largura)")
                res = self.acad_service.select_pillar_dims()
                if res.get('dist') is not None: self.pd_d.setText(str(res['dist']))
                if res.get('width') is not None: self.pd_w.setText(str(res['width']))
            
            # Update Model & Draw
            self.update_model()
            
        except Exception as e:
            print(f"Sequence Error: {e}")
            
        finally:
            if hasattr(self, '_floating'):
                self._floating.hide()
                self._floating.close()
                delattr(self, '_floating')
            
            self.showMaximized()
            self.raise_()
            self.activateWindow()

    def display_floating(self, msg):
        """Shows a floating instruction message to the user."""
        if not hasattr(self, '_floating'):
            self._floating = FloatingLabel(msg) # Top-level
        self._floating.show_msg(msg)
        QApplication.processEvents()

    def save_current_fundo(self):
        """Salva a viga atual na estrutura hierárquica (Obra -> Pavimento -> Viga)."""
        if not self.current_obra:
            QMessageBox.warning(self, "Aviso", "Selecione ou Crie uma Obra.")
            return

        # Validação de Sufixo (.A ou .B ou .Aa, .Ab, .Ac)
        # Note: Atualiza current_name após possível alteração pelo diálogo
        current_name = self.edt_name.text().strip()
        
        # Regex para verificar se termina em .A ou .B, opcionalmente seguido de uma letra minúscula (sequencial)
        import re
        has_suffix = bool(re.search(r'\.[AB][a-z]?$', current_name))
        
        if not has_suffix:
            msg = QMessageBox(self)
            msg.setWindowTitle("Sufixo de Lado Ausente")
            msg.setText(f"A viga '{current_name}' não possui indicação de lado (.A ou .B).")
            msg.setInformativeText("Selecione o lado para adicionar o sufixo e salvar:")
            btn_a = msg.addButton("Lado .A", QMessageBox.AcceptRole)
            btn_b = msg.addButton("Lado .B", QMessageBox.AcceptRole)
            btn_cancel = msg.addButton("Cancelar", QMessageBox.RejectRole)
            msg.exec()

            if msg.clickedButton() == btn_a:
                self.rb_side_a.setChecked(True)
                self.update_name_suffix() # Força atualização
            elif msg.clickedButton() == btn_b:
                self.rb_side_b.setChecked(True)
                self.update_name_suffix() # Força atualização
            else:
                return # Cancela o salvamento
            
            # Re-get name after update
            current_name = self.edt_name.text().strip()

        if not self.current_pavimento:
            QMessageBox.warning(self, "Aviso", "Selecione ou Crie um Pavimento.")
            return

        # Prepare Project Data Access
        if self.current_obra not in self.project_data: self.project_data[self.current_obra] = {}
        if self.current_pavimento not in self.project_data[self.current_obra]: 
             self.project_data[self.current_obra][self.current_pavimento] = {'vigas': {}, 'metadata': {'in': '', 'out': ''}}
        pav_data = self.project_data[self.current_obra][self.current_pavimento]
        if 'vigas' not in pav_data: pav_data['vigas'] = {}
        existing_keys = pav_data['vigas'].keys()

        # --- VALIDAÇÃO DE NÚMERO ÚNICO ---
        # Verifica se já existe outra viga com este mesmo número no pavimento
        current_num = self.edt_num.text().strip()
        print(f"DEBUG_SAVE: Starting Save. CurrentNum={current_num}, LastLoadedKey={getattr(self, 'last_loaded_key', 'None')}")
        overwrite_target_key = None
        
        if current_num:
            for k, v in pav_data['vigas'].items():
                # Pula se for a viga que estamos editando (pelo nome/key)
                if getattr(self, 'last_loaded_key', None) == k:
                    continue
                
                # Se for dict ou objeto, extraí o number
                v_num = v.get('number') if isinstance(v, dict) else getattr(v, 'number', '')
                if str(v_num).strip() == current_num:
                     # Encontrou conflito de NÚMERO
                     # Pergunta se deseja SUBSCREVER a viga existente (Clone com overwrite) ou Cancelar
                     msg_box = QMessageBox(self)
                     msg_box.setWindowTitle("Viga Existente")
                     msg_box.setText(f"Já existe uma viga (Key: {k}) com o número {current_num}.")
                     msg_box.setInformativeText("Deseja SOBRESCREVER esta viga existente com os dados atuais?\n(Isso substituirá a viga antiga pela nova)")
                     msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                     msg_box.setDefaultButton(QMessageBox.No)
                     ret = msg_box.exec()
                     
                     if ret == QMessageBox.No:
                         return # Aborta salvamento
                     else:
                         overwrite_target_key = k # Marca para remoção se o nome for diferente, ou simples update
                     break

        # --- Lógica de Sequenciamento Automático (.Aa, .Ab, .Ac) ---
        # 1. Identificar Base: V1.Aa -> V1.A | V1.A -> V1.A
        # Remove sufixos minúsculos para encontrar a base .A ou .B
        base_name = re.sub(r'[a-z]+$', '', current_name)
        
        # Garante que a base termina com .A ou .B
        if not (base_name.endswith(".A") or base_name.endswith(".B")):
             base_name = current_name # Fallback

        # 2. Encontrar o próximo sufixo
        # Alfabeto: abcdef...
        import string
        chars = string.ascii_lowercase # abcdefghijklmnopqrstuvwxyz
        next_char_idx = 0
        
        # Verificar o que já existe: base_name + char
        # Queremos o PRIMEIRO LIVRE ou o PRÓXIMO DA SEQUÊNCIA?
        # "caso o item que ele for salvar ja existir .Aa ele salve .Ab" -> Busca o próximo livre.
        
        final_name = f"{base_name}a" # Default start: .Aa
        
        # Loop para achar livre
        for char in chars:
            candidate = f"{base_name}{char}"
            
            # --- VERIFICAÇÃO DE REUSO DA CHAVE (SELF) ---
            # Só permitimos usar o nome da própria viga (overwrite) se o NÚMERO NÃO MUDOU.
            # Se o número mudou, OBRIGATORIAMENTE devemos gerar um novo sufixo (Clone).
            allow_self = False
            last_key = getattr(self, 'last_loaded_key', None)
            
            if last_key == candidate:
                if last_key in pav_data['vigas']:
                    old_item = pav_data['vigas'][last_key]
                    old_num = old_item.get('number') if isinstance(old_item, dict) else getattr(old_item, 'number', '')
                    if str(old_num).strip() == str(current_num).strip():
                        allow_self = True
                    else:
                        allow_self = False # Bloqueia reuso para forçar próximo sufixo
            
            # O nome é válido se não existir na lista OU se for permitido sobrescrever a si mesmo
            if (candidate not in existing_keys) or allow_self:
                final_name = candidate
                break
        
        # Atualiza UI e Modelo com o novo nome sequencial
        if current_name != final_name:
            self._updating = True
            self.edt_name.setText(final_name)
            self._updating = False
        
        # Ensure VigaState is up to date (updates self.model from UI - now with final_name)
        self.update_model() 
        name_key = self.model.name if self.model.name else "SemNome"
        
        # --- Lógica de Substituição de Chave e Sobrescrita ---
        
        # 1. Se confirmou sobrescrever uma viga existente (que tinha o mesmo número)
        if overwrite_target_key and overwrite_target_key in pav_data['vigas']:
            if overwrite_target_key != name_key:
                del pav_data['vigas'][overwrite_target_key]
                print(f"DEBUG: Sobrescrevendo viga existente '{overwrite_target_key}' por '{name_key}'")

        # 2. Se mudou o nome da viga atual (Renomeação ou Clone)
        if getattr(self, 'last_loaded_key', None) and self.last_loaded_key in pav_data['vigas']:
            # Recupera dados da viga antiga
            old_item = pav_data['vigas'][self.last_loaded_key]
            old_num = old_item.get('number') if isinstance(old_item, dict) else getattr(old_item, 'number', '')
            
            # Só removemos a chave antiga se o NOME mudou (V1.A -> V1.B ou V1.A -> V2.A)
            if self.last_loaded_key != name_key:
                # CLONAGEM vs RENOMEAÇÃO
                # Se o usuário confirmou Overwrite, a lógica acima já cuidou. 
                # Aqui cuidado com o item ORIGINAL que estamos editando.
                
                # Se o número é o mesmo -> Renomeação pura (ex: V1.A para V1.B) -> Apaga V1.A
                if str(old_num).strip() == str(current_num).strip():
                    del pav_data['vigas'][self.last_loaded_key]
                    print(f"DEBUG: Renomeação - Removida chave antiga '{self.last_loaded_key}'")
                else:
                    # Se o número mudou (ex: V1.A -> V2.A)
                    # 1. Se V2.A não existia (sem overwrite) -> Criamos V2.A e MANTEMOS V1.A (Clone)
                    # 2. Se V2.A existia e demos overwrite -> V2.A substitui a antiga V2.A. E V1.A??
                    # "deixa o anterior intact pois como foi alterado o numero o salvamento é em outro"
                    # ENTÃO -> NUNCA deletamos a last_loaded_key se o número mudou.
                    print(f"DEBUG: Clone - Nova viga '{name_key}' criada. Mantendo original '{self.last_loaded_key}' intacta.")
                    pass
        
        # Atualiza o last_loaded_key para o novo nome, para salvar futuras edições corretamente
        self.last_loaded_key = name_key

        pav_data['vigas'][name_key] = self.model
        
        # Update List
        self.update_vigas_list()
        
        # Auto-save session
        self.save_session_data()
        
        QMessageBox.information(self, "Salvo", f"Viga '{name_key}' salva em '{self.current_obra}/{self.current_pavimento}'.")

    def load_selected_fundo(self):
        """Carrega a viga selecionada na lista."""
        selected_items = self.tree1.selectedItems()
        if not selected_items: return
        
        item = selected_items[0]
        key = item.data(0, Qt.UserRole)
        self.last_loaded_key = key # Rastreia a chave original carregada
        
        if self.current_obra and self.current_pavimento:
            pav_data = self.project_data.get(self.current_obra, {}).get(self.current_pavimento, {})
            vigas_dict = pav_data.get('vigas', {})
            
            if key in vigas_dict:
                v_state = vigas_dict[key]
                # If it's a dict (from legacy load or raw json), convert to State?
                # We handle both in auto-load, so here it should be State or Dict.
                
                # Check type
                if isinstance(v_state, dict):
                    # Should verify if we want to support dicts at runtime or force convert at load.
                    # Better to treat as dict here if needed OR ensure all are converted.
                    # The auto-load converts, but if `save_current_fundo` saves object...
                    # Let's assume object if logic correct.
                    pass 
                
                # Populate UI
                self.populate_ui_from_state(v_state)

    def populate_ui_from_state(self, state: VigaState):
        """Populates UI from a VigaState object (or equivalent dict)."""
        # Handle if state is dict (fallback)
        if isinstance(state, dict):
             # Quick Hack: Create state from dict slightly unsafe
             # Better: just use dict.get
             d = state
        else:
             d = asdict(state)
        
        # Block signals to prevent feedback
        self._updating = True
        
        try:
            self.edt_num.setText(self._clean_str(d.get('number', '')))
            self.lbl_pav_tag.set_text(self._clean_str(d.get('floor', '')))
            self.edt_name.setText(self._clean_str(d.get('name', '')))
            self.edt_obs.setText(self._clean_str(d.get('obs', '')))
            
            # Set Class
            cls = d.get('segment_class', 'Lista Geral')
            idx = self.cmb_classes.findText(cls)
            if idx >= 0: 
                self.cmb_classes.blockSignals(True)
                self.cmb_classes.setCurrentIndex(idx)
                self.cmb_classes.blockSignals(False)
            else:
                self.cmb_classes.addItem(cls)
                self.cmb_classes.setCurrentText(cls)
                
            self.edt_lvl_beam.setText(self._clean_str(d.get('level_beam', '')))
            self.edt_lvl_opp.setText(self._clean_str(d.get('level_opposite', '')))
            self.edt_pe.setText(self._clean_str(d.get('level_ceiling', '')))
            self.edt_adjust.setText(self._clean_str(d.get('adjust', '')))
            self.edt_txt_l.setText(self._clean_str(d.get('text_left', '')))
            self.u_width.setText(self._clean_str(d.get('total_width', '')))
            self.u_h1.setText(self._clean_str(d.get('total_height', '')))
            self.u_h2.setText(self._clean_str(d.get('height2_global', '')))
            self.edt_txt_r.setText(self._clean_str(d.get('text_right', '')))
            self.edt_bottom.setText(self._clean_str(d.get('bottom', '')))
            
            if d.get('side') == 'B': self.rb_side_b.setChecked(True)
            else: self.rb_side_a.setChecked(True)
            
            # Continuation Logic
            cont = d.get('continuation', 'Proxima Parte')
            if cont == "Obstaculo": self.rb_cont_obs.setChecked(True)
            elif cont == "Viga Continuacao": self.rb_cont_cont.setChecked(True)
            else: self.rb_cont_next.setChecked(True)

            # Production Settings
            prod_holes = d.get('prod_holes', [False]*4)
            if len(prod_holes) == 4:
                self.chk_prod_h0.setChecked(prod_holes[0])
                self.chk_prod_h1.setChecked(prod_holes[1])
                self.chk_prod_h2.setChecked(prod_holes[2])
                self.chk_prod_h3.setChecked(prod_holes[3])
            
            prod_force_h1 = d.get('prod_force_h1', [False]*4)
            if len(prod_force_h1) == 4:
                self.chk_prod_fh0.setChecked(prod_force_h1[0])
                self.chk_prod_fh1.setChecked(prod_force_h1[1])
                self.chk_prod_fh2.setChecked(prod_force_h1[2])
                self.chk_prod_fh3.setChecked(prod_force_h1[3])
            
            self.chk_prod_pil_l.setChecked(d.get('prod_pillar_l', False))
            self.chk_prod_pil_r.setChecked(d.get('prod_pillar_r', False))
            self.chk_prod_lvl.setChecked(d.get('prod_viga_nivel', False))
            
            if d.get('prod_p1_type') == "Grade": self.rb_p1_grade.setChecked(True)
            else: self.rb_p1_sarr.setChecked(True)
            
            if d.get('prod_p2_type') == "Grade": self.rb_p2_grade.setChecked(True)
            else: self.rb_p2_sarr.setChecked(True)

            self.u_h1.setText(self._clean_str(d.get('total_height', '')) or self._clean_str(d.get('altura_geral', '')))
            self.u_h2.setText(self._clean_str(d.get('height2_global', '')))
            self.u_width.setText(self._clean_str(d.get('total_width', '')) or self._clean_str(d.get('largura', '')))
            
            # Panels
            panels = d.get('panels', [])
            for i, row in enumerate(self.panel_rows):
                if i < len(panels):
                    p = panels[i]
                    # If p is dict
                    if isinstance(p, dict):
                         row['w'].setText(str(p.get('width', '')))
                         row['h1'].setText(self._clean_str(p.get('height1', '')))
                         row['h2'].setText(self._clean_str(p.get('height2', '')))
                         if p.get('type1') == 'Grade': row['rb1_g'].setChecked(True)
                         else: row['rb1_s'].setChecked(True)
                         if p.get('type2') == 'Grade': row['rb2_g'].setChecked(True)
                         else: row['rb2_s'].setChecked(True)
                         row['g_h1'].setText(self._clean_str(p.get('grade_h1', '')))
                         row['g_h2'].setText(self._clean_str(p.get('grade_h2', '')))
                         row['ls'].setText(self._clean_str(p.get('slab_top', '')))
                         row['li'].setText(self._clean_str(p.get('slab_bottom', '')))
                         row['lc'].setText(self._clean_str(p.get('slab_center', '')))
                    else:
                         # Ensure string conversion
                         row['w'].setText(str(p.width))
                         row['h1'].setText(self._clean_str(p.height1))
                         row['h2'].setText(self._clean_str(p.height2))
                         if p.type1 == 'Grade': row['rb1_g'].setChecked(True)
                         else: row['rb1_s'].setChecked(True)
                         if p.type2 == 'Grade': row['rb2_g'].setChecked(True)
                         else: row['rb2_s'].setChecked(True)
                         row['g_h1'].setText(self._clean_str(p.grade_h1))
                         row['g_h2'].setText(self._clean_str(p.grade_h2))
                         row['ls'].setText(self._clean_str(p.slab_top))
                         row['li'].setText(self._clean_str(p.slab_bottom))
                         row['lc'].setText(self._clean_str(p.slab_center))
                else:
                    row['w'].clear(); row['h1'].clear(); row['h2'].clear()

            # Holes
            holes = d.get('holes', [])
            for i, (d_w, pr_w, w_w, chk) in enumerate(self.hole_rows):
                if i < len(holes):
                    h = holes[i]
                    if isinstance(h, dict):
                        d_w.setText(self._clean_str(h.get('dist', '')))
                        pr_w.setText(self._clean_str(h.get('depth', '')))
                        w_w.setText(self._clean_str(h.get('width', '')))
                        chk.setChecked(h.get('force_h1', False))
                    else:
                        d_w.setText(self._clean_str(h.dist))
                        pr_w.setText(self._clean_str(h.depth))
                        w_w.setText(self._clean_str(h.width))
                        chk.setChecked(h.force_h1)
                else:
                    d_w.clear(); pr_w.clear(); w_w.clear(); chk.setChecked(False)

            # Pillars
            pl = d.get('pillar_left', {})
            pd = d.get('pillar_right', {})
            if isinstance(pl, dict):
                self.pe_d.setText(self._clean_str(pl.get('dist', '')))
                self.pe_w.setText(self._clean_str(pl.get('width', '')))
            else:
                self.pe_d.setText(self._clean_str(pl.dist))
                self.pe_w.setText(self._clean_str(pl.width))
                
            if isinstance(pd, dict):
                self.pd_d.setText(self._clean_str(pd.get('dist', '')))
                self.pd_w.setText(self._clean_str(pd.get('width', '')))
            else:
                self.pd_d.setText(self._clean_str(pd.dist))
                self.pd_w.setText(self._clean_str(pd.width))

            # Sarrafos
            self.chk_sv_l.setChecked(d.get('sarrafo_left', True))
            self.chk_sv_r.setChecked(d.get('sarrafo_right', True))
            self.chk_sh2_l.setChecked(d.get('sarrafo_h2_left', False))
            self.chk_sh2_r.setChecked(d.get('sarrafo_h2_right', False))
            
            # Continuation
            cont = d.get('continuation', 'Proxima Parte')
            if cont == "Obstaculo": self.rb_cont_obs.setChecked(True)
            elif cont == "Viga Continuacao": self.rb_cont_cont.setChecked(True)
            else: self.rb_cont_next.setChecked(True)
            
        finally:
            self._updating = False
            self.update_model()
            
    def _clean_str(self, val):
        if val is None: return ""
        s = str(val)
        if s.endswith(".0"): return s[:-2]
        if s.endswith(".00"): return s[:-3]
        return s

    def import_script_generator(self):
        """Importa o gerador de script, fazendo patch no messagebox se necessário."""
        import sys
        import tkinter
        from tkinter import messagebox
        
        # Monkey patch tkinter messagebox to use non-blocking print or ignore
        # Or better yet, we just handle exceptions in calling code
        # But gerador_script_viga imports messagebox at top level
        
        try:
            from gerador_script_viga import gerar_script_viga
            return gerar_script_viga
        except ImportError:
            QMessageBox.warning(self, "Aviso", "Módulo 'gerador_script_viga.py' não encontrado.")
            return None

    def generate_script_current(self):
        """Gera o script para a viga atual."""
        self.update_model() # Garante que os dados da UI estão no model
        data = self.collect_current_data()
        pavimento = self._sanitize_name(data.get('pavimento', 'SEM_PAVIMENTO')) or 'SEM_PAVIMENTO'
        
        # Sanitize data inside dictionary too
        data['pavimento'] = pavimento
        data['nome'] = self._sanitize_name(data.get('nome', ''))
        data['obs'] = self._sanitize_name(data.get('obs', ''))
        
        base_dir = os.path.join(self._get_scripts_root(), "SCRIPTS")
        out_dir = os.path.join(base_dir, pavimento)
        
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
            
        generator = self.import_script_generator()
        if not generator:
            return
            
        # --- VERIFICAÇÃO DE LICENÇA (CRÉDITOS) ---
        if not hasattr(self, 'licensing_service') or not self.licensing_service or not self.licensing_service.user_data:
            QMessageBox.warning(self, "Modo Offline", "Geração de script bloqueada no modo Offline.\nRealize o login para consumir créditos e gerar scripts.")
            return

        area_m2 = self.calculate_total_area(self.model)
        if area_m2 <= 0:
            # Se não tem área, algo está errado nos dados, mas não vamos barrar se for 0? 
            # Melhor exigir ao menos uma largura.
            pass 
        
        # Pedir confirmação
        msg = f"A geração deste script consumirá {area_m2:.2f} m² de créditos.\n\nDeseja continuar?"
        ret = QMessageBox.question(self, "Consumo de Créditos", msg, QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return

        success, message = self.licensing_service.consume_credits(area_m2)
        if not success:
            QMessageBox.critical(self, "Sem Créditos", f"Erro ao consumir créditos: {message}")
            return
        
        # Atualiza interface com créditos restantes
        self.update_license_display()

        try:
            script_text, filepath = generator(data, out_dir)
            
            if filepath:
                 self._update_test_script(filepath)
                 QMessageBox.information(self, "Sucesso", f"Script gerado em:\n{filepath}\n\nO comando 'TV' no AutoCAD já está apontando para este arquivo.")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha na geração do script: {e}")
            import traceback
            traceback.print_exc()

    def generate_pavimento_scripts(self):
        """Gera os scripts para todas as vigas do pavimento atual."""
        pav = self.current_pavimento
        obra = self.current_obra
        if not obra or not pav:
            QMessageBox.warning(self, "Aviso", "Selecione uma Obra e Pavimento.")
            return
            
        vigas = self.project_data.get(obra, {}).get(pav, {}).get('vigas', {})
        if not vigas:
            QMessageBox.warning(self, "Aviso", "Nenhuma viga encontrada no pavimento atual.")
            return
            
        self._generate_bulk_scripts(vigas, pav, f"Deseja gerar scripts para TODAS ({len(vigas)}) as vigas do pavimento?")

    def generate_conjunto_scripts(self):
        """Gera os scripts para a CLASSE/CONJUNTO da viga atual (ex: 'Conjunto 1', 'Lista Geral', etc)."""
        pav = self.current_pavimento
        obra = self.current_obra
        
        # Determine Current Class from UI
        current_class = self.cmb_classes.currentText()
        if not current_class:
            QMessageBox.warning(self, "Aviso", "Selecione uma Classe/Conjunto primeiro.")
            return

        if not obra or not pav:
             QMessageBox.warning(self, "Aviso", "Selecione uma Obra e Pavimento.")
             return

        # Filtrar vigas do pavimento que pertencem à CLASSE
        pav_vigas = self.project_data.get(obra, {}).get(pav, {}).get('vigas', {})
        conjunto_vigas = {}
        
        for name, vstate in pav_vigas.items():
            # Check vstate class
            v_class = getattr(vstate, 'segment_class', 'Lista Geral') if not isinstance(vstate, dict) else vstate.get('segment_class', 'Lista Geral')
            
            if v_class == current_class:
                conjunto_vigas[name] = vstate
        
        if not conjunto_vigas:
            QMessageBox.warning(self, "Aviso", f"Nenhuma viga encontrada para a classe '{current_class}'.")
            return

        # Use Class Name as folder
        folder_name = f"{pav}_{current_class}" 
        
        self._generate_bulk_scripts(conjunto_vigas, folder_name, f"Deseja gerar scripts para a CLASSE '{current_class}' ({len(conjunto_vigas)} itens)?")

    def _generate_bulk_scripts(self, vigas_dict, folder_name, question_text):
        """Lógica comum para gerar múltiplos scripts em uma pasta, ordenar e combinar."""
        count = 0
        generator = self.import_script_generator()
        if not generator: return

        # Force save of current beam
        if self.edt_name.text().strip():
             self.save_current_fundo()

        confirm = QMessageBox.question(self, "Confirmar", question_text, QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes: return

        base_dir = os.path.join(self._get_scripts_root(), "SCRIPTS")
        out_dir = os.path.join(base_dir, self._sanitize_name(folder_name) or 'LOTE_VIGAS')
        
        # Limpeza da pasta
        if os.path.exists(out_dir):
            try:
                import shutil
                shutil.rmtree(out_dir)
            except Exception as e:
                print(f"Erro ao limpar pasta {out_dir}: {e}")
        
        if not os.path.exists(out_dir): 
            os.makedirs(out_dir)

        # --- VERIFICAÇÃO DE LICENÇA (LOTE) ---
        if not hasattr(self, 'licensing_service') or not self.licensing_service or not self.licensing_service.user_data:
            QMessageBox.warning(self, "Modo Offline", "Geração de lote bloqueada no modo Offline.\nRealize o login para consumir créditos e gerar scripts.")
            return

        total_lote_m2 = 0.0
        v_items = sorted(vigas_dict.items(), key=lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(x[0]))])
        for name, vstate_obj in v_items:
            if isinstance(vstate_obj, dict):
                v_model = self._dict_to_state(vstate_obj)
            else:
                v_model = vstate_obj
            total_lote_m2 += self.calculate_total_area(v_model)

        msg = f"A geração deste lote de {len(vigas_dict)} scripts consumirá um total de {total_lote_m2:.2f} m² de créditos.\n\nDeseja continuar?"
        ret = QMessageBox.question(self, "Consumo de Créditos", msg, QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return

        success, message = self.licensing_service.consume_credits(total_lote_m2)
        if not success:
            QMessageBox.critical(self, "Sem Créditos", f"Erro ao consumir créditos: {message}")
            return
        
        # Atualiza interface com créditos restantes
        self.update_license_display()

        v_items = sorted(vigas_dict.items(), key=lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(x[0]))])
        
        # Estrutura para acumular contagem de painéis por (VigaBase, Lado)
        # Ex: Key = "V1.A" -> Value = 5 (significa que o próximo painel do lado A começa no 6)
        panels_accumulators = {} 

        for name, vstate_obj in v_items:
            if isinstance(vstate_obj, dict):
                vstate = self._dict_to_state(vstate_obj)
            else:
                vstate = vstate_obj
            
            data = self._vstate_to_script_dict(vstate)
            
            # --- LÓGICA DE NUMERAÇÃO CONTÍNUA ---
            # Identificar a chave da série (Ex: V1.A)
            # Tenta separar por ponto: V1.Aa -> V1.A
            series_key = "Geral"
            if '.' in name:
                parts = name.split('.')
                base = parts[0] # V1
                suffix = parts[1] if len(parts) > 1 else ""
                if len(suffix) >= 1:
                    side = suffix[0] # A ou B
                    series_key = f"{base}.{side}"
            
            # Recuperar indice atual para essa série
            current_start_index = panels_accumulators.get(series_key, 0)
            
            # Injetar dados para o gerador
            data['numeracao_blocos'] = self.config.get('numeracao_blocos', {'ativo': False, 'comandos': {}})
            data['indice_inicial_painel'] = current_start_index
            
            # Calcular quantos painéis esta viga vai gerar para atualizar o acumulador
            qtde_paineis = 0
            l_total = float(data.get('largura', 0))
            
            # 1. Definido por lista explicita
            p_larguras = data.get('paineis_larguras', [])
            if p_larguras and isinstance(p_larguras, list) and any(float(x) > 0 for x in p_larguras):
                qtde_paineis = len([x for x in p_larguras if float(x) > 0])
            else:
                # 2. Definido por p1..p6
                count_p = 0
                for ip in range(1, 7):
                    if data.get(f'p{ip}') and float(data.get(f'p{ip}')) > 0:
                        count_p += 1
                
                if count_p > 0:
                     qtde_paineis = count_p
                else:
                    # 3. Calculado (resto divisão 244)
                     # Lógica simplificada que imita o gerador
                     paineis_fixos_width = 0
                     paineis_fixos = data.get('paineis', [])
                     if paineis_fixos:
                         paineis_fixos_width = sum(float(x) for x in paineis_fixos if float(x)>0)
                     
                     largura_restante = l_total - paineis_fixos_width
                     if largura_restante > 0:
                         import math
                         qtde_paineis = count_p + max(1, math.ceil(largura_restante / 244))
                     elif count_p == 0 and not paineis_fixos:
                         qtde_paineis = 1 # Pelo menos 1 painel (largura total)
            
            # Atualiza acumulador para o próximo segmento
            panels_accumulators[series_key] = current_start_index + qtde_paineis
            
            # GERA O SCRIPT
            _, filepath = generator(data, out_dir)
            count += 1

        # 1. Ordenação
        try:
            import importlib
            import Ordenador_VIGA
            importlib.reload(Ordenador_VIGA)
            Ordenador_VIGA.processar_pasta(out_dir)
        except Exception as e:
            print(f"Aviso ao ordenar: {e}")

        # 2. Combinação
        combined_script = None
        try:
            import importlib
            import Combinador_VIGA
            importlib.reload(Combinador_VIGA)
            Combinador_VIGA.processar_arquivos(out_dir)
            combined_script = os.path.join(out_dir, "Combinados", "1.scr")
        except Exception as e:
            print(f"Aviso ao combinar: {e}")
            
        # 3. Sincronização TV
        if combined_script and os.path.exists(combined_script):
            self._update_test_script(combined_script)
        
        QMessageBox.information(self, "Sucesso", f"{count} scripts gerados em:\n{out_dir}\n\nO comando 'TV' no AutoCAD iniciará a sequência deste lote.")

    def _vstate_to_script_dict(self, m):
        """Converte um VigaState para o formato de dicionário esperado pelo gerador."""
        data = {
            'numero': m.number,
            'pavimento': self._sanitize_name(m.floor),
            'nome': self._sanitize_name(m.name),
            'texto_esq': m.text_left,
            'texto_dir': m.text_right,
            'obs': self._sanitize_name(m.obs),
            'largura': m.total_width,
            'altura_geral': m.total_height, 
            'paineis_larguras': [p.width for p in m.panels],
            'paineis_alturas': [p.height1 for p in m.panels],
            'paineis_alturas2': [p.height2 for p in m.panels],
            'paineis_grade_altura1': [p.grade_h1 if p.grade_h1 > 0.1 else 7.0 for p in m.panels],
            'paineis_grade_altura2': [p.grade_h2 if p.grade_h2 > 0.1 else 7.0 for p in m.panels],
            'aberturas': [[h.dist, h.depth, h.width] for h in m.holes],
            'forcar_altura1': m.prod_force_h1, # Flag de forçar H1 para cada uma das 4 aberturas
            'sarrafo_esq': m.sarrafo_left,
            'sarrafo_dir': m.sarrafo_right,
            'lajes_sup': [p.slab_top for p in m.panels],
            'lajes_inf': [p.slab_bottom for p in m.panels],
            'lajes_central_alt': [p.slab_center for p in m.panels],
            'detalhe_pilar_esq': [m.pillar_left.dist, m.pillar_left.width],
            'detalhe_pilar_dir': [m.pillar_right.dist, m.pillar_right.width],
            'nivel_oposto': m.level_opposite,
            'nivel_viga': m.level_beam,
            'nivel_pe_direito': m.level_ceiling,
            'ajuste': m.adjust,
            'altura_2_geral': m.height2_global,
            'paineis_tipo1': [p.type1 for p in m.panels],
            'paineis_tipo2': [p.type2 for p in m.panels],
            'paineis_hatch': self._calculate_hatch_types(m),
            'continuacao': m.continuation,
            'lado': m.side,
        }
        
        # Merge global config (preserving beam data if collision)
        final_data = self.config.copy()
        final_data.update(data)
        
        return final_data


    def _calculate_hatch_types(self, state):
        """Calculates hatch types (green/yellow/None) for panels in state."""
        hatch_types = []
        for p in state.panels:
            htype = None
            from_uid = p.reused_from or p.reused_from_h2
            if from_uid and p.link_saved:
                from_uid_clean = str(from_uid).strip().split(' ')[0]
                info = self._lookup_panel_info(from_uid_clean)
                if info:
                    src = info['panel_obj']
                    # Handle dict vs object
                    sw = src.get('width', 0.0) if isinstance(src, dict) else src.width
                    sh1 = self._safe_float(src.get('height1', 0) if isinstance(src, dict) else src.height1)
                    sh2 = self._safe_float(src.get('height2', 0) if isinstance(src, dict) else src.height2)
                    
                    tw = self._safe_float(p.width)
                    th1 = self._safe_float(p.height1)
                    th2 = self._safe_float(p.height2)
                    
                    if abs(sw - tw) < 0.01 and abs(sh1 - th1) < 0.01 and abs(sh2 - th2) < 0.01:
                        htype = 'green'
                    else:
                        htype = 'yellow'
                else:
                    htype = 'yellow' # Fallback for missing source info
            elif from_uid:
                 # Link exists but not marked 'saved'?
                 pass
            
            # DEBUG
            # print(f"DEBUG_HATCH_CALC: Panel {p.uid} From={from_uid} Saved={p.link_saved} -> {htype}")
            hatch_types.append(htype)
        # print(f"DEBUG_HATCH_RET: Returned {len(hatch_types)} types.")
        return hatch_types

    def _dict_to_state(self, d):
        """Converts a dictionary (from json) back to VigaState, reconstructing objects."""
        if not isinstance(d, dict): return d
        try:
            # Reconstruct Panels
            panels_data = d.get('panels', [])
            panels_objs = []
            for pd in panels_data:
                p_obj = PanelData()
                if isinstance(pd, dict):
                    for k, v in pd.items():
                        if hasattr(p_obj, k):
                            setattr(p_obj, k, v)
                else:
                    # Assume it's already an object or incompatible
                    p_obj = pd
                panels_objs.append(p_obj)

            # Reconstruct Holes
            holes_data = d.get('holes', [])
            holes_objs = []
            for hd in holes_data:
                h_obj = HoleData()
                if isinstance(hd, dict):
                    for k, v in hd.items():
                        if hasattr(h_obj, k):
                            setattr(h_obj, k, v)
                else:
                    h_obj = hd
                holes_objs.append(h_obj)

            # Construct State
            d_clean = d.copy()
            d_clean['panels'] = panels_objs
            d_clean['holes'] = holes_objs
            
            # Pillars (Simple structs)
            if isinstance(d_clean.get('pillar_left'), dict):
                pl = PillarDetail()
                pl.dist = d_clean['pillar_left'].get('dist', 0.0)
                pl.width = d_clean['pillar_left'].get('width', 0.0)
                d_clean['pillar_left'] = pl
            
            if isinstance(d_clean.get('pillar_right'), dict):
                pr = PillarDetail()
                pr.dist = d_clean['pillar_right'].get('dist', 0.0)
                pr.width = d_clean['pillar_right'].get('width', 0.0)
                d_clean['pillar_right'] = pr

            return VigaState(**d_clean)
        except Exception as e:
            print(f"Error in _dict_to_state: {e}")
            import traceback
            traceback.print_exc()
            return VigaState()

    def _sanitize_name(self, text):
        """Substitui espaços por underscores para compatibilidade de caminhos e scripts."""
        if not text: return ""
        return str(text).strip().replace(" ", "_")

    def action_combine_scripts(self):
        """Abre o diálogo para selecionar pasta e combina os SCRs."""
        from PySide6.QtWidgets import QFileDialog
        dir_path = QFileDialog.getExistingDirectory(self, "Selecione a pasta com os arquivos SCR")
        if dir_path:
            try:
                import Combinador_VIGA
                Combinador_VIGA.processar_arquivos(dir_path)
                QMessageBox.information(self, "Sucesso", f"Arquivos combinados na pasta 'Combinados' dentro de:\n{dir_path}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao combinar scripts: {e}")

    def action_sort_scripts(self):
        """Abre o diálogo para selecionar pasta e ordena coordenadas nos SCRs."""
        from PySide6.QtWidgets import QFileDialog
        dir_path = QFileDialog.getExistingDirectory(self, "Selecione a pasta com os arquivos SCR para ordenar")
        if dir_path:
            try:
                import Ordenador_VIGA
                Ordenador_VIGA.processar_pasta(dir_path)
                QMessageBox.information(self, "Sucesso", f"Coordenadas ordenadas nos arquivos dentro de:\n{dir_path}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao ordenar scripts: {e}")

    def _get_scripts_root(self):
        """Retorna a pasta raiz para os scripts, adaptando para ambiente Dev ou EXE."""
        return self.app_root

    def action_create_lisp(self):
        """Cria os arquivos .lsp e .scr de infraestrutura com paths dinâmicos (Auto-Configuração)."""
        base_dir = self._get_scripts_root()
        scripts_dir = os.path.join(base_dir, "SCRIPTS")
        if not os.path.exists(scripts_dir):
            os.makedirs(scripts_dir)
            
        lsp_path = os.path.join(scripts_dir, "comando_TESTE_VIGA_TV.lsp")
        scr_path = os.path.join(scripts_dir, "TESTE_VIGA_TV.scr")
        
        # Path para o AutoCAD (usando / para compatibilidade)
        scr_path_cad = scr_path.replace("\\", "/")
        
        lsp_content = f';; Comando para executar script SCR automático (Gerado Dinamicamente)\n(defun c:TV ()\n  (command "_SCRIPT" "{scr_path_cad}")\n  (princ)\n)'
        
        try:
            # Escrever LSP
            with open(lsp_path, 'w', encoding='utf-8') as f:
                f.write(lsp_content)
            
            # Criar um .scr inicial/vazio se não existir (UTF-16 LE para o CAD)
            if not os.path.exists(scr_path):
                with open(scr_path, 'w', encoding='utf-16') as f:
                    f.write("; Script de Teste Inicial\n")
            
            QMessageBox.information(self, "Sucesso - Infra LISP", 
                f"Arquivos criados com sucesso!\n\n"
                f"1. Local: {scripts_dir}\n"
                f"2. Comado AutoCAD: TV\n\n"
                f"Arraste o arquivo .lsp para dentro do AutoCAD para ativar o comando.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao criar arquivos de infraestrutura: {e}")

    def _update_test_script(self, source_script_path):
        """Atualiza o conteúdo do TESTE_VIGA_TV.scr com o script recém-gerado."""
        try:
            base_dir = self._get_scripts_root()
            test_scr_path = os.path.join(base_dir, "SCRIPTS", "TESTE_VIGA_TV.scr")
            
            # Garante que a pasta existe
            if not os.path.exists(os.path.dirname(test_scr_path)):
                os.makedirs(os.path.dirname(test_scr_path))
                
            # Copia o conteúdo do script gerado para o script de teste principal
            shutil.copy2(source_script_path, test_scr_path)
            print(f"Sync: {os.path.basename(source_script_path)} -> TESTE_VIGA_TV.scr")
            
        except Exception as e:
            print(f"Erro ao sincronizar script de teste: {e}")

    def _select_names_logic(self):
        """
        Wizard de 6 Passos para coletar dados da viga:
        1. Nome
        2. Texto Esq
        3. Texto Dir
        4. Dimensão Laje -> Define L.Sup inicialmente
        5. Painel Superior -> Se > 0, define H2 e move Laje p/ L.Cen
        6. Altura Geral -> Define H1 (Total - Laje - H2)
        """
        
        def get_user_input(prompt_text):
            """Solicita via AutoCAD com respiro entre passos."""
            import time
            time.sleep(2.0) # Increased from 0.5s to 2.0s to avoid 'Call Rejected'
            
            fl = FloatingLabel(prompt_text)
            fl.show_msg(prompt_text)
            QApplication.processEvents()
            
            print(f"CAD_DEBUG: >>> INÍCIO PASSO: {prompt_text}")
            # Ensure window is active and idle before calling
            val_str = self.acad_service.select_or_type_text(prompt_text)
            print(f"CAD_DEBUG: <<< FIM PASSO: {prompt_text} | Resultado: '{val_str}'")
            
            fl.close()
            return val_str

        def parse_min_max(txt):
            """Extrai o menor e o maior número encontrados na string."""
            if not txt: return 0.0, 0.0
            try:
                clean_txt = txt.replace(',', '.')
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", clean_txt)
                if nums:
                    vals = [float(n) for n in nums]
                    return min(vals), max(vals)
            except: pass
            return 0.0, 0.0

        def parse_max_number(txt):
            _, mx = parse_min_max(txt)
            return mx

        # --- Passo 1: Nome ---
        n = get_user_input("1/6: Selecione ou Digite o NOME")
        if n: 
            self.edt_name.setText(n)
            self.update_name_suffix() # Auto-aplica sufixo baseado no Lado selecionado
            # (Removida a sincronização de número para manter o GAP sugerido)
        
        # --- Passo 2: Texto Esq ---
        l = get_user_input("2/6: Selecione Texto ESQUERDA")
        if l: self.edt_txt_l.setText(l)

        # --- Passo 3: Texto Dir ---
        r = get_user_input("3/6: Selecione Texto DIREITA")
        if r: self.edt_txt_r.setText(r)

        # --- Passo 4: Laje ---
        txt_slab = get_user_input("4/6: Selecione DIMENSÃO DA LAJE (ex: d=12, h=15)")
        val_slab = parse_max_number(txt_slab)
        # Inicialmente preenche L.Sup
        self.u_slab_t.setText(f"{val_slab:.2f}")

        # --- Passo 5: Painel Superior (H2) ---
        txt_top = get_user_input("5/6: Selecione ou Digite PAINEL SUPERIOR (0 se não houver)")
        val_top = parse_max_number(txt_top)
        
        if val_top > 0:
            # Tem H2: Preenche H2, Move Laje para Central, Zera Superior
            self.u_h2.setText(f"{val_top:.2f}")
            self.u_slab_c.setText(f"{val_slab:.2f}")
            self.u_slab_t.setText("0.00")
        else:
            # Não tem H2: H2=0, Laje fica no Superior
            self.u_h2.setText("0.00")
            # self.u_slab_t já está com val_slab
            # Garante que L.Cen esteja zero (ou mantém anterior? melhor zerar para consistência)
            # self.u_slab_c.setText("0.00") # Opcional, dependendo da lógica desejada. Deixarei intacto caso tenha default.

        # --- Passo 6: Altura Geral Viga ---
        txt_beam = get_user_input("6/6: Selecione ALTURA GERAL DA VIGA (ex: 30/60)")
        val_min, val_max = parse_min_max(txt_beam)
        
        # O maior valor é a altura do bruto
        val_beam_total = val_max
        # O menor valor preenche o campo Fundo
        if val_min > 0:
            self.edt_bottom.setText(str(val_min))
        
        # Cálculo Lógico: H1 = Total - Laje(detectada) - H2(detectado)
        final_h1 = val_beam_total - val_slab - val_top
        
        # Proteção contra negativos
        if final_h1 < 0: final_h1 = 0
        
        self.u_h1.setText(f"{final_h1:.2f}")

    def action_select_names(self):
        self.showMinimized()
        self._select_names_logic()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        
    def action_select_line(self):
        self.showMinimized()
        try:
            length = self.acad_service.select_line_length()
            if length > 0:
                self.u_width.setText(f"{length:.2f}")
        except Exception as e:
            print(f"Error select line: {e}")
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def action_select_levels(self):
        self.showMinimized()
        try:
            # Service returns {'slab': float, 'beam': float, 'ceiling': float}
            res = self.acad_service.select_levels()
            
            # Use 'beam' for Beam Level, 'slab' for Opposite/Floor Level
            if res.get('beam'): self.edt_lvl_beam.setText(str(res['beam']))
            if res.get('slab'): self.edt_lvl_opp.setText(str(res['slab']))
            # if res.get('ceiling'): self.edt_pe.setText(str(res['ceiling']))
            
            # Calculate Height1 (Pe - Lvl_Beam)? or specific logic
            # If we have Beam Level and Ceiling (Pe Direito), we can calc H1.
            # But where does Pe come from? Manual or calculated?
            # Usually H1 = (Lvl_Opp + Ceiling) - Lvl_Beam ?? 
            # Or Height = Level_Beam - Level_Floor ?
            # Let's assume standard calculation:
            # H = (Beam - Slab) if both present?
            # Or usually: H1 = (Pe - (Beam - Floor))?
            
            # Logic from original Tkinter (inferred):
            # If we have both, we try to set H1.
            try:
                beam = res.get('beam', 0)
                slab = res.get('slab', 0)
                # If both valid (non-zero or diff enough)
                if beam and slab:
                     # H = Beam - Slab? 
                     diff = abs(beam - slab)
                     # Adjust
                     adj = float(self.edt_adjust.text().replace(',','.') or 0)
                     h = diff + adj
                     self.u_h1.setText(f"{h:.2f}")
            except: pass
            
        except Exception as e:
            print(f"Error select levels: {e}")
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def action_select_pillar(self):
        self.showMinimized()
        try:
            # Check active pillars from General Tab
            do_left = self.chk_prod_pil_l.isChecked()
            do_right = self.chk_prod_pil_r.isChecked()
            
            # If neither selected, assume Left by default for manual trigger
            if not do_left and not do_right:
                do_left = True

            def process_capture(side_label):
                res = self.acad_service.select_pillar_dims(prompt=f"--- CAPTURA PILAR {side_label.upper()} ---")
                return res.get('dist', 0.0), res.get('width', 0.0)

            # 1. Process Left
            if do_left:
                 d, w = process_capture("Esquerdo")
                 if d > 0 or w > 0:
                     self.pe_d.setText(f"{d:.2f}")
                     self.pe_w.setText(f"{w:.2f}")
            
            # 2. Process Right
            if do_right:
                 d, w = process_capture("Direito")
                 if d > 0 or w > 0:
                     self.pd_d.setText(f"{d:.2f}")
                     self.pd_w.setText(f"{w:.2f}")

        except Exception as e:
            print(f"Error select pillar: {e}")
            
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def action_select_opening(self):
        # Ask user which opening slot to fill
        items = ["Topo/Esq", "Fundo/Esq", "Topo/Dir", "Fundo/Dir"]
        item, ok = QInputDialog.getItem(self, "Selecionar Abertura", 
                                        "Qual abertura preencher?", items, 0, False)
        if ok and item:
            idx = items.index(item)
            self.showMinimized()
            try:
                # Service select_opening_dims returns {'w':..., 'd':...}
                self._select_names_logic_notify("Selecione o Texto da Abertura (ex: 20x60)")
                
                res = self.acad_service.select_opening_dims()
                w = res.get('w', 0.0)
                d = res.get('d', 0.0)
                
                if w > 0:
                    # self.hole_rows[idx] is (d_widget, p_widget, w_widget, chk)
                    # Mapping: depth/peitoril -> p_widget (index 1)
                    # width -> w_widget (index 2)
                    self.hole_rows[idx][1].setText(f"{d:.2f}")
                    self.hole_rows[idx][2].setText(f"{w:.2f}")
                    
            except Exception as e:
                print(f"Error select opening: {e}")
            
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def update_classes_combo(self):
        """Syncs the cmb_classes dropdown with the current pavilion's metadata."""
        if not self.current_obra or not self.current_pavimento:
            return
            
        self.cmb_classes.blockSignals(True)
        self.cmb_classes.clear()
        
        pav_data = self.project_data.get(self.current_obra, {}).get(self.current_pavimento, {})
        meta = pav_data.get('metadata', {})
        classes = meta.get('segment_classes', ["Lista Geral"])
        
        if "Lista Geral" not in classes:
            classes.insert(0, "Lista Geral")
            
        self.cmb_classes.addItems(classes)
        
        # Restore selection from current model if possible
        if hasattr(self, 'model') and self.model.segment_class in classes:
            self.cmb_classes.setCurrentText(self.model.segment_class)
        else:
            self.cmb_classes.setCurrentIndex(0)
            
        self.cmb_classes.blockSignals(False)

    def _select_names_logic_notify(self, msg):
        fl = FloatingLabel(msg)
        fl.show_msg(msg)
        QApplication.processEvents()
        # Non-blocking notification helper for manual actions
        # We don't close it explicitly here since service blocks ??
        # Or we rely on GC? 
        # Better to just show and let it float.
        pass

    def on_tree2_selection_changed(self):
        """Handles selection in the Recycling/Reuse list (tree2)."""
        if not self.chk_recycling.isChecked():
            return
            
        items = self.tree2.selectedItems()
        if not items:
            return
            
        item = items[0]
        data = item.data(0, Qt.UserRole)
        # We only care about beams, not class headers
        if not data or not isinstance(data, dict) or data.get('type') != 'beam':
            return
            
        pav = data.get('pav')
        name = data.get('nome')
        
        # Pull from project data
        vigas_dict = self.project_data.get(self.current_obra, {}).get(pav, {}).get('vigas', {})
        vstate_data = vigas_dict.get(name)
        if not vstate_data: return
        
        # Instantiate VigaState if it was stored as dict
        if isinstance(vstate_data, dict):
            try: self.recycle_model = VigaState(**vstate_data)
            except: 
                print(f"Error instantiating recycle beam {name}")
                return
        else:
            self.recycle_model = vstate_data
        
        self._ensure_panel_ids(self.recycle_model)
        
        # When changing partner, clear unsaved suggestions from the main beam 
        # as they belonged to the previous partner.
        self._clear_unsaved_suggestions(self.model)
        
        # Run comparison logic (DISABLED AUTO RUN to respect unlinked state)
        # self._run_matching_suggestion()
            
        # Populate specialized recycle table
        self._populate_panel_list_recycle()
        self._populate_panel_list() # Refresh main too to show colors
        
        # Update Preview for side-by-side comparison
        self._prepare_preview_state(self.model)
        self._prepare_preview_state(self.recycle_model)
        self.preview.draw_dual_view(self.model, self.recycle_model)

    def _populate_panel_list_recycle(self):
        """Populates the comparative table for recycling."""
        self._populate_generic_table(self.recycle_model, self.table_panels_recycle)

    def _populate_panel_list(self):
        """Populates the main table for editing."""
        self._populate_generic_table(self.model, self.table_panels)

    def _populate_generic_table(self, m, table):
        """Refactored logic to populate any panel table with a VigaState model."""
        table.setRowCount(0)
        if not m: return

        is_main = (table == self.table_panels)
        partner_model = self.recycle_model if is_main else self.model

        color_red = QColor("#B71C1C")     # Red (Not linked)
        color_green = QColor("#1B5E20")    # Green (Success)
        color_yellow = QColor("#F9A825")   # Yellow (Cuttable)

        pav_str = m.floor
        conj_str = m.segment_class if hasattr(m, 'segment_class') else "Lista Geral"
        viga_str = m.name
        def yes_no(val): return "Sim" if val else "Não"
        
        panel_end_x = 0.0
        for i, p in enumerate(m.panels):
            if p.width <= 0: continue
            
            panel_start_x = panel_end_x
            panel_end_x += p.width
            
            row_idx = table.rowCount()
            table.insertRow(row_idx)
            # Link & Color logic
            bg_color = color_red
            
            # Prepare display texts (potentially multiline)
            link_de_text = "-"
            link_em_text = "-"
            p_ids_text = p.uid
            if p.uid_h2: p_ids_text += f"\n{p.uid_h2}"

            # Decide color based on the link between current visible models (H1 priority for color)
            target_link_uid = ""
            
            # Helper to format link text
            def fmt_link(uid1, uid2, default="-"):
                if not uid1 and not uid2: return default
                parts = []
                if uid1: parts.append(uid1 + (" (S)" if p.link_saved else ""))
                else: parts.append("-")
                
                if uid2: parts.append(uid2 + (" (S)" if p.link_saved else ""))
                elif uid1: pass # don't append empty line if only H1 exists? actually better to show structure
                
                return "\n".join(parts)

            if is_main:
                link_de_text = fmt_link(p.reused_from, p.reused_from_h2, default="Novo")
                link_em_text = fmt_link(p.reused_in, p.reused_in_h2, default="Nao Reutilizado")
                # target for lookup: prioritizing H1, but fallback to H2
                target_link_uid = p.reused_from if p.reused_from else p.reused_from_h2
            else:
                link_em_text = fmt_link(p.reused_in, p.reused_in_h2, default="Nao Reutilizado")
                link_de_text = fmt_link(p.reused_from, p.reused_from_h2, default="Novo")
                target_link_uid = p.reused_in if p.reused_in else p.reused_in_h2 

            if target_link_uid:

                # Default behavior: if saved, we assume valid/exact (Blue)
                if p.link_saved: bg_color = QColor("#2196F3")
                else: bg_color = color_green
                
                # Check partner for strict color match
                partner_p = None
                if partner_model:
                    partner_list = [px for px in partner_model.panels if px.uid == target_link_uid]
                    if partner_list: partner_p = partner_list[0]
                
                if partner_p:
                    source = partner_p if is_main else p
                    target = p if is_main else partner_p
                    
                    sw = self._safe_float(source.width)
                    tw = self._safe_float(target.width)
                    h1_s = self._safe_float(source.height1)
                    h1_t = self._safe_float(target.height1)
                    h2_s = self._safe_float(source.height2)
                    h2_t = self._safe_float(target.height2)

                    # Determine if it is an exact match
                    is_exact = (abs(sw - tw) < 0.01 and abs(h1_s - h1_t) < 0.01 and abs(h2_s - h2_t) < 0.01)

                    if p.link_saved:
                        # Saved: Blue (Exact) or Orange (Cut)
                        if is_exact: bg_color = QColor("#2196F3") 
                        else: bg_color = QColor("#FF9800") 
                    else:
                        # Suggestion: Green (Exact) or Yellow (Cut)
                        if is_exact: bg_color = color_green
                        else: bg_color = color_yellow
                    # Partner not found in current visible model, but link exists.
                    # If saved, keep it blue (Assume it's in another viga)
                    if p.link_saved: bg_color = QColor("#2196F3")
            else:
                pass
            # --- 0: Reap. De, 1: Reap. Em, 2: ID ---
            item_de = QTableWidgetItem(link_de_text)
            item_de.setBackground(bg_color)
            table.setItem(row_idx, 0, item_de)
            
            item_em = QTableWidgetItem(link_em_text)
            item_em.setBackground(bg_color)
            table.setItem(row_idx, 1, item_em)
            
            item_id = QTableWidgetItem(p_ids_text)
            item_id.setBackground(bg_color)
            table.setItem(row_idx, 2, item_id)
            
            # --- Basic Info (Shifted +1) ---
            item_pav = QTableWidgetItem(pav_str)
            item_pav.setBackground(QColor("#5C6BC0"))
            item_pav.setForeground(Qt.white)
            item_pav.setTextAlignment(Qt.AlignCenter)
            item_pav.setFlags(item_pav.flags() & ~Qt.ItemIsEditable)
            
            table.setItem(row_idx, 3, item_pav)
            table.setItem(row_idx, 4, QTableWidgetItem(conj_str))
            table.setItem(row_idx, 5, QTableWidgetItem(viga_str))
            table.setItem(row_idx, 6, QTableWidgetItem(f"{i+1}"))
            
            h1_str = str(p.height1) if p.height1 else "0"
            h2_val = self._safe_float(p.height2)
            dim_val = f"{p.width:.1f}x{h1_str}"
            if h2_val > 0: dim_val += f"/{p.height2}"
            
            table.setItem(row_idx, 7, QTableWidgetItem(dim_val))
            
            # --- Reap Info (8,9,10) ---
            r_pav = ""; r_conj = ""; r_viga = ""
            
            # Lookup basic info about the linked partner from project_data if possible
            # We search based on UID
            if target_link_uid:
                found = False
                # Optimization: check partner_model first if available
                if partner_model:
                     for px in partner_model.panels:
                         if px.uid == target_link_uid:
                             r_pav = partner_model.floor
                             r_conj = partner_model.segment_class
                             r_viga = f"{partner_model.name}"
                             found = True
                             break
                
                # If not found (or different beam), search project_data
                if not found:
                    for obra_key, obra_val in self.project_data.items():
                        for pav_key, pav_val in obra_val.items():
                            vigas_dict = pav_val.get('vigas', {})
                            for vpk, vpv in vigas_dict.items():
                                # vpv can be VigaState or dict
                                panels_list = []
                                v_floor = pav_key
                                v_class = "Lista Geral"
                                
                                if isinstance(vpv, dict):
                                    panels_list = vpv.get('panels', [])
                                    v_class = vpv.get('segment_class', "Lista Geral")
                                    # vpv might not have explicit panels objects, just dicts
                                elif hasattr(vpv, 'panels'):
                                    panels_list = vpv.panels
                                    v_class = getattr(vpv, 'segment_class', "Lista Geral")
                                    
                                for p_idx, p_item in enumerate(panels_list):
                                    # Check UID
                                    p_uid = ""
                                    p_uid_h2 = ""
                                    if isinstance(p_item, dict): 
                                        p_uid = p_item.get('uid', "")
                                        p_uid_h2 = p_item.get('uid_h2', "")
                                    else: 
                                        p_uid = p_item.uid
                                        p_uid_h2 = p_item.uid_h2
                                    
                                    # Check match against H1 or H2
                                    if p_uid == target_link_uid or (p_uid_h2 and p_uid_h2 == target_link_uid):
                                        r_pav = v_floor
                                        r_conj = v_class
                                        r_viga = f"{vpk}"
                                        found = True
                                        break
                                if found: break
                            if found: break
                        if found: break
            
            table.setItem(row_idx, 8, QTableWidgetItem(r_pav))
            table.setItem(row_idx, 9, QTableWidgetItem(r_conj))
            table.setItem(row_idx, 10, QTableWidgetItem(r_viga))
            
            # --- Sarrafo/Tipo (11,12,13) ---
            table.setItem(row_idx, 11, QTableWidgetItem(yes_no(p.slab_top > 0 or p.slab_center > 0)))
            table.setItem(row_idx, 12, QTableWidgetItem(yes_no(p.slab_bottom > 0 or p.slab_center > 0)))
            table.setItem(row_idx, 13, QTableWidgetItem(p.type1))
            
            # --- Aberturas (14,15) ---
            h_l = []; h_r = []
            for h_idx, h in enumerate(m.holes):
                if h.width <= 0: continue
                if panel_start_x <= h.dist < panel_end_x:
                    label = "Topo" if h_idx in [0,2] else "Fundo"
                    if h_idx in [0,1]: h_l.append(f"{label}:{h.depth:.0f}x{h.width:.0f}")
                    else: h_r.append(f"{label}:{h.depth:.0f}x{h.width:.0f}")
            
            table.setItem(row_idx, 14, QTableWidgetItem(", ".join(h_l) if h_l else "-"))
            table.setItem(row_idx, 15, QTableWidgetItem(", ".join(h_r) if h_r else "-"))
            
            # --- 16: Pilar ---
            pil_parts = []
            if m.pillar_left.width > 0:
                if max(panel_start_x, m.pillar_left.dist) < min(panel_end_x, m.pillar_left.dist + m.pillar_left.width):
                    pil_parts.append(f"Esq (D:{m.pillar_left.dist:.0f}, W:{m.pillar_left.width:.0f})")
            if m.pillar_right.width > 0:
                if max(panel_start_x, m.pillar_right.dist) < min(panel_end_x, m.pillar_right.dist + m.pillar_right.width):
                    pil_parts.append(f"Dir (D:{m.pillar_right.dist:.0f}, W:{m.pillar_right.width:.0f})")
            table.setItem(row_idx, 16, QTableWidgetItem(", ".join(pil_parts) if pil_parts else "-"))

            # Apply Row Background
            for c_idx in range(table.columnCount()):
                it = table.item(row_idx, c_idx)
                if it:
                    it.setBackground(bg_color)
                    it.setForeground(Qt.white)

        table.resizeColumnsToContents()

    def _clear_unsaved_suggestions(self, model):
        """Removes all Green/Yellow links (suggestions) from the model while preserving Saved links."""
        if not model: return
        for p in model.panels:
            if not p.link_saved:
                p.reused_from = ""
                p.reused_from_h2 = ""
                p.reused_in = ""
                p.reused_in_h2 = ""
                # Also reset tags related to suggestions in _preview_tag_text if needed, 
                # but _prepare_preview_state will handle it during the next redraw.
        
    def _run_matching_suggestion(self):
        """Analyzes both beams to find best recycling matches (Verde/Amarelo)."""
        if not self.model or not self.recycle_model: return
        
        # 1. Clear non-saved links
        for p in self.model.panels:
            if not p.link_saved: 
                if p.reused_from:
                    print(f"DEBUG_CLEAR: Clearing reused_from for UN-SAVED panel {p.uid}")
                p.reused_from = ""
                # reused_in might came from another comparison, we only clear what we are analyzing here (incoming)
        for p in self.recycle_model.panels:
            if not p.link_saved:
                p.reused_in = ""

        # 2. Match Verde (Identical) - p1 is target (Edition), p2 is source (Recycle)
        print("DEBUG_MATCH: Starting Green Match")
        for p1 in self.model.panels:
            # Clear conflicting direction for current suggestion context (Top should only consume)
            # if not p1.link_saved: p1.reused_in = "" # OPTIONAL: force clear reverse logic? logic says p1 is consumer.
            
            if p1.width <= 0 or p1.reused_from: continue
            for p2 in self.recycle_model.panels:
                if p2.width <= 0 or p2.reused_in: continue
                
                # Robust numeric comparison for dimensions
                w1 = self._safe_float(p1.width); w2 = self._safe_float(p2.width)
                h1_1 = self._safe_float(p1.height1); h1_2 = self._safe_float(p2.height1)
                h2_1 = self._safe_float(p1.height2); h2_2 = self._safe_float(p2.height2)
                
                if w1 == w2 and h1_1 == h1_2 and h2_1 == h2_2:
                    print(f"DEBUG_MATCH: GREEN HIT! Target={p1.uid} gets FROM={p2.uid} | Source={p2.uid} gets IN={p1.uid}")
                    p1.reused_from = p2.uid
                    p2.reused_in = p1.uid
                    
                    # Link H2 if exists
                    if h2_1 > 0 and p1.uid_h2 and p2.uid_h2:
                         p1.reused_from_h2 = p2.uid_h2
                         p2.reused_in_h2 = p1.uid_h2
                         
                    p1.link_saved = False 
                    break

        # 3. Match Amarelo (Cuttable)
        print("DEBUG_MATCH: Starting Yellow Match")
        for p1 in self.model.panels:
            if p1.width <= 0 or p1.reused_from: continue
            for p2 in self.recycle_model.panels:
                if p2.width <= 0 or p2.reused_in: continue
                
                # Robust numeric comparison
                w1 = self._safe_float(p1.width); w2 = self._safe_float(p2.width)
                h1_1 = self._safe_float(p1.height1); h1_2 = self._safe_float(p2.height1)
                h2_1 = self._safe_float(p1.height2); h2_2 = self._safe_float(p2.height2)
                
                # Amarelo: source (p2) is larger or equal
                if w2 >= w1 and h1_2 >= h1_1 and (h2_2 >= h2_1 or h2_1 == 0):
                    print(f"DEBUG_MATCH: YELLOW HIT! Target={p1.uid} gets FROM={p2.uid} | Source={p2.uid} gets IN={p1.uid}")
                    p1.reused_from = p2.uid
                    p2.reused_in = p1.uid
                    
                    # Link H2 if possible
                    if h2_1 > 0 and h2_2 >= h2_1 and p1.uid_h2 and p2.uid_h2:
                        p1.reused_from_h2 = p2.uid_h2
                        p2.reused_in_h2 = p1.uid_h2

                    p1.link_saved = False
                    break

    def _get_panel_at_row(self, table, model):
        """Helper to get the actual VigaPanel from a table row selection."""
        row = table.currentRow()
        if row < 0: return None
        # Rows in table match active panels in model (width > 0)
        active_panels = [p for p in model.panels if p.width > 0]
        if row < len(active_panels):
            return active_panels[row]
        return None

    def link_selected_verde(self):
        p1 = self._get_panel_at_row(self.table_panels, self.model) # Target (De)
        p2 = self._get_panel_at_row(self.table_panels_recycle, self.recycle_model) # Source (Para)
        if not p1 or not p2: 
            QMessageBox.warning(self, "Aviso", "Selecione exatamente 1 painel em cada tabela para vincular.")
            return
        
        if p1.width == p2.width and p1.height1 == p2.height1 and p1.height2 == p2.height2:
            p1.reused_from = p2.uid
            p2.reused_in = p1.uid
            
            # H2 Link
            if self._safe_float(p1.height2) > 0 and p1.uid_h2 and p2.uid_h2:
                p1.reused_from_h2 = p2.uid_h2
                p2.reused_in_h2 = p1.uid_h2
            
            p1.link_saved = False
            self._update_all_rec_ui()
        else:
            QMessageBox.warning(self, "Aviso", "Painéis não são idênticos (Verde).")

    def link_selected_amarelo(self):
        p1 = self._get_panel_at_row(self.table_panels, self.model)
        p2 = self._get_panel_at_row(self.table_panels_recycle, self.recycle_model)
        if not p1 or not p2: 
            QMessageBox.warning(self, "Aviso", "Selecione exatamente 1 painel em cada tabela para vincular.")
            return
        
        h1_1 = self._safe_float(p1.height1); h1_2 = self._safe_float(p2.height1)
        h2_1 = self._safe_float(p1.height2); h2_2 = self._safe_float(p2.height2)
        
        if p2.width >= p1.width and h1_2 >= h1_1 and (h2_2 >= h2_1 or h2_1 == 0):
            p1.reused_from = p2.uid
            p2.reused_in = p1.uid
            
            # H2 Link Check
            if h2_1 > 0 and h2_2 >= h2_1 and p1.uid_h2 and p2.uid_h2:
                p1.reused_from_h2 = p2.uid_h2
                p2.reused_in_h2 = p1.uid_h2

            p1.link_saved = False
            self._update_all_rec_ui()
        else:
            QMessageBox.warning(self, "Aviso", "Reaproveitante não cobre as dimensões necessárias (Amarelo).")

    def _clear_link_global(self, partner_uid, partner_h2_uid, is_source_clearing):
        """Helper to clear link on the PARTNER side globally."""
        # is_source_clearing = True means WE ARE THE SOURCE (cleared reused_in), so partner is TARGET (clear reused_from)
        # is_source_clearing = False means WE ARE THE TARGET (cleared reused_from), so partner is SOURCE (clear reused_in)
        
        field1 = 'reused_from' if is_source_clearing else 'reused_in'
        field2 = 'reused_from_h2' if is_source_clearing else 'reused_in_h2'
        
        # Search in project_data
        for obra_v in self.project_data.values():
            for pav_v in obra_v.values():
                for v_v in pav_v.get('vigas', {}).values():
                    panels = v_v.panels if hasattr(v_v, 'panels') else v_v.get('panels', [])
                    for px in panels:
                        px_uid = px.uid if hasattr(px, 'uid') else px.get('uid')
                        px_uid_h2 = px.uid_h2 if hasattr(px, 'uid_h2') else px.get('uid_h2', "")
                        
                        found_h1 = False
                        found_h2 = False
                        
                        if partner_uid and px_uid == partner_uid:
                            found_h1 = True
                        if partner_h2_uid and px_uid_h2 == partner_h2_uid:
                            found_h2 = True
                            
                        if found_h1 or found_h2:
                            if hasattr(px, 'uid'): # Object
                                if found_h1: setattr(px, field1, "")
                                if found_h2: setattr(px, field2, "")
                                px.link_saved = False
                            else: # Dict
                                if found_h1: px[field1] = ""
                                if found_h2: px[field2] = ""
                                px['link_saved'] = False

    def _clear_panel_links(self, p, is_source=False):
        """Clears links for a single panel and updates its global partner."""
        # Step 1: Handle FROM links (Incoming)
        u_f1 = p.reused_from; u_f2 = p.reused_from_h2

        if u_f1 or u_f2:
            p.reused_from = ""; p.reused_from_h2 = ""
            self._clear_link_global(u_f1, u_f2, is_source_clearing=False) # Partner is source (clear its reused_in)
            
        # Step 2: Handle IN links (Outgoing)
        u_i1 = p.reused_in; u_i2 = p.reused_in_h2
        if u_i1 or u_i2:
            p.reused_in = ""; p.reused_in_h2 = ""
            self._clear_link_global(u_i1, u_i2, is_source_clearing=True) # Partner is target (clear its reused_from)
            
        p.link_saved = False

    def _clear_panel_links_any(self, p, is_source=False):
        """Robust version of _clear_panel_links that handles both objects and dicts."""
        # Get values
        def get_v(obj, attr):
            if hasattr(obj, attr): return getattr(obj, attr)
            return obj.get(attr, "")
            
        def set_v(obj, attr, val):
            if hasattr(obj, attr): setattr(obj, attr, val)
            else: obj[attr] = val

        u_f1 = get_v(p, 'reused_from')
        u_f2 = get_v(p, 'reused_from_h2')

        if u_f1 or u_f2:
            set_v(p, 'reused_from', "")
            set_v(p, 'reused_from_h2', "")
            self._clear_link_global(u_f1, u_f2, is_source_clearing=False)
            
        u_i1 = get_v(p, 'reused_in')
        u_i2 = get_v(p, 'reused_in_h2')
        if u_i1 or u_i2:
            set_v(p, 'reused_in', "")
            set_v(p, 'reused_in_h2', "")
            self._clear_link_global(u_i1, u_i2, is_source_clearing=True)
            
        set_v(p, 'link_saved', False)



    def unlink_multiple_selected(self):
        """Unlinks all selected panels in the main table."""
        rows = set()
        for item in self.table_panels.selectedItems():
            rows.add(item.row())
            
        if not rows:
            QMessageBox.warning(self, "Aviso", "Selecione painéis na tabela principal para limpar os vínculos.")
            return

        count = 0
        for r in rows:
            # We assume panels match 1:1 with rows. 
            # We must fetch by index.
            if r < len(self.model.panels):
                p = self.model.panels[r]
                self._clear_panel_links(p, is_source=False)
                count += 1
                
        self._update_all_rec_ui()
        QMessageBox.information(self, "Sucesso", f"Vínculos removidos de {count} painéis.")

    def unlink_selected(self):
        # Determine selection type
        p1 = self._get_panel_at_row(self.table_panels, self.model)
        p2 = self._get_panel_at_row(self.table_panels_recycle, self.recycle_model)
        
        if not p1 and not p2:
            QMessageBox.warning(self, "Aviso", "Selecione um painel em uma das tabelas para desvincular.")
            return

        if p1:
            self._clear_panel_links(p1, is_source=False)
        
        if p2:
            self._clear_panel_links(p2, is_source=True)
                            
        self._update_all_rec_ui()

    def save_selected_link(self):
        p1 = self._get_panel_at_row(self.table_panels, self.model)
        p2 = self._get_panel_at_row(self.table_panels_recycle, self.recycle_model)
        
        if not p1 or not p2:
            QMessageBox.warning(self, "Aviso", "Selecione exatamente 1 painel em cada tabela para salvar o vínculo.")
            return

        # Ensure UIDs exist before linking (Vital for persistence)
        self._ensure_panel_ids(self.model)
        self._ensure_panel_ids(self.recycle_model)

        # Force link establishment and save
        # This addresses user request to ensure both columns are saved/updated
        p1.reused_from = p2.uid
        p1.reused_in = "" # Clean inverse to maintain strict directionality
        
        p2.reused_in = p1.uid
        p2.reused_from = "" # Clean inverse to maintain strict directionality

        
        # Check H2 compatibility optimistically
        have_h2_1 = self._safe_float(p1.height2) > 0
        have_h2_2 = self._safe_float(p2.height2) > 0
        if have_h2_1 and have_h2_2 and p1.uid_h2 and p2.uid_h2:
            p1.reused_from_h2 = p2.uid_h2
            p2.reused_in_h2 = p1.uid_h2
        
        p1.link_saved = True
        p2.link_saved = True
        
        print(f"DEBUG_SAVE: Linked {p1.uid} (FROM) <-> {p2.uid} (IN)")
        print(f"DEBUG_SAVE: P1 State: FROM={p1.reused_from} SAVED={p1.link_saved}")
        
        self._update_all_rec_ui()

    def action_reuse_sets(self):
        """
        Reaproveita conjuntos de vigas iguais entre pavimentos selecionados.
        Green: Name match priority, then class match (Exact).
        Yellow: Name match priority, then class match (Best fit - Largest Target vs Smallest Valid Source).
        """
        if not self.chk_recycling.isChecked(): return
        
        target_pav = self.cmb_pav.currentText()
        source_pav = self.cmb_filter2.currentText()
        if not target_pav or not source_pav: return
        
        self._sync_models_to_project()

        # 0. Clear existing suggestions (non-saved links) to allow re-matching
        # This is CRITICAL because the 'active' beam in the UI usually has a suggestion 
        # that blocks it from being re-processed in this bulk pass.
        for pav in [target_pav, source_pav]:
            pav_content = self.project_data[self.current_obra].get(pav, {})
            vigas = pav_content.get('vigas', {})
            for vstate in vigas.values():
                panels = getattr(vstate, 'panels', []) if not isinstance(vstate, dict) else vstate.get('panels', [])
                for p in panels:
                    if not self._get_p_attr(p, 'link_saved'):
                        # Clear both directions to be safe and avoid orphan references
                        self._set_p_attr(p, 'reused_from', "")
                        self._set_p_attr(p, 'reused_from_h2', "")
                        self._set_p_attr(p, 'reused_in', "")
                        self._set_p_attr(p, 'reused_in_h2', "")

        # 1. Collect Panels by Class
        targets_dict = self._collect_panels_by_class(self.current_obra, target_pav)
        sources_dict = self._collect_panels_by_class(self.current_obra, source_pav)
        
        total_links = 0
        
        # Iterate Common Classes
        common_classes = set(targets_dict.keys()) & set(sources_dict.keys())
        
        for cls_name in common_classes:
            tgt_list = targets_dict.get(cls_name, [])
            src_list = sources_dict.get(cls_name, [])
            
            if not tgt_list or not src_list: continue
            
            # Phase 1: Green (Exact) - Same Name Only
            count, _ = self._reuse_phase_logic(tgt_list, src_list, mode='green', same_name_only=True)
            if count > 0:
                # print(f"TRACE_REUSE_SETS: Class {cls_name} - Green SameName: {count}")
                total_links += count
                
            # Phase 2: Yellow (Cut) - Same Name Only
            count, _ = self._reuse_phase_logic(tgt_list, src_list, mode='yellow', same_name_only=True)
            if count > 0:
                # print(f"TRACE_REUSE_SETS: Class {cls_name} - Yellow SameName: {count}")
                total_links += count
            
        self._refresh_after_bulk_operation()
        
        msg = f"Processo 'Conjuntos' concluído! {total_links} novos vínculos criados (Apenas mesmo nome)."
        if total_links == 0:
            msg += "\n\nNenhuma correspondência exata de nome encontrada com dimensões compatíveis."
        QMessageBox.information(self, "Resultado", msg)

    def action_clear_pav_links(self):
        """Limpamos TODOS os vínculos de reaproveitamento do pavimento selecionado."""
        obra = self.cmb_obra.currentText()
        pav = self.cmb_pav.currentText()
        if not obra or not pav:
            QMessageBox.warning(self, "Aviso", "Selecione uma Obra e um Pavimento primeiro.")
            return

        msg = f"Deseja realmente LIMPAR TODOS os vínculos de reaproveitamento do pavimento '{pav}'?\nIsso removerá as associações em ambas as direções.\n\nEsta ação não pode ser desfeita."
        ret = QMessageBox.question(self, "Limpar Vínculos", msg, QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return

        # 1. Garante que o que está na tela/memória está sincronizado
        self._sync_models_to_project()

        # 2. Busca o dicionário de vigas do pavimento
        pav_data = self.project_data.get(obra, {}).get(pav, {})
        vigas_dict = pav_data.get('vigas', {})

        if not vigas_dict:
            QMessageBox.information(self, "Aviso", "Não há vigas cadastradas neste pavimento.")
            return

        # 3. Itera limpando
        for vname, vstate_obj in vigas_dict.items():
            # vstate_obj pode ser VigaState ou dict
            panels = []
            if hasattr(vstate_obj, 'panels'): panels = vstate_obj.panels
            elif isinstance(vstate_obj, dict): panels = vstate_obj.get('panels', [])
            
            for p in panels:
                self._clear_panel_links_any(p)

        # 4. Atualiza tudo
        self.save_session_data() # Persiste a limpeza no disco
        self._refresh_after_bulk_operation()
        self._update_all_rec_ui()
        
        # Se a viga atual estiver nesse pavimento, recalcula o preview
        if self.model and self.model.floor == pav:
             self.update_model()
             
        QMessageBox.information(self, "Limpeza Concluída", f"Todos os vínculos de reaproveitamento das {len(vigas_dict)} vigas de '{pav}' foram removidos.")


    def action_reuse_all(self):
        """
        Reaproveita o restante dos painéis (Global Match), sem restringir por nome da viga.
        """
        if not self.chk_recycling.isChecked(): return
        
        target_pav = self.cmb_pav.currentText()
        source_pav = self.cmb_filter2.currentText()
        # print(f"TRACE_REUSE_ALL: Target='{target_pav}', Source='{source_pav}'")
        
        if not target_pav or not source_pav: return
        
        self._sync_models_to_project()

        # Clear unsaved suggestions to prevent conflicts
        self._clear_suggestions_globally(target_pav, source_pav)

        # 1. Collect Panels (Grouped by Class initially)
        targets_dict = self._collect_panels_by_class(self.current_obra, target_pav)
        sources_dict = self._collect_panels_by_class(self.current_obra, source_pav)
        
        # Flatten structure: We want to match ANY remaining target against ANY remaining source
        # The geometric checks (H1, H2, Width) in _reuse_phase_logic will ensure validity
        all_targets = []
        for v_list in targets_dict.values():
            all_targets.extend(v_list)
            
        all_sources = []
        for v_list in sources_dict.values():
            all_sources.extend(v_list)
            
        total_links = 0
        
        # print(f"TRACE_REUSE_ALL: Flattened -> Targets: {len(all_targets)}, Sources: {len(all_sources)}")

        if all_targets and all_sources:
            # --- PHASE 1: GREEN GLOBAL ---
            count_g, stats_g = self._reuse_phase_logic(all_targets, all_sources, mode='green', same_name_only=False)
            if count_g > 0: pass # print(f"TRACE_REUSE_ALL: Green Global Links: {count_g}")
            
            # --- PHASE 2: YELLOW GLOBAL ---
            count_y, stats_y = self._reuse_phase_logic(all_targets, all_sources, mode='yellow', same_name_only=False)
            if count_y > 0: pass # print(f"TRACE_REUSE_ALL: Yellow Global Links: {count_y}")
            
            total_links += count_g + count_y
            
            # Merge stats for reporting if needed
            fails = {**stats_g, **stats_y}

    def action_reuse_selected_vigas(self):
        """
        Reaproveita apenas as vigas que estão selecionadas na Tree1 (Lista principal).
        Tenta primeiro Identicos (Green) e depois Cortes (Yellow).
        O pavimento fonte é o selecionado na lista debaixo (cmb_filter2).
        """
        if not self.chk_recycling.isChecked(): return
        
        target_pav = self.cmb_pav.currentText()
        source_pav = self.cmb_filter2.currentText()
        
        if not target_pav or not source_pav:
            QMessageBox.warning(self, "Aviso", "Selecione o pavimento alvo e o pavimento fonte.")
            return

        # 1. Obter vigas selecionadas
        selected_items = self.tree1.selectedItems()
        target_viga_names = []
        for item in selected_items:
            data = item.data(0, Qt.UserRole)
            if data and isinstance(data, dict) and data.get('type') == 'beam':
                name = data.get('key')
                if name: target_viga_names.append(name)

        if not target_viga_names:
            QMessageBox.warning(self, "Aviso", "Selecione ao menos uma viga na lista de vigas (superior) para reaproveitar.")
            return

        confirm = QMessageBox.question(self, "Reaproveitar Selecionadas", 
                                     f"Deseja reaproveitar as {len(target_viga_names)} vigas selecionadas?\n"
                                     f"Fonte: {source_pav}\nAlvo: {target_pav}",
                                     QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes: return

        # 2. Sync Current
        self._sync_models_to_project()

        # 3. Coletar dados do alvo (apenas selecionadas) e fonte (todas)
        targets_dict = self._collect_panels_by_class(self.current_obra, target_pav)
        sources_dict = self._collect_panels_by_class(self.current_obra, source_pav)

        # Filtrar targets para apenas as vigas selecionadas
        selected_targets = []
        for class_name, v_list in targets_dict.items():
            for entry in v_list:
                if entry['viga'] in target_viga_names:
                    selected_targets.append(entry)

        # Flatten sources (podemos reaproveitar de qualquer classe do pavimento fonte)
        all_sources = []
        for v_list in sources_dict.values():
            all_sources.extend(v_list)

        if not selected_targets:
            QMessageBox.warning(self, "Aviso", "Não foram encontrados painéis nas vigas selecionadas.")
            return
            
        if not all_sources:
            QMessageBox.warning(self, "Aviso", f"Não há painéis disponíveis no pavimento fonte '{source_pav}'.")
            return

        # 4. Executar Lógica
        # Passo 1: Identicos (Green) - Global (ignorando classe/nome, focado em geometria)
        count_g, _ = self._reuse_phase_logic(selected_targets, all_sources, mode='green', same_name_only=False)
        
        # Passo 2: Diferentes Menores (Yellow/Cortes)
        count_y, _ = self._reuse_phase_logic(selected_targets, all_sources, mode='yellow', same_name_only=False)

        # 5. Finalizar
        self._refresh_after_bulk_operation()
        self._update_all_rec_ui()
        
        QMessageBox.information(self, "Concluído", 
                                f"Reaproveitamento das vigas selecionadas concluído!\n"
                                f"Vínculos Verdes: {count_g}\nVínculos Amarelos: {count_y}")
 # simple merge, not perfect additive but gives idea

        self._refresh_after_bulk_operation()
        
        msg = f"Processo 'Todos' concluído! {total_links} novos vínculos criados (Global Irrestrito)."
        if total_links == 0:
            # Generate detailed report
            msg += "\n\nNenhum vínculo criado.\n\nMotivos Prováveis (Com base na geometria):"
            if 'fail_height' in fails and fails['fail_height'] > 0:
                msg += f"\n- {fails['fail_height']} testes falharam por Altura (H Source < H Target)."
            if 'fail_width' in fails and fails['fail_width'] > 0:
                msg += f"\n- {fails['fail_width']} testes falharam por Largura (W Source < W Target)."
                
            msg += "\n\nVerifique se o pavimento de 'Origem' (Lista 2) possui peças maiores que o 'Destino' (Lista 1)."
            
        QMessageBox.information(self, "Resultado", msg)

    def _clear_suggestions_globally(self, target_pav, source_pav):
        for pav in [target_pav, source_pav]:
            pav_content = self.project_data[self.current_obra].get(pav, {})
            vigas = pav_content.get('vigas', {})
            for vstate in vigas.values():
                panels = getattr(vstate, 'panels', []) if not isinstance(vstate, dict) else vstate.get('panels', [])
                for p in panels:
                    if not self._get_p_attr(p, 'link_saved'):
                        self._set_p_attr(p, 'reused_from', "")
                        self._set_p_attr(p, 'reused_from_h2', "")
                        self._set_p_attr(p, 'reused_in', "")
                        self._set_p_attr(p, 'reused_in_h2', "")

    def _collect_panels_by_class(self, obra, pav):
        """Returns dict {class_name: [{'viga': name, 'panel': p, 'idx': i}, ...]}"""
        # print(f"TRACE_COLLECT: Obra='{obra}', Pav='{pav}'")
        res = {}
        if obra not in self.project_data: 
            # print("TRACE_COLLECT: Obra not found in project_data")
            return res
        if pav not in self.project_data[obra]:
            # print(f"TRACE_COLLECT: Pav '{pav}' not found in project_data[{obra}]")
            return res
        
        vigas = self.project_data[obra][pav].get('vigas', {})
        # print(f"TRACE_COLLECT: Found {len(vigas)} vigas in {pav}")
        
        for vname, vdata in vigas.items():
            # Get Class
            v_class = getattr(vdata, 'segment_class', "Lista Geral") if not isinstance(vdata, dict) else vdata.get('segment_class', "Lista Geral")
            if not v_class: v_class = "Lista Geral"
            
            panels = getattr(vdata, 'panels', []) if not isinstance(vdata, dict) else vdata.get('panels', [])
            
            if v_class not in res: res[v_class] = []
            
            for i, p in enumerate(panels):
                # Only include available panels (target: not reused_from, source: not reused_in)
                # Actually we filter usage inside the matching logic to have fresh state
                res[v_class].append({'viga': vname, 'panel': p, 'idx': i})
        return res

    def _get_p_attr(self, p, attr, default=None):
        if isinstance(p, dict): return p.get(attr, default)
        return getattr(p, attr, default)

    def _set_p_attr(self, p, attr, value):
        if isinstance(p, dict): p[attr] = value
        else: setattr(p, attr, value)

    def _reuse_phase_logic(self, targets, sources, mode, same_name_only):
        count = 0
        stats = {'fail_height': 0, 'fail_width': 0}
        
        # Filter Unlinked Candidates
        # Targets: Need Reused_From empty
        # Sources: Need Reused_In empty
        # Filter Unlinked Candidates
        valid_targets = []
        for t in targets:
            if not self._get_p_attr(t['panel'], 'reused_from'):
                valid_targets.append(t)
                
        valid_sources = []
        skipped_source_count = 0
        for s in sources:
            if not self._get_p_attr(s['panel'], 'reused_in'):
                valid_sources.append(s)
            else:
                skipped_source_count += 1
                
        # print(f"TRACE_LOGIC: Mode={mode} | Valid Targets={len(valid_targets)} | Valid Sources={len(valid_sources)} | Skipped Sources (Already Used)={skipped_source_count}")
        
        if mode == 'yellow' and not same_name_only:
            # OPTIMIZATION: Process Largest Targets First
            # Sort valid_targets by Area Descending (W * H1) - ignoring H2 for simplicity or sum
            valid_targets.sort(key=lambda x: self._safe_float(self._get_p_attr(x['panel'], 'width')) * 
                                             self._safe_float(self._get_p_attr(x['panel'], 'height1')), reverse=True)
            
            # Sources: We will pick Best Fit (Smallest valid source) on the fly
        
        for tgt in valid_targets:
            tp = tgt['panel']
            if self._get_p_attr(tp, 'reused_from'): continue # Already linked in this pass
            
            # Dimensions
            tw = self._safe_float(self._get_p_attr(tp, 'width'))
            th1 = self._safe_float(self._get_p_attr(tp, 'height1'))
            th2 = self._safe_float(self._get_p_attr(tp, 'height2'))
            
            best_src = None
            best_waste = float('inf')
            
            # Search Sources
            # If optimizing yellow global, we search ALL sources for best fit.
            # Else (Green or SameName), first match is fine usually, or best fit for Green?? Green is exact, so any match is equal.
            
            candidate_sources = valid_sources
            if same_name_only:
                candidate_sources = [s for s in valid_sources if s['viga'] == tgt['viga']]
                
            for src in candidate_sources:
                sp = src['panel']
                if self._get_p_attr(sp, 'reused_in'): continue
                
                sw = self._safe_float(self._get_p_attr(sp, 'width'))
                sh1 = self._safe_float(self._get_p_attr(sp, 'height1'))
                sh2 = self._safe_float(self._get_p_attr(sp, 'height2'))
                
                s_name = f"{src['viga']}-{self._get_p_attr(sp, 'uid', '??')}"
                t_name = f"{tgt['viga']}-{self._get_p_attr(tp, 'uid', '??')}"

                # print(f"TRACE_CMP: {t_name}({tw:.1f}x{th1:.1f}) vs {s_name}({sw:.1f}x{sh1:.1f})")
                
                match = False
                if mode == 'green':
                    # Exact Match
                    if abs(sw - tw) < 0.01 and abs(sh1 - th1) < 0.01 and abs(sh2 - th2) < 0.01:
                        match = True
                else:
                    # Yellow Match (Source >= Target)
                    # H2 Logic: If target H2=0, source H2 can be anything (cut). If Target H2>0, Source H2 >= Target H2.
                    h2_ok = (sh2 >= th2) if th2 > 0 else True
                    if sw >= tw and sh1 >= th1 and h2_ok:
                        match = True
                    else:
                        if sh1 < th1: stats['fail_height'] += 1
                        elif sw < tw: stats['fail_width'] += 1
                        
                if match:
                    if mode == 'green':
                        best_src = src
                        break # Take first green
                    else:
                        # Yellow Best Fit: Minimize Area Waste
                        src_area = sw * (sh1 + sh2)
                        tgt_area = tw * (th1 + th2)
                        waste = src_area - tgt_area
                        if waste < best_waste:
                            best_waste = waste
                            best_src = src
            
            # Execute Link if found
            if best_src:
                sp = best_src['panel']
                
                # UIDs
                t_uid = self._get_p_attr(tp, 'uid')
                t_uid_h2 = self._get_p_attr(tp, 'uid_h2')
                s_uid = self._get_p_attr(sp, 'uid')
                s_uid_h2 = self._get_p_attr(sp, 'uid_h2')
                
                self._set_p_attr(tp, 'reused_from', s_uid)
                self._set_p_attr(sp, 'reused_in', t_uid)
                
                # Link H2 if possible
                if t_uid_h2 and s_uid_h2:
                    # Check H2 compatibility numeric again to be sure
                    try:
                        vh2_t = float(str(self._get_p_attr(tp, 'height2')).replace(',','.'))
                        vh2_s = float(str(self._get_p_attr(sp, 'height2')).replace(',','.'))
                    except: vh2_t=0; vh2_s=0
                    
                    if vh2_t > 0 and vh2_s >= vh2_t:
                        self._set_p_attr(tp, 'reused_from_h2', s_uid_h2)
                        self._set_p_attr(sp, 'reused_in_h2', t_uid_h2)
                
                self._set_p_attr(tp, 'link_saved', True)
                self._set_p_attr(sp, 'link_saved', True)
                
                count += 1
                
        return count, stats

    def save_links_by_type(self, check_type='green'):
        if not self.model or not self.recycle_model: return
        
        for p1 in self.model.panels:
            if p1.reused_from:
                # Find partner
                p2 = None
                for px in self.recycle_model.panels:
                    if px.uid == p1.reused_from:
                        p2 = px
                        break
                
                if p2:
                    # Classify current link
                    w1 = self._safe_float(p1.width); w2 = self._safe_float(p2.width)
                    h1_1 = self._safe_float(p1.height1); h1_2 = self._safe_float(p2.height1)
                    h2_1 = self._safe_float(p1.height2); h2_2 = self._safe_float(p2.height2)
                    
                    is_green = (w1 == w2 and h1_1 == h1_2 and h2_1 == h2_2)
                    
                    should_save = False
                    if check_type == 'green' and is_green:
                        should_save = True
                    elif check_type == 'yellow' and not is_green:
                        # Check if actually yellow (valid cut) or just random mismatch
                        # Yellow: p2 >= p1
                        if w2 >= w1 and h1_2 >= h1_1 and (h2_2 >= h2_1 or h2_1 == 0):
                            should_save = True
                            
                    if should_save:
                        # Ensure H2 link is established if possible before saving, similar to save_selected
                        if h2_1 > 0 and p1.uid_h2 and p2.uid_h2:
                             # Check if H2 match allows linking
                             if check_type == 'green' and h2_1 == h2_2:
                                 p1.reused_from_h2 = p2.uid_h2
                                 p2.reused_in_h2 = p1.uid_h2
                             elif check_type == 'yellow' and h2_2 >= h2_1:
                                 p1.reused_from_h2 = p2.uid_h2
                                 p2.reused_in_h2 = p1.uid_h2
                        
                        p1.link_saved = True
                        p2.link_saved = True
                        
        self._update_all_rec_ui()

    def _update_all_rec_ui(self):
        # Vital: Sync current in-memory models back to project_data before saving
        self._sync_models_to_project()
        
        self._populate_panel_list()
        self._populate_panel_list_recycle()
        self.update_vigas_list() # Ensure sidebar is in sync with possible name changes
        self.save_session_data() # Auto-persist the links
        
        # Redraw Canvas to show visual changes
        if hasattr(self, 'preview'):
            self._prepare_preview_state(self.model)
            if self.chk_recycling.isChecked() and self.recycle_model:
                self._prepare_preview_state(self.recycle_model)
                self.preview.draw_dual_view(self.model, self.recycle_model)
            else:
                self.preview.draw(self.model)

    def _refresh_after_bulk_operation(self):
        """Refreshes UI from Project Data (Disk/Memory) instead of overwriting it with Stale State."""
        self.save_session_data() # Ensure modifications are saved to disk
        
        self.update_vigas_list()
        
        # 2. Reload Main Beam (if active)
        if hasattr(self, 'current_beam_name') and self.current_beam_name:
            self.load_beam_view(self.current_beam_name)
            
        # 3. Reload Recycle Beam (if active and selected)
        if self.chk_recycling.isChecked() and self.tree2.selectedItems():
            self.on_tree2_selection_changed()

    def _sync_models_to_project(self):
        """Writes self.model and self.recycle_model back to self.project_data to ensure persistence."""
        if self.current_obra and self.model:
            # Save Main Model
            self._ensure_panel_ids(self.model) # Ensure IDs are current before saving
            pav = self.model.floor
            name = self.model.name
            if pav in self.project_data.get(self.current_obra, {}):
                self.project_data[self.current_obra][pav]['vigas'][name] = self.model
        
        if self.current_obra and self.recycle_model:
            # Save Recycle Model
            self._ensure_panel_ids(self.recycle_model) # Ensure IDs are current before saving
            pav_r = self.recycle_model.floor
            name_r = self.recycle_model.name
            if pav_r in self.project_data.get(self.current_obra, {}):
                self.project_data[self.current_obra][pav_r]['vigas'][name_r] = self.recycle_model

    def _sanitize_for_id(self, text):
        if not text: return "X"
        # Remove special chars and keep uppercase alphanumeric
        result = re.sub(r'[^A-Z0-9]', '', str(text).upper())
        return result if result else "X"

    def _ensure_panel_ids(self, state):
        """Guarantees every panel in the state has a unique ID following Obra-Pav-Classe-Viga-Pn."""
        if not state: return
        
        s_obra = self._sanitize_for_id(self.current_obra)
        s_pav = self._sanitize_for_id(state.floor)
        s_classe = self._sanitize_for_id(state.segment_class)
        s_viga = self._sanitize_for_id(state.name)
        
        for i, p in enumerate(state.panels):
            # Base logic: OBRA-PAV-CLASSE-VIGA-PN
            base = f"{s_obra}-{s_pav}-{s_classe}-{s_viga}-P{i+1}"
            
            # Enforce format PnH1
            if not p.uid or "-H1" not in p.uid:
                p.uid = f"{base}-H1"
            
            # Enforce H2 if val > 0
            val_h2 = self._safe_float(p.height2)
            if val_h2 > 0:
                p.uid_h2 = f"{base}-H2"
            else:
                p.uid_h2 = ""

    def migrate_all_panel_ids(self):
        """Fills missing IDs for all panels in the entire project data using the new structured pattern."""
        print("Migrating panel IDs...")
        for obra_name, pavs in self.project_data.items():
            s_obra = self._sanitize_for_id(obra_name)
            for pav_name, content in pavs.items():
                s_pav = self._sanitize_for_id(pav_name)
                vigas = content.get('vigas', {})
                for vname, vstate_raw in vigas.items():
                    # Handle both dicts and objects
                    if isinstance(vstate_raw, dict):
                        cls = self._sanitize_for_id(vstate_raw.get('segment_class', 'LG'))
                        v_id_name = self._sanitize_for_id(vstate_raw.get('name', vname))
                        panels = vstate_raw.get('panels', [])
                        for i, p in enumerate(panels):
                            if not p.get('uid'):
                                p['uid'] = f"{s_obra}-{s_pav}-{cls}-{v_id_name}-P{i+1}"
                    else:
                        # VigaState object
                        self._ensure_panel_ids(vstate_raw)
        print("Migration complete.")

    def prepare_continuation(self):
        """Prepara o sistema para capturar o próximo segmento da mesma viga avançando para o próximo número inteiro."""
        try:
            # Usuário solicitou que tanto próxima viga quanto próximo segmento avancem um número inteiro (sem frações)
            new_num = self.get_next_number()
            
            self.reset_fundo()
            self.edt_num.setText(new_num)
            self.action_select_names()
        except Exception as e:
            print(f"Error prepare_continuation: {e}")

    def get_next_number(self):
        """Calcula o próximo número inteiro base disponível no pavimento atual buscando o primeiro vácuo (Gap Filling)."""
        used_numbers = set()
        
        if not self.current_obra or not self.current_pavimento:
            return "1"

        try:
            pav_data = self.project_data.get(self.current_obra, {}).get(self.current_pavimento, {})
            vigas = pav_data.get('vigas', {})
            
            # 1. Coletar números de todas as vigas no pavimento
            for v_key, v_state in vigas.items():
                n_val = v_state.get('number', '') if isinstance(v_state, dict) else getattr(v_state, 'number', '')
                
                # Se vazio no campo, tenta extrair do nome/chave
                if not str(n_val).strip():
                    match = re.search(r'(\d+)', str(v_key))
                    if match: used_numbers.add(int(match.group(1)))
                else:
                    # Extrai a parte numérica (ignora frações caso existam)
                    match = re.search(r'(\d+)', str(n_val))
                    if match: used_numbers.add(int(match.group(1)))
            
            # 2. Considerar o número atual da interface como "ocupado" para podermos avançar a partir dele
            txt_ui = self.edt_num.text().strip()
            match_ui = re.search(r'(\d+)', txt_ui)
            if match_ui:
                used_numbers.add(int(match_ui.group(1)))
                
            # 3. Buscar o primeiro vácuo (gap) começando de 1
            candidate = 1
            while candidate in used_numbers:
                candidate += 1
                
            print(f"DEBUG_AUTO_NUM: Pavimento='{self.current_pavimento}' | Usados={sorted(list(used_numbers))} | Próximo Gerado={candidate}")
            return str(candidate)
        except Exception as e:
            print(f"Erro no cálculo de numeração: {e}")
            return "1"

    def prepare_new(self):
        """Prepara o sistema para a próxima viga inteira (ex: 1.2 -> 2)."""
        try:
            # Pega o próximo número inteiro e limpa decimais
            new_num = self.get_next_number()
            self.reset_fundo()
            self.edt_num.setText(new_num)
            self.action_select_names()
        except Exception as e:
            print(f"Error prepare_new: {e}")

            
    def reset_fundo(self):
        self._updating = True
        # Keep Pavimento, Obs, Pe Direito, Side? Usually yes.
        # Clearing specific fields
        self.edt_name.clear()
        self.edt_txt_l.clear()
        self.edt_txt_r.clear()
        self.last_loaded_key = None # Reset tracking on new/reset
        self.u_width.clear()
        self.u_h1.clear()
        self.u_h2.clear()
        # Reset to production defaults selected in General tab
        p1_type = "Sarrafeado" if self.rb_p1_sarr.isChecked() else "Grade"
        p2_type = "Sarrafeado" if self.rb_p2_sarr.isChecked() else "Grade"
        
        for r in self.panel_rows:
            r['w'].clear()
            r['h1'].clear()
            r['h2'].clear()
            if p1_type == "Sarrafeado": r['rb1_s'].setChecked(True)
            else: r['rb1_g'].setChecked(True)
            if p2_type == "Sarrafeado": r['rb2_s'].setChecked(True)
            else: r['rb2_g'].setChecked(True)
            
        self._updating = False
        self.update_model()
    
    # --- Persistence: Obra/Pavimento Hierarchy ---
    
    # --- Persistence: Obra/Pavimento Hierarchy ---
    
    def save_session_data(self):
        """Auto-save current session data to JSON."""
        try:
             # Prepare serializable dict
             serializable_data = {}
             for obra, pavs in self.project_data.items():
                 serializable_data[obra] = {}
                 for pav, content in pavs.items():
                     # Content is {'vigas': {}, 'metadata': {}}
                     vigas = content.get('vigas', {})
                     metadata = content.get('metadata', {'in': '', 'out': ''})
                     
                     vigas_serial = {}
                     for vname, vstate in vigas.items():
                         if isinstance(vstate, VigaState):
                             vigas_serial[vname] = asdict(vstate)
                         else:
                             vigas_serial[vname] = vstate
                             
                     serializable_data[obra][pav] = {
                         'vigas': vigas_serial,
                         'metadata': metadata
                     }
             
             data = {
                 'project_data': serializable_data,
                 'last_obra': self.current_obra,
                 'last_pavimento': self.current_pavimento
             }
             with open(self.persistence_file, 'w', encoding='utf-8') as f:
                 json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Auto-save error: {e}")

    def load_session_data(self):
        """Load session data from JSON."""
        loaded = False
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                raw_project = data.get('project_data', {})
                self.current_obra = data.get('last_obra', "")
                self.current_pavimento = data.get('last_pavimento', "")
             
                self.update_obra_combo()
                for obra, pavs in raw_project.items():
                    self.project_data[obra] = {}
                    for pav, content in pavs.items():
                        # Migration Logic
                        if 'vigas' in content:
                            raw_vigas = content['vigas']
                            metadata = content.get('metadata', {'in': '', 'out': ''})
                        else:
                            # Old format: content is vigas dict
                            raw_vigas = content
                            metadata = {'in': '', 'out': ''}
                            
                        # Segment Classes Initialization
                        if 'segment_classes' not in metadata:
                            metadata['segment_classes'] = ["Lista Geral"]
                            
                        self.project_data[obra][pav] = {
                            'vigas': {},
                            'metadata': metadata
                        }
                        
                        for vname, vdict in raw_vigas.items():
                             try:
                                 state = self._dict_to_state(vdict)
                                 # Ensure current class is in the list
                                 if state.segment_class not in metadata['segment_classes']:
                                     metadata['segment_classes'].append(state.segment_class)
                                 self.project_data[obra][pav]['vigas'][vname] = state
                             except: pass
                self.migrate_all_panel_ids() # Populate missing IDs after everything is loaded
                loaded = True
            except Exception as e:
                print(f"Auto-load error: {e}")
        
        # Check if we have any actual vigas loaded
        has_vigas = False
        for obra in self.project_data:
            for pav in self.project_data[obra]:
                if self.project_data[obra][pav].get('vigas'):
                    has_vigas = True
                    break
            if has_vigas: break

        # Default Initialization or Legacy Migration if empty or no vigas found
        if not self.project_data or not has_vigas:
            # Check for legacy pickle file (Absolute Paths)
            base_dir = os.path.dirname(os.path.abspath(__file__))
            legacy_file = os.path.join(base_dir, "fundos_salvos.json")
            legacy_file_parent = os.path.join(os.path.dirname(base_dir), "fundos_salvos.json")
            
            target_file = None
            if os.path.exists(legacy_file) and os.path.getsize(legacy_file) > 0:
                target_file = legacy_file
            elif os.path.exists(legacy_file_parent) and os.path.getsize(legacy_file_parent) > 0:
                target_file = legacy_file_parent
            
            migrated_legacy = False
            
            if target_file:
                try:
                    with open(target_file, 'r') as f:
                        # Check file size
                        f.seek(0, 2)
                        size = f.tell()
                        f.seek(0)
                        
                        if size > 0:
                            old_data = json.load(f)
                        else:
                            old_data = {}
                    
                    if old_data and isinstance(old_data, dict):
                         print("Migrating legacy data...")
                         # Initialize default structure
                         self.project_data = {
                            "Obra 1": {
                                "Pavimento 1": {
                                    "vigas": {},
                                    "metadata": {"in": "", "out": ""}
                                }
                            }
                         }
                         
                         # Migrate items
                         count = 0
                         target_vigas = self.project_data["Obra 1"]["Pavimento 1"]["vigas"]
                         
                         for k, vdict in old_data.items():
                             try:
                                 # Old keys were numbers usually, but vdict is main source
                                 # Ensure dict format is compatible or try to adapt
                                 state = self._dict_to_state(vdict)
                                 # Use name as key, or number if name empty
                                 vname = state.name if state.name else f"Viga {state.number}"
                                 target_vigas[vname] = state
                                 count += 1
                             except Exception as ex:
                                 print(f"Skipping item {k}: {ex}")
                                 
                         if count > 0:
                             print(f"Migrated {count} vigas from legacy storage.")
                             self.current_obra = "Obra 1"
                             self.current_pavimento = "Pavimento 1"
                             migrated_legacy = True
                             # Save immediately to new format
                             self.save_session_data()
                             QMessageBox.information(None, "Migração", f"{count} vigas antigas foram migradas para 'Obra 1 / Pavimento 1'.")
                except Exception as e:
                    print(f"Error migrating legacy data: {e}")

            if not migrated_legacy:
                self.project_data = {
                    "Obra 1": {
                        "Pavimento 1": {
                            "vigas": {},
                            "metadata": {"in": "", "out": ""}
                        }
                    }
                }
                self.current_obra = "Obra 1"
                self.current_pavimento = "Pavimento 1"
            
            loaded = True # We initialized defaults or migrated

        if loaded:
             self.update_obra_combo()
             # Trigger initial load of fields for default selection
             if self.current_obra and self.current_pavimento:
                 self.on_pav_changed(self.current_pavimento)

    def _dict_to_state(self, vdict):
        state = VigaState()
        
        # Mapping translation for simple fields
        translation = {
            'numero': 'number',
            'nome': 'name',
            'pavimento': 'floor',
            'obs': 'obs',
            'nivel_viga': 'level_beam',
            'nivel_oposto': 'level_opposite',
            'nivel_teto': 'level_ceiling',
            'ajuste': 'adjust',
            'texto_esq': 'text_left',
            'texto_dir': 'text_right',
            'segment_class': 'segment_class',
            'lado': 'side',
            'continuacao': 'continuation',
            'largura_total': 'total_width',
            'altura_total': 'total_height',
            'altura_geral': 'total_height', # Map both variants
            'altura2_global': 'height2_global',
            'sarrafo_esq': 'sarrafo_left',
            'sarrafo_dir': 'sarrafo_right',
            'sarrafo_h2_esq': 'sarrafo_h2_left',
            'sarrafo_h2_dir': 'sarrafo_h2_right',
            'sarrafo_alt2_esq': 'sarrafo_h2_left', # Variant
            'sarrafo_alt2_dir': 'sarrafo_h2_right', # Variant
            'area_util_m2': 'area_util',
            'fundo_viga': 'bottom',
            'bottom': 'bottom'
        }
        
        # Apply translation
        for old_k, new_k in translation.items():
            if old_k in vdict:
                val = vdict[old_k]
                # Type conversions if necessary
                if new_k == 'total_width' and isinstance(val, str):
                    try: val = float(val)
                    except: val = 0.0
                if new_k == 'total_height' and not isinstance(val, str):
                    val = str(val)
                setattr(state, new_k, val)

        # Apply standard keys (for newer JSON format)
        for k, v in vdict.items():
            if hasattr(state, k) and k not in ['panels', 'holes', 'pillar_left', 'pillar_right']:
                setattr(state, k, v)
        
        # Migration: Convert old single-link format to multiple links list
        if not state.combined_faces and vdict.get('combined_face_id'):
            old_name = vdict.get('combined_face_name', "")
            old_id = vdict.get('combined_face_id', "")
            if old_id:
                state.combined_faces = [{'name': old_name, 'id': old_id}]
        
        # Handle Panels Reconstruction
        if 'paineis_larguras' in vdict:
            # Legacy format (Separate lists)
            state.panels = []
            l_list = vdict.get('paineis_larguras', [0.0]*6)
            h1_list = vdict.get('paineis_alturas', vdict.get('paineis_alturas1', [0.0]*6))
            h2_list = vdict.get('paineis_alturas2', [0.0]*6)
            type1_list = vdict.get('paineis_tipo1', ['Sarrafeado']*6)
            type2_list = vdict.get('paineis_tipo2', ['Sarrafeado']*6)
            gh1_list = vdict.get('paineis_grade_altura1', [0.0]*6)
            gh2_list = vdict.get('paineis_grade_altura2', [0.0]*6)
            slab_sup = vdict.get('lajes_sup', [0.0]*6)
            slab_inf = vdict.get('lajes_inf', [0.0]*6)
            slab_alt = vdict.get('lajes_central_alt', [0.0]*6)
            
            for i in range(min(6, len(l_list))):
                state.panels.append(PanelData(
                    width=l_list[i],
                    height1=str(h1_list[i]) if i < len(h1_list) else "0.0",
                    height2=str(h2_list[i]) if i < len(h2_list) else "0.0",
                    type1=type1_list[i] if i < len(type1_list) else 'Sarrafeado',
                    type2=type2_list[i] if i < len(type2_list) else 'Sarrafeado',
                    grade_h1=gh1_list[i] if i < len(gh1_list) else 0.0,
                    grade_h2=gh2_list[i] if i < len(gh2_list) else 0.0,
                    slab_top=slab_sup[i] if i < len(slab_sup) else 0.0,
                    slab_bottom=slab_inf[i] if i < len(slab_inf) else 0.0,
                    slab_center=slab_alt[i] if i < len(slab_alt) else 0.0
                ))
        if 'panels' in vdict:
            # Standard JSON format
            state.panels = []
            for p_data in vdict.get('panels', []):
                # Robust numeric conversion for critical dimension fields
                params = {}
                numeric_fields = ['width', 'height1', 'height2', 'grade_h1', 'grade_h2', 'slab_top', 'slab_bottom', 'slab_center']
                
                # Copy all matching keys
                for k, v in p_data.items():
                    if k in numeric_fields:
                        try: params[k] = float(v)
                        except: params[k] = 0.0
                    elif k in PanelData.__annotations__:
                        params[k] = v
                
                # Instantiate with collected params. Missing keys will use dataclass defaults.
                p = PanelData(**params)
                state.panels.append(p)
            
        # Handle Holes Reconstruction
        if 'aberturas' in vdict:
            # Legacy format
            state.holes = []
            for item in vdict['aberturas']:
                if isinstance(item, list) and len(item) >= 3:
                     state.holes.append(HoleData(dist=item[0], depth=item[1], width=item[2]))
        elif 'holes' in vdict:
            state.holes = []
            for h_data in vdict.get('holes', []):
                h = HoleData(**{k: v for k, v in h_data.items() if k in HoleData.__annotations__})
                state.holes.append(h)
            
        # Handle Pillars Reconstruction
        if 'detalhe_pilar_esq' in vdict:
            p_esq = vdict['detalhe_pilar_esq']
            if isinstance(p_esq, list) and len(p_esq) >= 2:
                state.pillar_left = PillarDetail(dist=p_esq[0], width=p_esq[1])
        if 'pillar_left' in vdict:
            state.pillar_left = PillarDetail(**{k: v for k, v in vdict['pillar_left'].items() if k in PillarDetail.__annotations__})

        if 'detalhe_pilar_dir' in vdict:
            p_dir = vdict['detalhe_pilar_dir']
            if isinstance(p_dir, list) and len(p_dir) >= 2:
                state.pillar_right = PillarDetail(dist=p_dir[0], width=p_dir[1])
        if 'pillar_right' in vdict:
            state.pillar_right = PillarDetail(**{k: v for k, v in vdict['pillar_right'].items() if k in PillarDetail.__annotations__})
            
        return state

    # --- Export / Import JSON ---
    
    def export_data_json(self):
        self.save_session_data() # Ensure current state is saved to file
        # We can just copy the persistence file or reuse serialization
        # Reusing serialization logic is safer to not depend on file state
        try:
             file_path, _ = QFileDialog.getSaveFileName(self, "Exportar Dados JSON", "", "JSON Files (*.json)")
             if not file_path: return
             
             serializable_data = {}
             for obra, pavs in self.project_data.items():
                 serializable_data[obra] = {}
                 for pav, content in pavs.items():
                     vigas = content.get('vigas', {})
                     metadata = content.get('metadata', {'in': '', 'out': ''})
                     
                     vigas_serial = {}
                     for vname, vstate in vigas.items():
                         if isinstance(vstate, VigaState):
                             vigas_serial[vname] = asdict(vstate)
                         else:
                             vigas_serial[vname] = vstate
                             
                     serializable_data[obra][pav] = {
                         'vigas': vigas_serial,
                         'metadata': metadata
                     }
             
             with open(file_path, 'w', encoding='utf-8') as f:
                 json.dump(serializable_data, f, indent=4, ensure_ascii=False)
             QMessageBox.information(self, "Sucesso", "Dados exportados com sucesso!")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao exportar: {e}")

    def import_data_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Importar Dados JSON", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                self.project_data = {}
                for obra, pavs in data.items():
                    self.project_data[obra] = {}
                    for pav, content in pavs.items():
                        if 'vigas' in content:
                             raw_vigas = content['vigas']
                             metadata = content.get('metadata', {'in': '', 'out': ''})
                        else:
                             raw_vigas = content
                             metadata = {'in': '', 'out': ''}
                             
                        self.project_data[obra][pav] = {
                            'vigas': {},
                            'metadata': metadata
                        }
                        for vname, vdict in raw_vigas.items():
                             try:
                                 state = self._dict_to_state(vdict)
                                 self.project_data[obra][pav]['vigas'][vname] = state
                             except: pass
                             
                self.update_obra_combo()
                self.save_session_data()
                QMessageBox.information(self, "Sucesso", "Dados importados com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao importar: {e}")

    # --- Hierarchy Management Logic ---
    
    def on_obra_changed(self, text):
        self.current_obra = text
        self.update_pavimento_combo()
        self.save_session_data()

    def on_pav_changed(self, text):
        self.current_pavimento = text
        
        # Load Metadata
        if self.current_obra and self.current_pavimento:
            if self.current_obra in self.project_data and self.current_pavimento in self.project_data[self.current_obra]:
                pav_data = self.project_data[self.current_obra][self.current_pavimento]
                meta = pav_data.get('metadata', {})
                self.edt_pav_level_in.blockSignals(True)
                self.edt_pav_level_out.blockSignals(True)
                self.edt_pav_level_in.setText(meta.get('in', ''))
                self.edt_pav_level_out.setText(meta.get('out', ''))
                self.edt_pav_level_in.blockSignals(False)
                self.edt_pav_level_out.blockSignals(False)
                
                # Update Classes Combo
                self.update_classes_combo()
        
        # Conflict Prevention
        if self.chk_recycling.isChecked() and text == self.cmb_filter2.currentText() and text != "":
            QMessageBox.warning(self, "Conflito", "O pavimento de Reaproveitamento não pode ser o mesmo da viga em edição.")
            self.recycle_model = None
            self.preview.draw(self.model)
            self._populate_panel_list_recycle()
        
        self.update_vigas_list()
        self.save_session_data()
        
    def save_pavimento_metadata(self):
        if not self.current_obra or not self.current_pavimento: return
        if self.current_obra in self.project_data and self.current_pavimento in self.project_data[self.current_obra]:
             meta = {
                 'in': self.edt_pav_level_in.text(),
                 'out': self.edt_pav_level_out.text()
             }
             self.project_data[self.current_obra][self.current_pavimento]['metadata'] = meta
             self.save_session_data()

    def add_obra(self):
        text, ok = QInputDialog.getText(self, "Nova Obra", "Nome da Obra:")
        if ok and text:
            if text in self.project_data:
                QMessageBox.warning(self, "Aviso", "Obra já existe.")
                return
            self.project_data[text] = {}
            self.update_obra_combo()
            self.cmb_obra.setCurrentText(text)
            self.save_session_data() # Auto-save

    def del_obra(self):
        cur = self.cmb_obra.currentText()
        if not cur: return
        ret = QMessageBox.question(self, "Excluir", f"Excluir Obra '{cur}' e todos seus dados?", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            del self.project_data[cur]
            self.update_obra_combo()
            self.save_session_data()

    def add_pavimento(self):
        if not self.current_obra:
            QMessageBox.warning(self, "Aviso", "Selecione uma Obra primeiro.")
            return
        text, ok = QInputDialog.getText(self, "Novo Pavimento", "Nome do Pavimento:")
        if ok and text:
            if text in self.project_data[self.current_obra]:
                QMessageBox.warning(self, "Aviso", "Pavimento já existe nesta Obra.")
                return
            # Init with metadata structure
            self.project_data[self.current_obra][text] = {
                'vigas': {},
                'metadata': {'in': '', 'out': '', 'segment_classes': ["Lista Geral"]}
            }
            self.update_pavimento_combo()
            self.cmb_pav.setCurrentText(text)
            self.save_session_data()

    def del_pavimento(self):
        if not self.current_pavimento or not self.current_obra: return
        ret = QMessageBox.question(self, "Excluir", f"Deseja excluir o pavimento '{self.current_pavimento}' e todas as suas vigas?", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            del self.project_data[self.current_obra][self.current_pavimento]
            self.update_pavimento_combo()
            self.save_session_data()

    def copy_pavimento(self):
        """Cria uma cópia idêntica do pavimento selecionado com todos os seus itens."""
        if not self.current_obra or not self.current_pavimento:
            QMessageBox.warning(self, "Aviso", "Selecione uma obra e um pavimento para copiar.")
            return
            
        new_name, ok = QInputDialog.getText(self, "Copiar Pavimento", "Nome do novo pavimento:", text=f"{self.current_pavimento}_Copia")
        if not ok or not new_name.strip():
            return
            
        new_name = new_name.strip()
        if new_name in self.project_data[self.current_obra]:
            QMessageBox.warning(self, "Aviso", "Já existe um pavimento com esse nome.")
            return
            
        import copy
        source_content = self.project_data[self.current_obra][self.current_pavimento]
        
        # Deep copy the content
        # We ensure they are fresh objects by using deepcopy
        new_content = copy.deepcopy(source_content)
        
        # We should also ensure panels HAVE unique IDs and the floor tag is updated
        vigas = new_content.get('vigas', {})
        for vname, vstate in vigas.items():
            # Support both VigaState objects and raw dictionaries
            if isinstance(vstate, dict):
                vstate['floor'] = new_name # Update floor link
                p_list = vstate.get('panels', [])
                for p_dict in p_list:
                    p_dict['uid'] = "" # Will be re-generated
                    p_dict['uid_h2'] = ""
                    p_dict['reused_from'] = ""; p_dict['reused_from_h2'] = ""
                    p_dict['reused_in'] = ""; p_dict['reused_in_h2'] = ""
                    p_dict['link_saved'] = False
            elif hasattr(vstate, 'panels'):
                 vstate.floor = new_name # Update floor link
                 for p in vstate.panels:
                     p.uid = ""; p.uid_h2 = ""
                     p.reused_from = ""; p.reused_from_h2 = ""
                     p.reused_in = ""; p.reused_in_h2 = ""
                     p.link_saved = False
        
        self.project_data[self.current_obra][new_name] = new_content
        
        self.update_pavimento_combo()
        self.cmb_pav.setCurrentText(new_name)
        self.save_session_data()
        QMessageBox.information(self, "Sucesso", f"Pavimento '{new_name}' copiado com sucesso.")

    def update_obra_combo(self):
        self.cmb_obra.blockSignals(True)
        self.cmb_obra.clear()
        self.cmb_obra.addItems(sorted(self.project_data.keys()))
        self.cmb_obra.blockSignals(False)
        
        # Restore selection if possible
        if self.current_obra in self.project_data:
            self.cmb_obra.setCurrentText(self.current_obra)
        else:
            if self.cmb_obra.count() > 0:
                self.cmb_obra.setCurrentIndex(0)
                self.current_obra = self.cmb_obra.currentText()
            else:
                self.current_obra = ""
        
        self.update_pavimento_combo()

    def update_pavimento_combo(self):
        self.cmb_pav.blockSignals(True)
        self.cmb_pav.clear()
        
        pavimentos = []
        if self.current_obra and self.current_obra in self.project_data:
            pavimentos = sorted(self.project_data[self.current_obra].keys())
        
        self.cmb_pav.addItems(pavimentos)
        self.cmb_pav.blockSignals(False)
        
        if self.current_pavimento in pavimentos:
            self.cmb_pav.setCurrentText(self.current_pavimento)
            # Explicitly trigger load metadata since setCurrentText might not emit if text is same
            self.on_pav_changed(self.current_pavimento)
        else:
            if self.cmb_pav.count() > 0:
                self.cmb_pav.setCurrentIndex(0)
                self.current_pavimento = self.cmb_pav.currentText()
                self.on_pav_changed(self.current_pavimento)
            else:
                self.current_pavimento = ""
                self.update_vigas_list()

    def _detect_class(self, viga_name):
        """Helper to detect the segment class from a viga name or its state."""
        # This is a simplified version. In a real app, the VigaState object would have this.
        # For now, we'll assume it's part of the name or a default.
        # If the VigaState object is available, use vstate.segment_class
        # For now, just return "Lista Geral" as a fallback.
        return "Lista Geral"

    def _add_tree_item(self, parent, name, vstate, pav):
        item = QTreeWidgetItem(parent)
        item.setCheckState(0, Qt.Unchecked)
        
        import re
        nums = re.findall(r'\d+', name)
        num = nums[0] if nums else ""
        
        item.setText(2, num)
        item.setText(3, name)
        
        combined_name = ""
        if isinstance(vstate, dict):
             combined_name = vstate.get('combined_face_name', '')
        else:
             combined_name = getattr(vstate, 'combined_face_name', '')
        
        item.setText(5, combined_name)
        item.setData(0, Qt.UserRole, {"type": "beam", "key": name, "pav": pav})
        
        # Add Tag Widget
        self.tree1.setItemWidget(item, 4, TagLabel(pav, color="#455A64"))

    def update_vigas_list(self):
        """Update tree1 with vigas grouped by Segment Class or filtered by 'Todos'."""
        self.tree1.clear()
        self.lbl_total_m2.setText("Total m²: 0.00")
        
        if not self.current_obra:
            return
            
        cur_pav = self.cmb_pav.currentText()
        
        pavimentos = self.project_data.get(self.current_obra, {})
        
        # Se "Todos", iterar sobre tudo, senão só atual
        target_pavs = []
        if cur_pav == "Todos":
            if self.current_obra in self.project_data:
                target_pavs = sorted(self.project_data[self.current_obra].keys())
        elif cur_pav in pavimentos:
            target_pavs = [cur_pav]

        self.viga_grouping = {}
        
        for pav_name in target_pavs:
             if pav_name not in pavimentos: continue
             for viga_name, vstate in pavimentos[pav_name].get('vigas', {}).items(): # Access 'vigas' dict
                cls = getattr(vstate, 'segment_class', 'Lista Geral') if not isinstance(vstate, dict) else vstate.get('segment_class', 'Lista Geral')
                if cls not in self.viga_grouping:
                    self.viga_grouping[cls] = []
                # Append tuple (name, vstate, pav_origin) so we know where it came from if "Todos"
                self.viga_grouping[cls].append((viga_name, vstate, pav_name))

        total_m2 = 0.0
        
        # Draw Classes and Beams
        # Ensure "Lista Geral" is processed first if it exists
        sorted_classes = sorted(self.viga_grouping.keys())
        if "Lista Geral" in sorted_classes:
            sorted_classes.remove("Lista Geral")
            sorted_classes.insert(0, "Lista Geral")

        for cls_name in sorted_classes:
            v_list = self.viga_grouping.get(cls_name, [])
            
            # Create Class Header (Card-like)
            class_item = QTreeWidgetItem(self.tree1)
            class_item.setFirstColumnSpanned(True)  # Faz o texto ocupar todas as colunas
            class_item.setText(0, f"      {cls_name}") # Texto na coluna 0 agora expande
            class_item.setBackground(0, QColor("#424242"))
            class_item.setBackground(1, QColor("#424242"))
            class_item.setBackground(2, QColor("#424242"))
            class_item.setBackground(3, QColor("#424242"))
            class_item.setBackground(4, QColor("#424242"))
            font = QFont(); font.setBold(True); font.setPointSize(11)
            class_item.setFont(0, font) # Fonte na coluna 0
            class_item.setExpanded(True)
            class_item.setData(0, Qt.UserRole, {"type": "class", "key": cls_name})
            
            # Sort items in class
            # items_list is [(name, vstate, pav), ...]
            # Sort by numeric part of name
            def sort_key(x):
                import re
                nums = re.findall(r'\d+', x[0])
                return int(nums[0]) if nums else 0
            
            v_list.sort(key=sort_key)
            
            for vname, vstate, pav_origin in v_list:
                # Add to class group
                item = QTreeWidgetItem(class_item)
                
                num = getattr(vstate, 'number', '') if not isinstance(vstate, dict) else vstate.get('number', '')
                name = getattr(vstate, 'name', '') if not isinstance(vstate, dict) else vstate.get('name', '')
                area = getattr(vstate, 'area_util', 0.0) if not isinstance(vstate, dict) else vstate.get('area_util', 0.0)
                
                total_m2 += area
                
                item.setText(0, num)
                item.setText(1, name)
                
                comb_list = getattr(vstate, 'combined_faces', []) if not isinstance(vstate, dict) else vstate.get('combined_faces', [])
                comb_names = ", ".join([f.get('name', '') for f in comb_list if isinstance(f, dict)])
                item.setText(3, comb_names)
                
                item.setData(0, Qt.UserRole, {"type": "beam", "key": vname, "pav": pav_origin})
                
                # Add Tag Widget for Pav
                self.tree1.setItemWidget(item, 2, TagLabel(pav_origin, color="#455A64"))
                
        self.lbl_total_m2.setText(f"Total m²: {total_m2:.2f}")

    def _populate_recycling_options(self):
        """Popula o combobox de filtro da lista de reaproveitamento com os pavimentos da obra atual."""
        self.cmb_filter2.blockSignals(True)
        self.cmb_filter2.clear()
        
        if self.current_obra in self.project_data:
            pavs = sorted(self.project_data[self.current_obra].keys())
            self.cmb_filter2.addItems(pavs)
            
        self.cmb_filter2.blockSignals(False)
        self._filter_recycling_list()

    def _filter_recycling_list(self):
        """Atualiza a lista 2 (reaproveitamento) baseada no pavimento selecionado, com suporte a classes/grupos."""
        selected_pav = self.cmb_filter2.currentText()
        self.tree2.clear()
        
        if selected_pav == self.cmb_pav.currentText() and selected_pav != "":
            QMessageBox.warning(self, "Conflito", "O pavimento de Reaproveitamento não pode ser o mesmo da viga em edição.")
            return

        if self.current_obra not in self.project_data:
            return

        pavimentos_obra = self.project_data[self.current_obra]
        
        # 1. Coletar e Agrupar Dados
        grouping = {} # { class_name: [(vname, vstate, pav_name), ...] }
        
        for pav_name, pav_data in pavimentos_obra.items():
            # Filtro de Pavimento
            if selected_pav != "Todos" and pav_name != selected_pav:
                continue
                
            vigas_dict = pav_data.get('vigas', {})
            for viga_name, vstate in vigas_dict.items():
                # Determinar Classe
                cls = "Lista Geral"
                if not isinstance(vstate, dict):
                    cls = getattr(vstate, 'segment_class', 'Lista Geral')
                else:
                    cls = vstate.get('segment_class', 'Lista Geral')
                
                if cls not in grouping:
                    grouping[cls] = []
                grouping[cls].append((viga_name, vstate, pav_name))

        # 2. Desenhar na Tree2
        sorted_classes = sorted(grouping.keys())
        # Mover Lista Geral para o topo
        if "Lista Geral" in sorted_classes:
            sorted_classes.remove("Lista Geral")
            sorted_classes.insert(0, "Lista Geral")

        for cls_name in sorted_classes:
            v_list = grouping[cls_name]
            
            # Header da Classe
            class_item = QTreeWidgetItem(self.tree2)
            class_item.setFirstColumnSpanned(True)
            class_item.setText(0, f"      {cls_name}")
            class_item.setBackground(0, QColor("#37474F"))
            class_item.setBackground(1, QColor("#37474F"))
            class_item.setBackground(2, QColor("#37474F"))
            class_item.setBackground(3, QColor("#37474F"))
            font = QFont(); font.setBold(True)
            class_item.setFont(0, font)
            class_item.setExpanded(True)
            
            # Ordenar vigas numericamente
            def sort_key(x):
                import re
                nums = re.findall(r'\d+', x[0])
                return int(nums[0]) if nums else 0
            v_list.sort(key=sort_key)

            for vname, vstate, pav_origin in v_list:
                item = QTreeWidgetItem(class_item)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Unchecked)
                
                # Dados da Viga
                num = ""
                if not isinstance(vstate, dict):
                    num = getattr(vstate, 'number', '')
                else:
                    num = vstate.get('number', '')
                
                if not num: # Fallback regexp
                    import re
                    nums = re.findall(r'\d+', vname)
                    num = nums[0] if nums else "?"

                item.setText(1, str(num))
                item.setText(2, vname)
                
                # Pavimento Tag
                self.tree2.setItemWidget(item, 3, TagLabel(pav_origin, color="#455A64"))
                
                # Payload
                item.setData(0, Qt.UserRole, {"pav": pav_origin, "nome": vname, "type": "beam"})

    def delete_selected_vigas(self):
        if not self.current_obra or not self.current_pavimento: return
        
        selected = self.tree1.selectedItems()
        if not selected: return
        
        # Separate Classes and Beams
        classes_to_del = set()
        beams_to_del = set()
        
        for item in selected:
            data = item.data(0, Qt.UserRole)
            if not data: continue
            
            if isinstance(data, dict):
                if data['type'] == 'class':
                    classes_to_del.add(data['key'])
                elif data['type'] == 'beam':
                    beams_to_del.add(data['key'])
            else:
                # Legacy Assume Beam
                beams_to_del.add(data)
                
        msg = f"Excluir {len(beams_to_del)} vigas e {len(classes_to_del)} classes?"
        ret = QMessageBox.question(self, "Excluir", msg, QMessageBox.Yes | QMessageBox.No)
        
        if ret == QMessageBox.Yes:
            pav_data = self.project_data[self.current_obra][self.current_pavimento]
            vigas = pav_data.get('vigas', {})
            meta = pav_data.get('metadata', {})
            classes_list = meta.get('segment_classes', [])
            
            # Delete Classes (and their beams)
            for cls in classes_to_del:
                if cls == "Lista Geral": continue # Protect default
                
                # Find beams in this class
                keys_to_remove = []
                for k, v in vigas.items():
                    v_cls = getattr(v, 'segment_class', 'Lista Geral') if not isinstance(v, dict) else v.get('segment_class', 'Lista Geral')
                    if v_cls == cls:
                        keys_to_remove.append(k)
                        
                for k in keys_to_remove:
                    if k in vigas: del vigas[k]
                    
                if cls in classes_list:
                    classes_list.remove(cls)
                    
            # Delete Individual Beams
            for k in beams_to_del:
                if k in vigas: del vigas[k]
                
            self.update_vigas_list()
            self.save_session_data()

    def action_combine_faces(self):
        """Inicia o modo de seleção para combinar duas faces de viga."""
        sel = self.tree1.selectedItems()
        if len(sel) != 1:
            QMessageBox.warning(self, "Aviso", "Selecione exatamente UMA viga na lista para servir de origem.")
            return
            
        item = sel[0]
        data = item.data(0, Qt.UserRole)
        if not data or data.get('type') != 'beam':
            QMessageBox.warning(self, "Aviso", "Selecione uma VIGA válida.")
            return

        self.pending_combine_source = {
            'key': data.get('key'),
            'pav': data.get('pav')
        }
        
        # Altera o cursor para indicar modo de seleção
        self.setCursor(Qt.CrossCursor)
        self.display_floating("Selecione a outra viga que represente a outra face/lado da viga")

    def on_viga_tree_clicked(self, item, column):
        """Gerencia o clique na árvore, tratando especialmente o modo de combinação."""
        if hasattr(self, 'pending_combine_source') and self.pending_combine_source:
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'beam':
                target_key = data.get('key')
                target_pav = data.get('pav')
                source_key = self.pending_combine_source['key']
                source_pav = self.pending_combine_source['pav']
                
                if target_key == source_key and target_pav == source_pav:
                    QMessageBox.warning(self, "Aviso", "Não é possível combinar uma viga com ela mesma.")
                else:
                    self._perform_combination(source_pav, source_key, target_pav, target_key)
            
            # Reset picking mode
            self.pending_combine_source = None
            self.setCursor(Qt.ArrowCursor)
            if hasattr(self, '_floating'):
                self._floating.hide()

    def _perform_combination(self, pav1, key1, pav2, key2):
        """Realiza o vínculo bidirecional entre duas vigas."""
        try:
            # Pegar as vigas do projeto
            v1_raw = self.project_data[self.current_obra][pav1]['vigas'][key1]
            v2_raw = self.project_data[self.current_obra][pav2]['vigas'][key2]
            
            # Converter para objeto VigaState se necessário
            v1 = self._dict_to_state(v1_raw) if isinstance(v1_raw, dict) else v1_raw
            v2 = self._dict_to_state(v2_raw) if isinstance(v2_raw, dict) else v2_raw
            
            # BLOQUEIO: Mesma Classe e Mesmo Pavimento
            v1_cls = getattr(v1, 'segment_class', 'Lista Geral')
            v2_cls = getattr(v2, 'segment_class', 'Lista Geral')
            
            if pav1 != pav2:
                QMessageBox.warning(self, "Bloqueio", "Só é permitido combinar vigas do MESMO PAVIMENTO.")
                return
            
            if v1_cls != v2_cls:
                QMessageBox.warning(self, "Bloqueio", f"Só é permitido combinar vigas da MESMA CLASSE.\n\n'{key1}' é de '{v1_cls}'\n'{key2}' é de '{v2_cls}'")
                return
                 
            # Criar vínculo (Adiciona à lista se não existir)
            if not hasattr(v1, 'combined_faces'): v1.combined_faces = []
            if not any(f.get('id') == v2.unique_id for f in v1.combined_faces):
                v1.combined_faces.append({'name': key2, 'id': v2.unique_id})
            
            if not hasattr(v2, 'combined_faces'): v2.combined_faces = []
            if not any(f.get('id') == v1.unique_id for f in v2.combined_faces):
                v2.combined_faces.append({'name': key1, 'id': v1.unique_id})
            
            # Salvar de volta
            self.project_data[self.current_obra][pav1]['vigas'][key1] = v1
            self.project_data[self.current_obra][pav2]['vigas'][key2] = v2
            
            # Persistir
            self.save_session_data()
            self.update_vigas_list()
            QMessageBox.information(self, "Sucesso", f"Vigas '{key1}' e '{key2}' combinadas com sucesso!")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao combinar faces: {e}")
            import traceback
            traceback.print_exc()

    def action_uncombine_faces(self):
        """Remove o vínculo de combinação das vigas selecionadas."""
        sel = self.tree1.selectedItems()
        if not sel:
            QMessageBox.warning(self, "Aviso", "Selecione uma ou mais vigas para descombinar.")
            return
            
        count = 0
        for item in sel:
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'beam':
                pav = data.get('pav')
                key = data.get('key')
                
                v_raw = self.project_data[self.current_obra][pav]['vigas'][key]
                v = self._dict_to_state(v_raw) if isinstance(v_raw, dict) else v_raw
                
                # Get list of partners
                partners = getattr(v, 'combined_faces', [])
                partner_ids = [p.get('id') for p in partners if isinstance(p, dict)]
                
                # Limpar ID local
                v.combined_faces = []
                self.project_data[self.current_obra][pav]['vigas'][key] = v
                
                # Tentar limpar no parceiro globalmente
                for pid in partner_ids:
                    if pid:
                         self._unlink_partner_globally(pid, v.unique_id)
                
                count += 1
        
        if count > 0:
            self.save_session_data()
            self.update_vigas_list()
            QMessageBox.information(self, "Sucesso", f"{count} viga(s) descombinada(s).")

    def _unlink_partner_globally(self, partner_id, my_id):
        """Procura o parceiro pelo unique_id em todo o projeto e remove o vínculo dele com my_id."""
        obra_data = self.project_data.get(self.current_obra, {})
        for pav_name, pav_data in obra_data.items():
            if not isinstance(pav_data, dict): continue
            vigas = pav_data.get('vigas', {})
            for v_name, vstate in vigas.items():
                if isinstance(vstate, dict):
                    if vstate.get('unique_id') == partner_id:
                        faces = vstate.get('combined_faces', [])
                        vstate['combined_faces'] = [f for f in faces if f.get('id') != my_id]
                        return
                else:
                    if vstate.unique_id == partner_id:
                        faces = getattr(vstate, 'combined_faces', [])
                        vstate.combined_faces = [f for f in faces if f.get('id') != my_id]
                        return

    # Legacy methods removed.

def main():
    app = QApplication(sys.argv)
    window = VigaMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
