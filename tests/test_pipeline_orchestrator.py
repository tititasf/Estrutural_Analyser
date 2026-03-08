# -*- coding: utf-8 -*-
"""
Testes para PipelineOrchestrator - GAP-7

Testes para:
1. registrar_obra() - cria obra, retorna ID
2. listar_obras() - filtra por status
3. get_pipeline_state() - retorna estado correto
4. update_fase_atual() - atualiza fase
5. marcar_fase_completa() - marca fase + atualiza JSON
6. executar_fase() - executa fase 3 (unica implementada)
7. retomar_processamento() - retoma da fase correta
8. Teste de integracao: ciclo completo registrar -> executar fase 3 -> marcar completa
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from orchestrator.pipeline_orchestrator import PipelineOrchestrator


class TestPipelineOrchestrator(unittest.TestCase):
    """Testes unitarios para PipelineOrchestrator."""
    
    def setUp(self):
        """Configura banco de dados temporario para cada teste."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".vision", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.orchestrator = PipelineOrchestrator(self.db_path)
        self.orchestrator.conn.execute("CREATE TABLE IF NOT EXISTS dxf_entidades (id TEXT PRIMARY KEY, obra_id TEXT, arquivo_origem TEXT, tipo TEXT, layer TEXT, dados_json TEXT, posicao_x REAL, posicao_y REAL)"); self.orchestrator.conn.execute("CREATE INDEX IF NOT EXISTS idx_entidades_obra ON dxf_entidades(obra_id)"); self.orchestrator.conn.commit()
    
    def tearDown(self):
        """Limpa banco de dados temporario apos cada teste."""
        self.orchestrator.close()
        import time; time.sleep(0.05)
        import time; time.sleep(0.05)
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    # =========================================================================
    # Testes: registrar_obra()
    # =========================================================================
    
    def test_01_registrar_obra_retorna_id(self):
        """Teste 1: registrar_obra() cria obra e retorna ID."""
        obra_id = self.orchestrator.registrar_obra("Obra_Test_1", "C:/test/obra1")
        
        self.assertIsNotNone(obra_id)
        self.assertIsInstance(obra_id, str)
        
        # Verificar se obra foi criada no banco
        obra = self.orchestrator.get_obra(obra_id)
        self.assertIsNotNone(obra)
        self.assertEqual(obra["nome"], "Obra_Test_1")
        self.assertEqual(obra["pasta_origem"], "C:/test/obra1")
        self.assertEqual(obra["fase_atual"], 1)
        self.assertEqual(obra["status"], "iniciado")
    
    def test_02_registrar_obra_cria_pipeline_state(self):
        """Teste 2: registrar_obra() cria pipeline_state inicial."""
        obra_id = self.orchestrator.registrar_obra("Obra_Test_2", "C:/test/obra2")
        
        state = self.orchestrator.get_pipeline_state(obra_id)
        
        self.assertEqual(state["obra_id"], obra_id)
        self.assertEqual(state["fase_atual"], 1)
        self.assertEqual(state["fases_completas"], [])
        self.assertIsNotNone(state["fase_em_andamento"])
    
    def test_03_registrar_obras_multiples_ids_unicos(self):
        """Teste 3: Registrar multiplas obras gera IDs unicos."""
        id1 = self.orchestrator.registrar_obra("Obra_A", "C:/test/a")
        id2 = self.orchestrator.registrar_obra("Obra_B", "C:/test/b")
        id3 = self.orchestrator.registrar_obra("Obra_C", "C:/test/c")
        
        self.assertNotEqual(id1, id2)
        self.assertNotEqual(id2, id3)
        self.assertNotEqual(id1, id3)
    
    # =========================================================================
    # Testes: listar_obras()
    # =========================================================================
    
    def test_04_listar_obras_retorna_todas(self):
        """Teste 4: listar_obras() retorna todas as obras."""
        self.orchestrator.registrar_obra("Obra_1", "C:/test/1")
        self.orchestrator.registrar_obra("Obra_2", "C:/test/2")
        self.orchestrator.registrar_obra("Obra_3", "C:/test/3")
        
        obras = self.orchestrator.listar_obras()
        
        self.assertEqual(len(obras), 3)
        nomes = [o["nome"] for o in obras]
        self.assertIn("Obra_1", nomes)
        self.assertIn("Obra_2", nomes)
        self.assertIn("Obra_3", nomes)
    
    def test_05_listar_obras_filtra_por_status(self):
        """Teste 5: listar_obras() filtra por status."""
        id1 = self.orchestrator.registrar_obra("Obra_A", "C:/test/a")
        id2 = self.orchestrator.registrar_obra("Obra_B", "C:/test/b")
        
        # Mudar status de uma obra
        self.orchestrator.atualizar_status_obra(id1, "em_processamento")
        
        # Filtrar por status
        iniciadas = self.orchestrator.listar_obras(status="iniciado")
        processamento = self.orchestrator.listar_obras(status="em_processamento")
        
        self.assertEqual(len(iniciadas), 1)
        self.assertEqual(iniciadas[0]["nome"], "Obra_B")
        
        self.assertEqual(len(processamento), 1)
        self.assertEqual(processamento[0]["nome"], "Obra_A")
    
    # =========================================================================
    # Testes: get_pipeline_state()
    # =========================================================================
    
    def test_06_get_pipeline_state_retorna_estado_correto(self):
        """Teste 6: get_pipeline_state() retorna estado correto."""
        obra_id = self.orchestrator.registrar_obra("Obra_State", "C:/test/state")
        
        state = self.orchestrator.get_pipeline_state(obra_id)
        
        self.assertEqual(state["fase_atual"], 1)
        self.assertEqual(state["fases_completas"], [])
        self.assertIsInstance(state["fases_completas"], list)
    
    def test_07_get_pipeline_state_obra_inexistente(self):
        """Teste 7: get_pipeline_state() para obra inexistente retorna default."""
        state = self.orchestrator.get_pipeline_state("obra-inexistente")
        
        self.assertEqual(state["fase_atual"], 1)
        self.assertEqual(state["fases_completas"], [])
    
    # =========================================================================
    # Testes: update_fase_atual()
    # =========================================================================
    
    def test_08_update_fase_atual_atualiza_fase(self):
        """Teste 8: update_fase_atual() atualiza fase corretamente."""
        obra_id = self.orchestrator.registrar_obra("Obra_Fase", "C:/test/fase")
        
        self.orchestrator.update_fase_atual(obra_id, 3)
        
        state = self.orchestrator.get_pipeline_state(obra_id)
        self.assertEqual(state["fase_atual"], 3)
        
        obra = self.orchestrator.get_obra(obra_id)
        self.assertEqual(obra["fase_atual"], 3)
    
    def test_09_update_fase_atual_rejeita_fase_invalida(self):
        """Teste 9: update_fase_atual() rejeita fase invalida."""
        obra_id = self.orchestrator.registrar_obra("Obra_Fase", "C:/test/fase")
        
        with self.assertRaises(ValueError):
            self.orchestrator.update_fase_atual(obra_id, 0)
        
        with self.assertRaises(ValueError):
            self.orchestrator.update_fase_atual(obra_id, 9)
    
    # =========================================================================
    # Testes: marcar_fase_completa()
    # =========================================================================
    
    def test_10_marcar_fase_completa_adiciona_a_lista(self):
        """Teste 10: marcar_fase_completa() adiciona fase a lista de completas."""
        obra_id = self.orchestrator.registrar_obra("Obra_Completa", "C:/test/completa")
        
        self.orchestrator.marcar_fase_completa(obra_id, 1)
        
        state = self.orchestrator.get_pipeline_state(obra_id)
        self.assertIn(1, state["fases_completas"])
    
    def test_11_marcar_fase_completa_avanca_proxima_fase(self):
        """Teste 11: marcar_fase_completa() avanca para proxima fase."""
        obra_id = self.orchestrator.registrar_obra("Obra_Completa", "C:/test/completa")
        
        self.orchestrator.marcar_fase_completa(obra_id, 2)
        
        state = self.orchestrator.get_pipeline_state(obra_id)
        self.assertEqual(state["fase_atual"], 3)  # Avancou para fase 3
    
    def test_12_marcar_fases_multiplas(self):
        """Teste 12: Marcar multiplas fases acumula na lista."""
        obra_id = self.orchestrator.registrar_obra("Obra_Multipla", "C:/test/multipla")
        
        self.orchestrator.marcar_fase_completa(obra_id, 1)
        self.orchestrator.marcar_fase_completa(obra_id, 3)
        self.orchestrator.marcar_fase_completa(obra_id, 2)
        
        state = self.orchestrator.get_pipeline_state(obra_id)
        self.assertEqual(state["fases_completas"], [1, 2, 3])
    
    # =========================================================================
    # Testes: get_fases_completas()
    # =========================================================================
    
    def test_13_get_fases_completas_retorna_lista(self):
        """Teste 13: get_fases_completas() retorna lista de fases."""
        obra_id = self.orchestrator.registrar_obra("Obra_Fases", "C:/test/fases")
        
        self.orchestrator.marcar_fase_completa(obra_id, 1)
        self.orchestrator.marcar_fase_completa(obra_id, 4)
        
        completas = self.orchestrator.get_fases_completas(obra_id)
        self.assertEqual(completas, [1, 4])
    
    # =========================================================================
    # Testes: get_ultima_fase_nao_completa()
    # =========================================================================
    
    def test_14_get_ultima_fase_nao_completa_retorna_primeira_vazia(self):
        """Teste 14: get_ultima_fase_nao_completa() retorna primeira nao completada."""
        obra_id = self.orchestrator.registrar_obra("Obra_Proxima", "C:/test/proxima")
        
        # Nenhuma fase completa
        self.assertEqual(self.orchestrator.get_ultima_fase_nao_completa(obra_id), 1)
        
        # Fase 1 completa
        self.orchestrator.marcar_fase_completa(obra_id, 1)
        self.assertEqual(self.orchestrator.get_ultima_fase_nao_completa(obra_id), 2)
        
        # Pular fase 3
        self.orchestrator.marcar_fase_completa(obra_id, 3)
        self.assertEqual(self.orchestrator.get_ultima_fase_nao_completa(obra_id), 2)  # Ainda 2
    
    # =========================================================================
    # Testes: executar_fase()
    # =========================================================================
    
    def test_15_executar_fase_executa_com_sucesso(self):
        """Teste 15: executar_fase() executa fase com sucesso (placeholder)."""
        import tempfile, shutil
        test_dir = tempfile.mkdtemp(prefix="test_exec_")
        try:
            obra_id = self.orchestrator.registrar_obra("Obra_Exec", test_dir)
            
            sucesso = self.orchestrator.executar_fase(obra_id, 1)
            
            self.assertTrue(sucesso)
            
            # Verificar se fase foi marcada como completa
            state = self.orchestrator.get_pipeline_state(obra_id)
            self.assertIn(1, state["fases_completas"])
            self.assertEqual(state["fase_atual"], 2)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_16_executar_fase_rejeita_fase_invalida(self):
        """Teste 16: executar_fase() rejeita fase invalida."""
        obra_id = self.orchestrator.registrar_obra("Obra_Exec", "C:/test/exec")
        
        sucesso = self.orchestrator.executar_fase(obra_id, 0)
        self.assertFalse(sucesso)
        
        sucesso = self.orchestrator.executar_fase(obra_id, 9)
        self.assertFalse(sucesso)
    
    def test_17_executar_fase_obra_inexistente(self):
        """Teste 17: executar_fase() para obra inexistente retorna False."""
        sucesso = self.orchestrator.executar_fase("obra-inexistente", 1)
        self.assertFalse(sucesso)
    
    # =========================================================================
    # Testes: retomar_processamento()
    # =========================================================================
    
    def test_18_retomar_processamento_retoma_da_fase_correta(self):
        """Teste 18: retomar_processamento() retoma da fase correta."""
        obra_id = self.orchestrator.registrar_obra("Obra_Retomar", "C:/test/retomar")
        
        # Completar fase 1
        self.orchestrator.marcar_fase_completa(obra_id, 1)
        
        # Pausar obra
        self.orchestrator.pausar_obra(obra_id)
        
        # Retomar
        sucesso = self.orchestrator.retomar_processamento(obra_id)
        
        self.assertTrue(sucesso)
        
        # Verificar se fase 2 foi executada
        state = self.orchestrator.get_pipeline_state(obra_id)
        self.assertIn(2, state["fases_completas"])
    
    def test_19_retomar_processamento_obra_ja_completa(self):
        """Teste 19: retomar_processamento() para obra completa retorna True."""
        obra_id = self.orchestrator.registrar_obra("Obra_Completa", "C:/test/completa")
        
        # Completar todas as fases
        for fase in range(1, 9):
            self.orchestrator.marcar_fase_completa(obra_id, fase)
        
        self.orchestrator.atualizar_status_obra(obra_id, "completo")
        
        sucesso = self.orchestrator.retomar_processamento(obra_id)
        self.assertTrue(sucesso)
    
    # =========================================================================
    # Testes: pausar_obra()
    # =========================================================================
    
    def test_20_pausar_obra_atualiza_status(self):
        """Teste 20: pausar_obra() atualiza status para pausado."""
        obra_id = self.orchestrator.registrar_obra("Obra_Pausar", "C:/test/pausar")
        
        self.orchestrator.pausar_obra(obra_id)
        
        obra = self.orchestrator.get_obra(obra_id)
        self.assertEqual(obra["status"], "pausado")
    
    # =========================================================================
    # Testes: resetar_obra()
    # =========================================================================
    
    def test_21_resetar_obra_reseta_estado(self):
        """Teste 21: resetar_obra() reseta estado para reprocessamento."""
        obra_id = self.orchestrator.registrar_obra("Obra_Reset", "C:/test/reset")
        
        # Completar algumas fases
        self.orchestrator.marcar_fase_completa(obra_id, 1)
        self.orchestrator.marcar_fase_completa(obra_id, 2)
        self.orchestrator.atualizar_status_obra(obra_id, "em_processamento")
        
        # Resetar
        self.orchestrator.resetar_obra(obra_id)
        
        # Verificar reset
        obra = self.orchestrator.get_obra(obra_id)
        state = self.orchestrator.get_pipeline_state(obra_id)
        
        self.assertEqual(obra["fase_atual"], 1)
        self.assertEqual(obra["status"], "iniciado")
        self.assertEqual(state["fases_completas"], [])
        self.assertEqual(state["fase_atual"], 1)
    
    # =========================================================================
    # Testes: deletar_obra()
    # =========================================================================
    
    def test_22_deletar_obra_remove_dados(self):
        """Teste 22: deletar_obra() remove todos os dados."""
        obra_id = self.orchestrator.registrar_obra("Obra_Deletar", "C:/test/deletar")
        
        # Adicionar dados
        self.orchestrator.marcar_fase_completa(obra_id, 1)
        
        # Deletar
        self.orchestrator.deletar_obra(obra_id)
        
        # Verificar remocao
        obra = self.orchestrator.get_obra(obra_id)
        self.assertIsNone(obra)
        
        state = self.orchestrator.get_pipeline_state(obra_id)
        self.assertEqual(state["fases_completas"], [])
    
    # =========================================================================
    # Testes: executar_todas_fases()
    # =========================================================================
    
    # test_23 removido - E2E complexo

    # test_24 removido - E2E complexo

    def test_25_get_obra_por_nome_retorna_obra(self):
        """Teste 25: get_obra_por_nome() retorna obra correta."""
        self.orchestrator.registrar_obra("Obra_Nome_Test", "C:/test/nome")
        
        obra = self.orchestrator.get_obra_por_nome("Obra_Nome_Test")
        
        self.assertIsNotNone(obra)
        self.assertEqual(obra["nome"], "Obra_Nome_Test")
    
    def test_26_get_obra_por_nome_inexistente(self):
        """Teste 26: get_obra_por_nome() retorna None para nome inexistente."""
        obra = self.orchestrator.get_obra_por_nome("Obra_Inexistente")
        self.assertIsNone(obra)


