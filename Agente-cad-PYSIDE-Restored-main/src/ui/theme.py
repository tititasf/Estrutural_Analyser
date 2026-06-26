"""
theme.py — Design tokens centralizados Vision-Estrutural AI
Paleta escura industrial com acentos ciano/azul.

USO:
    from src.ui.theme import Colors, Fonts, Spacing, StyleSheets

    widget.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY};")
    tabs.setStyleSheet(StyleSheets.tab_widget())
"""


class Colors:
    """Paleta de cores unificada. Substitui ~40 valores hex inline."""

    # Backgrounds
    BG_PRIMARY = "#1a1a2e"       # fundo principal (app)
    BG_SECONDARY = "#16213e"     # paineis secundarios (sidebar, header)
    BG_PANEL = "#1e1e1e"         # paineis internos
    BG_CARD = "#252525"          # cards, items, inputs
    BG_HOVER = "#2a2a3e"         # hover state
    BG_SURFACE = "#252528"       # headers, list backgrounds
    BG_DEEP = "#121212"          # fundo mais escuro (login, main window)

    # Accent
    ACCENT_PRIMARY = "#00d4ff"   # ciano principal (links, selected, highlights)
    ACCENT_BRAND = "#00E5FF"     # ciano brand (logo, email — ligeiramente mais claro)
    ACCENT_BLUE = "#0078d4"      # azul MS (botoes primarios, tabs selected)
    ACCENT_BLUE_HOVER = "#0099ff"  # hover do azul
    ACCENT_SUCCESS = "#4caf50"   # verde sucesso
    ACCENT_SUCCESS_ALT = "#00cc66"  # verde validacao
    ACCENT_WARNING = "#ff9800"   # laranja aviso
    ACCENT_WARNING_ALT = "#ffb300"  # laranja headers
    ACCENT_DANGER = "#f44336"    # vermelho erro
    ACCENT_DANGER_ALT = "#f85149"  # vermelho GitHub style
    ACCENT_GOLD = "#FFD700"      # admin badge, gold items
    ACCENT_INFO = "#e3b341"      # info/nota (amarelo)
    ACCENT_TEAL = "#00bcd4"      # teal (sections, links manager)
    ACCENT_MINT = "#00ffcc"      # mint (add buttons, special groups)
    ACCENT_MAGENTA = "#d63384"   # magenta (sync buttons, training log)
    ACCENT_FOREST = "rgba(26, 74, 26, 1)"   # verde escuro (pipeline buttons SA)
    ACCENT_FOREST_BORDER = "rgba(46, 125, 50, 1)"  # borda verde escuro
    ACCENT_PURPLE = "#a070ff"           # roxo (overlay ativo, canvas active state)
    ACCENT_LINK_PURPLE = "#d500f9"      # roxo vibrante (indicador vínculos, progress bars)
    ACCENT_SLATE = "#6c7293"            # cinza-azulado (botões secundários, ações neutras)
    BG_DANGER_DARK = "#332222"          # fundo vermelho escuro (hover delete, danger btn)
    BORDER_TEAL_DARK = "#2a4654"        # borda azul-teal escuro (card principal)

    # Transparências
    GLASS_WHITE_3 = "rgba(255, 255, 255, 8)"   # frosted glass sutil (stats frames)
    GLASS_WHITE_5 = "rgba(255, 255, 255, 13)"   # frosted glass médio
    GLASS_WHITE_10 = "rgba(255, 255, 255, 26)"  # frosted glass forte

    # Text
    TEXT_PRIMARY = "#e0e0e0"     # texto principal
    TEXT_BRIGHT = "#ffffff"      # texto enfase maxima
    TEXT_SECONDARY = "#888888"   # texto secundario / labels
    TEXT_MUTED = "#555555"       # texto desabilitado / footer
    TEXT_DIM = "#666666"         # texto sutil
    TEXT_LINK = "#00d4ff"        # links (== ACCENT_PRIMARY)

    # Borders
    BORDER_DEFAULT = "#333333"   # borda padrao
    BORDER_SUBTLE = "#2a2a2a"    # borda suave (item separators)
    BORDER_ACCENT = "#00d4ff"    # borda destaque
    BORDER_PANEL = "#2d2d30"     # borda paineis (metric cards)
    BORDER_INPUT = "#444444"     # borda inputs, botoes secundarios


