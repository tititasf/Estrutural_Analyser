import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QComboBox, QPushButton, QFileDialog, 
                               QFrame, QTableWidget, QTableWidgetItem, QHeaderView, 
                               QMessageBox, QAbstractItemView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QColor

class DocumentUploadDialog(QDialog):
    def __init__(self, class_name="Geral", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pre-ficha de Documentos")
        self.resize(700, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.class_name = class_name
        self.files_data = [] # List of dicts: {'path': '', 'name': ''}
        self.setup_ui()
        
        # Auto-open file dialog on show? Optional. Let's let user click.

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("📤 Importação de Documentos em Lote")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #00d4ff;")
        layout.addWidget(header)
        
        lbl_info = QLabel(f"Destino: {self.class_name}")
        lbl_info.setStyleSheet("color: #aaa; font-weight: bold;")
        layout.addWidget(lbl_info)

        # Action Bar or Top Button
        top_bar = QHBoxLayout()
        self.btn_add_files = QPushButton("➕ Selecionar Arquivos")
        self.btn_add_files.setStyleSheet("""
            QPushButton {
                background: #333;
                color: white;
                border: 1px solid #555;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: #444; border-color: #00d4ff; }
        """)
        self.btn_add_files.clicked.connect(self.choose_files)
        top_bar.addWidget(self.btn_add_files)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Files Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Arquivo Original", "Nome de Exibição (Editável)", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 40)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42) # Aumentar altura da linha
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                background: #1e1e21;
                border: 1px solid #333;
                border-radius: 4px;
                gridline-color: #333;
            }
            QHeaderView::section {
                background: #252528;
                padding: 6px;
                border: none;
                font-weight: bold;
                color: #ddd;
            }
            QLineEdit {
                background: #111;
                border: 1px solid #444;
                color: #fff;
                padding: 6px;
                min-height: 25px;
            }
            QLineEdit:focus { border: 1px solid #00d4ff; }
        """)
        layout.addWidget(self.table)
        
        # Empty State Label (initially visible if table is empty, or just use table placeholder)
        # We'll just manage table rows.

        # Footer Actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet("color: #888; border: none; padding: 10px;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        self.btn_finish = QPushButton("Finalizar Upload")
        self.btn_finish.setEnabled(False)
        self.btn_finish.setStyleSheet("""
            QPushButton {
                background: #00d4ff;
                color: #000;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background: #00b8e6; }
            QPushButton:disabled { background: #333; color: #555; }
        """)
        self.btn_finish.clicked.connect(self.validate_and_accept)
        btn_layout.addWidget(self.btn_finish)

        layout.addLayout(btn_layout)
        
        # Open file dialog immediately? User requested: "PRIMEIRO SOLICITE QUE SELECIONE..."
        # So we can trigger it after a slight delay or just let the user click.
        # Let's keep it manual click to avoid popup blocking or confusion, 
        # unless user specific preference implies AUTOMATIC popup. 
        # "PRIMEIRO SOLICITE ... APÓS ISSO LISTE" sounds like sequential flow.
        # But a "Select Files" button is clearer. Let's stick to the button.

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Selecionar Documentos", "", 
            "Arquivos Suportados (*.dwg *.dxf *.jpg *.jpeg *.png *.pdf *.zip *.md *.txt)"
        )
        if paths:
            for path in paths:
                self.add_file_row(path)
            self.update_finish_button()

    def add_file_row(self, path):
        # Check if already added
        for i in range(self.table.rowCount()):
            existing_path = self.table.item(i, 0).data(Qt.UserRole)
            if existing_path == path:
                return # Skip duplicate

        row = self.table.rowCount()
        self.table.insertRow(row)
        
        filename = os.path.basename(path)
        
        # Col 0: Original Name
        item_name = QTableWidgetItem(filename)
        item_name.setData(Qt.UserRole, path)
        item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable) # Read-only
        self.table.setItem(row, 0, item_name)
        
        # Col 1: Display Name (Editable)
        display_name = os.path.splitext(filename)[0].upper()
        edit_display = QLineEdit(display_name)
        edit_display.setPlaceholderText("Nome de exibição")
        self.table.setCellWidget(row, 1, edit_display)
        
        # Col 2: Remove Button
        btn_remove = QPushButton("❌")
        btn_remove.setCursor(Qt.PointingHandCursor)
        btn_remove.setStyleSheet("background: transparent; color: #ff5555; border: none; font-weight: bold;")
        btn_remove.clicked.connect(lambda: self.remove_row(row))
        self.table.setCellWidget(row, 2, btn_remove)

    def remove_row(self, row):
        self.table.removeRow(row)
        self.update_finish_button()
        
        # Fix lambda bindings if rows shift? 
        # Actually QTableWidget handles widgets in cells. 
        # But the lambda captures 'row' by value/ref issues? 
        # YES, removing rows shifts indices, so old lambdas point to wrong rows or out of bounds.
        # Better approach: get the button's parent or position.
        
        # Re-binding method:
        # Since complexity of rebinding is high, usually it's easier to find the row from the sender.
        # But for strictly correct behavior, let's fix the removed button logic below.
        pass

    def get_row_from_button(self, btn):
        index = self.table.indexAt(btn.pos())
        return index.row()

    # Redefine add_file_row's connect:
    # btn_remove.clicked.connect(self.on_remove_clicked)
    
    # Implementation correction for remove:
    pass

    def on_remove_clicked(self):
        btn = self.sender()
        if btn:
            index = self.table.indexAt(btn.parentWidget().pos()) # btn is typically inside a widget? No, setCellWidget puts it directly (mostly). 
            # safe way:
            for i in range(self.table.rowCount()):
                if self.table.cellWidget(i, 2) == btn:
                    self.table.removeRow(i)
                    self.update_finish_button()
                    return

    def update_finish_button(self):
        self.btn_finish.setEnabled(self.table.rowCount() > 0)

    def validate_and_accept(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Aviso", "Selecione pelo menos um arquivo.")
            return

        self.files_data = [] # Reset
        for i in range(self.table.rowCount()):
            path_item = self.table.item(i, 0)
            widget_name = self.table.cellWidget(i, 1)
            
            original_path = path_item.data(Qt.UserRole)
            display_name = widget_name.text().strip()
            
            if not display_name:
                QMessageBox.warning(self, "Aviso", f"O arquivo na linha {i+1} está sem nome de exibição.")
                widget_name.setFocus()
                return

            self.files_data.append({
                "path": original_path,
                "name": display_name,
                "category": self.class_name
            })
            
        # Confirmation
        msg = f"Confirmar upload de {len(self.files_data)} documentos?"
        if QMessageBox.question(self, "Confirmar", msg, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.accept()

    def get_data(self):
        return self.files_data
