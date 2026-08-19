from pathlib import Path

from scripts.arete.refresh_pil_qa_runtime import refresh_html


def test_refresh_runtime_replaces_stale_script_without_touching_page_content(tmp_path: Path):
    path = tmp_path / "P18.html"
    path.write_text(
        '<html><head><script id="pil-qa-notes">OLD</script></head>'
        '<body><div id="human-note">preservar</div></body></html>',
        encoding="utf-8",
    )

    assert refresh_html(path) == "updated"
    html = path.read_text(encoding="utf-8")
    assert "OLD" not in html
    assert html.count('id="pil-qa-notes"') == 1
    assert "function _namespacePilSvg(svg, layerEl)" in html
    assert "function _auditPilSvgNamespaces()" in html
    assert '<div id="human-note">preservar</div>' in html


def test_refresh_runtime_is_idempotent(tmp_path: Path):
    path = tmp_path / "P9.html"
    path.write_text("<html><head></head><body>nota</body></html>", encoding="utf-8")

    assert refresh_html(path) == "inserted"
    assert refresh_html(path) == "unchanged"
