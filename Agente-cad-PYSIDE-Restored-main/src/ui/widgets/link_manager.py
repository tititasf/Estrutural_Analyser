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
    pick_requested = Signal(object) # slot_id|role ou dict de sub-vinculo
    research_requested = Signal(str) # slot_id
    element_removed = Signal(dict)
    training_requested = Signal(dict) # {slot, link, comment, status}
    config_changed = Signal(str, list) # field_key, updated_slots_config
    metadata_changed = Signal(str, str, dict) # slot_id, type="interpretation", data={prompt, patterns}
    link_data_changed = Signal()
    
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
             {'id': 'acrescimo_borda', 'name': 'Acrescimo Borda (+10cm)', 'type': 'poly', 'prompt': 'Desenhe acréscimo de 10cm no borde. [Enter] para finalizar.', 'help': 'Extensão de 10cm no borde da obra.', 'patterns': 'Linha ou Polilinha\nExtensão de exatos 10cm na direção externa.'}
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
             {'id': 'label', 'name': 'Vinculo Texto (Nivel)', 'type': 'text', 'prompt': 'Busque o texto de nivel proprio da laje (Ex: +2.80).', 'help': 'Cota de nivel textual da propria laje. Nao use geometria de corte aqui.', 'patterns': 'REGEX: [+-]?\\d+\\.\\d+|[+-]?\\d+\nExemplos: +2.80, 280, N+2.80\nPrioridade: texto proprio da laje.'}
        ],
        '_laje_cut_view': [
             {'id': 'cut_view_geom', 'name': 'Visao de Corte (Geometria)', 'type': 'poly', 'prompt': 'Desenhe a geometria da visao de corte da viga que toca/contorna a laje. [Enter] para finalizar.', 'help': 'Referencia geometrica de corte/desnivel usada antes do nivel textual para inferir contexto.'}
        ],
        '_laje_neighbor_levels': [
             {'id': 'neighbor_north', 'name': '↑ Vizinha Norte', 'type': 'text', 'prompt': 'Vincule nomes, alturas ou niveis da laje vizinha ao norte.', 'help': 'Textos de consciencia contextual da laje vizinha ao norte.'},
             {'id': 'neighbor_east', 'name': '→ Vizinha Leste', 'type': 'text', 'prompt': 'Vincule nomes, alturas ou niveis da laje vizinha ao leste.', 'help': 'Textos de consciencia contextual da laje vizinha ao leste.'},
             {'id': 'neighbor_west', 'name': '← Vizinha Oeste', 'type': 'text', 'prompt': 'Vincule nomes, alturas ou niveis da laje vizinha ao oeste.', 'help': 'Textos de consciencia contextual da laje vizinha ao oeste.'},
             {'id': 'neighbor_south', 'name': '↓ Vizinha Sul', 'type': 'text', 'prompt': 'Vincule nomes, alturas ou niveis da laje vizinha ao sul.', 'help': 'Textos de consciencia contextual da laje vizinha ao sul.'}
        ],
        '_laje_support_pillars': [
             {'id': 'pillar_geom', 'name': 'Geometria dos Pilares de Apoio', 'type': 'poly', 'prompt': 'Desenhe a geometria dos pilares que apoiam/tocam a laje. [Enter] para finalizar.', 'help': 'Pilares retangulares, circulares, L, U ou T. Separado de visao de corte.'},
             {'id': 'pillar_label', 'name': 'Texto/Nome do Pilar', 'type': 'text', 'prompt': 'Busque o texto do pilar de apoio (ex: P21).', 'help': 'Identificador textual do pilar de apoio da laje.'}
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

    def __init__(self, field_id, current_links, na_slots=None, validated_slots=None,
                 confidence_map=None, parent=None):
        super().__init__(parent)
        self.field_id = field_id
        self.links = current_links if isinstance(current_links, dict) else {}
        self.na_slots = set(na_slots) if na_slots else set()
        self.validated_slots = set(validated_slots) if validated_slots else set()
        self.confidence_map = confidence_map or {}
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
        if 'laje_visao_corte' in field_id:
             return self.SLOT_CONFIG['_laje_cut_view']
        if 'laje_vizinhas_niveis' in field_id:
             return self.SLOT_CONFIG['_laje_neighbor_levels']
        if 'laje_pilares_apoio' in field_id:
             return self.SLOT_CONFIG['_laje_support_pillars']
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
        
        self.setStyleSheet(f"""
            LinkManager {{
                background: {Colors.BG_DEEP};
                border: none;
            }}
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-family: 'Segoe UI', sans-serif;
                font-size: 10px;
            }}
            .SlotFrame {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 3px;
                padding: 3px 5px;
                margin: 1px 0px;
            }}
            .SlotFrame:hover {{
                border-color: {Colors.BORDER_DEFAULT};
            }}
            .SlotFrameValidated {{
                background: rgba(30, 200, 90, 20);
                border: 1px solid rgba(0, 200, 100, 60);
                border-radius: 3px;
                padding: 3px 5px;
                margin: 1px 0px;
            }}
            .SlotTitle {{
                font-size: 10px;
                font-weight: 600;
                color: {Colors.TEXT_MUTED};
                background: transparent;
                border: none;
                padding: 0px;
            }}
            .LinkItem {{
                background: {Colors.BG_DEEP};
                border-left: 2px solid {Colors.BORDER_INPUT};
                border-radius: 2px;
                padding: 2px 4px;
                margin: 1px 0px;
            }}
            .LinkItemValidated {{
                background: rgba(40, 167, 69, 25);
                border-left: 2px solid {Colors.ACCENT_SUCCESS};
                border-radius: 2px;
                padding: 2px 4px;
                margin: 1px 0px;
            }}
            .LinkItemFailed {{
                background: rgba(220, 53, 69, 25);
                border-left: 2px solid {Colors.ACCENT_DANGER};
                border-radius: 2px;
                padding: 2px 4px;
                margin: 1px 0px;
            }}
            .LinkValue {{
                color: {Colors.TEXT_PRIMARY};
                font-weight: 500;
                font-size: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
            }}
            QPushButton {{
                border-radius: 2px;
                font-weight: 600;
                font-size: 9px;
                padding: 1px 5px;
                border: 1px solid transparent;
            }}
            QPushButton.AddBtn {{
                background: transparent;
                color: {Colors.TEXT_MUTED};
                border: 1px dashed {Colors.BORDER_SUBTLE};
                font-size: 9px;
                padding: 2px;
                text-align: center;
                margin-top: 1px;
            }}
            QPushButton.AddBtn:hover {{
                background: {Colors.BG_CARD};
                color: {Colors.ACCENT_TEAL};
                border-color: {Colors.ACCENT_TEAL};
            }}
            QPushButton.ActionBtn {{
                background: transparent;
                border: 1px solid {Colors.ACCENT_INFO};
                color: {Colors.ACCENT_INFO};
                padding: 1px 4px;
            }}
            QPushButton.ActionBtn:hover {{
                background: {Colors.ACCENT_INFO};
                color: {Colors.BG_DEEP};
                border-color: {Colors.ACCENT_INFO};
            }}
            QPushButton.DelBtn {{
                background: transparent;
                border: 1px solid {Colors.BORDER_SUBTLE};
                color: {Colors.ACCENT_DANGER};
                padding: 1px 4px;
            }}
            QPushButton.DelBtn:hover {{
                background: {Colors.ACCENT_DANGER};
                color: {Colors.TEXT_BRIGHT};
            }}
            QPushButton.TrainBtn {{
                background: transparent;
                border: 1px solid {Colors.BORDER_SUBTLE};
                padding: 1px 4px;
            }}
            QPushButton.TrainSuccess {{
                color: {Colors.ACCENT_SUCCESS};
            }}
            QPushButton.TrainSuccess:hover {{
                background: {Colors.ACCENT_SUCCESS};
                color: {Colors.BG_DEEP};
            }}
            QPushButton.TrainFail {{
                color: {Colors.ACCENT_DANGER};
            }}
            QPushButton.TrainFail:hover {{
                background: {Colors.ACCENT_DANGER};
                color: {Colors.BG_DEEP};
            }}
        """)

        # Container direto (Sem ScrollArea interna)
        self.slots_container = QVBoxLayout()
        self.slots_container.setSpacing(3)
        self.slots_container.setContentsMargins(2, 2, 2, 2)
        
        layout.addLayout(self.slots_container)

        self.refresh_list()

    def refresh_list(self, partial=False):
        """Rebuild all slot cards. Set partial=True to skip when unnecessary."""
        if partial:
            return  # Skip full rebuild, local updates handle visuals
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
            sf_layout.setSpacing(2)

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
                btn_help = QPushButton("Ajuda")
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
            btn_val_class = QPushButton("Validar Tudo")
            btn_val_class.setCheckable(True)
            btn_val_class.setChecked(is_class_validated)
            btn_val_class.setCursor(Qt.PointingHandCursor)
            btn_val_class.setToolTip(f"Validar todo o grupo '{slot['name']}' (Clique para desfazer)")
            
            if is_class_validated:
                btn_val_class.setStyleSheet("""
                    QPushButton { background: rgba(27, 58, 36, 1); color: {Colors.ACCENT_SUCCESS_ALT}; border: 1px solid {Colors.ACCENT_SUCCESS_ALT}; border-radius: 4px; }
                    QPushButton:hover { background: {Colors.ACCENT_SUCCESS_ALT}; color: {Colors.TEXT_BRIGHT}; }
                """)
            else:
                btn_val_class.setStyleSheet("""
                    QPushButton { background: transparent; color: {Colors.ACCENT_SUCCESS_ALT}; border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px; }
                    QPushButton:hover { background: {Colors.ACCENT_SUCCESS_ALT}; color: {Colors.BG_DEEP}; border: 1px solid {Colors.ACCENT_SUCCESS_ALT}; }
                """)
                
            btn_val_class.clicked.connect(lambda checked, s_id=slot_id, sf=slot_frame: self._on_slot_class_validated(s_id, checked, sf))
            header_layout.addWidget(btn_val_class)
            
            # 2. N/A Class (🚫) -> Marca classe como N/A e limpa vínculos
            btn_na_class = QPushButton("N/A")
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
            btn_interp = QPushButton("Info")
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
                        
                    lf_layout = QVBoxLayout(link_frame)
                    lf_layout.setContentsMargins(4, 3, 4, 3)
                    lf_layout.setSpacing(3)
                    top_layout = QHBoxLayout()
                    top_layout.setContentsMargins(0, 0, 0, 0)
                    
                    val_text = str(link.get('text', 'Geometria'))
                    if len(val_text) > 30: val_text = val_text[:27] + "..."

                    val_lbl = QLabel(val_text)
                    val_lbl.setProperty("class", "LinkValue")

                    # Badge de confiança individual do vínculo
                    _fb = float(self.confidence_map.get(self.field_id, 0.0))
                    if '_link_conf' in link:
                        _lc = float(link['_link_conf'])
                    elif link.get('validated') or slot_id in self.validated_slots:
                        _lc = 1.0
                    elif _fb > 0:
                        _lc = _fb
                    else:
                        # Presente mas sem confidence explícita → detectado automaticamente
                        _lc = 0.65
                    _lc_pct = int(_lc * 100)
                    if _lc_pct > 80:
                        _lc_col = '#66bb6a'
                    elif _lc_pct > 40:
                        _lc_col = '#ffa726'
                    else:
                        _lc_col = '#ef5350'
                    conf_lbl = QLabel(f'{_lc_pct}%')
                    conf_lbl.setStyleSheet(
                        f'color:{_lc_col}; font-size:9px; font-weight:bold;'
                        f' padding:0 3px; border:1px solid {_lc_col}; border-radius:3px;'
                    )
                    conf_lbl.setToolTip(f'Confiança deste vínculo: {_lc_pct}%')

                    btn_focus = QPushButton("Zoom")
                    btn_focus.setProperty("class", "ActionBtn")
                    btn_focus.clicked.connect(lambda checked=False, l=link, s_id=slot_id: self._emit_focus_link(l, s_id))
                    
                    btn_del = QPushButton("Excluir")
                    btn_del.setProperty("class", "DelBtn")
                    btn_del.clicked.connect(lambda checked=False, s_id=slot_id, l=link: self._remove_link(s_id, l))
                    
                    # New: Training Buttons (Validate and Error)
                    btn_ok = QPushButton("Validar")
                    btn_ok.setProperty("class", "TrainBtn TrainSuccess")
                    btn_ok.setCheckable(True)
                    btn_ok.setChecked(is_valid)
                    btn_ok.setToolTip("Validar/Treinar IA (Clique novamente para desfazer)")
                    if is_valid: 
                        btn_ok.setStyleSheet(f"background: rgba(27, 58, 36, 1); color: {Colors.ACCENT_SUCCESS}; border: 1px solid {Colors.ACCENT_SUCCESS};")
                        
                    btn_ok.clicked.connect(lambda checked, s=slot_id, l=link: self._handle_training_click(s, l, 'valid'))

                    btn_err = QPushButton("Incorreto")
                    btn_err.setProperty("class", "TrainBtn TrainFail")
                    btn_err.setCheckable(True)
                    btn_err.setChecked(is_failed)
                    btn_err.setToolTip("Indicar Erro de IA (Clique novamente para desfazer)")
                    if is_failed:
                        btn_err.setStyleSheet(f"background: rgba(58, 27, 27, 1); color: {Colors.ACCENT_DANGER}; border: 1px solid {Colors.ACCENT_DANGER};")
                        
                    btn_err.clicked.connect(lambda checked, s=slot_id, l=link: self._handle_training_click(s, l, 'fail'))

                    top_layout.addWidget(val_lbl, 1)
                    top_layout.addWidget(conf_lbl)

                    # Horizontal Action Stack for "Text Buttons"
                    actions_h = QHBoxLayout()
                    actions_h.setSpacing(2)
                    actions_h.setContentsMargins(0,0,0,0)

                    actions_h.addWidget(btn_focus)
                    actions_h.addWidget(btn_ok)
                    actions_h.addWidget(btn_err)
                    actions_h.addWidget(btn_del)
                    
                    top_layout.addLayout(actions_h)
                    lf_layout.addLayout(top_layout)
                    ficha_widget = self._build_link_ficha(link, slot_id)
                    if ficha_widget:
                        lf_layout.addWidget(ficha_widget)
                    
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

    def _emit_focus_link(self, link, slot_id):
        payload = dict(link) if isinstance(link, dict) else {'value': link}
        payload['_field_id'] = self.field_id
        payload['_slot_name'] = slot_id
        self.focus_requested.emit(payload)

    def _direction_arrow(self, value: str) -> str:
        text = (value or '').strip().lower()
        if text.startswith('n'): return '↑'
        if text.startswith('s'): return '↓'
        if text.startswith('l') or text.startswith('e'): return '→'
        if text.startswith('o') or text.startswith('w'): return '←'
        return '•'

    def _ficha_fields_for_link(self, slot_id):
        if 'viga_fundo' in self.field_id and slot_id == 'contour':
            return [
                ('apoio_inicial', 'Apoio inicial', 'Viga/Pilar inicial', False, 'text'),
                ('apoio_final', 'Apoio final', 'Viga/Pilar final', False, 'text'),
                ('largura_total_fundo', 'Largura total do fundo', 'cm', False, 'text'),
                ('comprimento_total_fundo', 'Comprimento total do fundo', 'cm', False, 'text'),
                ('abertura_especial', 'Abertura especial', 'tipo/posicao/dimensao', False, 'text'),
                ('chanfro_esq_top', 'Chanfro esquerda topo', 'cm ou N/A', False, 'text'),
                ('chanfro_esq_fun', 'Chanfro esquerda fundo', 'cm ou N/A', False, 'text'),
                ('chanfro_dir_top', 'Chanfro direita topo', 'cm ou N/A', False, 'text'),
                ('chanfro_dir_fun', 'Chanfro direita fundo', 'cm ou N/A', False, 'text'),
                ('abertura_topo_esq', 'Abertura topo/esq.', 'profundidade x boca / ref.', False, 'text'),
                ('abertura_topo_dir', 'Abertura topo/dir.', 'profundidade x boca / ref.', False, 'text'),
                ('abertura_fundo_esq', 'Abertura fundo/esq.', 'profundidade x boca / ref.', False, 'text'),
                ('abertura_fundo_dir', 'Abertura fundo/dir.', 'profundidade x boca / ref.', False, 'text'),
            ]
        if self.field_id == 'laje_visao_corte' and slot_id == 'cut_view_geom':
            return [
                ('direction', 'Direcao', 'Norte/Sul/Leste/Oeste', False, 'text'),
                ('own_position', 'Laje atual posicao', 'topo/fundo/centro', False, 'text'),
                ('own_dist_bottom', 'Laje atual dist. fundo', 'cm', False, 'text'),
                ('own_dist_top', 'Laje atual dist. topo', 'cm', False, 'text'),
                ('own_height', 'Laje atual altura', 'h cm', True, 'text'),
                ('neighbor_position', 'Laje vizinha posicao', 'topo/fundo/centro', False, 'text'),
                ('neighbor_dist_bottom', 'Vizinha dist. fundo', 'cm', False, 'text'),
                ('neighbor_dist_top', 'Vizinha dist. topo', 'cm', False, 'text'),
                ('neighbor_height', 'Vizinha altura', 'h cm', True, 'text'),
                ('beam_name', 'Nome da viga', 'Vxxx', True, 'text'),
                ('beam_bottom_dim', 'Dimensao fundo viga', 'largura/fundo', True, 'text'),
                ('beam_height', 'Altura viga', 'h', True, 'text'),
                ('beam_lajes_side_a', 'Lajes lado A', 'qtd/texto', False, 'text'),
                ('beam_lajes_side_b', 'Lajes lado B', 'qtd/texto', False, 'text'),
                ('side_a_laje_name', 'Lado A nome laje', 'Lxxx', True, 'text'),
                ('side_a_laje_height', 'Lado A altura laje', 'h', True, 'text'),
                ('side_b_laje_name', 'Lado B nome laje', 'Lxxx', True, 'text'),
                ('side_b_laje_height', 'Lado B altura laje', 'h', True, 'text'),
            ]
        if self.field_id == 'laje_pilares_apoio' and slot_id == 'pillar_geom':
            return [
                ('pillar_side', 'Lado do Pilar', 'A/B/C/D', False, 'text'),
                ('touch_face', 'Face que toca a laje', 'baixo/cima/esq/dir', False, 'text'),
                ('pillar_orientation', 'Orientacao pilar', 'horizontal/vertical', False, 'text'),
                ('hatch_description', 'Descricao hatch interno', 'situacao do hatch', False, 'text'),
                ('pillar_name', 'Nome do pilar', 'Pxxx', True, 'text'),
            ]
        return []

    def _build_link_ficha(self, link, slot_id):
        fields = self._ficha_fields_for_link(slot_id)
        if not fields or not isinstance(link, dict):
            return None
        if not link.get('id'):
            link['id'] = str(uuid.uuid4())
        ficha = link.setdefault('ficha', {})
        ficha_links = link.setdefault('ficha_links', {})

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(255, 255, 255, 6);
                border-left: 2px solid {Colors.ACCENT_INFO};
                border-radius: 3px;
                margin-top: 2px;
                padding: 3px;
            }}
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 9px;
                font-weight: bold;
            }}
            QLineEdit {{
                background: {Colors.BG_DEEP};
                color: {Colors.TEXT_BRIGHT};
                border: 1px solid {Colors.BORDER_INPUT};
                border-radius: 3px;
                font-size: 10px;
                padding: 2px 4px;
            }}
            QPushButton {{
                font-size: 9px;
                padding: 1px 4px;
                border-radius: 2px;
                border: 1px solid {Colors.BORDER_SUBTLE};
                background: transparent;
                color: {Colors.ACCENT_INFO};
            }}
            QPushButton:hover {{
                background: {Colors.ACCENT_INFO};
                color: {Colors.BG_DEEP};
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(3)

        title = QLabel('FICHA DO VINCULO')
        title.setStyleSheet(f"color: {Colors.ACCENT_INFO}; font-size: 9px; font-weight: bold;")
        lay.addWidget(title)

        if self.field_id == 'laje_pilares_apoio' and slot_id == 'pillar_geom':
            hint = QLabel('Regra faces: A=baixo/esq, B=cima/dir, C=esq/cima, D=dir/baixo; A/B sao faces maiores.')
            hint.setWordWrap(True)
            hint.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 9px; font-weight: normal;")
            lay.addWidget(hint)
        elif 'viga_fundo' in self.field_id and slot_id == 'contour':
            hint = QLabel('Valores informacionais derivados da geometria do contorno. O vinculo editavel e apenas Segmentos de Area.')
            hint.setWordWrap(True)
            hint.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 9px; font-weight: normal;")
            lay.addWidget(hint)

        for key, label, placeholder, linkable, pick_type in fields:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(3)
            name_lbl = QLabel(label)
            name_lbl.setFixedWidth(110)
            row.addWidget(name_lbl)

            if key == 'direction':
                arrow = QLabel(self._direction_arrow(str(ficha.get(key, ''))))
                arrow.setFixedWidth(16)
                arrow.setStyleSheet(f"color: {Colors.ACCENT_INFO}; font-size: 15px; font-weight: bold;")
                row.addWidget(arrow)
            else:
                arrow = None

            edit = QLineEdit(str(ficha.get(key, '')))
            edit.setPlaceholderText(placeholder)
            edit.editingFinished.connect(lambda e=edit, k=key, a=arrow: self._update_ficha_value(link, k, e.text(), a))
            row.addWidget(edit, 1)

            if linkable:
                count = len(ficha_links.get(key, []) or [])
                btn_pick = QPushButton(f"Vincular {count}" if count else "Vincular 1")
                btn_pick.clicked.connect(lambda checked=False, l=link, s=slot_id, k=key, p=pick_type: self._request_ficha_pick(l, s, k, p))
                row.addWidget(btn_pick)
                btn_clear = QPushButton("Excluir")
                btn_clear.clicked.connect(lambda checked=False, l=link, k=key: self._clear_ficha_links(l, k))
                row.addWidget(btn_clear)

            lay.addLayout(row)
        return frame

    def _update_ficha_value(self, link, key, value, arrow_label=None):
        link.setdefault('ficha', {})[key] = value
        if arrow_label is not None:
            arrow_label.setText(self._direction_arrow(value))
        self.link_data_changed.emit()

    def _request_ficha_pick(self, link, slot_id, ficha_key, pick_type):
        if not link.get('id'):
            link['id'] = str(uuid.uuid4())
        self.pick_requested.emit({
            'slot': slot_id,
            'type': pick_type,
            'link_id': link.get('id'),
            'ficha_key': ficha_key,
            'ficha_target': True,
        })

    def _clear_ficha_links(self, link, ficha_key):
        link.setdefault('ficha_links', {})[ficha_key] = []
        self.link_data_changed.emit()
        self.refresh_list()

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
        Atualiza o estado visual do botao LOCALMENTE antes de emitir o signal.
        """
        sender = self.sender()
        is_already_checked = (target_status == 'valid' and link.get('validated')) or \
                             (target_status == 'fail' and link.get('failed'))
        
        status = 'removed' if is_already_checked else target_status
        comment = f"Undo: {target_status}" if status == 'removed' else (
            'Validado via Drawer' if target_status == 'valid' else 'Erro via Drawer'
        )
        
        # ATUALIZA DADOS localmente
        if status == 'valid':
            link['validated'] = True
            link.pop('failed', None)
        elif status == 'fail':
            link['failed'] = True
            link.pop('validated', None)
        elif status == 'removed':
            link.pop('validated', None)
            link.pop('failed', None)
        
        # ATUALIZA BOTAO visualmente (sem esperar refresh_list)
        if sender:
            # Forca o estado checked visual
            sender.setChecked(status != 'removed')
            if status == 'valid':
                sender.setStyleSheet(f"background: rgba(27, 58, 36, 1); color: #4caf50; border: 1px solid #4caf50; font-weight: bold;")
            elif status == 'fail':
                sender.setStyleSheet(f"background: rgba(58, 27, 27, 1); color: #f44336; border: 1px solid #f44336; font-weight: bold;")
            else:
                sender.setStyleSheet(f"background: transparent; color: #888; border: 1px solid #444; font-weight: bold;")
        
        # ATUALIZA LINK FRAME (cor de fundo)
        parent_frame = sender.parent().parent() if sender and sender.parent() else None
        if parent_frame:
            if status == 'valid':
                parent_frame.setProperty("class", "LinkItemValidated")
            elif status == 'fail':
                parent_frame.setProperty("class", "LinkItemFailed")
            else:
                parent_frame.setProperty("class", "LinkItem")
            parent_frame.style().unpolish(parent_frame)
            parent_frame.style().polish(parent_frame)
        
        self.training_requested.emit({
            'slot': slot_id,
            'link': link,
            'comment': comment,
            'status': status,
            'light_sync': True,
            'ui_refresh': False
        })
        self.link_data_changed.emit()

    def _on_slot_class_validated(self, slot_id, checked, slot_frame):
        """Validate all links in a slot class with local visual update, no rebuild"""
        # Update all links in this slot
        slot_links = self.links.get(slot_id, [])
        for link in slot_links:
            if checked:
                link['validated'] = True
                link['failed'] = False
            else:
                link['validated'] = False
        
        # Update slot frame appearance locally
        if slot_frame:
            if checked:
                slot_frame.setProperty("class", "SlotFrameValidated")
                self.validated_slots.add(slot_id)
            else:
                slot_frame.setProperty("class", "SlotFrame")
                self.validated_slots.discard(slot_id)
            slot_frame.style().unpolish(slot_frame)
            slot_frame.style().polish(slot_frame)
        
        # Update link frames inside
        if slot_frame:
            for child in slot_frame.findChildren(type(slot_frame)):
                cls = child.property('class') or ''
                if 'LinkItem' in cls:
                    child.setProperty("class", "LinkItemValidated" if checked else "LinkItem")
                    child.style().unpolish(child)
                    child.style().polish(child)
        
        self.slot_validated.emit(slot_id, checked)

    def _sync_slot_validation_ui(self, slot_id, is_valid, refresh=True):
        """Updates the slot visual state when changed externally (e.g., undo link)"""
        if is_valid:
            self.validated_slots.add(slot_id)
        else:
            self.validated_slots.discard(slot_id)
        if refresh:
            self.refresh_list()

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
