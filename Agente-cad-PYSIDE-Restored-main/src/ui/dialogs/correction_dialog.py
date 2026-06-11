"""
src/ui/dialogs/correction_dialog.py — CAD-10.6
Dialog de notificação de divergências entre DB e Fase-4.

Exibido quando o usuário valida um campo com valor diferente do Fase-4,
permitindo escolher: ignorar, aceitar valor F4, ou gravar correção no log.
"""
from __future__ import annotations

from typing import Any

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QAbstractItemView, QDialogButtonBox,
        QFrame, QSizePolicy,
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor, QFont
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

if _QT_AVAILABLE:
    class CorrectionDialog(QDialog):
        """
        Mostra divergências entre DB (validado pelo usuário) e Fase-4 (interpretado).

        Signals:
            corrections_chosen(list[dict])
                Emitido ao aceitar: lista de dicts com
                {field_id, json_key, f4_value, db_value, action}
                action ∈ {'keep_db', 'use_f4', 'log_correction'}
        """
        corrections_chosen = Signal(list)

        def __init__(self, divergences: list[dict], item_id: str = '',
                     parent=None):
            super().__init__(parent)
            self.divergences  = divergences
            self.item_id      = item_id
            self._choices: dict[int, str] = {}  # row → action

            self.setWindowTitle(f"Divergência detectada — {item_id}")
            self.setMinimumWidth(680)
            self.setMinimumHeight(380)
            self._build_ui()

        # ─── UI ───────────────────────────────────────────────────────────────

        def _build_ui(self):
            layout = QVBoxLayout(self)
            layout.setSpacing(8)

            # Header
            lbl = QLabel(
                f"<b>{len(self.divergences)} campo(s)</b> divergem entre o valor "
                "validado (Ficha) e o interpretado (Fase-4).<br>"
                "Escolha uma ação para cada campo:"
            )
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

            # Tabela
            self._table = QTableWidget(len(self.divergences), 5)
            self._table.setHorizontalHeaderLabels([
                "Campo", "Valor Fase-4", "Valor Ficha (DB)",
                "Ação", "",
            ])
            self._table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.Stretch)
            self._table.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.ResizeMode.ResizeToContents)
            self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

            for row, div in enumerate(self.divergences):
                self._table.setItem(row, 0, QTableWidgetItem(str(div.get('field_id', ''))))
                self._table.setItem(row, 1, QTableWidgetItem(str(div.get('f4_value', ''))))
                self._table.setItem(row, 2, QTableWidgetItem(str(div.get('db_value', ''))))

                # Ação padrão: manter DB
                self._choices[row] = 'keep_db'

                # Botões de ação inline
                btn_frame = QFrame()
                btn_layout = QHBoxLayout(btn_frame)
                btn_layout.setContentsMargins(2, 2, 2, 2)
                btn_layout.setSpacing(4)

                btn_keep = QPushButton("Manter")
                btn_keep.setToolTip("Manter valor da Ficha (DB)")
                btn_keep.setCheckable(True)
                btn_keep.setChecked(True)
                btn_keep.clicked.connect(lambda _, r=row, b=btn_keep: self._set_action(r, 'keep_db', b))

                btn_use_f4 = QPushButton("Usar F4")
                btn_use_f4.setToolTip("Substituir valor DB pelo Fase-4")
                btn_use_f4.setCheckable(True)
                btn_use_f4.clicked.connect(lambda _, r=row, b=btn_use_f4: self._set_action(r, 'use_f4', b))

                btn_log = QPushButton("Log")
                btn_log.setToolTip("Registrar correção no log de realimentação")
                btn_log.setCheckable(True)
                btn_log.clicked.connect(lambda _, r=row, b=btn_log: self._set_action(r, 'log_correction', b))

                # Grupo exclusivo simples
                self._row_buttons = getattr(self, '_row_buttons', {})
                self._row_buttons[row] = [btn_keep, btn_use_f4, btn_log]

                btn_layout.addWidget(btn_keep)
                btn_layout.addWidget(btn_use_f4)
                btn_layout.addWidget(btn_log)
                self._table.setCellWidget(row, 3, btn_frame)

            layout.addWidget(self._table)

            # Ações em massa
            bulk_frame = QFrame()
            bulk_layout = QHBoxLayout(bulk_frame)
            bulk_layout.setContentsMargins(0, 0, 0, 0)

            btn_all_keep = QPushButton("Manter Todos")
            btn_all_keep.clicked.connect(lambda: self._set_all('keep_db'))
            btn_all_f4 = QPushButton("Usar F4 em Todos")
            btn_all_f4.clicked.connect(lambda: self._set_all('use_f4'))
            btn_all_log = QPushButton("Log em Todos")
            btn_all_log.clicked.connect(lambda: self._set_all('log_correction'))

            bulk_layout.addWidget(QLabel("Todos:"))
            bulk_layout.addWidget(btn_all_keep)
            bulk_layout.addWidget(btn_all_f4)
            bulk_layout.addWidget(btn_all_log)
            bulk_layout.addStretch()
            layout.addWidget(bulk_frame)

            # Botões OK/Cancel
            bb = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok |
                QDialogButtonBox.StandardButton.Cancel
            )
            bb.accepted.connect(self._on_accept)
            bb.rejected.connect(self.reject)
            layout.addWidget(bb)

        # ─── Actions ─────────────────────────────────────────────────────────

        def _set_action(self, row: int, action: str, clicked_btn=None):
            self._choices[row] = action
            # Atualizar estado visual dos botões do row
            buttons = getattr(self, '_row_buttons', {}).get(row, [])
            action_map = ['keep_db', 'use_f4', 'log_correction']
            for i, btn in enumerate(buttons):
                btn.setChecked(action_map[i] == action)

        def _set_all(self, action: str):
            for row in range(len(self.divergences)):
                self._set_action(row, action)

        def _on_accept(self):
            result = []
            for row, div in enumerate(self.divergences):
                result.append({
                    'field_id':   div.get('field_id'),
                    'json_key':   div.get('json_key'),
                    'f4_value':   div.get('f4_value'),
                    'db_value':   div.get('db_value'),
                    'action':     self._choices.get(row, 'keep_db'),
                })
            self.corrections_chosen.emit(result)
            self.accept()

        # ─── Convenience ─────────────────────────────────────────────────────

        @staticmethod
        def ask(divergences: list[dict], item_id: str = '',
                parent=None) -> list[dict] | None:
            """
            Abre o dialog e retorna lista de choices, ou None se cancelado.

            Uso:
                choices = CorrectionDialog.ask(divergences, item_id='P1', parent=self)
                if choices is None:
                    return  # cancelado
            """
            dlg = CorrectionDialog(divergences, item_id=item_id, parent=parent)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                # Reconstruir resultado (corrections_chosen já emitiu, mas retornamos direto)
                result = []
                for row, div in enumerate(divergences):
                    result.append({
                        'field_id': div.get('field_id'),
                        'json_key': div.get('json_key'),
                        'f4_value': div.get('f4_value'),
                        'db_value': div.get('db_value'),
                        'action':   dlg._choices.get(row, 'keep_db'),
                    })
                return result
            return None

else:
    # Stub quando PySide6 não disponível (testes headless)
    class CorrectionDialog:  # type: ignore[no-redef]
        corrections_chosen = None

        def __init__(self, divergences, item_id='', parent=None):
            self.divergences = divergences
            self.item_id = item_id

        @staticmethod
        def ask(divergences, item_id='', parent=None):
            return None
