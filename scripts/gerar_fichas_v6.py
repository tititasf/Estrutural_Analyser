#!/usr/bin/env python3
"""Fichas Instrutivas v6 — CAD-ANALYZER
Extende v5 com seção RAG: Top-3 similares do corpus por elemento.
Gera os mesmos 3 PDFs + seção RAG ao final de cada ficha.
"""
import sys
from pathlib import Path

# ── Importar infraestrutura de v5 ────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from gerar_fichas_v5 import (
    # estilos e helpers
    SS, CW, NAVY, ORANGE, BLUE, GREEN, ORANGE_BG, BLUE_BG, GREEN_BG,
    GRAY1, GRAY2, BORDER, TEXT, TEXT2, INFO_BG, INFO_BD, WARN_BG, WARN_BD,
    OK_BG, OK_BD, ERR_BG, ERR_BD, OUT, IMGS, PW, PH, ML, MR, MT, MB,
    p, h1, h2, h3, sp, hr, caption, tbl, note, cb, esc, SH, PageHF, make_doc,
    # builders de cada elemento
    build_pilares, build_vigas, build_lajes,
)
from reportlab.lib.colors  import HexColor, white
from reportlab.lib.units   import mm
from reportlab.platypus    import (
    Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── RAG Imports (graceful degradation) ───────────────────────────────────────
_RAG_OK = False
try:
    from rag_commons import query as _rag_query, get_anomaly_score as _rag_anomaly
    _RAG_OK = True
except Exception as _e:
    _rag_query   = None
    _rag_anomaly = None


# ── Helpers RAG visuais ───────────────────────────────────────────────────────

def _rag_badge(score: float) -> str:
    """Converte similarity em badge colorido HTML para Paragraph."""
    if score >= 0.85:
        return f'<font color="#006b3f"><b>{score:.3f} ✓</b></font>'
    elif score >= 0.65:
        return f'<font color="#d97706"><b>{score:.3f} ~</b></font>'
    else:
        return f'<font color="#dc2626"><b>{score:.3f} !</b></font>'


def _rag_categoria(score: float) -> str:
    if score >= 0.85: return 'ACEITAR'
    if score >= 0.65: return 'ACEITAR_COM_AVISO'
    if score >= 0.40: return 'REVISAR'
    return 'REJEITAR'


def _fmt_meta(meta: dict, tipo: str) -> list:
    """Formata metadados RAG de um resultado similar para exibição."""
    rows = []
    obra = meta.get('obra', '—')
    pav  = meta.get('pavimento', '—')
    eid  = meta.get('elemento_id', meta.get('id', '—'))
    rows.append(['ID', eid])
    rows.append(['Obra', obra])
    rows.append(['Pavimento', pav])
    if tipo == 'pilar':
        b = meta.get('b', meta.get('largura', '—'))
        h = meta.get('h', meta.get('altura_secao', '—'))
        alt = meta.get('altura', meta.get('height', '—'))
        rows.append(['Seção (b×h)', f'{b} × {h} cm'])
        rows.append(['Altura', f'{alt} cm'])
    elif tipo == 'viga':
        b = meta.get('b', meta.get('largura', '—'))
        h = meta.get('h', '—')
        comp = meta.get('comprimento', '—')
        rows.append(['Seção (b×h)', f'{b} × {h} cm'])
        rows.append(['Comprimento', f'{comp} cm'])
    elif tipo == 'laje':
        esp  = meta.get('espessura', '—')
        area = meta.get('area_cm2', '—')
        rows.append(['Espessura', f'{esp} cm'])
        rows.append(['Área', f'{area} cm²'])
    return rows


def build_rag_section(tipo: str, ec, bg) -> list:
    """
    Seção RAG com Top-3 similares do corpus FAISS para o tipo de elemento.
    Inclui: score de similaridade, categoria, propriedades dimensionais.
    Retorna lista de flowables para inserir na story ReportLab.
    """
    s = []

    # ── Header da seção ──────────────────────────────────────────────────────
    sec_header = SH('RAG', f'Corpus Semântico — Top-3 Similares ({tipo.upper()})', ec=ec, bg=bg)
    s.append(sec_header)
    s.append(sp(3))

    if not _RAG_OK:
        s.append(note(
            'RAG não disponível — rag_commons.py não encontrado ou FAISS não carregado. '
            'Execute scripts/rag_ingestor.py para popular o índice.',
            'warn'
        ))
        s.append(sp(3))
        return s

    # ── Queries de demonstração por tipo ────────────────────────────────────
    QUERIES_DEMO = {
        'pilar': [
            ('Pilar retangular 20x50 pé-direito 652cm',  {'b': 20.0, 'h': 50.0, 'altura': 652.0}),
            ('Pilar quadrado 40x40 pé-direito 280cm',    {'b': 40.0, 'h': 40.0, 'altura': 280.0}),
            ('Pilar largo 20x90 estrutura especial',     {'b': 20.0, 'h': 90.0, 'altura': 300.0}),
        ],
        'viga':  [
            ('Viga baldrame 14x40 comprimento 320cm',    {'b': 14.0, 'h': 40.0, 'comprimento': 320.0}),
            ('Viga de fôrma 20x60 comprimento 600cm',    {'b': 20.0, 'h': 60.0, 'comprimento': 600.0}),
            ('Viga invertida 14x25 comprimento 180cm',   {'b': 14.0, 'h': 25.0, 'comprimento': 180.0}),
        ],
        'laje':  [
            ('Laje plana espessura 12cm área 171m²',     {'espessura': 12.0, 'area_cm2': 171000.0}),
            ('Laje maciça espessura 20cm área 50m²',     {'espessura': 20.0, 'area_cm2': 50000.0}),
            ('Laje nervurada espessura 15cm área 90m²',  {'espessura': 15.0, 'area_cm2': 90000.0}),
        ],
    }

    demos = QUERIES_DEMO.get(tipo, [])

    for q_idx, (query_text, dims) in enumerate(demos, 1):
        s.append(h2(f'Consulta {q_idx}: "{query_text}"'))
        s.append(sp(1))

        # Dimensões da consulta
        dim_rows = [[k, str(v)] for k, v in dims.items()]
        s.append(tbl(
            ['Parâmetro', 'Valor'],
            dim_rows,
            col_widths=[60*mm, CW - 60*mm],
        ))
        s.append(sp(2))

        # Query RAG
        try:
            resultados = _rag_query(query_text, tipo=tipo, k=3, threshold=0.0)
        except Exception as ex:
            s.append(note(f'Erro na consulta RAG: {esc(str(ex))}', 'err'))
            s.append(sp(2))
            continue

        if not resultados:
            s.append(note('Nenhum resultado similar encontrado no corpus.', 'warn'))
            s.append(sp(2))
            continue

        # Top-3 similares
        sim_data = []
        for rank, res in enumerate(resultados[:3], 1):
            score = res.get('score', 0.0)
            meta  = res.get('meta', {})
            cat   = _rag_categoria(score)

            props_rows = _fmt_meta(meta, tipo)
            props_str  = ' | '.join(f'{k}: {v}' for k, v in props_rows)

            sim_data.append([
                str(rank),
                _rag_badge(score),
                esc(meta.get('obra', '—')),
                esc(meta.get('elemento_id', meta.get('id', '—'))),
                esc(cat),
                esc(props_str),
            ])

        # Tabela de resultados
        col_w = [8*mm, 18*mm, 32*mm, 20*mm, 30*mm, CW - 108*mm]
        sim_rows_rendered = []
        for row in sim_data:
            rendered = []
            for i, cell in enumerate(row):
                if i == 1:  # badge com HTML
                    rendered.append(Paragraph(cell, SS['TC']))
                else:
                    rendered.append(Paragraph(esc(str(cell)), SS['TC']))
            sim_rows_rendered.append(rendered)

        headers = ['#', 'Score', 'Obra', 'ID', 'Ação RAG', 'Propriedades']
        data_tbl = [[Paragraph(esc(h), SS['TH']) for h in headers]] + sim_rows_rendered
        t = Table(data_tbl, colWidths=col_w, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  ec),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [GRAY1, GRAY2]),
            ('FONTSIZE',      (0, 0), (-1, -1), 8.0),
            ('LEFTPADDING',   (0, 0), (-1, -1), 5),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID',          (0, 0), (-1, -1), 0.3, BORDER),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        s.append(t)
        s.append(sp(1))

        # Nota interpretativa
        if resultados:
            top_score = resultados[0].get('score', 0)
            cat_top   = _rag_categoria(top_score)
            msgs = {
                'ACEITAR':            f'Top-1 similarity {top_score:.3f} — elemento bem coberto pelo corpus de treino.',
                'ACEITAR_COM_AVISO':  f'Top-1 similarity {top_score:.3f} — elemento similar ao corpus, atenção às dimensões.',
                'REVISAR':            f'Top-1 similarity {top_score:.3f} — elemento incomum. Revisão recomendada.',
                'REJEITAR':          f'Top-1 similarity {top_score:.3f} — elemento muito distante do corpus. Verificar dados.',
            }
            kind = 'ok' if cat_top == 'ACEITAR' else ('info' if cat_top == 'ACEITAR_COM_AVISO' else 'warn')
            s.append(note(msgs.get(cat_top, ''), kind))

        s.append(sp(3))

    # ── Tabela de thresholds RAG ─────────────────────────────────────────────
    s.append(h2('Thresholds de Decisão RAG'))
    s.append(sp(1))
    thresh_rows = [
        ['≥ 0.85', 'ACEITAR',           'Elemento típico — gerar DXF sem restrições'],
        ['≥ 0.65', 'ACEITAR_COM_AVISO', 'Elemento similar — alertar revisor, prosseguir'],
        ['≥ 0.40', 'REVISAR',           'Elemento incomum — suspender até revisão humana'],
        ['< 0.40', 'REJEITAR',          'Elemento anômalo — bloquear geração DXF'],
    ]
    s.append(tbl(
        ['Similarity', 'Ação', 'Comportamento do Pipeline'],
        thresh_rows,
        col_widths=[20*mm, 40*mm, CW - 60*mm],
    ))
    s.append(sp(2))

    # ── Fórmula AnomalyScore ─────────────────────────────────────────────────
    s.append(h2('Fórmula de Anomaly Score'))
    s += cb([
        'anomaly = 0.5 * (1 - semantic_similarity) + 0.5 * dim_penalty',
        '',
        'dim_penalty:',
        '  0.0  →  Todas as dimensões OK (dentro dos limites calibrados)',
        '  0.5  →  Pelo menos 1 AVISO dimensional',
        '  1.0  →  Pelo menos 1 CRÍTICO dimensional',
        '',
        'Categorias:',
        '  NORMAL   (0.00–0.30)  →  Elemento típico do corpus',
        '  INCOMUM  (0.30–0.55)  →  Aceitar com atenção',
        '  SUSPEITO (0.55–0.75)  →  Revisar antes de gerar DXF',
        '  ANOMALO  (0.75–1.00)  →  Bloquear geração',
    ], ec=ec)
    s.append(sp(2))

    # ── Integração no pipeline ────────────────────────────────────────────────
    s.append(h2('Integração no Pipeline'))
    s += cb([
        '# Em robot_integration.py (antes de engine.transform):',
        'from rag_plausibility import PlausibilityChecker',
        'from rag_validator    import StructuralValidator',
        '',
        '_plaus = PlausibilityChecker()',
        '_val   = StructuralValidator()',
        '',
        '# 1. Validação dimensional (hard limits — determinístico)',
        'val = _val.validate(tipo, eid, entity_data, obra)',
        'if val.bloqueado:',
        '    stats["skipped"] += 1',
        '    continue  # BLOQUEAR antes do TransformationEngine',
        '',
        '# 2. Plausibilidade semântica (RAG)',
        'plaus = _plaus.check(eid, tipo, entity_data, obra)',
        'if plaus.acao in ("REVISAR", "REJEITAR"):',
        '    entity_data["_rag_nota"] = plaus.nota_rag  # enriquecer',
    ], ec=ec)
    s.append(PageBreak())

    return s


