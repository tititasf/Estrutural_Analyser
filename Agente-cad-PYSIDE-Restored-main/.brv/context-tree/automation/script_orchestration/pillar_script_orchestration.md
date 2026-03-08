## Relations
@structure/services/legacy_data_service.md

## Raw Concept
**Task:**
Implement fully orchestrated script generation for pillars.

**Changes:**
- Replaced PainelControleDesenhoPMixin with AutomationOrchestratorService.
- Introduced a unified flow for script generation: Clean -> Generate -> Combine -> Orchestrate.

**Files:**
- _ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/services/automation_service.py
- _ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/ui/viewmodels/main_viewmodel.py

**Flow:**
generate_full_paviment_orchestration -> (generate_scripts_cima, generate_abcd_script, generate_grades_script) -> _run_combiner -> _read_combined_script

**Timestamp:** 2026-01-14

## Narrative
### Structure
- Located at `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/services/automation_service.py`.
- Class: `AutomationOrchestratorService`.
- Key method: `generate_full_paviment_orchestration`.

### Dependencies
- Depends on legacy generators: CIMA_FUNCIONAL_EXCEL, ABCD_FUNCIONAL_EXCEL (or ROBO_ABCD), GRADES_FUNCIONAL_EXCEL (or ROBO_GRADES).
- Relies on legacy combiners: Combinador_de_SCR _cima, Combinador_de_SCR_abcd, Combinador_de_SCR_grades.

### Features
- Sequential generation of CIMA, ABCD, and GRADES scripts.
- Cleans output directories before generation.
- Adapts PilarModel to legacy dictionary formats.
- Executes legacy combiners to merge partial .scr files into a single unified script.
- Provides a unified AutoCAD execution script.
