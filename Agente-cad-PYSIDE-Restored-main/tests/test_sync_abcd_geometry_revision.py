from pathlib import Path

from scripts.arete.pil_agentic_highlight_draw import _agentic_context_margin
from scripts.arete.sync_abcd_dxf_geometry_revision import (
    _replace_sa_tables,
    _tables_from_n1,
)


def test_agentic_margin_keeps_19x98_in_local_context():
    assert _agentic_context_margin(19.0, 98.0) == 460.2


def test_headless_abcd_tables_are_parsed_and_replace_only_sa(tmp_path: Path):
    headless = tmp_path / "P12.html"
    headless.write_text(
        """
        <div class="abcd-face-card"><div class="abcd-face-title">A — esquerda · face longa</div>
        <table class="abcd-mini"><tr><th>Família</th></tr>
        <tr><td>Lajes</td><td>L310</td><td>12</td><td>⚠</td><td>AA</td><td>—</td><td>—</td></tr>
        <tr><td>Passam</td><td>V314</td><td>19/120</td><td>852.19cm</td><td>AC</td><td>—</td><td>—</td></tr>
        </table></div>
        """,
        encoding="utf-8",
    )
    tables = _tables_from_n1(headless)
    assert tables["orientation"] == "vertical"
    assert tables["faces"]["A"]["passa"][0]["dim"] == "19/120"

    source = (
        '<div class="sec" data-ficha-panel="interp"><div class="sec-title">'
        'Interpretação ABCD — SA (atual motor)</div><div>19/50</div></div>'
        '<div class="sec" data-ficha-panel="interp"><div class="sec-title">'
        'Interpretação ABCD — proposta L1 (corrigida)</div><div>HISTORICO</div></div>'
    )
    updated = _replace_sa_tables(source, "P12", tables)
    assert "19/120" in updated
    assert "19/50" not in updated
    assert "HISTORICO" in updated
