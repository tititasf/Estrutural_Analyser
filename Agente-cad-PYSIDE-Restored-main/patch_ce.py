import re

with open('src/ui/modules/comparison_engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. NavSidebar: Add btn_certify, hide analise/fase4
nav_sidebar_replacement = """
        self.btn_analise = _mbtn("▶ Análise Geral", Colors.ACCENT_SUCCESS, "rgba(67, 160, 71, 1)")
        self.btn_analise.setToolTip("Processa o DXF estrutural N1 e preenche a lista de itens")
        self.btn_analise.clicked.connect(lambda: getattr(self, "analise_requested", None).emit() if hasattr(self, "analise_requested") else None)
        self.btn_analise.setVisible(False)
        lay.addWidget(self.btn_analise)

        self.btn_certify = QPushButton("✅ Certificar Obra")
        self.btn_certify.setObjectName("certify")
        self.btn_certify.setEnabled(False)
        self.btn_certify.setStyleSheet(f'''
            QPushButton#certify {{
                background: {Colors.ACCENT_SUCCESS};
                color: {Colors.BG_DEEP};
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
            }}
            QPushButton#certify:disabled {{
                background: {Colors.BG_CARD};
                color: {Colors.TEXT_DIM};
            }}
        ''')
        lay.addWidget(self.btn_certify)

        self.btn_rag_context = _mbtn("Consultar RAG", Colors.BG_CARD, Colors.BG_PANEL)
        self.btn_rag_context.setToolTip("Consulta read-only do RAG global. Usa apenas T1/T2 e regras semanticas; nao escreve nem autocompleta.")
        self.btn_rag_context.clicked.connect(self._on_rag_context_clicked)
        lay.addWidget(self.btn_rag_context)

        self.btn_fase4 = _mbtn("⚙ Fase 4 — Sync", Colors.ACCENT_WARNING, "rgba(245, 124, 0, 1)")
        self.btn_fase4.setToolTip("Executa motor_fase4.py para o pavimento selecionado")
        self.btn_fase4.clicked.connect(lambda: getattr(self, "fase4_requested", None).emit() if hasattr(self, "fase4_requested") else None)
        self.btn_fase4.setVisible(False)
        lay.addWidget(self.btn_fase4)
"""
# Replace the original block in NavSidebar
pattern_nav = r'self\.btn_analise = _mbtn.*?lay\.addWidget\(self\.btn_fase4\)'
text = re.sub(pattern_nav, nav_sidebar_replacement.strip(), text, flags=re.DOTALL)

# 2. Fase8Panel._build_ui
fase8_build_ui_pattern = r'# ── Status de Processamento N1/N2/N3 ────.*?# ── Scores ──────────────────────────────'
fase8_build_ui_replacement = """# ── Status de Processamento ────
        grp_proc = QGroupBox("Status de Processamento")
        proc_lay = QVBoxLayout(grp_proc)
        proc_lay.setContentsMargins(6, 4, 6, 4)
        proc_lay.setSpacing(4)

        status_grid = QHBoxLayout()
        status_grid.setSpacing(3)
        self._status_qty_labels = {}
        self._status_pct_labels = {}
        for t in TIPOS:
            col = QVBoxLayout()
            col.setSpacing(1)
            lbl_t = QLabel(t, alignment=Qt.AlignCenter)
            lbl_t.setStyleSheet(f"font-size: 9px; color: {Colors.TEXT_SECONDARY};")
            col.addWidget(lbl_t)
            lbl_qty = QLabel("0/0")
            lbl_qty.setAlignment(Qt.AlignCenter)
            lbl_qty.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 9px;")
            self._status_qty_labels[t] = lbl_qty
            col.addWidget(lbl_qty)
            sl = ScoreLabel("—")
            sl.setAlignment(Qt.AlignCenter)
            sl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 13px; font-weight: bold;")
            self._status_pct_labels[t] = sl
            col.addWidget(sl)
            status_grid.addLayout(col)
        proc_lay.addLayout(status_grid)
        outer.addWidget(grp_proc)

        # ── Scores ──────────────────────────────"""
text = re.sub(fase8_build_ui_pattern, fase8_build_ui_replacement, text, flags=re.DOTALL)

# Remove btn_certify from Fase8Panel
fase8_certify_pattern = r'# ── Certificar ──────────────────────────.*?self\.lbl_cert_status = QLabel\(""\)\n        outer\.addWidget\(self\.lbl_cert_status\)'
text = re.sub(fase8_certify_pattern, '', text, flags=re.DOTALL)

# 3. _refresh_processing_status in Fase8Panel
fase8_refresh_pattern = r'def _refresh_processing_status\(self, obra_name: str\):.*?_set\("N3",\n.*?\)'
fase8_refresh_replacement = """def _refresh_processing_status(self, obra_name: str, pav_key: str = None, stats: dict = None):
        \"\"\"Atualiza o painel de status com as validações de N3 por classe para a obra/pavimento.\"\"\"
        if not stats:
            for t in TIPOS:
                if t in self._status_qty_labels:
                    self._status_qty_labels[t].setText("0/0")
                    self._status_pct_labels[t].set_score(None)
            return

        for t in TIPOS:
            val = stats.get(t, {"validated": 0, "total": 0})
            v = val["validated"]
            tot = val["total"]
            if t in self._status_qty_labels:
                self._status_qty_labels[t].setText(f"{v}/{tot}")
                pct = (v / tot * 100) if tot > 0 else None
                self._status_pct_labels[t].set_score(pct)"""
text = re.sub(fase8_refresh_pattern, fase8_refresh_replacement, text, flags=re.DOTALL)

# 4. In ComparisonEngineModule._build_ui, connect nav_sidebar.btn_certify
comp_ui_replacement = """self.nav_sidebar.fase4_requested.connect(self._on_fase4_sync)
        self.nav_sidebar.btn_certify.clicked.connect(self.fase8_panel._on_certify)"""
text = text.replace('self.nav_sidebar.fase4_requested.connect(self._on_fase4_sync)', comp_ui_replacement)

# 5. _load_scores_for_obra update to use nav_sidebar.btn_certify
comp_load_scores_replacement = """self.nav_sidebar.btn_certify.setEnabled(avg is not None)"""
text = text.replace('self.btn_certify.setEnabled(avg is not None)', comp_load_scores_replacement)

# 6. _on_obra_pav_changed update
comp_obra_pav_pattern = r'self\.nav_sidebar\.set_pav\(pav\)\s*# filtra lista ER pelo pavimento selecionado\s*# Cancela sequência anterior'
comp_obra_pav_replacement = """self.nav_sidebar.set_pav(pav)   # filtra lista ER pelo pavimento selecionado
            
            stats = {}
            for t in ["PL", "LV", "FV", "LJ"]:
                structural = self.nav_sidebar._structural_item_rows(t)
                tot = len(structural)
                v = sum(1 for item_data in structural.values() if self.nav_sidebar._row_human_validated(t, item_data))
                stats[t] = {"validated": v, "total": tot}
            self.fase8_panel._refresh_processing_status(obra, pav, stats)

            # Cancela sequência anterior"""
text = re.sub(comp_obra_pav_pattern, comp_obra_pav_replacement, text, flags=re.DOTALL)

with open('src/ui/modules/comparison_engine.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patched successfully.")
