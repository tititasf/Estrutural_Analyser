"""Unit tests for GlobalBeamChannelExtractor."""

from src.core.beam_interpreters.global_channel_extractor import (
    BeamChannelSlot,
    GlobalBeamChannelExtractor,
    GlobalBeamChannelMesh,
)


def test_global_channel_extractor_finds_horizontal_and_vertical_slots():
    extractor = GlobalBeamChannelExtractor()

    # Define a pair of horizontal parallel lines (width = 19.0cm)
    h_line1 = [(100.0, 500.0), (400.0, 500.0)]
    h_line2 = [(100.0, 519.0), (400.0, 519.0)]

    # Define a pair of vertical parallel lines (width = 20.0cm)
    v_line1 = [(1000.0, 200.0), (1000.0, 600.0)]
    v_line2 = [(1020.0, 200.0), (1020.0, 600.0)]

    raw_lines = [h_line1, h_line2, v_line1, v_line2]
    mesh = extractor.extract_channel_mesh(raw_lines)

    assert isinstance(mesh, GlobalBeamChannelMesh)
    assert len(mesh.slots) >= 2

    # Check horizontal slot matching
    h_slot = mesh.find_best_matching_slot(
        beam_pos=(250.0, 510.0),
        span_coords=(100.0, 400.0),
        is_horizontal=True,
        expected_width=19.0,
    )
    assert h_slot is not None
    assert h_slot.is_horizontal is True
    assert abs(h_slot.width - 19.0) < 0.1
    assert abs(h_slot.transverse_pos - 509.5) < 0.1

    # Check vertical slot matching
    v_slot = mesh.find_best_matching_slot(
        beam_pos=(1010.0, 400.0),
        span_coords=(200.0, 600.0),
        is_horizontal=False,
        expected_width=20.0,
    )
    assert v_slot is not None
    assert v_slot.is_horizontal is False
    assert abs(v_slot.width - 20.0) < 0.1
    assert abs(v_slot.transverse_pos - 1010.0) < 0.1


def test_empty_raw_lines_returns_empty_mesh():
    extractor = GlobalBeamChannelExtractor()
    mesh = extractor.extract_channel_mesh([])
    assert isinstance(mesh, GlobalBeamChannelMesh)
    assert len(mesh.slots) == 0
    assert mesh.find_best_matching_slot((0, 0), (0, 100), True) is None
