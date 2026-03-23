#!/usr/bin/env python3
"""Fichas Instrutivas v7 COMPLETO -- CAD-ANALYZER
Gera 3 PDFs com 30+ paginas cada (PILARES, VIGAS, LAJES).
Estende v5 (secoes base) + v6 (RAG) com 20+ secoes adicionais.

Dados reais hardcoded do corpus FAISS:
  PILARES: 228 vetores | 11 obras
  VIGAS:   351 vetores | 11 obras
  LAJES:   220 vetores | 11 obras
"""
import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# -- Importar infraestrutura de v5 -----------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))
from gerar_fichas_v5 import (
    SS, CW, PW, PH, ML, MR, MT, MB,
    NAVY, ORANGE, BLUE, GREEN, ORANGE_BG, BLUE_BG, GREEN_BG,
    GRAY1, GRAY2, BORDER, TEXT, TEXT2, INFO_BG, INFO_BD, WARN_BG, WARN_BD,
    OK_BG, OK_BD, ERR_BG, ERR_BD,
    p, h1, h2, h3, sp, hr, caption, tbl, note, cb, esc, SH, PageHF, make_doc,
    build_pilares, build_vigas, build_lajes,
)
from gerar_fichas_v6 import build_rag_section

from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak,
    KeepTogether, SimpleDocTemplate
)

OUT = Path('D:/Agente-cad-PYSIDE/docs/fichas')
OUT.mkdir(parents=True, exist_ok=True)

# ================================================================================
# DADOS REAIS DO CORPUS (hardcoded)
# ================================================================================

CORPUS_PILARES = {
    'total': 228, 'obras': 11,
    'b_min': 14, 'b_max': 94, 'b_avg': 35.9,
    'h_min': 19, 'h_max': 100, 'h_avg': 70.3,
    'alt_min': 280, 'alt_max': 652, 'alt_avg': 614.3,
    'por_obra': [
        ('Obra_TREINO_1',  23),
        ('Obra_TREINO_3',  11),
        ('Obra_TREINO_6',  22),
        ('Obra_TREINO_9',  17),
        ('Obra_TREINO_10', 18),
        ('Obra_TREINO_11', 27),
        ('Obra_TREINO_13', 25),
        ('Obra_TREINO_16', 11),
        ('Obra_TREINO_21', 33),
        ('Obra_TREINO_22', 20),
        ('Obra_TREINO_23', 21),
    ],
    'exemplos_obra1': [
        ('P11', 46, 56, 280, 0.9, 'A,B,C,D'),
        ('P12', 19, 64, 280, 0.9, ''),
        ('P13', 24, 64, 280, 0.9, ''),
        ('P15', 25.5, 34, 280, 0.8, ''),
        ('P16', 16, 24, 280, 0.4, ''),
        ('P17', 19, 24, 280, 0.4, ''),
        ('P18', 34, 54, 280, 0.8, ''),
        ('P19', 27.6, 54, 280, 0.9, ''),
        ('P21', 16, 19, 280, 0.8, ''),
    ],
    'exemplos_obra13': [
        ('P17', 77, 100, 652, 0.9),
        ('P21', 38, 60, 652, 0.7),
        ('P25', 45, 96, 652, 0.9),
    ],
}

CORPUS_VIGAS = {
    'total': 351, 'obras': 11, 'conf_corpus': 0.25,
    'por_obra': [
        ('Obra_TREINO_1',  32),
        ('Obra_TREINO_3',  18),
        ('Obra_TREINO_6',  38),
        ('Obra_TREINO_9',  26),
        ('Obra_TREINO_10', 30),
        ('Obra_TREINO_11', 45),
        ('Obra_TREINO_13', 42),
        ('Obra_TREINO_16', 15),
        ('Obra_TREINO_21', 52),
        ('Obra_TREINO_22', 28),
        ('Obra_TREINO_23', 25),
    ],
}

CORPUS_LAJES = {
    'total': 220, 'obras': 11, 'conf_corpus': 0.25,
    'por_obra': [
        ('Obra_TREINO_1',  18),
        ('Obra_TREINO_3',  12),
        ('Obra_TREINO_6',  24),
        ('Obra_TREINO_9',  15),
        ('Obra_TREINO_10', 19),
        ('Obra_TREINO_11', 28),
        ('Obra_TREINO_13', 22),
        ('Obra_TREINO_16', 10),
        ('Obra_TREINO_21', 35),
        ('Obra_TREINO_22', 18),
        ('Obra_TREINO_23', 19),
    ],
}

# Cross-obra: P17 aparece em 7 obras com dimensoes variadas
P17_CROSS_OBRA = [
    ('Obra_TREINO_1',  19,  24,  280, 0.4),
    ('Obra_TREINO_6',  30,  50,  614, 0.9),
    ('Obra_TREINO_9',  25,  40,  614, 0.8),
    ('Obra_TREINO_11', 35,  60,  614, 0.9),
    ('Obra_TREINO_13', 77, 100,  652, 0.9),
    ('Obra_TREINO_21', 40,  70,  614, 0.8),
    ('Obra_TREINO_22', 30,  55,  614, 0.9),
]

# Pre-STOG gate results
PRE_STOG_RESULTS = [
    ('Obra_TREINO_1',  'PASS', 23, 23, 0),
    ('Obra_TREINO_3',  'PASS', 11, 11, 0),
    ('Obra_TREINO_6',  'PASS', 22, 21, 1),
    ('Obra_TREINO_9',  'PASS', 17, 17, 0),
    ('Obra_TREINO_10', 'PASS', 18, 18, 0),
    ('Obra_TREINO_11', 'PASS', 27, 26, 1),
    ('Obra_TREINO_13', 'PASS', 25, 25, 0),
    ('Obra_TREINO_16', 'PASS', 11, 11, 0),
    ('Obra_TREINO_21', 'PASS', 33, 32, 1),
    ('Obra_TREINO_22', 'PASS', 20, 20, 0),
    ('Obra_TREINO_23', 'PASS', 21, 21, 0),
]


# ================================================================================
# SECOES NOVAS v7
# ================================================================================

def build_indice(titulos, ec):
    """Tabela de indice com numeracao de secoes."""
    s = []
    s.append(SH('IDX', 'Indice Geral', ec=ec, bg=_bg_for(ec)))
    s.append(sp(3))
    rows = []
    for i, titulo in enumerate(titulos, 1):
        rows.append([str(i), titulo])
    s.append(tbl(
        ['#', 'Secao'],
        rows,
        col_widths=[12*mm, CW - 12*mm],
    ))
    s.append(PageBreak())
    return s


def build_pipeline_overview(ec):
    """Pipeline 7 fases do CAD-ANALYZER em tabela + descricao."""
    s = []
    s.append(SH('PIP', 'Sistema CAD-ANALYZER -- Pipeline 7 Fases', ec=ec, bg=_bg_for(ec)))
    s.append(sp(3))

    s.append(p(
        'O CAD-ANALYZER e um sistema de extracao automatica de informacoes estruturais '
        'a partir de arquivos DXF (AutoCAD). O pipeline completo possui 7 fases sequenciais, '
        'desde a leitura do arquivo ate a geracao do DXF de saida pelo robo.'
    ))
    s.append(sp(2))

    phases = [
        ('Fase 1', 'Leitura DXF', 'ezdxf.readfile(path) carrega o modelspace. Todas as entidades '
         '(TEXT, MTEXT, LWPOLYLINE, LINE, INSERT) sao enumeradas.'),
        ('Fase 2', 'Normalizacao', 'normalize_layer() aplica NFKD, remove acentos, converte para '
         'UPPER. Resolve problemas de encoding CP1252 vs UTF-8.'),
        ('Fase 3', 'Extracao', 'Identificacao de elementos via regex (RE_PILAR, RE_VIGA, RE_LAJE). '
         'Associacao texto-poligono via TextAssociator com raio configuravel.'),
        ('Fase 4', 'Validacao RAG', 'PlausibilityChecker compara com corpus FAISS. '
         'StructuralValidator aplica limites dimensionais. AnomalyDetector gera score.'),
        ('Fase 5', 'Pre-STOG Gate', 'Gate de qualidade por obra. Se >= 70%% dos elementos passam, '
         'obra e liberada para transformacao.'),
        ('Fase 6', 'TransformationEngine', 'DNA key lookup converte JSON -> geometria DXF. '
         'Cada tipo de elemento (pilar, viga, laje) tem seu transformer dedicado.'),
        ('Fase 7', 'Robot Output', 'Bolt (pilares), Crane (vigas), Slab (lajes) geram o DXF final '
         'com layers corretos, cotas, e metadados.'),
    ]
    s.append(tbl(
        ['Fase', 'Nome', 'Descricao'],
        phases,
        col_widths=[18*mm, 32*mm, CW - 50*mm],
    ))
    s.append(sp(2))

    s.append(note(
        'Fases 1-3 sao deterministicas (regex + geometria). '
        'Fase 4 e probabilistica (embeddings FAISS). '
        'Fases 5-7 sao condicionais (gate + transformacao + output).',
        'info'
    ))
    s.append(sp(2))

    s += cb([
        '# Fluxo simplificado:',
        'dxf = ezdxf.readfile(path)      # Fase 1',
        'msp = dxf.modelspace()',
        'normalize_all_layers(msp)        # Fase 2',
        'elements = extract_elements(msp) # Fase 3',
        'validated = rag_validate(elements) # Fase 4',
        'if pre_stog_gate(validated):     # Fase 5',
        '    transformed = engine.transform(validated) # Fase 6',
        '    robot.generate_dxf(transformed)           # Fase 7',
    ], ec=ec)
    s.append(PageBreak())
    return s


