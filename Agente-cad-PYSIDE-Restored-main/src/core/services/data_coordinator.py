from PySide6.QtCore import QObject, Signal

class DataCoordinator(QObject):
    """
    Central Coordinator for application state and events.
    Implements a Singleton pattern to be accessible globally if needed,
    but primarily passed via dependency injection.
    """
    
    _instance = None

    # --- Signals ---
    # Project & Navigation
    project_changed = Signal(str, str)  # project_id, project_name
    pavement_changed = Signal(str, str) # pavement_id, pavement_name
    work_changed = Signal(str)          # work_name
    
    # Selection & Interaction
    entity_selected = Signal(str, str)  # entity_id, entity_type (pillar, beam, slab)
    view_mode_changed = Signal(str)     # 'structural', 'architectural', etc.
    
    # Diagnostic Hub
    recommendation_applied = Signal(str) # recommendation_id
    
    # Comparison Engine
    scenarios_loaded = Signal(str, str)  # id_scenario_a, id_scenario_b
    sync_viewports_toggled = Signal(bool) # enabled/disabled
    show_differences_toggled = Signal(bool) # enabled/disabled

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataCoordinator, cls).__new__(cls)
            # Initialize QObject part safely
            # Note: QObject.__init__ is called in __init__ usually, doing it here carefully
        return cls._instance

    def __init__(self):
        # QObject init should only be called once
        if not hasattr(self, '_initialized'):
            super().__init__()
            self._initialized = True
            
            # State Cache (Optional, for late subscribers)
            self._current_project = None
            self._current_pavement = None
            self._current_work = None

    def set_project(self, project_id, project_name):
        if self._current_project != project_id:
            self._current_project = project_id
            self.project_changed.emit(project_id, project_name)

    def set_pavement(self, pavement_id, pavement_name):
        if self._current_pavement != pavement_id:
            self._current_pavement = pavement_id
            self.pavement_changed.emit(pavement_id, pavement_name)
            
    def set_work(self, work_name):
        if self._current_work != work_name:
            self._current_work = work_name
            self.work_changed.emit(work_name)

    def select_entity(self, entity_id, entity_type):
        self.entity_selected.emit(entity_id, entity_type)

    def toggle_sync(self, enabled: bool):
        self.sync_viewports_toggled.emit(enabled)

# Global accessor if strictly necessary (prefer injection)
def get_coordinator():
    return DataCoordinator()
