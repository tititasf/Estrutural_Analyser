from typing import Dict, List, Any
import re

class PillarAnalyzer:
    """
    Analisador Especialista de Pilares.
    Define AS REGRAS de o que buscar (Nome, Dimensão, Vizinhança) e orquestra o ContextEngine.
    """
    
    def __init__(self, context_engine):
        self.ctx_engine = context_engine

    def analyze(self, p_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa a interpretação completa de um pilar (Nome, Dim, Lajes/Vigas ao redor).
        Retorna p_data enriquecido com links e confiança.
        """
        if 'links' not in p_data: p_data['links'] = {}
        if 'confidence_map' not in p_data: p_data['confidence_map'] = {}
        
        # 0. Identificador (Nome)
        # Regra: Texto próximo iniciando com P
        self._analyze_field(p_data, 'name', 'label', {'prompt': "Buscar texto ('P')", 'radius': 500})
        
        # 1. Dimensão
        # Regra: Texto (ex: 20x40) Próximo. Regex simples dimensions
        dim_regex = r"\d+([xX]\d+)?"
        self._analyze_field(p_data, 'dim', 'label', {'prompt': f"regex: {dim_regex}", 'radius': 400})

        # 2. Topo/Nível
        # (Opcional, depende do projeto)
        
        # 3. Analisar Lados (Lajes e Vigas)
        sides_data = p_data.get('sides_data', {})
        for side, content in sides_data.items():
            # Laje Nome
            f_id_n = f'p_s{side}_l1_n'
            # Regra: Texto iniciando com L no setor 'side'
            self._analyze_field(p_data, f_id_n, 'label', {'prompt': "Buscar texto ('L')", 'radius': 800}, side=side)
            
            # Laje Espessura (h=12)
            f_id_h = f'p_s{side}_l1_h'
            # Regra: Texto numérico próximo à laje encontrada
            # Nota: Isso requer refinar o centro de busca se a laje foi encontrada. 
            # O ContextEngine suporta ref_origin mas aqui simplificamos usando o centro do pilar
            self._analyze_field(p_data, f_id_h, 'thick', {'prompt': "regex: h[=:]?\\d+", 'radius': 1000}, side=side)
            
            # Vigas (Esquerda/Direita do lado)
            # Simplificação: Apenas Viga Esquerda por enquanto (padrão do código original)
            f_id_vn = f'p_s{side}_v_esq_n'
            self._analyze_field(p_data, f_id_vn, 'label', {'prompt': "Buscar texto ('V')", 'radius': 600}, side=side)
            
            f_id_vd = f'p_s{side}_v_esq_d'
            self._analyze_field(p_data, f_id_vd, 'dim', {'prompt': f"regex: {dim_regex}", 'radius': 600}, side=side)
            
            # Validação de Vazio (X)
            # Se não achou Laje, verifica se tem X
            if not p_data['links'].get(f_id_n):
                self._analyze_field(p_data, f_id_n, 'void_x', {'prompt': "Buscar X", 'radius': 800}, side=side)

        return p_data

    def _analyze_field(self, p_data, field_id, slot_id, config, side=None):
        """Helper para chamar engine e salvar resultado no p_data."""
        # Configurar Identidade do Campo para Memória
        config['field_id'] = field_id
        config['slot_id'] = slot_id
        
        res = self.ctx_engine.perform_search(p_data, config, side=side)
        
        if res['found_ent']:
            # Atualizar Links
            p_data['links'][field_id] = {'label': res['links']} # Simplificado, manter estrutura original
            
            # Atualizar Valor no p_data (flattened) se necessário
            # Mapear field_id volta para estrutura hierarquica (sides_data) é complexo aqui.
            # Idealmente p_data seria flat ou usaríamos setters.
            # Pela compatibilidade, vamos injetar direto no sides_data se for side field
            val = res['found_ent']['text']
            
            if field_id == 'name': p_data['name'] = val
            elif field_id == 'dim': p_data['dim'] = val
            elif '_s' in field_id: # É side field (p_sA_l1_n)
                # p_s{SIDE}_{KEY}
                parts = field_id.split('_')
                if len(parts) >= 4:
                    s_code = parts[1][1:] # sA -> A
                    key = "_".join(parts[2:]) # l1_n
                    if s_code in p_data.get('sides_data', {}):
                        p_data['sides_data'][s_code][key] = val

            # Atualizar Confiança
            p_data['confidence_map'][field_id] = res['confidence']
