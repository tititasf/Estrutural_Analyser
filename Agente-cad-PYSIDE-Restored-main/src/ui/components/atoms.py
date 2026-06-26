from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from src.ui.theme import (
    Surface, Accent, Semantic, Contextual, Text, Border,
    Fonts, Spacing, Density, Radius, StyleSheets
)


class StatusBadge(QLabel):
    """
    Badge visual para status: VALID, REVISÃO, ERROR.
    Sempre exibe bolinha + texto — a cor não é o único sinal (acessibilidade).
    """
    _STATES = {
        "VALID":  (Semantic.SUCCESS_SUBTLE, Semantic.SUCCESS,  Semantic.SUCCESS,  "●"),
        "REVISAO":(Semantic.WARNING_SUBTLE, Semantic.WARNING,  Semantic.WARNING,  "●"),
        "ERROR":  (Semantic.DANGER_SUBTLE,  Semantic.DANGER,   Semantic.DANGER,   "●"),
    }
    _DEFAULT = (Semantic.WARNING_SUBTLE, Semantic.WARNING, Semantic.WARNING, "●")

    def __init__(self, status="VALID", compact=False):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self._compact = compact
        self.set_status(status)

    def set_status(self, status: str):
        key = status.upper()
        if "VALID" in key or "OK" in key:
            bg, color, border, dot = self._STATES["VALID"]
        elif "REVIS" in key or "WARN" in key:
            bg, color, border, dot = self._STATES["REVISAO"]
        elif "ERROR" in key or "CRIT" in key or "FAIL" in key:
            bg, color, border, dot = self._STATES["ERROR"]
        else:
            bg, color, border, dot = self._DEFAULT

        label = f"{dot} {status}"
        self.setText(label)

        pad = f"{Spacing.s2}px {Spacing.s4}px" if self._compact else f"{Spacing.s4}px {Spacing.s8}px"
        size = Fonts.CAPTION if self._compact else Fonts.LABEL

        self.setStyleSheet(f"""
            StatusBadge {{
                background-color: {bg};
                color: {color};
                border: 1px solid {border};
                border-radius: {Radius.SM};
                padding: {pad};
                font-weight: {Fonts.W_LABEL};
                font-family: {Fonts.FAMILY};
                font-size: {size};
            }}
        """)


class NavButton(QPushButton):
    """
    Botão de navegação de sidebar.
    Estado active: fundo tint 10% + borda esquerda Accent.PRIMARY.
    """
    def __init__(self, text: str, icon_str: str = None, active: bool = False):
        super().__init__(text)
        self.setCheckable(True)
        self.setChecked(active)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(Density.DEFAULT.ROW_HEIGHT)
        self.setStyleSheet(self._build_style())

    def _build_style(self) -> str:
        return f"""
            NavButton {{
                text-align: left;
                padding-left: {Spacing.s16}px;
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                color: {Text.SECONDARY};
                font-size: {Fonts.BODY};
                font-family: {Fonts.FAMILY};
            }}
            NavButton:hover {{
                background-color: {Contextual.GLASS_5};
                color: {Text.PRIMARY};
            }}
            NavButton:checked {{
                background-color: rgba(0, 120, 212, 26);
                color: {Accent.INTERACTIVE};
                border-left: 3px solid {Accent.INTERACTIVE};
                font-weight: {Fonts.W_SUBHEADING};
            }}
            NavButton:focus {{
                border-left: 3px solid {Accent.PRIMARY};
                outline: none;
            }}
            NavButton:disabled {{
                color: {Text.MUTED};
                background-color: transparent;
            }}
        """


class MetricLabel(QWidget):
    """
    Par Chave–Valor para painéis técnicos.
    Label em Text.SECONDARY; valor em Text.BRIGHT (ou Accent.PRIMARY se highlight).
    Valor técnico (ID, coord) usa fonte mono automaticamente se is_mono=True.
    """
    def __init__(self, label: str, value, unit: str = "",
                 highlight: bool = False, is_mono: bool = False):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, Spacing.s2, 0, Spacing.s2)
        layout.setSpacing(Spacing.s8)

        lbl_title = QLabel(label)
        lbl_title.setStyleSheet(
            f"color: {Text.SECONDARY}; font-size: {Fonts.LABEL}; background: transparent;"
        )

        full_value = f"{value} {unit}".strip() if unit else str(value)
        lbl_val = QLabel(full_value)

        color  = Accent.PRIMARY if highlight else Text.BRIGHT
        weight = Fonts.W_HEADING if highlight else Fonts.W_BODY
        family = Fonts.FAMILY_MONO if is_mono else Fonts.FAMILY
        size   = Fonts.MONO if is_mono else Fonts.BODY

        lbl_val.setStyleSheet(
            f"color: {color}; font-size: {size}; font-weight: {weight}; "
            f"font-family: {family}; background: transparent;"
        )
        lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(lbl_title)
        layout.addStretch()
        layout.addWidget(lbl_val)


