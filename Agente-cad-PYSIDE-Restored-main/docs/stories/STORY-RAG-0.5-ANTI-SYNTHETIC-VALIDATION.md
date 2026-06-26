# STORY RAG-0.5 - Anti Synthetic Validation Guard

## Objetivo
Garantir que nenhum fluxo automatico, CLI, looper, agente ou script possa gravar dado como
validado por humano, promover T1/T2, tombstonar ou indexar no RAG global.

## Contexto
Os ciclos de treino CROP/A/B/C devem poder rodar livremente para explicar logicas,
gerar candidatos, medir scores e produzir artefatos. Isso e desejado. O risco e o mesmo
processo se passar por validacao humana e contaminar o RAG.

## Escopo implementado
- `scripts/rag_tier.py`
  - detecta marcadores de origem sintetica/maquina;
  - rebaixa payload aprovado por CLI/script/looper para T0;
  - exige origem humana explicita para T1.
- `scripts/rag_validation_events.py`
  - bloqueia validacao/desvalidacao se `validation_origin` nao for humano;
  - grava candidatos automaticos como quarentena.
- `src/core/item_attention_store.py`
  - registra origem de nota e origem de validacao;
  - bloqueia `validation_origin='cli'` e similares em validacao humana.
- `src/ui/modules/comparison_engine.py`
  - clique humano da UI chama validacao com `validation_origin="human_ui"`.

## Criterios de aceite
- Um looper pode registrar candidato, score e evidencias.
- Um looper nao consegue marcar `human_validated=1`.
- Um looper nao consegue promover T1/T2.
- Um looper nao consegue tombstonar/desvalidar como humano.
- A UI humana continua podendo validar e desvalidar explicitamente.
- Consultas RAG globais continuam filtrando T1+ e ignorando quarentena.

## Nao fazer
- Nao criar bypass para testes aceitarem `validation_origin='test'` como humano.
- Nao deixar origem ausente virar humano por default em scripts de lote.
- Nao indexar T0 para "ganhar volume".

## Validacao tecnica
- `python scripts\rag_tier.py --selftest`
- `python -m pytest tests\test_rag_tier_synthetic_guard.py tests\test_rag_validation_events.py`
- `python -m pytest tests\test_item_attention_store.py`