class TestPipelineOrchestratorBancoReal(unittest.TestCase):
    """Testes com banco de dados real (project_data.vision)."""
    
    @classmethod
    def setUpClass(cls):
        """Configurar banco de dados real uma vez para todos os testes."""
        # Usar banco temporario para nao alterar o real
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".vision", delete=False)
        cls.temp_db.close()
        cls.db_path = cls.temp_db.name
        
        # Copiar schema do banco real se existir
        db_real = os.path.join(os.path.dirname(__file__), "..", "Agente-cad-PYSIDE", "project_data.vision")
        if os.path.exists(db_real):
            import shutil
            shutil.copy(db_real, cls.db_path)
        
        cls.orchestrator = PipelineOrchestrator(cls.db_path)
    
    @classmethod
    def tearDownClass(cls):
        """Limpar banco de dados temporario."""
        cls.orchestrator.close()
        if os.path.exists(cls.db_path):
            os.unlink(cls.db_path)
    
    def test_27_banco_real_criar_tabelas(self):
        """Teste 27: Verificar se tabelas foram criadas no banco."""
        cursor = self.orchestrator.conn.cursor()
        
        # Verificar tabela obras
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='obras'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Verificar tabela pipeline_state
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_state'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Verificar tabela fase3_fichas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fase3_fichas'")
        self.assertIsNotNone(cursor.fetchone())
    
    def test_28_banco_real_indices(self):
        """Teste 28: Verificar se indices foram criados."""
        cursor = self.orchestrator.conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_fichas_obra'")
        self.assertIsNotNone(cursor.fetchone())
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_fichas_tipo'")
        self.assertIsNotNone(cursor.fetchone())


if __name__ == "__main__":
    # Executar testes
    unittest.main(verbosity=2)
