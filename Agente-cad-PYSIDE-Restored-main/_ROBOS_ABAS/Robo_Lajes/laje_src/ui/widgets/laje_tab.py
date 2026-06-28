from ..styles import DS
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                                QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QGroupBox,
                                QLineEdit, QMessageBox, QInputDialog, QCheckBox, QHeaderView,
                                QFrame, QTextEdit)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QColor, QFont
import re

def natural_key(text):
    """Chave para ordenação natural (1, 2, 10 em vez de 1, 10, 2)"""
    if not text:
        return []
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', str(text))]

def _fmt_pav_label(name: str) -> str:
    """Formata nome de pavimento para exibição: [BADGE]  nome — mesmo padrão do SA."""
    up = name.upper()
    short = re.sub(r'_R\d{4}_ASCII_ODA.*$', '', name, flags=re.I)
    short = re.sub(r'\.(DXF|DWG)$', '', short, flags=re.I).strip()
    m = re.search(r'[-_ ](\d{1,2})P(?:AV?|V)?(?:[-_ ]|$)', up)
    if not m: m = re.match(r'^(\d{1,2})\s*PAV', up)
    if not m: m = re.match(r'^PAV\s*(\d{1,2})(?:\s|$)', up)
    if m: return f"[{m.group(1)}º PAV]  {short}"
    if re.search(r'[-_]TER[-_]|TERREO|TÉRREO', up): return f"[TÉRREO]  {short}"
    if re.search(r'[-_]FUN[-_]|FUNDA', up): return f"[FUNDAÇÃO]  {short}"
    if re.search(r'[-_]TIP[-_]|TIPO', up): return f"[TIPO]  {short}"
    if re.search(r'[-_]COB[E_-]|COBER|DECK|BARR', up): return f"[COBERTURA]  {short}"
    if re.search(r'[-_]ATC[-_]|ATICO|ÁTICO', up): return f"[ÁTICO]  {short}"
    if re.search(r'[-_]SUB[-_]|SUBSOLO', up): return f"[SUBSOLO]  {short}"
    m_id = re.search(r'[-_](\d{3,5})[-_]', name)
    if m_id: return f"[{m_id.group(1)}]  {short}"
    return short

def _set_pav_cmb(cmb, raw: str):
    """Seleciona item de combobox pelo userData (raw pav name)."""
    for i in range(cmb.count()):
        if cmb.itemData(i) == raw:
            cmb.setCurrentIndex(i)
            return
    cmb.setCurrentText(raw)

def _pav_cmb_raw(cmb) -> str:
    """Retorna o nome raw do pavimento selecionado."""
    d = cmb.currentData()
    return d if d is not None else cmb.currentText()
from laje_src.services.geometry_calculator import (
    calculate_area, validate_polygon, extract_xy_only, calculate_dimensions, 
    is_valid_coordinate, MAX_POLYGON_POINTS, MAX_OBSTACULOS
)

# Import opcional do AutocadInterface
try:
    from laje_src.services.autocad_interface import AutocadInterface
except ImportError:
    # Se pyautocad não estiver instalado, criar classe stub
    class AutocadInterface:
        def __init__(self):
            pass
        def select_hatch(self):
            raise Exception("pyautocad não está instalado")
        def select_polylines(self):
            raise Exception("pyautocad não está instalado")
        def select_any_object(self):
            raise Exception("pyautocad não está instalado")
        def draw_lines(self, *args):
            raise Exception("pyautocad não está instalado")
from laje_src.models.laje import Laje
from laje_src.models.obra import Obra
from laje_src.models.pavimento import Pavimento
from laje_src.services.calculo_modo1 import calcular_modo1, calcular_modo2
from laje_src.utils.path_helper import PathHelper

class SortableTreeWidgetItem(QTreeWidgetItem):
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        text1 = self.text(column)
        text2 = other.text(column)
        
        # Ordenação natural para todas as colunas (especialmente Nº e Nome)
        return natural_key(text1) < natural_key(text2)

class LajeTab(QWidget):
    laje_selecionada = Signal(object, bool)  # laje, aplicar_correcoes_automaticas
    obra_changed = Signal(object)  # Emitir quando obra é alterada
    save_requested = Signal(object)  # Emitir para salvar sem recálculos
    save_requested = Signal(object)  # Emitir para salvar sem recálculos
    save_requested = Signal(object)  # Emitir para salvar sem recálculos
    lajes_deleted = Signal(list)  # Lista de objetos Laje que foram excluídos
    
    # Sinais de Feedback AI (Movidos da Toolbar)
    ai_feedback_approved = Signal()
    ai_feedback_manual = Signal()
    ai_feedback_errors = Signal(str)
    

    
    def __init__(self, linhas_config_widget=None):
        super().__init__()
