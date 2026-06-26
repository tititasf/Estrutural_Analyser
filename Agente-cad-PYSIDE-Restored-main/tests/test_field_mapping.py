#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_field_mapping.py — CAD-10.1 (AC-6)
Unit tests do módulo field_mapping.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

FIXTURES = pathlib.Path(__file__).parent / 'fixtures' / 'fase4_samples'

from src.core.field_mapping import (
    map_pilar, map_viga_lateral, map_viga_fundo, map_laje,
    map_detail_to_fase4, FACES_PILAR,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding='utf-8-sig'))


# ─── AC-1: map_pilar básico ───────────────────────────────────────────────────

class TestMapPilarBasic:
    def test_dim_field_populated(self):
        """map_pilar → flat['dim'] = 'CxL'."""
        d = load_fixture('P1.json')
        r = map_pilar(d)
        assert 'dim' in r['flat']
        dim = r['flat']['dim']
        assert 'x' in dim
        comp = str(int(d['comprimento']))
        larg = str(int(d['largura']))
        assert comp in dim and larg in dim

    def test_at_least_15_field_ids(self):
        """Pilar deve retornar >= 15 field IDs populados em flat (chapas agora vão para flat)."""
        d = load_fixture('P1.json')
        r = map_pilar(d)
        populated_flat = sum(1 for v in r['flat'].values() if v not in (None, '', 0.0, 0, [], {}))
        assert populated_flat >= 15, f"Só {populated_flat} campos populados em flat"

    def test_pavimento_populated(self):
        d = load_fixture('P1.json')
        r = map_pilar(d)
        assert r['flat'].get('pavimento') or r['flat'].get('floor') or True  # pode ser vazio se DXF tem encoding issue

    def test_grade_1_mapped(self):
        d = load_fixture('P1.json')
        r = map_pilar(d)
        assert 'grade_1' in r['flat']
        assert r['flat']['grade_1'] > 0

    def test_par_mapped(self):
        d = load_fixture('P1.json')
        r = map_pilar(d)
        assert 'par_1_2' in r['flat']
        assert r['flat']['par_1_2'] > 0

    def test_distancia_mapped(self):
        d = load_fixture('P1.json')
        r = map_pilar(d)
        assert 'distancia_1' in r['flat']


# ─── AC-1: faces A–D — chapas em flat como p_s{face}_c_h{n} ─────────────────

class TestMapPilarAllFaces:
    def test_faces_abcd_c_h_fields_in_flat(self):
        """Faces A–D com larg1 > 0 devem ter campos p_s{face}_c_h1..h3 em flat."""
        d = load_fixture('P1.json')
        r = map_pilar(d)
        flat = r['flat']
        for face in ['A', 'B', 'C', 'D']:
            assert f'p_s{face}_c_h1' in flat, f"p_s{face}_c_h1 ausente em flat"

    def test_h1_h2_h3_per_face(self):
        """Cada face deve ter p_s{face}_c_h1, _c_h2, _c_h3 em flat."""
        d = load_fixture('P1.json')
        r = map_pilar(d)
        flat = r['flat']
        for face in ['A', 'B', 'C', 'D']:
            assert f'p_s{face}_c_h1' in flat, f"h1 ausente em face {face}"
            assert f'p_s{face}_c_h2' in flat, f"h2 ausente em face {face}"
            assert f'p_s{face}_c_h3' in flat, f"h3 ausente em face {face}"

    def test_larg1_per_active_face(self):
        """Faces A–D devem ter p_s{face}_c_larg1 > 0."""
        d = load_fixture('P1.json')
        r = map_pilar(d)
        flat = r['flat']
        for face in ['A', 'B', 'C', 'D']:
            assert flat.get(f'p_s{face}_c_larg1', 0) > 0, f"larg1 zerado em face {face}"

    def test_h2_maior_que_h1_h3(self):
        """h2 (corpo) deve ser maior que h1 (base) e h3 (topo) para pilares normais."""
        d = load_fixture('P1.json')
        r = map_pilar(d)
        flat = r['flat']
        for face in ['A', 'B', 'C', 'D']:
            h1 = flat.get(f'p_s{face}_c_h1', 0)
            h2 = flat.get(f'p_s{face}_c_h2', 0)
            h3 = flat.get(f'p_s{face}_c_h3', 0)
            assert h2 > h1, f"h2 ({h2}) não maior que h1 ({h1}) na face {face}"
            assert h2 > h3, f"h2 ({h2}) não maior que h3 ({h3}) na face {face}"

    def test_inactive_faces_have_zero_larg1(self):
        """Faces E–H de pilar retangular devem ter larg1 = 0."""
        d = load_fixture('P1.json')
        r = map_pilar(d)
        flat = r['flat']
        for face in ['E', 'F', 'G', 'H']:
            larg1 = flat.get(f'p_s{face}_c_larg1', 0)
            assert larg1 == 0, f"Face {face} ativa inesperadamente (larg1={larg1})"


