"""
src/ui/widgets/comparison_tab.py — CAD-10.4
Aba "Comparar" do DetailCard: tabela GT vs Fase-4 vs DB com ações por campo.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QMessageBox, QAbstractItemView, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont

from src.core.services.comparison_service import (
    ComparisonService, FieldStatus, _fmt, _empty,
)
from src.ui.theme import Colors


# ─── Paleta de status ─────────────────────────────────────────────────────────

_STATUS_COLOR = {
    FieldStatus.IGUAL:      ('#1a3320', '#4caf50'),  # bg_dark, fg  # hardcoded-ok
    FieldStatus.DIFERENTE:  ('#332900', '#ffc107'),  # hardcoded-ok
    FieldStatus.AUSENTE_GT: ('#1a1a1a', '#9e9e9e'),  # hardcoded-ok
    FieldStatus.AUSENTE_F4: ('#1a1a1a', '#9e9e9e'),  # hardcoded-ok
    FieldStatus.CONFLITO:   ('#330d00', '#f44336'),  # hardcoded-ok
}

_STATUS_ICON = {
    FieldStatus.IGUAL:      '✓',
    FieldStatus.DIFERENTE:  '≠',
    FieldStatus.AUSENTE_GT: '—',
    FieldStatus.AUSENTE_F4: '∅',
    FieldStatus.CONFLITO:   '!',
}


def _make_cell(text: str, fg: str = Colors.TEXT_PRIMARY,
               bg: str | None = None, bold: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text) if text else '—')
    item.setForeground(QBrush(QColor(fg)))
    if bg:
        item.setBackground(QBrush(QColor(bg)))
    if bold:
        f = QFont()
        f.setBold(True)
        item.setFont(f)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


# ─── Widget principal ─────────────────────────────────────────────────────────

class ComparisonTab(QWidget):
    """
    Aba "Comparar" — mostra tabela GT / Fase-4 / DB com ações por campo.

    Sinais:
      field_accepted(field_id)     — campo aceito, DetailCard deve re-render
      correction_saved(field_id)   — correção gravada no JSON Fase-4
    """

    field_accepted   = Signal(str)
    correction_saved = Signal(str)

    # ── Colunas ──────────────────────────────────────────────────────────────
    COL_FIELD  = 0
    COL_GT     = 1
    COL_F4     = 2
    COL_DB     = 3
    COL_STATUS = 4
    COL_ACTION = 5

    def __init__(self, item_data: dict, obra_path=None, db=None,
                 project_id: str = '', parent=None):
        super().__init__(parent)
        self.item_data   = item_data
        self.obra_path   = obra_path
        self.db          = db
        self.project_id  = project_id

        self._svc: ComparisonService | None = None
        self._rows: list = []

        self._build_ui()
        self._load_data()

    # ── Construção UI ─────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Score bar
        self._score_label = QLabel("—")
        self._score_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 11px; padding: 3px 6px;"
            f"background: rgba(0,0,0,76); border-radius: 4px;"
        )
        root.addWidget(self._score_label)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._btn_refresh = QPushButton("↺ Atualizar")
        self._btn_refresh.setFixedHeight(26)
        self._btn_refresh.setStyleSheet(
            f"background: rgba(0,80,80,1); color: {Colors.TEXT_BRIGHT};"
            "border: 1px solid #006666; border-radius: 4px; font-size: 11px;"  # hardcoded-ok
        )
        self._btn_refresh.clicked.connect(self._load_data)

        self._btn_accept_all = QPushButton("✓ Aceitar Todos (Sem Conflito)")
        self._btn_accept_all.setFixedHeight(26)
        self._btn_accept_all.setStyleSheet(
            f"background: rgba(0,80,20,1); color: #4caf50;"  # hardcoded-ok
            "border: 1px solid #4caf50; border-radius: 4px; font-size: 11px;"  # hardcoded-ok
        )
        self._btn_accept_all.clicked.connect(self._on_accept_all)

        toolbar.addWidget(self._btn_refresh)
        toolbar.addWidget(self._btn_accept_all)
        toolbar.addStretch()
        root.addLayout(toolbar)

        # Tabela
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Campo", "Ground Truth", "Interpretado (F4)", "Ficha Atual (DB)", "Status", "Ação"]
        )
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {Colors.BG_CARD};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                font-size: 11px;
                gridline-color: rgba(255,255,255,18);
            }}
            QHeaderView::section {{
                background: rgba(20,40,40,1);
                color: {Colors.TEXT_BRIGHT};
                border: 1px solid {Colors.BORDER_DEFAULT};
                padding: 3px;
                font-size: 10px;
                font-weight: bold;
            }}
            QTableWidget::item:selected {{
                background: rgba(0,100,100,128);
            }}
        """)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_FIELD,  QHeaderView.Stretch)
        hdr.setSectionResizeMode(self.COL_GT,     QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_F4,     QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_DB,     QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_STATUS, QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_ACTION, QHeaderView.Fixed)
        self._table.setColumnWidth(self.COL_GT,     100)
        self._table.setColumnWidth(self.COL_F4,     110)
        self._table.setColumnWidth(self.COL_DB,     110)
        self._table.setColumnWidth(self.COL_STATUS,  52)
        self._table.setColumnWidth(self.COL_ACTION,  72)
        self._table.setRowHeight(0, 26)

        root.addWidget(self._table, 1)

        # Mensagem "sem dados"
        self._no_data_label = QLabel()
        self._no_data_label.setAlignment(Qt.AlignCenter)
        self._no_data_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; padding: 20px;"
        )
        self._no_data_label.setWordWrap(True)
        self._no_data_label.setVisible(False)
        root.addWidget(self._no_data_label)

    # ── Carregamento de dados ─────────────────────────────────────────────────

    def _load_data(self):
        if not self.obra_path:
            self._show_no_data(
                "Caminho da obra não disponível.\n"
                "Abra este item a partir da aba de diagnóstico para habilitar comparação."
            )
            return

        self._svc = ComparisonService(self.item_data, self.obra_path)

        if not self._svc.has_fase4:
            self._show_no_data(
                f"Fase-4 não processada para {self.item_data.get('id_item', 'este item')}.\n"
                "Execute 'Análise Geral' primeiro para gerar os JSONs de interpretação."
            )
            return

        self._rows = self._svc.build_rows()
        self._populate_table()
        self._update_score()

    def _show_no_data(self, msg: str):
        self._table.setVisible(False)
        self._score_label.setText("—")
        self._no_data_label.setText(msg)
        self._no_data_label.setVisible(True)

    # ── População da tabela ───────────────────────────────────────────────────

    def _populate_table(self):
        self._table.setVisible(True)
        self._no_data_label.setVisible(False)
        self._table.setRowCount(0)

        for row_idx, row in enumerate(self._rows):
            self._table.insertRow(row_idx)
            self._table.setRowHeight(row_idx, 26)

            bg_dark, fg = _STATUS_COLOR.get(row.status, ('#1a1a1a', '#9e9e9e'))  # hardcoded-ok

            # Campo
            self._table.setItem(row_idx, self.COL_FIELD,
                                _make_cell(row.label, fg=Colors.TEXT_PRIMARY))

            # GT
            self._table.setItem(row_idx, self.COL_GT,
                                _make_cell(_fmt(row.gt_value), fg=Colors.TEXT_SECONDARY))

            # F4
            f4_fg = fg if not _empty(row.f4_value) else Colors.TEXT_SECONDARY
            self._table.setItem(row_idx, self.COL_F4,
                                _make_cell(_fmt(row.f4_value), fg=f4_fg))

            # DB
            db_fg = Colors.TEXT_BRIGHT if not _empty(row.db_value) else Colors.TEXT_SECONDARY
            self._table.setItem(row_idx, self.COL_DB,
                                _make_cell(_fmt(row.db_value), fg=db_fg))

            # Status
            icon = _STATUS_ICON.get(row.status, '?')
            st_cell = _make_cell(f"{icon} {row.status.value}", fg=fg, bg=bg_dark, bold=True)
            st_cell.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, self.COL_STATUS, st_cell)

            # Ação
            action_w = self._make_action_widget(row, row_idx)
            self._table.setCellWidget(row_idx, self.COL_ACTION, action_w)

    def _make_action_widget(self, row, row_idx: int) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(2, 1, 2, 1)
        h.setSpacing(2)

        can_accept = (row.status in (FieldStatus.DIFERENTE, FieldStatus.AUSENTE_F4)
                      and not _empty(row.f4_value))

        if can_accept:
            btn_acc = QPushButton("✓")
            btn_acc.setFixedSize(28, 22)
            btn_acc.setToolTip("Aceitar valor Fase-4")
            btn_acc.setStyleSheet(
                "background: rgba(0,80,20,1); color: #4caf50;"  # hardcoded-ok
                "border: 1px solid #4caf50; border-radius: 3px; font-size: 12px;"  # hardcoded-ok
            )
            fid = row.field_id
            btn_acc.clicked.connect(lambda checked=False, f=fid: self._on_accept(f))
            h.addWidget(btn_acc)

        can_save_correction = (
            not _empty(row.db_value)
            and not _empty(row.f4_value)
            and row.status in (FieldStatus.DIFERENTE, FieldStatus.CONFLITO)
        )
        if can_save_correction:
            btn_save = QPushButton("↩")
            btn_save.setFixedSize(28, 22)
            btn_save.setToolTip("Salvar valor DB → Fase-4 (correção)")
            btn_save.setStyleSheet(
                "background: rgba(80,30,0,1); color: #ff9800;"  # hardcoded-ok
                "border: 1px solid #ff9800; border-radius: 3px; font-size: 12px;"  # hardcoded-ok
            )
            fid = row.field_id
            db_val = row.db_value
            btn_save.clicked.connect(
                lambda checked=False, f=fid, v=db_val: self._on_save_correction(f, v)
            )
            h.addWidget(btn_save)

        if not can_accept and not can_save_correction:
            lbl = QLabel("—")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
            h.addWidget(lbl)

        return w

    # ── Score ──────────────────────────────────────────────────────────────

    def _update_score(self):
        if not self._svc:
            return
        sc = self._svc.score()
        self._score_label.setText(
            f"Completude: {sc['completude_pct']}% ({sc['f4_filled']}/{sc['total']})  "
            f"│  Match: {sc['match_pct']}% ({sc['matched']}/{sc['f4_filled']})"
        )

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _on_accept(self, field_id: str):
        if not self._svc or not self.db:
            QMessageBox.warning(self, "Aceitar", "DB não disponível neste contexto.")
            return
        ok = self._svc.accept_field(field_id, self.db, self.project_id)
        if ok:
            self._load_data()
            self.field_accepted.emit(field_id)

    def _on_accept_all(self):
        if not self._svc or not self.db:
            QMessageBox.warning(self, "Aceitar Todos", "DB não disponível neste contexto.")
            return
        accepted, preserved = self._svc.accept_all_non_conflict(self.db, self.project_id)
        self._load_data()
        for row in (self._rows or []):
            self.field_accepted.emit(row.field_id)
        QMessageBox.information(
            self, "Aceitar Todos",
            f"{accepted} campos aceitos, {preserved} conflitos preservados."
        )

    def _on_save_correction(self, field_id: str, new_value):
        if not self._svc or not self.db:
            QMessageBox.warning(self, "Corrigir", "DB não disponível neste contexto.")
            return
        ok = self._svc.save_correction(field_id, new_value, self.db, self.project_id)
        if ok:
            self._load_data()
            self.correction_saved.emit(field_id)
        else:
            QMessageBox.warning(
                self, "Corrigir",
                f"Não foi possível salvar correção para '{field_id}'.\n"
                "Verifique se o campo tem mapeamento inverso definido."
            )

    # ── API pública ───────────────────────────────────────────────────────────

    def refresh(self):
        """Recarrega dados (chamado quando DetailCard re-renderiza)."""
        self._load_data()

    def set_context(self, obra_path=None, db=None, project_id: str = ''):
        """Atualiza contexto após construção (ex: quando obra é selecionada)."""
        if obra_path is not None:
            self.obra_path = obra_path
        if db is not None:
            self.db = db
        if project_id:
            self.project_id = project_id
        self._load_data()
