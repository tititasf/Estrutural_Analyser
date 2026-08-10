"""Transform pixel ↔ DXF do viewer de desenho (P1 do MASTERPLAN-CONSOLIDACAO-ENTREGA).

Sem transform correta o traço do usuário vira coordenada DXF errada e o recorte
manual pega as entidades erradas — falha silenciosa que aparece depois como
"o motor interpretou errado". Estes testes existem para essa falha não passar.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from portal.app.dxf_preview import (
    SvgComTransform,
    obter_bbox_dxf,
    renderizar_dxf_svg_com_transform,
    renderizar_dxf_svg_com_transform_cacheado,
)

# Transform sintética: 100x50 px cobrindo o retângulo DXF (10,20)-(110,70).
TRANSFORM = SvgComTransform(
    svg=b"<svg/>", bbox_dxf=(10.0, 20.0, 110.0, 70.0), largura_px=100, altura_px=50
)


def test_origem_do_svg_e_o_canto_superior_esquerdo():
    """Pixel (0,0) = topo-esquerda do SVG = (x0, y1) no DXF — Y invertido."""
    assert TRANSFORM.px_para_dxf(0, 0) == (10.0, 70.0)


def test_canto_inferior_direito():
    assert TRANSFORM.px_para_dxf(100, 50) == (110.0, 20.0)


def test_centro():
    assert TRANSFORM.px_para_dxf(50, 25) == (60.0, 45.0)


@pytest.mark.parametrize("px,py", [(0, 0), (100, 50), (37.5, 12.25), (99.9, 0.1)])
def test_round_trip_px_dxf_px(px, py):
    x, y = TRANSFORM.px_para_dxf(px, py)
    volta_x, volta_y = TRANSFORM.dxf_para_px(x, y)
    assert volta_x == pytest.approx(px, abs=1e-9)
    assert volta_y == pytest.approx(py, abs=1e-9)


def test_y_cresce_em_sentidos_opostos():
    """Descer no SVG tem de diminuir o Y do DXF. Inverter isto espelha o desenho."""
    _, y_topo = TRANSFORM.px_para_dxf(50, 0)
    _, y_baixo = TRANSFORM.px_para_dxf(50, 50)
    assert y_topo > y_baixo


def test_dimensao_zero_nao_divide_por_zero():
    degenerado = SvgComTransform(
        svg=b"", bbox_dxf=(5.0, 5.0, 5.0, 5.0), largura_px=0, altura_px=0
    )
    assert degenerado.px_para_dxf(0, 0) == (5.0, 5.0)
    assert degenerado.dxf_para_px(5.0, 5.0) == (0.0, 0.0)


def test_como_dict_e_serializavel():
    payload = json.loads(json.dumps(TRANSFORM.como_dict()))
    assert payload["bbox_dxf"] == [10.0, 20.0, 110.0, 70.0]
    assert payload["largura_px"] == 100
    assert payload["altura_px"] == 50


# ── Render real (precisa de ezdxf/matplotlib) ────────────────────────────────

def _dxf_minimo(destino: Path) -> Path:
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (100, 0), (100, 40), (0, 40)], close=True
    )
    caminho = destino / "retangulo.dxf"
    doc.saveas(str(caminho))
    return caminho


def test_bbox_devolvido_e_o_real_pos_draw_nao_o_pedido(tmp_path):
    """O backend CAD força aspect='equal' e o matplotlib expande um dos eixos.

    Usar o bbox PEDIDO desloca silenciosamente todo ponto no eixo expandido —
    este teste existe para garantir que devolvemos o bbox EFETIVO.
    """
    pytest.importorskip("matplotlib")
    dxf = _dxf_minimo(tmp_path)
    pedido = obter_bbox_dxf(dxf)
    assert pedido is not None

    # 400x400 px sobre um desenho 100x40 força expansão vertical.
    resultado = renderizar_dxf_svg_com_transform(
        dxf, bbox=pedido, largura_px=400, altura_px=400, margem_pct=0.0
    )
    altura_pedida = pedido[3] - pedido[1]
    altura_efetiva = resultado.bbox_dxf[3] - resultado.bbox_dxf[1]
    assert altura_efetiva > altura_pedida, "bbox devolvido não pode ser o pedido cru"


def test_geometria_conhecida_cai_dentro_do_frame(tmp_path):
    pytest.importorskip("matplotlib")
    dxf = _dxf_minimo(tmp_path)
    bbox = obter_bbox_dxf(dxf)
    r = renderizar_dxf_svg_com_transform(
        dxf, bbox=bbox, largura_px=400, altura_px=300, margem_pct=0.05
    )
    for x, y in [(0, 0), (100, 0), (100, 40), (0, 40)]:
        px, py = r.dxf_para_px(x, y)
        assert -1 <= px <= r.largura_px + 1
        assert -1 <= py <= r.altura_px + 1


def test_cache_preserva_a_transform(tmp_path):
    pytest.importorskip("matplotlib")
    dxf = _dxf_minimo(tmp_path)
    cache = tmp_path / "cache"
    primeiro = renderizar_dxf_svg_com_transform_cacheado(dxf, cache, largura_px=300, altura_px=200)
    segundo = renderizar_dxf_svg_com_transform_cacheado(dxf, cache, largura_px=300, altura_px=200)
    assert segundo.bbox_dxf == primeiro.bbox_dxf
    assert segundo.svg == primeiro.svg
    assert list(cache.glob("*.transform.json")), "transform tem de ser persistida"


def test_transform_corrompida_no_cache_re_renderiza(tmp_path):
    """Cache inválido nunca pode devolver SVG com transform errada."""
    pytest.importorskip("matplotlib")
    dxf = _dxf_minimo(tmp_path)
    cache = tmp_path / "cache"
    bom = renderizar_dxf_svg_com_transform_cacheado(dxf, cache, largura_px=300, altura_px=200)
    for meta in cache.glob("*.transform.json"):
        meta.write_text("{lixo", encoding="utf-8")
    recuperado = renderizar_dxf_svg_com_transform_cacheado(dxf, cache, largura_px=300, altura_px=200)
    assert recuperado.bbox_dxf == bom.bbox_dxf


# ── Preview completo: fonte única da aritmética de dimensão ──────────────────
# `manual_crop` convertia clique->DXF reproduzindo a fórmula de
# renderizar_dxf_completo_cacheado. Dava o mesmo número (conferido, erro zero),
# mas era invariante acoplado SEM TESTE: mudar alvo_px/margem/proporção de um
# lado deslocaria todo recorte manual sem erro nenhum. Estes testes seguram isso.

def test_dimensoes_preview_mantem_proporcao_do_desenho():
    from portal.app.dxf_preview import dimensoes_preview_completo

    # Desenho deitado 200x50 -> largura no alvo, altura proporcional
    assert dimensoes_preview_completo((0, 0, 200, 50), alvo_px=2400) == (2400, 600)
    # Desenho em pé 50x200 -> altura no alvo
    assert dimensoes_preview_completo((0, 0, 50, 200), alvo_px=2400) == (600, 2400)
    # Quadrado
    assert dimensoes_preview_completo((0, 0, 100, 100), alvo_px=1000) == (1000, 1000)


def test_dimensoes_preview_tem_piso_de_200px():
    """Desenho muito alongado não pode virar imagem de 2px de altura."""
    from portal.app.dxf_preview import dimensoes_preview_completo

    _, altura = dimensoes_preview_completo((0, 0, 10000, 1), alvo_px=2400)
    assert altura == 200


def test_transform_do_preview_bate_com_a_formula_manual(tmp_path):
    """Regressão do acoplamento: a transform do render TEM de reproduzir os
    limites que a fórmula manual calculava — senão o recorte manual desloca."""
    pytest.importorskip("matplotlib")
    from portal.app.dxf_preview import obter_bbox_dxf, transform_preview_completo

    dxf = _dxf_minimo(tmp_path)
    bbox = obter_bbox_dxf(dxf)
    assert bbox is not None
    transform = transform_preview_completo(dxf)
    assert transform is not None

    # Fórmula que `manual_crop` usava embutida, com margem_pct=0.03.
    x0, y0, x1, y1 = bbox
    margem_x = max((x1 - x0) * 0.03, 0.5)
    margem_y = max((y1 - y0) * 0.03, 0.5)
    esperado = (x0 - margem_x, y0 - margem_y, x1 + margem_x, y1 + margem_y)

    for obtido, alvo in zip(transform.bbox_dxf, esperado):
        assert obtido == pytest.approx(alvo, rel=1e-6)


def test_canto_do_preview_mapeia_para_o_canto_do_desenho(tmp_path):
    """Percentual de tela -> DXF, o caminho exato que manual_crop percorre."""
    pytest.importorskip("matplotlib")
    from portal.app.dxf_preview import transform_preview_completo

    dxf = _dxf_minimo(tmp_path)
    t = transform_preview_completo(dxf)
    assert t is not None

    topo_esq = t.px_para_dxf(0, 0)
    base_dir = t.px_para_dxf(t.largura_px, t.altura_px)
    assert topo_esq[0] == pytest.approx(t.bbox_dxf[0])
    assert topo_esq[1] == pytest.approx(t.bbox_dxf[3])
    assert base_dir[0] == pytest.approx(t.bbox_dxf[2])
    assert base_dir[1] == pytest.approx(t.bbox_dxf[1])


def test_foto_completa_ja_deixa_transform_pronta_para_recorte(tmp_path, monkeypatch):
    """Abrir a foto uma vez deve impedir um segundo render ao recortar."""
    pytest.importorskip("matplotlib")
    from portal.app import dxf_preview as dp

    dxf = _dxf_minimo(tmp_path)
    cache = tmp_path / "cache-completo"
    svg = dp.renderizar_dxf_completo_cacheado(dxf, cache, alvo_px=300)
    assert b"<svg" in svg[:2000]
    assert list(cache.glob("*.transform.json"))

    def _nao_pode_renderizar(*args, **kwargs):
        raise AssertionError("transform do recorte tentou renderizar a foto novamente")

    monkeypatch.setattr(dp, "renderizar_dxf_svg_com_transform", _nao_pode_renderizar)
    transform = dp.transform_preview_completo(dxf, cache_dir=cache, alvo_px=300)
    assert transform is not None