# print("[DEBUG] LajeTab.__init__ CHAMADO! - Versão Com Debug de Exclusão (17:15)")
        self.obra_atual: Obra = None
        self.laje_atual: Laje = None
        self.autocad = AutocadInterface()
        self.linhas_config = linhas_config_widget  # Referência ao widget de linhas (deprecated)
        self.canvas_widget = None  # Referência ao canvas widget (para overlays)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Tabela de Lajes
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Rec", "Nº", "Nome", "Pav"])
        self.tree_widget.setColumnCount(4)
        
        # Configurar larguras das colunas
        header = self.tree_widget.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Rec
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Nº
        header.setSectionResizeMode(2, QHeaderView.Stretch)          # Nome (Expandir)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Pav
        
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree_widget.setSortingEnabled(True)
        self.tree_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # Ocultar scroll horizontal
        
        # Estilo premium FINAL da TreeWidget
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: {DS.DEEP};
                border: 1px solid {DS.BASE};
                border-radius: 4px;
                color: {DS.TEXT};
                outline: none;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 8px 4px;
                border-bottom: 1px solid {DS.BASE};
                height: 34px;
            }
            QTreeWidget::item:selected {
                background-color: rgba(102, 126, 234, int(12/100*255));
                color: {DS.WHITE};
                border-left: 3px solid {DS.PURPLE};
            }
            QTreeWidget::item:hover:!selected {
                background-color: {DS.DEEP};
            }
            QHeaderView {
                background-color: {DS.ELEVATED};
                border: none;
            }
            QHeaderView::section {
                background-color: {DS.ELEVATED};
                color: {DS.TEXT};
                padding: 6px 12px;
                border: none;
                border-right: 1px solid {DS.BORDER_STR};
                border-bottom: 1px solid {DS.BORDER_STR};
                font-weight: bold;
                font-size: 10px;
                text-transform: uppercase;
            }
            QTreeWidget::indicator:unchecked {
                border: 1px solid {DS.ELEVATED};
                background: {DS.DEEP};
                width: 15px;
                height: 15px;
                border-radius: 2px;
            }
            QTreeWidget::indicator:checked {
                border: 1px solid {DS.PURPLE};
                background: {DS.PURPLE};
                width: 15px;
                height: 15px;
                border-radius: 2px;
            }
            QScrollBar:vertical {
                background: {DS.DEEP};
                width: 4px;
            }
            QScrollBar::handle:vertical {
                background: {DS.BASE};
                border-radius: 2px;
            }
        """)
        self.tree_widget.setAlternatingRowColors(False)
        
        # Conectar seleção
        self.tree_widget.itemClicked.connect(lambda item, col: self.on_table_selection_changed())
        # NÃO adicionar ao layout - será adicionado na MainWindow como estava a tabela
        
        # Botão excluir (será movido para MainWindow, mas mantemos a referência aqui)
        self.delete_btn = QPushButton("🗑 EXCLUIR")
        self.delete_btn.clicked.connect(self.excluir_lajes_selecionadas)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {DS.DANGER}, stop:1 {DS.DANGER});
                color: white;
                border: none;
                border-radius: 3px;
                padding: 2px 8px;
                font-weight: 600;
                font-size: 9px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {DS.DANGER}, stop:1 {DS.DANGER});
            }
            QPushButton:pressed {
                background: {DS.DANGER};
            }
        """)
        # NÃO adicionar ao layout - será adicionado na MainWindow
        
        # Estilo do botão Salvar
        self.salvar_btn = QPushButton("💾 Salvar")
        self.salvar_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {DS.SUCCESS}, stop:1 {DS.SUCCESS});
                color: white;
                border: none;
                border-radius: 3px;
                padding: 2px 8px;
                font-weight: 600;
                font-size: 9px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {DS.SUCCESS}, stop:1 {DS.SUCCESS});
            }
            QPushButton:pressed {
                background: {DS.SUCCESS};
            }
        """)
        
        # Campos Individuais
        campos_group = QGroupBox("Dados da Laje")
        campos_layout = QVBoxLayout()
        
        # Botões AutoCAD
        autocad_layout = QHBoxLayout()
        self.btn_hatch = QPushButton("Boundary Cad")
        self.btn_poly = QPushButton("Linhas Cad")
        self.btn_any = QPushButton("Seleção Cad")
        
        self.btn_hatch.clicked.connect(lambda: self.selecionar_autocad("hatch"))
        self.btn_poly.clicked.connect(lambda: self.selecionar_autocad("polylines"))
        self.btn_any.clicked.connect(lambda: self.selecionar_autocad("any"))
        
        autocad_layout.addWidget(self.btn_hatch)
        autocad_layout.addWidget(self.btn_poly)
        autocad_layout.addWidget(self.btn_any)
        # Ocultar botões obsoletos
        self.btn_hatch.setVisible(False)
        self.btn_poly.setVisible(False)
        self.btn_any.setVisible(False)
        campos_layout.addLayout(autocad_layout)
        
        # Campos de entrada
        self.numero_edit = QLineEdit()
        self.nome_edit = QLineEdit()
        self.pavimento_combo = QComboBox()
        self.pavimento_combo.setEditable(True)  # Permitir edição para gerenciamento dinâmico
        
        campos_layout.addWidget(QLabel("Número:"))
        campos_layout.addWidget(self.numero_edit)
        campos_layout.addWidget(QLabel("Nome:"))
        campos_layout.addWidget(self.nome_edit)
        campos_layout.addWidget(QLabel("Pavimento:"))
        campos_layout.addWidget(self.pavimento_combo)
        
        # Conectar campo nome para atualizar canvas em tempo real
        self.nome_edit.textChanged.connect(self.on_nome_changed)
        
        # Conectar botão salvar (já criado acima com estilo)
        self.salvar_btn.clicked.connect(self.salvar_laje)
        # Botão salvar não fica no campos_layout - vai na lista de lajes
        
        # Botão Próxima Laje (Oculto a pedido do usuário)
        self.proxima_btn = QPushButton("Próxima Laje")
        self.proxima_btn.clicked.connect(self.salvar_e_limpar)
        
        # Botão Nova Laje
        self.nova_laje_btn = QPushButton("Nova Laje")
        self.nova_laje_btn.clicked.connect(self.nova_laje)
        
        # Botão Seleção Múltipla (selecionar várias lajes de uma vez)
        self.selecao_multipla_btn = QPushButton("🎯 Seleção Múltipla")
        self.selecao_multipla_btn.clicked.connect(self.selecionar_multiplas_lajes)
        
        # Botão Criar Comando LISP
        self.criar_lisp_btn = QPushButton("Criar Comando LISP")
        self.criar_lisp_btn.clicked.connect(self.criar_comando_lisp)
        
        campos_group.setLayout(campos_layout)
        layout.addWidget(campos_group)
        
        # Seção Opções de Desenho
        opcoes_desenho_group = QGroupBox("Opções de Desenho")
        opcoes_desenho_layout = QVBoxLayout()
        
        # Seção Opções
        opcoes_label = QLabel("Opções:")
        opcoes_desenho_layout.addWidget(opcoes_label)
        
        # Carregar configurações
        settings = QSettings("LajesApp", "Config")
        
        # Checkbox 1 - Desenhar com Nomes dos Painéis
        self.checkbox_nomes_paineis = QCheckBox("Desenhar com Nomes dos Painéis")
        self.checkbox_nomes_paineis.setChecked(settings.value("desenhar_nomes_paineis", True, type=bool))
        self.checkbox_nomes_paineis.stateChanged.connect(self.salvar_preferencias_desenho)
        opcoes_desenho_layout.addWidget(self.checkbox_nomes_paineis)
        
        # Checkbox 2 - Desenhar com nomes dos Reaproveitamento
        self.checkbox_nomes_reaproveitamento = QCheckBox("Desenhar com nomes dos Reaproveitamento")
        self.checkbox_nomes_reaproveitamento.setChecked(settings.value("desenhar_nomes_reaproveitamento", False, type=bool))
        self.checkbox_nomes_reaproveitamento.stateChanged.connect(self.salvar_preferencias_desenho)
        opcoes_desenho_layout.addWidget(self.checkbox_nomes_reaproveitamento)
        
        # Checkbox 3 - Desenhar com Hatchs dos Reaproveitamentos
        self.checkbox_hatchs_reaproveitamento = QCheckBox("Desenhar com Hatchs dos Reaproveitamentos")
        self.checkbox_hatchs_reaproveitamento.setChecked(settings.value("desenhar_hatchs_reaproveitamento", False, type=bool))
        self.checkbox_hatchs_reaproveitamento.stateChanged.connect(self.salvar_preferencias_desenho)
        opcoes_desenho_layout.addWidget(self.checkbox_hatchs_reaproveitamento)
        
        # Checkbox 4 - Desenhar com marco da Laje
        self.checkbox_marco_laje = QCheckBox("Desenhar com marco da Laje")
        self.checkbox_marco_laje.setChecked(settings.value("desenhar_marco_laje", True, type=bool))
        self.checkbox_marco_laje.stateChanged.connect(self.salvar_preferencias_desenho)
        opcoes_desenho_layout.addWidget(self.checkbox_marco_laje)
        
        # Checkbox 5 - Desenhar Unioes com Hatch
        self.checkbox_unioes_hatch = QCheckBox("Desenhar Unioes com Hatch")
        self.checkbox_unioes_hatch.setChecked(settings.value("desenhar_unioes_hatch", True, type=bool))
        self.checkbox_unioes_hatch.stateChanged.connect(self.salvar_preferencias_desenho)
        opcoes_desenho_layout.addWidget(self.checkbox_unioes_hatch)
        
        # Checkbox 6 - Cotas Automáticas (Rosa)
        self.checkbox_cotas_automaticas = QCheckBox("Cotas Automáticas (Pink)")
        self.checkbox_cotas_automaticas.setChecked(settings.value("desenhar_cotas_automaticas", True, type=bool))
        self.checkbox_cotas_automaticas.stateChanged.connect(self.salvar_preferencias_desenho)
        opcoes_desenho_layout.addWidget(self.checkbox_cotas_automaticas)
        

        
        # Botões de desenhar (Ocultos a pedido do usuário)
        self.desenhar_cad_btn = QPushButton("Desenhar Laje no CAD")
        self.desenhar_cad_btn.clicked.connect(self.desenhar_laje_cad)
        
        self.desenhar_pavimento_btn = QPushButton("Desenhar Pavimento no CAD")
        self.desenhar_pavimento_btn.clicked.connect(self.desenhar_pavimento_cad)
        
        self.desenhar_obra_btn = QPushButton("Desenhar Obra no CAD")
        self.desenhar_obra_btn.clicked.connect(self.desenhar_obra_cad)
        
        self.config_btn = QPushButton("Configurações")
        self.config_btn.clicked.connect(self.abrir_configuracoes)
        
        opcoes_desenho_group.setLayout(opcoes_desenho_layout)
        layout.addWidget(opcoes_desenho_group)
        
        # Area para Feedback da IA (Container)
        self.feedback_container = QWidget()
        self.feedback_layout = QVBoxLayout(self.feedback_container)
        self.feedback_layout.setContentsMargins(0, 5, 0, 0)
        self.feedback_layout.setSpacing(0)
        layout.addWidget(self.feedback_container)
        self.feedback_widget_current = None
        
        layout.addStretch()
        
        # Aplicar configurações iniciais ao canvas (se já estiver conectado)
        # Mas canvas_widget é definido depois, então não podemos fazer aqui.
        # Será feito quando on_table_selection_changed for chamado ou quando canvas_widget for setado.
    
    def salvar_preferencias_desenho(self):
        """Salva as preferências de desenho no QSettings"""
        settings = QSettings("LajesApp", "Config")
        settings.setValue("desenhar_nomes_paineis", self.checkbox_nomes_paineis.isChecked())
        settings.setValue("desenhar_nomes_reaproveitamento", self.checkbox_nomes_reaproveitamento.isChecked())
        settings.setValue("desenhar_hatchs_reaproveitamento", self.checkbox_hatchs_reaproveitamento.isChecked())
        settings.setValue("desenhar_marco_laje", self.checkbox_marco_laje.isChecked())
        settings.setValue("desenhar_unioes_hatch", self.checkbox_unioes_hatch.isChecked())
        settings.setValue("desenhar_cotas_automaticas", self.checkbox_cotas_automaticas.isChecked())
        
        # Atualizar canvas imediatamente
        self.atualizar_visualizacao_canvas()
    
    def atualizar_visualizacao_canvas(self):
        """Atualiza a visualização no canvas com base nas opções (aplicado globalmente)"""
        if self.canvas_widget:
            # Criar dicionário com todas as opções de desenho
            opcoes = {
                "nomes_paineis": self.checkbox_nomes_paineis.isChecked(),
                "nomes_reaproveitamento": self.checkbox_nomes_reaproveitamento.isChecked(),
                "hatches_reaproveitamento": self.checkbox_hatchs_reaproveitamento.isChecked(),
                "marco_laje": self.checkbox_marco_laje.isChecked(),
                "unioes_hatch": self.checkbox_unioes_hatch.isChecked(),
                "cotas_automaticas": self.checkbox_cotas_automaticas.isChecked()
            }
            # Aplicar opções globalmente ao canvas (afeta todos os modos)
            self.canvas_widget.set_opcoes_desenho(opcoes)
    
    def get_opcoes_desenho(self) -> dict:
        """Retorna as opções de desenho atuais"""
        return {
            "nomes_paineis": self.checkbox_nomes_paineis.isChecked(),
            "nomes_reaproveitamento": self.checkbox_nomes_reaproveitamento.isChecked(),
            "hatches_reaproveitamento": self.checkbox_hatchs_reaproveitamento.isChecked(),
            "marco_laje": self.checkbox_marco_laje.isChecked(),
            "unioes_hatch": self.checkbox_unioes_hatch.isChecked()
        }
    
    def on_obra_changed(self, obra: Obra):
        """Atualiza quando obra é alterada (chamado externamente)"""
        self.obra_atual = obra
        if self.obra_atual:
            # PRESERVAR pavimento selecionado antes de atualizar combo
            pavimento_selecionado_anterior = _pav_cmb_raw(self.pavimento_combo)

            # Bloquear sinais para evitar loops
            self.pavimento_combo.blockSignals(True)
            try:
                # Atualizar combo de pavimentos
                self.pavimento_combo.clear()
                for pavimento in self.obra_atual.pavimentos:
                    self.pavimento_combo.addItem(_fmt_pav_label(pavimento.nome), pavimento.nome)

                # Tentar manter o pavimento selecionado anteriormente
                if pavimento_selecionado_anterior:
                    # Verificar se o pavimento ainda existe
                    pavimento_existe = any(p.nome == pavimento_selecionado_anterior for p in self.obra_atual.pavimentos)
                    if pavimento_existe:
                        _set_pav_cmb(self.pavimento_combo, pavimento_selecionado_anterior)
                        # Atualizar tabela com lajes do pavimento preservado
                        pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == pavimento_selecionado_anterior), None)
                        if pavimento:
                            self._populate_tree(pavimento.lajes)
                    else:
                        # Se não existe mais, usar primeiro pavimento
                        if self.obra_atual.pavimentos:
                            primeiro_pav = self.obra_atual.pavimentos[0]
                            _set_pav_cmb(self.pavimento_combo, primeiro_pav.nome)
                            self._populate_tree(primeiro_pav.lajes)
                        else:
                            self._populate_tree([])
                else:
                    # Se não havia seleção anterior, usar primeiro pavimento
                    if self.obra_atual.pavimentos:
                        primeiro_pav = self.obra_atual.pavimentos[0]
                        _set_pav_cmb(self.pavimento_combo, primeiro_pav.nome)
                        self._populate_tree(primeiro_pav.lajes)
                    else:
                        self._populate_tree([])
            finally:
                self.pavimento_combo.blockSignals(False)
            
            # NÃO emitir obra_changed aqui para evitar loop infinito
            # self.obra_changed.emit(self.obra_atual)
            


    def _populate_tree(self, lajes: list[Laje]):
        """Popula a árvore de lajes SEM agrupamento (Lista Plana)"""
        self.tree_widget.clear()
        
        # Ordenar lajes por número e nome (natural sort)
        sorted_lajes = sorted(lajes, key=lambda x: (x.numero, natural_key(x.nome)))
        
        for laje in sorted_lajes:
            # Criar item diretamente na raiz (sem grupos)
            item = SortableTreeWidgetItem(self.tree_widget)
            
            # Rec column (0)
            rec_text = "R" if getattr(laje, 'reaproveitamento_dados', None) else ""
            item.setText(0, rec_text)
            item.setTextAlignment(0, Qt.AlignCenter)
            
            # N (1)
            item.setText(1, str(laje.numero))
            item.setTextAlignment(1, Qt.AlignCenter)
            
            # Nome (2)
            item.setText(2, laje.nome or "")
            
            # Pav (3)
            item.setText(3, laje.pavimento or "")
            
            # Armazenar objeto laje
            item.setData(0, Qt.UserRole, laje)
            
            # Estilo alternado sutil (opcional, já que setAlternatingRowColors é False)
            # Vamos manter simples por enquanto


    def atualizar_tabela_lajes(self):
        """Atualiza a tabela de lajes com base no pavimento selecionado"""
        if not self.obra_atual:
            self._populate_tree([])
            return
        
        # Obter pavimento selecionado
        pavimento_nome = _pav_cmb_raw(self.pavimento_combo)
        if not pavimento_nome:
            self._populate_tree([])
            return
        
        # Encontrar pavimento
        pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == pavimento_nome), None)
        if pavimento:
            self._populate_tree(pavimento.lajes)
        else:
            self._populate_tree([])
    
    def on_table_selection_changed(self):
        """Carrega canvas quando um item da tabela é selecionado"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return

        # Encontrar primeiro item selecionado que seja laje (tenha data)
        laje = None
        for item in selected_items:
            data = item.data(0, Qt.UserRole)
            if data:
                laje = data
                break
        
        # Se selecionou grupo, ignorar
        if not laje:
            return

        if laje and self.obra_atual:
            # Usar laje direta do item
            # índice / lista não é mais relevante diretamente pois temos o objeto
            
            # Se a laje selecionada é a mesma que já está em self.laje_atual, preservar obstáculos
            if (self.laje_atual and 
                self.laje_atual.numero == laje.numero and 
                self.laje_atual.nome == laje.nome and
                self.laje_atual.pavimento == laje.pavimento):
                # Preservar obstáculos da laje atual antes de substituir
                obstaculos_preservados = getattr(self.laje_atual, 'obstaculos', [])
                laje.obstaculos = obstaculos_preservados
            
            # Carregar dados da laje nos campos
            self.numero_edit.setText(str(laje.numero))
            # Bloquear sinal temporariamente para evitar loop ao carregar
            self.nome_edit.blockSignals(True)
            self.nome_edit.setText(laje.nome)
            self.nome_edit.blockSignals(False)
            _set_pav_cmb(self.pavimento_combo, laje.pavimento)
            # Definir laje atual
            self.laje_atual = laje
            # Verificar obstáculos na laje carregada
            obstaculos = getattr(laje, 'obstaculos', [])
            # Emitir sinal para atualizar canvas (carregar desenho salvo)
            # Não aplicar correções automáticas ao selecionar na lista
            self.laje_selecionada.emit(laje, False)
            
            # Atualizar visualização do canvas com as opções atuais
            self.atualizar_visualizacao_canvas()
    
    def on_nome_changed(self, text: str):
        """Atualiza o nome da laje no canvas quando o campo nome é alterado"""
        if not self.laje_atual:
            return
        
        # Atualizar nome na laje atual (mesmo se vazio)
        nome_limpo = text.strip()
        self.laje_atual.nome = nome_limpo if nome_limpo else ""
        
        # Atualizar canvas para redesenhar o nome (ou remover se vazio)
        if self.canvas_widget:
            # Atualizar a visualização do canvas
            # O método atualizar_visualizacao já trata o caso de nome vazio
            self.canvas_widget.atualizar_visualizacao()
    
    def salvar_laje(self, update_ui=True):
        """Salva laje atual sem limpar campos e SEM recalcular nada"""
        if not self.obra_atual:
            QMessageBox.warning(self, "Aviso", "Selecione ou crie uma obra primeiro.")
            return
        
        # Validar se nome e número estão preenchidos
        nome = self.nome_edit.text().strip()
        numero_texto = self.numero_edit.text().strip()
        
        if not nome or not numero_texto:
            return
        
        # Obter linhas diretamente dos overlays do canvas (o que está visível na tela)
        # Isso garante que estamos salvando exatamente o que o usuário vê
        verticais = []
        horizontais = []
        if self.canvas_widget:
            verticais = self.canvas_widget.vertical_lines_overlay.get_linhas()
            horizontais = self.canvas_widget.horizontal_lines_overlay.get_linhas()
        elif self.laje_atual:
            # Fallback: usar linhas da laje se canvas não disponível
            verticais = self.laje_atual.linhas_verticais if self.laje_atual.linhas_verticais else []
            horizontais = self.laje_atual.linhas_horizontais if self.laje_atual.linhas_horizontais else []
        
        # Obter modo e checkbox de uniões nos bordes do canvas
        modo_selecionado = 0
        unioes_nos_bordes = False
        if self.canvas_widget and self.canvas_widget.calculos_modos:
            # Verificar qual modo está selecionado
            for i, btn in enumerate(self.canvas_widget.calculos_modos.buttons):
                if btn.isChecked():
                    modo_selecionado = i
                    break
            unioes_nos_bordes = self.canvas_widget.calculos_modos.unioes_nos_bordes_ativado()
        
        # Criar ou atualizar laje atual
        if not self.laje_atual:
            # Fazer cópias das listas para evitar referências compartilhadas
            verticais_copy = list(verticais) if verticais else []
            horizontais_copy = list(horizontais) if horizontais else []
            # Criar nova laje com todos os detalhes
            self.laje_atual = Laje(
                numero=int(self.numero_edit.text() or "0"),
                nome=self.nome_edit.text() or "",
                comprimento=0.0,
                largura=0.0,
                pavimento=_pav_cmb_raw(self.pavimento_combo) or "",
                linhas_verticais=verticais_copy,
                linhas_horizontais=horizontais_copy,
                modo_selecionado=modo_selecionado,
                unioes_nos_bordes=unioes_nos_bordes
            )
            
            # Salvar cotas manuais da scene se existirem
            if self.canvas_widget and hasattr(self.canvas_widget.scene, 'manual_dimension_data'):
                manual_dims = []
                for dim_text, dim_data in self.canvas_widget.scene.manual_dimension_data.items():
                    try:
                        # Verificar se a cota ainda existe na cena
                        if dim_text.scene() is not None:
                            # Criar dicionário serializável (sem referências a objetos Qt)
                            dim_dict = {
                                "unique_id": dim_data.get("unique_id", ""),
                                "line_coords": list(dim_data.get("line_coords", (0, 0, 0, 0))),
                                "value": dim_text.toPlainText(),
                                "pos_x": dim_data.get("pos_x", 0),
                                "pos_y": dim_data.get("pos_y", 0),
                                "rotation": dim_data.get("rotation", 0),
                                "length": dim_data.get("length", 0),
                                "is_marco_special": getattr(dim_text, 'is_marco_special', False)
                            }
                            print(f"[DEBUG SAVE MANUAL] Text='{dim_text.toPlainText()}' ID={dim_dict.get('unique_id')} SavedVal={dim_dict['value']}")
                            manual_dims.append(dim_dict)
                    except (RuntimeError, AttributeError):
                        # Cota foi deletada, pular
                        continue
                self.laje_atual.manual_dimensions = manual_dims
        else:
            # Atualizar dados da laje
            # Preservar obstáculos antes de atualizar (sempre preservar, não limpar)
            obstaculos_preservados = getattr(self.laje_atual, 'obstaculos', [])
            # Preservar cotas excluídas antes de atualizar
            excluded_dimensions_preservados = getattr(self.laje_atual, 'excluded_dimensions', [])
            # Preservar cotas manuais antes de atualizar (serão atualizadas depois se houver novas)
            manual_dimensions_preservados = getattr(self.laje_atual, 'manual_dimensions', [])
            # Preservar posições das cotas movidas (IMPORTANTE: fazer cópia profunda)
            dimension_positions_preservados = {}
            if hasattr(self.laje_atual, 'dimension_positions') and self.laje_atual.dimension_positions:
                # Fazer cópia profunda do dicionário
                from copy import deepcopy
                dimension_positions_preservados = deepcopy(self.laje_atual.dimension_positions)