class DeltaBadge(QLabel):
    """
    Badge para comparação numérica (+12.4 / −3.1 / = 0.0).
    inverse=True: aumento é bom (rigidez, segurança).
    Usa fonte mono — dado técnico.
    """
    def __init__(self, value, suffix: str = "%", inverse: bool = False):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.update_value(value, suffix, inverse)

    def update_value(self, value, suffix: str = "%", inverse: bool = False):
        try:
            val = float(value)
        except (ValueError, TypeError):
            val = 0.0

        sign = "+" if val > 0 else ("−" if val < 0 else "=")
        abs_val = abs(val)
        self.setText(f"{sign} {abs_val}{suffix}")

        is_good = (val > 0 and inverse) or (val < 0 and not inverse)

        if val == 0:
            color, bg = Text.SECONDARY, Surface.CARD
        elif is_good:
            color, bg = Semantic.SUCCESS, Semantic.SUCCESS_SUBTLE
        else:
            color, bg = Semantic.DANGER, Semantic.DANGER_SUBTLE

        self.setStyleSheet(f"""
            DeltaBadge {{
                background-color: {bg};
                color: {color};
                border-radius: {Radius.SM};
                padding: 1px 4px;
                font-size: {Fonts.CAPTION};
                font-weight: {Fonts.W_LABEL};
                font-family: {Fonts.FAMILY_MONO};
            }}
        """)


class AISuggestionBox(QFrame):
    """
    Caixa de sugestão de IA.
    Usa Contextual.PURPLE — namespace exclusivo de IA, não reutilizar.
    """
    apply_clicked = Signal()

    def __init__(self, text: str = ""):
        super().__init__()
        self.setObjectName("AIBox")
        self.setStyleSheet(f"""
            #AIBox {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Surface.BASE},
                    stop:1 {Surface.CARD}
                );
                border: 1px solid rgba(160, 112, 255, 76);
                border-radius: {Radius.XL};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Spacing.MARGINS_TIGHT)
        layout.setSpacing(Spacing.s8)

        hdr = QLabel("✦ AI Analysis")
        hdr.setStyleSheet(
            f"color: {Contextual.PURPLE}; font-weight: {Fonts.W_SUBHEADING}; "
            f"font-size: {Fonts.LABEL}; background: transparent;"
        )
        layout.addWidget(hdr)

        self.lbl_text = QLabel(text)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet(
            f"color: {Text.PRIMARY}; font-size: {Fonts.BODY}; "
            f"margin-top: 2px; background: transparent;"
        )
        layout.addWidget(self.lbl_text)

        self.btn_action = QPushButton("APLICAR")
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(160, 112, 255, 40);
                border: 1px solid {Contextual.PURPLE};
                color: {Contextual.PURPLE};
                border-radius: {Radius.MD};
                padding: {Spacing.s4}px {Spacing.s8}px;
                font-size: {Fonts.LABEL};
                font-weight: {Fonts.W_LABEL};
                margin-top: {Spacing.s4}px;
            }}
            QPushButton:hover {{
                background-color: rgba(160, 112, 255, 80);
                color: {Text.BRIGHT};
            }}
            QPushButton:focus {{
                border: 2px solid {Accent.PRIMARY};
            }}
            QPushButton:disabled {{
                color: {Text.MUTED};
                border-color: {Border.DEFAULT};
            }}
        """)
        self.btn_action.clicked.connect(self.apply_clicked.emit)
        layout.addWidget(self.btn_action)

    def set_suggestion(self, text: str):
        self.lbl_text.setText(text)


class SyncToggleButton(QPushButton):
    """Toggle pill para sincronização de viewports."""

    def __init__(self):
        super().__init__("SYNC OFF")
        self.setCheckable(True)
        self.setFixedSize(120, 28)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
        self.toggled.connect(self._update_style)

    def _update_style(self):
        if self.isChecked():
            self.setText("SYNC ON")
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(0, 212, 255, 26);
                    border: 1px solid {Accent.PRIMARY};
                    color: {Accent.PRIMARY};
                    border-radius: {Radius.PILL};
                    font-weight: {Fonts.W_LABEL};
                    font-size: {Fonts.CAPTION};
                }}
                QPushButton:focus {{
                    border: 2px solid {Accent.PRIMARY};
                }}
            """)
        else:
            self.setText("SYNC OFF")
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {Border.STRONG};
                    color: {Text.MUTED};
                    border-radius: {Radius.PILL};
                    font-weight: {Fonts.W_LABEL};
                    font-size: {Fonts.CAPTION};
                }}
                QPushButton:hover {{
                    border-color: {Text.SECONDARY};
                    color: {Text.SECONDARY};
                }}
                QPushButton:focus {{
                    border: 2px solid {Accent.PRIMARY};
                    color: {Text.PRIMARY};
                }}
            """)


