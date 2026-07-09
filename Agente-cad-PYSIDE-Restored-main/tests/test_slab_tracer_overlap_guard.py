from src.core.slab_tracer import SlabTracer
from src.core.spatial_index import SpatialIndex


def _slab(id_, name, points, method="motor_geom"):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    return {
        "id": id_,
        "name": name,
        "points": points,
        "area": area,
        "method": method,
        "trace_diagnostics": {},
    }


def _insert_line(si, start, end, layer="VIGA"):
    item = {"start": start, "end": end, "layer": layer, "type": "LINE"}
    si.insert(
        item,
        (
            min(start[0], end[0]),
            min(start[1], end[1]),
            max(start[0], end[0]),
            max(start[1], end[1]),
        ),
    )


def _insert_text(si, text, pos, rotation=0.0, layer="COTA"):
    si.insert(
        {
            "text": text,
            "pos": pos,
            "rotation": rotation,
            "layer": layer,
            "type": "TEXT",
        },
        (pos[0] - 1, pos[1] - 1, pos[0] + 1, pos[1] + 1),
    )


def _long_strip_fixture(include_full_height_dimension=True):
    si = SpatialIndex()
    # Faixa originalmente detectada: 2471,5 x 152.
    slab = _slab(
        "temp_0",
        "L318",
        [(0, 49), (2471.5, 49), (2471.5, 201), (0, 201), (0, 49)],
        method="n2_axes",
    )
    # Eixo de degrau junto ao fim atual.
    _insert_line(si, (2413, 0), (2413, 201))
    # Eixo longo de uma fileira vizinha: span suficiente, overlap zero.
    _insert_line(si, (2831, 220), (2831, 500))
    # Cota interna que atravessa a faixa, mas não termina a borda superior.
    _insert_line(si, (3046, 0), (3046, 400), layer="COTA")
    # Borda estrutural correta e borda superior que termina nela.
    _insert_line(si, (3139, 0), (3139, 201))
    _insert_line(si, (-100, 201), (3139, 201))
    _insert_line(si, (2413, 0), (3139, 0))
    if include_full_height_dimension:
        _insert_text(si, "201", (2800, 100), rotation=90.0)
    tracer = SlabTracer(si)
    tracer._laj_label_centroids = {"L318": (1200, 120)}
    return tracer, slab


def test_long_strip_uses_axis_crossing_own_band_and_full_height_dimension():
    tracer, slab = _long_strip_fixture(include_full_height_dimension=True)

    tracer._expand_long_strip_right_step([slab])

    assert slab["points"] == [
        (0.0, 0.0),
        (3139.0, 0.0),
        (3139.0, 201.0),
        (0.0, 201.0),
        (0.0, 0.0),
    ]
    assert slab["area"] == 630939.0
    assert slab["trace_diagnostics"]["right_axis_band_validated"] is True
    assert slab["trace_diagnostics"]["right_step_full_height_dimension"] is True


def test_long_strip_keeps_step_without_explicit_full_height_dimension():
    tracer, slab = _long_strip_fixture(include_full_height_dimension=False)

    tracer._expand_long_strip_right_step([slab])

    assert slab["points"] == [
        (0.0, 49.0),
        (2413.0, 49.0),
        (2413.0, 0.0),
        (3139.0, 0.0),
        (3139.0, 201.0),
        (0.0, 201.0),
        (0.0, 49.0),
    ]
    assert slab["trace_diagnostics"]["right_step_full_height_dimension"] is False


def test_reverts_expanded_slab_that_overlaps_untouched_neighbor():
    """Reproduz o bug real (L318): uma passagem de normalizacao de fileira
    expande uma laje ate ela invadir a area de uma vizinha ja correta.
    A laje TOCADA deve ser revertida ao contorno original; a vizinha,
    que nunca foi modificada, deve permanecer intacta."""
    tracer = SlabTracer(SpatialIndex())

    original_points = [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)]
    neighbor_points = [(150, 0), (250, 0), (250, 80), (150, 80), (150, 0)]

    slabs = [
        # Expandida por uma passagem de normalizacao: agora invade a vizinha.
        _slab(
            "temp_0", "L318",
            [(0, 0), (200, 0), (200, 80), (0, 80), (0, 0)],
            method="motor_geom_right_step",
        ),
        # Nunca tocada pelas passagens de normalizacao.
        _slab("temp_1", "L319", neighbor_points),
    ]
    originals = {
        "temp_0": (original_points, 8000.0, "motor_geom"),
        "temp_1": (neighbor_points, 8000.0, "motor_geom"),
    }

    tracer._reject_overlapping_row_expansions(slabs, originals)

    l318 = next(s for s in slabs if s["name"] == "L318")
    l319 = next(s for s in slabs if s["name"] == "L319")

    assert l318["points"] == original_points
    assert l318["area"] == 8000.0
    assert l318["method"] == "motor_geom"
    assert l318["trace_diagnostics"].get("row_expansion_reverted_overlap") is True

    # A vizinha nunca modificada nao deve ser tocada.
    assert l319["points"] == neighbor_points
    assert "row_expansion_reverted_overlap" not in l319["trace_diagnostics"]