# print(f"[DEBUG] Preservando {len(dimension_positions_preservados)} posições de cotas")
            
            self.laje_atual.numero = int(self.numero_edit.text() or "0")
            self.laje_atual.nome = self.nome_edit.text() or ""
            self.laje_atual.pavimento = _pav_cmb_raw(self.pavimento_combo) or ""
            # Atualizar linhas (fazer cópias para evitar referências compartilhadas)
            self.laje_atual.linhas_verticais = list(verticais) if verticais else []
            self.laje_atual.linhas_horizontais = list(horizontais) if horizontais else []
            # Preservar cotas excluídas
            self.laje_atual.excluded_dimensions = excluded_dimensions_preservados
            # Preservar posições das cotas movidas (já são atualizadas automaticamente via itemChange)
            # IMPORTANTE: Mesclar com posições existentes, não substituir
            if not hasattr(self.laje_atual, 'dimension_positions'):
                self.laje_atual.dimension_positions = {}
            # Mesclar posições preservadas com as atuais (atualizadas via itemChange)
            self.laje_atual.dimension_positions.update(dimension_positions_preservados)
# print(f"[DEBUG] Posições de cotas após mesclar: {len(self.laje_atual.dimension_positions)}")
            
            # Salvar cotas manuais da scene (atualizar com as atuais)
            if self.canvas_widget and hasattr(self.canvas_widget.scene, 'manual_dimension_data'):
                manual_dims = []
                for dim_text, dim_data in self.canvas_widget.scene.manual_dimension_data.items():
                    try:
                        # Verificar se a cota ainda existe na cena
                        if dim_text.scene() is not None:
                            # Criar dicionário serializável (sem referências a objetos Qt)
                            dim_dict = {
                                "unique_id": dim_data.get("unique_id", ""),
                                "line_coords": list(dim_data.get("line_coords", (0, 0, 0, 0))),
                                "value": dim_text.toPlainText(),
                                "pos_x": dim_data.get("pos_x", 0),
                                "pos_y": dim_data.get("pos_y", 0),
                                "rotation": dim_data.get("rotation", 0),
                                "length": dim_data.get("length", 0),
                                "is_marco_special": getattr(dim_text, 'is_marco_special', False)
                            }
                            print(f"[DEBUG SAVE MANUAL UPD] Text='{dim_text.toPlainText()}' ID={dim_dict.get('unique_id')} SavedVal={dim_dict['value']}")
                            manual_dims.append(dim_dict)
                    except (RuntimeError, AttributeError):
                        # Cota foi deletada, pular
                        continue
                self.laje_atual.manual_dimensions = manual_dims
            else:
                # Se não houver canvas, preservar as cotas manuais existentes
                self.laje_atual.manual_dimensions = manual_dimensions_preservados
            # Atualizar modo e checkbox de uniões nos bordes
            self.laje_atual.modo_selecionado = modo_selecionado
            self.laje_atual.unioes_nos_bordes = unioes_nos_bordes
            # SEMPRE preservar obstáculos (não limpar durante atualização)
            self.laje_atual.obstaculos = obstaculos_preservados
        
        # Calcular dimensões a partir das coordenadas se existirem
        if self.laje_atual.coordenadas:
            # Calcular dimensões usando bounding box do polígono shapely
            self.laje_atual.comprimento, self.laje_atual.largura = calculate_dimensions(self.laje_atual.coordenadas)
        
        # IMPORTANTE: Sincronizar cotas excluídas e posições da cena para o modelo antes de salvar
        # Isso garante que as decisões da IA (quais cotas manter/ocultar) sejam persistidas
        if self.canvas_widget and hasattr(self.canvas_widget, 'sync_manual_dimensions_to_model'):
            self.canvas_widget.sync_manual_dimensions_to_model()
            # Também sincronizar dimension_positions da cena se existir
            if hasattr(self.canvas_widget.scene, 'excluded_dimensions'):
                # Garantir que excluded_dimensions do modelo está sincronizado com a cena
                if not hasattr(self.laje_atual, 'excluded_dimensions'):
                    self.laje_atual.excluded_dimensions = []
                # Atualizar com as exclusões da cena (que refletem as decisões da IA)
                self.laje_atual.excluded_dimensions = list(self.canvas_widget.scene.excluded_dimensions)
        
        # Encontrar ou criar pavimento
        pavimento_nome = self.laje_atual.pavimento
        if pavimento_nome:
            pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == pavimento_nome), None)
            if not pavimento:
                pavimento = Pavimento(nome=pavimento_nome)
                self.obra_atual.pavimentos.append(pavimento)
                self.pavimento_combo.addItem(_fmt_pav_label(pavimento_nome), pavimento_nome)
            
            # Verificar se laje já existe no pavimento (apenas por número)
            # Corrigido: antes verificava número E nome, causando duplicação quando nome mudava
            laje_existente = next(
                (l for l in pavimento.lajes 
                 if l.numero == self.laje_atual.numero),
                None
            )
            
            if laje_existente:
                # Atualizar laje existente com todos os dados (Cópia COMPLETA para evitar perda de dados)
                from copy import deepcopy
                laje_existente.nome = self.laje_atual.nome
                laje_existente.coordenadas = list(self.laje_atual.coordenadas) if self.laje_atual.coordenadas else []
                laje_existente.area_cm2 = self.laje_atual.area_cm2
                laje_existente.comprimento = self.laje_atual.comprimento
                laje_existente.largura = self.laje_atual.largura
                laje_existente.linhas_verticais = list(verticais) if verticais else []
                laje_existente.linhas_horizontais = list(horizontais) if horizontais else []
                laje_existente.modo_selecionado = modo_selecionado
                laje_existente.unioes_nos_bordes = unioes_nos_bordes
                laje_existente.observacoes = getattr(self.laje_atual, 'observacoes', "")
                
                # Campos complexos com deepcopy
                laje_existente.obstaculos = deepcopy(getattr(self.laje_atual, 'obstaculos', []))
                laje_existente.reaproveitamento_dados = deepcopy(getattr(self.laje_atual, 'reaproveitamento_dados', {}))
                laje_existente.sobras_recebidas = deepcopy(getattr(self.laje_atual, 'sobras_recebidas', []))
                laje_existente.excluded_dimensions = deepcopy(getattr(self.laje_atual, 'excluded_dimensions', []))
                laje_existente.manual_dimensions = deepcopy(getattr(self.laje_atual, 'manual_dimensions', []))
                laje_existente.marco_joined_positions = deepcopy(getattr(self.laje_atual, 'marco_joined_positions', {"vertical": [], "horizontal": []}))
                laje_existente.dimension_positions = deepcopy(getattr(self.laje_atual, 'dimension_positions', {}))
                
                # Atualizar referência para apontar para a laje na lista
                self.laje_atual = laje_existente
                if self.canvas_widget:
                    self.canvas_widget.laje_atual = laje_existente
            else:
                # Adicionar nova laje ao pavimento (apenas se não existe com mesmo número)
                pavimento.lajes.append(self.laje_atual)
        
        # Atualizar tabela apenas com lajes do pavimento atual
        if update_ui:
            pavimento_atual = next(
                (p for p in self.obra_atual.pavimentos if p.nome == _pav_cmb_raw(self.pavimento_combo)),
                None
            )
            if pavimento_atual:
                self._populate_tree(pavimento_atual.lajes)


        
        # IMPORTANTE: Salvar apenas o arquivo, SEM disparar recálculos ou atualizações de widgets
        # Usar sinal save_requested que apenas salva sem recálculos
        self.save_requested.emit(self.obra_atual)