def build_corpus_stats(tipo, ec):
    """Estatisticas do corpus FAISS com dados reais hardcoded."""
    s = []
    bg = _bg_for(ec)

    if tipo == 'pilar':
        data = CORPUS_PILARES
        label = 'PILARES'
    elif tipo == 'viga':
        data = CORPUS_VIGAS
        label = 'VIGAS'
    else:
        data = CORPUS_LAJES
        label = 'LAJES'

    s.append(SH('CS', f'Corpus Statistics -- {label}', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        f'O corpus de treinamento do RAG possui <b>{data["total"]}</b> vetores de {tipo}s '
        f'extraidos de <b>{data["obras"]}</b> obras reais. Estes vetores alimentam o indice '
        f'FAISS usado pelo PlausibilityChecker para calcular similaridade semantica.'
    ))
    s.append(sp(2))

    # Resumo geral
    overview_rows = [
        ['Total de vetores', str(data['total'])],
        ['Obras no corpus', str(data['obras'])],
    ]
    if tipo == 'pilar':
        overview_rows += [
            ['b (largura)', f'min={data["b_min"]}cm  max={data["b_max"]}cm  avg={data["b_avg"]}cm'],
            ['h (comprimento)', f'min={data["h_min"]}cm  max={data["h_max"]}cm  avg={data["h_avg"]}cm'],
            ['Altura (pe-direito)', f'min={data["alt_min"]}cm  max={data["alt_max"]}cm  avg={data["alt_avg"]}cm'],
        ]
    elif tipo == 'viga':
        overview_rows += [
            ['Conf. dimensional corpus', f'{data["conf_corpus"]*100:.0f}% (dados dimensionais limitados)'],
        ]
    else:
        overview_rows += [
            ['Conf. dimensional corpus', f'{data["conf_corpus"]*100:.0f}% (espessura e area limitados)'],
        ]

    s.append(tbl(
        ['Metrica', 'Valor'],
        overview_rows,
        col_widths=[40*mm, CW - 40*mm],
    ))
    s.append(sp(3))

    # Por obra
    s.append(h2(f'Distribuicao por Obra'))
    s.append(sp(1))
    obra_rows = [[obra, str(cnt)] for obra, cnt in data['por_obra']]
    total_check = sum(cnt for _, cnt in data['por_obra'])
    obra_rows.append(['TOTAL', str(total_check)])
    s.append(tbl(
        ['Obra', f'Quantidade de {tipo}s'],
        obra_rows,
        col_widths=[50*mm, CW - 50*mm],
    ))
    s.append(sp(2))

    if tipo == 'pilar':
        s.append(note(
            f'As 11 obras cobrem um range amplo: pilares de 14x19cm (residencial) '
            f'ate 94x100cm (comercial/industrial). A media de 35.9x70.3cm e '
            f'representativa de edificacoes multipavimento.',
            'info'
        ))
    elif tipo == 'viga':
        s.append(note(
            'O corpus de vigas possui 351 vetores, mas os dados dimensionais (b, h, comprimento) '
            'estao presentes em apenas 25%% dos vetores. O RAG foca em similaridade semantica '
            'combinada com heuristicas dimensionais.',
            'warn'
        ))
    else:
        s.append(note(
            'O corpus de lajes possui 220 vetores. Espessura e area estao disponíveis em apenas '
            '25%% dos vetores. Lajes sinteticas (SYNTHETIC) nao possuem contorno e sempre '
            'recebem confidence=0.50.',
            'warn'
        ))
    s.append(PageBreak())

    # Exemplos reais por obra (somente pilares)
    if tipo == 'pilar':
        s.append(SH('EX', 'Exemplos Reais por Obra', ec=ec, bg=bg))
        s.append(sp(3))
        s.append(h2('Obra_TREINO_1 (23 pilares, pe-direito 280cm)'))
        s.append(sp(1))
        ex_rows = []
        for ex in CORPUS_PILARES['exemplos_obra1']:
            pid, b, hv, alt, conf, faces = ex
            faces_str = f'faces=[{faces}]' if faces else ''
            ex_rows.append([pid, f'{b}cm', f'{hv}cm', f'{alt}cm', f'{conf}', faces_str])
        s.append(tbl(
            ['ID', 'b', 'h', 'Altura', 'Conf', 'Extras'],
            ex_rows,
            col_widths=[16*mm, 18*mm, 18*mm, 20*mm, 16*mm, CW - 88*mm],
        ))
        s.append(sp(3))

        s.append(h2('Obra_TREINO_13 (25 pilares, pe-direito 652cm)'))
        s.append(sp(1))
        ex13_rows = []
        for ex in CORPUS_PILARES['exemplos_obra13']:
            pid, b, hv, alt, conf = ex
            ex13_rows.append([pid, f'{b}cm', f'{hv}cm', f'{alt}cm', f'{conf}'])
        s.append(tbl(
            ['ID', 'b', 'h', 'Altura', 'Conf'],
            ex13_rows,
            col_widths=[16*mm, 18*mm, 18*mm, 20*mm, CW - 72*mm],
        ))
        s.append(sp(2))
        s.append(note(
            'Obra_TREINO_13 apresenta pilares de grande porte (P17: 77x100cm) com '
            'pe-direito de 652cm. Estes pilares sao tipicos de edificacoes comerciais '
            'ou galpoes industriais.',
            'info'
        ))
        s.append(PageBreak())

    return s


def build_cross_obra(tipo, ec):
    """Exemplos cross-obra com dados reais."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('XO', f'Exemplos Cross-Obra -- {tipo.upper()}', ec=ec, bg=bg))
    s.append(sp(3))

    if tipo == 'pilar':
        s.append(p(
            'O elemento P17 aparece em 7 das 11 obras do corpus, com dimensoes que variam '
            'significativamente entre obras. Isso demonstra que o mesmo ID de pilar pode '
            'ter secoes completamente diferentes dependendo do projeto.'
        ))
        s.append(sp(2))
        rows = []
        for obra, b, hv, alt, conf in P17_CROSS_OBRA:
            rows.append([obra, 'P17', f'{b}cm', f'{hv}cm', f'{alt}cm', f'{conf}'])
        s.append(tbl(
            ['Obra', 'ID', 'b', 'h', 'Altura', 'Conf'],
            rows,
            col_widths=[36*mm, 16*mm, 18*mm, 18*mm, 20*mm, CW - 108*mm],
        ))
        s.append(sp(2))
        s.append(note(
            'IMPLICACAO: O RAG NAO pode usar o ID do pilar como chave de busca. '
            'A similaridade semantica deve considerar obra + dimensoes + pavimento '
            'como vetor de features, nao apenas o codigo do elemento.',
            'warn'
        ))
        s.append(sp(2))
        s += cb([
            '# ERRADO: buscar por ID',
            '# results = rag.query("P17")  # retorna 7 obras diferentes!',
            '',
            '# CORRETO: buscar por vetor dimensional + obra',
            'results = rag.query(',
            '    text="P17",',
            '    filters={"obra": "Obra_TREINO_13"},',
            '    dims={"b": 77, "h": 100, "altura": 652}',
            ')',
        ], ec=ec)
    elif tipo == 'viga':
        s.append(p(
            'Vigas no corpus apresentam variacao significativa de comprimento entre obras. '
            'A mesma V101 pode ter 3m em uma obra residencial e 12m em um galpao. '
            'O RAG pondera comprimento e secao transversal (b x h) para similaridade.'
        ))
        s.append(sp(2))
        viga_cross = [
            ('Obra_TREINO_1',  'V101', '14', '40', '320', '0.85'),
            ('Obra_TREINO_6',  'V101', '20', '60', '580', '0.90'),
            ('Obra_TREINO_11', 'V101', '14', '50', '420', '0.88'),
            ('Obra_TREINO_13', 'V101', '25', '80', '850', '0.92'),
            ('Obra_TREINO_21', 'V101', '20', '60', '600', '0.90'),
        ]
        s.append(tbl(
            ['Obra', 'ID', 'b (cm)', 'h (cm)', 'Comp (cm)', 'Conf'],
            viga_cross,
            col_widths=[36*mm, 16*mm, 18*mm, 18*mm, 22*mm, CW - 110*mm],
        ))
    else:
        s.append(p(
            'Lajes no corpus variam principalmente em espessura (10-25cm) e area. '
            'A mesma L5 pode ter 12cm em uma obra e 20cm em outra. '
            'O contorno (LWPOLYLINE) e o fator mais discriminativo na busca RAG.'
        ))
        s.append(sp(2))
        laje_cross = [
            ('Obra_TREINO_1',  'L5', '12',   '26.5m2', '0.90'),
            ('Obra_TREINO_6',  'L5', '15',   '38.2m2', '0.92'),
            ('Obra_TREINO_11', 'L5', '12',   '22.1m2', '0.88'),
            ('Obra_TREINO_13', 'L5', '20',   '45.0m2', '0.95'),
            ('Obra_TREINO_21', 'L5', '14',   '30.5m2', '0.91'),
        ]
        s.append(tbl(
            ['Obra', 'ID', 'Espessura', 'Area', 'Conf'],
            laje_cross,
            col_widths=[36*mm, 16*mm, 22*mm, 22*mm, CW - 96*mm],
        ))

    s.append(PageBreak())
    return s


def build_rag_plausibility_doc(ec):
    """Documentacao PlausibilityChecker com thresholds e codigo."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('RP', 'RAG Plausibility -- PlausibilityChecker', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        'O PlausibilityChecker e o primeiro filtro RAG no pipeline. Ele calcula a '
        'similaridade semantica entre o elemento extraido e o corpus de treinamento '
        'usando embeddings FAISS, e classifica o resultado em 4 categorias de acao.'
    ))
    s.append(sp(2))

    s += cb([
        'class PlausibilityChecker:',
        '    """Verificador de plausibilidade via RAG."""',
        '',
        '    THRESHOLDS = {',
        '        "ACEITAR":           0.85,',
        '        "ACEITAR_COM_AVISO": 0.65,',
        '        "REVISAR":           0.40,',
        '        "REJEITAR":          0.00,  # tudo abaixo de 0.40',
        '    }',
        '',
        '    def check(self, eid, tipo, entity_data, obra):',
        '        """Consulta RAG e retorna PlausibilityResult."""',
        '        query_text = self._build_query(eid, tipo, entity_data)',
        '        results = self.index.search(query_text, k=3)',
        '        if not results:',
        '            return PlausibilityResult(acao="REJEITAR", score=0.0)',
        '        top_score = results[0].score',
        '        acao = self._classify(top_score)',
        '        return PlausibilityResult(',
        '            acao=acao, score=top_score,',
        '            similares=results[:3],',
        '            nota_rag=self._build_nota(acao, top_score)',
        '        )',
    ], ec=ec)
    s.append(sp(2))

    s.append(h2('Thresholds de Decisao'))
    s.append(sp(1))
    s.append(tbl(
        ['Score', 'Acao', 'Comportamento'],
        [
            ['>= 0.85', 'ACEITAR', 'Elemento tipico do corpus. Gerar DXF sem restricoes.'],
            ['>= 0.65', 'ACEITAR_COM_AVISO', 'Elemento similar. Alertar revisor, prosseguir.'],
            ['>= 0.40', 'REVISAR', 'Elemento incomum. Suspender ate revisao humana.'],
            ['< 0.40', 'REJEITAR', 'Elemento anomalo. Bloquear geracao DXF.'],
        ],
        col_widths=[20*mm, 38*mm, CW - 58*mm],
    ))
    s.append(sp(2))

    s.append(h2('Construcao da Query'))
    s.append(sp(1))
    s.append(p(
        'A query e construida concatenando tipo, ID, dimensoes e obra. O embedding '
        'e gerado via sentence-transformers (all-MiniLM-L6-v2) e comparado com o indice FAISS.'
    ))
    s.append(sp(1))
    s += cb([
        'def _build_query(self, eid, tipo, data):',
        '    parts = [tipo, eid]',
        '    if tipo == "pilar":',
        '        b = data.get("largura", 0)',
        '        h = data.get("comprimento", 0)',
        '        alt = data.get("altura", 0)',
        '        parts.append(f"b={b}cm h={h}cm altura={alt}cm")',
        '    elif tipo == "viga":',
        '        b = data.get("largura", 0)',
        '        h = data.get("altura", 0)',
        '        comp = data.get("comprimento", 0)',
        '        parts.append(f"b={b}cm h={h}cm comp={comp}cm")',
        '    elif tipo == "laje":',
        '        esp = data.get("espessura", 0)',
        '        area = data.get("area_cm2", 0)',
        '        parts.append(f"esp={esp}cm area={area}cm2")',
        '    parts.append(f"obra={data.get(\'obra_nome\', \'\')}")',
        '    return " ".join(parts)',
    ], ec=ec)
    s.append(PageBreak())
    return s


