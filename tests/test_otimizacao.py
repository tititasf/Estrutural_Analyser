# -*- coding: utf-8 -*-
"""
Testes de Benchmark e Otimização - SPRINT 13
Objetivo: Reduzir tempo do pipeline de 20min para < 5min
"""

import os
import sys
import time
import tempfile
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, Any, List
import json

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

# Imports das classes otimizadas
try:
    from phases.fase1_ingestao import Fase1Ingestao, processar_dxf_individual
    from core.cache import DXFCache, PipelineCache
    from orchestrator.pipeline_orchestrator import PipelineOrchestrator
    FASES_DISPONIVEIS = True
except ImportError as e:
    FASES_DISPONIVEIS = False
    print(f"Aviso: Algumas classes não disponíveis: {e}")


class TestBenchmarkIngestao:
    """Benchmarks para Fase 1 - Ingestão."""
    
    @pytest.fixture
    def temp_dir(self):
        """Cria diretório temporário para testes."""
        dirpath = tempfile.mkdtemp(prefix="benchmark_")
        yield dirpath
        shutil.rmtree(dirpath, ignore_errors=True)
    
    @pytest.fixture
    def db_path(self, temp_dir):
        """Cria banco de dados temporário."""
        return os.path.join(temp_dir, "test.vision")
    
    @pytest.fixture
    def dxf_files(self, temp_dir):
        """Cria arquivos DXF de teste."""
        if not FASES_DISPONIVEIS:
            return []
        
        try:
            import ezdxf
        except ImportError:
            return []
        
        files = []
        for i in range(10):
            dxf_path = os.path.join(temp_dir, f"test_{i}.dxf")
            doc = ezdxf.new()
            msp = doc.modelspace()
            
            # Adicionar entidades
            for j in range(100):
                msp.add_line((j, j), (j + 10, j + 10))
                msp.add_text(f"Texto {j}", dxfattribs={"height": 2.5})
            
            doc.saveas(dxf_path)
            files.append(dxf_path)
        
        return files
    
    def test_processamento_sequencial(self, temp_dir, db_path, dxf_files):
        """Benchmark: Processamento sequencial de DXFs."""
        if not dxf_files or not FASES_DISPONIVEIS:
            pytest.skip(" ezdxf não disponível")
        
        inicio = time.time()
        
        for dxf_path in dxf_files:
            processar_dxf_individual(dxf_path, usar_cache=False)
        
        tempo_sequencial = time.time() - inicio
        
        print(f"\nProcessamento sequencial: {len(dxf_files)} DXFs em {tempo_sequencial:.2f}s")
        print(f"Média: {tempo_sequencial/len(dxf_files):.3f}s por DXF")
        
        assert tempo_sequencial < 30, "Processamento sequencial muito lento"
    
    def test_processamento_paralelo(self, temp_dir, db_path, dxf_files):
        """Benchmark: Processamento paralelo de DXFs."""
        if not dxf_files or not FASES_DISPONIVEIS:
            pytest.skip(" ezdxf não disponível")
        
        from concurrent.futures import ProcessPoolExecutor, as_completed
        
        inicio = time.time()
        
        with ProcessPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(processar_dxf_individual, dxf_path, False, db_path)
                for dxf_path in dxf_files
            ]
            
            resultados = []
            for future in as_completed(futures):
                resultados.append(future.result())
        
        tempo_paralelo = time.time() - inicio
        
        print(f"\nProcessamento paralelo: {len(dxf_files)} DXFs em {tempo_paralelo:.2f}s")
        print(f"Média: {tempo_paralelo/len(dxf_files):.3f}s por DXF")
        
        assert tempo_paralelo < 30, "Processamento paralelo muito lento"
    
    def test_cache_hit(self, temp_dir, db_path, dxf_files):
        """Benchmark: Cache hit para DXF já processado."""
        if not dxf_files or not FASES_DISPONIVEIS:
            pytest.skip(" ezdxf não disponível")
        
        # Primeira execução (cache miss)
        inicio = time.time()
        resultado1 = processar_dxf_individual(dxf_files[0], usar_cache=True, db_path=db_path)
        tempo_miss = time.time() - inicio
        
        # Segunda execução (cache hit)
        inicio = time.time()
        resultado2 = processar_dxf_individual(dxf_files[0], usar_cache=True, db_path=db_path)
        tempo_hit = time.time() - inicio
        
        print(f"\nCache miss: {tempo_miss:.3f}s")
        print(f"Cache hit: {tempo_hit:.3f}s")
        print(f"Speedup: {tempo_miss/max(tempo_hit, 0.001):.1f}x")
        
        # Cache hit deve ser significativamente mais rápido
        assert tempo_hit < tempo_miss, "Cache hit não foi mais rápido que miss"
    
    def test_ingestao_completa(self, temp_dir, db_path, dxf_files):
        """Benchmark: Ingestão completa com cache."""
        if not dxf_files or not FASES_DISPONIVEIS:
            pytest.skip(" ezdxf não disponível")
        
        ingestao = Fase1Ingestao(temp_dir, db_path, usar_cache=True, num_workers=4)
        
        # Primeira execução
        inicio = time.time()
        resultado1 = ingestao.executar("obra_teste_1")
        tempo_1 = time.time() - inicio
        
        ingestao.close()
        
        # Segunda execução (com cache)
        ingestao2 = Fase1Ingestao(temp_dir, db_path, usar_cache=True, num_workers=4)
        
        inicio = time.time()
        resultado2 = ingestao2.executar("obra_teste_2")
        tempo_2 = time.time() - inicio
        
        ingestao2.close()
        
        print(f"\nIngestão completa (sem cache): {tempo_1:.2f}s")
        print(f"  Arquivos: {resultado1.arquivos_processados}")
        print(f"  Entidades: {resultado1.entidades_extraidas}")
        print(f"  Cache hits: {resultado1.cache_hits}")
        
        print(f"\nIngestão completa (com cache): {tempo_2:.2f}s")
        print(f"  Arquivos: {resultado2.arquivos_processados}")
        print(f"  Cache hits: {resultado2.cache_hits}")
        
        if tempo_1 > 0:
            speedup = tempo_1 / max(tempo_2, 0.01)
            print(f"\nSpeedup com cache: {speedup:.1f}x")


