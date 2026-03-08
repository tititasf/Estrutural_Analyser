## Relations
@structure/services/automation_service.md

## Raw Concept
**Task:**
Fix legacy data integrity and improve loading service.

**Changes:**
- Improved robustness of legacy data loading to handle inconsistent `.pkl` structures.
- Added explicit type conversion for critical fields during the loading process.

**Files:**
- _ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/services/legacy_service.py

**Flow:**
load_all_data -> pickle.load -> iterate Obras -> iterate Pavimentos -> validate/coerce Pillars -> ObraModel collection

**Timestamp:** 2026-01-14

## Narrative
### Structure
- Located at `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/services/legacy_service.py`.
- Class: `LegacyDataService`.
- Key method: `load_all_data`.

### Dependencies
- Uses `PilarModel` for data validation and coercion.
- Loads data from `.pkl` files (`obras_salvas.pkl`).
- Integrated with `MainViewModel` for state management.

### Features
- Handles multiple legacy data formats (dicts, lists, nested structures).
- Ensures data integrity by forcing critical fields (name, number) to strings.
- Leverages `PilarModel`'s type coercion (e.g., converting comma-separated strings to floats).
- Supports loading entire works (Obras) with their respective pavements and pillars.
