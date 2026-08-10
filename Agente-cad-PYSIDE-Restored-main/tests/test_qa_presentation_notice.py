from src.core.qa_presentation_notice import banner_html, inject_into_html


def test_inject_banner_after_body_once():
    html = "<!doctype html><html><body><h1>x</h1></body></html>"
    out = inject_into_html(html)
    assert "data-qa-presentation" in out
    assert out.count("data-qa-presentation") == 1
    assert inject_into_html(out).count("data-qa-presentation") == 1
    assert "Apresentação" in banner_html() or "prova" in banner_html()