class TestBenchmarkCache:
    """Benchmarks para sistema de cache."""
    
    @pytest.fixture
    def temp_dir(self):
        """Cria diretório temporário para testes."""
        dirpath = tempfile.mkdtemp(prefix="cache_test_")
        yield dirpath
        shutil.rmtree(dirpath, ignore_errors=True)
    
    @pytest.fixture
    def db_path(self, temp_dir):
        """Cria banco de dados temporário."""
        return os.path.join(temp_dir, "cache_test.vision")
    
    def test_cache_dxf_set_get(self, temp_dir, db_path):
        """Benchmark: Operações set/get do cache DXF."""
        if not FASES_DISPONIVEIS:
            pytest.skip("Fases não disponíveis")
        
        cache = DXFCache(db_path)
        
        # Criar DXF de teste
        try:
            import ezdxf
            dxf_path = os.path.join(temp_dir, "test.dxf")
            doc = ezdxf.new()
            msp = doc.modelspace()
            for i in range(100):
                msp.add_line((i, i), (i + 10, i + 10))
            doc.saveas(dxf_path)
        except ImportError:
            pytest.skip(" ezdxf não disponível")
        
        entidades = [{"tipo": "LINE", "layer": "0"} for _ in range(100)]
        layers = ["0", "Layer1", "Layer2"]
        blocks = ["Block1", "Block2"]
        
        # Testar set
        inicio = time.time()
        cache.set(dxf_path, entidades, layers, blocks)
        tempo_set = time.time() - inicio
        
        # Testar get
        inicio = time.time()
        resultado = cache.get(dxf_path)
        tempo_get = time.time() - inicio
        
        print(f"\nCache set: {tempo_set:.3f}s")
        print(f"Cache get: {tempo_get:.3f}s")
        
        assert resultado is not None
        assert len(resultado["entidades"]) == 100
        
        cache.close()
    
    def test_cache_stats(self, db_path):
        """Test: Estatísticas do cache."""
        if not FASES_DISPONIVEIS:
            pytest.skip("Fases não disponíveis")
        
        cache = PipelineCache(db_path)
        stats = cache.get_stats()
        
        print(f"\nEstatísticas do cache: {json.dumps(stats, indent=2)}")
        
        cache.close()
        
        assert "dxf_cache" in stats