class Fonts:
    """Tamanhos e familias tipograficas."""

    SIZE_XS = "9px"
    SIZE_SM = "10px"
    SIZE_MD = "11px"
    SIZE_LG = "12px"
    SIZE_XL = "13px"
    SIZE_XXL = "14px"
    SIZE_TITLE = "16px"
    SIZE_HERO = "20px"

    FAMILY = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
    FAMILY_MONO = "'Consolas', monospace"


class Spacing:
    """
    Espacamento padronizado em pixels (int).

    Hierarquia:
        DENSE (4)  → grupos de botões, linhas de detalhe
        BASE  (8)  → espaçamento padrão entre itens
        LOOSE (12) → separadores de seção
        LARGE (16) → seções maiores
        OUTER (20) → margens de container externo
        SECTION (25) → reservado para project_manager (uso controlado)

    Margens de container (setContentsMargins):
        INNER  = (16, 16, 16, 16)  → painéis internos
        OUTER  = (20, 20, 20, 20)  → containers principais
        TIGHT  = (8,  8,  8,  8)   → cards compactos
        ZERO   = (0,  0,  0,  0)   → sem margem (encaixe flush)
    """
    # Valores escalares para setSpacing()
    DENSE   = 4
    BASE    = 8
    LOOSE   = 12
    LARGE   = 16
    OUTER   = 20

    # Aliases legados (mantidos por compatibilidade)
    XS = 2
    SM = 4
    MD = 6
    LG = 8
    XL = 10
    XXL = 12
    XXXL = 16
    SECTION = 20

    # Tuplas para setContentsMargins()
    MARGINS_ZERO  = (0,  0,  0,  0)
    MARGINS_TIGHT = (8,  8,  8,  8)
    MARGINS_INNER = (16, 16, 16, 16)
    MARGINS_OUTER = (20, 20, 20, 20)


class Radius:
    """Border-radius padronizados."""

    SM = "3px"
    MD = "4px"
    LG = "6px"
    XL = "8px"
    PILL = "12px"
    CIRCLE = "50%"


