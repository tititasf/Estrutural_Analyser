"""Regressoes visuais do destaque sobre o estrutural limpo."""

from pathlib import Path


TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_todas_as_classes_reutilizam_o_azul_dos_pilares():
    """A pagina integrada e o viewer dedicado nao podem divergir por classe."""
    for template in ("obra_detalhe.html", "viewer.html"):
        html = (TEMPLATES / template).read_text(encoding="utf-8")
        assert 'COR_DESTAQUE_ESTRUTURAL = ' in html
        assert '#4ea1ff' in html
        for grupo in (
            "pilares", "lat_a_para", "lat_a_passa", "lat_b_para",
            "lat_b_passa", "laterais", "fundos", "lajes",
        ):
            assert f"{grupo}: COR_DESTAQUE_ESTRUTURAL" in html


def test_cores_antigas_de_classe_nao_permanecem_nos_viewers():
    antigas = ("#ffd166", "#f4a261", "#e9c46a", "#e76f51", "#06d6a0", "#c77dff")
    for template in ("obra_detalhe.html", "viewer.html"):
        html = (TEMPLATES / template).read_text(encoding="utf-8")
        assert not any(cor in html for cor in antigas)


def test_linha_azul_tem_espessura_dobrada_e_erro_preserva_sua_espessura():
    for template in ("obra_detalhe.html", "viewer.html"):
        html = (TEMPLATES / template).read_text(encoding="utf-8")
        assert "fora_do_frame ? '4.6' : '6'" in html or 'fora_do_frame ? "4.6" : "6"' in html
