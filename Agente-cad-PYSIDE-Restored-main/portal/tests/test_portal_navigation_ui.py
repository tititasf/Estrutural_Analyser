"""Regressoes da navegacao compacta e dos destaques integrados da obra."""

from pathlib import Path


TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_sidebar_tem_controle_acessivel_e_persistente_de_recolher():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    css = (STATIC / "portal.css").read_text(encoding="utf-8")

    assert 'id="portal-sidebar"' in base
    assert 'id="sidebar-collapse-toggle"' in base
    assert 'aria-controls="portal-sidebar"' in base
    assert "portal-sidebar-collapsed" in base
    assert "body.sidebar-collapsed .sidebar" in css
    assert "body.sidebar-collapsed .sidebar-collapse-toggle" in css


def test_hub_usa_nome_detalhamento_etapas_sem_mudar_etapa_sa():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")

    assert "hubLabel: 'Detalhamento Etapas'" in drill
    assert "var hubLabel = e.hubLabel || (e.nome + ' · ' + e.short)" in drill
    assert "data-id=\"' + e.id" in drill


def test_viewer_integrado_unifica_laterais_por_para_e_passa():
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")

    assert "function gruposDestaqueParaExibicao" in html
    assert "id === 'lat_a_para' || id === 'lat_b_para'" in html
    assert "id === 'lat_a_passa' || id === 'lat_b_passa'" in html
    assert "Lateral A.B. · Para" in html
    assert "Lateral A.B. · Passa" in html
    assert "gruposDestaque.forEach(function (grupo)" in html


def test_drill_separa_lados_e_abre_criacao_na_classe_real():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")

    assert "laterais_para" in drill
    assert "lateral_a_para" in drill
    assert "lateral_b_para" in drill
    assert "function renderLateraisCombinadas" in drill
    assert "drill-viga-sidecount\">A · " in drill
    assert "drill-viga-sidecount\">B · " in drill
    assert "renderSegmentosLadoSelecionado('A'" in drill
    assert "renderSegmentosLadoSelecionado('B'" in drill
    assert "Criar segmento ' + lado" in drill
    assert "openTorreCriar(id, level || '')" in drill
    assert "window._criarItemVigaPref = vigaPref || null" in drill

    # A abertura pelo drill deve entregar formulário realmente aberto, com a
    # classe A/B selecionada e o nome da viga disponível antes de calcular SEG.
    assert "var prefViga = window._criarItemVigaPref" in html
    assert "inpNome.value = normalizarNomeViga(prefViga)" in html
    assert "(prefClasse ? ' open' : '')" in html


def test_criacao_de_segmento_reutiliza_nome_da_viga_sem_duplicar_seg():
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")

    assert "function segmentosDaViga(classe, nomeViga, brutoId)" in html
    assert "normalizarNomeViga(r.nome || r.beam_name) !== nomeN" in html
    assert "beam_name: nome" in html
    assert "SEG ' + seg + ' já existe" in html


def test_revisao_agentica_da_classe_exibe_progresso_persistente():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    css = (STATIC / "portal.css").read_text(encoding="utf-8")
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")

    assert "QA_STORAGE_KEY" in drill
    assert "pollQaRound(data.round_id)" in drill
    assert "recoverQaRunsFromJobs" in drill
    assert "processando item " in drill
    assert "aria-live=\"polite\"" in drill
    assert "drill-qa-progress" in css
    assert "button.is-processing" in css
    assert 'data-drill="qa-job-control"' in drill
    assert "controlQaJob(id, level)" in drill
    assert "drill-qa-controls" in css
    assert 'id="job-control"' not in html
    assert 'data-job-control=' not in html
