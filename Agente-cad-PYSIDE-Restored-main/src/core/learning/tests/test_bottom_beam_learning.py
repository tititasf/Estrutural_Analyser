# src/core/learning/tests/test_bottom_beam_learning.py
import os
import pytest
from datetime import datetime
from src.core.learning.bottom_beam_learning_store import BottomBeamLearningStore
from src.core.learning.feedback_models import FeedbackEntry

def test_bottom_beam_learning_store(tmp_path):
    store = BottomBeamLearningStore(project_uuid="TEST_UUID", base_dir=str(tmp_path))
    
    # Validate defaults
    params = store.get_learning_params()
    assert params["length_measurement_tolerance"] == 0.02
    assert params["panel_detection_threshold"] == 0.75
    
    # Simulate 5 misses for comprimento_total
    for i in range(5):
        entry = FeedbackEntry(
            class_type="bottom_beam",
            element_id=f"V{i}",
            field_name="comprimento_total",
            predicted_value=10.0,
            actual_value=12.0,
            was_correct=False,
            confidence_at_prediction=0.9,
            context_signature={"segment_count": 1},
            timestamp=datetime.now().isoformat(),
            pavimento="1",
            project_uuid="TEST_UUID"
        )
        store.record_feedback(entry)
        
    # Check updated params
    params = store.get_learning_params()
    assert params["length_measurement_tolerance"] == 0.05
