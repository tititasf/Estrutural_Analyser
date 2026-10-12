"""Contrato do redesenho: coordenadas da camada clicada e alvo exclusivo."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_drawing_uses_source_svg_home_extent():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node indisponível")
    source = (Path(__file__).resolve().parents[1] / "app/static/item_geometry.js").read_text(encoding="utf-8")
    function = source[source.index("  function pointsToDxf("):source.index("  function reload(")]
    script = "const assert=require('node:assert/strict');\n" + function + """
const bbox=[100,200,1300,744];
// Fundo: 864 x 391.68 pt. Overlay: 1200 x 544 px.
assert.deepEqual(pointsToDxf([{x:432,y:195.84}],bbox,[0,0,864,391.68]),[[700,472]]);
assert.deepEqual(pointsToDxf([{x:0,y:0},{x:864,y:391.68}],bbox,[0,0,864,391.68]),[[100,744],[1300,200]]);
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "drawingSvg.dataset.homeVb" in source
    assert "overlay.dataset.homeVb" not in source


def test_redraw_isolates_target_and_cancel_refreshes_overlay():
    source = (Path(__file__).resolve().parents[1] / "app/static/item_geometry.js").read_text(encoding="utf-8")
    template = (Path(__file__).resolve().parents[1] / "app/templates/obra_detalhe.html").read_text(encoding="utf-8")
    assert "item.classe_sa!==target.classe || item.item_id!==target.itemId" in source
    assert "window.ItemGeometry.hides(item)" in template
    assert "container._renderDestaques = desenhar" in template
    assert source.count("if(container._renderDestaques) container._renderDestaques();") == 2


def test_structural_save_refreshes_highlights_without_navigation():
    source = (Path(__file__).resolve().parents[1] / "app/static/item_geometry.js").read_text(encoding="utf-8")
    template = (Path(__file__).resolve().parents[1] / "app/templates/obra_detalhe.html").read_text(encoding="utf-8")
    handler = source.split("saveButton.addEventListener('click'", 1)[1].split("    },true);", 1)[0]
    assert 'reload(' not in handler
    assert 'container._refreshDestaques(savedTarget.classe)' in handler
    assert handler.index('persisted=true') < handler.index("progress(75,")
    assert handler.index('_refreshDestaques') < handler.index("progress(100,")
    assert 'clearInterval(waiting)' in handler
    assert 'desenho preservado' in handler
    assert 'st.itemId=selection.itemId' not in source
    refresh = template.split('container._refreshDestaques = function', 1)[1].split('        if (botoesEl) {', 1)[0]
    assert "cache: 'no-store'" in refresh
    assert 'aplicarPanZoomDual' not in refresh
    assert "setAttribute('viewBox'" not in refresh
