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
