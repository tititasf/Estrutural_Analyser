# -*- coding: utf-8 -*-
"""
Diagnostic Reverse Hub — Tab 2
Motor de engenharia reversa: visualização, recorte e processamento granular
dos DXFs STOG humanos (Projetos_Finalizados_para_Engenharia_Reversa/).

Sprint ER-2 | MASTERPLAN-ENGENHARIA-REVERSA.md
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread, QObject, QSize
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QProgressBar, QMessageBox, QSizePolicy, QScrollArea,
    QComboBox, QDialog, QDialogButtonBox, QLineEdit,
    QGraphicsLineItem, QGraphicsPathItem, QGraphicsEllipseItem,
    QGraphicsSimpleTextItem, QRadioButton, QButtonGroup,
)
from PySide6.QtGui import QColor

from src.ui.theme import Colors, Fonts
from src.ui.canvas import CADCanvas

# ── Constantes ──────────────────────────────────────────────────────────────
DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DB_PATH = "D:/Agente-cad-PYSIDE/project_data.vision"

_CLASSES = [
    ("PIL", "Pilares"),
    ("LV",  "L.Viga"),
    ("FV",  "F.Viga"),
    ("LAJ", "Lajes"),
]
_CLS_COLORS = {
    "PIL": "#7ab3e0", "LV": "#4caf50", "FV": "#ff9800", "LAJ": "#e91e63"
}

# Valores aceitos por chave de classe (short + full, ambos podem aparecer em notes)
_CLS_FILTER: dict[str, set] = {
    "PIL": {"PIL", "Pilares"},
    "LV":  {"LV",  "Lateral de Viga", "Laterais de Viga"},
    "FV":  {"FV",  "Fundos de Viga",  "Fundo de Viga"},
    "LAJ": {"LAJ", "Lajes"},
}

import re as _re, unicodedata as _ucd

def _infer_cls_from_filename(fname: str) -> str:
    """Infere classe ER a partir do nome do arquivo (fallback quando notes não tem er_class)."""
    stem = _ucd.normalize('NFKD', fname)
    stem = ''.join(c for c in stem if not _ucd.combining(c)).upper()
    stem = _re.sub(r'\.\w+$', '', stem)
    if _re.search(r'(?<![A-Z])FV(?![A-Z])', stem):  return "FV"
    if _re.search(r'(?<![A-Z])LV(?![A-Z])', stem):  return "LV"
    if _re.search(r'(?<![A-Z])LJ(?![A-Z])', stem):  return "LAJ"
    if _re.search(r'(?<![A-Z])LAJ(?![A-Z])', stem): return "LAJ"
    if _re.search(r'[-\s]PL[-\s.]|[-\s]PL$', stem): return "PIL"
    return "OUTROS"

# ── DB migration — garante colunas novas ─────────────────────────────────────

def _db_ensure_schema():
    """Adiciona colunas novas ao reverse_eng_recortes se ainda não existirem."""
    try:
        conn = sqlite3.connect(DB_PATH)
        existing = {r[1] for r in conn.execute("PRAGMA table_info(reverse_eng_recortes)").fetchall()}
        if 'confidence' not in existing:
            conn.execute("ALTER TABLE reverse_eng_recortes ADD COLUMN confidence REAL DEFAULT NULL")
        conn.commit()
        conn.close()
    except Exception:
        pass

_db_ensure_schema()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _db_query(sql: str, params: tuple = ()) -> list:
    """Executa query no SQLite com tratamento seguro de erro."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def _db_execute(sql: str, params: tuple = ()) -> bool:
    """Executa DML (INSERT/UPDATE) no SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(sql, params)
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ── Painel Esquerdo ──────────────────────────────────────────────────────────

class _LeftPanel(QFrame):
    """Lista 'Projetos Finalizados Reversos Aprovados' + filtro de classe."""

    item_selected = Signal(str, str, str)   # obra_name, elemento_id, dxf_path
    class_changed = Signal(str)             # classe PIL|LV|FV|LAJ
    obra_changed  = Signal(str)             # quando o combo de obra muda

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_obra: str = ""
        self._current_cls: str = "PIL"
        self._cls_btns: dict = {}

        self.setStyleSheet(f"background:{Colors.BG_SECONDARY};")
        self.setFixedWidth(220)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(5, 5, 5, 5)
        lay.setSpacing(4)

        # Título
        lbl = QLabel("Projetos Finalizados\nReversos Aprovados")
        lbl.setStyleSheet(
            f"color:{Colors.ACCENT_PRIMARY}; font-weight:bold; font-size:10px; background:transparent;"
        )
        lay.addWidget(lbl)

        # ComboBox de obras
        self.cmb_obra = QComboBox()
        self.cmb_obra.setPlaceholderText("— selecione a obra —")
        self.cmb_obra.setStyleSheet(f"""
            QComboBox {{
                background:{Colors.BG_DEEP}; color:{Colors.TEXT_PRIMARY};
                border:1px solid {Colors.BORDER_DEFAULT}; border-radius:4px;
                font-size:10px; padding:2px 6px;
            }}
            QComboBox::drop-down {{ border:none; }}
            QComboBox QAbstractItemView {{
                background:{Colors.BG_CARD}; color:{Colors.TEXT_PRIMARY};
                selection-background-color:{Colors.ACCENT_BLUE};
            }}
        """)
        self.cmb_obra.currentTextChanged.connect(self._on_cmb_obra_changed)
        lay.addWidget(self.cmb_obra)
        self._populate_obra_combo()

        # Botões de classe
        cls_row = QHBoxLayout()
        cls_row.setSpacing(2)
        cls_row.setContentsMargins(0, 0, 0, 0)
        for key, label in _CLASSES:
            btn = QPushButton(label)
            btn.setFixedHeight(20)
            btn.setCheckable(True)
            btn.setProperty("cls_key", key)
            btn.clicked.connect(lambda _checked, k=key: self._select_cls(k))
            self._cls_btns[key] = btn
            cls_row.addWidget(btn)
        lay.addLayout(cls_row)

        # Lista de itens
        self.lst = QListWidget()
        self.lst.setStyleSheet(f"""
            QListWidget {{
                background:{Colors.BG_DEEP}; color:{Colors.TEXT_PRIMARY};
                border:1px solid {Colors.BORDER_DEFAULT}; font-size:10px;
            }}
            QListWidget::item {{ padding:2px 4px; }}
            QListWidget::item:selected {{ background:{Colors.ACCENT_BLUE}; color:{Colors.TEXT_BRIGHT}; }}
            QListWidget::item:hover {{ background:{Colors.BG_CARD}; }}
        """)
        self.lst.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self.lst, 1)

        # Inicializar com "PIL" selecionado
        self._select_cls("PIL")

    def _populate_obra_combo(self, obras: list[str] | None = None):
        """Carrega todas as obras no combo (igual ao cmb_works do main).

        Se `obras` for fornecida (lista de strings), usa direto.
        Caso contrário faz query no DB (todas as obras cadastradas).
        """
        if obras is None:
            rows = _db_query(
                "SELECT DISTINCT obra_name FROM obras ORDER BY obra_name ASC"
            )
            if not rows:
                # fallback: pegar de obra_triagem (qualquer status)
                rows = _db_query(
                    "SELECT DISTINCT obra_name FROM obra_triagem ORDER BY obra_name ASC"
                )
            obras = [r[0] for r in rows if r[0]]

        self.cmb_obra.blockSignals(True)
        current = self._current_obra
        self.cmb_obra.clear()
        for obra in obras:
            self.cmb_obra.addItem(obra)
        if current:
            idx = self.cmb_obra.findText(current)
            if idx >= 0:
                self.cmb_obra.setCurrentIndex(idx)
        self.cmb_obra.blockSignals(False)

    def _on_cmb_obra_changed(self, obra_name: str):
        if obra_name and obra_name != self._current_obra:
            self._current_obra = obra_name
            self._refresh_list()
            self.obra_changed.emit(obra_name)

    def _select_cls(self, cls: str):
        self._current_cls = cls
        color = _CLS_COLORS.get(cls, Colors.ACCENT_BLUE)
        for key, btn in self._cls_btns.items():
            active = (key == cls)
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(
                    f"QPushButton {{ background:{color}; color:#fff; border-radius:3px; "
                    f"font-size:9px; font-weight:bold; border-bottom:2px solid white; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_SECONDARY}; "
                    f"border-radius:3px; font-size:9px; border:1px solid {Colors.BORDER_DEFAULT}; }} "
                    f"QPushButton:hover {{ background:{Colors.BG_PANEL}; }}"
                )
        self.class_changed.emit(cls)
        self._refresh_list()

    def _refresh_list(self):
        self.lst.clear()
        if not self._current_obra:
            ph = QListWidgetItem("— selecione uma obra —")
            ph.setForeground(QColor(Colors.TEXT_DIM))
            ph.setFlags(ph.flags() & ~Qt.ItemIsSelectable)
            self.lst.addItem(ph)
            return

        # Fonte: obra_triagem — mesmos itens que aparecem em "Projetos Finalizados"
        rows = _db_query(
            "SELECT id, file_name, file_path, notes FROM obra_triagem "
            "WHERE obra_name=? AND status='approved' "
            "AND (suggested_category LIKE '%Engenharia Reversa%' "
            "     OR suggested_category LIKE '%Projetos Finalizados%') "
            "ORDER BY file_name ASC",
            (self._current_obra,)
        )

        # Filtrar pela classe selecionada (via notes JSON ou inferência por filename)
        accepted = _CLS_FILTER.get(self._current_cls, set())
        filtered = []
        for (row_id, fname, fpath, notes_json) in rows:
            er_class = "OUTROS"
            if notes_json:
                try:
                    notes = json.loads(notes_json)
                    er_class = notes.get("er_class", "OUTROS")
                except Exception:
                    pass
            if er_class == "OUTROS" or er_class not in accepted:
                # fallback: inferir pelo nome do arquivo
                er_class = _infer_cls_from_filename(fname or "")
            if er_class in accepted:
                filtered.append((row_id, fname, fpath))

        if not filtered:
            ph = QListWidgetItem("— sem itens para esta classe —")
            ph.setForeground(QColor(Colors.TEXT_DIM))
            ph.setFlags(ph.flags() & ~Qt.ItemIsSelectable)
            self.lst.addItem(ph)
            return

        color = QColor(_CLS_COLORS.get(self._current_cls, Colors.ACCENT_SUCCESS))
        for (row_id, fname, fpath) in filtered:
            label = Path(fname).stem if fname else str(row_id)
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, (str(row_id), fpath or ""))
            it.setForeground(color)
            self.lst.addItem(it)

    def _on_item_clicked(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if not data:
            return
        proj_id, dxf_path = data
        self.item_selected.emit(self._current_obra, str(proj_id), dxf_path or "")

    def set_obra(self, obra_name: str):
        self._current_obra = obra_name
        # Sincroniza combo se necessário
        idx = self.cmb_obra.findText(obra_name)
        if idx < 0:
            self._populate_obra_combo()
            idx = self.cmb_obra.findText(obra_name)
        if idx >= 0 and self.cmb_obra.currentIndex() != idx:
            self.cmb_obra.blockSignals(True)
            self.cmb_obra.setCurrentIndex(idx)
            self.cmb_obra.blockSignals(False)
        self._refresh_list()

    def select_item_by_path(self, file_path: str):
        """Seleciona na lista o item cujo file_path corresponde ao dado."""
        if not file_path:
            return
        fname = Path(file_path).name
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            data = it.data(Qt.UserRole)
            if data:
                _, item_path = data
                if item_path and (item_path == file_path or Path(item_path).name == fname):
                    self.lst.setCurrentItem(it)
                    self._on_item_clicked(it)
                    return

    def refresh(self):
        self._populate_obra_combo()
        self._refresh_list()


# ── Proxy para carregamento assíncrono de DXF no CADCanvas ───────────────────

# Limite de entidades para o viewer "completo" (referência visual, não edição).
# DXFs grandes (PIL ~23k linhas) bloqueiam o main thread sem este cap.
_MAX_RENDER_COMPLETO = 800


def _cap_entities(entities: dict, max_ents: int):
    """Subsampla todos os tipos de entidade para no máximo max_ents total.

    Usa amostragem proporcional em cada tipo (linhas, polylines, textos,
    círculos, hatches) para não ultrapassar o budget total.

    Returns:
        (capped_dict, was_capped, original_total)
    """
    lines   = entities.get('lines',     [])
    polys   = entities.get('polylines', [])
    texts   = entities.get('texts',     [])
    circles = entities.get('circles',   [])
    hatches = entities.get('hatches',   [])

    total = len(lines) + len(polys) + len(texts) + len(circles) + len(hatches)
    if total <= max_ents:
        return entities, False, total

    ratio = max_ents / total

    def _sample(lst):
        if not lst:
            return lst
        n = max(1, int(len(lst) * ratio))
        if n >= len(lst):
            return lst
        step = max(1, len(lst) // n)
        return lst[::step][:n]

    capped = dict(entities)
    capped['lines']     = _sample(lines)
    capped['polylines'] = _sample(polys)
    capped['texts']     = _sample(texts)
    capped['circles']   = _sample(circles)
    capped['hatches']   = _sample(hatches)
    return capped, True, total


class _DXFRenderProxy(QObject):
    """Vive no main thread — recebe sinal do worker e renderiza no CADCanvas."""
    def __init__(self, canvas: "CADCanvas", thread_ref, pending: dict,
                 max_entities: int | None = None, parent=None):
        super().__init__(parent)
        self._canvas       = canvas
        self._canvas_id    = id(canvas)
        self._thread_ref   = thread_ref
        self._pending      = pending
        self._max_entities = max_entities

    def on_loaded(self, entities, dur, dd):
        if self._pending.get(self._canvas_id) is not self._thread_ref:
            return
        canvas = self._canvas
        try:
            if entities:
                canvas.set_loading(True, "⌛ Renderizando…")
                # Desabilita repaints intermediários do viewport durante o loop de add.
                # Sem isso, cada processEvents() dentro de add_dxf_entities repinta a
                # cena crescente (caro para 20k+ itens). Um único repaint no finally.
                vp = canvas.viewport()
                if vp is not None:
                    vp.setUpdatesEnabled(False)
                try:
                    canvas.add_dxf_entities(entities,
                                            render_mode=dd.get('render_mode', 'TRUE_GEOMETRY'),
                                            compute_snaps=False)
                finally:
                    if vp is not None:
                        vp.setUpdatesEnabled(True)
                        vp.update()          # único repaint com cena completa
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            canvas.set_loading(False)

    def on_error(self, e: str):
        if self._pending.get(self._canvas_id) is self._thread_ref:
            self._canvas.set_loading(False)


# ── Painel Central ───────────────────────────────────────────────────────────

class _CenterPanel(QFrame):
    """4 tabs: Viz.Completo (CADCanvas) | Viz.Granular | Ficha Granular | Ficha Obra ER"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{Colors.BG_DEEP};")

        # Estado de loading assíncrono
        self._dxf_threads:  list = []
        self._dxf_workers:  list = []
        self._dxf_proxies:  list = []
        self._canvas_pending: dict = {}
        # Lazy loading: DXF completo só carrega quando Tab 0 está ativa
        self._pending_completo_dxf: str | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border:none; background:{Colors.BG_DEEP}; }}
            QTabBar::tab {{
                background:{Colors.BG_CARD}; color:{Colors.TEXT_SECONDARY};
                padding:4px 10px; font-size:9px; border-right:1px solid {Colors.BORDER_DEFAULT};
            }}
            QTabBar::tab:selected {{
                background:{Colors.BG_PANEL}; color:{Colors.TEXT_BRIGHT}; font-weight:bold;
            }}
        """)
        lay.addWidget(self._tabs)

        # ── Tab 1 — Visualizador Projeto Completo (CADCanvas com toolbar) ──
        completo_container = QWidget()
        completo_container.setStyleSheet("background:transparent;")
        comp_lay = QVBoxLayout(completo_container)
        comp_lay.setContentsMargins(0, 0, 0, 0)
        comp_lay.setSpacing(0)

        # Toolbar: Pan | Selecionar | Deletar Seleção | Fit
        toolbar = QFrame()
        toolbar.setFixedHeight(28)
        toolbar.setStyleSheet(
            f"background:{Colors.BG_SECONDARY}; border-bottom:1px solid {Colors.BORDER_DEFAULT};"
        )
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(6, 2, 6, 2)
        tb_lay.setSpacing(4)

        def _tbtn(text: str, tip: str) -> QPushButton:
            b = QPushButton(text)
            b.setFixedHeight(22)
            b.setToolTip(tip)
            b.setStyleSheet(
                f"QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_PRIMARY}; "
                f"border:1px solid {Colors.BORDER_DEFAULT}; border-radius:3px; "
                f"font-size:9px; padding:0 7px; }} "
                f"QPushButton:hover {{ background:{Colors.BG_PANEL}; color:{Colors.TEXT_BRIGHT}; }} "
                f"QPushButton:checked {{ background:{Colors.ACCENT_BLUE}; color:#fff; }}"
            )
            b.setCheckable(True)
            return b

        btn_delete = QPushButton("🗑 Deletar Seleção")
        btn_delete.setFixedHeight(22)
        btn_delete.setToolTip("Remove entidades selecionadas do canvas")
        btn_delete.setStyleSheet(
            f"QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.ACCENT_DANGER}; "
            f"border:1px solid {Colors.BORDER_DEFAULT}; border-radius:3px; "
            f"font-size:9px; padding:0 7px; }} "
            f"QPushButton:hover {{ background:rgba(211,47,47,38); }}"
        )

        btn_fit = QPushButton("⊞ Fit")
        btn_fit.setFixedHeight(22)
        btn_fit.setToolTip("Ajustar view ao conteúdo")
        btn_fit.setCheckable(False)
        btn_fit.setStyleSheet(
            f"QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_PRIMARY}; "
            f"border:1px solid {Colors.BORDER_DEFAULT}; border-radius:3px; "
            f"font-size:9px; padding:0 7px; }} "
            f"QPushButton:hover {{ background:{Colors.BG_PANEL}; }}"
        )

        lbl_hint = QLabel("⬚ Seleção ativa · Scroll=zoom · Btn3=pan · Del=remove")
        lbl_hint.setStyleSheet(f"color:{Colors.TEXT_DIM}; font-size:9px; background:transparent;")

        tb_lay.addWidget(btn_delete)
        tb_lay.addWidget(btn_fit)
        tb_lay.addStretch()
        tb_lay.addWidget(lbl_hint)
        comp_lay.addWidget(toolbar)

        # CADCanvas — sempre em modo select; pan via botão do meio
        self.canvas = CADCanvas()
        self.canvas.toolbar.setVisible(False)
        self.canvas.set_edit_mode('select')
        comp_lay.addWidget(self.canvas, 1)
        self._tabs.addTab(completo_container, "Visualizador Projeto Completo")

        # Conectar toolbar
        btn_delete.clicked.connect(self._delete_selected)
        btn_fit.clicked.connect(self._fit_view)
        # Delete key no canvas
        self.canvas.keyPressEvent = self._canvas_key_press

        # ── Tab 2 — Visualizador Granular (CADCanvas com toolbar) ──
        self._granular_dxf_path: str | None = None   # path do recorte atual
        self._granular_deleted: list = []             # data(0) de itens deletados nesta sessão

        gran_container = QWidget()
        gran_container.setStyleSheet("background:transparent;")
        gran_lay = QVBoxLayout(gran_container)
        gran_lay.setContentsMargins(0, 0, 0, 0)
        gran_lay.setSpacing(0)

        # Toolbar granular
        gran_toolbar = QFrame()
        gran_toolbar.setFixedHeight(28)
        gran_toolbar.setStyleSheet(
            f"background:{Colors.BG_SECONDARY}; border-bottom:1px solid {Colors.BORDER_DEFAULT};"
        )
        gtb_lay = QHBoxLayout(gran_toolbar)
        gtb_lay.setContentsMargins(6, 2, 6, 2)
        gtb_lay.setSpacing(4)

        def _gtbtn(text: str, tip: str, checkable: bool = True) -> QPushButton:
            b = QPushButton(text)
            b.setFixedHeight(22)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setStyleSheet(
                f"QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_PRIMARY}; "
                f"border:1px solid {Colors.BORDER_DEFAULT}; border-radius:3px; "
                f"font-size:9px; padding:0 7px; }} "
                f"QPushButton:hover {{ background:{Colors.BG_PANEL}; color:{Colors.TEXT_BRIGHT}; }} "
                f"QPushButton:checked {{ background:{Colors.ACCENT_BLUE}; color:#fff; }}"
            )
            return b

        gbtn_delete = QPushButton("🗑 Deletar Seleção")
        gbtn_delete.setFixedHeight(22)
        gbtn_delete.setCheckable(False)
        gbtn_delete.setToolTip("Remove entidades selecionadas do canvas granular")
        gbtn_delete.setStyleSheet(
            f"QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.ACCENT_DANGER}; "
            f"border:1px solid {Colors.BORDER_DEFAULT}; border-radius:3px; "
            f"font-size:9px; padding:0 7px; }} "
            f"QPushButton:hover {{ background:rgba(211,47,47,38); }}"
        )

        gbtn_save = QPushButton("💾 Salvar")
        gbtn_save.setFixedHeight(22)
        gbtn_save.setCheckable(False)
        gbtn_save.setToolTip("Salva o DXF granular atual (sobrescreve recorte)")
        gbtn_save.setStyleSheet(
            f"QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.ACCENT_SUCCESS}; "
            f"border:1px solid {Colors.BORDER_DEFAULT}; border-radius:3px; "
            f"font-size:9px; padding:0 7px; }} "
            f"QPushButton:hover {{ background:rgba(67,160,71,38); }}"
        )

        gbtn_fit = QPushButton("⊞ Fit")
        gbtn_fit.setFixedHeight(22)
        gbtn_fit.setCheckable(False)
        gbtn_fit.setToolTip("Ajustar view ao conteúdo")
        gbtn_fit.setStyleSheet(
            f"QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_PRIMARY}; "
            f"border:1px solid {Colors.BORDER_DEFAULT}; border-radius:3px; "
            f"font-size:9px; padding:0 7px; }} "
            f"QPushButton:hover {{ background:{Colors.BG_PANEL}; }}"
        )

        lbl_ghint = QLabel("⬚ Seleção ativa · Scroll=zoom · Btn3=pan · Del=remove")
        lbl_ghint.setStyleSheet(f"color:{Colors.TEXT_DIM}; font-size:9px; background:transparent;")

        gtb_lay.addWidget(gbtn_delete)
        gtb_lay.addWidget(gbtn_save)
        gtb_lay.addWidget(gbtn_fit)
        gtb_lay.addStretch()
        gtb_lay.addWidget(lbl_ghint)
        gran_lay.addWidget(gran_toolbar)

        # CADCanvas granular — sempre em modo select; pan via botão do meio
        self.canvas_granular = CADCanvas()
        self.canvas_granular.toolbar.setVisible(False)
        self.canvas_granular.set_edit_mode('select')
        gran_lay.addWidget(self.canvas_granular, 1)

        self._tabs.addTab(gran_container, "Visualizador Granular")

        # Conectar toolbar granular
        gbtn_delete.clicked.connect(self._delete_selected_granular)
        gbtn_save.clicked.connect(self._save_granular_dxf)
        gbtn_fit.clicked.connect(self._fit_granular)
        self.canvas_granular.keyPressEvent = self._canvas_granular_key_press

        # ── Tab 3 — Ficha Granular ──
        self._ficha_table = QTableWidget(0, 2)
        self._ficha_table.setHorizontalHeaderLabels(["Campo", "Valor"])
        self._ficha_table.horizontalHeader().setStretchLastSection(True)
        self._ficha_table.setStyleSheet(
            f"background:{Colors.BG_CARD}; color:{Colors.TEXT_PRIMARY}; "
            f"gridline-color:{Colors.BORDER_DEFAULT}; font-size:10px;"
        )
        self._tabs.addTab(self._ficha_table, "Ficha Granular")

        # ── Tab 4 — Ficha Obra ER ──
        self._obra_text = QTextEdit()
        self._obra_text.setReadOnly(True)
        self._obra_text.setPlaceholderText(
            "Execute 'Processar todos itens granulares da Obra'\npara gerar a ficha da obra."
        )
        self._obra_text.setStyleSheet(
            f"background:{Colors.BG_CARD}; color:{Colors.TEXT_PRIMARY}; font-size:10px;"
        )
        self._tabs.addTab(self._obra_text, "Ficha Obra Engenharia Reversa")

        # Lazy load: dispara carregamento do completo só ao ativar a aba
        self._tabs.currentChanged.connect(self._on_tab_changed)

    # ── Toolbar helpers ───────────────────────────────────────────────

    def _delete_selected(self):
        canvas = self.canvas
        items = list(canvas.selected_items) if canvas.selected_items else canvas.scene.selectedItems()
        if not items:
            return
        for item in items:
            try:
                canvas.scene.removeItem(item)
            except RuntimeError:
                pass
        canvas.selected_items.clear()
        # Manter modo select ativo após deletar

    def _fit_view(self):
        rect = self.canvas.scene.itemsBoundingRect()
        if not rect.isEmpty():
            self.canvas.fitInView(rect, Qt.KeepAspectRatio)

    def _canvas_key_press(self, event):
        from PySide6.QtCore import Qt as _Qt
        if event.key() == _Qt.Key_Delete:
            self._delete_selected()
        else:
            CADCanvas.keyPressEvent(self.canvas, event)

    # ── Toolbar helpers — Granular ────────────────────────────────────

    def _delete_selected_granular(self):
        canvas = self.canvas_granular
        items = list(canvas.selected_items) if canvas.selected_items else canvas.scene.selectedItems()
        if not items:
            return
        for item in items:
            try:
                # Guardar data(0) para uso no save (matching contra ezdxf)
                d = item.data(0)
                if d:
                    self._granular_deleted.append(d)
                canvas.scene.removeItem(item)
            except RuntimeError:
                pass
        canvas.selected_items.clear()
        # Manter modo select ativo após deletar

    def _fit_granular(self):
        rect = self.canvas_granular.scene.itemsBoundingRect()
        if not rect.isEmpty():
            self.canvas_granular.fitInView(rect, Qt.KeepAspectRatio)

    def _save_granular_dxf(self):
        """
        Salva edições do canvas_granular de volta ao DXF original.

        Estratégia: exporta o estado ATUAL da cena para o arquivo
        (o que resta na cena após deleções é exatamente o que deve ser salvo).
        """
        if not self._granular_dxf_path:
            QMessageBox.warning(self, "Salvar", "Nenhum recorte granular carregado.")
            return

        out_path = Path(self._granular_dxf_path)

        result = _CenterPanel.export_scene_to_dxf(self.canvas_granular, out_path)
        if result.get('error'):
            QMessageBox.critical(self, "Salvar Granular",
                                 f"Erro ao salvar:\n{result['error']}")
            return

        self._granular_deleted.clear()
        n = result.get('entities_copied', 0)
        QMessageBox.information(
            self, "Salvar Granular",
            f"DXF salvo com sucesso.\n{n} entidade(s) · {out_path.name}"
        )

    def _save_granular_dxf_silent(self):
        """
        Versão silenciosa — chamada pelo botão Salvar do painel direito.
        Só age se há deleções pendentes. Sem dialogs de sucesso.
        """
        if not self._granular_dxf_path:
            return
        if not self._granular_deleted:
            return  # nada foi editado, não sobrescrever

        out_path = Path(self._granular_dxf_path)

        result = _CenterPanel.export_scene_to_dxf(self.canvas_granular, out_path)
        if result.get('error'):
            QMessageBox.critical(self, "Salvar Granular",
                                 f"Erro ao salvar edições DXF:\n{result['error']}")
            return

        self._granular_deleted.clear()

    def _canvas_granular_key_press(self, event):
        from PySide6.QtCore import Qt as _Qt
        if event.key() == _Qt.Key_Delete:
            self._delete_selected_granular()
        else:
            CADCanvas.keyPressEvent(self.canvas_granular, event)

    # ── Loading assíncrono ────────────────────────────────────────────

    def _on_tab_changed(self, idx: int):
        """Lazy-load do DXF completo: só renderiza quando a aba for ativada."""
        if idx == 0 and self._pending_completo_dxf:
            path = self._pending_completo_dxf
            self._pending_completo_dxf = None
            self._do_load_dxf_completo(path)

    def load_dxf_completo(self, dxf_path: str):
        """Agenda carregamento do DXF no viewer completo.

        Se Tab 0 (Visualizador Projeto Completo) não estiver ativa, apenas
        armazena o path — o carregamento ocorre quando o usuário clicar na aba.
        Isso evita bloquear o main thread durante a navegação de pavimentos.
        """
        if not dxf_path:
            # Sem DXF: limpar canvas e cancelar pending
            self._pending_completo_dxf = None
            self.canvas.scene.clear()
            self.canvas.set_loading(False)
            return

        if self._tabs.currentIndex() != 0:
            # Aba não está ativa — diferir carregamento
            self._pending_completo_dxf = dxf_path
            # Limpar canvas anterior + mostrar placeholder (sem bloquear)
            self.canvas.scene.clear()
            self.canvas.set_loading(True, "◀ Clique em 'Visualizador Projeto Completo' para carregar")
            return

        # Aba está ativa — carregar agora
        self._pending_completo_dxf = None
        self._do_load_dxf_completo(dxf_path)

    def _do_load_dxf_completo(self, dxf_path: str):
        """Carrega DXF no CADCanvas via DXFLoadWorker (async, thread-safe)."""
        try:
            p = Path(dxf_path)
            if not p.exists():
                return
        except OSError:
            return

        try:
            from src.ui.workers import DXFLoadWorker
        except ImportError:
            return

        canvas = self.canvas
        canvas_id = id(canvas)
        canvas.scene.clear()
        canvas.set_loading(True, "⌛ Carregando DXF…")

        thread = QThread()
        worker = DXFLoadWorker(str(dxf_path))
        worker.moveToThread(thread)
        # Sem cap — qualidade total. Performance garantida pelo viewport trick em on_loaded.
        proxy  = _DXFRenderProxy(canvas, thread, self._canvas_pending, parent=self)
        self._canvas_pending[canvas_id] = thread

        thread.started.connect(worker.run)
        worker.finished.connect(proxy.on_loaded)
        worker.error.connect(proxy.on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        self._dxf_threads.append(thread)
        self._dxf_workers.append(worker)
        self._dxf_proxies.append(proxy)
        thread.start()

    def load_dxf_granular(self, dxf_path: str | None):
        """Carrega DXF no CADCanvas granular via DXFLoadWorker (async, thread-safe)."""
        if not dxf_path or not Path(dxf_path).exists():
            self._granular_dxf_path = None
            self._granular_deleted = []
            self.canvas_granular.scene.clear()
            self.canvas_granular.set_loading(False)
            return

        self._granular_dxf_path = dxf_path
        self._granular_deleted = []  # reset ao carregar novo recorte

        try:
            from src.ui.workers import DXFLoadWorker
        except ImportError:
            return

        canvas = self.canvas_granular
        canvas_id = id(canvas)
        canvas.scene.clear()
        canvas.set_loading(True, "⌛ Carregando DXF granular…")

        thread = QThread()
        worker = DXFLoadWorker(str(dxf_path))
        worker.moveToThread(thread)
        proxy  = _DXFRenderProxy(canvas, thread, self._canvas_pending, parent=self)
        self._canvas_pending[canvas_id] = thread

        thread.started.connect(worker.run)
        worker.finished.connect(proxy.on_loaded)
        worker.error.connect(proxy.on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        self._dxf_threads.append(thread)
        self._dxf_workers.append(worker)
        self._dxf_proxies.append(proxy)
        thread.start()

    def load_ficha_granular(self, campos_json: str | None):
        self._ficha_table.setRowCount(0)
        if not campos_json:
            return
        try:
            data: dict = json.loads(campos_json)
        except Exception:
            return
        for campo, valor in data.items():
            row = self._ficha_table.rowCount()
            self._ficha_table.insertRow(row)
            self._ficha_table.setItem(row, 0, QTableWidgetItem(str(campo)))
            self._ficha_table.setItem(row, 1, QTableWidgetItem(str(valor)))

    def load_ficha_obra(self, resumo_json: str | None):
        if not resumo_json:
            self._obra_text.setPlaceholderText(
                "Execute 'Processar todos itens granulares da Obra'\npara gerar a ficha da obra."
            )
            self._obra_text.clear()
            return
        try:
            data = json.loads(resumo_json)
            self._obra_text.setText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            self._obra_text.setText(resumo_json)

    # ── Export scene → DXF ────────────────────────────────────────────

    @staticmethod
    def export_scene_to_dxf(canvas: "CADCanvas", output_path: Path) -> dict:
        """Itera QGraphicsScene e grava DXF via ezdxf (mesma lógica do DiagnosticHub)."""
        try:
            import ezdxf
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()
            n = 0
            for item in canvas.scene.items():
                # Pular snap markers, overlays e itens internos do canvas:
                # — itens sem data(0) são snap markers / helpers criados diretamente
                # — itens invisíveis são marcadores ocultos (snap, temp, etc.)
                data = item.data(0)
                if not data:
                    continue
                if not item.isVisible():
                    continue
                layer  = str(data.get('layer', '0') or '0')
                aci    = data.get('aci', 256)
                attribs: dict = {'layer': layer}
                if isinstance(aci, int) and aci not in (0, 256):
                    attribs['color'] = aci

                if isinstance(item, QGraphicsLineItem):
                    ln = item.line()
                    msp.add_line((ln.x1(), ln.y1()), (ln.x2(), ln.y2()), dxfattribs=attribs)
                    n += 1
                elif isinstance(item, QGraphicsPathItem):
                    path = item.path()
                    pts = [(path.elementAt(i).x, path.elementAt(i).y)
                           for i in range(path.elementCount())]
                    if len(pts) >= 2:
                        msp.add_polyline2d(pts, dxfattribs=attribs)
                        n += 1
                elif isinstance(item, QGraphicsEllipseItem):
                    rect = item.rect()
                    cx, cy = rect.center().x(), rect.center().y()
                    rw, rh = rect.width() / 2, rect.height() / 2
                    if abs(rw - rh) < 0.5:
                        msp.add_circle((cx, cy), (rw + rh) / 2, dxfattribs=attribs)
                        n += 1
                elif isinstance(item, QGraphicsSimpleTextItem):
                    p = item.pos()
                    h = float(data.get('height', 2.5) or 2.5)
                    msp.add_text(item.text(),
                                 dxfattribs={**attribs, 'height': h,
                                             'insert': (p.x(), p.y())})
                    n += 1
            doc.saveas(str(output_path))
            return {'entities_copied': n}
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def export_selection_to_dxf(canvas: "CADCanvas", output_path: Path) -> dict:
        """Exporta APENAS os itens selecionados na scene para DXF."""
        try:
            import ezdxf
            selected = canvas.scene.selectedItems()
            # [FIX] Fallback para lista interna se scene foi limpa pelo QDialog.exec()
            if not selected:
                selected = [i for i in canvas.selected_items if i is not None]
            if not selected:
                return {'error': 'Nenhum item selecionado. Use box select no viewer antes de recortar.'}
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()
            n = 0
            for item in selected:
                data = item.data(0)
                if not data or not item.isVisible():
                    continue
                layer  = str(data.get('layer', '0') or '0')
                aci    = data.get('aci', 256)
                attribs: dict = {'layer': layer}
                if isinstance(aci, int) and aci not in (0, 256):
                    attribs['color'] = aci
                if isinstance(item, QGraphicsLineItem):
                    ln = item.line()
                    msp.add_line((ln.x1(), ln.y1()), (ln.x2(), ln.y2()), dxfattribs=attribs)
                    n += 1
                elif isinstance(item, QGraphicsPathItem):
                    path = item.path()
                    pts = [(path.elementAt(i).x, path.elementAt(i).y)
                           for i in range(path.elementCount())]
                    if len(pts) >= 2:
                        msp.add_polyline2d(pts, dxfattribs=attribs)
                        n += 1
                elif isinstance(item, QGraphicsEllipseItem):
                    rect = item.rect()
                    cx, cy = rect.center().x(), rect.center().y()
                    rw, rh = rect.width() / 2, rect.height() / 2
                    if abs(rw - rh) < 0.5:
                        msp.add_circle((cx, cy), (rw + rh) / 2, dxfattribs=attribs)
                        n += 1
                elif isinstance(item, QGraphicsSimpleTextItem):
                    p = item.pos()
                    h = float(data.get('height', 2.5) or 2.5)
                    msp.add_text(item.text(),
                                 dxfattribs={**attribs, 'height': h,
                                             'insert': (p.x(), p.y())})
                    n += 1
            doc.saveas(str(output_path))
            return {'entities_copied': n}
        except Exception as e:
            return {'error': str(e)}


# ── Widget de item de recorte com badge de status ─────────────────────────────

class _RecorteItemWidget(QWidget):
    """Item da lista de recortes: texto + badge confiança + badge status."""

    _STYLE_OK = (
        "background:#0d2b0d; color:#4caf50; border:1px solid #4caf50; "
        "border-radius:3px; font-size:8px; font-weight:bold; padding:0 3px;"
    )
    _STYLE_AUTO = (
        "background:#1a2a0d; color:#8bc34a; border:1px solid #8bc34a; "
        "border-radius:3px; font-size:8px; padding:0 3px;"
    )
    _STYLE_PEND = (
        "background:transparent; color:#777; border:1px solid #444; "
        "border-radius:3px; font-size:8px; padding:0 3px;"
    )
    _STYLE_CONF_HIGH  = "background:#0d2b0d; color:#4caf50; border:1px solid #4caf50; border-radius:3px; font-size:8px; font-weight:bold; padding:0 3px;"
    _STYLE_CONF_MED   = "background:#2b2000; color:#ffb300; border:1px solid #ffb300; border-radius:3px; font-size:8px; padding:0 3px;"
    _STYLE_CONF_LOW   = "background:#2b0000; color:#ef5350; border:1px solid #ef5350; border-radius:3px; font-size:8px; padding:0 3px;"
    _STYLE_CONF_NONE  = "background:transparent; color:#555; border:1px solid #333; border-radius:3px; font-size:8px; padding:0 3px;"

    def __init__(self, text: str, status: str, confidence: float | None = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        h = QHBoxLayout(self)
        h.setContentsMargins(4, 1, 4, 1)
        h.setSpacing(3)

        self._lbl_text = QLabel(text)
        self._lbl_text.setStyleSheet(
            "color:#cccccc; font-size:9px; background:transparent;"
        )
        self._lbl_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        h.addWidget(self._lbl_text, 1)

        # Badge de confiança (% do motor)
        self._lbl_conf = QLabel()
        self._lbl_conf.setFixedSize(38, 15)
        self._lbl_conf.setAlignment(Qt.AlignCenter)
        h.addWidget(self._lbl_conf)

        # Badge de status
        self._lbl_badge = QLabel()
        self._lbl_badge.setFixedSize(52, 15)
        self._lbl_badge.setAlignment(Qt.AlignCenter)
        h.addWidget(self._lbl_badge)

        self.set_confidence(confidence)
        self.set_status(status)

    def set_text(self, text: str):
        self._lbl_text.setText(text)

    def get_text(self) -> str:
        return self._lbl_text.text()

    def set_confidence(self, confidence: float | None):
        if confidence is None:
            self._lbl_conf.setText("—")
            self._lbl_conf.setStyleSheet(self._STYLE_CONF_NONE)
            self._lbl_conf.setToolTip("Confiança não calculada")
        elif confidence >= 90:
            self._lbl_conf.setText(f"{confidence:.0f}%")
            self._lbl_conf.setStyleSheet(self._STYLE_CONF_HIGH)
            self._lbl_conf.setToolTip(f"Confiança alta: {confidence:.1f}%")
        elif confidence >= 70:
            self._lbl_conf.setText(f"{confidence:.0f}%")
            self._lbl_conf.setStyleSheet(self._STYLE_CONF_MED)
            self._lbl_conf.setToolTip(f"Confiança média: {confidence:.1f}%")
        else:
            self._lbl_conf.setText(f"{confidence:.0f}%")
            self._lbl_conf.setStyleSheet(self._STYLE_CONF_LOW)
            self._lbl_conf.setToolTip(f"Confiança baixa: {confidence:.1f}% — revisar")

    def set_status(self, status: str):
        _map = {
            "aprovado":      ("✓ humano",   self._STYLE_OK),
            "approved":      ("✓ humano",   self._STYLE_OK),   # compat legado
            "auto_aprovado": ("⚡ auto",    self._STYLE_AUTO),
            "motor":         ("⚙ motor",   self._STYLE_PEND),
            "manual":        ("✏ manual",  self._STYLE_PEND),
        }
        txt, style = _map.get(status, ("⏳ pend.", self._STYLE_PEND))
        self._lbl_badge.setText(txt)
        self._lbl_badge.setStyleSheet(style)


# ── Painel Direito ────────────────────────────────────────────────────────────

class _RightPanel(QFrame):
    """Lista de recortes granulares + botões de ação por item selecionado na esquerda."""

    recortar_requested          = Signal(str, str)  # elemento_id, classe
    recortar_selecao_requested  = Signal(str, str)  # elemento_id, classe
    processar_cls               = Signal(str)       # classe
    salvar_requested            = Signal()
    aprovar_requested           = Signal()
    aprovar_auto_requested      = Signal()          # auto-aprova ≥90% (sem treino)
    excluir_requested           = Signal()
    processar_tudo              = Signal()
    gerar_ficha_requested       = Signal()          # gerar fichas obra para itens aprovados
    recorte_selected            = Signal(str)       # dxf_path do recorte clicado

    # [FIX] referência ao canvas para pré-verificar seleção antes de abrir dialog
    _canvas_ref = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(230)
        self.setStyleSheet(f"background:{Colors.BG_SECONDARY};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 8, 6, 8)
        lay.setSpacing(5)

        def _btn(text: str, bg: str, hover: str, h: int = 26) -> QPushButton:
            b = QPushButton(text)
            b.setFixedHeight(h)
            b.setStyleSheet(
                f"QPushButton {{ background:{bg}; color:#fff; border-radius:3px; "
                f"font-size:9px; font-weight:bold; padding:2px 4px; }} "
                f"QPushButton:hover {{ background:{hover}; }} "
                f"QPushButton:disabled {{ background:{Colors.BORDER_DEFAULT}; color:{Colors.TEXT_DIM}; }}"
            )
            return b

        # ── Seção: Lista de Recortes ──────────────────────────────────
        lbl_rec = QLabel("Recortes Granulares")
        lbl_rec.setStyleSheet(
            f"color:{Colors.ACCENT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;"
        )
        lay.addWidget(lbl_rec)

        self._lbl_recortes_count = QLabel("— selecione um item —")
        self._lbl_recortes_count.setStyleSheet(
            f"color:{Colors.TEXT_DIM}; font-size:9px; background:transparent;"
        )
        lay.addWidget(self._lbl_recortes_count)

        self.lst_recortes = QListWidget()
        self.lst_recortes.setStyleSheet(f"""
            QListWidget {{
                background:{Colors.BG_DEEP}; color:{Colors.TEXT_PRIMARY};
                border:1px solid {Colors.BORDER_DEFAULT}; font-size:9px;
            }}
            QListWidget::item {{ padding:2px 4px; }}
            QListWidget::item:selected {{ background:{Colors.ACCENT_BLUE}; color:{Colors.TEXT_BRIGHT}; }}
            QListWidget::item:hover {{ background:{Colors.BG_CARD}; }}
        """)
        self.lst_recortes.itemClicked.connect(self._on_recorte_clicked)
        lay.addWidget(self.lst_recortes, 1)   # stretch — ocupa espaço disponível

        lay.addWidget(self._sep())

        # ── Seção: Ações ──────────────────────────────────────────────
        # Recortar (todas as entidades visíveis)
        btn_rec = _btn("✂ Recortar", "#1b3a6b", "#2a5ab0")
        btn_rec.setToolTip("Recortar — exporta todas as entidades visíveis do canvas")
        btn_rec.clicked.connect(self._on_recortar)
        lay.addWidget(btn_rec)

        # Recortar Seleção (apenas itens selecionados via box select)
        btn_rec_sel = _btn("✂ Recortar Seleção", "#4a1a7a", "#7a3ab0")
        btn_rec_sel.setToolTip(
            "Recortar Seleção — exporta apenas os itens selecionados (box select) do canvas"
        )
        btn_rec_sel.clicked.connect(self._on_recortar_selecao)
        lay.addWidget(btn_rec_sel)

        lay.addWidget(self._sep())

        # 4 botões Processar por classe
        lbl_proc = QLabel("Processar Granulares:")
        lbl_proc.setStyleSheet(f"color:{Colors.TEXT_DIM}; font-size:9px; background:transparent;")
        lay.addWidget(lbl_proc)

        for cls_key, cls_label, bg, hover in [
            ("PIL", "Pilares",  "#1b3a6b", "#2a5ab0"),
            ("LV",  "L.Vigas",  "#1a4a2a", "#2a7a4a"),
            ("FV",  "F.Vigas",  "#4a2a00", "#8a5a00"),
            ("LAJ", "Lajes",    "#4a002a", "#8a0050"),
        ]:
            b = _btn(f"▶ {cls_label}", bg, hover)
            b.setToolTip(f"Processar Granulares {cls_label} — DXF selecionado")
            b.clicked.connect(lambda _c, k=cls_key: self._on_processar_cls(k))
            lay.addWidget(b)

        # ⚡ Processar TODOS — todos pavimentos × todas classes da obra
        btn_tudo = _btn("⚡ Processar toda a Obra\n(todos pavimentos × classes)", "#3a1a5a", "#5a2a8a", h=44)
        btn_tudo.setToolTip(
            "Roda PIL/LV/FV/LAJ em todos os pavimentos aprovados da obra.\n"
            "Cada classe usa o DXF correto automaticamente."
        )
        btn_tudo.clicked.connect(self._on_processar_tudo)
        lay.addWidget(btn_tudo)

        # 📋 Gerar fichas — apenas itens aprovados (treino)
        btn_ficha = _btn(
            "📋 Gerar Ficha Obra\ne Fichas Granulares\n(itens aprovados)", "#1a3a1a", "#2a6a2a", h=52
        )
        btn_ficha.setToolTip(
            "Para cada pavimento que tenha ≥ 1 recorte com status 'aprovado',\n"
            "gera a Ficha Granular (campos N2) e consolida a Ficha Obra ER.\n"
            "Somente itens aprovados 1-a-1 entram no processamento.\n"
            "(Motor de extração ER-3 — em construção)"
        )
        btn_ficha.clicked.connect(self._on_gerar_ficha)
        lay.addWidget(btn_ficha)

        lay.addWidget(self._sep())

        # ── Ajustar Classe do recorte selecionado ────────────────────
        lbl_cls_adj = QLabel("Ajustar Classe:")
        lbl_cls_adj.setStyleSheet(
            f"color:{Colors.TEXT_DIM}; font-size:9px; background:transparent;"
        )
        lay.addWidget(lbl_cls_adj)

        cls_frame = QFrame()
        cls_frame.setStyleSheet(
            f"background:{Colors.BG_CARD}; border:1px solid {Colors.BORDER_DEFAULT}; "
            f"border-radius:4px;"
        )
        cls_lay = QVBoxLayout(cls_frame)
        cls_lay.setContentsMargins(6, 4, 6, 4)
        cls_lay.setSpacing(3)

        self._cls_radios: dict[str, QRadioButton] = {}
        self._cls_group = QButtonGroup(self)
        rb_style = (
            f"QRadioButton {{ color:{Colors.TEXT_PRIMARY}; font-size:10px; "
            f"background:transparent; }}"
            f"QRadioButton::indicator {{ width:12px; height:12px; }}"
            f"QRadioButton::indicator:checked {{ background:{Colors.ACCENT_BLUE}; "
            f"border:2px solid {Colors.ACCENT_BLUE}; border-radius:6px; }}"
            f"QRadioButton::indicator:unchecked {{ background:transparent; "
            f"border:2px solid {Colors.BORDER_DEFAULT}; border-radius:6px; }}"
        )
        for i, (key, label) in enumerate(_CLASSES):
            rb = QRadioButton(label)
            rb.setStyleSheet(rb_style)
            self._cls_group.addButton(rb, i)
            self._cls_radios[key] = rb
            cls_lay.addWidget(rb)

        lay.addWidget(cls_frame)

        lay.addWidget(self._sep())

        # Salvar / Aprovar / Excluir
        btn_salvar  = _btn("💾 Salvar",  Colors.ACCENT_BLUE,    Colors.ACCENT_BLUE_HOVER)
        btn_excluir = _btn("🗑 Excluir", Colors.ACCENT_DANGER,   "rgba(211,47,47,1)")

        # Aprovar tudo ≥ 90%: auto-aprova sem revisão humana (NÃO entra como treino)
        btn_auto_aprovar = _btn("⚡ Aprovar tudo ≥ 90%", "#1a4a1a", "#2a7a2a", h=36)
        btn_auto_aprovar.setToolTip(
            "Aprova automaticamente todos os recortes com confiança ≥ 90%.\n"
            "⚠️ Estes NÃO são usados como dados de treino.\n"
            "Use apenas para avançar — revisão humana 1-a-1 gera dados reais."
        )
        btn_auto_aprovar.clicked.connect(self._on_aprovar_auto)

        btn_aprovar = _btn("✅ Aprovar", Colors.ACCENT_SUCCESS,  "rgba(67,160,71,1)")
        btn_aprovar.setToolTip("Aprova este recorte com revisão humana — gera dado de treino autêntico.")

        btn_salvar.clicked.connect(self._on_salvar)
        btn_aprovar.clicked.connect(self._on_aprovar)
        btn_excluir.clicked.connect(self._on_excluir)
        lay.addWidget(btn_salvar)
        lay.addWidget(btn_auto_aprovar)
        lay.addWidget(btn_aprovar)
        lay.addWidget(btn_excluir)

        lay.addWidget(self._sep())

        # ── Área de progresso do motor ────────────────────────────────
        # Label de status: "PIL · 1° PAV PL  (3/12 DXFs)"
        self._lbl_motor_status = QLabel("")
        self._lbl_motor_status.setVisible(False)
        self._lbl_motor_status.setStyleSheet(
            f"color:{Colors.ACCENT_BLUE}; font-size:9px; font-weight:bold; background:transparent;"
        )
        self._lbl_motor_status.setWordWrap(True)
        lay.addWidget(self._lbl_motor_status)

        # ProgressBar (agora determinada quando total conhecido)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(12)
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%v / %m")
        self.progress.setStyleSheet(
            f"QProgressBar {{ background:{Colors.BG_DEEP}; border-radius:3px; "
            f"  color:{Colors.TEXT_DIM}; font-size:8px; }} "
            f"QProgressBar::chunk {{ background:{Colors.ACCENT_BLUE}; border-radius:3px; }}"
        )
        lay.addWidget(self.progress)

        # Label de detalhe: "P12 (elemento 8/37)"
        self._lbl_motor_detail = QLabel("")
        self._lbl_motor_detail.setVisible(False)
        self._lbl_motor_detail.setStyleSheet(
            f"color:{Colors.TEXT_DIM}; font-size:8px; background:transparent;"
        )
        lay.addWidget(self._lbl_motor_detail)

    # ── API pública ───────────────────────────────────────────────────

    def load_recortes(self, proj_id: str, obra_name: str, dxf_path: str):
        """Popula a lista de recortes granulares para o item selecionado na esquerda."""
        self.lst_recortes.clear()

        rows: list = []

        # 1. Busca em reverse_eng_recortes (recortes do motor reverso) — inclui confiança
        rows += _db_query(
            "SELECT recorte_path, elemento_id, classe, status, confidence "
            "FROM reverse_eng_recortes "
            "WHERE projeto_id=? ORDER BY elemento_id ASC",
            (proj_id,)
        )

        # 2. Busca em obra_recortes (recortes do DiagnosticHub) vinculados ao mesmo DXF
        if dxf_path:
            fname = Path(dxf_path).name
            extra = _db_query(
                "SELECT recorte_path, element_id, element_type, status, NULL "
                "FROM obra_recortes "
                "WHERE obra_name=? AND dxf_bruto_path LIKE ? ORDER BY element_id ASC",
                (obra_name, f"%{fname}%")
            )
            rows += extra

        if not rows:
            self._lbl_recortes_count.setText("0 recortes")
            ph = QListWidgetItem("— nenhum recorte ainda —")
            ph.setForeground(QColor(Colors.TEXT_DIM))
            ph.setFlags(ph.flags() & ~Qt.ItemIsSelectable)
            self.lst_recortes.addItem(ph)
            return

        # Métricas de progresso
        total = len(rows)
        aprovados   = sum(1 for r in rows if r[3] in ('aprovado', 'approved'))
        auto_apr    = sum(1 for r in rows if r[3] == 'auto_aprovado')
        conf_vals   = [r[4] for r in rows if r[4] is not None]
        avg_conf    = (sum(conf_vals) / len(conf_vals)) if conf_vals else None
        conf_str    = f"  conf.média: {avg_conf:.0f}%" if avg_conf is not None else ""
        self._lbl_recortes_count.setText(
            f"{total} recortes  ✓{aprovados}  ⚡{auto_apr}{conf_str}"
        )

        for row in rows:
            recorte_path  = row[0]
            elem_id       = row[1]
            cls_or_type   = row[2]
            status        = row[3]
            confidence    = row[4]  # float ou None
            label = f"{cls_or_type} · {elem_id}" if elem_id else (Path(recorte_path).stem if recorte_path else "?")
            it = QListWidgetItem()
            it.setSizeHint(QSize(220, 26))
            it.setData(Qt.UserRole,     recorte_path or "")
            it.setData(Qt.UserRole + 1, cls_or_type or "")
            it.setData(Qt.UserRole + 2, elem_id or "")
            it.setData(Qt.UserRole + 3, status or "")
            self.lst_recortes.addItem(it)
            self.lst_recortes.setItemWidget(
                it, _RecorteItemWidget(label, status or "", confidence)
            )

    def _on_recorte_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            self.recorte_selected.emit(path)
        # Sincronizar radio button com a classe do recorte clicado
        cls_key = item.data(Qt.UserRole + 1) or ""
        if cls_key in self._cls_radios:
            self._cls_radios[cls_key].setChecked(True)
        else:
            # Nenhuma classe reconhecida — desmarcar todos
            self._cls_group.setExclusive(False)
            for rb in self._cls_radios.values():
                rb.setChecked(False)
            self._cls_group.setExclusive(True)

    @staticmethod
    def _sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet(f"background:{Colors.BORDER_DEFAULT}; border:none;")
        return f

    def _open_recorte_dialog(self, title: str, hint: str):
        """Diálogo reutilizável: Nome/ID + 4 radio buttons de classe. Retorna (elem_id, cls_key) ou (None, None)."""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(340)
        dialog.setStyleSheet(f"background:{Colors.BG_PANEL}; color:{Colors.TEXT_PRIMARY};")
        dlg_lay = QVBoxLayout(dialog)
        dlg_lay.setSpacing(10)

        # Nome / ID
        dlg_lay.addWidget(QLabel("Nome / ID do elemento:"))
        le_id = QLineEdit()
        le_id.setPlaceholderText("ex: PIL-01, VIG-A3, LAJ-P02…")
        le_id.setStyleSheet(
            f"background:{Colors.BG_DEEP}; color:{Colors.TEXT_PRIMARY}; "
            f"border:1px solid {Colors.BORDER_DEFAULT}; border-radius:3px; padding:4px;"
        )
        dlg_lay.addWidget(le_id)

        # Classe — 4 radio buttons em linha
        dlg_lay.addWidget(QLabel("Classe do elemento:"))
        cls_frame = QFrame()
        cls_frame.setStyleSheet(
            f"background:{Colors.BG_DEEP}; border:1px solid {Colors.BORDER_DEFAULT}; border-radius:4px;"
        )
        cls_row = QHBoxLayout(cls_frame)
        cls_row.setContentsMargins(8, 6, 8, 6)
        cls_row.setSpacing(12)

        _cls_colors = {"PIL": "#7ab3e0", "LV": "#4caf50", "FV": "#ff9800", "LAJ": "#e91e63"}
        rb_group = QButtonGroup(dialog)
        radios = {}
        for i, (key, label) in enumerate(_CLASSES):
            color = _cls_colors.get(key, Colors.TEXT_PRIMARY)
            rb = QRadioButton(label)
            rb.setStyleSheet(
                f"QRadioButton {{ color:{color}; font-size:11px; font-weight:bold; background:transparent; border:none; }} "
                f"QRadioButton::indicator {{ width:14px; height:14px; }} "
                f"QRadioButton::indicator:checked {{ background:{color}; border:2px solid {color}; border-radius:7px; }} "
                f"QRadioButton::indicator:unchecked {{ background:transparent; border:2px solid {Colors.BORDER_DEFAULT}; border-radius:7px; }}"
            )
            rb_group.addButton(rb, i)
            cls_row.addWidget(rb)
            radios[key] = rb
        radios[_CLASSES[0][0]].setChecked(True)  # PIL selecionado por padrão
        dlg_lay.addWidget(cls_frame)

        # Hint
        lbl_hint = QLabel(hint)
        lbl_hint.setStyleSheet(f"color:{Colors.TEXT_DIM}; font-size:9px; background:transparent;")
        dlg_lay.addWidget(lbl_hint)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        dlg_lay.addWidget(btns)

        if dialog.exec() != QDialog.Accepted:
            return None, None

        elem_id = le_id.text().strip()
        cls_key = next((k for k, rb in radios.items() if rb.isChecked()), _CLASSES[0][0])
        return elem_id, cls_key

    def _on_recortar(self):
        """Abre dialog pedindo nome do elemento e classe, depois emite recortar_requested."""
        elem_id, cls_key = self._open_recorte_dialog(
            "Novo Recorte Granular",
            "💡 Use o modo Selecionar na toolbar para marcar\n"
            "   as entidades desejadas antes de clicar OK.\n"
            "   Apenas as entidades VISÍVEIS serão exportadas."
        )
        if not elem_id:
            if elem_id is not None:
                QMessageBox.warning(self, "Recortar", "Informe o nome/ID do elemento.")
            return
        self.recortar_requested.emit(elem_id, cls_key)

    def _on_recortar_selecao(self):
        """Mesmo dialog do Recortar, mas emite recortar_selecao_requested (só itens selecionados)."""
        # [FIX] Pré-verificar seleção ANTES de abrir o dialog (QDialog.exec() limpa scene)
        if self._canvas_ref is not None:
            canvas = self._canvas_ref
            has_sel = bool(canvas.scene.selectedItems()) or bool(canvas.selected_items)
            if not has_sel:
                QMessageBox.warning(
                    self, "Recortar Seleção",
                    "Nenhum item selecionado no canvas.\n"
                    "Use o modo Selecionar + box select antes de recortar."
                )
                return

        elem_id, cls_key = self._open_recorte_dialog(
            "Recortar Seleção",
            "💡 Selecione as entidades com box select no viewer\n"
            "   antes de confirmar. Apenas os itens SELECIONADOS\n"
            "   serão exportados para o recorte."
        )
        if not elem_id:
            if elem_id is not None:
                QMessageBox.warning(self, "Recortar Seleção", "Informe o nome/ID do elemento.")
            return
        self.recortar_selecao_requested.emit(elem_id, cls_key)

    def _on_processar_cls(self, cls: str):
        self.processar_cls.emit(cls)

    def _on_salvar(self):
        self.salvar_requested.emit()

    def _on_aprovar(self):
        self.aprovar_requested.emit()

    def _on_aprovar_auto(self):
        self.aprovar_auto_requested.emit()

    def _on_excluir(self):
        self.excluir_requested.emit()

    def _on_processar_tudo(self):
        self.processar_tudo.emit()

    def _on_gerar_ficha(self):
        self.gerar_ficha_requested.emit()


# ── Worker: Motor Reverso de Fichas ──────────────────────────────────────────

class _FichaMotorWorker(QObject):
    """
    Worker QThread para extrair fichas N2 de todos os recortes aprovados de uma obra.

    Emite progresso por elemento e resultado final.
    """
    progresso = Signal(int, int, str)   # (atual, total, mensagem)
    elemento_concluido = Signal(str, str, str, float)  # (classe, elemento_id, campos_json, confianca)
    concluido  = Signal(int, int)       # (n_ok, n_err)
    erro       = Signal(str)

    def __init__(self, obra_name: str, incluir_auto: bool = True, parent=None):
        super().__init__(parent)
        self.obra_name    = obra_name
        self.incluir_auto = incluir_auto

    def run(self):
        try:
            import sqlite3 as _sql
            import json as _json
            from pathlib import Path as _P

            conn = _sql.connect(DB_PATH)

            # Status aceitos
            status_filter = "('aprovado', 'auto_aprovado')" if self.incluir_auto else "('aprovado')"

            rows = conn.execute(f"""
                SELECT id, elemento_id, classe, recorte_path, status, projeto_id
                FROM reverse_eng_recortes
                WHERE obra_name=? AND status IN {status_filter}
                ORDER BY classe, elemento_id
            """, (self.obra_name,)).fetchall()
            conn.close()

            total = len(rows)
            if total == 0:
                self.concluido.emit(0, 0)
                return

            n_ok = 0
            n_err = 0

            for i, (rec_id, elem_id, classe, recorte_path, status, proj_id) in enumerate(rows):
                self.progresso.emit(i + 1, total, f"{classe} \u00b7 {elem_id}")

                try:
                    campos, conf = self._extrair_ficha(classe, elem_id, recorte_path)

                    # Inferir pavimento do recorte_path
                    pavimento = self._inferir_pavimento(recorte_path)

                    # Salvar em reverse_eng_fichas
                    self._salvar_ficha(
                        obra_name=self.obra_name,
                        pavimento=pavimento,
                        classe=classe,
                        elemento_id=elem_id,
                        campos_json=_json.dumps(campos, ensure_ascii=False),
                        recorte_path=recorte_path,
                        confianca=conf,
                        projeto_id=proj_id,
                    )

                    self.elemento_concluido.emit(classe, elem_id,
                                                 _json.dumps(campos, ensure_ascii=False), conf)
                    n_ok += 1

                except Exception as ex:
                    n_err += 1
                    import logging
                    logging.getLogger(__name__).warning("FichaWorker erro %s/%s: %s", classe, elem_id, ex)

            # Consolidar ficha obra para todos os pavimentos
            self._consolidar_obra()

            self.concluido.emit(n_ok, n_err)

        except Exception as ex:
            self.erro.emit(str(ex))

    def _extrair_ficha(self, classe: str, elem_id: str, recorte_path: str) -> tuple:
        """Chama o motor reverso correto para a classe."""
        import sys as _sys
        from pathlib import Path as _P
        # Garantir que scripts/ esta no path
        scripts_dir = str(_P(__file__).resolve().parent.parent.parent.parent / "scripts")
        if scripts_dir not in _sys.path:
            _sys.path.insert(0, scripts_dir)

        if classe == 'PIL':
            from motor_reverso_pil import extrair_ficha_pilar
            result = extrair_ficha_pilar(recorte_path, elem_id, self.obra_name)
        elif classe == 'LV':
            from motor_reverso_lv import extrair_ficha_lateral_viga
            result = extrair_ficha_lateral_viga(recorte_path, elem_id, self.obra_name)
        elif classe == 'FV':
            from motor_reverso_fv import extrair_ficha_fundo_viga
            result = extrair_ficha_fundo_viga(recorte_path, elem_id, self.obra_name)
        elif classe == 'LAJ':
            from motor_reverso_laj import extrair_ficha_laje
            result = extrair_ficha_laje(recorte_path, elem_id, self.obra_name)
        else:
            result = {'_er_meta': {'source': 'unknown'}, '_confianca': 0.0}

        conf = float(result.pop('_confianca', 0.5))
        return result, conf

    def _inferir_pavimento(self, recorte_path: str) -> str:
        """Extrai nome do pavimento a partir do path do recorte."""
        from pathlib import Path as _P
        import re as _re
        import unicodedata as _ucd
        # recortes_reversos/{DXF_STEM}/...
        p = _P(recorte_path)
        folder = p.parent.name
        folder_norm = _ucd.normalize('NFKD', folder)
        folder_norm = ''.join(c for c in folder_norm if not _ucd.combining(c))
        m = _re.search(r'(\d+)\s*[oO\u00b0]\s*PAV', folder_norm, _re.IGNORECASE)
        if m:
            return f"{m.group(1)}_PAV"
        if 'TIPO' in folder_norm.upper():
            return 'TIPO'
        if 'TERREO' in folder_norm.upper():
            return 'TERREO'
        if 'COB' in folder_norm.upper():
            return 'COBERTURA'
        return 'Pavimento'

    def _salvar_ficha(self, obra_name, pavimento, classe, elemento_id,
                      campos_json, recorte_path, confianca, projeto_id):
        """INSERT OR REPLACE em reverse_eng_fichas."""
        import sqlite3 as _sql
        from datetime import datetime as _dt
        conn = _sql.connect(DB_PATH)
        conn.execute("""
            INSERT INTO reverse_eng_fichas
                (projeto_id, obra_name, pavimento, classe, elemento_id,
                 campos_json, recorte_path, confianca, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,'draft',?,?)
            ON CONFLICT(obra_name, pavimento, elemento_id) DO UPDATE SET
                campos_json=excluded.campos_json,
                confianca=excluded.confianca,
                recorte_path=excluded.recorte_path,
                updated_at=excluded.updated_at
        """, (projeto_id, obra_name, pavimento, classe, elemento_id,
              campos_json, recorte_path, confianca,
              _dt.now().isoformat(), _dt.now().isoformat()))
        conn.commit()
        conn.close()

    def _consolidar_obra(self):
        """Chama motor_reverso_obra para gerar ficha consolidada da obra."""
        try:
            import sys as _sys
            from pathlib import Path as _P
            scripts_dir = str(_P(__file__).resolve().parent.parent.parent.parent / "scripts")
            if scripts_dir not in _sys.path:
                _sys.path.insert(0, scripts_dir)
            from motor_reverso_obra import consolidar_ficha_obra, salvar_ficha_obra
            resumo = consolidar_ficha_obra(self.obra_name)
            salvar_ficha_obra(self.obra_name, 'GERAL', resumo)
        except Exception as ex:
            import logging
            logging.getLogger(__name__).warning("Consolidar obra erro: %s", ex)


# ── Módulo Principal ─────────────────────────────────────────────────────────

class DiagnosticReverseHub(QWidget):
    """
    Tab 2 — Diagnostic Reverse Hub
    Visualiza, recorta e processa DXFs STOG humanos para gerar fichas granulares N2.

    Layout: [LeftPanel 220px] | [CenterPanel flex] | [RightPanel 200px]
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_obra: str = ""
        self._selected_proj_id: str = ""
        self._selected_dxf_path: str = ""

        self.setStyleSheet(f"background:{Colors.BG_DEEP};")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Painel Esquerdo ───────────────────────────────────────────
        self._left = _LeftPanel()
        self._left.item_selected.connect(self._on_item_selected)
        self._left.obra_changed.connect(lambda obra: setattr(self, '_current_obra', obra))
        root.addWidget(self._left)

        # ── Divisor central ──────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background:{Colors.BORDER_DEFAULT}; }}"
        )

        # ── Painel Central ────────────────────────────────────────────
        self._center = _CenterPanel()
        splitter.addWidget(self._center)

        root.addWidget(splitter, 1)

        # ── Painel Direito ────────────────────────────────────────────
        self._right = _RightPanel()
        self._right.salvar_requested.connect(self._on_salvar)
        self._right.aprovar_requested.connect(self._on_aprovar)
        self._right.aprovar_auto_requested.connect(self._on_aprovar_auto)
        self._right.excluir_requested.connect(self._on_excluir)
        self._right.recortar_requested.connect(self._on_recortar)
        self._right.recortar_selecao_requested.connect(self._on_recortar_selecao)
        # [FIX] Injetar canvas no _RightPanel para pré-verificação de seleção
        self._right._canvas_ref = self._center.canvas
        # Recorte clicado na lista direita → carrega DXF granular no centro
        self._right.recorte_selected.connect(self._center.load_dxf_granular)
        # Motores de recorte automático
        self._right.processar_cls.connect(self._on_processar_cls)
        self._right.processar_tudo.connect(self._on_processar_tudo)
        self._right.gerar_ficha_requested.connect(self._on_gerar_ficha)
        root.addWidget(self._right)

        # Worker de motor (para não bloquear UI)
        self._motor_worker: QThread | None = None

    # ── Slots públicos ───────────────────────────────────────────────

    def refresh_obras(self, obras: list[str] | None = None):
        """Sincroniza o combo de obras com a lista global (chamado por _refresh_nav_combos)."""
        self._left._populate_obra_combo(obras)

    def set_obra(self, obra_name: str):
        """Notificado quando a obra selecionada muda (via main.py)."""
        self._current_obra = obra_name
        self._left.set_obra(obra_name)
        self._load_obra_ficha(obra_name)

    # ── Slots internos ───────────────────────────────────────────────

    def _on_item_selected(self, obra_name: str, proj_id: str, dxf_path: str):
        self._selected_proj_id  = proj_id
        self._selected_dxf_path = dxf_path

        # Tab 1: DXF completo
        self._center.load_dxf_completo(dxf_path)

        # Tab 2: primeiro recorte disponível (será substituído quando usuário clicar na lista)
        recorte = self._get_recorte_path(proj_id)
        self._center.load_dxf_granular(recorte)

        # Tab 3: ficha granular (busca pelo elemento_id na obra)
        self._load_ficha_for_elemento(proj_id, obra_name)

        # Painel Direito: lista de recortes do item selecionado
        self._right.load_recortes(proj_id, obra_name, dxf_path)

    def _on_recortar(self, elemento_id: str, classe: str):
        """
        Exporta o estado atual do CADCanvas como DXF de recorte granular.
        Salva em reverse_eng_recortes e atualiza a lista no painel direito.
        """
        if not self._selected_proj_id or not self._selected_dxf_path:
            QMessageBox.warning(self, "Recortar", "Selecione um item da lista antes de recortar.")
            return

        import time, uuid as _uuid
        from datetime import datetime as _dt

        canvas = self._center.canvas
        if not canvas.scene.items():
            QMessageBox.warning(self, "Recortar", "O canvas está vazio. Selecione um item na lista para carregar o DXF.")
            return

        # ── Diretório de saída ────────────────────────────────────────────────
        dxf_stem = Path(self._selected_dxf_path).stem
        out_dir = DADOS_OBRAS_ROOT / self._current_obra / "Fase-2_Triagem" / "recortes_reversos" / dxf_stem
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        safe_id = elemento_id.replace("/", "-").replace("\\", "-").replace(" ", "_")
        out_path = out_dir / f"{classe}_{safe_id}_{ts}.dxf"
        while out_path.exists():
            ts += 1
            out_path = out_dir / f"{classe}_{safe_id}_{ts}.dxf"

        # ── Exportar scene → DXF ─────────────────────────────────────────────
        result = _CenterPanel.export_scene_to_dxf(canvas, out_path)
        if result.get("error"):
            QMessageBox.critical(self, "Recortar", f"Erro ao exportar:\n{result['error']}")
            return

        n_ent = result.get("entities_copied", 0)

        # ── Persistir em reverse_eng_recortes ────────────────────────────────
        # id é INTEGER PRIMARY KEY (autoincrement) — não passar
        now = _dt.now().isoformat()
        ok = _db_execute(
            """INSERT INTO reverse_eng_recortes
               (obra_name, projeto_id, elemento_id, classe,
                recorte_path, entity_count, status, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (self._current_obra, self._selected_proj_id,
             elemento_id, classe, str(out_path), n_ent, "manual", now)
        )
        if not ok:
            QMessageBox.warning(self, "Recortar", f"DXF salvo em {out_path.name}, mas erro ao registrar no banco.")
            return

        # ── Atualizar lista de recortes sem reload completo ───────────────────
        cls_labels = dict(_CLASSES)
        label = f"{cls_labels.get(classe, classe)} · {elemento_id}"
        it = QListWidgetItem()
        it.setSizeHint(QSize(220, 26))
        it.setData(Qt.UserRole,     str(out_path))
        it.setData(Qt.UserRole + 1, classe)
        it.setData(Qt.UserRole + 2, elemento_id)
        it.setData(Qt.UserRole + 3, "pending")
        self._right.lst_recortes.addItem(it)
        self._right.lst_recortes.setItemWidget(it, _RecorteItemWidget(label, "pending"))
        self._right.lst_recortes.setCurrentItem(it)
        # Sincronizar radio button com a classe do novo recorte
        if classe in self._right._cls_radios:
            self._right._cls_radios[classe].setChecked(True)
        count = self._right.lst_recortes.count()
        self._right._lbl_recortes_count.setText(f"{count} recortes")

        # Tab Visualizador Granular → mostra recorte recém criado
        self._center.load_dxf_granular(str(out_path))
        self._center._tabs.setCurrentIndex(1)

        QMessageBox.information(
            self, "Recorte salvo",
            f"✅ {out_path.name}\n{n_ent} entidades · {classe} · {elemento_id}"
        )

    def _on_recortar_selecao(self, elemento_id: str, classe: str):
        """
        Exporta APENAS os itens selecionados no canvas como DXF de recorte granular.
        """
        if not self._selected_proj_id or not self._selected_dxf_path:
            QMessageBox.warning(self, "Recortar Seleção", "Selecione um item da lista antes de recortar.")
            return

        import time, uuid as _uuid
        from datetime import datetime as _dt

        canvas = self._center.canvas

        # [FIX] QDialog.exec() cria loop modal que pode limpar scene.selectedItems().
        # canvas.selected_items é a lista Python interna — persiste mesmo após o dialog.
        # Restaurar a seleção da lista interna se a scene estiver vazia.
        if not canvas.scene.selectedItems() and canvas.selected_items:
            for item in list(canvas.selected_items):
                try:
                    item.setSelected(True)
                except RuntimeError:
                    canvas.selected_items.remove(item)

        selected = canvas.scene.selectedItems()
        if not selected:
            # Fallback: usar a lista interna diretamente
            selected = [i for i in canvas.selected_items if i is not None]

        if not selected:
            QMessageBox.warning(
                self, "Recortar Seleção",
                "Nenhum item selecionado no canvas.\n"
                "Use box select no viewer para selecionar a área desejada."
            )
            return

        dxf_stem = Path(self._selected_dxf_path).stem
        out_dir = DADOS_OBRAS_ROOT / self._current_obra / "Fase-2_Triagem" / "recortes_reversos" / dxf_stem
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        safe_id = elemento_id.replace("/", "-").replace("\\", "-").replace(" ", "_")
        out_path = out_dir / f"{classe}_{safe_id}_sel_{ts}.dxf"
        while out_path.exists():
            ts += 1
            out_path = out_dir / f"{classe}_{safe_id}_sel_{ts}.dxf"

        result = _CenterPanel.export_selection_to_dxf(canvas, out_path)
        if result.get("error"):
            QMessageBox.critical(self, "Recortar Seleção", f"Erro ao exportar:\n{result['error']}")
            return

        n_ent = result.get("entities_copied", 0)

        # id é INTEGER PRIMARY KEY (autoincrement) — não passar
        now = _dt.now().isoformat()
        ok = _db_execute(
            """INSERT INTO reverse_eng_recortes
               (obra_name, projeto_id, elemento_id, classe,
                recorte_path, entity_count, status, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (self._current_obra, self._selected_proj_id,
             elemento_id, classe, str(out_path), n_ent, "manual_sel", now)
        )
        if not ok:
            QMessageBox.warning(self, "Recortar Seleção",
                                f"DXF salvo em {out_path.name}, mas erro ao registrar no banco.")
            return

        cls_labels = dict(_CLASSES)
        label = f"[sel] {cls_labels.get(classe, classe)} · {elemento_id}"
        it = QListWidgetItem()
        it.setSizeHint(QSize(220, 26))
        it.setData(Qt.UserRole,     str(out_path))
        it.setData(Qt.UserRole + 1, classe)
        it.setData(Qt.UserRole + 2, elemento_id)
        it.setData(Qt.UserRole + 3, "pending")
        self._right.lst_recortes.addItem(it)
        self._right.lst_recortes.setItemWidget(it, _RecorteItemWidget(label, "pending"))
        self._right.lst_recortes.setCurrentItem(it)
        # Sincronizar radio button
        if classe in self._right._cls_radios:
            self._right._cls_radios[classe].setChecked(True)
        count = self._right.lst_recortes.count()
        self._right._lbl_recortes_count.setText(f"{count} recortes")

        self._center.load_dxf_granular(str(out_path))
        self._center._tabs.setCurrentIndex(1)

        QMessageBox.information(
            self, "Recorte de Seleção salvo",
            f"✅ {out_path.name}\n{n_ent} entidades selecionadas · {classe} · {elemento_id}"
        )

    def _on_salvar(self):
        """Salva a classe ajustada nos radio buttons para o recorte selecionado na lista."""
        lst = self._right.lst_recortes
        current = lst.currentItem()
        if current is None:
            QMessageBox.warning(self, "Aviso", "Selecione um recorte na lista antes de salvar.")
            return

        recorte_path = current.data(Qt.UserRole)
        if not recorte_path:
            QMessageBox.warning(self, "Aviso", "Item sem caminho de arquivo associado.")
            return

        # Descobrir qual radio está marcado
        new_cls = None
        for key, rb in self._right._cls_radios.items():
            if rb.isChecked():
                new_cls = key
                break

        if not new_cls:
            QMessageBox.warning(self, "Aviso", "Selecione uma classe antes de salvar.")
            return

        # Atualizar banco de dados
        _db_execute(
            "UPDATE reverse_eng_recortes SET classe=? WHERE recorte_path=?",
            (new_cls, recorte_path)
        )
        # Tentar também em obra_recortes (element_type)
        _db_execute(
            "UPDATE obra_recortes SET element_type=? WHERE recorte_path=?",
            (new_cls, recorte_path)
        )

        # Atualizar o label do item no widget visual
        cls_labels = dict(_CLASSES)
        elem_id = current.data(Qt.UserRole + 2) or ""
        widget = self._right.lst_recortes.itemWidget(current)
        # Detectar prefixo [sel] pelo texto atual do widget
        old_text = widget.get_text() if isinstance(widget, _RecorteItemWidget) else ""
        prefix = "[sel] " if old_text.startswith("[sel]") else ""
        new_label = f"{prefix}{cls_labels.get(new_cls, new_cls)} · {elem_id}" if elem_id \
                    else f"{prefix}{cls_labels.get(new_cls, new_cls)}"
        if isinstance(widget, _RecorteItemWidget):
            widget.set_text(new_label)

        # Salvar nova classe nos dados do item
        current.setData(Qt.UserRole + 1, new_cls)

        # Se há edições DXF pendentes no Visualizador Granular → salvar junto
        self._center._save_granular_dxf_silent()

    def _on_aprovar(self):
        """Aprova 1-a-1 com revisão humana — este recorte ENTRA nos dados de treino."""
        lst = self._right.lst_recortes
        current = lst.currentItem()
        if current is None:
            QMessageBox.warning(self, "Aviso", "Selecione um recorte na lista antes de aprovar.")
            return

        recorte_path = current.data(Qt.UserRole)
        if not recorte_path:
            QMessageBox.warning(self, "Aviso", "Item sem caminho associado.")
            return

        # status='aprovado' = revisão humana autêntica → usado em treino
        _db_execute(
            "UPDATE reverse_eng_recortes SET status='aprovado' WHERE recorte_path=?",
            (recorte_path,)
        )
        _db_execute(
            "UPDATE obra_recortes SET status='aprovado' WHERE recorte_path=?",
            (recorte_path,)
        )

        widget = lst.itemWidget(current)
        if isinstance(widget, _RecorteItemWidget):
            widget.set_status("aprovado")
        current.setData(Qt.UserRole + 3, "aprovado")

    def _on_aprovar_auto(self):
        """Aprova em bulk todos os recortes com confiança ≥ 90% da obra selecionada.

        status='auto_aprovado' — NÃO entra nos dados de treino.
        Serve apenas para avançar rapidamente; revisão humana 1-a-1 gera dados reais.
        """
        obra_name = self._current_obra or self._left._current_obra
        if not obra_name:
            QMessageBox.warning(self, "Auto-Aprovar", "Selecione uma obra primeiro.")
            return
        self._current_obra = obra_name

        THRESHOLD = 90.0

        # Contar quantos seriam aprovados
        rows = _db_query(
            "SELECT COUNT(*) FROM reverse_eng_recortes "
            "WHERE obra_name=? AND confidence >= ? AND status='motor'",
            (self._current_obra, THRESHOLD)
        )
        count = rows[0][0] if rows else 0

        if count == 0:
            QMessageBox.information(
                self, "Auto-Aprovar",
                f"Nenhum recorte com confiança ≥ {THRESHOLD:.0f}% encontrado.\n"
                "Execute os motores primeiro."
            )
            return

        reply = QMessageBox.question(
            self, "Auto-Aprovar",
            f"Aprovar automaticamente {count} recorte(s) com confiança ≥ {THRESHOLD:.0f}%?\n\n"
            "⚠️ Estes NÃO serão usados como dados de treino.\n"
            f"Obra: {self._current_obra}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        _db_execute(
            "UPDATE reverse_eng_recortes SET status='auto_aprovado' "
            "WHERE obra_name=? AND confidence >= ? AND status='motor'",
            (self._current_obra, THRESHOLD)
        )

        # Recarregar lista para refletir mudança
        self._right.load_recortes(
            self._selected_proj_id, self._current_obra, self._selected_dxf_path
        )

        QMessageBox.information(
            self, "Auto-Aprovar",
            f"{count} recorte(s) marcados como 'auto_aprovado'.\n"
            "Para gerar dados de treino, use ✅ Aprovar 1-a-1."
        )

    def _on_gerar_ficha(self):
        """
        Gera Ficha Granular (N2) e Ficha Obra ER para todos os recortes aprovados+auto_aprovados.

        Usa motores ER-3 (motor_reverso_pil/lv/fv/laj) via QThread para nao bloquear UI.
        Ao concluir: popula Tab 3 (Ficha Granular) e Tab 4 (Ficha Obra ER).
        """
        obra_name = self._current_obra or self._left._current_obra
        if not obra_name:
            QMessageBox.warning(self, "Gerar Ficha", "Selecione uma obra primeiro.")
            return
        self._current_obra = obra_name

        # Verificar se ja tem worker rodando
        if self._motor_worker and self._motor_worker.isRunning():
            QMessageBox.information(self, "Gerar Ficha", "Motor ja esta em execucao. Aguarde.")
            return

        # Contar recortes disponiveis
        total_rows = _db_query(
            "SELECT COUNT(*) FROM reverse_eng_recortes "
            "WHERE obra_name=? AND status IN ('aprovado','auto_aprovado')",
            (obra_name,)
        )
        total = total_rows[0][0] if total_rows else 0

        if total == 0:
            QMessageBox.information(
                self, "Gerar Ficha",
                f"Nenhum recorte aprovado ou auto_aprovado para '{obra_name}'.\n\n"
                "Use Aprovar ou Aprovar tudo >= 90% antes de gerar fichas."
            )
            return

        # Confirmar com o usuario
        resp = QMessageBox.question(
            self, "Gerar Fichas N2",
            f"Obra: {obra_name}\n"
            f"Total recortes: {total} (aprovados + auto_aprovados)\n\n"
            "O motor de Engenharia Reversa ira extrair fichas granulares N2\n"
            "para cada recorte e consolidar a Ficha Obra.\n\n"
            "Continuar?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        # Setup UI de progresso
        self._right.progress.setVisible(True)
        self._right.progress.setRange(0, total)
        self._right.progress.setValue(0)
        self._right._lbl_motor_status.setVisible(True)
        self._right._lbl_motor_status.setText(f"Gerando fichas N2 \u00b7 {obra_name}")
        self._right._lbl_motor_detail.setVisible(True)
        self._right._lbl_motor_detail.setText("Iniciando motores reversos...")

        # Criar worker + thread
        self._ficha_thread = QThread()
        self._ficha_worker = _FichaMotorWorker(obra_name, incluir_auto=True)
        self._ficha_worker.moveToThread(self._ficha_thread)

        self._ficha_thread.started.connect(self._ficha_worker.run)
        self._ficha_worker.progresso.connect(self._on_ficha_progresso)
        self._ficha_worker.elemento_concluido.connect(self._on_ficha_elemento)
        self._ficha_worker.concluido.connect(self._on_ficha_concluido)
        self._ficha_worker.erro.connect(self._on_ficha_erro)
        self._ficha_worker.concluido.connect(self._ficha_thread.quit)
        self._ficha_worker.erro.connect(self._ficha_thread.quit)
        self._ficha_thread.finished.connect(self._ficha_thread.deleteLater)

        self._ficha_thread.start()

    def _on_ficha_progresso(self, atual: int, total: int, msg: str):
        self._right.progress.setMaximum(total)
        self._right.progress.setValue(atual)
        self._right._lbl_motor_detail.setText(f"{msg}  ({atual}/{total})")

    def _on_ficha_elemento(self, classe: str, elem_id: str, campos_json: str, conf: float):
        """Chamado para cada elemento processado -- atualiza Tab 3 se for o item selecionado."""
        selected = self._right.lst_recortes.currentItem()
        if selected:
            sel_elem = selected.data(Qt.UserRole + 2)
            sel_cls  = selected.data(Qt.UserRole + 1)
            if sel_elem == elem_id and sel_cls == classe:
                self._center.load_ficha_granular(campos_json)

    def _on_ficha_concluido(self, n_ok: int, n_err: int):
        self._right.progress.setVisible(False)
        self._right._lbl_motor_status.setText(
            f"{n_ok} fichas geradas" + (f"  {n_err} erros" if n_err else "")
        )
        self._right._lbl_motor_detail.setVisible(False)

        # Atualizar Tab 4 (Ficha Obra)
        self._load_obra_ficha(self._current_obra)

        # Atualizar Tab 3 para o item selecionado (se houver)
        selected = self._right.lst_recortes.currentItem()
        if selected:
            elem_id = selected.data(Qt.UserRole + 2)
            if elem_id:
                self._load_ficha_for_elemento(elem_id, self._current_obra)

        QMessageBox.information(
            self, "Fichas N2 Geradas",
            f"Motor de Engenharia Reversa concluido.\n"
            f"{n_ok} fichas geradas  {'  ' + str(n_err) + ' erros' if n_err else ''}\n\n"
            "Acesse Tab 'Ficha Granular' para ver os campos N2.\n"
            "Acesse Tab 'Ficha Obra Engenharia Reversa' para o resumo da obra."
        )

    def _on_ficha_erro(self, msg: str):
        self._right.progress.setVisible(False)
        self._right._lbl_motor_status.setText("Erro no motor")
        QMessageBox.critical(self, "Erro Motor ER-3", f"Erro ao gerar fichas:\n{msg}")

    def _load_ficha_for_elemento(self, id_or_elem: str, obra_name: str):
        """Carrega ficha granular para um elemento especifico em Tab 3.

        Tenta primeiro por elemento_id na obra, depois por projeto_id (fallback legado).
        """
        rows = _db_query(
            "SELECT campos_json FROM reverse_eng_fichas "
            "WHERE obra_name=? AND elemento_id=? ORDER BY updated_at DESC LIMIT 1",
            (obra_name, id_or_elem)
        )
        if not rows:
            # Fallback: proj_id numerico (legado)
            rows = _db_query(
                "SELECT campos_json FROM reverse_eng_fichas WHERE projeto_id=? LIMIT 1",
                (id_or_elem,)
            )
        self._center.load_ficha_granular(rows[0][0] if rows else None)

    def _on_excluir(self):
        """Exclui o recorte selecionado na lista direita (reverse_eng_recortes + arquivo físico)."""
        lst = self._right.lst_recortes
        current = lst.currentItem()
        if current is None:
            QMessageBox.warning(self, "Aviso", "Selecione um recorte na lista antes de excluir.")
            return

        recorte_path = current.data(Qt.UserRole)
        if not recorte_path:
            # Item placeholder (sem caminho) — apenas remove da lista
            lst.takeItem(lst.row(current))
            count = lst.count()
            self._right._lbl_recortes_count.setText(f"{count} recortes")
            return

        resp = QMessageBox.question(
            self, "Confirmar exclusão",
            f"Excluir este recorte?\n{Path(recorte_path).name}\n\nEsta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        # 1. Remover do banco de dados
        _db_execute(
            "DELETE FROM reverse_eng_recortes WHERE recorte_path=?",
            (recorte_path,)
        )

        # 2. Apagar arquivo físico DXF
        try:
            p = Path(recorte_path)
            if p.exists():
                p.unlink()
        except Exception:
            pass

        # 3. Remover da lista e atualizar contador
        lst.takeItem(lst.row(current))
        count = lst.count()
        self._right._lbl_recortes_count.setText(f"{count} recortes")

        # 4. Se lista ficou vazia, mostrar placeholder
        if count == 0:
            ph = QListWidgetItem("— nenhum recorte ainda —")
            from PySide6.QtGui import QColor
            ph.setForeground(QColor(Colors.TEXT_DIM))
            ph.setFlags(ph.flags() & ~Qt.ItemIsSelectable)
            lst.addItem(ph)
            self._right._lbl_recortes_count.setText("0 recortes")

    # ── Motor de Recorte Automático ──────────────────────────────────

    def _on_processar_cls(self, cls: str):
        """Roda RecorteMotor para a classe `cls` no DXF selecionado."""
        if not self._selected_dxf_path:
            QMessageBox.warning(self, "Motor", "Selecione um projeto na lista antes de processar.")
            return
        self._run_motor([cls])

    def _on_processar_tudo(self):
        """Roda RecorteMotor para todas as 4 classes — busca o DXF correto para cada classe."""
        # Prioridade: obra do item selecionado → obra do ComboBox do painel esquerdo
        obra_name = self._current_obra or self._left._current_obra
        if not obra_name:
            QMessageBox.warning(self, "Motor", "Selecione uma obra no combo antes de processar.")
            return
        # Garantir que o hub está sincronizado com o combobox
        self._current_obra = obra_name

        # Buscar todos os DXFs aprovados da obra e agrupar por classe ER
        # Buscar TODOS os DXFs aprovados da obra (todos pavimentos, todas classes)
        rows = _db_query(
            "SELECT id, file_name, file_path, notes FROM obra_triagem "
            "WHERE obra_name=? AND status='approved' "
            "AND (suggested_category LIKE '%Engenharia Reversa%' "
            "     OR suggested_category LIKE '%Projetos Finalizados%') "
            "ORDER BY file_name ASC",
            (self._current_obra,)
        )

        # Montar tasks: uma por (pavimento × classe) — cada DXF com o motor correto
        tasks_by_key: dict[str, tuple] = {}  # chave=f"{cls}|{fname}" → (cls, pid, fpath)
        for (row_id, fname, fpath, notes_json) in rows:
            if not fpath or not Path(fpath).exists():
                continue
            er_class = "OUTROS"
            if notes_json:
                try:
                    er_class = json.loads(notes_json).get("er_class", "OUTROS")
                except Exception:
                    pass
            if er_class == "OUTROS":
                er_class = _infer_cls_from_filename(fname or "")
            if er_class in ("PIL", "LV", "FV", "LAJ"):
                tasks_by_key[f"{er_class}|{fname}"] = (er_class, str(row_id), fpath)

        if not tasks_by_key:
            QMessageBox.warning(
                self, "Motor",
                f"Nenhum DXF aprovado encontrado para a obra '{self._current_obra}'.\n"
                "Verifique se os projetos estão com status 'approved' na triagem."
            )
            return

        obra_name = self._current_obra
        tasks = []
        cls_counts: dict[str, int] = {}
        for er_class, pid, fpath in tasks_by_key.values():
            dxf_stem = Path(fpath).stem
            out_dir = DADOS_OBRAS_ROOT / obra_name / "Fase-2_Triagem" / "recortes_reversos" / dxf_stem
            tasks.append((er_class, fpath, pid, out_dir))
            cls_counts[er_class] = cls_counts.get(er_class, 0) + 1

        summary = ", ".join(f"{cls}×{n}" for cls, n in sorted(cls_counts.items()))
        reply = QMessageBox.question(
            self, "Processar toda a Obra",
            f"Obra: {obra_name}\n"
            f"DXFs encontrados: {summary}\n"
            f"Total: {len(tasks)} motores\n\n"
            "Executar tudo? (pode demorar alguns minutos)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._run_motor_tasks(tasks, obra_name, label=f"{len(tasks)} DXFs")

    def _on_processar_cls(self, cls: str):
        """Roda RecorteMotor para a classe `cls` no DXF selecionado."""
        if not self._selected_dxf_path:
            QMessageBox.warning(self, "Motor", "Selecione um projeto na lista antes de processar.")
            return
        self._run_motor([cls])

    def _run_motor(self, classes: list[str]):
        """Dispara RecorteMotor para as classes indicadas usando o DXF selecionado."""
        if self._motor_worker and self._motor_worker.isRunning():
            QMessageBox.information(self, "Motor", "Motor já em execução. Aguarde terminar.")
            return

        obra_name = self._current_obra
        proj_id   = self._selected_proj_id
        dxf_path  = self._selected_dxf_path
        dxf_stem  = Path(dxf_path).stem
        out_dir   = DADOS_OBRAS_ROOT / obra_name / "Fase-2_Triagem" / "recortes_reversos" / dxf_stem

        tasks = [(cls, dxf_path, proj_id, out_dir) for cls in classes]
        cls_label = "/".join(classes) if len(classes) < 4 else "todas as classes"
        self._run_motor_tasks(tasks, obra_name, label=cls_label,
                              reload_proj_id=proj_id, reload_dxf=dxf_path)

    def _run_motor_tasks(
        self,
        tasks: list,           # lista de (cls, dxf_path, proj_id, out_dir)
        obra_name: str,
        *,
        label: str = "motor",
        reload_proj_id: str = "",
        reload_dxf: str = "",
    ):
        """Worker genérico — executa RecorteMotor para cada task (cls, dxf, proj_id, out_dir).

        Emite progresso granular (por elemento) para atualizar a barra e labels em tempo real.
        """
        if self._motor_worker and self._motor_worker.isRunning():
            QMessageBox.information(self, "Motor", "Motor já em execução. Aguarde terminar.")
            return

        progress_bar  = self._right.progress
        lbl_status    = self._right._lbl_motor_status
        lbl_detail    = self._right._lbl_motor_detail
        right_panel   = self._right
        n_tasks       = len(tasks)

        class _MotorWorker(QThread):
            finished     = Signal(list)
            error        = Signal(str)
            # task_started(task_idx, total_tasks, cls, dxf_name, n_elements)
            task_started = Signal(int, int, str, str, int)
            # elem_done(elem_idx, total_elems, elem_id, global_done, global_total)
            elem_done    = Signal(int, int, str, int, int)

            def __init__(self, tasks, obra_name, parent=None):
                super().__init__(parent)
                self._tasks = tasks
                self._obra  = obra_name

            def run(self):
                try:
                    from src.core.recorte_motor import RecorteMotor
                    from datetime import datetime as _dt
                    import sqlite3 as _sql

                    # Contar total de elementos estimado (descoberta prévia não é viável sem
                    # carregar todos os DXFs — usamos o nº de tasks × estimativa, atualizamos
                    # ao descobrir os elementos reais de cada DXF).
                    global_done  = 0
                    global_total = len(self._tasks)   # mínimo — atualizado ao descobrir elems
                    all_results  = []

                    for task_idx, (cls, dxf_path, proj_id, out_dir) in enumerate(self._tasks):
                        from pathlib import Path as _P
                        _P(out_dir).mkdir(parents=True, exist_ok=True)
                        dxf_name = _P(dxf_path).stem

                        try:
                            motor = RecorteMotor(dxf_path, er_type=cls)
                            motor._load_source()
                            elements = motor._discover_elements()
                            n_elems  = len(elements)

                            # Atualizar total global agora que sabemos quantos elementos há
                            global_total = global_total - 1 + n_elems  # substitui estimativa de 1
                            self.task_started.emit(task_idx, len(self._tasks), cls, dxf_name, n_elems)

                            conn = _sql.connect(DB_PATH)
                            cur  = conn.cursor()
                            now  = _dt.now().isoformat()

                            for elem_idx, (elem_id, label_pts, frame_bboxes) in enumerate(elements):
                                # Recortes aprovados manualmente (humano) sao referencias
                                # corretas usadas para treino — NUNCA sobrescrever arquivo
                                # nem registro ao reprocessar classe/obra.
                                cur.execute(
                                    "SELECT recorte_path, entity_count, confidence "
                                    "FROM reverse_eng_recortes "
                                    "WHERE projeto_id=? AND elemento_id=? AND classe=? AND status='aprovado'",
                                    (proj_id, elem_id, cls)
                                )
                                approved = cur.fetchone()
                                if approved:
                                    rec = {
                                        'elemento_id':  elem_id,
                                        'recorte_path': approved[0],
                                        'entity_count': approved[1],
                                        'confidence':   approved[2],
                                        'status':       'aprovado',
                                        '_skipped':     True,
                                    }
                                    global_done += 1
                                    all_results.append(rec)
                                    self.elem_done.emit(
                                        elem_idx + 1, n_elems,
                                        f"{elem_id} (aprovado, preservado)",
                                        global_done, global_total
                                    )
                                    continue

                                try:
                                    rec = motor._extract_one(
                                        elem_id, label_pts, frame_bboxes,
                                        _P(out_dir), overwrite=True
                                    )
                                except Exception as exc:
                                    rec = {'elemento_id': elem_id, 'entity_count': 0,
                                           'status': 'error', '_err': str(exc)}

                                if rec.get('recorte_path'):
                                    cur.execute(
                                        "SELECT id FROM reverse_eng_recortes "
                                        "WHERE projeto_id=? AND elemento_id=? AND classe=?",
                                        (proj_id, rec['elemento_id'], cls)
                                    )
                                    row = cur.fetchone()
                                    if row:
                                        cur.execute(
                                            "SELECT status FROM reverse_eng_recortes WHERE id=?",
                                            (row[0],)
                                        )
                                        cur_st = (cur.fetchone() or ('motor',))[0]
                                        keep   = cur_st if cur_st in ('aprovado', 'auto_aprovado') else 'motor'
                                        cur.execute(
                                            "UPDATE reverse_eng_recortes "
                                            "SET recorte_path=?, entity_count=?, status=?, confidence=? WHERE id=?",
                                            (rec['recorte_path'], rec['entity_count'], keep,
                                             rec.get('confidence'), row[0])
                                        )
                                    else:
                                        cur.execute(
                                            "INSERT INTO reverse_eng_recortes "
                                            "(obra_name, projeto_id, elemento_id, classe, "
                                            " recorte_path, entity_count, status, confidence, created_at) "
                                            "VALUES (?,?,?,?,?,?,?,?,?)",
                                            (self._obra, proj_id, rec['elemento_id'], cls,
                                             rec['recorte_path'], rec['entity_count'], 'motor',
                                             rec.get('confidence'), now)
                                        )
                                    conn.commit()

                                global_done += 1
                                all_results.append(rec)
                                self.elem_done.emit(
                                    elem_idx + 1, n_elems,
                                    elem_id,
                                    global_done, global_total
                                )

                            conn.close()

                        except Exception as exc:
                            global_done += 1
                            all_results.append({'elemento_id': '?', 'entity_count': 0,
                                                'status': 'error', '_cls': cls, '_err': str(exc)})
                            self.elem_done.emit(1, 1, '?', global_done, global_total)

                    self.finished.emit(all_results)
                except Exception as exc:
                    self.error.emit(str(exc))

        worker = _MotorWorker(tasks, obra_name)

        # ── Mostrar área de progresso ─────────────────────────────────
        progress_bar.setRange(0, max(n_tasks, 1))
        progress_bar.setValue(0)
        progress_bar.setVisible(True)
        lbl_status.setText(f"Iniciando — {n_tasks} DXF(s)…")
        lbl_status.setVisible(True)
        lbl_detail.setText("")
        lbl_detail.setVisible(True)

        def on_task_started(task_idx, total_tasks, cls, dxf_name, n_elems):
            short_name = dxf_name[-45:] if len(dxf_name) > 45 else dxf_name
            lbl_status.setText(
                f"[{task_idx + 1}/{total_tasks}]  {cls}  ·  {short_name}"
                f"  ({n_elems} elementos)"
            )
            lbl_detail.setText("aguardando primeiro elemento…")

        def on_elem_done(elem_idx, total_elems, elem_id, global_done, global_total):
            # Barra reflete progresso global
            progress_bar.setRange(0, max(global_total, 1))
            progress_bar.setValue(global_done)
            lbl_detail.setText(f"{elem_id}  ·  elem {elem_idx}/{total_elems}")

        def on_finished(results):
            progress_bar.setVisible(False)
            lbl_status.setVisible(False)
            lbl_detail.setVisible(False)
            ok  = sum(1 for r in results if r.get('entity_count', 0) > 0)
            err = sum(1 for r in results if r.get('status') == 'error')
            QMessageBox.information(
                self, "Motor concluído",
                f"Motor {label}: {ok} recortes extraídos"
                + (f"\n{err} erro(s)" if err else "")
            )
            if reload_proj_id and reload_dxf:
                right_panel.load_recortes(reload_proj_id, obra_name, reload_dxf)

        def on_error(msg):
            progress_bar.setVisible(False)
            lbl_status.setVisible(False)
            lbl_detail.setVisible(False)
            QMessageBox.critical(self, "Motor — Erro", msg)

        worker.task_started.connect(on_task_started)
        worker.elem_done.connect(on_elem_done)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        self._motor_worker = worker
        worker.start()

    # ── Helpers DB ───────────────────────────────────────────────────

    def _get_recorte_path(self, proj_id: str) -> str | None:
        rows = _db_query(
            "SELECT recorte_path FROM reverse_eng_fichas WHERE projeto_id=? LIMIT 1",
            (proj_id,)
        )
        return rows[0][0] if rows and rows[0][0] else None

    def _get_ficha_json(self, proj_id: str) -> str | None:
        rows = _db_query(
            "SELECT campos_json FROM reverse_eng_fichas WHERE projeto_id=? LIMIT 1",
            (proj_id,)
        )
        return rows[0][0] if rows else None

    def _load_obra_ficha(self, obra_name: str):
        rows = _db_query(
            "SELECT resumo_json FROM reverse_eng_obra_ficha WHERE obra_name=? ORDER BY created_at DESC LIMIT 1",
            (obra_name,)
        )
        self._center.load_ficha_obra(rows[0][0] if rows else None)