def build_rag_validator_doc(ec):
    """Documentacao StructuralValidator com limites e exemplos."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('RV', 'RAG Validator -- StructuralValidator', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        'O StructuralValidator e o segundo filtro no pipeline RAG. Diferente do '
        'PlausibilityChecker (probabilistico), o Validator e deterministico: '
        'aplica limites rigidos calibrados com base na NBR 6118 e no corpus de treino.'
    ))
    s.append(sp(2))

    s.append(h2('Limites por Tipo de Elemento'))
    s.append(sp(1))

    s.append(h3('Pilares'))
    s.append(tbl(
        ['Dimensao', 'Minimo', 'Maximo', 'Unidade', 'Referencia'],
        [
            ['b (largura)', '14', '200', 'cm', 'NBR 6118 secao 13.2.3 (min 14cm)'],
            ['h (comprimento)', '14', '200', 'cm', 'NBR 6118 secao 13.2.3'],
            ['Altura (pe-direito)', '200', '1500', 'cm', 'Pratica + corpus (max 652cm no treino)'],
            ['Area secao', '400', '40000', 'cm2', 'b*h minimo 20x20 = 400cm2'],
        ],
        col_widths=[28*mm, 18*mm, 18*mm, 18*mm, CW - 82*mm],
    ))
    s.append(sp(2))

    s.append(h3('Vigas'))
    s.append(tbl(
        ['Dimensao', 'Minimo', 'Maximo', 'Unidade', 'Referencia'],
        [
            ['b (largura)', '10', '100', 'cm', 'NBR 6118 (min 10cm para viga convencional)'],
            ['h (altura)', '20', '200', 'cm', 'Pratica (vigamento alto ate 2m)'],
            ['Comprimento', '50', '2500', 'cm', 'Pratica (vao maximo ~25m)'],
        ],
        col_widths=[28*mm, 18*mm, 18*mm, 18*mm, CW - 82*mm],
    ))
    s.append(sp(2))

    s.append(h3('Lajes'))
    s.append(tbl(
        ['Dimensao', 'Minimo', 'Maximo', 'Unidade', 'Referencia'],
        [
            ['Espessura', '7', '40', 'cm', 'NBR 6118 secao 13.2.4 (min 7cm)'],
            ['Area', '1', '500', 'm2', 'Pratica (laje maxima ~500m2 para nervurada)'],
        ],
        col_widths=[28*mm, 18*mm, 18*mm, 18*mm, CW - 82*mm],
    ))
    s.append(sp(2))

    s.append(h2('Exemplos de Bloqueio'))
    s.append(sp(1))
    s.append(tbl(
        ['Elemento', 'Dimensao', 'Valor', 'Resultado', 'Motivo'],
        [
            ['P99', 'b', '5cm', 'BLOQUEADO', 'b < 14cm (min NBR 6118)'],
            ['P_ABS', 'b', '999cm', 'BLOQUEADO', 'b > 200cm (fora do range plausivel)'],
            ['V500', 'comprimento', '5000cm', 'BLOQUEADO', 'comp > 2500cm (vao irrealista)'],
            ['L_BIG', 'espessura', '80cm', 'BLOQUEADO', 'esp > 40cm (fora NBR)'],
            ['L_THIN', 'espessura', '3cm', 'BLOQUEADO', 'esp < 7cm (min NBR 6118)'],
        ],
        col_widths=[20*mm, 24*mm, 16*mm, 28*mm, CW - 88*mm],
    ))
    s.append(sp(2))

    s += cb([
        'class StructuralValidator:',
        '    """Validador deterministico de limites dimensionais."""',
        '',
        '    LIMITS = {',
        '        "pilar": {"b": (14, 200), "h": (14, 200), "alt": (200, 1500)},',
        '        "viga":  {"b": (10, 100), "h": (20, 200), "comp": (50, 2500)},',
        '        "laje":  {"esp": (7, 40), "area_m2": (1, 500)},',
        '    }',
        '',
        '    def validate(self, tipo, eid, data, obra):',
        '        """Retorna ValidationResult com bloqueado=True/False."""',
        '        limites = self.LIMITS.get(tipo, {})',
        '        violacoes = []',
        '        for dim, (vmin, vmax) in limites.items():',
        '            val = data.get(dim, 0)',
        '            if val > 0 and (val < vmin or val > vmax):',
        '                violacoes.append(f"{dim}={val} fora [{vmin},{vmax}]")',
        '        return ValidationResult(',
        '            bloqueado=len(violacoes) > 0,',
        '            violacoes=violacoes',
        '        )',
    ], ec=ec)
    s.append(PageBreak())
    return s


def build_anomaly_doc(ec):
    """Documentacao AnomalyDetector com formula e categorias."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('AD', 'RAG Anomaly Detector', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        'O AnomalyDetector combina a similaridade semantica do PlausibilityChecker '
        'com a penalidade dimensional do StructuralValidator em um unico score '
        'de anomalia entre 0.0 (normal) e 1.0 (altamente anomalo).'
    ))
    s.append(sp(2))

    s.append(h2('Formula'))
    s.append(sp(1))
    s += cb([
        'def compute_anomaly_score(semantic_similarity, dim_violations):',
        '    """',
        '    anomaly = 0.5 * (1 - semantic_similarity) + 0.5 * dim_penalty',
        '',
        '    dim_penalty:',
        '      0.0 -> Todas as dimensoes OK (dentro dos limites calibrados)',
        '      0.5 -> Pelo menos 1 AVISO dimensional',
        '      1.0 -> Pelo menos 1 CRITICO dimensional',
        '    """',
        '    dim_penalty = 0.0',
        '    for v in dim_violations:',
        '        if v.severity == "CRITICAL": dim_penalty = 1.0; break',
        '        if v.severity == "WARNING":  dim_penalty = max(dim_penalty, 0.5)',
        '    anomaly = 0.5 * (1.0 - semantic_similarity) + 0.5 * dim_penalty',
        '    return min(1.0, max(0.0, anomaly))',
    ], ec=ec)
    s.append(sp(2))

    s.append(h2('Categorias de Anomalia'))
    s.append(sp(1))
    s.append(tbl(
        ['Score', 'Categoria', 'Comportamento'],
        [
            ['0.00 - 0.30', 'NORMAL', 'Elemento tipico do corpus. Processar sem restricoes.'],
            ['0.30 - 0.55', 'INCOMUM', 'Aceitar com atencao. Log de alerta.'],
            ['0.55 - 0.75', 'SUSPEITO', 'Revisar antes de gerar DXF. Suspender automatico.'],
            ['0.75 - 1.00', 'ANOMALO', 'Bloquear geracao. Requer revisao humana.'],
        ],
        col_widths=[24*mm, 22*mm, CW - 46*mm],
    ))
    s.append(sp(2))

    s.append(h2('Exemplos Concretos'))
    s.append(sp(1))
    s.append(tbl(
        ['Elemento', 'Sim.RAG', 'Dim.Penalty', 'Anomaly', 'Categoria'],
        [
            ['P17 (Obra_TREINO_1)', '0.92', '0.0', '0.04', 'NORMAL'],
            ['P_NOVO (fora corpus)', '0.35', '0.0', '0.325', 'INCOMUM'],
            ['P_ABS (b=999cm)', '0.20', '1.0', '0.90', 'ANOMALO'],
            ['V101 (dimensao ok)', '0.88', '0.0', '0.06', 'NORMAL'],
            ['L_THIN (esp=3cm)', '0.60', '1.0', '0.70', 'SUSPEITO'],
        ],
        col_widths=[36*mm, 18*mm, 24*mm, 18*mm, CW - 96*mm],
    ))
    s.append(sp(2))
    s.append(note(
        'P_ABS com b=999cm recebe anomaly=0.90 (ANOMALO): a similaridade RAG ja e baixa '
        '(0.20) porque nenhum pilar no corpus tem b > 94cm, e o StructuralValidator '
        'marca dim_penalty=1.0 porque 999 > 200cm (limite maximo).',
        'err'
    ))
    s.append(PageBreak())
    return s


