"""G0/G2 calibration corpus and CAD packet factory for optional Jev second reading.

This package does not call the Jev API, write N1, or replace the canonical QA loop.
"""

from .schemas import (
    ADJUDICATION_SCHEMA,
    BASELINE_SCHEMA,
    RUN_MANIFEST_SCHEMA,
    SOURCE_PACKET_SCHEMA,
)

__all__ = [
    "ADJUDICATION_SCHEMA",
    "BASELINE_SCHEMA",
    "RUN_MANIFEST_SCHEMA",
    "SOURCE_PACKET_SCHEMA",
]