# ════════════════════════════════════════════════════════════════════════════
# VERSÃO v6: builders estendidos com seção RAG
# ════════════════════════════════════════════════════════════════════════════

def build_pilares_v6():
    return build_pilares() + build_rag_section('pilar', ORANGE, ORANGE_BG)

def build_vigas_v6():
    return build_vigas() + build_rag_section('viga', BLUE, BLUE_BG)

def build_lajes_v6():
    return build_lajes() + build_rag_section('laje', GREEN, GREEN_BG)


# ── PageHF v6 ────────────────────────────────────────────────────────────────
class PageHF_v6(PageHF):
    def __call__(self, canvas, doc):
        super().__call__(canvas, doc)
        # Substituir versão no header (v5.0 → v6.0)
        canvas.saveState()
        canvas.setFillColor(HexColor('#0d1b2e'))
        canvas.rect(PW - MR - 50*mm, PH - MT + 6*mm + 1, 50*mm, MT - 6*mm - 2, fill=1, stroke=0)
        canvas.setFillColor(HexColor('#8ba0cc'))
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(PW - MR, PH - 11*mm, 'v6.0  ·  2026-03-19')
        canvas.restoreState()


def make_doc_v6(path, elem, ec):
    hf = PageHF_v6(elem, ec)
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate
    return SimpleDocTemplate(str(path), pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        onFirstPage=hf, onLaterPages=hf,
        title=f'CAD-ANALYZER · Fichas {elem} (RAG v6)', author='Diana Corporação Senciente')


# ════════════════════════════════════════════════════════════════════════════
# GERAR PDFs v6
# ════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    rag_status = 'OK (FAISS carregado)' if _RAG_OK else 'AUSENTE (seção RAG sem dados reais)'
    print(f'CAD-ANALYZER — Fichas v6 (ReportLab + RAG Similares)')
    print(f'  RAG: {rag_status}')
    print('  Gerando PDFs...')

    tasks = [
        ('fichas_pilares_v6.pdf', 'PILARES', ORANGE, build_pilares_v6),
        ('fichas_vigas_v6.pdf',   'VIGAS',   BLUE,   build_vigas_v6),
        ('fichas_lajes_v6.pdf',   'LAJES',   GREEN,  build_lajes_v6),
    ]

    for fname, elem, ec, builder in tasks:
        print(f'  Montando {elem}...')
        path = OUT / fname
        doc  = make_doc_v6(path, elem, ec)
        story = builder()
        doc.build(story)
        kb = path.stat().st_size // 1024
        print(f'  [OK] {fname}: {kb} KB')

    print('\nConcluido:')
    for fname, *_ in tasks:
        path = OUT / fname
        if path.exists():
            print(f'  {path}: {path.stat().st_size // 1024} KB')