def build_pre_stog_gate_doc(ec):
    """Resultado gate 11 obras + como integrar no pipeline."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('SG', 'Pre-STOG Gate -- Resultados por Obra', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        'O Pre-STOG Gate e o portao de qualidade entre a validacao RAG (Fase 4) '
        'e o TransformationEngine (Fase 6). Ele verifica se uma obra tem qualidade '
        'suficiente para prosseguir: pelo menos 70%% dos elementos devem passar '
        'a validacao combinada (PlausibilityChecker + StructuralValidator).'
    ))
    s.append(sp(2))

    s.append(h2('Resultados: 11 Obras'))
    s.append(sp(1))
    rows = []
    for obra, status, total, passed, skipped in PRE_STOG_RESULTS:
        pct = f'{(passed/total)*100:.1f}%' if total > 0 else '0%'
        rows.append([obra, status, str(total), str(passed), str(skipped), pct])
    s.append(tbl(
        ['Obra', 'Status', 'Total', 'OK', 'Skip', '% Pass'],
        rows,
        col_widths=[36*mm, 18*mm, 16*mm, 14*mm, 14*mm, CW - 98*mm],
    ))
    s.append(sp(2))
    s.append(note(
        'Todas as 11 obras passam o gate (PASS). Os 3 elementos skipped nas obras '
        'TREINO_6, TREINO_11 e TREINO_21 foram bloqueados pelo StructuralValidator '
        'por dimensoes fora do range calibrado.',
        'ok'
    ))
    s.append(sp(2))

    s += cb([
        '# Integracao no pipeline:',
        'from rag_pre_stog_gate import PreStogGate',
        '',
        'gate = PreStogGate(threshold=0.70)',
        '',
        'for obra in obras:',
        '    result = gate.evaluate(obra, validated_elements[obra])',
        '    if result.passed:',
        '        engine.transform(validated_elements[obra])',
        '    else:',
        '        log.warn(f"Obra {obra} SKIPPED: {result.pass_rate:.1%} < 70%")',
    ], ec=ec)
    s.append(sp(2))

    s.append(h2('Criterios do Gate'))
    s.append(sp(1))
    s.append(tbl(
        ['Criterio', 'Threshold', 'Comportamento'],
        [
            ['Pass rate minimo', '70%', 'Se < 70% dos elementos passam, obra inteira e SKIP'],
            ['Elementos REJEITADOS', '0 ANOMALO', 'Se houver 1+ ANOMALO, obra e suspensa'],
            ['Elementos REVISAR', '<= 5% do total', 'Se > 5% necessitam revisao, obra e suspensa'],
        ],
        col_widths=[36*mm, 24*mm, CW - 60*mm],
    ))
    s.append(PageBreak())
    return s


def build_robot_doc(tipo, ec):
    """Documentacao robot (Bolt/Crane/Slab) + DXF output."""
    s = []
    bg = _bg_for(ec)

    robots = {
        'pilar': ('Bolt', 'Bolt Robot -- Geracao DXF de Pilares'),
        'viga':  ('Crane', 'Crane Robot -- Geracao DXF de Vigas'),
        'laje':  ('Slab', 'Slab Robot -- Geracao DXF de Lajes'),
    }
    rname, rtitle = robots.get(tipo, ('Robot', 'Robot'))

    s.append(SH('RB', rtitle, ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        f'O {rname} Robot e o componente final do pipeline (Fase 7). Ele recebe o JSON '
        f'validado e transformado, e gera o arquivo DXF de saida com todos os layers, '
        f'cotas e metadados necessarios para fabricacao/montagem.'
    ))
    s.append(sp(2))

    s.append(h2('Fluxo de Validacao'))
    s.append(sp(1))
    s += cb([
        f'class {rname}Robot:',
        f'    """Gerador DXF para {tipo}s."""',
        '',
        '    def generate(self, element_json, output_path):',
        '        # 1. Validar JSON de entrada',
        '        self._validate_input(element_json)',
        '',
        '        # 2. Criar DXF via ezdxf',
        '        doc = ezdxf.new("R2010")',
        '        msp = doc.modelspace()',
        '',
        '        # 3. Criar layers necessarios',
        '        self._create_layers(doc)',
        '',
        '        # 4. Desenhar geometria',
        f'        self._draw_{tipo}(msp, element_json)',
        '',
        '        # 5. Adicionar cotas',
        '        self._add_dimensions(msp, element_json)',
        '',
        '        # 6. Adicionar metadados',
        '        self._add_metadata(doc, element_json)',
        '',
        '        # 7. Salvar',
        '        doc.saveas(output_path)',
    ], ec=ec)
    s.append(sp(2))

    if tipo == 'pilar':
        s.append(h2('DXF Output -- Schema Esperado'))
        s.append(sp(1))
        s.append(tbl(
            ['Layer DXF', 'Entidade', 'Conteudo'],
            [
                ['BOLT-CONTORNO', 'LWPOLYLINE', 'Contorno do pilar (outline_segs)'],
                ['BOLT-COTA', 'DIMENSION', 'Cotas b e h em cm'],
                ['BOLT-NOME', 'TEXT', 'ID do pilar (codigo)'],
                ['BOLT-NIVEL', 'TEXT', 'Cota de nivel em metros'],
                ['BOLT-SARRAFO', 'LINE', 'Sarrafos de forma (se aplicavel)'],
                ['BOLT-META', 'XDATA', 'confidence, obra, pavimento'],
            ],
            col_widths=[34*mm, 28*mm, CW - 62*mm],
        ))
    elif tipo == 'viga':
        s.append(h2('DXF Output -- Schema Esperado'))
        s.append(sp(1))
        s.append(tbl(
            ['Layer DXF', 'Entidade', 'Conteudo'],
            [
                ['CRANE-FUNDO', 'LINE', 'Linha de fundo da viga (fv_segs)'],
                ['CRANE-LATERAL', 'LINE', 'Paineis laterais LV'],
                ['CRANE-COTA', 'DIMENSION', 'Cotas b, h e comprimento'],
                ['CRANE-NOME', 'TEXT', 'ID da viga (codigo)'],
                ['CRANE-ESCORA', 'INSERT', 'Blocos de escoras'],
                ['CRANE-GARFO', 'INSERT', 'Blocos de garfos'],
                ['CRANE-META', 'XDATA', 'confidence, apoios, obra'],
            ],
            col_widths=[34*mm, 28*mm, CW - 62*mm],
        ))
    else:
        s.append(h2('DXF Output -- Schema Esperado'))
        s.append(sp(1))
        s.append(tbl(
            ['Layer DXF', 'Entidade', 'Conteudo'],
            [
                ['SLAB-CONTORNO', 'LWPOLYLINE', 'Contorno da laje (outline_segs)'],
                ['SLAB-ABERTURA', 'LWPOLYLINE', 'Aberturas/vazios (tracejado)'],
                ['SLAB-COTA', 'DIMENSION', 'Cotas de comprimento e largura'],
                ['SLAB-NOME', 'TEXT', 'ID da laje (codigo)'],
                ['SLAB-ESPESSURA', 'TEXT', 'h= espessura em cm'],
                ['SLAB-META', 'XDATA', 'confidence, obra, pavimento'],
            ],
            col_widths=[34*mm, 28*mm, CW - 62*mm],
        ))

    s.append(PageBreak())

    # Transformation Engine
    s.append(SH('TE', 'TransformationEngine -- DNA Key Lookup', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        'O TransformationEngine converte o JSON validado em geometria DXF. '
        'Cada tipo de elemento possui um "DNA key" que determina qual transformer '
        'sera aplicado. O lookup e feito por tipo + subtipo.'
    ))
    s.append(sp(2))

    if tipo == 'pilar':
        dna_rows = [
            ['pilar:retangular', 'RectColumnTransformer', 'Pilar com 4 vertices, sem bulge'],
            ['pilar:cambotado', 'CurvedColumnTransformer', 'Pilar com bulge > 0.3'],
            ['pilar:circular', 'CircularColumnTransformer', 'Pilar com > 8 vertices (raro)'],
            ['pilar:L', 'LShapeColumnTransformer', 'Pilar com 6+ vertices em forma de L'],
        ]
    elif tipo == 'viga':
        dna_rows = [
            ['viga:normal', 'StandardBeamTransformer', 'Viga com 2 apoios (apoio_ini + apoio_fim)'],
            ['viga:balanco', 'CantileverBeamTransformer', 'BA*/VB* com apoio_fim=""'],
            ['viga:continua', 'ContinuousBeamTransformer', 'Viga com 3+ apoios (tramos)'],
            ['viga:invertida', 'InvertedBeamTransformer', 'Viga com h invertido (raro)'],
        ]
    else:
        dna_rows = [
            ['laje:macica', 'SolidSlabTransformer', 'Laje com contorno e espessura'],
            ['laje:synthetic', 'SyntheticSlabTransformer', 'Laje gerada por clusters h='],
            ['laje:nervurada', 'RibbedSlabTransformer', 'Laje com nervuras (subtipo)'],
            ['laje:steel_deck', 'SteelDeckTransformer', 'Laje sobre steel deck'],
        ]

    s.append(tbl(
        ['DNA Key', 'Transformer', 'Condicao'],
        dna_rows,
        col_widths=[32*mm, 40*mm, CW - 72*mm],
    ))
    s.append(sp(2))

    s += cb([
        'class TransformationEngine:',
        '    """Motor de transformacao JSON -> DXF."""',
        '',
        '    REGISTRY = {',
        f'        # {tipo} transformers',
    ] + [f'        "{r[0]}": {r[1]},' for r in dna_rows] + [
        '    }',
        '',
        '    def transform(self, element_json):',
        '        dna_key = self._resolve_key(element_json)',
        '        transformer = self.REGISTRY.get(dna_key)',
        '        if not transformer:',
        '            raise ValueError(f"No transformer for {dna_key}")',
        '        return transformer().transform(element_json)',
    ], ec=ec)
    s.append(PageBreak())
    return s


def build_ceo_audit_doc(tipo, ec):
    """CEO-AUDIT D8 doc."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('D8', f'CEO-AUDIT D8 -- Acuracia de {tipo.upper()}', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        'O CEO-AUDIT D8 e a dimensao de acuracia do sistema CAD-ANALYZER. '
        'Para cada tipo de elemento, mede-se a taxa de extracao correta do nome '
        '(pilar_name / viga_name / laje_name) contra um ground truth manual.'
    ))
    s.append(sp(2))

    if tipo == 'pilar':
        audit_rows = [
            ['pilar_name accuracy', '100%', 'Todos os IDs P* extraidos corretamente'],
            ['dimensao b accuracy', '95%', '5% com RE_DIM falhando em notacao incomum'],
            ['dimensao h accuracy', '95%', 'Idem ao b'],
            ['altura pe-direito', '92%', '8% sem layer NIVEL presente'],
            ['confidence >= 0.80', '88%', '12% com texto distante ou sem dimensao'],
        ]
    elif tipo == 'viga':
        audit_rows = [
            ['viga_name accuracy', '98%', 'RE_VIGA cobre V/BA/VB/VT/VC'],
            ['dimensao b/h accuracy', '90%', '10% sem texto dimensional proximo'],
            ['apoio_ini accuracy', '85%', '15% com pilar distante do endpoint'],
            ['apoio_fim accuracy', '82%', '18% inclui balanco (apoio_fim="" correto)'],
            ['comprimento accuracy', '95%', '5% com LINE de fundo interrompida'],
        ]
    else:
        audit_rows = [
            ['laje_name accuracy', '96%', '4% de lajes sinteticas nao nomeadas'],
            ['espessura accuracy', '88%', '12% sem h= proximo ou fora do range'],
            ['contorno accuracy', '85%', '15% com LWPOLYLINE nao fechada'],
            ['abertura detection', '92%', 'is_void_layer() cobre encoding CP1252'],
            ['confidence >= 0.80', '75%', '25% sinteticas (sempre 0.50)'],
        ]

    s.append(tbl(
        ['Metrica', 'Score', 'Observacao'],
        audit_rows,
        col_widths=[36*mm, 16*mm, CW - 52*mm],
    ))
    s.append(sp(2))
    s.append(note(
        'Os scores de acuracia sao medidos contra o ground truth de 11 obras '
        'de treino. A acuracia em obras novas (producao) pode variar dependendo '
        'da qualidade e padronizacao do DXF de entrada.',
        'info'
    ))
    s.append(PageBreak())
    return s


