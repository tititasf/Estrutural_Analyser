from ..styles import DS
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QButtonGroup, QLabel, QCheckBox, QGroupBox)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QColor



class RoundButton(QPushButton):
    """Botão redondo customizado"""
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        # Tamanho reduzido
        self.setMinimumSize(20, 20)
        self.setMaximumSize(20, 20)
        self.setStyleSheet(f"""
            QPushButton {{
                border-radius: 10px;
                background-color: {DS.BORDER_STR};
                border: 1px solid {DS.MUTED};
                color: {DS.WHITE};
                font-weight: bold;
                font-size: 8px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {DS.MUTED};
                border: 1px solid {DS.INTERACTIVE};
            }}
            QPushButton:checked {{
                background-color: {DS.INTERACTIVE};
                border: 1px solid {DS.INTERACTIVE};
            }}
        """)

class CorrectionButton(QPushButton):
    """Botão de correção"""
    def __init__(self, text: str, parent=None, compact: bool = False):
        super().__init__(text, parent)
        if compact:
            # Botões compactos (1x), (2x), etc
            self.setMinimumSize(35, 20)
            self.setMaximumHeight(20)
        else:
            # Botões normais (Inverter Verticais, etc)
            self.setMinimumSize(50, 20)
            self.setMaximumHeight(20)
        self.setStyleSheet(f"""
            QPushButton {{
                border-radius: 3px;
                background-color: {DS.ELEVATED};
                border: 1px solid {DS.MUTED};
                color: {DS.WARNING};
                font-weight: bold;
                font-size: 9px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {DS.BORDER_STR};
                border: 1px solid {DS.WARNING};
            }}
            QPushButton:pressed {{
                background-color: {DS.DEEP};
            }}
        """)

