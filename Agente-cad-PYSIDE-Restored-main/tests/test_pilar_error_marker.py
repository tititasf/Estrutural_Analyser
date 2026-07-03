"""Testa o checkbox de erro + flag de sidebar da ficha granular de pilar.

`_write_pilar_pages` (o gerador da página inteira) é uma função aninhada
dentro de `_export_html_snapshot`, um método enorme que monta praticamente
todo o snapshot HTML da app — não é isolável num teste sem mockar dezenas
de atributos do dialog (`self._pilares`, `self._dxf_data`, `self._db_path`,
etc.), diferente de LAJ/FV/LV, que têm gerador próprio em módulo separado
(`preficha_laje_html.py`/`preficha_fundo_html.py`/`preficha_lateral_html.py`,
cada um com seu `test_preficha_*_html.py`). Por isso este teste cobre
diretamente as duas funções puras e independentes que compõem o checkbox
de PIL — mesma cobertura de comportamento que os testes das outras 3
classes dão para suas respectivas `_error_marker_block`/
`_sidebar_error_flags_script`, só que sem precisar montar a página inteira.
"""

from bs4 import BeautifulSoup

from src.ui.widgets.pre_validation_dialog import (
    _error_marker_block_pil,
    _sidebar_error_flags_script_pil,
)


class _FakeDialog:
    _obra = "Obra_TESTE"
    _pavimento = "13_PAV"


def test_error_marker_block_pil_has_checkbox_textarea_and_correct_key():
    html = _error_marker_block_pil(_FakeDialog(), "P1")
    soup = BeautifulSoup(html, "html.parser")

    checkbox = soup.select_one("#erro_check")
    textarea = soup.select_one("#erro_nota")
    assert checkbox is not None and checkbox.get("type") == "checkbox"
    assert textarea is not None
    assert "Marcar esta ficha como ERRADA" in soup.get_text()

    # Mesma convenção de chave de LAJ/FV/LV: aten_erro_{classe}_{obra}_{pav}_{nome}
    assert "aten_erro_pil_Obra_TESTE_13_PAV_P1" in html


def test_error_marker_block_pil_key_replaces_spaces_with_underscore():
    class _DialogWithSpaces:
        _obra = "Obra Com Espaco"
        _pavimento = "13 PAV"

    html = _error_marker_block_pil(_DialogWithSpaces(), "P 1")
    assert "aten_erro_pil_Obra_Com_Espaco_13_PAV_P_1" in html
    assert " " not in html.split("var key=")[1].split(";")[0]


def test_sidebar_error_flags_script_pil_targets_data_pilar_and_prefix():
    script = _sidebar_error_flags_script_pil(_FakeDialog())

    assert ".sidebar li[data-pilar]" in script
    assert "aten_erro_pil_" in script
    assert '"Obra_TESTE"' in script
    assert '"13_PAV"' in script
    assert ".erro-flag" in script