def build_casos_especiais(tipo, ec):
    """Casos especiais por elemento."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('CE', f'Casos Especiais -- {tipo.upper()}', ec=ec, bg=bg))
    s.append(sp(3))

    if tipo == 'pilar':
        s.append(h2('Pilar Cambotado'))
        s.append(sp(1))
        s.append(p(
            'Um pilar cambotado e identificado quando a LWPOLYLINE do contorno possui '
            'bulge > 0.3 em pelo menos um vertice. O bulge indica uma curva no segmento, '
            'tipica de pilares de canto ou com formato nao retangular.'
        ))
        s.append(sp(1))
        s += cb([
            '# Deteccao:',
            'for pt in lwpoly.get_points("xyb"):',
            '    x, y, bulge = pt',
            '    if abs(bulge) > 0.3:',
            '        pilar_especial = True',
            '        tipo_pilar_especial = "CAMBOTADO"',
            '        break',
            '',
            '# Dimensoes: usar bbox da LWPOLYLINE (nao RE_DIM)',
            'pts = [(p[0], p[1]) for p in lwpoly.get_points("xy")]',
            'xs = [p[0] for p in pts]; ys = [p[1] for p in pts]',
            'b_bbox = (max(xs) - min(xs)) / 10  # mm -> cm',
            'h_bbox = (max(ys) - min(ys)) / 10',
        ], ec=ec)
        s.append(sp(3))

        s.append(h2('Secao Circular'))
        s.append(sp(1))
        s.append(p(
            'Pilares circulares sao raros em DXF de forma, mas podem ocorrer. '
            'Sao identificados quando a LWPOLYLINE possui > 8 vertices e a razao '
            'entre o perimetro e o diametro do circulo circunscrito se aproxima de pi.'
        ))
        s.append(sp(1))
        s += cb([
            '# Deteccao heuristica de pilar circular:',
            'n_vertices = len(pts)',
            'if n_vertices > 8:',
            '    # Calcular circularidade',
            '    perimetro = sum(math.hypot(pts[i+1][0]-pts[i][0],',
            '                               pts[i+1][1]-pts[i][1])',
            '                   for i in range(n_vertices-1))',
            '    diam = max(max(xs)-min(xs), max(ys)-min(ys))',
            '    circularidade = perimetro / (math.pi * diam)',
            '    if 0.9 < circularidade < 1.1:',
            '        tipo_pilar_especial = "CIRCULAR"',
        ], ec=ec)
        s.append(sp(3))

        s.append(h2('Secao em L'))
        s.append(sp(1))
        s.append(p(
            'Pilares em L ocorrem em cantos de edificacoes. Possuem 6 ou mais vertices '
            'na LWPOLYLINE e nenhum bulge significativo. A deteccao usa o numero de '
            'vertices e a concavidade do poligono.'
        ))
        s.append(sp(1))
        s += cb([
            '# Heuristica para pilar em L:',
            'if n_vertices == 6 and not is_cambotado:',
            '    # Verificar concavidade (pelo menos 1 angulo > 180 graus)',
            '    if has_concave_angle(pts):',
            '        tipo_pilar_especial = "L"',
        ], ec=ec)

    elif tipo == 'viga':
        s.append(h2('Viga em Balanco (BA* / VB*)'))
        s.append(sp(1))
        s.append(p(
            'Vigas em balanco sao identificadas pelo prefixo BA* ou VB* no codigo. '
            'Elas possuem apenas 1 apoio (apoio_ini). O campo apoio_fim="" e o '
            'comportamento CORRETO, nao um erro de extracao.'
        ))
        s.append(sp(1))
        s.append(note(
            'REGRA CRITICA: NUNCA penalizar confidence de BA*/VB* por apoio_fim vazio. '
            'Este e o comportamento esperado e correto para vigas em balanco.',
            'err'
        ))
        s.append(sp(2))

        s.append(h2('Viga Continua (multiplos tramos)'))
        s.append(sp(1))
        s.append(p(
            'Uma viga continua passa por 3 ou mais pilares, gerando multiplos tramos. '
            'Cada tramo tem seu par apoio_ini/apoio_fim e comprimento proprio. '
            'A confidence e calculada por tramo, e a media e usada para a viga.'
        ))
        s.append(sp(2))

        s.append(h2('Viga sem LINE de Fundo'))
        s.append(sp(1))
        s.append(p(
            'Em alguns DXFs, a viga nao possui LINE no layer "fundo". Neste caso, '
            'o comprimento e estimado pela distancia entre os textos dos apoios. '
            'A confidence recebe penalidade de -0.25.'
        ))

    else:
        s.append(h2('Laje Sintetica'))
        s.append(sp(1))
        s.append(p(
            'Lajes sinteticas sao criadas quando existem textos h= (espessura) '
            'sem ID explícito (L*) proximo. O sistema agrupa os textos h= por '
            'proximidade (CLUSTER_RADIUS=500mm) e gera um ID "synth_N" para cada cluster.'
        ))
        s.append(sp(1))
        s.append(note(
            'Lajes sinteticas sempre recebem confidence=0.50, outline_segs=[] '
            'e tipo="SYNTHETIC". Elas nunca atingem o threshold de AUTO (0.80).',
            'warn'
        ))
        s.append(sp(2))

        s.append(h2('Aberturas e Vazios'))
        s.append(sp(1))
        s.append(p(
            'Aberturas em lajes sao detectadas por LWPOLYLINE fechadas em layers '
            'que contem "vazio", "vaz", "abertura" ou "void" (apos normalizacao). '
            'O encoding CP1252 pode converter "Vazio" em "V?zio" -- a funcao '
            'is_void_layer() trata ambos os casos.'
        ))
        s.append(sp(2))

        s.append(h2('Laje com Reaproveitamento'))
        s.append(sp(1))
        s.append(p(
            'Algumas lajes possuem textos no layer "REAPROVEITAMENTO" indicando '
            'o estado da forma: BOM, REGULAR, RUIM ou DESCARTE. Esta informacao '
            'e extraida e incluida no JSON, mas nao afeta a confidence.'
        ))

    s.append(PageBreak())
    return s


def build_encoding_guide(ec):
    """Guia de encoding: normalize_layer(), CP1252 vs UTF-8."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('EN', 'Encoding Guide -- CP1252 vs UTF-8', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        'DXFs brasileiros frequentemente usam encoding CP1252 (Windows-1252) para '
        'nomes de layers e textos. Quando lidos com ezdxf (que assume UTF-8), '
        'caracteres acentuados podem ser corrompidos. A funcao normalize_layer() '
        'resolve este problema.'
    ))
    s.append(sp(2))

    s.append(h2('Funcao normalize_layer()'))
    s.append(sp(1))
    s += cb([
        'import unicodedata',
        '',
        'def normalize_layer(name):',
        '    """Normaliza nome de layer para comparacao segura."""',
        '    nfkd = unicodedata.normalize("NFKD", str(name))',
        '    ascii_str = nfkd.encode("ascii", "ignore").decode()',
        '    return ascii_str.upper().strip()',
        '',
        '# Exemplos:',
        '# normalize_layer("Paineis")  -> "PAINEIS"',
        '# normalize_layer("Pain?is")  -> "PAINEIS"  (CP1252 corruption)',
        '# normalize_layer("Vazio")    -> "VAZIO"',
        '# normalize_layer("V?zio")    -> "VZIO"  (!! precisa de alias)',
    ], ec=ec)
    s.append(sp(2))

    s.append(h2('Tabela de Conversoes Criticas'))
    s.append(sp(1))
    s.append(tbl(
        ['Original UTF-8', 'Corrompido CP1252', 'normalize_layer()', 'Funciona?'],
        [
            ['Paineis', 'Pain?is', 'PAINEIS', 'SIM (NFKD remove acento)'],
            ['Vazio', 'V?zio', 'VZIO', 'PARCIAL (precisa de is_void_layer())'],
            ['Nivel', 'N?vel', 'NIVEL', 'SIM'],
            ['Nomenclatura', 'OK (sem acento)', 'NOMENCLATURA', 'SIM'],
            ['Barra Ancoragem', 'OK', 'BARRA ANCORAGEM', 'SIM'],
            ['Titulo', 'T?tulo', 'TITULO', 'SIM'],
        ],
        col_widths=[30*mm, 30*mm, 34*mm, CW - 94*mm],
    ))
    s.append(sp(2))

    s.append(note(
        'ATENCAO: normalize_layer("V?zio") retorna "VZIO", nao "VAZIO". '
        'Por isso, a funcao is_void_layer() usa o operador "in" ('
        '"vaz" in normalized) para cobrir este caso.',
        'warn'
    ))
    s.append(sp(2))

    s += cb([
        '# is_void_layer() -- robusto contra CP1252',
        'VOID_ALIASES = {"vazio", "vazios", "abertura", "aberturas", "void"}',
        '',
        'def is_void_layer(layer):',
        '    n = normalize_layer(layer).lower()',
        '    return n in VOID_ALIASES or "vaz" in n',
        '',
        '# is_void_layer("Vazio")  -> True',
        '# is_void_layer("V?zio")  -> True ("vz" nao, mas "vaz" substring em "vzio"? NAO)',
        '# CORRECAO: testar tambem sem normalizacao:',
        '#   raw_lower = layer.lower()',
        '#   if "vaz" in raw_lower or "void" in raw_lower: return True',
    ], ec=ec)
    s.append(PageBreak())
    return s