class StyleSheets:
    """Snippets QSS reutilizaveis compostos a partir dos tokens."""

    @staticmethod
    def tab_widget():
        return f"""
QTabWidget::pane {{
    background: {Colors.BG_PANEL};
    border: 1px solid {Colors.BORDER_DEFAULT};
}}
QTabBar::tab {{
    background: {Colors.BG_PANEL};
    color: {Colors.TEXT_SECONDARY};
    padding: 8px 15px;
    border: 1px solid {Colors.BORDER_DEFAULT};
    margin-right: 2px;
    font-size: {Fonts.SIZE_MD};
}}
QTabBar::tab:selected {{
    background: {Colors.BG_CARD};
    color: {Colors.TEXT_BRIGHT};
    border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
}}
QTabBar::tab:hover {{
    background: {Colors.BG_HOVER};
    color: {Colors.TEXT_PRIMARY};
}}
"""

    @staticmethod
    def button_primary():
        return f"""
QPushButton {{
    background: {Colors.ACCENT_BLUE};
    color: {Colors.TEXT_BRIGHT};
    border: none;
    padding: 8px 16px;
    font-size: {Fonts.SIZE_MD};
    font-weight: bold;
    border-radius: {Radius.LG};
}}
QPushButton:hover {{
    background: {Colors.ACCENT_BLUE_HOVER};
}}
QPushButton:pressed {{
    background: #005A9E;
}}
QPushButton:disabled {{
    color: {Colors.TEXT_MUTED};
    background: {Colors.BG_CARD};
}}
"""

    @staticmethod
    def button_secondary():
        return f"""
QPushButton {{
    background: {Colors.BG_CARD};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.BORDER_INPUT};
    padding: 5px 10px;
    font-size: {Fonts.SIZE_MD};
    border-radius: {Radius.MD};
}}
QPushButton:hover {{
    background: #3a3a3a;
    border-color: {Colors.BORDER_DEFAULT};
}}
QPushButton:pressed {{
    background: #202020;
}}
"""

    @staticmethod
    def button_accent():
        return f"""
QPushButton {{
    background: {Colors.BG_CARD};
    color: {Colors.ACCENT_PRIMARY};
    border: 1px solid {Colors.ACCENT_PRIMARY};
    padding: 4px 8px;
    font-size: {Fonts.SIZE_MD};
    border-radius: {Radius.SM};
}}
QPushButton:hover {{
    background: {Colors.ACCENT_PRIMARY};
    color: {Colors.BG_PRIMARY};
}}
QPushButton:disabled {{
    color: {Colors.TEXT_MUTED};
    border-color: {Colors.BORDER_DEFAULT};
}}
"""

    @staticmethod
    def panel():
        return f"""
QWidget {{
    background: {Colors.BG_PANEL};
}}
QLabel {{
    color: {Colors.TEXT_PRIMARY};
    font-size: {Fonts.SIZE_MD};
}}
"""

    @staticmethod
    def sidebar():
        return f"""
QWidget {{
    background: {Colors.BG_PANEL};
    border-right: 1px solid {Colors.BORDER_DEFAULT};
}}
QTreeWidget {{
    background: transparent;
    color: {Colors.TEXT_PRIMARY};
    border: none;
    font-size: {Fonts.SIZE_LG};
}}
QTreeWidget::item {{
    padding: 8px;
    border-bottom: 1px solid {Colors.BORDER_SUBTLE};
}}
QTreeWidget::item:hover {{
    background: {Colors.BG_HOVER};
}}
QTreeWidget::item:selected {{
    background: {Colors.BG_HOVER};
    color: {Colors.ACCENT_PRIMARY};
}}
"""

    @staticmethod
    def list_widget():
        return f"""
QListWidget {{
    background: {Colors.BG_SURFACE};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.BORDER_INPUT};
    border-radius: {Radius.MD};
    font-size: {Fonts.SIZE_SM};
}}
QListWidget::item:hover {{
    background: {Colors.BG_HOVER};
}}
QListWidget::item:selected {{
    background: {Colors.BG_SECONDARY};
    color: {Colors.ACCENT_PRIMARY};
}}
"""

    @staticmethod
    def combo_box():
        return f"""
QComboBox {{
    background: {Colors.BG_CARD};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.BORDER_DEFAULT};
    padding: 4px 6px;
    font-size: {Fonts.SIZE_MD};
    border-radius: {Radius.SM};
}}
QComboBox:hover {{
    border-color: {Colors.ACCENT_PRIMARY};
}}
QComboBox:focus {{
    border-color: {Colors.ACCENT_PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background: {Colors.BG_CARD};
    color: {Colors.TEXT_PRIMARY};
    selection-background-color: {Colors.BG_HOVER};
}}
"""

    @staticmethod
    def progress_bar():
        return f"""
QProgressBar {{
    background: {Colors.BG_CARD};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: {Radius.SM};
    text-align: center;
    color: {Colors.TEXT_PRIMARY};
    font-size: {Fonts.SIZE_SM};
    height: 14px;
}}
QProgressBar::chunk {{
    background: {Colors.ACCENT_PRIMARY};
    border-radius: 2px;
}}
"""

    @staticmethod
    def input_field():
        return f"""
QLineEdit, QTextEdit {{
    background: {Colors.BG_CARD};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: {Radius.SM};
    padding: 4px;
    color: {Colors.TEXT_PRIMARY};
    font-size: {Fonts.SIZE_XL};
}}
QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid {Colors.ACCENT_PRIMARY};
}}
"""

    @staticmethod
    def group_box():
        return f"""
QGroupBox {{
    font-size: {Fonts.SIZE_MD};
    font-weight: bold;
    color: {Colors.ACCENT_PRIMARY};
    border: 1px solid {Colors.BORDER_DEFAULT};
    margin-top: 5px;
    padding-top: 10px;
    border-radius: {Radius.XL};
}}
"""

    @staticmethod
    def scroll_area():
        return f"""
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    border: none;
    background: {Colors.BG_PANEL};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {Colors.BORDER_INPUT};
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""

    @staticmethod
    def dialog():
        return f"""
