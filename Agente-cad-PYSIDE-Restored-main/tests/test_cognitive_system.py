"""
Testes do Sistema Cognitivo

Valida funcionamento do CausalVectorEngine e Swarm Agents.
"""

import sys
import os

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_vector_trajectory():
    """Testa VectorTrajectory."""
    print("=" * 60)
    print("TESTE: VectorTrajectory")
    print("=" * 60)
    
    try:
        from cognitive.vector_trajectory import VectorTrajectory, TrajectoryPhase
        import numpy as np
        
        # Criar trajetoria
        traj = VectorTrajectory()
        print(f"[OK] Trajetoria criada: {traj.trajectory_id}")
        
        # Adicionar nos
        node1 = traj.append(
            phase=TrajectoryPhase.PERCEPTION,
            vector=np.random.randn(384),
            reasoning="Percepcao inicial",
            confidence=0.9
        )
        print(f"[OK] No 1 adicionado: {node1.phase.value}")
        
        node2 = traj.append(
            phase=TrajectoryPhase.INTERPRETATION,
            vector=np.random.randn(384),
            reasoning="Interpretacao",
            confidence=0.85
        )
        print(f"[OK] No 2 adicionado: {node2.phase.value}")
        
        # Validar cadeia
        is_valid, error = traj.validate_chain()
        print(f"[OK] Cadeia valida: {is_valid}")
        
        # Debug trail
        trail = traj.get_debug_trail()
        print(f"[OK] Debug trail com {len(trail)} passos")
        
        print("[SUCESSO] VectorTrajectory funcionando!")
        return True
        
    except Exception as e:
        print(f"[ERRO] {e}")
        return False


def test_causal_engine():
    """Testa CausalVectorEngine."""
    print("\n" + "=" * 60)
    print("TESTE: CausalVectorEngine")
    print("=" * 60)
    
    try:
        from cognitive.causal_engine import CausalVectorEngine
        
        # Criar engine
        engine = CausalVectorEngine()
        print("[OK] Engine criado")
        
        # Iniciar trajetoria
        traj = engine.start_trajectory({"query": "Teste"})
        print(f"[OK] Trajetoria iniciada: {traj.trajectory_id}")
        
        # Executar busca dialetica
        result = engine.dialectic_search("Como identificar um pilar?")
        print(f"[OK] Busca dialetica executada")
        print(f"    - Confianca: {result['confidence']:.2f}")
        print(f"    - Contexto denso: {len(result['dense_context'])} itens")
        
        # Debug info
        debug = engine.get_debug_info()
        if "error" not in debug:
            print(f"[OK] Debug info disponivel")
        
        print("[SUCESSO] CausalVectorEngine funcionando!")
        return True
        
    except Exception as e:
        print(f"[ERRO] {e}")
        return False


def test_rag_dialectic():
    """Testa RAGDialectic."""
    print("\n" + "=" * 60)
    print("TESTE: RAGDialectic")
    print("=" * 60)
    
    try:
        from cognitive.rag_dialectic import RAGDialectic
        
        # Criar RAG
        rag = RAGDialectic()
        print("[OK] RAGDialectic criado")
        
        # Executar processo dialetico
        result = rag.process("Como calcular area de laje?")
        print(f"[OK] Processo dialetico executado")
        print(f"    - Passos: {len(result.steps)}")
        print(f"    - Confianca: {result.overall_confidence:.2f}")
        
        # Verificar fases
        phases = [s.phase.value for s in result.steps]
        print(f"    - Fases: {phases}")
        
        print("[SUCESSO] RAGDialectic funcionando!")
        return True
        
    except Exception as e:
        print(f"[ERRO] {e}")
        return False


def test_swarm_agents():
    """Testa Swarm Agents."""
    print("\n" + "=" * 60)
    print("TESTE: Swarm Agents")
    print("=" * 60)
    
    try:
        from agents.swarm_orchestrator import SwarmOrchestrator
        
        # Criar orchestrator
        orchestrator = SwarmOrchestrator()
        print("[OK] SwarmOrchestrator criado")
        
        # Listar agentes
        agents = orchestrator.list_agents()
        print(f"[OK] {len(agents)} agentes registrados:")
        for agent in agents:
            print(f"    - {agent['name']} ({agent['role']})")
        
        # Criar task
        task = orchestrator.create_task(
            task_type="interpret_only",
            input_data={
                "elements": {
                    "pilares": [{"nome": "P-1", "dimensoes": {"largura": 40}}],
                    "vigas": [],
                    "lajes": []
                },
                "texts": []
            }
        )
        print(f"[OK] Task criada: {task.task_id}")
        
        # Executar task
        result = orchestrator.execute_task(task)
        print(f"[OK] Task executada: {result.status.value}")
        
        # Status do orchestrator
        status = orchestrator.get_status()
        print(f"[OK] Tasks completadas: {status['tasks_completed']}")
        
        print("[SUCESSO] Swarm Agents funcionando!")
        return True
        
    except Exception as e:
        print(f"[ERRO] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_pipeline():
    """Testa pipeline completo."""
    print("\n" + "=" * 60)
    print("TESTE: Pipeline Completo")
    print("=" * 60)
    
    try:
        from agents.swarm_orchestrator import SwarmOrchestrator
        
        orchestrator = SwarmOrchestrator()
        
        # Criar task de pipeline completo
        task = orchestrator.create_task(
            task_type="full_pipeline",
            input_data={
                "dxf_path": "test_structural.dxf",
                "output_format": "json"
            }
        )
        
        # Executar
        result = orchestrator.execute_task(task)
        
        print(f"[OK] Pipeline executado: {result.status.value}")
        
        if result.results:
            stages = result.results.get("stages", {})
            print(f"    - Stages executados: {list(stages.keys())}")
        
        print("[SUCESSO] Pipeline completo funcionando!")
        return True
        
    except Exception as e:
        print(f"[ERRO] {e}")
        return False


def main():
    """Executa todos os testes."""
    print("\n")
    print("=" * 60)
    print("TESTES DO SISTEMA COGNITIVO - AGENTECAD")
    print("=" * 60)
    
    results = []
    
    results.append(("VectorTrajectory", test_vector_trajectory()))
    results.append(("CausalVectorEngine", test_causal_engine()))
    results.append(("RAGDialectic", test_rag_dialectic()))
    results.append(("Swarm Agents", test_swarm_agents()))
    results.append(("Full Pipeline", test_full_pipeline()))
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "OK" if result else "FALHOU"
        print(f"  {name}: {status}")
    
    print("-" * 60)
    print(f"TOTAL: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\nSISTEMA COGNITIVO PRONTO PARA USO!")
        return 0
    else:
        print("\nALGUNS TESTES FALHARAM - VERIFICAR ERROS ACIMA")
        return 1


if __name__ == "__main__":
    sys.exit(main())
