import copy
import importlib.util
from pathlib import Path


def _load_headless():
    path = Path(__file__).parents[1] / "scripts" / "arete" / "headless_sa_analise.py"
    spec = importlib.util.spec_from_file_location("headless_geometry_cache_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cached_context_geometry_diff_is_materialized_without_transient_marker():
    module = _load_headless()
    report = {
        "P12": {
            "name": "P12",
            "points": [[0, 0], [19, 0], [19, 98], [0, 98], [0, 0]],
            "bbox": [0, 0, 19, 98],
        }
    }
    stale = [{
        "name": "P12",
        "points": [[0, 0], [19, 0], [19, 26], [0, 26]],
        "validated_fields": {"pilar_segs": [{"origem": "qa_agente"}]},
    }]

    assert module._refresh_recovered_pillar_geometry(stale, copy.deepcopy(report)) == 1
    xs = [point[0] for point in stale[0]["points"]]
    ys = [point[1] for point in stale[0]["points"]]
    assert max(xs) - min(xs) == 19
    assert max(ys) - min(ys) == 98
    assert (min(ys) + max(ys)) / 2 == 13  # centro do fragmento original
    assert stale[0]["_geometry_repaired"]["method"] == "same_name_dimensions_at_original_centroid"


def test_cached_context_never_overwrites_human_geometry():
    module = _load_headless()
    report = {"P1": {"name": "P1", "points": [[0, 0], [19, 0], [19, 98], [0, 98]]}}
    human = [{
        "name": "P1",
        "points": [[0, 0], [19, 0], [19, 26], [0, 26]],
        "validated_fields": {"pilar_segs": [{"origem": "humano_portal"}]},
    }]

    assert module._refresh_recovered_pillar_geometry(human, report) == 0
    assert human[0]["points"][-1] == [0, 26]
