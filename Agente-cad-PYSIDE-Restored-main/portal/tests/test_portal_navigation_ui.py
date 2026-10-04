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


def test_lista_de_obras_reusa_contorno_azul_sem_mudar_dimensoes_dos_cards():
    css = (STATIC / "portal.css").read_text(encoding="utf-8")

    assert ".side-obras-group-title" in css
    assert "border-left: 3px solid #3b82f6" in css
    assert "background: linear-gradient(90deg, rgba(37, 99, 235, .2)" in css
    assert ".obra-card-side {" in css
    assert "border: 1px solid #3b82f6" in css
    assert ".obra-card-side:focus-visible" in css
    # A borda já ocupava 1px transparente; mudar apenas a cor preserva caixa.
    assert "padding: 8px 10px" in css
    assert "border-radius: 9px" in css


def test_hub_usa_nome_detalhamento_etapas_sem_mudar_etapa_sa():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")

    assert "hubLabel: 'Detalhamento Etapas'" in drill
    assert "Detalhamento de Etapas" in drill
    assert "doc.kind === 'torre'" in drill
    assert 'data-level="' in drill
    assert "SA · N3 · N5 desta torre" in drill
    assert "state.analysisDoc = level || state.analysisDoc" in drill


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


def test_url_restaura_navegacao_granular_ate_item_e_aba_interna():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")
    fv = (STATIC / "fv_ficha.js").read_text(encoding="utf-8")

    for field in (
        "pavimento", "etapa", "classe", "item", "viga", "documento", "torre",
        "vista", "subvista", "lado", "segmento", "corte",
    ):
        assert field in drill
    assert "function readUrlIntent()" in drill
    assert "function syncNavigationUrl()" in drill
    assert "function finishRestore()" in drill
    assert "window.PortalDeepLink" in drill
    assert "data-pillar-n1-subtab" in drill
    assert "data-lv-layer" in drill
    assert "initialLayer: window.PortalDeepLink" in html
    assert "initialSide: window.PortalDeepLink" in html
    assert "window.PortalDeepLink.get('subvista', 'proximo')" in html
    assert "options.initialLayer || 'sa'" in fv
    assert "data-fv-target" in fv


def test_recortes_usam_um_viewer_com_abas_sincronizadas():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")
    css = (STATIC / "portal.css").read_text(encoding="utf-8")

    assert "Ordem fixa do viewer único: Bruto → Torres" in drill
    assert "function recorteTabsHtml(activeId)" in drill
    assert 'role="tablist"' in drill
    assert 'data-recorte-tab="' in drill
    assert "mountRecorteTabs(d.id)" in drill
    assert "refreshRecorteTabs" in drill
    assert "function selectRecorteDoc(id)" in drill
    assert "state.etapa = null" in drill
    assert "Recortes do Estrutural" in drill
    assert ".recorte-tabs-shell" in css
    assert ".drill-sec-recortes" in css

    # Detalhes oferece as mesmas ferramentas contextuais da torre: criação
    # de geometria SA e filtros de destaque sobre o recorte.
    assert "permiteFerramentasEstruturais = isTorre ||" in html
    assert "isRecorteEstruturalEditavel" in html
    assert "isRecorteEstruturalEditavel && window._viewerPavimentoAtual" in html


def test_refazer_recorte_substitui_explicitamente_e_reabre_o_item():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")

    assert "startRecorteReplace" in drill
    assert "openRecorteById: selectRecorteDoc" in drill
    assert "Substituir recorte existente" in html
    assert "substituir_item_id: substituirItem" in html
    assert "Refazer & Processar" in html
    assert "grupoCriar.firstElementChild.selected = true" in html
    assert "var substituirTorre = /^torre_\\d+$/.test(substituirItem || '')" in html
    assert "Somente os dados SA/N3/N5 vinculados a ela serão apagados" in html
    assert "Apenas o recorte selecionado será substituído" in html
    assert "os dados SA/N3/N5 das torres serão preservados" in html
    assert "confirmar_limpeza_dependencias: substituirTorre" in html
    assert "_recorte_atualizado" in html
    assert "cache: 'no-store'" in html
    assert "↻ Refazer recorte" in html
    assert "✖ Invalidar" not in html


