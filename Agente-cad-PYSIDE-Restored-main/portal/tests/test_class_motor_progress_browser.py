"""Os motores da classe exibem o job correto e bloqueiam disparos repetidos."""

from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "app" / "static" / "drill_grade.js"
STYLE = SCRIPT.with_name("portal.css")


@pytest.fixture
def page():
    sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as error:
            pytest.skip(f"Chromium indisponível: {error}")
        page = browser.new_page()
        page.set_content('<div id="drill-root" data-obra="test" data-obra-nome="Obra"></div>')
        page.add_style_tag(path=str(STYLE))
        page.add_script_tag(path=str(SCRIPT))
        yield page
        browser.close()


@pytest.mark.parametrize("classe,secao", [
    ("pilares", "pilares"),
    ("lajes", "lajes"),
    ("fundo", "fundos_viga"),
    ("laterais_para", "laterais_viga"),
])
def test_job_n3_mostra_percentual_e_bloqueia_motores_da_classe(page, classe, secao):
    page.evaluate("""({classe,secao}) => {
      const state = window.DrillGrade.state;
      state.level = 'itens'; state.etapa = 'sa'; state.pav = '14_PAV'; state.classe = classe;
      state.classesCache = [{classe, titulo:classe, total:1}]; state.itens = [];
      window._todosJobs = [{id:'job', status:'executando',
        meta:{etapa:'n3', pav:'14_PAV', secao:[secao]},
        progresso:{percentual_estimado:42, rotulo:'Processando no motor',
          decorrido_s:60, restante_estimado_s:80}}];
      window.DrillGrade.render();
    }""", {"classe": classe, "secao": secao})

    buttons = page.locator('.drill-class-engine button')
    assert buttons.count() == 3
    assert all(button.is_disabled() for button in buttons.all())
    assert page.locator('.drill-class-engine [role="progressbar"]').count() == 1
    assert page.locator('.drill-class-engine [role="progressbar"]').get_attribute('aria-valuenow') == '42'
    assert '42% estimado' in page.locator('.drill-class-engine').nth(1).inner_text()


def test_n5_sincrono_mostra_estimativa_e_trava_ate_resposta(page):
    page.evaluate("""() => {
      const state = window.DrillGrade.state;
      state.level='itens'; state.etapa='sa'; state.pav='14_PAV'; state.classe='pilares';
      state.classesCache=[{classe:'pilares',titulo:'Pilares',total:1}]; state.itens=[];
      window._todosJobs=[];
      window.escolherModoDesenho=() => Promise.resolve('NOVA');
      window.fetch=() => new Promise(() => {});
      window.DrillGrade.render();
    }""")

    page.locator('.drill-class-engine button[data-id="n5"]').click()
    page.locator('.drill-class-engine [role="progressbar"]').wait_for()
    assert all(button.is_disabled() for button in page.locator('.drill-class-engine button').all())
    assert 'estimado' in page.locator('.drill-class-engine').nth(2).inner_text()


def test_job_lateral_passa_nao_bloqueia_para_nem_outro_pavimento(page):
    page.evaluate("""() => {
      const state = window.DrillGrade.state;
      state.level='itens'; state.etapa='sa'; state.pav='14_PAV';
      state.classe='laterais_passa'; state.classesCache=[]; state.itens=[];
      window._todosJobs=[{id:'passa',status:'na_fila',
        meta:{etapa:'sa',pav:'14_PAV',secao:['laterais_viga'],classe_ui:'laterais_passa'},
        fila:{posicao:3,a_frente:2,total_ativos:5},
        progresso:{percentual_estimado:0}}];
      window.DrillGrade.render();
    }""")
    assert all(button.is_disabled() for button in page.locator('.drill-class-engine button').all())
    assert 'posição 3 de 5 · 2 pedidos à frente' in page.locator('.drill-class-engine').first.inner_text()

    page.evaluate("""() => {
      window.DrillGrade.state.classe='laterais_para';
      window.DrillGrade.render();
    }""")
    assert all(not button.is_disabled() for button in page.locator('.drill-class-engine button').all())
    assert page.locator('.drill-class-engine [role="progressbar"]').count() == 0

    page.evaluate("""() => {
      window.DrillGrade.state.classe='laterais_passa';
      window.DrillGrade.state.pav='15_PAV';
      window.DrillGrade.render();
    }""")
    assert all(not button.is_disabled() for button in page.locator('.drill-class-engine button').all())
