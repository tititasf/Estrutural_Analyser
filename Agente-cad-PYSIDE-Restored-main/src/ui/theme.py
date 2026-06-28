"""
theme.py — Design System v1.0 · CAD Analyzer – Vision Estrutural AI
Fonte da verdade para tokens de cor, tipografia, espaçamento, elevação e densidade.

HIERARQUIA DE CLASSES (usar em código novo):
  Surface    — 5 níveis de fundo (L0–L4)
  Accent     — Primary (estado/foco) · Interactive (ação) · Brand
  Semantic   — Success / Warning / Danger / Info + variantes subtle
  Contextual — Purple (IA) · Gold (Admin) · Magenta (data-viz) · Slate (chrome)
  Text       — Bright / Primary / Secondary / Muted
  Border     — Strong / Default / Subtle
  Fonts      — 8 roles semânticos + escala numérica legada
  Spacing    — Escala base-4 (s2…s32) + aliases semânticos/legados
  Density    — COMPACT / DEFAULT / COMFORTABLE
  Elevation  — L0–L5 com surface + separação QSS
  Radius     — Border-radius padronizados

  Colors     — Aliases legados (backward compat) → apontam para tokens acima.
               NÃO adicionar novos atributos aqui; usar as classes acima.
  StyleSheets — Snippets QSS reutilizáveis compostos a partir dos tokens

USO:
    # Código novo
    from src.ui.theme import Surface, Accent, Semantic, Text, Fonts, Spacing

    # Código existente (continua funcionando)
    from src.ui.theme import Colors, Fonts, Spacing, StyleSheets
"""


# ══════════════════════════════════════════════════════════════════════════════
# 1. SURFACE HIERARCHY  (5 níveis · luz sobe)
# ══════════════════════════════════════════════════════════════════════════════

class Surface:
    """
    Cinco níveis de superfície. Quanto mais "alto" na pilha Z, mais claro.
    Navy (#1a1a2e / #16213e) = chrome estrutural da app (moldura, nunca dado).
    Cinza (#252525 / #2a2a3e) = conteúdo manipulável (cards, inputs, dialogs).
    """
    DEEP     = "#121212"  # L0 — canvas, main window, login
    BASE     = "#1a1a2e"  # L2 — painéis, conteúdo de aba
    RAISED   = "#16213e"  # L1 — sidebar, header bar, tab strip
    CARD     = "#252525"  # L3 — cards, inputs, list items
    ELEVATED = "#2a2a3e"  # L4/L5 — dialogs, popovers, hover state, toasts


# ══════════════════════════════════════════════════════════════════════════════
# 2. ACCENT HIERARCHY  (3 tiers)
# ══════════════════════════════════════════════════════════════════════════════

class Accent:
    """
    PRIMARY      = estado/seleção (ciano) — indica "onde estou". Nunca é botão clicável.
    INTERACTIVE  = ação clicável (azul MS) — indica "o que faço".
    BRAND        = identidade visual (splash/logo) — não usar em UI funcional.
    """
    PRIMARY           = "#00d4ff"  # seleção, foco, links, borda ativa
    INTERACTIVE       = "#0078d4"  # botão primário base
    INTERACTIVE_HOVER = "#0099ff"  # botão primário hover
    INTERACTIVE_PRESS = "#0064b5"  # botão primário pressed
    BRAND             = "#00E5FF"  # logo, splash — reservado (não usar em UI)


# ══════════════════════════════════════════════════════════════════════════════
# 3. SEMANTIC COLORS  (1 cor por significado + variante subtle)
# ══════════════════════════════════════════════════════════════════════════════

class Semantic:
    """
    Variantes _SUBTLE (~14% opacidade) são para fundo de badge/row — nunca para texto.
    Os tokens _ALT duplicados foram eliminados; todo uso aponta para a cor primária.
    """
    SUCCESS        = "#4caf50"
    SUCCESS_SUBTLE = "rgba(76, 175, 80, 36)"

    WARNING        = "#ff9800"
    WARNING_SUBTLE = "rgba(255, 152, 0, 36)"

    DANGER         = "#f44336"
    DANGER_SUBTLE  = "rgba(244, 67, 54, 36)"

    SUCCESS_BG_DARK = "#1a3320"  # dark green bg (table cells, row highlights)
    WARNING_BG_DARK = "#332900"  # dark amber bg
    DANGER_BG_DARK  = "#330d00"  # dark red bg
    NEUTRAL_BG_DARK = "#1a1a1a"  # neutral dark bg for absent/N.A.

    INFO           = "#00d4ff"   # mesmo que Accent.PRIMARY — dica neutra