class TestBenchmarkOrchestrator:
    """Benchmarks para orchestrator com checkpoint/resume."""
    
    @pytest.fixture
    def temp_dir(self):
        """Cria diretório temporário para testes."""
        dirpath = tempfile.mkdtemp(prefix="orchestrator_test_")
        yield dirpath
        shutil.rmtree(dirpath, ignore_errors=True)
    
    @pytest.fixture
    def db_path(self, temp_dir):
        """Cria banco de dados temporário."""
        return os.path.join(temp_dir, "orchestrator_test.vision")
    
    def test_checkpoint_salvar_carregar(self, temp_dir, db_path):
        """Test: Salvar e carregar checkpoint."""
        if not FASES_DISPONIVEIS:
            pytest.skip("Fases não disponíveis")
        
        orchestrator = PipelineOrchestrator(db_path)
        
        # Registrar obra
        obra_id = orchestrator.registrar_obra("Teste", temp_dir)
        
        # Salvar checkpoint
        estado = {"progresso": 0.5, "arquivos_processados": 50}
        inicio = time.time()
        checkpoint_id = orchestrator.salvar_checkpoint(obra_id, 1, estado, 0.5)
        tempo_salvar = time.time() - inicio
        
        # Carregar checkpoint
        inicio = time.time()
        checkpoint = orchestrator.carregar_checkpoint(obra_id, 1)
        tempo_carregar = time.time() - inicio
        
        print(f"\nSalvar checkpoint: {tempo_salvar:.3f}s")
        print(f"Carregar checkpoint: {tempo_carregar:.3f}s")
        
        assert checkpoint is not None
        assert checkpoint["progresso"] == 0.5
        
        orchestrator.close()
    
    def test_performance_metrics(self, temp_dir, db_path):
        """Test: Métricas de performance."""
        if not FASES_DISPONIVEIS:
            pytest.skip("Fases não disponíveis")
        
        orchestrator = PipelineOrchestrator(db_path)
        obra_id = orchestrator.registrar_obra("Teste", temp_dir)
        
        # Simular execução de fase
        orchestrator._salvar_performance_metric(
            obra_id, 1, 
            tempo_total=10.5,
            arquivos=100,
            entidades=500,
            cache_hits=80,
            cache_misses=20,
            workers=4
        )
        
        # Obter métricas
        metrics = orchestrator.get_performance_metrics(obra_id)
        
        assert len(metrics) == 1
        assert metrics[0]["tempo_total_seg"] == 10.5
        assert metrics[0]["arquivos_processados"] == 100
        
        # Obter resumo
        resumo = orchestrator.get_performance_summary(obra_id)
        
        print(f"\nResumo de performance: {json.dumps(resumo, indent=2)}")
        
        assert resumo["total_tempo_seg"] == 10.5
        assert resumo["cache_hit_rate"] == 0.8
        
        orchestrator.close()


