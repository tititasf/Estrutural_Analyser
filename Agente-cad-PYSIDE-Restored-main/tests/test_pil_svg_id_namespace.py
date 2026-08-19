from src.core.pil_qa_notes_chrome import js_pil_qa


def test_pil_layers_namespace_inline_svg_ids_before_rendering():
    script = js_pil_qa()

    assert "function _namespacePilSvg(svg, layerEl)" in script
    assert "data-pil-ids-namespaced" in script
    assert "changed.replace(/#([A-Za-z0-9_.:-]+)/g" in script
    assert "_namespacePilSvg(s,layerEl); _prepPilSvg(s)" in script
    assert "function _auditPilSvgNamespaces()" in script
    assert "window.auditPilSvgNamespaces=_auditPilSvgNamespaces" in script
    assert "document.body.dataset.pilSvgIdsOk=ok?'1':'0'" in script
    assert "_namespacePilSvg(s, s.closest('.pil-layer'))" in script


def test_pil_svg_namespace_protocol_checks_duplicate_ids_and_unresolved_glyphs():
    script = js_pil_qa()

    assert "if(seen[id]) duplicates.push(id)" in script
    assert "svg.querySelectorAll('use')" in script
    assert "!local[href.slice(1)]" in script
    assert "PIL SVG namespace inválido" in script
