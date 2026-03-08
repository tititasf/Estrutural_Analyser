import json
import os
import sys
import unittest

# Adicionar root do projeto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# Mocks para engine
from src.core.pillar_analyzer import PillarAnalyzer
from src.core.context_engine import ContextEngine

class MockSpatialIndex:
    def __init__(self, data):
        self.data = data
    def query_bbox(self, bbox):
        # Retorna todas as linhas ou polígonos dentro
        res = []
        for l in self.data.get('lines', []):
            res.append(l)
        return res

class TestStructuralPhase3(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.dirname(__file__)
        with open(os.path.join(self.test_dir, 'mock_dxf_data.json'), 'r') as f:
            self.dxf_data = json.load(f)
        with open(os.path.join(self.test_dir, 'ground_truth.json'), 'r') as f:
            self.ground_truth = json.load(f)
            
        self.spatial = MockSpatialIndex(self.dxf_data)
        self.engine = ContextEngine(self.dxf_data, self.spatial)
        self.analyzer = PillarAnalyzer(self.engine)

    def test_pillar_extraction_phase3(self):
        """Valida que o Analisador extrai perfeitamente as geometrias e textos baseado no Ground Truth."""
        # Preparar dados de entrada mockados 
        pilar_raw = self.dxf_data['pillars'][0]
        p_data = {
            'id': pilar_raw['id'],
            'points': pilar_raw['points'],
            'pos': pilar_raw['pos'],
            'sides_data': {'A': {}, 'B': {}, 'C': {}, 'D': {}},
            'links': {},
            'confidence_map': {}
        }
        
        # Executar a Fase 3
        result = self.analyzer.analyze(p_data)
        
        # Asserções Padrão Ouro
        self.assertEqual(result.get('name'), self.ground_truth['name'], "Nome do pilar incorreto")
        self.assertEqual(result.get('dim'), self.ground_truth['dim'], "Dimensão do pilar incorreta")
        
        # Validar Lados
        sides_expected = self.ground_truth['sides_data']
        res_sides = result.get('sides_data', {})
        
        # A - Tem Laje L1, Viga V10
        self.assertEqual(res_sides['A'].get('l1_n'), sides_expected['A'].get('p_sA_l1_n'), "Laje lado A errada")
        self.assertEqual(res_sides['A'].get('v_ch1_n'), sides_expected['A'].get('p_sA_v_ch1_n'), "Viga lado A errada")
        
        # B - Não tem Laje (Tem X)
        self.assertEqual(res_sides['B'].get('l1_n'), sides_expected['B'].get('p_sB_l1_n'), "Laje lado B (Vazio) não identificado")
        self.assertEqual(res_sides['B'].get('v_ch1_n'), sides_expected['B'].get('p_sB_v_ch1_n'), "Viga chegada lado B falhou")
        
        # C - Laje L2
        self.assertEqual(res_sides['C'].get('l1_n'), sides_expected['C'].get('p_sC_l1_n'), "Laje lado C errada")

if __name__ == '__main__':
    unittest.main()
