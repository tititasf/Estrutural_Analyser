"""
test_natural_sync.py — Testa ordenação natural e clustering de vigas.

Os testes são lógica pura Python — não precisam de QApplication.
PySide6 removido do nível de módulo (era desnecessário aqui).
"""
import re
import unittest


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r"(\d+)", str(s))]


class TestNaturalSync(unittest.TestCase):

    def test_natural_sort_key(self):
        unsorted = ["V10.1", "V1.1", "V2.1", "V1.10", "V1.2"]
        expected = ["V1.1", "V1.2", "V1.10", "V2.1", "V10.1"]
        result = sorted(unsorted, key=natural_sort_key)
        self.assertEqual(result, expected)

    def test_robo_fundo_clustering(self):
        fundos_salvos = {
            "1.1":  {"nome": "V1.1",  "parent_name": "V1"},
            "10.1": {"nome": "V10.1", "parent_name": "V10"},
            "2.1":  {"nome": "V2.1",  "parent_name": "V2"},
            "1.2":  {"nome": "V1.2",  "parent_name": "V1"},
        }

        clusters: dict[str, list] = {}
        for num, dados in fundos_salvos.items():
            key = dados.get("parent_name", "Geral")
            clusters.setdefault(key, []).append(num)

        sorted_classes = sorted(clusters.keys(), key=natural_sort_key)
        self.assertEqual(sorted_classes, ["V1", "V2", "V10"])

        v1_items = sorted(clusters["V1"], key=natural_sort_key)
        self.assertEqual(v1_items, ["1.1", "1.2"])


if __name__ == "__main__":
    unittest.main()