# print(f"  - Obstáculos: {len(getattr(self.laje_atual, 'obstaculos', []))}")
    
    def selecionar_autocad(self, method: str, aplicar_correcoes_automaticas: bool = True):
        """Seleciona laje no AutoCAD usando método especificado
        
        Args:
            method: Método de seleção ("hatch", "polylines", "any")
            aplicar_correcoes_automaticas: Se True (padrão), executa interpretação inteligente automática
        """
        # Verificar se já existe uma laje com coordenadas e pedir confirmação
        if self.laje_atual and self.laje_atual.coordenadas:
            reply = QMessageBox.question(
                self,
                "Confirmar Nova Seleção",
                "A seleção atual será perdida e sobreposta pela nova seleção.\n\nDeseja continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        try:
            if method == "hatch":
                # select_hatch agora faz boundary E seleção de texto em sequência
                resultado = self.autocad.select_hatch()
                
                # Trazer interface para frente e maximizar (SEM minimizar o CAD)
                main_window = self.window()
                if main_window:
                    main_window.showMaximized()
                    main_window.raise_()
                    main_window.activateWindow()
                    # Garantir que a janela fique no topo
                    from PySide6.QtCore import Qt
                    current_state = main_window.windowState()
                    main_window.setWindowState(current_state & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
                    main_window.raise_()
                    main_window.activateWindow()
                
                # select_hatch agora retorna (coordenadas, obstaculos, texto_nome)
                obstaculos = []  # Inicializar sempre
                texto_nome = ""  # Inicializar sempre
                if isinstance(resultado, tuple) and len(resultado) == 3:
                    coordenadas, obstaculos, texto_nome = resultado
                    # NÃO preencher campo nome aqui - será preenchido quando criar a nova laje
                    # Isso evita que o nome seja perdido se o campo já foi limpo
                elif isinstance(resultado, tuple) and len(resultado) == 2:
                    # Compatibilidade com versão antiga (coordenadas, texto_nome)
                    coordenadas, texto_nome = resultado
                    obstaculos = []
                    # NÃO preencher campo nome aqui - será preenchido quando criar a nova laje
                else:
                    # Compatibilidade com versão muito antiga (apenas coordenadas)
                    coordenadas = resultado
                    obstaculos = []
                    texto_nome = ""
            elif method == "polylines":
                coordenadas = self.autocad.select_polylines()
                obstaculos = []  # Polylines não têm obstáculos
            else:  # any
                coordenadas = self.autocad.select_any_object()
                obstaculos = []  # Any não tem obstáculos
            
            # Extrair apenas X,Y
            coordenadas = extract_xy_only(coordenadas)
            
            # Para "any", apenas desenhar no canvas sem validar como polígono
            if method == "any":
                # Criar ou atualizar laje atual apenas para desenhar no canvas
                if not self.laje_atual:
                    self.laje_atual = Laje(
                        numero=int(self.numero_edit.text() or "0"),
                        nome=self.nome_edit.text() or "",
                        comprimento=0.0,
                        largura=0.0,
                        pavimento=""
                    )
                
                # Armazenar todas as coordenadas para desenhar no canvas
                self.laje_atual.coordenadas = coordenadas
                self.laje_atual.area_cm2 = 0.0  # Não calcular área para múltiplos objetos
                
                # Emitir sinal para atualizar canvas (desenhar tudo)
                # Não aplicar correções automáticas para método "any"
                self.laje_selecionada.emit(self.laje_atual, False)
                return
            
            # Para hatch e polylines, validar como polígono
            if not validate_polygon(coordenadas):
                QMessageBox.warning(self, "Erro",
                    "Geometria inválida. Por favor, selecione novamente ou use outro método.")
                return
            
            # Calcular área
            area_cm2 = calculate_area(coordenadas)
            
            # Atualizar campos
            # Calcular dimensões a partir das coordenadas
            comprimento = 0.0
            largura = 0.0
            if coordenadas:
                # Calcular dimensões usando bounding box do polígono shapely
                comprimento, largura = calculate_dimensions(coordenadas)
            
            # IMPORTANTE: Se o texto do AutoCAD foi obtido, usar ele como nome
            # Caso contrário, usar o nome do campo (que pode estar vazio se for nova laje)
            nome_laje = texto_nome if texto_nome else (self.nome_edit.text() or "")
            
            # Armazenar coordenadas na laje atual
            # IMPORTANTE: Sempre criar nova laje limpa (não reutilizar laje anterior)
            # Isso evita que dados da laje anterior sejam herdados
            self.laje_atual = Laje(
                numero=int(self.numero_edit.text() or "0"),
                nome=nome_laje,  # Usar nome do texto do AutoCAD ou do campo
                comprimento=comprimento,
                largura=largura,
                pavimento=""
            )
            
            # Atualizar campo nome com o nome da laje (que pode vir do texto do AutoCAD)
            if nome_laje:
                self.nome_edit.blockSignals(True)
                self.nome_edit.setText(nome_laje)
                self.nome_edit.blockSignals(False)
            else:
                # Se não há nome, limpar o campo (para próxima laje)
                self.nome_edit.clear()
            
            # Garantir que a nova laje comece COMPLETAMENTE limpa (sem dados da anterior)
            self.laje_atual.coordenadas = coordenadas
            self.laje_atual.area_cm2 = area_cm2
            self.laje_atual.linhas_verticais = []
            self.laje_atual.linhas_horizontais = []
            self.laje_atual.dimension_positions = {}  # Garantir que comece vazio
            self.laje_atual.manual_dimensions = []  # IMPORTANTE: Limpar cotas manuais da laje anterior
            self.laje_atual.excluded_dimensions = []  # Limpar cotas excluídas
            self.laje_atual.marco_joined_positions = {"vertical": [], "horizontal": []}  # Limpar joins
            # Armazenar obstáculos se existirem (apenas para método hatch)
            if method == "hatch":
                self.laje_atual.obstaculos = obstaculos if obstaculos else []
            else:
                self.laje_atual.obstaculos = []
            
            # IMPORTANTE: Garantir que o canvas está completamente limpo antes de desenhar a nova laje
            # Isso evita que cotas manuais da laje anterior sejam herdadas
            if self.canvas_widget and hasattr(self.canvas_widget, 'scene'):
                # Limpar listas de cotas manuais novamente (por segurança)
                self.canvas_widget.scene.manual_dimension_texts.clear()
                self.canvas_widget.scene.manual_dimension_data.clear()
            
            # Salvar automaticamente após selecionar (apenas se houver obra selecionada)
            if self.obra_atual:
                try:
                    self.salvar_laje()
                    # A seleção na tabela e sincronização de obstáculos é feita pelo salvar_laje()
                except Exception as e:
                    import traceback
                    traceback.print_exc()
            
            # Emitir sinal para atualizar canvas e disparar a interpretação inteligente
            # Passar flag True para aplicar as correções inteligentes via LayoutLearner
            self.laje_selecionada.emit(self.laje_atual, aplicar_correcoes_automaticas)
            
        except Exception as e:
            QMessageBox.critical(self, "Erro AutoCAD",
                f"Erro ao conectar ao AutoCAD: {str(e)}")
    
    def salvar_e_limpar(self):
        """Apenas ATUALIZA laje atual (se existir), depois limpa campos para nova entrada (Botão Próxima Laje)
        
        IMPORTANTE: Este método NÃO cria novas lajes - apenas atualiza existentes.
        A criação de nova laje acontece dentro de selecionar_autocad quando o usuário
        seleciona um novo hatch no CAD.
        """
        if not self.obra_atual:
            QMessageBox.warning(self, "Aviso", "Selecione ou crie uma obra primeiro.")
            return
        
        # Obter pavimento atual
        pavimento_nome = _pav_cmb_raw(self.pavimento_combo) or ""
        if not pavimento_nome:
            QMessageBox.warning(self, "Aviso", "Selecione um pavimento primeiro.")
            return
        
        # Encontrar pavimento (não criar novo)
        pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == pavimento_nome), None)
        if not pavimento:
            # Se pavimento não existe, apenas criar ele vazio (sem lajes)
            pavimento = Pavimento(nome=pavimento_nome)
            self.obra_atual.pavimentos.append(pavimento)
            self.pavimento_combo.addItem(_fmt_pav_label(pavimento_nome), pavimento_nome)

        # IMPORTANTE: Salvar dados da laje atual ANTES de limpar campos
        # Preservar nome e número antes de limpar
        nome_atual = self.nome_edit.text() or ""
        numero_atual = int(self.numero_edit.text() or "0")
        laje_atual_backup = self.laje_atual  # Backup da laje atual
        
        # APENAS ATUALIZAR laje atual se ela JÁ EXISTIR no pavimento
        # NÃO criar nova laje aqui - isso evita duplicação
        if laje_atual_backup and laje_atual_backup.coordenadas:
            # Verificar se a laje REALMENTE já existe no pavimento
            laje_existente = next(
                (l for l in pavimento.lajes if l.numero == numero_atual),
                None
            )
            
            # APENAS atualizar se existir - NUNCA criar nova aqui
            if laje_existente:
                # IMPORTANTE: Salvar manual_dimensions ANTES de limpar canvas
                # Obter cotas manuais do canvas se disponível
                manual_dimensions_preservados = []
                if self.canvas_widget and self.canvas_widget.scene:
                    # Obter cotas manuais da scene
                    manual_dims = []
                    for dim_text, dim_data in self.canvas_widget.scene.manual_dimension_data.items():
                        if dim_data:
                            manual_dims.append({
                                "unique_id": dim_data.get("unique_id", ""),
                                "line_coords": dim_data.get("line_coords", (0, 0, 0, 0)),
                                "value": dim_data.get("length", 0),
                                "pos_x": dim_data.get("pos_x", 0),
                                "pos_y": dim_data.get("pos_y", 0),
                                "rotation": dim_data.get("rotation", 0),
                                "length": dim_data.get("length", 0)
                            })
                    manual_dimensions_preservados = manual_dims
                elif hasattr(laje_atual_backup, 'manual_dimensions') and laje_atual_backup.manual_dimensions:
                    from copy import deepcopy
                    manual_dimensions_preservados = deepcopy(laje_atual_backup.manual_dimensions)
                
                # Atualizar com dados PRESERVADOS (antes de limpar)
                laje_existente.nome = nome_atual  # IMPORTANTE: usar nome preservado
                laje_existente.coordenadas = list(laje_atual_backup.coordenadas)
                laje_existente.area_cm2 = laje_atual_backup.area_cm2
                # Calcular dimensões usando bounding box do polígono shapely
                laje_existente.comprimento, laje_existente.largura = calculate_dimensions(laje_atual_backup.coordenadas)
                laje_existente.linhas_verticais = list(laje_atual_backup.linhas_verticais) if laje_atual_backup.linhas_verticais else []
                laje_existente.linhas_horizontais = list(laje_atual_backup.linhas_horizontais) if laje_atual_backup.linhas_horizontais else []
                laje_existente.obstaculos = [[(x, y) for x, y in obst] for obst in getattr(laje_atual_backup, 'obstaculos', [])]
                # Preservar cotas manuais
                laje_existente.manual_dimensions = manual_dimensions_preservados
                # Preservar posições das cotas movidas (IMPORTANTE: usar backup)
                if hasattr(laje_atual_backup, 'dimension_positions') and laje_atual_backup.dimension_positions:
                    from copy import deepcopy
                    laje_existente.dimension_positions = deepcopy(laje_atual_backup.dimension_positions)
# print(f"[DEBUG] Copiadas {len(laje_existente.dimension_positions)} posições de cotas para laje existente")
                else:
                    # Se não há dimension_positions no backup, preservar o que já existe na laje_existente
                    if not hasattr(laje_existente, 'dimension_positions'):
                        laje_existente.dimension_positions = {}
# print(f"  [Próxima Laje] Laje #{numero_atual} '{nome_atual}' atualizada (preservando {len(manual_dimensions_preservados)} cotas manuais)")
            # Se não existe, NÃO fazer nada - não criar nova laje
        
        # Buscar próximo número disponível no pavimento
        if pavimento.lajes:
            numeros_usados = [laje.numero for laje in pavimento.lajes if laje.numero > 0]
            proximo_numero = max(numeros_usados) + 1 if numeros_usados else 1
        else:
            proximo_numero = 1
        
        # IMPORTANTE: Limpar canvas ANTES de limpar campos e criar nova laje
        # Isso evita que cotas da laje anterior sejam passadas para a nova
        if self.canvas_widget:
            # Limpar canvas emitindo sinal com None
            # IMPORTANTE: Isso também limpa as listas de cotas manuais no canvas
            self.laje_selecionada.emit(None, False)
            # Garantir que as listas de cotas manuais sejam limpas
            if hasattr(self.canvas_widget, 'scene'):
                self.canvas_widget.scene.manual_dimension_texts.clear()
                self.canvas_widget.scene.manual_dimension_data.clear()
        
        # Limpar campos para próxima laje (APÓS salvar e limpar canvas)
        # IMPORTANTE: NÃO limpar o nome ainda - será limpo DEPOIS que a nova laje for criada
        # com o texto do AutoCAD, para evitar que o nome seja perdido
        self.numero_edit.setText(str(proximo_numero))
        # NÃO limpar nome aqui - será limpo em selecionar_autocad após criar a nova laje
        # self.nome_edit.clear()  # REMOVIDO - será limpo depois
        self.laje_atual = None
        
        # Chamar automaticamente seleção no CAD (hatch + texto)
        # A NOVA laje será criada aqui quando o usuário selecionar o hatch
        self.selecionar_autocad("hatch", aplicar_correcoes_automaticas=True)
        
        # Atualizar tabela APENAS com lajes do pavimento atual (após seleção)
        if self.laje_atual and self.laje_atual.coordenadas:
            self.table_model.set_lajes(pavimento.lajes)
    
    def nova_laje(self):
        """Limpa campos e canvas"""
        # Limpar campos
        self.numero_edit.clear()
        self.nome_edit.clear()
        self.laje_atual = None
        
        # Limpar canvas - emitir sinal com None para limpar
        self.laje_selecionada.emit(None, False)
    
    def selecionar_multiplas_lajes(self):
        """
        Seleciona múltiplas lajes de forma iterativa no AutoCAD.
        Cópia da função "Próxima Laje" mas em loop:
        - Seleciona boundary -> texto -> processa -> cria laje
        - Repete até que usuário dê Enter sem selecionar boundary
        - Não volta à interface durante o processo
        """
        if not self.obra_atual:
            QMessageBox.warning(self, "Aviso", "Selecione ou crie uma obra primeiro.")
            return
        
        # Obter pavimento atual
        pavimento_nome = _pav_cmb_raw(self.pavimento_combo) or ""
        if not pavimento_nome:
            QMessageBox.warning(self, "Aviso", "Selecione um pavimento primeiro.")
            return
        
        # Encontrar ou criar pavimento
        pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == pavimento_nome), None)
        if not pavimento:
            pavimento = Pavimento(nome=pavimento_nome)
            self.obra_atual.pavimentos.append(pavimento)
            self.pavimento_combo.addItem(_fmt_pav_label(pavimento_nome), pavimento_nome)

        # Determinar próximo número de laje disponível
        if pavimento.lajes:
            numeros_usados = [laje.numero for laje in pavimento.lajes if laje.numero > 0]
            proximo_numero = max(numeros_usados) + 1 if numeros_usados else 1
        else:
            proximo_numero = 1
        
        try:
            # Conectar ao AutoCAD
            if not self.autocad.acad:
                self.autocad.connect()
            
            # Trazer AutoCAD para frente
            self.autocad.bring_to_front()
            
            lajes_criadas = []
            boundaries_falhados = []
            contador = 0
            
            # Importar utilitários e App
            from PySide6.QtWidgets import QApplication
            from laje_src.services.geometry_calculator import (
                extract_xy_only, validate_polygon, calculate_area, 
                calculate_dimensions, is_valid_coordinate, MAX_POLYGON_POINTS,
                MAX_OBSTACULOS
            )

            # Loop de seleção
            while True:
                contador += 1
                try:
                    # 1. Verificar contagem ANTES de emitir BOUNDARY
                    count_before = 0
                    try:
                        if self.autocad.model_space:
                            count_before = self.autocad.model_space.Count
                    except:
                        pass
                    
                    # 2. Selecionar boundary + texto (usando select_hatch)
                    try:
                        resultado = self.autocad.select_hatch()
                    except Exception as e:
                        # Se for erro de cancelamento ou nenhum objeto, finalizar loop
                        if "Nenhum objeto" in str(e) or "Nenhum novo" in str(e) or "COMError" in str(type(e)):
                            break
                        # Outros erros, mostrar mensagem e continuar
