from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLineEdit
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon
from .atoms import StatusBadge, NavButton

class FloorListItem(QWidget):
    """
    Item de lista para seleção de pavimentos.
    Mostra: Nome do Pavimento | Status | Ranges
    """
    clicked = Signal(str) # Emits floor_id

    def __init__(self, floor_id, name, level_range, status="VALID", active=False):
        super().__init__()
        self.floor_id = floor_id
        self._active = active
        self.setObjectName("FloorItem")
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(10)
        
        # 1. Info Container
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        self.lbl_name = QLabel(name)
        self.lbl_name.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
        
        self.lbl_range = QLabel(level_range)
        self.lbl_range.setStyleSheet("color: #888; font-size: 10px;")
        
        info_layout.addWidget(self.lbl_name)
        info_layout.addWidget(self.lbl_range)
        
        self.layout.addLayout(info_layout)
        self.layout.addStretch()
        
        # 2. Status Badge
        self.badge = StatusBadge(status, compact=True)
        self.layout.addWidget(self.badge)
        
        self._set_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self.floor_id)
        super().mousePressEvent(event)

    def set_active(self, active):
        self._active = active
        self._set_style()

    def _set_style(self):
        bg = "rgba(0, 120, 212, 0.2)" if self._active else "transparent"
        border = "1px solid #0078d4" if self._active else "1px solid transparent"
        
        self.setStyleSheet(f"""
            #FloorItem {{
                background-color: {bg};
                border: {border};
                border-radius: 6px;
            }}
            #FloorItem:hover {{
                background-color: rgba(255, 255, 255, 0.05);
            }}
        """)

class ViewShortcutItem(QWidget):
    """
    Atalho para uma visão de câmera (Detalhe de Viga, etc).
    """
    clicked = Signal(str) # view_id
    
    def __init__(self, view_id, name, is_locked=False):
        super().__init__()
        self.view_id = view_id
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Icone Olho (Placeholder texto por enquanto)
        lbl_icon = QLabel("👁️") 
        layout.addWidget(lbl_icon)
        
        self.btn = QPushButton(name)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setStyleSheet("""
            text-align: left;
            background: transparent;
            border: none;
            color: #ccc;
        """)
        self.btn.clicked.connect(lambda: self.clicked.emit(view_id))
        layout.addWidget(self.btn)
        
        layout.addStretch()
        
        if is_locked:
            lbl_lock = QLabel("🔒")
            layout.addWidget(lbl_lock)

class EntityRow(QWidget):
    """
    Linha de propriedade chave-valor editável ou readonly.
    """
    value_changed = Signal(str, str) # key, new_value

    def __init__(self, key, value, editable=False):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(2)
        
        lbl_key = QLabel(key)
        lbl_key.setStyleSheet("color: #777; font-size: 10px; text-transform: uppercase;")
        layout.addWidget(lbl_key)
        
        if editable:
            self.editor = QLineEdit(str(value))
            self.editor.setStyleSheet("""
                background: #252525;
                border: 1px solid #444;
                color: white;
                padding: 4px;
                border-radius: 4px;
            """)
            self.editor.editingFinished.connect(lambda: self.value_changed.emit(key, self.editor.text()))
            layout.addWidget(self.editor)
        else:
            self.lbl_val = QLabel(str(value))
            self.lbl_val.setStyleSheet("color: #ddd; font-weight: bold; padding-left: 2px;")
            layout.addWidget(self.lbl_val)
