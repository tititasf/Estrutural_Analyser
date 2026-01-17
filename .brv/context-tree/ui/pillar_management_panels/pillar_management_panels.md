## Relations
@automation/script_orchestration/pillar_script_orchestration.md

## Raw Concept
**Task:**
Complete D.CAD sidebar actions and item list population.

**Changes:**
- Implemented sidebar with full drawing orchestration triggers.
- Completed the pillar list panel with dynamic population and filtering logic.

**Files:**
- _ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/ui/organisms/panels.py
- _ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/ui/main_window.py

**Flow:**
User Interaction (Sidebar/List) -> ViewModel Slot -> Service Execution -> UI Update (via property_changed)

**Timestamp:** 2026-01-14

## Narrative
### Structure
- Located at `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/ui/organisms/panels.py`.
- Classes: `SidebarWidget`, `PilarListPanel`.

### Dependencies
- Linked to `MainViewModel` for action execution and data synchronization.
- Styles defined in `ui.styles.AppStyles`.

### Features
- Sidebar: Unified "D.CAD" actions (Complete, CIMA, ABCD, Grades) and CAD Import tools.
- Pillar List: Dynamic population based on selected Work/Pavement.
- Real-time filtering and selection synchronization.
- Automatic area (m²) calculation in the list view.
