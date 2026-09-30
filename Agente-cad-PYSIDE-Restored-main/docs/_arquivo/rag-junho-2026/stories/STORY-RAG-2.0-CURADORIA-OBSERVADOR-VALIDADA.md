# STORY RAG-2.0 - Curadoria Observador Validada

## Status
Base read-only validada em 2026-06-27.

## Objetivo
Garantir que a Curadoria consiga ler o estado do cerebro RAG, expor pendencias e suportar
classe nova no `classe_registry`, sem escrever no banco.

## Execucao
- Validado `ProjectManager._collect_curadoria_rag_metrics`.
- Corrigido fallback para carregar `classe_registry.py` do repo principal quando o DB/obra
  esta em diretorio temporario ou separado.
- Mantido comportamento read-only: a coleta de metricas nao altera `project_data.vision`.

## Validacao
```powershell
python -m py_compile D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\src\ui\widgets\project_manager.py
python -m pytest tests\test_curadoria_rag_metrics.py
```

Resultado: 1 passed.

## Escopo Nao Validado Ainda
- Validacao visual manual da UI aberta na app.
- Clique em cada sub-aba da Curadoria dentro do PySide rodando.
- Acoes seguras futuras como `Indexar Validados Pendentes`.

## Nao Fazer
- Nao transformar a Curadoria Observador em tela que promove T1/T2.
- Nao adicionar botao de "indexar tudo".
- Nao escrever no RAG global a partir da coleta de metricas.
