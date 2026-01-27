import logging
import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QScrollArea, QSplitter,
    QTreeView, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QTabWidget, QMessageBox, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, QSize, Slot, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QStandardItemModel, QStandardItem

# Imports de Atoms e Molecules
from src.ui.components.atoms import MetricLabel, StatusBadge
from src.ui.components.molecules_control import (
    EmailListItem, DocumentRowItem, UserStatusRow
)
from src.ui.dialogs.create_client_dialog import CreateClientDialog
from src.ui.dialogs.convert_doc_dialog import ConvertDocDialog, ConvertToPavementDialog
from src.ui.dialogs.email_detail_dialog import EmailDetailDialog
from src.core.services.email_service import EmailService, EmailSyncThread

class MetricCard(QFrame):
    def __init__(self, title, value, icon_text, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumWidth(200)
        self.setFixedHeight(90)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        icon_lbl = QLabel(icon_text)
        icon_lbl.setStyleSheet("font-size: 24px; color: #0078d4;")
        layout.addWidget(icon_lbl)
        
        v_layout = QVBoxLayout()
        v_layout.setSpacing(2)
        
        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet("color: #888; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        v_layout.addWidget(title_lbl)
        
        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet("color: #fff; font-size: 20px; font-weight: bold;")
        v_layout.addWidget(self.value_lbl)
        
        layout.addLayout(v_layout)
        layout.addStretch()

class CentralControle(QWidget):
    def __init__(self, db, memory, auth_service=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.memory = memory
        self.auth_service = auth_service
        self.current_client_data = None
        
        # Email Service
        # TODO: Load these from secure storage or settings
        self.email_service = EmailService("thierry.tasf2@gmail.com", "qzpj pqdj ansq tzzi")
        self.email_service.new_email_received.connect(self.on_email_received)
        self.email_service.sync_finished.connect(self.on_email_sync_finished)
        self.email_thread = EmailSyncThread(self.email_service)
        
        self.setup_ui()
        self.refresh_data()
        
        # Auto-refresh team and emails periodically
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_periodic)
        self.timer.start(60000) # 1 min

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 1. TOP METRICS
        self.setup_metrics()
        self.main_layout.addWidget(self.metrics_container)
        
        # 2. MIDDLE AREA (Splitter)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("QSplitter::handle { background: #2d2d2d; }")
        
        # 2.1 Side Clients
        self.setup_clients_sidebar()
        self.splitter.addWidget(self.clients_panel)
        
        # 2.2 Center Content (Communication Hub)
        self.setup_center_content()
        self.splitter.addWidget(self.center_widget)
        
        # 2.3 Team Tracking
        self.setup_team_tracking()
        self.splitter.addWidget(self.team_panel)
        
        self.splitter.setSizes([280, 800, 320])
        self.main_layout.addWidget(self.splitter)
        
    def setup_metrics(self):
        self.metrics_container = QWidget()
        self.metrics_container.setFixedHeight(110)
        metrics_layout = QHBoxLayout(self.metrics_container)
        metrics_layout.setContentsMargins(20, 10, 20, 10)
        metrics_layout.setSpacing(15)
        
        self.card_m2 = MetricCard("M² Projetados", "0 m²", "📐")
        self.card_prazos = MetricCard("Prazos Ativos", "0", "⏱️")
        self.card_clients = MetricCard("Clientes", "0", "👥")
        self.card_docs = MetricCard("Docs Processados", "0", "📄")
        
        metrics_layout.addWidget(self.card_m2)
        metrics_layout.addWidget(self.card_prazos)
        metrics_layout.addWidget(self.card_clients)
        metrics_layout.addWidget(self.card_docs)
        
    def setup_clients_sidebar(self):
        self.clients_panel = QFrame()
        self.clients_panel.setStyleSheet("background: #1a1a1a; border-right: 1px solid #2d2d2d;")
        layout = QVBoxLayout(self.clients_panel)
        layout.setContentsMargins(15, 20, 15, 20)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>CLIENTES</b>"))
        header_layout.addStretch()
        btn_reload = QPushButton("🔄")
        btn_reload.setFixedSize(24, 24)
        btn_reload.clicked.connect(self.load_clients)
        btn_reload.setStyleSheet("border: none; color: #888;")
        header_layout.addWidget(btn_reload)
        layout.addLayout(header_layout)
        
        self.search_client = QLineEdit()
        self.search_client.setPlaceholderText("Buscar cliente...")
        self.search_client.setStyleSheet("background: #252526; border: 1px solid #3e3e42; padding: 6px; border-radius: 4px; color: #fff;")
        layout.addWidget(self.search_client)
        
        self.tree_clients = QTreeView()
        self.tree_clients.setHeaderHidden(True)
        self.tree_clients.setStyleSheet("background: transparent; border: none; color: #ddd;")
        self.tree_clients.clicked.connect(self.on_client_selected)
        layout.addWidget(self.tree_clients)
        
        btn_new_client = QPushButton("+ Novo Cliente")
        btn_new_client.setCursor(Qt.PointingHandCursor)
        btn_new_client.setStyleSheet("background-color: #0078d4; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        btn_new_client.clicked.connect(self.open_new_client_dialog)
        layout.addWidget(btn_new_client)

    def setup_center_content(self):
        self.center_widget = QWidget()
        layout = QVBoxLayout(self.center_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Client Header
        self.client_header = QFrame()
        self.client_header.setFixedHeight(80)
        self.client_header.setStyleSheet("border-bottom: 1px solid #2d2d2d; background: #1e1e1e;")
        head_lay = QHBoxLayout(self.client_header)
        head_lay.setContentsMargins(20, 10, 20, 10)
        
        self.avatar_lbl = QLabel("👤")
        self.avatar_lbl.setFixedSize(48, 48)
        self.avatar_lbl.setStyleSheet("background: #333; border-radius: 24px; color: #aaa; font-size: 24px;")
        self.avatar_lbl.setAlignment(Qt.AlignCenter)
        head_lay.addWidget(self.avatar_lbl)
        
        info_v = QVBoxLayout()
        info_v.setSpacing(2)
        self.lbl_client_name = QLabel("Selecione um Cliente")
        self.lbl_client_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        self.lbl_client_detail = QLabel("...")
        self.lbl_client_detail.setStyleSheet("color: #888; font-size: 11px;")
        info_v.addWidget(self.lbl_client_name)
        info_v.addWidget(self.lbl_client_detail)
        head_lay.addLayout(info_v)
        head_lay.addStretch()
        
        btn_sync_email = QPushButton("Sync Email")
        btn_sync_email.clicked.connect(self.start_email_sync)
        btn_sync_email.setStyleSheet("background: #2d2d30; border: 1px solid #444; color: #ccc; padding: 6px 12px; border-radius: 4px;")
        head_lay.addWidget(btn_sync_email)
        
        layout.addWidget(self.client_header)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { background: transparent; padding: 10px 20px; color: #888; font-weight: bold; border-bottom: 2px solid transparent; }
            QTabBar::tab:selected { color: #0078d4; border-color: #0078d4; }
        """)
        
        self.tab_conversas = QWidget()
        self.setup_tab_conversas()
        self.tabs.addTab(self.tab_conversas, "CONVERSAS")
        
        self.tab_docs = QWidget()
        self.setup_tab_docs()
        self.tabs.addTab(self.tab_docs, "DOCUMENTOS")
        
        layout.addWidget(self.tabs)

    def setup_tab_conversas(self):
        layout = QVBoxLayout(self.tab_conversas)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_emails = QScrollArea()
        self.scroll_emails.setWidgetResizable(True)
        self.scroll_emails.setStyleSheet("background: transparent; border: none;")
        self.emails_container = QWidget()
        self.emails_layout = QVBoxLayout(self.emails_container)
        self.emails_layout.setAlignment(Qt.AlignTop)
        self.emails_layout.setSpacing(0)
        self.scroll_emails.setWidget(self.emails_container)
        
        layout.addWidget(self.scroll_emails)

    def setup_tab_docs(self):
        layout = QVBoxLayout(self.tab_docs)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Docs List
        self.scroll_docs = QScrollArea()
        self.scroll_docs.setWidgetResizable(True)
        self.scroll_docs.setStyleSheet("background: transparent; border: none;")
        self.docs_container = QWidget()
        self.docs_layout = QVBoxLayout(self.docs_container)
        self.docs_layout.setAlignment(Qt.AlignTop)
        self.scroll_docs.setWidget(self.docs_container)
        
        layout.addWidget(self.scroll_docs)

    def setup_team_tracking(self):
        self.team_panel = QFrame()
        self.team_panel.setStyleSheet("background: #1a1a1a; border-left: 1px solid #2d2d2d;")
        layout = QVBoxLayout(self.team_panel)
        layout.setContentsMargins(15, 20, 15, 20)
        
        layout.addWidget(QLabel("<b>RASTREAMENTO DE EQUIPE</b>"))
        
        self.scroll_team = QScrollArea()
        self.scroll_team.setWidgetResizable(True)
        self.scroll_team.setStyleSheet("background: transparent; border: none;")
        self.team_container = QWidget()
        self.team_layout = QVBoxLayout(self.team_container)
        self.team_layout.setAlignment(Qt.AlignTop)
        self.scroll_team.setWidget(self.team_container)
        layout.addWidget(self.scroll_team)
        
    # --- Logic ---

    def refresh_data(self):
        self.load_clients()
        self.update_summary_metrics()
        self.load_team_tracking()
        self.refresh_periodic() # Load emails

    def refresh_periodic(self):
        # Trigger email sync silently -> DISABLED BY USER REQUEST (Avoid Overquota)
        # if not self.email_thread.isRunning():
        #     self.email_thread.start()
        self.load_team_tracking() # Refresh status if needed

    def load_clients(self):
        self.client_model = QStandardItemModel()
        self.tree_clients.setModel(self.client_model)
        clients = self.db.get_all_clients()
        
        for c in clients:
            item = QStandardItem(c['name'])
            item.setData(c, Qt.UserRole)
            self.client_model.appendRow(item)
            
        self.card_clients.value_lbl.setText(str(len(clients)))

    def on_client_selected(self, index):
        item = self.client_model.itemFromIndex(index)
        if not item: return
        self.current_client_data = item.data(Qt.UserRole)
        
        # Update Header
        self.lbl_client_name.setText(self.current_client_data['name'])
        comp = self.current_client_data.get('company', '')
        email = self.current_client_data.get('email', '')
        self.lbl_client_detail.setText(f"{comp} • {email}")
        
        # Filter Conversations & Docs
        self.filter_emails_docs()

    def start_email_sync(self):
        if not self.email_thread.isRunning():
            self.email_thread.start()
            QMessageBox.information(self, "Sync", "Sincronização iniciada...")

    @Slot(dict)
    def on_email_received(self, email_data):
        # Save to DB
        clients = self.db.get_all_clients()
        client_id = None
        sender_email = email_data['sender'].lower()
        safe_subject = email_data.get('subject', '')

        # Advanced matching logic
        # 1. Match by Email in sender string
        for c in clients:
            c_email = c.get('email', '').strip().lower()
            if c_email and c_email in sender_email:
                client_id = c['id']
                break
        
        # 2. Match by Subject keyword "PROJETO" if still no client
        if not client_id:
            if "PROJETO" in safe_subject.upper():
                pass
        
        # Log with ACTUAL email date
        safe_sender = email_data['sender']
        safe_subject = email_data['subject']
        clean_attachments = email_data['attachments']
        received_at = email_data.get('date')

        print(f"DEBUG: Database Module: {self.db.__module__}")
        try:
            import inspect
            print(f"DEBUG: Database File: {inspect.getfile(self.db.__class__)}")
        except: pass

        self.db.log_communication(
            client_id=client_id,
            source_type='email',
            sender=safe_sender,
            subject=safe_subject,
            content=email_data.get('body', ''),
            attachments=clean_attachments,
            received_at=received_at # Now passing correctly
        )
        # self.db.cleanup_duplicates() # Moved to finished sync to avoid spam
        self.filter_emails_docs() # Refresh UI

    @Slot(int)
    def on_email_sync_finished(self, count):
        self.db.cleanup_duplicates() # Run once after all emails are synced
        if count > 0:
            self.filter_emails_docs()

    def filter_emails_docs(self):
        # Clear Lists
        self._clear_layout(self.emails_layout)
        self._clear_layout(self.docs_layout)
        
        client_id = self.current_client_data['id'] if self.current_client_data else None
        
        # Load Communication History
        comms = self.db.get_communication_history(client_id)
        
        doc_count = 0
        
        for comm in comms:
            # 1. Add Email Item
            # Parse DB dict back to UI format
            email_ui_data = {
                'sender': comm['sender_email'],
                'subject': comm['subject'],
                'date': comm['received_at'],
                'body': comm['content'], # Needed for detail view
                'attachments': json.loads(comm.get('attachments_json', '[]') or '[]')
            }
            item = EmailListItem(email_ui_data)
            item.clicked.connect(self.open_email_details)
            self.emails_layout.addWidget(item)
            
            # 2. Add Docs from attachments
            for att in email_ui_data['attachments']:
                # FIX: Handle potential dirty data (string vs dict)
                if isinstance(att, dict):
                    att_name = att.get('name', 'Anexo sem nome')
                    att_size = att.get('size', 0)
                else:
                    att_name = str(att)
                    att_size = 0

                doc_ui_data = {
                    'name': att_name,
                    'size_str': f"{att_size/1024:.1f} KB",
                    'date': comm['received_at'],
                    'client_id': comm.get('client_id'), 
                    'path': "",
                    'drive_link': att.get('drive_link') if isinstance(att, dict) else None,
                    'comm_id': comm['id'] # For binary retrieval
                }
                d_item = DocumentRowItem(doc_ui_data)
                d_item.convert_requested.connect(self.open_convert_dialog)
                d_item.convert_to_pavement_requested.connect(self.open_pavement_convert_dialog)
                d_item.download_requested.connect(self.download_attachment)
                self.docs_layout.addWidget(d_item)
                doc_count += 1

        # 3. Add Permanent Work Documents
        # If a project is selected, or we have a context, we can show work docs
        # Here we use work_name if available in UI (e.g. from main window sync)
        # For now, let's try to infer work from the client context if possible
        # but the best way is to check the Main Window's current work.
        if hasattr(self.parent(), 'cmb_works'):
            work_name = self.parent().cmb_works.currentText()
            if work_name:
                work_docs = self.db.get_work_documents(work_name)
                for wd in work_docs:
                    doc_ui_data = {
                        'name': wd['name'],
                        'size_str': "Local",
                        'date': wd['created_at'],
                        'client_id': client_id,
                        'path': wd['file_path'],
                        'db_doc_id': wd['id'] # Permanent doc
                    }
                    d_item = DocumentRowItem(doc_ui_data)
                    d_item.convert_requested.connect(self.open_convert_dialog)
                    d_item.convert_to_pavement_requested.connect(self.open_pavement_convert_dialog)
                    d_item.download_requested.connect(self.download_attachment)
                    self.docs_layout.addWidget(d_item)
                    doc_count += 1

        self.card_docs.value_lbl.setText(str(doc_count))

    def open_email_details(self, email_data):
        """Abre dialogo com detalhes do email."""
        dlg = EmailDetailDialog(email_data, self)
        dlg.exec()

    def load_team_tracking(self):
        self._clear_layout(self.team_layout)
        
        users = []
        if self.auth_service:
            users = self.auth_service.get_all_users()
        else:
            users = self.db.get_team_members() # Fallback
            
        for u in users:
            # Convert to dict if object
            if hasattr(u, 'to_dict'): u_data = u.to_dict()
            elif hasattr(u, '__dict__'): u_data = u.__dict__
            else: u_data = u
            
            row = UserStatusRow(u_data)
            self.team_layout.addWidget(row)

    def open_new_client_dialog(self):
        dlg = CreateClientDialog(self.db, self)
        if dlg.exec_():
            self.load_clients() # Refresh list

    def open_convert_dialog(self, doc_data):
        dlg = ConvertDocDialog(doc_data, self.db, self)
        dlg.exec_()

    def open_pavement_convert_dialog(self, doc_data):
        dlg = ConvertToPavementDialog(doc_data, self.db, self)
        dlg.exec_()

    def download_attachment(self, doc_data):
        """Baixa anexo ou abre link do Drive."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        import logging

        logging.info(f"Download solicitado para: {doc_data}")
        
        # 1. Drive Link
        if doc_data.get('drive_link'):
            url = doc_data['drive_link']
            logging.info(f"Abrindo link do Drive: {url}")
            QDesktopServices.openUrl(QUrl(url))
            return

        # 2. Local File or Virtual
        if doc_data.get('path'):
            QDesktopServices.openUrl(QUrl.fromLocalFile(doc_data['path']))
            return

        # 3. Virtual Binary (Base64 in DB)
        comm_id = doc_data.get('comm_id')
        filename = doc_data.get('name')
        
        if comm_id and filename:
            b64_data = self.db.get_attachment_data(comm_id, filename)
            if b64_data:
                save_path, _ = QFileDialog.getSaveFileName(self, "Salvar Anexo", filename)
                if save_path:
                    try:
                        import base64
                        with open(save_path, 'wb') as f:
                            f.write(base64.b64decode(b64_data))
                        QMessageBox.information(self, "Download", f"Arquivo salvo com sucesso em:\n{save_path}")
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", f"Falha ao salvar arquivo: {e}")
                return

        # Fallback for old records or missing data
        QMessageBox.information(self, "Download", 
            "Este anexo é virtual e não possui dados binários cacheados ou link do Drive disponível.\n\n"
            "Anexos antigos podem não ter sido salvos com conteúdo binário.")

    def update_summary_metrics(self):
        # Update metrics cards logic
        pass

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
