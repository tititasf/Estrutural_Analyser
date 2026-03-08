
import sys
import unittest
from PySide6.QtWidgets import QApplication

# Mock ou Import do VigaState se necessário
class VigaState:
    def __init__(self, number, name, floor, segment_class="Lista Geral"):
        self.number = number
        self.name = name
        self.floor = floor
        self.segment_class = segment_class
        self.area_util = 0.0

class TestNaturalSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Necessário para instanciar QWidgets se for testar UI
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_natural_sort_key(self):
        import re
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower()
                    for text in re.split(r'(\d+)', str(s))]
        
        unsorted = ["V10.1", "V1.1", "V2.1", "V1.10", "V1.2"]
        expected = ["V1.1", "V1.2", "V1.10", "V2.1", "V10.1"]
        
        result = sorted(unsorted, key=natural_sort_key)
        self.assertEqual(result, expected)

    def test_robo_fundo_clustering(self):
        # Simular dados do Robo Fundo
        fundos_salvos = {
            "1.1": {"nome": "V1.1", "parent_name": "V1"},
            "10.1": {"nome": "V10.1", "parent_name": "V10"},
            "2.1": {"nome": "V2.1", "parent_name": "V2"},
            "1.2": {"nome": "V1.2", "parent_name": "V1"}
        }
        
        import re
        def natural_key(text):
            if not text: return []
            return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(text))]

        # Cluster logic
        clusters = {}
        for num, dados in fundos_salvos.items():
            cluster_key = dados.get('parent_name', "Geral")
            if cluster_key not in clusters: clusters[cluster_key] = []
            clusters[cluster_key].append(num)
            
        # Verify sorted classes
        sorted_classes = sorted(clusters.keys(), key=natural_key)
        self.assertEqual(sorted_classes, ["V1", "V2", "V10"])
        
        # Verify sorted items in V1
        v1_items = sorted(clusters["V1"], key=natural_key)
        self.assertEqual(v1_items, ["1.1", "1.2"])

if __name__ == "__main__":
    unittest.main()
