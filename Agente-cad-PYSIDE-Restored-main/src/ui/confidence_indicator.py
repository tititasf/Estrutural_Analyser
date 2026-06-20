"""
ConfidenceIndicator - Widget reutilizavel para exibir confidence de campos.
WCAG AA: combina cor + icone + texto (nunca so cor).

Estados:
    HIGH (>= 0.8):   verde  + ✅ + "Confirmado"
    MEDIUM (0.5-0.8): amarelo + ⚠ + "Revisar"
    LOW (< 0.5):     vermelho + ⛔ + "Atencao"
    NO_DATA (None):  cinza  + — + "Sem dados"

Badge adicional: "Baixa taxa historica" se hit_rate < 40% com 5+ amostras.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Property
from PySide6.QtGui import QFont


# Estilos QSS (ASCII-clean, sem UTF-8 multibyte)
_STYLE_HIGH = "color: #22c55e; font-weight: bold;"
_STYLE_MEDIUM = "color: #eab308; font-weight: bold;"
_STYLE_LOW = "color: #ef4444; font-weight: bold;"
_STYLE_NO_DATA = "color: #94a3b8;"

_STYLE_BADGE = "color: #ef4444; font-size: 10px; font-weight: normal; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 3px; padding: 1px 4px;"


class ConfidenceIndicator(QWidget):
    """Indicador de confidence com 3 dimensoes: cor + icone + texto."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._confidence = None
        self._hit_rate = None
        self._sample_count = 0
        self._low_performance = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._icon_label = QLabel()
        self._value_label = QLabel()
        self._status_label = QLabel()
        self._badge_label = QLabel()

        font = QFont()
        font.setPointSize(8)
        self._icon_label.setFont(font)
        self._value_label.setFont(font)
        self._status_label.setFont(font)

        badge_font = QFont()
        badge_font.setPointSize(7)
        self._badge_label.setFont(badge_font)
        self._badge_label.setStyleSheet(_STYLE_BADGE)
        self._badge_label.hide()

        layout.addWidget(self._icon_label)
        layout.addWidget(self._value_label)
        layout.addWidget(self._status_label)
        layout.addWidget(self._badge_label)
        layout.addStretch()

    def set_confidence(self, confidence: float, hit_rate: float = None,
                       sample_count: int = 0, low_performance: bool = False):
        """Atualiza o indicador com novos dados.

        Args:
            confidence: 0.0-1.0 ou None se sem dados
            hit_rate: 0.0-1.0 ou None (opcional)
            sample_count: numero de amostras de feedback
            low_performance: True se hit_rate < 40% com 5+ amostras
        """
        self._confidence = confidence
        self._hit_rate = hit_rate
        self._sample_count = sample_count
        self._low_performance = low_performance
        self._update_display()

    def _update_display(self):
        c = self._confidence

        if c is None:
            self._icon_label.setText("--")
            self._icon_label.setStyleSheet(_STYLE_NO_DATA)
            self._value_label.setText("")
            self._status_label.setText("Sem dados")
            self._status_label.setStyleSheet(_STYLE_NO_DATA)
            accessible = "Confidence: sem dados"
        elif c >= 0.8:
            self._icon_label.setText("[OK]")
            self._icon_label.setStyleSheet(_STYLE_HIGH)
            pct = int(c * 100)
            self._value_label.setText(str(pct) + "%")
            self._value_label.setStyleSheet(_STYLE_HIGH)
            self._status_label.setText("Confirmado")
            self._status_label.setStyleSheet(_STYLE_HIGH)
            accessible = "Confidence: " + str(pct) + " por cento, confirmado"
        elif c >= 0.5:
            self._icon_label.setText("[!]")
            self._icon_label.setStyleSheet(_STYLE_MEDIUM)
            pct = int(c * 100)
            self._value_label.setText(str(pct) + "%")
            self._value_label.setStyleSheet(_STYLE_MEDIUM)
            self._status_label.setText("Revisar")
            self._status_label.setStyleSheet(_STYLE_MEDIUM)
            accessible = "Confidence: " + str(pct) + " por cento, revisar"
        else:
            self._icon_label.setText("[X]")
            self._icon_label.setStyleSheet(_STYLE_LOW)
            pct = int(c * 100)
            self._value_label.setText(str(pct) + "%")
            self._value_label.setStyleSheet(_STYLE_LOW)
            self._status_label.setText("Atencao")
            self._status_label.setStyleSheet(_STYLE_LOW)
            accessible = "Confidence: " + str(pct) + " por cento, atencao"

        # Badge de baixa taxa historica
        if self._low_performance:
            self._badge_label.setText("! Baixa taxa historica")
            self._badge_label.show()
            accessible += ", baixa taxa historica de acerto"
        else:
            self._badge_label.hide()

        # Accessibility
        self.setAccessibleName(accessible)
        self.setAccessibleDescription(accessible)