# ══════════════════════════════════════════════════════════════════════════════
# 4. CONTEXTUAL COLORS  (namespace fixo — não reutilizar fora do escopo)
# ══════════════════════════════════════════════════════════════════════════════

class Contextual:
    """
    Cada cor tem um namespace exclusivo. Usar fora do namespace é proibido.

    PURPLE  → IA only   : AISuggestionBox, badges de sugestão de IA
    GOLD    → Admin only: badge de privilégio, itens premium
    MAGENTA → data-viz  : séries em gráfico, categorias de dados
    SLATE   → chrome    : ícones inativos, chips off, botões neutros
    """
    PURPLE  = "#a070ff"   # IA only
    GOLD    = "#e6b400"   # Ficha/Admin gold (amber — legível em fundo escuro)
    MAGENTA = "#d63384"   # data-viz only
    SLATE   = "#6c7293"   # chrome neutro

    # Backgrounds especializados (componentes existentes)
    FOREST           = "rgba(26, 74, 26, 1)"    # pipeline buttons SA
    FOREST_BORDER    = "rgba(46, 125, 50, 1)"   # borda verde escuro
    DANGER_DARK      = "#332222"                 # hover delete, danger btn
    BORDER_TEAL_DARK = "#2a4654"                 # card principal (legado)
    BORDER_GOLD_DARK = "#3a3000"                 # borda dark-amber para painéis de ficha

    # Glass / frosted
    GLASS_3  = "rgba(255, 255, 255, 8)"    # sutil
    GLASS_5  = "rgba(255, 255, 255, 13)"   # médio
    GLASS_10 = "rgba(255, 255, 255, 26)"   # forte


# ══════════════════════════════════════════════════════════════════════════════
# 5. TEXT  (4 níveis)
# ══════════════════════════════════════════════════════════════════════════════

class Text:
    """
    BRIGHT   → pontos de fixação (títulos, valores) — não usar em corpo.
    PRIMARY  → corpo padrão (reduz fadiga visual em sessões longas).
    SECONDARY→ labels, captions, metadados (~6:1 vs Surface.BASE = WCAG AA ok).
    MUTED    → disabled, placeholder — nunca carrega texto legível.
    """
    BRIGHT    = "#ffffff"   # títulos, valores em destaque
    PRIMARY   = "#e0e0e0"   # corpo, conteúdo padrão
    SECONDARY = "#9a9aa6"   # labels, captions, metadados (subiu de #888 para atingir 6:1)
    MUTED     = "#666666"   # disabled, placeholder — só decorativo


# ══════════════════════════════════════════════════════════════════════════════
# 6. BORDER  (3 níveis)
# ══════════════════════════════════════════════════════════════════════════════

class Border:
    """
    STRONG  → inputs e elementos foco-ready.
    DEFAULT → divisores e contorno de card.
    SUBTLE  → separadores internos discretos.
    """
    STRONG  = "#444444"   # input border, foco-ready
    DEFAULT = "#333333"   # divisores, contorno de card
    SUBTLE  = "#2a2a2a"   # separador interno discreto


# ══════════════════════════════════════════════════════════════════════════════
# 7. FONTS  (8 roles semânticos · piso = 11px)
# ══════════════════════════════════════════════════════════════════════════════

