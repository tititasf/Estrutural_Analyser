import json
import os

def generate_phase3_ground_truth():
    """
    Gera um mock estruturado (JSON) simulando o cache do dxf_data (dxf_loader) 
    para um pilar P1 rodeado por Lajes L1 e Vigas V1.
    As geometrias são exatas para forçar os algoritmos de "Raycast / Lados" a funcionar.
    """
    # Centro do Pilar P1 (20x40) em 0,0
    pilar_points = [
        (-10, 20), (10, 20), (10, -20), (-10, -20)
    ]
    
    # Textos mockados:
    texts = [
        {'text': 'P1', 'pos': (0, 0)},
        {'text': '20x40', 'pos': (0, -25)},
        # Lado A: Cima (45~135) -> Laje L1, Viga V10
        {'text': 'L1', 'pos': (0, 50)},
        {'text': 'h=12', 'pos': (0, 60)},
        {'text': 'V10', 'pos': (-30, 30)},
        {'text': '15x40', 'pos': (-30, 40)},
        # Lado B: Leste (-45~45) -> Sem laje (X), Viga chegando V20
        {'text': 'V20', 'pos': (40, 0)},
        {'text': '20x50', 'pos': (50, 0)},
        # Lado C: Baixo (-135~-45) -> Laje L2
        {'text': 'L2', 'pos': (0, -50)},
        {'text': 'h=10', 'pos': (0, -60)},
    ]
    
    # Criar Linhas: Para o Vazio 'X' no Lado B
    lines = [
        {'start': (20, 20), 'end': (80, -20), 'layer': 'VAZIO'},
        {'start': (20, -20), 'end': (80, 20), 'layer': 'VAZIO'}
    ]
    
    dxf_data_mock = {
        'texts': texts,
        'lines': lines,
        'pillars': [{'id': 'p1', 'points': pilar_points, 'name': 'P1', 'pos': (0,0)}]
    }
    
    # The Ground Truth Dictionary (oque esperamos que a IA / ContextEngine devolva)
    ground_truth = {
        'name': 'P1',
        'dim': '20x40',
        # Sides Data do Pilar P1:
        'sides_data': {
            'A': {
                'p_sA_l1_n': 'L1',
                'p_sA_l1_h': '12.0',
                'p_sA_v_ch1_n': 'V10',
                'p_sA_v_ch1_d': '15x40'
            },
            'B': {
                'p_sB_l1_n': 'SEM LAJE', # VAZIO X encontrado
                'p_sB_v_ch1_n': 'V20',
                'p_sB_v_ch1_d': '20x50'
            },
            'C': {
                'p_sC_l1_n': 'L2',
                'p_sC_l1_h': '10.0'
            },
            'D': {
                'p_sD_l1_n': None # Lado sem nada
            }
        }
    }
    
    out_dir = r"c:\Users\Ryzen\Desktop\AIOS-DIANA\Agente-cad-PYSIDE\tests\core\phase3"
    os.makedirs(out_dir, exist_ok=True)
    
    with open(os.path.join(out_dir, 'mock_dxf_data.json'), 'w') as f:
        json.dump(dxf_data_mock, f, indent=2)
        
    with open(os.path.join(out_dir, 'ground_truth.json'), 'w') as f:
        json.dump(ground_truth, f, indent=2)

if __name__ == "__main__":
    generate_phase3_ground_truth()
    print("Mocks e Ground Truth gerados com sucesso!")
