# STORY RAG-6.0 — Operação segura e plugins de classe

**Status:** Concluída em 2026-06-27.

## Entrega

- Health check read-only para banco, FAISS, snapshots e memória visual.
- Export auditável com SHA-256, sem mutação das fontes.
- Registry de extratores e robôs para PIL/LV/FV/LAJ.
- Contrato base impede motor reverso novo de produzir T1/T2.
- Auditoria confirma módulos e callables reais das quatro classes.

## Gate

`test_rag_health_export.py`, `test_classe_registry.py` e
`test_robo_registry.py` aprovados.

## Pendente humano

A primeira classe nova só deve ser registrada após definição de semântica,
campos, exemplos e gates pelo dono.
