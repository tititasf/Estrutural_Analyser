# -*- coding: utf-8 -*-
"""
Analisador Especialista de Pilares.
Define AS REGRAS de o que buscar (Nome, Dimensão, Vizinhança) e orquestra o ContextEngine.
"""

import re
from typing import Dict, List, Any

import logging

logger = logging.getLogger(__name__)


class PillarAnalyzer:
    """
    Analisador Especialista de Pilares.
    Define AS REGRAS de o que buscar (Nome, Dimensão, Vizinhança) e orquestra o ContextEngine.
    """

    def __init__(self, context_engine: Any) -> None:
        self.ctx_engine = context_engine

    def analyze(self, p_data: Dict) -> Dict:
        """
        Executa a interpretação completa de um pilar (Nome, Dim, Lajes/Vigas ao redor).
        Retorna p_data enriquecido com links e confiança.
        """
        # Ensure required structures exist
        if 'links' not in p_data:
            p_data['links'] = {}
        if 'confidence_map' not in p_data:
            p_data['confidence_map'] = {}

        # --- 1. Nome do Pilar (prefix 'P') ---
        self._analyze_field(
            p_data,
            field_id='name',
            slot_id='label',
            config={'prompt': "Buscar texto ('P')", 'radius': 500},
            side=None,
        )

        # --- 2. Dimensão do Pilar (regex para NNxNN) ---
        dim_regex = r'^\d{1,3}[xX\*]\d{1,3}$'
        self._analyze_field(
            p_data,
            field_id='dim',
            slot_id='dim',
            config={'prompt': 'regex: ' + dim_regex, 'radius': 400},
            side=None,
        )

        # --- 3. Lajes e Vigas por lado (sides_data) ---
        sides_data = p_data.get('sides_data', {})

        for side_code, content in sides_data.items():
            # Generate field IDs based on side code (e.g., 'p_s_A', 'p_s_B')
            f_id_n = side_code + '_l1_n'      # Laje nome
            f_id_h = side_code + '_l1_h'       # Laje espessura
            f_id_vn = side_code + '_v_ch1_n'   # Viga nome
            f_id_vd = side_code + '_v_ch1_d'   # Viga vazio

            # Laje nome (prefix 'L')
            self._analyze_field(
                p_data,
                field_id=f_id_n,
                slot_id='_l1_n',
                config={'prompt': "Buscar texto ('L')", 'radius': 800},
                side=side_code,
            )

            # Laje espessura (regex h=NN ou h:NN)
            self._analyze_field(
                p_data,
                field_id=f_id_h,
                slot_id='thick',
                config={'prompt': r'regex: h[=:]?\d+', 'radius': 1000},
                side=side_code,
            )

            # Viga nome (prefix 'V')
            self._analyze_field(
                p_data,
                field_id=f_id_vn,
                slot_id='_v_ch1_n',
                config={'prompt': "Buscar texto ('V')", 'radius': 600},
                side=side_code,
            )

            # Viga vazio (X lines)
            self._analyze_field(
                p_data,
                field_id=f_id_vd,
                slot_id='void_x',
                config={'prompt': 'Buscar X', 'radius': 600},
                side=side_code,
            )

        return p_data

    def _analyze_field(
        self,
        p_data: Dict,
        field_id: str,
        slot_id: str,
        config: Dict,
        side: Any = None,
    ) -> Dict:
        """Helper para chamar engine e salvar resultado no p_data."""
        # Build search config
        search_config = {
            'field_id': field_id,
            'slot_id': slot_id,
            **config,
        }

        if side is not None:
            search_config['side'] = side

        # Execute search via context engine
        res = self.ctx_engine.perform_search(
            item_context=p_data,
            search_config=search_config,
            side=side or '',
        )

        # Extract result
        found_ent = res.get('found_ent')
        val = None

        if found_ent:
            val = found_ent.get('text', '')
            label = found_ent.get('text', '')

            # Save link
            p_data['links'][field_id] = val

            # For 'name' field, also set the pilar's name directly
            if slot_id == 'label':
                p_data['name'] = val

            # For 'dim' field, parse dimension parts
            if slot_id == 'dim':
                parts = re.split(r'[xX\*]', val)
                if len(parts) >= 2:
                    p_data['dim'] = val

            # For sided fields, store in sides_data
            if '_' in field_id and len(field_id.split('_')) >= 4:
                s_code = field_id.split('_')[0]
                key = '_'.join(field_id.split('_')[1:])
                if 'sides_data' not in p_data:
                    p_data['sides_data'] = {}
                if s_code not in p_data['sides_data']:
                    p_data['sides_data'][s_code] = {}
                p_data['sides_data'][s_code][key] = val

        # Save confidence
        confidence = res.get('confidence', 0.0)
        p_data['confidence_map'][field_id] = confidence

        return p_data