class EmailSourceIcon(QLabel):
    """Ícone de origem de documento (Gmail, Upload, System)."""

    _ICONS = {
        "Gmail":   "✉",
        "Outlook": "✉",
        "Email":   "✉",
        "Upload":  "⬆",
        "System":  "⚙",
    }

    def __init__(self, source_type: str = "Email"):
        super().__init__()
        self.setFixedSize(24, 24)
        self.setAlignment(Qt.AlignCenter)
        self.setText(self._ICONS.get(source_type, "?"))
        self.setToolTip(f"Origem: {source_type}")
        self.setStyleSheet(
            f"font-size: {Fonts.HEADING}; color: {Text.SECONDARY}; "
            f"background: transparent;"
        )


class AttachmentChip(QPushButton):
    """Chip representando um anexo. Ex: ⊞ planta.dxf"""

    def __init__(self, filename: str):
        super().__init__(f"⊞ {filename}")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {Surface.CARD};
                border: 1px solid {Border.STRONG};
                color: {Text.PRIMARY};
                border-radius: {Radius.PILL};
                padding: 2px {Spacing.s8}px;
                font-size: {Fonts.CAPTION};
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {Surface.ELEVATED};
                border-color: {Border.DEFAULT};
            }}
            QPushButton:focus {{
                border: 2px solid {Accent.PRIMARY};
            }}
        """)


class UserAvatar(QLabel):
    """Avatar circular com iniciais e cor de borda por status."""

    _STATUS_COLORS = {
        "Online": Semantic.SUCCESS,
        "Busy":   Semantic.DANGER,
        "Away":   Semantic.WARNING,
    }

    def __init__(self, name: str, status: str = "Offline", size: int = 32):
        super().__init__()
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setText((name[:2].upper() if name else "??"))

        border_color = self._STATUS_COLORS.get(status, Text.MUTED)
        half = size // 2
        font_size = max(size // 2 - 2, 9)

        self.setStyleSheet(f"""
            QLabel {{
                background-color: {Accent.INTERACTIVE};
                color: {Text.BRIGHT};
                border: 2px solid {border_color};
                border-radius: {half}px;
                font-weight: {Fonts.W_HEADING};
                font-size: {font_size}px;
            }}
        """)
        self.setToolTip(f"{name} ({status})")


class PriorityTag(QLabel):
    """Badge colorida para tags de prioridade (ALTA, MÉDIA, BAIXA, VIP)."""

    _PRESETS = {
        "ALTA":  Semantic.DANGER,
        "MEDIA": Semantic.WARNING,
        "BAIXA": Semantic.SUCCESS,
        "VIP":   Contextual.GOLD,
        "ADMIN": Contextual.GOLD,
    }

    def __init__(self, text: str, color: str = None):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        bg = color or self._PRESETS.get(text.upper(), Accent.INTERACTIVE)
        self.setStyleSheet(f"""
            background-color: {bg};
            color: {Text.BRIGHT};
            padding: 2px {Spacing.s4}px;
            border-radius: {Radius.SM};
            font-size: {Fonts.CAPTION};
            font-weight: {Fonts.W_LABEL};
        """)


def make_section_header(title: str, subtitle: str = "",
                        accent_color: str = "") -> QWidget:
    """
    Cabeçalho de seção padronizado: título (HEADING) + linha separadora.

    Uso:
        header = make_section_header("PILARES", "42 registros")
        layout.addWidget(header)
    """
    color = accent_color or Accent.PRIMARY

    container = QWidget()
    h_layout = QHBoxLayout(container)
    h_layout.setContentsMargins(0, 0, 0, 0)
    h_layout.setSpacing(Spacing.s8)

    lbl_title = QLabel(title.upper())
    lbl_title.setStyleSheet(
        f"color: {color}; font-size: {Fonts.HEADING}; "
        f"font-weight: {Fonts.W_HEADING}; background: transparent;"
    )
    h_layout.addWidget(lbl_title)

    if subtitle:
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(
            f"color: {Text.SECONDARY}; font-size: {Fonts.CAPTION}; "
            f"background: transparent;"
        )
        h_layout.addWidget(lbl_sub)

    h_layout.addStretch()

    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {Border.SUBTLE}; border: none;")

    wrapper = QWidget()
    v_layout = QVBoxLayout(wrapper)
    v_layout.setContentsMargins(0, 0, 0, Spacing.s4)
    v_layout.setSpacing(Spacing.s4)
    v_layout.addWidget(container)
    v_layout.addWidget(line)

    return wrapper