class Fonts:
    """
    Piso = 11px (CAPTION). Tamanhos 9px e 10px aposentados — ilegíveis em 1080p.
    Mono = sinal semântico de "dado preciso e copiável" (IDs, coords, hashes).

    QSS:  font-size: {Fonts.BODY}; font-weight: {Fonts.W_BODY};
    """
    # ── Roles semânticos ─────────────────────────────────────────────────────
    DISPLAY    = "20px"   # hero de página, título de módulo no header
    TITLE      = "16px"   # título de aba, nome de projeto em card
    HEADING    = "14px"   # cabeçalho de seção dentro de painel
    SUBHEADING = "13px"   # subtítulo, label de grupo
    BODY       = "13px"   # conteúdo padrão, descrições, mensagens
    LABEL      = "12px"   # label de campo em formulário / ficha N2
    CAPTION    = "11px"   # metadado, timestamp, contagem, rodapé de card
    MONO       = "13px"   # valores técnicos, IDs, coordenadas DXF

    # ── Pesos por role ───────────────────────────────────────────────────────
    W_DISPLAY    = "700"
    W_TITLE      = "700"
    W_HEADING    = "600"
    W_SUBHEADING = "600"
    W_BODY       = "400"
    W_LABEL      = "500"
    W_CAPTION    = "400"
    W_MONO       = "400"

    # ── Famílias ─────────────────────────────────────────────────────────────
    FAMILY      = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
    FAMILY_MONO = "'Consolas', monospace"

    # ── Aliases legados (backward compat — não usar em código novo) ───────────
    SIZE_XS    = "9px"    # APOSENTADO
    SIZE_SM    = "10px"   # APOSENTADO
    SIZE_MD    = "11px"   # → CAPTION
    SIZE_LG    = "12px"   # → LABEL
    SIZE_XL    = "13px"   # → BODY / SUBHEADING
    SIZE_XXL   = "14px"   # → HEADING
    SIZE_TITLE = "16px"   # → TITLE
    SIZE_HERO  = "20px"   # → DISPLAY


# ══════════════════════════════════════════════════════════════════════════════
# 8. SPACING  (escala base-4 · s2…s32)
# ══════════════════════════════════════════════════════════════════════════════

class Spacing:
    """
    Escala base-4. Nomes numéricos dizem exatamente quantos px (s8 = 8px).
    Todos múltiplos de 4 — alinhamento de pixel em layouts densos garantido.

    setSpacing():         Spacing.s8
    setContentsMargins(): *Spacing.MARGINS_TIGHT
    """
    # ── Escala base-4 ─────────────────────────────────────────────────────────
    s2  = 2    # hairline, ajuste óptico
    s4  = 4    # gap em tabela / lista densa
    s8  = 8    # gap padrão entre elementos
    s12 = 12   # padding de card, gap de grupo
    s16 = 16   # padding de painel
    s20 = 20   # margem externa de janela / dialog
    s24 = 24   # separação entre seções
    s32 = 32   # respiro de header / hero

    # ── Aliases semânticos → novos valores ───────────────────────────────────
    DENSE = s4
    BASE  = s8
    LOOSE = s12
    LARGE = s16
    OUTER = s20

    # ── Aliases legados (backward compat — valores originais preservados) ─────
    XS      = 2    # → s2
    SM      = 4    # → s4
    MD      = 6    # legado (não é base-4 — usar s8 em código novo)
    LG      = 8    # → s8
    XL      = 10   # legado (não é base-4 — usar s12 em código novo)
    XXL     = 12   # → s12
    XXXL    = 16   # → s16
    SECTION = 20   # → s20

    # ── Tuplas para setContentsMargins() ────────────────────────────────────
    MARGINS_ZERO      = (0,   0,   0,   0)
    MARGINS_COMPACT   = (s4,  s4,  s4,  s4)
    MARGINS_TIGHT     = (s8,  s8,  s8,  s8)
    MARGINS_INNER     = (s16, s16, s16, s16)
    MARGINS_OUTER     = (s20, s20, s20, s20)
    MARGINS_SECTION   = (s24, s24, s24, s24)


# ══════════════════════════════════════════════════════════════════════════════
# 9. DENSITY  (propriedade da tarefa, não preferência global)
# ══════════════════════════════════════════════════════════════════════════════

class Density:
    """
    COMPACT     → tabelas, listas de itens estruturais (padrão da app)
    DEFAULT     → cards de projeto, painéis de métricas
    COMFORTABLE → formulários, dialogs de edição (alvos 44px, menos erro de clique)
    """
    class COMPACT:
        ROW_HEIGHT = 26
        PADDING_V  = 4
        PADDING_H  = 8
        GAP        = 4

    class DEFAULT:
        ROW_HEIGHT = 36
        PADDING_V  = 8
        PADDING_H  = 12
        GAP        = 8

    class COMFORTABLE:
        ROW_HEIGHT = 44
        PADDING_V  = 12
        PADDING_H  = 16
        GAP        = 12


