from pathlib import Path
from copy import deepcopy
import pytest

ROOT = Path(__file__).resolve().parents[2]
fixture = {
    "pillar": "P10", "special": False, "source": {"human_override": False}, "revision": 0,
    "faces": {"B": {
        "n3_width_extra": 22, "top_void_cm": 0,
        "panels": [
            {"id": "B1-1", "row": 1, "column": 1, "distance": 0, "width": 60, "height": 2, "kind": "panel", "hatch": "none"},
            {"id": "B2-1", "row": 2, "column": 1, "distance": 0, "width": 60, "height": 122, "kind": "panel", "hatch": "none"},
            {"id": "B3-1", "row": 3, "column": 1, "distance": 0, "width": 60, "height": 122, "kind": "panel", "hatch": "none"},
            {"id": "B4-1", "row": 4, "column": 1, "distance": 0, "width": 60, "height": 60, "kind": "panel", "hatch": "none"},
        ],
        "openings": {
            "left": [
                {"distance": 0, "width": 11, "depth": 64, "level": 0, "top_distance": 0, "element_level": 855.25, "beam_name": "V409", "beam_dimension": "19/60", "beam_behavior": "viga_para"},
            ],
            "right": [
                {"distance": 0, "width": 34, "depth": 59, "level": 0, "top_distance": 0, "element_level": 855.25, "beam_name": "V402", "beam_dimension": "19/55", "beam_behavior": "viga_chega"},
                {"distance": 0, "width": 11, "depth": 64, "level": 0, "top_distance": 0, "element_level": 855.25, "beam_name": "V410", "beam_dimension": "19/60", "beam_behavior": "viga_para"},
            ],
        },
        "slabs": [{"left_distance": 11, "right_distance": 34, "top_distance": 3, "level": 852.12, "width": 37, "height": 16, "slab_name": "L410", "slab_dimension": "14", "slab_behavior": "laje"}],
    }},
}

def test_connected_l_panel_uses_overall_measurements_and_adapts_on_edit():
    sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as error:
            pytest.skip(f"Chromium indisponível: {error}")
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_content('<div id="pillar-n3-editor"></div>')
        page.add_style_tag(path=str(ROOT / "portal/app/static/pillar_ficha.css"))
        page.evaluate("fixture => { window.savedFichas=[]; window.fetch = (url,options) => { if(options&&options.method==='PUT') window.savedFichas.push(JSON.parse(options.body).ficha); return Promise.resolve({ok:true,json:()=>Promise.resolve({ficha:fixture,revision:1})}); }; }", fixture)
        page.add_script_tag(path=str(ROOT / "portal/app/static/pillar_ficha.js"))
        page.evaluate("PillarFicha.mount(document.querySelector('#pillar-n3-editor'), {obraId:'x',classe:'pilares',itemId:'P10',initialTab:'abcd-para'})")
        page.wait_for_selector('.plf-svg-cell')
        before = page.locator('g[data-face="B"] .plf-svg-cell[data-panel-id="B4-1"]')
        assert before.count() == 2, [item.get_attribute('aria-label') for item in before.all()]
        assert [item.locator('rect').count() for item in before.all()] == [1, 2]
        assert before.nth(1).locator('rect').first.evaluate('(rect) => getComputedStyle(rect).stroke') == 'none'
        joined = before.nth(1).evaluate('group => [...group.querySelectorAll("rect")].map(r => ({x:+r.getAttribute("x"), y:+r.getAttribute("y"), w:+r.getAttribute("width"), h:+r.getAttribute("height")}))')
        assert min(joined[0]['x']+joined[0]['w'], joined[1]['x']+joined[1]['w']) - max(joined[0]['x'], joined[1]['x']) > 0
        assert min(joined[0]['y']+joined[0]['h'], joined[1]['y']+joined[1]['h']) - max(joined[0]['y'], joined[1]['y']) > 0
        l_panel = page.get_by_role('button', name='B4-1.2 · em L · 60 × 41 cm', exact=True)
        l_panel.click()
        width = page.locator('[data-panel-dimension="width"] input')
        height = page.locator('[data-panel-dimension="height"] input')
        assert width.input_value() == '60'
        assert height.input_value() == '41'
        width.fill('65')
        width.press('Tab')
        after = page.locator('g[data-face="B"] .plf-svg-cell[data-panel-id="B4-1"]')
        labels = [item.get_attribute('aria-label') for item in after.all()]
        assert len(labels) == 2, labels
        assert any('em L · 65 × 41 cm' in label for label in labels), labels
        height = page.locator('[data-panel-dimension="height"] input')
        height.fill('45')
        height.press('Tab')
        labels = [item.get_attribute('aria-label') for item in after.all()]
        assert any('em L · 65 × 45 cm' in label for label in labels), labels
        page.get_by_role('button', name='B4-1.2 · em L · 65 × 45 cm', exact=True).click()
        assert page.locator('[data-panel-dimension="width"] input').input_value() == '65'
        assert page.locator('[data-panel-dimension="height"] input').input_value() == '45'
        page.wait_for_timeout(1000)
        assert page.evaluate('window.savedFichas.length') > 0, (page.locator('.plf-status').inner_text(), errors)
        saved = page.evaluate('window.savedFichas.at(-1).faces.B')
        assert saved['panels'][-1]['width'] == 65
        assert saved['panels'][-1]['height'] == 64
        assert saved['slabs'][0]['width'] == 42
        browser.close()


def test_corte_totalmente_coberto_fica_na_ficha_mas_nao_duplica_no_desenho():
    sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
    data = deepcopy(fixture)
    data["faces"]["B"]["openings"]["right"] = [
        {"distance": 0, "width": 34, "depth": 59, "level": 0,
         "top_distance": 0, "element_level": 855.25, "beam_name": "V402", "beam_behavior": "viga_chega"},
        {"distance": 0, "width": 11, "depth": 40, "level": 0,
         "top_distance": 0, "element_level": 855.25, "beam_name": "V410", "beam_behavior": "viga_para"},
    ]
    data["faces"]["B"]["slabs"] = [{"left_distance": 48, "right_distance": 14,
                                      "top_distance": 0, "width": 20, "height": 10,
                                      "slab_name": "L410", "slab_dimension": "8"}]
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as error:
            pytest.skip(f"Chromium indisponível: {error}")
        page = browser.new_page()
        page.set_content('<div id="pillar-n3-editor"></div>')
        page.add_script_tag(path=str(ROOT / "portal/app/static/pillar_ficha.js"))
        page.evaluate("fixture => { window.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve({ficha:fixture})}); window.app=PillarFicha.mount(document.querySelector('#pillar-n3-editor'),{obraId:'x',classe:'pilares',itemId:'P10',initialTab:'abcd-para'}); }", data)
        page.wait_for_selector('.plf-svg-opening')
        assert page.locator('g[data-face="B"] .plf-svg-opening').count() == 2
        assert 'V410' in page.locator('.plf-opening-row').all_inner_texts()[-1]
        assert page.locator('g[data-face="B"] .plf-svg-slab').count() == 0
        assert 'L410' in page.locator('.plf-slab-row').all_inner_texts()[0]
        page.evaluate("() => { app.data.faces.B.openings.right[1].depth=60; app.render(); }")
        assert page.locator('g[data-face="B"] .plf-svg-opening').count() == 3
        page.evaluate("() => { app.data.faces.B.slabs[0].height=60; app.render(); }")
        assert page.locator('g[data-face="B"] .plf-svg-slab').count() == 1
        browser.close()