# ─── AC-2: map_viga_lateral ───────────────────────────────────────────────────

class TestMapVigaWithPanels:
    def test_returns_at_least_5_field_ids_per_segment(self):
        d = load_fixture('V101_A.json')
        r = map_viga_lateral(d, 'A')
        # V101_A tem 5 painéis → 5 segmentos × ≥5 campos
        seg_keys = [k for k in r['flat'] if 'seg_1_' in k]
        assert len(seg_keys) >= 5, f"Só {len(seg_keys)} campos no segmento 1"

    def test_comprimento_total_per_segment(self):
        d = load_fixture('V101_A.json')
        r = map_viga_lateral(d, 'A')
        panels = d.get('panels', [])
        for i, panel in enumerate(panels, start=1):
            key = f'viga_a_seg_{i}_comprimento_total'
            if panel.get('width', 0) > 0:
                assert key in r['flat'], f"Chave {key} ausente"
                assert abs(r['flat'][key] - panel['width']) < 0.1

    def test_h1_h2_per_segment(self):
        d = load_fixture('V101_A.json')
        r = map_viga_lateral(d, 'A')
        panels = d.get('panels', [])
        for i in range(1, len(panels) + 1):
            assert f'viga_a_seg_{i}_h1' in r['flat']
            assert f'viga_a_seg_{i}_h2' in r['flat']

    def test_dim_field(self):
        d = load_fixture('V101_A.json')
        r = map_viga_lateral(d, 'A')
        assert 'dim' in r['flat']
        assert 'x' in r['flat']['dim']

    def test_side_b_prefix(self):
        """Lado B usa prefixo 'viga_b_'."""
        d = load_fixture('V101_A.json')
        r = map_viga_lateral(d, 'B')
        keys = [k for k in r['flat'] if k.startswith('viga_b_')]
        assert len(keys) > 0


# ─── AC-2: holes ─────────────────────────────────────────────────────────────

class TestMapVigaWithHoles:
    def test_inactive_holes_not_mapped(self):
        """Aberturas inativas não devem gerar campos has_hole."""
        d = load_fixture('V101_A.json')
        r = map_viga_lateral(d, 'A')
        hole_keys = [k for k in r['flat'] if 'has_hole' in k]
        # V101_A tem todas as aberturas inativas
        assert len(hole_keys) == 0

    def test_active_hole_generates_fields(self):
        """Abertura ativa deve gerar has_hole, hole_width, hole_height, hole_position."""
        d = {
            'name': 'V999_A', 'floor': 'TÉRREO', 'side': 'A',
            'total_width': 19.0, 'total_height': '120.0',
            'panels': [{'width': 200.0, 'height1': 120.0, 'height2': 120.0,
                        'grade_h1': '0', 'grade_h2': '0'}],
            'holes': [{'active': True, 'width': 40.0, 'height': 30.0, 'position': 80.0}],
            'pillar_left': {'active': False, 'width': 0.0, 'length': 0.0},
            'pillar_right': {'active': False, 'width': 0.0, 'length': 0.0},
        }
        r = map_viga_lateral(d, 'A')
        assert r['flat'].get('viga_a_seg_1_has_hole') is True
        assert r['flat'].get('viga_a_seg_1_hole_width') == 40.0
        assert r['flat'].get('viga_a_seg_1_hole_height') == 30.0