# ══════════════════════════════════════════════════════════════════════════════
# 10. ELEVATION  (QSS: brilho + borda, não box-shadow)
# ══════════════════════════════════════════════════════════════════════════════

class Elevation:
    """
    QSS não tem box-shadow real — profundidade = brilho de superfície + borda.
    L4/L5 podem usar QGraphicsDropShadowEffect(blur=24, color=#000A, yOffset=4).
    NUNCA DropShadowEffect por-item de lista (custo de render proibitivo).
    """
    L0 = Surface.DEEP      # canvas, main window
    L1 = Surface.RAISED    # sidebar, header bar
    L2 = Surface.BASE      # painéis, conteúdo de aba
    L3 = Surface.CARD      # cards, list items, inputs
    L4 = Surface.ELEVATED  # dialogs, popovers
    L5 = Surface.ELEVATED  # toasts, overlays modais

    # Bordas de separação por nível
    BORDER_L0 = "none"
    BORDER_L1 = Border.SUBTLE    # "#2a2a2a"
    BORDER_L2 = Border.DEFAULT   # "#333333"
    BORDER_L3 = Border.DEFAULT   # "#333333"
    BORDER_L4 = "#3a3a52"        # mais clara → simula elevação
    BORDER_L5 = Accent.PRIMARY   # borda accent em overlays modais


# ══════════════════════════════════════════════════════════════════════════════
# 11. RADIUS
# ══════════════════════════════════════════════════════════════════════════════

class Radius:
    """Border-radius padronizados."""
    SM     = "3px"
    MD     = "4px"
    LG     = "6px"
    XL     = "8px"
    PILL   = "12px"
    CIRCLE = "50%"


# ══════════════════════════════════════════════════════════════════════════════
# COLORS — aliases legados (backward compat)
# Todo atributo aponta para o token semântico correspondente.
# Migrar aos poucos: quando grep zerar para um nome, remover o alias.
# NÃO adicionar novos atributos aqui — usar as classes semânticas acima.
# ══════════════════════════════════════════════════════════════════════════════

class Colors:
    # ── Backgrounds → Surface ────────────────────────────────────────────────
    BG_PRIMARY   = Surface.BASE      # "#1a1a2e"
    BG_SECONDARY = Surface.RAISED    # "#16213e"
    BG_PANEL     = Surface.BASE      # "#1a1a2e"  (era #1e1e1e — consolidado em Base)
    BG_CARD      = Surface.CARD      # "#252525"
    BG_HOVER     = Surface.ELEVATED  # "#2a2a3e"
    BG_SURFACE   = Surface.CARD      # "#252525"  (era #252528 — diff imperceptível)
    BG_DEEP      = Surface.DEEP      # "#121212"

    # ── Accent → Accent + Semantic ───────────────────────────────────────────
    ACCENT_PRIMARY      = Accent.PRIMARY            # "#00d4ff"
    ACCENT_BRAND        = Accent.BRAND              # "#00E5FF"
    ACCENT_BLUE         = Accent.INTERACTIVE        # "#0078d4"
    ACCENT_BLUE_HOVER   = Accent.INTERACTIVE_HOVER  # "#0099ff"
    ACCENT_SUCCESS      = Semantic.SUCCESS           # "#4caf50"
    ACCENT_SUCCESS_ALT  = Semantic.SUCCESS           # ELIMINADO → aponta para SUCCESS
    ACCENT_WARNING      = Semantic.WARNING           # "#ff9800"
    ACCENT_WARNING_ALT  = Semantic.WARNING           # ELIMINADO → aponta para WARNING
    ACCENT_DANGER       = Semantic.DANGER            # "#f44336"
    ACCENT_DANGER_ALT   = Semantic.DANGER            # ELIMINADO → aponta para DANGER
    ACCENT_INFO         = Semantic.INFO              # "#00d4ff"
    ACCENT_TEAL         = Accent.PRIMARY             # ELIMINADO → aponta para PRIMARY
    ACCENT_MINT         = Semantic.SUCCESS           # ELIMINADO → aponta para SUCCESS

    # ── Contextual (mantidos com namespace fixo) ──────────────────────────────
    ACCENT_GOLD          = Contextual.GOLD            # Admin only
    ACCENT_MAGENTA       = Contextual.MAGENTA         # data-viz only
    ACCENT_PURPLE        = Contextual.PURPLE          # IA only
    ACCENT_SLATE         = Contextual.SLATE           # chrome neutro
    ACCENT_FOREST        = Contextual.FOREST
    ACCENT_FOREST_BORDER = Contextual.FOREST_BORDER
    BG_DANGER_DARK       = Contextual.DANGER_DARK
    BORDER_TEAL_DARK     = Contextual.BORDER_TEAL_DARK

    # ── Glass ────────────────────────────────────────────────────────────────
    GLASS_WHITE_3  = Contextual.GLASS_3
    GLASS_WHITE_5  = Contextual.GLASS_5
    GLASS_WHITE_10 = Contextual.GLASS_10

    # ── Text → Text ──────────────────────────────────────────────────────────
    TEXT_PRIMARY   = Text.PRIMARY    # "#e0e0e0"
    TEXT_BRIGHT    = Text.BRIGHT     # "#ffffff"
    TEXT_SECONDARY = Text.SECONDARY  # "#9a9aa6" (subiu de #888888 para ~6:1)
    TEXT_MUTED     = Text.MUTED      # "#666666"
    TEXT_DIM       = Text.MUTED      # CONSOLIDADO → MUTED
    TEXT_LINK      = Accent.PRIMARY  # "#00d4ff"

    # ── Borders → Border ─────────────────────────────────────────────────────
    BORDER_DEFAULT = Border.DEFAULT  # "#333333"
    BORDER_SUBTLE  = Border.SUBTLE   # "#2a2a2a"
    BORDER_ACCENT  = Accent.PRIMARY  # "#00d4ff"
    BORDER_PANEL   = Border.DEFAULT  # "#333333"
    BORDER_INPUT   = Border.STRONG   # "#444444"


