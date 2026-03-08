
import sys
import os
import unittest
from PySide6.QtCore import QCoreApplication

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.services.data_coordinator import DataCoordinator, get_coordinator

class TestDataCoordinator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # QCoreApplication is needed for Signals to work
        if not QCoreApplication.instance():
            cls.app = QCoreApplication(sys.argv)
        else:
            cls.app = QCoreApplication.instance()

    def setUp(self):
        # Reset singleton logic if possible or just get instance
        self.coordinator = get_coordinator()
        # Reset state manually for tests
        self.coordinator._current_project = None
        self.coordinator._current_pavement = None
        self.coordinator._current_work = None
        
        self.received_signals = {}
    
    def on_project_changed(self, pid, pname):
        self.received_signals['project'] = (pid, pname)
        
    def on_sync_toggled(self, state):
        self.received_signals['sync'] = state

    def test_singleton_behavior(self):
        c1 = DataCoordinator()
        c2 = get_coordinator()
        self.assertIs(c1, c2, "DataCoordinator deve ser Singleton")

    def test_project_changed_signal(self):
        # Connect
        self.coordinator.project_changed.connect(self.on_project_changed)
        
        # Trigger
        self.coordinator.set_project("PROJ-001", "Edificio A")
        
        # Verify
        self.assertIn('project', self.received_signals)
        self.assertEqual(self.received_signals['project'], ("PROJ-001", "Edificio A"))
        
        # Disconnect
        self.coordinator.project_changed.disconnect(self.on_project_changed)

    def test_sync_toggle(self):
        self.coordinator.sync_viewports_toggled.connect(self.on_sync_toggled)
        
        self.coordinator.toggle_sync(True)
        self.assertEqual(self.received_signals['sync'], True)
        
        self.coordinator.toggle_sync(False)
        self.assertEqual(self.received_signals['sync'], False)
        
        self.coordinator.sync_viewports_toggled.disconnect(self.on_sync_toggled)

if __name__ == '__main__':
    unittest.main()
