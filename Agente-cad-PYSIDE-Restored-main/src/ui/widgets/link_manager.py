import json
import logging
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFrame, QScrollArea, QInputDialog, QMessageBox, QLineEdit)
from PySide6.QtCore import Qt, Signal
from src.ui.widgets.interpretation_dialog import InterpretationDialog
from src.ui.theme import Colors, Fonts, Radius

class LinkManager(QWidget):
    """
    Mini-widget para gerenciamento de vínculos com suporte a Classes (Slots) de objetos.
    Cada slot representa uma informação necessária para o campo.
    """
    focus_requested = Signal(dict)
    remove_requested = Signal(dict)
    pick_requested = Signal(str) # slot_id|role
    research_requested = Signal(str) # slot_id
    element_removed = Signal(dict)
    training_requested = Signal(dict) # {slot, link, comment, status}
    config_changed = Signal(str, list) # field_key, updated_slots_config
    metadata_changed = Signal(str, str, dict) # slot_id, type="interpretation", data={prompt, patterns}
    
    # New Signals for Hierarchy Validation
    slot_validated = Signal(str, bool) # slot_id, checked
    slot_na_toggled = Signal(str, bool) # slot_id, checked

    SLOT_CONFIG = {
        '_l1_n': [
            {'id': 'label', 'name': 'Identificador Laje', 'type': 'text', 'prompt': 'Busque textos "L" + numeral próximo ao pilar.', 'help': 'Texto "Lxx". Define qual painel de laje descarrega aqui.'},
            {'id': 'void_x', 'name': 'Vazio (X)', 'type': 'poly', 'prompt': 'Desenhe as linhas do "X" que indica vazio. [Enter] para finalizar.', 'help': 'Marca este setor como "SEM LAJE" (Vazios/Shafts).'}
        ],
        '_l1_h': [
            {'id': 'thick', 'name': 'Texto de Espessura', 'type': 'text', 'prompt': 'Busque padrões "H=" ou "d=" próximo à laje. regex: ([Hd]=?\\d+)', 'help': 'Texto "H=12" ou "d=12". Define a altura da laje.'}
        ],
        '_l1_v': [
            {'id': 'level', 'name': 'Nível da Laje', 'type': 'text', 'prompt': 'Busque cotas de nível (+0.00) próximas. regex: ([+-]\\d+\\.\\d+)', 'help': 'Cota de nível (ex: +3.00). Define a base de apoio.'}
        ],
        '_segs': [ 
            {'id': 'segments', 'name': 'Geometria Real', 'type': 'poly', 'prompt': 'Desenhe as linhas que definem o contorno. [Enter] para finalizar.', 'help': 'Linhas/Polilinhas no CAD que representam o corpo do objeto.'}
        ],
        '_v_': [ 
            {'id': 'label', 'name': 'Identificador Viga', 'type': 'text', 'prompt': 'Busque textos "V" + numeral cruzando o pilar.', 'help': 'Texto "Vxx". Identifica a viga de suporte.'}
        ],
        '_viga_': [ 
            {'id': 'label', 'name': 'Identificador Viga', 'type': 'text', 'prompt': 'Busque o nome da viga neste trecho.', 'help': 'Identificador da viga neste trecho.'}
        ],
        'name': [
            {'id': 'label', 'name': 'Identificador Primário', 'type': 'text', 'prompt': 'Busque o texto Pxx central ao pilar.', 'help': 'O texto "Pxx" que identifica o pilar.'}
        ],
        'dim': [
            {'id': 'label', 'name': 'Texto de Dimensão', 'type': 'text', 'prompt': 'Busque textos de seção (ex: 20x50, 15/40). regex: (\\d+[\\s]*[xX/][\\s]*\\d+)', 'help': 'Texto "20x50" que define a seção bruta.'}
        ],
        '_beam_dim': [
            {'id': 'dim', 'name': 'Texto de Dimensão', 'type': 'text', 'prompt': 'Busque textos com 2 números (ex: 20x50, 100/60, (10x40), (50/54)). regex: (\\d+\\s*[xX/]\\s*\\d+)', 'help': 'Texto de seção da viga.'}
        ],
        '_dist_c': [
            {'id': 'dist_text', 'name': 'Distância (Texto/Cota)', 'type': 'text', 'prompt': 'Busque texto/cota de distância próximo ao corte. regex: (\\d+[\\.,]?\\d*)', 'help': 'Valor numérico da distância ao centro.'},
            {'id': 'dist_line', 'name': 'Distância (Linha)', 'type': 'poly', 'prompt': 'Desenhe a linha representando a distância. [Enter] para finalizar.', 'help': 'Linha medida no CAD para extrair o valor.'}
        ],
        '_diff_v': [
            {'id': 'diff_text', 'name': 'Diferença de Nível (Texto/Cota)', 'type': 'text', 'prompt': 'Busque texto/cota de diferença de nível. regex: ([+-]?\\d+[\\.,]?\\d*)', 'help': 'Valor numérico da diferença de nível.'},
            {'id': 'diff_line', 'name': 'Diferença de Nível (Linha)', 'type': 'poly', 'prompt': 'Desenhe a linha representando a diferença de nível. [Enter] para finalizar.', 'help': 'Linha medida no CAD para extrair o valor.'}
        ],
        '_v_esq_segs': [
            {'id': 'seg_cont', 'name': 'Segmento de Continuação', 'type': 'poly', 'prompt': 'Desenhe os segmentos da viga de continuação. [Enter] para finalizar.', 'help': 'Referência geométrica da viga que continua do pilar.'}
        ],
        '_v_dir_segs': [
            {'id': 'seg_cont', 'name': 'Segmento de Continuação', 'type': 'poly', 'prompt': 'Desenhe os segmentos da viga de continuação. [Enter] para finalizar.', 'help': 'Referência geométrica da viga que continua do pilar.'}
        ],
        '_v_ch': [
            {'id': 'seg_1', 'name': 'Segmento Chegada 1', 'type': 'poly', 'prompt': 'Desenhe a primeira linha da viga de chegada. [Enter] para finalizar.', 'help': 'Segmento 1 da viga que chega no pilar.'},
            {'id': 'seg_2', 'name': 'Segmento Chegada 2', 'type': 'poly', 'prompt': 'Desenhe a segunda linha da viga de chegada. [Enter] para finalizar.', 'help': 'Segmento 2 da viga que chega no pilar.'}
        ],
        '_viga_segs': [
             {'id': 'seg_bottom', 'name': 'Segmentos Fundos', 'type': 'poly', 'prompt': 'Desenhe os segmentos do Fundo. [Enter] para finalizar.', 'help': 'Linhas do fundo da viga.'}
        ],
        '_viga_seg_side_a': [
             {'id': 'seg_side_a', 'name': 'Segmentos Lado A', 'type': 'poly', 'prompt': 'Desenhe os segmentos do Lado A. [Enter] para finalizar.', 'help': 'Linhas do lado A da viga.'}
        ],
        '_viga_seg_side_b': [
             {'id': 'seg_side_b', 'name': 'Segmentos Lado B', 'type': 'poly', 'prompt': 'Desenhe os segmentos do Lado B. [Enter] para finalizar.', 'help': 'Linhas do lado B da viga.'}
        ],
        '_ajuste_comprimento': [
             {'id': 'adjustment', 'name': 'Segmento de Ajuste', 'type': 'line', 'prompt': 'Ajuste automático gerado (+10cm).', 'help': 'Extensão automática para valor inteiro.'}
        ],
        '_fundo_segs': [
             {'id': 'contour', 'name': 'Contorno Fundo', 'type': 'poly', 'prompt': 'Desenhe o perímetro do fundo (Polyline). [Enter] para finalizar.', 'help': 'Geometria do fundo da viga.'}
        ],
        '_location': [
             {'id': 'label', 'name': 'Texto do Apoio', 'type': 'text', 'prompt': 'Identifique o texto do pilar ou viga de apoio.', 'help': 'Texto (ex: P1 ou V2) que identifica o suporte.'},
             {'id': 'geometry', 'name': 'Geometria do Apoio', 'type': 'poly', 'prompt': 'Desenhe os segmentos do apoio. [Enter] para finalizar.', 'help': 'Referência visual/geométrica do objeto de apoio.'}
        ],
        '_laje_geom': [
             {'id': 'contour', 'name': 'Contorno Laje', 'type': 'poly', 'prompt': 'Desenhe o perímetro da laje. [Enter] para finalizar.', 'help': 'Geometria da área da laje.', 'patterns': 'Polilinha Fechada (LWPOLYLINE)\nLayer: ARQ_LAJE, CONCRETO\nDeve estar fechada.'},
             {'id': 'acrescimo_borda', 'name': 'ACRESCIMO DE 10 CM POR ESTAR NO BORDE DA OBRA', 'type': 'poly', 'prompt': 'Desenhe o acréscimo de 10cm na direção do borde. [Enter] para finalizar.', 'help': 'Desenho extra de 10cm na direção do borde se a laje tocar o borde.', 'patterns': 'Linha ou Polilinha\nExtensão de exatos 10cm na direção externa.'}
        ],
        '_laje_complex': [
             {'id': 'label', 'name': '1. Nome da Laje', 'type': 'text', 'prompt': 'Busque o texto identificador (Ex: L1).', 'help': 'Identificador da laje.'},
             {'id': 'dim', 'name': '2. Dimensão (Valor)', 'type': 'text', 'prompt': 'Busque o texto de dimensão (Ex: H=12).', 'help': 'Define o valor do campo.'},
             {'id': 'cut_view', 'name': '3. Visão de Corte', 'type': 'poly', 'prompt': 'Desenhe a linha de corte/T sobre a viga. [Enter] para finalizar.', 'help': 'Referência visual da posição da laje.'}
        ],
        '_abert_pilar_esq': [
             {'id': 'label', 'name': '1. Texto Pilar', 'type': 'text', 'prompt': 'Identifique o nome do pilar.'},
             {'id': 'segment', 'name': '2. Segmento Pilar', 'type': 'poly', 'prompt': 'Desenhe o contorno do pilar.'},
             {'id': 'contact_lines', 'name': '3. Linhas Contato', 'type': 'poly', 'prompt': 'Desenhe Dist + Larg contato.'},
             {'id': 'cont_tip_esq', 'name': '4. Cont. Esq', 'type': 'poly', 'prompt': 'Desenhe continuidade esquerda.'},
             {'id': 'cont_tip_dir', 'name': '5. Cont. Dir', 'type': 'poly', 'prompt': 'Desenhe continuidade direita.'}
        ],
        '_abert_pilar_dir': [
             {'id': 'label', 'name': '1. Texto Pilar', 'type': 'text', 'prompt': 'Identifique o nome do pilar.'},
             {'id': 'segment', 'name': '2. Segmento Pilar', 'type': 'poly', 'prompt': 'Desenhe o contorno do pilar.'},
             {'id': 'contact_lines', 'name': '3. Linhas Contato', 'type': 'poly', 'prompt': 'Desenhe Dist + Larg contato.'},
             {'id': 'cont_tip_esq', 'name': '4. Cont. Esq', 'type': 'poly', 'prompt': 'Desenhe continuidade esquerda.'},
             {'id': 'cont_tip_dir', 'name': '5. Cont. Dir', 'type': 'poly', 'prompt': 'Desenhe continuidade direita.'}
        ],
        '_abert_viga_top_esq': [
             {'id': 'arr_label', 'name': '1. Nome Viga', 'type': 'text', 'prompt': 'Nome da viga que chega.'},
             {'id': 'arr_geom', 'name': '2. Geometria', 'type': 'poly', 'prompt': 'Desenhe a viga que chega.'},
             {'id': 'arr_dim', 'name': '3. Dimensões', 'type': 'text', 'prompt': 'Busque texto tipo 20x60.'},
             {'id': 'adj_mouth', 'name': '4. Ajuste Boca', 'type': 'poly', 'prompt': 'Desenhe ajuste boca.'},
             {'id': 'adj_depth', 'name': '5. Ajuste Prof.', 'type': 'poly', 'prompt': 'Desenhe ajuste profundidade.'}
        ],
        '_abert_viga_top_dir': [
             {'id': 'arr_label', 'name': '1. Nome Viga', 'type': 'text', 'prompt': 'Nome da viga que chega.'},
             {'id': 'arr_geom', 'name': '2. Geometria', 'type': 'poly', 'prompt': 'Desenhe a viga que chega.'},
             {'id': 'arr_dim', 'name': '3. Dimensões', 'type': 'text', 'prompt': 'Busque texto tipo 20x60.'},
             {'id': 'adj_mouth', 'name': '4. Ajuste Boca', 'type': 'poly', 'prompt': 'Desenhe ajuste boca.'},
             {'id': 'adj_depth', 'name': '5. Ajuste Prof.', 'type': 'poly', 'prompt': 'Desenhe ajuste profundidade.'}
        ],
        '_abert_viga_fun_esq': [
             {'id': 'arr_label', 'name': '1. Nome Viga', 'type': 'text', 'prompt': 'Nome da viga que chega.'},
             {'id': 'arr_geom', 'name': '2. Geometria', 'type': 'poly', 'prompt': 'Desenhe a viga que chega.'},
             {'id': 'arr_dim', 'name': '3. Dimensões', 'type': 'text', 'prompt': 'Busque texto tipo 20x60.'},
             {'id': 'adj_mouth', 'name': '4. Ajuste Boca', 'type': 'poly', 'prompt': 'Desenhe ajuste boca.'},
             {'id': 'adj_depth', 'name': '5. Ajuste Prof.', 'type': 'poly', 'prompt': 'Desenhe ajuste profundidade.'}
        ],
        '_abert_viga_fun_dir': [
             {'id': 'arr_label', 'name': '1. Nome Viga', 'type': 'text', 'prompt': 'Nome da viga que chega.'},
             {'id': 'arr_geom', 'name': '2. Geometria', 'type': 'poly', 'prompt': 'Desenhe a viga que chega.'},
             {'id': 'arr_dim', 'name': '3. Dimensões', 'type': 'text', 'prompt': 'Busque texto tipo 20x60.'},
             {'id': 'adj_mouth', 'name': '4. Ajuste Boca', 'type': 'poly', 'prompt': 'Desenhe ajuste boca.'},
             {'id': 'adj_depth', 'name': '5. Ajuste Prof.', 'type': 'poly', 'prompt': 'Desenhe ajuste profundidade.'}
        ],
        '_laje_dim': [
             {'id': 'label', 'name': 'Vínculo de Texto (Dimensão)', 'type': 'text', 'prompt': 'Busque o texto de dimensão (Ex: H=12).', 'help': 'Texto identificador da espessura/dimensão da laje.', 'patterns': 'REGEX: [HhDd][= :]?\\d+\nExemplos: H=12, d=10, h=15\nLayer: ARQ_TXT_LAJE'}
        ],
        '_laje_level': [
             {'id': 'label', 'name': 'Vínculo Texto (Nível)', 'type': 'text', 'prompt': 'Busque o texto de nível da laje (Ex: +2.80).', 'help': 'Cota de nível da laje.', 'patterns': 'REGEX: [+-]?\\d+\\.\\d+|[+-]?\\d+\nExemplos: +2.80, 280, N+2.80\nPrioridade: Texto próximo ao centro.'},
             {'id': 'cut_view_geom', 'name': 'Visão de Corte (Geometria)', 'type': 'poly', 'prompt': 'Desenhe a referência de visão de corte da viga que contorna a laje. [Enter] para finalizar.', 'help': 'Referência geométrica de viga para definir o nível.'},
             {'id': 'cut_view_text', 'name': 'Visao corte texto', 'type': 'text', 'prompt': 'Busque textos de visão de corte.', 'help': 'Vínculo de texto normal, similar ao nível.', 'patterns': 'Texto indicando corte ou vista.'}
        ],
        '_laje_islands': [
             {'id': 'contour', 'name': 'Contorno da Ilha', 'type': 'poly', 'prompt': 'Desenhe o contorno da ilha (polígono fechado). [Enter] para finalizar.', 'help': 'Define a geometria do furo interno.'}
        ],
        '_height_complex': [
             {'id': 'dim', 'name': '1. Dimensão (Valor)', 'type': 'text', 'prompt': 'Busque o texto de altura.', 'help': 'Define o valor da altura.'},
             {'id': 'cut_view', 'name': '2. Visão de Corte', 'type': 'poly', 'prompt': 'Desenhe a referência visual. [Enter] para finalizar.', 'help': 'Referência visual.'}
        ],
        '_pilar_opening': [
             {'id': 'label', 'name': '1. Texto Pilar', 'type': 'text', 'prompt': 'Identifique o nome do pilar.', 'help': 'Identificação do pilar.'},
             {'id': 'segment', 'name': '2. Segmento Pilar', 'type': 'poly', 'prompt': 'Desenhe o contorno do pilar. [Enter] para finalizar.', 'help': 'Geometria do pilar.'},
             {'id': 'contact_lines', 'name': '3. Linhas de Contato', 'type': 'poly', 'prompt': 'Desenhe 1 linha (Largura) ou 2 linhas (Dist + Larg) de contato com a viga. [Enter] para finalizar.', 'help': 'Define Distância e Largura.'},
             {'id': 'cont_tip_esq', 'name': '4. Continuidade (Ponta Esq)', 'type': 'poly', 'prompt': 'Desenhe a linha da viga na esquerda da interseção. [Enter] para finalizar.', 'help': 'Define se continua ou para (lado esq).'},
             {'id': 'cont_tip_dir', 'name': '5. Continuidade (Ponta Dir)', 'type': 'poly', 'prompt': 'Desenhe a linha da viga na direita da interseção. [Enter] para finalizar.', 'help': 'Define se continua ou para (lado dir).'}
        ],
        '_beam_opening': [
             {'id': 'arr_label', 'name': '1. Nome Viga Chegada', 'type': 'text', 'prompt': 'Identifique o nome da viga que chega.', 'help': 'Identificação da viga.'},
             {'id': 'arr_geom', 'name': '2. Geometria Viga Chegada', 'type': 'poly', 'prompt': 'Desenhe a viga que chega. [Enter] para finalizar.', 'help': 'Geometria da viga.'},
             {'id': 'arr_dim', 'name': '3. Dimensões Viga Chegada', 'type': 'text', 'prompt': 'Busque texto tipo 20x60.', 'help': 'Define Largura Boca e Profundidade.'},
             {'id': 'curr_dim', 'name': '4. Dimensões Viga Atual', 'type': 'text', 'prompt': 'Busque dimensões da viga atual.', 'help': 'Referência cruzada.'},
             {'id': 'adj_mouth', 'name': '5. Ajuste Boca', 'type': 'text', 'mode': 'manual', 'default': '8', 'prompt': 'Valor manual de ajuste da boca.', 'help': 'Valor fixo para ajuste da boca (cm).'},
             {'id': 'adj_depth', 'name': '6. Ajuste Profundidade', 'type': 'text', 'mode': 'manual', 'default': '4', 'prompt': 'Valor manual de ajuste da profundidade.', 'help': 'Valor fixo para ajuste da profundidade (cm).'}
        ],
        '_comprimento_total': [
             {'id': 'geometry', 'name': 'Linha de Comprimento', 'type': 'poly', 'prompt': 'Desenhe a linha total do vão. [Enter] para finalizar.', 'help': 'Define o valor do comprimento.'}
        ],
        '_cut_view_complex': [
             {'id': 'geometry', 'name': 'Geometria Visão Corte', 'type': 'poly', 'prompt': 'Desenhe as linhas da visão de corte. [Enter] para finalizar.', 'help': 'Geometria visual do corte.'},
             {'id': 'h1_a', 'name': 'Medida Altura H1 (Lado A)', 'type': 'text', 'prompt': 'Selecione o texto H1 A.', 'help': 'Texto H1 Lado A.'},
             {'id': 'h1_b', 'name': 'Medida Altura H1 (Lado B)', 'type': 'text', 'prompt': 'Selecione o texto H1 B.', 'help': 'Texto H1 Lado B.'},
             {'id': 'h2_a', 'name': 'Medida Altura H2 (Lado A)', 'type': 'text', 'prompt': 'Selecione o texto H2 A.', 'help': 'Texto H2 Lado A.'},
             {'id': 'h2_b', 'name': 'Medida Altura H2 (Lado B)', 'type': 'text', 'prompt': 'Selecione o texto H2 B.', 'help': 'Texto H2 Lado B.'},
             {'id': 'laje_inf_a', 'name': 'Laje Inferior (Lado A)', 'type': 'text', 'prompt': 'Selecione o texto Laje Inf A.', 'help': 'Texto Laje Inferior A.'},
             {'id': 'laje_inf_b', 'name': 'Laje Inferior (Lado B)', 'type': 'text', 'prompt': 'Selecione o texto Laje Inf B.', 'help': 'Texto Laje Inferior B.'},
             {'id': 'laje_cen_a', 'name': 'Laje Central (Lado A)', 'type': 'text', 'prompt': 'Selecione o texto Laje Cen A.', 'help': 'Texto Laje Central A.'},
             {'id': 'laje_cen_b', 'name': 'Laje Central (Lado B)', 'type': 'text', 'prompt': 'Selecione o texto Laje Cen B.', 'help': 'Texto Laje Central B.'},
             {'id': 'laje_sup_a', 'name': 'Laje Superior (Lado A)', 'type': 'text', 'prompt': 'Selecione o texto Laje Sup A.', 'help': 'Texto Laje Superior A.'},
             {'id': 'laje_sup_b', 'name': 'Laje Superior (Lado B)', 'type': 'text', 'prompt': 'Selecione o texto Laje Sup B.', 'help': 'Texto Laje Superior B.'}
        ],
        '_marco_vigas': [
             {'id': 'default', 'name': 'Vigas na Extremidade', 'type': 'poly', 'prompt': 'Selecione todos os segmentos de vigas que devem tocar a parede. [Enter] para finalizar.', 'help': 'Linhas/Vigas que o sistema deve estender para criar o marco.'}
        ],
        '_marco_extensao': [
             {'id': 'main', 'name': 'Linha da Viga (Total)', 'type': 'poly', 'prompt': 'Selecione a linha completa da viga para referência de comprimento.', 'help': 'Geometria principal da viga.'},
             {'id': 'default', 'name': 'Segmento de Ajuste (+-10cm)', 'type': 'poly', 'prompt': 'Desenhe ou selecione as linhas de 10cm de continuação. [Enter] para finalizar.', 'help': 'Segmentos que saem das vigas em direção ao marco.'}
        ],
        '_marco_uniao': [
             {'id': 'default', 'name': 'Uniões do Marco', 'type': 'poly', 'prompt': 'Desenhe as linhas de fechamento do perímetro (Marco). [Enter] para finalizar.', 'help': 'Linhas que conectam as extensões para fechar a obra.'}
        ],
        'default': [
            {'id': 'main', 'name': 'Vínculo Principal', 'type': 'text', 'prompt': 'Identifique o elemento principal no CAD.', 'help': 'Texto ou objeto que define o valor deste campo.'}
        ]
    }

    def __init__(self, field_id, current_links, na_slots=None, validated_slots=None, parent=None):
        super().__init__(parent)
        self.field_id = field_id
        # links agora é um dicionário: {slot_id: [links...]}
        self.links = current_links if isinstance(current_links, dict) else {}
        self.na_slots = set(na_slots) if na_slots else set()
        self.validated_slots = set(validated_slots) if validated_slots else set()
        self.metadata_cache = {}
        self.init_ui()

    def _get_slots(self, field_id):
        # Ordem de prioridade: das mais específicas para as mais genéricas
        if '_v_esq_segs' in field_id:
            return self.SLOT_CONFIG['_v_esq_segs']
        if '_v_dir_segs' in field_id:
            return self.SLOT_CONFIG['_v_dir_segs']
        if '_v_ch' in field_id and '_segs' in field_id:
            return self.SLOT_CONFIG['_v_ch']
        
        if 'viga_fundo' in field_id and '_segs' in field_id:
             return self.SLOT_CONFIG['_fundo_segs']
        if 'laje_dim' in field_id or ('dim' in field_id and 'laje' in field_id):
             return self.SLOT_CONFIG['_laje_dim']
        if 'laje_nivel' in field_id:
             return self.SLOT_CONFIG['_laje_level']
        
        if 'laje' in field_id and ('_geom' in field_id or 'outline' in field_id):
             return self.SLOT_CONFIG['_laje_geom']
        
        if 'island' in field_id:
             return self.SLOT_CONFIG['_laje_islands']

        if 'laje' in field_id and not '_geom' in field_id:
             return self.SLOT_CONFIG['_laje_complex']
        
        if '_h1' in field_id or '_h2' in field_id:
             return self.SLOT_CONFIG['_height_complex']

        if '_abert_pilar_esq' in field_id:
             return self.SLOT_CONFIG['_abert_pilar_esq']
        if '_abert_pilar_dir' in field_id:
             return self.SLOT_CONFIG['_abert_pilar_dir']

        if '_abert_viga_top_esq' in field_id:
             return self.SLOT_CONFIG['_abert_viga_top_esq']
        if '_abert_viga_top_dir' in field_id:
             return self.SLOT_CONFIG['_abert_viga_top_dir']
        if '_abert_viga_fun_esq' in field_id:
             return self.SLOT_CONFIG['_abert_viga_fun_esq']
        if '_abert_viga_fun_dir' in field_id:
             return self.SLOT_CONFIG['_abert_viga_fun_dir']
             
        if '_comprimento' in field_id and '_ajuste' not in field_id:
             return self.SLOT_CONFIG['_comprimento_total']
        
        if '_ajuste_comprimento' in field_id:
             return self.SLOT_CONFIG['_ajuste_comprimento']

        if '_visao_corte' in field_id:
            return self.SLOT_CONFIG['_cut_view_complex']

        if 'vigas_extremidade' in field_id:
            return self.SLOT_CONFIG['_marco_vigas']
        if 'extensoes' in field_id or 'ext_viga_' in field_id:
            return self.SLOT_CONFIG['_marco_extensao']
        if 'unioes_marco' in field_id:
            return self.SLOT_CONFIG['_marco_uniao']

        if 'comp_total_passa' in field_id:
            # Detectar se é lado A ou B
            if 'viga_a_' in field_id:
                return self.SLOT_CONFIG['_viga_seg_side_a']
            elif 'viga_b_' in field_id:
                return self.SLOT_CONFIG['_viga_seg_side_b']
        
        if 'viga_' in field_id and '_segs' in field_id:
            return self.SLOT_CONFIG['_viga_segs']
        
        if any(x in field_id for x in ['_ini_name', '_end_name', '_local_ini', '_local_fim']):
            return self.SLOT_CONFIG['_location']
        
        if '_dist_c' in field_id:
            return self.SLOT_CONFIG['_dist_c']
        if '_diff_v' in field_id:
            return self.SLOT_CONFIG['_diff_v']
        if field_id.startswith('p_s') and '_v_' in field_id and field_id.endswith('_d'):
            return self.SLOT_CONFIG['_beam_dim']
        if field_id.endswith('_dim'):
            return self.SLOT_CONFIG['dim']
        
        for key in self.SLOT_CONFIG:
            if key in field_id:
                return self.SLOT_CONFIG[key]
        return self.SLOT_CONFIG['default']

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.setStyleSheet("""
            QWidget { 
                background-color: {Colors.BG_DEEP};
                color: {Colors.TEXT_PRIMARY};
            }
            QLabel { color: {Colors.TEXT_PRIMARY}; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
            .HeaderLabel { font-size: 14px; font-weight: bold; color: {Colors.ACCENT_PRIMARY}; margin-bottom: 5px; }
            
            /* SLOT CARD DESIGN */
            .SlotFrame { 
                background: {Colors.BG_PANEL}; 
                border: 1px solid {Colors.BORDER_DEFAULT}; 
                border-radius: 8px; 
                padding: 10px; 
                margin-bottom: 5px; 
            }
            .SlotFrameValidated { 
                background: rgba(0,230,118,13); 
                border: 1px solid {Colors.ACCENT_SUCCESS_ALT}; 
                border-radius: 8px; 
                padding: 10px; 
                margin-bottom: 5px; 
            }
            .SlotTitle { 
                font-size: 12px; 
                font-weight: bold; 
                color: {Colors.TEXT_BRIGHT}; 
                background: transparent; 
                border: none;
                padding: 2px;
            }
            
            /* LINK ITEM CARD DESIGN */
            .LinkItem { 
                background: {Colors.BG_CARD}; 
                border-left: 3px solid {Colors.ACCENT_PRIMARY}; 
                border-radius: 4px; 
                padding: 6px; 
                margin-top: 5px; 
            }
            .LinkItemValidated { 
                background: rgba(27,58,36,1); 
                border-left: 4px solid {Colors.ACCENT_SUCCESS}; 
                border-radius: 4px; 
                padding: 6px; 
                margin-top: 5px; 
            }
            .LinkItemFailed { 
                background: rgba(58,27,27,1); 
                border-left: 4px solid {Colors.ACCENT_DANGER}; 
                border-radius: 4px; 
                padding: 6px; 
                margin-top: 5px; 
            }
            .LinkValue { 
                color: {Colors.TEXT_BRIGHT}; 
                font-weight: bold; 
                font-size: 11px; 
                font-family: 'Consolas', monospace; 
            }
            
            /* BUTTONS */
            QPushButton {
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
                padding: 4px 8px;
            }
            
            QPushButton.AddBtn { 
                background: {Colors.BG_PANEL}; color: {Colors.ACCENT_WARNING_ALT}; border: 1px dashed {Colors.BORDER_INPUT}; 
                font-size: 11px; padding: 6px; text-align: center;
            }
            QPushButton.AddBtn:hover { background: {Colors.BG_CARD}; color: {Colors.ACCENT_INFO}; }
            
            QPushButton.ActionBtn { background: {Colors.BG_CARD}; border: none; color: {Colors.TEXT_BRIGHT}; }
            QPushButton.ActionBtn:hover { background: {Colors.BORDER_INPUT}; }
            
            QPushButton.DelBtn { background: {Colors.BG_CARD}; color: {Colors.ACCENT_DANGER}; }
            QPushButton.DelBtn:hover { background: #332222; }  /* hardcoded-ok: Colors.BG_DANGER_DARK */

            /* TRAINING BUTTONS */
            QPushButton.TrainBtn { background: {Colors.BG_PANEL}; border: 1px solid {Colors.BORDER_DEFAULT}; }
            QPushButton.TrainSuccess { color: {Colors.ACCENT_SUCCESS}; }
            QPushButton.TrainSuccess:hover { background: rgba(27,58,36,1); border-color: {Colors.ACCENT_SUCCESS}; }
            QPushButton.TrainFail { color: {Colors.ACCENT_DANGER}; }
            QPushButton.TrainFail:hover { background: rgba(58,27,27,1); border-color: {Colors.ACCENT_DANGER}; }
        """)

        # Container direto (Sem ScrollArea interna)
        self.slots_container = QVBoxLayout()
        self.slots_container.setSpacing(10)
        self.slots_container.setContentsMargins(8, 8, 8, 8)
        
        layout.addLayout(self.slots_container)

        self.refresh_list()

    def refresh_list(self):
        try:
            if self.slots_container is None: return
            
            # Limpar layout (QVBoxLayout)
            # Check type to avoid 'count' error on Widget
            if not isinstance(self.slots_container, QVBoxLayout):
                # Fallback panic mode
                print(f"[LinkManager] Error: slots_container is {type(self.slots_container)}, expected QVBoxLayout")
                return

            while self.slots_container.count():
                item = self.slots_container.takeAt(0)
                if item.widget(): 
                    item.widget().deleteLater()
                elif item.layout():
                    # Limpeza recursiva para layouts aninhados (h_wrapper_slot)
                    sub_layout = item.layout()
                    while sub_layout.count():
                        sub_item = sub_layout.takeAt(0)
                        if sub_item.widget(): 
                            sub_item.widget().deleteLater()
                    sub_layout.deleteLater()
        except RuntimeError:
            return

        slots = self._get_slots(self.field_id)
        
        for slot in slots:
            slot_id = slot['id']
            slot_links = self.links.get(slot_id, [])
            is_empty = len(slot_links) == 0

            slot_frame = QFrame()
            
            # Check if class is "Explicitly Validated"
            is_class_validated = slot_id in self.validated_slots
            
            if is_class_validated:
                slot_frame.setProperty("class", "SlotFrameValidated")
            else:
                slot_frame.setProperty("class", "SlotFrame")
                
            sf_layout = QVBoxLayout(slot_frame)
            sf_layout.setSpacing(5)

            # --- MANUAL MODE RENDER ---
            if slot.get('mode') == 'manual':
                # Layout Simplificado para Campos Manuais
                man_layout = QHBoxLayout()
                man_layout.setContentsMargins(0, 0, 0, 0)
                
                # Titulo
                lbl_name = QLabel(slot['name'].upper())
                lbl_name.setStyleSheet(f"font-weight: bold; color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
                man_layout.addWidget(lbl_name)
                
                # Input Valor Manual
                # Tentar recuperar valor existente nos links ou usar default
                current_val = slot.get('default', '')
                if not is_empty and slot_links:
                    current_val = str(slot_links[0].get('text', current_val))
                
                inp_manual = QLineEdit(current_val)
                inp_manual.setFixedWidth(60)
                inp_manual.setStyleSheet("""
                    QLineEdit { 
                        background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_INPUT}; color: {Colors.TEXT_BRIGHT}; 
                        padding: 2px; border-radius: 3px; font-weight: bold;
                    }
                    QLineEdit:focus { border: 1px solid {Colors.ACCENT_PRIMARY}; background: {Colors.BORDER_INPUT}; }
                """)
                
                # Salvar alteração simulando um link de texto
                def save_manual_val(text, s_id=slot_id):
                    # Cria estrutura de link fake para manter compatibilidade
                    fake_link = {'id': str(uuid.uuid4()), 'type': 'text', 'text': text, 'manual': True}
                    self.links[s_id] = [fake_link]
                    # Dispara signals necessários
                    self.config_changed.emit(self.field_id, []) 
                
                inp_manual.textChanged.connect(save_manual_val)
                man_layout.addWidget(inp_manual)
                man_layout.addStretch()
                
                # Help Icon
                btn_help = QPushButton("?")
                btn_help.setFixedSize(20, 20)
                btn_help.setStyleSheet(f"border: none; color: {Colors.TEXT_DIM}; font-weight: bold;")
                btn_help.setToolTip(slot.get('help', ''))
                man_layout.addWidget(btn_help)
                
                sf_layout.addLayout(man_layout)
                self.slots_container.addWidget(slot_frame)
                continue # Pula renderização padrão

            # --- STANDARD RENDER ---
            # Header
            header_layout = QHBoxLayout()
            st_lbl = QLabel(slot['name'].upper())
            st_lbl.setProperty("class", "SlotTitle")
            st_lbl.setWordWrap(True)
            
            # Application of N/A Style to Title
            is_na_slot = slot_id in self.na_slots
            if is_na_slot:
                st_lbl.setStyleSheet(f"color: {Colors.ACCENT_DANGER}; text-decoration: line-through;")
            
            header_layout.addWidget(st_lbl, 1)
            
            # --- ACTION BUTTONS (CLASS LEVEL) ---
            
            # 1. Validate Class (✔) -> Valida todos os vínculos internos
            btn_val_class = QPushButton("✔")
            btn_val_class.setFixedSize(24, 20)
            btn_val_class.setCheckable(True)
            btn_val_class.setChecked(is_class_validated)
            btn_val_class.setCursor(Qt.PointingHandCursor)
            btn_val_class.setToolTip(f"Validar todo o grupo '{slot['name']}' (Clique para desfazer)")
            
            if is_class_validated:
                btn_val_class.setStyleSheet("""
                    QPushButton { background: rgba(27,58,36,1); color: {Colors.ACCENT_SUCCESS_ALT}; border: 1px solid {Colors.ACCENT_SUCCESS_ALT}; border-radius: 4px; }
                    QPushButton:hover { background: {Colors.ACCENT_SUCCESS_ALT}; color: {Colors.TEXT_BRIGHT}; }
                """)
            else:
                btn_val_class.setStyleSheet("""
                    QPushButton { background: transparent; color: {Colors.ACCENT_SUCCESS_ALT}; border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px; }
                    QPushButton:hover { background: {Colors.ACCENT_SUCCESS_ALT}; color: {Colors.BG_DEEP}; border: 1px solid {Colors.ACCENT_SUCCESS_ALT}; }
                """)
                
            btn_val_class.clicked.connect(lambda checked, s_id=slot_id: self.slot_validated.emit(s_id, checked))
            header_layout.addWidget(btn_val_class)
            
            # 2. N/A Class (🚫) -> Marca classe como N/A e limpa vínculos
            btn_na_class = QPushButton("🚫")
            btn_na_class.setFixedSize(24, 20)
            btn_na_class.setCheckable(True)
            btn_na_class.setChecked(is_na_slot)
            btn_na_class.setCursor(Qt.PointingHandCursor)
            btn_na_class.setToolTip(f"Marcar '{slot['name']}' como Não se Aplica")
            btn_na_class.setStyleSheet(f"""
                QPushButton {{ 
                    background: {Colors.BG_DEEP if is_na_slot else 'transparent'}; 
                    color: {Colors.ACCENT_DANGER if is_na_slot else Colors.TEXT_SECONDARY}; 
                    border: 1px solid {Colors.ACCENT_DANGER if is_na_slot else Colors.BORDER_INPUT}; 
                    border-radius: 4px; 
                }}
                QPushButton:hover {{ background: {Colors.ACCENT_DANGER}; color: {Colors.TEXT_BRIGHT}; }}
            """)
            btn_na_class.clicked.connect(lambda checked, s_id=slot_id: self.slot_na_toggled.emit(s_id, checked))
            header_layout.addWidget(btn_na_class)
            
            # 3. Botão Interpretação (Nível de Classe/Slot)
            btn_interp = QPushButton("📝")
            btn_interp.setFixedSize(24, 20)
            btn_interp.setCursor(Qt.PointingHandCursor)
            btn_interp.setToolTip(f"Detalhamento e Padrões para {slot['name']}")
            btn_interp.setStyleSheet("""
                QPushButton { background: transparent; color: #b388ff; border: 1px solid {Colors.BORDER_INPUT}; border-radius: 4px; }
                QPushButton:hover { background: #b388ff; color: {Colors.TEXT_BRIGHT}; border: 1px solid #b388ff; }
            """)
            btn_interp.clicked.connect(lambda checked=False, s_id=slot_id, s_name=slot['name']: self._open_slot_interpretation(s_id, s_name))
            header_layout.addWidget(btn_interp)

            sf_layout.addLayout(header_layout)

            # Lista de Vínculos
            if not is_empty:
                for link in slot_links:
                    link_frame = QFrame()
                    is_valid = link.get('validated', False)
                    is_failed = link.get('failed', False)
                    
                    if is_valid:
                        link_frame.setProperty("class", "LinkItemValidated")
                    elif is_failed:
                        link_frame.setProperty("class", "LinkItemFailed")
                    else:
                        link_frame.setProperty("class", "LinkItem")
                        
                    lf_layout = QHBoxLayout(link_frame)
                    
                    val_text = str(link.get('text', 'Geometria'))
                    if len(val_text) > 30: val_text = val_text[:27] + "..."
                    
                    val_lbl = QLabel(val_text)
                    val_lbl.setProperty("class", "LinkValue")
                    
                    btn_focus = QPushButton("🔍")
                    btn_focus.setProperty("class", "ActionBtn")
                    btn_focus.setFixedSize(24, 20)
                    btn_focus.clicked.connect(lambda checked=False, l=link: self.focus_requested.emit(l))
                    
                    btn_del = QPushButton("❌")
                    btn_del.setProperty("class", "DelBtn")
                    btn_del.setFixedSize(24, 20)
                    btn_del.clicked.connect(lambda checked=False, s_id=slot_id, l=link: self._remove_link(s_id, l))
                    
                    # New: Training Buttons (Validate and Error)
                    btn_ok = QPushButton("✔")
                    btn_ok.setProperty("class", "TrainBtn TrainSuccess")
                    btn_ok.setFixedSize(24, 20)
                    btn_ok.setCheckable(True)
                    btn_ok.setChecked(is_valid)
                    btn_ok.setToolTip("Validar/Treinar IA (Clique novamente para desfazer)")
                    if is_valid: 
                        btn_ok.setStyleSheet(f"background: rgba(27,58,36,1); color: {Colors.ACCENT_SUCCESS}; border: 1px solid {Colors.ACCENT_SUCCESS};")
                        
                    btn_ok.clicked.connect(lambda checked, s=slot_id, l=link: self._handle_training_click(s, l, 'valid'))

                    btn_err = QPushButton("⚠️")
                    btn_err.setProperty("class", "TrainBtn TrainFail")
                    btn_err.setFixedSize(24, 20)
                    btn_err.setCheckable(True)
                    btn_err.setChecked(is_failed)
                    btn_err.setToolTip("Indicar Erro de IA (Clique novamente para desfazer)")
                    if is_failed:
                        btn_err.setStyleSheet(f"background: rgba(58,27,27,1); color: {Colors.ACCENT_DANGER}; border: 1px solid {Colors.ACCENT_DANGER};")
                        
                    btn_err.clicked.connect(lambda checked, s=slot_id, l=link: self._handle_training_click(s, l, 'fail'))

                    lf_layout.addWidget(val_lbl, 1)
                    
                    # Vertical Action Stack for "Micro Buttons"
                    actions_v = QVBoxLayout()
                    actions_v.setSpacing(4)

                    row1 = QHBoxLayout(); row1.setSpacing(4); row1.setContentsMargins(0,0,0,0)
                    row1.addWidget(btn_focus); row1.addWidget(btn_del)

                    row2 = QHBoxLayout(); row2.setSpacing(4); row2.setContentsMargins(0,0,0,0)
                    row2.addWidget(btn_ok); row2.addWidget(btn_err)
                    
                    actions_v.addLayout(row1)
                    actions_v.addLayout(row2)
                    lf_layout.addLayout(actions_v)
                    
                    sf_layout.addWidget(link_frame)

            # Botão Capturar
            btn_add = QPushButton(f"+ Capturar")
            btn_add.setProperty("class", "AddBtn")
            btn_add.clicked.connect(lambda checked=False, s=slot: self._on_pick_clicked(s))
            sf_layout.addWidget(btn_add)
            
            if self.field_id == 'laje_outline_segs':
                h_wrapper_slot = QHBoxLayout()
                h_wrapper_slot.setContentsMargins(0,0,0,0)
                
                # Diferenciar tamanho por tipo de slot (Contorno vs Acrescimo)
                s_name_lower = slot['name'].lower()
                if 'acrescimo' in s_name_lower or 'acréscimo' in s_name_lower:
                     h_wrapper_slot.addWidget(slot_frame, 5)
                     h_wrapper_slot.addStretch(5)
                else:
                     h_wrapper_slot.addWidget(slot_frame, 7)
                     h_wrapper_slot.addStretch(3)
                     
                self.slots_container.addLayout(h_wrapper_slot)
            else:
                self.slots_container.addWidget(slot_frame)
        
        # self.slots_container.addStretch() # Opcional em VBox direto
        
        self.slots_container.addStretch()

    def _on_pick_clicked(self, slot):
        # Transmite o pedido de captura para o DetailCard -> MainWindow
        self.pick_requested.emit(f"{slot['id']}|{slot['type']}")

    def _remove_link(self, slot_id, link):
        # Transmite o pedido de remoção
        self.remove_requested.emit({'slot': slot_id, 'link': link})
        # O DetailCard deve atualizar o item_data e chamar refresh_list do LM se necessário
        # Mas para feedback imediato na UI local:
        if slot_id in self.links:
            if link in self.links[slot_id]:
                self.links[slot_id].remove(link)
                self.refresh_list()

    def _handle_training_click(self, slot_id, link, target_status):
        """
        Gerencia o clique nos botões de treino (OK/Erro) com suporte a Toggle (Undo).
        """
        is_already_checked = (target_status == 'valid' and link.get('validated')) or \
                             (target_status == 'fail' and link.get('failed'))
        
        status = 'removed' if is_already_checked else target_status
        comment = f"Undo: {target_status}" if status == 'removed' else (
            'Validado via Drawer' if target_status == 'valid' else 'Erro via Drawer'
        )
        
        self.training_requested.emit({
            'slot': slot_id,
            'link': link,
            'comment': comment,
            'status': status
        })

    def _open_slot_interpretation(self, slot_id, slot_name):
        """Abre o diálogo de interpretação para uma CLASSE DE VÍNCULO (Slot) específica"""
        
        current_meta = self.metadata_cache.get(slot_id, {})
        
        # Fallback to default config if meta is empty
        default_prompt = ""
        default_patterns = ""
        default_patterns_na = ""
        
        # Encontra a configuração deste slot para pegar os defaults
        slots = self._get_slots(self.field_id)
        if slots:
            for s in slots:
                if s['id'] == slot_id:
                    default_prompt = s.get('prompt', "")
                    default_patterns = s.get('patterns', "")
                    default_patterns_na = s.get('patterns_na', "")
                    break
        
        current_prompt = current_meta.get('prompt', default_prompt)
        current_patterns = current_meta.get('patterns', default_patterns)
        current_patterns_na = current_meta.get('patterns_na', default_patterns_na)
        
        dlg = InterpretationDialog(self, field_label=f"{slot_name} ({slot_id})", 
                                   current_prompt=current_prompt, 
                                   current_patterns=current_patterns,
                                   current_patterns_na=current_patterns_na)
        
        if dlg.exec():
            new_prompt, new_patterns, new_patterns_na = dlg.get_data()
            
            # Atualiza cache local
            if slot_id not in self.metadata_cache: self.metadata_cache[slot_id] = {}
            self.metadata_cache[slot_id]['prompt'] = new_prompt
            self.metadata_cache[slot_id]['patterns'] = new_patterns
            self.metadata_cache[slot_id]['patterns_na'] = new_patterns_na
            
            # Avisa quem coordena (DetailCard) para salvar no JSON do item
            self.metadata_changed.emit(slot_id, "interpretation", {
                'prompt': new_prompt,
                'patterns': new_patterns,
                'patterns_na': new_patterns_na
            })

    def _save_slot_definition(self, slot, name, prompt, help_text):
        # Simplificado para o modo embedded
        pass
