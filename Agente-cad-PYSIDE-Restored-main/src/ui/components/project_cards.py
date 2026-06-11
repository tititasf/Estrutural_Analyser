import re as _re
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QProgressBar, QWidget, QGridLayout, QScrollArea)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QCursor, QFont
from src.ui.theme import Colors, Fonts, Radius


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_pav_class(name: str) -> tuple[str, str]:
    """
    Extrai classe canônica e cor do nome de pavimento DXF.
    Ex: 'TMC-EST-EX-1000-FUN-R01_R2018_ASCII_ODA' → ('FUN', '#e67e22')

    Retorna (label, hex_color).
    """
    n = name.upper()
    # Tenta padrão canônico: NNNN-CLASSE-RNN
    m = _re.search(r'\d{4}-([A-Z0-9°]+)-R\d', n)
    raw = m.group(1) if m else ""

    # Mapa classe → (label legível, cor)
    _MAP = {
        "FUN":  ("FUN",   "#e67e22"),   # laranja — fundação
        "TER":  ("TER",   "#f1c40f"),   # amarelo — térreo
        "TIP":  ("TIPO",  "#00d9ff"),   # ciano   — tipo
        "COB":  ("COB",   "#9b59b6"),   # roxo    — cobertura
        "ATC":  ("ÁTC",   "#e91e8c"),   # pink    — ático
        "LOC":  ("LOC",   "#7f8c8d"),   # cinza   — localização
        "BAR":  ("BAR",   "#7f8c8d"),   # cinza   — barrilete
        "DEC":  ("DECK",  "#7f8c8d"),   # cinza
    }
    if raw in _MAP:
        return _MAP[raw]

    # Pavimento numerado: 1PV, 2PV, 13P, 14P, SS, etc.
    if _re.match(r'^\d+PV?$', raw):
        # 1PV → "1PV", 13P → "13P"
        return (raw, "#00c864")   # verde

    if raw.startswith("SS") or "SUB" in raw:
        return ("SS", "#3498db")

    # fallback — primeiros 6 chars do raw ou do nome original
    label = raw[:6] if raw else name.split("-")[-1][:6]
    return (label, "#8a9ab5")  # cinza neutro

class BaseCard(QFrame):
    clicked = Signal(object) # Emits project data on click

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setObjectName("BaseCard")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet("""
            #BaseCard {
                background-color: {Colors.BG_DEEP};
                border-radius: 12px;
                border: 1px solid {Colors.BG_HOVER};
            }
            #BaseCard:hover {
                background-color: {Colors.BG_DEEP};
                border: 1px solid {Colors.ACCENT_PRIMARY};
            }
        """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.data)
        super().mousePressEvent(event)