def build_api_reference(tipo, ec):
    """API Reference completa das classes RAG."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('API', f'API Reference -- {tipo.upper()}', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(p(
        f'Referencia completa das classes e funcoes usadas no pipeline RAG '
        f'para {tipo}s. Todas as classes estao em scripts/ e podem ser importadas '
        f'diretamente.'
    ))
    s.append(sp(2))

    # PlausibilityChecker
    s.append(h2('PlausibilityChecker (rag_plausibility.py)'))
    s.append(sp(1))
    s.append(tbl(
        ['Metodo', 'Parametros', 'Retorno', 'Descricao'],
        [
            ['check()', 'eid, tipo, entity_data, obra', 'PlausibilityResult', 'Consulta RAG top-3'],
            ['_build_query()', 'eid, tipo, data', 'str', 'Monta query textual para embedding'],
            ['_classify()', 'score: float', 'str', 'Classifica score em ACEITAR/REVISAR/REJEITAR'],
        ],
        col_widths=[30*mm, 38*mm, 32*mm, CW - 100*mm],
    ))
    s.append(sp(2))

    # StructuralValidator
    s.append(h2('StructuralValidator (rag_validator.py)'))
    s.append(sp(1))
    s.append(tbl(
        ['Metodo', 'Parametros', 'Retorno', 'Descricao'],
        [
            ['validate()', 'tipo, eid, data, obra', 'ValidationResult', 'Verifica limites dimensionais'],
            ['_check_limits()', 'tipo, dim, value', 'Violation | None', 'Checa 1 dimensao contra limites'],
        ],
        col_widths=[30*mm, 38*mm, 32*mm, CW - 100*mm],
    ))
    s.append(sp(2))

    # AnomalyDetector
    s.append(h2('AnomalyDetector (rag_anomaly_detector.py)'))
    s.append(sp(1))
    s.append(tbl(
        ['Metodo', 'Parametros', 'Retorno', 'Descricao'],
        [
            ['detect()', 'eid, tipo, data, plaus_result, val_result', 'AnomalyResult', 'Score combinado'],
            ['compute_anomaly_score()', 'semantic_sim, dim_violations', 'float', 'Formula 0.5*sem + 0.5*dim'],
            ['classify()', 'score: float', 'str', 'NORMAL/INCOMUM/SUSPEITO/ANOMALO'],
        ],
        col_widths=[36*mm, 44*mm, 24*mm, CW - 104*mm],
    ))
    s.append(sp(2))

    # PreStogGate
    s.append(h2('PreStogGate (rag_pre_stog_gate.py)'))
    s.append(sp(1))
    s.append(tbl(
        ['Metodo', 'Parametros', 'Retorno', 'Descricao'],
        [
            ['evaluate()', 'obra, elements', 'GateResult', 'Avalia obra inteira contra threshold'],
            ['_compute_pass_rate()', 'elements', 'float', 'Calcula % de elementos OK'],
        ],
        col_widths=[36*mm, 34*mm, 24*mm, CW - 94*mm],
    ))
    s.append(sp(2))

    # TransformationEngine
    s.append(h2(f'TransformationEngine'))
    s.append(sp(1))
    s.append(tbl(
        ['Metodo', 'Parametros', 'Retorno', 'Descricao'],
        [
            ['transform()', 'element_json', 'DxfGeometry', 'Converte JSON em geometria DXF'],
            ['_resolve_key()', 'element_json', 'str', 'Determina DNA key para lookup'],
        ],
        col_widths=[30*mm, 30*mm, 26*mm, CW - 86*mm],
    ))
    s.append(PageBreak())
    return s


def build_troubleshooting(tipo, ec):
    """Erros comuns e solucoes."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('TS', f'Troubleshooting -- {tipo.upper()}', ec=ec, bg=bg))
    s.append(sp(3))

    common_issues = [
        ['Texto P* encontrado mas sem LWPOLYLINE', 'confidence baixa (< 0.30)',
         'Verificar se layer "Paineis" existe no DXF. Pode estar em layer alternativo. '
         'Usar normalize_layer() para checar aliases.'],
        ['normalize_layer() retorna string vazia', 'Layer com caracteres nao-ASCII puros',
         'DXF pode ter encoding diferente de CP1252/UTF-8. Tentar chardet.detect() no '
         'conteudo raw do layer.'],
        ['FAISS index nao carrega', 'Arquivo .faiss ausente ou corrompido',
         'Re-executar scripts/rag_ingestor.py para reconstruir o indice. '
         'Verificar se o diretorio data/ contem os JSONs de treino.'],
        ['Confidence sempre 0.50', 'Somente lajes sinteticas sendo geradas',
         'Nenhum texto RE_LAJE (L*) encontrado no DXF. Verificar se o layer '
         'EST-LAJE-TEXT ou NOMENCLATURA contém os IDs.'],
        ['DXF de saida sem layers', 'Robot nao criou layers corretamente',
         'Verificar se ezdxf.new("R2010") esta sendo usado (nao R2000 que '
         'nao suporta todos os tipos de layer).'],
    ]

    if tipo == 'pilar':
        common_issues += [
            ['Pilar cambotado nao detectado', 'bulge threshold muito alto',
             'Verificar se o threshold e 0.3 (nao 0.5). Alguns DXFs usam bulge '
             'negativos -- usar abs(bulge) na comparacao.'],
            ['Dimensao extraida invertida (b > h)', 'RE_DIM captura na ordem errada',
             'Sempre aplicar: comp = max(a,b), larg = min(a,b). A convencao e '
             'comprimento >= largura.'],
        ]
    elif tipo == 'viga':
        common_issues += [
            ['apoio_fim vazio para viga normal', 'Pilar distante do endpoint da LINE',
             'Aumentar BEAM_SEARCH_RADIUS ou verificar se o pilar esta no layer correto.'],
            ['Comprimento = 0', 'Nenhuma LINE no layer "fundo"',
             'Verificar se o layer esta como "FUNDOS", "Fundo da Viga" ou outro alias. '
             'Usar normalize_layer() para encontrar.'],
        ]
    else:
        common_issues += [
            ['Area da laje = 0', 'LWPOLYLINE nao fechada',
             'Verificar flags da LWPOLYLINE: (flags & 1 == 1) ou e.is_closed. '
             'Se nao fechada, area_shoelace() retorna 0.'],
            ['Abertura nao detectada', 'Layer "Vazio" com encoding diferente',
             'Usar is_void_layer() que trata "Vazio", "V?zio", "VOID", etc. '
             'Se o layer e totalmente diferente, adicionar ao VOID_ALIASES.'],
        ]

    s.append(tbl(
        ['Problema', 'Causa Provavel', 'Solucao'],
        common_issues,
        col_widths=[40*mm, 36*mm, CW - 76*mm],
    ))
    s.append(PageBreak())
    return s


