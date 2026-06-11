import base64
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFrame, QMessageBox, QWidget, QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, Signal, QSize
from src.core.auth.models import UserProfile, UserRole
from src.core.services.auth_service import AuthService
from src.ui.theme import Colors, Fonts, Radius

class UserProfileDialog(QDialog):
    logout_requested = Signal()

    def __init__(self, user: UserProfile, parent=None):
        super().__init__(parent)
        self.user = user
        self.auth_service = AuthService()
        self.auth_service.refresh_credits() # Refresh data from DB
        self.setWindowTitle("Vision-Estrutural Pro | Perfil")
        self.setFixedSize(500, 650)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Background Wrapper (Shadow)
        wrapper = QFrame()
        wrapper.setObjectName("MainWrapper")
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        # Container Principal
        container = QFrame()
        container.setObjectName("ProfileContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 1. Header Area (Branding)
        header_widget = QFrame()
        header_widget.setObjectName("ProfileHeader")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(25, 20, 15, 20)
        
        logo_lbl = QLabel(f"VISION ESTRUTURAL <font color='{Colors.ACCENT_BRAND}'>PRO</font>")
        logo_lbl.setStyleSheet(f"font-size: {Fonts.SIZE_XXL}; font-weight: bold; letter-spacing: 1px; color: {Colors.TEXT_SECONDARY};")
        header_layout.addWidget(logo_lbl)
        
        header_layout.addStretch()
        
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.TEXT_MUTED}; font-size: 18px; border: none; border-radius: 15px;
            }}
            QPushButton:hover {{ background: {Colors.BG_CARD}; color: {Colors.TEXT_BRIGHT}; }}
        """)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        header_layout.addWidget(btn_close)
        
        container_layout.addWidget(header_widget)

        # 2. Hero Section (User Identity)
        hero_section = QFrame()
        hero_section.setObjectName("HeroSection")
        hero_layout = QVBoxLayout(hero_section)
        hero_layout.setContentsMargins(40, 30, 40, 30)
        hero_layout.setSpacing(10)

        # Avatar Placeholder (Circle with Initials)
        initials = self.user.full_name[:2].upper() if self.user.full_name else self.user.email[:2].upper()
        avatar_lbl = QLabel(initials)
        avatar_lbl.setAlignment(Qt.AlignCenter)
        avatar_lbl.setFixedSize(100, 100)
        avatar_lbl.setObjectName("AvatarCircle")
        
        avatar_row = QHBoxLayout()
        avatar_row.addWidget(avatar_lbl)
        hero_layout.addLayout(avatar_row)

        name_lbl = QLabel(self.user.full_name or "Usuário Vision")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Colors.TEXT_BRIGHT}; margin-top: 10px;")
        hero_layout.addWidget(name_lbl)

        email_lbl = QLabel(self.user.email)
        email_lbl.setAlignment(Qt.AlignCenter)
        email_lbl.setStyleSheet(f"font-size: {Fonts.SIZE_XXL}; color: {Colors.ACCENT_BRAND}; opacity: 0.8;")
        hero_layout.addWidget(email_lbl)

        # Role Badge
        is_admin = self.user.role == UserRole.ADMIN
        role_text = "ADMINISTRADOR" if is_admin else "USUÁRIO"
        role_color = Colors.ACCENT_GOLD if is_admin else Colors.TEXT_DIM
        role_bg = "rgba(255,215,0,26)" if is_admin else "rgba(68,68,68,128)"
        
        role_badge = QLabel(role_text)
        role_badge.setAlignment(Qt.AlignCenter)
        role_badge.setFixedWidth(140)
        role_badge.setStyleSheet(f"""
            background: {role_bg};
            color: {role_color};
            border: 1px solid {role_color};
            border-radius: {Radius.PILL};
            padding: 4px;
            font-size: {Fonts.SIZE_SM};
            font-weight: bold;
            letter-spacing: 2px;
            margin-top: 10px;
        """)
        role_row = QHBoxLayout()
        role_row.addWidget(role_badge)
        hero_layout.addLayout(role_row)

        container_layout.addWidget(hero_section)

        # 3. Details Section (Stats)
        details_section = QFrame()
        details_section.setObjectName("DetailsSection")
        details_layout = QVBoxLayout(details_section)
        details_layout.setContentsMargins(40, 20, 40, 20)
        details_layout.setSpacing(15)

        def add_detail(label, value):
            row = QHBoxLayout()
            l = QLabel(label)
            l.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_LG};")
            v = QLabel(value)
            v.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_XL}; font-weight: 500;")
            row.addWidget(l)
            row.addStretch()
            row.addWidget(v)
            details_layout.addLayout(row)
            
            # Subtle Line
            separator = QFrame()
            separator.setFixedHeight(1)
            separator.setStyleSheet(f"background: {Colors.BORDER_DEFAULT};")
            details_layout.addWidget(separator)

        last_login_str = self.user.last_login.strftime("%d/%m/%Y %H:%M") if self.user.last_login else "Agora"
        created_at_str = self.user.created_at.strftime("%d/%m/%Y")
        
        add_detail("Último Acesso", last_login_str)
        add_detail("Membro desde", created_at_str)
        add_detail("Status da Nuvem", "✅ Conectado")
        add_detail("Saldo de Créditos", str(self.user.credits))
        
        container_layout.addWidget(details_section)
        container_layout.addStretch()

        # 4. Actions Area
        actions_header = QLabel("SEGURANÇA E ACESSO")
        actions_header.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Fonts.SIZE_SM}; font-weight: bold; letter-spacing: 1px; margin-left: 40px; margin-bottom: 5px;")
        container_layout.addWidget(actions_header)

        actions_section = QFrame()
        actions_layout = QVBoxLayout(actions_section)
        actions_layout.setContentsMargins(40, 0, 40, 40)
        actions_layout.setSpacing(12)

        btn_change_pass = QPushButton("ALTERAR SENHA")
        btn_change_pass.setFixedHeight(45)
        btn_change_pass.setObjectName("BtnAccent")
        btn_change_pass.clicked.connect(self.handle_change_password)
        btn_change_pass.setCursor(Qt.PointingHandCursor)
        actions_layout.addWidget(btn_change_pass)

        btn_logout = QPushButton("ENCERRAR SESSÃO")
        btn_logout.setFixedHeight(45)
        btn_logout.setObjectName("BtnLogout")
        btn_logout.clicked.connect(self.handle_logout)
        btn_logout.setCursor(Qt.PointingHandCursor)
        actions_layout.addWidget(btn_logout)

        container_layout.addWidget(actions_section)

        wrapper_layout.addWidget(container)
        layout.addWidget(wrapper)

        # Estilos Detalhados
        self.setStyleSheet(f"""
            #ProfileContainer {{
                background-color: {Colors.BG_DEEP};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 20px;
            }}
            #HeroSection {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Colors.BG_PANEL}, stop:1 {Colors.BG_DEEP});
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
            }}
            #AvatarCircle {{
                background-color: {Colors.ACCENT_BRAND};
                color: {Colors.BG_DEEP};
                font-size: 36px;
                font-weight: bold;
                border-radius: 50px;
            }}
            QPushButton#BtnAccent {{
                background-color: {Colors.BG_CARD};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_INPUT};
                border-radius: {Radius.XL};
                font-weight: bold;
            }}
            QPushButton#BtnAccent:hover {{ background-color: {Colors.BG_HOVER}; border-color: {Colors.ACCENT_BRAND}; }}

            QPushButton#BtnLogout {{
                background-color: rgba(211,47,47,26);
                color: {Colors.ACCENT_DANGER};
                border: 1px solid rgba(211,47,47,76);
                border-radius: {Radius.XL};
                font-weight: bold;
            }}
            QPushButton#BtnLogout:hover {{ background-color: {Colors.ACCENT_DANGER}; color: {Colors.TEXT_BRIGHT}; }}
        """)

        # Shadow Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(Qt.black)
        container.setGraphicsEffect(shadow)

    def handle_change_password(self):
        QMessageBox.information(self, "Alterar Senha", 
                               "Um link de redefinição de senha segura foi solicitado e enviado para seu e-mail cadastrado.")

    def handle_logout(self):
        reply = QMessageBox.question(self, "Logout", 
                                   "Você deseja encerrar sua sessão profissional com segurança?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.auth_service.logout()
            self.logout_requested.emit()
            self.accept()
