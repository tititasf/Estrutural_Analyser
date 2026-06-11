from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QFrame
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from src.ui.theme import Colors, Fonts, Radius

class StatusBadge(QLabel):
    """
    Badge visual para status (VALID, REVISÃO, ERROR).
    Cores: VALID=Verde, REVISAO=Laranja, ERROR=Vermelho
    """
    def __init__(self, status="VALID", compact=False):
        super().__init__(status)
        self.setAlignment(Qt.AlignCenter)
        self._status = status
        self._compact = compact
        self._set_style()
        
    def set_status(self, status):
        self.setText(status)
        self._status = status
        self._set_style()
        
    def _set_style(self):
        s = self._status.upper()
        if "VALID" in s or "OK" in s:
            bg, color, border = "rgba(40,167,69,51)", Colors.ACCENT_SUCCESS, Colors.ACCENT_SUCCESS
        elif "REVIS" in s or "WARN" in s:
            bg, color, border = "rgba(255,193,7,51)", Colors.ACCENT_WARNING, Colors.ACCENT_WARNING
        else: # ERROR, CRITICAL
            bg, color, border = "rgba(220,53,69,51)", Colors.ACCENT_DANGER, Colors.ACCENT_DANGER
            
        pad = "2px 6px" if self._compact else "4px 8px"
        font_size = "10px" if self._compact else "11px"
        
        self.setStyleSheet(f"""
            StatusBadge {{
                background-color: {bg};
                color: {color};
                border: 1px solid {border};
                border-radius: 4px;
                padding: {pad};
                font-weight: bold;
                font-family: 'Segoe UI', sans-serif;
                font-size: {font_size};
            }}
        """)

class NavButton(QPushButton):
    """
    Botão estilizado para sidebar de navegação.
    Suporta estado ativo (selecionado).
    """
    def __init__(self, text, icon_str=None, active=False):
        super().__init__(text)
        self.setCheckable(True)
        self.setChecked(active)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        
        # Estilo base
        self.setStyleSheet(self._get_style())
        
        # Se tiver ícone real, setar aqui (placeholder str por enquanto)
        if icon_str:
            # self.setIcon(QIcon(icon_str))
            pass

    def _get_style(self):
        return """
            NavButton {
                text-align: left;
                padding-left: 15px;
                background-color: transparent;
                border: none;
                color: {Colors.TEXT_SECONDARY};
                font-size: 13px;
                border-left: 3px solid transparent;
            }
            NavButton:hover {
                background-color: rgba(255,255,255,13);
                color: {Colors.TEXT_BRIGHT};
            }
            NavButton:checked {
                background-color: rgba(0,120,212,26);
                color: {Colors.ACCENT_BLUE};
                border-left: 3px solid {Colors.ACCENT_BLUE};
                font-weight: bold;
            }
        """

class MetricLabel(QWidget):
    """
    Par Chave-Valor estilizado para painéis técnicos.
    Ex: "Carga Crítica" (cinza) : "142.5 kN" (azul neon/branco)
    """
    def __init__(self, label, value, unit="", highlight=False):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        
        lbl_title = QLabel(label)
        lbl_title.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        
        full_value = f"{value} {unit}" if unit else str(value)
        lbl_val = QLabel(full_value)
        
        color = Colors.ACCENT_BRAND if highlight else Colors.TEXT_BRIGHT
        weight = "bold" if highlight else "normal"
        lbl_val.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: {weight};")
        lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        layout.addWidget(lbl_title)
        layout.addStretch()
        layout.addWidget(lbl_val)

