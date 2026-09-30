"""A ficha lateral mantém a interpretação junto da subaba ativa do viewer."""

from pathlib import Path

import pytest


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def _segment(index: int, side: str) -> dict:
    return {
        "id": f"{side}-{index}", "index": index, "length_cm": 100 + index,
        "width_cm": 19, "beam_height_cm": 55, "level": 855.25,
        "level_source": "sa_beam_segment", "slabs": [], "beam_openings": [],
        "beam_openings_status": "verified", "pillar_openings": [],
        "layers": {"sa": {"available": True, "svg": '<svg viewBox="0 0 10 10"></svg>'},
                   "c1": {"available": False}, "c2": {"available": False},
                   "c3": {"available": False}, "n3_panels": {"available": False}},
    }


def test_lv_interpretacao_acompanha_subaba_e_fica_no_mesmo_box_do_viewer():
    sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as error:
            pytest.skip(f"Chromium indisponível: {error}")
        page = browser.new_page()
        page.set_content('<div id="lv-ficha-root"></div>')
        page.add_style_tag(path=str(STATIC / "fv_ficha.css"))
        payload = {
            "schema": "cad.portal.lv_ficha/v1",
            "beam": {"name": "V401", "behavior": "passa",
                     "behavior_label": "Segmentos passam pelos pilares",
                     "position": 1, "total_beams": 1, "previous": None, "next": None},
            "sides": {"A": {"class": "lateral_a_passa", "segments": [_segment(1, "A"), _segment(2, "A")]},
                      "B": {"class": "lateral_b_passa", "segments": [_segment(1, "B")]}},
            "cut_views": [
                {"own_slab": "L1", "layers": {"sa": {"available": True, "svg": '<svg viewBox="0 0 10 10"><text>SA VC1</text></svg>'}, "n3_cut": {"available": True, "svg": '<svg viewBox="0 0 10 10"></svg>'}}},
                {"own_slab": "L2", "layers": {"sa": {"available": True, "svg": '<svg viewBox="0 0 10 10"><text>SA VC2</text></svg>'}, "n3_cut": {"available": True, "svg": '<svg viewBox="0 0 10 10"></svg>'}}},
            ],
        }
        page.evaluate("""window.fetch = async url => ({ok:true, json:async () =>
          String(url).includes('/camada/')
            ? {available:true, svg:'<svg viewBox="0 0 10 10"></svg>'}
            : window.lvPayload})""")
        page.evaluate("payload => window.lvPayload = payload", payload)
        page.add_script_tag(path=str(STATIC / "lv_ficha.js"))
        page.evaluate("window.LvFicha.mount(document.getElementById('lv-ficha-root'), "
                      "{obraId:'obra',behavior:'passa',beam:'V401',initialSegment:1})")

        card = page.locator(".lv-web-ficha > .fv-web-viewer-card")
        assert card.locator(".lv-side-tabs").count() == 1
        assert card.locator(".lv-behavior-tag").count() == 0
        assert page.locator(".lv-name-line .lv-behavior-tag strong").inner_text() == "passam"
        assert card.locator(".fv-web-seg-row").count() == 1
        assert card.locator(".lv-cut-card").count() == 0
        assert card.locator(".lv-interpretation-card .fv-web-section-title").count() == 0
        assert card.locator(".lv-interpretation-card").get_attribute("aria-label") == "Interpretação dos segmentos · Lado A"
        assert card.evaluate("el => [...el.children].map(child => child.className)")[:4] == [
            "lv-side-tabs fv-web-layerbar", "fv-web-layerbar", "fv-web-segtabs", "fv-web-table-card lv-interpretation-card",
        ]

        card.locator('[data-lv-segment-tab="todos"]').click()
        assert page.locator(".lv-web-ficha .fv-web-seg-row").count() == 2
        page.locator('[data-lv-segment-tab="2"]').click()
        assert page.locator(".lv-web-ficha .fv-web-seg-row").count() == 1
        assert "S2" in page.locator(".lv-web-ficha .fv-web-seg-row").inner_text()

        assert page.locator('[data-lv-layer="n3_cut"]').count() == 0
        page.locator('[data-lv-view="cut"]').click()
        assert page.locator('[data-lv-layer="sa_cut"]').get_attribute('class').endswith('active')
        assert page.locator('.fv-web-canvas text').text_content() == 'SA VC1'
        assert page.locator('[data-lv-layer="n3_panels"]').count() == 0
        assert page.locator('[data-lv-layer="c1"]').is_disabled()
        assert page.locator('[data-lv-validate]').count() == 0
        page.locator('[data-lv-layer="n3_cut"]').click()
        assert page.locator(".lv-cut-card .lv-cut-row").count() == 1
        assert card.locator(".lv-cut-card .fv-web-section-title").count() == 0
        assert page.locator(".lv-web-ficha .fv-web-seg-row").count() == 0
        page.locator('[data-lv-cut-tab="todos"]').click()
        assert page.locator(".lv-cut-card .lv-cut-row").count() == 2
        page.locator('[data-lv-cut-tab="1"]').click()
        assert page.locator(".lv-cut-card .lv-cut-row").count() == 1
        assert "VC2" in page.locator(".lv-cut-card .lv-cut-row").inner_text()
        page.locator('[data-lv-side="B"]').click()
        assert page.locator('[data-lv-layer="n3_cut"]').count() == 0
        assert page.locator('.lv-interpretation-card').get_attribute('aria-label').endswith('Lado B')
        browser.close()
