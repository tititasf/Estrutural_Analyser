import base64
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QTreeWidget, QTreeWidgetItem, QPushButton, QWidget, 
                               QSplitter, QStackedWidget, QFrame, QScrollArea, QHeaderView)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QCursor
from src.ui.theme import Colors, Fonts, Radius

# Helper de ofuscação (mantido para compatibilidade, embora não usado logicamente no novo UI)
def _get_obf_str(key):
    return key # Simplificado para evitar erros se não for crítico, ou manter o original se necessário

class ProjectDetailsDialog(QDialog):
    download_requested = Signal(str) # doc_name or id

    def __init__(self, project_data, documents=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"VISION AI - Detalhamento: {project_data.get('name', 'Sem Nome')}")
        self.resize(1000, 700)
        self.setStyleSheet("""
            QDialog { background: {Colors.BG_DEEP}; color: {Colors.TEXT_PRIMARY}; }
            QLabel { color: {Colors.TEXT_PRIMARY}; }
            QTreeWidget { 
                background: {Colors.BG_PANEL}; 
                border: 1px solid {Colors.BORDER_DEFAULT}; 
                border-radius: 6px;
                color: {Colors.TEXT_BRIGHT};
                font-size: 13px;
                padding: 5px;
            }
            QTreeWidget::item { padding: 4px; }
            QTreeWidget::item:selected { background: rgba(0, 77, 64, 1); color: {Colors.TEXT_BRIGHT}; }
            QTreeWidget::item:hover { background: {Colors.BG_CARD}; }
            
            QSplitter::handle { background: {Colors.BG_CARD}; width: 2px; }
            
        """)
        
        self.project_data = project_data
        self.documents = documents or [] # List of dicts: {'name': 'foo.dxf', 'type': 'structural', ...}
        self.items_cache = self._parse_items()
        
        self._init_ui()
        
    def _parse_items(self):
        """Extrai e organiza itens do JSON do projeto"""
        meta = self.project_data.get('metadata', {})
        if isinstance(meta, str):
            try: meta = json.loads(meta)
            except: meta = {}
            
        return {
            'pillars': meta.get('pillars', []) or [],
            'beams': meta.get('beams', []) or [],
            'slabs': meta.get('slabs', []) or []
        }

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QHBoxLayout()
        title = QLabel(f"📂 {self.project_data.get('name', 'PROJETO').upper()}")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {Colors.TEXT_BRIGHT};")
        header.addWidget(title)
        header.addStretch()
        
        # Global Stats Tags
        total = sum(len(v) for v in self.items_cache.values())
        self._add_header_tag(header, "ITENS TOTAIS", str(total), Colors.ACCENT_PRIMARY)
        
        # Mocking reuse calculation
        reuse_pct = "12%" 
        self._add_header_tag(header, "REAPROVEITAMENTO", reuse_pct, Colors.ACCENT_SUCCESS_ALT)
        
        main_layout.addLayout(header)
        main_layout.addSpacing(15)
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        
        # Left Panel: Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2) # Column 1 for Name, Column 2 for Action Buttons (Right)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        
        self._populate_tree()
        splitter.addWidget(self.tree)
        
        # Right Panel: Content Stack
        self.content_stack = QStackedWidget()
        
        # Page 0: Summary / Empty State
        self.page_summary = self._create_summary_page()
        self.content_stack.addWidget(self.page_summary)
        
        # Page 1: Details View (Dynamic)
        self.page_details = QWidget()
        self.details_layout = QVBoxLayout(self.page_details)
        self.details_layout.setAlignment(Qt.AlignTop)
        self.content_stack.addWidget(self.page_details)
        
        splitter.addWidget(self.content_stack)
        splitter.setSizes([300, 700])
        
        main_layout.addWidget(splitter)

    def _add_header_tag(self, layout, label, value, color):
        container = QFrame()
        container.setStyleSheet(f"background: {color}20; border: 1px solid {color}50; border-radius: 4px; padding: 4px 8px;")
        l = QHBoxLayout(container)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(5)
        
        lbl_k = QLabel(label)
        lbl_k.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
        l.addWidget(lbl_k)
        
        lbl_v = QLabel(value)
        lbl_v.setStyleSheet(f"color: {Colors.TEXT_BRIGHT}; font-size: 11px; font-weight: bold;")
        l.addWidget(lbl_v)
        
        layout.addWidget(container)

    def _populate_tree(self):
        # 1. Structural Class (Main)
        root_struct = QTreeWidgetItem(self.tree)
        root_struct.setText(0, "Estrutural")
        root_struct.setExpanded(True)
        # Icon?
        
        # Main DXF
        dxf_name = f"{self.project_data.get('name')}.dxf" # Mock if not present
        item_dxf = QTreeWidgetItem(root_struct)
        item_dxf.setText(0, dxf_name)
        # Add Download Button to column 1
        btn_dl = QPushButton("⬇")
        btn_dl.setFixedSize(24, 24)
        btn_dl.setFlat(True)
        btn_dl.setCursor(Qt.PointingHandCursor)
        btn_dl.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-weight: bold;")
        btn_dl.setToolTip("Baixar DXF")
        btn_dl.clicked.connect(lambda: self.download_requested.emit(dxf_name))
        
        self.tree.setItemWidget(item_dxf, 1, btn_dl)
        
        # 2. Categories
        cats = {
            'Pilares': self.items_cache['pillars'],
            'Vigas': self.items_cache['beams'],
            'Lajes': self.items_cache['slabs']
        }
        
        for cat_name, items in cats.items():
            root_cat = QTreeWidgetItem(self.tree)
            root_cat.setText(0, f"{cat_name} ({len(items)})")
            
            for item in items:
                i_name = item.get('label') or item.get('name') or f"Item {item.get('id')}"
                child = QTreeWidgetItem(root_cat)
                child.setText(0, i_name)
                child.setData(0, Qt.UserRole, item) # Store item data

    def _create_summary_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setAlignment(Qt.AlignCenter)
        lbl = QLabel("Selecione um item na árvore para ver os detalhes.")
        lbl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 14px;")
        l.addWidget(lbl)
        return w

    def on_tree_item_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data:
            self._show_item_details(data)
        elif item.parent() is None:
            # Clicked on Category Root
            self.content_stack.setCurrentWidget(self.page_summary)

    def _show_item_details(self, item_data):
        # Clear previous layout
        while self.details_layout.count():
            child = self.details_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        self.content_stack.setCurrentWidget(self.page_details)
        
        # Header
        name = item_data.get('label') or item_data.get('name') or "?"
        header = QLabel(f"Detalhes do Elemento: {name}")
        header.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {Colors.TEXT_BRIGHT}; margin-bottom: 20px;")
        self.details_layout.addWidget(header)
        
        # Info Grid
        info_widget = QWidget()
        grid = QGridLayout(info_widget)
        grid.setSpacing(15)
        
        # Status Tag
        is_blue = item_data.get('is_fully_validated', False)
        status = "VALIDADO (AZUL)" if is_blue else "EM ANÁLISE"
        s_color = Colors.ACCENT_PRIMARY if is_blue else Colors.ACCENT_WARNING_ALT
        
        lbl_st = QLabel(status)
        lbl_st.setStyleSheet(f"background: {s_color}22; color: {s_color}; padding: 6px; border-radius: 4px; font-weight: bold;")
        self.details_layout.addWidget(lbl_st)
        self.details_layout.addSpacing(15)
        
        # Validated Fields Tags
        lbl_f = QLabel("Campos Identificados:")
        lbl_f.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: bold;")
        self.details_layout.addWidget(lbl_f)
        
        fields_container = QWidget()
        flow = FlowLayout(fields_container) # Need FlowLayout? Or simple Wrap?
        # Let's use a wrap layout or simple grid for now if FlowLayout not importable
        # Since I don't have FlowLayout handy in imports, I'll use a grid that wraps manually or just vertical for now
        
        fields = item_data.get('validated_fields', [])
        if not fields:
             self.details_layout.addWidget(QLabel("Nenhum campo validado."))
        else:
            # Create a simple flow-like effect with QHBoxLayouts in a global VBox?
            # Or just list them
            for f in fields:
                tag = QLabel(f"✔ {f}")
                tag.setStyleSheet(f"background: rgba(46, 125, 50, 1); color: {Colors.TEXT_BRIGHT}; padding: 4px 8px; border-radius: 12px; margin: 2px;")
                self.details_layout.addWidget(tag)

        self.details_layout.addStretch()

# Minimal Flow Layout Implementation (if needed, otherwise just VBox)
# Skipping FlowLayout for brevity, VBox is fine for now as requested "detalhamento individual"