def test_somente_recorte_de_torre_pode_invalidar_dados_estruturais():
    from portal.app.routers.recortes_routes import _recorte_tem_dependencias_estruturais

    assert _recorte_tem_dependencias_estruturais("torre_1") is True
    assert _recorte_tem_dependencias_estruturais("torre_27") is True
    assert _recorte_tem_dependencias_estruturais("detalhes") is False
    assert _recorte_tem_dependencias_estruturais("convencao_pilares") is False
    assert _recorte_tem_dependencias_estruturais("convencao_niveis") is False
    assert _recorte_tem_dependencias_estruturais("outros") is False


def test_limpeza_sa_da_substituicao_remove_somente_projeto_da_torre(tmp_path):
    import sqlite3
    from types import SimpleNamespace

    from portal.app.routers.recortes_routes import _limpar_projetos_sa

    db_path = tmp_path / "sa.vision"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE projects(id TEXT PRIMARY KEY);"
        "CREATE TABLE pillars(id TEXT, project_id TEXT);"
        "CREATE TABLE audit_sem_projeto(id TEXT);"
        "INSERT INTO projects VALUES ('torre1'), ('torre2');"
        "INSERT INTO pillars VALUES ('P1','torre1'), ('P2','torre2');"
    )
    conn.commit()
    conn.close()

    removidos = _limpar_projetos_sa(
        SimpleNamespace(sa_db_path=db_path), [{"project_id": "torre1"}],
    )

    conn = sqlite3.connect(db_path)
    assert removidos == 1
    assert conn.execute("SELECT id FROM projects ORDER BY id").fetchall() == [("torre2",)]
    assert conn.execute("SELECT id FROM pillars ORDER BY id").fetchall() == [("P2",)]
    conn.close()


def test_refazer_recorte_arquiva_somente_estado_e_run_da_torre_alvo(tmp_path):
    import json

    from portal.app.routers.recortes_routes import (
        _arquivar_artefatos_sa,
        _artefatos_sa_que_usam_recorte,
    )

    obra = tmp_path / "obra"
    recortes = obra / "Fase-2_Triagem" / "recortes" / "bruto"
    recortes.mkdir(parents=True)
    torre1 = recortes / "torre_1.dxf"
    torre2 = recortes / "torre_2.dxf"
    torre1.write_text("torre 1", encoding="utf-8")
    torre2.write_text("torre 2", encoding="utf-8")
    production = obra / "Fase-6_Execucao_CAD" / "production_sa"

    def run(pavimento, nome, source):
        pasta = production / pavimento / nome
        pasta.mkdir(parents=True)
        (pasta / "production_manifest.json").write_text(
            json.dumps({"source_dxf": str(source.resolve())}), encoding="utf-8",
        )
        return pasta

    run_torre2 = run("14_PAV", "20260921_100000_111", torre2)
    run_torre1 = run("14_PAV", "20260921_110000_222", torre1)
    run_torre2_outro_pav = run("15_PAV", "20260921_120000_333", torre2)
    canonical = obra / "estado_14_PAV.json"
    snapshot = obra / "estado_14_PAV_pid222.json"
    estado_outro = obra / "estado_15_PAV.json"
    for path in (canonical, snapshot, estado_outro):
        path.write_text("{}", encoding="utf-8")

    artefatos = _artefatos_sa_que_usam_recorte(obra, torre1)
    assert set(artefatos) == {run_torre1, canonical, snapshot}

    arquivados = _arquivar_artefatos_sa(obra, torre1, artefatos)
    assert len(arquivados) == 3
    assert not run_torre1.exists()
    assert not canonical.exists()
    assert not snapshot.exists()
    assert run_torre2.exists()
    assert run_torre2_outro_pav.exists()
    assert estado_outro.exists()


