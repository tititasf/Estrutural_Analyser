import sys
import unittest
import json
import os
from PySide6.QtWidgets import QApplication
from robo_laterais_viga_pyside import VigaMainWindow, VigaState

# Mock AutoCAD Service to avoid COM errors
from unittest.mock import MagicMock
import robo_laterais_viga_pyside
robo_laterais_viga_pyside.AutoCADService = MagicMock()

app = QApplication.instance() or QApplication(sys.argv)

class TestHierarchyLogic(unittest.TestCase):
    def setUp(self):
        self.mw = VigaMainWindow()
        # Reset project data
        self.mw.project_data = {}
        self.mw.current_obra = ""
        self.mw.current_pavimento = ""
        self.mw.persistence_file = "test_persistence.json"
        if os.path.exists(self.mw.persistence_file):
            os.remove(self.mw.persistence_file)

    def tearDown(self):
        if os.path.exists("test_persistence.json"):
            os.remove("test_persistence.json")
        self.mw.close()

    def test_add_obra_pavimento(self):
        # Simulate Add Obra
        obra_name = "Obra Teste"
        self.mw.project_data[obra_name] = {}
        self.mw.update_obra_combo()
        self.mw.cmb_obra.setCurrentText(obra_name)
        
        self.assertEqual(self.mw.current_obra, obra_name)
        self.assertIn(obra_name, self.mw.project_data)
        
        # Simulate Add Pavimento structure {vigas:{}, metadata:{}}
        pav_name = "Pav 1"
        self.mw.project_data[obra_name][pav_name] = {'vigas': {}, 'metadata': {'in': '10', 'out': '20'}}
        self.mw.update_pavimento_combo()
        self.mw.cmb_pav.setCurrentText(pav_name)
        self.mw.on_pav_changed(pav_name) # Explicit call to ensure logic runs
        
        self.assertEqual(self.mw.current_pavimento, pav_name)
        self.assertIn(pav_name, self.mw.project_data[obra_name])
        # Check metadata load
        self.assertEqual(self.mw.edt_pav_level_in.text(), '10')

    def test_save_viga_hierarchy(self):
        # Setup Hierarchy
        self.mw.project_data = {"Obra1": {"Pav1": {'vigas': {}, 'metadata': {}}}}
        self.mw.update_obra_combo()
        self.mw.cmb_obra.setCurrentText("Obra1")
        self.mw.update_pavimento_combo()
        self.mw.cmb_pav.setCurrentText("Pav1")
        
        # Setup Viga Model
        self.mw.edt_name.setText("Viga 101")
        self.mw.edt_num.setText("101")
        self.mw.update_model()
        
        # Save
        self.mw.save_current_fundo()
        
        # Verify
        pav_content = self.mw.project_data["Obra1"]["Pav1"]
        self.assertIn("Viga 101", pav_content['vigas'])
        saved_viga = pav_content['vigas']["Viga 101"]
        self.assertEqual(saved_viga.number, "101")
        
        # Verify JSON File
        self.assertTrue(os.path.exists("test_persistence.json"))
        with open("test_persistence.json", 'r') as f:
            data = json.load(f)
            # data structure: project_data -> Obra -> Pav -> {vigas, metadata}
            pav_data = data["project_data"]["Obra1"]["Pav1"]
            self.assertIn("vigas", pav_data)
            self.assertIn("Viga 101", pav_data["vigas"])

    def test_json_import_export(self):
        # Create Dummy Data
        state = VigaState(name="Viga Exp", number="999")
        # Structure: Obra -> Pav -> {vigas: {name: state}, metadata: {}}
        self.mw.project_data = {
            "ObraExp": {
                "PavExp": {
                    "vigas": {"Viga Exp": state},
                    "metadata": {"in": "100", "out": "200"}
                }
            }
        }
        
        # Export manually
        export_file = "test_export.json"
        serializable_data = {
            "ObraExp": {
                "PavExp": {
                    "vigas": {"Viga Exp": state.to_dict()},
                    "metadata": {"in": "100", "out": "200"}
                }
            }
        }
        with open(export_file, 'w') as f:
            json.dump(serializable_data, f)
            
        # Clear Data
        self.mw.project_data = {}
        self.mw.update_obra_combo()
        
        # Import manually logic simulation
        with open(export_file, 'r') as f:
            data = json.load(f)
            self.mw.project_data = {}
            for obra, pavs in data.items():
                self.mw.project_data[obra] = {}
                for pav, content in pavs.items():
                    # Simplified structure assumption
                    self.mw.project_data[obra][pav] = {
                        'vigas': {},
                        'metadata': content.get('metadata', {})
                    }
                    for vname, vdict in content.get('vigas', {}).items():
                         v = VigaState()
                         v.name = vdict.get('name')
                         self.mw.project_data[obra][pav]['vigas'][vname] = v
        
        self.mw.update_obra_combo()
        
        self.assertIn("ObraExp", self.mw.project_data)
        pav_content = self.mw.project_data["ObraExp"]["PavExp"]
        self.assertIn("Viga Exp", pav_content['vigas'])
        self.assertEqual(pav_content['metadata']['in'], "100")
        
        if os.path.exists(export_file): os.remove(export_file)

if __name__ == '__main__':
    unittest.main()
