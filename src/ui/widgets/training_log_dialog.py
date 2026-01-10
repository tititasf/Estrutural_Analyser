from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                                 QTableWidgetItem, QPushButton, QLabel, QHeaderView, 
                                 QMessageBox, QAbstractItemView)
from PySide6.QtCore import Qt, Signal
import json
import logging

class TrainingLogDialog(QDialog):
    """
    Dialog to manage the Training Data history (High-Level Memory).
    Allows user to see what the AI learned (Positives & Negatives) and delete bad data.
    """
    
    # Signal emitted when focus is requested {type, pos/points, text}
    focus_requested = Signal(dict) 

    def __init__(self, db, project_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.project_id = project_id
        
        self.setWindowTitle("🧠 Histórico de Aprendizado da IA")
        self.resize(800, 600)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        lbl_info = QLabel("Gerenciamento de Memória: Aqui você remove treinos incorretos para evitar 'envenenar' a IA.")
        lbl_info.setStyleSheet("color: #aaa; font-style: italic; margin-bottom: 10px;")
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Data/Hora", "Status", "Item/Campo", "Valor Alvo", "Ações"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        # Dark Mode Table Style
        self.table.setStyleSheet("""
            QTableWidget { background: #1e1e1e; border: 1px solid #333; gridline-color: #333; }
            QHeaderView::section { background: #252525; padding: 4px; border: 1px solid #333; font-weight: bold; }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background: #00d4ff; color: #000; }
        """)
        
        layout.addWidget(self.table)
        
        # Action Buttons (Refresh, Close)
        btn_layout = QHBoxLayout()
        
        btn_refresh = QPushButton("🔄 Atualizar")
        btn_refresh.clicked.connect(self.load_data)
        
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.close)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def load_data(self):
        self.table.setRowCount(0)
        events = self.db.get_training_events(self.project_id)
        
        self.table.setRowCount(len(events))
        
        for i, ev in enumerate(events):
            # 0: Timestamp
            time_str = ev['timestamp']
            self.table.setItem(i, 0, QTableWidgetItem(str(time_str)))
            
            # 1: Status
            status = ev.get('status', 'valid')
            st_item = QTableWidgetItem(status.upper())
            if status == 'valid':
                st_item.setForeground(Qt.green)
            else:
                st_item.setForeground(Qt.red)
            st_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 1, st_item)
            
            # 2: Role (Item/Field)
            self.table.setItem(i, 2, QTableWidgetItem(ev.get('role', '?')))
            
            # 3: Target Value (Snippet)
            val = str(ev.get('target_value', ''))
            if len(val) > 40: val = val[:37] + "..."
            self.table.setItem(i, 3, QTableWidgetItem(val))
            
            # 4: Actions (Widget Container)
            act_widget = self._create_action_buttons(ev)
            self.table.setCellWidget(i, 4, act_widget)
            
    def _create_action_buttons(self, event_data):
        """Cria botões de Focar e Apagar"""
        from PySide6.QtWidgets import QWidget
        container = QWidget()
        l = QHBoxLayout(container)
        l.setContentsMargins(2, 2, 2, 2)
        l.setSpacing(4)
        
        # Focus Btn
        btn_focus = QPushButton("🔍")
        btn_focus.setToolTip("Ver geometria vinculada no Canvas")
        btn_focus.setFixedWidth(24)
        btn_focus.setStyleSheet("QPushButton { border: 1px solid #444; border-radius: 4px; } QPushButton:hover{background:#333;}")
        # Parse DNA to get geometric context for focus
        btn_focus.clicked.connect(lambda _, e=event_data: self._on_focus(e))
        l.addWidget(btn_focus)
        
        # Delete Btn
        btn_del = QPushButton("❌")
        btn_del.setToolTip("Apagar este registro de treino")
        btn_del.setFixedWidth(24)
        btn_del.setStyleSheet("QPushButton { border: 1px solid #844; color: #f55; border-radius: 4px; } QPushButton:hover{background:#522;}")
        btn_del.clicked.connect(lambda _, e=event_data: self._on_delete(e))
        l.addWidget(btn_del)
        
        return container

    def _on_focus(self, event_data):
        try:
            dna_json = event_data.get('context_dna_json')
            if not dna_json: return
            
            dna = json.loads(dna_json)
            # Estrutura esperada:
            # level_3_field -> 'local_geometry' / 'link'
            field_ctx = dna.get('level_3_field', {})
            link = field_ctx.get('link') or field_ctx.get('local_geometry_raw')
            
            if link and isinstance(link, dict): # Should allow focusing on link dict
                 self.focus_requested.emit(link)
                 # Bring main window to front?
            elif isinstance(link, (list, tuple)): # Coordinate
                 self.focus_requested.emit({'pos': link, 'type': 'point'})
            else:
                 QMessageBox.warning(self, "Dados Ausentes", "A geometria original não foi encontrada neste registro.")
                 
        except Exception as e:
            logging.error(f"Erro ao focar treino: {e}")
            QMessageBox.warning(self, "Erro", f"Falha ao ler geometria: {e}")

    def _on_delete(self, event_data):
        eid = event_data.get('id')
        role = event_data.get('role')
        
        reply = QMessageBox.question(self, "Confirmar Exclusão", 
                                     f"Tem certeza que deseja esquecer o treino para '{role}'?",
                                     QMessageBox.Yes | QMessageBox.No)
                                     
        if reply == QMessageBox.Yes:
            self.db.delete_training_event(eid)
            self.load_data() # Refresh list
