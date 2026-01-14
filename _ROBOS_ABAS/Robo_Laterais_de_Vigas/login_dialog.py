import sys
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox, QFrame, QCheckBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon, QLinearGradient, QColor, QPalette

class LoginDialog(QDialog):
    login_successful = Signal(dict)

    def __init__(self, licensing_service, parent=None):
        super().__init__(parent)
        self.licensing_service = licensing_service
        self.setWindowTitle("Login - Sistema Robo")
        self.setFixedSize(400, 500)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.init_ui()

    def init_ui(self):
        # Main Container with Rounded Corners and Shadow style
        self.container = QFrame(self)
        self.container.setGeometry(10, 10, 380, 480)
        self.container.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-radius: 20px;
                border: 1px solid #333;
            }
        """)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Close Button
        self.btn_close = QPushButton("×", self.container)
        self.btn_close.setGeometry(340, 10, 30, 30)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666;
                font-size: 20px;
                border: none;
            }
            QPushButton:hover {
                color: #ff4d4d;
            }
        """)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.reject)

        # Title
        lbl_title = QLabel("ROBO VIGAS")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("""
            QLabel {
                color: #4FC3F7;
                font-size: 24pt;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(lbl_title)

        lbl_subtitle = QLabel("Acesso ao Sistema")
        lbl_subtitle.setAlignment(Qt.AlignCenter)
        lbl_subtitle.setStyleSheet("color: #888; font-size: 10pt; background: transparent; border: none;")
        layout.addWidget(lbl_subtitle)

        layout.addSpacing(20)

        # Inputs
        self.edt_email = QLineEdit()
        self.edt_email.setPlaceholderText("E-mail")
        self._style_input(self.edt_email)
        layout.addWidget(self.edt_email)

        self.edt_password = QLineEdit()
        self.edt_password.setPlaceholderText("Senha")
        self.edt_password.setEchoMode(QLineEdit.Password)
        self._style_input(self.edt_password)
        layout.addWidget(self.edt_password)

        # Remember Me Checkbox
        self.chk_remember = QCheckBox("Lembrar-me")
        self.chk_remember.setStyleSheet("""
            QCheckBox {
                color: #888;
                font-size: 9pt;
                background: transparent;
                border: none;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #444;
                background-color: #262626;
            }
            QCheckBox::indicator:checked {
                background-color: #4FC3F7;
                border: 1px solid #4FC3F7;
            }
        """)
        self.chk_remember.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.chk_remember)

        layout.addSpacing(10)

        # Login Button
        self.btn_login = QPushButton("ENTRAR")
        self.btn_login.setFixedHeight(50)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #4FC3F7;
                color: #000;
                font-weight: bold;
                border-radius: 10px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #81D4FA;
            }
            QPushButton:pressed {
                background-color: #039BE5;
            }
        """)
        self.btn_login.clicked.connect(self.handle_login)
        self.btn_login.setDefault(True) # Faz o ENTER disparar o login
        layout.addWidget(self.btn_login)

        # Status Label
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #ff4d4d; font-size: 9pt; background: transparent; border: none;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        # Check for existing session
        if self.licensing_service.load_session():
            session_data = self.licensing_service.user_data
            if session_data:
                self.edt_email.setText(session_data.get('email', ''))
                self.edt_password.setText(session_data.get('saved_password', ''))
                self.chk_remember.setChecked(True)
                self.lbl_status.setText(f"Bem-vindo de volta, {session_data.get('nome', '')}")
                self.lbl_status.setStyleSheet("color: #4CAF50; font-size: 9pt; background: transparent; border: none;")

    def _style_input(self, widget):
        widget.setFixedHeight(45)
        widget.setStyleSheet("""
            QLineEdit {
                background-color: #262626;
                color: white;
                border: 1px solid #444;
                border-radius: 10px;
                padding-left: 15px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #4FC3F7;
            }
        """)

    def handle_login(self):
        email = self.edt_email.text()
        password = self.edt_password.text()

        if not email or not password:
            self.lbl_status.setText("Preencha todos os campos.")
            return

        self.btn_login.setEnabled(False)
        self.btn_login.setText("VERIFICANDO...")
        
        # In actual production, we should use a thread for the network request
        # For simplicity in this step, we call directly (GAS usually returns in < 2s)
        try:
            success, message = self.licensing_service.login(email, password)
            if success:
                if self.chk_remember.isChecked():
                    if self.licensing_service.user_data:
                        self.licensing_service.user_data['saved_password'] = password
                    self.licensing_service.save_session()
                else:
                    self.licensing_service.logout()
                
                self.login_successful.emit(self.licensing_service.user_data)
                self.accept()
            else:
                self.lbl_status.setText(message)
                self.btn_login.setEnabled(True)
                self.btn_login.setText("ENTRAR")
        except Exception as e:
            self.lbl_status.setText(f"Erro de conexão: {str(e)}")
            self.btn_login.setEnabled(True)
            self.btn_login.setText("ENTRAR")

    # Mouse drag events for frameless window
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()