def test_motores_da_torre_confirmam_bloqueiam_e_exibem_progresso():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    css = (STATIC / "portal.css").read_text(encoding="utf-8")

    assert "if (!window.confirm(confirmLabel)) return" in drill
    assert "var allJob = activeJob('all')" in drill
    assert "var disabled = allJob || ownJob" in drill
    assert "drill-inline-job" in drill
    assert "percentual_estimado" in drill
    assert "% estimado" in drill
    assert "Finalizando · aguardando resposta do motor" in drill
    assert "Último processamento falhou" in drill
    assert "Rodar os 3 em sequência · SA → N3 → N5" in drill
    assert "function engineStep(stage, label)" in drill
    assert "engineStep('sa', 'Rodar interpretação · todas as classes')" in drill
    assert "engineStep('n3', 'Rodar desenho · todas as classes')" in drill
    assert "engineStep('n5', 'Rodar unificação · todas as classes')" in drill
    assert "drill-engine-all" in drill
    assert "drill-engine-flow" not in drill
    assert "SA interpreta e já materializa" not in drill
    assert ".drill-inline-job" in css
    assert ".drill-engine-step" in css


def test_motores_de_cada_classe_bloqueiam_e_exibem_progresso_por_etapa():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    css = (STATIC / "portal.css").read_text(encoding="utf-8")

    assert "jobMatchesClass(job, stage ? [stage, 'motores'] : ['sa', 'n3', 'n5', 'motores'])" in drill
    assert "var locked = !!(activeMotor || submittingMotor)" in drill
    assert "locked ? ' disabled aria-disabled=\"true\"'" in drill
    assert "motorProgress(ownJob, ownRequest)" in drill
    assert "role=\"progressbar\" aria-label=\"Progresso estimado do motor\"" in drill
    assert "var progressTimer = window.setInterval" in drill
    assert "delete submittingMotors[requestKey]" in drill
    assert ".drill-class-engine button:disabled" in css


def test_botoes_de_classes_usam_padrao_compacto_das_outras_classes():
    css = (STATIC / "portal.css").read_text(encoding="utf-8")
    bloco = css[css.index(".drill-cls-row {") : css.index(".drill-itens {")]

    assert "min-height: 28px" in bloco
    assert "padding: 4px 8px" in bloco
    assert "background: #152544" in bloco
    assert "border: 1px solid #3b82f6" in bloco
    assert "border-radius: 6px" in bloco


def test_preprocessamento_fica_no_hub_e_nao_herda_motores_estruturais():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    css = (STATIC / "portal.css").read_text(encoding="utf-8")

    hub = drill[drill.index("function renderHub()") : drill.index("function renderProcBox")]
    assert hub.index("Recortes do Estrutural") < hub.index("Pré-processamento")
    assert hub.index("Pré-processamento") < hub.index("Detalhamento de Etapas")
    assert "preRow('Visão de Cortes'" in hub
    assert "preRow('Convenção de Pilares'" in hub
    assert "preRow('Convenção de Níveis'" in hub
    assert "function renderCortesPreprocessamento()" in drill
    cortes = drill[drill.index("function renderCortesPreprocessamento()") : drill.index("function renderUnifiedProcBox()")]
    assert "renderClassActions" not in cortes
    assert "renderClassFooter" not in cortes
    assert "drill-criar" not in cortes
    assert "preproc-doc" in drill
    assert "preproc-cortes" in drill
    assert ".drill-pre-row" in css


def test_detalhamento_e_status_identificam_a_torre_sem_card_duplicado():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    css = (STATIC / "portal.css").read_text(encoding="utf-8")

    assert "function nomeTorreAnalise(doc)" in drill
    assert "Detalhamento da " in drill
    assert 'class="drill-tower-title"' in drill
    assert "Status ' + esc(torreNome)" not in drill
    assert "Status conjunto" not in drill
    assert ".drill-tower-title" in css
    assert "border-bottom: 2px solid #2563eb" in css
    assert ".drill-proc-unified { margin:0 8px 8px; padding:0; background:transparent; border:0;" in css


