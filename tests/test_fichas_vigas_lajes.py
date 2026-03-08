"""
Testes das fichas de Vigas e Lajes.
Roda sem AutoCAD - só valida a transformação de dados.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pipeline.ficha_vigas_schema import (
    FichaFase3Viga,
    ficha_fase3_to_robo_viga_dict,
    fichas_to_vigas_salvas,
    fichas_to_tramos_salvos,
    salvar_fichas_json,
    carregar_fichas_json,
)
from src.pipeline.ficha_lajes_schema import (
    FichaFase3Laje,
    ficha_fase3_to_robo_laje_dict,
    fichas_to_lajes_salvas,
    fichas_to_lajes_outline,
    salvar_fichas_json as lajes_salvar,
    carregar_fichas_json as lajes_carregar,
)
from src.adapters.fase3_to_fase4_vigas import adaptar_fase3_para_fase4 as adaptar_vigas
from src.adapters.fase3_to_fase4_lajes import adaptar_fase3_para_fase4 as adaptar_lajes


def _viga_exemplo(codigo="V1", pav="P-1") -> FichaFase3Viga:
    return FichaFase3Viga(
        codigo=codigo,
        pavimento=pav,
        obra_nome="Obra Teste",
        tipo="retangular",
        largura=20.0,
        altura=40.0,
        comprimento=450.0,
        secao_transversal={"tipo": "retangular", "dimensoes": {"b": 20, "h": 40}},
        tramos=[{"comprimento": 450.0, "tipo_apoio": "fixo"}],
        armadura_positiva={"qtd_barras": 3, "diametro": 16, "tipo_aco": "CA-50"},
        armadura_negativa={"qtd_barras": 2, "diametro": 10, "tipo_aco": "CA-50"},
        estribos={"diametro": 8, "espacamento": 15, "tipo_aco": "CA-50"},
        confidence=0.92,
        revisado=True,
    )


def _laje_exemplo(codigo="L1", pav="P-1") -> FichaFase3Laje:
    return FichaFase3Laje(
        codigo=codigo,
        pavimento=pav,
        obra_nome="Obra Teste",
        tipo="macica",
        dimensoes={"comprimento": 400, "largura": 300, "espessura": 10},
        espessura=10.0,
        outline_segs=[{"x": 0, "y": 0}, {"x": 400, "y": 0}, {"x": 400, "y": 300}, {"x": 0, "y": 300}, {"x": 0, "y": 0}],
        nivel=3.0,
        armadura={"tipo": "CA-50", "diametro": 10, "espacamento": 15, "direcao": "bidirecional"},
        confidence=0.88,
        revisado=True,
    )


class TestFichaVigaSchema(unittest.TestCase):

    def test_validacao_ok(self):
        v = _viga_exemplo()
        self.assertEqual(v.validate(), [])

    def test_validacao_largura_minima(self):
        v = _viga_exemplo()
        v.largura = 10
        erros = v.validate()
        self.assertTrue(any("largura" in e for e in erros))

    def test_validacao_altura_minima(self):
        v = _viga_exemplo()
        v.altura = 20
        erros = v.validate()
        self.assertTrue(any("altura" in e for e in erros))

    def test_validacao_tipo_invalido(self):
        v = _viga_exemplo()
        v.tipo = "circular"
        erros = v.validate()
        self.assertTrue(any("tipo" in e for e in erros))

    def test_validacao_tramos_vazio(self):
        v = _viga_exemplo()
        v.tramos = []
        erros = v.validate()
        self.assertTrue(any("tramo" in e for e in erros))

    def test_validacao_confidence_invalida(self):
        v = _viga_exemplo()
        v.confidence = 1.5
        erros = v.validate()
        self.assertTrue(any("confidence" in e for e in erros))

    def test_precisa_revisao_confidence_baixa(self):
        v = _viga_exemplo()
        v.confidence = 0.5
        v.revisado = False
        self.assertTrue(v.precisa_revisao())

    def test_nao_precisa_revisao_se_revisado(self):
        v = _viga_exemplo()
        v.confidence = 0.3
        v.revisado = True
        self.assertFalse(v.precisa_revisao())

    def test_area_secao(self):
        v = _viga_exemplo()
        self.assertEqual(v.area_secao(), 800.0)  # 20 * 40

    def test_volume_concreto(self):
        v = _viga_exemplo()
        esperado = (800.0 * 450.0) / 1_000_000  # 0.36 m³
        self.assertAlmostEqual(v.volume_concreto(), esperado, places=4)

    def test_to_dict_serialization(self):
        v = _viga_exemplo()
        d = v.to_dict()
        self.assertEqual(d["codigo"], "V1")
        self.assertEqual(d["largura"], 20.0)
        self.assertIn("data_extracao", d)

    def test_from_dict_factory(self):
        dados = {
            "codigo": "V2", "pavimento": "P-2", "obra_nome": "Teste",
            "tipo": "L", "largura": 15, "altura": 35, "comprimento": 300,
            "secao_transversal": {}, "tramos": [{"comprimento": 300}],
            "armadura_positiva": {}, "armadura_negativa": {}, "estribos": {},
        }
        v = FichaFase3Viga.from_dict(dados)
        self.assertEqual(v.codigo, "V2")
        self.assertEqual(v.tipo, "L")


class TestFichaLajeSchema(unittest.TestCase):

    def test_validacao_ok(self):
        l = _laje_exemplo()
        self.assertEqual(l.validate(), [])

    def test_validacao_espessura_minima(self):
        l = _laje_exemplo()
        l.espessura = 5
        erros = l.validate()
        self.assertTrue(any("espessura" in e for e in erros))

    def test_validacao_tipo_invalido(self):
        l = _laje_exemplo()
        l.tipo = "invalido"
        erros = l.validate()
        self.assertTrue(any("tipo" in e for e in erros))

    def test_validacao_outline_vazio(self):
        l = _laje_exemplo()
        l.outline_segs = []
        erros = l.validate()
        self.assertTrue(any("outline" in e for e in erros))

    def test_area_retangular_fallback(self):
        l = FichaFase3Laje(
            codigo="L1", pavimento="P-1", obra_nome="Teste",
            tipo="macica", dimensoes={"comprimento": 400, "largura": 300, "espessura": 10},
            espessura=10, outline_segs=[], nivel=3.0, armadura={}
        )
        area = l.area()
        self.assertAlmostEqual(area, 12.0, places=1)  # 4m * 3m

    def test_area_shoelace(self):
        l = _laje_exemplo()
        area = l.area()
        self.assertAlmostEqual(area, 12.0, places=1)  # 400cm * 300cm = 12 m²

    def test_volume_concreto(self):
        l = _laje_exemplo()
        volume = l.volume_concreto()
        self.assertAlmostEqual(volume, 1.2, places=1)  # 12 m² * 0.1m

    def test_to_dict_serialization(self):
        l = _laje_exemplo()
        d = l.to_dict()
        self.assertEqual(d["codigo"], "L1")
        self.assertEqual(d["espessura"], 10.0)

    def test_from_dict_factory(self):
        dados = {
            "codigo": "L2", "pavimento": "P-2", "obra_nome": "Teste",
            "tipo": "pre_moldada", "dimensoes": {"comprimento": 500, "largura": 400},
            "espessura": 12, "outline_segs": [], "nivel": 6.0, "armadura": {},
        }
        l = FichaFase3Laje.from_dict(dados)
        self.assertEqual(l.codigo, "L2")
        self.assertEqual(l.tipo, "pre_moldada")


class TestConversaoVigaParaRobo(unittest.TestCase):

    def test_campos_mapeados_corretamente(self):
        v = _viga_exemplo()
        robo = ficha_fase3_to_robo_viga_dict(v)
        d = robo["dados"]
        self.assertEqual(d["codigo"], "V1")
        self.assertEqual(d["dimensoes"]["b"], 20.0)
        self.assertEqual(d["dimensoes"]["h"], 40.0)
        self.assertEqual(d["armadura"]["positiva"]["qtd_barras"], 3)

    def test_vigas_salvas_chave_composta(self):
        vigas = [_viga_exemplo("V1", "P-1"), _viga_exemplo("V2", "P-1")]
        salvos = fichas_to_vigas_salvas(vigas)
        self.assertIn("V1_P-1", salvos)
        self.assertIn("V2_P-1", salvos)

    def test_tramos_salvos_chave_composta(self):
        v = _viga_exemplo()
        v.tramos = [{"comprimento": 200}, {"comprimento": 250}]
        tramos = fichas_to_tramos_salvos([v])
        self.assertIn("V1_P-1_T1", tramos)
        self.assertIn("V1_P-1_T2", tramos)


class TestConversaoLajeParaRobo(unittest.TestCase):

    def test_campos_mapeados_corretamente(self):
        l = _laje_exemplo()
        robo = ficha_fase3_to_robo_laje_dict(l)
        d = robo["dados"]
        self.assertEqual(d["codigo"], "L1")
        self.assertEqual(d["tipo"], "MACICA")
        self.assertEqual(d["espessura"], 10.0)

    def test_lajes_salvas_chave_composta(self):
        lajes = [_laje_exemplo("L1", "P-1"), _laje_exemplo("L2", "P-1")]
        salvos = fichas_to_lajes_salvas(lajes)
        self.assertIn("L1_P-1", salvos)
        self.assertIn("L2_P-1", salvos)

    def test_lajes_outline(self):
        l = _laje_exemplo()
        outline = fichas_to_lajes_outline([l])
        chave = "L1_P-1"
        self.assertIn(chave, outline)
        self.assertAlmostEqual(outline[chave]["area_m2"], 12.0, places=1)


class TestPersistencia(unittest.TestCase):

    def test_viga_salvar_e_carregar_json(self):
        vigas = [_viga_exemplo("V1"), _viga_exemplo("V2")]
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho = os.path.join(tmpdir, "vigas.json")
            salvar_fichas_json(vigas, caminho)
            carregadas = carregar_fichas_json(caminho)
        self.assertEqual(len(carregadas), 2)
        self.assertEqual(carregadas[0].codigo, "V1")

    def test_laje_salvar_e_carregar_json(self):
        lajes = [_laje_exemplo("L1"), _laje_exemplo("L2")]
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho = os.path.join(tmpdir, "lajes.json")
            lajes_salvar(lajes, caminho)
            carregadas = lajes_carregar(caminho)
        self.assertEqual(len(carregadas), 2)
        self.assertEqual(carregadas[0].codigo, "L1")


class TestAdapterVigaE2E(unittest.TestCase):

    def test_adapter_end_to_end(self):
        vigas = [_viga_exemplo("V1"), _viga_exemplo("V2")]
        with tempfile.TemporaryDirectory() as tmpdir:
            fichas_path = os.path.join(tmpdir, "fichas_vigas.json")
            salvar_fichas_json(vigas, fichas_path)
            output_path = os.path.join(tmpdir, "fase4")
            relatorio = adaptar_vigas(fichas_path, "Obra Teste", output_path)
            self.assertEqual(relatorio["total"], 2)
            self.assertEqual(relatorio["validas"], 2)
            self.assertTrue(os.path.exists(os.path.join(output_path, "vigas_salvas.json")))
            self.assertTrue(os.path.exists(os.path.join(output_path, "tramos_salvos.json")))


class TestAdapterLajeE2E(unittest.TestCase):

    def test_adapter_end_to_end(self):
        lajes = [_laje_exemplo("L1"), _laje_exemplo("L2")]
        with tempfile.TemporaryDirectory() as tmpdir:
            fichas_path = os.path.join(tmpdir, "fichas_lajes.json")
            lajes_salvar(lajes, fichas_path)
            output_path = os.path.join(tmpdir, "fase4")
            relatorio = adaptar_lajes(fichas_path, "Obra Teste", output_path)
            self.assertEqual(relatorio["total"], 2)
            self.assertEqual(relatorio["validas"], 2)
            self.assertTrue(os.path.exists(os.path.join(output_path, "lajes_salvas.json")))
            self.assertTrue(os.path.exists(os.path.join(output_path, "lajes_outline.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