def test_keeps_rectangular_expansion_with_independent_structural_evidence():
    tracer = SlabTracer(SpatialIndex())
    original_points = [(0, 49), (100, 49), (100, 80), (0, 80), (0, 49)]
    expanded_points = [(0, 0), (200, 0), (200, 80), (0, 80), (0, 0)]
    neighbor_points = [(150, 0), (250, 0), (250, 80), (150, 80), (150, 0)]
    expanded = _slab(
        "temp_0", "L318", expanded_points, method="n2_axes_right_step"
    )
    expanded["trace_diagnostics"] = {
        "right_axis_band_validated": True,
        "right_step_full_height_dimension": True,
    }
    slabs = [expanded, _slab("temp_1", "L319", neighbor_points)]
    originals = {
        "temp_0": (original_points, 3100.0, "n2_axes"),
        "temp_1": (neighbor_points, 8000.0, "motor_geom"),
    }

    tracer._reject_overlapping_row_expansions(slabs, originals)

    assert expanded["points"] == expanded_points
    assert expanded["trace_diagnostics"][
        "row_expansion_overlap_accepted_structural_evidence"
    ] is True
    assert "row_expansion_reverted_overlap" not in expanded["trace_diagnostics"]


def test_keeps_neighbor_expansion_for_small_overlap_with_strong_outline():
    tracer = SlabTracer(SpatialIndex())
    strong = _slab(
        "temp_0",
        "L318",
        [(0, 0), (200, 0), (200, 100), (0, 100), (0, 0)],
        method="n2_axes_right_step",
    )
    strong["trace_diagnostics"] = {
        "right_axis_band_validated": True,
        "right_step_full_height_dimension": True,
    }
    neighbor_original = [
        (190, 0), (290, 0), (290, 80), (190, 80), (190, 0)
    ]
    neighbor_expanded = _slab(
        "temp_1",
        "L319",
        [(192, 0), (392, 0), (392, 100), (192, 100), (192, 0)],
        method="n2_axes_left_chamfer_ext",
    )
    slabs = [strong, neighbor_expanded]
    originals = {
        "temp_0": (
            [(0, 20), (150, 20), (150, 100), (0, 100), (0, 20)],
            12000.0,
            "n2_axes",
        ),
        "temp_1": (neighbor_original, 8000.0, "n2_axes"),
    }

    tracer._reject_overlapping_row_expansions(slabs, originals)

    assert neighbor_expanded["method"] == "n2_axes_left_chamfer_ext"
    assert "row_expansion_reverted_overlap" not in neighbor_expanded[
        "trace_diagnostics"
    ]


def test_keeps_expansion_when_no_overlap_occurs():
    """Expansao legitima (sem invadir ninguem) nao deve ser revertida."""
    tracer = SlabTracer(SpatialIndex())

    original_points = [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)]
    expanded_points = [(0, 0), (140, 0), (140, 80), (0, 80), (0, 0)]
    neighbor_points = [(300, 0), (400, 0), (400, 80), (300, 80), (300, 0)]

    slabs = [
        _slab("temp_0", "L100", expanded_points, method="motor_geom_medium_row"),
        _slab("temp_1", "L101", neighbor_points),
    ]
    originals = {
        "temp_0": (original_points, 8000.0, "motor_geom"),
        "temp_1": (neighbor_points, 8000.0, "motor_geom"),
    }

    tracer._reject_overlapping_row_expansions(slabs, originals)

    l100 = next(s for s in slabs if s["name"] == "L100")
    assert l100["points"] == expanded_points
    assert "row_expansion_reverted_overlap" not in l100["trace_diagnostics"]


def test_does_not_touch_slabs_never_modified_by_normalization_passes():
    """Se nenhuma laje foi modificada pelas passagens (todas identicas ao
    original), a funcao nao deve alterar nada -- mesmo que, por algum
    motivo externo, duas lajes originais já se sobrepusessem (não é
    responsabilidade desta guarda re-litigar geometria que ela não
    produziu)."""
    tracer = SlabTracer(SpatialIndex())
    pts_a = [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)]
    pts_b = [(50, 0), (150, 0), (150, 80), (50, 80), (50, 0)]

    slabs = [
        _slab("temp_0", "L1", pts_a),
        _slab("temp_1", "L2", pts_b),
    ]
    originals = {
        "temp_0": (pts_a, 8000.0, "motor_geom"),
        "temp_1": (pts_b, 8000.0, "motor_geom"),
    }

    tracer._reject_overlapping_row_expansions(slabs, originals)

    assert slabs[0]["points"] == pts_a
    assert slabs[1]["points"] == pts_b
