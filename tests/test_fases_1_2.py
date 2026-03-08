# -*- coding: utf-8 -*-
"""
Testes para Fases 1 e 2 do Pipeline GAP-5 - VERSAO FINAL
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    from phases.fase1_ingestao import (
        Fase1Ingestao, IngestaoResultado, DXFResultado, 
        PDFResultado, FotoResultado, Catalogo
    )
    from phases.fase2_triagem import (
        Fase2Triagem, TriagemResultado, IndiceEspacial
    )
    FASES_DISPONIVEIS = True
except ImportError as e:
    print(f"Aviso: Fases nao disponiveis: {e}")
    FASES_DISPONIVEIS = False


def criar_dxf_teste_simples(caminho: str) -> str:
    """Cria um arquivo DXF de teste simples usando ezdxf."""
    try:
        import ezdxf
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "VIGA"})
        msp.add_line((0, 100), (100, 100), dxfattribs={"layer": "VIGA"})
        msp.add_text("P1", dxfattribs={"layer": "PILAR"})
        msp.add_text("P2", dxfattribs={"layer": "PILAR"})
        doc.saveas(caminho)
        return caminho
    except ImportError:
        # DXF minimo manual
        dxf_content = """0
SECTION
2
HEADER
9
$ACADVER
1
AC1015
0
ENDSEC
0
SECTION
2
TABLES
0
TABLE
2
LAYER
0
LAYER
2
PILAR
70
0
62
7
6
CONTINUOUS
0
LAYER
2
VIGA
70
0
62
7
6
CONTINUOUS
0
ENDTAB
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
VIGA
10
0.0
20
0.0
11
100.0
21
0.0
0
LINE
8
VIGA
10
0.0
20
100.0
11
100.0
21
100.0
0
TEXT
8
PILAR
10
10.0
20
10.0
40
2.5
1
P1
0
TEXT
8
PILAR
10
50.0
20
10.0
40
2.5
1
P2
0
ENDSEC
0
EOF
"""
        with open(caminho, "w") as f:
            f.write(dxf_content)
        return caminho


@unittest.skipUnless(FASES_DISPONIVEIS, "Fases nao disponiveis")
class TestFase1Ingestao(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".vision", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.ingestao = Fase1Ingestao(self.temp_dir, self.db_path)
    
    def tearDown(self):
        self.ingestao.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_01_ingestar_dxf_extrai_entidades(self):
        dxf_path = os.path.join(self.temp_dir, "teste.dxf")
        criar_dxf_teste_simples(dxf_path)
        resultado = self.ingestao.ingestar_dxf(dxf_path)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.caminho, dxf_path)
        self.assertIsInstance(resultado.entidades, list)
    
    def test_02_ingestar_dxf_extrai_layers(self):
        dxf_path = os.path.join(self.temp_dir, "teste.dxf")
        criar_dxf_teste_simples(dxf_path)
        resultado = self.ingestao.ingestar_dxf(dxf_path)
        self.assertIsInstance(resultado.layers, list)
        self.assertGreater(len(resultado.layers), 0)
    
    def test_03_ingestar_dxf_extrai_blocks(self):
        dxf_path = os.path.join(self.temp_dir, "teste.dxf")
        criar_dxf_teste_simples(dxf_path)
        resultado = self.ingestao.ingestar_dxf(dxf_path)
        self.assertIsInstance(resultado.blocks, list)
    
    def test_04_ingestar_dxf_arquivo_inexistente(self):
        resultado = self.ingestao.ingestar_dxf("arquivo_inexistente.dxf")
        self.assertIsNotNone(resultado.erro)
    
    def test_05_ingestar_dxf_tipos_entidades(self):
        dxf_path = os.path.join(self.temp_dir, "teste.dxf")
        criar_dxf_teste_simples(dxf_path)
        resultado = self.ingestao.ingestar_dxf(dxf_path)
        tipos = set(e.get("tipo") for e in resultado.entidades)
        self.assertTrue(len(tipos) > 0)
    
    def test_06_ingestar_pdf_extrai_texto(self):
        pdf_path = os.path.join(self.temp_dir, "teste.pdf")
        with open(pdf_path, "w", encoding="utf-8") as f:
            f.write("TESTE PDF")
        resultado = self.ingestao.ingestar_pdf(pdf_path)
        self.assertIsNotNone(resultado)
    
    def test_07_ingestar_pdf_arquivo_inexistente(self):
        resultado = self.ingestao.ingestar_pdf("arquivo_inexistente.pdf")
        self.assertIsNotNone(resultado.erro)
    
    def test_08_catalogar_entidades_por_tipo(self):
        entidades = [
            {"tipo": "INSERT", "layer": "PILAR"},
            {"tipo": "LINE", "layer": "VIGA"},
            {"tipo": "HATCH", "layer": "LAJE"},
            {"tipo": "TEXT", "layer": "TEXTO"},
            {"tipo": "DIMENSION", "layer": "COTA"},
        ]
        catalogo = self.ingestao.catalogar_entidades(entidades)
        self.assertIsInstance(catalogo, Catalogo)
        self.assertEqual(len(catalogo.pilares), 1)
        self.assertEqual(len(catalogo.vigas), 1)
    
    def test_09_catalogar_entidades_total(self):
        entidades = [
            {"tipo": "INSERT", "layer": "PILAR"},
            {"tipo": "INSERT", "layer": "PILAR"},
            {"tipo": "LINE", "layer": "VIGA"},
        ]
        catalogo = self.ingestao.catalogar_entidades(entidades)
        self.assertEqual(catalogo.total_entidades(), 3)
    
    def test_10_catalogar_entidades_camadas(self):
        entidades = [
            {"tipo": "LINE", "layer": "ESTRUTURA_PILAR"},
            {"tipo": "LINE", "layer": "PILARES"},
        ]
        catalogo = self.ingestao.catalogar_entidades(entidades)
        self.assertEqual(len(catalogo.pilares), 2)
    
    def test_11_executar_ingestao_completa(self):
        dxf_path = os.path.join(self.temp_dir, "teste.dxf")
        criar_dxf_teste_simples(dxf_path)
        resultado = self.ingestao.executar("obra_teste")
        self.assertIsInstance(resultado, IngestaoResultado)
        self.assertGreater(resultado.tempo_total_seg, 0)
    
    def test_12_executar_diretorio_inexistente(self):
        ingestao = Fase1Ingestao("/diretorio/inexistente", self.db_path)
        resultado = ingestao.executar()
        self.assertGreater(len(resultado.erros), 0)
        ingestao.close()


@unittest.skipUnless(FASES_DISPONIVEIS, "Fases nao disponiveis")
class TestFase2Triagem(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".vision", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.triagem = Fase2Triagem(self.temp_dir, self.db_path)
        # Criar tabela
        self.triagem.conn.execute("""
            CREATE TABLE IF NOT EXISTS dxf_entidades (
                id TEXT PRIMARY KEY, obra_id TEXT, tipo TEXT, layer TEXT, 
                dados_json TEXT, posicao_x REAL, posicao_y REAL
            )
        """)
        self.triagem.conn.commit()
        self._inserir_dados_teste()
    
    def tearDown(self):
        self.triagem.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _inserir_dados_teste(self):
        cursor = self.triagem.conn
        cursor.execute("""
            INSERT INTO dxf_entidades (id, obra_id, tipo, layer, dados_json, posicao_x, posicao_y)
            VALUES 
                ('ent_1', 'obra_1', 'INSERT', 'PILAR', '{"conteudo": "P1"}', 10.0, 10.0),
                ('ent_2', 'obra_1', 'INSERT', 'PILAR', '{"conteudo": "P2"}', 50.0, 10.0),
                ('ent_3', 'obra_1', 'LINE', 'VIGA', '{}', 0.0, 0.0),
                ('ent_4', 'obra_1', 'LINE', 'VIGA_P-1', '{}', 0.0, 100.0),
                ('ent_5', 'obra_1', 'TEXT', 'TEXTO', '{"conteudo": "P1"}', 12.0, 12.0),
                ('ent_6', 'obra_1', 'HATCH', 'LAJE', '{}', 50.0, 50.0)
        """)
        cursor.commit()
    
    def test_13_separar_pavimentos_por_layer(self):
        entidades = [{"layer": "P-1_VIGA"}, {"layer": "P-2_VIGA"}, {"layer": "TERREO_PILAR"}]
        pavimentos = self.triagem.separar_pavimentos(entidades)
        self.assertIsInstance(pavimentos, dict)
        self.assertGreater(len(pavimentos), 0)
    
    def test_14_separar_pavimentos_detecta_padroes(self):
        entidades = [{"layer": "P1_ESTRUTURA"}, {"layer": "P2_ESTRUTURA"}]
        pavimentos = self.triagem.separar_pavimentos(entidades)
        self.assertGreater(len(pavimentos), 1)
    
    def test_15_limpar_layers_padroniza(self):
        entidades = [{"layer": "Pilar"}, {"layer": "PILARES"}, {"layer": "LAJE@1"}]
        entidades_limpa = self.triagem.limpar_layers(entidades)
        for ent in entidades_limpa:
            self.assertIn("layer", ent)
            self.assertIn("layer_original", ent)
    
    def test_16_limpar_layers_mapeia_equivalentes(self):
        entidades = [{"layer": "PILARES"}, {"layer": "VIGAS"}]
        entidades_limpa = self.triagem.limpar_layers(entidades)
        layers = [e["layer"] for e in entidades_limpa]
        self.assertIn("PILAR", layers)
        self.assertIn("VIGA", layers)
    
    def test_17_nomear_entidades_associa_textos(self):
        entidades = [{"id": "e1", "posicao_x": 10.0, "posicao_y": 10.0}]
        textos = [{"conteudo": "P1", "posicao_x": 12.0, "posicao_y": 12.0}]
        entidades_nomeadas = self.triagem.nomear_entidades(entidades, textos)
        self.assertEqual(len(entidades_nomeadas), 1)
    
    def test_18_nomear_entidades_calcula_distancia(self):
        entidades = [{"id": "e1", "posicao_x": 0.0, "posicao_y": 0.0}]
        textos = [{"conteudo": "P1", "posicao_x": 3.0, "posicao_y": 4.0}]
        entidades_nomeadas = self.triagem.nomear_entidades(entidades, textos)
        distancias = [e.get("distancia_nome") for e in entidades_nomeadas if e.get("distancia_nome")]
        self.assertGreater(len(distancias), 0)
    
    def test_19_criar_indice_espacial_funciona(self):
        entidades = [{"id": "e1", "posicao_x": 10.0, "posicao_y": 10.0}]
        indice = self.triagem.criar_indice_espacial(entidades)
        self.assertIsInstance(indice, IndiceEspacial)
    
    def test_20_indice_espacial_consulta(self):
        indice = IndiceEspacial()
        indice.inserir("e1", (0, 0, 10, 10))
        indice.inserir("e2", (50, 50, 60, 60))
        resultados = indice.consultar((0, 0, 20, 20))
        self.assertIn("e1", resultados)
        self.assertNotIn("e2", resultados)
    
    def test_21_indice_espacial_salvar_carregar(self):
        indice = IndiceEspacial()
        indice.inserir("e1", (0, 0, 10, 10))
        path = os.path.join(self.temp_dir, "indice.json")
        indice.salvar(path)
        indice2 = IndiceEspacial()
        indice2.carregar(path)
        self.assertEqual(len(indice2), len(indice))
    
    def test_22_detectar_detalhes_identifica(self):
        entidades = [{"layer": "DETALHE_ESCADARIA"}, {"layer": "VIGA"}]
        detalhes = self.triagem.detectar_detalhes(entidades)
        self.assertGreaterEqual(len(detalhes), 1)


@unittest.skipUnless(FASES_DISPONIVEIS, "Fases nao disponiveis")
class TestIntegracaoFases12(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".vision", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.dxf_path = os.path.join(self.temp_dir, "estrutura.dxf")
        criar_dxf_teste_simples(self.dxf_path)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_23_integracao_ingestao_triagem(self):
        ingestao = Fase1Ingestao(self.temp_dir, self.db_path)
        resultado_ingestao = ingestao.executar("obra_teste")
        ingestao.close()
        self.assertIsInstance(resultado_ingestao, IngestaoResultado)
        
        triagem = Fase2Triagem(self.temp_dir, self.db_path)
        resultado_triagem = triagem.executar("obra_teste")
        triagem.close()
        self.assertIsInstance(resultado_triagem, TriagemResultado)
    
    def test_24_integracao_dados_persistidos(self):
        ingestao = Fase1Ingestao(self.temp_dir, self.db_path)
        ingestao.executar("obra_teste")
        ingestao.close()
        
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dxf_entidades")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
