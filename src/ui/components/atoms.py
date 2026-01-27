from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QFrame
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QFont, QIcon

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
            bg, color, border = "rgba(40, 167, 69, 0.2)", "#28a745", "#28a745"
        elif "REVIS" in s or "WARN" in s:
            bg, color, border = "rgba(255, 193, 7, 0.2)", "#ffc107", "#ffc107"
        else: # ERROR, CRITICAL
            bg, color, border = "rgba(220, 53, 69, 0.2)", "#dc3545", "#dc3545"
            
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
                color: #aaaaaa;
                font-size: 13px;
                border-left: 3px solid transparent;
            }
            NavButton:hover {
                background-color: rgba(255, 255, 255, 0.05);
                color: #ffffff;
            }
            NavButton:checked {
                background-color: rgba(0, 120, 212, 0.1);
                color: #0078d4;
                border-left: 3px solid #0078d4;
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
        lbl_title.setStyleSheet("color: #888; font-size: 11px;")
        
        full_value = f"{value} {unit}" if unit else str(value)
        lbl_val = QLabel(full_value)
        
        color = "#00E5FF" if highlight else "#EEE"
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
            color = "#888"
            bg = "#333"
        elif is_good:
            color = "#28a745"
            bg = "rgba(40, 167, 69, 0.1)"
        else:
            color = "#dc3545"
            bg = "rgba(220, 53, 69, 0.1)"
            
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
                border: 1px solid rgba(100, 100, 255, 0.3);
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header com ícone
        hdr_lbl = QLabel("✨ AI Analysis")
        hdr_lbl.setStyleSheet("color: #a0a0ff; font-weight: bold; font-size: 11px;")
        layout.addWidget(hdr_lbl)
        
        # Texto corpo
        self.lbl_text = QLabel(text)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet("color: #ddd; font-size: 11px; margin-top: 5px;")
        layout.addWidget(self.lbl_text)
        
        # Botão Ação
        self.btn_action = QPushButton("APPLY FIX")
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 120, 212, 0.3);
                border: 1px solid #0078d4;
                color: #fff;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: rgba(0, 120, 212, 0.5);
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
                    background-color: rgba(0, 229, 255, 0.15);
                    border: 1px solid #00E5FF;
                    color: #00E5FF;
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
                    border: 1px solid #555;
                    color: #777;
                    border-radius: 14px;
                     font-weight: bold; font-size: 10px;
                }
                QPushButton:hover {
                    border-color: #888;
                    color: #aaa;
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
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                color: #ddd;
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #3e3e42;
                border-color: #555;
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
        border_color = "#666"
        if status == "Online": border_color = "#4caf50"
        elif status == "Busy": border_color = "#f44336"
        elif status == "Away": border_color = "#ffc107"
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: #0078d4;
                color: #fff;
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
    def __init__(self, text, color="#0078d4"):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            background-color: {color};
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 9px;
            font-weight: bold;
        """)
