from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                                QPushButton, QProgressBar, QWidget, QGridLayout, QScrollArea)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QCursor, QFont

class BaseCard(QFrame):
    clicked = Signal(object) # Emits project data on click

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setObjectName("BaseCard")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet("""
            #BaseCard {
                background-color: #1a1b25;
                border-radius: 12px;
                border: 1px solid #2d2d3a;
            }
            #BaseCard:hover {
                background-color: #20212b;
                border: 1px solid #00d4ff;
            }
        """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.data)
        super().mousePressEvent(event)

class ProjectCard(BaseCard):
    """Card para Pavimentos Locais (ProjectManager) - V2 Premium Design"""
    action_ficha = Signal(dict)
    action_sync = Signal(dict)
    action_move = Signal(dict)
    action_delete = Signal(dict)
    action_open_dxf = Signal(dict)
    
    def __init__(self, project_data, parent=None):
        super().__init__(project_data, parent)
        # Removido tamanho fixo para permitir expansão em X e controle em Y
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(150)
        self.setMaximumHeight(180)
        self._setup_ui()

    def _setup_ui(self):
        # Layout principal Horizontal
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(20)

        # --- BLOCO 1: INFO (ESQUERDA) ---
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        name_lbl = QLabel(self.data.get('name', 'Sem Nome').upper())
        name_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #00d4ff; letter-spacing: 0.5px;")
        info_layout.addWidget(name_lbl)
        
        author = self.data.get('author_name', 'Local')
        date_upd = str(self.data.get('updated_at') or '')[:16].replace('T', ' ')
        meta_lbl = QLabel(f"Autor: {author} | Editado: {date_upd}")
        meta_lbl.setStyleSheet("color: #6c7293; font-size: 10px; font-weight: 500;")
        info_layout.addWidget(meta_lbl)
        
        # Observação menor
        obs_box = QLabel("Obs: Aguardando revisão do detalhamento das vigas...")
        obs_box.setWordWrap(True)
        obs_box.setStyleSheet("color: #888; font-size: 10px; font-style: italic;")
        info_layout.addWidget(obs_box)
        info_layout.addStretch()
        
        main_layout.addLayout(info_layout, 2) # Peso 2

        # --- BLOCO 2: STATS (CENTRO) ---
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: rgba(255,255,255,0.03); border-radius: 8px; border: 1px solid #2d2d3a;")
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setContentsMargins(10, 10, 10, 10)
        stats_layout.setSpacing(8)
        
        # Headers reduzidos
        l_stat = QLabel("STATUS DE EXTRAÇÃO")
        l_stat.setStyleSheet("color: #6c7293; font-size: 8px; font-weight: bold;")
        stats_layout.addWidget(l_stat, 0, 0, 1, 4, Qt.AlignCenter)

        self._add_stat_row(stats_layout, 1, "PILARES", 'pil', multiplier=140) 
        self._add_stat_row(stats_layout, 2, "VIGAS", 'beam', multiplier=45)
        self._add_stat_row(stats_layout, 3, "LAJES", 'slab', multiplier=7)
        
        main_layout.addWidget(stats_frame, 3) # Peso 3

        # --- BLOCO 3: AÇÕES (DIREITA) ---
        action_layout = QVBoxLayout()
        action_layout.setSpacing(8)
        
        # Status Badge no topo das ações
        status = self.data.get('sync_status') or "pending"
        badge_color = "#00d4ff" if status == 'synced' else "#ffab00"
        lbl_status = QLabel(status.upper())
        lbl_status.setAlignment(Qt.AlignCenter)
        lbl_status.setFixedHeight(20)
        lbl_status.setStyleSheet(f"background: rgba(0,0,0,0.2); color: {badge_color}; border: 1px solid {badge_color}; border-radius: 4px; font-size: 9px; font-weight: bold; width: 100%;")
        action_layout.addWidget(lbl_status)

        # Botões principais lado a lado
        btns_row = QHBoxLayout()
        btn_ficha = QPushButton("📄 FICHA")
        btn_ficha.setFixedHeight(30)
        btn_ficha.setCursor(Qt.PointingHandCursor)
        btn_ficha.setStyleSheet("background: #252630; border: 1px solid #3d3d4d; color: #ccc; font-size: 9px; font-weight: bold;")
        btn_ficha.clicked.connect(lambda: self.action_ficha.emit(self.data))
        btns_row.addWidget(btn_ficha)

        btn_cloud = QPushButton("☁ SYNC")
        btn_cloud.setFixedHeight(30)
        btn_cloud.setCursor(Qt.PointingHandCursor)
        btn_cloud.setStyleSheet("background: #252630; border: 1px solid #00d4ff; color: #00d4ff; font-size: 9px; font-weight: bold;")
        btn_cloud.clicked.connect(lambda: self.action_sync.emit(self.data))
        btns_row.addWidget(btn_cloud)
        action_layout.addLayout(btns_row)

        # Ações extras (Mover/Excluir)
        extras_row = QHBoxLayout()
        btn_move = QPushButton("Mover")
        btn_move.setStyleSheet("color: #aaa; background: transparent; border: none; font-size: 9px;")
        btn_move.clicked.connect(lambda: self.action_move.emit(self.data))
        extras_row.addWidget(btn_move)
        
        btn_delete = QPushButton("Excluir")
        btn_delete.setStyleSheet("color: #933; background: transparent; border: none; font-size: 9px;")
        btn_delete.clicked.connect(lambda: self.action_delete.emit(self.data))
        extras_row.addWidget(btn_delete)
        
        btn_open_cad = QPushButton("📂 ABRIR DXF")
        btn_open_cad.setStyleSheet("""
            QPushButton {
                background: #00d4ff; 
                color: #000; 
                border-radius: 4px; 
                font-weight: bold; 
                font-size: 10px;
                padding: 4px;
            }
            QPushButton:hover { background: #00b8e6; }
        """)
        btn_open_cad.clicked.connect(lambda: self.action_open_dxf.emit(self.data))
        extras_row.addWidget(btn_open_cad)
        
        action_layout.addLayout(extras_row)
        
        main_layout.addLayout(action_layout, 1) # Peso 1

    def _add_stat_row(self, grid, row, label, key_prefix, multiplier=10):
        # Label
        l_name = QLabel(label)
        l_name.setStyleSheet("color: #ccc; font-size: 10px; font-weight: 500;")
        grid.addWidget(l_name, row, 0)
        
        # Stats from DB key_valid, key_total, key_started
        valid = self.data.get(f'{key_prefix}_valid') or 0
        started = self.data.get(f'{key_prefix}_started') or 0
        total = self.data.get(f'{key_prefix}_total') or 0
        
        # Bar 1: Started (Yellow)
        self._add_progress_bar_cell(grid, row, 1, started, total, "#ffab00")

        # Bar 2: Finished (Green)
        self._add_progress_bar_cell(grid, row, 2, valid, total, "#00d4ff")
        
        # Bar 3: Links (Purple) - Estimate for Local
        # Total Links = Total Items * Multiplier
        # Valid Links (Estimate) = Valid Items * Multiplier + Started * (0.2 * Multiplier)
        # FIX: 'started' from DB includes 'valid' items. We need strictly started.
        strictly_started = max(0, started - valid)
        
        link_total = total * multiplier
        link_valid = int(valid * multiplier + (strictly_started * multiplier * 0.2))
        
        self._add_progress_bar_cell(grid, row, 3, link_valid, link_total, "#d500f9")

    def _add_progress_bar_cell(self, grid, row, col, val, total, color):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        lbl_val = QLabel(f"{val}/{total}")
        lbl_val.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: bold; min-width: 40px;")
        layout.addWidget(lbl_val)
        
        pb = QProgressBar()
        pb.setFixedHeight(4)
        pb.setTextVisible(False)
        pct = (val / total * 100) if total > 0 else 0
        pb.setValue(int(pct))
        pb.setStyleSheet(f"""
            QProgressBar {{ background: #2d2d3a; border-radius: 2px; border: none; }}
            QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}
        """)
        layout.addWidget(pb)
        
        grid.addWidget(container, row, col)

    def _add_doc_item(self, layout, name, count):
        pass # Not used in this version


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
            background-color: #2d2d3a; color: #8890b0; 
            border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: bold;
        """)
        header.addWidget(lbl_id)
        
        p_name = self.data.get('project_name') or self.data.get('name') or 'Sem Nome'
        lbl_name = QLabel(str(p_name).upper())
        lbl_name.setStyleSheet("font-size: 14px; font-weight: bold; color: white;")
        header.addWidget(lbl_name)
        
        header.addStretch()
        
        # Owner / Profile info
        profile = self.data.get('profiles', {})
        author_email = profile.get('email', 'Desconhecido')
        author_name = profile.get('full_name') or author_email.split('@')[0]
        
        date = str(self.data.get('updated_at') or self.data.get('created_at') or '-')[:16].replace('T', ' ')
        lbl_date = QLabel(f"{author_name.upper()}  •  {date}")
        lbl_date.setStyleSheet("color: #666; font-size: 10px; font-weight: bold;")
        header.addWidget(lbl_date)
        
        layout.addLayout(header)
        
        # Status Badge Row
        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        
        work_name = self.data.get('metadata', {}).get('work_name') or self.data.get('work_name') or 'OBRA DESCONHECIDA'
        lbl_work = QLabel(work_name.upper())
        lbl_work.setStyleSheet("color: #8890b0; font-size: 10px; font-weight: 600; letter-spacing: 0.5px;")
        status_row.addWidget(lbl_work)
        
        status_row.addStretch()
        
        status = self.data.get('status') or 'PENDENTE'
        if self.data.get('is_trained'): status = 'SINCRONIZADO' 
        lbl_status = QLabel(status)
        lbl_status.setStyleSheet("color: #ffab00; font-size: 10px; font-weight: bold;")
        status_row.addWidget(lbl_status)
        layout.addLayout(status_row)
        
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #2d2d3a; max-height: 1px;")
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
        self._add_stat(grid, 0, 0, "ITENS INICIADOS", started_items, total_items, "#ffab00") # Start
        self._add_stat(grid, 0, 1, "ITENS FINALIZADOS", finished_items, total_items, "#00d4ff") # Finish
        
        # Row 2: Links
        self._add_stat(grid, 1, 0, "VÍNCULOS", valid_links, total_links, "#d500f9") # Link
        
        # Row 3: Training Indicator (Simulation)
        # Training considers Finished Items only
        self._add_stat(grid, 1, 1, "TREINO (DISPONÍVEL)", finished_items, total_items, "#28a745")

        layout.addLayout(grid)
        layout.addSpacing(10)
        
        # --- 3. Docs Section ---
        doc_header = QHBoxLayout()
        doc_title = QLabel("DOCUMENTOS POR CLASSE")
        doc_title.setStyleSheet("color: #6c7293; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
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
        
        btn_train = self._create_btn("🛠️ TREINAR", "#00d4ff")
        btn_train.clicked.connect(lambda: self.train_requested.emit(self.data.get('id'), total_items))
        footer.addWidget(btn_train, 2)
        
        btn_details = self._create_btn("📄 FICHA", "#6c7293")
        btn_details.clicked.connect(lambda: self.details_requested.emit(self.data))
        footer.addWidget(btn_details, 1)
        
        sync_label = "☁️ SINCRONIZAR" if self.data.get('local_exists') else "☁️ BAIXAR"
        btn_sync = self._create_btn(sync_label, "#6c7293")
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
        lbl.setStyleSheet("color: #6c7293; font-size: 9px; font-weight: bold;")
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
        pb.setStyleSheet(f"QProgressBar {{ background: #2d2d3a; border: none; }} QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}")
        l.addWidget(pb)
        
        grid.addWidget(container, r, c)

    def _add_doc_row(self, layout, name, count):
        row = QHBoxLayout()
        name_l = QLabel(name)
        name_l.setStyleSheet("color: #8890b0; font-size: 10px;")
        row.addWidget(name_l)
        row.addStretch()
        
        cnt_badge = QLabel(str(count))
        cnt_badge.setStyleSheet(f"background: #252630; color: #ccc; padding: 2px 6px; border-radius: 8px; font-size: 9px; font-weight: bold;")
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
                    background-color: rgba(0, 212, 255, 0.1);
                    border: 1px solid {color};
                    color: {color};
                    font-weight: bold; font-size: 10px; border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: {color}; color: #000; }}
            """)
        else:
             btn.setStyleSheet("""
                QPushButton {
                    background-color: #252630; border: 1px solid #3d3d4d;
                    color: #888; font-weight: bold; font-size: 10px; border-radius: 4px;
                }
                QPushButton:hover { border: 1px solid #666; color: white; }
            """)
        return btn
