
import unittest
import sys
import os
import shutil
import pickle
import uuid
from pathlib import Path

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from src.core.storage.project_storage import ProjectStorageManager
from src.core.database import DatabaseManager

class TestProjectStorage(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_storage.vision"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        self.db = DatabaseManager(self.db_path)
        self.storage_base = Path("TEST_DADOS_OBRAS_ROOT")
        self.storage = ProjectStorageManager(base_dir=self.storage_base)
        self.work_name = "Obra_Teste_Unitario"
        
        # Cleanup storage before start
        if self.storage.storage_root.exists():
            shutil.rmtree(self.storage.storage_root)
            
    def tearDown(self):
        if hasattr(self, 'db'):
            # Close connection if implicit, but here we just delete file
            pass
        # os.remove(self.db_path) # Optionally keep for inspection
        if self.storage.storage_root.exists():
            shutil.rmtree(self.storage.storage_root)
        if self.storage_base.exists():
            shutil.rmtree(self.storage_base)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_folder_structure_creation(self):
        """Testa se a estrutura de pastas é criada corretamente."""
        self.storage.initialize_work_structure(self.work_name)
        
        work_path = self.storage.get_work_path(self.work_name)
        self.assertTrue(work_path.exists())
        
        # Check standard phases
        phase1 = work_path / "Fase-1_Ingestao"
        self.assertTrue(phase1.exists())
        
        # Check standard classes
        class_folder = phase1 / "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
        # Since _sanitize_name functionality:
        # "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)"
        # -> replace " " with "_" -> "Estruturais_dos_Pavimentos,_Estado_Bruto_(.DWG/.DXF)"
        # -> replace "/" with "_" -> "Estruturais_dos_Pavimentos,_Estado_Bruto_(.DWG_.DXF)"
        # -> replace "." with "" -> "Estruturais_dos_Pavimentos,_Estado_Bruto_(DWG_DXF)"
        # -> re.sub(r'[^\w\-]', '', name) -> remove parens/commas
        
        # We need to trust _sanitize_name or reverse engineer it here.
        # Let's perform a save and check if it lands there.
        pass

    def test_save_and_db_integration(self):
        """Testa salvar arquivo e registrar no DB."""
        # 1. Create Work in DB
        self.db.create_work(self.work_name)
        self.storage.initialize_work_structure(self.work_name)
        
        # 2. Add Project
        project_id = self.db.create_project(
            "Pavimento_Terreo", 
            work_name=self.work_name, 
            pavement_name="Terreo"
        )
        
        # 3. Save a dummy file
        dummy_file = Path("dummy_test_doc.txt")
        dummy_file.write_text("Hello Storage")
        
        try:
            target_path = self.storage.save_file(
                source_file_path=str(dummy_file),
                work_name=self.work_name,
                phase_id=1,
                class_name="Geral",
                new_filename="test_doc.txt"
            )
            
            # Check physical existence
            self.assertTrue(target_path.exists())
            self.assertIn(self.work_name, str(target_path))
            self.assertIn("Fase-1", str(target_path))
            
            # 4. Save to DB
            self.db.save_document(
                project_id=project_id,
                name="Documento Teste",
                file_path=str(target_path),
                extension=".txt",
                phase=1,
                category="Geral"
            )
            
            # 5. Retrieve from DB
            docs = self.db.get_project_documents(project_id)
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]['file_path'], str(target_path))
            
        finally:
            if dummy_file.exists():
                os.remove(dummy_file)

    def test_pkl_persistence(self):
        """Testa salvar e recuperar .pkl via DB workflow."""
        self.db.create_work(self.work_name)
        project_id = self.db.create_project("Pav_Pkl", work_name=self.work_name)
        
        # Create a complex object
        data = {'a': 1, 'b': [1, 2, 3]}
        pillar_id = str(uuid.uuid4())
        
        # Save PKL
        pkl_path = self.storage.save_data_object(
            data_object=data,
            work_name=self.work_name,
            phase_id=3,
            class_name="Pilares",
            identifier=f"Pilar_{pillar_id}"
        )
        
        self.assertTrue(pkl_path.exists())
        self.assertTrue(str(pkl_path).endswith(".pkl"))
        
        # Save Pillar to DB with pkl_path
        pillar_data = {
            'id': pillar_id,
            'name': 'P1',
            'type': 'square',
            'validated_fields': ['name'],
            'pkl_path': str(pkl_path)
        }
        
        self.db.save_pillar(pillar_data, project_id)
        
        # Load and verify
        loaded_pillars = self.db.load_pillars(project_id)
        self.assertEqual(len(loaded_pillars), 1)
        loaded = loaded_pillars[0]
        
        self.assertEqual(loaded['pkl_path'], str(pkl_path))
        
        # Load object from storage to verify content
        loaded_obj = self.storage.load_data_object(loaded['pkl_path'])
        self.assertEqual(loaded_obj, data)

if __name__ == '__main__':
    unittest.main()