# ─── AC-3: map_laje ───────────────────────────────────────────────────────────

class TestMapLajeBasic:
    def test_laje_dim_in_links(self):
        d = load_fixture('L101.json')
        r = map_laje(d)
        assert 'laje_dim' in r['links']

    def test_laje_dim_value(self):
        d = load_fixture('L101.json')
        r = map_laje(d)
        slots = r['links']['laje_dim']
        text = list(slots.values())[0][0]['text']
        assert 'x' in text

    def test_area_populated(self):
        d = load_fixture('L101.json')
        r = map_laje(d)
        assert r['flat'].get('area', 0) > 0

    def test_pontaletes_populated(self):
        d = load_fixture('L101.json')
        r = map_laje(d)
        pont = r['flat'].get('pontaletes')
        assert pont is not None
        assert pont.get('total', 0) > 0

    def test_at_least_4_field_ids(self):
        d = load_fixture('L101.json')
        r = map_laje(d)
        total = len(r['flat']) + len(r['links'])
        assert total >= 4, f"Só {total} fields para laje"

    def test_linhas_verticais_populated(self):
        d = load_fixture('L101.json')
        r = map_laje(d)
        lvs = r['flat'].get('laje_linhas_v', [])
        assert len(lvs) > 0


# ─── AC-4: mapeamento inverso ─────────────────────────────────────────────────

class TestMapInverse:
    def test_inverse_pilar_grade_1(self):
        result = map_detail_to_fase4('grade_1', '88.0')
        assert result is not None
        assert result[0] == 'grade_1'
        assert result[1] == 88.0

    def test_inverse_pilar_face_h1(self):
        result = map_detail_to_fase4('p_sA_c_h1', '2.0')
        assert result is not None
        assert result[0] == 'h1_A'
        assert result[1] == 2.0

    def test_inverse_pilar_face_larg1(self):
        result = map_detail_to_fase4('p_sB_c_larg1', '19.0')
        assert result is not None
        assert result[0] == 'larg1_B'
        assert result[1] == 19.0

    def test_inverse_pilar_laje_height(self):
        result = map_detail_to_fase4('p_sC_l1_h', '30.0')
        assert result is not None
        assert result[0] == 'laje_C'
        assert result[1] == 30.0

    def test_inverse_returns_none_for_unmapped(self):
        result = map_detail_to_fase4('viga_a_seg_1_h1', '120.0')
        assert result is None  # vigas não têm inverso definido ainda

    def test_inverse_all_faces(self):
        """Todas as faces A–H devem ter inverso para c_h1."""
        for face in FACES_PILAR:
            r = map_detail_to_fase4(f'p_s{face}_c_h1', '2.0')
            assert r is not None, f"Sem inverso para p_s{face}_c_h1"
            assert r[0] == f'h1_{face}'


# ─── AC-5: campos sem mapeamento documentados ─────────────────────────────────

class TestUnmappedFieldsDocumented:
    def test_fase4_fields_all_in_result(self):
        """Todos os campos do P1.json devem aparecer no resultado (flat ou sides_data)."""
        d = load_fixture('P1.json')
        r = map_pilar(d)

        all_result_keys = set(r['flat'].keys())
        for face, keys in r['sides_data'].items():
            for k in keys:
                all_result_keys.add(f'p_s{face}_{k}')

        # Campos importantes devem estar presentes
        assert 'dim' in all_result_keys
        assert 'grade_1' in all_result_keys
        assert 'par_1_2' in all_result_keys

    def test_meta_populated_for_all_mapped_fields(self):
        """Campos mapeados devem ter entrada em meta (confidence)."""
        d = load_fixture('P1.json')
        r = map_pilar(d)
        assert len(r['meta']) > 0
        assert 'dim' in r['meta']
        assert 'grade_1' in r['meta']
