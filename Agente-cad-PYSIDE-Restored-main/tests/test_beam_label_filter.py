from src.core.beam_tracer import BeamTracer
from src.core.spatial_index import SpatialIndex


def test_cut_call_is_not_a_beam_label(monkeypatch):
    tracer = BeamTracer(SpatialIndex())
    def should_not_trace(*args, **kwargs):
        raise AssertionError('A section call was interpreted as a beam')
    monkeypatch.setattr(tracer, '_determine_orientation', should_not_trace)
    assert tracer.detect_beams([{'text': 'VER CORTE 1-1', 'pos': (0, 0)}], []) == []
