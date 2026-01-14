import sys
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

# Mock AutoCADService BEFORE importing main window to avoid COM initialization
import robo_laterais_viga_pyside
from robo_laterais_viga_pyside import VigaMainWindow, CancelledSelectionError

app = QApplication.instance() or QApplication(sys.argv)

class TestESCCancel(unittest.TestCase):
    def setUp(self):
        # Patch the AutoCADService class in the module
        self.mock_acad_class = patch('robo_laterais_viga_pyside.AutoCADService').start()
        self.mw = VigaMainWindow()
        self.mw.acad_service = self.mock_acad_class.return_value
        
        # Mock UI elements that might block
        self.mw.statusBar = MagicMock()
        self.mw.display_floating = MagicMock()
        self.mw.update_model = MagicMock()

    def tearDown(self):
        patch.stopall()
        self.mw.close()

    def test_run_sequence_logic_stops_on_esc(self):
        # Configure mock to raise CancelledSelectionError on the first selection step (select_line_length)
        self.mw.acad_service.select_line_length.side_effect = CancelledSelectionError("ESC Pressed")
        
        # We need to set a name so it doesn't trigger name selection
        self.mw.edt_name.setText("Viga Teste.A")
        
        # Run logic
        self.mw.run_sequence_logic()
        
        # Verify that select_levels was NOT called (sequence stopped)
        self.mw.acad_service.select_levels.assert_not_called()
        
        # Verify status bar message
        self.mw.statusBar().showMessage.assert_any_call("⚠️ Seleção Cancelada: ESC Pressed", 5000)
        
        print("\nSUCCESS: Sequence stopped correctly on ESC.")

if __name__ == '__main__':
    unittest.main()
