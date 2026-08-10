import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gerar_lj_dxf_stog.py"
SPEC = importlib.util.spec_from_file_location("gerar_lj_dxf_stog", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_rejects_obstacle_whose_center_is_outside_slab_polygon():
    polygon = [(0.0, 49.0), (100.0, 49.0), (100.0, 100.0), (0.0, 100.0)]
    obstacle = {"x": 10.0, "y": 10.0, "width": 20.0, "height": 19.0}

    assert not MODULE._obstacle_is_inside_polygon(obstacle, polygon, 0.0, 0.0)


def test_keeps_obstacle_whose_center_is_inside_slab_polygon():
    polygon = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    obstacle = {"x": 10.0, "y": 10.0, "width": 20.0, "height": 19.0}

    assert MODULE._obstacle_is_inside_polygon(obstacle, polygon, 0.0, 0.0)


def test_short_vertical_segments_use_internal_center_guide(monkeypatch):
    """Faixa baixa: cotas verticais no eixo central (junta), não à esquerda externa."""
    calls = []
    monkeypatch.setattr(MODULE, "add_dim_on_paineis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        MODULE,
        "add_dim_vertical_on_paineis",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    # x0=100, guide_x=117 (mais perto do centro de 234) → vertical_panel_x=217
    MODULE._add_reference_dimensions(
        object(), 100.0, 200.0, 234.0, 71.0, [117.0], [35.5], []
    )

    assert len(calls) == 2
    expected_ext = 100.0 + 117.0  # x0 + guide_x (centro)
    expected_dim = expected_ext - MODULE.DIM_VERTICAL_OFFSET_CM
    assert all(abs(call[0][3] - expected_dim) < 1e-6 for call in calls)
    assert all(abs(call[0][4] - expected_ext) < 1e-6 for call in calls)
    # textos no mesmo eixo interno (não espalhados para fora)
    assert abs(calls[0][1]["text_location"][0] - expected_dim) < 1e-6
    assert abs(calls[1][1]["text_location"][0] - expected_dim) < 1e-6


def test_regular_vertical_segments_keep_internal_dimension_chain(monkeypatch):
    calls = []
    monkeypatch.setattr(MODULE, "add_dim_on_paineis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        MODULE,
        "add_dim_vertical_on_paineis",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    MODULE._add_reference_dimensions(
        object(), 100.0, 200.0, 406.0, 613.0, [122.0, 264.0], [179.0, 331.0], []
    )

    assert calls
    assert all(call[0][3] > 100.0 for call in calls)


def test_complex_projection_dedupes_redundant_step_vertices(monkeypatch):
    """L419 (14_PAV): degrau de borda de 2,5cm em CADA ponta (esquerda e
    direita) — cada ponta legitimamente precisa da sua própria cota 17/19,
    então o total correto é 2 de cada (1 por ponta), não 1.

    O bug real: na ponta ESQUERDA, os dois vértices adjacentes da mesma aresta
    curta do degrau — (0,52) e (2.5,52) — disparam, cada um por conta própria,
    uma regra diferente que mede a MESMA altura, então antes do fix a ponta
    esquerda sozinha já desenhava 17 e 19 duas vezes cada (quase na mesma
    posição, texto sobreposto/ilegível). A ponta direita (vértice (415.5,52))
    nunca teve esse problema — dispara só uma vez. Total pré-fix: 3 de cada
    (2 esquerda + 1 direita). Total pós-fix esperado: 2 de cada (1 esquerda
    consolidada, escolhendo o vértice sobre a parede real x=0, + 1 direita)."""
    calls = []
    monkeypatch.setattr(MODULE, "add_dim_on_paineis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        MODULE, "add_dim_vertical_on_paineis",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    poly_pts = [
        (2.5, 0.0), (415.5, 0.0), (415.5, 52.0), (418.0, 52.0),
        (418.0, 71.0), (0.0, 71.0), (0.0, 52.0), (2.5, 52.0),
    ]
    comp, larg = 418.0, 71.0
    v_positions, h_positions = [], [35.0]

    MODULE._add_cut_edge_dimensions(
        object(), poly_pts, 0.0, 0.0, comp, larg, v_positions, h_positions
    )

    values = [
        float(kwargs["text_override"]) for _, kwargs in calls
        if kwargs.get("text_override") is not None
    ]
    assert values.count(17.0) == 2, f"esperado 2 cotas de 17 (1 por ponta), veio {values.count(17.0)}"
    assert values.count(19.0) == 2, f"esperado 2 cotas de 19 (1 por ponta), veio {values.count(19.0)}"

    # A cota "17" sobrevivente da ponta esquerda tem que estar ancorada na
    # parede real (x=0), não no canto interno redundante (x=2.5) — é isso
    # que _pick_canonical_dim_candidate garante.
    left_anchor_candidates = [
        args[3] for args, kwargs in calls
        if kwargs.get("text_override") == "17" and args[3] < 100.0
    ]
    assert left_anchor_candidates, "nenhuma cota 17 do lado esquerdo encontrada"
    # base_x = anchor + offset; para o vértice canônico (x=0, offset=27, cota
    # por dentro da laje — decisão do dono 24/07) -> base_x=27.
    # Para o vértice redundante (x=2.5, offset=10) -> base_x=12.5. Só o primeiro deve sobrar.
    assert 27.0 in left_anchor_candidates
    assert 12.5 not in left_anchor_candidates


def test_consolidate_dim_candidates_merges_close_anchors_same_span():
    """Dois candidatos com a mesma medida (span) e anchors próximos (menos que
    DIM_CANDIDATE_CLUSTER_TOL_CM) são a mesma feição física -> mantém só 1,
    escolhendo o anchor mais próximo de uma linha de grade real."""
    close = MODULE._DimCandidate(
        axis="v", span_raw=(35.0, 52.0), span_key=(35.0, 52.0),
        anchor=0.0, offset=-22.0, text_override="17", text_location=None,
        source="a",
    )
    redundant = MODULE._DimCandidate(
        axis="v", span_raw=(35.0, 52.0), span_key=(35.0, 52.0),
        anchor=2.5, offset=10.0, text_override="17", text_location=None,
        source="b",
    )
    winners = MODULE._consolidate_dim_candidates([close, redundant], [0.0, 418.0], [0.0, 35.0, 71.0])
    assert len(winners) == 1
    # anchor=0.0 esta em cima da grade (x=0.0); anchor=2.5 esta a 2.5cm dela.
    assert winners[0].anchor == 0.0


def test_consolidate_dim_candidates_keeps_distant_anchors_same_span():
    """Mesma medida (span), mas anchors distantes (feição espelhada do outro
    lado da laje) -> são feições distintas, as duas devem ser mantidas."""
    left = MODULE._DimCandidate(
        axis="v", span_raw=(35.0, 52.0), span_key=(35.0, 52.0),
        anchor=0.0, offset=-22.0, text_override="17", text_location=None,
        source="left",
    )
    right = MODULE._DimCandidate(
        axis="v", span_raw=(35.0, 52.0), span_key=(35.0, 52.0),
        anchor=415.5, offset=-10.0, text_override="17", text_location=None,
        source="right",
    )
    winners = MODULE._consolidate_dim_candidates([left, right], [0.0, 418.0], [0.0, 35.0, 71.0])
    assert len(winners) == 2
    assert {w.anchor for w in winners} == {0.0, 415.5}
