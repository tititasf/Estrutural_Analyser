import uuid
import math
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                                QTabWidget, QTableWidget, QTableWidgetItem, 
                                QPushButton, QHeaderView, QFrame, QMessageBox,
                                QLineEdit, QFormLayout, QScrollArea, QComboBox, QGroupBox, QSizePolicy,
                                QRadioButton, QCheckBox, QButtonGroup, QGridLayout, QInputDialog)
from PySide6.QtCore import Qt, Signal
from .link_manager import LinkManager
from src.ui.widgets.interpretation_dialog import InterpretationDialog
from src.ui.theme import Colors, Fonts, Radius, Semantic, Text, Surface, Border, Accent

try:
    from src.ui.widgets.comparison_tab import ComparisonTab
    _COMPARISON_AVAILABLE = True
except ImportError:
    _COMPARISON_AVAILABLE = False

try:
    from src.core.services.correction_service import detect_divergences, apply_correction, append_correction_log, build_log_entry
    from src.ui.dialogs.correction_dialog import CorrectionDialog
    _CORRECTION_AVAILABLE = True
except ImportError:
    _CORRECTION_AVAILABLE = False

try:
    from src.ui.dialogs.generate_dxf_dialog import GenerateDXFDialog
    _DXF_GEN_AVAILABLE = True
except ImportError:
    _DXF_GEN_AVAILABLE = False