class DeltaBadge(QLabel):
    """
    Badge para comparação de valores (+15%, -20kg).
    Verde para reduções positivas (ou aumentos dependendo do contexto), Vermelho para negativo.
    Por padrão: Aumento = Vermelho (Ex: Carga), Redução = Verde.
    Use `inverse=True` para Aumento = Verde (Ex: Segurança).
    """
    def __init__(self, value, suffix="%", inverse=False):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.update_value(value, suffix, inverse)
        
    def update_value(self, value, suffix="%", inverse=False):
        try:
            val_float = float(value)
        except:
            val_float = 0.0
            
        signal_char = "+" if val_float > 0 else ""
        text = f"{signal_char}{val_float}{suffix}"
        self.setText(text)
        
        # Lógica de cor
        # Default: Aumento (>0) é RUIM (Vermelho), Queda (<0) é BOM (Verde) - ex: Peso, Custo, Deformação
        # Inverse: Aumento (>0) é BOM (Verde), Queda (<0) é RUIM (Vermelho) - ex: Rigidez, Segurança
        
        is_good = (val_float > 0 and inverse) or (val_float < 0 and not inverse)
        
        if val_float == 0:
            color = Colors.TEXT_SECONDARY
            bg = Colors.BG_CARD
        elif is_good:
            color = Colors.ACCENT_SUCCESS
            bg = "rgba(40,167,69,26)"
        else:
            color = Colors.ACCENT_DANGER
            bg = "rgba(220,53,69,26)"
            
        self.setStyleSheet(f"""
            DeltaBadge {{
                background-color: {bg};
                color: {color};
                border-radius: 3px;
                padding: 1px 4px;
                font-size: 10px;
                font-weight: bold;
            }}
        """)

class AISuggestionBox(QFrame):
    """
    Caixa de destaque para insights da IA.
    Visual 'Glass' com borda sutil e botão de ação.
    """
    apply_clicked = Signal()

    def __init__(self, text="No suggestion."):
        super().__init__()
        self.setObjectName("AIBox")
        self.setStyleSheet("""
            #AIBox {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(30, 30, 40, 255), stop:1 rgba(40, 40, 60, 255));
                border: 1px solid rgba(100,100,255,76);
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header com ícone
        hdr_lbl = QLabel("✨ AI Analysis")
        hdr_lbl.setStyleSheet("color: rgba(160,160,255,1); font-weight: bold; font-size: 11px;")
        layout.addWidget(hdr_lbl)
        
        # Texto corpo
        self.lbl_text = QLabel(text)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet(f"color: {Colors.TEXT_BRIGHT}; font-size: 11px; margin-top: 5px;")
        layout.addWidget(self.lbl_text)
        
        # Botão Ação
        self.btn_action = QPushButton("APPLY FIX")
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background-color: rgba(0,120,212,76);
                border: 1px solid {Colors.ACCENT_BLUE};
                color: {Colors.TEXT_BRIGHT};
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: rgba(0,120,212,128);
            }
        """)
        self.btn_action.clicked.connect(self.apply_clicked.emit)
        layout.addWidget(self.btn_action)
        
    def set_suggestion(self, text):
        self.lbl_text.setText(text)

class SyncToggleButton(QPushButton):
    """
    Botão de Toggle para Sincronização de Viewports.
    """
    def __init__(self):
        super().__init__("SYNC VIEWPORTS")
        self.setCheckable(True)
        self.setFixedSize(120, 28)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
        self.toggled.connect(self._update_style)
        
    def _update_style(self):
        if self.isChecked():
            # Ativo: Azul neon
            self.setText("SYNC ON")
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0,229,255,38);
                    border: 1px solid {Colors.ACCENT_BRAND};
                    color: {Colors.ACCENT_BRAND};
                    border-radius: 14px;
                    font-weight: bold; font-size: 10px;
                }
            """)
        else:
            # Inativo: Cinza
            self.setText("SYNC OFF")
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: 1px solid {Colors.BORDER_INPUT};
                    color: {Colors.TEXT_MUTED};
                    border-radius: 14px;
                     font-weight: bold; font-size: 10px;
                }
                QPushButton:hover {
                    border-color: {Colors.TEXT_SECONDARY};
                    color: {Colors.TEXT_SECONDARY};
                }
            """)

