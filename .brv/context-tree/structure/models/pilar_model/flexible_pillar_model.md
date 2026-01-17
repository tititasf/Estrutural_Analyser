## Relations
@structure/services/legacy_data_service.md

## Raw Concept
**Task:**
Update PilarModel to be flexible for legacy data.

**Changes:**
- Updated model to be highly flexible for legacy data.
- Implemented automatic type coercion for float and string fields.

**Files:**
- _ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/models/pilar_model.py

**Flow:**
Data Input -> coerce_to_type Validator -> Field Assignment -> PilarModel Instance

**Timestamp:** 2026-01-14

## Narrative
### Structure
- Located at `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/models/pilar_model.py`.
- Class: `PilarModel`.

### Dependencies
- Built with Pydantic.
- Used by `LegacyDataService` for validation.
- Consumed by `AutomationOrchestratorService` for script generation.

### Features
- `extra="allow"`: Supports arbitrary legacy fields not explicitly defined.
- `coerce_to_type`: Custom validator that handles common legacy data issues (e.g., commas in floats, null strings).
- Comprehensive field mapping for pillars (geometry, bolts, reinforcement, special types).
