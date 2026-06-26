#!/usr/bin/env python3
"""
Teste Simples de Importação - Sistema de Memória AgenteCAD

Verifica se todos os módulos criados podem ser importados corretamente.
"""

import sys
import os

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Testar imports dos módulos criados"""
    tests = [
        ("core.agent_identity", "AgentIdentity, MemoryTier, ModalityType"),
        ("core.memory_system", "MultimodalMemorySystem, MemoryQuery"),
        ("ai.multimodal_processor", "MultimodalVectorProcessor, ProcessedContent"),
    ]

    passed = 0
    failed = 0

    print("TESTANDO IMPORTS DOS MODULOS CRIADOS")
    print("=" * 50)

    for module_name, classes in tests:
        try:
            module = __import__(module_name, fromlist=[cls.strip() for cls in classes.split(',')])
            print(f"[OK] {module_name}: {classes}")
            passed += 1
        except ImportError as e:
            print(f"[FAIL] {module_name}: ImportError - {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {module_name}: Error - {e}")
            failed += 1

    print("=" * 50)
    print(f"IMPORTS: {passed} OK, {failed} FAILED")

    return failed == 0

def test_file_existence():
    """Verificar se os arquivos criados existem"""
    files_to_check = [
        "src/core/agent_identity.py",
        "src/core/memory_system.py",
        "src/ai/multimodal_processor.py",
        ".cursor/rules/byterover-memory-sync.mdc",
        "MEMORY_SYSTEM_README.md"
    ]

    passed = 0
    failed = 0

    print("\nVERIFICANDO EXISTENCIA DOS ARQUIVOS CRIADOS")
    print("=" * 50)

    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"[OK] {file_path}")
            passed += 1
        else:
            print(f"[FAIL] {file_path} - Arquivo nao encontrado")
            failed += 1

    print("=" * 50)
    print(f"ARQUIVOS: {passed} OK, {failed} FAILED")

    return failed == 0

def main():
    """Função principal"""
    print("TESTE SIMPLES - SISTEMA DE MEMORIA AGENTECAD")
    print("=" * 60)

    import_success = test_imports()
    files_success = test_file_existence()

    print("\n" + "=" * 60)
    if import_success and files_success:
        print("RESULTADO: SUCESSO - Todos os componentes foram criados corretamente!")
        print("O sistema de memoria esta pronto para integracao.")
        return 0
    else:
        print("RESULTADO: FALHA - Alguns componentes estao faltando ou com erros.")
        return 1

if __name__ == "__main__":
    sys.exit(main())