# ══════════════════════════════════════════════════════════════════════════════
# STYLESHEETS — snippets QSS com todos os estados
# Regra: nenhum valor literal hex aqui — sempre via token.
# ══════════════════════════════════════════════════════════════════════════════

class StyleSheets:
    """Snippets QSS reutilizáveis. Compõem tokens — nunca valores literais."""

    @staticmethod
    def tab_widget():
        return f"""
QTabWidget::pane {{
    background: {Surface.BASE};
    border: 1px solid {Border.DEFAULT};
}}
QTabBar::tab {{
    background: {Surface.BASE};
    color: {Text.SECONDARY};
    padding: 8px 15px;
    border: 1px solid {Border.DEFAULT};
    margin-right: 2px;
    font-size: {Fonts.BODY};
}}
QTabBar::tab:selected {{
    background: {Surface.CARD};
    color: {Text.BRIGHT};
    border-bottom: 2px solid {Accent.PRIMARY};
}}
QTabBar::tab:hover {{
    background: {Surface.ELEVATED};
    color: {Text.PRIMARY};
}}
QTabBar::tab:focus {{
    border: 2px solid {Accent.PRIMARY};
}}
"""

    @staticmethod
    def button_primary():
        return f"""
QPushButton {{
    background: {Accent.INTERACTIVE};
    color: {Text.BRIGHT};
    border: none;
    padding: 7px 16px;
    font-size: {Fonts.BODY};
    font-weight: {Fonts.W_HEADING};
    border-radius: {Radius.LG};
}}
QPushButton:hover {{
    background: {Accent.INTERACTIVE_HOVER};
}}
QPushButton:pressed {{
    background: {Accent.INTERACTIVE_PRESS};
}}
QPushButton:focus {{
    border: 2px solid {Accent.PRIMARY};
    padding: 6px 15px;
}}
QPushButton:disabled {{
    color: {Text.MUTED};
    background: {Surface.CARD};
}}
"""

    @staticmethod
    def button_secondary():
        return f"""
QPushButton {{
    background: {Surface.CARD};
    color: {Text.PRIMARY};
    border: 1px solid {Border.STRONG};
    padding: 5px 10px;
    font-size: {Fonts.BODY};
    border-radius: {Radius.MD};
}}
QPushButton:hover {{
    background: {Surface.ELEVATED};
    border-color: {Border.DEFAULT};
}}
QPushButton:pressed {{
    background: {Surface.DEEP};
}}
QPushButton:focus {{
    border: 2px solid {Accent.PRIMARY};
    padding: 4px 9px;
}}
QPushButton:disabled {{
    color: {Text.MUTED};
    background: {Surface.CARD};
    border-color: {Border.SUBTLE};
}}
"""

    @staticmethod
    def button_accent():
        return f"""
QPushButton {{
    background: {Surface.CARD};
    color: {Accent.PRIMARY};
    border: 1px solid {Accent.PRIMARY};
    padding: 4px 8px;
    font-size: {Fonts.BODY};
    border-radius: {Radius.SM};
}}
QPushButton:hover {{
    background: {Accent.PRIMARY};
    color: {Surface.BASE};
}}
QPushButton:pressed {{
    background: {Accent.INTERACTIVE};
    color: {Text.BRIGHT};
    border-color: {Accent.INTERACTIVE};
}}
QPushButton:focus {{
    border: 2px solid {Accent.PRIMARY};
    padding: 3px 7px;
}}
QPushButton:disabled {{
    color: {Text.MUTED};
    border-color: {Border.DEFAULT};
    background: transparent;
}}
"""

    @staticmethod
    def button_ghost():
        """Botão sem peso visual — para ações secundárias e Cancel em dialogs."""
        return f"""
QPushButton {{
    background: transparent;
    color: {Text.SECONDARY};
    border: 1px solid transparent;
    padding: 5px 10px;
    font-size: {Fonts.BODY};
    border-radius: {Radius.MD};
}}
QPushButton:hover {{
    background: {Surface.ELEVATED};
    color: {Text.PRIMARY};
    border-color: {Border.SUBTLE};
}}
QPushButton:pressed {{
    background: {Surface.CARD};
}}
QPushButton:focus {{
    border: 2px solid {Accent.PRIMARY};
    padding: 4px 9px;
}}
QPushButton:disabled {{
    color: {Text.MUTED};
}}
"""

    @staticmethod
    def button_danger():
        """Botão destrutivo — para ações que iniciam exclusão na tela principal."""
        return f"""
QPushButton {{
    background: {Surface.CARD};
    color: {Semantic.DANGER};
    border: 1px solid {Semantic.DANGER};
    padding: 5px 10px;
    font-size: {Fonts.BODY};
    border-radius: {Radius.MD};
}}
QPushButton:hover {{
    background: {Contextual.DANGER_DARK};
    color: {Text.BRIGHT};
}}
QPushButton:pressed {{
    background: {Semantic.DANGER};
    color: {Text.BRIGHT};
}}
QPushButton:focus {{
    border: 2px solid {Semantic.DANGER};
    padding: 4px 9px;
}}
QPushButton:disabled {{
    color: {Text.MUTED};
    border-color: {Border.DEFAULT};
}}
"""

    @staticmethod
    def panel():
        return f"""
QWidget {{
    background: {Surface.BASE};
}}
QLabel {{
    color: {Text.PRIMARY};
    font-size: {Fonts.BODY};
}}
"""

    @staticmethod
    def sidebar():
        return f"""
QWidget {{
    background: {Surface.RAISED};
    border-right: 1px solid {Border.SUBTLE};
}}
QTreeWidget {{
    background: transparent;
    color: {Text.PRIMARY};
    border: none;
    font-size: {Fonts.LABEL};
}}
QTreeWidget::item {{
    padding: {Spacing.s8}px;
    border-bottom: 1px solid {Border.SUBTLE};
}}
QTreeWidget::item:hover {{
    background: {Surface.CARD};
}}
QTreeWidget::item:selected {{
    background: {Surface.ELEVATED};
    color: {Accent.PRIMARY};
    border-left: 3px solid {Accent.PRIMARY};
}}
"""

    @staticmethod
    def list_widget():
        return f"""
QListWidget {{
    background: {Surface.CARD};
    color: {Text.PRIMARY};
    border: 1px solid {Border.STRONG};
    border-radius: {Radius.MD};
    font-size: {Fonts.CAPTION};
}}
QListWidget::item {{
    padding: {Density.COMPACT.PADDING_V}px {Density.COMPACT.PADDING_H}px;
}}
QListWidget::item:hover {{
    background: {Surface.ELEVATED};
}}
QListWidget::item:selected {{
    background: {Surface.RAISED};
    color: {Accent.PRIMARY};
    border-left: 3px solid {Accent.PRIMARY};
}}
QListWidget::item:focus {{
    border: 1px solid {Accent.PRIMARY};
}}
"""

    @staticmethod
    def combo_box():
        return f"""
QComboBox {{
    background: {Surface.CARD};
    color: {Text.PRIMARY};
    border: 1px solid {Border.DEFAULT};
    padding: 4px 6px;
    font-size: {Fonts.BODY};
    border-radius: {Radius.SM};
}}
QComboBox:hover {{
    border-color: {Accent.PRIMARY};
}}
QComboBox:focus {{
    border: 2px solid {Accent.PRIMARY};
    padding: 3px 5px;
}}
QComboBox:disabled {{
    color: {Text.MUTED};
    border-color: {Border.SUBTLE};
    background: {Surface.CARD};
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background: {Surface.CARD};
    color: {Text.PRIMARY};
    selection-background-color: {Surface.ELEVATED};
    selection-color: {Accent.PRIMARY};
    border: 1px solid {Border.DEFAULT};
}}
"""

    @staticmethod
    def progress_bar():
        return f"""
QProgressBar {{
    background: {Surface.CARD};
    border: 1px solid {Border.DEFAULT};
    border-radius: {Radius.SM};
    text-align: center;
    color: {Text.PRIMARY};
    font-size: {Fonts.CAPTION};
    height: 14px;
}}
QProgressBar::chunk {{
    background: {Accent.PRIMARY};
    border-radius: 2px;
}}
"""

    @staticmethod
    def input_field():
        pv = Density.DEFAULT.PADDING_V
        ph = Density.DEFAULT.PADDING_H
        return f"""
QLineEdit, QTextEdit {{
    background: {Surface.CARD};
    border: 1px solid {Border.DEFAULT};
    border-radius: {Radius.SM};
    padding: {pv}px {ph}px;
    color: {Text.PRIMARY};
    font-size: {Fonts.BODY};
}}
QLineEdit:focus, QTextEdit:focus {{
    border: 2px solid {Accent.PRIMARY};
    padding: {pv - 1}px {ph - 1}px;
}}
QLineEdit:disabled, QTextEdit:disabled {{
    color: {Text.MUTED};
    background: {Surface.RAISED};
    border-color: {Border.SUBTLE};
}}
QLineEdit[error="true"] {{
    border: 2px solid {Semantic.DANGER};
    padding: {pv - 1}px {ph - 1}px;
}}
"""

    @staticmethod
    def group_box():
        return f"""
QGroupBox {{
    font-size: {Fonts.HEADING};
    font-weight: {Fonts.W_HEADING};
    color: {Accent.PRIMARY};
    border: 1px solid {Border.DEFAULT};
    margin-top: 5px;
    padding-top: 10px;
    border-radius: {Radius.XL};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    color: {Accent.PRIMARY};
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
    background: {Surface.BASE};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {Border.STRONG};
    min-height: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: {Text.MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    border: none;
    background: {Surface.BASE};
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {Border.STRONG};
    min-width: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {Text.MUTED};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
"""

    @staticmethod
    def dialog():
        return f"""
QDialog {{
    background-color: {Surface.ELEVATED};
    color: {Text.PRIMARY};
    font-family: {Fonts.FAMILY};
    border: 1px solid {Elevation.BORDER_L4};
    border-radius: {Radius.XL};
}}
QLabel {{
    color: {Text.SECONDARY};
    font-size: {Fonts.BODY};
}}
"""

    @staticmethod
    def table_widget():
        """QSS para QTableWidget em modo COMPACT (padrão da app)."""
        return f"""
QTableWidget {{
    background: {Surface.BASE};
    color: {Text.PRIMARY};
    border: 1px solid {Border.DEFAULT};
    border-radius: {Radius.MD};
    font-size: {Fonts.CAPTION};
    gridline-color: {Border.SUBTLE};
}}
QTableWidget::item {{
    padding: {Density.COMPACT.PADDING_V}px {Density.COMPACT.PADDING_H}px;
    border-bottom: 1px solid {Border.SUBTLE};
}}
QTableWidget::item:hover {{
    background: {Surface.ELEVATED};
}}
QTableWidget::item:selected {{
    background: {Surface.RAISED};
    color: {Accent.PRIMARY};
}}
QHeaderView::section {{
    background: {Surface.RAISED};
    color: {Text.SECONDARY};
    font-size: {Fonts.LABEL};
    font-weight: {Fonts.W_LABEL};
    padding: {Spacing.s4}px {Spacing.s8}px;
    border: none;
    border-bottom: 1px solid {Border.DEFAULT};
    border-right: 1px solid {Border.SUBTLE};
}}
"""


