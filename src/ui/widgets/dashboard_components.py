from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                                QPushButton, QFrame, QSizePolicy, QScrollArea, QLineEdit)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QFont, QPainter

class ElidedLabel(QLabel):
    """Label que elida o texto automaticamente com '...'"""
    def paintEvent(self, event):
        painter = QPainter(self)
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self.text(), Qt.ElideRight, self.width())
        painter.drawText(self.rect(), self.alignment(), elided)

class BreadcrumbWidget(QWidget):
    """Navegação hierárquica estilizada."""
    clicked = Signal(str) # category: 'root', 'work', 'project'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.set_path("Projetos")

    def set_path(self, *steps):
        # Clear
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for i, step in enumerate(steps):
            if i > 0:
                sep = QLabel("›")
                sep.setStyleSheet("color: #666; font-size: 18px;")
                self.layout.addWidget(sep)
            
            btn = QPushButton(step.upper())
            btn.setFlat(True)
            is_last = (i == len(steps) - 1)
            color = "#fff" if is_last else "#888"
            font_weight = "bold" if is_last else "normal"
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    color: {color};
                    font-weight: {font_weight};
                    border: none;
                    background: transparent;
                    font-size: 13px;
                    padding: 4px;
                }}
                QPushButton:hover {{ color: #00d4ff; }}
            """)
            self.layout.addWidget(btn)
        
        self.layout.addStretch()

class MetricCard(QFrame):
    """Card de métrica técnica (ex: Carga Viva, Concreto)."""
    def __init__(self, title, value, unit="", parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 80)
        self.setStyleSheet("""
            MetricCard {
                background: #252528;
                border: 1px solid #333;
                border-radius: 8px;
            }
            QLabel#Title { color: #888; font-size: 10px; text-transform: uppercase; }
            QLabel#Value { color: #fff; font-size: 18px; font-weight: bold; }
            QLabel#Unit { color: #666; font-size: 11px; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        
        lbl_title = QLabel(title)
        lbl_title.setObjectName("Title")
        layout.addWidget(lbl_title)
        
        val_layout = QHBoxLayout()
        val_layout.setSpacing(4)
        
        lbl_val = QLabel(str(value))
        lbl_val.setObjectName("Value")
        val_layout.addWidget(lbl_val)
        
        if unit:
            lbl_unit = QLabel(unit)
            lbl_unit.setObjectName("Unit")
            lbl_unit.setAlignment(Qt.AlignBottom)
            val_layout.addWidget(lbl_unit)
            
        val_layout.addStretch()
        layout.addLayout(val_layout)

    def update_value(self, new_value):
        lbl = self.findChild(QLabel, "Value")
        if lbl:
            lbl.setText(str(new_value))

class DocumentItemWidget(QFrame):
    """Linha de documento na lista com ícone e ações (Legacy, keep for compatibility if needed elsewhere)."""
    delete_requested = Signal()
    open_requested = Signal()

    def __init__(self, name, size_info, ext, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36) # Reduced from 50
        self.setStyleSheet("""
            DocumentItemWidget {
                background: #222;
                border: 1px solid #333;
                border-radius: 6px;
                margin-bottom: 2px; # Reduced margin
            }
            DocumentItemWidget:hover { border-color: #00d4ff; background: #282828; }
            QLabel#DocName { color: #eee; font-weight: bold; font-size: 11px; } # Small font adjustment
            QLabel#DocMeta { color: #666; font-size: 9px; }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 2) # Reduced vertical margins
        
        # Icon placeholder based on extension
        icon_lbl = QLabel(self._get_icon_for_ext(ext))
        icon_lbl.setFixedSize(24, 24)
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)
        
        # Use ElidedLabel for name
        self.lbl_name = ElidedLabel(name)
        self.lbl_name.setObjectName("DocName")
        # lbl_name.setWordWrap(False) # Not needed/conflicts with elide
        info_layout.addWidget(self.lbl_name)
        
        self.lbl_meta = QLabel(size_info)
        self.lbl_meta.setObjectName("DocMeta")
        info_layout.addWidget(self.lbl_meta)
        
        layout.addLayout(info_layout, stretch=1)
        
        self.btn_open = QPushButton("↗")
        self.btn_open.setFixedSize(24, 24)
        self.btn_open.setFlat(True)
        self.btn_open.setToolTip("Abrir documento")
        self.btn_open.clicked.connect(self.open_requested)
        layout.addWidget(self.btn_open)
        
        self.btn_del = QPushButton("✕")
        self.btn_del.setFixedSize(24, 24)
        self.btn_del.setFlat(True)
        self.btn_del.setToolTip("Remover")
        self.btn_del.setStyleSheet("color: #666;")
        self.btn_del.clicked.connect(self.delete_requested)
        layout.addWidget(self.btn_del)

    def _get_icon_for_ext(self, ext):
        ext = ext.lower().replace(".", "")
        if ext in ('dwg', 'dxf'): return "📐"
        if ext in ('jpg', 'jpeg', 'png'): return "🖼️"
        if ext == 'pdf': return "📕"
        return "📄"

class DocumentationCategoryRow(QWidget):
    """Uma linha de categoria clicável que expande/recolhe."""
    clicked = Signal()

    def __init__(self, name, count, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32) # Reduced from 45 for slimmer look
        self.is_expanded = False
        self.setStyleSheet("""
            QWidget { 
                border-bottom: 1px solid #1f2029; 
                background: transparent;
            }
            QWidget:hover { background: #1a1b22; }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        
        # Seta de expansão
        self.arrow = QLabel("▸") # Right arrow for collapsed
        self.arrow.setStyleSheet("color: #666; font-size: 14px; border: none; margin-right: 5px;")
        layout.addWidget(self.arrow)

        self.lbl_name = QLabel(name)
        self.lbl_name.setStyleSheet("color: #ccc; font-size: 13px; border: none;")
        layout.addWidget(self.lbl_name)
        
        layout.addStretch()
        
        self.lbl_count = QLabel(f"{count:02d}")
        self.lbl_count.setStyleSheet("""
            background-color: #2c2d3a; 
            color: #8890b0; 
            padding: 4px 8px; 
            border-radius: 10px; 
            font-size: 11px; 
            font-weight: bold;
            border: none;
        """)
        layout.addWidget(self.lbl_count)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def set_expanded(self, expanded: bool):
        self.is_expanded = expanded
        self.arrow.setText("▾" if expanded else "▸")
        self.setStyleSheet(f"""
            QWidget {{ 
                border-bottom: 1px solid #1f2029; 
                background: {"#16171d" if expanded else "transparent"};
            }}
            QWidget:hover {{ background: #1a1b22; }}
        """)

class DocumentationListWidget(QFrame):
    """Lista de categorias de documentação estilizada (Para Painel Lateral)."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            DocumentationListWidget {
                background-color: #121319; 
                border-radius: 8px;
                border: 1px solid #252630;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header with expand icon and SEARCH
        header_main = QVBoxLayout()
        header_main.setSpacing(10)
        
        header_row = QHBoxLayout()
        lbl = QLabel("DOCUMENTAÇÃO")
        lbl.setStyleSheet("color: #6c7293; font-weight: bold; font-size: 11px; letter-spacing: 1.5px;")
        header_row.addWidget(lbl)
        header_row.addStretch()
        
        icon_expand = QLabel("❉") # Snowflake/Burst icon
        icon_expand.setStyleSheet("color: #00d4ff; font-size: 14px;")
        header_row.addWidget(icon_expand)
        header_main.addLayout(header_row)
        
        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar documento...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #1a1b22;
                border: 1px solid #2d2d3a;
                border-radius: 6px;
                padding: 6px 12px;
                color: #fff;
                font-size: 11px;
            }
            QLineEdit:focus { border: 1px solid #00d4ff; background: #1f2029; }
        """)
        self.search_input.textChanged.connect(self._filter_items)
        header_main.addWidget(self.search_input)
        
        layout.addLayout(header_main)
        
        # List Container
        self.container_widget = QWidget()
        self.list_layout = QVBoxLayout(self.container_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.container_widget)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(scroll)
        
        # Data storage
        self.category_groups = {} # {name: {'row': widget, 'items_container': widget, 'docs': []}}

    def set_items(self, categories_data):
        """categories_data: dict {CategoryName: [doc_list]}"""
        # Clear
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        self.category_groups = {}

        for name, docs in categories_data.items():
            self._add_category_group(name, docs)
            
        # Smart Auto-expand: Open categories that contain main documents
        for name, group in self.category_groups.items():
            if any(d.get('is_main') for d in group['docs']):
                 self._toggle_category(name)

    def _add_category_group(self, name, docs):
        # Category Row
        row = DocumentationCategoryRow(name, len(docs))
        self.list_layout.addWidget(row)
        
        # Items Container (Hidden by default)
        items_container = QWidget()
        items_container.setVisible(False)
        items_layout = QVBoxLayout(items_container)
        items_layout.setContentsMargins(15, 5, 5, 5)
        items_layout.setSpacing(5)
        
        for d in docs:
            # Note: DocumentItemWidget is defined above. We need to pass signals or handle them.
            # ProjectManager will probably want to connect these, so we might need a way to expose them.
            fpath = d.get('file_path')
            size_mb = "--"
            import os
            if fpath and os.path.exists(fpath):
                 size_mb = f"{(os.path.getsize(fpath) / 1024 / 1024):.2f} MB"
            
            doc_item = DocumentItemWidget(d['name'], size_mb, d.get('extension', ''))
            
            # Decorate if main
            if d.get('is_main'):
                doc_item.btn_del.setVisible(False)
                doc_item.setStyleSheet("background: #1a2634; border: 1px solid #2a4654; border-radius: 5px;")
            
            # Store data in widget to retrieve later or emit signals
            doc_item.setProperty("doc_data", d)
            items_layout.addWidget(doc_item)
            
        self.list_layout.addWidget(items_container)
        
        # Toggle Logic
        row.clicked.connect(lambda: self._toggle_category(name))
        
        self.category_groups[name] = {
            'row': row,
            'container': items_container,
            'docs': docs
        }

    def _toggle_category(self, name):
        group = self.category_groups.get(name)
        if not group: return
        
        is_visible = group['container'].isVisible()
        group['container'].setVisible(not is_visible)
        group['row'].set_expanded(not is_visible)

    def _filter_items(self, text):
        """Filtra visualmente os itens e categorias baseado no texto de busca."""
        text = text.lower().strip()
        for name, group in self.category_groups.items():
            container = group['container']
            row = group['row']
            
            any_visible = False
            for i in range(container.layout().count()):
                w = container.layout().itemAt(i).widget()
                if isinstance(w, DocumentItemWidget):
                    match = text in w.lbl_name.text().lower()
                    w.setVisible(match or not text)
                    if match: any_visible = True
            
            # Se a categoria bater com o nome ou tiver itens visíveis
            cat_match = text in name.lower()
            row.setVisible(cat_match or any_visible or not text)
            
            # Se for busca ativa, expande automaticamente as categorias que deram match
            if text and (cat_match or any_visible):
                container.setVisible(True)
                row.set_expanded(True)
            elif not text:
                # Volta para o estado padrão (Recolhido, exceto se for Main - mas aqui simplificamos)
                pass

    def get_document_item_widgets(self):
        """Helper to let ProjectManager find and connect signals of all items."""
        widgets = []
        for name, group in self.category_groups.items():
            container = group['container']
            for i in range(container.layout().count()):
                w = container.layout().itemAt(i).widget()
                if isinstance(w, DocumentItemWidget):
                    widgets.append(w)
        return widgets