class ProjectCard(BaseCard):
    """Card compacto para Pavimentos Limpos — linha única estilo Triagem."""
    action_ficha   = Signal(dict)
    action_sync    = Signal(dict)
    action_move    = Signal(dict)
    action_delete  = Signal(dict)
    action_open_dxf = Signal(dict)

    def __init__(self, project_data, parent=None):
        super().__init__(project_data, parent)
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(44)
        self.setMaximumHeight(56)
        self.setObjectName("BaseCard")
        self.setStyleSheet(
            "#BaseCard { background: #12161e; border: 1px solid #2a2f3d;"
            " border-radius: 5px; }"
            "#BaseCard:hover { border-color: #00d9ff; }"
        )
        self._setup_ui()

    def _setup_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(8)

        # ── Status badge ──────────────────────────────────────────────
        status = (self.data.get('sync_status') or 'pending').upper()
        if status == 'SYNCED':
            badge_bg, badge_fg = 'rgba(0,200,100,38)', '#00c864'
        elif status == 'EXTRACTING':
            badge_bg, badge_fg = 'rgba(0,217,255,38)', '#00d9ff'
        else:
            badge_bg, badge_fg = 'rgba(230,180,0,38)', '#e6b400'

        lbl_status = QLabel(status)
        lbl_status.setFixedWidth(72)
        lbl_status.setFixedHeight(20)
        lbl_status.setAlignment(Qt.AlignCenter)
        lbl_status.setStyleSheet(
            f"background: {badge_bg}; color: {badge_fg};"
            f" border: 1px solid {badge_fg}; border-radius: 3px;"
            f" font-size: 9px; font-weight: bold;"
        )
        row.addWidget(lbl_status)

        # ── Pavimento name + badge de classe ─────────────────────────
        pav_name = self.data.get('pavement_name') or self.data.get('name', '—')

        # Badge de classe (FUN / TER / 1P / TIPO / COB …)
        cls_label, cls_color = _extract_pav_class(pav_name)
        lbl_cls = QLabel(cls_label)
        lbl_cls.setFixedHeight(18)
        lbl_cls.setAlignment(Qt.AlignCenter)
        lbl_cls.setStyleSheet(
            f"color: {cls_color}; font-size: 8px; font-weight: bold;"
            f" background: transparent; border: 1px solid {cls_color};"
            f" border-radius: 3px; padding: 0 4px;"
        )
        row.addWidget(lbl_cls)

        # Nome completo (legível, tooltip com raw)
        lbl_pav = QLabel(pav_name)
        lbl_pav.setStyleSheet(
            "color: #00d9ff; font-size: 11px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        lbl_pav.setToolTip(self.data.get('name', pav_name))
        row.addWidget(lbl_pav)

        row.addStretch(1)

        # ── Extraction stats: PIL / VIG / LAJ ────────────────────────
        def _stat_chip(label, key_prefix, color):
            valid = self.data.get(f'{key_prefix}_valid') or 0
            total = self.data.get(f'{key_prefix}_total') or 0
            chip = QLabel(f"{label} {valid}/{total}")
            chip.setFixedHeight(20)
            chip.setStyleSheet(
                f"color: {color}; font-size: 9px; font-weight: bold;"
                f" background: rgba(0,0,0,64); border: 1px solid {color}40;"
                f" border-radius: 3px; padding: 0 5px;"
            )
            return chip

        row.addWidget(_stat_chip("PIL", "pil",  "#9B59B6"))
        row.addWidget(_stat_chip("VIG", "beam", "#2980B9"))
        row.addWidget(_stat_chip("LAJ", "slab", "#27AE60"))

        # ── Date ──────────────────────────────────────────────────────
        date_upd = str(self.data.get('updated_at') or '')[:16].replace('T', ' ')
        if date_upd:
            lbl_date = QLabel(date_upd)
            lbl_date.setStyleSheet(
                "color: #4a5060; font-size: 9px; background: transparent; border: none;"
            )
            row.addWidget(lbl_date)

        # ── Action buttons ────────────────────────────────────────────
        _btn_css = (
            "QPushButton { background: #1a1f2e; color: #8a9ab5;"
            " border: 1px solid #2a3040; border-radius: 3px;"
            " font-size: 10px; font-weight: bold; padding: 1px 8px; }"
            " QPushButton:hover { color: #ffffff; border-color: #00d9ff; }"
        )

        btn_ficha = QPushButton("📄 Ficha")
        btn_ficha.setFixedHeight(24)
        btn_ficha.setStyleSheet(_btn_css)
        btn_ficha.setCursor(Qt.PointingHandCursor)
        btn_ficha.clicked.connect(lambda: self.action_ficha.emit(self.data))
        row.addWidget(btn_ficha)

        btn_dxf = QPushButton("👁 Abrir DXF")
        btn_dxf.setFixedHeight(24)
        btn_dxf.setStyleSheet(
            "QPushButton { background: rgba(0,217,255,31); color: #00d9ff;"
            " border: 1px solid #00d9ff; border-radius: 3px;"
            " font-size: 10px; font-weight: bold; padding: 1px 8px; }"
            " QPushButton:hover { background: rgba(0,217,255,64); }"
        )
        btn_dxf.setCursor(Qt.PointingHandCursor)
        btn_dxf.clicked.connect(lambda: self.action_open_dxf.emit(self.data))
        row.addWidget(btn_dxf)

        btn_del = QPushButton("✕")
        btn_del.setFixedSize(24, 24)
        btn_del.setStyleSheet(
            "QPushButton { background: transparent; color: #4a3040;"
            " border: 1px solid #3a2030; border-radius: 3px; font-size: 12px; }"
            " QPushButton:hover { color: #e74c3c; border-color: #e74c3c; }"
        )
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.clicked.connect(lambda: self.action_delete.emit(self.data))
        row.addWidget(btn_del)


class CuradoriaCard(BaseCard):
    """Card para Projetos da Comunidade (AdminDashboard) - Design Premium v3 (3 Bars)"""
    train_requested = Signal(str, int) # project_id, total_items
    details_requested = Signal(dict)   # project_data
    sync_requested = Signal(dict)

    def __init__(self, project_data, parent=None):
        super().__init__(project_data, parent)
        self.setFixedSize(500, 420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # --- 1. Header (P-ID, Name, Date, Status) ---
        header = QHBoxLayout()
        header.setSpacing(10)
        
        pid = str(self.data.get('id', '???'))[:8]
        lbl_id = QLabel(pid.upper())
        lbl_id.setAlignment(Qt.AlignCenter)
        lbl_id.setFixedSize(70, 24)
        lbl_id.setStyleSheet("""
            background-color: {Colors.BG_HOVER}; color: rgba(136,144,176,1); 
            border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: bold;
        """)
        header.addWidget(lbl_id)
        
        p_name = self.data.get('project_name') or self.data.get('name') or 'Sem Nome'
        lbl_name = QLabel(str(p_name).upper())
        lbl_name.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {Colors.TEXT_BRIGHT};")
        header.addWidget(lbl_name)
        
        header.addStretch()
        
        # Owner / Profile info
        profile = self.data.get('profiles', {})
        author_email = profile.get('email', 'Desconhecido')
        author_name = profile.get('full_name') or author_email.split('@')[0]
        
        date = str(self.data.get('updated_at') or self.data.get('created_at') or '-')[:16].replace('T', ' ')
        lbl_date = QLabel(f"{author_name.upper()}  •  {date}")
        lbl_date.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 10px; font-weight: bold;")
        header.addWidget(lbl_date)
        
        layout.addLayout(header)
        
        # Status Badge Row
        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        
        work_name = self.data.get('metadata', {}).get('work_name') or self.data.get('work_name') or 'OBRA DESCONHECIDA'
        lbl_work = QLabel(work_name.upper())
        lbl_work.setStyleSheet("color: rgba(136,144,176,1); font-size: 10px; font-weight: 600; letter-spacing: 0.5px;")
        status_row.addWidget(lbl_work)
        
        status_row.addStretch()
        
        status = self.data.get('status') or 'PENDENTE'
        if self.data.get('is_trained'): status = 'SINCRONIZADO' 
        lbl_status = QLabel(status)
        lbl_status.setStyleSheet(f"color: {Colors.ACCENT_WARNING_ALT}; font-size: 10px; font-weight: bold;")
        status_row.addWidget(lbl_status)
        layout.addLayout(status_row)
        
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color: {Colors.BG_HOVER}; max-height: 1px;")
        layout.addWidget(line)
        layout.addSpacing(5)

        # --- 2. Stats Grid (3 Bars) ---
        stats = self.data.get('metadata', {}).get('stats', {})
        total_items = stats.get('total_items', 0)
        
        # New Standard
        finished_items = stats.get('finished_items')
        started_items = stats.get('started_items', 0)
        total_links = stats.get('total_links_expected')
        valid_links = stats.get('total_links_validated')

        # Backward Compatibility (Old Standard)
        if finished_items is None:
             finished_items = stats.get('blue_items', 0)
        
        if total_links is None:
             total_links = stats.get('total_links', 0)
             
        if valid_links is None:
             valid_links = stats.get('green_links', 0)
             
        # Fallback for display
        finished_items = finished_items or 0
        total_links = total_links or 0
        valid_links = valid_links or 0
        
        grid = QGridLayout()
        grid.setSpacing(12)
        
        # Row 1: Items Started vs Finished
        self._add_stat(grid, 0, 0, "ITENS INICIADOS", started_items, total_items, Colors.ACCENT_WARNING_ALT) # Start
        self._add_stat(grid, 0, 1, "ITENS FINALIZADOS", finished_items, total_items, Colors.ACCENT_PRIMARY) # Finish
        
        # Row 2: Links
        self._add_stat(grid, 1, 0, "VÍNCULOS", valid_links, total_links, Colors.ACCENT_LINK_PURPLE) # Link
        
        # Row 3: Training Indicator (Simulation)
        # Training considers Finished Items only
        self._add_stat(grid, 1, 1, "TREINO (DISPONÍVEL)", finished_items, total_items, Colors.ACCENT_SUCCESS)

        layout.addLayout(grid)
        layout.addSpacing(10)
        
        # --- 3. Docs Section ---
        doc_header = QHBoxLayout()
        doc_title = QLabel("DOCUMENTOS POR CLASSE")
        doc_title.setStyleSheet("color: {Colors.TEXT_SECONDARY}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        doc_header.addWidget(doc_title)
        doc_header.addStretch()
        layout.addLayout(doc_header)
        
        docs_layout = QVBoxLayout()
        docs_layout.setSpacing(2)
        
        doc_stats = self.data.get('metadata', {}).get('doc_stats', {})
        if not doc_stats:
            doc_stats = {"ESTRUTURAL": 0, "PILARES": 0, "LAJES": 0, "VIGAS": 0}

        for label, count in doc_stats.items():
            if count > 0: self._add_doc_row(docs_layout, label, count)
        
        layout.addLayout(docs_layout)
        layout.addStretch()
        
        # --- 4. Footer Actions ---
        footer = QHBoxLayout()
        footer.setSpacing(8)
        
        btn_train = self._create_btn("🛠️ TREINAR", Colors.ACCENT_PRIMARY)
        btn_train.clicked.connect(lambda: self.train_requested.emit(self.data.get('id'), total_items))
        footer.addWidget(btn_train, 2)
        
        btn_details = self._create_btn("📄 FICHA", Colors.ACCENT_SLATE)
        btn_details.clicked.connect(lambda: self.details_requested.emit(self.data))
        footer.addWidget(btn_details, 1)
        
        sync_label = "☁️ SINCRONIZAR" if self.data.get('local_exists') else "☁️ BAIXAR"
        btn_sync = self._create_btn(sync_label, Colors.ACCENT_SLATE)
        btn_sync.clicked.connect(lambda: self.sync_requested.emit(self.data))
        footer.addWidget(btn_sync, 1)
        
        layout.addLayout(footer)

    def _add_stat(self, grid, r, c, label, val, total, color):
        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(0,0,0,0)
        l.setSpacing(4)
        
        top = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet("color: {Colors.TEXT_SECONDARY}; font-size: 9px; font-weight: bold;")
        top.addWidget(lbl)
        top.addStretch()
        
        pct = (val / total * 100) if total > 0 else 0
        v_lbl = QLabel(f"{val} ({int(pct)}%)")
        v_lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
        top.addWidget(v_lbl)
        l.addLayout(top)
        
        pb = QProgressBar()
        pb.setFixedHeight(4)
        pb.setTextVisible(False)
        pb.setRange(0, 100)
        pb.setValue(int(pct))
        pb.setStyleSheet(f"QProgressBar {{ background: {Colors.BG_HOVER}; border: none; }} QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}")
        l.addWidget(pb)
        
        grid.addWidget(container, r, c)

    def _add_doc_row(self, layout, name, count):
        row = QHBoxLayout()
        name_l = QLabel(name)
        name_l.setStyleSheet("color: rgba(136,144,176,1); font-size: 10px;")
        row.addWidget(name_l)
        row.addStretch()
        
        cnt_badge = QLabel(str(count))
        cnt_badge.setStyleSheet(f"background: {Colors.BG_SURFACE}; color: {Colors.TEXT_PRIMARY}; padding: 2px 6px; border-radius: 8px; font-size: 9px; font-weight: bold;")
        row.addWidget(cnt_badge)
        layout.addLayout(row)

    def _create_btn(self, text, color):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        
        is_primary = "TREINAR" in text
        if is_primary:
             btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(0,212,255,26);
                    border: 1px solid {color};
                    color: {color};
                    font-weight: bold; font-size: 10px; border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: {color}; color: {Colors.BG_DEEP}; }}
            """)
        else:
             btn.setStyleSheet("""
                QPushButton {
                    background-color: #252630; border: 1px solid {Colors.BORDER_INPUT};
                    color: {Colors.TEXT_SECONDARY}; font-weight: bold; font-size: 10px; border-radius: 4px;
                }
                QPushButton:hover { border: 1px solid {Colors.TEXT_DIM}; color: {Colors.TEXT_BRIGHT}; }
            """)
        return btn