# ══════════════════════════════════════════════════════════════════════════════
# WIDGETS REUTILIZÁVEIS DE ESTADO
# Importar: from src.ui.theme import EmptyStateWidget, LoadingStateWidget
# ══════════════════════════════════════════════════════════════════════════════

def _make_empty_state(parent=None, message: str = "Nenhum dado disponível",
                      icon: str = "○", detail: str = "",
                      cta_text: str = "", cta_callback=None):
    """
    Widget padronizado de estado vazio: ícone + frase + CTA opcional.

    Uso:
        empty = _make_empty_state(
            message="Nenhum elemento detectado",
            icon="◈",
            detail="Importe um arquivo DXF para iniciar.",
            cta_text="Importar DXF",
            cta_callback=self._on_import,
        )
        layout.addWidget(empty)
    """
    try:
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt

        w = QWidget(parent)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(*Spacing.MARGINS_OUTER)
        lay.setSpacing(Spacing.s8)
        lay.setAlignment(Qt.AlignCenter)

        lbl_icon = QLabel(icon)
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet(
            f"color: {Text.MUTED}; font-size: 32px; background: transparent;"
        )

        lbl_msg = QLabel(message)
        lbl_msg.setAlignment(Qt.AlignCenter)
        lbl_msg.setStyleSheet(
            f"color: {Text.SECONDARY}; font-size: {Fonts.SUBHEADING}; "
            f"font-weight: {Fonts.W_SUBHEADING}; background: transparent;"
        )

        lay.addWidget(lbl_icon)
        lay.addWidget(lbl_msg)

        if detail:
            lbl_detail = QLabel(detail)
            lbl_detail.setAlignment(Qt.AlignCenter)
            lbl_detail.setWordWrap(True)
            lbl_detail.setStyleSheet(
                f"color: {Text.MUTED}; font-size: {Fonts.CAPTION}; "
                f"background: transparent;"
            )
            lay.addWidget(lbl_detail)

        if cta_text and cta_callback:
            from PySide6.QtWidgets import QPushButton
            btn = QPushButton(cta_text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(StyleSheets.button_accent())
            btn.clicked.connect(cta_callback)
            btn.setFixedWidth(160)
            lay.addSpacing(Spacing.s8)
            lay.addWidget(btn, alignment=Qt.AlignCenter)

        return w
    except ImportError:
        return None


def _make_loading_state(parent=None, message: str = "Carregando..."):
    """
    Widget padronizado de loading com barra de progresso indeterminada.

    Uso:
        loading = _make_loading_state(message="Processando DXF...")
        layout.addWidget(loading)
        # Remover: layout.removeWidget(loading); loading.deleteLater()
    """
    try:
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
        from PySide6.QtCore import Qt

        w = QWidget(parent)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(*Spacing.MARGINS_OUTER)
        lay.setSpacing(Spacing.s12)
        lay.setAlignment(Qt.AlignCenter)

        lbl = QLabel(message)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"color: {Text.PRIMARY}; font-size: {Fonts.BODY}; "
            f"background: transparent;"
        )

        bar = QProgressBar()
        bar.setRange(0, 0)  # indeterminate
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: {Surface.CARD};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {Accent.PRIMARY};
                border-radius: 2px;
            }}
        """)

        lay.addWidget(lbl)
        lay.addWidget(bar)
        return w
    except ImportError:
        return None


# Aliases públicos
EmptyStateWidget   = _make_empty_state
LoadingStateWidget = _make_loading_state