# print(f"[ERRO] Erro ao selecionar boundary: {e}")
                        continue
                    
                    # Se resultado for None, usuário pressionou Enter sem selecionar boundary
                    if resultado is None:
                        break
                    
                    # 3. Verificar se foi criado objeto
                    count_after = 0
                    try:
                        if self.autocad.model_space:
                            count_after = self.autocad.model_space.Count
                    except:
                        pass
                    
                    # Se não criou objeto, finalizar loop
                    if count_after <= count_before:
                        break
                        
                    # Extrair resultado: (coordenadas, obstaculos, texto_nome)
                    if isinstance(resultado, tuple) and len(resultado) == 3:
                        coordenadas, obstaculos, texto_nome = resultado
                    else:
                        coordenadas = resultado[0] if len(resultado) > 0 else []
                        obstaculos = resultado[1] if len(resultado) > 1 else []
                        texto_nome = resultado[2] if len(resultado) > 2 else ""
                        
                    # Processar coordenadas
                    coordenadas_originais = extract_xy_only(coordenadas)
                    
                    if not coordenadas_originais or len(coordenadas_originais) < 3:
# print(f"[AVISO] Boundary {contador} rejeitado: pontos insuficientes")
                        boundaries_falhados.append(contador)
                        continue
                        
                    # Calcular propriedades
                    area_cm2 = calculate_area(coordenadas_originais)
                    comprimento, largura = calculate_dimensions(coordenadas_originais)
                    
                    # Definir número e nome
                    numero_laje = proximo_numero
                    proximo_numero += 1
                    
                    nome_final = texto_nome.strip() if texto_nome else f"L{numero_laje}"
                    
                    # Evitar conflitos de nome
                    nomes_existentes = {l.nome for l in pavimento.lajes if l.nome}
                    if nome_final in nomes_existentes:
                        c = 1
                        orig = nome_final
                        while nome_final in nomes_existentes:
                            nome_final = f"{orig}_{c}"
                            c += 1
                            
                    # Processar obstáculos
                    obstaculos_validos = []
                    if obstaculos:
                        for obst in obstaculos:
                            try:
                                obs_clean = extract_xy_only(obst)
                                if len(obs_clean) >= 3 and validate_polygon(obs_clean):
                                     obstaculos_validos.append(obs_clean)
                            except:
                                pass
                                
                    # Criar Objeto Laje
                    nova_laje = Laje(
                        numero=numero_laje,
                        nome=nome_final,
                        comprimento=comprimento,
                        largura=largura,
                        pavimento=pavimento_nome
                    )
                    nova_laje.coordenadas = coordenadas_originais
                    nova_laje.area_cm2 = area_cm2
                    nova_laje.obstaculos = obstaculos_validos
                    
                    # Adicionar ao pavimento
                    pavimento.lajes.append(nova_laje)
                    lajes_criadas.append(nova_laje)
                    
                    # ATUALIZAR INTERFACE IMEDIATAMENTE
                    self._populate_tree(pavimento.lajes)
                    self.obra_changed.emit(self.obra_atual)
                    
                    # Definir como Laje Atual
                    self.laje_atual = nova_laje
                    self.numero_edit.setText(str(nova_laje.numero))
                    self.nome_edit.blockSignals(True)
                    self.nome_edit.setText(nova_laje.nome or "")
                    self.nome_edit.blockSignals(False)
                    
                    # Selecionar na árvore (sem grupos)
                    for i in range(self.tree_widget.topLevelItemCount()):
                        item = self.tree_widget.topLevelItem(i)
                        data = item.data(0, Qt.UserRole)
                        # Comparamos identidade pois é o mesmo objeto python
                        if data is nova_laje:
                             self.tree_widget.clearSelection()
                             item.setSelected(True)
                             self.tree_widget.scrollToItem(item)
                             break
                    
                    # Emitir sinal de seleção (dispara canvas e possivelmente IA)
                    self.laje_selecionada.emit(nova_laje, True)
# print(f"[SUCESSO] Laje {nova_laje.nome} (#{nova_laje.numero}) adicionada.")
                    
                    # Processar eventos para UI fluida
                    QApplication.processEvents()
                    
                except Exception as e:
# print(f"[ERRO] Erro no loop de seleção: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            # Pós-Loop
            if boundaries_falhados:
                QMessageBox.warning(self, "Aviso", f"Alguns boundaries falharam (pontos insuficientes): {boundaries_falhados}")

            if not lajes_criadas:
                 QMessageBox.information(self, "Aviso", "Nenhuma laje criada nesta operação.")
                 
            # Trazer janela para frente ao final
            main_window = self.window()
            if main_window:
                main_window.showMaximized()
                main_window.raise_()
                main_window.activateWindow()

        except Exception as e:
             QMessageBox.critical(self, "Erro Fatal", f"Erro em selecionar_multiplas_lajes: {str(e)}")
             import traceback
             traceback.print_exc()
    
    def excluir_lajes_selecionadas(self):
        """Exclui apenas as lajes selecionadas na tabela do pavimento atual"""
        try:
# print("[DEBUG EXCLUIR] Função excluir_lajes_selecionadas CHAMADA!")
            import sys
            sys.stdout.flush()
            
            if not self.obra_atual:
# print("[DEBUG EXCLUIR] Abortando: self.obra_atual é None.")
                return
            
            # --- CORREÇÃO ROBUSTA: Não confiar cegamente no ComboBox ---
            # O ComboBox pode ter sido editado (digitado) sem atualizar a tabela,
            # causando falha ao tentar encontrar um pavimento que não existe na obra,
            # enquanto a tabela mostra itens de outro pavimento válido.
            
            selected_items = self.tree_widget.selectedItems()
# print(f"[DEBUG EXCLUIR] QTreeWidget reports {len(selected_items)} selected items.")
            
            if not selected_items:
# print("[DEBUG EXCLUIR] Abortando: Nenhuma seleção detectada na TreeWidget.")
                QMessageBox.warning(self, "Aviso", "Selecione ao menos uma laje para excluir.")
                return

            # Tentar inferir o pavimento correto a partir dos itens selecionados
            # Pegar a primeira laje válida e usar seu pavimento
            pavimento_alvo_nome = None
            
            for item in selected_items:
                data = item.data(0, Qt.UserRole)
                if data and isinstance(data, Laje):
                    pavimento_alvo_nome = data.pavimento
# print(f"[DEBUG EXCLUIR] Pavimento inferido da seleção: '{pavimento_alvo_nome}'")
                    break
            
            # Fallback para o combo se não conseguir inferir
            if not pavimento_alvo_nome:
                pavimento_alvo_nome = _pav_cmb_raw(self.pavimento_combo)
# print(f"[DEBUG EXCLUIR] Fallback: Usando texto do combo: '{pavimento_alvo_nome}'")

            if not pavimento_alvo_nome:
                QMessageBox.warning(self, "Aviso", "Não foi possível identificar o pavimento alvo.")
# print("[DEBUG EXCLUIR] Abortando: Pavimento alvo desconhecido.")
                return
# print(f"[DEBUG EXCLUIR] Procurando pavimento '{pavimento_alvo_nome}' na lista da obra...")
            
            # Busca manual com log
            pavimento_atual = None
            for p in self.obra_atual.pavimentos:
                if str(p.nome).strip() == str(pavimento_alvo_nome).strip():
                    pavimento_atual = p
# print(f"[DEBUG EXCLUIR] -> ENCONTRADO! ID/Ref: {id(p)}")
                    break
            
            # if not pavimento_atual:
# print(f"[DEBUG EXCLUIR] -> NÃO ENCONTRADO APÓS BUSCA! Tentando listar disponíveis...")
# print(f"[DEBUG EXCLUIR] Pavimentos disponíveis: {[p.nome for p in self.obra_atual.pavimentos]}")
# print(f"[DEBUG EXCLUIR] Pavimento alvo '{pavimento_alvo_nome}' desconhecido. Prosseguindo com busca global.")
                # Não abortamos mais. Deixamos pavimento_atual = None e a lógica abaixo tentará encontrar a laje em qualquer lugar.
                # return
# print("[DEBUG EXCLUIR] Prosseguindo para filtragem...")
            # sys.stdout.flush()
            
            # Filtrar apenas lajes (ignorar grupos) e que pertencem ao pavimento encontrado
            lajes_para_excluir = []
            for i, item in enumerate(selected_items):
                data = item.data(0, Qt.UserRole)
# print(f"[DEBUG EXCLUIR] Item {i}: Text='{item.text(0)}', DataType={type(data)}, Data={str(data)[:50]}...")
                if data and isinstance(data, Laje):
                    lajes_para_excluir.append(data)
                else:
                    pass
# print(f"[DEBUG EXCLUIR] Item {i} ignorado (sem dados de Laje)")
            
            if not lajes_para_excluir:
# print("[DEBUG EXCLUIR] Abortando: Pós-filtro vazio (nenhuma Laje válida encontrada).")
                QMessageBox.warning(
                    self, "Aviso", 
                    "Nenhuma laje válida selecionada (apenas grupos ou itens sem dados)."
                )
                return
            
            # Confirmar exclusão
            nomes_lajes = ", ".join([f"{l.nome or f'#{l.numero}'}" for l in lajes_para_excluir])