class TestBenchmarkIndicesSQLite:
    """Benchmarks para índices SQLite."""
    
    @pytest.fixture
    def temp_dir(self):
        """Cria diretório temporário para testes."""
        dirpath = tempfile.mkdtemp(prefix="sqlite_test_")
        yield dirpath
        shutil.rmtree(dirpath, ignore_errors=True)
    
    def test_query_com_indice(self, temp_dir):
        """Benchmark: Query com índice vs sem índice."""
        db_path = os.path.join(temp_dir, "index_test.db")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Criar tabela sem índice
        cursor.execute("""
            CREATE TABLE entidades_sem_indice (
                id INTEGER PRIMARY KEY,
                obra_id TEXT,
                tipo TEXT,
                dados TEXT
            )
        """)
        
        # Criar tabela com índice
        cursor.execute("""
            CREATE TABLE entidades_com_indice (
                id INTEGER PRIMARY KEY,
                obra_id TEXT,
                tipo TEXT,
                dados TEXT
            )
        """)
        cursor.execute("CREATE INDEX idx_obra_tipo ON entidades_com_indice(obra_id, tipo)")
        
        # Inserir dados
        dados = [(i % 100, f"tipo_{i % 10}", f"dados_{i}") for i in range(10000)]
        
        cursor.executemany(
            "INSERT INTO entidades_sem_indice (obra_id, tipo, dados) VALUES (?, ?, ?)",
            dados
        )
        cursor.executemany(
            "INSERT INTO entidades_com_indice (obra_id, tipo, dados) VALUES (?, ?, ?)",
            dados
        )
        conn.commit()
        
        # Query sem índice
        inicio = time.time()
        for _ in range(100):
            cursor.execute(
                "SELECT COUNT(*) FROM entidades_sem_indice WHERE obra_id = ? AND tipo = ?",
                (50, "tipo_5")
            )
            cursor.fetchone()
        tempo_sem_indice = time.time() - inicio
        
        # Query com índice
        inicio = time.time()
        for _ in range(100):
            cursor.execute(
                "SELECT COUNT(*) FROM entidades_com_indice WHERE obra_id = ? AND tipo = ?",
                (50, "tipo_5")
            )
            cursor.fetchone()
        tempo_com_indice = time.time() - inicio
        
        print(f"\nQuery sem índice: {tempo_sem_indice:.3f}s (100 iterações)")
        print(f"Query com índice: {tempo_com_indice:.3f}s (100 iterações)")
        
        if tempo_sem_indice > 0:
            speedup = tempo_sem_indice / max(tempo_com_indice, 0.001)
            print(f"Speedup com índice: {speedup:.1f}x")
        
        conn.close()
        
        assert tempo_com_indice <= tempo_sem_indice, "Índice não melhorou performance"


class TestBenchmarkMemoria:
    """Benchmarks para uso de memória."""
    
    @pytest.fixture
    def temp_dir(self):
        """Cria diretório temporário para testes."""
        dirpath = tempfile.mkdtemp(prefix="memoria_test_")
        yield dirpath
        shutil.rmtree(dirpath, ignore_errors=True)
    
    def test_memoria_peak(self, temp_dir):
        """Test: Medir pico de uso de memória."""
        try:
            import psutil
            process = psutil.Process()
            memoria_inicial = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            pytest.skip("psutil não disponível")
        
        # Simular processamento
        dados = []
        for i in range(1000):
            dados.append({"id": i, "dados": "x" * 1000})
        
        try:
            memoria_peak = process.memory_info().rss / 1024 / 1024  # MB
        except:
            memoria_peak = memoria_inicial + 10
        
        print(f"\nMemória inicial: {memoria_inicial:.1f} MB")
        print(f"Memória peak: {memoria_peak:.1f} MB")
        
        # Limpar memória
        del dados
        
        assert memoria_peak < 2000, "Uso de memória excedeu 2GB"


def run_benchmark_summary():
    """Executa resumo dos benchmarks."""
    print("\n" + "=" * 70)
    print("SPRINT 13 - BENCHMARK SUMMARY")
    print("=" * 70)
    print("\nObjetivo: Reduzir tempo do pipeline de 20min para < 5min\n")
    
    print("Otimizações implementadas:")
    print("  1. Processamento paralelo de DXFs (ProcessPoolExecutor)")
    print("  2. Cache de resultados (DXFCache, TransformationCache, FichaCache)")
    print("  3. Checkpoint/Resume por fase")
    print("  4. Índices SQLite para performance")
    print("  5. Bulk inserts para SQLite")
    print()
    
    print("Métricas esperadas:")
    print("  - Ingestão DXF: 4x mais rápido (7min -> ~2min)")
    print("  - Cache hit: 10-100x mais rápido que reprocessamento")
    print("  - Índices SQLite: 2-10x mais rápido em queries")
    print("  - Pipeline completo: < 5min para obra média")
    print()
    
    print("Para executar benchmarks completos:")
    print("  pytest tests/test_otimizacao.py -v --tb=short")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_benchmark_summary()
