"""
Testes do adapter Fase 3 → Fase 4 para pilares.
Roda sem AutoCAD, sem executável — só valida a transformação de dados.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pipeline.ficha_pilares_schema import (
    FichaFase3Pilar,
    ficha_fase3_to_robo_dict,
    fichas_to_obras_salvas,
    fichas_to_pilares_salvos,
    salvar_fichas_json,
    carregar_fichas_json,
)
from src.adapters.fase3_to_fase4_pilares import adaptar_fase3_para_fase4


def _ficha_exemplo(id="P1", numero="1", pav="TERREO") -> FichaFase3Pilar:
    return FichaFase3Pilar(
        id=id,
        numero=numero,
        pavimento=pav,
        pavimento_numero=0,
        obra="Obra Teste",
        comprimento=50.0,
        largura=20.0,
        altura_cm=300.0,
        nivel_saida_m=0.0,
        nivel_chegada_m=3.0,
        par_1_2="8",
        par_2_3="8",
        grade_1="8",
        distancia_1="15",
        confidence=0.91,
        revisado_por_humano=True,
    )


class TestFichaSchema(unittest.TestCase):

    def test_validacao_ok(self):
        f = _ficha_exemplo()
        self.assertEqual(f.validar(), [])

    def test_validacao_falha_comprimento_zero(self):
        f = _ficha_exemplo()
        f.comprimento = 0
        erros = f.validar()
        self.assertTrue(any("comprimento" in e for e in erros))

    def test_validacao_comprimento_menor_largura(self):
        f = _ficha_exemplo()
        f.comprimento = 10
        f.largura = 20
        erros = f.validar()
        self.assertTrue(any("comprimento" in e for e in erros))

    def test_precisa_revisao_confidence_baixa(self):
        f = _ficha_exemplo()
        f.confidence = 0.5
        f.revisado_por_humano = False
        self.assertTrue(f.precisa_revisao())

    def test_nao_precisa_revisao_se_revisado(self):
        f = _ficha_exemplo()
        f.confidence = 0.3
        f.revisado_por_humano = True
        self.assertFalse(f.precisa_revisao())


class TestConversaoParaRobo(unittest.TestCase):

    def test_campos_mapeados_corretamente(self):
        f = _ficha_exemplo()
        robo = ficha_fase3_to_robo_dict(f)
        d = robo["dados"]

        self.assertEqual(d["nome"], "P1")
        self.assertEqual(d["comprimento"], "50.0")
        self.assertEqual(d["largura"], "20.0")
        self.assertEqual(d["altura"], "300.0")
        self.assertEqual(d["parafusos"]["par_1_2"], "8")
        self.assertEqual(d["grades"]["grade_1"], "8")
        self.assertEqual(d["grades"]["distancia_1"], "15")

    def test_obras_salvas_estrutura(self):
        fichas = [
            _ficha_exemplo("P1", "1", "TERREO"),
            _ficha_exemplo("P2", "2", "TERREO"),
            _ficha_exemplo("P1", "1", "1_PAVIMENTO"),
        ]
        obras = fichas_to_obras_salvas(fichas, "Obra Teste")
        self.assertIn("Obra Teste", obras)
        self.assertIn("TERREO", obras["Obra Teste"])
        self.assertIn("1_PAVIMENTO", obras["Obra Teste"])
        self.assertIn("1", obras["Obra Teste"]["TERREO"])
        self.assertIn("2", obras["Obra Teste"]["TERREO"])

    def test_pilares_salvos_chave_composta(self):
        fichas = [_ficha_exemplo("P1", "1", "TERREO")]
        salvos = fichas_to_pilares_salvos(fichas)
        self.assertIn("1_TERREO", salvos)


class TestPersistencia(unittest.TestCase):

    def test_salvar_e_carregar_json(self):
        fichas = [_ficha_exemplo("P1"), _ficha_exemplo("P2")]
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho = os.path.join(tmpdir, "fichas.json")
            salvar_fichas_json(fichas, caminho)
            carregadas = carregar_fichas_json(caminho)

        self.assertEqual(len(carregadas), 2)
        self.assertEqual(carregadas[0].id, "P1")
        self.assertEqual(carregadas[0].comprimento, 50.0)


class TestAdapterE2E(unittest.TestCase):

    def test_adapter_end_to_end(self):
        fichas = [
            _ficha_exemplo("P1", "1", "TERREO"),
            _ficha_exemplo("P2", "2", "TERREO"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            fichas_path = os.path.join(tmpdir, "fichas_fase3.json")
            salvar_fichas_json(fichas, fichas_path)

            output_path = os.path.join(tmpdir, "fase4")
            relatorio = adaptar_fase3_para_fase4(
                caminho_fichas=fichas_path,
                nome_obra="Obra Teste",
                pasta_saida=output_path,
            )

            self.assertEqual(relatorio["total"], 2)
            self.assertEqual(relatorio["validas"], 2)
            self.assertEqual(relatorio["com_erros"], 0)

            # Verificar arquivos gerados
            self.assertTrue(os.path.exists(os.path.join(output_path, "obras_salvas.json")))
            self.assertTrue(os.path.exists(os.path.join(output_path, "pilares_salvos.json")))
            self.assertTrue(os.path.exists(os.path.join(output_path, "pavimentos_lista.json")))

            # Validar estrutura do obras_salvas.json
            with open(os.path.join(output_path, "obras_salvas.json")) as fp:
                obras = json.load(fp)
            self.assertIn("Obra Teste", obras)
            self.assertIn("TERREO", obras["Obra Teste"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
