"""Unit tests for ChannelConfidenceScorer."""

from src.core.beam_interpreters.channel_confidence_scorer import (
    ChannelConfidenceResult,
    ChannelConfidenceScorer,
)
from src.core.beam_interpreters.global_channel_extractor import (
    BeamChannelSlot,
    GlobalBeamChannelMesh,
)


def test_scorer_returns_unsupported_for_empty_mesh():
    scorer = ChannelConfidenceScorer()
    res = scorer.score_segment((100.0, 500.0, 400.0, 519.0), 19.0, True, GlobalBeamChannelMesh())
    assert isinstance(res, ChannelConfidenceResult)
    assert res.confidence_score == 0.0
    assert res.status_flag == "UNSUPPORTED"
    assert res.matched_slot_id is None


def test_scorer_high_confidence_match():
    slot = BeamChannelSlot(
        slot_id="slot_h_1",
        is_horizontal=True,
        width=19.0,
        axial_span=(100.0, 400.0),
        transverse_pos=509.5,
        bbox=(100.0, 500.0, 400.0, 519.0),
        dim_text="19/60",
        height=60.0,
    )
    mesh = GlobalBeamChannelMesh(slots=[slot])
    scorer = ChannelConfidenceScorer()

    res = scorer.score_segment((100.0, 500.0, 400.0, 519.0), 19.0, True, mesh)
    assert res.matched_slot_id == "slot_h_1"
    assert res.confidence_score >= 0.75
    assert res.status_flag == "HIGH_CONFIDENCE"
    assert res.dim_text_matched == "19/60"
    assert res.transverse_offset_cm == 0.0


def test_scorer_detects_width_and_offset_warnings():
    # Slot with width 14cm at transverse_pos 520 (offset 10.5cm from 509.5)
    slot = BeamChannelSlot(
        slot_id="slot_h_2",
        is_horizontal=True,
        width=14.0,
        axial_span=(100.0, 400.0),
        transverse_pos=520.0,
        bbox=(100.0, 513.0, 400.0, 527.0),
    )
    mesh = GlobalBeamChannelMesh(slots=[slot])
    scorer = ChannelConfidenceScorer()

    res = scorer.score_segment((100.0, 500.0, 400.0, 519.0), 19.0, True, mesh)
    assert res.matched_slot_id == "slot_h_2"
    assert res.status_flag == "WARNING_OFFSET"
    assert res.transverse_offset_cm == 10.5
    assert res.width_delta_cm == 5.0