class DetailCard(QWidget):
    """
    Ficha Técnica Master - Interface Especialista e Rotulagem de IA.
    Configurada para Pilares (Lados A-H), Vigas (Segmentos A/B) e Lajes.
    """
    data_validated = Signal(dict)
    data_invalidated = Signal(dict)
    element_focused = Signal(object) # (str para nome ou dict para link direto)
    element_removed = Signal(dict)   # (dict com slot e link removido)
    pick_requested = Signal(str, object) # (field_id, type/request)
    focus_requested = Signal(str)    # (field_id) disparado pelo botão de lupa
    research_requested = Signal(str, str) # field_id, slot_id
    training_requested = Signal(str, dict) # field_id, train_data
    config_updated = Signal(str, list)      # field_key, slots_config
    data_changed = Signal(dict)           # (dict) disparado quando qualquer dado muda (nome, dim, etc)
    validation_changed = Signal(dict)     # (dict) mudanca leve: somente estado de validacao/treino
    log_requested = Signal(str)           # (str) pedido de log no console principal

    # Deve permanecer em paridade com MainWindow._calculate_completion().
    _LAJE_REQUIRED_VALIDATION_FIELDS = frozenset({
        'name', 'laje_dim', 'laje_visao_corte', 'laje_vizinhas_niveis',
        'laje_pilares_apoio', 'laje_nivel', 'laje_outline_segs', 'laje_islands',
    })
    
    # Estilos CSS Reutilizáveis — usando tokens do design system
    # [2026-07-13] Campo validado por humano no app desktop é AZUL (era
    # verde) — harmoniza com o modelo de 3 origens de campo (azul=app,
    # rosa=Portal, laranja=agente QA), ver `src/core/validation_model.py`.
    STYLE_DEFAULT        = f"background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_INPUT}; padding: 4px 6px; border-radius: {Radius.MD}; color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_XL};"
    STYLE_VALID          = f"background: {Colors.BG_CARD}; border: 1px solid {Colors.ACCENT_PRIMARY}; padding: 4px 6px; border-radius: {Radius.MD}; color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_XL}; font-weight: bold;"
    STYLE_VALID_ROSA     = f"background: {Colors.BG_CARD}; border: 1px solid {Colors.ACCENT_ROSA}; padding: 4px 6px; border-radius: {Radius.MD}; color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_XL}; font-weight: bold;"
    STYLE_VALID_LARANJA  = f"background: {Colors.BG_CARD}; border: 1px solid {Colors.ACCENT_WARNING}; padding: 4px 6px; border-radius: {Radius.MD}; color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_XL}; font-weight: bold;"
    STYLE_NA             = f"background: rgba(51, 51, 17, 230); border: 1px solid {Colors.ACCENT_INFO}; padding: 4px 6px; border-radius: {Radius.MD}; color: {Colors.ACCENT_INFO}; font-size: {Fonts.SIZE_XL}; font-style: italic;"

    def __init__(self, item_data: dict, parent=None,
                 obra_path=None, db=None, project_id: str = ''):
        super().__init__(parent)
        self.item_data  = item_data
        self.obra_path  = obra_path   # CAD-10.4: path da obra para aba Comparar
        self.db         = db          # CAD-10.4: banco para aceitar/corrigir
        self.project_id = project_id  # CAD-10.4: project_id para persistência
        
        # FIX: Migração de chave legada (segments -> pilar_segs)
        if self.item_data.get('type') == 'Pilar':
            l = self.item_data.get('links', {})
            if l and 'segments' in l and 'pilar_segs' not in l:
                l['pilar_segs'] = l.pop('segments')
            
            # FIX 2: Migração interna (main -> segments) para bater com LinkManager config
            if l and 'pilar_segs' in l:
                ps = l['pilar_segs']
                if 'main' in ps and 'segments' not in ps:
                    ps['segments'] = ps.pop('main')

        self.fields = {}
        self.indicators = {}
        self.action_btns = {} # field_id -> { 'link': btn, 'focus': btn, 'na': btn, 'express': btn }
        self.embedded_managers = {}
        self._tipo_comp_buttons = {}  # Armazena referências aos round buttons de tipo comprimento
        self._link_conf_badges  = {}  # field_id -> QLabel do badge XX% de confiança vínculos
        self.init_ui()
        
        # Conectar sinal interno para auto-atualização do cabeçalho
        self.data_changed.connect(self._update_header_counts)
        self.validation_changed.connect(self._update_header_counts)

    def _scan_local_segments(self):
        """Conta segmentos locais (A, B, C) para exibicao no cabecalho"""
        sa, sb, sc = {1}, {1}, {1}
        for k in self.item_data.keys():
            if '_seg_' in k:
                try:
                    parts = k.split('_')
                    if 'seg' in parts:
                        idx = int(parts[parts.index('seg') + 1])
                        if k.startswith('viga_a_'): sa.add(idx)
                        elif k.startswith('viga_b_'): sb.add(idx)
                        elif k.startswith('viga_fundo_'): sc.add(idx)
                except: pass
        return len(sa), len(sb), len(sc)

    def _update_header_counts(self, _=None):
        """Atualiza widgets de contagem no cabeçalho se existirem"""
        if 'viga_count_a' in self.fields or 'viga_count_b' in self.fields or 'viga_count_c' in self.fields:
            na, nb, nc = self._scan_local_segments()
            
            if 'viga_count_a' in self.fields:
                self.fields['viga_count_a'].setText(str(na))
                # Forçar atualização visual estilo readonly
                self.fields['viga_count_a'].setStyleSheet(f"background: {Colors.BG_CARD}; color: {Colors.ACCENT_PRIMARY}; font-weight: bold; border: none;")

            if 'viga_count_b' in self.fields:
                self.fields['viga_count_b'].setText(str(nb))
                self.fields['viga_count_b'].setStyleSheet(f"background: {Colors.BG_CARD}; color: {Colors.ACCENT_PRIMARY}; font-weight: bold; border: none;")

            if 'viga_count_c' in self.fields:
                self.fields['viga_count_c'].setText(str(nc))
                self.fields['viga_count_c'].setStyleSheet(f"background: {Colors.BG_CARD}; color: {Colors.ACCENT_PRIMARY}; font-weight: bold; border: none;")


    def _add_info_row(self, layout, label_text, field_id, is_combo=False, combo_items=None):
        if is_combo:
            w = QComboBox()
            w.setStyleSheet(f"background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_INPUT}; border-radius: 3px; color: {Colors.TEXT_BRIGHT};")
            if combo_items:
                w.addItems(combo_items)
            w.currentTextChanged.connect(lambda txt: self._on_field_changed(field_id, txt))
        else:
            w = QLineEdit()
            w.setStyleSheet(f"background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_INPUT}; border-radius: 3px; color: {Colors.TEXT_BRIGHT};")
            w.textChanged.connect(lambda txt: self._on_field_changed(field_id, txt))
        
        w.setFixedHeight(24)
        
        # Populate initial value
        initial_val = str(self.item_data.get('fields', {}).get(field_id, self.item_data.get(field_id, '')))
        if initial_val and initial_val != 'None':
            if is_combo:
                idx = w.findText(initial_val)
                if idx >= 0:
                    w.setCurrentIndex(idx)
            else:
                w.setText(initial_val)
                
        self.fields[field_id] = w
        layout.addRow(label_text, w)

    def _add_linked_row(self, layout, label_text, field_id, pick_type='text', is_combo=False, combo_items=None, 
                        show_links=True, show_focus=True, hide_input=False, show_validate=True, show_na=True):
        
        w = None
        btn_link = None
        btn_focus = None
        if not hide_input:
            if is_combo:
                w = QComboBox()
                if combo_items: w.addItems(combo_items)
                w.setFixedHeight(22)
                w.setMinimumWidth(20)
                w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                if "Pos." in label_text: # Lógica especial para posição da laje
                    w.currentTextChanged.connect(lambda t: self._on_position_changed(field_id, t))
            else:
                w = QLineEdit()
                w.setFixedHeight(22)
                w.setMinimumWidth(20)
                w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                
            w.setStyleSheet(self.STYLE_DEFAULT if field_id not in self.item_data.get('validated_fields', []) else self.STYLE_VALID)
            self.fields[field_id] = w
            
            # Conectar mudança imediata para refletir nas listas do MainWindow
            if is_combo:
                w.currentTextChanged.connect(lambda txt: self._on_field_changed(field_id, txt))
            else:
                w.textChanged.connect(lambda txt: self._on_field_changed(field_id, txt))
            
            # Tentar carregar valor inicial
            initial_val = self._get_initial_value(field_id)
            if initial_val is not None:
                if is_combo: w.setCurrentText(str(initial_val))
                else: w.setText(str(initial_val))
        else:
            # Placeholder invisível ou label para campos sem input de texto (como apenas segmentos)
            w = QLabel("Vínculo Pendente")
            w.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-style: italic; font-size: 10px;")
            self.fields[field_id] = w
            
            # Tentar carregar valor inicial (se houver extração de texto automática)
            initial_val = self._get_initial_value(field_id)
            
            # Se já tiver vínculos, mostrar contagem (Fallback)
            links = self.item_data.get('links', {}).get(field_id, {})
            count = 0
            if isinstance(links, dict):
                for sl_links in links.values(): count += len(sl_links)
            elif isinstance(links, list):
                count = len(links)
                
            if initial_val:
                if 'dim' in field_id.lower():
                    w.setText(f"Dim: {initial_val}")
                else:
                    w.setText(f"{initial_val}")
                w.setStyleSheet(f"color: {Colors.ACCENT_SUCCESS_ALT}; font-weight: bold; font-size: 10px;")
            elif count > 0 and isinstance(w, QLabel):
                w.setText(f"{count} Vínculo(s) Ok")
                w.setStyleSheet(f"color: {Colors.ACCENT_SUCCESS_ALT}; font-weight: bold; font-size: 10px;")

        # Sub-container for the drawer (inline LinkManager)
        drawer_container = QWidget()
        drawer_container.hide()
        drawer_container.setStyleSheet(f"""
            QWidget {{ background: {Colors.BG_DEEP}; border-left: 2px solid {Colors.ACCENT_PRIMARY}; margin-bottom: 5px; }}
        """)

        if show_links:
            btn_link = QPushButton("Vincular")
            btn_link.setFixedHeight(22)
            btn_link.setStyleSheet(f"font-size: 10px; color: {Colors.ACCENT_PRIMARY}; background: transparent; border: none; font-weight: bold; text-align: right;")
            btn_link.setCursor(Qt.PointingHandCursor)
            btn_link.setToolTip("Gerenciar Vínculos (Expandir)")
            btn_link.clicked.connect(lambda checked=False, f=field_id, c=drawer_container, b=btn_link: self._toggle_link_drawer(f, c, b))

        if show_focus:
            btn_focus = QPushButton("🔍 Zoom")
            # btn_focus.setFixedSize(28, 24)
            btn_focus.setProperty("class", "FieldBtn")
            btn_focus.setStyleSheet("font-size: 12px; padding: 2px;")
            btn_focus.setCursor(Qt.PointingHandCursor)
            btn_focus.setToolTip("Localizar objeto no CAD")
            btn_focus.clicked.connect(lambda checked=False, f_id=field_id: self.focus_requested.emit(f_id))
        
        # --- LAYOUT HORIZONTAL ÚNICO ---
        # Garante que tudo fique em UMA linha só
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(1)

        # 1. Label — strip [field_key] suffix, move to tooltip
        import re as _re
        _clean = _re.sub(r'\s*\[[\w_]+\]:?\s*$', '', label_text).rstrip(':').strip()
        _tooltip_key = (_re.search(r'\[([\w_]+)\]', label_text) or type('', (), {'group': lambda s, n: ''})()).group(1)
        lbl = QLabel(_clean + ":")
        lbl.setFixedWidth(140)
        lbl.setWordWrap(True)
        if _tooltip_key:
            lbl.setToolTip(f"Campo: {_tooltip_key}")
        lbl.setStyleSheet(f"font-size: 9px; color: {Colors.TEXT_SECONDARY};")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(lbl)

        # 2. Input Field (Flexível, stretch=1)
        # O input vai ocupar todo o espaço que sobrar entre o label e os botões
        if w:
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            w.setMinimumWidth(20) # Permite encolher bastante se necessário
            row_layout.addWidget(w, stretch=1)
            
        # 3. Bloco de Acoes (Fixo à direita)
        actions_frame = QWidget()
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(1)
        
        # Indicador Confianca (WCAG AA: cor + tooltip + accessibleName)
        conf_score = self.item_data.get("confidence_map", {}).get(field_id, 0.0)
        color = Colors.ACCENT_DANGER
        conf_status = "Atencao"
        if conf_score > 0.8:
            color = Colors.ACCENT_SUCCESS_ALT
            conf_status = "Confirmado"
        elif conf_score > 0.4:
            color = Colors.ACCENT_INFO
            conf_status = "Revisar"
        
        conf_indicator = QLabel("*")
        conf_indicator.setFixedSize(10, 20)
        conf_indicator.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold; margin-left: 2px;")
        conf_pct = int(conf_score * 100) if conf_score else 0
        conf_indicator.setToolTip(f"Confidence: {conf_pct}% - {conf_status}")
        conf_indicator.setAccessibleName(f"Confidence {conf_pct} por cento, {conf_status}")
        actions_layout.addWidget(conf_indicator)
        
        if btn_link:
            btn_link.setText("Vínculos")
            btn_link.setFixedHeight(22)
            btn_link.setToolTip("Expandir Vínculos")
            btn_link.setStyleSheet(f"""
                QPushButton {{ font-size: 10px; color: {Colors.ACCENT_PRIMARY}; background: transparent; border: 1px solid transparent; font-weight: bold; border-radius: 4px; padding: 0 4px; }}
                QPushButton:hover {{ background: rgba(0, 212, 255, int(1/100*255)); border: 1px solid {Colors.ACCENT_PRIMARY}; }}
            """)
            actions_layout.addWidget(btn_link)

            # Badge de % confiança dos vínculos (entre Vínculos e Validar)
            _lc = self._calc_field_links_confidence(field_id)
            _lc_pct = int(_lc * 100)
            if _lc_pct > 80:
                _lc_color = Semantic.SUCCESS
                _lc_tip   = 'Alta confiança'
            elif _lc_pct > 40:
                _lc_color = Semantic.WARNING
                _lc_tip   = 'Confiança média — revisar'
            else:
                _lc_color = Semantic.DANGER
                _lc_tip   = 'Baixa confiança — verificar vínculos'
            _lc_lbl = QLabel(f'{_lc_pct}%')
            _lc_lbl.setFixedHeight(22)
            _lc_lbl.setStyleSheet(
                f'color: {_lc_color}; font-size: 9px; font-weight: bold;'
                f' padding: 0 3px; border: 1px solid {_lc_color};'
                f' border-radius: 3px;'
            )
            _lc_lbl.setToolTip(f'Confiança dos vínculos: {_lc_pct}% — {_lc_tip}')
            self._link_conf_badges[field_id] = _lc_lbl
            actions_layout.addWidget(_lc_lbl)

        if show_validate:
            btn_express = QPushButton("Validar")
            btn_express.setFixedHeight(22)
            btn_express.setToolTip("Validação Express (Clique para desfazer)")
            btn_express.setCheckable(True)
            btn_express.setChecked(field_id in self.item_data.get('validated_fields', []))
            btn_express.setProperty("class", "FieldBtn")
            btn_express.setCursor(Qt.PointingHandCursor)
            
            btn_express.setStyleSheet(f"""
                QPushButton {{ color: {Colors.TEXT_MUTED}; background: transparent; border: 1px solid transparent; border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0 4px;}}
                QPushButton:hover {{ background: rgba(0, 200, 100, int(1/100*255)); color: {Colors.ACCENT_SUCCESS}; border: 1px solid {Colors.ACCENT_SUCCESS}; }}
                QPushButton:checked {{ background: rgba(0, 200, 100, int(2/100*255)); color: {Colors.ACCENT_SUCCESS}; border: 1px solid {Colors.ACCENT_SUCCESS}; }}
            """)
            btn_express.clicked.connect(lambda checked, f_id=field_id: self._on_express_validate(f_id))
            actions_layout.addWidget(btn_express)

        if btn_focus:
            btn_focus.setText("Focar")
            btn_focus.setFixedHeight(22)
            btn_focus.setToolTip("Localizar no CAD")
            btn_focus.setStyleSheet(f"""
                QPushButton {{ color: {Colors.TEXT_MUTED}; background: transparent; border: 1px solid transparent; border-radius: 4px; font-size: 10px; padding: 0 4px;}}
                QPushButton:hover {{ background: rgba(255, 255, 255, int(1/100*255)); color: {Colors.TEXT_PRIMARY}; border: 1px solid {Colors.BORDER_DEFAULT}; }}
            """)
            actions_layout.addWidget(btn_focus)

        if show_na:
            btn_na = QPushButton("N/A")
            btn_na.setFixedHeight(22)
            btn_na.setToolTip("Marcar como Não Aplicável")
            btn_na.setCheckable(True)
            btn_na.setChecked(field_id in self.item_data.get('na_fields', []))
            btn_na.setProperty("class", "FieldBtn")
            btn_na.setCursor(Qt.PointingHandCursor)
            btn_na.setStyleSheet(f"""
                QPushButton {{ color: {Colors.TEXT_MUTED}; background: transparent; border: 1px solid transparent; border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0 4px;}}
                QPushButton:hover {{ background: rgba(244, 67, 54, int(1/100*255)); color: {Colors.ACCENT_DANGER}; border: 1px solid {Colors.ACCENT_DANGER}; }}
                QPushButton:checked {{ background: rgba(244, 67, 54, int(2/100*255)); color: {Colors.ACCENT_DANGER}; border: 1px solid {Colors.ACCENT_DANGER}; }}
            """)
            btn_na.clicked.connect(lambda chk, f_id=field_id: self._on_na_clicked(f_id, chk))
            actions_layout.addWidget(btn_na)
        else:
            btn_na = None
        
        # Guardar referências para bloqueio reativo
        self.action_btns[field_id] = {
            'link': btn_link,
            'focus': btn_focus,
            'na': btn_na,
            'express': btn_express if 'btn_express' in locals() else None
        }

        row_layout.addWidget(actions_frame)

        # Adiciona a linha principal e o drawer (que começa oculto)
        layout.addRow(row_layout)
        layout.addRow(drawer_container)

    def _on_position_changed(self, field_id, text):
        """Exibe campo de distância se for 'Centro' ou 'Laje central'"""
        dist_field_id = field_id.replace("_p", "_dist_c")
        if dist_field_id in self.fields:
            field_widget = self.fields[dist_field_id]
            visible = (text in ("Centro", "Esquerda", "Direita"))
            field_widget.setEnabled(visible)
            if not visible: field_widget.setText("0.0")
            field_widget.setVisible(True)

    def _toggle_link_drawer(self, field_id, container, btn=None):
        """Toggles the inline LinkManager drawer"""
        if container.isVisible():
            container.hide()
            if btn: btn.setText("▶ Vincular")
        else:
            if container.layout() is None or container.layout().count() == 0:
                self._load_link_manager_into(field_id, container)
            
            # Forçar atualização de dados antes de exibir
            lm = self.embedded_managers.get(field_id)
            if lm:
                links_dict = self.item_data.get('links', {})
                current_links = links_dict.get(field_id, {})
                if isinstance(current_links, list): current_links = {'label': current_links}
                lm.links = current_links
                lm.refresh_list()
                
            container.show()

    def _load_link_manager_into(self, field_id, container):
        """Instantiates and embeds a LinkManager into the container"""
        # Ensure layout
        if not container.layout():
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0,0,0,0)
            layout.setSpacing(0)
        
        # Get links
        links_dict = self.item_data.get('links', {})
        current_links = links_dict.get(field_id, {})
        if isinstance(current_links, list):
             # CONVERTER E SALVAR: Normaliza para dicionário para manter referência consistente
             # Isso corrige o bug onde o LinkManager operava num dict temporário e o remove_link falhava
             normalized_links = {'label': current_links}
             links_dict[field_id] = normalized_links
             current_links = normalized_links
             
        # New: Retrieve N/A and Validated Slots for this field
        na_slots_map = self.item_data.get('na_link_classes', {})
        current_na_slots = na_slots_map.get(field_id, [])
        
        valid_slots_map = self.item_data.get('validated_link_classes', {})
        current_valid_slots = valid_slots_map.get(field_id, [])
             
        # Create Manager
        lm = LinkManager(
            field_id, current_links,
            na_slots=current_na_slots,
            validated_slots=current_valid_slots,
            confidence_map=self.item_data.get('confidence_map', {}),
            parent=self,
        )
        self.embedded_managers[field_id] = lm
        
        # Connect Signals (Similar to original dialog logic)
        lm.pick_requested.connect(lambda slot_req: self._on_manager_pick_requested(field_id, slot_req))
        lm.focus_requested.connect(lambda l: self.element_focused.emit(l))
        lm.remove_requested.connect(lambda data: self._remove_link(field_id, data, lm))
        lm.research_requested.connect(lambda s_id: self.research_requested.emit(field_id, s_id))
        lm.training_requested.connect(lambda t_data: self._on_link_training_requested(field_id, t_data))
        lm.config_changed.connect(lambda k, v: self.config_updated.emit(k, v))
        lm.link_data_changed.connect(lambda f=field_id: (
            self._refresh_link_conf_badge(f),
            self._refresh_text_field_from_link(f),
            self.data_changed.emit(self.item_data),
        ))
        
        # New Signals for Hierarchy
        lm.slot_na_toggled.connect(lambda s_id, is_na: self._on_slot_na_toggled(field_id, s_id, is_na))
        lm.slot_validated.connect(lambda s_id, checked: self._on_slot_validated(field_id, s_id, checked))
        
        # --- NOVO: Conectar mudança de metadados de interpretação ---
        lm.metadata_changed.connect(lambda s_id, t_type, d: self._on_metadata_changed(field_id, s_id, t_type, d))
        
        # Injetar metadados existentes para carregar o cache do LM
        if 'field_metadata' in self.item_data:
            # Estrutura esperada: item_data['field_metadata'][field_id][slot_id] = {prompt, patterns}
            field_meta = self.item_data['field_metadata'].get(field_id, {})
            lm.metadata_cache = field_meta.copy() # Copia simples
        
        container.layout().addWidget(lm)

    def _on_metadata_changed(self, field_id, slot_id, meta_type, data):
        """Salva metadados vindos do LinkManager (nível de Slot)"""
        if 'field_metadata' not in self.item_data:
            self.item_data['field_metadata'] = {}
            
        if field_id not in self.item_data['field_metadata']:
            self.item_data['field_metadata'][field_id] = {}
            
        # Salva especificamente para o slot
        self.item_data['field_metadata'][field_id][slot_id] = data
        
        # Opcional: print debug
        print(f"[DetailCard] Metadados de {meta_type} atualizados para {field_id} -> {slot_id}")
        self.data_changed.emit(self.item_data)

    def _on_manager_pick_requested(self, field_id, slot_req):
        """Disparado quando um slot específico pede captura no canvas"""
        self.pick_requested.emit(field_id, slot_req)

    def _remove_link(self, field_id, data, dlg):
        """data is a dict: {'slot': slot_id, 'link': link_obj}"""
        slot_id = data.get('slot')
        link = data.get('link')
        
        links_dict = self.item_data.get('links', {})
        field_links = links_dict.get(field_id, {})
        
        if slot_id in field_links:
            # REMOÇÃO ROBUSTA: LinkManager pode já ter removido da lista (mesma ref), 
            # ou pode ser uma cópia.
            
            # 1. Tentar remover por identidade de objeto
            if link in field_links[slot_id]:
                field_links[slot_id].remove(link)
                print(f"[DetailCard] Link removido por referência direta de {slot_id}.")
            else:
                 # 2. Remover por igualdade de conteúdo (Fallback)
                 idx_to_remove = -1
                 for i, l in enumerate(field_links[slot_id]):
                     # Compara chaves essenciais para garantir que é o mesmo vínculo
                     same_text = l.get('text') == link.get('text')
                     same_type = l.get('type') == link.get('type')
                     same_pos = str(l.get('pos')) == str(link.get('pos')) # str compare to avoid float issues
                     same_pts = str(l.get('points')) == str(link.get('points'))
                     
                     if same_type and (same_text or same_pts): # Pelo menos tipo e um identificador
                         if same_pos: # Posição é forte indicador
                             idx_to_remove = i
                             break
                 
                 if idx_to_remove >= 0:
                     del field_links[slot_id][idx_to_remove]
                     print(f"[DetailCard] Link removido por comparação de valor de {slot_id}.")
                 else:
                     print(f"[DetailCard] AVISO: Link não encontrado para remoção em {slot_id} (Provavelmente removido pelo LinkManager?)")
                
            # Se o link sendo removido estava validado, propaga a desvalidação para o slot
            if link.get('validated'):
                self._on_link_training_requested(field_id, {
                    'status': 'removed',
                    'slot': slot_id,
                    'link': link,
                    'light_sync': True
                })
                
            # Verificar se restaram vínculos validados no campo. Se não, desvalida o campo inteiro.
            has_validated_links = False
            for s_id, s_links in field_links.items():
                if any(l.get('validated') for l in s_links):
                    has_validated_links = True
                    break
                    
            if not has_validated_links and field_id in self.item_data.get('validated_fields', []):
                self.undo_field_validation(field_id)
            
            # Recalcular is_validated da Ficha inteira
            if not self.item_data.get('validated_fields'):
                self.item_data['is_validated'] = False

            print(f"[DetailCard] Vínculo removido de {field_id}. Restantes: {len(field_links[slot_id]) if slot_id in field_links else 0}")
            self.refresh_validation_styles()
            
            # Notificar mudança de dados para sincronizar listas e canvas
            self.data_changed.emit(self.item_data)
            self.element_removed.emit({'slot': slot_id, 'link': link})
            dlg.refresh_list()

    def _on_link_training_requested(self, field_id, t_data):
        """Intercepta o treino granular do link para propagar (vice-versa) para a validação do campo."""
        status = t_data.get('status')
        slot_id = t_data.get('slot')
        light_sync = bool(t_data.get('light_sync'))

        if not light_sync:
            # Propaga o evento original apenas quando ha intencao de registrar treino.
            self.training_requested.emit(field_id, t_data)
        
        # Se foi removida a validação de um vínculo, e o slot também estava validado, removemos a do slot
        if status == 'removed' and slot_id:
            self._clear_full_validation_state()
            valid_map = self.item_data.get('validated_link_classes', {})
            if field_id in valid_map and slot_id in valid_map[field_id]:
                valid_map[field_id].remove(slot_id)
                self.validation_changed.emit({
                    'item': self.item_data,
                    'field_id': field_id,
                    'slot_id': slot_id,
                    'is_valid': False,
                    'scope': 'slot'
                })
                # Atualizar a UI do próprio Header/LinkManager seria necessário, 
                # mas o refresh_validation_styles pode não dar conta de atualizar o checkbox do Header.
                # O Header checkbox é gerido por LinkManager._on_slot_validated.
                # Então avisamos o LinkManager para desmarcar seu header:
                if field_id in self.embedded_managers:
                    self.embedded_managers[field_id]._sync_slot_validation_ui(slot_id, False, refresh=not light_sync)

        if light_sync:
            self.validation_changed.emit({
                'item': self.item_data,
                'field_id': field_id,
                'slot_id': slot_id,
                'is_valid': status == 'valid',
                'scope': 'link',
            })
        else:
            self.refresh_validation_styles()

    def _clear_full_validation_state(self):
        """Remove o selo de item completo quando uma validação granular é desfeita."""
        if self.item_data.get('is_fully_validated'):
            self.item_data['is_fully_validated'] = False
        if self.item_data.get('is_validated'):
            self.item_data['is_validated'] = False

    def _campos_obrigatorios_do_item(self) -> set:
        item_type = str(self.item_data.get('type') or '').lower()
        if 'laje' in item_type:
            return set(self._LAJE_REQUIRED_VALIDATION_FIELDS)
        # Fora de LAJ, sela somente quando cada campo que a UI oferece
        # para Validar/N/A foi resolvido pelo usuario.
        return set(self.action_btns)

    def _auto_seal_completed_item(self) -> bool:
        """Recalcula os 3 selos de campo (azul/rosa/laranja,
        `src/core/validation_model.calcular_selos_item`) sempre que os
        campos mudam, e concede — sem diálogo — o selo azul + o selo verde
        (cascata já existente) na primeira vez que os campos completam
        100% via `humano_app` [2026-07-13, modelo de 4 selos]."""
        from src.core.validation_model import calcular_selos_item

        na_fields = self.item_data.get('na_fields', [])
        na_fields = set(na_fields.keys()) if isinstance(na_fields, dict) else set(na_fields)
        selos = calcular_selos_item(
            self.item_data.get('validated_fields', {}), na_fields, self._campos_obrigatorios_do_item(),
        )
        self.item_data['selo_rosa'] = selos['rosa']
        self.item_data['selo_laranja'] = selos['laranja']

        if self.item_data.get('is_fully_validated') or not selos['azul']:
            self.item_data['selo_azul'] = selos['azul']
            return False

        # Azul = todos os campos resolvidos por humano no app + validacao
        # do item. O verde permanece reservado ao fluxo manual de
        # validacao simples, mas a cascata já existente se mantém:
        # atingir azul também liga verde.
        self.item_data['selo_azul'] = True
        self.item_data['is_fully_validated'] = True  # alias de compat (nome antigo)
        self.item_data['is_validated'] = True
        self.refresh_validation_styles()
        self.validation_changed.emit({
            'item': self.item_data,
            'is_valid': True,
            'scope': 'item_auto_complete',
        })
        self.data_validated.emit(self.item_data)
        self.log_requested.emit('Item certificado automaticamente: 100% dos campos validados/N/A (selo azul).')
        return True

    # ── Validação individual por segmento (FV/LV) ──────────────────────────
    # Espelha o par selo verde/azul do item, mas escopado a 1 segmento
    # (`{prefix}_seg_{idx}`). Campos validam o segmento (auto, via
    # `_sync_segment_flag_from_fields`), mas validar um segmento manualmente
    # NUNCA valida seus campos — só quando TODOS os segmentos ativos do item
    # estão validados (manual ou por campo) o item ganha selo verde; o selo
    # azul do item continua exigindo 100% dos campos do item inteiro.
    _SEG_FIELD_RE = re.compile(r'^(viga_(?:a|b|fundo))_seg_(\d+)_')

    def _extract_segment_from_field(self, field_id: str):
        match = self._SEG_FIELD_RE.match(str(field_id))
        if not match:
            return None
        return match.group(1), int(match.group(2))

    def _segment_key(self, prefix: str, idx: int) -> str:
        return f'{prefix}_seg_{idx}'

    def _segment_required_fields(self, prefix: str, idx: int) -> set:
        seg_uid = self._segment_key(prefix, idx)
        return {fid for fid in self.action_btns if str(fid).startswith(f'{seg_uid}_')}

    def _segment_reaches_full_validation(self, prefix: str, idx: int) -> bool:
        validated = self.item_data.get('validated_fields', [])
        na_fields = self.item_data.get('na_fields', [])
        validated = set(validated.keys()) if isinstance(validated, dict) else set(validated)
        na_fields = set(na_fields.keys()) if isinstance(na_fields, dict) else set(na_fields)
        completed = validated | na_fields
        required = self._segment_required_fields(prefix, idx)
        return bool(required) and required.issubset(completed)

    def _all_active_segment_keys(self) -> set:
        """Todas as chaves de segmento ativas neste item — FV usa só
        `viga_fundo`; LV usa `viga_a`/`viga_b` conforme o tipo do item."""
        itype = str(self.item_data.get('type') or '').lower()
        keys: set = set()
        if itype in ('viga_fundo', 'viga_fundo_c'):
            for idx in self._existing_beam_segment_indices('viga_fundo', is_fundo=True):
                keys.add(self._segment_key('viga_fundo', idx))
            return keys
        prefixes = []
        if itype in ('viga_lateral', 'viga_lateral_a'):
            prefixes.append('viga_a')
        if itype in ('viga_lateral', 'viga_lateral_b'):
            prefixes.append('viga_b')
        for prefix in prefixes:
            for idx in self._existing_beam_segment_indices(prefix, is_fundo=False):
                keys.add(self._segment_key(prefix, idx))
        return keys

    def _maybe_cascade_segments_to_item(self):
        """Quando TODOS os segmentos ativos estão validados (manual ou via
        campo), o item ganha selo verde — nunca inventa o selo azul a partir
        disso, que continua exigindo 100% dos campos do item inteiro."""
        active = self._all_active_segment_keys()
        if not active:
            return
        segs = self.item_data.get('validated_segments') or {}
        if all(segs.get(k) for k in active) and not self.item_data.get('is_validated'):
            self.item_data['is_validated'] = True
            self.refresh_validation_styles()
            self.validation_changed.emit({
                'item': self.item_data,
                'is_valid': True,
                'scope': 'all_segments_complete',
            })

    def _sync_segment_flag_from_fields(self, prefix: str, idx: int):
        """Chamado após validar/desfazer um campo — emite o selo automático
        do SEGMENTO quando os campos DELE (só dele) chegam a 100%, espelhando
        `_auto_seal_completed_item` mas escopado. Não mexe no selo manual de
        outros segmentos nem desliga um selo manual já dado a este."""
        key = self._segment_key(prefix, idx)
        segs = self.item_data.setdefault('validated_segments', {})
        if self._segment_reaches_full_validation(prefix, idx):
            if not segs.get(key):
                segs[key] = True
                self._maybe_cascade_segments_to_item()

    def toggle_segment_validated_manual(self, prefix: str, idx: int):
        """Selo verde MANUAL de 1 segmento — ação do usuário, independente
        dos campos (o inverso é automático: campos validam o segmento, ver
        `_sync_segment_flag_from_fields`; validar o segmento não valida os
        campos dele)."""
        key = self._segment_key(prefix, idx)
        segs = self.item_data.setdefault('validated_segments', {})
        segs[key] = not segs.get(key, False)
        if segs[key]:
            self._maybe_cascade_segments_to_item()
        self.refresh_validation_styles()
        self.data_changed.emit(self.item_data)

    def _build_segment_validate_button(self, prefix: str, idx: int) -> QPushButton:
        """Botão checável de validação individual do segmento (FV/LV) — usado
        no cabeçalho do card de segmento em `_add_rich_segment_pack`/
        `_add_fundo_segment_pack`."""
        key = self._segment_key(prefix, idx)
        segs = self.item_data.get('validated_segments') or {}
        btn = QPushButton("✓ Segmento validado")
        btn.setCheckable(True)
        btn.setChecked(bool(segs.get(key)))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(28)

        def _style(checked: bool):
            if checked:
                btn.setStyleSheet(
                    f"font-size: 11px; font-weight: bold; padding: 4px 10px; "
                    f"background: {Colors.ACCENT_MINT}; color: #05261f; "
                    f"border: 1px solid {Colors.ACCENT_MINT}; border-radius: 4px;"
                )
            else:
                btn.setStyleSheet(
                    f"font-size: 11px; padding: 4px 10px; background: {Colors.BG_CARD}; "
                    f"color: {Colors.TEXT_SECONDARY}; border: 1px solid {Colors.BORDER_INPUT}; "
                    f"border-radius: 4px;"
                )

        _style(btn.isChecked())

        def _on_click(checked, p=prefix, i=idx, b=btn):
            self.toggle_segment_validated_manual(p, i)
            _style(b.isChecked())

        btn.clicked.connect(_on_click)
        return btn

    def mark_field_validated(self, field_id, is_valid=True, emit_data_changed=True):
        """Aplica estilo visual de validação no widget do campo de forma
        otimizada — validação humana feita aqui no app desktop é sempre
        origem `humano_app` (selo azul), ver `src/core/validation_model.py`."""
        from src.core.validation_model import (
            ORIGEM_HUMANO_APP, adicionar_validacao_campo, origens_do_campo, remover_validacao_campo,
        )
        validated = self.item_data.get('validated_fields')

        # Otimização: Se já estiver no estado desejado, não faz nada
        ja_validado_humano = ORIGEM_HUMANO_APP in origens_do_campo(validated, field_id)
        if is_valid and ja_validado_humano: return
        if not is_valid and not ja_validado_humano: return

        if is_valid:
            self.item_data['validated_fields'] = adicionar_validacao_campo(validated, field_id, ORIGEM_HUMANO_APP)

            # --- CASCADE VALIDATION TO LINKS ---
            if 'links' in self.item_data and field_id in self.item_data['links']:
                links_data = self.item_data['links'][field_id]
                if isinstance(links_data, dict):
                    valid_map = self.item_data.setdefault('validated_link_classes', {})
                    valid_map[field_id] = list(links_data.keys())

                    for slot_id, link_list in links_data.items():
                        for link in link_list:
                            link['validated'] = True

            if field_id in self.embedded_managers:
                lm = self.embedded_managers[field_id]
                lm.links = self.item_data['links'].get(field_id, {})
                lm.validated_slots = set(self.item_data.get('validated_link_classes', {}).get(field_id, []))
                lm.refresh_list()
        else:
            self.item_data['validated_fields'] = remover_validacao_campo(validated, field_id, origem=ORIGEM_HUMANO_APP)
            self._clear_full_validation_state()

        self._refresh_link_conf_badge(field_id)
        seg = self._extract_segment_from_field(field_id) if is_valid else None
        if seg:
            self._sync_segment_flag_from_fields(*seg)
        self.refresh_validation_styles()
        auto_sealed = is_valid and self._auto_seal_completed_item()
        if emit_data_changed:
            self.data_changed.emit(self.item_data)
        elif not auto_sealed:
            self.validation_changed.emit({
                'item': self.item_data,
                'field_id': field_id,
                'is_valid': is_valid,
                'scope': 'field',
            })

    def _on_na_clicked(self, field_id, checked):
        """Gerencia o estado 'Não se Aplica' de um campo com justificativa"""
        na_fields = self.item_data.setdefault('na_fields', [])
        na_reasons = self.item_data.setdefault('na_reasons', {})
        
        if checked:
            # Não solicita mais comentário (Task_01)
            reason = "Omitido pelo usuário"
            na_reasons[field_id] = reason
            if field_id not in na_fields: na_fields.append(field_id)
            self.mark_field_validated(field_id, True)
                
            # --- CASCADE N/A TO SLOTS ---
            if 'na_link_classes' not in self.item_data: self.item_data['na_link_classes'] = {}
            na_map = self.item_data['na_link_classes']
            
            slots_to_na = []
            if field_id in self.embedded_managers:
                lm = self.embedded_managers[field_id]
                slots_to_na = [s['id'] for s in lm._get_slots(field_id)]
            else:
                current_links = self.item_data.get('links', {}).get(field_id, {})
                if isinstance(current_links, dict):
                    slots_to_na = list(current_links.keys())
            
            na_map[field_id] = list(set(slots_to_na))
            
            # Limpa vínculos
            if 'links' in self.item_data and field_id in self.item_data['links']:
                links_data = self.item_data['links'][field_id]
                if isinstance(links_data, dict):
                    for k in links_data: links_data[k] = []
                elif isinstance(links_data, list):
                    self.item_data['links'][field_id] = {}

            # Atualiza LM se existir
            if field_id in self.embedded_managers:
                lm = self.embedded_managers[field_id]
                lm.na_slots = set(slots_to_na)
                lm.links = self.item_data['links'].get(field_id, {})
                lm.refresh_list(partial=True)
            
            # Visual Clean
            widget = self.fields.get(field_id)
            if widget:
                if isinstance(widget, QLineEdit): widget.setText("N/A")
                elif isinstance(widget, QComboBox):
                    idx = widget.findText("N/A")
                    if idx >= 0: widget.setCurrentIndex(idx)
            
            # Treino em Cascata
            for s_id in slots_to_na:
                self.training_requested.emit(field_id, {
                    'status': 'na',
                    'comment': f"Cascata N/A: {reason}",
                    'slot': s_id
                })
            if not slots_to_na:
                self.training_requested.emit(field_id, {
                    'status': 'na',
                    'comment': f"Campo N/A: {reason}",
                    'slot': 'main'
                })
        else:
            if field_id in na_fields: na_fields.remove(field_id)
            if field_id in na_reasons: del na_reasons[field_id]
            
            widget = self.fields.get(field_id)
            if widget and isinstance(widget, QLineEdit) and widget.text() == "N/A":
                widget.setText("")
            
            na_map = self.item_data.get('na_link_classes', {})
            slots_to_reset = na_map.get(field_id, [])
            for s_id in slots_to_reset:
                 self.training_requested.emit(field_id, { 'status': 'removed', 'slot': s_id, 'link': {'text': 'N/A'} })
            
            if field_id in na_map: del na_map[field_id]
            self.mark_field_validated(field_id, False)
        self.refresh_validation_styles()
        self.data_changed.emit(self.item_data)

    def _on_express_validate(self, field_id):
        """Valida o campo imediatamente ou Desfaz (Undo) se já estava validado"""
        is_already_validated = field_id in self.item_data.get('validated_fields', [])
        
        if is_already_validated:
             self.undo_field_validation(field_id)
             return
             
        widget = self.fields.get(field_id)
        if not widget: return
        
        val = ""
        if isinstance(widget, QLineEdit): val = widget.text()
        elif isinstance(widget, QComboBox): val = widget.currentText()
        
        # Recuperar links existentes para treino
        links = self.item_data.get('links', {}).get(field_id, {})
        if isinstance(links, list): links = {'label': links}
        
        target_link = None
        target_slot = 'default'
        
        # Busca primeiro link disponível
        for slot, link_list in links.items():
            if link_list:
                target_link = link_list[0]
                target_slot = slot
                break
        
        if not target_link:
            # Cria synthetic link se não houver
            target_link = {
                'text': val, 
                'type': 'text', 
                'pos': self.item_data.get('pos', (0,0)), 
                'debug': 'Express Validation'
            }
            
        # Emite sinal de treino para o campo principal (se aplicavel)
        if target_slot == 'default':
             self.training_requested.emit(field_id, {
                 'slot': target_slot,
                 'link': target_link,
                 'comment': "Expresso: Validado pelo usuário",
                 'status': "valid",
                 'propagate': False,
                 'ui_refresh': False
             })

        # --- SMART VALIDATION CASCADE ---
        # 1. Obter slots esperados para este campo
        expected_slots = []
        if field_id in self.embedded_managers:
             expected_slots = [s['id'] for s in self.embedded_managers[field_id]._get_slots(field_id)]
        else:
             # Instância temporária para obter configuração
             try:
                 tmp = LinkManager(field_id, {}, parent=None)
                 expected_slots = [s['id'] for s in tmp._get_slots(field_id)]
                 tmp.deleteLater()
             except:
                 expected_slots = []

        # 2. Verificar conteúdo e distribuir status
        if expected_slots:
             valid_map = self.item_data.setdefault('validated_link_classes', {})
             na_map = self.item_data.setdefault('na_link_classes', {})
             
             # Garante listas iniciadas
             if field_id not in valid_map: valid_map[field_id] = []
             if field_id not in na_map: na_map[field_id] = []
             
             current_links = self.item_data.get('links', {}).get(field_id, {})
             if isinstance(current_links, list): current_links = {'label': current_links} # Normalize
             
             for slot_id in expected_slots:
                 has_links = slot_id in current_links and len(current_links[slot_id]) > 0
                 
                 if has_links:
                     # Tem links -> Valida
                     if slot_id not in valid_map[field_id]: 
                         valid_map[field_id].append(slot_id)
                     if slot_id in na_map[field_id]:
                         na_map[field_id].remove(slot_id)
                         
                     # Treinar este slot como valido
                     self.training_requested.emit(field_id, {
                         'slot': slot_id,
                         'link': current_links[slot_id][0], # Usa o primeiro link como exemplo
                         'comment': f"Smart Validation: Slot {slot_id} validado.",
                         'status': "valid",
                         'propagate': False,
                         'ui_refresh': False
                     })
                 else:
                     # Vazio -> Marca N/A (Não se aplica a este item)
                     if slot_id not in na_map[field_id]:
                         na_map[field_id].append(slot_id)
                     if slot_id in valid_map[field_id]:
                         valid_map[field_id].remove(slot_id)
                         
                     # Treinar este slot como N/A
                     self.training_requested.emit(field_id, {
                         'status': 'na',
                         'comment': f"Smart Validation: Slot {slot_id} vazio marcado como N/A",
                         'slot': slot_id,
                         'ui_refresh': False
                     })
        
        # Marca e atualiza visual
        self.mark_field_validated(field_id, True, emit_data_changed=False)
        if field_id == "laje_outline_segs":
            self._record_human_laje_outline_validated()
        
        if self.embedded_managers.get(field_id):
            return

    def _record_human_laje_outline_validated(self):
        try:
            from src.core.engrev_laj_n1_interpretacao_learning_store import (
                record_human_laje_outline_validated,
            )
            links = self.item_data.get('links', {}).get('laje_outline_segs', {})
            elemento_id = (
                self.item_data.get('id_item')
                or self.item_data.get('name')
                or self.item_data.get('nome')
                or self.item_data.get('id')
                or 'LAJ'
            )
            record_human_laje_outline_validated(
                elemento_id=str(elemento_id),
                laje_outline_segs=links,
                obra_name=self.item_data.get('obra_name') or self.item_data.get('work_name'),
                pavimento=self.item_data.get('pavimento') or self.item_data.get('pavement_name'),
                analysis_mode=self.item_data.get('analysis_mode', 'engrev_assisted'),
            )
        except Exception as exc:
            self.log_requested.emit(f"Falha ao registrar evento human_laje_outline_validated: {exc}")

    def _add_pilar_opening_group(self, form_layout, label_text, prefix):
        """Creates a specialized grouped row for Pillar Openings (Clean List)"""
        # Outer container for the group
        group_container = QWidget()
        group_layout = QVBoxLayout(group_container)
        group_layout.setContentsMargins(0, 5, 0, 5)
        group_layout.setSpacing(2)

        # Header with Label + Link Button
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0,0,0,0)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"font-size: 11px; color: {Colors.ACCENT_TEAL}; font-weight: bold;")

        # Drawer for Pillar
        drawer = QWidget()
        drawer.hide()
        drawer.setStyleSheet(f"background: {Colors.BG_DEEP}; border-left: 2px solid {Colors.ACCENT_TEAL};")

        btn_link = QPushButton("Vincular")
        btn_link.setFixedHeight(22)
        btn_link.setCursor(Qt.PointingHandCursor)
        btn_link.setStyleSheet(f"font-size: 10px; color: {Colors.ACCENT_PRIMARY}; background: transparent; border: none; font-weight: bold; text-align: right;")
        btn_link.clicked.connect(lambda checked=False, p=prefix, d=drawer, b=btn_link: self._toggle_link_drawer(p, d, b))
        
        btn_focus = QPushButton("🔍 Zoom")
        # btn_focus.setFixedSize(24, 20)
        btn_focus.setCursor(Qt.PointingHandCursor)
        btn_focus.setStyleSheet(f"background: transparent; border: 1px solid {Colors.BORDER_INPUT}; color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        btn_focus.clicked.connect(lambda checked=False, p=prefix: self.focus_requested.emit(p))
        
        header_layout.addWidget(lbl)
        header_layout.addStretch()
        header_layout.addWidget(btn_focus)
        header_layout.addWidget(btn_link)
        
        group_layout.addWidget(header_widget)
        group_layout.addWidget(drawer) # Add drawer here too
        
        # Internal Form for Fields (Indented)
        form_inner_widget = QWidget()
        form_inner = QFormLayout(form_inner_widget)
        form_inner.setContentsMargins(5, 0, 0, 0) # Reduzido ident para caber melhor
        form_inner.setSpacing(1)
        form_inner.setLabelAlignment(Qt.AlignLeft)
        
        # Fields: Dist, Larg, Diff
        # Remove fixed width restrictions for cleaner look
        f_dist = self._create_sub_field(prefix, "dist", "", 0) 
        f_larg = self._create_sub_field(prefix, "larg", "", 0)
        f_diff = self._create_sub_field(prefix, "diff", "", 0)
        
        form_inner.addRow("Dist:", f_dist)
        form_inner.addRow("Larg:", f_larg)
        form_inner.addRow("Dif:", f_diff)
        
        group_layout.addWidget(form_inner_widget)
        
        # Add the whole group as a single row in the main form (spanning both cols)
        form_layout.addRow(group_container)

    def _add_beam_opening_group(self, form_layout, label_text, prefix):
        """Creates a specialized grouped row for Beam Openings (Clean List)"""
        group_container = QWidget()
        group_layout = QVBoxLayout(group_container)
        group_layout.setContentsMargins(0, 5, 0, 5)
        group_layout.setSpacing(2)

        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0,0,0,0)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"font-size: 11px; color: {Colors.ACCENT_TEAL}; font-weight: bold;")

        # Drawer for Beam
        drawer = QWidget()
        drawer.hide()
        drawer.setStyleSheet(f"background: {Colors.BG_DEEP}; border-left: 2px solid {Colors.ACCENT_TEAL};")

        btn_link = QPushButton("Vincular")
        btn_link.setFixedHeight(22)
        btn_link.setCursor(Qt.PointingHandCursor)
        btn_link.setStyleSheet(f"font-size: 10px; color: {Colors.ACCENT_PRIMARY}; background: transparent; border: none; font-weight: bold; text-align: right;")
        btn_link.clicked.connect(lambda checked=False, p=prefix, d=drawer, b=btn_link: self._toggle_link_drawer(p, d, b))
        
        btn_focus = QPushButton("🔍 Zoom")
        # btn_focus.setFixedSize(24, 20)
        btn_focus.setCursor(Qt.PointingHandCursor)
        btn_focus.setStyleSheet(f"background: transparent; border: 1px solid {Colors.BORDER_INPUT}; color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        btn_focus.clicked.connect(lambda checked=False, p=prefix: self.focus_requested.emit(p))
        
        header_layout.addWidget(lbl)
        header_layout.addStretch()
        header_layout.addWidget(btn_focus)
        header_layout.addWidget(btn_link)
        
        group_layout.addWidget(header_widget)
        group_layout.addWidget(drawer)

        # Internal Form
        form_inner_widget = QWidget()
        form_inner = QFormLayout(form_inner_widget)
        form_inner.setContentsMargins(5, 0, 0, 0) # Reduzido ident
        form_inner.setSpacing(1)
        form_inner.setLabelAlignment(Qt.AlignLeft)

        # Fields: Larg, Aj.Boca, Prof, Aj.Prof
        f_larg = self._create_sub_field(prefix, "larg", "", 0)
        f_aj_b = self._create_sub_field(prefix, "aj_boca", "", 0)
        f_prof = self._create_sub_field(prefix, "prof", "", 0)
        f_aj_p = self._create_sub_field(prefix, "aj_prof", "", 0)

        form_inner.addRow("Larg M:", f_larg)
        form_inner.addRow("Aj. Boca:", f_aj_b)
        form_inner.addRow("Prof:", f_prof)
        form_inner.addRow("Aj. Prof:", f_aj_p)
        
        group_layout.addWidget(form_inner_widget)

        form_layout.addRow(group_container)

    def _create_sub_field(self, prefix, suffix, placeholder, width):
        """Helper to create sub-fields for complex groups"""
        full_key = f"{prefix}_{suffix}"
        
        default_val = self.item_data.get(full_key, "")
        
        f = QLineEdit(str(default_val))
        if placeholder: f.setPlaceholderText(placeholder)
        if width > 0:
            f.setFixedWidth(width)
        else:
            f.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
        f.setStyleSheet(self.STYLE_DEFAULT)
        f.textChanged.connect(lambda txt: self._on_field_changed(full_key, txt))
        
        self.fields[full_key] = f
        return f

    def _on_field_changed(self, key, value):
        """Atualiza item_data imediatamente ao digitar"""
        self.item_data[key] = value
        self.data_changed.emit(self.item_data)
        
        # Sincronização especial para Marco DXF
        if key.startswith('ext_viga_') and 'vigas_individuais' in self.item_data:
            v_id = key.replace('ext_viga_', '')
            for v in self.item_data['vigas_individuais']:
                if v.get('id') == v_id:
                    try:
                        v['extension_len'] = float(value)
                        v['final_len'] = v['original_len'] + v['extension_len']
                    except: pass
                    break

    # [2026-07-13] Rótulo + emoji de cada origem, pra tooltip "quem validou".
    _ORIGEM_ROTULO = {
        'humano_app': ('🔵', 'App Desktop (humano)'),
        'humano_portal': ('🌸', 'Portal de Formas (humano)'),
        'qa_agente': ('🟠', 'Agente QA-Global-Evidências'),
    }

    def _estilo_e_tooltip_por_origem(self, fid: str):
        """Escolhe a cor de borda (prioridade azul > laranja > rosa quando
        o campo tem mais de 1 origem — só pra escolha visual da ÚNICA
        borda possível, não é peso/hierarquia de confiança) e monta o
        tooltip listando TODAS as origens presentes (pode ter até 3)."""
        from src.core.validation_model import origens_do_campo
        origens = origens_do_campo(self.item_data.get('validated_fields'), fid)
        if 'humano_app' in origens:
            estilo = self.STYLE_VALID
        elif 'qa_agente' in origens:
            estilo = self.STYLE_VALID_LARANJA
        elif 'humano_portal' in origens:
            estilo = self.STYLE_VALID_ROSA
        else:
            estilo = None
        if origens:
            partes = [self._ORIGEM_ROTULO[o][0] + ' ' + self._ORIGEM_ROTULO[o][1] for o in origens if o in self._ORIGEM_ROTULO]
            tooltip = 'Validado por:\n' + '\n'.join(partes)
        else:
            tooltip = ''
        return estilo, tooltip

    def refresh_validation_styles(self):
        """Otimizado: Varre campos e aplica estilos apenas em mudanças de estado"""
        validated_fields_raw = self.item_data.get('validated_fields', [])
        validated_fields = set(validated_fields_raw.keys()) if isinstance(validated_fields_raw, dict) else set(validated_fields_raw)
        na_fields = set(self.item_data.get('na_fields', []))

        for fid, w in list(self.fields.items()):
            try:
                if isinstance(w, QButtonGroup): continue

                is_valid = fid in validated_fields
                is_na = fid in na_fields

                # 1. Input Fields (Optimized Stylesheet)
                if isinstance(w, (QLineEdit, QComboBox)):
                    if not is_na and fid.endswith(('_prof', '_boca', '_dist', '_larg', '_h_sel')):
                         # Verificar N/A herdado de tabelas de abertura
                         # Prefixo pai é o fid sem o sufixo
                         parent_na = False
                         for suf in ['_prof', '_boca', '_dist', '_larg', '_h_sel']:
                             if fid.endswith(suf):
                                 parent_id = fid[:-len(suf)]
                                 if parent_id in na_fields:
                                     is_na = True
                                     parent_na = True
                                     break

                    estilo_origem, tooltip_origem = self._estilo_e_tooltip_por_origem(fid)
                    target_style = self.STYLE_NA if is_na else (estilo_origem or self.STYLE_DEFAULT)
                    if w.styleSheet() != target_style:
                        w.setStyleSheet(target_style)
                    if not is_na and w.toolTip() != tooltip_origem:
                        w.setToolTip(tooltip_origem)

                    target_enabled = not is_na
                    if w.isEnabled() != target_enabled:
                        w.setEnabled(target_enabled)

                # 2. Action Buttons
                btns = self.action_btns.get(fid, {})
                if btns:
                    for bkey in ['focus', 'express']:
                        b = btns.get(bkey)
                        if b and b.isEnabled() == is_na: # Toggle only if needed
                            b.setEnabled(not is_na)
                    
                    b_valid = btns.get('express')
                    if b_valid:
                        if b_valid.isChecked() != is_valid:
                            b_valid.blockSignals(True)
                            b_valid.setChecked(is_valid)
                            b_valid.blockSignals(False)

                    b_na = btns.get('na')
                    if b_na:
                        if b_na.isChecked() != is_na:
                            b_na.blockSignals(True)
                            b_na.setChecked(is_na)
                            b_na.blockSignals(False)
                
                # 3. Linked Labels (hide_input=True)
                if isinstance(w, QLabel):
                    if is_na:
                        new_text = "N/A - Não se aplica"
                        if w.text() != new_text:
                            w.setText(new_text)
                            w.setStyleSheet(f"color: {Colors.ACCENT_INFO}; font-weight: bold; font-size: 10px; font-style: italic;")
                    else:
                        links = self.item_data.get('links', {}).get(fid, {})
                        count = 0
                        if isinstance(links, dict):
                            count = len(links.get('seg_bottom', [])) if fid == 'viga_segs' else sum(len(l) for l in links.values())
                        elif isinstance(links, list):
                            count = len(links)
                        
                        if is_valid:
                            from src.core.validation_model import origens_do_campo
                            origens = origens_do_campo(self.item_data.get('validated_fields'), fid)
                            if 'humano_app' in origens:
                                cor_link, icone_link = Colors.ACCENT_PRIMARY, '🔵'
                            elif 'qa_agente' in origens:
                                cor_link, icone_link = Colors.ACCENT_WARNING, '🟠'
                            elif 'humano_portal' in origens:
                                cor_link, icone_link = Colors.ACCENT_ROSA, '🌸'
                            else:
                                cor_link, icone_link = Colors.ACCENT_SUCCESS_ALT, '✅'
                            txt = f"{count} Vínculo(s) {icone_link}" if count > 0 else f"Validado {icone_link}"
                            if w.text() != txt:
                                w.setText(txt)
                                w.setStyleSheet(f"color: {cor_link}; font-weight: bold; font-size: 11px; background: rgba(0, 204, 102, 26); border: 1px solid {cor_link}; border-radius: 4px; padding: 2px;")
                                _, tooltip_link = self._estilo_e_tooltip_por_origem(fid)
                                w.setToolTip(tooltip_link or '')
                        elif count > 0:
                            txt = f"{count} Vínculo(s) Ok"
                            if w.text() != txt:
                                w.setText(txt)
                                w.setStyleSheet(f"color: {Colors.ACCENT_SUCCESS_ALT}; font-weight: bold; font-size: 10px;")
                        else:
                            if w.text() != "Vínculo Pendente":
                                w.setText("Vínculo Pendente")
                                w.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-style: italic; font-size: 10px;")
            except RuntimeError:
                pass

        # 4. Indicators
        for fid, w in list(self.indicators.items()):
            try:
                is_valid = fid in validated_fields
                is_na = fid in na_fields
                indicator = w
                if is_na:
                    st = f"color: {Colors.ACCENT_INFO}; font-size: 14px; margin-right: 5px;"
                elif is_valid:
                    from src.core.validation_model import origens_do_campo
                    origens = origens_do_campo(self.item_data.get('validated_fields'), fid)
                    if 'humano_app' in origens:
                        cor_ind = Colors.ACCENT_PRIMARY
                    elif 'qa_agente' in origens:
                        cor_ind = Colors.ACCENT_WARNING
                    elif 'humano_portal' in origens:
                        cor_ind = Colors.ACCENT_ROSA
                    else:
                        cor_ind = Colors.ACCENT_SUCCESS_ALT
                    st = f"color: {cor_ind}; font-size: 14px; margin-right: 5px;"
                else:
                    conf = self.item_data.get('confidence_map', {}).get(fid, 0.0)
                    clr = Colors.ACCENT_DANGER if conf <= 0.4 else (Colors.ACCENT_INFO if conf <= 0.8 else Colors.ACCENT_SUCCESS_ALT)
                    st = f"color: {clr}; font-size: 14px; margin-right: 5px;"
                
                if indicator.styleSheet() != st:
                    indicator.setStyleSheet(st)
            except RuntimeError:
                pass
        
        # Async-like update for LinkManagers
        for fid, lm in list(self.embedded_managers.items()):
            try:
                if lm.isVisible(): # Optimization: Refresh only if visible
                    lm.na_slots = set(self.item_data.get('na_link_classes', {}).get(fid, []))
                    lm.validated_slots = set(self.item_data.get('validated_link_classes', {}).get(fid, []))
                    lm.refresh_list()
            except RuntimeError:
                pass

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 5, 2, 5) # Margem mínima
        layout.setSpacing(3)
        
        # --- Cabeçalho Dinâmico ---
        elem_type = self.item_data.get('type', 'Pilar').upper()
        
        # PARA LAJES ou MARCO: O Header é omitido aqui e criado dentro da aba/view específica
        if 'LAJE' not in elem_type and 'MARCO' not in elem_type:
            header_title = f"DADOS GERAIS - {elem_type}"
            
            header = QGroupBox(header_title)
            header.setStyleSheet(f"QGroupBox {{ font-size: 10px; font-weight: bold; color: {Colors.ACCENT_PRIMARY}; border: 1px solid {Colors.BORDER_DEFAULT}; margin-top: 5px; padding-top: 8px; }}")
            h_layout = QFormLayout(header)
            h_layout.setContentsMargins(2, 2, 2, 2)
            h_layout.setSpacing(1)
            
            self._add_linked_row(h_layout, "Nº Item:", "id_item", "text", show_links=False, show_focus=False, show_validate=False, show_na=False)
            # Tratamento de Nome Especial
            display_name = self.item_data.get('name', '')
            itype = self.item_data.get('type', '').lower()
            if itype == 'viga_fundo_c':
                if display_name.endswith('-1'):
                    display_name = display_name[:-2] + '.C'
                elif not display_name.endswith('.C'):
                    display_name = display_name + '.C'
            
            self._add_linked_row(h_layout, "Nome:", "name", "text")
            self.fields['name'].setText(display_name)
            
            if 'VIGA' in elem_type:
                 itype = self.item_data.get('type', '').lower()
                 na, nb, nc = self._scan_local_segments()
                 
                 if itype == 'viga_fundo_c':
                     self._add_linked_row(h_layout, "Qtd. Seg. C:", "viga_count_c", "text", show_links=False, show_focus=False, show_validate=True, show_na=False)
                     self.fields['viga_count_c'].setText(str(nc))
                     self.fields['viga_count_c'].setReadOnly(True)
                 else:
                     self._add_linked_row(h_layout, "Qtd. Seg. A:", "viga_count_a", "text", show_links=False, show_focus=False, show_validate=False, show_na=False)
                     self.fields['viga_count_a'].setText(str(na))
                     self.fields['viga_count_a'].setReadOnly(True)
                     
                     self._add_linked_row(h_layout, "Qtd. Seg. B:", "viga_count_b", "text", show_links=False, show_focus=False, show_validate=False, show_na=False)
                     self.fields['viga_count_b'].setText(str(nb))
                     self.fields['viga_count_b'].setReadOnly(True)
                 
                 # Trigger initial style
                 self._update_header_counts()
                 
            else: # Pilar (default)
                self._add_linked_row(h_layout, "Dimensão B×H [dim]:", "dim", "text")
                self._add_linked_row(h_layout, "Segmentos Geometria [pilar_segs]:", "pilar_segs", "text")

                # Formato (Apenas Pilar)
                self.fields['format'] = QComboBox()
                self.fields['format'].addItems(["Retangular", "Circular", "Em L", "Em T", "Em U"])
                self.fields['format'].setCurrentText(self.item_data.get('format', 'Retangular'))
                self.fields['format'].setFixedHeight(24)
                self.fields['format'].setStyleSheet(f"background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_INPUT}; border-radius: 3px; color: {Colors.TEXT_BRIGHT};")
                self.fields['format'].currentTextChanged.connect(lambda txt: self._on_field_changed('format', txt))
                h_layout.addRow("Formato da Seção [format]:", self.fields['format'])

                # Classificação (Apenas Pilar) — [2026-07-13, Fase 3.2] vira
                # campo validável de verdade (_add_linked_row com combo),
                # antes era um QComboBox solto fora do sistema de selos.
                _classif_raw = (
                    self.item_data.get('classification')
                    or (self.item_data.get('fields') or {}).get('Classificação')
                    or 'INDETERMINADO'
                )
                _classif_val = str(_classif_raw).strip().upper() or 'INDETERMINADO'
                _CLASSIF_ITEMS = ["INDETERMINADO", "NASCE", "SEGUE", "MORRE", "PASSA", "CONTINUA"]
                self._add_linked_row(
                    h_layout, "Classificação [classification]:", "classification", "text",
                    is_combo=True, combo_items=_CLASSIF_ITEMS,
                )
                self.fields['classification'].setCurrentText(
                    _classif_val if _classif_val in _CLASSIF_ITEMS else "INDETERMINADO"
                )

            layout.addWidget(header)

            # ── GRUPO: Dimensional / Geometria Global (Pilares) ──────────────────
            if 'PILAR' in elem_type:
                grp_dim = QGroupBox("Dimensional / Geometria Global")
                grp_dim.setStyleSheet(f"QGroupBox {{ font-size: 10px; font-weight: bold; color: {Colors.ACCENT_BLUE}; border: 1px solid {Colors.BORDER_DEFAULT}; margin-top: 4px; padding-top: 8px; }}")
                f_dim = QFormLayout(grp_dim)
                f_dim.setContentsMargins(2, 4, 2, 4)
                f_dim.setSpacing(1)
                self._add_info_row(f_dim, "Altura Total do Pilar cm [altura]:", "altura")
                self._add_info_row(f_dim, "Nível de Chegada cm [nivel_chegada]:", "nivel_chegada")
                self._add_info_row(f_dim, "Nível de Saída cm [nivel_saida]:", "nivel_saida")
                layout.addWidget(grp_dim)

        # Container para conteúdo dinâmico (Abas que mudam com o formato)
        self.dynamic_container = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_container)
        self.dynamic_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.dynamic_container, 1) # Give stretch factor to expand

        # Inicializa conteúdo dinâmico
        self._refresh_dynamic_content()
        
        # Conecta sinal de mudança de formato (se existir)
        if 'format' in self.fields:
            self.fields['format'].currentTextChanged.connect(self._on_format_changed)

        layout.addLayout(self._create_action_buttons())
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # Garante aplicação de estilos de validação após toda UI estar pronta
        self.refresh_validation_styles()
        
        # Conecta os signals para cálculo dinâmico (Grades, Parafusos, Chapas)
        if 'dim' in self.fields:
            self.fields['dim'].textChanged.connect(lambda _: self._recalc_pilar_geometry_if_needed())
        if 'altura' in self.fields:
            self.fields['altura'].textChanged.connect(lambda _: self._recalc_pilar_geometry_if_needed())
            
        # Trigger initial calculation
        self._recalc_pilar_geometry_if_needed()

    def _recalc_pilar_geometry_if_needed(self):
        import re, math
        if 'dim' not in self.fields or 'altura' not in self.fields:
            return
            
        dim_str = self.fields['dim'].text()
        alt_str = self.fields['altura'].text()
        if not dim_str or not alt_str: return
        
        nums = [float(n.replace(',', '.')) for n in re.findall(r'\d+[.,]?\d*', dim_str)]
        if len(nums) < 2: return
        comp = max(nums)
        larg = min(nums)
        
        try:
            alt = float(alt_str.replace(',', '.'))
        except Exception:
            return
            
        # 1. Calc Parafusos
        comp_adj = comp + 24.0
        qtd_par = int(math.ceil(comp_adj / 72.0))
        if qtd_par > 8: qtd_par = 8
        
        if qtd_par == 2:
            val = round(comp_adj / 2.0, 1)
            parafusos = [val, val] + [0]*(8-2)
        elif qtd_par > 2:
            base = int(math.floor(comp_adj / qtd_par))
            resto = int(round(comp_adj - (base * qtd_par)))
            par = [base] * qtd_par
            l, r = 0, qtd_par - 1
            for i in range(resto):
                if i % 2 == 0:
                    par[l] += 1
                    l += 1
                else:
                    par[r] += 1
                    r -= 1
            parafusos = par + [0]*(8-qtd_par)
        else:
            parafusos = [0]*8
            
        for i in range(8):
            fname = f"par_{i+1}_{i+2}"
            if fname in self.fields and not self.fields[fname].hasFocus():
                self.fields[fname].setText(str(float(parafusos[i])))
                self.item_data.setdefault('fields', {})[fname] = float(parafusos[i])
                
        # 2. Calc Grades
        comp_grade = comp + 22.0
        grades, dists = [0]*3, [0]*2
        if comp_grade <= 106:
            grades[0] = comp_grade
        elif comp_grade <= 259:
            tg = min(106, comp_grade/2)
            tg_menor = int(tg/5)*5
            tg_maior = tg_menor + 5
            d_menor = comp_grade - 2*tg_menor
            d_maior = comp_grade - 2*tg_maior
            if tg_maior <= 106 and 1 <= d_maior <= 15:
                t, d = tg_maior, d_maior
            elif 1 <= d_menor <= 15:
                t, d = tg_menor, d_menor
            else:
                d = max(1, min(15, d_menor))
                t = (comp_grade - d)/2
            t = round(t)
            d = comp_grade - 2*t
            if d < 1: d = 1
            elif d > 15: d = 15
            grades[0] = grades[1] = t
            dists[0] = d
        else:
            tg = min(106, comp_grade/3)
            tg_menor = int(tg/5)*5
            tg_maior = tg_menor + 5
            d_menor = (comp_grade - 3*tg_menor)/2
            d_maior = (comp_grade - 3*tg_maior)/2
            if tg_maior <= 106 and 1 <= d_maior <= 15:
                t, d = tg_maior, d_maior
            elif 1 <= d_menor <= 15:
                t, d = tg_menor, d_menor
            else:
                d = max(1, min(15, d_menor))
                t = (comp_grade - 2*d)/3
            t = round(t)
            d = (comp_grade - 3*t)/2
            if d < 1: d = 1
            elif d > 15: d = 15
            grades = [t, t, t]
            dists = [d, d]
            
        for i, val in enumerate(grades):
            f = f"grade_{i+1}"
            if f in self.fields and not self.fields[f].hasFocus():
                self.fields[f].setText(str(float(val)))
                self.item_data.setdefault('fields', {})[f] = float(val)
                
        for i, val in enumerate(dists):
            f = f"distancia_{i+1}"
            if f in self.fields and not self.fields[f].hasFocus():
                self.fields[f].setText(str(float(val)))
                self.item_data.setdefault('fields', {})[f] = float(val)
                
        # 3. Calc Chapa/Forma
        shape = self.item_data.get('format', 'Retangular')
        sides = ['A', 'B', 'C', 'D']
        if shape == "Circular": sides = ["Superior", "Inferior"]
        elif shape == "Em L": sides = ['A', 'B', 'C', 'D', 'E', 'F']
        elif shape in ["Em T", "Em U"]: sides = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        
        for side in sides:
            h1 = 2.0
            laje_h = 0.0
            if f"p_s{side}_l1_h" in self.fields:
                try: laje_h = float(self.fields[f"p_s{side}_l1_h"].text().replace(',', '.'))
                except: pass
            
            alt_util = alt - laje_h - h1
            if alt_util > 244:
                h2 = 244.0
                h3 = max(0.0, alt_util - h2)
            else:
                h2 = max(0.0, alt_util)
                h3 = 0.0
                
            for h_idx, h_val in enumerate([h1, h2, h3, 0.0, 0.0]):
                f = f"p_s{side}_c_h{h_idx+1}"
                if f in self.fields and not self.fields[f].hasFocus():
                    self.fields[f].setText(str(float(h_val)))
                    self.item_data.setdefault('fields', {})[f] = float(h_val)
                    
            larg_val = comp if side in ['A', 'B'] else larg
            for larg_idx, l_val in enumerate([larg_val, 0.0, 0.0]):
                f = f"p_s{side}_c_larg{larg_idx+1}"
                if f in self.fields and not self.fields[f].hasFocus():
                    self.fields[f].setText(str(float(l_val)))
                    self.item_data.setdefault('fields', {})[f] = float(l_val)

    # ... (keeps existing helper methods until _setup_laje_complex_view)

    def _build_ficha_granular_tab(self) -> QWidget:
        from PySide6.QtGui import QColor, QFont, QBrush
        
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(10, 10, 10, 10)
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Propriedade", "Valor Extraído"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(f"""
            QTableWidget {{
                background: transparent; 
                color: {Colors.TEXT_PRIMARY};
                font-size: 11px; 
                border: none;
            }}
            QTableWidget::item {{
                border-bottom: 1px solid rgba(255, 255, 255, 10);
                padding: 6px 10px;
            }}
            QTableWidget::item:alternate {{
                background: rgba(255, 255, 255, 3);
            }}
            QTableWidget::item:hover {{
                background: rgba(180, 80, 200, 15);
            }}
            QHeaderView::section {{
                background: {Colors.BG_CARD}; 
                color: {Colors.ACCENT_PRIMARY};
                border: none; 
                border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
                font-size: 11px; 
                font-weight: bold;
                padding: 8px 10px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
        """)
        
        rows = []
        rows.append(("ID Item", str(self.item_data.get("id_item", ""))))
        rows.append(("Nome", str(self.item_data.get("name", ""))))
        rows.append(("Tipo", str(self.item_data.get("type", ""))))
        
        fields = self.item_data.get("fields", {})
        for k, v in fields.items():
            if k not in ["name", "id_item", "type"]:
                rows.append((k, str(v)))
                
        metrics = self.item_data.get("metrics", {})
        if metrics:
            rows.append(("---", ""))
            rows.append(("MÉTRICAS DA GEOMETRIA", "VALOR"))
            for k, v in metrics.items():
                rows.append((k, str(v)))
                
        table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            item_k = QTableWidgetItem(k)
            item_v = QTableWidgetItem(v)
            if k == "---":
                item_k.setText("")
                item_v.setText("")
                item_k.setBackground(QBrush(QColor(Colors.BORDER_DEFAULT)))
                item_v.setBackground(QBrush(QColor(Colors.BORDER_DEFAULT)))
            elif k == "MÉTRICAS DA GEOMETRIA":
                item_k.setForeground(QBrush(QColor(Colors.ACCENT_PURPLE)))
                item_v.setForeground(QBrush(QColor(Colors.ACCENT_PURPLE)))
                font = QFont()
                font.setBold(True)
                item_k.setFont(font)
                item_v.setFont(font)
                
            table.setItem(i, 0, item_k)
            table.setItem(i, 1, item_v)
            
        table.resizeColumnsToContents()
        if table.columnWidth(0) < 180:
            table.setColumnWidth(0, 180)
            
        lay.addWidget(table)
        return container

    def _setup_laje_complex_view(self, layout):
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabBar::tab { padding: 8px 20px; font-weight: bold; }
            QTabWidget::pane { border: 1px solid {Colors.BORDER_INPUT}; }
        """)
        
        tab = QWidget()
        l = QVBoxLayout(tab)
        l.setSpacing(10)
        
        # --- DADOS GERAIS (Exclusivo para Laje aqui dentro) ---
        grp = QGroupBox("DADOS GERAIS - LAJE")
        grp.setStyleSheet(f"QGroupBox {{ font-size: 11px; font-weight: bold; border: 1px solid {Colors.BORDER_INPUT}; margin-top: 5px; padding-top: 10px; color: {Colors.ACCENT_MINT}; }}")
        form = QFormLayout(grp)
        form.setSpacing(5)
        
        # Campos principais movidos para cá
        self._add_linked_row(
            form, "Nº Item [id_item]:", "id_item", "text",
            show_links=False, show_focus=False, show_validate=False, show_na=False
        )
        self._add_linked_row(form, "Nome [name]:", "name", "text")
        self._add_linked_row(form, "Dimensão C×L cm [laje_dim]:", "laje_dim", "text")
        self._add_linked_row(form, "Visao de Corte [laje_visao_corte]:", "laje_visao_corte", "poly", hide_input=True)
        self._add_linked_row(form, "Níveis / Lajes Vizinhas [laje_vizinhas_niveis]:", "laje_vizinhas_niveis", "text", hide_input=True)
        self._add_linked_row(form, "Pilares de Apoio da Laje [laje_pilares_apoio]:", "laje_pilares_apoio", "poly", hide_input=True)
        self._add_linked_row(form, "Nível / Pavimento ex: +2.80 [laje_nivel]:", "laje_nivel", "text")
        nivel_box = self._build_nivel_detail_box()
        if nivel_box:
            form.addRow("", nivel_box)
        self._add_linked_row(form, "Segmentos da Área (Geometria) [laje_outline_segs]:", "laje_outline_segs", "poly", hide_input=True)
        self._add_linked_row(form, "Contorno da Ilha / Obstáculo [laje_islands]:", "laje_islands", "poly", hide_input=True)

        if "laje_dim" in self.fields:
             self.fields["laje_dim"].textChanged.connect(lambda t: self._clean_laje_dim_input(t))

        # ── GRUPO: Cálculo / Métricas da Laje ────────────────────────────────
        grp_calc = QGroupBox("Cálculo / Métricas da Laje")
        grp_calc.setStyleSheet(f"QGroupBox {{ font-size: 10px; font-weight: bold; color: {Colors.ACCENT_MINT}; border: 1px solid {Colors.BORDER_DEFAULT}; margin-top: 5px; padding-top: 8px; }}")
        f_calc = QFormLayout(grp_calc)
        f_calc.setContentsMargins(2, 4, 2, 4)
        f_calc.setSpacing(1)
        readonly_row = {
            "show_links": False,
            "show_focus": False,
            "show_validate": False,
            "show_na": False,
        }
        self._add_linked_row(f_calc, "Área Total m² (calculada) [area]:", "area", "text", **readonly_row)
        self._add_linked_row(f_calc, "Modo de Cálculo 0=normal 1=espelho [modo_selecionado]:", "modo_selecionado", "text", **readonly_row)
        self._add_linked_row(f_calc, "Qtd. Linhas Verticais de Pontalete [laje_linhas_v_count]:", "laje_linhas_v_count", "text", **readonly_row)
        self._add_linked_row(f_calc, "Qtd. Linhas Horizontais de Pontalete [laje_linhas_h_count]:", "laje_linhas_h_count", "text", **readonly_row)
        self._add_linked_row(f_calc, "Uniões nos Bordos (sim/não) [unioes_nos_bordes]:", "unioes_nos_bordes", "text", **readonly_row)
        self._add_linked_row(f_calc, "Observações / Notas [observacoes]:", "observacoes", "text", **readonly_row)
        l.addWidget(grp_calc)

        # ── GRUPO: Pontaletes / Escoras ───────────────────────────────────────
        grp_pont = QGroupBox("Pontaletes / Escoras")
        grp_pont.setStyleSheet(f"QGroupBox {{ font-size: 10px; font-weight: bold; color: {Colors.ACCENT_WARNING_ALT}; border: 1px solid {Colors.BORDER_DEFAULT}; margin-top: 5px; padding-top: 8px; }}")
        f_pont = QFormLayout(grp_pont)
        f_pont.setContentsMargins(2, 4, 2, 4)
        f_pont.setSpacing(1)
        self._add_linked_row(f_pont, "Total de Pontaletes (inteiros) [pont_total]:", "pont_total", "text")
        self._add_linked_row(f_pont, "Meio Pontalete (complementos) [pont_meio]:", "pont_meio", "text")
        self._add_linked_row(f_pont, "Linhas de Pontaletes (no comprimento) [pont_linhas]:", "pont_linhas", "text")
        self._add_linked_row(f_pont, "Colunas de Pontaletes (na largura) [pont_colunas]:", "pont_colunas", "text")
        self._add_linked_row(f_pont, "Tipo do Pontalete ex: PONTALETE [pont_tipo]:", "pont_tipo", "text")
        self._add_linked_row(f_pont, "Altura do Pavimento cm [pont_altura_pav]:", "pont_altura_pav", "text")
        self._add_linked_row(f_pont, "Comprimento da Laje cm (pontalete) [pont_comp_cm]:", "pont_comp_cm", "text")
        self._add_linked_row(f_pont, "Largura da Laje cm (pontalete) [pont_larg_cm]:", "pont_larg_cm", "text")
        grp_pont.setVisible(False)
        l.addWidget(grp_pont)
        
        l.addWidget(grp)
        l.addStretch() # Empurrar tudo para cima
        
        tabs.addTab(tab, "Laje")

        # ── Aba Ficha Granular [F5] ──
        ficha_tab = self._build_ficha_granular_tab()
        tabs.addTab(ficha_tab, "📋 Ficha Granular [F5]")

        # ── Aba Comparar (CAD-10.4) ───────────────────────────────────────
        if _COMPARISON_AVAILABLE:
            cmp_tab = ComparisonTab(
                self.item_data, self.obra_path, self.db, self.project_id, parent=self
            )
            cmp_tab.field_accepted.connect(lambda fid: self._refresh_dynamic_content())
            tabs.addTab(cmp_tab, "Comparar")

        layout.addWidget(tabs)

    def _setup_pilar_complex_view(self, layout):
        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { padding: 5px; font-size: 10px; }")
        shape = self.fields['format'].currentText()
        
        sides = ['A', 'B', 'C', 'D']
        if shape == "Circular": sides = ["Superior", "Inferior"]
        elif shape == "Em L": sides = ['A', 'B', 'C', 'D', 'E', 'F']
        elif shape in ["Em T", "Em U"]: sides = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

        for side in sides:
            tab = QWidget()
            tab_l = QVBoxLayout(tab)
            tab_l.setContentsMargins(5, 5, 5, 5)
            tab_l.setSpacing(2)


            # Lajes - Layout Vertical (Laje 2 abaixo da Laje 1) para compactar largura
            for i in [1, 2]:
                grp = QGroupBox(f"Laje {i}")
                grp.setStyleSheet(f"QGroupBox {{ font-size: 10px; font-weight: bold; border: 1px solid {Colors.BORDER_DEFAULT}; margin-top: 5px; padding-top: 5px; }}")
                f = QFormLayout(grp)
                f.setSpacing(1)
                f.setContentsMargins(2, 5, 2, 2)
                self._add_linked_row(f, "Nome da Laje:", f'p_s{side}_l{i}_n', "text")
                # Auto-preenchimento de H e Nível ao vincular o nome da laje
                _n_fid = f'p_s{side}_l{i}_n'
                _n_w = self.fields.get(_n_fid)
                if _n_w and hasattr(_n_w, 'textChanged'):
                    _n_w.textChanged.connect(
                        lambda txt, _s=side, _li=i: self._on_panel_slab_name_changed(_s, _li, txt)
                    )
                self._add_linked_row(f, "Altura / Espessura (H):", f'p_s{side}_l{i}_h', "text")
                self._add_linked_row(f, "Nível da Laje:", f'p_s{side}_l{i}_v', "text")

                # Ajuste Laje 2: Pos. -> Laje central e opções Esquerda/Direita
                if i == 2:
                    self._add_info_row(f, "Posição da Laje C:", f'p_s{side}_l{i}_p', is_combo=True, combo_items=["Esquerda", "Direita"])
                else:
                    self._add_info_row(f, "Posição da Laje:", f'p_s{side}_l{i}_p', is_combo=True, combo_items=["Topo", "Centro", "Fundo"])

                self._add_info_row(f, "Distância ao Topo:", f'p_s{side}_l{i}_dist_t')
                self._add_info_row(f, "Distância Parede Esquerda:", f'p_s{side}_l{i}_dist_esq')
                self._add_info_row(f, "Distância Parede Direita:", f'p_s{side}_l{i}_dist_dir')
                
                # Inicialização de valores padrão se vazio
                for fd in ['dist_esq', 'dist_dir']:
                    fw = self.fields.get(f'p_s{side}_l{i}_{fd}')
                    if fw and fw.text() == "":
                        fw.setText("0")

                # Auto-fill inicial: H e Nível se nome da laje já está preenchido
                # (usa singleShot 0 para rodar após a UI estar completamente construída)
                _init_n = (self.fields[f'p_s{side}_l{i}_n'].text().strip()
                           if f'p_s{side}_l{i}_n' in self.fields else '')
                if _init_n:
                    from PySide6.QtCore import QTimer as _QT
                    _QT.singleShot(0, lambda _s=side, _li=i, _nm=_init_n:
                                   self._on_panel_slab_name_changed(_s, _li, _nm))

                tab_l.addWidget(grp)

            # ── Vigas que passam: 2 slots por face (esquina esq / dir) ──
            # Contorno esq/dir REMOVIDO — não é usado no fluxo N1/N3.
            # Cantos canônicos (INTERPRETACAO-PILARES-ABCD + aberturas NOVA):
            #   A: AC|AD  B: BD|BC  C: CA|CB  D: DA|DB
            _FACE_PASS_CORNERS = {
                'A': ('AC', 'AD'),
                'B': ('BD', 'BC'),
                'C': ('CA', 'CB'),
                'D': ('DA', 'DB'),
            }
            _c_esq, _c_dir = _FACE_PASS_CORNERS.get(side, ('ESQ', 'DIR'))
            for _slot, _corner, _title_side in (
                ('passa_esq', _c_esq, 'Esquerda'),
                ('passa_dir', _c_dir, 'Direita'),
            ):
                v_pass_grp = QGroupBox(
                    f"Vigas que Passam — Esquina {_corner} "
                    f"({_title_side} · Lado {side})"
                )
                v_pass_grp.setStyleSheet(
                    f"QGroupBox {{ font-size: 10px; font-weight: bold; "
                    f"color: {Colors.ACCENT_MINT}; border: 1px solid "
                    f"{Colors.BORDER_DEFAULT}; margin-top: 10px; padding-top: 5px; }}"
                )
                f_vp = QFormLayout(v_pass_grp)
                f_vp.setSpacing(1)
                f_vp.setContentsMargins(2, 5, 2, 2)
                id_vp = f'p_s{side}_v_{_slot}'
                self._add_linked_row(f_vp, "Nome da Viga:", f'{id_vp}_n', "text")
                self._add_linked_row(f_vp, "Dimensão (B x H):", f'{id_vp}_d', "text")
                self._add_linked_row(f_vp, "Nível da Viga:", f'{id_vp}_v', "text")
                self._add_info_row(f_vp, "Distância ao Topo:", f'{id_vp}_dist_t')
                self._add_info_row(f_vp, "Distância Parede Esquerda:", f'{id_vp}_dist_esq')
                self._add_info_row(f_vp, "Distância Parede Direita:", f'{id_vp}_dist_dir')
                # Legado v_int → migra para passa_esq se o novo slot estiver vazio
                if _slot == 'passa_esq':
                    self._migrate_legacy_v_int_to_passa_esq(side)
                tab_l.addWidget(v_pass_grp)

            # Pre-fill N/A: Laje 2 e Vigas Passam vazios → N/A (após UI construída)
            from PySide6.QtCore import QTimer as _QTna
            _QTna.singleShot(10, lambda _s=side: self._init_side_na_defaults(_s))

            # Chegadas: até 3 vigas que param / chegam no pilar por face
            beam_categories = [
                ("Viga de Chegada 1", "ch1", True),
                ("Viga de Chegada 2", "ch2", True),
                ("Viga de Chegada 3", "ch3", True),
            ]
            
            for cat_name, cat_id, is_arrival in beam_categories:
                v_grp = QGroupBox(cat_name)
                v_grp.setStyleSheet(f"QGroupBox {{ font-size: 10px; color: {Colors.ACCENT_BLUE}; border: 1px solid {Colors.BORDER_DEFAULT}; margin-top: 10px; padding-top: 5px; }}")
                vf = QFormLayout(v_grp)
                vf.setSpacing(1)
                vf.setContentsMargins(2, 5, 2, 2)
                
                id_pref = f'p_s{side}_v_{cat_id}'
                self._add_linked_row(vf, "Nome da Viga:", f'{id_pref}_n', "text")
                self._add_linked_row(vf, "Dimensão (B x H):", f'{id_pref}_d', "text")
                self._add_linked_row(vf, "Segmentos Geometria:", f'{id_pref}_segs', "poly", hide_input=True)
                
                if is_arrival:
                    self._add_info_row(vf, "Distância Parede Esquerda:", f'{id_pref}_dist_esq')
                    self._add_info_row(vf, "Distância Parede Direita:", f'{id_pref}_dist_dir')
                
                # Distância Topo sem link, auto-calculado
                self._add_info_row(vf, "Distância Topo (Auto):", f'{id_pref}_prof')
                
                # Auto-update logic
                dim_widget = self.fields[f'{id_pref}_d']
                prof_widget = self.fields[f'{id_pref}_prof']
                dim_widget.textChanged.connect(lambda t, w=prof_widget: self._update_depth_from_dim(t, w))
                
                self._add_linked_row(vf, "Nível Viga:", f'{id_pref}_diff_v', "text")
                tab_l.addWidget(v_grp)
                
            tabs.addTab(tab, f"Lado {side}")

        # ── Aba Ficha Granular [F5] ──
        ficha_tab = self._build_ficha_granular_tab()
        tabs.addTab(ficha_tab, "📋 Ficha Granular [F5]")

        # ── Aba Comparar (CAD-10.4) ───────────────────────────────────────
        if _COMPARISON_AVAILABLE:
            cmp_tab = ComparisonTab(
                self.item_data, self.obra_path, self.db, self.project_id, parent=self
            )
            cmp_tab.field_accepted.connect(lambda fid: self._refresh_dynamic_content())
            tabs.addTab(cmp_tab, "Comparar")

        layout.addWidget(tabs)

    def _update_depth_from_dim(self, text, target_widget):
        """Calcula profundidade (maior valor) baseado no texto de dimensão (ex: '15x40')"""
        import re
        try:
            # Busca números, suportando decimais com ponto ou vírgula
            nums = [float(n.replace(',', '.')) for n in re.findall(r'\d+[.,]?\d*', text)]
            if len(nums) >= 2:
                # Se tiver pelo menos 2 números (ex: 15 e 40), pega o maior
                max_val = max(nums)
                # Formata removendo .0 se for inteiro
                txt_val = f"{int(max_val)}" if max_val.is_integer() else f"{max_val}"
                target_widget.setText(txt_val)
        except Exception:
            pass

    def _setup_viga_complex_view(self, layout):
        """Implementa detalhamento rigoroso de Lado A, Lado B e Fundo"""
        tabs = QTabWidget()
        itype = self.item_data.get('type', '').lower()
        if itype == 'viga_lateral_a':
            sides_config = [('A', 'Lado A', False)]
        elif itype == 'viga_lateral_b':
            sides_config = [('B', 'Lado B', False)]
        elif itype == 'viga_fundo_c':
            sides_config = [('Fundo', 'Fundo Lado C', True)]
        elif itype == 'viga_lateral':
            sides_config = [('A', 'Lado A', False), ('B', 'Lado B', False)]
        elif itype == 'viga_fundo':
            sides_config = [('Fundo', 'Fundo', True)]
        else:
            sides_config = [('A', 'Lado A', False), ('B', 'Lado B', False), ('Fundo', 'Fundo Lado C', True)]
        
        for side, label, is_bottom in sides_config:
            tab = QWidget()
            tab_l = QVBoxLayout(tab)
            tab_l.setSpacing(15)
            tab_l.setContentsMargins(5, 5, 5, 5)
            
            prefix = f"viga_{side.lower()}"

            if not is_bottom:
                # Container de Segmentos Rica
                segs_container = QWidget()
                segs_layout = QVBoxLayout(segs_container)
                segs_layout.setContentsMargins(0,0,0,0)
                segs_layout.setSpacing(15)
                tab_l.addWidget(segs_container)
                
                # A sublista Para/Passa usa somente os segmentos cujo vínculo
                # específico continua ativo. Chaves vazias ignoradas na
                # pré-ficha não geram cartões fantasmas.
                existing_indices = self._existing_beam_segment_indices(
                    prefix, is_fundo=False
                )
                
                for i in sorted(list(existing_indices)):
                    self._add_rich_segment_pack(segs_layout, prefix, i)
                    
                # Botão Add
                btn_add = QPushButton(" + Adicionar Segmento Completo")
                btn_add.setFixedHeight(30)
                btn_add.setStyleSheet(f"background: rgba(0, 68, 68, 1); color: {Colors.ACCENT_MINT}; border: 1px dashed {Colors.ACCENT_MINT}; font-weight: bold; font-size: 11px;")
                btn_add.setCursor(Qt.PointingHandCursor)
                btn_add.clicked.connect(lambda checked=False, l=segs_layout, p=prefix: self._add_rich_segment_pack(l, p))
                tab_l.addWidget(btn_add)

            else:
                # Layout Dinâmico para Fundo (Segmentos Fundo)
                segs_container = QWidget()
                segs_layout = QVBoxLayout(segs_container)
                segs_layout.setContentsMargins(0,0,0,0)
                segs_layout.setSpacing(15)
                tab_l.addWidget(segs_container)
                
                # Fundos ignorados permanecem com a chave para rastreabilidade,
                # mas contour vazio não deve criar um cartão de segmento.
                existing_indices = self._existing_beam_segment_indices(
                    prefix, is_fundo=True
                )
                
                for i in sorted(list(existing_indices)):
                    self._add_fundo_segment_pack(segs_layout, prefix, i)
                
                # Botão Adicionar Segmento Fundo
                btn_add = QPushButton(" + Adicionar Segmento Fundo")
                btn_add.setFixedHeight(30)
                btn_add.setStyleSheet("background: rgba(68, 0, 68, 1); color: rgba(255, 136, 255, 1); border: 1px dashed rgba(255, 136, 255, 1); font-weight: bold; font-size: 11px;")
                btn_add.setCursor(Qt.PointingHandCursor)
                btn_add.clicked.connect(lambda checked=False, l=segs_layout, p=prefix: self._add_fundo_segment_pack(l, p))
                tab_l.addWidget(btn_add)
            
            tab_l.addStretch()
            tabs.addTab(tab, label)

        # ── Aba Ficha Granular [F5] ──
        ficha_tab = self._build_ficha_granular_tab()
        tabs.addTab(ficha_tab, "📋 Ficha Granular [F5]")

        # ── Aba Comparar (CAD-10.4) ──
        if _COMPARISON_AVAILABLE:
            cmp_tab = ComparisonTab(
                self.item_data, self.obra_path, self.db, self.project_id, parent=self
            )
            cmp_tab.field_accepted.connect(lambda fid: self._refresh_dynamic_content())
            tabs.addTab(cmp_tab, "Comparar")

        layout.addWidget(tabs)

    def _existing_beam_segment_indices(self, prefix: str, is_fundo: bool) -> set[int]:
        """Lista somente segmentos ativos no contexto FV ou LV Para/Passa atual."""
        links = self.item_data.get('links') or {}
        if not isinstance(links, dict):
            links = {}

        active: set[int] = set()
        source_seen = False
        if is_fundo:
            pattern = re.compile(rf'^{re.escape(prefix)}_seg_(\d+)_area_segs$')
            slot_name = 'contour'
        else:
            tipo_comp = str(self.item_data.get('_tipo_comp') or 'passa').lower()
            suffix = 'comprimento_total' if tipo_comp == 'para' else 'comp_total_passa'
            pattern = re.compile(rf'^{re.escape(prefix)}_seg_(\d+)_{suffix}$')
            slot_name = 'seg_side_a' if prefix == 'viga_a' else 'seg_side_b'

        for field_id, slots in links.items():
            match = pattern.match(str(field_id))
            if not match:
                continue
            source_seen = True
            values = slots.get(slot_name) if isinstance(slots, dict) else []
            if any(
                isinstance(link, dict) and bool(link.get('points'))
                for link in (values or [])
            ):
                active.add(int(match.group(1)))

        # Quando o contrato novo existe, inclusive vazio por decisão de ignorar,
        # ele é a fonte autoritativa. O botão "Adicionar" continua disponível.
        if source_seen:
            return active

        # Compatibilidade para fichas antigas que ainda não possuem as chaves
        # geométricas novas, mas têm campos/markers de segmentos.
        legacy: set[int] = set()
        all_keys = list(self.item_data)
        fields = self.item_data.get('fields')
        if isinstance(fields, dict):
            all_keys.extend(fields)
        for key in all_keys:
            match = re.match(rf'^{re.escape(prefix)}_seg_(\d+)', str(key))
            if not match:
                continue
            index = int(match.group(1))
            marker = self.item_data.get(f'{prefix}_seg_{index}_exists')
            if marker is not False:
                legacy.add(index)
        return legacy or {1}

    def _add_rich_segment_pack(self, layout, prefix, idx_override=None):
        """Cria um Box Completo de Segmento com todos os campos de engenharia"""
        
        # Determinar índice
        if idx_override:
            idx = idx_override
        else:
            # Contagem baseada nos widgets visuais para sequencia logica
            idx = layout.count() + 1
            
            # Garantir existência no item_data para detecção externa
            marker_key = f"{prefix}_seg_{idx}_exists"
            if marker_key not in self.item_data:
                self.item_data[marker_key] = True
                # Emitir sinal para atualizar UI principal imediatamente
                self.data_changed.emit(self.item_data)
            
        seg_uid = f"{prefix}_seg_{idx}"
        
        # Grupo Principal do Segmento (Retratil)
        pack = QWidget()
        pack_layout = QVBoxLayout(pack)
        pack_layout.setContentsMargins(0, 5, 0, 5)
        pack_layout.setSpacing(0)
        
        btn_toggle = QPushButton(f"▼ Segmento {idx}")
        btn_toggle.setStyleSheet(f"text-align: left; font-size: 13px; font-weight: bold; color: {Colors.ACCENT_MINT}; background: {Colors.BG_CARD}; padding: 8px; border: 1px solid {Colors.BORDER_INPUT}; border-radius: 4px;")
        btn_toggle.setCursor(Qt.PointingHandCursor)

        header_row = QHBoxLayout()
        header_row.setSpacing(4)
        header_row.addWidget(btn_toggle, 1)
        header_row.addWidget(self._build_segment_validate_button(prefix, idx))

        content_frame = QFrame()
        content_frame.setStyleSheet(f"border: 1px solid {Colors.BORDER_INPUT}; border-top: none; background: {Colors.BG_PANEL};")

        pack_layout.addLayout(header_row)
        pack_layout.addWidget(content_frame)
        
        btn_toggle.clicked.connect(lambda checked=False, cf=content_frame, btn=btn_toggle, i=idx: (
            cf.setVisible(not cf.isVisible()),
            btn.setText(f"▼ Segmento {i}" if cf.isVisible() else f"▶ Segmento {i}")
        ))
        
        # Layout principal do pack
        main_v = QVBoxLayout(content_frame)
        main_v.setSpacing(10)
        
        # 1. Campos de Geometria (FormLayout)
        form_w = QWidget()
        form = QFormLayout(form_w)
        form.setSpacing(4)
        form.setContentsMargins(2,2,2,2)
        
        # Determinar lado (A ou B) baseado no prefixo
        # prefix pode ser "viga_a", "viga_b" ou "viga_fundo"
        # Este método só é chamado para lados A e B (não para fundo)
        if prefix == "viga_a":
            side_label = "A"
        elif prefix == "viga_b":
            side_label = "B"
        else:
            side_label = ""  # Fallback (não deveria acontecer neste método)
        
        # Ordem de curadoria SA (pedido dono 2026-07):
        # 1. Linha Comprimento
        # 2. Ajuste Comprimento
        # 3. Dimensão B×H  (logo abaixo do ajuste)
        # 4. Visão de Corte (acima do Nível)
        # 5. Apoios
        # 6. Nível da Viga
        # 7. Lajes 1/2/3
        _tipo_comp = self.item_data.get('_tipo_comp', 'passa')
        if _tipo_comp == 'para':
            linha_comp_key = f'{seg_uid}_comprimento_total'
        else:
            linha_comp_key = f'{seg_uid}_comp_total_passa'
        self._add_linked_row(form, "Linha Comprimento:", linha_comp_key, "poly")

        self._add_linked_row(form, "Ajuste Comprimento:", f'{seg_uid}_ajuste_comprimento', "text",
                             show_links=False, show_focus=False, show_validate=False, show_na=False)

        self._add_linked_row(form, "Dimensão da Viga (B x H):", f'{seg_uid}_dim', "text")

        self._add_linked_row(form, "Visão de Corte (Seção Transversal):", f'{seg_uid}_visao_corte', "group", hide_input=True)

        self._add_linked_row(form, "Apoio Inicial (Viga/Pilar):", f'{seg_uid}_ini_name', "text")
        self._add_linked_row(form, "Apoio Final (Viga/Pilar):", f'{seg_uid}_end_name', "text")

        # Nível único da viga (interpretação: laje mais alta deste lado / oposto)
        self._add_linked_row(
            form,
            "Nível da Viga:",
            f'{seg_uid}_nivel_viga',
            "text",
        )
        _nivel_hint = QLabel(
            "Interpretação: use o nível da laje mais alta em contato com esta face "
            "(ou a do lado oposto quando for a referência de cota do desenho)."
        )
        _nivel_hint.setWordWrap(True)
        _nivel_hint.setStyleSheet(
            f"font-size: 9px; color: {Colors.TEXT_DIM}; font-style: italic; padding: 0 2px 4px 2px;"
        )
        form.addRow("", _nivel_hint)

        # Lajes 1/2/3 — multi-vínculo com ficha por laje
        self._migrate_legacy_lv_lajes(seg_uid)
        self._add_linked_row(
            form,
            "Lajes (1 / 2 / 3):",
            f'{seg_uid}_lajes',
            "text",
            hide_input=True,
        )
        _lajes_hint = QLabel(
            "Até 3 lajes por segmento. Em cada vínculo: nível, espessura e distâncias "
            "às pontas esquerda/direita do painel (degraus e posição X/Y na lateral)."
        )
        _lajes_hint.setWordWrap(True)
        _lajes_hint.setStyleSheet(
            f"font-size: 9px; color: {Colors.TEXT_DIM}; font-style: italic; padding: 0 2px 4px 2px;"
        )
        form.addRow("", _lajes_hint)

        # NOTA: Modo Painel H1/H2, Continuidade, Detalhamento de Sarrafos e
        # Alturas H1/H2 saíram do SA — ficam na ficha N3 do Comparison Engine
        # (painel superior ao item, junto ao Modo visual). Chaves legadas no
        # item_data continuam legíveis para não quebrar fichas já preenchidas.

        # 1. Campos de Engenharia (FormLayout)
        main_v.addWidget(form_w)
        
        # Aberturas: pilares sarrafeados que atravessam + pontas de viga que passam por baixo
        self._add_pillar_openings_table(main_v, f'{seg_uid}_abert_pilar_esq', f'{seg_uid}_abert_pilar_dir')
        self._add_beam_openings_table(main_v, f'{seg_uid}_abert_viga_top_esq', f'{seg_uid}_abert_viga_top_dir', 
                                      f'{seg_uid}_abert_viga_fun_esq', f'{seg_uid}_abert_viga_fun_dir')
        
        # Botão Remover (se não for o segmento 1, ou permitir remover todos?)
        # Geralmente segmento 1 é obrigatório, mas vamos permitir flexibilidade
        if idx > 1:
            btn_rem = QPushButton("Remover Este Segmento")
            btn_rem.setStyleSheet(f"color: {Colors.ACCENT_DANGER}; background: transparent; border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 4px; padding: 4px;")
            btn_rem.setCursor(Qt.PointingHandCursor)
            btn_rem.clicked.connect(lambda: self._remove_segment(pack, layout, prefix, idx))
            main_v.addWidget(btn_rem)
            
        layout.addWidget(pack)
    
    def update_all_tipo_comp_buttons(self, tipo: str):
        """Atualiza o tipo para/passa de contexto do card (substituiu os radio buttons removidos)."""
        self.item_data['_tipo_comp'] = tipo

    def _migrate_legacy_lv_lajes(self, seg_uid: str) -> None:
        """Converte laje_sup/cen/inf legados em vínculos do campo unificado `_lajes`.

        Não sobrescreve se `_lajes` já tiver vínculos. Cada laje legada vira um
        link de texto com ficha mínima (nível/espessura vazios para curadoria).
        """
        import uuid as _uuid
        field_id = f'{seg_uid}_lajes'
        links = self.item_data.setdefault('links', {})
        existing = links.get(field_id)
        if isinstance(existing, dict):
            for slot_links in existing.values():
                if isinstance(slot_links, list) and slot_links:
                    return  # já migrado / preenchido
        elif isinstance(existing, list) and existing:
            return

        legacy_keys = (
            f'{seg_uid}_laje_sup',
            f'{seg_uid}_laje_cen',
            f'{seg_uid}_laje_inf',
        )
        migrated = []
        for key in legacy_keys:
            raw = self.item_data.get(key)
            if raw is None:
                fields = self.item_data.get('fields') or {}
                raw = fields.get(key) if isinstance(fields, dict) else None
            name = str(raw or '').strip()
            if not name or name.upper() in ('N/A', 'N.A.', 'NULO', 'NONE', '—', '0', '-'):
                continue
            migrated.append({
                'id': str(_uuid.uuid4()),
                'type': 'text',
                'text': name,
                'role': 'Laje legada',
                'ficha': {
                    'nivel': '',
                    'espessura': '',
                    'dist_esq': '',
                    'dist_dir': '',
                },
                'ficha_links': {},
            })
            if len(migrated) >= 3:
                break

        if not migrated:
            return
        links[field_id] = {'laje': migrated}

    def _add_fundo_segment_pack(self, layout, prefix, idx_override=None):
        """Cria um Box Completo de Segmento de Fundo"""
        
        # Determinar índice
        if idx_override:
            idx = idx_override
        else:
            idx = layout.count() + 1
            
            # Garantir existência no item_data para detecção externa
            marker_key = f"{prefix}_seg_{idx}_exists"
            if marker_key not in self.item_data:
                self.item_data[marker_key] = True
                self.data_changed.emit(self.item_data)

        seg_uid = f"{prefix}_seg_{idx}"
        
        # Grupo Principal do Segmento (Retratil)
        pack = QWidget()
        pack_layout = QVBoxLayout(pack)
        pack_layout.setContentsMargins(0, 5, 0, 5)
        pack_layout.setSpacing(0)
        
        btn_toggle = QPushButton(f"▼ Segmento Fundo {idx}")
        btn_toggle.setStyleSheet(f"text-align: left; font-size: 13px; font-weight: bold; color: rgba(170, 136, 255, 1); background: {Colors.BG_CARD}; padding: 8px; border: 1px solid {Colors.BORDER_INPUT}; border-radius: 4px;")
        btn_toggle.setCursor(Qt.PointingHandCursor)

        header_row = QHBoxLayout()
        header_row.setSpacing(4)
        header_row.addWidget(btn_toggle, 1)
        header_row.addWidget(self._build_segment_validate_button(prefix, idx))

        content_frame = QFrame()
        content_frame.setStyleSheet(f"border: 1px solid {Colors.BORDER_INPUT}; border-top: none; background: {Colors.BG_PANEL};")

        pack_layout.addLayout(header_row)
        pack_layout.addWidget(content_frame)
        
        btn_toggle.clicked.connect(lambda checked=False, cf=content_frame, btn=btn_toggle, i=idx: (
            cf.setVisible(not cf.isVisible()),
            btn.setText(f"▼ Segmento Fundo {i}" if cf.isVisible() else f"▶ Segmento Fundo {i}")
        ))
        
        # Layout principal do pack
        main_v = QVBoxLayout(content_frame)
        main_v.setSpacing(10)
        
        # 1. Campos de Engenharia (FormLayout)
        form_w = QWidget()
        form = QFormLayout(form_w)
        form.setSpacing(4)
        form.setContentsMargins(2,2,2,2)
        
        # Campos Solicitados
        self._add_linked_row(form, "Segmentos de Área (Geometria):", f'{seg_uid}_area_segs', "poly", hide_input=True)
        
        # Dimensão (Movido dos Dados Gerais para cá)
        self._add_linked_row(form, "Dimensão:", f'{seg_uid}_dim', "text")
        form.addRow("", self._create_fundo_metric_tags(seg_uid))

        self._add_linked_row(form, "Apoio Inicial:", f'{seg_uid}_local_ini', "text")
        self._add_linked_row(form, "Apoio Final:", f'{seg_uid}_local_fim', "text")
        
        info = QLabel("Largura, comprimento, chanfros e aberturas sao ficha do vinculo geometrico.")
        info.setWordWrap(True)
        info.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_SECONDARY}; font-style: italic;")
        form.addRow("", info)
        
        main_v.addWidget(form_w)

        # 2. Continuidade (Radio)
        cont_opts_fundo = ["Obstáculo", "Recorte", "Último Seg."]
        main_v.addWidget(self._create_radio_group("Continuidade (Fundo)", cont_opts_fundo, f"{seg_uid}_continuidade"))
        
        # Botão Remover
        if idx > 1:
            btn_rem = QPushButton("Remover Este Segmento")
            btn_rem.setStyleSheet(f"color: {Colors.ACCENT_DANGER}; background: transparent; border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 4px; padding: 4px;")
            btn_rem.setCursor(Qt.PointingHandCursor)
            btn_rem.clicked.connect(lambda: self._remove_segment(pack, layout, prefix, idx))
            main_v.addWidget(btn_rem)
            
        layout.addWidget(pack)


    def _create_fundo_metric_tags(self, seg_uid):
        values = self._get_fundo_metric_values(seg_uid)
        row = QWidget()
        lay = QVBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        for label, value in [
            ("Comp. total", values.get('comprimento_total_fundo') or "N/D"),
            ("Altura total", values.get('altura_total') or "N/D"),
            ("Largura total", values.get('largura_total_fundo') or "N/D"),
        ]:
            tag = QLabel(f"{label}: {value}")
            tag.setStyleSheet(
                f"font-size: 9px; color: {Colors.TEXT_PRIMARY};"
                f" background: {Colors.BG_DEEP}; border: 1px solid {Colors.BORDER_INPUT};"
                f" border-radius: 3px; padding: 2px 5px;"
            )
            tag.setToolTip("Informacional dinamico; valor derivado dos vinculos.")
            lay.addWidget(tag)
        return row

    def _get_fundo_metric_values(self, seg_uid):
        links = self.item_data.get('links', {}) if isinstance(self.item_data, dict) else {}
        contour = links.get(f'{seg_uid}_area_segs', {}).get('contour', [])
        ficha = {}
        if isinstance(contour, list):
            for link in contour:
                if isinstance(link, dict) and isinstance(link.get('ficha'), dict):
                    ficha = link.get('ficha') or {}
                    break

        def _fmt(value):
            if value in (None, ''):
                return ''
            try:
                n = float(str(value).replace(',', '.'))
                return str(int(n)) if abs(n - int(n)) < 0.05 else f"{n:.1f}"
            except Exception:
                return str(value)

        dim_text = (
            self._get_initial_value(f'{seg_uid}_dim')
            or self._get_initial_value('dim')
            or self.item_data.get('dim')
            or self.item_data.get('dimensao')
            or self.item_data.get('fields', {}).get('dim')
            or self.item_data.get('fields', {}).get('dimensao')
            or ''
        )
        nums = [float(n.replace(',', '.')) for n in re.findall(r'\d+(?:[,.]\d+)?', str(dim_text))]
        altura = max(nums) if nums else ''

        return {
            'comprimento_total_fundo': _fmt(ficha.get('comprimento_total_fundo')),
            'largura_total_fundo': _fmt(ficha.get('largura_total_fundo')),
            'altura_total': _fmt(altura),
        }

    def _create_radio_group(self, title, options, key_prefix, has_grade_input=False):
        """Cria um grupo de opções exclusivas (Sarrafo/Garfo/Grade) - Super Compacto"""
        grp = QGroupBox(title)
        grp.setStyleSheet(f"QGroupBox {{ font-size: 9px; font-weight: bold; border: 1px solid {Colors.BORDER_DEFAULT}; padding-top: 5px; margin-top: 2px; }}")
        l = QHBoxLayout(grp)
        l.setContentsMargins(4, 10, 4, 1) # Margens mínimas em Y
        l.setSpacing(8)
        
        bg = QButtonGroup(grp) # Garante exclusividade lógica
        self.fields[f"{key_prefix}_bg"] = bg # Mantém ref para não ser garbage collected
        
        # Valor atual salvo
        current_val = self.item_data.get(key_prefix, options[0])
        
        for opt in options:
            rb = QRadioButton(opt)
            rb.setStyleSheet(f"QRadioButton {{ font-size: 10px; color: {Colors.TEXT_PRIMARY}; }}")
            if opt == current_val: rb.setChecked(True)
            bg.addButton(rb)
            l.addWidget(rb)
            
            # Se for opção "Grade" e tiver input ativado
            if has_grade_input and "Grade" in opt:
                grade_input = QLineEdit()
                grade_input.setPlaceholderText("Tam. Grade (cm)")
                grade_input.setFixedHeight(20)
                grade_input.setStyleSheet(self.STYLE_DEFAULT)
                
                # Chave para salvar tamanho da grade
                grade_key = f"{key_prefix}_grade_size"
                self.fields[grade_key] = grade_input
                grade_input.setText(str(self.item_data.get(grade_key, "")))
                
                # Visibilidade condicional
                grade_input.setVisible(rb.isChecked())
                rb.toggled.connect(grade_input.setVisible)
                
                l.addWidget(grade_input)
                
        # Conectar mudança do grupo para atualizar data (opcional, pois validamos no final)
        # bg.buttonClicked.connect(lambda btn: self.item_data.update({key_prefix: btn.text()}))
        
        return grp

    def _create_checkbox_group(self, title, options, key_prefix):
        """Cria Grid de Checkboxes compacta para Sarrafos (4 colunas)"""
        grp = QGroupBox(title)
        grp.setStyleSheet(f"QGroupBox {{ font-size: 11px; border: 1px solid {Colors.BORDER_INPUT}; padding-top: 5px; }}")
        
        grid = QGridLayout()
        grid.setContentsMargins(5, 12, 5, 5)
        grid.setSpacing(5)
        
        # Mapeamento para grid 4x2
        # Opções vêm em ordem: Esq H1, Esq H1, Esq H2, Esq H2, Dir H1...
        # Vamos usar lógica de sufixo para posicionar
        for label, suffix in options:
            cb = QCheckBox(label)
            cb.setStyleSheet(f"QCheckBox {{ font-size: 10px; color: {Colors.TEXT_PRIMARY}; }}")
            full_key = f"{key_prefix}_chk_{suffix}"
            self.fields[full_key] = cb
            if self.item_data.get(full_key, False): cb.setChecked(True)
            
            # Lógica de posicionamento (Compacta)
            row = 0 if 'h1' in suffix else 1
            col = 0
            if 'v_e' in suffix: col = 0
            elif 'p_e' in suffix: col = 1
            elif 'v_d' in suffix: col = 2
            elif 'p_d' in suffix: col = 3
            
            grid.addWidget(cb, row, col)
            
        grp.setLayout(grid)
        return grp


    def _remove_segment(self, widget, layout, prefix, idx):
        """Remove visualmente e limpa referências"""
        widget.hide()
        layout.removeWidget(widget)
        widget.deleteLater()
        
        seg_prefix = f"{prefix}_seg_{idx}"
        
        # Limpar do self.fields para não ser salvo novamente
        keys_to_remove = [k for k in self.fields.keys() if k.startswith(seg_prefix)]
        for k in keys_to_remove:
            del self.fields[k]
            
        # Remover campos da lista de validados
        validated_fields = self.item_data.get('validated_fields', [])
        fields_to_unvalidate = [k for k in validated_fields if k.startswith(seg_prefix)]
        for k in fields_to_unvalidate:
            self.undo_field_validation(k)
        
        # Remover metadados e vínculos (links)
        for data_dict_name in ['links', 'validated_link_classes', 'na_link_classes', 'field_metadata']:
            data_dict = self.item_data.get(data_dict_name, {})
            keys_to_delete = [k for k in data_dict.keys() if k.startswith(seg_prefix)]
            for k in keys_to_delete:
                del data_dict[k]
        
        # Removendo imediatamente do item_data plano para garantir consistência visual x dados
        keys_data_remove = [k for k in self.item_data.keys() if k.startswith(seg_prefix)]
        for k in keys_data_remove:
            del self.item_data[k]
            
        # Recalcular is_validated se necessário
        if not self.item_data.get('validated_fields'):
            self.item_data['is_validated'] = False
            
        self.data_changed.emit(self.item_data)


    def _get_initial_value(self, field_id):
        """Busca valor, priorizando links > sides_data > flat_key"""
        
        # 1. Prioridade: Valor do Vínculo (Se existir e for Texto/Line validado)
        links = self.item_data.get('links', {})
        if field_id in links:
            slots = links[field_id]
            if isinstance(slots, dict):
                 # Lógica especial para campos de comprimento que usam polyline
                 # Calcular comprimento se for campo comp_total_passa ou comprimento_total
                 if 'comp_total_passa' in field_id or '_comprimento_total' in field_id:
                     # Procurar por slots com pontos (polyline)
                     for slot_id, s_list in slots.items():
                         if s_list and len(s_list) > 0:
                             link_obj = s_list[0]
                             pts = link_obj.get('points', [])
                             if len(pts) >= 2:
                                 # Calcular comprimento total da polyline
                                 length = sum(((pts[i][0]-pts[i+1][0])**2 + (pts[i][1]-pts[i+1][1])**2)**0.5 for i in range(len(pts)-1))
                                 # Salvar no item_data para persistência
                                 self.item_data[field_id] = f"{length:.0f}"
                                 return f"{length:.0f}"
                 
                 # Lógica padrão para outros campos
                 for s_list in slots.values():
                     if s_list and len(s_list) > 0:
                         txt = str(s_list[0].get('text', ''))
                         if txt.strip(): 
                             # Somente extrair número se NÃO for campo de nome ou dimensão
                             is_dim_or_name = "dim" in field_id or "name" in field_id or "local" in field_id or field_id.endswith("_n") or field_id.endswith("_d")
                             if not is_dim_or_name:
                                 import re
                                 nums = re.findall(r'\d+[.,]?\d*', txt)
                                 if nums:
                                     return nums[0].replace(',', '.')
                             return txt
            elif isinstance(slots, list) and len(slots) > 0:
                 # Lógica especial para campos de comprimento (polyline)
                 if 'comp_total_passa' in field_id or '_comprimento_total' in field_id:
                     link_obj = slots[0]
                     pts = link_obj.get('points', [])
                     if len(pts) >= 2:
                         length = sum(((pts[i][0]-pts[i+1][0])**2 + (pts[i][1]-pts[i+1][1])**2)**0.5 for i in range(len(pts)-1))
                         self.item_data[field_id] = f"{length:.0f}"
                         return f"{length:.0f}"
                 
                 txt = str(slots[0].get('text', ''))
                 if txt.strip(): 
                     is_dim_or_name = "dim" in field_id or "name" in field_id or "local" in field_id or field_id.endswith("_n") or field_id.endswith("_d")
                     if not is_dim_or_name:
                         import re
                         nums = re.findall(r'\d+[.,]?\d*', txt)
                         if nums:
                             return nums[0].replace(',', '.')
                     return txt

        # 2. Prioridade: Flat Key
        if field_id in self.item_data:
            return self.item_data[field_id]
        
        # 3. Prioridade: Nested Data (sides_data)
        if field_id.startswith('p_s'):
            try:
                parts = field_id.split('_', 2) 
                if len(parts) >= 3:
                    side = parts[1][1:] 
                    key = parts[2]
                    sides = self.item_data.get('sides_data', {})
                    side_content = sides.get(side, {})
                    return side_content.get(key)
            except Exception: pass
            
        return None

    def _migrate_legacy_v_int_to_passa_esq(self, side: str) -> None:
        """Copia p_sX_v_int_* → p_sX_v_passa_esq_* se o slot novo estiver vazio."""
        legacy_n = str(self.item_data.get(f'p_s{side}_v_int_n') or '').strip()
        new_n = str(self.item_data.get(f'p_s{side}_v_passa_esq_n') or '').strip()
        empty = ('', 'N/A', 'N.A.', 'NONE', '—')
        if legacy_n.upper() in empty or new_n.upper() not in empty:
            return
        for sfx in ('_n', '_d', '_v', '_dist_t', '_dist_esq', '_dist_dir'):
            src = f'p_s{side}_v_int{sfx}'
            dst = f'p_s{side}_v_passa_esq{sfx}'
            val = self.item_data.get(src)
            if val in (None, ''):
                continue
            self.item_data[dst] = val
            w = self.fields.get(dst)
            if w and hasattr(w, 'setText') and not str(w.text() or '').strip():
                w.blockSignals(True)
                w.setText(str(val))
                w.blockSignals(False)

    def _init_side_na_defaults(self, side: str) -> None:
        """Pre-fill N/A em campos de Laje 1/2 e Vigas que Passam quando vazios.

        Chamado via QTimer após a aba do lado ser construída. Só preenche campos
        ainda vazios — nunca sobrescreve valor já digitado pelo usuário.

        Regras:
          Laje 1: se nome vazio ou 'N/A' → H e Nível recebem N/A
          Laje 2: se nome vazio          → nome + H + Nível recebem N/A
          Passa esq/dir: se nome vazio   → nome + Dimensão + Nível recebem N/A
        """
        def _na(fid: str) -> None:
            w = self.fields.get(fid)
            if w and hasattr(w, 'text') and not w.text().strip():
                w.blockSignals(True)
                w.setText('N/A')
                w.blockSignals(False)
                self.item_data[fid] = 'N/A'

        # Laje 1: H e Nível vazios quando nome é 'N/A' ou quando nome também está vazio
        l1_n_w = self.fields.get(f'p_s{side}_l1_n')
        l1_nome = l1_n_w.text().strip() if (l1_n_w and hasattr(l1_n_w, 'text')) else ''
        if not l1_nome or l1_nome.upper() in ('N/A', 'N.A.', 'NULO', 'NONE', '—'):
            _na(f'p_s{side}_l1_h')
            _na(f'p_s{side}_l1_v')

        # Laje 2: se nome vazio → todos os campos de Laje 2 recebem N/A
        l2_n_w = self.fields.get(f'p_s{side}_l2_n')
        if l2_n_w and hasattr(l2_n_w, 'text') and not l2_n_w.text().strip():
            for fid in (f'p_s{side}_l2_n', f'p_s{side}_l2_h', f'p_s{side}_l2_v'):
                _na(fid)

        # Vigas que Passam (2 esquinas): se nome vazio → N/A nos campos principais
        for slot in ('passa_esq', 'passa_dir'):
            v_n_w = self.fields.get(f'p_s{side}_v_{slot}_n')
            if v_n_w and hasattr(v_n_w, 'text') and not v_n_w.text().strip():
                for fid in (
                    f'p_s{side}_v_{slot}_n',
                    f'p_s{side}_v_{slot}_d',
                    f'p_s{side}_v_{slot}_v',
                ):
                    _na(fid)

    def _on_panel_slab_name_changed(self, side: str, laje_idx: int, slab_name: str):
        """Auto-preenche Altura e Nível da Laje quando o nome é informado.

        Busca a laje em slabs_found da main window pelo nome e consulta o
        nivel_report para obter o level_str. Só preenche se o campo estiver vazio.
        """
        slab_name = (slab_name or '').strip()
        if not slab_name:
            return

        # Nome indica ausência de laje (N/A, nulo, etc.) → H e Nível recebem N/A
        if slab_name.upper() in ('N/A', 'N.A.', 'NULO', 'NONE', '—'):
            for fid in (f'p_s{side}_l{laje_idx}_h', f'p_s{side}_l{laje_idx}_v'):
                w = self.fields.get(fid)
                if w and hasattr(w, 'text') and not w.text().strip():
                    w.blockSignals(True)
                    w.setText('N/A')
                    w.blockSignals(False)
                    self.item_data[fid] = 'N/A'
            return

        try:
            main_win = self.window()
            slabs = getattr(main_win, 'slabs_found', None) or []
            slab = next(
                (s for s in slabs if (s.get('name') or '').strip().upper() == slab_name.upper()),
                None
            )

            # ── Auto-fill Altura / Espessura ────────────────────────────────────
            h_fid = f'p_s{side}_l{laje_idx}_h'
            h_w = self.fields.get(h_fid)
            if h_w and hasattr(h_w, 'text') and not h_w.text().strip() and slab:
                f2 = slab.get('fields') or {}
                dim_txt = str(f2.get('laje_dim') or slab.get('laje_dim') or '').strip()
                if dim_txt:
                    h_w.blockSignals(True)
                    h_w.setText(dim_txt)
                    h_w.blockSignals(False)
                    self.item_data[h_fid] = dim_txt

            # ── Auto-fill Nível da Laje ─────────────────────────────────────────
            v_fid = f'p_s{side}_l{laje_idx}_v'
            v_w = self.fields.get(v_fid)
            if v_w and hasattr(v_w, 'text') and not v_w.text().strip():
                nivel_str = ''
                if hasattr(main_win, 'pavimento_nivel_report'):
                    nr = getattr(main_win, 'pavimento_nivel_report', {}) or {}
                    entry = (nr.get('lajes') or {}).get(slab_name, {})
                    nivel_str = entry.get('level_str', '')
                if not nivel_str and slab:
                    f2 = slab.get('fields') or {}
                    nivel_str = str(f2.get('laje_nivel') or slab.get('laje_nivel') or '').strip()
                if nivel_str:
                    v_w.blockSignals(True)
                    v_w.setText(nivel_str)
                    v_w.blockSignals(False)
                    self.item_data[v_fid] = nivel_str
                    self._compute_nivel_saida()
        except Exception:
            pass

    def _compute_nivel_saida(self):
        """Atualiza nivel_saida com o maior nível entre todos os painéis (A-H).

        Considera p_sX_l1_v e p_sX_l2_v para cada lado.
        Vigas (p_sX_v_int_v) serão consideradas quando tiverem seu nível definido.
        """
        import re as _re
        max_val: float | None = None
        for fid, w in self.fields.items():
            if not fid.startswith('p_s'):
                continue
            # Captura campos de nível de laje: p_sA_l1_v, p_sB_l2_v, etc.
            if not _re.search(r'_l\d+_v$', fid):
                continue
            if not hasattr(w, 'text'):
                continue
            raw = w.text().strip()
            if not raw:
                continue
            try:
                val = float(raw.replace(',', '.').replace('+', ''))
                if max_val is None or val > max_val:
                    max_val = val
            except (ValueError, TypeError):
                pass

        if max_val is None:
            return
        ns_w = self.fields.get('nivel_saida')
        if ns_w and hasattr(ns_w, 'text'):
            ns_str = f'{max_val:.2f}'.rstrip('0').rstrip('.')
            ns_w.blockSignals(True)
            ns_w.setText(ns_str)
            ns_w.blockSignals(False)
            self.item_data['nivel_saida'] = ns_str

    def _refresh_text_field_from_link(self, field_id: str) -> None:
        """Atualiza QLineEdit a partir do link 'label' slot quando link_data_changed dispara.

        Só atualiza se o campo está vazio (não sobrescreve texto digitado manualmente).
        Usado para campos como Apoio Inicial/Final que são QLineEdit mas podem ser
        populados via vincular CAD.
        """
        from PySide6.QtWidgets import QLineEdit as _QLE
        w = self.fields.get(field_id)
        if not isinstance(w, _QLE):
            return
        if w.text().strip():
            return
        val = self._get_initial_value(field_id)
        if val:
            w.blockSignals(True)
            w.setText(str(val))
            w.blockSignals(False)

    def _calc_field_links_confidence(self, field_id) -> float:
        """Confiança dos vínculos de um campo — escala de 0.0 a 1.0.

        Hierarquia por vínculo (maior prioridade primeiro):
        1. link._link_conf    → valor explícito do analyzer
        2. link.validated=True ou slot em validated_link_classes → 1.0 (humano confirmou)
        3. Vínculo presente mas sem confirmação → 0.65 (detectado automaticamente)
        4. Sem vínculos → 0.0 (nada detectado para este campo)
        confidence_map[field_id] só é usado se não há vínculos E o mapa tem dado.
        """
        links_field = self.item_data.get('links', {}).get(field_id, {})
        if isinstance(links_field, list):
            links_field = {'label': links_field}
        vlc = self.item_data.get('validated_link_classes', {}).get(field_id, [])
        scores = []
        if isinstance(links_field, dict):
            for slot_id, slot_list in links_field.items():
                for lk in (slot_list or []):
                    if not isinstance(lk, dict):
                        continue
                    if '_link_conf' in lk:
                        scores.append(float(lk['_link_conf']))
                    elif lk.get('validated') or slot_id in vlc:
                        scores.append(1.0)
                    else:
                        # Detectado automaticamente mas não confirmado pelo humano
                        scores.append(0.65)
        if not scores:
            # Sem vínculos: usar confidence_map se disponível, senão 0
            fallback = float(self.item_data.get('confidence_map', {}).get(field_id, 0.0))
            return fallback
        return sum(scores) / len(scores)

    def _refresh_link_conf_badge(self, field_id: str) -> None:
        """Atualiza dinamicamente o badge XX% de um campo após validar/desvalidar."""
        badge = self._link_conf_badges.get(field_id)
        if badge is None:
            return
        try:
            lc = self._calc_field_links_confidence(field_id)
            lc_pct = int(lc * 100)
            if lc_pct > 80:
                color = Semantic.SUCCESS
                tip   = 'Alta confiança'
            elif lc_pct > 40:
                color = Semantic.WARNING
                tip   = 'Confiança média — revisar'
            else:
                color = Semantic.DANGER
                tip   = 'Baixa confiança — verificar vínculos'
            badge.setText(f'{lc_pct}%')
            badge.setStyleSheet(
                f'color: {color}; font-size: 9px; font-weight: bold;'
                f' padding: 0 3px; border: 1px solid {color}; border-radius: 3px;'
            )
            badge.setToolTip(f'Confiança dos vínculos: {lc_pct}% — {tip}')
        except RuntimeError:
            pass  # widget C++ já deletado

    def _create_action_buttons(self):
        # Layout Vertical para economizar largura no painel
        v = QVBoxLayout()
        v.setContentsMargins(0, 5, 0, 0)
        v.setSpacing(5)

        btn_valid = QPushButton("VALIDAR (TREINAR IA)")
        btn_valid.setObjectName("Success")
        btn_valid.setCursor(Qt.PointingHandCursor)
        btn_valid.setFixedHeight(35)
        btn_valid.setToolTip("Salva e treina o padrão atual no banco de dados")
        btn_valid.clicked.connect(self.on_validate)

        btn_invalid = QPushButton("MARCAR FALHA")
        btn_invalid.setObjectName("Danger")
        btn_invalid.setCursor(Qt.PointingHandCursor)
        btn_invalid.setFixedHeight(35)
        btn_invalid.setToolTip("Marca este item para revisão manual posterior")
        btn_invalid.clicked.connect(self.on_invalidate)

        # CAD-11: Gerar DXF STOG
        btn_dxf = QPushButton("GERAR DXF")
        btn_dxf.setCursor(Qt.PointingHandCursor)
        btn_dxf.setFixedHeight(35)
        btn_dxf.setStyleSheet(
            f"QPushButton {{ background: {Surface.RAISED}; color: {Accent.PRIMARY}; border: 1px solid {Accent.PRIMARY}; "
            f"border-radius: 4px; font-weight: bold; }} "
            f"QPushButton:hover {{ background: {Surface.BASE}; }} "
            f"QPushButton:disabled {{ color: {Text.MUTED}; border-color: {Text.MUTED}; }}"
        )
        btn_dxf.setToolTip("Gera o DXF STOG deste item a partir dos dados de Fase-4")
        btn_dxf.clicked.connect(self._on_gerar_dxf)
        if not _DXF_GEN_AVAILABLE:
            btn_dxf.setEnabled(False)
            btn_dxf.setToolTip("Módulo de geração DXF não disponível")

        v.addWidget(btn_valid)
        v.addWidget(btn_invalid)
        v.addWidget(btn_dxf)

        return v

    def _on_gerar_dxf(self):
        """CAD-11: Abre o dialog de geração DXF para o item atual."""
        if not _DXF_GEN_AVAILABLE:
            return
        obra_path = getattr(self, 'obra_path', None)
        if not obra_path:
            QMessageBox.warning(
                self, "Obra não vinculada",
                "Este item não está vinculado a uma obra com Fase-4.\n"
                "Execute 'Analise Geral' primeiro."
            )
            return
        item_type = self.item_data.get('type', '')
        item_id   = self.item_data.get('id_item', '')
        GenerateDXFDialog.open_for_item(obra_path, item_type, item_id, parent=self)

    def on_validate(self):
        final_data = self.item_data.copy()
        validated = final_data.setdefault('validated_fields', [])

        # Ensure sides_data exists
        if 'sides_data' not in final_data: final_data['sides_data'] = {}

        for key, widget in self.fields.items():
            if isinstance(widget, QLineEdit): val = widget.text()
            elif isinstance(widget, QComboBox): val = widget.currentText()
            else: continue

            final_data[key] = val
            # Ao validar o card todo, todos os campos preenchidos ganham selo de validado
            if val and key not in validated:
                validated.append(key)

        # [NOVO] SELO AZUL (Validação Completa de Contexto)
        # Só este botão concede o status de "Item 100% Validado" para curadoria
        final_data['is_fully_validated'] = True
        final_data['is_validated'] = True
        self.item_data['is_fully_validated'] = True
        self.item_data['is_validated'] = True

        # Cascata pro segmento: validar o item inteiro validado todos os
        # segmentos ativos também (a pedido do dono — "ao validar o item se
        # conclui e valida todos os segmentos").
        active_segments = self._all_active_segment_keys()
        if active_segments:
            segs = self.item_data.setdefault('validated_segments', {})
            for key in active_segments:
                segs[key] = True
            final_data['validated_segments'] = dict(segs)

        self.refresh_validation_styles()

        # ── CAD-10.6: Detectar divergências com Fase-4 e oferecer realimentação ──
        self._check_fase4_divergences(final_data)

        self.data_validated.emit(final_data)

    def _check_fase4_divergences(self, final_data: dict):
        """
        Compara valores validados com Fase-4 e, se houver divergências,
        abre CorrectionDialog para o usuário escolher a ação.
        Aplicado só quando obra_path e correction_service disponíveis.
        """
        if not _CORRECTION_AVAILABLE:
            return
        obra_path = getattr(self, 'obra_path', None)
        if not obra_path:
            return

        # Coletar campos preenchidos pelo usuário (flat + sides_data)
        db_values: dict = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                v = widget.text()
                if v:
                    db_values[key] = v
            elif isinstance(widget, QComboBox):
                v = widget.currentText()
                if v:
                    db_values[key] = v

        divergences = detect_divergences(final_data, obra_path, db_values)
        if not divergences:
            return

        choices = CorrectionDialog.ask(
            divergences,
            item_id=final_data.get('id_item', ''),
            parent=self,
        )
        if not choices:
            return  # usuário cancelou

        from pathlib import Path
        obra = Path(obra_path)
        item_id   = final_data.get('id_item', '')
        item_type = final_data.get('type', 'pilar')

        for choice in choices:
            action    = choice.get('action', 'keep_db')
            json_key  = choice.get('json_key', '')
            field_id  = choice.get('field_id', '')
            f4_value  = choice.get('f4_value')
            db_value  = choice.get('db_value')

            if action == 'use_f4':
                # Atualiza o widget com o valor Fase-4
                widget = self.fields.get(field_id)
                if widget and isinstance(widget, QLineEdit):
                    widget.setText(str(f4_value))
                elif widget and isinstance(widget, QComboBox):
                    idx = widget.findText(str(f4_value))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)

            elif action == 'log_correction':
                # Registra correção no log (realimenta o interpretador)
                from src.core.services.correction_service import _find_json_path
                json_path = _find_json_path(obra, item_id, item_type)
                if json_path:
                    apply_correction(json_path, json_key, db_value)
                    entry = build_log_entry(
                        item_id=item_id,
                        item_type=item_type,
                        json_key=json_key,
                        detail_field_id=field_id,
                        old_value=f4_value,
                        new_value=db_value,
                    )
                    append_correction_log(obra, entry)

    def on_invalidate(self):
        self.data_invalidated.emit(self.item_data)
        QMessageBox.warning(self, "IA Training", "Item marcado para revisão manual.")

    def _on_format_changed(self, text):
        """Reage à mudança no ComboBox de formato"""
        self.item_data['format'] = text
        self._refresh_dynamic_content()

    def _refresh_dynamic_content(self):
        """Reconstrói a área dinâmica baseada no tipo e formato atual"""
        self._clear_dynamic_content()
        
        elem_type = self.item_data.get('type', '').lower()
        if 'pilar' in elem_type:
            # Garante que usamos o layout dinâmico
            self._setup_pilar_complex_view(self.dynamic_layout)
        elif 'viga' in elem_type:
            self._setup_viga_complex_view(self.dynamic_layout)
        elif 'laje' in elem_type:
            self._setup_laje_complex_view(self.dynamic_layout)
        elif 'marcodxf' in elem_type:
            self._setup_marco_view(self.dynamic_layout)

    def _clear_dynamic_content(self):
        """Remove widgets dinâmicos e limpa referências no self.fields"""
        # Identifica campos que pertencem ao container dinâmico para remover do self.fields
        to_remove = []
        for key, widget in self.fields.items():
            if self._is_descendant(widget, self.dynamic_container):
                to_remove.append(key)
        
        for k in to_remove:
            del self.fields[k]
            
        # Remove widgets do layout
        while self.dynamic_layout.count():
            item = self.dynamic_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Se for um layout aninhado, precisamos limpar recursivamente ou deletar o item
                # Layouts em Qt não são widgets, mas items layout.
                # O ideal é que tudo esteja dentro de widgets.
                # Como usamos .addWidget(tabs), tabs é um widget.
                pass

    def _is_descendant(self, widget, ancestor):
        b_name = self.item_data.get('name', 'Sem Nome')
        if override_type != 'viga_lateral':
            if b_name.endswith('-1'):
                b_name = b_name[:-2] + '.C'
            elif not b_name.endswith('.C'):
                b_name = b_name + '.C'
                
        lbl_title.setText(f"Viga {'Lateral' if override_type == 'viga_lateral' else 'Fundo'}: {b_name}")
        """Verifica se widget é descendente de ancestor (para limpeza segura)"""
        p = widget
        while p:
            if p == ancestor: return True
            p = p.parentWidget()
        return False

    def _build_nivel_detail_box(self) -> QFrame | None:
        """
        Constrói um box colapsável de detalhes de compreensão para o campo laje_nivel.
        Lê level_inference do item_data. Retorna None se não houver dados relevantes.
        """
        inference = self.item_data.get('level_inference') or {}
        # Também tenta obter o relatório completo do pavimento se disponível via parent chain
        nivel_report_entry: dict = {}
        try:
            main_win = self.window()
            if hasattr(main_win, 'get_nivel_report'):
                nr = main_win.get_nivel_report()
                slab_name = self.item_data.get('name') or ''
                nivel_report_entry = (nr.get('lajes') or {}).get(slab_name, {})
        except Exception:
            pass

        has_inference = bool(inference)
        has_entry = bool(nivel_report_entry)
        if not has_inference and not has_entry:
            return None

        # ── Container ──────────────────────────────────────────────────────────
        container = QFrame()
        container.setObjectName("NivelDetailBox")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # ── Botão toggle ───────────────────────────────────────────────────────
        toggle_btn = QPushButton("▶  Detalhes de compreensão do Nível")
        toggle_btn.setCheckable(True)
        toggle_btn.setChecked(False)
        toggle_btn.setStyleSheet(
            f"QPushButton {{ text-align:left; padding:2px 4px; font-size:9px; "
            f"color:{Colors.ACCENT_MINT}; background:transparent; border:none; }}"
            f"QPushButton:checked {{ color:{Colors.ACCENT_WARNING_ALT}; }}"
        )
        container_layout.addWidget(toggle_btn)

        # ── Painel de detalhes (inicialmente oculto) ───────────────────────────
        panel = QFrame()
        panel.setVisible(False)
        panel.setStyleSheet(
            f"QFrame {{ background:{Colors.BG_SECONDARY}; "
            f"border:1px solid {Colors.BORDER_DEFAULT}; border-radius:4px; padding:4px; }}"
        )
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 4, 6, 4)
        panel_layout.setSpacing(3)

        def _lbl(text: str, color: str = '') -> QLabel:
            lb = QLabel(text)
            lb.setWordWrap(True)
            style = f"font-size:9px; color:{color};" if color else "font-size:9px;"
            lb.setStyleSheet(style)
            return lb

        def _conf_color(conf: float) -> str:
            if conf >= 0.9:
                return Semantic.SUCCESS
            if conf >= 0.7:
                return Semantic.WARNING
            if conf >= 0.5:
                return Semantic.WARNING
            return Semantic.DANGER

        SOURCE_LABELS = {
            'human_direct': 'Texto humano vinculado diretamente',
            'text_label': 'Texto vinculado (não validado)',
            'cut_view_delta': 'Calculado por delta geométrico do corte',
            'neighbor_inferred': 'Inferido por consenso de vizinhas',
            'auto_linked': 'Auto-vinculado (semi-automático)',
            'unknown': 'Desconhecido — sem fonte detectada',
        }

        # Dados do relatório (preferência) ou do inference direto
        source_type = nivel_report_entry.get('source_type') or inference.get('reason') or '—'
        confidence = float(nivel_report_entry.get('confidence', 0) or inference.get('confidence', 0) or 0)
        level_str = nivel_report_entry.get('level_str') or inference.get('value') or '—'
        warnings = nivel_report_entry.get('warnings') or []
        neighbors = nivel_report_entry.get('neighbors') or {}
        status = inference.get('status') or ''

        source_label = SOURCE_LABELS.get(source_type, source_type)
        conf_pct = f"{confidence * 100:.0f}%"
        conf_color = _conf_color(confidence)

        panel_layout.addWidget(_lbl(f"Fonte: {source_label}"))
        panel_layout.addWidget(_lbl(f"Nível: {level_str}   |   Confiança: {conf_pct}", conf_color))

        if status and status not in ('inferred',):
            panel_layout.addWidget(_lbl(f"Status: {status}", Text.SECONDARY))

        # Detalhes da inferência
        inf_reason = inference.get('reason') or ''
        if inf_reason:
            panel_layout.addWidget(_lbl(f"Razão: {inf_reason}", Text.SECONDARY))

        inf_sources = inference.get('sources') or []
        if inf_sources:
            src_names = ', '.join(
                str(s.get('slab') or s.get('source_slab') or '?')
                for s in inf_sources[:3]
                if isinstance(s, dict)
            )
            if src_names:
                panel_layout.addWidget(_lbl(f"Lajes usadas: {src_names}", Text.SECONDARY))

        # Vizinhas
        if neighbors:
            DIR_MAP = {'north': 'N', 'south': 'S', 'east': 'L', 'west': 'O'}
            nb_parts = [f"{DIR_MAP.get(d, d)}: {v}" for d, v in neighbors.items()]
            panel_layout.addWidget(_lbl("Vizinhas: " + ' | '.join(nb_parts), Text.MUTED))

        # Warnings
        for w in warnings:
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet(f"color:{Colors.BORDER_DEFAULT};")
            panel_layout.addWidget(sep)
            panel_layout.addWidget(_lbl(f"⚠  {w}", Semantic.DANGER))

        container_layout.addWidget(panel)

        def _toggle(checked: bool):
            panel.setVisible(checked)
            toggle_btn.setText(("▼" if checked else "▶") + "  Detalhes de compreensão do Nível")

        toggle_btn.toggled.connect(_toggle)
        return container

    def _clean_laje_dim_input(self, text):
        """Limpa entrada de dimensão de laje (ex: 'd=12' -> '12')"""
        import re
        # Se tiver d= ou h=, extrai o número
        match = re.search(r'[dhDH]=\s*(\d+[.,]?\d*)', text)
        if match:
             clean_val = match.group(1)
             # Evita loop infinito
             current = self.fields['laje_dim'].text()
             if current != clean_val:
                  self.fields['laje_dim'].blockSignals(True)
                  self.fields['laje_dim'].setText(clean_val)
                  self.fields['laje_dim'].blockSignals(False)
                  # Atualiza dados
                  self._on_field_changed('laje_dim', clean_val)

    def _setup_marco_view(self, layout_container):
        """View em formato de Tabela (Grid) para o Tratamento Prévio do Marco"""
        from PySide6.QtWidgets import QGridLayout, QFrame
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        lbl_head = QLabel("🛠️ TRATAMENTO PRÉVIO - PERÍMETRO")
        lbl_head.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Colors.ACCENT_PRIMARY};")
        layout.addWidget(lbl_head)

        vigas = self.item_data.get('vigas_individuais', [])
        
        if not vigas:
            layout.addWidget(QLabel("Nenhuma viga de extremidade detectada."))
        else:
            # Header da "Tabela"
            header_frame = QFrame()
            header_frame.setStyleSheet(f"background: {Colors.BG_PANEL}; border-bottom: 1px solid {Colors.BORDER_INPUT};")
            h_lay = QHBoxLayout(header_frame)
            h_lay.setContentsMargins(5, 5, 5, 5)
            
            lbl_ref = QLabel("Referência"); lbl_ref.setStyleSheet(f"font-weight: bold; color: {Colors.TEXT_SECONDARY};")
            lbl_tam = QLabel("Tamanho"); lbl_tam.setStyleSheet(f"font-weight: bold; color: {Colors.TEXT_SECONDARY};")
            lbl_lnk = QLabel("Acoes"); lbl_lnk.setStyleSheet(f"font-weight: bold; color: {Colors.TEXT_SECONDARY};")
            lbl_val = QLabel("Soma (cm)"); lbl_val.setStyleSheet(f"font-weight: bold; color: {Colors.TEXT_SECONDARY};")
            
            h_lay.addWidget(lbl_ref, 2)
            h_lay.addWidget(lbl_tam, 2)
            h_lay.addWidget(lbl_lnk, 2) 
            h_lay.addWidget(lbl_val, 2)
            layout.addWidget(header_frame)

            # Lista de Itens (Rows)
            for v in vigas:
                v_id = v.get('id')
                field_key = f"ext_viga_{v_id}"
                
                row_container = QFrame()
                row_container.setStyleSheet(f"border-bottom: 1px solid {Colors.BORDER_SUBTLE};")
                row_v_lay = QVBoxLayout(row_container)
                row_v_lay.setContentsMargins(0, 0, 0, 0)
                row_v_lay.setSpacing(0)
                
                # Linha de Dados
                data_row = QWidget()
                dr_lay = QHBoxLayout(data_row)
                dr_lay.setContentsMargins(5, 4, 5, 4) # Mais margem
                
                # 1. Referência
                lbl_v_id = QLabel(f"Viga_{v_id[:4]}")
                lbl_v_id.setStyleSheet(f"color: {Colors.TEXT_BRIGHT}; font-weight: bold;")
                dr_lay.addWidget(lbl_v_id, 2)
                
                # 2. Tamanho (Original)
                dr_lay.addWidget(QLabel(f"{v.get('original_len', 0):.1f}"), 2)
                
                # 3. Bloco de Botões (Compacto: Ícones Ajustados)
                btns_widget = QWidget()
                btns_lay = QHBoxLayout(btns_widget)
                btns_lay.setContentsMargins(0, 0, 0, 0)
                btns_lay.setSpacing(4)
                
                drawer = QWidget()
                drawer.hide()
                drawer.setStyleSheet(f"background: {Colors.BG_DEEP}; border-left: 3px solid {Colors.ACCENT_PRIMARY}; margin: 2px; border-radius: 2px;")
                
                # Botão ZOOM
                btn_zoom = QPushButton("🔍 Zoom")
                # btn_zoom.setFixedSize(24, 24)
                btn_zoom.setCursor(Qt.PointingHandCursor)
                btn_zoom.setStyleSheet("""
                    QPushButton { 
                        background: rgba(60, 60, 60, 180); border: 1px solid {Colors.BORDER_INPUT}; border-radius: 3px;
                        color: {Colors.ACCENT_INFO}; font-size: 13px; font-weight: bold; padding: 0px;
                    }
                    QPushButton:hover { background: rgba(100, 100, 100, 255); border: 1px solid {Colors.ACCENT_INFO}; }
                """)
                btn_zoom.clicked.connect(lambda checked=False, f=field_key: self.focus_requested.emit(f))
                
                # Botão VINC
                btn_link = QPushButton("Vincular")
                btn_link.setFixedHeight(22)
                btn_link.setCursor(Qt.PointingHandCursor)
                btn_link.setStyleSheet(f"font-size: 10px; color: {Colors.ACCENT_PRIMARY}; background: transparent; border: none; font-weight: bold; text-align: right;")
                btn_link.clicked.connect(lambda checked=False, f=field_key, d=drawer, b=btn_link: self._toggle_link_drawer(f, d, b))
                
                # Botão EXCL
                btn_del = QPushButton("✖ Excluir")
                # btn_del.setFixedSize(24, 24)
                btn_del.setCursor(Qt.PointingHandCursor)
                btn_del.setStyleSheet("""
                    QPushButton { 
                        background: rgba(60, 60, 60, 180); border: 1px solid {Colors.BORDER_INPUT}; border-radius: 3px;
                        color: {Colors.ACCENT_DANGER}; font-size: 13px; font-weight: bold; padding: 0px;
                    }
                    QPushButton:hover { background: rgba(220, 50, 50, 255); border: 1px solid {Colors.ACCENT_DANGER}; }
                """)
                btn_del.clicked.connect(lambda checked=False, vid=v_id, cont=row_container: self._remove_marco_row(vid, cont))
                
                btns_lay.addWidget(btn_zoom)
                btns_lay.addWidget(btn_link)
                btns_lay.addWidget(btn_del)
                dr_lay.addWidget(btns_widget, 2)
                
                # 4. Campo Valor
                ext_val = v.get('extension_len', 10.0)
                display_val = "10.0"
                if isinstance(ext_val, (int, float)):
                     display_val = f"{ext_val:.1f}"
                elif isinstance(ext_val, str) and ext_val.replace('.','',1).isdigit():
                     display_val = ext_val
                else: 
                     display_val = "10.0" # Fallback se vier lixo (ex: 'Polyline...')

                val_edit = QLineEdit(display_val)
                val_edit.setFixedWidth(60)
                val_edit.setAlignment(Qt.AlignCenter)
                val_edit.setStyleSheet(f"""
                    QLineEdit {{
                        background: {Colors.BG_DEEP}; border: 1px solid {Colors.BORDER_DEFAULT}; color: {Colors.ACCENT_SUCCESS_ALT};
                        font-weight: bold; border-radius: 4px; font-size: 12px; padding: 2px;
                    }}
                    QLineEdit:focus {{ border: 1px solid {Colors.ACCENT_SUCCESS_ALT}; background: {Colors.BG_CARD}; }}
                """)
                val_edit.textChanged.connect(lambda t, k=field_key: self._on_field_changed(k, t))
                self.fields[field_key] = val_edit
                
                dr_lay.addWidget(val_edit, 2)
                
                row_v_lay.addWidget(data_row)
                row_v_lay.addWidget(drawer)
                layout.addWidget(row_container)

        # Botão Adicionar Nova Viga
        btn_add = QPushButton("➕ ADICIONAR VIGA MANUAL")
        btn_add.setStyleSheet(f"""
            QPushButton {{ background: rgba(26, 58, 90, 1); color: {Colors.ACCENT_PRIMARY}; border: 1px dashed {Colors.ACCENT_PRIMARY}; padding: 8px; font-weight: bold; margin-top: 10px; border-radius: 4px;}}
            QPushButton:hover {{ background: rgba(42, 90, 138, 1); border-style: solid; }}
        """)
        btn_add.clicked.connect(self._add_manual_marco_row)
        layout.addWidget(btn_add)

        # Uniões do Marco (Separado)
        group_uniao = QGroupBox("FECHAMENTO DO MARCO (UNIÕES PONTAS)")
        group_uniao.setStyleSheet(f"QGroupBox {{ font-size: 11px; font-weight: bold; color: {Colors.ACCENT_WARNING_ALT}; border: 1px solid {Colors.BORDER_DEFAULT}; margin-top: 20px; padding-top: 15px; }}")
        uniao_layout = QFormLayout(group_uniao)
        self._add_linked_row(uniao_layout, "Uniões Marco:", "unioes_marco", pick_type='poly', hide_input=True)
        layout.addWidget(group_uniao)
        
        layout.addStretch()
        layout_container.addWidget(container)

    def _remove_marco_row(self, v_id, container):
        """Remove uma viga da lista de extremidades e limpa seus vínculos"""
        # Exclusão direta conforme solicitado
        vigas = self.item_data.get('vigas_individuais', [])
        self.item_data['vigas_individuais'] = [v for v in vigas if v.get('id') != v_id]
        
        # Limpar vínculos do campo
        field_key = f"ext_viga_{v_id}"
        if 'links' in self.item_data and field_key in self.item_data['links']:
            del self.item_data['links'][field_key]
        
        if field_key in self.fields:
            del self.fields[field_key]
        
        # Remover widget
        container.deleteLater()
        
        # Sincronizar mudança externamente
        self.data_changed.emit(self.item_data)
        self.refresh_validation_styles()

    def _add_manual_marco_row(self):
        """Adiciona manualmente uma nova viga à lista de tratamento prévio"""
        new_id = str(uuid.uuid4())[:8]
        new_viga = {
            'id': new_id,
            'type': 'line',
            'points': [],
            'text': f'Viga_{new_id[:4]}',
            'original_len': 0.0,
            'extension_len': 10.0,
            'final_len': 10.0
        }
        
        if 'vigas_individuais' not in self.item_data:
            self.item_data['vigas_individuais'] = []
            
        self.item_data['vigas_individuais'].append(new_viga)
        
        # Iniciar links vazios para ela (Main = Viga Total, Default = Segmento Ajuste)
        if 'links' not in self.item_data: self.item_data['links'] = {}
        self.item_data['links'][f"ext_viga_{new_id}"] = {'main': [], 'default': []}
        
        # Feedback visual removido para dinamismo
    def _on_slot_na_toggled(self, field_id, slot_id, is_na):
        """Gerencia o N/A de um slot específico (Classe de Vínculo)"""
        na_slots_map = self.item_data.setdefault('na_link_classes', {})
        na_list = na_slots_map.setdefault(field_id, [])
        
        if is_na:
            if slot_id not in na_list: na_list.append(slot_id)
            # Limpar links deste slot
            if 'links' in self.item_data and field_id in self.item_data['links']:
                field_links = self.item_data['links'][field_id]
                if isinstance(field_links, dict) and slot_id in field_links:
                    print(f"[DEBUG HIERARCHY] Slot '{slot_id}' marked N/A. Clearing {len(field_links[slot_id])} links.")
                    field_links[slot_id] = []
            # Limpar validação se marcar N/A
            valid_map = self.item_data.get('validated_link_classes', {})
            if field_id in valid_map and slot_id in valid_map[field_id]:
                valid_map[field_id].remove(slot_id)
            
            # Emitir Treino para N/A da Classe
            self.training_requested.emit(field_id, {
                'status': 'na',
                'comment': f"Usuário marcou classe {slot_id} como N/A",
                'slot': slot_id
            })
        else:
            if slot_id in na_list: na_list.remove(slot_id)
            print(f"[DEBUG HIERARCHY] Slot '{slot_id}' unmarked N/A.")
            
        print(f"[DetailCard] Slot NA toggled: {field_id} -> {slot_id} = {is_na}")
        self.data_changed.emit(self.item_data)
        self.refresh_validation_styles()

    def _on_slot_validated(self, field_id, slot_id, checked=True):
        """Gerencia validação (ou undo) de uma classe/slot específica"""
        valid_map = self.item_data.setdefault('validated_link_classes', {})
        if field_id not in valid_map: valid_map[field_id] = []
        
        if checked:
            if slot_id not in valid_map[field_id]:
                valid_map[field_id].append(slot_id)
            
            # Cascata: Validar todos os links internos
            links_dict = self.item_data.get('links', {})
            field_links = links_dict.get(field_id, {})
            if isinstance(field_links, dict) and slot_id in field_links:
                for lk in field_links[slot_id]:
                    lk['validated'] = True
                    lk.pop('failed', None)
        else:
            # UNDO SLOT
            self.undo_slot_validation(field_id, slot_id)

        self._refresh_link_conf_badge(field_id)
        self.validation_changed.emit({
            'item': self.item_data,
            'field_id': field_id,
            'slot_id': slot_id,
            'is_valid': checked,
            'scope': 'slot',
        })

    def undo_slot_validation(self, field_id, slot_id):
        """Remove a validação de um slot e seus vínculos (Undo)"""
        self._clear_full_validation_state()

        # 1. Remover do mapa de validados
        valid_map = self.item_data.get('validated_link_classes', {})
        if field_id in valid_map and slot_id in valid_map[field_id]:
            valid_map[field_id].remove(slot_id)

        # 2. Resetar links internos e pedir REMOÇÃO de treino
        links_dict = self.item_data.get('links', {})
        field_links = links_dict.get(field_id, {})
        if isinstance(field_links, dict) and slot_id in field_links:
            for lk in field_links[slot_id]:
                lk.pop('validated', None)
                lk.pop('failed', None)
        
        if field_id in self.embedded_managers:
            self.embedded_managers[field_id]._sync_slot_validation_ui(slot_id, False, refresh=False)

    def undo_field_validation(self, field_id):
        """Desfaz toda a validação de um campo (Undo de alto nível)"""
        self._clear_full_validation_state()

        validated = self.item_data.get('validated_fields', [])
        if field_id in validated:
            validated.remove(field_id)
        
        # Cascata para Slots
        valid_map = self.item_data.get('validated_link_classes', {})
        if field_id in valid_map:
            slots_to_undo = list(valid_map[field_id]) # Cópia para iterar
            for s_id in slots_to_undo:
                self.undo_slot_validation(field_id, s_id)
        
        # Reset visual
        self._refresh_link_conf_badge(field_id)
        self.refresh_validation_styles()
        self.validation_changed.emit({
            'item': self.item_data,
            'field_id': field_id,
            'is_valid': False,
            'scope': 'field_undo',
        })
        self.log_requested.emit(f"🔄 Validação do campo '{field_id}' desfeita.")

    def _on_slot_na_toggled(self, field_id, slot_id, is_na):
        """Gerencia o estado 'Não se Aplica' para um slot/classe específica"""
        na_map = self.item_data.setdefault('na_link_classes', {})
        if field_id not in na_map: na_map[field_id] = []
        
        if is_na:
            if slot_id not in na_map[field_id]:
                na_map[field_id].append(slot_id)
            
            # Limpa vínculos desse slot
            links_dict = self.item_data.get('links', {})
            field_links = links_dict.get(field_id, {})
            if isinstance(field_links, dict) and slot_id in field_links:
                field_links[slot_id] = []
            
            # Treinar como N/A
            self.training_requested.emit(field_id, {
                'status': 'na',
                'comment': f"Slot '{slot_id}' marcado como N/A pelo usuário.",
                'slot': slot_id
            })
        else:
            if slot_id in na_map[field_id]:
                na_map[field_id].remove(slot_id)
            
            # Undo N/A Treino
            self.training_requested.emit(field_id, {
                'status': 'removed',
                'slot': slot_id,
                'link': {'text': 'N/A'}
            })

        self.refresh_validation_styles()
        self.data_changed.emit(self.item_data)

    def _refresh_dynamic_content(self):
        """Atualiza o conteúdo dinâmico (abas/campos) baseado no tipo e formato do item"""
        if not hasattr(self, 'dynamic_layout') or self.dynamic_layout is None:
            return
            
        # Limpar conteúdo anterior do layout dinâmico
        while self.dynamic_layout.count():
            item = self.dynamic_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout_recursive(item.layout())
        
        itype = self.item_data.get('type', '').lower()
        if 'pilar' in itype: 
            self._setup_pilar_complex_view(self.dynamic_layout)
        elif 'viga' in itype: 
            self._setup_viga_complex_view(self.dynamic_layout)
        elif 'laje' in itype: 
            self._setup_laje_complex_view(self.dynamic_layout)
            
        # Garante que os estilos de validação se apliquem aos novos widgets criados
        self.refresh_validation_styles()

    def _clear_layout_recursive(self, layout):
        if not layout: return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
            elif item.layout(): self._clear_layout_recursive(item.layout())

    def _add_pillar_openings_table(self, container_layout, key_esq, key_dir):
        """Aberturas de pilares sarrafeados que atravessam a lateral (Esq / Dir).

        Interpretação: trecho da lateral que será sarrafeado no pilar
        (regra típica: comprimento_pilar + 11 cm cada lado).
        """
        grp = QGroupBox("Aberturas em Pilares — sarrafeados que atravessam (Esq / Dir)")
        grp.setStyleSheet(f"""
            QGroupBox {{ border: 1px solid {Colors.BORDER_INPUT}; border-radius: 6px; margin-top: 10px; padding-top: 15px; background: {Colors.BG_PANEL}; }}
            QGroupBox::title {{ color: {Colors.ACCENT_PRIMARY}; subcontrol-origin: margin; left: 10px; }}
        """)
        
        layout = QVBoxLayout(grp)
        layout.setSpacing(5)
        _hint = QLabel(
            "Distância = da ponta do segmento até o início da abertura; "
            "Largura = abertura efetiva (ex.: 11+comp.pilar+11)."
        )
        _hint.setWordWrap(True)
        _hint.setStyleSheet(f"font-size: 9px; color: {Colors.TEXT_DIM}; font-style: italic;")
        layout.addWidget(_hint)

        # Header da Tabela
        grid = QGridLayout()
        grid.setSpacing(5)
        
        headers = ["Lado", "Distância (cm)", "Largura (cm)", "Acoes"]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {Colors.TEXT_SECONDARY};")
            grid.addWidget(lbl, 0, col)

        # Linha Pilar Esquerdo
        grid.addWidget(QLabel("ESQUERDO"), 1, 0)
        f_dist_e = self._create_opening_field(key_esq, "dist", "0.0", 60)
        f_larg_e = self._create_opening_field(key_esq, "larg", "0.0", 60)
        grid.addWidget(f_dist_e, 1, 1)
        grid.addWidget(f_larg_e, 1, 2)
        
        # Acoes Pilar Esquerdo
        actions_e, drawer_e = self._create_action_buttons_for_row(key_esq)
        grid.addWidget(actions_e, 1, 3)
        grid.addWidget(drawer_e, 2, 0, 1, 4) # Span 4 cols

        # Linha Pilar Direito
        grid.addWidget(QLabel("DIREITO"), 3, 0)
        f_dist_d = self._create_opening_field(key_dir, "dist", "0.0", 60)
        f_larg_d = self._create_opening_field(key_dir, "larg", "0.0", 60)
        grid.addWidget(f_dist_d, 3, 1)
        grid.addWidget(f_larg_d, 3, 2)
        
        # Acoes Pilar Direito
        actions_d, drawer_d = self._create_action_buttons_for_row(key_dir)
        grid.addWidget(actions_d, 3, 3)
        grid.addWidget(drawer_d, 4, 0, 1, 4)

        layout.addLayout(grid)
        container_layout.addWidget(grp)

    def _add_beam_openings_table(self, container_layout, k_top_e, k_top_d, k_fun_e, k_fun_d):
        """Aberturas de pontas de viga que passam por baixo (Topo/Fundo × Esq/Dir).

        Interpretação da ficha: vigas incidentes que passam sob a lateral e
        geram recortes (profundidade × boca) nas quatro esquinas do painel.
        """
        grp = QGroupBox("Aberturas em Vigas — pontas que passam por baixo (Topo / Fundo)")
        grp.setStyleSheet(f"""
            QGroupBox {{ border: 1px solid {Colors.BORDER_INPUT}; border-radius: 6px; margin-top: 10px; padding-top: 15px; background: {Colors.BG_PANEL}; }}
            QGroupBox::title {{ color: {Colors.ACCENT_INFO}; subcontrol-origin: margin; left: 10px; }}
        """)
        
        layout = QVBoxLayout(grp)
        layout.setSpacing(5)
        _hint = QLabel(
            "Cada canto: profundidade e boca/largura da abertura + ref. H1/H2 do painel. "
            "Vincule nome/geometria/dimensão da viga incidente no drawer de ações."
        )
        _hint.setWordWrap(True)
        _hint.setStyleSheet(f"font-size: 9px; color: {Colors.TEXT_DIM}; font-style: italic;")
        layout.addWidget(_hint)
        
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setVerticalSpacing(8)
        
        headers = ["Posição", "Profundidade", "Boca/Largura", "Ref. (H)", "Acoes"]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"font-size: 9px; font-weight: bold; color: {Colors.TEXT_DIM}; text-transform: uppercase;")
            grid.addWidget(lbl, 0, col)

        # Configuração das 4 linhas solicitadas
        rows_config = [
            ("TOPO / ESQ.", k_top_e),
            ("TOPO / DIR.", k_top_d),
            ("FUNDO / ESQ.", k_fun_e),
            ("FUNDO / DIR.", k_fun_d)
        ]

        for i, (label, key) in enumerate(rows_config):
            row_idx = (i * 2) + 1 # 1, 3, 5, 7 (para dar lugar ao drawer)
            
            # Label de Posição
            lbl_pos = QLabel(label)
            lbl_pos.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_SECONDARY}; font-weight: bold;")
            grid.addWidget(lbl_pos, row_idx, 0, Qt.AlignVCenter)
            
            f_prof = self._create_opening_field(key, "prof", "0.0", 65)
            f_boca = self._create_opening_field(key, "boca", "0.0", 65)
            h_sel = self._create_h_selector(key)
            
            grid.addWidget(f_prof, row_idx, 1, Qt.AlignCenter)
            grid.addWidget(f_boca, row_idx, 2, Qt.AlignCenter)
            grid.addWidget(h_sel, row_idx, 3, Qt.AlignCenter)
            
            # Acoes
            actions_w, drawer_w = self._create_action_buttons_for_row(key)
            grid.addWidget(actions_w, row_idx, 4)
            grid.addWidget(drawer_w, row_idx + 1, 0, 1, 5) # Span 5 cols

        layout.addLayout(grid)
        container_layout.addWidget(grp)

    def _create_opening_field(self, prefix, suffix, placeholder, width):
        """Helper para criar mini-fields para as tabelas"""
        f = QLineEdit()
        f.setPlaceholderText(placeholder)
        if width > 0: f.setFixedWidth(width)
        f.setStyleSheet(self.STYLE_DEFAULT)
        
        full_key = f"{prefix}_{suffix}"
        self.fields[full_key] = f
        
        val = self._get_initial_value(full_key)
        if val: f.setText(str(val))
        
        f.textChanged.connect(lambda t, k=full_key: self._on_field_changed(k, t))
        return f

    def _create_h_selector(self, key_prefix):
        """Cria seletor H1/H2 compacto para tabela"""
        widget = QWidget()
        l = QHBoxLayout(widget)
        l.setContentsMargins(0,0,0,0)
        l.setSpacing(5)
        
        bg = QButtonGroup(widget)
        rb1 = QRadioButton("H1"); rb2 = QRadioButton("H2")
        rb1.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_PRIMARY};")
        rb2.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_PRIMARY};")
        
        full_key = f"{key_prefix}_h_sel"
        current = self.item_data.get(full_key, "H1")
        if current == "H2": rb2.setChecked(True)
        else: rb1.setChecked(True)
        
        bg.addButton(rb1); bg.addButton(rb2)
        l.addWidget(rb1); l.addWidget(rb2)
        
        rb1.toggled.connect(lambda checked: self._on_field_changed(full_key, "H1") if checked else None)
        rb2.toggled.connect(lambda checked: self._on_field_changed(full_key, "H2") if checked else None)
        
        return widget

    def _create_action_buttons_for_row(self, field_id):
        """Helper para criar o bloco de botões de ação e o drawer LinkManager para uma linha de tabela"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Drawer
        drawer = QWidget()
        drawer.hide()
        drawer.setStyleSheet(f"background: {Colors.BG_DEEP}; border-top: 1px solid {Colors.BORDER_INPUT}; margin-top: 2px;")

        # Botão Vincular
        btn_link = QPushButton("Vincular")
        btn_link.setFixedHeight(22)
        btn_link.setProperty("class", "FieldBtn")
        btn_link.setCursor(Qt.PointingHandCursor)
        btn_link.setToolTip("Vincular / Gerenciar")
        btn_link.setStyleSheet("font-size: 10px; font-weight: bold; padding: 0px;")
        btn_link.clicked.connect(lambda: self._toggle_link_drawer(field_id, drawer))
        layout.addWidget(btn_link)

        # Botão Validar
        btn_valid = QPushButton("Ok")
        btn_valid.setFixedSize(30, 22)
        btn_valid.setCheckable(True)
        btn_valid.setChecked(field_id in self.item_data.get('validated_fields', []))
        btn_valid.setProperty("class", "FieldBtn")
        btn_valid.setCursor(Qt.PointingHandCursor)
        btn_valid.setStyleSheet(f"""
            QPushButton {{ font-size: 10px; font-weight: bold; padding: 0px; }}
            QPushButton:checked {{ color: {Colors.ACCENT_SUCCESS}; border-color: {Colors.ACCENT_SUCCESS}; }}
        """)
        btn_valid.clicked.connect(lambda checked, f_id=field_id: self._on_express_validate(f_id))
        layout.addWidget(btn_valid)

        # Botão Zoom
        btn_zoom = QPushButton("Zoom")
        btn_zoom.setFixedSize(35, 22)
        btn_zoom.setProperty("class", "FieldBtn")
        btn_zoom.setCursor(Qt.PointingHandCursor)
        btn_zoom.setStyleSheet("font-size: 10px; font-weight: bold; padding: 0px;")
        btn_zoom.clicked.connect(lambda checked=False, f_id=field_id: self.focus_requested.emit(f_id))
        layout.addWidget(btn_zoom)

        # Botão N/A
        btn_na = QPushButton("N/A")
        btn_na.setFixedSize(30, 22)
        btn_na.setCheckable(True)
        btn_na.setChecked(field_id in self.item_data.get('na_fields', []))
        btn_na.setProperty("class", "FieldBtn")
        btn_na.setCursor(Qt.PointingHandCursor)
        btn_na.setStyleSheet(f"""
            QPushButton {{ font-size: 10px; font-weight: bold; padding: 0px; }}
            QPushButton:checked {{ color: {Colors.ACCENT_DANGER}; border-color: {Colors.ACCENT_DANGER}; }}
        """)
        btn_na.clicked.connect(lambda chk, f_id=field_id: self._on_na_clicked(f_id, chk))
        layout.addWidget(btn_na)

        # Registrar no mapa para atualizações de estilo
        self.action_btns[field_id] = {
            'link': btn_link,
            'express': btn_valid,
            'focus': btn_zoom,
            'na': btn_na
        }

        return container, drawer