# print(f"[DEBUG EXCLUIR] Pavimento alvo: {pavimento_atual.nome if pavimento_atual else 'N/A'}")
# print(f"[DEBUG EXCLUIR] Items selecionados: {len(selected_items)}")
# print(f"[DEBUG EXCLUIR] Lajes identificadas para excluir: {len(lajes_para_excluir)}")
            # Loop de debug removido
            # for l in lajes_para_excluir:
                # print(...)
    
            reply = QMessageBox.question(
                self,
                "Confirmar Exclusão",
                f"Deseja excluir as seguintes lajes do pavimento '{pavimento_atual.nome if pavimento_atual else 'N/A'}'?\n\n{nomes_lajes}\n\nEsta ação não pode ser desfeita.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
# print("[DEBUG EXCLUIR] Cancelado pelo usuário.")
                return
            
            # Iterar e remover
            removidos_count = 0
            
            for laje_target in lajes_para_excluir:
                removed_this = False
                
                # 1. Tentar remover do pavimento identificado (se existir e se estiver nele)
                if pavimento_atual:
                    # Verificar se está na lista deste pavimento
                    # Nota: laje_target pode ser uma instância diferente mas igual em valores
                    # Tentar achar índice
                    found_idx = -1
                    for idx, l in enumerate(pavimento_atual.lajes):
                        # Comparar identidade (para garantir que é o objeto da árvore)
                        # OU se valores batem (numero e nome)
                        if l is laje_target or (l.numero == laje_target.numero and l.nome == laje_target.nome):
                            found_idx = idx
                            break
                    
                    if found_idx >= 0:
                        try:
                            pavimento_atual.lajes.pop(found_idx)
# print(f"[DEBUG EXCLUIR] Removido via índice do pavimento '{pavimento_atual.nome}': {laje_target.nome}")
                            removed_this = True
                        except Exception as e:
                            pass
# print(f"[DEBUG EXCLUIR] Erro ao remover do pavimento atual: {e}")

                # 2. Se falhou, procurar em TODOS os pavimentos da obra (busca global por atributos)
                if not removed_this:
# print(f"[DEBUG EXCLUIR] Laje '{laje_target.nome}' não encontrada diretamente em '{pavimento_atual.nome if pavimento_atual else 'None'}'. Iniciando busca global...")
                    for p in self.obra_atual.pavimentos:
                        # Tentar encontrar por identidade ou atributos (Num + Nome)
                        laje_found_idx = -1
                        for idx, l in enumerate(p.lajes):
                             if l is laje_target or (l.numero == laje_target.numero and l.nome == laje_target.nome):
                                 laje_found_idx = idx
                                 break
                        
                        if laje_found_idx >= 0:
                            try:
                                p.lajes.pop(laje_found_idx)
# print(f"[DEBUG EXCLUIR] Removido via busca global do pavimento '{p.nome}': {laje_target.nome}")
                                removed_this = True
                                break # Parar de procurar nos pavimentos
                            except ValueError:
                                pass
                
                if removed_this:
                    removidos_count += 1
                else:
                    pass
# print(f"[DEBUG EXCLUIR] FALHA FINAL: Não foi possível encontrar a laje '{laje_target.nome}' em NENHUM pavimento.")
# print(f"[DEBUG EXCLUIR] Total removidos: {removidos_count}/{len(lajes_para_excluir)}")            
            
            if removidos_count > 0:
                # Emitir sinal para que MainWindow possa limpar do DB de IA se necessário
                self.lajes_deleted.emit(lajes_para_excluir)
                # Atualizar a interface completamente para refletir a realidade
                self.obra_changed.emit(self.obra_atual)
                
                # Se tínhamos um pavimento alvo, atualizar arvore
                if pavimento_atual:
                     self._populate_tree(pavimento_atual.lajes)
                else: 
                    # Se foi busca global, melhor repopular com o pavimento atual do combo
                     self.atualizar_tabela_lajes() # Usa o combo atual

                # Limpar campos se a laje atual foi removida
                if self.laje_atual in lajes_para_excluir:
                    self.laje_atual = None
                    self.numero_edit.clear()
                    self.nome_edit.clear()
                    self.laje_selecionada.emit(None, False)
                
                QMessageBox.information(self, "Sucesso", f"{removidos_count} laje(s) excluída(s).")
            else:
                 QMessageBox.warning(self, "Erro", "Falha ao remover lajes. Verifique o log para detalhes.")
    

    
        except Exception as e:
# print(f"[CRITICAL ERROR] Exceção em excluir_lajes_selecionadas: {e}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()

    def desenhar_laje_cad(self):
        """Gera script .scr com linhas e cotas (exceto marco e cotas do marco)"""
        if not self.laje_atual or not self.laje_atual.coordenadas:
            QMessageBox.warning(self, "Aviso", "Selecione uma laje primeiro.")
            return
        
        if not self.laje_atual.linhas_verticais and not self.laje_atual.linhas_horizontais:
            QMessageBox.warning(self, "Aviso", "A laje não possui linhas verticais ou horizontais definidas.")
            return
            
        # Verificar se está offline
        from laje_src.services.auth_service import auth_service
        if auth_service.is_offline:
            QMessageBox.warning(self, "Modo Offline", "O sistema está em modo OFFLINE. Conecte-se à internet para gerar scripts.")
            return
        
        # Verificar e consumir créditos
        try:
            from laje_src.services.credits_service import (
                calcular_area_laje, verificar_e_consumir_creditos, formatar_confirmacao_consumo
            )
            from laje_src.config.secrets import DEBUG_MODE
            
            if not DEBUG_MODE:
                area_m2 = calcular_area_laje(self.laje_atual)
                
                if area_m2 > 0:
                    # Confirmar consumo
                    msg = formatar_confirmacao_consumo(area_m2, "Laje", self.laje_atual.nome)
                    reply = QMessageBox.question(
                        self, "Confirmar Consumo de Créditos", msg,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    
                    # Consumir créditos
                    success, message = verificar_e_consumir_creditos(
                        area_m2, 
                        f"Desenhar Laje: {self.laje_atual.nome} ({self.laje_atual.pavimento})"
                    )
                    
                    if not success:
                        QMessageBox.warning(self, "Créditos Insuficientes", message)
                        return
        except ImportError:
            pass  # Módulo não disponível, continuar sem verificação
        
        try:
            from laje_src.services.gerar_script_scr import gerar_script_scr
            import os
            from pathlib import Path
            
            # Obter diretório src (onde está o código)
            # __file__ = src/ui/widgets/laje_tab.py
            # .parent = src/ui/widgets/
            # .parent.parent = src/ui/
            # .parent.parent.parent = src/
            # Usar PathHelper para obter o diretório de scripts (adaptável a PC de cliente)
            output_dir = PathHelper.get_scripts_dir()
            
            # Gerar nome do arquivo baseado na laje
            nome_arquivo = f"laje_{self.laje_atual.numero}_{self.laje_atual.nome}".replace(" ", "_")
            if self.laje_atual.pavimento:
                nome_arquivo = f"{self.laje_atual.pavimento}_{nome_arquivo}".replace(" ", "_")
            
            # Obter estado dos checkboxes
            desenhar_nomes = self.checkbox_nomes_paineis.isChecked()
            desenhar_marco = self.checkbox_marco_laje.isChecked()
            desenhar_unioes_hatch = self.checkbox_unioes_hatch.isChecked()
            
            # Gerar script usando gerar_conteudo_script_scr e depois salvar
            from laje_src.services.gerar_script_scr import gerar_conteudo_script_scr
            obstaculos = getattr(self.laje_atual, 'obstaculos', [])
            
            # ========== OBTER LINHAS DIRETAMENTE DO CANVAS (ATUALIZADAS) ==========
            # IMPORTANTE: Obter linhas diretamente do canvas para garantir que estamos usando
            # os dados mais recentes que o usuário está vendo, não dados em cache
            linhas_verticais_do_canvas = []
            linhas_horizontais_do_canvas = []
            
            if hasattr(self, 'canvas_widget') and self.canvas_widget:
                if hasattr(self.canvas_widget, 'vertical_lines_overlay'):
                    linhas_verticais_do_canvas = self.canvas_widget.vertical_lines_overlay.get_linhas()
                if hasattr(self.canvas_widget, 'horizontal_lines_overlay'):
                    linhas_horizontais_do_canvas = self.canvas_widget.horizontal_lines_overlay.get_linhas()
            
            # Se não conseguiu obter do canvas, usar dados da laje como fallback
            if not linhas_verticais_do_canvas:
                linhas_verticais_do_canvas = self.laje_atual.linhas_verticais
            if not linhas_horizontais_do_canvas:
                linhas_horizontais_do_canvas = self.laje_atual.linhas_horizontais
            
            # Gerar script
            # ========== DEBUG: VERIFICAR DADOS DO LAJE_ATUAL E DO CANVAS ==========
# print("\n" + "="*80)
# print("[DEBUG LAJE_TAB] DADOS DO LAJE_ATUAL ANTES DE GERAR SCRIPT")
# print("="*80)
# print(f"[DEBUG LAJE_TAB] ID do objeto: {id(self.laje_atual)}")
# print(f"[DEBUG LAJE_TAB] Laje: {self.laje_atual.numero} - {self.laje_atual.nome}")
# print(f"[DEBUG LAJE_TAB] Pavimento: {self.laje_atual.pavimento}")
# print(f"[DEBUG LAJE_TAB] linhas_horizontais (da laje): {self.laje_atual.linhas_horizontais}")
# print(f"[DEBUG LAJE_TAB] linhas_horizontais (formatado, da laje): {[f'{d:.1f}' for d in self.laje_atual.linhas_horizontais]}")
# print(f"[DEBUG LAJE_TAB] linhas_horizontais (DO CANVAS): {linhas_horizontais_do_canvas}")
# print(f"[DEBUG LAJE_TAB] linhas_horizontais (formatado, DO CANVAS): {[f'{d:.1f}' for d in linhas_horizontais_do_canvas]}")
# print(f"[DEBUG LAJE_TAB] Total de distâncias horizontais (da laje): {len(self.laje_atual.linhas_horizontais)}")
# print(f"[DEBUG LAJE_TAB] Total de distâncias horizontais (DO CANVAS): {len(linhas_horizontais_do_canvas)}")
# print(f"[DEBUG LAJE_TAB] linhas_verticais (da laje): {self.laje_atual.linhas_verticais}")
# print(f"[DEBUG LAJE_TAB] linhas_verticais (DO CANVAS): {linhas_verticais_do_canvas}")
# print(f"[DEBUG LAJE_TAB] Coordenadas: {len(self.laje_atual.coordenadas)} pontos")
            # Debug coordinates removed
            # if self.laje_atual.coordenadas:
                # print(...)
            
            # Coletar todas as cotas visíveis da cena (automáticas, manuais, especiais)
            # para incluir no script
            all_dimensions_data = []
            if hasattr(self, 'canvas_widget') and self.canvas_widget and self.canvas_widget.scene:
                all_dimensions_data = self.canvas_widget.scene.get_all_visible_dimensions(self.laje_atual.coordenadas)
            
            # Verificar se há dados de reaproveitamento no canvas scene e sincronizar
            reap_dados = getattr(self.laje_atual, 'reaproveitamento_dados', [])
            if hasattr(self, 'canvas_widget') and self.canvas_widget and hasattr(self.canvas_widget.scene, 'reaproveitamento_dados'):
                scene_reap_dados = self.canvas_widget.scene.reaproveitamento_dados
                if scene_reap_dados:
# print(f"[DEBUG LAJE_TAB] Usando reaproveitamento_dados do CANVAS scene ({len(scene_reap_dados)} itens)")
                    reap_dados = scene_reap_dados
                else:
                    pass
# print(f"[DEBUG LAJE_TAB] Reaproveitamento_dados do CANVAS scene está vazio")


            if reap_dados:
                # Obter primeiro item de forma segura (funciona para list, dict, set)
                primeiro_item = next(iter(reap_dados.values())) if isinstance(reap_dados, dict) else next(iter(reap_dados))
# print(f"[DEBUG LAJE_TAB] Exemplo primeiro item: {primeiro_item}")
                # Debug tag removed
                # if hasattr(primeiro_item, 'tag_reap'):
                    # print(...)

            linhas_script = gerar_conteudo_script_scr(
                coordenadas_laje=self.laje_atual.coordenadas,
                linhas_verticais=linhas_verticais_do_canvas,
                linhas_horizontais=linhas_horizontais_do_canvas,
                desenhar_nomes_paineis=desenhar_nomes,
                desenhar_marco=desenhar_marco,
                desenhar_unioes_hatch=desenhar_unioes_hatch,
                obstaculos=obstaculos,
                pavimento_nome=self.laje_atual.pavimento,
                laje_nome=self.laje_atual.nome,
                manual_dimensions_data=all_dimensions_data,
                reaproveitamento_dados=reap_dados,
                desenhar_reap_tags=self.checkbox_nomes_reaproveitamento.isChecked(),
                desenhar_reap_hatches=self.checkbox_hatchs_reaproveitamento.isChecked()
            )
            
            # Salvar arquivo em UTF-16 LE com BOM
            caminho_arquivo = output_dir / f"{nome_arquivo}.scr"
            conteudo = "\n".join(linhas_script)
            
            # DEBUG: Verificar comandos PLINE das linhas horizontais no conteúdo final
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
# print(f"\n[DEBUG SALVAMENTO] [{timestamp}] Verificando comandos PLINE no conteúdo final do script:")
            linhas_conteudo = conteudo.split('\n')
            pline_count = 0
            plines_horizontais = []
            for i, linha in enumerate(linhas_conteudo):
                if linha.strip() == "_PLINE" and i + 2 < len(linhas_conteudo):
                    pline_count += 1
                    coord1 = linhas_conteudo[i+1].strip() if i+1 < len(linhas_conteudo) else ""
                    coord2 = linhas_conteudo[i+2].strip() if i+2 < len(linhas_conteudo) else ""
                    # Extrair Y da primeira coordenada
                    try:
                        if ',' in coord1:
                            y_val = float(coord1.split(',')[1])
                            # Verificar se é horizontal (Y similar em ambas coordenadas)
                            if ',' in coord2:
                                y2_val = float(coord2.split(',')[1])
                                if abs(y_val - y2_val) < 1.0:  # Linha horizontal
                                    plines_horizontais.append((i+1, y_val))
# print(f"[DEBUG SALVAMENTO]   PLINE HORIZONTAL #{len(plines_horizontais)}: Y={y_val:.1f} (linha {i+1} do script)")
                    except:
                        pass
            
            # Mostrar ordem das linhas horizontais
# print(f"[DEBUG SALVAMENTO] Ordem das linhas horizontais no script: {[f'Y={y:.1f}' for _, y in plines_horizontais]}")
            
            # Deletar arquivo antigo se existir para forçar recriação
            if caminho_arquivo.exists():
                caminho_arquivo.unlink()
# print(f"[DEBUG SALVAMENTO] Arquivo antigo deletado para forçar recriação")
            
            with open(caminho_arquivo, 'w', encoding='utf-16-le') as f:
                # Escrever BOM (Byte Order Mark) UTF-16 LE
                f.write('\ufeff')  # BOM para UTF-16 LE
                f.write(conteudo)
# print(f"[DEBUG SALVAMENTO] Arquivo NOVO salvo: {caminho_arquivo}")
# print(f"[DEBUG SALVAMENTO] Total de linhas no arquivo: {len(linhas_conteudo)}")
# print(f"[DEBUG SALVAMENTO] Timestamp: {timestamp}")
            
            # Copiar conteúdo completo do script gerado para script_LAZ.scr em ferramentas_LOAD_LISP
            lisp_dir = PathHelper.get_lisp_dir()  # ferramentas_LOAD_LISP
            script_laz_path = lisp_dir / "script_LAZ.scr"
            with open(caminho_arquivo, 'r') as f:
                conteudo_script_bytes = f.read()
            
            with open(script_laz_path, 'w') as f:
                f.write(conteudo_script_bytes)
            
            QMessageBox.information(
                self, 
                "Sucesso", 
                f"Script .scr gerado com sucesso!\n\nArquivo: {caminho_arquivo}\n\nscript_LAZ.scr atualizado em {script_laz_path}!"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao gerar script .scr: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def abrir_configuracoes(self):
        """Abre a janela de configurações"""
        from laje_src.ui.widgets.config_window import ConfigWindow
        config_window = ConfigWindow(self)
        config_window.exec()
    
    def criar_comando_lisp(self):
        """Cria os arquivos comando_LAZ.lsp e script_LAZ.scr nos diretórios corretos"""
        # Verificar se está offline
        from laje_src.services.auth_service import auth_service
        if auth_service.is_offline:
            QMessageBox.warning(self, "Modo Offline", "O sistema está em modo OFFLINE. Conecte-se à internet para criar comandos LISP.")
            return
            
        try:
            from pathlib import Path
            
            # Usar PathHelper para obter diretórios corretos
            lisp_dir = PathHelper.get_lisp_dir()  # ferramentas_LOAD_LISP
            scripts_dir = PathHelper.get_scripts_dir()  # SCRIPTS_ROBOS
            
            # Caminho absoluto para o AutoCAD usar (formato posix para evitar problemas de escape)
            # script_LAZ.scr deve estar em ferramentas_LOAD_LISP junto com os comandos LISP
            script_laz_absoluto = (lisp_dir / "script_LAZ.scr").as_posix()
            
            # Criar arquivo comando_LAZ.lsp em ferramentas_LOAD_LISP
            comando_lisp_path = lisp_dir / "comando_LAZ.lsp"
            with open(comando_lisp_path, 'w', encoding='utf-8') as f:
                # Escrever BOM UTF-8
                f.write('\ufeff')  # BOM UTF-8
                f.write(";; Comando para executar script SCR LAZ\n")
                f.write("(defun c:LAZ ()\n")
                f.write("  (setvar \"filedia\" 0)\n")
                f.write(f'  (command "_SCRIPT" "{script_laz_absoluto}")\n')
                f.write("  (setvar \"filedia\" 1)\n")
                f.write("  (princ)\n")
                f.write(")\n")
            
            # Criar arquivo comando_LAR.lsp em ferramentas_LOAD_LISP
            comando_lar_path = lisp_dir / "comando_LAR.lsp"
            with open(comando_lar_path, 'w', encoding='utf-8') as f:
                # Escrever BOM UTF-8
                f.write('\ufeff')  # BOM UTF-8
                f.write(";; Comando para executar script SCR LAZ\n")
                f.write("(defun c:LAR ()\n")
                f.write("  (setvar \"filedia\" 0)\n")
                f.write(f'  (command "_SCRIPT" "{script_laz_absoluto}")\n')
                f.write("  (setvar \"filedia\" 1)\n")
                f.write("  (princ)\n")
                f.write(")\n")
            
            # Criar arquivo script_LAZ.scr (vazio inicialmente) em ferramentas_LOAD_LISP
            script_laz_path = lisp_dir / "script_LAZ.scr"
            if not script_laz_path.exists():
                # Criar arquivo vazio inicialmente com BOM
                with open(script_laz_path, 'w', encoding='utf-16-le') as f:
                    f.write('\ufeff')  # BOM UTF-16 LE
            
            QMessageBox.information(
                self,
                "Sucesso",
                f"Arquivos LISP criados com sucesso!\n\n"
                f"comando_LAZ.lsp: {comando_lisp_path}\n"
                f"comando_LAR.lsp: {comando_lar_path}\n"
                f"script_LAZ.scr: {script_laz_path}\n\n"
                f"Para usar no AutoCAD:\n"
                f"1. Carregue o arquivo comando_LAZ.lsp ou comando_LAR.lsp\n"
                f"2. Digite 'LAZ' ou 'LAR' no AutoCAD para executar o script"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao criar arquivos LISP: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _generate_dimensions_data_for_laje(self, laje, show_labels=True):
        """Gera dados de cotas (automáticas, manuais e especiais) simulando o canvas"""
        try:
            from laje_src.ui.models.graphics_scene import LajeGraphicsScene
            
            # Criar scene temporária (off-screen)
            scene = LajeGraphicsScene()
            
            # Transferir dados de exclusão e posições salvas da laje para a scene temporária
            if hasattr(laje, 'excluded_dimensions') and laje.excluded_dimensions:
                scene.excluded_dimensions = list(laje.excluded_dimensions) # Cópia para segurança
            
            if hasattr(laje, 'dimension_positions') and laje.dimension_positions:
                scene.saved_dimension_positions = dict(laje.dimension_positions) # Cópia para segurança
            
            # Desenhar tudo na scene para gerar cotas automáticas
            obstaculos = getattr(laje, 'obstaculos', [])
            
            scene.draw_laje(laje.coordenadas, obstaculos=obstaculos)
            
            # Usar as linhas exatamente como estão no objeto laje
            v_lines = list(laje.linhas_verticais) if laje.linhas_verticais else []
            h_lines = list(laje.linhas_horizontais) if laje.linhas_horizontais else []
            
            if v_lines:
                scene.draw_vertical_lines(v_lines, laje.coordenadas, obstaculos)
            
            if h_lines:
                scene.draw_horizontal_lines(h_lines, laje.coordenadas, obstaculos)
                
            # Importante: desenhar marco para ter referências
            scene.draw_marco_segments(
                laje.coordenadas, 
                v_lines, 
                h_lines,
                obstaculos
            )
            
            # Gerar cotas automáticas (rosas e verdes)
            # Chamar join automático antes de gerar cotas para evitar processamento de segmentos indevidos
            scene.join_automatico()
            
            # Assinatura de draw_dimensions: (vertical_distances, horizontal_distances, laje_coords, laje=None)
            scene.draw_dimensions(v_lines, h_lines, laje.coordenadas, laje=laje)
            
            # Gerar numeração de painéis e COTAS ESPECIAIS (amarelas de deformidades/recortes)
            scene.draw_panel_labels_and_special_dimensions(
                v_lines,
                h_lines,
                laje.coordenadas,
                laje.pavimento,
                laje.nome,
                obstaculos,
                show_labels=show_labels,
                laje=laje
            )
            
            # Restaurar cotas manuais
            if hasattr(laje, 'manual_dimensions') and laje.manual_dimensions:
                scene.restore_manual_dimensions(laje.manual_dimensions, laje.coordenadas, laje=laje)
            
            # Extrair dados no formato esperado pelo gerador de script
            visible_dimensions = scene.get_all_visible_dimensions(laje.coordenadas)
# print(f"\n[DEBUG LAJE_TAB] Dimensões extraídas para {laje.nome}: {len(visible_dimensions)}")
            # Debug loop removed
            # for dim in visible_dimensions:
                # ...
            
            return visible_dimensions
            
        except Exception as e:
# print(f"[ERRO GERA_DIMS] Erro ao gerar cotas para laje {laje.nome}: {e}")
            import traceback
            traceback.print_exc()
            return getattr(laje, 'manual_dimensions', [])

    def desenhar_pavimento_cad(self):
        """Gera script .scr com todas as lajes do pavimento atual em sequência"""
        if not self.obra_atual:
            QMessageBox.warning(self, "Aviso", "Selecione uma obra primeiro.")
            return
        
        pavimento_nome = _pav_cmb_raw(self.pavimento_combo) or ""
        if not pavimento_nome:
            QMessageBox.warning(self, "Aviso", "Selecione um pavimento primeiro.")
            return
        
        # Encontrar pavimento
        pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == pavimento_nome), None)
        if not pavimento or not pavimento.lajes:
            QMessageBox.warning(self, "Aviso", "O pavimento não possui lajes.")
            return
            
        # Verificar se está offline
        from laje_src.services.auth_service import auth_service
        if auth_service.is_offline:
            QMessageBox.warning(self, "Modo Offline", "O sistema está em modo OFFLINE. Conecte-se à internet para gerar scripts.")
            return
        
        # Verificar e consumir créditos
        try:
            from laje_src.services.credits_service import (
                calcular_area_pavimento, verificar_e_consumir_creditos, formatar_confirmacao_consumo
            )
            from laje_src.config.secrets import DEBUG_MODE
            
            if not DEBUG_MODE:
                area_m2 = calcular_area_pavimento(pavimento)
                
                if area_m2 > 0:
                    # Confirmar consumo
                    msg = formatar_confirmacao_consumo(area_m2, "Pavimento", pavimento_nome)
                    reply = QMessageBox.question(
                        self, "Confirmar Consumo de Créditos", msg,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    
                    # Consumir créditos
                    success, message = verificar_e_consumir_creditos(
                        area_m2, 
                        f"Desenhar Pavimento: {pavimento_nome}"
                    )
                    
                    if not success:
                        QMessageBox.warning(self, "Créditos Insuficientes", message)
                        return
        except ImportError:
            pass  # Módulo não disponível, continuar sem verificação
        
        try:
            from laje_src.services.gerar_script_scr import gerar_conteudo_script_scr
            import os
            from pathlib import Path
            
            # Obter diretório src (onde está o código)
            # __file__ = src/ui/widgets/laje_tab.py
            # .parent = src/ui/widgets/
            # .parent.parent = src/ui/
            # .parent.parent.parent = src/
            # Usar PathHelper para obter o diretório de scripts (adaptável a PC de cliente)
            output_dir = PathHelper.get_scripts_dir()
            
            # Gerar nome do arquivo
            nome_arquivo = f"pavimento_{pavimento_nome}".replace(" ", "_")
            caminho_arquivo = output_dir / f"{nome_arquivo}.scr"
            
            # Gerar script combinado de todas as lajes
            todas_linhas = []
            
            for laje in pavimento.lajes:
                if not laje.coordenadas:
                    continue
                if not laje.linhas_verticais and not laje.linhas_horizontais:
                    continue
                
                # Obter estado dos checkboxes
                desenhar_nomes = self.checkbox_nomes_paineis.isChecked()
                desenhar_marco = self.checkbox_marco_laje.isChecked()
                desenhar_unioes_hatch = self.checkbox_unioes_hatch.isChecked()
                
                # Gerar conteúdo do script para esta laje
                obstaculos = getattr(laje, 'obstaculos', [])
                
                # GERAR COTAS (SIMULANDO O CANVAS)
                dimensions_data = self._generate_dimensions_data_for_laje(laje, show_labels=desenhar_nomes)
                
                linhas_laje = gerar_conteudo_script_scr(
                    coordenadas_laje=laje.coordenadas,
                    linhas_verticais=laje.linhas_verticais,
                    linhas_horizontais=laje.linhas_horizontais,
                    desenhar_nomes_paineis=desenhar_nomes,
                    desenhar_marco=desenhar_marco,
                    desenhar_unioes_hatch=desenhar_unioes_hatch,
                    obstaculos=obstaculos,
                    pavimento_nome=laje.pavimento,
                    laje_nome=laje.nome,
                    manual_dimensions_data=dimensions_data,
                    reaproveitamento_dados=getattr(laje, 'reaproveitamento_dados', []),
                    desenhar_reap_tags=self.checkbox_nomes_reaproveitamento.isChecked(),
                    desenhar_reap_hatches=self.checkbox_hatchs_reaproveitamento.isChecked()
                )
                todas_linhas.extend(linhas_laje)
            
            if not todas_linhas:
                QMessageBox.warning(self, "Aviso", "Nenhuma laje válida encontrada no pavimento.")
                return
            
            # Salvar arquivo em UTF-16 LE com BOM
            conteudo = "\n".join(todas_linhas)
            with open(caminho_arquivo, 'w', encoding='utf-16-le') as f:
                # Escrever BOM (Byte Order Mark) UTF-16 LE: \xff\xfe
                f.write('\ufeff')  # BOM para UTF-16 LE
                f.write(conteudo)
            
            # Copiar conteúdo completo do script gerado para script_LAZ.scr em ferramentas_LOAD_LISP
            lisp_dir = PathHelper.get_lisp_dir()  # ferramentas_LOAD_LISP
            script_laz_path = lisp_dir / "script_LAZ.scr"
            with open(caminho_arquivo, 'r') as f:
                conteudo_script_bytes = f.read()
            
            with open(script_laz_path, 'w') as f:
                f.write(conteudo_script_bytes)
            
            QMessageBox.information(
                self,
                "Sucesso",
                f"Script do pavimento gerado com sucesso!\n\n"
                f"Arquivo: {caminho_arquivo}\n"
                f"Lajes processadas: {len([l for l in pavimento.lajes if l.coordenadas and (l.linhas_verticais or l.linhas_horizontais)])}\n\n"
                f"script_LAZ.scr atualizado em {script_laz_path}!"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao gerar script do pavimento: {str(e)}")
            import traceback
            traceback.print_exc()

    def desenhar_obra_cad(self):
        """Gera script .scr com todas as lajes de todos os pavimentos da obra em sequência"""
        if not self.obra_atual:
            QMessageBox.warning(self, "Aviso", "Selecione uma obra primeiro.")
            return
        
        if not self.obra_atual.pavimentos:
            QMessageBox.warning(self, "Aviso", "A obra não possui pavimentos.")
            return
            
        # Verificar se está offline
        from laje_src.services.auth_service import auth_service
        if auth_service.is_offline:
            QMessageBox.warning(self, "Modo Offline", "O sistema está em modo OFFLINE. Conecte-se à internet para gerar scripts.")
            return
        
        # Verificar e consumir créditos
        try:
            from laje_src.services.credits_service import (
                calcular_area_obra, verificar_e_consumir_creditos, formatar_confirmacao_consumo
            )
            from laje_src.config.secrets import DEBUG_MODE
            
            if not DEBUG_MODE:
                area_m2 = calcular_area_obra(self.obra_atual)
                
                if area_m2 > 0:
                    # Confirmar consumo
                    msg = formatar_confirmacao_consumo(area_m2, "Obra", self.obra_atual.nome)
                    reply = QMessageBox.question(
                        self, "Confirmar Consumo de Créditos", msg,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    
                    # Consumir créditos
                    success, message = verificar_e_consumir_creditos(
                        area_m2, 
                        f"Desenhar Obra: {self.obra_atual.nome}"
                    )
                    
                    if not success:
                        QMessageBox.warning(self, "Créditos Insuficientes", message)
                        return
        except ImportError:
            pass  # Módulo não disponível, continuar sem verificação
        
        try:
            from laje_src.services.gerar_script_scr import gerar_conteudo_script_scr
            import os
            from pathlib import Path
            
            # Obter diretório src (onde está o código)
            # __file__ = src/ui/widgets/laje_tab.py
            # .parent = src/ui/widgets/
            # .parent.parent = src/ui/
            # .parent.parent.parent = src/
            # Usar PathHelper para obter o diretório de scripts (adaptável a PC de cliente)
            output_dir = PathHelper.get_scripts_dir()
            
            # Gerar nome do arquivo
            nome_arquivo = f"obra_{self.obra_atual.nome}".replace(" ", "_")
            caminho_arquivo = output_dir / f"{nome_arquivo}.scr"
            
            # Gerar script combinado de todas as lajes de todos os pavimentos
            todas_linhas = []
            total_lajes = 0
            
            for pavimento in self.obra_atual.pavimentos:
                for laje in pavimento.lajes:
                    if not laje.coordenadas:
                        continue
                    if not laje.linhas_verticais and not laje.linhas_horizontais:
                        continue
                    
                    # Obter estado dos checkboxes
                    desenhar_nomes = self.checkbox_nomes_paineis.isChecked()
                    desenhar_marco = self.checkbox_marco_laje.isChecked()
                    
                    # Gerar conteúdo do script para esta laje
                    
                    # GERAR COTAS (SIMULANDO O CANVAS)
                    dimensions_data = self._generate_dimensions_data_for_laje(laje, show_labels=desenhar_nomes)
                    
                    linhas_laje = gerar_conteudo_script_scr(
                        coordenadas_laje=laje.coordenadas,
                        linhas_verticais=laje.linhas_verticais,
                        linhas_horizontais=laje.linhas_horizontais,
                        desenhar_nomes_paineis=desenhar_nomes,
                        desenhar_marco=desenhar_marco,
                        pavimento_nome=laje.pavimento,
                        laje_nome=laje.nome,
                        manual_dimensions_data=dimensions_data,
                        reaproveitamento_dados=getattr(laje, 'reaproveitamento_dados', []),
                        desenhar_reap_tags=self.checkbox_nomes_reaproveitamento.isChecked(),
                        desenhar_reap_hatches=self.checkbox_hatchs_reaproveitamento.isChecked()
                    )
                    todas_linhas.extend(linhas_laje)
                    total_lajes += 1
            
            if not todas_linhas:
                QMessageBox.warning(self, "Aviso", "Nenhuma laje válida encontrada na obra.")
                return
            
            # Salvar arquivo em UTF-16 LE com BOM
            conteudo = "\n".join(todas_linhas)
            with open(caminho_arquivo, 'w', encoding='utf-16-le') as f:
                # Escrever BOM (Byte Order Mark) UTF-16 LE: \xff\xfe
                f.write('\ufeff')  # BOM para UTF-16 LE
                f.write(conteudo)
            
            # Copiar conteúdo completo do script gerado para script_LAZ.scr em ferramentas_LOAD_LISP
            lisp_dir = PathHelper.get_lisp_dir()  # ferramentas_LOAD_LISP
            script_laz_path = lisp_dir / "script_LAZ.scr"
            with open(caminho_arquivo, 'r') as f:
                conteudo_script_bytes = f.read()
            
            with open(script_laz_path, 'w') as f:
                f.write(conteudo_script_bytes)
            
            QMessageBox.information(
                self,
                "Sucesso",
                f"Script da obra gerado com sucesso!\n\n"
                f"Arquivo: {caminho_arquivo}\n"
                f"Pavimentos: {len(self.obra_atual.pavimentos)}\n"
                f"Lajes processadas: {total_lajes}\n\n"
                f"script_LAZ.scr atualizado em {script_laz_path}!"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao gerar script da obra: {str(e)}")
            import traceback
            traceback.print_exc()

        
    def show_ai_feedback(self, kept: int, removed: int):
        """Exibe o widget de feedback da IA no painel esquerdo"""
        # Limpar anterior
        if self.feedback_widget_current:
            self.feedback_widget_current.deleteLater()
            self.feedback_widget_current = None
            
        self.feedback_widget_current = AIFeedbackWidget(kept, removed)
        
        # Conectar sinais
        self.feedback_widget_current.approved.connect(self._on_feedback_approved)
        self.feedback_widget_current.manual_refine.connect(self._on_feedback_manual)
        self.feedback_widget_current.report_error.connect(self._on_feedback_error)
        
        self.feedback_layout.addWidget(self.feedback_widget_current)
        
    def _on_feedback_approved(self):
        self.ai_feedback_approved.emit()
        self.clear_feedback()
        
    def _on_feedback_manual(self):
        self.ai_feedback_manual.emit()
        self.clear_feedback()
        
    def _on_feedback_error(self, comment):
        self.ai_feedback_errors.emit(comment)
        self.clear_feedback()
        
    def clear_feedback(self):
        if self.feedback_widget_current:
            self.feedback_widget_current.deleteLater()
            self.feedback_widget_current = None

    def automate_ai_for_all_lajes(self, progress_callback=None):
        """
        Itera sobre todas as lajes da tabela atual e executa IA Linhas e IA Cotas.
        Ignora feedbacks manuais e garante que a UI não trave.
        """
        from PySide6.QtWidgets import QApplication
        import time

        # Obter contagem de lajes
        total = self.tree_widget.topLevelItemCount()
        if total == 0:
            return

        print(f"[AI AUTOMATION] Iniciando processamento de {total} lajes...")

        for idx in range(total):
            # 1. Selecionar a laje visualmente pelo índice (robusto contra deleções)
            item = self.tree_widget.topLevelItem(idx)
            if not item: continue
            
            laje = item.data(0, Qt.UserRole)
            if not laje: continue

            # Selecionar e focar
            self.tree_widget.setCurrentItem(item)
            QApplication.processEvents()
            
            # Pequeno delay para o usuário acompanhar a mudança de seleção
            time.sleep(0.5)

            if not self.canvas_widget or not self.laje_atual:
                continue

            print(f"[AI AUTOMATION] [{idx+1}/{total}] Processando {laje.nome}...")
            if progress_callback:
                pct = int(((idx+1) / total) * 100)
                progress_callback(pct, f"IA processando {laje.nome} ({idx+1}/{total})...")

            # 2. Executar IA Linhas (Silencioso)
            self.canvas_widget._perform_smart_interpret(silent=True)
            QApplication.processEvents()
            time.sleep(0.3) # Delay visual

            # 3. Executar IA Cotas (Silencioso)
            self.canvas_widget._perform_smart_dimensions(silent=True)
            QApplication.processEvents()
            time.sleep(0.3) # Delay visual

            # 4. Salvar os resultados para esta laje SEM atualizar a árvore (importante!)
            # Passamos update_ui=False para não invalidar os objetos C++ do tree_widget
            self.salvar_laje(update_ui=False)
            QApplication.processEvents()
            
            print(f"[AI AUTOMATION] ✅ Laje {laje.nome} processada ({idx+1}/{total}).")
            QApplication.processEvents()
            
            # Delay final antes da próxima
            time.sleep(0.4)

        # Atualização final da UI após todo o lote
        pavimento_atual = next(
            (p for p in self.obra_atual.pavimentos if p.nome == _pav_cmb_raw(self.pavimento_combo)),
            None
        )
        if pavimento_atual:
            self._populate_tree(pavimento_atual.lajes)

        # Salvar uma última vez para garantir que tudo está persistido
        # (cada laje já foi salva individualmente, mas este é um salvamento final de segurança)
        main_window = self.parent()
        while main_window and not hasattr(main_window, 'save_all_obras_auto'):
            main_window = main_window.parent()
        
        if main_window and hasattr(main_window, 'save_all_obras_auto'):
            main_window.save_all_obras_auto()
            print("[AI AUTOMATION] ✅ Salvamento final de segurança concluído.")
        else:
            # Fallback: emitir sinal obra_changed para que MainWindow salve
            self.obra_changed.emit(self.obra_atual)
            print("[AI AUTOMATION] ✅ Sinal final emitido para salvamento.")

        print("[AI AUTOMATION] Processamento concluído com sucesso. Todas as lajes foram salvas individualmente.")




class AIFeedbackWidget(QFrame):
    """Widget de feedback para IA (Aprovar/Refinar/Erro) - Movido para LajeTab"""
    approved = Signal()
    manual_refine = Signal()
    report_error = Signal(str)
    
    def __init__(self, kept: int, removed: int, parent=None):
        super().__init__(parent)
        self.kept = kept
        self.removed = removed
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Estilo Frame
        self.setStyleSheet("""
            AIFeedbackWidget {
                background-color: {DS.BASE};
                border: 1px solid {DS.BORDER_STR};
                border-radius: 5px;
                margin-top: 5px;
            }
            QLabel { color: {DS.SECONDARY}; font-size: 11px; }
        """)
        
        # Header Stats
        lbl_stats = QLabel(f"<b>IA Cotas Sugeriu:</b><br>Mantidas: <span style='color:{DS.SUCCESS}'>{self.kept}</span> | Ocultas: <span style='color:{DS.DANGER}'>{self.removed}</span>")
        lbl_stats.setTextFormat(Qt.TextFormat.RichText)
        lbl_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_stats)
        
        # Botões
        # 1. Aprovar (Verde)
        btn_approve = QPushButton("✅ Aprovar Resultado")
        btn_approve.setStyleSheet("""
            QPushButton {
                background-color: {DS.SUCCESS_DK}; color: white; border: none; padding: 6px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: {DS.SUCCESS}; }
        """)
        btn_approve.clicked.connect(self.approved.emit)
        layout.addWidget(btn_approve)
        
        # 2. Refinar Manual (Amarelo)
        btn_manual = QPushButton("✏️ Refinar Manualmente")
        btn_manual.setStyleSheet("""
            QPushButton {
                background-color: {DS.GOLD}; color: white; border: none; padding: 6px; border-radius: 4px;
            }
            QPushButton:hover { background-color: {DS.GOLD}; }
        """)
        btn_manual.clicked.connect(self.manual_refine.emit)
        layout.addWidget(btn_manual)
        
        # 3. Reportar Erros (Vermelho) - Toggle
        self.btn_error_toggle = QPushButton("⚠️ Selecionar Erros...")
        self.btn_error_toggle.setStyleSheet("""
            QPushButton {
                background-color: {DS.DANGER}; color: white; border: none; padding: 6px; border-radius: 4px;
            }
            QPushButton:hover { background-color: {DS.DANGER}; }
        """)
        self.btn_error_toggle.setCheckable(True)
        self.btn_error_toggle.toggled.connect(self.toggle_error_section)
        layout.addWidget(self.btn_error_toggle)
        
        # Seção de Erro (Oculta incialmente)
        self.error_container = QWidget()
        self.error_container.setVisible(False)
        err_layout = QVBoxLayout(self.error_container)
        err_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_info = QLabel("Descreva o erro (opcional):")
        err_layout.addWidget(lbl_info)
        
        self.txt_comment = QTextEdit()
        self.txt_comment.setPlaceholderText("Ex: Cotas sobrepostas, cota incorreta...")
        self.txt_comment.setMaximumHeight(60)
        self.txt_comment.setStyleSheet(f"background-color: {DS.DEEP}; border: 1px solid {DS.BORDER}; color: white;")
        err_layout.addWidget(self.txt_comment)
        
        btn_send_error = QPushButton("Iniciar Seleção de Erros")
        btn_send_error.setStyleSheet(f"background-color: {DS.DANGER}; color: white; border-radius: 4px; padding: 5px;")
        btn_send_error.clicked.connect(self.on_send_error)
        err_layout.addWidget(btn_send_error)
        
        layout.addWidget(self.error_container)
        
    def toggle_error_section(self, checked):
        self.error_container.setVisible(checked)
        
    def on_send_error(self):
        comment = self.txt_comment.toPlainText()
        self.report_error.emit(comment)