class CalculosModosWidget(QWidget):
    """Widget para seleção de modos de cálculo e correções"""
    modo_selecionado = Signal(int)  # Emite o índice do modo selecionado (0-1)
    correcao_122_60_requested = Signal(int) # Emite o número de ciclos para 122+60
    correcao_122_20_requested = Signal(int) # Emite o número de ciclos para 122+20 (União)
    correcao_122_uniao_requested = Signal() 
    correcao_20_uniao_requested = Signal()
    inverter_verticais_requested = Signal()
    inverter_horizontais_requested = Signal()
    ajustar_sobra_requested = Signal()
    unioes_ilhas_esquerda_changed = Signal(int)
    unioes_ilhas_direita_changed = Signal(int)
    unioes_set_all_requested = Signal(float)
    
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 1. MODOS (M1 / M2) - Topo
        modes_container = QWidget()
        modes_layout = QHBoxLayout(modes_container)
        modes_layout.setContentsMargins(0, 0, 0, 0)
        modes_layout.setSpacing(8)
        
        lbl_modes = QLabel("Modos:")
        lbl_modes.setStyleSheet(f"color: {DS.SECONDARY}; font-size: 10px; font-weight: bold;")
        modes_layout.addWidget(lbl_modes)
        
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        
        # M1
        self.btn_m1 = RoundButton("M1")
        self.btn_m1.setToolTip("MODO VERTICAL")
        self.button_group.addButton(self.btn_m1, 0)
        self.buttons.append(self.btn_m1)
        modes_layout.addWidget(self.btn_m1)
        
        lbl_m1_desc = QLabel("MODO VERTICAL")
        lbl_m1_desc.setStyleSheet(f"color: {DS.SECONDARY}; font-size: 9px;")
        modes_layout.addWidget(lbl_m1_desc)
        
        modes_layout.addSpacing(10)
        
        # M2
        self.btn_m2 = RoundButton("M2")
        self.btn_m2.setToolTip("MODO HORIZONTAL")
        self.button_group.addButton(self.btn_m2, 1)
        self.buttons.append(self.btn_m2)
        modes_layout.addWidget(self.btn_m2)

        lbl_m2_desc = QLabel("MODO HORIZONTAL")
        lbl_m2_desc.setStyleSheet(f"color: {DS.SECONDARY}; font-size: 9px;")
        modes_layout.addWidget(lbl_m2_desc)

        modes_layout.addStretch()
        self.button_group.buttonClicked.connect(self.on_modo_selecionado)
        layout.addWidget(modes_container)
        
        # 2. CORREÇÕES
        corr_container = QWidget()
        corr_layout = QHBoxLayout(corr_container)
        corr_layout.setContentsMargins(0, 0, 0, 0)
        corr_layout.setSpacing(4)
        
        lbl_c = QLabel("Correções:")
        lbl_c.setStyleSheet(f"color: {DS.SECONDARY}; font-size: 10px;")
        corr_layout.addWidget(lbl_c)
        
        self.btn_inv_v = CorrectionButton("Inverter Verticais")
        self.btn_inv_v.clicked.connect(self.inverter_verticais_requested.emit)
        corr_layout.addWidget(self.btn_inv_v)
        
        self.btn_inv_h = CorrectionButton("Inverter Horizontais")
        self.btn_inv_h.clicked.connect(self.inverter_horizontais_requested.emit)
        corr_layout.addWidget(self.btn_inv_h)
        
        self.btn_sobra = CorrectionButton("Ajustar Sobra")
        self.btn_sobra.clicked.connect(self.ajustar_sobra_requested.emit)
        corr_layout.addWidget(self.btn_sobra)
        
        corr_layout.addStretch()
        layout.addWidget(corr_container)
        
        # 3. SUGESTÕES (122+60)
        sug60_container = QWidget()
        sug60_layout = QHBoxLayout(sug60_container)
        sug60_layout.setContentsMargins(0, 0, 0, 0)
        sug60_layout.setSpacing(2)
        
        lbl_s60 = QLabel("Sugestões (122+60):")
        lbl_s60.setStyleSheet(f"color: {DS.INTERACTIVE}; font-size: 10px; font-weight: bold;")
        sug60_layout.addWidget(lbl_s60)
        
        for i in range(1, 10):
             btn = CorrectionButton(f"({i}x)", compact=True)
             btn.clicked.connect(lambda _, x=i: self.correcao_122_60_requested.emit(x))
             sug60_layout.addWidget(btn)
             
        sug60_layout.addStretch()
        layout.addWidget(sug60_container)

        # 4. SUGESTÕES (122+20) / União
        sug20_container = QWidget()
        sug20_layout = QHBoxLayout(sug20_container)
        sug20_layout.setContentsMargins(0, 0, 0, 0)
        sug20_layout.setSpacing(2)
        
        lbl_s20 = QLabel("Sugestões (122+20):")
        lbl_s20.setStyleSheet(f"color: {DS.INTERACTIVE}; font-size: 10px; font-weight: bold;")
        sug20_layout.addWidget(lbl_s20)
        
        for i in range(1, 10):
             btn = CorrectionButton(f"({i}x)", compact=True)
             btn.clicked.connect(lambda _, x=i: self.correcao_122_20_requested.emit(x))
             sug20_layout.addWidget(btn)
             
        sug20_layout.addStretch()
        layout.addWidget(sug20_container)

        # Uniões Botões
        u_container = QWidget()
        u_layout = QHBoxLayout(u_container)
        u_layout.setContentsMargins(0, 0, 0, 0)
        u_layout.setSpacing(4)
        
        lbl_u = QLabel("Definir Uniões em:")
        lbl_u.setStyleSheet(f"color: {DS.WARNING}; font-size: 10px; font-weight: bold;")
        u_layout.addWidget(lbl_u)
        
        for val in [20, 25, 30]:
            btn = CorrectionButton(f"{val}", compact=True)
            btn.clicked.connect(lambda _, v=float(val): self.unioes_set_all_requested.emit(v))
            u_layout.addWidget(btn)
            
        u_layout.addStretch()
        layout.addWidget(u_container)
        
        # 4. CHECKBOXES
        cb_container = QWidget()
        self.bottom_row_layout = QHBoxLayout(cb_container)
        self.bottom_row_layout.setContentsMargins(0, 5, 0, 5) # Margem top para separar
        self.bottom_row_layout.setSpacing(10)
        
        self.checkbox_unioes_bordes = QCheckBox("Uniões nos bordes")
        self.style_checkbox(self.checkbox_unioes_bordes)
        self.bottom_row_layout.addWidget(self.checkbox_unioes_bordes)
        
        self.checkbox_unioes_ilhas_esquerda = QCheckBox("Ilhas Esq/Fundo")
        self.style_checkbox(self.checkbox_unioes_ilhas_esquerda, color=f"{DS.WARNING}")
        self.checkbox_unioes_ilhas_esquerda.stateChanged.connect(self.unioes_ilhas_esquerda_changed.emit)
        self.bottom_row_layout.addWidget(self.checkbox_unioes_ilhas_esquerda)
        
        self.checkbox_unioes_ilhas_direita = QCheckBox("Ilhas Dir/Topo")
        self.style_checkbox(self.checkbox_unioes_ilhas_direita, color=f"{DS.WARNING}")
        self.checkbox_unioes_ilhas_direita.stateChanged.connect(self.unioes_ilhas_direita_changed.emit)
        self.bottom_row_layout.addWidget(self.checkbox_unioes_ilhas_direita)
         
        self.bottom_row_layout.addStretch()
        
        layout.addWidget(cb_container)

    def setup_modos_layout(self, parent_layout: QHBoxLayout):
        """Depreciado: Funcionalidade movida para init_ui"""
        pass

    def style_checkbox(self, cb: QCheckBox, color: str = f"{DS.INTERACTIVE}"):
        """Aplica estilo padronizado ao checkbox"""
        cb.setStyleSheet(f"""
            QCheckBox {{
                color: {DS.SECONDARY};
                font-size: 10px;
            }}
            QCheckBox::indicator {{
                width: 12px;
                height: 12px;
                border: 1px solid {DS.MUTED};
                border-radius: 2px;
                background-color: {DS.ELEVATED};
            }}
            QCheckBox::indicator:checked {{
                background-color: {color};
                border: 1px solid {color};
            }}
        """)

    def on_modo_selecionado(self, button: QPushButton):
        modo_index = self.button_group.id(button)
        self.modo_selecionado.emit(modo_index)
    
    def set_modo(self, modo_index: int):
        if 0 <= modo_index < len(self.buttons):
            self.buttons[modo_index].setChecked(True)
    
    def unioes_nos_bordes_ativado(self) -> bool:
        return self.checkbox_unioes_bordes.isChecked()
    
    def unioes_ilhas_esquerda_ativado(self) -> bool:
        return hasattr(self, 'checkbox_unioes_ilhas_esquerda') and self.checkbox_unioes_ilhas_esquerda.isChecked()
    
    def unioes_ilhas_direita_ativado(self) -> bool:
        return hasattr(self, 'checkbox_unioes_ilhas_direita') and self.checkbox_unioes_ilhas_direita.isChecked()
    
    def add_widget_to_bottom_row(self, widget: QWidget):
        """Adiciona um widget à esquerda da linha inferior (onde ficam os checkboxes)"""
        # Inserir no início (índice 0)
        self.bottom_row_layout.insertWidget(0, widget)