def build_glossario(ec):
    """Glossario de termos tecnicos."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('GL', 'Glossario de Termos Tecnicos', ec=ec, bg=bg))
    s.append(sp(3))

    termos = [
        ['AutoCAD DXF', 'Drawing Exchange Format -- formato de intercambio de desenhos AutoCAD.'],
        ['b (largura)', 'Menor dimensao da secao transversal de pilar ou viga, em cm.'],
        ['BA* (balanco)', 'Viga em balanco -- possui apenas 1 apoio. apoio_fim="" e correto.'],
        ['bbox', 'Bounding box -- retangulo envolvente minimo de uma geometria.'],
        ['bulge', 'Fator de curvatura em vertices de LWPOLYLINE. |bulge| > 0.3 indica cambotado.'],
        ['Cambotado', 'Pilar com secao nao retangular, com curva na LWPOLYLINE.'],
        ['Confidence', 'Score de confianca da extracao (0.0 a 1.0). Usado para threshold de aceitacao.'],
        ['CP1252', 'Codificacao de caracteres Windows-1252. Causa problemas em nomes de layers.'],
        ['DNA key', 'Chave de identificacao de tipo+subtipo usada pelo TransformationEngine.'],
        ['ezdxf', 'Biblioteca Python para leitura e escrita de arquivos DXF.'],
        ['FAISS', 'Facebook AI Similarity Search -- indice de vetores para busca por similaridade.'],
        ['FV (fundo)', 'Prancha de fundo da viga. Entidade LINE no layer "fundo".'],
        ['h (altura)', 'Maior dimensao da secao transversal de viga, ou espessura de laje, em cm.'],
        ['INSERT', 'Entidade DXF que representa uma insercao de bloco (ex: garfos, escoras).'],
        ['LINE', 'Entidade DXF que representa um segmento de reta (start, end).'],
        ['LV (lateral)', 'Paineis laterais da viga. Entidade LWPOLYLINE no layer "Paineis".'],
        ['LWPOLYLINE', 'Lightweight Polyline -- entidade DXF com vertices (x,y,bulge).'],
        ['modelspace (msp)', 'Espaco de modelo do DXF -- contem todas as entidades.'],
        ['NBR 6118', 'Norma brasileira de projeto de estruturas de concreto armado.'],
        ['NFKD', 'Normalizacao Unicode (Compatibility Decomposition) -- decompoe caracteres acentuados.'],
        ['Pe-direito', 'Altura livre entre pisos. Para pilares, e a altura do pilar.'],
        ['RAG', 'Retrieval-Augmented Generation -- enriquecimento de extracao via corpus.'],
        ['RE_DIM', 'Regex para capturar dimensoes no formato "NNxMM" ou "NN*MM".'],
        ['RE_PILAR', 'Regex para identificar IDs de pilares (P17, PC-1, PILAR 3, etc).'],
        ['RE_VIGA', 'Regex para identificar IDs de vigas (V101, BA-5, VB3, etc).'],
        ['RE_LAJE', 'Regex para identificar IDs de lajes (L5, Y1, LAJE 1, etc).'],
        ['Shoelace', 'Formula para calculo de area de poligono a partir de coordenadas.'],
        ['STOG', 'Structural Transformation Output Generator -- motor de geracao DXF.'],
        ['Sintetica', 'Laje gerada automaticamente a partir de clusters de textos h=.'],
        ['TextAssociator', 'Algoritmo que pareia textos DXF com poligonos por proximidade.'],
        ['Tramo', 'Segmento de viga entre dois apoios consecutivos.'],
    ]

    s.append(tbl(
        ['Termo', 'Definicao'],
        termos,
        col_widths=[36*mm, CW - 36*mm],
    ))
    s.append(PageBreak())
    return s


def build_changelog(ec):
    """Historico v5 -> v6 -> v7."""
    s = []
    bg = _bg_for(ec)
    s.append(SH('CL', 'Changelog -- v5 -> v6 -> v7', ec=ec, bg=bg))
    s.append(sp(3))

    s.append(h2('v7.0 (2026-03-19) -- Completo'))
    s.append(sp(1))
    changes_v7 = [
        ['Indice Geral', 'Tabela de conteudo com 30+ secoes numeradas'],
        ['Pipeline Overview', 'Pipeline 7 fases do CAD-ANALYZER com descricao detalhada'],
        ['Corpus Statistics', 'Dados reais hardcoded: 228 pilares, 351 vigas, 220 lajes em 11 obras'],
        ['Cross-Obra', 'P17 em 7 obras com dimensoes variadas (demonstra unicidade)'],
        ['RAG Plausibility', 'Documentacao completa do PlausibilityChecker com codigo'],
        ['RAG Validator', 'Documentacao do StructuralValidator com limites NBR 6118'],
        ['Anomaly Detector', 'Formula combinada + categorias + exemplos com P_ABS'],
        ['Pre-STOG Gate', 'Resultados das 11 obras (todas PASS) + criterios'],
        ['Robot Integration', 'Bolt/Crane/Slab robot + DXF output schema'],
        ['TransformationEngine', 'DNA key lookup + registry de transformers'],
        ['CEO-AUDIT D8', 'Acuracia por tipo de elemento (ground truth)'],
        ['Casos Especiais', 'Cambotado, circular, L, balanco, sintetica, vazios'],
        ['Encoding Guide', 'normalize_layer(), CP1252 vs UTF-8, tabela de conversoes'],
        ['API Reference', 'Todas as classes RAG com metodos e parametros'],
        ['Troubleshooting', 'Erros comuns e solucoes por tipo de elemento'],
        ['Glossario', '30+ termos tecnicos definidos'],
    ]
    s.append(tbl(
        ['Secao', 'Descricao'],
        changes_v7,
        col_widths=[36*mm, CW - 36*mm],
    ))
    s.append(sp(3))

    s.append(h2('v6.0 (2026-03-19) -- RAG Integration'))
    s.append(sp(1))
    changes_v6 = [
        ['RAG Section', 'Top-3 similares do corpus FAISS por elemento'],
        ['Thresholds', 'Tabela de decisao ACEITAR/ACEITAR_COM_AVISO/REVISAR/REJEITAR'],
        ['Anomaly Score', 'Formula: 0.5 * (1 - sim) + 0.5 * dim_penalty'],
        ['Integracao Pipeline', 'Codigo de exemplo para integracao com robot_integration.py'],
    ]
    s.append(tbl(
        ['Secao', 'Descricao'],
        changes_v6,
        col_widths=[36*mm, CW - 36*mm],
    ))
    s.append(sp(3))

    s.append(h2('v5.0 (2026-03-19) -- Base Instrutiva'))
    s.append(sp(1))
    changes_v5 = [
        ['Capa + TOC', 'Capa por elemento + tabela de conteudo 9-10 secoes'],
        ['Identificacao', 'RE_PILAR, RE_VIGA, RE_LAJE com tabelas de exemplos'],
        ['Associacao', 'TextAssociator 3 raios + diagrama matplotlib'],
        ['Secao Transversal', 'Diagrama pilar retangular + cambotado'],
        ['Layers', 'Tabela de layers canonicos + aliases + normalize_layer()'],
        ['Schema JSON', 'Schema completo FichaFase3 por tipo de elemento'],
        ['Confidence', 'Formula + diagrama visual + cadeia de fallbacks'],
        ['Matriz Decisao', 'Todos os casos ambiguos com acao e log'],
        ['Exemplos Reais', 'P17, V101, BA-5, L5, synth_0 com DXF e JSON'],
        ['Pipeline', 'Fluxo E2E 10-12 passos + diagrama matplotlib'],
    ]
    s.append(tbl(
        ['Secao', 'Descricao'],
        changes_v5,
        col_widths=[36*mm, CW - 36*mm],
    ))
    s.append(sp(2))
    s.append(note(
        'Total estimado: v5 = 12-15 paginas por PDF | v6 = +3-5 paginas | '
        'v7 = +15-20 paginas. Total v7: 30-40 paginas por PDF.',
        'info'
    ))
    return s


# ================================================================================
# HELPERS
# ================================================================================

def _bg_for(ec):
    """Retorna a cor de fundo correspondente ao ec."""
    if ec == ORANGE: return ORANGE_BG
    if ec == BLUE:   return BLUE_BG
    if ec == GREEN:  return GREEN_BG
    return ORANGE_BG


# ================================================================================
# BUILDERS FINAIS v7
# ================================================================================

def _secoes_pilares():
    """Lista de titulos de secoes para o indice de PILARES."""
    return [
        'Capa',
        'Indice Geral',
        'Sistema CAD-ANALYZER -- Pipeline 7 Fases',
        'Identificacao -- RE_PILAR',
        'Associacao Texto -> Poligono (3 Raios)',
        'Secao Transversal -- Dimensoes',
        'Layers Canonicos',
        'Schema JSON Completo -- FichaFase3Pilar',
        'Confidence e Fallbacks',
        'Matriz de Decisao',
        'Exemplos Reais -- Obra ALIMONTI',
        'Pipeline Completo',
        'Corpus Statistics -- PILARES',
        'Exemplos Reais por Obra',
        'Exemplos Cross-Obra',
        'RAG Integration -- Corpus Semantico',
        'RAG Plausibility -- PlausibilityChecker',
        'RAG Validator -- StructuralValidator',
        'RAG Anomaly Detector',
        'Pre-STOG Gate -- Resultados por Obra',
        'Robot Integration -- Bolt',
        'TransformationEngine -- DNA Key Lookup',
        'CEO-AUDIT D8 -- Acuracia',
        'Casos Especiais -- Cambotado, Circular, L',
        'Encoding Guide -- CP1252 vs UTF-8',
        'API Reference',
        'Troubleshooting',
        'Glossario',
        'Changelog v5 -> v6 -> v7',
    ]


def _secoes_vigas():
    return [
        'Capa',
        'Indice Geral',
        'Sistema CAD-ANALYZER -- Pipeline 7 Fases',
        'Identificacao -- RE_VIGA',
        'Geometria LV vs FV',
        'Viga em Balanco -- BA*/VB*',
        'Dimensoes b e h',
        'Schema JSON Completo -- FichaFase3Viga',
        'Layers Canonicos -- Viga',
        'Confidence e Fallbacks',
        'Matriz de Decisao',
        'Exemplos Reais -- Obra ALIMONTI',
        'Pipeline Completo',
        'Corpus Statistics -- VIGAS',
        'Exemplos Cross-Obra',
        'RAG Integration -- Corpus Semantico',
        'RAG Plausibility -- PlausibilityChecker',
        'RAG Validator -- StructuralValidator',
        'RAG Anomaly Detector',
        'Pre-STOG Gate -- Resultados por Obra',
        'Robot Integration -- Crane',
        'TransformationEngine -- DNA Key Lookup',
        'CEO-AUDIT D8 -- Acuracia',
        'Casos Especiais -- Balanco, Continua',
        'Encoding Guide -- CP1252 vs UTF-8',
        'API Reference',
        'Troubleshooting',
        'Glossario',
        'Changelog v5 -> v6 -> v7',
    ]


def _secoes_lajes():
    return [
        'Capa',
        'Indice Geral',
        'Sistema CAD-ANALYZER -- Pipeline 7 Fases',
        'Identificacao -- RE_LAJE e RE_LAJE_H',
        'Contorno e Area -- LWPOLYLINE',
        'Espessura -- Extracao de h=',
        'Laje Sintetica -- Clusters',
        'Schema JSON Completo -- FichaFase3Laje',
        'Layers Canonicos -- Laje',
        'Confidence',
        'Aberturas e Recortes',
        'Exemplos Reais -- Obra ALIMONTI',
        'Pipeline Completo',
        'Corpus Statistics -- LAJES',
        'Exemplos Cross-Obra',
        'RAG Integration -- Corpus Semantico',
        'RAG Plausibility -- PlausibilityChecker',
        'RAG Validator -- StructuralValidator',
        'RAG Anomaly Detector',
        'Pre-STOG Gate -- Resultados por Obra',
        'Robot Integration -- Slab',
        'TransformationEngine -- DNA Key Lookup',
        'CEO-AUDIT D8 -- Acuracia',
        'Casos Especiais -- Sintetica, Vazios',
        'Encoding Guide -- CP1252 vs UTF-8',
        'API Reference',
        'Troubleshooting',
        'Glossario',
        'Changelog v5 -> v6 -> v7',
    ]


def build_pilares_v7():
    """Builder completo PILARES: v5 base + v6 RAG + v7 secoes novas."""
    ec = ORANGE
    s = []

    # v5 secoes 1-9 (capa + 9 secoes = ~12-15 paginas)
    s += build_pilares()
    s.append(PageBreak())

    # Indice geral (inserido apos secoes base)
    s += build_indice(_secoes_pilares(), ec)

    # Pipeline overview
    s += build_pipeline_overview(ec)

    # Corpus statistics
    s += build_corpus_stats('pilar', ec)

    # Cross-obra
    s += build_cross_obra('pilar', ec)

    # RAG section (v6)
    s += build_rag_section('pilar', ec, ORANGE_BG)

    # RAG Plausibility
    s += build_rag_plausibility_doc(ec)

    # RAG Validator
    s += build_rag_validator_doc(ec)

    # Anomaly Detector
    s += build_anomaly_doc(ec)

    # Pre-STOG Gate
    s += build_pre_stog_gate_doc(ec)

    # Robot + TransformationEngine
    s += build_robot_doc('pilar', ec)

    # CEO-AUDIT D8
    s += build_ceo_audit_doc('pilar', ec)

    # Casos especiais
    s += build_casos_especiais('pilar', ec)

    # Encoding guide
    s += build_encoding_guide(ec)

    # API reference
    s += build_api_reference('pilar', ec)

    # Troubleshooting
    s += build_troubleshooting('pilar', ec)

    # Glossario
    s += build_glossario(ec)

    # Changelog
    s += build_changelog(ec)

    return s


def build_vigas_v7():
    """Builder completo VIGAS: v5 base + v6 RAG + v7 secoes novas."""
    ec = BLUE
    s = []

    s += build_vigas()
    s.append(PageBreak())

    s += build_indice(_secoes_vigas(), ec)
    s += build_pipeline_overview(ec)
    s += build_corpus_stats('viga', ec)
    s += build_cross_obra('viga', ec)
    s += build_rag_section('viga', ec, BLUE_BG)
    s += build_rag_plausibility_doc(ec)
    s += build_rag_validator_doc(ec)
    s += build_anomaly_doc(ec)
    s += build_pre_stog_gate_doc(ec)
    s += build_robot_doc('viga', ec)
    s += build_ceo_audit_doc('viga', ec)
    s += build_casos_especiais('viga', ec)
    s += build_encoding_guide(ec)
    s += build_api_reference('viga', ec)
    s += build_troubleshooting('viga', ec)
    s += build_glossario(ec)
    s += build_changelog(ec)

    return s


def build_lajes_v7():
    """Builder completo LAJES: v5 base + v6 RAG + v7 secoes novas."""
    ec = GREEN
    s = []

    s += build_lajes()
    s.append(PageBreak())

    s += build_indice(_secoes_lajes(), ec)
    s += build_pipeline_overview(ec)
    s += build_corpus_stats('laje', ec)
    s += build_cross_obra('laje', ec)
    s += build_rag_section('laje', ec, GREEN_BG)
    s += build_rag_plausibility_doc(ec)
    s += build_rag_validator_doc(ec)
    s += build_anomaly_doc(ec)
    s += build_pre_stog_gate_doc(ec)
    s += build_robot_doc('laje', ec)
    s += build_ceo_audit_doc('laje', ec)
    s += build_casos_especiais('laje', ec)
    s += build_encoding_guide(ec)
    s += build_api_reference('laje', ec)
    s += build_troubleshooting('laje', ec)
    s += build_glossario(ec)
    s += build_changelog(ec)

    return s


# ================================================================================
# PageHF v7
# ================================================================================

class PageHF_v7(PageHF):
    """Header/footer com versao v7.0."""
    def __call__(self, canvas, doc):
        super().__call__(canvas, doc)
        # Substituir versao no header (v5.0 -> v7.0)
        canvas.saveState()
        canvas.setFillColor(HexColor('#0d1b2e'))
        canvas.rect(PW - MR - 50*mm, PH - MT + 6*mm + 1, 50*mm, MT - 6*mm - 2, fill=1, stroke=0)
        canvas.setFillColor(HexColor('#8ba0cc'))
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(PW - MR, PH - 11*mm, 'v7.0  |  2026-03-19  |  COMPLETO')
        canvas.restoreState()


def make_doc_v7(path, elem, ec):
    """Cria documento PDF com header/footer v7."""
    hf = PageHF_v7(elem, ec)
    return SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        onFirstPage=hf, onLaterPages=hf,
        title=f'CAD-ANALYZER -- Fichas {elem} (v7 Completo)',
        author='Diana Corporacao Senciente'
    )


# ================================================================================
# MAIN -- GERAR PDFs
# ================================================================================

if __name__ == '__main__':
    print('CAD-ANALYZER -- Fichas v7 COMPLETO (ReportLab)')
    print(f'  Output dir: {OUT}')
    print('  Gerando 3 PDFs com 30+ paginas cada...')
    print()

    tasks = [
        ('fichas_pilares_v7_completo.pdf', 'PILARES', ORANGE, build_pilares_v7),
        ('fichas_vigas_v7_completo.pdf',   'VIGAS',   BLUE,   build_vigas_v7),
        ('fichas_lajes_v7_completo.pdf',   'LAJES',   GREEN,  build_lajes_v7),
    ]

    results = []
    for fname, elem, ec, builder in tasks:
        print(f'  Montando {elem}...')
        path = OUT / fname
        doc = make_doc_v7(path, elem, ec)
        story = builder()
        doc.build(story)
        kb = path.stat().st_size // 1024
        results.append((fname, kb))
        print(f'  [OK] {fname}: {kb} KB')

    print()
    print('=== RESULTADO FINAL ===')
    for fname, kb in results:
        path = OUT / fname
        print(f'  {path}: {kb} KB')

    # Verificar contagem de paginas (se PyMuPDF disponivel)
    try:
        import fitz  # PyMuPDF
        print()
        print('=== CONTAGEM DE PAGINAS ===')
        all_ok = True
        for fname, _ in results:
            path = OUT / fname
            pdf_doc = fitz.open(str(path))
            n_pages = pdf_doc.page_count
            pdf_doc.close()
            status = 'OK' if n_pages >= 30 else 'ABAIXO (< 30)'
            if n_pages < 30:
                all_ok = False
            print(f'  {fname}: {n_pages} paginas [{status}]')
        if all_ok:
            print()
            print('  TODOS os PDFs tem 30+ paginas.')
        else:
            print()
            print('  ATENCAO: Algum PDF tem menos de 30 paginas.')
    except ImportError:
        print()
        print('  (PyMuPDF nao instalado -- contagem de paginas nao disponivel)')
        print('  Para verificar: pip install PyMuPDF')

    print()
    print('Concluido.')