class EmailSourceIcon(QLabel): # Typo fixed to QLabel in actual code
    """
    Ícone indicando origem (Gmail, Outlook, Upload).
    """
    def __init__(self, source_type="Email"):
        super().__init__()
        self.setFixedSize(24, 24)
        self.setAlignment(Qt.AlignCenter)
        
        # Mapeamento de Ícones (Unicode/Emoji por enquanto)
        icons = {
            "Gmail": "📧",
            "Outlook": "📧", 
            "Email": "📧",
            "Upload": "📤",
            "System": "🤖"
        }
        
        txt = icons.get(source_type, "❓")
        self.setText(txt)
        self.setToolTip(f"Origem: {source_type}")
        self.setStyleSheet("font-size: 14px;")

class AttachmentChip(QPushButton):
    """
    Chip representando anexos.
    Ex: [ 📎 planta.dxf ]
    """
    def __init__(self, filename):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setText(f"📎 {filename}")
        self.setStyleSheet("""
            QPushButton {
                background-color: {Colors.BORDER_PANEL};
                border: 1px solid {Colors.BORDER_INPUT};
                color: {Colors.TEXT_BRIGHT};
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.TEXT_MUTED};
            }
        """)

class UserAvatar(QLabel):
    """
    Avatar circular com status.
    """
    def __init__(self, name, status="Offline", size=32):
        super().__init__()
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        
        initials = name[:2].upper() if name else "??"
        self.setText(initials)
        
        # Cor de borda baseada no status
        border_color = Colors.TEXT_DIM
        if status == "Online": border_color = Colors.ACCENT_SUCCESS
        elif status == "Busy": border_color = Colors.ACCENT_DANGER
        elif status == "Away": border_color = Colors.ACCENT_WARNING
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.ACCENT_BLUE};
                color: {Colors.TEXT_BRIGHT};
                border: 2px solid {border_color};
                border-radius: {size//2}px;
                font-weight: bold;
                font-size: {size//2 - 2}px;
            }}
        """)
        self.setToolTip(f"{name} ({status})")

class PriorityTag(QLabel):
    """
    Badge colorida para tags (VIP, Urgente).
    """
    def __init__(self, text, color=Colors.ACCENT_BLUE):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            background-color: {color};
            color: {Colors.TEXT_BRIGHT};
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 9px;
            font-weight: bold;
        """)


def make_section_header(title: str, subtitle: str = "", accent_color: str = "") -> QWidget:
    """
    Cria um cabeçalho de seção padronizado para uso em painéis e abas.

    Args:
        title:        Texto principal em maiúsculas (ex: "DOCUMENTAÇÃO").
        subtitle:     Texto secundário opcional (ex: "12 itens").
        accent_color: Cor de destaque do título. Padrão: Colors.ACCENT_PRIMARY.

    Returns:
        QWidget contendo o cabeçalho pronto para inserir em qualquer layout.

    Uso:
        header = make_section_header("PILARES", "42 registros")
        layout.addWidget(header)
    """
    color = accent_color or Colors.ACCENT_PRIMARY

    container = QWidget()
    h_layout = QHBoxLayout(container)
    h_layout.setContentsMargins(0, 0, 0, 0)
    h_layout.setSpacing(8)

    lbl_title = QLabel(title.upper())
    lbl_title.setStyleSheet(
        f"color: {color}; font-size: {Fonts.SIZE_MD}; "
        f"font-weight: bold; letter-spacing: 1.5px; background: transparent;"
    )
    h_layout.addWidget(lbl_title)

    if subtitle:
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM}; "
            f"background: transparent;"
        )
        h_layout.addWidget(lbl_sub)

    h_layout.addStretch()

    # Linha separadora abaixo do título
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {Colors.BORDER_SUBTLE}; border: none;")

    wrapper = QWidget()
    v_layout = QVBoxLayout(wrapper)
    v_layout.setContentsMargins(0, 0, 0, 4)
    v_layout.setSpacing(4)
    v_layout.addWidget(container)
    v_layout.addWidget(line)

    return wrapper
