from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QLabel, QHeaderView)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

class TrainingLog(QWidget):
    sync_requested = Signal()

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.current_project_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Histórico de Aprendizado (Feedback)"))
        
        self.btn_sync = QPushButton("Sincronizar com Cérebro (Vector DB)")
        self.btn_sync.clicked.connect(self.sync_requested.emit)
        self.btn_sync.setStyleSheet("background-color: #d63384; color: white; font-weight: bold;")
        header_layout.addWidget(self.btn_sync)
        
        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Status", "Elemento (Role)", "Valor (Target)", "DNA Context"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def load_events(self, project_id):
        self.current_project_id = project_id
        if not project_id:
            self.table.setRowCount(0)
            return

        events = self.db.get_training_events(project_id)
        self.table.setRowCount(len(events))

        for i, ev in enumerate(events):
            # Timestamp
            self.table.setItem(i, 0, QTableWidgetItem(str(ev['timestamp'])))

            # Status (Color Coded)
            status_item = QTableWidgetItem(ev['status'])
            if ev['status'] == 'valid':
                status_item.setBackground(QColor("#d4edda")) # Greenish
                status_item.setForeground(QColor("#155724"))
            else:
                status_item.setBackground(QColor("#f8d7da")) # Reddish
                status_item.setForeground(QColor("#721c24"))
            self.table.setItem(i, 1, status_item)

            # Role
            self.table.setItem(i, 2, QTableWidgetItem(str(ev['role'])))

            # Value
            self.table.setItem(i, 3, QTableWidgetItem(str(ev['target_value'])))

            # DNA (Summary)
            try:
                import json
                dna_data = json.loads(ev['context_dna_json'])
                if isinstance(dna_data, list):
                    dna_text = f"vec[{len(dna_data)}]"
                else:
                    vec = dna_data.get('dna', [])
                    dna_text = f"vec[{len(vec)}] + pos"
            except:
                dna_text = "N/A"
            self.table.setItem(i, 4, QTableWidgetItem(dna_text))