def test_cabecalho_lateral_exibe_apenas_nome_da_obra_com_estilo_de_titulo():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    css = (STATIC / "portal.css").read_text(encoding="utf-8")

    trecho = drill[drill.index("function crumbHtml()") : drill.index("function backLabel()")]
    assert "esc(OBRA_NOME)" in trecho
    assert "state.pav" not in trecho
    assert "state.etapa" not in trecho
    assert "drill-crumb drill-obra-title" in drill
    assert ".drill-obra-title" in css
    assert "border-bottom: 2px solid #2563eb" in css


def test_alerta_da_obra_oculta_ruido_qt_e_explicita_falha_n3():
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")

    assert "O motor de desenho N3 não concluiu" in html
    assert "Os dados SA foram preservados" in html
    assert "obra.erro_msg.split('[portal]')[-1].strip()" in html
    assert 'id="obra-erro-alerta" role="alert" style="white-space:pre-wrap' not in html
    assert "obra-engine-alert-close" in html
    assert "Fechar e não mostrar novamente" in html
    assert "window.localStorage.setItem(storageKey, mensagem)" in html
    assert "window.localStorage.getItem(storageKey) === mensagem" in html


def test_progresso_sa_conta_somente_recortes_de_torre():
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")

    assert "Somente torres são unidades de SA" in html
    assert "String(item.item_id || '').indexOf('torre') === 0" in html


def test_botao_unificados_compartilha_design_das_outras_classes():
    css = (STATIC / "portal.css").read_text(encoding="utf-8")

    assert ".drill-class-actions button,\n.drill-unified,\n.drill-other-classes button" in css
    assert ".drill-unified:hover,\n.drill-unified:focus-visible," in css
    assert ".drill-unified { margin:4px 8px 5px; width:calc(100% - 16px); }" in css
    assert ".drill-unified { margin:9px 6px 5px" not in css
    assert "color:#bbf7d0" not in css


def test_sidebar_remove_rotulos_redundantes():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")

    assert "Dono — vê tudo" not in base
    assert "Abre a Torre limpa à direita · coluna fica nesta classe" not in drill


def test_fluxo_n5_separa_unificados_da_gestao_global():
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    html = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")

    assert "function statusMarker(status, label)" in drill
    assert "engineStatusMarker(stage)" in drill
    assert "classMotorButton('sa', 'Rodar motor interpretativo')" in drill
    assert "classMotorButton('n3', 'Rodar motor de desenho')" in drill
    assert "classMotorButton('n5', 'Rodar motor de unificação')" in drill
    assert "qaStatusMarker(layer)" in drill
    assert "if (c === 'lajes') return 'LJ'" in drill
    assert drill.index("classMotorButton('n5', 'Rodar motor de unificação')") < drill.index('data-drill="unificados">Visualizar unificados')
    assert "mostrarDetalhe('n5-pavimento')" in drill
    assert "intent.vista === 'unificados'" in drill
    assert 'id="detalhe-n5-pavimento"' in html
    assert 'data-open-finalizados' in html
    assert "Acessar Gestão de finalizados" in html
    assert "Download Todos N5 (Zip)" not in html
    assert "Downloads N5 por pavimento" in html
    assert "Baixar ZIP completo de" in html
    assert "Baixar todos os pavimentos" in html
    assert 'data-validar-n5="{{ classe }}"' in html
    assert 'class="n5-pav-tabs"' in html
    assert 'data-n5-tab="{{ classe }}"' in html
    assert 'data-n5-panel="{{ classe }}"' in html
    assert 'data-n5-svg-src=' in html
    assert '<img loading="lazy" alt="N5' not in html
    assert "function carregarSvgN5(viewport)" in html
    assert "new DOMParser().parseFromString(source, 'image/svg+xml')" in html
    assert "Baixar ZIP do pavimento" in html
    assert 'class="n5-pav-grid"' not in html
