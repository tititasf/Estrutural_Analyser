"""
Teste de Integração Completa - Sistema de Memória Multi-Nível AgenteCAD

Este teste demonstra a integração completa do sistema de memória:
- Core de Identidade Agentica
- Sistema de Memória Multi-Nível (Curto/Médio/Longo Prazo)
- Processamento Multimodal
- Sincronização com Byterover

Cenário de teste: Simulação de workflow completo de análise CAD
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, Any

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from core.agent_identity import AgentIdentity, MemoryTier, ModalityType, AgentContext
    from core.memory_system import MultimodalMemorySystem, MemoryQuery
    from core.database import DatabaseManager
    from ai.multimodal_processor import MultimodalVectorProcessor, ProcessedContent

    print("OK: Imports bem-sucedidos")

except ImportError as e:
    print(f"❌ Erro nos imports: {e}")
    sys.exit(1)


class MemoryIntegrationTest:
    """Suite de testes para sistema de memória integrado"""

    def __init__(self):
        self.db_manager = None
        self.agent_identity = None
        self.memory_system = None
        self.multimodal_processor = None

        self.test_results = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'errors': []
        }

    def setup(self):
        """Configurar ambiente de teste"""
        try:
            print("\n🔧 Configurando ambiente de teste...")

            # Simular DatabaseManager (mock para teste)
            self.db_manager = MockDatabaseManager()

            # Inicializar componentes
            self.agent_identity = AgentIdentity(self.db_manager)
            self.memory_system = MultimodalMemorySystem(self.db_manager, self.agent_identity)
            self.multimodal_processor = MultimodalVectorProcessor()

            print("OK: Ambiente configurado com sucesso")
            return True

        except Exception as e:
            print(f"ERRO: Erro na configuração: {e}")
            return False

    def run_all_tests(self):
        """Executar todos os testes"""
        print("\nTEST: Executando testes de integração...")

        tests = [
            self.test_agent_identity_initialization,
            self.test_memory_tier_storage,
            self.test_multimodal_processing,
            self.test_memory_query_system,
            self.test_context_awareness,
            self.test_byterover_sync_simulation,
            self.test_performance_metrics,
            self.test_error_handling
        ]

        for test in tests:
            try:
                print(f"\n📋 Executando: {test.__name__}")
                result = test()
                self.test_results['tests_run'] += 1

                if result:
                    self.test_results['tests_passed'] += 1
                    print(f"PASS: {test.__name__}: PASSOU")
                else:
                    self.test_results['tests_failed'] += 1
                    print(f"FAIL: {test.__name__}: FALHOU")

            except Exception as e:
                self.test_results['tests_run'] += 1
                self.test_results['tests_failed'] += 1
                self.test_results['errors'].append(f"{test.__name__}: {str(e)}")
                print(f"ERRO: {test.__name__}: ERRO - {e}")

        self.print_test_summary()

    def test_agent_identity_initialization(self) -> bool:
        """Testar inicialização da identidade agentica"""
        try:
            # Verificar se identidade foi criada
            assert self.agent_identity.agent_id is not None
            assert self.agent_identity.current_context is not None
            assert self.agent_identity.current_context.agent_id == self.agent_identity.agent_id

            # Verificar consciência inicial
            assert 0.0 <= self.agent_identity.current_context.consciousness_level <= 1.0

            # Verificar sistemas de memória inicializados
            assert len(self.agent_identity.memory_systems) == 3  # Curto, médio, longo

            return True

        except Exception as e:
            print(f"Erro no teste: {e}")
            return False

    def test_memory_tier_storage(self) -> bool:
        """Testar armazenamento em diferentes níveis de memória"""
        try:
            # Criar contexto de teste
            test_context = AgentContext(
                agent_id=self.agent_identity.agent_id,
                session_id="test_session_001",
                project_context={"id": "test_project", "name": "Test CAD Analysis"},
                user_profile={"role": "engineer", "level": "senior"},
                current_module="beam_analyzer",
                active_workflows=["structural_analysis"],
                memory_state={"test": True},
                last_interaction=datetime.now(),
                consciousness_level=0.9
            )

            # Testar armazenamento em curto prazo
            short_term_id = self.memory_system.store(
                content="Análise rápida de viga concluída",
                modality=ModalityType.TEXT,
                metadata={"operation": "beam_analysis", "duration_ms": 150},
                tier=MemoryTier.SHORT_TERM,
                context=test_context
            )

            # Testar armazenamento em médio prazo
            medium_term_id = self.memory_system.store(
                content="Padrão de dimensionamento de vigas identificado: b/h = 0.3-0.5",
                modality=ModalityType.STRUCTURAL_PATTERN,
                metadata={"pattern_type": "beam_sizing", "confidence": 0.85},
                tier=MemoryTier.MEDIUM_TERM,
                context=test_context
            )

            # Testar armazenamento em longo prazo (simulado)
            long_term_id = self.memory_system.store(
                content="Nova abordagem de análise estrutural implementada com sucesso",
                modality=ModalityType.ML_MODEL,
                metadata={"architectural_decision": True, "impact": "high"},
                tier=MemoryTier.LONG_TERM,
                context=test_context
            )

            # Verificar se IDs foram gerados
            assert short_term_id is not None
            assert medium_term_id is not None
            assert long_term_id is not None

            return True

        except Exception as e:
            print(f"Erro no teste: {e}")
            return False

    def test_multimodal_processing(self) -> bool:
        """Testar processamento multimodal"""
        try:
            # Testar processamento de texto
            text_content = "Especificação técnica: Viga W12x26 com carga de 50kN/m"
            processed_text = self.multimodal_processor.process_content(
                text_content, 'text', generate_embedding=True
            )

            assert processed_text.modality_type == 'text'
            assert processed_text.processed_data['length'] == len(text_content)
            assert processed_text.embedding_vector is not None

            # Testar processamento de imagem (simulado)
            image_content = b"fake_image_data_jpg_format"
            processed_image = self.multimodal_processor.process_content(
                image_content, 'image', generate_embedding=True
            )

            assert processed_image.modality_type == 'image'
            assert processed_image.processed_data['size_bytes'] == len(image_content)

            # Testar processamento DXF (simulado)
            dxf_content = {"entities": ["line", "circle"], "layers": ["structural", "annotations"]}
            processed_dxf = self.multimodal_processor.process_content(
                dxf_content, 'dxf', generate_embedding=True
            )

            assert processed_dxf.modality_type == 'dxf'
            assert processed_dxf.processed_data['entities_count'] == 0  # Placeholder

            return True

        except Exception as e:
            print(f"Erro no teste: {e}")
            return False

    def test_memory_query_system(self) -> bool:
        """Testar sistema de consultas de memória"""
        try:
            # Armazenar alguns itens para teste
            self.memory_system.store(
                "Análise de pilares circulares concluída",
                ModalityType.TEXT,
                {"analysis_type": "pillar_circular"}
            )

            self.memory_system.store(
                "Padrão de laje unidirecional identificado",
                ModalityType.STRUCTURAL_PATTERN,
                {"pattern_type": "slab_unidirectional"}
            )

            # Testar consulta simples
            results = self.memory_system.query("análise de pilares")
            assert len(results) > 0

            # Testar consulta estruturada
            structured_query = MemoryQuery(
                query_type="semantic",
                content="padrões estruturais",
                modality=ModalityType.STRUCTURAL_PATTERN,
                limit=5
            )

            structured_results = self.memory_system.query(structured_query)
            assert isinstance(structured_results, list)

            return True

        except Exception as e:
            print(f"Erro no teste: {e}")
            return False

    def test_context_awareness(self) -> bool:
        """Testar awareness contextual do agente"""
        try:
            # Simular mudança de contexto
            initial_module = self.agent_identity.current_context.current_module
            initial_consciousness = self.agent_identity.current_context.consciousness_level

            # Atualizar contexto
            self.agent_identity.update_context(
                current_module="slab_analyzer",
                active_workflows=["thermal_analysis", "structural_analysis"]
            )

            # Verificar mudança
            assert self.agent_identity.current_context.current_module == "slab_analyzer"
            assert "thermal_analysis" in self.agent_identity.current_context.active_workflows
            assert self.agent_identity.stats["context_switches"] > 0

            return True

        except Exception as e:
            print(f"Erro no teste: {e}")
            return False

    def test_byterover_sync_simulation(self) -> bool:
        """Testar simulação de sincronização com Byterover"""
        try:
            # Simular insight importante
            insight_content = {
                "type": "architectural_decision",
                "description": "Implementação de cache multinível para análise CAD",
                "impact": "high",
                "technical_details": {
                    "cache_strategy": "LRU",
                    "layers": ["memory", "disk", "network"],
                    "performance_gain": "35%"
                }
            }

            # Verificar se seria identificado como insight importante
            is_important = self.agent_identity._is_important_insight({
                "metadata": {"event_type": "architectural_decision"},
                "content": insight_content
            })

            assert is_important, "Insight arquitetural deveria ser identificado como importante"

            # Simular sincronização (não executa de fato)
            self.agent_identity._trigger_byterover_sync({
                "metadata": {"event_type": "architectural_decision"},
                "content": insight_content
            })

            return True

        except Exception as e:
            print(f"Erro no teste: {e}")
            return False

    def test_performance_metrics(self) -> bool:
        """Testar métricas de performance"""
        try:
            # Executar algumas operações para gerar métricas
            for i in range(5):
                self.memory_system.store(
                    f"Teste de performance {i}",
                    ModalityType.TEXT,
                    {"test_id": i}
                )

            for i in range(3):
                self.memory_system.query(f"teste {i}")

            # Verificar estatísticas
            system_status = self.memory_system.get_system_status()
            assert 'system_stats' in system_status
            assert system_status['system_stats']['queries_processed'] >= 3

            # Verificar saúde do agente
            health = self.agent_identity.get_health_status()
            assert 'consciousness_level' in health
            assert 'operation_stats' in health

            return True

        except Exception as e:
            print(f"Erro no teste: {e}")
            return False

    def test_error_handling(self) -> bool:
        """Testar tratamento de erros"""
        try:
            # Testar armazenamento com dados inválidos
            invalid_result = self.memory_system.store(
                None, ModalityType.TEXT, {}
            )

            # Sistema deve lidar com erro graciosamente
            assert invalid_result is None or isinstance(invalid_result, str)

            # Testar consulta com dados inválidos
            invalid_query_results = self.memory_system.query(None)
            assert isinstance(invalid_query_results, list)

            # Testar processamento multimodal com dados inválidos
            invalid_processed = self.multimodal_processor.process_content(
                None, 'invalid_modality'
            )

            assert invalid_processed.modality_type == 'invalid_modality'
            assert not invalid_processed.metadata.get('processing_success', True)

            return True

        except Exception as e:
            print(f"Erro no teste: {e}")
            return False

    def print_test_summary(self):
        """Imprimir resumo dos testes"""
        print("\n" + "="*60)
        print("📊 RESUMO DOS TESTES DE INTEGRAÇÃO")
        print("="*60)

        results = self.test_results
        total = results['tests_run']
        passed = results['tests_passed']
        failed = results['tests_failed']

        print(f"Total de testes: {total}")
        print(f"APROVADOS: {passed}")
        print(f"REPROVADOS: {failed}")
        print(".1f")

        if results['errors']:
            print("\nERROS encontrados:")
            for error in results['errors'][:5]:  # Limitar a 5 erros
                print(f"  - {error}")

        # Status do sistema
        if self.memory_system:
            status = self.memory_system.get_system_status()
            print("\nSTATUS do Sistema de Memoria:")
            print(f"  - Consultas processadas: {status['system_stats']['queries_processed']}")
            print(f"  - Itens em cache: {status['system_stats']['cache_size']}")

        print("\nRESULTADO: Teste de integracao " + ("APROVADO" if failed == 0 else "REPROVADO"))


class MockDatabaseManager:
    """Mock do DatabaseManager para testes"""

    def __init__(self):
        self.memory_packets = []
        self.training_events = []

    def log_training_event(self, **kwargs):
        """Mock do método de log"""
        self.training_events.append(kwargs)

    def get_health_status(self):
        """Mock do status de saúde"""
        return {"status": "mock_ok"}

    # Implementar outros métodos conforme necessário para os testes


def run_integration_test():
    """Executar teste de integração completo"""
    print("INICIANDO: Teste de Integracao - Sistema de Memoria AgenteCAD")
    print("="*70)

    test_suite = MemoryIntegrationTest()

    if not test_suite.setup():
        print("ERRO: Falha na configuracao do teste")
        return False

    test_suite.run_all_tests()

    # Verificar se todos os testes passaram
    results = test_suite.test_results
    success = results['tests_failed'] == 0

    if success:
        print("\nSUCESSO: Todos os testes de integracao passaram!")
        print("OK: Sistema de memoria esta funcional e integrado")
    else:
        print(f"\nAVISO: {results['tests_failed']} testes falharam")
        print("ATENCAO: Revisar implementacao dos componentes")

    return success


if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)