QDialog {{
    background-color: {Colors.BG_DEEP};
    color: {Colors.TEXT_PRIMARY};
    font-family: {Fonts.FAMILY};
}}
QLabel {{
    color: {Colors.TEXT_SECONDARY};
    font-size: {Fonts.SIZE_MD};
}}
"""


# ──────────────────────────────────────────────────────────────────────────────
# WIDGETS REUTILIZÁVEIS DE ESTADO
# Importar: from src.ui.theme import EmptyStateWidget, LoadingStateWidget
# ──────────────────────────────────────────────────────────────────────────────

def _make_empty_state(parent=None, message: str = "Nenhum dado disponível",
                      icon: str = "○", detail: str = ""):
    """
    Cria um widget padronizado de estado vazio para uso em qualquer aba.

    Uso:
        empty = _make_empty_state(message="Nenhum projeto carregado",
                                   icon="📂", detail="Selecione uma obra.")
        layout.addWidget(empty)
    """
    try:
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
        from PySide6.QtCore import Qt

        w = QWidget(parent)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(*Spacing.MARGINS_OUTER)
        lay.setSpacing(Spacing.BASE)
        lay.setAlignment(Qt.AlignCenter)

        lbl_icon = QLabel(icon)
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 32px; background: transparent;"
        )

        lbl_msg = QLabel(message)
        lbl_msg.setAlignment(Qt.AlignCenter)
        lbl_msg.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_XL}; "
            f"font-weight: bold; background: transparent;"
        )

        lay.addWidget(lbl_icon)
        lay.addWidget(lbl_msg)

        if detail:
            lbl_detail = QLabel(detail)
            lbl_detail.setAlignment(Qt.AlignCenter)
            lbl_detail.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: {Fonts.SIZE_MD}; "
                f"background: transparent;"
            )
            lay.addWidget(lbl_detail)

        return w
    except ImportError:
        return None  # Sem PySide6 no contexto (testes headless)


def _make_loading_state(parent=None, message: str = "Carregando..."):
    """
    Cria um widget padronizado de loading com barra de progresso indeterminada.

    Uso:
        loading = _make_loading_state(message="Processando DXF...")
        layout.addWidget(loading)
        # Para remover: layout.removeWidget(loading); loading.deleteLater()
    """
    try:
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
        from PySide6.QtCore import Qt

        w = QWidget(parent)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(*Spacing.MARGINS_OUTER)
        lay.setSpacing(Spacing.LOOSE)
        lay.setAlignment(Qt.AlignCenter)

        lbl = QLabel(message)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_XL}; "
            f"background: transparent;"
        )

        bar = QProgressBar()
        bar.setRange(0, 0)  # indeterminate
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: {Colors.BG_CARD};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {Colors.ACCENT_PRIMARY};
                border-radius: 2px;
            }}
        """)

        lay.addWidget(lbl)
        lay.addWidget(bar)
        return w
    except ImportError:
        return None


# Aliases públicos
EmptyStateWidget = _make_empty_state
LoadingStateWidget = _make_loading_state
